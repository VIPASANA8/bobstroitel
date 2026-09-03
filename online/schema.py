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
    JSON,
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
    Column("branding_json", JSON, nullable=False, server_default=text("'{}'")),
    Column("support_url", String(500)),
    Column("created_at", timestamp, **created_at),
)

tenant_bots = Table(
    "tenant_bots", metadata,
    Column("id", String(64), primary_key=True),
    Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
    Column("telegram_bot_id", BIGINT, nullable=False),
    Column("secret_ref", String(200), nullable=False),
    Column("enabled", Boolean, nullable=False, server_default=text("true")),
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
    Column("auth_method", String(16), nullable=False, server_default=text("'legacy'")),
    Column("expires_at", timestamp, nullable=False),
    Column("revoked_at", timestamp),
    Column("created_at", timestamp, **created_at),
    CheckConstraint("auth_method IN ('telegram', 'dev', 'guest', 'legacy')", name="ck_auth_sessions_method"),
)

system_players = Table(
    "system_players", metadata,
    Column("id", String(64), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("difficulty", String(32), nullable=False),
    Column("wins", Integer, nullable=False, server_default=text("0")),
    Column("hands_played", Integer, nullable=False, server_default=text("0")),
    # A bot carries a level for one reason: so its seat reads like a person's.
    # Nothing else of the progression stack applies to it -- see progression.py.
    Column("xp", Integer, nullable=False, server_default=text("0")),
    Column("active", Boolean, nullable=False, server_default=text("true")),
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
    Column("asset", String(16), nullable=False, server_default=text("'PLAY'")),
    Column("name", String(200), nullable=False),
    Column("small_blind_units", BIGINT, nullable=False),
    Column("big_blind_units", BIGINT, nullable=False),
    Column("small_blind_micros", BIGINT),
    Column("big_blind_micros", BIGINT),
    Column("chip_micros", BIGINT),
    Column("min_buy_in_bb", Integer, nullable=False),
    Column("max_buy_in_bb", Integer, nullable=False),
    # House rake in basis points of what a winner takes off the other players.
    # Zero everywhere except a CASH table: PLAY chips are not money.
    Column("rake_bps", Integer, nullable=False, server_default=text("0")),
    Column("max_seats", Integer, nullable=False, server_default=text("6")),
    Column("status", String(32), nullable=False, server_default=text("'open'")),
    Column("button_seat", Integer),
    # Set only for a room a player opened; the built-in tables leave it null.
    # Deliberately no ForeignKey: SQLite cannot add one through ALTER, and that
    # alone cost the migration both its downgrade and its repeatability.
    Column("created_by", String(64)),
    Column("visibility", String(16), nullable=False, server_default=text("'public'")),
    # Salted with the room's own id (see online/catalogue.py) and checked on
    # SeatingService.ready() -- replaces the old link-only rooms, which had
    # no check at all on the join path once you had the URL.
    Column("password_hash", String(64)),
    Column("created_at", timestamp, **created_at),
    Column("updated_at", timestamp, **created_at),
    CheckConstraint("scope IN ('network', 'tenant')"),
    CheckConstraint("asset IN ('PLAY', 'CASH_USDT')", name="ck_poker_tables_asset"),
    CheckConstraint("max_seats = 6"),
    CheckConstraint("visibility IN ('public', 'link')", name="ck_poker_tables_visibility"),
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
    Column("cash_escrow_account_id", String(64), ForeignKey(
        "cash_accounts.id", name="fk_table_seats_cash_escrow",
    )),
    Column("stack_units", BIGINT, nullable=False, server_default=text("0")),
    Column("stack_micros", BIGINT, nullable=False, server_default=text("0")),
    Column("state", String(32), nullable=False, server_default=text("'empty'")),
    # When this occupancy began. A session is one occupancy (docs/progression.md
    # §4), and the row is blanked rather than deleted on the way out, so this is
    # also what tells a returning player's new session from their last one.
    Column("seated_at", timestamp),
    Column("disconnected_at", timestamp),
    Column("hold_until", timestamp),
    Column("updated_at", timestamp, **created_at),
    UniqueConstraint("table_id", "seat_no"),
    CheckConstraint("seat_no >= 0 AND seat_no <= 5"),
    CheckConstraint("occupant_kind IN ('empty', 'user', 'system')"),
    CheckConstraint("state IN ('empty', 'seated', 'held', 'leaving')"),
    CheckConstraint("stack_units >= 0"),
    CheckConstraint("stack_micros >= 0", name="ck_table_seats_cash_stack_nonnegative"),
    CheckConstraint(
        "NOT (escrow_account_id IS NOT NULL AND cash_escrow_account_id IS NOT NULL)",
        name="ck_table_seats_one_escrow",
    ),
)

seat_queue = Table(
    "seat_queue", metadata,
    Column("id", String(64), primary_key=True),
    Column("table_id", String(64), ForeignKey("poker_tables.id"), nullable=False),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("seat_no", Integer, nullable=False, server_default=text("0")),
    Column("requested_buy_in_units", BIGINT, nullable=False),
    Column("state", String(32), nullable=False, server_default=text("'waiting'")),
    Column("position_seq", BIGINT, nullable=False),
    Column("created_at", timestamp, **created_at),
    Column("expires_at", timestamp),
    UniqueConstraint("table_id", "user_id"),
    CheckConstraint("seat_no >= 0 AND seat_no <= 5"),
    CheckConstraint("state IN ('waiting', 'cancelled', 'seated', 'expired')"),
)

chat_messages = Table(
    "chat_messages", metadata,
    Column("id", String(64), primary_key=True),
    Column("table_id", String(64), ForeignKey("poker_tables.id"), nullable=False),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("text", String(1000), nullable=False),
    Column("created_at", timestamp, **created_at),
)
Index("ix_chat_messages_table_time", chat_messages.c.table_id, chat_messages.c.created_at)

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

table_runtimes = Table(
    "table_runtimes", metadata,
    Column("table_id", String(64), ForeignKey("poker_tables.id"), primary_key=True),
    Column("revision", BIGINT, nullable=False, server_default=text("0")),
    Column("phase", String(32), nullable=False, server_default=text("'waiting'")),
    Column("private_state_json", JSON),
    Column("public_payload_json", JSON),
    Column("action_deadline", timestamp),
    Column("result_clear_at", timestamp),
    Column("next_hand_at", timestamp),
    Column("paused_reason", String(200)),
    Column("updated_at", timestamp, **created_at),
    CheckConstraint("phase IN ('waiting', 'active', 'result', 'countdown', 'paused')"),
)

game_commands = Table(
    "game_commands", metadata,
    Column("table_id", String(64), ForeignKey("poker_tables.id"), primary_key=True),
    Column("command_id", String(128), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id")),
    Column("expected_revision", BIGINT, nullable=False),
    Column("command_type", String(64), nullable=False),
    Column("payload_json", JSON, nullable=False),
    Column("status", String(32), nullable=False),
    Column("result_json", JSON),
    Column("created_at", timestamp, **created_at),
    CheckConstraint("status IN ('accepted', 'rejected')"),
)

hands = Table(
    "hands", metadata,
    Column("id", String(64), primary_key=True),
    Column("table_id", String(64), ForeignKey("poker_tables.id"), nullable=False),
    Column("revision_started", BIGINT, nullable=False),
    Column("button_seat", Integer, nullable=False),
    Column("board_json", JSON, nullable=False),
    Column("result_json", JSON),
    Column("started_at", timestamp, **created_at),
    Column("completed_at", timestamp),
    Column("terminal", Boolean, nullable=False, server_default=text("false")),
)

hand_players = Table(
    "hand_players", metadata,
    Column("hand_id", String(64), ForeignKey("hands.id"), primary_key=True),
    Column("participant_id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id")),
    Column("system_player_id", String(64), ForeignKey("system_players.id")),
    Column("seat_no", Integer, nullable=False),
    Column("position", String(32), nullable=False),
    Column("start_stack_units", BIGINT),
    Column("end_stack_units", BIGINT),
    Column("cash_escrow_account_id", String(64), ForeignKey(
        "cash_accounts.id", name="fk_hand_players_cash_escrow",
    )),
    Column("start_stack_micros", BIGINT),
    Column("end_stack_micros", BIGINT),
    Column("hole_cards_json", JSON),
    Column("shown", Boolean, nullable=False, server_default=text("false")),
    Column("folded", Boolean, nullable=False, server_default=text("false")),
    Column("net_units", BIGINT),
    Column("net_micros", BIGINT),
)

hand_actions = Table(
    "hand_actions", metadata,
    Column("hand_id", String(64), ForeignKey("hands.id"), primary_key=True),
    Column("sequence", Integer, primary_key=True),
    Column("participant_id", String(64), nullable=False),
    Column("street", String(32), nullable=False),
    Column("action", String(32), nullable=False),
    Column("amount_units", BIGINT, nullable=False),
    Column("pot_before_units", BIGINT, nullable=False),
    Column("pot_after_units", BIGINT, nullable=False),
    Column("to_call_before_units", BIGINT, nullable=False),
    Column("created_at", timestamp, **created_at),
)

integrity_events = Table(
    "integrity_events", metadata,
    Column("id", String(64), primary_key=True),
    Column("tenant_id", String(64), ForeignKey("tenants.id")),
    Column("table_id", String(64), ForeignKey("poker_tables.id")),
    Column("hand_id", String(64), ForeignKey("hands.id")),
    Column("user_id", String(64), ForeignKey("users.id")),
    Column("event_type", String(64), nullable=False),
    Column("public_payload_json", JSON, nullable=False),
    Column("created_at", timestamp, **created_at),
)

user_progression = Table(
    "user_progression", metadata,
    Column("user_id", String(64), ForeignKey("users.id"), primary_key=True),
    Column("xp", Integer, nullable=False, server_default=text("0")),
    Column("level", Integer, nullable=False, server_default=text("1")),
    Column("achievement_points", Integer, nullable=False, server_default=text("0")),
    Column("updated_at", timestamp, **created_at),
    CheckConstraint("xp >= 0"),
)

xp_events = Table(
    "xp_events", metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("amount", Integer, nullable=False),
    Column("source", String(32), nullable=False),
    Column("reference", String(128)),
    Column("idempotency_key", String(200), nullable=False, unique=True),
    Column("created_at", timestamp, **created_at),
    CheckConstraint("amount > 0"),
)

# One row per owner per MSK day. It is the soft cap's counter first and the
# rollup every statistic will be read from second, which is why it is keyed
# the polymorphic way play_accounts already is: bots need the counter, and
# nothing else in here.
progress_days = Table(
    "progress_days", metadata,
    Column("owner_kind", String(32), primary_key=True),
    Column("owner_id", String(64), primary_key=True),
    Column("day", String(10), primary_key=True),
    Column("hands", Integer, nullable=False, server_default=text("0")),
    Column("hands_won", Integer, nullable=False, server_default=text("0")),
    # Of those hands, the ones played where a result counts (§3). It is the
    # denominator of BB/100: counting room hands there would dilute the rate
    # with hands whose result was deliberately never added to it.
    Column("result_hands", Integer, nullable=False, server_default=text("0")),
    # Hands dealt at a table with five or more players in them, and a six-bit
    # mask of the positions played. Both are read by daily missions and both
    # are a single write on the hand that is already being recorded.
    Column("full_table_hands", Integer, nullable=False, server_default=text("0")),
    Column("positions_mask", Integer, nullable=False, server_default=text("0")),
    Column("xp", Integer, nullable=False, server_default=text("0")),
    # Hundredths of a big blind, not units: units from a 1/2 table and a 5/10
    # table cannot be added together, and every comparison in §30 is in BB.
    # Integer hundredths keep the arithmetic exact.
    Column("net_bb_x100", BIGINT, nullable=False, server_default=text("0")),
    CheckConstraint("owner_kind IN ('user', 'system')"),
)

# One row per finished occupancy, written when the seat is released. It has to
# outlive the seat: the report is read from the lobby, by which time the seat
# row has been blanked and reused.
play_sessions = Table(
    "play_sessions", metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("table_id", String(64), ForeignKey("poker_tables.id"), nullable=False),
    Column("started_at", timestamp, nullable=False),
    Column("ended_at", timestamp, **created_at),
    Column("hands", Integer, nullable=False, server_default=text("0")),
    Column("net_units", BIGINT, nullable=False, server_default=text("0")),
    Column("big_blind_units", BIGINT, nullable=False),
    Column("biggest_pot_units", BIGINT, nullable=False, server_default=text("0")),
    Column("xp_earned", Integer, nullable=False, server_default=text("0")),
    # Daily XP that landed as this session closed, kept apart from the hands'
    # own XP: the report says where each number came from, and a card claiming
    # +1 XP for a session that paid 56 is worse than no card.
    Column("daily_xp", Integer, nullable=False, server_default=text("0")),
    Column("seen_at", timestamp),
)
Index("ix_play_sessions_unseen", play_sessions.c.user_id, play_sessions.c.seen_at)

user_achievements = Table(
    "user_achievements", metadata,
    Column("user_id", String(64), ForeignKey("users.id"), primary_key=True),
    Column("code", String(64), primary_key=True),
    Column("progress", BIGINT, nullable=False, server_default=text("0")),
    # Tiers completed, not the tier being worked on: THE GRIND at tier 4 has
    # passed four thresholds and is climbing towards the fifth.
    Column("tier", Integer, nullable=False, server_default=text("0")),
    Column("completed_at", timestamp),
    Column("updated_at", timestamp, **created_at),
)

# Who a player has actually sat with. A count alone cannot say whether the
# person across the table is somebody new, and that is the whole of SOCIAL.
# Bots are never written here (docs/progression.md §3).
user_opponents = Table(
    "user_opponents", metadata,
    Column("user_id", String(64), ForeignKey("users.id"), primary_key=True),
    Column("opponent_id", String(64), ForeignKey("users.id"), primary_key=True),
    Column("first_played_at", timestamp, **created_at),
)

# One row per slot per day, and only once there is something to remember about
# it. Which mission a slot holds is derived from the player and the date (see
# missions.py); reroll_offset is the one part of that a player can change.
user_missions = Table(
    "user_missions", metadata,
    Column("user_id", String(64), ForeignKey("users.id"), primary_key=True),
    Column("day", String(10), primary_key=True),
    Column("slot", String(32), primary_key=True),
    Column("reroll_offset", Integer, nullable=False, server_default=text("0")),
    Column("reroll_claimed", Boolean, nullable=False, server_default=text("false")),
    Column("progress", Integer, nullable=False, server_default=text("0")),
    Column("completed_at", timestamp),
    Column("updated_at", timestamp, **created_at),
    CheckConstraint("slot IN ('volume', 'session', 'variety')"),
)

# The daily quota is separate from mission identity: legacy days can have
# multiple replacement missions whose choices and progress must be preserved.
Index(
    "uq_user_missions_daily_reroll", user_missions.c.user_id, user_missions.c.day, unique=True,
    postgresql_where=user_missions.c.reroll_claimed.is_(True),
    sqlite_where=user_missions.c.reroll_claimed.is_(True),
)

Index("ix_table_runtimes_action_deadline", table_runtimes.c.action_deadline)
Index("ix_hands_table_terminal", hands.c.table_id, hands.c.terminal)
Index("ix_integrity_events_user_time", integrity_events.c.user_id, integrity_events.c.created_at)


cash_accounts = Table(
    "cash_accounts", metadata,
    Column("id", String(64), primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("user_id", String(64), ForeignKey("users.id")),
    Column("reference_id", String(100), nullable=False),
    Column("balance_micros", BIGINT, nullable=False, server_default=text("0")),
    Column("created_at", timestamp, **created_at),
    UniqueConstraint("kind", "reference_id", name="uq_cash_account_reference"),
    CheckConstraint("kind IN ('available', 'escrow', 'withdrawal', 'clearing')", name="ck_cash_account_kind"),
    CheckConstraint("(kind = 'clearing' AND user_id IS NULL) OR (kind <> 'clearing' AND user_id IS NOT NULL)", name="ck_cash_account_owner"),
    CheckConstraint("kind = 'clearing' OR balance_micros >= 0", name="ck_cash_nonnegative"),
)

cash_transactions = Table(
    "cash_transactions", metadata,
    Column("id", String(32), primary_key=True),
    Column("scope", String(64), nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("reference_id", String(100), nullable=False),
    Column("actor", String(100), nullable=False),
    Column("created_at", timestamp, **created_at),
    UniqueConstraint("scope", "idempotency_key", name="uq_cash_transaction_key"),
    CheckConstraint("kind IN ('deposit', 'reserve', 'release', 'settlement', 'payout', 'adjustment')", name="ck_cash_transaction_kind"),
)

cash_entries = Table(
    "cash_entries", metadata,
    Column("transaction_id", String(32), ForeignKey("cash_transactions.id"), primary_key=True),
    Column("account_id", String(64), ForeignKey("cash_accounts.id"), primary_key=True),
    Column("amount_micros", BIGINT, nullable=False),
    Column("created_at", timestamp, **created_at),
    CheckConstraint("amount_micros <> 0", name="ck_cash_nonzero_entry"),
)
Index("ix_cash_entries_account", cash_entries.c.account_id)

cash_deposits = Table(
    "cash_deposits", metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
    Column("request_key", String(200), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("network", String(16), nullable=False),
    Column("token_contract", String(128), nullable=False),
    Column("destination_address", String(128), nullable=False),
    Column("requested_micros", BIGINT, nullable=False),
    Column("expected_micros", BIGINT, nullable=False),
    Column("status", String(32), nullable=False),
    Column("expires_at", timestamp, nullable=False),
    Column("created_at", timestamp, **created_at),
    Column("updated_at", timestamp, **created_at),
    UniqueConstraint("user_id", "request_key", name="uq_cash_deposit_request"),
    UniqueConstraint("destination_address", "expected_micros", name="uq_cash_deposit_amount"),
    CheckConstraint("requested_micros BETWEEN 1000000 AND 100000000", name="ck_cash_deposit_requested"),
    CheckConstraint("expected_micros BETWEEN requested_micros AND 100000000", name="ck_cash_deposit_expected"),
    CheckConstraint("status IN ('created','awaiting_transfer','confirmed','credited','expired','cancelled','review_required')", name="ck_cash_deposit_status"),
)

cash_payment_events = Table(
    "cash_payment_events", metadata,
    Column("id", String(64), primary_key=True),
    Column("provider", String(32), nullable=False),
    Column("external_event_id", String(200), nullable=False),
    Column("event_hash", String(64), nullable=False),
    Column("tx_hash", String(128), nullable=False),
    Column("event_index", Integer, nullable=False),
    Column("network", String(16), nullable=False),
    Column("token_contract", String(128), nullable=False),
    Column("destination_address", String(128), nullable=False),
    Column("amount_micros", BIGINT, nullable=False),
    Column("occurred_at", timestamp, nullable=False),
    Column("status", String(32), nullable=False),
    Column("deposit_id", String(64), ForeignKey("cash_deposits.id")),
    Column("detail_json", JSON, nullable=False, server_default=text("'{}'")),
    Column("created_at", timestamp, **created_at),
    Column("processed_at", timestamp),
    UniqueConstraint("provider", "external_event_id", name="uq_cash_payment_event_external"),
    UniqueConstraint("provider", "tx_hash", "event_index", name="uq_cash_payment_event_chain"),
    CheckConstraint("amount_micros > 0", name="ck_cash_payment_event_amount"),
    CheckConstraint("status IN ('observed','processed','review_required','resolved_credited','resolved_rejected')", name="ck_cash_payment_event_status"),
)

cash_fiat_orders = Table(
    "cash_fiat_orders", metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
    Column("request_key", String(200), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("partner_order_id", BIGINT, unique=True),
    Column("currency", String(3), nullable=False),
    Column("requested_micros", BIGINT, nullable=False),
    Column("fee_micros", BIGINT, nullable=False, server_default=text("0")),
    Column("fiat_kopecks", BIGINT),
    Column("requisites", String(500)),
    Column("trader_username", String(100)),
    Column("status", String(32), nullable=False),
    Column("detail", String(500)),
    Column("user_confirmed", Boolean, nullable=False, server_default=text("false")),
    Column("expires_at", timestamp),
    Column("created_at", timestamp, **created_at),
    Column("updated_at", timestamp, **created_at),
    UniqueConstraint("user_id", "request_key", name="uq_cash_fiat_order_request"),
    CheckConstraint("currency = 'RUB'", name="ck_cash_fiat_order_currency"),
    CheckConstraint("requested_micros BETWEEN 20000000 AND 500000000", name="ck_cash_fiat_order_amount"),
    CheckConstraint("fee_micros >= 0", name="ck_cash_fiat_order_fee"),
    CheckConstraint(
        "status IN ('requesting','unavailable','awaiting_user','waiting_trader','clarifying','credited','expired','cancelled','review_required')",
        name="ck_cash_fiat_order_status",
    ),
)

_active_fiat_order_states = cash_fiat_orders.c.status.in_(
    ("requesting", "awaiting_user", "waiting_trader", "clarifying"),
)
Index(
    "uq_cash_fiat_order_active_user", cash_fiat_orders.c.user_id, unique=True,
    postgresql_where=_active_fiat_order_states,
    sqlite_where=_active_fiat_order_states,
)

cash_fiat_events = Table(
    "cash_fiat_events", metadata,
    Column("provider", String(32), primary_key=True),
    Column("event_id", BIGINT, primary_key=True),
    Column("partner_order_id", BIGINT, nullable=False),
    Column("fiat_order_id", String(64), ForeignKey("cash_fiat_orders.id")),
    Column("event_type", String(32), nullable=False),
    Column("event_hash", String(64)),
    Column("status", String(32), nullable=False),
    Column("detail", String(500)),
    Column("created_at", timestamp, **created_at),
    Column("processed_at", timestamp),
    CheckConstraint("status IN ('observed','processed','review_required')", name="ck_cash_fiat_event_status"),
)

cash_partner_cursors = Table(
    "cash_partner_cursors", metadata,
    Column("provider", String(32), primary_key=True),
    Column("offset", BIGINT, nullable=False, server_default=text("0")),
    Column("updated_at", timestamp, **created_at),
    CheckConstraint('"offset" >= 0', name="ck_cash_partner_cursor_offset"),
)

cash_user_holds = Table(
    "cash_user_holds", metadata,
    Column("user_id", String(64), ForeignKey("users.id"), primary_key=True),
    Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
    Column("reason", String(500), nullable=False),
    Column("operator_id", String(64), ForeignKey("cash_operators.id"), nullable=False),
    Column("created_at", timestamp, **created_at),
)

cash_withdrawals = Table(
    "cash_withdrawals", metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id"), nullable=False),
    Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
    Column("request_key", String(200), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("network", String(16), nullable=False),
    Column("destination_address", String(128), nullable=False),
    Column("amount_micros", BIGINT, nullable=False),
    Column("fee_micros", BIGINT, nullable=False, server_default=text("0")),
    Column("reserve_account_id", String(64), ForeignKey("cash_accounts.id"), nullable=False),
    Column("payout_id", String(64), nullable=False, unique=True),
    Column("tx_hash", String(128)),
    Column("status", String(32), nullable=False),
    Column("detail", String(500)),
    Column("created_at", timestamp, **created_at),
    Column("updated_at", timestamp, **created_at),
    Column("submitted_at", timestamp),
    Column("confirmed_at", timestamp),
    UniqueConstraint("user_id", "request_key", name="uq_cash_withdrawal_request"),
    CheckConstraint("amount_micros BETWEEN 10000 AND 100000000", name="ck_cash_withdrawal_amount"),
    CheckConstraint("fee_micros >= 0", name="ck_cash_withdrawal_fee"),
    CheckConstraint("status IN ('requested','reserved','approved','sending','submitted','confirmed','rejected','cancelled','unknown')", name="ck_cash_withdrawal_status"),
)

cash_operators = Table(
    "cash_operators", metadata,
    Column("id", String(64), primary_key=True),
    Column("telegram_user_id", BIGINT, nullable=False, unique=True),
    Column("tenant_id", String(64), ForeignKey("tenants.id")),
    Column("role", String(16), nullable=False),
    Column("active", Boolean, nullable=False, server_default=text("true")),
    Column("created_at", timestamp, **created_at),
    Column("updated_at", timestamp, **created_at),
    CheckConstraint("role IN ('reviewer','operator','admin')", name="ck_cash_operator_role"),
    CheckConstraint("role = 'admin' OR tenant_id IS NOT NULL", name="ck_cash_operator_scope"),
)

cash_audit_events = Table(
    "cash_audit_events", metadata,
    Column("id", String(64), primary_key=True),
    Column("operator_id", String(64), ForeignKey("cash_operators.id"), nullable=False),
    Column("actor_telegram_user_id", BIGINT, nullable=False),
    Column("tenant_id", String(64), ForeignKey("tenants.id")),
    Column("action", String(64), nullable=False),
    Column("target_type", String(32), nullable=False),
    Column("target_id", String(64), nullable=False),
    Column("reason", String(500), nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("before_json", JSON, nullable=False),
    Column("after_json", JSON, nullable=False),
    Column("created_at", timestamp, **created_at),
    UniqueConstraint("operator_id", "idempotency_key", name="uq_cash_audit_operator_key"),
    CheckConstraint("length(reason) >= 3", name="ck_cash_audit_reason"),
)
Index("ix_cash_audit_tenant_time", cash_audit_events.c.tenant_id, cash_audit_events.c.created_at)
