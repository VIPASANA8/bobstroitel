from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from online.schema import cash_user_holds


class CashUserFrozen(PermissionError):
    """A hold stops new money in or out.

    It never traps money already at risk: a credited deposit still lands, a
    seated player still leaves, and a settled hand still pays. Freezing an
    account that is mid-payment must not turn the user's own money into a
    hostage of the investigation.
    """


#: A break shorter than this is not a break, it is a pause between hands.
MIN_BREAK = timedelta(hours=1)
#: Long enough to cover a self-exclusion; past this an operator hold is meant.
MAX_BREAK = timedelta(days=365)

_LIVE = or_(cash_user_holds.c.until.is_(None), cash_user_holds.c.until > func.now())


async def assert_not_frozen(session, user_id: str) -> None:
    held = (await session.execute(select(
        cash_user_holds.c.operator_id, cash_user_holds.c.until,
    ).where(cash_user_holds.c.user_id == user_id, _LIVE))).mappings().first()
    if held is None:
        return
    if held["operator_id"] is None:
        # Their own decision, so they get the one detail that matters.
        raise CashUserFrozen(
            f"you asked for a break from cash play until {held['until']:%Y-%m-%d %H:%M} UTC"
        )
    # The operator's reason stays with the operator.
    raise CashUserFrozen("cash operations are on hold for this account")


async def take_a_break(session, *, user_id: str, tenant_id: str, hours: int,
                       now: datetime | None = None) -> datetime:
    """Let a player shut themselves out of CASH for a while.

    One mechanism covers both names on the plan: a short one is a cooling-off,
    a long one is self-exclusion. It can be started and extended, never
    shortened and never cancelled -- a break you can call off the moment you
    want to play again protects nobody. An operator hold is left untouched,
    because the user must not be able to overwrite an investigation with a
    break of their own choosing.
    """
    if type(hours) is not int or not MIN_BREAK <= timedelta(hours=hours) <= MAX_BREAK:
        raise ValueError(
            f"a break lasts between {MIN_BREAK // timedelta(hours=1)} hour and "
            f"{MAX_BREAK // timedelta(days=1)} days"
        )
    now = now or datetime.now(timezone.utc)
    until = now + timedelta(hours=hours)
    existing = (await session.execute(select(
        cash_user_holds.c.operator_id, cash_user_holds.c.until,
    ).where(cash_user_holds.c.user_id == user_id).with_for_update())).mappings().first()
    if existing is not None and existing["operator_id"] is not None:
        raise CashUserFrozen("cash operations are on hold for this account")
    if existing is not None and existing["until"] is not None and existing["until"] >= until:
        return existing["until"]
    await session.execute(pg_insert(cash_user_holds).values(
        user_id=user_id, tenant_id=tenant_id, reason="self-imposed break",
        operator_id=None, until=until,
    ).on_conflict_do_update(
        index_elements=[cash_user_holds.c.user_id],
        set_={"until": until, "reason": "self-imposed break"},
    ))
    return until


async def clear_expired_breaks(session) -> int:
    """Sweep breaks that have run out. Operator holds never expire and stay."""
    result = await session.execute(delete(cash_user_holds).where(
        cash_user_holds.c.operator_id.is_(None),
        cash_user_holds.c.until.is_not(None),
        cash_user_holds.c.until <= func.now(),
    ))
    return result.rowcount or 0
