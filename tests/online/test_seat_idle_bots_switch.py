"""TEMPORARY -- bots do not take free seats on the server right now.

Turned off while live testing needs the free seats to stay free. It is
deliberately narrow: only the *arrival* of new bots is suppressed. Whoever
is already seated stays and keeps playing, and a table that is over its
count still sheds the extras, because the removals run before this point.

**Restore before the MVP release**: delete `POKER8_SEAT_IDLE_BOTS` from
compose.server.yaml. Nothing else has to change -- the setting defaults to
on, which is why every other test in this suite still seats bots normally.
This file exists as much to make that deletion hard to forget as to check
the behaviour.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import insert, select

from online.catalogue import Catalogue
from online.config import Settings
from online.ledger import PlayLedger
from online.schema import table_seats, tenants, users
from online.seating import SeatingService

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def lobby(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    asyncio.run(Catalogue(db_session_factory).seed_defaults())
    return ledger, db_session_factory


async def _bots(session_factory, table_id):
    async with session_factory() as session:
        return len((await session.execute(
            select(table_seats.c.id).where(
                table_seats.c.table_id == table_id,
                table_seats.c.occupant_kind == "system",
                table_seats.c.state == "seated")
        )).scalars().all())


def test_the_switch_defaults_to_on():
    """So tests and local runs behave as they always did, and restoring it
    on the server is a deletion rather than an edit."""
    assert Settings.from_mapping({}).seat_idle_bots is True
    assert Settings.from_mapping({"POKER8_SEAT_IDLE_BOTS": "0"}).seat_idle_bots is False


def test_the_server_currently_has_it_off():
    """Delete that line at MVP and this test goes with it."""
    compose = Path("compose.server.yaml").read_text(encoding="utf-8")
    assert "POKER8_SEAT_IDLE_BOTS: ${POKER8_SEAT_IDLE_BOTS:-0}" in compose


@pytest.mark.anyio
async def test_no_bot_takes_a_free_seat_while_it_is_off(lobby):
    ledger, session_factory = lobby
    seating = SeatingService(session_factory, ledger, seat_idle_bots=False)
    await seating.process_boundary("mid-b", now=START)
    assert await _bots(session_factory, "mid-b") == 0


@pytest.mark.anyio
async def test_bots_already_seated_are_left_alone(lobby):
    """The switch stops arrivals; it must not evict anyone. Seated first with
    the switch on, then a boundary runs with it off."""
    ledger, session_factory = lobby
    await SeatingService(session_factory, ledger).process_boundary("mid-b", now=START)
    assert await _bots(session_factory, "mid-b") == 6

    await SeatingService(session_factory, ledger, seat_idle_bots=False).process_boundary("mid-b", now=START)
    assert await _bots(session_factory, "mid-b") == 6


@pytest.mark.anyio
async def test_a_table_over_its_count_still_sheds_bots(lobby):
    """Removals run before the switch is consulted, so a table that should
    hold fewer bots still lets them go."""
    ledger, session_factory = lobby
    await SeatingService(session_factory, ledger).process_boundary("mid-b", now=START)
    assert await _bots(session_factory, "mid-b") == 6

    # micro-a's own count is 1; seat it full first, then let it rebalance.
    off = SeatingService(session_factory, ledger, seat_idle_bots=False)
    await SeatingService(session_factory, ledger).process_boundary("micro-a", now=START)
    await off.process_boundary("micro-a", now=START)
    assert await _bots(session_factory, "micro-a") == 1
