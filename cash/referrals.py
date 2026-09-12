"""Who brought whom.

A referral binding is one row, written once, when the account is created. It
is not an attribute of the account that a later link can change: the primary
key is the whole of the immutability, and nothing in this package ever updates
`referrer_id`. What that buys is the answer to the obvious attack -- open the
app through your own link after the profitable months have already happened.

The code is an entity of its own and not the tenant the player arrived
through. A tenant is a brand with a bot behind it; a code is one person's
invitation, and the two answer different questions.

Nothing here decides money. It decides attribution; `cash.settlement` decides
what, if anything, that attribution is worth.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from online.schema import referral_codes, referral_settlements, referrals, users


#: No look-alike characters: a code is read off a screen and typed back.
ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
CODE_LENGTH = 8
#: What the deep link carries, so a referral start payload is never mistaken
#: for a login nonce -- the bot's /start already means one thing.
LINK_PREFIX = "r"


def normalise(code: str | None) -> str | None:
    """The code as stored, or None for anything that cannot be one."""
    if not isinstance(code, str):
        return None
    candidate = code.strip().upper()
    if candidate.startswith(LINK_PREFIX.upper()) and len(candidate) == CODE_LENGTH + 1:
        candidate = candidate[1:]
    if len(candidate) != CODE_LENGTH or any(char not in ALPHABET for char in candidate):
        return None
    return candidate


def start_payload(code: str) -> str:
    """What goes into `?start=` / `?startapp=` for this code."""
    return f"{LINK_PREFIX}{code}"


def web_link(host: str, code: str) -> str:
    """The same invitation as a site address, for people who are not in Telegram."""
    return f"https://{host}/?ref={start_payload(code)}"


async def code_for(session, user_id: str) -> str:
    """This user's own code, made the first time anybody asks for it."""
    existing = await session.scalar(
        select(referral_codes.c.code).where(referral_codes.c.user_id == user_id)
    )
    if existing:
        return existing
    for _ in range(8):
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        try:
            async with session.begin_nested():
                await session.execute(referral_codes.insert().values(
                    code=code, user_id=user_id,
                ))
            return code
        except IntegrityError:
            # Either the code collided or another request made this user's
            # code first. Both are answered by reading it back.
            existing = await session.scalar(
                select(referral_codes.c.code).where(referral_codes.c.user_id == user_id)
            )
            if existing:
                return existing
    raise RuntimeError("could not allocate a referral code")


async def bind(session, *, user_id: str, code: str | None, now: datetime | None = None) -> str | None:
    """Attach this account to the code's owner, once and for all.

    Every refusal is silent and returns None: a link that cannot be honoured
    is not an error the person following it can do anything about. What is
    refused, and why:

    * a second binding -- the first one stands, whatever the new link says;
    * yourself -- the obvious one;
    * the person you referred -- a two-account ring is a self-referral with a
      step in it, and pays out on the same money twice;
    * an internal account on either side -- owners and partners are paid
      through the partner's share, and would otherwise be paid twice.
    """
    normalised = normalise(code)
    if normalised is None:
        return None
    bound = await session.scalar(
        select(referrals.c.referrer_id).where(referrals.c.user_id == user_id)
    )
    if bound is not None:
        return bound
    referrer_id = await session.scalar(
        select(referral_codes.c.user_id).where(referral_codes.c.code == normalised)
    )
    if not referrer_id or referrer_id == user_id:
        return None
    parties = dict((await session.execute(select(users.c.id, users.c.internal).where(
        users.c.id.in_([user_id, referrer_id]),
    ))).all())
    if len(parties) != 2 or any(parties.values()):
        return None
    upstream = await session.scalar(
        select(referrals.c.referrer_id).where(referrals.c.user_id == referrer_id)
    )
    if upstream == user_id:
        return None
    try:
        async with session.begin_nested():
            await session.execute(referrals.insert().values(
                user_id=user_id, referrer_id=referrer_id, code=normalised,
                bound_at=now or datetime.now(timezone.utc),
            ))
    except IntegrityError:
        return await session.scalar(
            select(referrals.c.referrer_id).where(referrals.c.user_id == user_id)
        )
    return referrer_id


async def summary(session, user_id: str) -> dict[str, object]:
    """What the player sees: their code, their group, and what it has paid."""
    code = await code_for(session, user_id)
    invited = await session.scalar(select(func.count()).select_from(referrals).where(
        referrals.c.referrer_id == user_id,
    ))
    totals = dict((await session.execute(
        select(referral_settlements.c.status, func.coalesce(func.sum(
            referral_settlements.c.amount_micros,
        ), 0)).where(referral_settlements.c.referrer_id == user_id)
        .group_by(referral_settlements.c.status)
    )).all())
    carryover = await session.scalar(
        select(referral_settlements.c.carryover_after_micros).where(
            referral_settlements.c.referrer_id == user_id,
            referral_settlements.c.source == "cube",
        ).order_by(referral_settlements.c.period_start.desc()).limit(1)
    )
    return {
        "code": code,
        "start_payload": start_payload(code),
        "invited": int(invited or 0),
        "pending_micros": int(totals.get("pending", 0)),
        "paid_micros": int(totals.get("available", 0)),
        # Negative: what the group's losses still have to earn back before the
        # next reward. Shown because a referrer who cannot see it will read a
        # zero payout as a bug.
        "carryover_micros": int(carryover or 0),
    }


async def mark_internal(session, telegram_user_ids) -> int:
    """Owners, partners and service accounts, as configured. Idempotent."""
    ids = [int(value) for value in telegram_user_ids]
    if not ids:
        return 0
    result = await session.execute(
        update(users).where(
            users.c.telegram_user_id.in_(ids), users.c.internal.is_(False),
        ).values(internal=True)
    )
    return result.rowcount or 0
