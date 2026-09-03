"""Restore a CASH backup into a fresh database and prove nothing pays twice.

    python tools/cash_backup_restore_check.py [--keep]

Builds a database that has done every irreversible CASH thing -- a credited
TRC20 provider event, a credited RUB partner event, a reserved and submitted
payout on both rails, and a settled CASH hand that paid rake -- takes a
`pg_dump`, restores it into a second database, and then replays every one of
those operations against the restored copy. A backup is only good if the replay
is refused: the idempotency keys have to be inside the dump, not in the memory
of the process that made them.

Run it from a checkout whose compose project owns the postgres_test container;
from a git worktree that means COMPOSE_PROJECT_NAME has to name it.

Exits non-zero on the first thing that does not hold.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.online import EXPECTED_MIGRATION_REVISION  # noqa: E402
from cash.deposits import DepositService  # noqa: E402
from cash.fiat_orders import FiatOrderService  # noqa: E402
from cash.fiat_p2p import MockCase8Partner, PartnerEvent  # noqa: E402
from cash.access import CashOperator  # noqa: E402
from cash.admin import CashAdminService  # noqa: E402
from cash.game import CashGameService  # noqa: E402
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, TransferEvent  # noqa: E402
from cash.withdrawals import P2P_RUB, WithdrawalService  # noqa: E402
from online.schema import (  # noqa: E402
    cash_accounts, cash_audit_events, cash_deposits, cash_entries, cash_fiat_events,
    cash_fiat_orders, cash_partner_cursors, cash_payment_events, cash_transactions,
    cash_operators, cash_withdrawals, hands, poker_tables, tenants, users,
)
from online.asyncio_runner import run as run_async  # noqa: E402
from poker.models import ActionType  # noqa: E402

SOURCE_DB = "poker8_backup_source"
RESTORED_DB = "poker8_backup_restored"
TABLE_ID = "cash-backup-check"
OPERATOR = CashOperator("backup-operator", 9001, "tenant", "operator")


class CheckFailed(RuntimeError):
    pass


def base_url():
    raw = os.environ.get("POKER8_CASH_TEST_DATABASE_URL", "")
    url = make_url(raw) if raw else None
    if url is None or not (
        url.drivername == "postgresql+psycopg"
        and url.host in {"localhost", "127.0.0.1", "::1"}
        and url.port == 5433 and url.database == "poker8_test" and not url.query
    ):
        raise SystemExit("Set POKER8_CASH_TEST_DATABASE_URL to the local postgres_test service")
    return url


def sessions_for(url):
    engine = create_async_engine(url.render_as_string(hide_password=False), poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def admin_sql(url, statements):
    engine, _ = sessions_for(url.set(database="postgres"))
    try:
        async with engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


def run_alembic(url):
    environment = os.environ | {"POKER8_DATABASE_URL": url.render_as_string(hide_password=False)}
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=ROOT, env=environment, check=True, capture_output=True,
    )


def postgres_tool(name, arguments, *, stdin=None, stdout=None):
    """Prefer a local client; fall back to the one inside the compose service."""
    if shutil.which(name):
        environment = os.environ | {"PGPASSWORD": "poker8"}
        command = [name, "-h", "127.0.0.1", "-p", "5433", "-U", "poker8", *arguments]
    else:
        environment = os.environ
        command = ["docker", "compose", "exec", "-T", "postgres_test", name, "-U", "poker8", *arguments]
    result = subprocess.run(command, cwd=ROOT, env=environment, stdin=stdin, stdout=stdout,
                            stderr=subprocess.PIPE)
    if result.returncode:
        raise CheckFailed(f"{name} failed: {result.stderr.decode(errors='replace')[-2000:]}")


async def seed(factory):
    """Do every irreversible thing once, and remember how to try it again."""
    async with factory() as session:
        async with session.begin():
            await session.execute(tenants.insert().values(id="tenant", slug="backup", name="Backup"))
            await session.execute(users.insert(), [
                {"id": "alice", "telegram_user_id": 1, "display_name": "Alice", "acquisition_tenant_id": "tenant"},
                {"id": "bob", "telegram_user_id": 2, "display_name": "Bob", "acquisition_tenant_id": "tenant"},
            ])
            await session.execute(poker_tables.insert().values(
                id=TABLE_ID, scope="network", asset="CASH_USDT", name="Backup Heads-Up",
                # The live stakes, not the old micro ones: at 0.01/0.02 a chip
                # is half a big blind and the rake floors to nothing, so the
                # path this check exists to cover would never run.
                small_blind_units=5, big_blind_units=10, small_blind_micros=50_000,
                big_blind_micros=100_000, chip_micros=10_000, min_buy_in_bb=40,
                max_buy_in_bb=100, max_seats=6, rake_bps=1_000,
            ))
            await session.execute(cash_operators.insert().values(
                id="backup-operator", tenant_id="tenant", telegram_user_id=9001,
                role="operator", active=True,
            ))

    deposits = DepositService(factory)
    events = []
    for user_id in ("alice", "bob"):
        deposit = await deposits.create(
            user_id=user_id, tenant_id="tenant", amount_usdt="30", request_key=f"deposit-{user_id}",
        )
        event = TransferEvent(
            provider="mock-trc20", external_event_id=f"chain-{user_id}", tx_hash=f"tx-{user_id}",
            event_index=0, network=MOCK_NETWORK, token_contract=deposit["token_contract"],
            destination_address=MOCK_ADDRESS, amount_micros=deposit["expected_micros"],
            occurred_at=deposit["created_at"] + timedelta(seconds=1),
        )
        await deposits.observe(event)
        events.append(event)

    fiat = FiatOrderService(factory, partner=MockCase8Partner())
    order = await fiat.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-backup",
    )
    await fiat.mark_paid(order["id"], "alice")
    await fiat.poll_once()
    async with factory() as session:
        partner_event = (await session.execute(select(cash_fiat_events))).mappings().one()

    withdrawals = WithdrawalService(factory)
    withdrawal = await withdrawals.create(
        user_id="bob", tenant_id="tenant", amount_usdt="5",
        destination_address="TBackupCheckWallet", request_key="withdraw-backup",
    )
    await withdrawals.approve(withdrawal["id"])
    await withdrawals.execute(withdrawal["id"], "success")

    # The P2P rail has no executor to refuse a second send: a replay that got
    # through would be a person paying a second time out of their own pocket.
    fiat_payout = await withdrawals.create(
        user_id="alice", tenant_id="tenant", amount_usdt="5",
        destination_address="2200 7007 1234 5678", request_key="p2p-backup", rail=P2P_RUB,
    )
    admin = CashAdminService(factory)
    await admin.approve_withdrawal(fiat_payout["id"], OPERATOR, reason="backup check", key="p1")
    await admin.settle_p2p_withdrawal(
        fiat_payout["id"], OPERATOR, fiat_kopecks=45_000, reason="backup check", key="p2",
    )

    # Checked down rather than folded, so the hand reaches a flop and the table
    # actually takes its rake -- a folded hand posts nothing to the house and
    # would leave the newest money path out of the backup entirely.
    game = CashGameService(factory)
    await game.seat("alice", TABLE_ID, 0, 5_000_000, "seat-alice")
    await game.seat("bob", TABLE_ID, 1, 5_000_000, "seat-bob")
    started = await game.start_hand(TABLE_ID, button_seat=0)
    result, replayable, step = started, None, 0
    while not result.state.terminal:
        actor, state = result.state.acting_player, result.state
        owed = state.current_bet - state.players[actor].street_invested
        step += 1
        if replayable is None:
            replayable = {"actor": actor, "revision": result.revision,
                          "command_id": f"street-{step}",
                          "action": ActionType.CALL if owed else ActionType.CHECK}
        result = await game.act(
            TABLE_ID, actor, ActionType.CALL if owed else ActionType.CHECK,
            amount_micros=0, command_id=f"street-{step}", expected_revision=result.revision,
        )
    finished = result
    if not finished.state.terminal:
        raise CheckFailed("the seeded hand did not settle")
    if not finished.state.rake:
        raise CheckFailed("the seeded hand paid no rake, so the rake path is untested")

    return {
        "transfer_events": events,
        "partner_event": PartnerEvent(
            partner_event["event_id"], partner_event["partner_order_id"], partner_event["event_type"],
        ),
        "withdrawal_id": withdrawal["id"],
        "tx_hash": (await withdrawals.get(withdrawal["id"]))["tx_hash"],
        "p2p_withdrawal_id": fiat_payout["id"],
        "fiat_order_id": order["id"],
        "replayable": replayable,
        "hand_id": started.state.hand_id,
    }


async def snapshot(factory):
    async with factory() as session:
        balances = dict((await session.execute(select(
            cash_accounts.c.id, cash_accounts.c.balance_micros,
        ).order_by(cash_accounts.c.id))).all())
        counts = {}
        for name, table in (
            ("transactions", cash_transactions), ("entries", cash_entries),
            ("deposits", cash_deposits), ("withdrawals", cash_withdrawals),
            ("fiat_orders", cash_fiat_orders), ("fiat_events", cash_fiat_events),
            ("payment_events", cash_payment_events), ("partner_cursors", cash_partner_cursors),
            ("audit_events", cash_audit_events), ("hands", hands),
        ):
            counts[name] = await session.scalar(select(func.count()).select_from(table))
        revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    return {"balances": balances, "counts": counts, "revision": revision}


class RefuseToPayTwice:
    """A payout executor that records a send instead of making one."""

    def __init__(self):
        self.calls = 0

    def send(self, payout_id, outcome):
        self.calls += 1
        return {"status": "submitted", "tx_hash": f"replayed-{payout_id}"}


class ResendingPartner:
    """The partner redelivering an event the restored copy has already applied."""

    def __init__(self, event):
        self.event = event

    async def poll_events(self, offset):
        return [self.event], max(offset, self.event.event_id)


async def replay(factory, state):
    """Try every payment again. Each line records what the restored copy did."""
    outcomes = []

    for event in state["transfer_events"]:
        await DepositService(factory).observe(event)
    outcomes.append("provider transfer events redelivered")

    await FiatOrderService(factory, partner=ResendingPartner(state["partner_event"])).poll_once()
    outcomes.append("partner completion redelivered")

    executor = RefuseToPayTwice()
    replayed_payout = await WithdrawalService(factory, executor=executor).execute(
        state["withdrawal_id"], "success",
    )
    if executor.calls:
        raise CheckFailed("the restored copy sent the payout again")
    if replayed_payout["tx_hash"] != state["tx_hash"]:
        raise CheckFailed("the restored copy rewrote the payout reference")
    outcomes.append("payout execution repeated, executor never called")

    # The operator settles the same P2P payout again, exactly as a person
    # working from a restored queue would.
    repeated = await CashAdminService(factory).settle_p2p_withdrawal(
        state["p2p_withdrawal_id"], OPERATOR, fiat_kopecks=45_000,
        reason="backup check", key="p2",
    )
    if repeated["status"] != "submitted":
        raise CheckFailed("the restored copy lost the P2P payout")
    outcomes.append("P2P payout settled again, nothing posted twice")

    command = state["replayable"]
    replayed = await CashGameService(factory).act(
        TABLE_ID, command["actor"], command["action"],
        amount_micros=0, command_id=command["command_id"],
        expected_revision=command["revision"],
    )
    outcomes.append(f"raked hand command replayed to revision {replayed.revision}")
    return outcomes


def differences(before, after):
    found = []
    for account, amount in after["balances"].items():
        if before["balances"].get(account) != amount:
            found.append(f"{account}: {before['balances'].get(account)} -> {amount}")
    for account in before["balances"].keys() - after["balances"].keys():
        found.append(f"{account}: disappeared")
    for name, count in after["counts"].items():
        if before["counts"][name] != count:
            found.append(f"{name}: {before['counts'][name]} -> {count} rows")
    if before["revision"] != after["revision"]:
        found.append(f"alembic revision: {before['revision']} -> {after['revision']}")
    return found


async def main(keep: bool) -> int:
    url = base_url()
    source_url = url.set(database=SOURCE_DB)
    restored_url = url.set(database=RESTORED_DB)
    await admin_sql(url, [
        f'DROP DATABASE IF EXISTS "{SOURCE_DB}" WITH (FORCE)',
        f'DROP DATABASE IF EXISTS "{RESTORED_DB}" WITH (FORCE)',
        f'CREATE DATABASE "{SOURCE_DB}"',
        f'CREATE DATABASE "{RESTORED_DB}"',
    ])
    print(f"- created {SOURCE_DB} and {RESTORED_DB}")

    run_alembic(source_url)
    engine, factory = sessions_for(source_url)
    try:
        state = await seed(factory)
        before = await snapshot(factory)
    finally:
        await engine.dispose()
    print("- seeded a credited deposit, a credited RUB order, a submitted payout and a settled hand")
    if before["revision"] != EXPECTED_MIGRATION_REVISION:
        raise CheckFailed(f"source is at {before['revision']}, the app expects {EXPECTED_MIGRATION_REVISION}")

    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as handle:
        dump_path = Path(handle.name)
    try:
        with dump_path.open("wb") as target:
            postgres_tool("pg_dump", ["-d", SOURCE_DB], stdout=target)
        print(f"- dumped {dump_path.stat().st_size // 1024} KiB")
        with dump_path.open("rb") as source:
            postgres_tool(
                "psql", ["-v", "ON_ERROR_STOP=1", "-q", "-d", RESTORED_DB],
                stdin=source, stdout=subprocess.DEVNULL,
            )
        print("- restored into a database that has never run the application")
    finally:
        if not keep:
            dump_path.unlink(missing_ok=True)

    engine, factory = sessions_for(restored_url)
    try:
        restored = await snapshot(factory)
        gaps = differences(before, restored)
        if gaps:
            raise CheckFailed("the restored copy is not the backup:\n  " + "\n  ".join(gaps))
        print(f"- restored copy matches: {restored['counts']} at {restored['revision']}")

        for line in await replay(factory, state):
            print(f"    {line}")
        after = await snapshot(factory)
        moved = differences(restored, after)
        if moved:
            raise CheckFailed("the replay changed money or history:\n  " + "\n  ".join(moved))
    finally:
        await engine.dispose()

    print("OK: a restored backup credits, pays and settles nothing a second time")
    if not keep:
        await admin_sql(url, [
            f'DROP DATABASE IF EXISTS "{SOURCE_DB}" WITH (FORCE)',
            f'DROP DATABASE IF EXISTS "{RESTORED_DB}" WITH (FORCE)',
        ])
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="leave the dump and both databases behind")
    options = parser.parse_args()
    try:
        raise SystemExit(run_async(main(options.keep)))
    except CheckFailed as failure:
        print(f"FAIL: {failure}")
        raise SystemExit(1)
