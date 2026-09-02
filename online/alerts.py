from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request


logger = logging.getLogger(__name__)


class AlertNotifier:
    """Webhook and Telegram delivery shared by the watchdogs that wake a human."""

    def __init__(
        self, *,
        webhook_url: str | None = None,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
    ) -> None:
        self.webhook_url = (
            webhook_url if webhook_url is not None
            else os.getenv("POKER8_ESCROW_ALERT_WEBHOOK_URL", "")
        )
        self.telegram_bot_token = (
            telegram_bot_token if telegram_bot_token is not None
            else os.getenv("POKER8_ALERT_TELEGRAM_BOT_TOKEN", "")
        )
        self.telegram_chat_id = (
            telegram_chat_id if telegram_chat_id is not None
            else os.getenv("POKER8_ALERT_TELEGRAM_CHAT_ID", "")
        )

    @property
    def configured(self) -> bool:
        return bool(self.webhook_url or (self.telegram_bot_token and self.telegram_chat_id))

    async def send(self, event: str, text: str, payload: dict[str, object]) -> None:
        body = json.dumps({"event": event, **payload}).encode("utf-8")

        def post_webhook() -> None:
            request = urllib.request.Request(
                self.webhook_url, data=body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(request, timeout=4) as response:
                response.read(1)

        def post_telegram() -> None:
            telegram_body = json.dumps({"chat_id": self.telegram_chat_id, "text": text}).encode("utf-8")
            request = urllib.request.Request(
                f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
                data=telegram_body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(request, timeout=4) as response:
                response.read(1)

        deliveries = []
        if self.webhook_url:
            deliveries.append(post_webhook)
        if self.telegram_bot_token and self.telegram_chat_id:
            deliveries.append(post_telegram)
        for delivery in deliveries:
            try:
                await asyncio.to_thread(delivery)
            except Exception:
                logger.exception("poker8_alert_delivery_failed", extra={"event": event})
