import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import insert, select
from types import SimpleNamespace

from online.catalogue import CASH_MOCK_TABLE, CASH_USDT, PLAY, Catalogue, RoomError
from online.integrity import EscrowIntegrityMonitor
from online.ledger import PlayLedger
from online.schema import integrity_events, poker_tables, system_players, table_seats, tenants, users
from online.seating import CashRuntimeUnavailable, SeatingService
from online.runtime import RuntimeErrorBase, TableRuntimeManager
from app.dependencies import AuthenticatedUser, require_play_table_user
from app.routers import chat
from app.routers.lobby import CreateRoomRequest, create_room, current_lobby_session
from app.routers.profiles import _profile


@pytest.fixture
def table_services(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
            await session.execute(insert(system_players).values(
                id="bot-1", name="Bot", difficulty="normal", active=True))
            await session.commit()
    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    return Catalogue(db_session_factory), SeatingService(db_session_factory, ledger), db_session_factory


@pytest.mark.anyio
async def test_default_catalogue_is_exactly_six_play_tables(table_services):
    catalogue, _, _ = table_services
    await catalogue.seed_defaults()
    rows = await catalogue.list_tables(per_page=100)
    assert [row.id for row in rows] == ["micro-a", "micro-b", "low-a", "low-b", "mid-a", "mid-b"]
    assert all(row.asset == PLAY for row in rows)


@pytest.mark.anyio
async def test_mock_seed_adds_one_idempotent_cash_table(table_services):
    catalogue, _, _ = table_services
    await catalogue.seed_cash_mock()
    await catalogue.seed_cash_mock()
    rows = await catalogue.list_tables(per_page=100, asset=CASH_USDT)
    assert [row.id for row in rows] == [CASH_MOCK_TABLE["id"]]
    assert rows[0].min_buy_in_micros == 800_000
    assert rows[0].max_buy_in_micros == 2_000_000


@pytest.mark.anyio
async def test_catalogue_never_crosses_asset_boundaries(table_services):
    catalogue, _, factory = table_services
    await catalogue.seed_defaults()
    async with factory() as session:
        await session.execute(insert(poker_tables).values(
            id="cash-test", scope="network", asset=CASH_USDT, name="Cash Test",
            small_blind_units=1, big_blind_units=2,
            small_blind_micros=10_000, big_blind_micros=20_000, chip_micros=10_000,
            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
        ))
        await session.commit()
    assert "cash-test" not in {row.id for row in await catalogue.list_tables(per_page=100)}
    cash = await catalogue.list_tables(per_page=100, asset=CASH_USDT)
    assert [row.id for row in cash] == ["cash-test"]
    assert (await catalogue.quick_play("u1", 100_000)).asset == PLAY
    assert (await catalogue.quick_play("u1", 1_000_000, asset=CASH_USDT)).id == "cash-test"
    with pytest.raises(ValueError, match="asset"):
        await catalogue.list_tables(asset="USDT")


@pytest.mark.anyio
async def test_play_seating_and_bots_refuse_cash_table(table_services):
    _, seating, factory = table_services
    async with factory() as session:
        await session.execute(insert(poker_tables).values(
            id="cash-test", scope="network", asset=CASH_USDT, name="Cash Test",
            small_blind_units=1_000, big_blind_units=2_000,
            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
        ))
        await session.commit()
    with pytest.raises(CashRuntimeUnavailable):
        await seating.ready("u1", "cash-test", 0, 80_000)
    with pytest.raises(CashRuntimeUnavailable):
        await seating.process_boundary("cash-test")
    async with factory() as session:
        assert await session.scalar(select(table_seats.c.id).where(table_seats.c.table_id == "cash-test")) is None


@pytest.mark.anyio
async def test_shared_table_routes_gate_cash_direct_ids_by_mode(table_services):
    _, _, factory = table_services
    async with factory() as session:
        await session.execute(insert(poker_tables).values(
            id="cash-test", scope="network", asset=CASH_USDT, name="Cash Test",
            small_blind_units=1_000, big_blind_units=2_000,
            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
        ))
        await session.commit()
    user = AuthenticatedUser("u1", "tenant", 1, "A", "dev")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        session_factory=factory, settings=SimpleNamespace(cash_mode="off"),
    )))
    with pytest.raises(HTTPException) as off:
        await require_play_table_user("cash-test", request, user)
    assert off.value.status_code == 404
    request.app.state.settings.cash_mode = "mock"
    assert await require_play_table_user("cash-test", request, user) == user


@pytest.mark.anyio
async def test_play_runtime_refuses_to_start_cash_hand(table_services):
    _, _, factory = table_services
    async with factory() as session:
        await session.execute(insert(poker_tables).values(
            id="cash-test", scope="network", asset=CASH_USDT, name="Cash Test",
            small_blind_units=1_000, big_blind_units=2_000,
            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
        ))
        await session.commit()
    runtime = TableRuntimeManager(factory, PlayLedger(factory))
    with pytest.raises(RuntimeErrorBase, match="CASH runtime"):
        await runtime.start_hand("cash-test")


