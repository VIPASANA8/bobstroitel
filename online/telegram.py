"""Talking to the Bot API: what the bot needs to say, and where it listens."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

import httpx


logger = logging.getLogger("poker8.telegram")

API = "https://api.telegram.org"
#: /start opens a login and the button under it confirms one. Asking for more
#: would be traffic nothing in here looks at.
ALLOWED_UPDATES = ["message", "callback_query"]


def webhook_secret(bot_token: str) -> str:
    """The secret Telegram echoes back on every delivery, derived from the token.

    Derived rather than configured: a separate setting would be one more thing
    to place on a deployment and one more thing to leave unset, and this can
    only be produced by somebody who already has the token.
    """
    return hmac.new(b"poker8-webhook", bot_token.encode(), hashlib.sha256).hexdigest()


async def send_message(
    bot_token: str, chat_id: int, text: str,
    reply_markup: dict | None = None, parse_mode: str | None = None,
) -> int | None:
    """Best effort: a player who does not get the confirmation in the chat is
    still signed in, because the browser learns it from the server, not here.
    Returns the message id, for a card whose buttons will be redrawn later."""
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    sent = await _call(bot_token, "sendMessage", payload)
    return sent.get("message_id") if sent else None


async def send_photo(
    bot_token: str, chat_id: int, photo: bytes | str, caption: str,
    reply_markup: dict | None = None, parse_mode: str | None = None,
    filename: str = "image.jpg",
) -> tuple[int, str] | None:
    """A picture with the card as its caption. `photo` is raw bytes the first
    time and the file_id Telegram gave back for every copy after that -- which
    is the second thing returned, beside the message id."""
    payload = {"chat_id": str(chat_id), "caption": caption}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    if isinstance(photo, str):
        sent = await _call(bot_token, "sendPhoto", {**payload, "photo": photo})
    else:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                sent = _result(await client.post(
                    f"{API}/bot{bot_token}/sendPhoto", data=payload,
                    files={"photo": (filename, photo)},
                ))
        except (httpx.HTTPError, ValueError):
            logger.warning("poker8_telegram_send_failed", extra={"chat_id": chat_id})
            sent = None
    if not sent:
        return None
    sizes = sent.get("photo") or [{}]
    return sent["message_id"], str(sizes[-1].get("file_id") or "")


async def edit_reply_markup(
    bot_token: str, chat_id: int, message_id: int, reply_markup: dict | None,
) -> None:
    """Swap the buttons under a message that was already sent."""
    await _call(bot_token, "editMessageReplyMarkup", {
        "chat_id": chat_id, "message_id": message_id,
        "reply_markup": reply_markup or {"inline_keyboard": []},
    })


async def download_file(bot_token: str, file_id: str) -> bytes | None:
    """The bytes behind a file_id. A file_id is the receiving bot's own: to
    send a player's photo on through another bot it has to come down first."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            info = _result(await client.post(f"{API}/bot{bot_token}/getFile", json={"file_id": file_id}))
            path = (info or {}).get("file_path")
            if not path:
                return None
            response = await client.get(f"{API}/file/bot{bot_token}/{path}")
            return response.content if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        logger.warning("poker8_telegram_download_failed")
        return None


def _result(response) -> dict | None:
    """The message Telegram sent, or None when it said no."""
    body = response.json()
    result = body.get("result") if body.get("ok") else None
    return result if isinstance(result, dict) else None


async def _call(bot_token: str, method: str, payload: dict) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            return _result(await client.post(f"{API}/bot{bot_token}/{method}", json=payload))
    except (httpx.HTTPError, ValueError):
        logger.warning("poker8_telegram_send_failed", extra={"chat_id": payload.get("chat_id")})
        return None


async def edit_message(
    bot_token: str, chat_id: int, message_id: int, text: str,
    reply_markup: dict | None = None, parse_mode: str | None = None,
) -> None:
    """Redraw the screen in place. A panel that answers by appending is a chat
    log; one that replaces itself is a panel."""
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            await client.post(f"{API}/bot{bot_token}/editMessageText", json=payload)
    except httpx.HTTPError:
        logger.warning("poker8_telegram_edit_failed", extra={"chat_id": chat_id})


async def answer_callback(bot_token: str, callback_id: str, text: str) -> None:
    """Clear the spinner on the button that was just pressed."""
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            await client.post(
                f"{API}/bot{bot_token}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text},
            )
    except httpx.HTTPError:
        logger.warning("poker8_telegram_answer_failed")


async def ensure_webhook(bot_token: str, url: str) -> bool:
    """Point the bot at `url`, unless it already points there.

    Checked before it is set so a restart is not a write to Telegram, and so a
    webhook somebody else configured is visible in the logs rather than
    silently replaced.
    """
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            current = ((await client.get(f"{API}/bot{bot_token}/getWebhookInfo")).json()
                       .get("result") or {})
            existing = current.get("url") or ""
            # The kinds matter as much as the address: a webhook left over from
            # a version that only wanted messages would never deliver the
            # confirm button, and the login would wait forever.
            if existing == url and sorted(current.get("allowed_updates") or []) == sorted(ALLOWED_UPDATES):
                return True
            if existing:
                logger.warning(
                    "poker8_telegram_webhook_replaced", extra={"previous": existing},
                )
            response = await client.post(
                f"{API}/bot{bot_token}/setWebhook",
                json={
                    "url": url,
                    "secret_token": webhook_secret(bot_token),
                    "allowed_updates": ALLOWED_UPDATES,
                    "drop_pending_updates": True,
                },
            )
            return bool(response.json().get("ok"))
    except (httpx.HTTPError, ValueError):
        logger.warning("poker8_telegram_webhook_failed")
        return False
