from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timezone

import httpx
from sqlalchemy import text

from cash.fiat_p2p import PartnerProtocolError


# CASE8 has no webhook, so one process long-polls /events for the whole
# deployment. The advisory lock picks that process; the others idle.
LEADER_LOCK_KEY = 8202609
DEFAULT_RETRY_SECONDS = 5.0
MAX_RETRY_SECONDS = 60.0


class FiatPoller:
    """Durable CASE8 long poll: one leader, bounded retries, visible staleness."""

    def __init__(self, service, *, idle_seconds: float = 1.0, now=None):
        self.service = service
        self.idle_seconds = idle_seconds
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.leader = False
        self.last_success_at: datetime | None = None
        self.last_error: str | None = None
        self.partner_fee = None
        self.poisoned = False
        self._stop = asyncio.Event()
        self._leadership = AsyncExitStack()
        self._lock_session = None

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        if not await self._acquire_leadership():
            return
        try:
            await self._health_check()
            delay = 0.0
            while not self._stop.is_set() and not self.poisoned:
                if not await self._wait(delay):
                    break
                try:
                    await self.service.poll_once()
                except Exception as exc:  # partner or database, never the ledger's word
                    delay = self._after_failure(exc, delay)
                    continue
                self.last_error = None
                self.last_success_at = self.now()
                delay = self.idle_seconds
        finally:
            await self._release_leadership()

    async def _health_check(self) -> None:
        try:
            self.partner_fee = (await self.service.partner.me()).get("Fee")
        except Exception as exc:
            # A partner that answers /events but not /me still deserves polling.
            self.last_error = f"/me unavailable: {exc!r}"

    def _after_failure(self, exc: Exception, previous: float) -> float:
        self.last_error = repr(exc)
        if isinstance(exc, PartnerProtocolError):
            # Poison event: hold the offset where it is and let an operator look.
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
        session = await self._leadership.enter_async_context(self.service.sessions())
        dialect = getattr(getattr(session, "bind", None), "dialect", None)
        if dialect is None or dialect.name != "postgresql":
            self.leader = True
        else:
            self.leader = bool(await session.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": LEADER_LOCK_KEY},
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
                text("SELECT pg_advisory_unlock(:key)"), {"key": LEADER_LOCK_KEY},
            )
            self._lock_session = None
        await self._leadership.aclose()
