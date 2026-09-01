from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from cash.access import CashAccessDenied, ensure_cash_access
from online.catalogue import CASH_USDT
from online.schema import auth_sessions, poker_tables, users


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    tenant_id: str
    telegram_user_id: int
    display_name: str
    auth_method: str = "legacy"


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
                    auth_sessions.c.auth_method,
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


async def get_cash_user(
    request: Request, user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    try:
        ensure_cash_access(request.app.state.settings.cash_mode, user.auth_method)
    except CashAccessDenied as exc:
        status = 404 if request.app.state.settings.cash_mode == "off" else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return user


async def require_play_table_user(
    table_id: str, request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Keep every existing table route on PLAY until the CASH runtime exists."""
    async with request.app.state.session_factory() as session:
        asset = await session.scalar(select(poker_tables.c.asset).where(poker_tables.c.id == table_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="table not found")
    if asset == CASH_USDT:
        try:
            ensure_cash_access(request.app.state.settings.cash_mode, user.auth_method)
        except CashAccessDenied as exc:
            status = 404 if request.app.state.settings.cash_mode == "off" else 403
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        raise HTTPException(status_code=409, detail="CASH table runtime is not enabled")
    return user
