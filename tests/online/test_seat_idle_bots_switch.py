"""POKER8_SEAT_IDLE_BOTS -- whether a bot may take a free seat beside a player.

On by default, and on everywhere now: it was held off while live testing
needed the seats next to a tester to stay free, and that cost a lone player
their game -- at a table whose one bot had left, nobody could ever arrive, so
the hand could not start and the seat was a dead end.

The switch is deliberately narrow and stays supported for that kind of
testing: only the arrival of new bots *at a table someone is sitting at* is
suppressed. An empty room still fills to its own count, or the lobby would
drain to nothing and there would be no five-player table to find a
five-player bug at. Whoever is already seated stays and keeps playing, and a
table over its count still sheds the extras, because the removals run before
this point.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import insert, select

from online.catalogue import IDLE_BOT_COUNTS, Catalogue
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


async def _seat_user(session_factory, table_id, seat_no):
    """Seat rows exist only for seats somebody holds, so a person sitting
    down is a new row rather than an empty one changing hands."""
    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id=f"{table_id}-u{seat_no}", table_id=table_id, seat_no=seat_no,
            occupant_kind="user", user_id="u1", stack_units=10_000, state="seated"))
        await session.commit()


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


def test_no_deployment_holds_bots_off_by_default():
    """A lone player at a table whose only bot has left can never start a
    hand: two seats are the minimum, and with arrivals suppressed nobody can
    ever be the second. Overriding the switch stays possible; defaulting to
    it does not."""
    for name in ("compose.server.yaml", "compose.pilot.yaml"):
        compose = Path(name).read_text(encoding="utf-8")
        assert "POKER8_SEAT_IDLE_BOTS:-0" not in compose, name


@pytest.mark.anyio
async def test_no_bot_takes_a_free_seat_beside_a_player(lobby):
    """micro-a holds one bot. Seat a person, drop the bot, and no
    replacement arrives to take the seat next to them."""
    ledger, session_factory = lobby
    off = SeatingService(session_factory, ledger, seat_idle_bots=False)
    await _seat_user(session_factory, "micro-a", seat_no=0)
    await off.process_boundary("micro-a", now=START)
    assert await _bots(session_factory, "micro-a") == 0


@pytest.mark.anyio
async def test_a_lone_player_gets_someone_to_play_against(lobby):
    """The switch off left this table a dead end: one person, no bot, and a
    hand needs two seats. With arrivals allowed, micro-a refills to its own
    count beside them and the table can deal."""
    ledger, session_factory = lobby
    await _seat_user(session_factory, "micro-a", seat_no=0)
    await SeatingService(session_factory, ledger).process_boundary("micro-a", now=START)
    assert await _bots(session_factory, "micro-a") == IDLE_BOT_COUNTS["micro-a"]


@pytest.mark.anyio
async def test_an_empty_room_still_fills_to_its_own_count(lobby):
    """The lobby's shop window, and the reason the switch is not a freeze:
    each room holds its configured number so a layout can be checked at
    every player count from one to six."""
    ledger, session_factory = lobby
    off = SeatingService(session_factory, ledger, seat_idle_bots=False)
    for table_id, expected in IDLE_BOT_COUNTS.items():
        await off.process_boundary(table_id, now=START)
        assert await _bots(session_factory, table_id) == expected, table_id


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
