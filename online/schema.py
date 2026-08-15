from __future__ import annotations

from sqlalchemy import (
    BIGINT,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    text,
)


metadata = MetaData()
timestamp = DateTime(timezone=True)
created_at = dict(nullable=False, server_default=text("CURRENT_TIMESTAMP"))

tenants = Table(
    "tenants", metadata,
    Column("id", String(64), primary_key=True),
    Column("slug", String(100), nullable=False, unique=True),
    Column("name", String(200), nullable=False),
    Column("status", String(32), nullable=False, server_default=text("'active'")),
    Column("created_at", timestamp, **created_at),
)

tenant_bots = Table(
    "tenant_bots", metadata,
    Column("id", String(64), primary_key=True),
    Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
    Column("telegram_bot_id", BIGINT, nullable=False),
    Column("secret_ref", String(200), nullable=False),
    Column("enabled", Boolean, nullable=False, server_default=text("1")),
    Column("created_at", timestamp, **created_at),
)

users = Table(
    "users", metadata,
    Column("id", String(64), primary_key=True),
    Column("telegram_user_id", BIGINT, nullable=False, unique=True),
    Column("display_name", String(200), nullable=False),
    Column("acquisition_tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
    Column("wins", Integer, nullable=False, server_default=text("0")),
    Column("hands_played", Integer, nullable=False, server_default=text("0")),
    Column("created_at", timestamp, **created_at),
    Column("updated_at", timestamp, **created_at),
)

user_tenant_visits = Table(
    "user_tenant_visits", metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
    Column("first_seen_at", timestamp, **created_at),
    Column("last_seen_at", timestamp, **created_at),
    UniqueConstraint("user_id", "tenant_id"),
)

auth_sessions = Table(
    "auth_sessions", metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("expires_at", timestamp, nullable=False),
    Column("revoked_at", timestamp),
    Column("created_at", timestamp, **created_at),
)

system_players = Table(
    "system_players", metadata,
    Column("id", String(64), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("difficulty", String(32), nullable=False),
    Column("wins", Integer, nullable=False, server_default=text("0")),
    Column("hands_played", Integer, nullable=False, server_default=text("0")),
    Column("active", Boolean, nullable=False, server_default=text("1")),
    Column("created_at", timestamp, **created_at),
    CheckConstraint("difficulty IN ('easy', 'normal', 'hard', 'maximum')"),
)

play_accounts = Table(
    "play_accounts", metadata,
    Column("id", String(64), primary_key=True),
    Column("owner_kind", String(32), nullable=False),
    Column("owner_id", String(64), nullable=False),
    Column("account_kind", String(32), nullable=False),
    Column("balance_units", BIGINT, nullable=False, server_default=text("0")),
    Column("created_at", timestamp, **created_at),
    UniqueConstraint("owner_kind", "owner_id", "account_kind"),
    CheckConstraint("owner_kind IN ('user', 'system', 'table')"),
    CheckConstraint("account_kind IN ('wallet', 'escrow', 'faucet')"),
    CheckConstraint("account_kind = 'faucet' OR balance_units >= 0"),
)

play_transactions = Table(
    "play_transactions", metadata,
    Column("id", String(64), primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("idempotency_key", String(200), nullable=False, unique=True),
    Column("reference_type", String(64), nullable=False),
    Column("reference_id", String(64), nullable=False),
    Column("status", String(32), nullable=False, server_default=text("'pending'")),
    Column("created_at", timestamp, **created_at),
    Column("posted_at", timestamp),
    CheckConstraint("kind IN ('faucet_grant', 'buy_in', 'add_on', 'settlement', 'return')"),
    CheckConstraint("status IN ('pending', 'posted')"),
)

play_entries = Table(
    "play_entries", metadata,
    Column("id", String(64), primary_key=True),
    Column("transaction_id", String(64), ForeignKey("play_transactions.id"), nullable=False),
    Column("account_id", String(64), ForeignKey("play_accounts.id"), nullable=False),
    Column("amount_units", BIGINT, nullable=False),
    Column("created_at", timestamp, **created_at),
    CheckConstraint("amount_units <> 0"),
)

poker_tables = Table(
    "poker_tables", metadata,
    Column("id", String(64), primary_key=True),
    Column("tenant_id", String(64), ForeignKey("tenants.id")),
    Column("scope", String(32), nullable=False),
    Column("name", String(200), nullable=False),
    Column("small_blind_units", BIGINT, nullable=False),
    Column("big_blind_units", BIGINT, nullable=False),
    Column("min_buy_in_bb", Integer, nullable=False),
    Column("max_buy_in_bb", Integer, nullable=False),
    Column("max_seats", Integer, nullable=False, server_default=text("6")),
    Column("status", String(32), nullable=False, server_default=text("'open'")),
    Column("button_seat", Integer),
    Column("created_at", timestamp, **created_at),
    Column("updated_at", timestamp, **created_at),
    CheckConstraint("scope IN ('network', 'tenant')"),
    CheckConstraint("max_seats = 6"),
)

table_seats = Table(
    "table_seats", metadata,
    Column("id", String(64), primary_key=True),
    Column("table_id", String(64), ForeignKey("poker_tables.id"), nullable=False),
    Column("seat_no", Integer, nullable=False),
    Column("occupant_kind", String(32), nullable=False),
    Column("user_id", String(64), ForeignKey("users.id")),
    Column("system_player_id", String(64), ForeignKey("system_players.id")),
    Column("escrow_account_id", String(64), ForeignKey("play_accounts.id")),
    Column("stack_units", BIGINT, nullable=False, server_default=text("0")),
    Column("state", String(32), nullable=False, server_default=text("'empty'")),
    Column("disconnected_at", timestamp),
    Column("hold_until", timestamp),
    Column("updated_at", timestamp, **created_at),
    UniqueConstraint("table_id", "seat_no"),
    CheckConstraint("seat_no >= 0 AND seat_no <= 5"),
    CheckConstraint("occupant_kind IN ('empty', 'user', 'system')"),
    CheckConstraint("state IN ('empty', 'seated', 'held', 'leaving')"),
    CheckConstraint("stack_units >= 0"),
)

seat_queue = Table(
    "seat_queue", metadata,
    Column("id", String(64), primary_key=True),
    Column("table_id", String(64), ForeignKey("poker_tables.id"), nullable=False),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("requested_buy_in_units", BIGINT, nullable=False),
    Column("state", String(32), nullable=False, server_default=text("'waiting'")),
    Column("position_seq", BIGINT, nullable=False),
    Column("created_at", timestamp, **created_at),
    Column("expires_at", timestamp),
    UniqueConstraint("table_id", "user_id"),
    CheckConstraint("state IN ('waiting', 'cancelled', 'seated', 'expired')"),
)

_active_seat_states = table_seats.c.state.in_(("seated", "held", "leaving"))
Index(
    "uq_active_table_seat_user", table_seats.c.user_id, unique=True,
    postgresql_where=table_seats.c.user_id.is_not(None) & _active_seat_states,
    sqlite_where=table_seats.c.user_id.is_not(None) & _active_seat_states,
)
Index(
    "uq_active_table_seat_system_player", table_seats.c.system_player_id, unique=True,
    postgresql_where=table_seats.c.system_player_id.is_not(None) & _active_seat_states,
    sqlite_where=table_seats.c.system_player_id.is_not(None) & _active_seat_states,
)
