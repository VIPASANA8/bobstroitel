from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from online.schema import cash_rub_rates


async def current_rub_rate(session) -> int | None:
    """Kopecks per USDT as last set by an operator; None until somebody has."""
    return await session.scalar(select(cash_rub_rates.c.kopecks_per_usdt).order_by(
        cash_rub_rates.c.created_at.desc(), cash_rub_rates.c.id.desc(),
    ).limit(1))


async def set_rub_rate(session, *, kopecks_per_usdt: int, actor: str, note: str | None = None) -> str:
    if type(kopecks_per_usdt) is not int or not 0 < kopecks_per_usdt <= 100_000_00:
        raise ValueError("the RUB rate is kopecks per USDT, between 0.01 and 100000")
    rate_id = uuid4().hex
    await session.execute(cash_rub_rates.insert().values(
        id=rate_id, kopecks_per_usdt=kopecks_per_usdt, actor=actor, note=note or None,
    ))
    return rate_id


def quote_kopecks(payout_micros: int, kopecks_per_usdt: int) -> int:
    """Roubles for the USDT that actually leaves, rounded down to the kopeck."""
    return payout_micros * kopecks_per_usdt // 1_000_000
