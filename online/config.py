from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    default_tenant_slug: str
    default_bot_token: str | None
    session_cookie_name: str
    session_ttl_seconds: int
    telegram_auth_max_age_seconds: int
    dev_profiles: dict[int, str]

    @classmethod
    def from_mapping(cls, source: Mapping[str, str]) -> "Settings":
        environment = source.get("POKER8_ENV", "development").strip().lower()
        database_url = source.get("POKER8_DATABASE_URL", "").strip()
        bot_token = source.get("POKER8_DEFAULT_BOT_TOKEN", "").strip() or None
        if environment == "production" and not database_url:
            raise ValueError("POKER8_DATABASE_URL is required in production")
        if environment == "production" and not bot_token:
            raise ValueError("POKER8_DEFAULT_BOT_TOKEN is required in production")
        if not database_url:
            database_url = "sqlite+aiosqlite:///./data/poker8_online_dev.sqlite3"

        profiles: dict[int, str] = {}
        for item in filter(None, source.get("POKER8_DEV_PROFILES", "101:Dev Player").split(",")):
            raw_id, name = item.split(":", 1)
            profiles[int(raw_id.strip())] = name.strip()

        return cls(
            environment=environment,
            database_url=database_url,
            default_tenant_slug=source.get("POKER8_DEFAULT_TENANT", "poker8").strip(),
            default_bot_token=bot_token,
            session_cookie_name="poker8_session",
            session_ttl_seconds=7 * 24 * 60 * 60,
            telegram_auth_max_age_seconds=15 * 60,
            dev_profiles=profiles,
        )
