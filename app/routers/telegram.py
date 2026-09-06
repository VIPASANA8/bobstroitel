from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select

from admin_bot.formatting import queue_messages
from cash.access import CashOperator
from cash.admin import OperatorAccessDenied
from cash.amounts import micros_to_usdt
from online.auth import AuthenticationError, login_code
from online.schema import cash_operators
from online.telegram import answer_callback, send_message, webhook_secret


router = APIRouter(prefix="/api/telegram", tags=["telegram"])

#: What the confirm button carries back. Short, because Telegram allows 64
#: bytes of callback data and the nonce takes most of them.
CONFIRM = "login:"

#: Telegram renders one message as one block, so the panel is built as lines.
NEWLINE = "\n"

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
    """Updates from the tenant's bot: opening a login, and confirming one.

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
        await _confirm(auth, token, tenant_slug, callback)
        return {"ok": True}

    message = update.get("message")
    if not isinstance(message, dict):
        return {"ok": True}
    chat_id = (message.get("chat") or {}).get("id")
    text = message.get("text")
    if not chat_id or not isinstance(text, str) or not text.startswith(("/start", "/admin")):
        return {"ok": True}

    if text.startswith("/admin"):
        await _admin(request, token, chat_id, sender=message.get("from") or {})
        return {"ok": True}

    nonce = text[len("/start"):].strip()
    if not nonce:
        await send_message(token, chat_id, WELCOME)
        return {"ok": True}

    # Nothing is bound yet. Pressing Start only says somebody opened the link,
    # and a link is a piece of text that can be forwarded to anybody -- so the
    # bot shows what it is being asked to confirm and waits to be told yes.
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


async def _is_open(auth, tenant_slug: str, nonce: str) -> bool:
    """A tenant this deployment does not actually run is not an error worth a
    retry, and not a login either -- Telegram would only redeliver it."""
    try:
        return await auth.pending_login_request(tenant_slug, nonce)
    except AuthenticationError:
        return False


async def _confirm(auth, token: str, tenant_slug: str, callback: dict) -> None:
    """The button was pressed: bind this person to the login they confirmed."""
    data = callback.get("data")
    callback_id = callback.get("id")
    if not isinstance(data, str) or not data.startswith(CONFIRM):
        return
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


def _line(label: str, micros: int) -> str:
    return f"{label}: <b>{micros_to_usdt(micros)}</b> USDT"


async def _admin(request: Request, token: str, chat_id: int, sender: dict) -> None:
    """The operator panel, for whoever the operator table says is one.

    Read-only on purpose. Approving a withdrawal or crediting a payment is
    already possible, through an API that takes an operator key and writes a
    reason into the audit log for every move; putting the same buttons behind a
    chat id would be the same money with less of a record behind it.
    """
    telegram_id = sender.get("id")
    async with request.app.state.session_factory() as session:
        row = (await session.execute(select(cash_operators).where(
            cash_operators.c.telegram_user_id == telegram_id,
            cash_operators.c.active.is_(True),
        ))).mappings().first()
    # No answer at all to anybody else: a "you may not" would tell a stranger
    # the command is there to be guessed at.
    if row is None:
        return
    operator = CashOperator(row["id"], row["telegram_user_id"], row["tenant_id"], row["role"])

    try:
        summary = await request.app.state.cash_admin.overview(operator)
        head = NEWLINE.join([
            "🛠 <b>Панель оператора</b>",
            f"Игроков: <b>{summary['players']}</b> · под холдом: <b>{summary['frozen']}</b>",
            _line("На балансах", summary["available_micros"]),
            _line("В игре", summary["escrow_micros"]),
            _line("Ждёт вывода", summary["withdrawal_micros"]),
            "",
            f"🎲 CUBE за сутки: <b>{summary['cube_rounds_day']}</b> раундов, "
            f"результат {micros_to_usdt(summary['cube_result_day_micros'])} USDT",
            _line("Касса кубика", summary["cube_house_micros"]),
        ])
    except OperatorAccessDenied:
        head = NEWLINE.join([
            "🛠 <b>Панель оператора</b>",
            "Сводка по деньгам — только для глобального админа.",
        ])
    await send_message(token, chat_id, head, parse_mode="HTML")

    queue = await request.app.state.cash_admin.queue(operator)
    messages = queue_messages(queue)
    if not messages:
        await send_message(token, chat_id, "Очередь пуста — разбирать нечего.")
        return
    await send_message(token, chat_id, f"В очереди: <b>{len(messages)}</b>", parse_mode="HTML")
    # A phone is not a console: the oldest few, and the rest through the
    # operator API, which is where acting on them lives anyway.
    for _kind, _target, _status, body in messages[:5]:
        await send_message(token, chat_id, body, parse_mode="HTML")
