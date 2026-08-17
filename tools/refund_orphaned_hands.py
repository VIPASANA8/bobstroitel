"""One-time reconciliation: refund the buy-ins that abandoned (orphaned)
hands left stuck in a table's escrow.

An orphaned hand is one that never went terminal but is no longer the
table's current hand — the runtime moved on (paused-table recovery before
the auto-heal fix landed, or a manual intervention) without ever crediting
each seat back through the ledger. hand_players.start_stack_units is the one
number we can vouch for: exactly what that participant brought to the hand.
We refund that, not a guess at what they would have won or lost.

Only user participants are refunded; a bot's stake is house money and
self-corrects the next time its seat gets refilled.

Usage:
    python -m tools.refund_orphaned_hands            # dry run, prints only
    python -m tools.refund_orphaned_hands --apply     # actually transfers
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

from online.database import create_database
from online.ledger import PlayLedger
from online.schema import hand_players, hands, table_runtimes, users


async def find_orphaned_refunds(session_factory):
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    hands.c.table_id, hands.c.id.label("hand_id"),
                    hand_players.c.participant_id, hand_players.c.start_stack_units,
                    users.c.display_name,
                )
                .select_from(hands)
                .join(hand_players, hand_players.c.hand_id == hands.c.id)
                .join(users, users.c.id == hand_players.c.participant_id)
                .where(hands.c.terminal.is_(False))
            )
        ).mappings().all()
        current_hands = dict(
            (
                await session.execute(
                    select(table_runtimes.c.table_id, table_runtimes.c.private_state_json["hand_id"].as_string())
                )
            ).all()
        )
    return [
        row for row in rows
        if row["hand_id"] != current_hands.get(row["table_id"])
    ]


async def main(apply: bool) -> None:
    database_url = os.environ["POKER8_DATABASE_URL"]
    engine, session_factory = create_database(database_url)
    ledger = PlayLedger(session_factory)
    refunds = await find_orphaned_refunds(session_factory)
    if not refunds:
        print("No orphaned-hand refunds found.")
        await engine.dispose()
        return

    total = 0
    for row in refunds:
        total += row["start_stack_units"]
        print(
            f"{'REFUND' if apply else 'WOULD REFUND'} "
            f"{row['start_stack_units']} units -> {row['display_name']} ({row['participant_id']}) "
            f"table={row['table_id']} hand={row['hand_id']}"
        )
        if apply:
            key = f"reconcile-orphaned-hand:{row['hand_id']}:{row['participant_id']}"
            await ledger.return_stack(
                row["participant_id"], row["table_id"], key, amount_units=row["start_stack_units"],
            )
    print(f"Total: {total} units across {len(refunds)} refund(s).")
    if not apply:
        print("Dry run only. Re-run with --apply to transfer.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
