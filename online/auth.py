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

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.schema import auth_sessions, tenants, user_tenant_visits, users


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


@dataclass(frozen=True)
class AuthResult:
    token: str
    user_id: str
    tenant_id: str
    telegram_user_id: int
    display_name: str
    acquisition_tenant_slug: str
    access_tenant_slug: str


class AuthService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_tokens: Mapping[str, str],
        *,
        now: Callable[[], int] = lambda: int(time.time()),
        session_ttl_seconds: int = 7 * 24 * 60 * 60,
        telegram_auth_max_age_seconds: int = 15 * 60,
    ) -> None:
        self.session_factory = session_factory
        self.tenant_tokens = dict(tenant_tokens)
        self.now = now
        self.session_ttl_seconds = session_ttl_seconds
        self.telegram_auth_max_age_seconds = telegram_auth_max_age_seconds

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
            )

    async def authenticate_dev(
        self, tenant_slug: str, telegram_user_id: int, display_name: str
    ) -> AuthResult:
        async with self.session_factory() as session:
            tenant_row = await self._tenant(session, tenant_slug)
            return await self._authenticate_identity(
                session, tenant_row, telegram_user_id, display_name
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
        self, session: AsyncSession, tenant_row, telegram_user_id: int, display_name: str
    ) -> AuthResult:
        tenant_slug = tenant_row["slug"]
        now = datetime.fromtimestamp(int(self.now()), tz=timezone.utc)
        user_row = (
            await session.execute(
                select(users).where(users.c.telegram_user_id == telegram_user_id)
            )
        ).mappings().first()
        if user_row is None:
            user_id = uuid.uuid4().hex
            acquisition_tenant_id = tenant_row["id"]
            await session.execute(users.insert().values(
                id=user_id,
                telegram_user_id=telegram_user_id,
                display_name=display_name,
                acquisition_tenant_id=acquisition_tenant_id,
                created_at=now,
                updated_at=now,
            ))
            acquisition_slug = tenant_slug
        else:
            user_id = user_row["id"]
            acquisition_tenant_id = user_row["acquisition_tenant_id"]
            await session.execute(
                update(users)
                .where(users.c.id == user_id)
                .values(display_name=display_name, updated_at=now)
            )
            acquisition_slug = (
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
        )

    @staticmethod
    def _display_name(user: dict) -> str:
        # First name only, never @username -- a handle at the table reads as
        # a login, not a player, and avatarInitials() on the client splits a
        # display name on whitespace, so "@handle" was rendering as just "@".
        first_name = user.get("first_name")
        if isinstance(first_name, str) and first_name.strip():
            return first_name.strip()
        return str(user["id"])
