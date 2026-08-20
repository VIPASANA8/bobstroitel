import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select, update

from online.ledger import PlayLedger
from online.schema import poker_tables, seat_queue, system_players, table_seats, tenants, users
from online.seating import MAX_SYSTEM_BOTS, READY_TTL, AlreadySeated, SeatingService


@pytest.fixture
def user_a():
    return "u1"


@pytest.fixture
def user_b():
    return "u2"


@pytest.fixture
def table_id():
    return "t1"


@pytest.fixture
def second_table_id():
    return "t2"


@pytest.fixture
def ledger(db_session_factory, user_a, user_b, table_id, second_table_id):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users), [
                {"id": user_a, "telegram_user_id": 1, "display_name": "A", "acquisition_tenant_id": "tenant"},
                {"id": user_b, "telegram_user_id": 2, "display_name": "B", "acquisition_tenant_id": "tenant"},
            ])
            await session.execute(insert(system_players), [
                {"id": f"bot-{index}", "name": f"Room Player {index}", "difficulty": "normal", "active": True}
                for index in range(1, 7)
            ])
            await session.execute(insert(poker_tables), [
                {"id": table_id, "scope": "network", "name": "One", "small_blind_units": 50,
                 "big_blind_units": 100, "min_buy_in_bb": 40, "max_buy_in_bb": 100, "max_seats": 6},
                {"id": second_table_id, "scope": "network", "name": "Two", "small_blind_units": 50,
                 "big_blind_units": 100, "min_buy_in_bb": 40, "max_buy_in_bb": 100, "max_seats": 6},
            ])
            await session.commit()

    asyncio.run(seed())
    service = PlayLedger(db_session_factory)
    asyncio.run(service.ensure_faucet())
    asyncio.run(service.grant(user_a, 100_000, "grant:u1"))
    asyncio.run(service.grant(user_b, 100_000, "grant:u2"))
    return service


@pytest.fixture
def seating(db_session_factory, ledger):
    return SeatingService(db_session_factory, ledger)


async def _seat_a_person(db_session_factory, table_id, user_id="u1", seat_no=0):
    """Bots only join a table that has somebody to play against, so a test
    about bots needs a person sitting there first."""
    async with db_session_factory() as session:
        await session.execute(insert(table_seats).values(
            id=f"seat-{table_id}-{seat_no}", table_id=table_id, seat_no=seat_no,
            occupant_kind="user", user_id=user_id, stack_units=10_000, state="seated"))
        await session.commit()


@pytest.mark.anyio
async def test_ready_appends_fifo_and_reserves_nothing(seating, ledger, user_a, table_id):
    request = await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    assert request.state == "waiting"
    assert await ledger.available_units(user_a) == 100_000


@pytest.mark.anyio
async def test_boundary_seats_both_requests_without_overfilling(seating, db_session_factory, table_id, user_a, user_b):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.ready(user_b, table_id, seat_no=2, buy_in_units=4_000)
    result = await seating.process_boundary(table_id)
    # FIFO: the first request wins seat 2, the second falls back to another seat.
    assert result.seated_user_ids == [user_a, user_b]
    # The table keeps a bounded number of bots, so both players fit on free
    # seats and no system player has to be evicted to make room.
    async with db_session_factory() as session:
        seats = (await session.execute(select(table_seats).where(
            table_seats.c.table_id == table_id, table_seats.c.state == "seated",
        ))).mappings().all()
    assert sum(1 for seat in seats if seat["occupant_kind"] == "system") <= MAX_SYSTEM_BOTS
    assert len(seats) <= 6


