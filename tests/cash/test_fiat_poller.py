import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from cash.fiat_poller import MAX_RETRY_SECONDS, FiatPoller
from cash.fiat_p2p import PartnerProtocolError


pytestmark = pytest.mark.anyio


class FakePartner:
    def __init__(self, me=None):
        self._me = me

    async def me(self):
        if isinstance(self._me, Exception):
            raise self._me
        return self._me or {"Fee": 3}


class FakeService:
    """Only what the poller touches: a session factory, a partner and one poll."""

    def __init__(self, sessions, *, partner=None, outcomes=()):
        self.sessions = sessions
        self.partner = partner or FakePartner()
        self.outcomes = list(outcomes)
        self.polls = 0

    async def poll_once(self):
        self.polls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if isinstance(outcome, Exception):
            raise outcome
        return outcome or 0


def _status_error(status, headers=None):
    request = httpx.Request("GET", "https://partner.example/events")
    response = httpx.Response(status, headers=headers or {}, request=request)
    return httpx.HTTPStatusError("transient", request=request, response=response)


async def test_leader_polls_until_it_is_asked_to_stop(db_session_factory):
    service = FakeService(db_session_factory)
    poller = FiatPoller(service, idle_seconds=0)

    async def run():
        await poller.run()

    task = asyncio.create_task(run())
    while service.polls < 3:
        await asyncio.sleep(0)
    poller.stop()
    await asyncio.wait_for(task, 5)

    assert service.polls >= 3
    assert poller.last_success_at is not None and poller.last_error is None
    assert poller.partner_fee == 3
    assert poller.leader is False  # leadership is handed back on the way out


async def test_health_check_failure_never_stops_the_poll(db_session_factory):
    service = FakeService(db_session_factory, partner=FakePartner(httpx.ConnectError("down")))
    poller = FiatPoller(service, idle_seconds=0)

    task = asyncio.create_task(poller.run())
    while service.polls < 1:
        await asyncio.sleep(0)
    poller.stop()
    await asyncio.wait_for(task, 5)

    assert service.polls >= 1
    assert poller.last_error is None  # the successful poll cleared the /me note


async def test_a_poison_event_stops_the_loop_instead_of_skipping_the_offset(db_session_factory):
    service = FakeService(db_session_factory, outcomes=[PartnerProtocolError("unknown status")])
    poller = FiatPoller(service, idle_seconds=0)

    await asyncio.wait_for(poller.run(), 5)

    assert service.polls == 1
    assert poller.poisoned is True
    assert "unknown status" in poller.last_error
    assert poller.last_success_at is None


def test_transient_failures_back_off_and_respect_retry_after():
    poller = FiatPoller(FakeService(None))

    assert poller._after_failure(_status_error(429, {"Retry-After": "12"}), 0) == 12
    assert poller._after_failure(_status_error(503), 0) == 5
    assert poller._after_failure(_status_error(503), 5) == 10
    assert poller._after_failure(httpx.ReadTimeout("slow"), 40) == MAX_RETRY_SECONDS
    # A malformed Retry-After is a header, not a schedule.
    assert poller._after_failure(_status_error(429, {"Retry-After": "Wed, 21 Oct"}), 0) == 5
    assert poller.poisoned is False


@pytest.mark.postgres
async def test_only_one_process_polls_the_partner(cash_db):
    first = FiatPoller(FakeService(cash_db), idle_seconds=0)
    second = FiatPoller(FakeService(cash_db), idle_seconds=0)

    assert await first._acquire_leadership() is True
    assert await second._acquire_leadership() is False

    await first._release_leadership()
    assert await second._acquire_leadership() is True
    await second._release_leadership()
