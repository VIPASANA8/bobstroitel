from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict, dataclass, replace

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.bot_names import BOT_NAMES
from online.schema import poker_tables, system_players, table_seats


DEFAULT_TABLES = (
    ("micro-a", "Micro A", 50, 100),
    ("micro-b", "Micro B", 50, 100),
    ("low-a", "Low A", 100, 200),
    ("low-b", "Low B", 100, 200),
    ("mid-a", "Mid A", 500, 1000),
    ("mid-b", "Mid B", 500, 1000),
)

CASH_MOCK_TABLE = {
    "id": "cash-micro-test",
    "name": "CASH Micro",
    # Compatibility chip counts for the current table client. Money remains
    # authoritative only in the exact *_micros columns below.
    "small_blind_units": 5,
    "big_blind_units": 10,
    # 0.05 / 0.10 USDT. The blinds are set by the deposit floor, not the other
    # way round: CASE8 will not take less than 20 USDT, and at 0.01/0.02 that
    # first deposit was twenty-five maximum buy-ins -- a bankroll nobody spends
    # and therefore nobody tops up. At 0.05/0.10 it is two to five buy-ins.
    "small_blind_micros": 50_000,
    "big_blind_micros": 100_000,
    # Unchanged at 0.01 USDT, but now a tenth of the big blind instead of half
    # of it. That is what makes a percentage rake expressible at all: at the
    # old size the smallest possible cut was 50% of a big blind.
    "chip_micros": 10_000,
    "rake_bps": 1_000,
}

PLAY = "PLAY"
CASH_USDT = "CASH_USDT"
TABLE_ASSETS = {PLAY, CASH_USDT}


#: How many bots a lobby table shows while nobody is sitting at it. Everything
#: not named here uses the usual four.
#:
#: Low B keeps five, so there is always one open seat visible -- a table you
#: can join on sight. Mid B keeps six, a full game to watch; a person joining
#: that one queues and takes a bot's seat at the next hand boundary, which
#: _choose_seat already does whenever more than the minimum three are sitting.
#: Both drop back to the normal count as soon as people arrive.
# One count per table, 1 through 6, so every seat count is reachable for
# testing without editing anything: the layouts, the ready gate and the
# spectator hexagon all behave differently at each, and only two of the six
# were exercised before.
IDLE_BOT_COUNTS = {
    "micro-a": 1,
    "micro-b": 2,
    "low-a": 3,
    "low-b": 4,
    "mid-a": 5,
    "mid-b": 6,
}


# What a player may pick when opening a room. Free-form blinds would let anyone
# create a table nobody can afford to sit at, so the choice is the same three
# levels the built-in tables already use.
ROOM_BLIND_LEVELS = {
    "micro": (50, 100),
    "low": (100, 200),
    "mid": (500, 1000),
}
# A CASH room opens at the pilot's own money parameters and nothing else: the
# escrow, rake and chip size are proved against exactly one set of blinds, so a
# player-made table is that table under a different name.
CASH_ROOM_LEVEL = "cash-micro"
ROOM_NAME_MAX = 40
# Seat count is not a room setting: every seat layout is drawn for six.
ROOM_SEATS = 6
ROOM_PASSWORD_MIN = 4
ROOM_PASSWORD_MAX = 32


def hash_room_password(table_id: str, password: str) -> str:
    """Salted with the room's own id -- unique per room, so the same password
    reused across two rooms does not hash the same way, without needing a
    separate salt column. Low-stakes on purpose: this gates a virtual-chips
    practice room, not a real account, so sha256 (already this codebase's
    pattern for secrets -- see online/auth.py) is enough."""
    return hashlib.sha256(f"{table_id}:{password}".encode()).hexdigest()



class RoomError(ValueError):
    pass


class RoomLimitReached(RoomError):
    """Carries the room already open, so the caller can offer to go there."""

    def __init__(self, message: str, table_id: str) -> None:
        super().__init__(message)
        self.table_id = table_id