@pytest.mark.anyio
async def test_same_user_cannot_hold_two_network_seats(seating, user_a, table_id, second_table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    with pytest.raises(AlreadySeated):
        await seating.ready(user_a, second_table_id, seat_no=1, buy_in_units=4_000)


@pytest.mark.anyio
async def test_boundary_removes_zero_stack_user_so_they_can_rejoin(seating, db_session_factory, user_a, table_id, second_table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    async with db_session_factory() as session:
        async with session.begin():
            await session.execute(
                update(table_seats)
                .where(table_seats.c.table_id == table_id, table_seats.c.user_id == user_a)
                .values(stack_units=0, state="held")
            )

    await seating.process_boundary(table_id)

    async with db_session_factory() as session:
        row = (await session.execute(
            select(table_seats.c.state, table_seats.c.user_id)
            .where(table_seats.c.table_id == table_id, table_seats.c.seat_no == 2)
        )).mappings().one()
    assert row["user_id"] is None
    assert (await seating.ready(user_a, second_table_id, seat_no=1, buy_in_units=4_000)).state == "waiting"


async def seat_states(session_factory, user_id):
    async with session_factory() as session:
        return (
            await session.execute(select(table_seats.c.state).where(table_seats.c.user_id == user_id))
        ).scalars().all()


@pytest.mark.anyio
async def test_boundary_releases_a_seat_whose_hold_expired(seating, db_session_factory, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    now = datetime.now(timezone.utc)
    await seating.mark_disconnected(user_a, table_id, now - timedelta(minutes=5))

    await seating.process_boundary(table_id, now=now)

    assert await seat_states(db_session_factory, user_a) == []


@pytest.mark.anyio
async def test_disconnect_does_not_undo_a_pending_leave(seating, db_session_factory, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    await seating.request_leave(user_a, table_id)
    await seating.mark_disconnected(user_a, table_id, datetime.now(timezone.utc))

    assert await seat_states(db_session_factory, user_a) == ["leaving"]


@pytest.mark.anyio
async def test_user_can_sit_down_again_after_leaving(seating, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    await seating.request_leave(user_a, table_id)
    await seating.process_boundary(table_id)

    request = await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)

    assert request.state == "waiting"


@pytest.mark.anyio
async def test_ready_request_outlives_a_running_hand(seating, db_session_factory, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    boundary = datetime.now(timezone.utc) + READY_TTL - timedelta(seconds=1)

    await seating.process_boundary(table_id, now=boundary)

    async with db_session_factory() as session:
        assert (await session.execute(select(seat_queue.c.state))).scalars().all() == ["seated"]


@pytest.mark.anyio
async def test_request_for_a_taken_seat_falls_back(seating, db_session_factory, user_a, user_b, table_id):
    await seating.ready(user_b, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)

    result = await seating.process_boundary(table_id)

    assert result.seated_user_ids == [user_a]
    assert await seat_states(db_session_factory, user_a) == ["seated"]


@pytest.mark.anyio
async def test_restart_holds_seats_so_they_can_be_released(seating, db_session_factory, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    now = datetime.now(timezone.utc)

    await seating.hold_all_users(now)
    await seating.process_boundary(table_id, now=now + timedelta(minutes=1))

    assert await seat_states(db_session_factory, user_a) == []


@pytest.mark.anyio
async def test_blocked_ready_reports_where_the_user_is_seated(seating, user_a, table_id, second_table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)

    with pytest.raises(AlreadySeated) as error:
        await seating.ready(user_a, second_table_id, seat_no=1, buy_in_units=4_000)

    assert error.value.table_id == table_id
    assert error.value.seat_state == "seated"


@pytest.mark.anyio
async def test_releasing_a_seat_retires_its_queue_row(seating, db_session_factory, user_a, table_id):
    """A seat row and its queue row describe one seat, so they have to be
    released together. Leaving only the queue row at "seated" turns the user
    into a ghost: no seat row, so the table API reports them a spectator and
    the client hides every action control, while the queue still claims the
    seat is theirs."""
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    await seating.request_leave(user_a, table_id)
    await seating.process_boundary(table_id)

    async with db_session_factory() as session:
        queue_state = (
            await session.execute(select(seat_queue.c.state).where(seat_queue.c.user_id == user_a))
        ).scalar_one()
    assert queue_state != "seated"


@pytest.mark.anyio
async def test_an_unaffordable_buy_in_is_refused_up_front(seating, db_session_factory, user_a, table_id):
    """The boundary cancels an unaffordable request silently and moves on, so
    the player watched their request be accepted and then vanish a few seconds
    later with no reason given. Refuse it at the point of asking instead, and
    carry both numbers so the client can say how far short they are.

    2_495 is what the player who reported this actually had: below the table's
    40 BB minimum of 4_000, and so below every table in the network."""
    from online.schema import play_accounts
    from online.seating import InsufficientFunds

    async with db_session_factory() as session:
        await session.execute(
            update(play_accounts)
            .where(
                play_accounts.c.owner_kind == "user",
                play_accounts.c.owner_id == user_a,
                play_accounts.c.account_kind == "wallet",
            )
            .values(balance_units=2_495)
        )
        await session.commit()

    with pytest.raises(InsufficientFunds) as caught:
        await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)

    assert caught.value.required_units == 4_000
    assert caught.value.available_units == 2_495

    # Nothing was queued, so no request can later disappear on its own.
    async with db_session_factory() as session:
        rows = (await session.execute(select(seat_queue.c.state))).scalars().all()
    assert "waiting" not in rows


@pytest.mark.anyio
async def test_releasing_the_same_seat_twice_drains_the_escrow_both_times(
    seating, ledger, db_session_factory, table_id
):
    """Seat rows are reused -- _clear_seat blanks a row instead of deleting it --
    so a release key built from the row id repeated on every later release of
    that seat. The ledger then treated it as the first one, already posted, and
    the bot's escrow was simply never drained again: production shows 7012
    funding grants against 75 returns."""
    from online.schema import play_accounts

    async def bot_escrow(system_player_id: str) -> int:
        async with db_session_factory() as session:
            return (await session.execute(
                select(play_accounts.c.balance_units).where(
                    play_accounts.c.owner_kind == "system",
                    play_accounts.c.owner_id == system_player_id,
                    play_accounts.c.account_kind == "escrow",
                )
            )).scalar_one_or_none() or 0

    # Two full cycles of the same seat row: fill, then clear it out again.
    await _seat_a_person(db_session_factory, table_id)
    await seating.process_boundary(table_id)
    async with db_session_factory() as session:
        seated = (await session.execute(
            select(table_seats).where(
                table_seats.c.table_id == table_id,
                table_seats.c.occupant_kind == "system",
            )
        )).mappings().all()
    assert seated, "boundary should have seated bots"

    for row in seated:
        assert await bot_escrow(row["system_player_id"]) > 0
        await seating.ledger.release_system_seat(
            row["system_player_id"], table_id, f"release:{row['id']}:{row['system_player_id']}:first"
        )
        assert await bot_escrow(row["system_player_id"]) == 0

        # Fund it again, exactly as a re-seating would, then release once more.
        await seating.ledger.fund_system_seat(
            row["system_player_id"], table_id, 4_000, f"refund:{row['id']}:{row['system_player_id']}"
        )
        assert await bot_escrow(row["system_player_id"]) == 4_000
        await seating.ledger.release_system_seat(
            row["system_player_id"], table_id, f"release:{row['id']}:{row['system_player_id']}:second"
        )
        assert await bot_escrow(row["system_player_id"]) == 0, "second release must move money too"


def test_system_seat_release_keys_are_unique_per_release():
    from pathlib import Path

    source = Path("online/seating.py").read_text(encoding="utf-8")
    assert 'f"release:{row[\'id\']}:{row[\'system_player_id\']}:{uuid.uuid4().hex}"' in source
    assert 'f"rebalance:{row[\'id\']}:{uuid.uuid4().hex}"' in source


@pytest.mark.anyio
async def test_leaving_the_same_seat_twice_returns_the_stack_both_times(
    seating, ledger, db_session_factory, user_a, table_id
):
    """Seat rows are reused, so a return key built from the row id repeated the
    second time the same player left the same seat -- and the ledger took it for
    the first return already posted, leaving their stack in the table escrow.
    Unlike the bot case this is player money: production showed 59 buy-ins
    against 16 returns."""
    start = await ledger.available_units(user_a)

    for _ in range(2):
        await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
        await seating.process_boundary(table_id)
        assert await ledger.available_units(user_a) == start - 4_000
        await seating.request_leave(user_a, table_id)
        await seating.process_boundary(table_id)
        # Both departures have to put the stack back, not just the first.
        assert await ledger.available_units(user_a) == start


def test_user_stack_return_keys_are_unique_per_departure():
    from pathlib import Path

    source = Path("online/seating.py").read_text(encoding="utf-8")
    assert 'f"return:{row[\'id\']}:{row[\'user_id\']}:{uuid.uuid4().hex}"' in source


@pytest.mark.anyio
async def test_a_second_add_on_moves_money_and_does_not_mint_chips(
    seating, ledger, db_session_factory, user_a, table_id
):
    """The add-on key used to be static for a (user, table, seat row), and seat
    rows are reused -- so every add-on after the first was taken for a repeat of
    it and moved no money, while stack_units is added to unconditionally. That
    mints chips: the seat grows and nothing leaves the wallet. Never fired in
    production only because nobody had used add-on yet."""
    from online.schema import play_accounts

    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    start_wallet = await ledger.available_units(user_a)

    async def seat_stack() -> int:
        async with db_session_factory() as session:
            return (await session.execute(
                select(table_seats.c.stack_units).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.user_id == user_a,
                )
            )).scalar_one()

    async def table_escrow() -> int:
        async with db_session_factory() as session:
            return (await session.execute(
                select(play_accounts.c.balance_units).where(
                    play_accounts.c.owner_kind == "table",
                    play_accounts.c.owner_id == table_id,
                    play_accounts.c.account_kind == "escrow",
                )
            )).scalar_one()

    before_stack, before_escrow = await seat_stack(), await table_escrow()
    await seating.add_on(user_a, table_id, 1_000, "req-1")
    await seating.add_on(user_a, table_id, 1_000, "req-2")

    # Both add-ons: chips arrive on the seat and leave the wallet, and the table
    # escrow backs every chip sitting on it.
    assert await seat_stack() == before_stack + 2_000
    assert await ledger.available_units(user_a) == start_wallet - 2_000
    assert await table_escrow() == before_escrow + 2_000

    # A retry of the same request changes nothing at all -- not the wallet, and
    # not the seat either. Guarding only the ledger call would leave the stack
    # growing against money that never moved: the same minting, another route.
    await seating.add_on(user_a, table_id, 1_000, "req-2")
    assert await ledger.available_units(user_a) == start_wallet - 2_000
    assert await seat_stack() == before_stack + 2_000
    assert await table_escrow() == before_escrow + 2_000


@pytest.mark.anyio
async def test_a_bot_is_held_to_the_same_ceiling_as_a_player(
    seating, db_session_factory, table_id
):
    """max_buy_in_bb bounds what a person may bring, but nothing bounded a bot:
    it keeps everything it wins and is funded afresh on every seating. On
    production one sat on 1250x the table maximum. The excess goes back to the
    faucet, the seat is trimmed with it, and escrow follows the seat."""
    from online.schema import play_accounts

    await _seat_a_person(db_session_factory, table_id)
    await seating.process_boundary(table_id)
    async with db_session_factory() as session:
        bot = (await session.execute(
            select(table_seats).where(
                table_seats.c.table_id == table_id,
                table_seats.c.occupant_kind == "system",
            ).limit(1)
        )).mappings().first()
        table = (await session.execute(
            select(poker_tables).where(poker_tables.c.id == table_id)
        )).mappings().one()
    ceiling = table["big_blind_units"] * table["max_buy_in_bb"]

    # Let it win far past what any player could bring, on both sides of the books.
    async with db_session_factory() as session:
        await session.execute(
            update(table_seats).where(table_seats.c.id == bot["id"]).values(stack_units=ceiling * 50)
        )
        await session.commit()
    await seating.ledger.fund_system_seat(
        bot["system_player_id"], table_id, ceiling * 50 - bot["stack_units"], "windfall"
    )

    await seating.process_boundary(table_id)

    async with db_session_factory() as session:
        stack = (await session.execute(
            select(table_seats.c.stack_units).where(table_seats.c.id == bot["id"])
        )).scalar_one()
        escrow = (await session.execute(
            select(play_accounts.c.balance_units).where(
                play_accounts.c.owner_kind == "system",
                play_accounts.c.owner_id == bot["system_player_id"],
                play_accounts.c.account_kind == "escrow",
            )
        )).scalar_one()

    assert stack == ceiling, "the seat is trimmed to the table's own ceiling"
    assert escrow == ceiling, "and the books follow the seat, not the other way round"


@pytest.mark.anyio
async def test_bots_rotate_off_the_table_each_on_its_own_clock(seating, db_session_factory, table_id):
    """Without rotation a bot leaves only by going broke or being rebalanced
    away, so the same names sit at one table indefinitely. Each gets its own
    moment inside the band, which is what keeps them from standing up together."""
    from online.seating import BOT_ROTATE_BAND, MIN_SYSTEM_BOTS

    # First boundary seats the bots; the next one is where they are first seen
    # and given their moment, since rotation runs ahead of the leave pipeline.
    await _seat_a_person(db_session_factory, table_id)
    await seating.process_boundary(table_id)
    await seating.process_boundary(table_id)
    due = dict(seating._bot_rotate_at)
    assert len(due) >= MIN_SYSTEM_BOTS, "every seated bot gets a moment on first sight"
    assert len(set(due.values())) == len(due), "and no two share it"

    low, high = BOT_ROTATE_BAND
    base = min(due.values()) - low
    for when in due.values():
        assert low <= when - base <= high

    # Nobody leaves early.
    async with db_session_factory() as session:
        before = (await session.execute(
            select(table_seats.c.system_player_id).where(
                table_seats.c.table_id == table_id,
                table_seats.c.occupant_kind == "system",
                table_seats.c.state == "seated",
            )
        )).scalars().all()
    await seating.process_boundary(table_id, now=datetime.now(timezone.utc) + timedelta(minutes=1))
    async with db_session_factory() as session:
        still = (await session.execute(
            select(table_seats.c.system_player_id).where(
                table_seats.c.table_id == table_id,
                table_seats.c.occupant_kind == "system",
                table_seats.c.state == "seated",
            )
        )).scalars().all()
    assert set(still) == set(before)

    # Past the far end of the band every one of them has got up. Which bots come
    # back is not the point and is not guaranteed -- with a small roster the same
    # ones may sit straight back down -- so what is asserted is that they really
    # left and were seated afresh, each funded again.
    from online.schema import play_transactions

    async def grants() -> int:
        async with db_session_factory() as session:
            return len((await session.execute(
                select(play_transactions.c.id).where(play_transactions.c.kind == "faucet_grant")
            )).scalars().all())

    before_grants = await grants()
    await seating.process_boundary(table_id, now=datetime.now(timezone.utc) + high + timedelta(minutes=1))

    async with db_session_factory() as session:
        after = (await session.execute(
            select(table_seats.c.system_player_id).where(
                table_seats.c.table_id == table_id,
                table_seats.c.occupant_kind == "system",
                table_seats.c.state == "seated",
            )
        )).scalars().all()
    assert await grants() >= before_grants + len(before), "every seated bot was replaced"
    assert len(after) >= MIN_SYSTEM_BOTS, "and the table stayed populated"
    assert not seating._bot_rotate_at.keys() & due.keys(), "spent moments are not reused"
