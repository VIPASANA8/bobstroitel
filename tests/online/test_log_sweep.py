"""Two logs grew with every hand and nothing ever removed a row from either."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, insert, select

from online.catalogue import Catalogue
from online.coordinator import (
    COMMAND_LOG_TTL,
    EVENT_LOG_TTL,
    LOG_SWEEP_BATCH,
    LOG_SWEEP_EVERY,
    NOISY_EVENT_TYPES,
    OnlineCoordinator,
)
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import game_commands, integrity_events, poker_tables, tenants
from online.seating import SeatingService


class _Clock:
    def __init__(self, start): self.current = start
    def __call__(self): return self.current
    def advance(self, delta): self.current += delta


@pytest.fixture
def swept(db_session_factory):
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)

    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6))
            await session.execute(insert(game_commands), [
                {"table_id": "t1", "command_id": f"old-{i}", "expected_revision": i,
                 "command_type": "action", "payload_json": {}, "status": "accepted",
                 "result_json": {}, "created_at": now - COMMAND_LOG_TTL - timedelta(hours=1)}
                for i in range(5)
            ] + [
                {"table_id": "t1", "command_id": "fresh", "expected_revision": 99,
                 "command_type": "action", "payload_json": {}, "status": "accepted",
                 "result_json": {}, "created_at": now - timedelta(minutes=5)},
            ])
            await session.execute(insert(integrity_events), [
                {"id": f"noise-{i}", "event_type": NOISY_EVENT_TYPES[i % len(NOISY_EVENT_TYPES)],
                 "public_payload_json": {}, "created_at": now - EVENT_LOG_TTL - timedelta(days=1)}
                for i in range(4)
            ] + [
                {"id": "audit", "event_type": "escrow_stack_mismatch",
                 "public_payload_json": {"table_id": "t1"},
                 "created_at": now - EVENT_LOG_TTL - timedelta(days=30)},
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    clock = _Clock(now)
    runtime = TableRuntimeManager(db_session_factory, ledger, now=clock)
    coordinator = OnlineCoordinator(
        runtime, SeatingService(db_session_factory, ledger),
        Catalogue(db_session_factory), interval_seconds=0)
    return coordinator, clock, db_session_factory


async def _count(session_factory, table, **where):
    async with session_factory() as session:
        query = select(func.count()).select_from(table)
        for column, value in where.items():
            query = query.where(table.c[column] == value)
        return (await session.execute(query)).scalar_one()


@pytest.mark.anyio
async def test_a_command_nobody_can_replay_is_removed(swept):
    """game_commands exists to recognise a command_id that arrives twice, which
    only happens when a client retries. A day-old one never will be."""
    coordinator, clock, session_factory = swept

    await coordinator._sweep_logs()

    assert await _count(session_factory, game_commands, command_id="fresh") == 1
    assert await _count(session_factory, game_commands) == 1, "the stale ones went"


@pytest.mark.anyio
async def test_the_money_trail_is_never_swept(swept):
    """Escrow findings are the audit trail; only the volume goes."""
    coordinator, clock, session_factory = swept

    await coordinator._sweep_logs()

    assert await _count(session_factory, integrity_events, id="audit") == 1, \
        "a thirty-day-old escrow finding was deleted"
    assert await _count(session_factory, integrity_events) == 1, "the noise went"


@pytest.mark.anyio
async def test_it_runs_rarely_and_takes_a_bounded_bite(swept):
    """The first sweep of a database that has never been swept has a million
    rows to get through, and one statement that size holds locks for its
    length."""
    coordinator, clock, session_factory = swept
    assert LOG_SWEEP_BATCH <= 20000
    assert LOG_SWEEP_EVERY >= timedelta(minutes=5)

    await coordinator._sweep_logs()
    remaining = await _count(session_factory, game_commands)

    # A second call in the same window must do nothing at all.
    async with session_factory() as session:
        await session.execute(insert(game_commands).values(
            table_id="t1", command_id="another-old", expected_revision=7,
            command_type="action", payload_json={}, status="accepted", result_json={},
            created_at=clock.current - COMMAND_LOG_TTL - timedelta(hours=2)))
        await session.commit()
    await coordinator._sweep_logs()
    assert await _count(session_factory, game_commands) == remaining + 1

    clock.advance(LOG_SWEEP_EVERY + timedelta(minutes=1))
    await coordinator._sweep_logs()
    assert await _count(session_factory, game_commands) == remaining


@pytest.mark.anyio
async def test_housekeeping_never_stops_a_table(swept):
    """A sweep that fails must not take the tick with it."""
    coordinator, clock, session_factory = swept

    class _Boom:
        def __call__(self, *args, **kwargs):
            raise RuntimeError("no database today")

    coordinator.runtime.session_factory = _Boom()
    await coordinator._sweep_logs()  # must not raise