@dataclass(frozen=True)
class TableSummary:
    id: str
    name: str
    scope: str
    asset: str
    small_blind_units: int
    big_blind_units: int
    min_buy_in_units: int
    max_buy_in_units: int
    max_seats: int
    occupied_count: int
    human_count: int
    system_count: int
    human_join_available: bool
    visibility: str = "public"
    created_by: str | None = None
    join_mode: str = "buy_in"
    # Never the hash itself -- just enough for the lobby to show a lock icon
    # and the table page to know it needs to ask.
    has_password: bool = False
    small_blind_micros: int | None = None
    big_blind_micros: int | None = None
    chip_micros: int | None = None
    min_buy_in_micros: int | None = None
    max_buy_in_micros: int | None = None

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


class Catalogue:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def seed_defaults(self) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                existing_tables = set(
                    (
                        await session.execute(
                            select(poker_tables.c.id).where(poker_tables.c.scope == "network")
                        )
                    ).scalars()
                )
                for table_id, name, small_blind, big_blind in DEFAULT_TABLES:
                    if table_id in existing_tables:
                        continue
                    await session.execute(poker_tables.insert().values(
                        id=table_id,
                        scope="network",
                        asset=PLAY,
                        name=name,
                        small_blind_units=small_blind,
                        big_blind_units=big_blind,
                        min_buy_in_bb=40,
                        max_buy_in_bb=100,
                        max_seats=6,
                    ))

                existing_players = set(
                    (
                        await session.execute(select(system_players.c.id))
                    ).scalars()
                )
                difficulties = ("easy", "normal", "hard", "maximum")
                for number in range(1, 37):
                    player_id = f"system-{number:02d}"
                    if player_id in existing_players:
                        continue
                    await session.execute(system_players.insert().values(
                        id=player_id,
                        name=BOT_NAMES[(number - 1) % len(BOT_NAMES)],
                        difficulty=difficulties[(number - 1) % len(difficulties)],
                        active=True,
                    ))
                # Rows seeded before the names existed still read "Room Player
                # 19", which gives the game away at a glance -- no amount of
                # work on how a bot plays survives its name tag. Renaming in
                # place keeps the id, so every persona and every hand of
                # history stays attached to the same player.
                for player_id, name in (
                    await session.execute(
                        select(system_players.c.id, system_players.c.name)
                        .where(system_players.c.name.like("Room Player%"))
                    )
                ).all():
                    index = int(player_id.rsplit("-", 1)[-1]) - 1 if player_id.rsplit("-", 1)[-1].isdigit() else 0
                    await session.execute(
                        system_players.update()
                        .where(system_players.c.id == player_id)
                        .values(name=BOT_NAMES[index % len(BOT_NAMES)])
                    )

    async def seed_cash_mock(self) -> None:
        """Create the one human-only table used by the isolated mock pilot."""
        async with self.session_factory() as session:
            async with session.begin():
                existing = (await session.execute(select(poker_tables).where(
                    poker_tables.c.id == CASH_MOCK_TABLE["id"]
                ))).mappings().one_or_none()
                if existing:
                    expected = {
                        key: value for key, value in CASH_MOCK_TABLE.items() if key != "name"
                    }
                    expected["asset"] = CASH_USDT
                    if any(existing[key] != value for key, value in expected.items()):
                        raise RuntimeError("existing mock CASH table has incompatible parameters")
                    # The name is a label, not a money parameter. Refusing to
                    # boot over a renamed table would make renaming it a
                    # migration; adopting the new name costs nothing, and the
                    # blinds, chip and rake above are still checked exactly.
                    if existing["name"] != CASH_MOCK_TABLE["name"]:
                        await session.execute(update(poker_tables).where(
                            poker_tables.c.id == CASH_MOCK_TABLE["id"]
                        ).values(name=CASH_MOCK_TABLE["name"]))
                    return
                await session.execute(poker_tables.insert().values(
                    **CASH_MOCK_TABLE,
                    scope="network", asset=CASH_USDT,
                    min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
                ))

    async def list_tables(
        self, page: int = 1, per_page: int = 6, viewer_id: str | None = None,
        asset: str = PLAY,
    ) -> list[TableSummary]:
        """Open tables. With a viewer, only what that viewer may see.

        Without one the caller is the coordinator, which has to advance every
        open table regardless of who may look at it. A link-only room stays
        reachable by its URL either way -- visibility governs the listing, not
        the door.
        """
        if asset not in TABLE_ASSETS:
            raise ValueError("unknown table asset")
        page = max(1, page)
        per_page = max(1, min(per_page, 100))
        conditions = [
            poker_tables.c.scope == "network", poker_tables.c.status == "open",
            poker_tables.c.asset == asset,
        ]
        if viewer_id is not None:
            conditions.append(
                (poker_tables.c.visibility == "public")
                | (poker_tables.c.created_by == viewer_id)
            )
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(poker_tables)
                    .where(*conditions)
                    .order_by(poker_tables.c.big_blind_units, poker_tables.c.id)
                    .offset((page - 1) * per_page)
                    .limit(per_page)
                )
            ).mappings().all()
            return [await self._summary(session, row) for row in rows]

    async def quick_play(
        self, user_id: str, available_units: int, *, asset: str = PLAY,
    ) -> TableSummary:
        # Public and password-free only: quick play is for finding a game, not
        # for wandering into a room somebody opened for their own friends.
        rows = [
            row for row in await self.list_tables(page=1, per_page=100, asset=asset)
            if row.visibility == "public" and not row.has_password
        ]
        affordable = [
            row for row in rows
            if (
                row.min_buy_in_micros if asset == CASH_USDT
                else row.min_buy_in_units
            ) <= available_units
        ]
        if not affordable:
            raise LookupError("no affordable table")
        chosen = min(
            affordable,
            key=lambda row: (
                not row.human_join_available,
                row.big_blind_micros if asset == CASH_USDT else row.big_blind_units,
                -row.occupied_count,
                row.id,
            ),
        )
        return replace(chosen, join_mode="buy_in" if chosen.human_join_available else "queue")

    async def create_room(
        self, user_id: str, name: str, level: str, password: str | None = None,
        asset: str = PLAY,
    ) -> TableSummary:
        """Open a room for a player. One at a time, so the lobby cannot be flooded.

        Always listed publicly now -- a password gates the seat instead of a
        secret URL gating the listing (see hash_room_password's docstring for
        why the old link-only rooms did not actually protect anything).
        """
        if asset not in TABLE_ASSETS:
            raise RoomError("unknown table asset")
        if level not in (ROOM_BLIND_LEVELS if asset == PLAY else {CASH_ROOM_LEVEL: None}):
            raise RoomError("unknown blind level")
        name = re.sub(r"\s+", " ", str(name or "")).strip()
        if not name:
            raise RoomError("room needs a name")
        if len(name) > ROOM_NAME_MAX:
            raise RoomError(f"name is longer than {ROOM_NAME_MAX} characters")
        password = (password or "").strip() or None
        if password is not None and not (ROOM_PASSWORD_MIN <= len(password) <= ROOM_PASSWORD_MAX):
            raise RoomError(f"password must be {ROOM_PASSWORD_MIN}-{ROOM_PASSWORD_MAX} characters")

        if asset == CASH_USDT:
            # Everything but the identity: same blinds, same chip, same rake as
            # the seeded mock table.
            money = {key: value for key, value in CASH_MOCK_TABLE.items() if key not in ("id", "name")}
        else:
            small_blind, big_blind = ROOM_BLIND_LEVELS[level]
            money = {"small_blind_units": small_blind, "big_blind_units": big_blind}
        async with self.session_factory() as session:
            async with session.begin():
                existing = (
                    await session.execute(
                        select(poker_tables.c.id).where(
                            poker_tables.c.created_by == user_id,
                            poker_tables.c.status == "open",
                            poker_tables.c.asset == asset,
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    raise RoomLimitReached("player already has an open room", table_id=existing)
                table_id = f"room-{uuid.uuid4().hex[:10]}"
                await session.execute(poker_tables.insert().values(
                    id=table_id,
                    scope="network",
                    asset=asset,
                    name=name,
                    **money,
                    min_buy_in_bb=40,
                    max_buy_in_bb=100,
                    max_seats=ROOM_SEATS,
                    created_by=user_id,
                    visibility="public",
                    password_hash=hash_room_password(table_id, password) if password else None,
                ))
            row = (
                await session.execute(select(poker_tables).where(poker_tables.c.id == table_id))
            ).mappings().one()
            return await self._summary(session, row)

    async def own_room(self, user_id: str, asset: str = PLAY) -> TableSummary | None:
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    select(poker_tables).where(
                        poker_tables.c.created_by == user_id,
                        poker_tables.c.status == "open",
                        poker_tables.c.asset == asset,
                    )
                )
            ).mappings().first()
            return await self._summary(session, row) if row else None

    async def close_room(self, table_id: str, user_id: str | None = None) -> None:
        """Retire a room. Callers must empty its seats first.

        Closed only hides it: the row stays, because finished hands reference it
        and deleting the table would take their history with it.
        """
        async with self.session_factory() as session:
            async with session.begin():
                row = (
                    await session.execute(select(poker_tables).where(poker_tables.c.id == table_id))
                ).mappings().first()
                if row is None or row["created_by"] is None:
                    raise RoomError("not a player room")
                if user_id is not None and row["created_by"] != user_id:
                    raise RoomError("not your room")
                if row["asset"] != PLAY and (
                    await session.execute(select(table_seats.c.id).where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.state != "empty",
                    ))
                ).first():
                    # A closed table stops being advanced and the PLAY leave
                    # pipeline cannot move cash escrow, so anyone still seated
                    # would be locked out of their own stack.
                    raise RoomError("cash room still has players")
                await session.execute(
                    update(poker_tables).where(poker_tables.c.id == table_id).values(status="closed")
                )

    async def idle_room_ids(self) -> list[tuple[str, str]]:
        """Open player rooms with nobody human in them right now, as
        (table_id, asset) -- retiring a CASH room takes a different path to a
        PLAY one, and the caller cannot tell them apart from the id."""
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(poker_tables.c.id, poker_tables.c.asset).where(
                        poker_tables.c.status == "open",
                        poker_tables.c.created_by.is_not(None),
                    )
                )
            ).all()
            if not rows:
                return []
            busy = set(
                (
                    await session.execute(
                        select(table_seats.c.table_id).where(
                            table_seats.c.table_id.in_([row[0] for row in rows]),
                            table_seats.c.occupant_kind == "user",
                            table_seats.c.state.in_(("seated", "held", "leaving")),
                        )
                    )
                ).scalars()
            )
        return [(table_id, asset) for table_id, asset in rows if table_id not in busy]

    async def _summary(self, session: AsyncSession, row) -> TableSummary:
        seats = (
            await session.execute(
                select(table_seats.c.occupant_kind, table_seats.c.state)
                .where(table_seats.c.table_id == row["id"])
            )
        ).all()
        active = [seat for seat in seats if seat.state != "empty" and seat.occupant_kind != "empty"]
        human_count = sum(seat.occupant_kind == "user" for seat in active)
        system_count = sum(seat.occupant_kind == "system" for seat in active)
        occupied_count = len(active)
        min_cash = (
            row["big_blind_micros"] * row["min_buy_in_bb"]
            if row["asset"] == CASH_USDT and row["big_blind_micros"] is not None else None
        )
        max_cash = (
            row["big_blind_micros"] * row["max_buy_in_bb"]
            if row["asset"] == CASH_USDT and row["big_blind_micros"] is not None else None
        )
        return TableSummary(
            id=row["id"],
            name=row["name"],
            scope=row["scope"],
            asset=row["asset"],
            small_blind_units=row["small_blind_units"],
            big_blind_units=row["big_blind_units"],
            min_buy_in_units=row["big_blind_units"] * row["min_buy_in_bb"],
            max_buy_in_units=row["big_blind_units"] * row["max_buy_in_bb"],
            max_seats=row["max_seats"],
            occupied_count=occupied_count,
            human_count=human_count,
            system_count=system_count,
            visibility=row["visibility"],
            created_by=row["created_by"],
            human_join_available=occupied_count < row["max_seats"] or system_count > 0,
            has_password=bool(row["password_hash"]),
            small_blind_micros=row["small_blind_micros"],
            big_blind_micros=row["big_blind_micros"],
            chip_micros=row["chip_micros"],
            min_buy_in_micros=min_cash,
            max_buy_in_micros=max_cash,
        )
