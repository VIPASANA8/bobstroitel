from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping
from urllib.parse import parse_qsl

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cash.referrals import bind as bind_referral
from online.schema import auth_login_requests, auth_sessions, tenants, user_tenant_visits, users


def login_code(nonce: str) -> str:
    """The four characters the page shows and the bot repeats back.

    A deep link is a piece of text anybody can forward, so "somebody pressed
    the button" is not on its own proof that the person pressing it is the
    person who asked to log in. This is what makes the difference visible: the
    browser that opened the login shows a code, the bot shows the code it was
    handed, and they only match for the person looking at both.

    Derived from the nonce rather than stored beside it, and hashed rather than
    sliced off it, so the visible half is not a piece of the secret half.
    """
    return hashlib.sha256(f"login-code:{nonce}".encode()).hexdigest()[:4].upper()


def _aware(stamp: datetime) -> datetime:
    """SQLite hands back naive timestamps where PostgreSQL keeps the zone."""
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


class AuthenticationError(ValueError):
    """Raised when Telegram identity data or tenant access is invalid."""


def verify_init_data(init_data: str, bot_token: str, now: int, max_age_seconds: int) -> dict:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    supplied_hash = pairs.pop("hash", "")
    if not supplied_hash or "auth_date" not in pairs or "user" not in pairs:
        raise AuthenticationError("invalid Telegram signature")
    check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied_hash):
        raise AuthenticationError("invalid Telegram signature")
    try:
        auth_date = int(pairs["auth_date"])
        user = json.loads(pairs["user"])
        if not isinstance(user, dict) or "id" not in user:
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuthenticationError("invalid Telegram initData") from exc
    if now - auth_date > max_age_seconds or auth_date > now + 30:
        raise AuthenticationError("Telegram initData expired")
    return user


def start_param(init_data: str) -> str | None:
    """The `start_param` of an initData whose signature already checked out.

    Reading it again from the same verified string is not a second trust
    decision -- the whole string was signed together, this field included.
    It is where a referral link that opened the Mini App arrives.
    """
    return dict(parse_qsl(init_data, keep_blank_values=True)).get("start_param") or None


def app_link(username: str, has_main_web_app: bool) -> str:
    """Where "открыть в Telegram" goes.

    A bot with a main Mini App opens straight into it; without one the link
    lands in the bot's chat, where its menu button is. Both are t.me links
    rather than tg:// ones, so a browser with no Telegram installed gets
    Telegram's own page instead of a dead scheme.
    """
    return f"https://t.me/{username}" + ("?startapp" if has_main_web_app else "")


async def resolve_login_bots(tenant_tokens: Mapping[str, str]) -> dict[str, dict[str, str]]:
    """Ask Telegram what each tenant's token belongs to, and where its app lives.

    The token already says which bot it is, so a second setting carrying the
    same fact would only ever be wrong when the two disagreed. Two things come
    back: the @username the login widget needs, and the link that opens the
    Mini App itself -- `?startapp` when the bot has a main one, the bot's chat
    otherwise, where its menu button is.

    Anything that fails is left out, and the page then offers what it can.
    """
    resolved: dict[str, dict[str, str]] = {}
    for slug, token in tenant_tokens.items():
        if not token:
            continue
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            bot = response.json()["result"]
            username = bot["username"]
        except Exception:
            continue
        if not isinstance(username, str) or not username:
            continue
        resolved[slug] = {
            "username": username,
            "app_url": app_link(username, bool(bot.get("has_main_web_app"))),
        }
    return resolved


@dataclass(frozen=True)
class AuthResult:
    token: str
    user_id: str
    tenant_id: str
    telegram_user_id: int
    display_name: str
    acquisition_tenant_slug: str
    access_tenant_slug: str
    auth_method: str


