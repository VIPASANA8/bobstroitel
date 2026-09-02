from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from cash.amounts import micros_to_usdt
from cash.deposits import DepositService
from cash.leader_poller import PoisonedFeed
from cash.trc20_watcher import MAINNET_USDT, PAGE_SIZE, Trc20DepositWatcher
from cash.wallet import WalletService
from online.schema import cash_partner_cursors


pytestmark = pytest.mark.anyio

ADDRESS = "TPoker8DepositAddress11111111111111"
MOMENT = datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc)
MOMENT_MS = int(MOMENT.timestamp() * 1000)
FAKE_USDT = "TFakeUSDTContract1111111111111111111"


def transfer(**overrides):
    row = {
        "transaction_id": "a" * 64,
        "token_info": {"symbol": "USDT", "address": MAINNET_USDT, "decimals": 6},
        "block_timestamp": MOMENT_MS,
        "from": "TSender11111111111111111111111111111",
        "to": ADDRESS,
        "type": "Transfer",
        "value": "20010000",
    }
    row.update(overrides)
    return row


def watcher(sessions, pages, *, deposits=None, requests=None):
    """Serve the given pages in order; repeat the last one forever."""
    remaining = list(pages)

    def handler(request: httpx.Request):
        if requests is not None:
            requests.append(dict(request.url.params))
        page = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        return httpx.Response(200, json=page)

    service = deposits or SimpleNamespace(sessions=sessions, observe=None)
    return Trc20DepositWatcher(
        service, base_url="https://api.trongrid.io", address=ADDRESS,
        transport=httpx.MockTransport(handler),
    )


class Recorder:
    def __init__(self, sessions):
        self.sessions = sessions
        self.events = []

    async def observe(self, event):
        self.events.append(event)


async def test_a_confirmed_usdt_transfer_becomes_one_deposit_event(db_session_factory):
    recorder = Recorder(db_session_factory)
    requests = []
    watch = watcher(
        db_session_factory, [{"data": [transfer()]}, {"data": []}],
        deposits=recorder, requests=requests,
    )
    try:
        assert await watch.poll() is False
        await watch.poll()
    finally:
        await watch.close()

    event = recorder.events[0]
    assert len(recorder.events) == 1
    assert event.provider == "trc20-tron"
    assert event.external_event_id == "a" * 64 + ":0"
    assert event.amount_micros == 20_010_000
    assert event.token_contract == MAINNET_USDT
    assert event.destination_address == ADDRESS
    assert event.occurred_at == MOMENT
    event.validate()

    # Only confirmed transfers to this address and this contract are ever asked for.
    assert requests[0] == {
        "only_confirmed": "true", "only_to": "true", "contract_address": MAINNET_USDT,
        "min_timestamp": "0", "limit": str(PAGE_SIZE), "order_by": "block_timestamp,asc",
    }
    # The cursor is durable and inclusive, so a shared millisecond is not lost.
    async with db_session_factory() as session:
        assert await session.scalar(select(cash_partner_cursors.c.offset).where(
            cash_partner_cursors.c.provider == "trc20-tron",
        )) == MOMENT_MS
    assert requests[1]["min_timestamp"] == str(MOMENT_MS)


@pytest.mark.parametrize("row", [
    transfer(token_info={"symbol": "USDT", "address": FAKE_USDT, "decimals": 6}),
    transfer(token_info={"symbol": "USDT", "address": MAINNET_USDT, "decimals": 18}),
    transfer(to="TSomebodyElse111111111111111111111"),
    transfer(type="Approval"),
])
async def test_anything_that_is_not_our_usdt_is_counted_and_dropped(db_session_factory, row):
    recorder = Recorder(db_session_factory)
    watch = watcher(db_session_factory, [{"data": [row]}], deposits=recorder)
    try:
        await watch.poll()
    finally:
        await watch.close()

    assert recorder.events == []
    assert watch.ignored == 1


@pytest.mark.parametrize("page", [
    {"data": "not-a-list"},
    ["not-a-page"],
    {"data": [transfer(value="20.01")]},
    {"data": [transfer(block_timestamp="soon")]},
    {"data": [transfer(transaction_id=None)]},
])
async def test_an_unreadable_page_is_poison_and_stops_the_cursor(db_session_factory, page):
    recorder = Recorder(db_session_factory)
    watch = watcher(db_session_factory, [page], deposits=recorder)
    try:
        with pytest.raises(PoisonedFeed):
            await watch.poll()
        await watch.run()
    finally:
        await watch.close()

    assert watch.poisoned is True
    assert recorder.events == []
    async with db_session_factory() as session:
        assert await session.scalar(select(cash_partner_cursors.c.offset)) is None


async def test_two_transfers_in_one_transaction_stay_two_events(db_session_factory):
    recorder = Recorder(db_session_factory)
    watch = watcher(db_session_factory, [{"data": [transfer(), transfer(value="30000000")]}],
                    deposits=recorder)
    try:
        await watch.poll()
    finally:
        await watch.close()

    assert [event.external_event_id for event in recorder.events] == ["a" * 64 + ":0", "a" * 64 + ":1"]
    assert [event.amount_micros for event in recorder.events] == [20_010_000, 30_000_000]


async def test_a_full_page_comes_back_without_idling(db_session_factory):
    recorder = Recorder(db_session_factory)
    page = {"data": [transfer(transaction_id=f"{index:064x}") for index in range(PAGE_SIZE)]}
    watch = watcher(db_session_factory, [page], deposits=recorder)
    try:
        assert await watch.poll() is True
    finally:
        await watch.close()
    assert len(recorder.events) == PAGE_SIZE


async def test_the_endpoint_must_be_https(db_session_factory):
    with pytest.raises(ValueError, match="HTTPS"):
        Trc20DepositWatcher(
            SimpleNamespace(sessions=db_session_factory), base_url="http://api.trongrid.io",
            address=ADDRESS,
        )


@pytest.mark.postgres
async def test_a_watched_transfer_credits_its_deposit_and_a_fake_token_never_does(cash_db):
    deposits = DepositService(cash_db, address=ADDRESS, contract=MAINNET_USDT)
    deposit = await deposits.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="chain-1",
    )
    landed = int(deposit["created_at"].timestamp() * 1000) + 1_000
    paid = transfer(value=str(deposit["expected_micros"]), block_timestamp=landed)
    spoofed = transfer(
        transaction_id="b" * 64, value=str(deposit["expected_micros"]),
        block_timestamp=landed, token_info={"symbol": "USDT", "address": FAKE_USDT, "decimals": 6},
    )
    watch = watcher(cash_db, [{"data": [spoofed, paid]}], deposits=deposits)
    try:
        await watch.poll()
    finally:
        await watch.close()

    assert watch.ignored == 1
    assert (await deposits.get(deposit["id"], "alice"))["status"] == "credited"
    credited = micros_to_usdt(deposit["expected_micros"])
    assert (await WalletService(cash_db).get("alice"))["available_usdt"] == credited
