from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Mapping

# Pure decimal parsing, no database and no cycle: the money amounts in this
# file are the same amounts the cash package validates.
from cash.amounts import usdt_to_micros


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
    open_access: bool
    self_top_up_enabled: bool
    seat_idle_bots: bool
    cash_mode: str
    cash_fiat_fee_bps: int
    cash_trc20_api_url: str
    cash_trc20_address: str
    cash_trc20_contract: str
    cash_trc20_api_key: str
    cash_orders_per_hour: int
    cash_daily_deposit_micros: int
    cash_withdrawal_fee_micros: int
    cash_allowlist: tuple[int, ...]
    cash_admin_api_key: str
    cash_admin_operators: tuple[dict[str, object], ...]
    cash_fiat_api_url: str
    cash_fiat_token: str
    cash_payout_provider: str
    legacy_play_rooms_enabled: bool
    dev_profiles: dict[int, str]
    tenant_configs: dict[str, dict[str, object]] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, source: Mapping[str, str]) -> "Settings":
        environment = source.get("POKER8_ENV", "development").strip().lower()
        raw_coordinator = source.get(
            "POKER8_COORDINATOR_ENABLED",
            "1" if environment in {"production", "test"} else "0",
        ).strip().lower()
        raw_open_access = source.get("POKER8_OPEN_ACCESS", "0").strip().lower()
        # Off outside development. The endpoint hands the caller whatever they
        # ask for, up to 100M units, with a request id they choose themselves --
        # so any guest, and a guest session is free, could repeat it forever. On
        # a deployment anyone can reach that makes every stack meaningless, and
        # it is the exact door a real top-up has to come through instead.
        raw_self_top_up = source.get(
            "POKER8_SELF_TOP_UP",
            "1" if environment == "development" else "0",
        ).strip().lower()
        # TEMPORARY -- restore before the MVP release. Off on the server while
        # live testing needs the seats predictable: bots stop taking free ones,
        # but whoever is already seated stays and keeps playing, and a bot that
        # should leave still leaves. Defaults on, so tests and local runs are
        # unchanged; turning it back on is deleting one line from
        # compose.server.yaml.
        raw_seat_idle_bots = source.get("POKER8_SEAT_IDLE_BOTS", "1").strip().lower()
        # Three modes, each tied to the environment that may run it. `mock` moves
        # pretend money and therefore may not run where real players are; nothing
        # in `production` is allowed to be a stand-in. Splitting them this way is
        # what frees the pilot from POKER8_ENV=test: real CASH runs under a real
        # production environment instead of borrowing the test one.
        cash_mode = source.get("POKER8_CASH_MODE", "off").strip().lower()
        if cash_mode not in {"off", "mock", "production"}:
            raise ValueError("POKER8_CASH_MODE must be off, mock, or production")
        if cash_mode == "mock" and environment not in {"development", "test"}:
            raise ValueError("POKER8_CASH_MODE=mock is only allowed in development/test")
        if cash_mode == "production" and environment != "production":
            raise ValueError("POKER8_CASH_MODE=production requires POKER8_ENV=production")
        try:
            cash_fiat_fee_bps = int(source.get("POKER8_CASH_FIAT_FEE_BPS", "100").strip() or 0)
        except ValueError as exc:
            raise ValueError("POKER8_CASH_FIAT_FEE_BPS must be basis points") from exc
        if not 0 <= cash_fiat_fee_bps <= 1_000:
            raise ValueError("POKER8_CASH_FIAT_FEE_BPS must be between 0 and 1000 basis points")
        # Antifraud knobs. Zero means off, which is what the pilot asked for on
        # the daily amount; the request rate stays on because no honest cashier
        # opens six RUB orders in an hour.
        try:
            cash_orders_per_hour = int(source.get("POKER8_CASH_ORDERS_PER_HOUR", "6").strip() or 0)
            cash_daily_deposit_usdt = int(source.get("POKER8_CASH_DAILY_DEPOSIT_USDT", "0").strip() or 0)
        except ValueError as exc:
            raise ValueError("POKER8_CASH_ORDERS_PER_HOUR and POKER8_CASH_DAILY_DEPOSIT_USDT must be integers") from exc
        if cash_orders_per_hour < 0 or cash_daily_deposit_usdt < 0:
            raise ValueError("cash antifraud limits cannot be negative")
        # What a TRC20 payout costs us, charged to whoever asks for one. Left at
        # zero the house pays the network for every withdrawal, including the
        # one-cent ones, which is why this has to be measured and set before a
        # real payout executor is ever switched on.
        try:
            cash_withdrawal_fee_micros = usdt_to_micros(
                source.get("POKER8_CASH_WITHDRAWAL_FEE_USDT", "0").strip() or "0"
            )
        except ValueError as exc:
            raise ValueError("POKER8_CASH_WITHDRAWAL_FEE_USDT must be a USDT amount") from exc
        if cash_withdrawal_fee_micros >= 100_000_000:
            raise ValueError("POKER8_CASH_WITHDRAWAL_FEE_USDT must be under 100 USDT")
        # The deposit watcher is read-only: an endpoint, an address it reads and
        # the one token contract that counts. No key of any kind signs anything.
        trc20_api_url = source.get("POKER8_CASH_TRC20_API_URL", "").strip()
        trc20_address = source.get("POKER8_CASH_TRC20_ADDRESS", "").strip()
        trc20_contract = source.get("POKER8_CASH_TRC20_CONTRACT", "").strip()
        trc20_api_key = source.get("POKER8_CASH_TRC20_API_KEY", "").strip()
        if trc20_api_url or trc20_address or trc20_contract:
            if not (trc20_api_url and trc20_address and trc20_contract):
                raise ValueError(
                    "POKER8_CASH_TRC20_API_URL, _ADDRESS and _CONTRACT are set together"
                )
            if not trc20_api_url.startswith("https://"):
                raise ValueError("POKER8_CASH_TRC20_API_URL must be HTTPS")
            if any(not re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", value)
                   for value in (trc20_address, trc20_contract)):
                raise ValueError("POKER8_CASH_TRC20_ADDRESS and _CONTRACT must be TRON addresses")
        raw_cash_allowlist = source.get("POKER8_CASH_ALLOWLIST", "").strip()
        try:
            cash_allowlist = tuple(int(value.strip()) for value in raw_cash_allowlist.split(",") if value.strip())
        except ValueError as exc:
            raise ValueError("POKER8_CASH_ALLOWLIST must contain positive Telegram IDs") from exc
        if any(value <= 0 for value in cash_allowlist) or len(set(cash_allowlist)) != len(cash_allowlist):
            raise ValueError("POKER8_CASH_ALLOWLIST must contain unique positive Telegram IDs")
        raw_legacy_rooms = source.get("POKER8_LEGACY_PLAY_ROOMS", "0").strip().lower()
        # The live CASE8 endpoint. The pinned partner source ships
        # PARTNER_TLS_VERIFY=false against a self-signed certificate on a bare
        # IP; Case8PartnerClient does not carry that over, so an HTTPS hostname
        # with a trusted certificate is the only thing that will connect.
        cash_fiat_api_url = source.get("POKER8_CASH_FIAT_API_URL", "").strip()
        cash_fiat_token = source.get("POKER8_CASH_FIAT_TOKEN", "").strip()
        # Who signs and holds the keys for an outgoing payout. Never this
        # application: it may only queue a payout and read back its status.
        cash_payout_provider = source.get("POKER8_CASH_PAYOUT_PROVIDER", "").strip()
        if cash_mode == "production":
            missing = [
                name for name, value in (
                    ("POKER8_CASH_FIAT_API_URL", cash_fiat_api_url),
                    ("POKER8_CASH_FIAT_TOKEN", cash_fiat_token),
                    ("POKER8_CASH_TRC20_API_URL", trc20_api_url),
                    ("POKER8_CASH_TRC20_ADDRESS", trc20_address),
                    ("POKER8_CASH_TRC20_CONTRACT", trc20_contract),
                    ("POKER8_CASH_PAYOUT_PROVIDER", cash_payout_provider),
                ) if not value
            ]
            if missing:
                raise ValueError(
                    "POKER8_CASH_MODE=production requires " + ", ".join(missing)
                )
            if not cash_fiat_api_url.startswith("https://"):
                raise ValueError("POKER8_CASH_FIAT_API_URL must be HTTPS")

        cash_admin_api_key = source.get("POKER8_CASH_ADMIN_API_KEY", "").strip()
        raw_cash_operators = source.get("POKER8_CASH_ADMIN_OPERATORS_JSON", "[]").strip()
        try:
            parsed_cash_operators = json.loads(raw_cash_operators)
        except (TypeError, ValueError) as exc:
            raise ValueError("POKER8_CASH_ADMIN_OPERATORS_JSON must be a JSON array") from exc
        if not isinstance(parsed_cash_operators, list):
            raise ValueError("POKER8_CASH_ADMIN_OPERATORS_JSON must be a JSON array")
        cash_admin_operators = tuple(parsed_cash_operators)
        if not all(isinstance(item, dict) for item in cash_admin_operators):
            raise ValueError("POKER8_CASH_ADMIN_OPERATORS_JSON must be a JSON array of objects")
        if cash_admin_operators and not cash_admin_api_key:
            raise ValueError("POKER8_CASH_ADMIN_API_KEY is required when cash operators are configured")
        if cash_admin_api_key and len(cash_admin_api_key) < 16:
            raise ValueError("POKER8_CASH_ADMIN_API_KEY must contain at least 16 characters")
        for item in cash_admin_operators:
            try:
                telegram_id = int(item["telegram_user_id"])
                role = str(item["role"]).lower()
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("cash operator requires telegram_user_id and role") from exc
            if telegram_id <= 0 or role not in {"reviewer", "operator", "admin"}:
                raise ValueError("cash operator has an invalid Telegram ID or role")
            if role != "admin" and not str(item.get("tenant_slug") or "").strip():
                raise ValueError("non-admin cash operator requires tenant_slug")
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
            # Same reasoning as the session cookie: anything that is not local
            # development is somebody's real deployment. A guest has no identity
            # to hold responsible for anything, so the door only opens locally.
            open_access=environment == "development" and raw_open_access in {"1", "true", "yes", "on"},
            self_top_up_enabled=raw_self_top_up in {"1", "true", "yes", "on"},
            seat_idle_bots=raw_seat_idle_bots in {"1", "true", "yes", "on"},
            cash_mode=cash_mode,
            cash_fiat_fee_bps=cash_fiat_fee_bps,
            cash_trc20_api_url=trc20_api_url,
            cash_trc20_address=trc20_address,
            cash_trc20_contract=trc20_contract,
            cash_trc20_api_key=trc20_api_key,
            cash_orders_per_hour=cash_orders_per_hour,
            cash_daily_deposit_micros=cash_daily_deposit_usdt * 1_000_000,
            cash_withdrawal_fee_micros=cash_withdrawal_fee_micros,
            cash_allowlist=cash_allowlist,
            cash_admin_api_key=cash_admin_api_key,
            cash_admin_operators=cash_admin_operators,
            cash_fiat_api_url=cash_fiat_api_url,
            cash_fiat_token=cash_fiat_token,
            cash_payout_provider=cash_payout_provider,
            legacy_play_rooms_enabled=(
                environment in {"development", "test"}
                and raw_legacy_rooms in {"1", "true", "yes", "on"}
            ),
            dev_profiles=profiles,
            tenant_configs=tenant_configs,
        )
