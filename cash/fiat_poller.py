from __future__ import annotations

from cash.fiat_p2p import PartnerProtocolError
from cash.leader_poller import (  # noqa: F401  (re-exported for the tests and callers)
    DEFAULT_RETRY_SECONDS, MAX_RETRY_SECONDS, LeaderPoller,
)


# pservice sends its completion webhook to CASE8's own backend, not to us, so
# one Poker8 process polls the status of its open orders for the whole
# deployment. The advisory lock picks that process; the others idle.
LEADER_LOCK_KEY = 8202609


class FiatPoller(LeaderPoller):
    """Durable CASE8 long poll: one leader, bounded retries, visible staleness."""

    lock_key = LEADER_LOCK_KEY

    def __init__(self, service, *, idle_seconds: float = 1.0, now=None):
        super().__init__(service.sessions, idle_seconds=idle_seconds, now=now)
        self.service = service
        self.partner_fee = None

    async def warm_up(self) -> None:
        try:
            self.partner_fee = (await self.service.partner.business()).get("fee")
        except Exception as exc:
            # A pservice that answers status but not /admin still deserves polling.
            self.last_error = f"business snapshot unavailable: {exc!r}"

    async def poll(self) -> bool:
        await self.service.poll_once()
        return False

    def _after_failure(self, exc: Exception, previous: float) -> float:
        if isinstance(exc, PartnerProtocolError):
            # An unknown or malformed event is poison: hold the offset where it
            # is, stop, and let an operator decide what it was.
            self.last_error = repr(exc)
            self.poisoned = True
            return 0.0
        return super()._after_failure(exc, previous)
