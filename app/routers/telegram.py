from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Request

from online.telegram import send_message, webhook_secret


router = APIRouter(prefix="/api/telegram", tags=["telegram"])

WELCOME = (
    "Это бот стола. Здесь только вход на сайт — играть можно в браузере "
    "или в мини-приложении."
)
SIGNED_IN = "Готово. Возвращайтесь на вкладку с игрой — вы уже вошли."
STALE = "Ссылка для входа устарела. Откройте сайт и нажмите «Войти» ещё раз."


@router.post("/webhook/{tenant_slug}")
async def webhook(
    tenant_slug: str,
    request: Request,
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    """Updates from the tenant's bot. The only one that matters is `/start`.

    Two things guard this door: the secret in the path, which Telegram is the
    only party told, and the header it echoes back with every delivery. Both
    are derived from the bot token, so neither is a secret anybody has to
    remember to set, and neither can be produced without the token itself.

    It answers 200 to everything it understands and everything it does not:
    Telegram retries a failure, and there is nothing here worth retrying.
    """
    settings = request.app.state.settings
    token = (settings.tenant_configs.get(tenant_slug) or {}).get("token")
    if not token:
        raise HTTPException(status_code=404, detail="not found")
    if not secret or not hmac.compare_digest(secret, webhook_secret(token)):
        raise HTTPException(status_code=403, detail="forbidden")

    update = await request.json()
    message = update.get("message") if isinstance(update, dict) else None
    if not isinstance(message, dict):
        return {"ok": True}
    chat_id = (message.get("chat") or {}).get("id")
    sender = message.get("from") or {}
    text = message.get("text")
    if not chat_id or not isinstance(text, str) or not text.startswith("/start"):
        return {"ok": True}

    nonce = text[len("/start"):].strip()
    if not nonce:
        await send_message(token, chat_id, WELCOME)
        return {"ok": True}

    first_name = sender.get("first_name")
    display_name = first_name.strip() if isinstance(first_name, str) and first_name.strip() else "Игрок"
    opened = await request.app.state.auth_service.bind_login_request(
        nonce, int(sender.get("id") or 0), display_name,
    )
    await send_message(token, chat_id, SIGNED_IN if opened else STALE)
    return {"ok": True}
