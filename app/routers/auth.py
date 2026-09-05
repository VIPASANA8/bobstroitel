from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from online.auth import AuthenticationError
from online.faucet import WELCOME_UNITS, refill_if_broke
from online.ratelimit import WindowLimiter, caller


router = APIRouter(prefix="/api/auth", tags=["auth"])

#: Generous for a person opening the Mini App, including retries and a reload
#: or two; nowhere near enough to be worth pointing a script at.
LOGIN_LIMIT, LOGIN_WINDOW = 20, 60


def _throttle(request: Request) -> None:
    """The counter belongs to the app, not to the module.

    Module state is shared by every app in a process, which is one app in
    production and dozens in a test run -- there the limiter would carry counts
    from one test into the next and eventually refuse a login nobody made.
    """
    state = request.app.state
    limiter = getattr(state, "login_limiter", None)
    if limiter is None:
        limiter = state.login_limiter = WindowLimiter(
            limit=LOGIN_LIMIT, seconds=LOGIN_WINDOW,
        )
    limiter.check(caller(request))


class TelegramAuthRequest(BaseModel):
    init_data: str


def _tenant_slug(request: Request) -> str:
    settings = request.app.state.settings
    bindings = getattr(request.app.state, "tenant_hosts", {})
    if not bindings and settings.environment == "development":
        return settings.default_tenant_slug
    host = request.headers.get("host", "").split(":", 1)[0].lower()
    try:
        return bindings[host]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown tenant host") from exc


def _public_auth(result, available_units: int) -> dict[str, object]:
    return {
        "user_id": result.user_id,
        "tenant_id": result.tenant_id,
        "telegram_user_id": result.telegram_user_id,
        "display_name": result.display_name,
        "acquisition_tenant_slug": result.acquisition_tenant_slug,
        "access_tenant_slug": result.access_tenant_slug,
        "available_units": available_units,
    }


def _set_session_cookie(response: JSONResponse, request: Request, token: str) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        # Keyed on "not local development", not on the label "production": the
        # pilot runs POKER8_ENV=test because that is the only environment the
        # CASH mock is allowed in, and it is served over HTTPS on a public
        # domain all the same. Tying the flag to the label meant the session
        # cookie of every real player travelled without it.
        secure=settings.environment != "development",
        samesite="lax",
        path="/",
    )


async def _finish_login(request: Request, result):
    ledger = request.app.state.ledger
    await ledger.ensure_user_wallet(result.user_id)
    await ledger.grant(result.user_id, WELCOME_UNITS, f"welcome:{result.user_id}")
    # Opening the app is the moment a refill is worth anything, and the lobby
    # reads its balance from this response rather than from /api/profile.
    available_units, _ = await refill_if_broke(
        request.app.state.session_factory, ledger, result.user_id,
    )
    response = JSONResponse(_public_auth(result, available_units))
    _set_session_cookie(response, request, result.token)
    return response


@router.post("/telegram")
async def telegram_login(payload: TelegramAuthRequest, request: Request):
    _throttle(request)
    try:
        result = await request.app.state.auth_service.authenticate(
            _tenant_slug(request), payload.init_data
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return await _finish_login(request, result)


@router.post("/guest")
async def guest_login(request: Request):
    _throttle(request)
    if not request.app.state.settings.open_access:
        raise HTTPException(status_code=404, detail="Guest access is disabled")
    try:
        result = await request.app.state.auth_service.authenticate_guest(_tenant_slug(request))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return await _finish_login(request, result)


@router.post("/dev/{telegram_user_id}")
async def dev_login(telegram_user_id: int, request: Request):
    settings = request.app.state.settings
    if settings.environment != "development":
        raise HTTPException(status_code=404, detail="Development login is disabled")
    try:
        display_name = settings.dev_profiles[telegram_user_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown development profile") from exc
    try:
        result = await request.app.state.auth_service.authenticate_dev(
            _tenant_slug(request), telegram_user_id, display_name
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return await _finish_login(request, result)


@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(request.app.state.settings.session_cookie_name)
    if token:
        await request.app.state.auth_service.revoke_session(token)
    response = JSONResponse({"ok": True})
    response.delete_cookie(request.app.state.settings.session_cookie_name, path="/")
    return response
