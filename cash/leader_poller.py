from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timezone

import httpx
from sqlalchemy import text


DEFAULT_RETRY_SECONDS = 5.0
MAX_RETRY_SECONDS = 60.0


class PoisonedFeed(ValueError):
    """Content the loop must not skip past. It stops and waits for an operator."""


class LeaderPoller:
    """One process per database polls an outside source; the rest idle.

    Subclasses provide `poll()` and, if they have one, a `warm_up()`. Everything
    else -- the advisory lock that picks the leader, bounded backoff that
    honours an integer `Retry-After`, a stop that never interrupts a committed
    transaction, and the staleness a watchdog alerts on -- is the same problem
    whether the source is a P2P partner or a blockchain node.
    """

    lock_key = 0

    def __init__(self, sessions, *, idle_seconds: float = 1.0, now=None):
        self.sessions = sessions
        self.idle_seconds = idle_seconds
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.leader = False
        self.last_success_at: datetime | None = None
        self.last_error: str | None = None
        self.poisoned = False
        self._stop = asyncio.Event()
        self._leadership = AsyncExitStack()
        self._lock_session = None

    def stop(self) -> None:
        self._stop.set()

    async def poll(self) -> bool:
        """One round. Return True to come back immediately instead of idling."""
        raise NotImplementedError

    async def warm_up(self) -> None:
        """Optional once-per-leadership check. Failure here is noted, not fatal."""

    async def run(self) -> None:
        if not await self._acquire_leadership():
            return
        try:
            await self.warm_up()
            delay = 0.0
            while not self._stop.is_set() and not self.poisoned:
                if not await self._wait(delay):
                    break
                try:
                    more = await self.poll()
                except Exception as exc:  # the source or the database, never the ledger
                    delay = self._after_failure(exc, delay)
                    continue
                self.last_error = None
                self.last_success_at = self.now()
                delay = 0.0 if more else self.idle_seconds
        finally:
            await self._release_leadership()

    def _after_failure(self, exc: Exception, previous: float) -> float:
        self.last_error = repr(exc)
        if isinstance(exc, PoisonedFeed):
            # Hold the cursor where it is and let an operator look at the item.
            self.poisoned = True
            return 0.0
        return min(self._retry_after(exc) or max(2 * previous, DEFAULT_RETRY_SECONDS), MAX_RETRY_SECONDS)

    @staticmethod
    def _retry_after(exc: Exception) -> float | None:
        if not isinstance(exc, httpx.HTTPStatusError):
            return None
        header = exc.response.headers.get("retry-after", "").strip()
        return float(header) if header.isdigit() else None

    async def _wait(self, delay: float) -> bool:
        """Sleep, or return False as soon as a shutdown is asked for."""
        try:
            await asyncio.wait_for(self._stop.wait(), delay)
        except (asyncio.TimeoutError, TimeoutError):
            return True
        return False

    async def _acquire_leadership(self) -> bool:
        session = await self._leadership.enter_async_context(self.sessions())
        dialect = getattr(getattr(session, "bind", None), "dialect", None)
        if dialect is None or dialect.name != "postgresql":
            self.leader = True
        else:
            self.leader = bool(await session.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": self.lock_key},
            ))
            self._lock_session = session if self.leader else None
            if not self.leader:
                await self._leadership.aclose()
        return self.leader

    async def _release_leadership(self) -> None:
        self.leader = False
        if self._lock_session is not None:
            # A pooled connection keeps its advisory lock, so hand it back unlocked.
            await self._lock_session.scalar(
                text("SELECT pg_advisory_unlock(:key)"), {"key": self.lock_key},
            )
            self._lock_session = None
        await self._leadership.aclose()
