"""Putting money on a balance by hand: the one place it appears without a payment."""
import pytest
from sqlalchemy import select

from cash.access import CashOperator
from cash.admin import ADJUSTMENT_ACCOUNT, CashAdminService, MAX_ADJUSTMENT_MICROS, OperatorAccessDenied
from cash.ledger import CashLedger, InsufficientCash
from online.schema import cash_accounts, cash_audit_events

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]

ADMIN = CashOperator("global-admin", 1004, None, "admin")
OPERATOR = CashOperator("operator", 1001, "tenant", "operator")
REVIEWER = CashOperator("reviewer", 1002, "tenant", "reviewer")


async def fund(factory, amount, key="fund"):
    async with factory() as session:
        async with session.begin():
            await CashLedger().post(
                session, scope="adjust-test", key=key, kind="deposit",
                reference_id=key, actor="test:fund",
                postings={"external": -amount, "alice-wallet": amount},
            )


async def balance(factory, account_id="alice-wallet"):
    async with factory() as session:
        return int(await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.id == account_id,
        )) or 0)


async def test_a_credit_lands_on_the_balance_and_in_the_audit_log(cash_db):
    service = CashAdminService(cash_db)
    result = await service.adjust_balance(
        "alice", ADMIN, amount_micros=25_500_000, reason="возврат после инцидента", key="adj-1",
    )

    assert result["direction"] == "credit" and result["available_usdt"] == "25.5"
    assert await balance(cash_db) == 25_500_000
    async with cash_db() as session:
        row = (await session.execute(select(cash_audit_events).where(
            cash_audit_events.c.action == "user.adjust",
        ))).mappings().one()
        assert row["reason"] == "возврат после инцидента"
        assert row["actor_telegram_user_id"] == 1004
        # The money came from a named clearing account, not from nowhere.
        clearing = int(await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.kind == "clearing",
            cash_accounts.c.reference_id == ADJUSTMENT_ACCOUNT,
        )))
    assert clearing == -25_500_000


async def test_a_debit_cannot_push_a_balance_below_zero(cash_db):
    await fund(cash_db, 5_000_000)
    service = CashAdminService(cash_db)
    with pytest.raises(InsufficientCash):
        await service.adjust_balance("alice", ADMIN, amount_micros=-9_000_000, reason="перебор", key="adj-1")
    assert await balance(cash_db) == 5_000_000

    await service.adjust_balance("alice", ADMIN, amount_micros=-2_000_000, reason="списание", key="adj-2")
    assert await balance(cash_db) == 3_000_000


async def test_the_same_key_is_the_same_correction(cash_db):
    """An operator who taps confirm twice corrects once."""
    service = CashAdminService(cash_db)
    first = await service.adjust_balance("alice", ADMIN, amount_micros=1_000_000, reason="раз", key="adj-1")
    again = await service.adjust_balance("alice", ADMIN, amount_micros=1_000_000, reason="раз", key="adj-1")
    assert first == again
    assert await balance(cash_db) == 1_000_000


@pytest.mark.parametrize("amount", [0, MAX_ADJUSTMENT_MICROS + 1, -MAX_ADJUSTMENT_MICROS - 1])
async def test_nothing_and_too_much_are_both_refused(cash_db, amount):
    """Zero is not a correction, and the cap is where a slipped decimal point
    stops being recoverable."""
    with pytest.raises(ValueError):
        await CashAdminService(cash_db).adjust_balance(
            "alice", ADMIN, amount_micros=amount, reason="проверка", key="adj-1")
    assert await balance(cash_db) == 0


async def test_it_takes_a_global_admin(cash_db):
    """The clearing account it books against is nobody's tenant, so an operator
    who owns one of them cannot be the one to move it."""
    service = CashAdminService(cash_db)
    for who in (OPERATOR, REVIEWER):
        with pytest.raises(OperatorAccessDenied):
            await service.adjust_balance("alice", who, amount_micros=1_000_000, reason="нет", key=f"k-{who.id}")
    assert await balance(cash_db) == 0
