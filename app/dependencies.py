from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select

from cash.access import CashAccessDenied, CashOperator, ensure_cash_access
from online.catalogue import CASH_USDT
from online.schema import auth_sessions, cash_operators, poker_tables, users


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
        ensure_cash_access(
            request.app.state.settings.cash_mode, user.auth_method,
            user.telegram_user_id, getattr(request.app.state.settings, "cash_allowlist", ()),
        )
    except CashAccessDenied as exc:
        status = 404 if request.app.state.settings.cash_mode == "off" else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return user


async def get_cash_operator(
    request: Request,
    api_key: str | None = Header(default=None, alias="X-Cash-Admin-Key"),
    actor_id: str | None = Header(default=None, alias="X-Cash-Operator-Telegram-Id"),
) -> CashOperator:
    settings = request.app.state.settings
    # Any live mode needs its operators -- production more than mock, because
    # that is where a P2P payout is moderated by hand.
    if settings.cash_mode == "off":
        raise HTTPException(status_code=404, detail="cash operator control is disabled")
    expected = settings.cash_admin_api_key
    if not expected:
        raise HTTPException(status_code=503, detail="cash operator authentication is not configured")
    if not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="invalid cash operator service key")
    try:
        telegram_user_id = int(actor_id or "")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid cash operator identity") from exc
    async with request.app.state.session_factory() as session:
        row = (await session.execute(select(cash_operators).where(
            cash_operators.c.telegram_user_id == telegram_user_id,
            cash_operators.c.active.is_(True),
        ))).mappings().first()
    if row is None:
        raise HTTPException(status_code=403, detail="cash operator is not active")
    return CashOperator(row["id"], row["telegram_user_id"], row["tenant_id"], row["role"])


async def require_play_table_user(
    table_id: str, request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Authenticate a table viewer and apply the CASH mode gate by asset."""
    async with request.app.state.session_factory() as session:
        asset = await session.scalar(select(poker_tables.c.asset).where(poker_tables.c.id == table_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="table not found")
    if asset == CASH_USDT:
        try:
            ensure_cash_access(
                request.app.state.settings.cash_mode, user.auth_method,
                user.telegram_user_id, getattr(request.app.state.settings, "cash_allowlist", ()),
            )
        except CashAccessDenied as exc:
            status = 404 if request.app.state.settings.cash_mode == "off" else 403
            raise HTTPException(status_code=status, detail=str(exc)) from exc
    return user
