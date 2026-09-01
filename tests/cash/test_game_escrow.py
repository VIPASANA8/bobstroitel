import pytest
from sqlalchemy import insert, select, update

from cash.game import CashGameService, CashIntegrityError, CashSeatError
from cash.ledger import CashLedger
from online.schema import (
    cash_accounts, cash_transactions, hands, poker_tables, system_players,
    table_runtimes, table_seats,
)
from poker.models import ActionType

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]


async def seed_cash_table(factory):
    async with factory() as session:
        async with session.begin():
            await session.execute(insert(poker_tables).values(
                id="cash-heads-up", scope="network", asset="CASH_USDT", name="Cash Heads-Up",
                small_blind_units=0, big_blind_units=0,
                small_blind_micros=10_000, big_blind_micros=20_000, chip_micros=10_000,
                min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))


async def fund(factory, user_wallet, amount, key):
    async with factory() as session:
        async with session.begin():
            await CashLedger().post(
                session, scope="cash-game-test", key=key, kind="deposit",
                reference_id=key, actor="test:fund",
                postings={"external": -amount, user_wallet: amount},
            )


async def balance(factory, account_id):
    async with factory() as session:
        return await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.id == account_id
        ))


async def active_seat(factory, user_id):
    async with factory() as session:
        return (
            await session.execute(select(table_seats).where(
                table_seats.c.user_id == user_id,
                table_seats.c.state.in_(("seated", "held", "leaving")),
            ))
        ).mappings().one_or_none()


async def test_buyin_settlement_restart_and_return_are_exact(cash_db):
    await seed_cash_table(cash_db)
    await fund(cash_db, "alice-wallet", 2_000_000, "fund-alice")
    await fund(cash_db, "bob-wallet", 2_000_000, "fund-bob")
    service = CashGameService(cash_db)

    alice = await service.seat("alice", "cash-heads-up", 0, 800_000, "seat-alice")
    bob = await service.seat("bob", "cash-heads-up", 1, 800_000, "seat-bob")
    assert alice.stack_micros == bob.stack_micros == 800_000
    assert alice.cash_escrow_account_id != bob.cash_escrow_account_id
    assert await balance(cash_db, "alice-wallet") == 1_200_000

    started = await service.start_hand("cash-heads-up", button_seat=0)
    actor = started.state.acting_player
    finished = await service.act(
        "cash-heads-up", actor, ActionType.FOLD,
        amount_micros=0, command_id="fold-1", expected_revision=started.revision,
    )
    assert finished.state.terminal
    assert all(type(player.stack) is int for player in finished.state.players.values())

    alice_seat = await active_seat(cash_db, "alice")
    bob_seat = await active_seat(cash_db, "bob")
    assert {alice_seat["stack_micros"], bob_seat["stack_micros"]} == {790_000, 810_000}
    assert await balance(cash_db, alice_seat["cash_escrow_account_id"]) == alice_seat["stack_micros"]
    assert await balance(cash_db, bob_seat["cash_escrow_account_id"]) == bob_seat["stack_micros"]

    # A new process repeats the last command after the transaction committed.
    replay = await CashGameService(cash_db).act(
        "cash-heads-up", actor, ActionType.FOLD,
        amount_micros=0, command_id="fold-1", expected_revision=started.revision,
    )
    assert replay.revision == finished.revision
    async with cash_db() as session:
        assert await session.scalar(select(cash_transactions.c.id).where(
            cash_transactions.c.idempotency_key == f"hand:{started.state.hand_id}"
        )) is not None
        assert await session.scalar(select(hands.c.terminal).where(
            hands.c.id == started.state.hand_id
        )) is True

    await service.leave("alice", "cash-heads-up", "leave-alice")
    await service.leave("bob", "cash-heads-up", "leave-bob")
    assert await active_seat(cash_db, "alice") is None
    assert await active_seat(cash_db, "bob") is None
    assert await balance(cash_db, "alice-wallet") + await balance(cash_db, "bob-wallet") == 4_000_000


async def test_mid_hand_leave_waits_for_settlement(cash_db):
    await seed_cash_table(cash_db)
    await fund(cash_db, "alice-wallet", 2_000_000, "fund-alice")
    await fund(cash_db, "bob-wallet", 2_000_000, "fund-bob")
    service = CashGameService(cash_db)
    await service.seat("alice", "cash-heads-up", 0, 800_000, "seat-alice")
    await service.seat("bob", "cash-heads-up", 1, 800_000, "seat-bob")
    started = await service.start_hand("cash-heads-up", button_seat=0)
    actor = started.state.acting_player

    await service.leave(actor, "cash-heads-up", "leave-mid-hand")
    leaving = await active_seat(cash_db, actor)
    assert leaving["state"] == "leaving"
    assert await balance(cash_db, leaving["cash_escrow_account_id"]) == 800_000

    await service.act(
        "cash-heads-up", actor, ActionType.FOLD,
        amount_micros=0, command_id="fold-after-leave", expected_revision=started.revision,
    )
    assert await active_seat(cash_db, actor) is None
    assert await balance(cash_db, f"{actor}-wallet") in {1_990_000, 2_010_000}


