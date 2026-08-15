from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select

from online.schema import auth_sessions, users


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    tenant_id: str
    telegram_user_id: int
    display_name: str


async def get_current_user(request: Request) -> AuthenticatedUser:
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        row = (
            await session.execute(
                select(
                    auth_sessions.c.user_id,
                    auth_sessions.c.tenant_id,
                    users.c.telegram_user_id,
                    users.c.display_name,
                )
                .join(users, users.c.id == auth_sessions.c.user_id)
                .where(
                    auth_sessions.c.token_hash == token_hash,
                    auth_sessions.c.revoked_at.is_(None),
                    auth_sessions.c.expires_at > now,
                )
            )
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return AuthenticatedUser(**row)
