from __future__ import annotations

import json
from dataclasses import dataclass, field
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
    coordinator_enabled: bool
    dev_profiles: dict[int, str]
    tenant_configs: dict[str, dict[str, object]] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, source: Mapping[str, str]) -> "Settings":
        environment = source.get("POKER8_ENV", "development").strip().lower()
        raw_coordinator = source.get(
            "POKER8_COORDINATOR_ENABLED",
            "1" if environment in {"production", "test"} else "0",
        ).strip().lower()
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

        default_slug = source.get("POKER8_DEFAULT_TENANT", "poker8").strip()
        raw_tenants = source.get("POKER8_TENANTS_JSON", "").strip()
        tenant_configs: dict[str, dict[str, object]] = {}
        if raw_tenants:
            for item in json.loads(raw_tenants):
                slug = str(item["slug"])
                token_env = str(item.get("token_env", ""))
                tenant_configs[slug] = {
                    "hosts": list(item.get("hosts", [])),
                    "name": str(item.get("name", slug)),
                    "support_url": item.get("support_url"),
                    "branding": dict(item.get("branding", {})),
                    "token": source.get(token_env, "") if token_env else "",
                }
        if not tenant_configs:
            tenant_configs[default_slug] = {
                "hosts": [], "name": "Poker8", "support_url": None, "branding": {}, "token": bot_token or "",
            }
        return cls(
            environment=environment,
            database_url=database_url,
            default_tenant_slug=default_slug,
            default_bot_token=bot_token,
            session_cookie_name="poker8_session",
            session_ttl_seconds=7 * 24 * 60 * 60,
            telegram_auth_max_age_seconds=15 * 60,
            coordinator_enabled=raw_coordinator in {"1", "true", "yes", "on"},
            dev_profiles=profiles,
            tenant_configs=tenant_configs,
        )
