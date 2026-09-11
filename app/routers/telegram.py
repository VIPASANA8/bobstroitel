from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Request

from cash.referrals import code_for, normalise as normalise_referral, start_payload
from online.auth import AuthenticationError, login_code
from online.telegram import answer_callback, edit_message, send_message, webhook_secret


router = APIRouter(prefix="/api/telegram", tags=["telegram"])

#: What the login's confirm button carries back. Short, because Telegram allows
#: 64 bytes of callback data and the nonce takes most of them. Everything that
#: does not start with this belongs to the operator panel.
CONFIRM = "login:"

WELCOME = (
    "<b>Привет! 👋</b>\n\n"
    "Играйте в <b>POKER</b>, бросайте кубик в <b>CUBE</b> и выводите средства "
    "в <b>рублях или USDT</b>.\n\n"
    "♠️ <b>POKER:</b> donbass.win\n\n"
    "🎲 <b>CUBE:</b> donbass.win/cube\n\n"
    "Или играйте прямо в Telegram — нажмите кнопку <b>«Играть»</b>.\n\n"
    "👥 <b>Приглашайте друзей и зарабатывайте от 5 до 15% с их игры!</b>"
)
#: Under the welcome, once the player has an account for the link to pay into.
REFERRAL_LINE = "\n\nВаша ссылка: {link}"
STALE = "Ссылка для входа устарела. Откройте сайт и нажмите «Войти» ещё раз."
INVITED = (
    "Вас пригласили в Poker8. Откройте приложение — приглашение закрепится "
    "за вашим аккаунтом при первом входе."
)
SIGNED_IN = "Готово. Возвращайтесь на вкладку с игрой — вы уже вошли."


def _ask(host: str, code: str) -> str:
    return (
        f"Вход на {host}\n\n"
        f"Код на экране: {code}\n\n"
        "Нажмите «Подтвердить», только если этот код сейчас показан на вашей "
        "странице. Если вы не начинали вход — просто закройте этот чат."
    )


@router.post("/admin/{tenant_slug}")
async def admin_webhook(
    tenant_slug: str,
    request: Request,
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    """Updates from the operator bot, which is a different bot on purpose.

    The players' bot carries the login and nothing else; commands they are not
    meant to find should not be sitting in it waiting to be guessed at. Same
    two guards -- a secret in the path and one in the header -- derived from
    this bot's own token.
    """
    settings = request.app.state.settings
    token = settings.admin_bot_token
    if not token or tenant_slug not in settings.tenant_configs:
        raise HTTPException(status_code=404, detail="not found")
    if not secret or not hmac.compare_digest(secret, webhook_secret(token)):
        raise HTTPException(status_code=403, detail="forbidden")

    update = await request.json()
    if not isinstance(update, dict):
        return {"ok": True}

    callback = update.get("callback_query")
    if isinstance(callback, dict):
        origin = callback.get("message") or {}
        chat_id = (origin.get("chat") or {}).get("id")
        if chat_id:
            await _ops(request, token, chat_id, callback.get("from") or {},
                       data=callback.get("data") or "", callback_id=callback.get("id"),
                       message_id=origin.get("message_id"))
        return {"ok": True}

    message = update.get("message")
    if not isinstance(message, dict):
        return {"ok": True}
    chat_id = (message.get("chat") or {}).get("id")
    text = message.get("text")
    if chat_id and isinstance(text, str):
        # /start here is the panel's own greeting, not a login: this bot has
        # no players to sign in.
        await _ops(request, token, chat_id, message.get("from") or {},
                   text="/admin" if text.strip() == "/start" else text)
    return {"ok": True}


@router.post("/webhook/{tenant_slug}")
async def webhook(
    tenant_slug: str,
    request: Request,
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    """Updates from the players' bot. The only one it acts on is the login.

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
            link = await _referral_link(request, tenant_slug, sender)
            await send_message(
                token, chat_id,
                WELCOME + (REFERRAL_LINE.format(link=link) if link else ""),
                parse_mode="HTML",
            )
            return {"ok": True}
        # A referral link and a login share this one payload slot, so they are
        # told apart by shape: a code is nine characters, a login nonce is
        # thirty-two. The bot cannot bind anything itself -- it has no account
        # to bind yet -- so it hands the invitation on to the Mini App, where
        # the first login carries it in `start_param`.
        code = normalise_referral(nonce)
        if code:
            username = getattr(request.app.state, "telegram_login_bots", {}).get(
                tenant_slug, {},
            ).get("username")
            await send_message(
                token, chat_id, INVITED,
                reply_markup={"inline_keyboard": [[{
                    "text": "Открыть Poker8",
                    "url": f"https://t.me/{username}?startapp={start_payload(code)}",
                }]]} if username else None,
            )
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

    return {"ok": True}


async def _referral_link(request: Request, tenant_slug: str, sender: dict) -> str | None:
    """This person's own invitation. A /start is the first the site hears of
    most people, so the account the code belongs to is opened right here."""
    username = getattr(request.app.state, "telegram_login_bots", {}).get(
        tenant_slug, {},
    ).get("username")
    if not username or not sender.get("id"):
        return None
    try:
        user_id = await request.app.state.auth_service.register(
            tenant_slug, int(sender["id"]), _display_name(sender),
        )
    except AuthenticationError:
        return None
    async with request.app.state.session_factory() as session:
        async with session.begin():
            code = await code_for(session, user_id)
    return f"https://t.me/{username}?startapp={start_payload(code)}"


def _display_name(sender: dict) -> str:
    first_name = sender.get("first_name")
    return first_name.strip() if isinstance(first_name, str) and first_name.strip() else "Игрок"


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
    try:
        opened = await auth.bind_login_request(
            tenant_slug, data[len(CONFIRM):], int(sender.get("id") or 0), _display_name(sender),
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
               callback_id: str | None = None, message_id: int | None = None) -> bool:
    """Hand one update to the operator panel. False means it was not theirs.

    Silence for everybody else, the existence of the panel included: a refusal
    would tell a stranger there is something here worth guessing at.
    """
    bot = getattr(request.app.state, "opsbot", None)
    if bot is None:
        return False
    operator = await bot.operator(sender.get("id"))
    if operator is None:
        return False
    if callback_id:
        # Clears the spinner on the button straight away; the screen it leads
        # to can take as long as its query does.
        await answer_callback(token, callback_id, "")
    replies = await (
        bot.callback(operator, data) if data is not None else bot.message(operator, text or "")
    )
    for how, body, keyboard in replies:
        markup = {"inline_keyboard": keyboard} if keyboard else None
        # "edit" is the panel redrawing itself. Without a message to redraw --
        # a typed answer, say -- it becomes a new one.
        if how == "edit" and message_id:
            await edit_message(token, chat_id, message_id, body, markup, "HTML")
        else:
            await send_message(token, chat_id, body, markup, "HTML")
    return bool(replies)
