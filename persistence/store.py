from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import RLock
from uuid import uuid4

from bots.difficulty import normalize_difficulty


class TrainingStore:
    """SQLite persistence for profiles, 7-max seats, bankrolls and training data."""

    INITIAL_BALANCE = 1000.0
    MAX_BOTS = 6

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_db()

    def _connect(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _column_names(con, table: str) -> set[str]:
        return {row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}

    def _ensure_column(self, con, table: str, column: str, definition: str):
        if column not in self._column_names(con, table):
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _setting(self, key: str, default: str | None = None) -> str | None:
        with self._lock, self._connect() as con:
            row = con.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def _set_setting(self, key: str, value: str):
        now = self._now()
        with self._lock, self._connect() as con:
            con.execute(
                """INSERT INTO app_settings(key,value,updated_at) VALUES(?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (key, value, now),
            )

    def _init_db(self):
        with self._lock, self._connect() as con:
            con.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS bankroll (
                    player_id TEXT PRIMARY KEY,
                    balance REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS table_seats (
                    seat INTEGER PRIMARY KEY,
                    player_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    is_bot INTEGER NOT NULL,
                    difficulty TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS human_profiles (
                    profile_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    balance REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS player_models (
                    profile_id TEXT PRIMARY KEY,
                    hands_seen INTEGER NOT NULL DEFAULT 0,
                    model_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS hands7 (
                    hand_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    button TEXT NOT NULL,
                    board_json TEXT NOT NULL,
                    winners_json TEXT NOT NULL DEFAULT '[]',
                    result_text TEXT NOT NULL DEFAULT '',
                    terminal INTEGER NOT NULL DEFAULT 0,
                    reviews_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS hand_players7 (
                    hand_id TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    seat INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    is_bot INTEGER NOT NULL,
                    difficulty TEXT NOT NULL,
                    position TEXT NOT NULL,
                    start_stack REAL NOT NULL,
                    end_stack REAL,
                    cards_json TEXT NOT NULL,
                    folded INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (hand_id, player_id)
                );

                CREATE TABLE IF NOT EXISTS actions7 (
                    hand_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    player_id TEXT NOT NULL,
                    street TEXT NOT NULL,
                    action TEXT NOT NULL,
                    amount REAL NOT NULL,
                    pot_after REAL NOT NULL,
                    PRIMARY KEY (hand_id, seq)
                );

                CREATE TABLE IF NOT EXISTS saved_tables (
                    table_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    seats_json TEXT NOT NULL,
                    button_seat INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_opened_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bot_rebuys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    balance_after REAL NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bot_cooldowns (
                    player_id TEXT PRIMARY KEY,
                    room_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    last_seat INTEGER NOT NULL,
                    busted_at TEXT NOT NULL,
                    return_at TEXT NOT NULL,
                    rebuy_balance REAL NOT NULL DEFAULT 1000
                );
                """
            )

            self._ensure_column(con, "hands7", "profile_id", "TEXT")  # legacy primary-view profile
            self._ensure_column(con, "hand_players7", "profile_id", "TEXT")
            self._ensure_column(con, "actions7", "profile_id", "TEXT")
            self._ensure_column(con, "actions7", "pot_before", "REAL NOT NULL DEFAULT 0")
            self._ensure_column(con, "actions7", "to_call_before", "REAL NOT NULL DEFAULT 0")
            self._ensure_column(con, "actions7", "live_players_before", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(con, "actions7", "position", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(con, "table_seats", "occupant_type", "TEXT NOT NULL DEFAULT 'empty'")
            self._ensure_column(con, "table_seats", "profile_id", "TEXT")
            self._ensure_column(con, "saved_tables", "bot_cooldown_minutes", "INTEGER NOT NULL DEFAULT 10")

            now = self._now()
            # Ensure one default human profile exists, migrating the old hero bankroll/name.
            active = con.execute("SELECT value FROM app_settings WHERE key='active_profile_id'").fetchone()
            active_profile_id = active["value"] if active else "profile_default"
            if not con.execute("SELECT 1 FROM human_profiles WHERE profile_id=?", (active_profile_id,)).fetchone():
                old_hero = con.execute("SELECT balance FROM bankroll WHERE player_id='hero'").fetchone()
                old_seat = con.execute("SELECT name FROM table_seats WHERE seat=0").fetchone()
                con.execute(
                    "INSERT OR IGNORE INTO human_profiles(profile_id,name,balance,created_at,updated_at) VALUES(?,?,?,?,?)",
                    (active_profile_id, (old_seat["name"] if old_seat else "Вы") or "Вы",
                     float(old_hero["balance"]) if old_hero else self.INITIAL_BALANCE, now, now),
                )
                con.execute(
                    "INSERT OR REPLACE INTO app_settings(key,value,updated_at) VALUES('active_profile_id',?,?)",
                    (active_profile_id, now),
                )

            # Always keep exactly seven seat records. Old v0.8 seat 0 becomes a human seat,
            # active old bot seats remain bots, inactive seats become empty.
            existing = {int(r["seat"]): r for r in con.execute("SELECT * FROM table_seats").fetchall()}
            was_fresh = not existing
            for seat in range(7):
                row = existing.get(seat)
                if not row:
                    pid = f"empty_{seat}"
                    con.execute(
                        """INSERT INTO table_seats(seat,player_id,name,is_bot,difficulty,active,updated_at,occupant_type,profile_id)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (seat, pid, "Свободно", 0, "normal", 0, now, "empty", None),
                    )
                    continue
                if seat == 0:
                    con.execute(
                        """UPDATE table_seats SET player_id=?,name=?,is_bot=0,difficulty='normal',active=1,
                           occupant_type='human',profile_id=?,updated_at=? WHERE seat=0""",
                        (f"human_{active_profile_id}", self._profile_name_in_con(con, active_profile_id), active_profile_id, now),
                    )
                elif int(row["active"] or 0):
                    con.execute(
                        "UPDATE table_seats SET occupant_type='bot',profile_id=NULL,is_bot=1,updated_at=? WHERE seat=?",
                        (now, seat),
                    )
                else:
                    con.execute(
                        """UPDATE table_seats SET player_id=?,name='Свободно',is_bot=0,difficulty='normal',active=0,
                           occupant_type='empty',profile_id=NULL,updated_at=? WHERE seat=?""",
                        (f"empty_{seat}", now, seat),
                    )

            if was_fresh:
                con.execute(
                    """UPDATE table_seats SET player_id=?,name=?,is_bot=0,difficulty='normal',active=1,
                       occupant_type='human',profile_id=?,updated_at=? WHERE seat=0""",
                    (f"human_{active_profile_id}", self._profile_name_in_con(con, active_profile_id), active_profile_id, now),
                )
                con.execute(
                    """UPDATE table_seats SET player_id='bot_1',name='Бот 1',is_bot=1,difficulty='normal',active=1,
                       occupant_type='bot',profile_id=NULL,updated_at=? WHERE seat=1""", (now,),
                )
                con.execute(
                    "INSERT OR IGNORE INTO bankroll(player_id,balance,updated_at) VALUES('bot_1',?,?)",
                    (self.INITIAL_BALANCE, now),
                )

            # Old hands/actions of hero are assigned to the migrated profile.
            con.execute("UPDATE hands7 SET profile_id=? WHERE profile_id IS NULL OR profile_id=''", (active_profile_id,))
            con.execute(
                "UPDATE hand_players7 SET profile_id=? WHERE player_id='hero' AND (profile_id IS NULL OR profile_id='')",
                (active_profile_id,),
            )
            con.execute(
                "UPDATE actions7 SET profile_id=? WHERE player_id='hero' AND (profile_id IS NULL OR profile_id='')",
                (active_profile_id,),
            )

        for p in self.list_profiles(include_stats=False):
            self.refresh_profile_model(p["id"])

    @staticmethod
    def _profile_name_in_con(con, profile_id: str) -> str:
        row = con.execute("SELECT name FROM human_profiles WHERE profile_id=?", (profile_id,)).fetchone()
        return row["name"] if row else "Игрок"

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------
    def active_profile_id(self) -> str:
        return self._setting("active_profile_id", "profile_default") or "profile_default"

    def get_profile_record(self, profile_id: str | None = None) -> dict:
        profile_id = profile_id or self.active_profile_id()
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT profile_id,name,balance,created_at,updated_at FROM human_profiles WHERE profile_id=?",
                (profile_id,),
            ).fetchone()
        if not row:
            raise ValueError("Профиль не найден")
        return {
            "id": row["profile_id"], "name": row["name"], "balance": round(float(row["balance"]), 2),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    def list_profiles(self, include_stats: bool = True) -> list[dict]:
        active_id = self.active_profile_id()
        seated = {r["profile_id"] for r in self.get_table() if r.get("occupant_type") == "human"} if include_stats else set()
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT profile_id,name,balance,created_at,updated_at FROM human_profiles ORDER BY created_at"
            ).fetchall()
        out = []
        for r in rows:
            item = {
                "id": r["profile_id"], "name": r["name"], "balance": round(float(r["balance"]), 2),
                "active": r["profile_id"] == active_id, "seated": r["profile_id"] in seated,
                "created_at": r["created_at"],
            }
            if include_stats:
                item["hands"] = self._count_profile_hands(r["profile_id"])
            out.append(item)
        return out

    def create_profile(self, name: str) -> dict:
        clean = (name or "").strip()[:24]
        if not clean:
            raise ValueError("Введите имя профиля")
        now = self._now()
        pid = "p_" + uuid4().hex[:12]
        with self._lock, self._connect() as con:
            if con.execute("SELECT 1 FROM human_profiles WHERE lower(name)=lower(?)", (clean,)).fetchone():
                raise ValueError("Профиль с таким именем уже существует")
            con.execute(
                "INSERT INTO human_profiles(profile_id,name,balance,created_at,updated_at) VALUES(?,?,?,?,?)",
                (pid, clean, self.INITIAL_BALANCE, now, now),
            )
        self.refresh_profile_model(pid)
        return self.get_profile_record(pid)

    def select_profile(self, profile_id: str) -> dict:
        """Select a profile for the stats panel without changing any seat."""
        self.get_profile_record(profile_id)
        self._set_setting("active_profile_id", profile_id)
        return self.profile(profile_id)

    def activate_profile(self, profile_id: str) -> dict:
        record = self.get_profile_record(profile_id)
        self._set_setting("active_profile_id", profile_id)
        humans = [r for r in self.get_table() if r["active"] and r["occupant_type"] == "human"]
        # Preserve v0.8's single-player workflow: with one human in seat 0,
        # selecting another profile also swaps that seat. Once multiple humans
        # are seated, selection is stats-only and never changes the table.
        if len(humans) == 1 and humans[0]["seat"] == 0:
            self.set_human_seat(0, profile_id)
        return self.profile(profile_id)

    def rename_profile(self, profile_id: str, name: str) -> dict:
        clean = (name or "").strip()[:24]
        if not clean:
            raise ValueError("Введите имя профиля")
        now = self._now()
        with self._lock, self._connect() as con:
            if con.execute(
                "SELECT 1 FROM human_profiles WHERE lower(name)=lower(?) AND profile_id<>?", (clean, profile_id)
            ).fetchone():
                raise ValueError("Профиль с таким именем уже существует")
            cur = con.execute("UPDATE human_profiles SET name=?,updated_at=? WHERE profile_id=?", (clean, now, profile_id))
            if not cur.rowcount:
                raise ValueError("Профиль не найден")
            con.execute("UPDATE table_seats SET name=?,updated_at=? WHERE profile_id=?", (clean, now, profile_id))
        self._autosave_current_table()
        return self.profile(profile_id)

    def _count_profile_hands(self, profile_id: str) -> int:
        with self._lock, self._connect() as con:
            row = con.execute(
                """SELECT COUNT(DISTINCT hp.hand_id) AS n FROM hand_players7 hp
                   JOIN hands7 h ON h.hand_id=hp.hand_id
                   WHERE h.terminal=1 AND hp.profile_id=?""", (profile_id,)
            ).fetchone()
        return int(row["n"] or 0)

    # ------------------------------------------------------------------
    # Balances / current table
    # ------------------------------------------------------------------
    def get_balances(self) -> dict[str, float]:
        """Legacy HU compatibility used by older tests/tools."""
        bot = self.get_balance("bot")
        with self._lock, self._connect() as con:
            if not con.execute("SELECT 1 FROM bankroll WHERE player_id='bot'").fetchone():
                bot = self.get_balance("bot_1")
        return {"hero": float(self.get_profile_record()["balance"]), "bot": float(bot)}

    def set_balances(self, hero: float, bot: float):
        self.set_profile_balance(self.active_profile_id(), hero)
        self.set_balance("bot", bot)

    def get_balance(self, player_id: str) -> float:
        if player_id.startswith("human_"):
            return self.get_profile_record(player_id.removeprefix("human_"))["balance"]
        with self._lock, self._connect() as con:
            row = con.execute("SELECT balance FROM bankroll WHERE player_id=?", (player_id,)).fetchone()
        return float(row["balance"]) if row else self.INITIAL_BALANCE

    def set_balance(self, player_id: str, balance: float):
        now = self._now()
        if player_id.startswith("human_"):
            self.set_profile_balance(player_id.removeprefix("human_"), balance)
            return
        with self._lock, self._connect() as con:
            con.execute(
                """INSERT INTO bankroll(player_id,balance,updated_at) VALUES(?,?,?)
                   ON CONFLICT(player_id) DO UPDATE SET balance=excluded.balance,updated_at=excluded.updated_at""",
                (player_id, float(balance), now),
            )

    def set_profile_balance(self, profile_id: str, balance: float):
        with self._lock, self._connect() as con:
            cur = con.execute(
                "UPDATE human_profiles SET balance=?,updated_at=? WHERE profile_id=?",
                (float(balance), self._now(), profile_id),
            )
            if not cur.rowcount:
                raise ValueError("Профиль не найден")

    def _seat_rows(self):
        with self._lock, self._connect() as con:
            return con.execute("SELECT * FROM table_seats ORDER BY seat").fetchall()

    def get_table(self) -> list[dict]:
        out = []
        for r in self._seat_rows():
            seat = int(r["seat"])
            typ = r["occupant_type"] or ("bot" if r["is_bot"] else "empty")
            active = bool(r["active"]) and typ != "empty"
            profile_id = r["profile_id"] if typ == "human" else None
            if typ == "human" and profile_id:
                try:
                    rec = self.get_profile_record(profile_id)
                    name, balance = rec["name"], rec["balance"]
                except ValueError:
                    typ, active, profile_id, name, balance = "empty", False, None, "Свободно", self.INITIAL_BALANCE
            elif typ == "bot" and active:
                name, balance = r["name"], round(self.get_balance(r["player_id"]), 2)
            else:
                name, balance = "Свободно", self.INITIAL_BALANCE
            public_id = "hero" if typ == "human" and seat == 0 else r["player_id"]
            out.append({
                "seat": seat, "id": public_id, "profile_id": profile_id, "name": name,
                "occupant_type": typ, "is_bot": typ == "bot", "difficulty": r["difficulty"],
                "active": active, "balance": balance,
            })
        return out

    def active_seats(self) -> list[dict]:
        return [r for r in self.get_table() if r["active"]]

    def _ensure_profile_not_seated_elsewhere(self, profile_id: str, seat: int):
        for row in self.get_table():
            if row["seat"] != seat and row.get("profile_id") == profile_id and row["active"]:
                raise ValueError(f"Профиль «{row['name']}» уже сидит за столом")

    def set_human_seat(self, seat: int, profile_id: str) -> dict:
        if not 0 <= seat <= 6:
            raise ValueError("Неверное место")
        profile = self.get_profile_record(profile_id)
        self._ensure_profile_not_seated_elsewhere(profile_id, seat)
        now = self._now()
        with self._lock, self._connect() as con:
            con.execute(
                """UPDATE table_seats SET player_id=?,name=?,is_bot=0,difficulty='normal',active=1,
                   occupant_type='human',profile_id=?,updated_at=? WHERE seat=?""",
                (f"human_{profile_id}", profile["name"], profile_id, now, seat),
            )
        self._autosave_current_table()
        return next(r for r in self.get_table() if r["seat"] == seat)

    def add_bot(self, seat: int, name: str | None = None, difficulty: str = "normal") -> dict:
        if not 0 <= seat <= 6:
            raise ValueError("Неверное место")
        current_table = self.get_table()
        current = next(r for r in current_table if r["seat"] == seat)
        bot_count = sum(1 for r in current_table if r["active"] and r["occupant_type"] == "bot")
        if current["occupant_type"] != "bot" and bot_count >= self.MAX_BOTS:
            raise ValueError("За одним столом может быть не больше 6 ботов")
        difficulty = normalize_difficulty(difficulty)
        clean = (name or f"Бот {seat + 1}").strip()[:24] or f"Бот {seat + 1}"
        # Editing an already seated bot keeps its identity and bankroll.
        # A bot added to an empty/human chair is a NEW room participant: give it
        # a unique id and a fresh deposit. Reusing ids such as ``bot_4`` caused
        # a newly added bot to inherit a previously busted bot's 0.00 BB balance.
        is_existing_bot = current["occupant_type"] == "bot"
        bot_id = current["id"] if is_existing_bot else "bot_" + uuid4().hex[:12]
        now = self._now()
        with self._lock, self._connect() as con:
            con.execute(
                """UPDATE table_seats SET player_id=?,name=?,is_bot=1,difficulty=?,active=1,
                   occupant_type='bot',profile_id=NULL,updated_at=? WHERE seat=?""",
                (bot_id, clean, difficulty, now, seat),
            )
            if is_existing_bot:
                con.execute(
                    "INSERT OR IGNORE INTO bankroll(player_id,balance,updated_at) VALUES(?,?,?)",
                    (bot_id, self.INITIAL_BALANCE, now),
                )
            else:
                con.execute(
                    """INSERT INTO bankroll(player_id,balance,updated_at) VALUES(?,?,?)
                       ON CONFLICT(player_id) DO UPDATE SET balance=excluded.balance,updated_at=excluded.updated_at""",
                    (bot_id, self.INITIAL_BALANCE, now),
                )
        self._autosave_current_table()
        return next(r for r in self.get_table() if r["seat"] == seat)

    def clear_seat(self, seat: int):
        if not 0 <= seat <= 6:
            raise ValueError("Неверное место")
        now = self._now()
        with self._lock, self._connect() as con:
            con.execute(
                """UPDATE table_seats SET player_id=?,name='Свободно',is_bot=0,difficulty='normal',active=0,
                   occupant_type='empty',profile_id=NULL,updated_at=? WHERE seat=?""",
                (f"empty_{seat}", now, seat),
            )
        self._autosave_current_table()

    # v0.8 endpoint compatibility
    def remove_bot(self, seat: int):
        self.clear_seat(seat)

    def update_bot(self, seat: int, name: str | None = None, difficulty: str | None = None) -> dict:
        row = next(x for x in self.get_table() if x["seat"] == seat)
        return self.add_bot(seat, name or row["name"], difficulty or row["difficulty"])

    def reset_balances(self):
        now = self._now()
        with self._lock, self._connect() as con:
            con.execute("UPDATE human_profiles SET balance=?,updated_at=?", (self.INITIAL_BALANCE, now))
            con.execute("UPDATE bankroll SET balance=?,updated_at=?", (self.INITIAL_BALANCE, now))
        self._autosave_current_table()
        return self.get_table()

    # ------------------------------------------------------------------
    # Bot bust / cooldown lifecycle
    # ------------------------------------------------------------------
    def bot_cooldown_minutes(self) -> int:
        try:
            value = int(self._setting("bot_bust_cooldown_minutes", "10") or 10)
        except (TypeError, ValueError):
            value = 10
        return value if value in {5, 10, 15} else 10

    def set_bot_cooldown_minutes(self, minutes: int) -> int:
        minutes = int(minutes)
        if minutes not in {5, 10, 15}:
            raise ValueError("Тайм-аут бота может быть 5, 10 или 15 минут")
        self._set_setting("bot_bust_cooldown_minutes", str(minutes))
        self._autosave_current_table()
        return minutes

    def _room_key(self) -> str:
        return self.current_table_id() or "__unsaved__"

    @staticmethod
    def _parse_time(value: str) -> datetime:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    def bot_cooldowns(self, room_key: str | None = None) -> list[dict]:
        room_key = room_key or self._room_key()
        now_dt = datetime.now(timezone.utc)
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM bot_cooldowns WHERE room_key=? ORDER BY return_at",
                (room_key,),
            ).fetchall()
        out = []
        for r in rows:
            return_at = self._parse_time(r["return_at"])
            remaining = max(0, int((return_at - now_dt).total_seconds() + 0.999))
            out.append({
                "player_id": r["player_id"],
                "name": r["name"],
                "difficulty": r["difficulty"],
                "last_seat": int(r["last_seat"]),
                "busted_at": r["busted_at"],
                "return_at": r["return_at"],
                "remaining_seconds": remaining,
                "ready": remaining <= 0,
                "rebuy_balance": float(r["rebuy_balance"]),
            })
        return out

    def eject_busted_bots(self, minimum_stack: float = 1.0, minutes: int | None = None) -> list[dict]:
        """Remove busted bots from the room; the seat becomes immediately free.

        The bot itself is put on a room-scoped cooldown. No seat is reserved.
        """
        minutes = self.bot_cooldown_minutes() if minutes is None else int(minutes)
        if minutes not in {5, 10, 15}:
            raise ValueError("Тайм-аут бота может быть 5, 10 или 15 минут")
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        return_at = (now_dt + timedelta(minutes=minutes)).isoformat()
        room_key = self._room_key()
        busted = []
        for row in list(self.active_seats()):
            if row["occupant_type"] != "bot" or float(row["balance"]) >= float(minimum_stack):
                continue
            player_id = row["id"]
            with self._lock, self._connect() as con:
                con.execute(
                    """INSERT INTO bot_cooldowns(player_id,room_key,name,difficulty,last_seat,busted_at,return_at,rebuy_balance)
                       VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(player_id) DO UPDATE SET room_key=excluded.room_key,name=excluded.name,
                         difficulty=excluded.difficulty,last_seat=excluded.last_seat,busted_at=excluded.busted_at,
                         return_at=excluded.return_at,rebuy_balance=excluded.rebuy_balance""",
                    (player_id, room_key, row["name"], row["difficulty"], int(row["seat"]), now, return_at, self.INITIAL_BALANCE),
                )
                con.execute(
                    """UPDATE table_seats SET player_id=?,name='Свободно',is_bot=0,difficulty='normal',active=0,
                       occupant_type='empty',profile_id=NULL,updated_at=? WHERE seat=?""",
                    (f"empty_{int(row['seat'])}", now, int(row["seat"])),
                )
            busted.append({
                "player_id": player_id, "name": row["name"], "last_seat": int(row["seat"]),
                "cooldown_minutes": minutes, "return_at": return_at,
            })
        if busted:
            self._autosave_current_table()
        return busted

    def return_ready_bots(self) -> list[dict]:
        """Seat ready bots in any free chair. Original chair is preferred but never reserved."""
        room_key = self._room_key()
        ready = [r for r in self.bot_cooldowns(room_key) if r["ready"]]
        if not ready:
            return []
        returned = []
        now = self._now()
        for bot in ready:
            table = self.get_table()
            if sum(1 for r in table if r["active"] and r["occupant_type"] == "bot") >= self.MAX_BOTS:
                break
            free = [r for r in table if not r["active"] or r["occupant_type"] == "empty"]
            if not free:
                break
            target = next((r for r in free if int(r["seat"]) == int(bot["last_seat"])), free[0])
            seat = int(target["seat"])
            with self._lock, self._connect() as con:
                con.execute(
                    """UPDATE table_seats SET player_id=?,name=?,is_bot=1,difficulty=?,active=1,
                       occupant_type='bot',profile_id=NULL,updated_at=? WHERE seat=?""",
                    (bot["player_id"], bot["name"], normalize_difficulty(bot["difficulty"]), now, seat),
                )
                con.execute(
                    """INSERT INTO bankroll(player_id,balance,updated_at) VALUES(?,?,?)
                       ON CONFLICT(player_id) DO UPDATE SET balance=excluded.balance,updated_at=excluded.updated_at""",
                    (bot["player_id"], float(bot["rebuy_balance"]), now),
                )
                con.execute("DELETE FROM bot_cooldowns WHERE player_id=?", (bot["player_id"],))
            returned.append({
                "player_id": bot["player_id"], "name": bot["name"], "seat": seat,
                "balance": float(bot["rebuy_balance"]),
            })
        if returned:
            self._autosave_current_table()
        return returned

    # Legacy API: instant rebuy is intentionally disabled from v0.9.2 onward.
    def rebuy_busted_bots(self, minimum_stack: float = 1.0) -> list[dict]:
        return []

    # ------------------------------------------------------------------
    # Saved tables
    # ------------------------------------------------------------------
    def current_table_id(self) -> str | None:
        value = self._setting("current_saved_table_id", "") or ""
        return value or None

    def _table_snapshot(self) -> list[dict]:
        snap = []
        for row in self.get_table():
            item = {
                "seat": row["seat"], "occupant_type": row["occupant_type"], "profile_id": row.get("profile_id"),
                "player_id": row["id"], "name": row["name"], "difficulty": row["difficulty"],
            }
            if row["occupant_type"] == "bot":
                item["balance"] = row["balance"]
            snap.append(item)
        return snap

    def list_saved_tables(self) -> list[dict]:
        current = self.current_table_id()
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT table_id,name,seats_json,button_seat,bot_cooldown_minutes,created_at,updated_at,last_opened_at FROM saved_tables ORDER BY last_opened_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            try:
                seats = json.loads(r["seats_json"])
            except json.JSONDecodeError:
                seats = []
            out.append({
                "id": r["table_id"], "name": r["name"], "button_seat": int(r["button_seat"]),
                "bot_cooldown_minutes": int(r["bot_cooldown_minutes"] or 10),
                "players": sum(1 for s in seats if s.get("occupant_type") != "empty"),
                "humans": sum(1 for s in seats if s.get("occupant_type") == "human"),
                "bots": sum(1 for s in seats if s.get("occupant_type") == "bot"),
                "current": r["table_id"] == current, "updated_at": r["updated_at"],
            })
        return out

    def save_current_table(self, name: str, table_id: str | None = None, button_seat: int = 0) -> dict:
        clean = (name or "").strip()[:40]
        if not clean:
            raise ValueError("Введите название стола")
        now = self._now()
        table_id = table_id or "t_" + uuid4().hex[:12]
        payload = json.dumps(self._table_snapshot(), ensure_ascii=False)
        with self._lock, self._connect() as con:
            con.execute(
                """INSERT INTO saved_tables(table_id,name,seats_json,button_seat,bot_cooldown_minutes,created_at,updated_at,last_opened_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(table_id) DO UPDATE SET name=excluded.name,seats_json=excluded.seats_json,
                     button_seat=excluded.button_seat,bot_cooldown_minutes=excluded.bot_cooldown_minutes,
                     updated_at=excluded.updated_at,last_opened_at=excluded.last_opened_at""",
                (table_id, clean, payload, int(button_seat), self.bot_cooldown_minutes(), now, now, now),
            )
        self._set_setting("current_saved_table_id", table_id)
        return next(t for t in self.list_saved_tables() if t["id"] == table_id)

    def _autosave_current_table(self):
        table_id = self.current_table_id()
        if not table_id:
            return
        with self._lock, self._connect() as con:
            row = con.execute("SELECT name,button_seat FROM saved_tables WHERE table_id=?", (table_id,)).fetchone()
        if row:
            self.save_current_table(row["name"], table_id, int(row["button_seat"]))

    def load_saved_table(self, table_id: str) -> dict:
        with self._lock, self._connect() as con:
            row = con.execute("SELECT * FROM saved_tables WHERE table_id=?", (table_id,)).fetchone()
        if not row:
            raise ValueError("Сохранённый стол не найден")
        try:
            seats = json.loads(row["seats_json"])
        except json.JSONDecodeError as exc:
            raise ValueError("Не удалось прочитать состав стола") from exc

        # Validate composition before mutating the table.
        if sum(1 for s in seats if s.get("occupant_type") == "bot") > self.MAX_BOTS:
            raise ValueError("В сохранённом столе больше 6 ботов")
        for s in seats:
            if s.get("occupant_type") == "human":
                self.get_profile_record(s.get("profile_id"))

        now = self._now()
        with self._lock, self._connect() as con:
            # Clear first so UNIQUE(player_id) never blocks profiles/bots that move
            # to a different seat between saved tables.
            for seat in range(7):
                con.execute(
                    """UPDATE table_seats SET player_id=?,name='Свободно',is_bot=0,difficulty='normal',active=0,
                       occupant_type='empty',profile_id=NULL,updated_at=? WHERE seat=?""",
                    (f"empty_{seat}", now, seat),
                )
            for seat in range(7):
                s = next((x for x in seats if int(x.get("seat", -1)) == seat), None) or {"occupant_type": "empty"}
                typ = s.get("occupant_type", "empty")
                if typ == "human":
                    p = con.execute("SELECT name FROM human_profiles WHERE profile_id=?", (s["profile_id"],)).fetchone()
                    con.execute(
                        """UPDATE table_seats SET player_id=?,name=?,is_bot=0,difficulty='normal',active=1,
                           occupant_type='human',profile_id=?,updated_at=? WHERE seat=?""",
                        (f"human_{s['profile_id']}", p["name"], s["profile_id"], now, seat),
                    )
                elif typ == "bot":
                    bot_id = s.get("player_id") or "bot_" + uuid4().hex[:12]
                    con.execute(
                        """UPDATE table_seats SET player_id=?,name=?,is_bot=1,difficulty=?,active=1,
                           occupant_type='bot',profile_id=NULL,updated_at=? WHERE seat=?""",
                        (bot_id, s.get("name") or f"Бот {seat + 1}", normalize_difficulty(s.get("difficulty", "normal")), now, seat),
                    )
                    con.execute(
                        """INSERT INTO bankroll(player_id,balance,updated_at) VALUES(?,?,?)
                           ON CONFLICT(player_id) DO UPDATE SET balance=excluded.balance,updated_at=excluded.updated_at""",
                        (bot_id, float(s.get("balance", self.INITIAL_BALANCE)), now),
                    )
                else:
                    con.execute(
                        """UPDATE table_seats SET player_id=?,name='Свободно',is_bot=0,difficulty='normal',active=0,
                           occupant_type='empty',profile_id=NULL,updated_at=? WHERE seat=?""",
                        (f"empty_{seat}", now, seat),
                    )
            con.execute("UPDATE saved_tables SET last_opened_at=? WHERE table_id=?", (now, table_id))
        self._set_setting("current_saved_table_id", table_id)
        self._set_setting("bot_bust_cooldown_minutes", str(int(row["bot_cooldown_minutes"] or 10)))
        return {"table": self.get_table(), "saved_table": next(t for t in self.list_saved_tables() if t["id"] == table_id)}

    def delete_saved_table(self, table_id: str):
        with self._lock, self._connect() as con:
            cur = con.execute("DELETE FROM saved_tables WHERE table_id=?", (table_id,))
        if not cur.rowcount:
            raise ValueError("Сохранённый стол не найден")
        if self.current_table_id() == table_id:
            self._set_setting("current_saved_table_id", "")

    # ------------------------------------------------------------------
    # Hands / training
    # ------------------------------------------------------------------
    def save_state(self, state):
        now = self._now()
        human_profile_ids = [
            (p.profile_id or (self.active_profile_id() if p.id == "hero" else None))
            for p in state.players.values() if not p.is_bot
        ]
        human_profile_ids = [x for x in human_profile_ids if x]
        legacy_profile_id = human_profile_ids[0] if human_profile_ids else self.active_profile_id()

        with self._lock, self._connect() as con:
            existing = con.execute("SELECT started_at FROM hands7 WHERE hand_id=?", (state.hand_id,)).fetchone()
            started_at = existing["started_at"] if existing else now
            con.execute(
                """INSERT INTO hands7(hand_id,started_at,updated_at,completed_at,button,board_json,winners_json,
                                      result_text,terminal,reviews_json,profile_id)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(hand_id) DO UPDATE SET updated_at=excluded.updated_at,completed_at=excluded.completed_at,
                     button=excluded.button,board_json=excluded.board_json,winners_json=excluded.winners_json,
                     result_text=excluded.result_text,terminal=excluded.terminal,reviews_json=excluded.reviews_json""",
                (state.hand_id, started_at, now, now if state.terminal else None, state.button,
                 json.dumps(state.board), json.dumps(state.winners), state.result_text, 1 if state.terminal else 0,
                 json.dumps(state.decision_reviews, ensure_ascii=False), legacy_profile_id),
            )

            for pid in state.seat_order:
                p = state.players[pid]
                player_profile_id = p.profile_id or (self.active_profile_id() if (not p.is_bot and pid == "hero") else None)
                con.execute(
                    """INSERT INTO hand_players7(hand_id,player_id,seat,name,is_bot,difficulty,position,start_stack,
                                                  end_stack,cards_json,folded,profile_id)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(hand_id,player_id) DO UPDATE SET name=excluded.name,difficulty=excluded.difficulty,
                         position=excluded.position,end_stack=excluded.end_stack,cards_json=excluded.cards_json,
                         folded=excluded.folded,profile_id=excluded.profile_id""",
                    (state.hand_id, pid, p.seat, p.name, 1 if p.is_bot else 0, p.difficulty, p.position,
                     float(state.starting_stacks[pid]), float(p.stack) if state.terminal else None,
                     json.dumps(p.hole_cards), 1 if p.folded else 0, player_profile_id),
                )

            con.execute("DELETE FROM actions7 WHERE hand_id=?", (state.hand_id,))
            for idx, a in enumerate(state.history):
                p = state.players[a.player_id]
                action_profile_id = p.profile_id or (self.active_profile_id() if (not p.is_bot and p.id == "hero") else None)
                con.execute(
                    """INSERT INTO actions7(hand_id,seq,player_id,street,action,amount,pot_after,profile_id,
                                            pot_before,to_call_before,live_players_before,position)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (state.hand_id, idx, a.player_id, a.street.value, a.action.value, float(a.amount), float(a.pot_after),
                     action_profile_id, float(a.pot_before), float(a.to_call_before), int(a.live_players_before), p.position),
                )

            if state.terminal:
                for pid in state.seat_order:
                    p = state.players[pid]
                    player_profile_id = p.profile_id or (self.active_profile_id() if (not p.is_bot and pid == "hero") else None)
                    if not p.is_bot and player_profile_id:
                        con.execute(
                            "UPDATE human_profiles SET balance=?,updated_at=? WHERE profile_id=?",
                            (float(p.stack), now, player_profile_id),
                        )
                    elif p.is_bot:
                        con.execute(
                            """INSERT INTO bankroll(player_id,balance,updated_at) VALUES(?,?,?)
                               ON CONFLICT(player_id) DO UPDATE SET balance=excluded.balance,updated_at=excluded.updated_at""",
                            (pid, float(p.stack), now),
                        )

        if state.terminal:
            for profile_id in set(human_profile_ids):
                self.refresh_profile_model(profile_id)
            self._autosave_current_table()

    def discard_incomplete_hand(self, hand_id: str) -> bool:
        with self._lock, self._connect() as con:
            row = con.execute("SELECT terminal FROM hands7 WHERE hand_id=?", (hand_id,)).fetchone()
            if not row or int(row["terminal"] or 0):
                return False
            con.execute("DELETE FROM actions7 WHERE hand_id=?", (hand_id,))
            con.execute("DELETE FROM hand_players7 WHERE hand_id=?", (hand_id,))
            con.execute("DELETE FROM hands7 WHERE hand_id=?", (hand_id,))
        return True

    # ------------------------------------------------------------------
    # Long-term player models
    # ------------------------------------------------------------------
    def _profile_stats(self, profile_id: str) -> dict:
        profile = self.get_profile_record(profile_id)
        with self._lock, self._connect() as con:
            hand_rows = con.execute(
                """SELECT h.hand_id,h.reviews_json,h.winners_json,hp.player_id
                   FROM hands7 h JOIN hand_players7 hp ON hp.hand_id=h.hand_id
                   WHERE h.terminal=1 AND hp.profile_id=? ORDER BY h.started_at""",
                (profile_id,),
            ).fetchall()
            action_rows = con.execute(
                """SELECT hand_id,seq,player_id,street,action,amount,pot_before,to_call_before,position
                   FROM actions7 WHERE profile_id=?
                   ORDER BY hand_id,seq""", (profile_id,)
            ).fetchall()

        by_hand: dict[str, list[dict]] = {}
        for r in action_rows:
            by_hand.setdefault(r["hand_id"], []).append(dict(r))

        total = len(hand_rows)
        vpip_hands = pfr_hands = three_bets = three_bet_opportunities = 0
        fold3 = fold3_opportunities = post_aggr = post_calls = wins = 0
        ev_losses: list[float] = []

        for hand in hand_rows:
            player_id = hand["player_id"]
            actions = by_hand.get(hand["hand_id"], [])
            pre = [r for r in actions if r["street"] == "preflop"]
            mine = [r for r in pre if r["player_id"] == player_id]
            if any(r["action"] in {"call", "bet", "raise", "all_in"} for r in mine):
                vpip_hands += 1
            if any(r["action"] in {"raise", "all_in"} for r in mine):
                pfr_hands += 1

            raises_seen = 0
            mine_raised = mine_opened = waiting_fold = counted_3 = counted_fold = False
            for r in pre:
                aggressive = r["action"] in {"raise", "all_in"}
                if r["player_id"] == player_id:
                    if raises_seen == 1 and not mine_raised and not counted_3:
                        three_bet_opportunities += 1; counted_3 = True
                        if aggressive: three_bets += 1
                    if waiting_fold and not counted_fold:
                        fold3_opportunities += 1; counted_fold = True
                        if r["action"] == "fold": fold3 += 1
                    if aggressive:
                        if raises_seen == 0: mine_opened = True
                        mine_raised = True
                elif aggressive and mine_opened and raises_seen >= 1 and not counted_fold:
                    waiting_fold = True
                if aggressive: raises_seen += 1

            post = [r for r in actions if r["player_id"] == player_id and r["street"] in {"flop", "turn", "river"}]
            post_aggr += sum(r["action"] in {"bet", "raise", "all_in"} for r in post)
            post_calls += sum(r["action"] == "call" for r in post)

            try: winners = json.loads(hand["winners_json"] or "[]")
            except json.JSONDecodeError: winners = []
            if player_id in winners: wins += 1
            try: reviews = json.loads(hand["reviews_json"] or "[]")
            except json.JSONDecodeError: reviews = []
            ev_losses.extend(
                float(r["ev_loss_bb"]) for r in reviews
                if "ev_loss_bb" in r and (r.get("profile_id") == profile_id or (not r.get("profile_id") and player_id == "hero"))
            )

        aggression = post_aggr / post_calls if post_calls else float(post_aggr)
        return {
            "id": profile["id"], "name": profile["name"], "hands": total,
            "hero_balance": profile["balance"], "balance": profile["balance"],
            "vpip": round(vpip_hands / total * 100, 1) if total else 0.0,
            "pfr": round(pfr_hands / total * 100, 1) if total else 0.0,
            "three_bet": round(three_bets / three_bet_opportunities * 100, 1) if three_bet_opportunities else 0.0,
            "three_bet_opportunities": three_bet_opportunities,
            "fold_to_3bet": round(fold3 / fold3_opportunities * 100, 1) if fold3_opportunities else 0.0,
            "fold_to_3bet_opportunities": fold3_opportunities,
            "postflop_aggression": round(aggression, 2),
            "avg_ev_loss_bb": round(sum(ev_losses) / len(ev_losses), 3) if ev_losses else 0.0,
            "decisions_reviewed": len(ev_losses),
            "win_rate_hands": round(wins / total * 100, 1) if total else 0.0,
        }

    @staticmethod
    def _build_model(stats: dict) -> dict:
        hands = int(stats["hands"])
        confidence = min(1.0, hands / 200.0)
        traits: list[dict] = []
        def trait(key, label, detail, strength):
            traits.append({"key": key, "label": label, "detail": detail, "strength": round(max(0, min(1, strength)), 2)})
        if hands >= 12:
            if stats["vpip"] >= 42: trait("loose", "Широкий вход в банки", f"VPIP {stats['vpip']:.1f}%", (stats["vpip"]-35)/30)
            elif stats["vpip"] <= 23: trait("tight", "Тайтовый префлоп", f"VPIP {stats['vpip']:.1f}%", (28-stats["vpip"])/20)
            gap = stats["vpip"] - stats["pfr"]
            if gap >= 15: trait("preflop_passive", "Много коллов префлоп", f"разрыв VPIP/PFR {gap:.1f} п.п.", gap/35)
            if stats["pfr"] >= 31: trait("preflop_aggressive", "Высокая префлоп-агрессия", f"PFR {stats['pfr']:.1f}%", (stats["pfr"]-25)/25)
        if stats["three_bet_opportunities"] >= 8:
            if stats["three_bet"] >= 12: trait("threebet_high", "Частые 3-беты", f"3-bet {stats['three_bet']:.1f}%", stats["three_bet"]/25)
            elif stats["three_bet"] <= 5: trait("threebet_low", "Редкие 3-беты", f"3-bet {stats['three_bet']:.1f}%", (7-stats["three_bet"])/7)
        if stats["fold_to_3bet_opportunities"] >= 6:
            if stats["fold_to_3bet"] >= 65: trait("overfold_3bet", "Часто сдаётся на 3-бет", f"fold to 3-bet {stats['fold_to_3bet']:.1f}%", (stats["fold_to_3bet"]-50)/40)
            elif stats["fold_to_3bet"] <= 35: trait("sticky_3bet", "Часто продолжает против 3-бета", f"fold to 3-bet {stats['fold_to_3bet']:.1f}%", (45-stats["fold_to_3bet"])/40)
        if hands >= 20:
            if stats["postflop_aggression"] >= 3: trait("postflop_aggressive", "Агрессивный постфлоп", f"AF {stats['postflop_aggression']:.2f}", stats["postflop_aggression"]/6)
            elif stats["postflop_aggression"] <= 1.1: trait("postflop_passive", "Пассивный постфлоп", f"AF {stats['postflop_aggression']:.2f}", (1.5-stats["postflop_aggression"])/1.5)
        if stats["decisions_reviewed"] >= 10 and stats["avg_ev_loss_bb"] >= .35:
            trait("ev_leaks", "Повторяющиеся EV-потери", f"в среднем {stats['avg_ev_loss_bb']:.3f} ББ", stats["avg_ev_loss_bb"]/1.5)
        traits.sort(key=lambda x: x["strength"], reverse=True)
        exploit = {
            "value_widen": max(-1, min(1, (stats["vpip"]-32)/28)) if hands else 0,
            "bluff_pressure": max(-1, min(1, (stats["fold_to_3bet"]-50)/35)) if stats["fold_to_3bet_opportunities"] >= 6 else 0,
            "call_down": max(-1, min(1, (stats["postflop_aggression"]-1.8)/2.5)) if hands >= 20 else 0,
            "preflop_passivity": max(0, min(1, (stats["vpip"]-stats["pfr"]-8)/25)) if hands >= 12 else 0,
        }
        return {"profile_id": stats["id"], "hands_seen": hands, "confidence": round(confidence,3),
                "confidence_pct": round(confidence*100,1), "traits": traits[:6],
                "exploit": {k: round(v,3) for k,v in exploit.items()}}

    def refresh_profile_model(self, profile_id: str) -> dict:
        stats = self._profile_stats(profile_id)
        model = self._build_model(stats)
        model["stats"] = {k: stats[k] for k in (
            "hands","vpip","pfr","three_bet","three_bet_opportunities","fold_to_3bet",
            "fold_to_3bet_opportunities","postflop_aggression","avg_ev_loss_bb","decisions_reviewed","win_rate_hands"
        )}
        with self._lock, self._connect() as con:
            con.execute(
                """INSERT INTO player_models(profile_id,hands_seen,model_json,updated_at) VALUES(?,?,?,?)
                   ON CONFLICT(profile_id) DO UPDATE SET hands_seen=excluded.hands_seen,model_json=excluded.model_json,updated_at=excluded.updated_at""",
                (profile_id, stats["hands"], json.dumps(model, ensure_ascii=False), self._now()),
            )
        return model

    def get_profile_model(self, profile_id: str | None = None) -> dict:
        profile_id = profile_id or self.active_profile_id()
        with self._lock, self._connect() as con:
            row = con.execute("SELECT model_json FROM player_models WHERE profile_id=?", (profile_id,)).fetchone()
        if not row:
            return self.refresh_profile_model(profile_id)
        try:
            model = json.loads(row["model_json"] or "{}")
            return model if "stats" in model else self.refresh_profile_model(profile_id)
        except json.JSONDecodeError:
            return self.refresh_profile_model(profile_id)

    def profile(self, profile_id: str | None = None) -> dict:
        profile_id = profile_id or self.active_profile_id()
        rec = self.get_profile_record(profile_id)
        model = self.get_profile_model(profile_id)
        snap = model.get("stats", {})
        stats = {"id": rec["id"], "name": rec["name"], "hero_balance": rec["balance"], "balance": rec["balance"], **snap}
        for key, default in {
            "hands":0,"vpip":0.0,"pfr":0.0,"three_bet":0.0,"three_bet_opportunities":0,"fold_to_3bet":0.0,
            "fold_to_3bet_opportunities":0,"postflop_aggression":0.0,"avg_ev_loss_bb":0.0,"decisions_reviewed":0,"win_rate_hands":0.0
        }.items(): stats.setdefault(key, default)
        stats["model"] = model
        stats["active"] = profile_id == self.active_profile_id()
        stats["active_players"] = len(self.active_seats())
        return stats

    def bot_opponent_model(self, profile_id: str | None = None) -> dict:
        rec = self.get_profile_record(profile_id)
        model = self.get_profile_model(rec["id"])
        snap = model.get("stats", {})
        return {
            "profile_id": rec["id"], "name": rec["name"], "hands": int(snap.get("hands",0)),
            "vpip": float(snap.get("vpip",0)), "pfr": float(snap.get("pfr",0)), "three_bet": float(snap.get("three_bet",0)),
            "fold_to_3bet": float(snap.get("fold_to_3bet",0)), "postflop_aggression": float(snap.get("postflop_aggression",0)),
            "confidence": float(model.get("confidence",0)), "traits": model.get("traits",[]), "exploit": model.get("exploit",{}),
        }

    def recent_hands(self, limit: int = 20, profile_id: str | None = None) -> list[dict]:
        profile_id = profile_id or self.active_profile_id(); limit = max(1,min(int(limit),100))
        with self._lock, self._connect() as con:
            rows = con.execute(
                """SELECT DISTINCT h.hand_id,h.completed_at,h.button,h.winners_json,h.result_text
                   FROM hands7 h JOIN hand_players7 hp ON hp.hand_id=h.hand_id
                   WHERE h.terminal=1 AND hp.profile_id=? ORDER BY h.completed_at DESC LIMIT ?""",
                (profile_id,limit),
            ).fetchall()
        out=[]
        for r in rows:
            x=dict(r)
            x["winners"] = json.loads(x.pop("winners_json") or "[]")
            x["winner"] = x["winners"][0] if len(x["winners"]) == 1 else ("tie" if x["winners"] else None)
            out.append(x)
        return out

    def training_samples(self, profile_id: str | None = None, limit: int = 500) -> list[dict]:
        profile_id = profile_id or self.active_profile_id(); limit=max(1,min(int(limit),5000))
        with self._lock, self._connect() as con:
            rows = con.execute(
                """SELECT a.hand_id,a.seq,a.player_id,a.street,a.action,a.amount,a.pot_before,a.pot_after,
                          a.to_call_before,a.live_players_before,a.position,h.board_json,h.completed_at
                   FROM actions7 a JOIN hands7 h ON h.hand_id=a.hand_id
                   WHERE a.profile_id=? AND h.terminal=1 ORDER BY h.completed_at DESC,a.seq DESC LIMIT ?""",
                (profile_id,limit),
            ).fetchall()
        out=[]
        for r in rows:
            x=dict(r)
            try: x["board"]=json.loads(x.pop("board_json") or "[]")
            except json.JSONDecodeError: x["board"]=[]
            out.append(x)
        return out