@pytest.mark.anyio
async def test_play_startup_does_not_hold_cash_seats(table_services):
    _, seating, factory = table_services
    async with factory() as session:
        await session.execute(insert(poker_tables).values(
            id="cash-test", scope="network", asset=CASH_USDT, name="Cash Test",
            small_blind_units=1_000, big_blind_units=2_000,
            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
        ))
        await session.execute(insert(table_seats).values(
            id="cash-seat", table_id="cash-test", seat_no=0,
            occupant_kind="user", user_id="u1", stack_units=10_000, state="seated",
        ))
        await session.commit()
    await seating.hold_all_users(datetime.now(timezone.utc))
    async with factory() as session:
        assert await session.scalar(select(table_seats.c.state).where(table_seats.c.id == "cash-seat")) == "seated"


@pytest.mark.anyio
async def test_play_room_management_refuses_cash_table(table_services):
    catalogue, seating, factory = table_services
    async with factory() as session:
        await session.execute(insert(poker_tables).values(
            id="cash-room", scope="tenant", asset=CASH_USDT, name="Cash Room",
            small_blind_units=1_000, big_blind_units=2_000,
            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6, created_by="u1",
        ))
        await session.commit()
    assert await catalogue.own_room("u1") is None
    with pytest.raises(RoomError, match="PLAY"):
        await catalogue.close_room("cash-room", "u1")
    with pytest.raises(CashRuntimeUnavailable):
        await seating.evict_table("cash-room")


@pytest.mark.anyio
async def test_play_integrity_monitor_ignores_cash_seats(table_services):
    _, _, factory = table_services
    async with factory() as session:
        await session.execute(insert(poker_tables).values(
            id="cash-test", scope="network", asset=CASH_USDT, name="Cash Test",
            small_blind_units=1_000, big_blind_units=2_000,
            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
        ))
        await session.execute(insert(table_seats).values(
            id="cash-seat", table_id="cash-test", seat_no=0,
            occupant_kind="user", user_id="u1", stack_units=10_000, state="seated",
        ))
        await session.commit()
    monitor = EscrowIntegrityMonitor(factory)
    assert await monitor.check() == []
    async with factory() as session:
        assert await session.scalar(select(integrity_events.c.id)) is None


@pytest.mark.anyio
async def test_play_lobby_session_ignores_cash_seat(table_services):
    _, _, factory = table_services
    async with factory() as session:
        await session.execute(insert(poker_tables).values(
            id="cash-test", scope="network", asset=CASH_USDT, name="Cash Test",
            small_blind_units=1_000, big_blind_units=2_000,
            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
        ))
        await session.execute(insert(table_seats).values(
            id="cash-seat", table_id="cash-test", seat_no=0,
            occupant_kind="user", user_id="u1", stack_units=10_000, state="seated",
        ))
        await session.commit()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=factory)))
    user = AuthenticatedUser("u1", "tenant", 1, "A", "telegram")
    assert await current_lobby_session(request, user) == {"session": None}


@pytest.mark.anyio
async def test_play_profile_ignores_cash_seat(table_services):
    _, _, factory = table_services
    async with factory() as session:
        await session.execute(insert(poker_tables).values(
            id="cash-test", scope="network", asset=CASH_USDT, name="Cash Test",
            small_blind_units=1_000, big_blind_units=2_000,
            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
        ))
        await session.execute(insert(table_seats).values(
            id="cash-seat", table_id="cash-test", seat_no=0,
            occupant_kind="user", user_id="u1", stack_units=10_000, state="seated",
        ))
        await session.commit()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        session_factory=factory, ledger=PlayLedger(factory),
    )))
    user = AuthenticatedUser("u1", "tenant", 1, "A", "telegram")
    result = await _profile(request, user)
    assert result["active_table_stack_units"] == 0
    assert result["active_table_id"] is None


def test_chat_routes_use_play_table_access_gate():
    routes = [route for route in chat.router.routes if isinstance(route, APIRoute)]
    assert len(routes) == 2
    assert all(
        any(dependency.call is require_play_table_user for dependency in route.dependant.dependencies)
        for route in routes
    )


@pytest.mark.anyio
async def test_new_play_rooms_are_disabled_by_default():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        settings=SimpleNamespace(legacy_play_rooms_enabled=False),
    )))
    user = AuthenticatedUser("u1", "tenant", 1, "A", "telegram")
    with pytest.raises(HTTPException) as refusal:
        await create_room(CreateRoomRequest(name="Old PLAY room", level="micro"), request, user)
    assert refusal.value.status_code == 409
    assert refusal.value.detail["code"] == "cash_runtime_pending"
