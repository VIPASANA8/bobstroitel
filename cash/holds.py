from __future__ import annotations

from sqlalchemy import select

from online.schema import cash_user_holds


class CashUserFrozen(PermissionError):
    """A hold stops new money in or out.

    It never traps money already at risk: a credited deposit still lands, a
    seated player still leaves, and a settled hand still pays. Freezing an
    account that is mid-payment must not turn the user's own money into a
    hostage of the investigation.
    """


async def assert_not_frozen(session, user_id: str) -> None:
    held = await session.scalar(select(cash_user_holds.c.user_id).where(
        cash_user_holds.c.user_id == user_id,
    ))
    if held is not None:
        # The operator's reason stays with the operator.
        raise CashUserFrozen("cash operations are on hold for this account")
