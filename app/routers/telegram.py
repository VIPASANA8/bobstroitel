from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Request

from online.auth import AuthenticationError, login_code
from online.telegram import answer_callback, send_message, webhook_secret


router = APIRouter(prefix="/api/telegram", tags=["telegram"])

#: What the login's confirm button carries back. Short, because Telegram allows
#: 64 bytes of callback data and the nonce takes most of them. Everything that
#: does not start with this belongs to the operator panel.
CONFIRM = "login:"

WELCOME = (
    "Это бот стола. Здесь только вход на сайт — играть можно в браузере "
    "или в мини-приложении."
)
STALE = "Ссылка для входа устарела. Откройте сайт и нажмите «Войти» ещё раз."
SIGNED_IN = "Готово. Возвращайтесь на вкладку с игрой — вы уже вошли."


def _ask(host: str, code: str) -> str:
    return (
        f"Вход на {host}\n\n"
        f"Код на экране: {code}\n\n"
        "Нажмите «Подтвердить», только если этот код сейчас показан на вашей "
        "странице. Если вы не начинали вход — просто закройте этот чат."
    )


@router.post("/webhook/{tenant_slug}")
async def webhook(
    tenant_slug: str,
    request: Request,
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    """Updates from the tenant's bot: the login, and the operator panel.

    Two things guard this door: the secret in the path, which Telegram is the
    only party told, and the header it echoes back with every delivery. Both
    are derived from the bot token, so neither is a secret anybody has to
    remember to set, and neither can be produced without the token itself.

    It answers 200 to everything it understands and everything it does not:
    Telegram retries a failure, and there is nothing here worth retrying.
    """
    settings = request.app.state.settings
    tenant = settings.tenant_configs.get(tenant_slug) or {}
    token = tenant.get("token")
    if not token:
        raise HTTPException(status_code=404, detail="not found")
    if not secret or not hmac.compare_digest(secret, webhook_secret(token)):
        raise HTTPException(status_code=403, detail="forbidden")

    update = await request.json()
    if not isinstance(update, dict):
        return {"ok": True}
    auth = request.app.state.auth_service
    host = next(iter(tenant.get("hosts", [])), tenant.get("name") or "сайт")

    callback = update.get("callback_query")
    if isinstance(callback, dict):
        data = callback.get("data")
        chat_id = ((callback.get("message") or {}).get("chat") or {}).get("id")
        if isinstance(data, str) and data.startswith(CONFIRM):
            await _confirm(auth, token, tenant_slug, callback)
        elif chat_id:
            await _ops(request, token, chat_id, callback.get("from") or {},
                       data=data or "", callback_id=callback.get("id"))
        return {"ok": True}

    message = update.get("message")
    if not isinstance(message, dict):
        return {"ok": True}
    chat_id = (message.get("chat") or {}).get("id")
    text = message.get("text")
    if not chat_id or not isinstance(text, str):
        return {"ok": True}
    sender = message.get("from") or {}

    if text.startswith("/start"):
        # An operator is a player too, so the login keeps this command.
        nonce = text[len("/start"):].strip()
        if not nonce:
            await send_message(token, chat_id, WELCOME)
            return {"ok": True}
        # Nothing is bound yet. Pressing Start only says somebody opened the
        # link, and a link is a piece of text that can be forwarded to anybody
        # -- so the bot shows what it is being asked to confirm and waits.
        if not await _is_open(auth, tenant_slug, nonce):
            await send_message(token, chat_id, STALE)
            return {"ok": True}
        await send_message(
            token, chat_id, _ask(host, login_code(nonce)),
            reply_markup={"inline_keyboard": [[
                {"text": "Подтвердить вход", "callback_data": f"{CONFIRM}{nonce}"},
            ]]},
        )
        return {"ok": True}

    # Anything else is either an operator working, or nothing at all: the panel
    # answers its own people and stays silent for everybody else.
    await _ops(request, token, chat_id, sender, text=text)
    return {"ok": True}


async def _is_open(auth, tenant_slug: str, nonce: str) -> bool:
    """A tenant this deployment does not actually run is not an error worth a
    retry, and not a login either -- Telegram would only redeliver it."""
    try:
        return await auth.pending_login_request(tenant_slug, nonce)
    except AuthenticationError:
        return False


async def _confirm(auth, token: str, tenant_slug: str, callback: dict) -> None:
    """The login button was pressed: bind this person to what they confirmed."""
    data = callback.get("data") or ""
    callback_id = callback.get("id")
    sender = callback.get("from") or {}
    first_name = sender.get("first_name")
    display_name = (
        first_name.strip() if isinstance(first_name, str) and first_name.strip() else "Игрок"
    )
    try:
        opened = await auth.bind_login_request(
            tenant_slug, data[len(CONFIRM):], int(sender.get("id") or 0), display_name,
        )
    except AuthenticationError:
        opened = False
    if callback_id:
        await answer_callback(token, callback_id, SIGNED_IN if opened else STALE)
    chat_id = ((callback.get("message") or {}).get("chat") or {}).get("id")
    if chat_id:
        await send_message(token, chat_id, SIGNED_IN if opened else STALE)


async def _ops(request: Request, token: str, chat_id: int, sender: dict, *,
               text: str | None = None, data: str | None = None,
               callback_id: str | None = None) -> bool:
    """Hand one update to the operator panel. False means it was not theirs.

    Silence for everybody else, the existence of the commands included: a
    refusal would tell a stranger there is something here worth guessing at.
    """
    bot = getattr(request.app.state, "opsbot", None)
    if bot is None:
        return False
    operator = await bot.operator(sender.get("id"))
    if operator is None:
        return False
    if callback_id:
        await answer_callback(token, callback_id, "")
    replies = await (
        bot.callback(operator, data) if data is not None else bot.message(operator, text or "")
    )
    for body, keyboard in replies:
        await send_message(
            token, chat_id, body,
            reply_markup={"inline_keyboard": keyboard} if keyboard else None,
            parse_mode="HTML",
        )
    return bool(replies)
