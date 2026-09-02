import pytest
from sqlalchemy import func, insert, select

from cash.access import CashOperator
from cash.admin import CashAdminService, OperatorAccessDenied
from cash.antifraud import DepositPolicy, DepositRefused
from cash.deposits import DepositService
from cash.fiat_orders import FiatOrderService
from cash.fiat_p2p import MockCase8Partner
from cash.game import CashGameService
from cash.holds import CashUserFrozen
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, TransferEvent
from cash.wallet import WalletService
from cash.withdrawals import WithdrawalService
from online.schema import cash_audit_events, cash_user_holds, poker_tables


pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
OPERATOR = CashOperator("operator", 1001, "tenant", "operator")
REVIEWER = CashOperator("reviewer", 1002, "tenant", "reviewer")
OTHER = CashOperator("other-operator", 1003, "tenant-other", "operator")
TABLE_ID = "cash-hold-table"


async def funded(cash_db, user_id="alice", amount="30"):
    deposits = DepositService(cash_db)
    deposit = await deposits.create(
        user_id=user_id, tenant_id="tenant", amount_usdt=amount, request_key=f"fund-{user_id}",
    )
    await deposits.observe(TransferEvent(
        provider="mock-trc20", external_event_id=f"chain-{user_id}", tx_hash=f"tx-{user_id}",
        event_index=0, network=MOCK_NETWORK, token_contract=deposit["token_contract"],
        destination_address=MOCK_ADDRESS, amount_micros=deposit["expected_micros"],
        occurred_at=deposit["created_at"],
    ))
    return deposit


async def seed_table(cash_db):
    async with cash_db() as session:
        async with session.begin():
            await session.execute(insert(poker_tables).values(
                id=TABLE_ID, scope="network", asset="CASH_USDT", name="Hold Heads-Up",
                small_blind_units=0, big_blind_units=0, small_blind_micros=10_000,
                big_blind_micros=20_000, chip_micros=10_000, min_buy_in_bb=40,
                max_buy_in_bb=100, max_seats=6,
            ))


async def test_a_hold_stops_every_new_money_path_and_lifts_cleanly(cash_db):
    await funded(cash_db)
    await seed_table(cash_db)
    admin = CashAdminService(cash_db)

    frozen = await admin.freeze_user("alice", OPERATOR, reason="suspected card fraud", key="hold-1")
    assert frozen == {"user_id": "alice", "held": True, "reason": "suspected card fraud"}

    with pytest.raises(CashUserFrozen):
        await DepositService(cash_db).create(
            user_id="alice", tenant_id="tenant", amount_usdt="5", request_key="after-hold",
        )
    with pytest.raises(CashUserFrozen):
        await FiatOrderService(cash_db, partner=MockCase8Partner()).create(
            user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-after-hold",
        )
    with pytest.raises(CashUserFrozen):
        await WithdrawalService(cash_db).create(
            user_id="alice", tenant_id="tenant", amount_usdt="5",
            destination_address="TAliceWallet", request_key="out-after-hold",
        )
    with pytest.raises(CashUserFrozen):
        await CashGameService(cash_db).seat("alice", TABLE_ID, 0, 800_000, "seat-after-hold")

    # The balance is still theirs and still visible.
    assert (await WalletService(cash_db).get("alice"))["available_usdt"] == "30"

    released = await admin.release_user("alice", OPERATOR, reason="documents checked", key="hold-2")
    assert released == {"user_id": "alice", "held": False, "reason": None}
    seat = await CashGameService(cash_db).seat("alice", TABLE_ID, 0, 800_000, "seat-after-release")
    assert seat.seat_no == 0


async def test_a_hold_never_traps_money_already_at_risk(cash_db):
    await funded(cash_db)
    await seed_table(cash_db)
    fiat = FiatOrderService(cash_db, partner=MockCase8Partner())
    order = await fiat.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-paid",
    )
    await fiat.mark_paid(order["id"], "alice")
    game = CashGameService(cash_db)
    await game.seat("alice", TABLE_ID, 0, 800_000, "seat-before-hold")

    await CashAdminService(cash_db).freeze_user(
        "alice", OPERATOR, reason="under review while paid", key="hold-3",
    )

    # The trader confirms: the user paid before the hold and keeps their money.
    assert await fiat.poll_once() == 1
    assert (await fiat.get(order["id"], "alice"))["status"] == "credited"
    # And a seated player still leaves with their escrow.
    await game.leave("alice", TABLE_ID, "leave-under-hold")
    wallet = await WalletService(cash_db).get("alice")
    assert wallet["escrow_usdt"] == "0"
    assert wallet["available_usdt"] == "50"


async def test_only_a_scoped_operator_freezes_and_the_key_replays(cash_db):
    admin = CashAdminService(cash_db)

    with pytest.raises(OperatorAccessDenied):
        await admin.freeze_user("alice", REVIEWER, reason="reviewers only read", key="hold-r")
    with pytest.raises(OperatorAccessDenied):
        await admin.freeze_user("alice", OTHER, reason="wrong tenant", key="hold-o")
    with pytest.raises(LookupError):
        await admin.freeze_user("nobody", OPERATOR, reason="unknown user", key="hold-n")

    first = await admin.freeze_user("alice", OPERATOR, reason="chargeback opened", key="hold-4")
    replay = await admin.freeze_user("alice", OPERATOR, reason="chargeback opened", key="hold-4")

    assert first == replay
    async with cash_db() as session:
        assert await session.scalar(select(func.count()).select_from(cash_user_holds)) == 1
        assert await session.scalar(select(func.count()).select_from(cash_audit_events)) == 1
    card = await admin.user(OPERATOR, "alice")
    assert card["hold"]["reason"] == "chargeback opened"
    assert card["hold"]["operator_id"] == "operator"


async def test_the_request_rate_and_the_daily_limit_refuse_before_a_trader_is_asked(cash_db):
    policy = DepositPolicy(orders_per_hour=3, daily_micros=60_000_000)
    partner = MockCase8Partner()
    service = FiatOrderService(cash_db, partner=partner, policy=policy)

    for index in range(3):
        order = await service.create(
            user_id="alice", tenant_id="tenant", amount_usdt="20", request_key=f"rub-{index}",
        )
        await service.cancel(order["id"], "alice")

    with pytest.raises(DepositRefused, match="too many RUB requests"):
        await service.create(
            user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-4",
        )

    # Cancelled orders cost the user nothing, so only what they asked for and
    # kept counts against the day.
    limited = FiatOrderService(
        cash_db, partner=partner,
        policy=DepositPolicy(orders_per_hour=0, daily_micros=50_000_000),
    )
    for index in range(2):
        order = await limited.create(
            user_id="alice", tenant_id="tenant", amount_usdt="20", request_key=f"day-{index}",
        )
        await limited.mark_paid(order["id"], "alice")
        await limited.poll_once()

    with pytest.raises(DepositRefused, match="daily RUB deposit limit"):
        await limited.create(
            user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="day-2",
        )
