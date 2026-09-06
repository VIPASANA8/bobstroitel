"""Talking to the Bot API: what the bot needs to say, and where it listens."""
from __future__ import annotations

import hashlib
import hmac
import logging

import httpx


logger = logging.getLogger("poker8.telegram")

API = "https://api.telegram.org"


def webhook_secret(bot_token: str) -> str:
    """The secret Telegram echoes back on every delivery, derived from the token.

    Derived rather than configured: a separate setting would be one more thing
    to place on a deployment and one more thing to leave unset, and this can
    only be produced by somebody who already has the token.
    """
    return hmac.new(b"poker8-webhook", bot_token.encode(), hashlib.sha256).hexdigest()


async def send_message(bot_token: str, chat_id: int, text: str) -> None:
    """Best effort: a player who does not get the confirmation in the chat is
    still signed in, because the browser learns it from the server, not here."""
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            await client.post(
                f"{API}/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
    except httpx.HTTPError:
        logger.warning("poker8_telegram_send_failed", extra={"chat_id": chat_id})


async def ensure_webhook(bot_token: str, url: str) -> bool:
    """Point the bot at `url`, unless it already points there.

    Checked before it is set so a restart is not a write to Telegram, and so a
    webhook somebody else configured is visible in the logs rather than
    silently replaced.
    """
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            current = (await client.get(f"{API}/bot{bot_token}/getWebhookInfo")).json()
            existing = (current.get("result") or {}).get("url") or ""
            if existing == url:
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
                    # The login only ever reads /start; asking for the rest
                    # would be traffic nothing in here looks at.
                    "allowed_updates": ["message"],
                    "drop_pending_updates": True,
                },
            )
            return bool(response.json().get("ok"))
    except (httpx.HTTPError, ValueError):
        logger.warning("poker8_telegram_webhook_failed")
        return False