class AuthService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_tokens: Mapping[str, str],
        *,
        now: Callable[[], int] = lambda: int(time.time()),
        session_ttl_seconds: int = 7 * 24 * 60 * 60,
        telegram_auth_max_age_seconds: int = 15 * 60,
        internal_telegram_ids: tuple[int, ...] = (),
        #: Long enough to switch to Telegram, find the chat and press Start.
        login_request_ttl_seconds: int = 10 * 60,
    ) -> None:
        self.session_factory = session_factory
        self.tenant_tokens = dict(tenant_tokens)
        self.now = now
        self.session_ttl_seconds = session_ttl_seconds
        self.telegram_auth_max_age_seconds = telegram_auth_max_age_seconds
        self.internal_telegram_ids = frozenset(internal_telegram_ids)
        self.login_request_ttl_seconds = login_request_ttl_seconds

    async def authenticate(self, tenant_slug: str, init_data: str) -> AuthResult:
        async with self.session_factory() as session:
            tenant_row = await self._tenant(session, tenant_slug)
            bot_token = self.tenant_tokens.get(tenant_slug)
            if not bot_token:
                raise AuthenticationError("unknown tenant")
            telegram_user = verify_init_data(
                init_data,
                bot_token,
                int(self.now()),
                self.telegram_auth_max_age_seconds,
            )
            return await self._authenticate_identity(
                session,
                tenant_row,
                int(telegram_user["id"]),
                self._display_name(telegram_user),
                "telegram",
                referral_code=start_param(init_data),
            )

    async def start_login_request(self, tenant_slug: str) -> str:
        """Open a login and return the code the browser sends to the bot."""
        now = datetime.now(timezone.utc)
        nonce = secrets.token_urlsafe(24)
        async with self.session_factory() as session:
            async with session.begin():
                tenant_row = await self._tenant(session, tenant_slug)
                # Codes are short-lived and worthless once spent; sweeping the
                # dead ones here keeps the table from being a place things
                # accumulate, without a job that has to be remembered.
                await session.execute(
                    auth_login_requests.delete().where(auth_login_requests.c.expires_at < now)
                )
                await session.execute(auth_login_requests.insert().values(
                    nonce=nonce,
                    tenant_id=tenant_row["id"],
                    expires_at=now + timedelta(seconds=self.login_request_ttl_seconds),
                ))
        return nonce

    async def pending_login_request(self, tenant_slug: str, nonce: str) -> bool:
        """Is this an open login of this tenant's, waiting to be confirmed?

        The bot asks before it offers anybody a confirm button, so a code that
        is spent, expired, already answered or another tenant's gets the same
        flat "not a login" -- naming which of those it was would tell a
        stranger which codes exist.
        """
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            tenant_row = await self._tenant(session, tenant_slug)
            return bool(await session.scalar(
                select(auth_login_requests.c.nonce).where(
                    auth_login_requests.c.nonce == nonce,
                    auth_login_requests.c.tenant_id == tenant_row["id"],
                    auth_login_requests.c.telegram_user_id.is_(None),
                    auth_login_requests.c.consumed_at.is_(None),
                    auth_login_requests.c.expires_at > now,
                )
            ))

    async def bind_login_request(
        self, tenant_slug: str, nonce: str, telegram_user_id: int, display_name: str
    ) -> bool:
        """Somebody confirmed in the bot. Answer whether that opened a login.

        Scoped to the tenant whose bot delivered it: a code belongs to the site
        that issued it, and one network's bot has no business vouching for a
        login on another's, however it came to know the code.
        """
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            async with session.begin():
                tenant_row = await self._tenant(session, tenant_slug)
                result = await session.execute(
                    update(auth_login_requests)
                    .where(
                        auth_login_requests.c.nonce == nonce,
                        auth_login_requests.c.tenant_id == tenant_row["id"],
                        auth_login_requests.c.telegram_user_id.is_(None),
                        auth_login_requests.c.consumed_at.is_(None),
                        auth_login_requests.c.expires_at > now,
                    )
                    .values(telegram_user_id=telegram_user_id, display_name=display_name)
                )
        return bool(result.rowcount)

    async def claim_login_request(self, tenant_slug: str, nonce: str) -> AuthResult | None:
        """Turn a confirmed code into a session. None while nobody has confirmed.

        The session is the same one the Mini App gets, down to the auth method:
        the bot is Telegram vouching for this person, so the cashier has no
        reason to treat them differently from somebody who came in through it.
        """
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            async with session.begin():
                row = (await session.execute(
                    select(auth_login_requests)
                    .where(auth_login_requests.c.nonce == nonce)
                    .with_for_update()
                )).mappings().first()
                if row is None or row["consumed_at"] is not None:
                    raise AuthenticationError("this login has expired, start again")
                if _aware(row["expires_at"]) <= now:
                    raise AuthenticationError("this login has expired, start again")
                if row["telegram_user_id"] is None:
                    return None
                tenant_row = await self._tenant(session, tenant_slug)
                if tenant_row["id"] != row["tenant_id"]:
                    raise AuthenticationError("unknown tenant")
                await session.execute(
                    update(auth_login_requests)
                    .where(auth_login_requests.c.nonce == nonce)
                    .values(consumed_at=now)
                )
                return await self._authenticate_identity(
                    session,
                    tenant_row,
                    int(row["telegram_user_id"]),
                    row["display_name"] or "Игрок",
                    "telegram",
                )

    async def authenticate_dev(
        self, tenant_slug: str, telegram_user_id: int, display_name: str
    ) -> AuthResult:
        async with self.session_factory() as session:
            tenant_row = await self._tenant(session, tenant_slug)
            return await self._authenticate_identity(
                session, tenant_row, telegram_user_id, display_name, "dev"
            )

    async def authenticate_guest(self, tenant_slug: str) -> AuthResult:
        async with self.session_factory() as session:
            tenant_row = await self._tenant(session, tenant_slug)
            for _ in range(10):
                guest_telegram_id = -secrets.randbelow(9_000_000_000_000_000_000) - 1
                exists = await session.execute(
                    select(users.c.id).where(users.c.telegram_user_id == guest_telegram_id)
                )
                if exists.scalar_one_or_none() is None:
                    return await self._authenticate_identity(
                        session,
                        tenant_row,
                        guest_telegram_id,
                        f"Guest-{secrets.token_hex(3).upper()}",
                        "guest",
                    )
        raise AuthenticationError("could not allocate a guest identity")

    async def revoke_session(self, token: str) -> None:
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            await session.execute(
                update(auth_sessions)
                .where(auth_sessions.c.token_hash == hashlib.sha256(token.encode()).hexdigest())
                .values(revoked_at=now)
            )
            await session.commit()

    async def _tenant(self, session: AsyncSession, tenant_slug: str):
        tenant_row = (
            await session.execute(select(tenants).where(tenants.c.slug == tenant_slug))
        ).mappings().first()
        if not tenant_row or tenant_row["status"] != "active":
            raise AuthenticationError("unknown tenant")
        return tenant_row

    async def _authenticate_identity(
        self, session: AsyncSession, tenant_row, telegram_user_id: int, display_name: str,
        auth_method: str, referral_code: str | None = None,
    ) -> AuthResult:
        tenant_slug = tenant_row["slug"]
        now = datetime.fromtimestamp(int(self.now()), tz=timezone.utc)
        user_id, acquisition_tenant_id = await self._ensure_user(
            session, tenant_row, telegram_user_id, display_name, referral_code, now,
        )
        acquisition_slug = tenant_slug if acquisition_tenant_id == tenant_row["id"] else (
            await session.execute(
                select(tenants.c.slug).where(tenants.c.id == acquisition_tenant_id)
            )
        ).scalar_one()

        visit = (
            await session.execute(
                select(user_tenant_visits.c.id).where(
                    user_tenant_visits.c.user_id == user_id,
                    user_tenant_visits.c.tenant_id == tenant_row["id"],
                )
            )
        ).scalar_one_or_none()
        if visit is None:
            await session.execute(user_tenant_visits.insert().values(
                id=uuid.uuid4().hex,
                user_id=user_id,
                tenant_id=tenant_row["id"],
                first_seen_at=now,
                last_seen_at=now,
            ))
        else:
            await session.execute(
                update(user_tenant_visits)
                .where(user_tenant_visits.c.id == visit)
                .values(last_seen_at=now)
            )

        token = secrets.token_urlsafe(32)
        await session.execute(auth_sessions.insert().values(
            id=uuid.uuid4().hex,
            user_id=user_id,
            tenant_id=tenant_row["id"],
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            auth_method=auth_method,
            expires_at=now + timedelta(seconds=self.session_ttl_seconds),
            created_at=now,
        ))
        await session.commit()
        return AuthResult(
            token=token,
            user_id=user_id,
            tenant_id=tenant_row["id"],
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            acquisition_tenant_slug=acquisition_slug,
            access_tenant_slug=tenant_slug,
            auth_method=auth_method,
        )

    async def register(self, tenant_slug: str, telegram_user_id: int, display_name: str) -> str:
        """The account behind this Telegram user, made now if there is none.

        For the bot, which meets people before they ever open the app: a
        referral link needs an account to be paid into, and a /start is enough
        proof of who is asking -- Telegram delivered it.
        """
        now = datetime.fromtimestamp(int(self.now()), tz=timezone.utc)
        async with self.session_factory() as session:
            async with session.begin():
                tenant_row = await self._tenant(session, tenant_slug)
                user_id, _ = await self._ensure_user(
                    session, tenant_row, telegram_user_id, display_name, None, now,
                )
        return user_id

    async def _ensure_user(
        self, session: AsyncSession, tenant_row, telegram_user_id: int, display_name: str,
        referral_code: str | None, now: datetime,
    ) -> tuple[str, str]:
        """(user_id, acquisition_tenant_id), inserting the user on first sight."""
        user_row = (
            await session.execute(
                select(users).where(users.c.telegram_user_id == telegram_user_id)
            )
        ).mappings().first()
        if user_row is not None:
            await session.execute(
                update(users)
                .where(users.c.id == user_row["id"])
                .values(display_name=display_name, updated_at=now)
            )
            return user_row["id"], user_row["acquisition_tenant_id"]
        user_id = uuid.uuid4().hex
        await session.execute(users.insert().values(
            id=user_id,
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            acquisition_tenant_id=tenant_row["id"],
            internal=telegram_user_id in self.internal_telegram_ids,
            created_at=now,
            updated_at=now,
        ))
        # Only here, and only once: a link followed by an account that
        # already has a history behind it would let somebody claim a player
        # after the profitable months, which is what `referrals` refuses by
        # having the user as its primary key.
        await bind_referral(session, user_id=user_id, code=referral_code, now=now)
        return user_id, tenant_row["id"]

    @staticmethod
    def _display_name(user: dict) -> str:
        # First name only, never @username -- a handle at the table reads as
        # a login, not a player, and avatarInitials() on the client splits a
        # display name on whitespace, so "@handle" was rendering as just "@".
        first_name = user.get("first_name")
        if isinstance(first_name, str) and first_name.strip():
            return first_name.strip()
        return str(user["id"])
