from dataclasses import dataclass
import os
from urllib.parse import urlparse


@dataclass(frozen=True)
class BotConfig:
    telegram_token: str
    api_base_url: str
    api_key: str

    @classmethod
    def from_env(cls):
        token = os.environ.get("POKER8_CASH_ADMIN_BOT_TOKEN", "").strip()
        url = os.environ.get("POKER8_CASH_ADMIN_API_URL", "").strip().rstrip("/")
        key = os.environ.get("POKER8_CASH_ADMIN_API_KEY", "").strip()
        if not token or not url or not key:
            raise ValueError("admin bot token, API URL and API key are required")
        parsed = urlparse(url)
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("admin API must use HTTPS outside localhost")
        return cls(token, url, key)
