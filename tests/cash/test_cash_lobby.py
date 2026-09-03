from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.dependencies import AuthenticatedUser
from app.routers.cash import DepositRequest, create_deposit, simulate_deposit_transfer
from app.routers.lobby import current_lobby_session, list_lobby_tables, quick_play
from app.routers.tables import ReadyRequest, leave, ready, ready_up, table_snapshot
from cash.deposits import DepositService
from cash.game import CashGameService
from cash.wallet import WalletService
from online.catalogue import CASH_MOCK_TABLE, CASH_USDT, Catalogue
from online.schema import table_seats


class SeatLookup:
    def __init__(self, sessions):
        self.sessions = sessions

    async def user_seat_number(self, user_id, table_id):
        async with self.sessions() as session:
            return await session.scalar(select(table_seats.c.seat_no).where(
                table_seats.c.user_id == user_id,
                table_seats.c.table_id == table_id,
                table_seats.c.state == "seated",
            ))


@pytest.mark.postgres
@pytest.mark.anyio
async def test_public_cash_lobby_never_falls_back_to_play(cash_db):
    catalogue = Catalogue(cash_db)
    await catalogue.seed_cash_mock()
    state = SimpleNamespace(
        session_factory=cash_db,
        settings=SimpleNamespace(cash_mode="mock"),
        catalogue=catalogue,
        cash_game=CashGameService(cash_db),
        cash_deposits=DepositService(cash_db),
        cash_wallet=WalletService(cash_db),
        seating=SeatLookup(cash_db),
    )
    request = SimpleNamespace(app=SimpleNamespace(state=state))
    alice = AuthenticatedUser("alice", "tenant", 1, "Alice", "dev")
    bob = AuthenticatedUser("bob", "tenant", 2, "Bob", "dev")

    for user in (alice, bob):
        deposit = await create_deposit(
            DepositRequest(amount_usdt="5", request_id=f"deposit-{user.user_id}"),
            request, user,
        )
        credited = await simulate_deposit_transfer(deposit["id"], request, user)
        assert credited["status"] == "credited"

    listing = await list_lobby_tables(request, 1, 6, CASH_USDT, alice)
    assert [row["id"] for row in listing["tables"]] == [CASH_MOCK_TABLE["id"]]
    assert listing["tables"][0]["min_buy_in_micros"] == 4_000_000

    chosen = await quick_play(request, alice, CASH_USDT)
    assert chosen["table"]["asset"] == CASH_USDT
    assert chosen["table"]["id"] == CASH_MOCK_TABLE["id"]

    seated = await ready(
        CASH_MOCK_TABLE["id"],
        ReadyRequest(seat_no=0, buy_in_units=400, request_id="public-seat-alice"),
        request, alice,
    )
    assert seated["viewer_state"] == "seated"
    assert (await current_lobby_session(request, alice, CASH_USDT))["session"]["table_id"] == CASH_MOCK_TABLE["id"]
    snapshot = await table_snapshot(CASH_MOCK_TABLE["id"], request, alice)
    assert snapshot["table"]["asset"] == CASH_USDT
    assert snapshot["state"]["cash_test"] is True
    assert snapshot["state"]["current_seats"][0]["stack"] == 40  # 400 chips / 10 per BB

    await ready(
        CASH_MOCK_TABLE["id"],
        ReadyRequest(seat_no=1, buy_in_units=400, request_id="public-seat-bob"),
        request, bob,
    )
    active = await table_snapshot(CASH_MOCK_TABLE["id"], request, alice)
    assert active["state"]["phase"] == "active"
    assert active["state"]["occupancy"] == 2
    assert active["state"]["cash_test"] is True
    assert all(not player["is_bot"] for player in active["state"]["players"].values())

    acting_id = active["state"]["acting_player"]
    acting_user = alice if acting_id == "alice" else bob
    await leave(CASH_MOCK_TABLE["id"], request, acting_user)
    after_disconnect = await table_snapshot(CASH_MOCK_TABLE["id"], request, acting_user)
    assert after_disconnect["state"]["phase"] == "result"
    assert acting_id not in {
        seat["id"] for seat in after_disconnect["state"]["current_seats"].values()
    }
    with pytest.raises(HTTPException) as spectator_start:
        await ready_up(CASH_MOCK_TABLE["id"], request, acting_user)
    assert spectator_start.value.status_code == 409
