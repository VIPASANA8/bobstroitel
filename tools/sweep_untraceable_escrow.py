"""One-time reconciliation: sweep table escrow that exceeds what any currently
seated user is owed, back to the faucet it originally came from.

tools/refund_orphaned_hands.py already returns every stray unit that a
hand_players record can trace to a specific participant. What is left after
that -- confirmed stable across repeated checks in this table's case -- has
no hand record clean enough to attribute to anyone. Leaving it in the table's
escrow account permanently trips EscrowIntegrityMonitor and leaves play money
sitting nowhere in particular; it is swept back to the faucet it was minted
from instead, with a full ledger audit trail, rather than left unexplained or
credited to a guess.

Never touches a seat that is currently occupied: the swept amount is exactly
(current escrow balance) minus (sum of stacks at seated/held/leaving seats),
recomputed at the moment this runs.

Usage:
    python -m tools.sweep_untraceable_escrow            # dry run, prints only
    python -m tools.sweep_untraceable_escrow --apply     # actually transfers
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date

from sqlalchemy import func, select

from online.database import create_database
from online.ledger import FAUCET_OWNER, PlayLedger
from online.schema import play_accounts, table_seats

ACTIVE_SEAT_STATES = ("seated", "held", "leaving")


async def find_excess(session_factory) -> list[dict]:
    async with session_factory() as session:
        escrow_rows = (
            await session.execute(
                select(play_accounts.c.owner_id, play_accounts.c.balance_units)
                .where(play_accounts.c.owner_kind == "table", play_accounts.c.account_kind == "escrow")
            )
        ).all()
        seated_totals = dict(
            (
                await session.execute(
                    select(table_seats.c.table_id, func.sum(table_seats.c.stack_units))
                    .where(table_seats.c.occupant_kind == "user", table_seats.c.state.in_(ACTIVE_SEAT_STATES))
                    .group_by(table_seats.c.table_id)
                )
            ).all()
        )
    excess = []
    for table_id, balance in escrow_rows:
        owed = int(seated_totals.get(table_id, 0) or 0)
        stray = int(balance) - owed
        if stray > 0:
            excess.append({"table_id": table_id, "balance": int(balance), "owed": owed, "excess": stray})
    return excess


async def main(apply: bool) -> None:
    database_url = os.environ["POKER8_DATABASE_URL"]
    engine, session_factory = create_database(database_url)
    ledger = PlayLedger(session_factory)

    rows = await find_excess(session_factory)
    if not rows:
        print("No untraceable escrow found.")
        await engine.dispose()
        return

    total = 0
    for row in rows:
        total += row["excess"]
        print(
            f"{'SWEEP' if apply else 'WOULD SWEEP'} {row['excess']} units from table={row['table_id']} "
            f"(escrow={row['balance']}, owed to seated users={row['owed']})"
        )
        if apply:
            key = f"reconcile-untraceable-escrow:{row['table_id']}:{date.today().isoformat()}"
            await ledger._transfer(
                # play_transactions.kind has a DB check constraint; "return" is
                # the same shape release_system_seat already uses for handing
                # an account's balance back to the faucet it came from.
                kind="return",
                reference_type="table",
                reference_id=row["table_id"],
                idempotency_key=key,
                entries=[("table", row["table_id"], "escrow"), FAUCET_OWNER],
                amounts=[-row["excess"], row["excess"]],
                available_owner=FAUCET_OWNER,
                session=None,
            )
    print(f"Total: {total} units across {len(rows)} table(s).")
    if not apply:
        print("Dry run only. Re-run with --apply to transfer.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
