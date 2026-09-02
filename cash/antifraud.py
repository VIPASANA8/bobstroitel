from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select

from cash.amounts import micros_to_usdt
from online.schema import cash_fiat_orders


# What a user has asked for and not lost: open orders plus credited ones.
COUNTED_STATES = ("requesting", "awaiting_user", "waiting_trader", "clarifying", "credited")


class DepositRefused(ValueError):
    """An antifraud limit, not a protocol error: later, the same request is fine."""


@dataclass(frozen=True)
class DepositPolicy:
    orders_per_hour: int = 6
    daily_micros: int = 0

    @classmethod
    def from_settings(cls, settings) -> "DepositPolicy":
        return cls(
            orders_per_hour=getattr(settings, "cash_orders_per_hour", 6),
            daily_micros=getattr(settings, "cash_daily_deposit_micros", 0),
        )


async def screen_fiat_order(session, *, user_id, amount_micros, now, policy):
    """Refuse the request before a trader is asked for anything. Zero means off."""
    if policy.orders_per_hour:
        recent = await session.scalar(select(func.count()).select_from(cash_fiat_orders).where(
            cash_fiat_orders.c.user_id == user_id,
            cash_fiat_orders.c.created_at >= now - timedelta(hours=1),
        ))
        if recent >= policy.orders_per_hour:
            raise DepositRefused("too many RUB requests in the last hour, try again later")
    if policy.daily_micros:
        asked = await session.scalar(select(func.coalesce(
            func.sum(cash_fiat_orders.c.requested_micros), 0,
        )).where(
            cash_fiat_orders.c.user_id == user_id,
            cash_fiat_orders.c.status.in_(COUNTED_STATES),
            cash_fiat_orders.c.created_at >= now - timedelta(days=1),
        ))
        if asked + amount_micros > policy.daily_micros:
            raise DepositRefused(
                f"the daily RUB deposit limit of {micros_to_usdt(policy.daily_micros)} USDT is reached"
            )


async def cancelled_after_payment(session, *, since, threshold=3):
    """Users who said they had paid and then cancelled, more often than looks honest.

    A signal for an operator, never an automatic freeze: the same pattern fits a
    trader who kept going silent.
    """
    rows = await session.execute(
        select(cash_fiat_orders.c.user_id, func.count().label("cancellations")).where(
            cash_fiat_orders.c.status == "cancelled",
            cash_fiat_orders.c.user_confirmed.is_(True),
            cash_fiat_orders.c.updated_at >= since,
        ).group_by(cash_fiat_orders.c.user_id).having(func.count() >= threshold)
    )
    return dict(rows.all())
