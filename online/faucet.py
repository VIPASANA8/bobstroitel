"""The daily faucet -- what puts a broke practice player back in the game.

Practice chips are not money, so running out of them is not a state anybody
should be stuck in. They are also not worth handing out on demand, or the
number on the profile stops meaning anything. So the rule is narrow: once a
day, and only for somebody who cannot afford to sit down anywhere at all.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select

from online.catalogue import PLAY
from online.schema import play_transactions, poker_tables, table_seats


#: What a new player starts with, and what the faucet tops back up to.
WELCOME_UNITS = 100_000
#: One buy-in at the cheapest table in the lobby: 40 big blinds of 1.00.
#: Below this a player cannot take a seat anywhere, and that -- not "zero" --
#: is what being out of chips actually means. Somebody who can still sit down
#: has a game to play and gets nothing.
FLOOR_UNITS = 4_000
REFILL_EVERY = timedelta(hours=24)


def _aware(stamp: datetime) -> datetime:
    """SQLite hands back naive timestamps where PostgreSQL keeps the zone."""
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


async def refill_if_broke(session_factory, ledger, user_id: str, *, now: datetime | None = None):
    """Return (available_units, next_refill_at), topping the player up first.

    next_refill_at is None unless the player is under the floor *and* the
    faucet is shut -- the only time there is anything to wait for. Above the
    floor there is nothing to say, and after a successful refill there is
    nothing to wait for either.
    """
    now = now or datetime.now(timezone.utc)
    available = await ledger.available_units(user_id)
    async with session_factory() as session:
        # Chips sitting in front of them at a table are still theirs. Without
        # this, taking a seat with the last of a stack reads as being broke
        # and the faucet mints a second one on top of it.
        in_play = sum(
            (
                await session.execute(
                    select(table_seats.c.stack_units)
                    .join(poker_tables, poker_tables.c.id == table_seats.c.table_id)
                    .where(
                        table_seats.c.user_id == user_id,
                        table_seats.c.state.in_(("seated", "held", "leaving")),
                        poker_tables.c.asset == PLAY,
                    )
                )
            ).scalars().all()
        )
        if available + in_play >= FLOOR_UNITS:
            return available, None
        # Every faucet grant counts, the welcome one included: a player who
        # was handed a stack an hour ago and spent it has not been waiting a
        # day for anything.
        last = (
            await session.execute(
                select(play_transactions.c.created_at)
                .where(
                    play_transactions.c.kind == "faucet_grant",
                    play_transactions.c.reference_type == "user",
                    play_transactions.c.reference_id == user_id,
                )
                .order_by(desc(play_transactions.c.created_at))
                .limit(1)
            )
        ).scalar_one_or_none()
    if last is not None:
        opens_at = _aware(last) + REFILL_EVERY
        if opens_at > now:
            return available, opens_at
    # Keyed on the day rather than the moment: two requests arriving together
    # would both pass the check above, and the unique constraint on the
    # idempotency key is what actually stops the second stack being minted.
    result = await ledger.grant(
        user_id,
        WELCOME_UNITS - available,
        f"refill:{user_id}:{now.date().isoformat()}",
    )
    return result.available_units, None
