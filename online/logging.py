from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


SENSITIVE_KEYS = {"telegram_user_id", "bot_token", "cookie", "hole_cards", "private_state_json", "deck_cards"}


def redact_event(payload: dict[str, Any]) -> dict[str, Any]:
    def clean(value):
        if isinstance(value, dict):
            return {key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    return clean(payload)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"event": record.getMessage(), "timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname}
        extra = getattr(record, "event_payload", None)
        if isinstance(extra, dict):
            payload.update(redact_event(extra))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def event_logger() -> logging.Logger:
    logger = logging.getLogger("poker8.online")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
