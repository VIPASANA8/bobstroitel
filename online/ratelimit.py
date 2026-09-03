"""A cap on how often one caller may knock on an unauthenticated door.

Only the login endpoints need this. Everything behind a session is already
bounded by rules that mean something -- one open RUB order, one live
withdrawal, a daily deposit ceiling -- and a request counter would add noise on
top of limits that already say no for a reason. `/api/auth/*` has none of that:
it is reachable by anyone, and every call costs a signature check and, on
success, a row in three tables.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimited(HTTPException):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            status_code=429, detail="too many attempts, try again shortly",
            headers={"Retry-After": str(max(1, retry_after))},
        )


class WindowLimiter:
    """Per-caller sliding window, held in memory.

    ponytail: in-process, so the count is per worker. The pilot runs a single
    uvicorn process, which makes that exact rather than approximate; the day it
    runs two, this needs to move to Redis or a table, and the limit silently
    doubles until it does.
    """

    def __init__(self, *, limit: int, seconds: int) -> None:
        if limit < 1 or seconds < 1:
            raise ValueError("a rate limit needs a positive count and window")
        self.limit = limit
        self.seconds = seconds
        self._seen: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        hits = self._seen[key]
        cutoff = now - self.seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.limit:
            raise RateLimited(int(hits[0] + self.seconds - now) + 1)
        hits.append(now)
        # Callers who stopped knocking stop costing memory. Cheap because it
        # only runs when somebody is at the door anyway.
        if len(self._seen) > 4096:
            for stale in [k for k, v in self._seen.items() if not v or v[-1] <= cutoff]:
                del self._seen[stale]


def caller(request: Request) -> str:
    """Who is knocking, as far as we can honestly tell.

    The **last** X-Forwarded-For entry, not the first. Everything to the left of
    it was written by whoever sent the request and can say anything; the last
    one was appended by the proxy immediately in front of us, which is the only
    party here that saw the connection itself. Caddy happens to replace the
    header outright today, which makes the two the same -- but then the limit
    would rest on a proxy setting rather than on this function, and a caller
    who could pick their own key would have no limit at all.

    Reading the header is still necessary: without it every request carries the
    proxy's own address, and one visitor throttles everybody at once.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.rsplit(",", 1)[-1].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]
