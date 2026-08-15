from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from online.auth import AuthenticationError


router = APIRouter(prefix="/api/auth", tags=["auth"])


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


def _public_auth(result) -> dict[str, object]:
    return {
        "user_id": result.user_id,
        "tenant_id": result.tenant_id,
        "telegram_user_id": result.telegram_user_id,
        "display_name": result.display_name,
        "acquisition_tenant_slug": result.acquisition_tenant_slug,
        "access_tenant_slug": result.access_tenant_slug,
    }


def _set_session_cookie(response: JSONResponse, request: Request, token: str) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


@router.post("/telegram")
async def telegram_login(payload: TelegramAuthRequest, request: Request):
    try:
        result = await request.app.state.auth_service.authenticate(
            _tenant_slug(request), payload.init_data
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    response = JSONResponse(_public_auth(result))
    _set_session_cookie(response, request, result.token)
    return response


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
    response = JSONResponse(_public_auth(result))
    _set_session_cookie(response, request, result.token)
    return response


@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(request.app.state.settings.session_cookie_name)
    if token:
        await request.app.state.auth_service.revoke_session(token)
    response = JSONResponse({"ok": True})
    response.delete_cookie(request.app.state.settings.session_cookie_name, path="/")
    return response