async def test_cash_add_on_is_exact_capped_and_idempotent(cash_db):
    await seed_cash_table(cash_db)
    await fund(cash_db, "alice-wallet", 2_000_000, "fund-alice")
    service = CashGameService(cash_db)
    seat = await service.seat("alice", "cash-heads-up", 0, 800_000, "seat-alice")

    first = await service.add_on("alice", "cash-heads-up", 200_000, "add-on-1")
    replay = await service.add_on("alice", "cash-heads-up", 200_000, "add-on-1")
    assert first.stack_micros == replay.stack_micros == 1_000_000
    assert await balance(cash_db, seat.cash_escrow_account_id) == 1_000_000
    assert await balance(cash_db, "alice-wallet") == 1_000_000
    with pytest.raises(CashSeatError, match="chip"):
        await service.add_on("alice", "cash-heads-up", 1, "fractional-add-on")
    with pytest.raises(CashSeatError, match="maximum"):
        await service.add_on("alice", "cash-heads-up", 1_010_000, "too-large")


async def test_reused_physical_seat_gets_new_owned_escrow(cash_db):
    await seed_cash_table(cash_db)
    await fund(cash_db, "alice-wallet", 2_000_000, "fund-alice")
    service = CashGameService(cash_db)
    first = await service.seat("alice", "cash-heads-up", 0, 800_000, "seat-first")
    await service.leave("alice", "cash-heads-up", "leave-first")
    second = await service.seat("alice", "cash-heads-up", 0, 800_000, "seat-second")

    assert second.id == first.id
    assert second.cash_escrow_account_id != first.cash_escrow_account_id
    async with cash_db() as session:
        old = (
            await session.execute(select(cash_accounts).where(
                cash_accounts.c.id == first.cash_escrow_account_id
            ))
        ).mappings().one()
        assert old["kind"] == "escrow" and old["user_id"] == "alice"
        assert old["balance_micros"] == 0


async def test_escrow_mismatch_pauses_only_cash_table_without_faucet(cash_db):
    await seed_cash_table(cash_db)
    await fund(cash_db, "alice-wallet", 2_000_000, "fund-alice")
    await fund(cash_db, "bob-wallet", 2_000_000, "fund-bob")
    service = CashGameService(cash_db)
    await service.seat("alice", "cash-heads-up", 0, 800_000, "seat-alice")
    await service.seat("bob", "cash-heads-up", 1, 800_000, "seat-bob")
    started = await service.start_hand("cash-heads-up", button_seat=0)
    actor = started.state.acting_player
    seat = await active_seat(cash_db, actor)
    async with cash_db() as session:
        async with session.begin():
            await session.execute(update(cash_accounts).where(
                cash_accounts.c.id == seat["cash_escrow_account_id"]
            ).values(balance_micros=799_999))

    with pytest.raises(CashIntegrityError, match="escrow"):
        await service.act(
            "cash-heads-up", actor, ActionType.FOLD,
            amount_micros=0, command_id="mismatch-fold", expected_revision=started.revision,
        )
    async with cash_db() as session:
        runtime = (
            await session.execute(select(table_runtimes).where(
                table_runtimes.c.table_id == "cash-heads-up"
            ))
        ).mappings().one()
        assert runtime["phase"] == "paused"
        assert "escrow" in runtime["paused_reason"]
        assert await session.scalar(select(hands.c.terminal).where(
            hands.c.id == started.state.hand_id
        )) is False
        assert await session.scalar(select(cash_transactions.c.id).where(
            cash_transactions.c.idempotency_key == f"hand:{started.state.hand_id}"
        )) is None
    await service.leave(actor, "cash-heads-up", "leave-paused")
    still_reserved = await active_seat(cash_db, actor)
    assert still_reserved["state"] == "leaving"
    assert await balance(cash_db, "alice-wallet" if actor == "alice" else "bob-wallet") == 1_200_000


async def test_cash_seat_rejects_fractional_chip_and_system_occupant(cash_db):
    await seed_cash_table(cash_db)
    await fund(cash_db, "alice-wallet", 2_000_000, "fund-alice")
    service = CashGameService(cash_db)
    with pytest.raises(CashSeatError, match="chip"):
        await service.seat("alice", "cash-heads-up", 0, 800_001, "fractional")
    await service.seat("alice", "cash-heads-up", 0, 800_000, "seat-alice")
    async with cash_db() as session:
        async with session.begin():
            await session.execute(insert(system_players).values(
                id="cash-bot", name="Forbidden", difficulty="normal", active=True,
            ))
            await session.execute(insert(table_seats).values(
                id="cash-bot-seat", table_id="cash-heads-up", seat_no=1,
                occupant_kind="system", system_player_id="cash-bot",
                stack_micros=800_000, state="seated",
            ))
    with pytest.raises(CashSeatError, match="system occupants"):
        await service.start_hand("cash-heads-up", button_seat=0)
