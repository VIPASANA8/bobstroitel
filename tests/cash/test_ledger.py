import asyncio

import pytest
from sqlalchemy import func, select

from cash.amounts import MAX_MICROS, micros_to_units
from cash.ledger import CashLedger, IdempotencyConflict, InsufficientCash
from online.ledger import PlayLedger
from online.schema import cash_accounts, cash_entries, cash_transactions

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
ledger = CashLedger()


async def submit(factory, key, postings, *, kind="reserve", ref="test-ref", actor="system:test", gate=None):
    async with factory() as session:
        async with session.begin():
            if gate is not None:
                await session.connection()
                await gate.wait()
            return await ledger.post(
                session, scope="test", key=key, kind=kind,
                reference_id=ref, actor=actor, postings=postings,
            )


async def fund(factory, amount=10_000_000, key="deposit"):
    return await submit(
        factory, key, {"external": -amount, "alice-wallet": amount},
        kind="deposit", ref="mock-deposit",
    )


async def balances(factory):
    async with factory() as session:
        result = await session.execute(select(cash_accounts.c.id, cash_accounts.c.balance_micros))
        return dict(result.all())


async def transaction_count(factory):
    async with factory() as session:
        return await session.scalar(select(func.count()).select_from(cash_transactions))


async def assert_reconciled(factory):
    async with factory() as session:
        rows = (await session.execute(
            select(
                cash_accounts.c.id, cash_accounts.c.balance_micros,
                func.coalesce(func.sum(cash_entries.c.amount_micros), 0),
            )
            .outerjoin(cash_entries, cash_entries.c.account_id == cash_accounts.c.id)
            .group_by(cash_accounts.c.id, cash_accounts.c.balance_micros)
        )).all()
        assert all(balance == entry_sum for _, balance, entry_sum in rows)
        totals = (await session.execute(
            select(cash_transactions.c.id, func.sum(cash_entries.c.amount_micros), func.count(cash_entries.c.account_id))
            .outerjoin(cash_entries, cash_entries.c.transaction_id == cash_transactions.c.id)
            .group_by(cash_transactions.c.id)
        )).all()
        assert all(total == 0 and count >= 2 for _, total, count in totals)


async def test_cash_starts_at_zero_and_play_grants_do_not_change_it(cash_db):
    assert (await balances(cash_db))["alice-wallet"] == 0
    await PlayLedger(cash_db).grant("alice", 1_000, "play-only")
    assert await PlayLedger(cash_db).available_units("alice") == 13_345
    assert (await balances(cash_db))["alice-wallet"] == 0
    assert await transaction_count(cash_db) == 0


async def test_deposit_replay_preserves_amount_and_detects_changed_recipient(cash_db):
    first = await fund(cash_db, 10_010_000)
    replay = await submit(
        cash_db, "deposit", {"alice-wallet": 10_010_000, "external": -10_010_000},
        kind="deposit", ref="mock-deposit",
    )
    assert first.transaction_id == replay.transaction_id
    assert first.created and not replay.created
    assert micros_to_units((await balances(cash_db))["alice-wallet"]) == "100.1"
    with pytest.raises(IdempotencyConflict):
        await submit(cash_db, "deposit", {"bob-wallet": 10_010_000, "external": -10_010_000}, kind="deposit", ref="mock-deposit")
    with pytest.raises(IdempotencyConflict):
        await fund(cash_db, 11_000_000)
    with pytest.raises(IdempotencyConflict):
        await submit(cash_db, "deposit", {"alice-wallet": 10_010_000, "external": -10_010_000}, kind="deposit", ref="mock-deposit", actor="different-actor")
    assert await transaction_count(cash_db) == 1
    await assert_reconciled(cash_db)


@pytest.mark.parametrize("postings", [
    {"external": -1, "alice-wallet": 2},
    {"external": 0, "alice-wallet": 0},
    {"external": -1, "alice-wallet": True},
    {"external": -1.0, "alice-wallet": 1.0},
    {"external": -(MAX_MICROS + 1), "alice-wallet": MAX_MICROS + 1},
])
async def test_invalid_postings_do_not_write_anything(cash_db, postings):
    with pytest.raises(ValueError):
        await submit(cash_db, "invalid", postings)
    assert await transaction_count(cash_db) == 0
    assert all(value == 0 for value in (await balances(cash_db)).values())


async def test_missing_account_does_not_leave_an_operation(cash_db):
    with pytest.raises(ValueError, match="unknown cash account"):
        await submit(cash_db, "missing", {"external": -1, "missing": 1})
    assert await transaction_count(cash_db) == 0


async def test_reserve_and_idempotent_release(cash_db):
    await fund(cash_db)
    await submit(cash_db, "reserve", {"alice-wallet": -7_000_000, "alice-withdraw": 7_000_000})
    before = await balances(cash_db)
    assert before["alice-wallet"] == 3_000_000 and before["alice-withdraw"] == 7_000_000
    first = await submit(cash_db, "release", {"alice-withdraw": -7_000_000, "alice-wallet": 7_000_000}, kind="release")
    replay = await submit(cash_db, "release", {"alice-withdraw": -7_000_000, "alice-wallet": 7_000_000}, kind="release")
    assert first.created and not replay.created
    assert (await balances(cash_db))["alice-wallet"] == 10_000_000
    assert (await balances(cash_db))["alice-withdraw"] == 0
    assert await transaction_count(cash_db) == 3
    await assert_reconciled(cash_db)


async def test_outer_rollback_removes_claim_entries_and_projection(cash_db):
    with pytest.raises(RuntimeError, match="workflow rollback"):
        async with cash_db() as session:
            async with session.begin():
                await ledger.post(session, scope="test", key="rollback", kind="deposit", reference_id="mock-deposit", actor="system:test", postings={"external": -100, "alice-wallet": 100})
                raise RuntimeError("workflow rollback")
    assert await transaction_count(cash_db) == 0
    assert (await balances(cash_db))["alice-wallet"] == 0
    assert (await fund(cash_db, 100, key="rollback")).created
    await assert_reconciled(cash_db)


async def test_failed_operation_can_be_retried_in_same_outer_transaction(cash_db):
    async with cash_db() as session:
        async with session.begin():
            command = dict(scope="test", key="reserve", kind="reserve", reference_id="seat", actor="system:test", postings={"alice-wallet": -100, "alice-seat": 100})
            with pytest.raises(InsufficientCash):
                await ledger.post(session, **command)
            assert await session.scalar(select(func.count()).select_from(cash_transactions)) == 0
            await ledger.post(session, scope="test", key="deposit", kind="deposit", reference_id="mock", actor="system:test", postings={"external": -100, "alice-wallet": 100})
            assert (await ledger.post(session, **command)).created
    assert (await balances(cash_db))["alice-seat"] == 100
    await assert_reconciled(cash_db)


async def test_concurrent_duplicate_callbacks_credit_once(cash_db):
    gate = asyncio.Barrier(8)
    tasks = [asyncio.create_task(submit(
        cash_db, "same-event", {"external": -10_000_000, "alice-wallet": 10_000_000},
        kind="deposit", gate=gate,
    )) for _ in range(8)]
    results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15)
    assert sum(result.created for result in results) == 1
    assert len({result.transaction_id for result in results}) == 1
    assert (await balances(cash_db))["alice-wallet"] == 10_000_000
    assert await transaction_count(cash_db) == 1
    await assert_reconciled(cash_db)


async def test_buyin_and_withdrawal_cannot_spend_the_same_money(cash_db):
    await fund(cash_db)
    gate = asyncio.Barrier(2)
    tasks = [
        asyncio.create_task(submit(cash_db, "buyin", {"alice-wallet": -8_000_000, "alice-seat": 8_000_000}, gate=gate)),
        asyncio.create_task(submit(cash_db, "withdraw", {"alice-wallet": -8_000_000, "alice-withdraw": 8_000_000}, gate=gate)),
    ]
    results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=15)
    assert sum(isinstance(result, InsufficientCash) for result in results) == 1
    assert sum(not isinstance(result, BaseException) for result in results) == 1
    result = await balances(cash_db)
    assert result["alice-wallet"] == 2_000_000
    assert result["alice-seat"] + result["alice-withdraw"] == 8_000_000
    assert await transaction_count(cash_db) == 2
    await assert_reconciled(cash_db)


async def test_concurrent_distinct_deposits_do_not_lose_an_update(cash_db):
    await asyncio.wait_for(asyncio.gather(fund(cash_db, key="one"), fund(cash_db, key="two")), timeout=15)
    assert (await balances(cash_db))["alice-wallet"] == 20_000_000
    assert await transaction_count(cash_db) == 2
    await assert_reconciled(cash_db)


async def test_balance_overflow_rolls_back_the_whole_operation(cash_db):
    await fund(cash_db, MAX_MICROS)
    with pytest.raises(ValueError, match="range"):
        await fund(cash_db, 1, key="overflow")
    assert (await balances(cash_db))["alice-wallet"] == MAX_MICROS
    assert await transaction_count(cash_db) == 1
    await assert_reconciled(cash_db)
