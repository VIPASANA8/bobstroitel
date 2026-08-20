from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.ledger import PlayLedger
from online.schema import play_accounts, poker_tables, seat_queue, system_players, table_runtimes, table_seats


# A ready request has to survive the hand that is running when it is made,
# otherwise it expires before the boundary that would seat the player.
READY_TTL = timedelta(minutes=3)
HOLD_WINDOW = timedelta(seconds=30)
MIN_SYSTEM_BOTS = 3
MAX_SYSTEM_BOTS = 4
# How long a bot stays at one table before it gets up and a fresh one sits down.
# A band, not a fixed ten minutes: a single interval would rotate the whole
# table at once, which reads as scripted rather than as people coming and going.
BOT_ROTATE_BAND = (timedelta(minutes=7), timedelta(minutes=13))


class SeatingError(ValueError):
    pass


class InsufficientFunds(SeatingError):
    """Carries both numbers so the client can say how far short the player is."""

    def __init__(self, message: str, required_units: int, available_units: int) -> None:
        super().__init__(message)
        self.required_units = required_units
        self.available_units = available_units


class AlreadySeated(SeatingError):
    """Carries the blocking seat so the caller can send the player to it."""

    def __init__(self, message: str, table_id: str, seat_state: str) -> None:
        super().__init__(message)
        self.table_id = table_id
        self.seat_state = seat_state


@dataclass(frozen=True)
class SeatingRequest:
    id: str
    table_id: str
    user_id: str
    seat_no: int
    requested_buy_in_units: int
    state: str
    position_seq: int


@dataclass(frozen=True)
class BoundaryResult:
    seated_user_ids: list[str]
    removed_system_player_ids: list[str]


class SeatingService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], ledger: PlayLedger
    ) -> None:
        self.session_factory = session_factory
        self.ledger = ledger
        # When each seated bot is due to leave. In memory on purpose: a restart
        # just re-rolls the timers, and rotation has nothing to recover.
        self._bot_rotate_at: dict[str, datetime] = {}

    async def ready(self, user_id: str, table_id: str, seat_no: int, buy_in_units: int) -> SeatingRequest:
        async with self.session_factory() as session:
            async with session.begin():
                now = datetime.now(timezone.utc)
                table = await self._table(session, table_id)
                if not 0 <= seat_no <= 5:
                    raise SeatingError("seat_no must be between 0 and 5")
                minimum = table["big_blind_units"] * table["min_buy_in_bb"]
                maximum = table["big_blind_units"] * table["max_buy_in_bb"]
                if not minimum <= buy_in_units <= maximum:
                    raise SeatingError(
                        f"buy-in must be between {table['min_buy_in_bb']} and {table['max_buy_in_bb']} BB"
                    )
                # Checked here, not only at the boundary. The boundary cancels an
                # unaffordable request silently and moves on, so the player saw
                # their request accepted and then vanish a few seconds later with
                # no reason given. Refusing up front makes it immediate and says
                # why; the boundary keeps its own check for a balance that drops
                # between the request and the seating.
                available = await self.ledger.available_units(user_id, session=session)
                if available < buy_in_units:
                    raise InsufficientFunds(
                        "not enough chips for this buy-in",
                        required_units=buy_in_units,
                        available_units=available,
                    )
                occupied = (
                    await session.execute(
                        select(table_seats.c.table_id, table_seats.c.state).where(
                            table_seats.c.user_id == user_id,
                            table_seats.c.state.in_(("seated", "held", "leaving")),
                        )
                    )
                ).mappings().first()
                if occupied:
                    raise AlreadySeated(
                        "user already has a network seat",
                        table_id=occupied["table_id"],
                        seat_state=occupied["state"],
                    )
                # One row per (table, user) exists at most, whatever its state:
                # a previous "seated" row must be reused, not inserted over.
                existing = (
                    await session.execute(
                        select(seat_queue).where(
                            seat_queue.c.table_id == table_id,
                            seat_queue.c.user_id == user_id,
                        )
                    )
                ).mappings().first()
                if existing:
                    if existing["state"] == "waiting" and (
                        existing["expires_at"] is None or existing["expires_at"] > now
                    ):
                        return self._request(existing)
                position = (
                    await session.execute(
                        select(seat_queue.c.position_seq)
                        .where(seat_queue.c.table_id == table_id)
                        .order_by(seat_queue.c.position_seq.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                request = {
                    "id": uuid.uuid4().hex,
                    "table_id": table_id,
                    "user_id": user_id,
                    "requested_buy_in_units": buy_in_units,
                    "state": "waiting",
                    "position_seq": int(position or 0) + 1,
                    "seat_no": seat_no,
                }
                values = {
                    "table_id": table_id,
                    "user_id": user_id,
                    "seat_no": seat_no,
                    "requested_buy_in_units": buy_in_units,
                    "state": "waiting",
                    "position_seq": request["position_seq"],
                    "expires_at": now + READY_TTL,
                }
                if existing:
                    await session.execute(update(seat_queue).where(seat_queue.c.id == existing["id"]).values(**values))
                    request["id"] = existing["id"]
                else:
                    await session.execute(seat_queue.insert().values(id=request["id"], **values))
                return SeatingRequest(**request)

    async def cancel_ready(self, user_id: str, table_id: str) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(seat_queue)
                    .where(
                        seat_queue.c.table_id == table_id,
                        seat_queue.c.user_id == user_id,
                        seat_queue.c.state == "waiting",
                    )
                    .values(state="cancelled")
                )

    async def process_boundary(self, table_id: str, now: datetime | None = None) -> BoundaryResult:
        now = now or datetime.now(timezone.utc)
        async with self.session_factory() as session:
            async with session.begin():
                table = await self._table(session, table_id, lock=True)
                await session.execute(
                    update(seat_queue)
                    .where(
                        seat_queue.c.table_id == table_id,
                        seat_queue.c.state == "waiting",
                        seat_queue.c.expires_at.is_not(None),
                        seat_queue.c.expires_at <= now,
                    )
                    .values(state="expired")
                )
                await session.execute(
                    update(table_seats)
                    .where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.state == "held",
                        table_seats.c.hold_until <= now,
                    )
                    .values(state="leaving")
                )
                await session.execute(
                    update(table_seats)
                    .where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.occupant_kind == "system",
                        table_seats.c.state == "seated",
                        table_seats.c.stack_units < table["big_blind_units"],
                    )
                    .values(state="leaving")
                )
                await session.execute(
                    update(table_seats)
                    .where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.occupant_kind == "user",
                        table_seats.c.state.in_(("seated", "held")),
                        table_seats.c.stack_units < table["big_blind_units"],
                    )
                    .values(state="leaving")
                )
                await self._rotate_stale_bots(session, table_id, now)
                await self._process_leaving(session, table_id)
                requests = (
                    await session.execute(
                        select(seat_queue)
                        .where(seat_queue.c.table_id == table_id, seat_queue.c.state == "waiting")
                        .order_by(seat_queue.c.position_seq)
                        .with_for_update()
                    )
                ).mappings().all()
                seated: list[str] = []
                removed: list[str] = []
                for request in requests:
                    if await self.ledger.available_units(request["user_id"], session=session) < request["requested_buy_in_units"]:
                        await session.execute(
                            update(seat_queue).where(seat_queue.c.id == request["id"]).values(state="cancelled")
                        )
                        continue
                    seat = await self._choose_seat(session, table_id, request["seat_no"])
                    if seat is None:
                        continue
                    if seat["occupant_kind"] == "system":
                        await self.ledger.release_system_seat(
                            seat["system_player_id"], table_id,
                            f"release:{request['id']}:{request['position_seq']}",
                            session=session,
                        )
                        removed.append(seat["system_player_id"])
                        await self._clear_seat(session, seat["id"])
                    await self.ledger.reserve_buy_in(
                        request["user_id"], table_id, request["requested_buy_in_units"],
                        f"buyin:{request['id']}:{request['position_seq']}", session=session,
                    )
                    escrow_id = await self._escrow_id(session, table_id)
                    if seat["id"] is None:
                        await session.execute(table_seats.insert().values(
                            id=uuid.uuid4().hex,
                            table_id=table_id,
                            seat_no=seat["seat_no"],
                            occupant_kind="user",
                            user_id=request["user_id"],
                            escrow_account_id=escrow_id,
                            stack_units=request["requested_buy_in_units"],
                            state="seated",
                        ))
                    else:
                        await session.execute(
                            update(table_seats).where(table_seats.c.id == seat["id"]).values(
                                occupant_kind="user",
                                user_id=request["user_id"],
                                system_player_id=None,
                                escrow_account_id=escrow_id,
                                stack_units=request["requested_buy_in_units"],
                                state="seated",
                                disconnected_at=None,
                                hold_until=None,
                            )
                        )
                    await session.execute(
                        update(seat_queue).where(seat_queue.c.id == request["id"]).values(state="seated")
                    )
                    seated.append(request["user_id"])
                removed.extend(await self._fill_system_seats(session, table))
                await self._cap_system_stacks(session, table)
                return BoundaryResult(seated, removed)

    async def active_seat_count(self, table_id: str) -> int:
        async with self.session_factory() as session:
            return len((await session.execute(
                select(table_seats.c.id).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.state == "seated",
                    table_seats.c.occupant_kind.in_(("user", "system")),
                )
            )).scalars().all())

    async def seated_human_seat_numbers(self, table_id: str) -> set[int]:
        """Bots are implicitly ready -- only human seats gate a new hand."""
        async with self.session_factory() as session:
            rows = await session.execute(
                select(table_seats.c.seat_no).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.state == "seated",
                    table_seats.c.occupant_kind == "user",
                )
            )
            return {row[0] for row in rows}

    async def seated_bot_seat_numbers(self, table_id: str) -> set[int]:
        """Bots gate a hand too now -- they mark themselves ready on their own
        uneven beat so the table doesn't snap to six checkmarks at once."""
        async with self.session_factory() as session:
            rows = await session.execute(
                select(table_seats.c.seat_no).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.state == "seated",
                    table_seats.c.occupant_kind == "system",
                )
            )
            return {row[0] for row in rows}

    async def user_seat_number(self, user_id: str, table_id: str) -> int | None:
        async with self.session_factory() as session:
            return await session.scalar(
                select(table_seats.c.seat_no).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.user_id == user_id,
                    table_seats.c.state == "seated",
                )
            )

    async def mark_disconnected(self, user_id: str, table_id: str, now: datetime) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(table_seats)
                    .where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.user_id == user_id,
                        table_seats.c.state == "seated",
                    )
                    .values(state="held", disconnected_at=now, hold_until=now + HOLD_WINDOW)
                )

    async def hold_all_users(self, now: datetime) -> None:
        """No socket survives a restart, so hold every occupied seat: players
        who are still there reconnect, the rest are released at the boundary."""
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(table_seats)
                    .where(table_seats.c.occupant_kind == "user", table_seats.c.state == "seated")
                    .values(state="held", disconnected_at=now, hold_until=now + HOLD_WINDOW)
                )

    async def reconnect(self, user_id: str, table_id: str) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(table_seats)
                    .where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.user_id == user_id,
                        table_seats.c.state == "held",
                    )
                    .values(state="seated", disconnected_at=None, hold_until=None)
                )

    async def request_leave(self, user_id: str, table_id: str) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(table_seats)
                    .where(table_seats.c.table_id == table_id, table_seats.c.user_id == user_id)
                    .values(state="leaving")
                )

    async def add_on(self, user_id: str, table_id: str, amount_units: int, request_id: str) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                table = await self._table(session, table_id, lock=True)
                runtime_phase = (
                    await session.execute(
                        select(table_runtimes.c.phase).where(table_runtimes.c.table_id == table_id)
                    )
                ).scalar_one_or_none()
                if runtime_phase == "active":
                    raise SeatingError("add-on is unavailable during an active hand")
                seat = await self._user_seat(session, user_id, table_id)
                if not seat:
                    raise SeatingError("user is not seated")
                maximum = table["big_blind_units"] * table["max_buy_in_bb"]
                if seat["stack_units"] + amount_units > maximum:
                    raise SeatingError("stack cannot exceed 100 BB")
                # Keyed on the caller's own request id, which the client already
                # sends fresh per add-on. The previous key was static for a
                # (user, table, seat row) -- and seat rows are reused -- so every
                # add-on after the first was taken for a repeat of it and moved no
                # money, while the stack below is added to unconditionally. That
                # mints chips: the seat grows and nothing leaves the wallet.
                key = f"addon:{user_id}:{table_id}:{request_id}"
                # And a genuine retry of one request must change nothing at all.
                # The ledger call alone would quietly no-op while the stack below
                # still grew, which is the same minting by a different route.
                if await self.ledger.transaction_exists(key, session=session):
                    return
                await self.ledger.add_on(user_id, table_id, amount_units, key, session=session)
                await session.execute(
                    update(table_seats).where(table_seats.c.id == seat["id"]).values(stack_units=seat["stack_units"] + amount_units)
                )

    async def evict_table(self, table_id: str) -> None:
        """Empty a table completely, returning every stack and escrow.

        Used when a room is retired. A closed table stops being advanced, so
        anyone still seated would keep their chips locked in its escrow forever
        -- the leave pipeline is what puts them back where they belong.
        """
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(table_seats)
                    .where(table_seats.c.table_id == table_id, table_seats.c.state != "empty")
                    .values(state="leaving")
                )
                await self._process_leaving(session, table_id)

    async def _process_leaving(self, session: AsyncSession, table_id: str) -> None:
        rows = (
            await session.execute(
                select(table_seats).where(table_seats.c.table_id == table_id, table_seats.c.state == "leaving")
            )
        ).mappings().all()
        for row in rows:
            if row["occupant_kind"] == "user" and row["user_id"]:
                await self.ledger.return_stack(
                    # Unique per departure. Seat rows are reused -- _clear_seat
                    # blanks a row rather than deleting it -- so the same player
                    # leaving the same seat a second time repeated this key, the
                    # ledger took it for the first return already posted, and
                    # their stack stayed in the table escrow instead of going
                    # back to their wallet. This is player money, not the
                    # faucet's: 59 buy-ins against 16 returns.
                    row["user_id"], table_id,
                    f"return:{row['id']}:{row['user_id']}:{uuid.uuid4().hex}",
                    amount_units=row["stack_units"], session=session
                )
            elif row["occupant_kind"] == "system" and row["system_player_id"]:
                await self.ledger.release_system_seat(
                    row["system_player_id"], table_id,
                    # Unique per release, like the funding grant above it. Seat rows
                    # are reused -- _clear_seat blanks a row rather than deleting it --
                    # so a key built from the row id repeated on every later release of
                    # the same seat, and the ledger treated it as the first one already
                    # posted: the escrow was simply never drained again.
                    f"release:{row['id']}:{row['system_player_id']}:{uuid.uuid4().hex}", session=session,
                )
            await self._clear_seat(session, row["id"])

    async def _rotate_stale_bots(self, session: AsyncSession, table_id: str, now: datetime) -> None:
        """Retire a bot that has sat long enough, so the table keeps turning over.

        Without this a bot only ever leaves by going broke or being rebalanced
        away, so the same names sit at the same table indefinitely. Each gets its
        own moment inside the band, assigned when it is first seen, which is what
        keeps them from all standing up together.

        Marking the seat as leaving is enough: the leave pipeline below returns
        the escrow, clears the seat, and the refill puts somebody new in it.
        """
        rows = (
            await session.execute(
                select(table_seats).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.occupant_kind == "system",
                    table_seats.c.state == "seated",
                )
            )
        ).mappings().all()
        low, high = BOT_ROTATE_BAND
        span = (high - low).total_seconds()
        for row in rows:
            key = f"{row['id']}:{row['system_player_id']}"
            due = self._bot_rotate_at.get(key)
            if due is None:
                self._bot_rotate_at[key] = now + low + timedelta(seconds=random.uniform(0, span))
                continue
            if due > now:
                continue
            self._bot_rotate_at.pop(key, None)
            await session.execute(
                update(table_seats).where(table_seats.c.id == row["id"]).values(state="leaving")
            )

    async def _cap_system_stacks(self, session: AsyncSession, table) -> None:
        """Hold bots to the table's own ceiling, the one people already obey.

        max_buy_in_bb bounds what a person may bring, but nothing bounded a bot:
        it keeps everything it wins and is funded afresh on every seating. On
        production that produced a bot sitting on 1250x the table maximum, at a
        table where a player may bring 100 BB. Winnings above the ceiling go back
        to the faucet they came from, and the seat is trimmed with them, so the
        bot keeps playing at the same size everyone else can match.
        """
        ceiling = int(table["big_blind_units"]) * int(table["max_buy_in_bb"])
        rows = (
            await session.execute(
                select(table_seats).where(
                    table_seats.c.table_id == table["id"],
                    table_seats.c.occupant_kind == "system",
                    table_seats.c.state.in_(("seated", "held", "leaving")),
                    table_seats.c.stack_units > ceiling,
                )
            )
        ).mappings().all()
        for row in rows:
            excess = int(row["stack_units"]) - ceiling
            # Keyed on the stack being trimmed, so a repeat at the same size is
            # the same operation and a later overshoot is a new one.
            await self.ledger.reconcile_system_escrow(
                row["system_player_id"], excess,
                f"cap:{row['system_player_id']}:{row['stack_units']}",
                session=session,
            )
            await session.execute(
                update(table_seats).where(table_seats.c.id == row["id"]).values(stack_units=ceiling)
            )

    async def _fill_system_seats(self, session: AsyncSession, table) -> list[str]:
        """Keep a table at three or four bots when capacity permits.

        Users are seated first at a hand boundary. Only then are idle system
        seats removed or added, so a person is never displaced merely to keep
        a bot count. With four or more users the physical six-seat cap wins.
        """
        rows = (
            await session.execute(
                select(table_seats).where(table_seats.c.table_id == table["id"])
            )
        ).mappings().all()
        active_rows = [row for row in rows if row["state"] != "empty"]
        user_count = sum(1 for row in active_rows if row["occupant_kind"] == "user")
        # Room policy: 1–2 humans play with four bots; 3 humans play with
        # three bots. New people wait once all six seats are occupied, rather
        # than evicting the third bot and turning the table into a human-only room.
        #
        # Nobody there means no bots at all. Bots exist to give a person
        # opponents, and with nought people they had none to give: they dealt
        # to each other around the clock, which is what let one of them pile up
        # a stack in the millions. It also meant a player who opened a room
        # walked into a hand already in progress instead of their own table.
        # Zero bots leaves fewer than two seats filled, so no hand starts.
        target_bot_count = 0 if user_count == 0 else (
            MAX_SYSTEM_BOTS if user_count <= 2 else MIN_SYSTEM_BOTS
        )

        seated_bots = sorted(
            (row for row in active_rows if row["occupant_kind"] == "system" and row["state"] == "seated"),
            key=lambda row: row["seat_no"],
        )
        removed: list[str] = []
        for row in seated_bots[target_bot_count:]:
            system_player_id = row["system_player_id"]
            if system_player_id:
                await self.ledger.release_system_seat(
                    system_player_id, table["id"],
                    f"rebalance:{row['id']}:{uuid.uuid4().hex}", session=session,
                )
                removed.append(system_player_id)
            await self._clear_seat(session, row["id"])

        rows = (
            await session.execute(
                select(table_seats).where(table_seats.c.table_id == table["id"])
            )
        ).mappings().all()
        active_rows = [row for row in rows if row["state"] != "empty"]
        seated_bot_count = sum(
            1 for row in active_rows if row["occupant_kind"] == "system" and row["state"] == "seated"
        )
        needed = max(0, target_bot_count - seated_bot_count)
        if not needed:
            return removed

        occupied_seats = {row["seat_no"] for row in active_rows}
        empty_by_seat = {row["seat_no"]: row for row in rows if row["state"] == "empty"}
        active_system_ids = {
            row["system_player_id"]
            for row in (await session.execute(
                select(table_seats).where(
                    table_seats.c.occupant_kind == "system",
                    table_seats.c.state != "empty",
                )
            )).mappings().all()
            if row["system_player_id"]
        }
        candidates = (
            await session.execute(select(system_players).where(system_players.c.active == True))
        ).mappings().all()
        available = [row for row in candidates if row["id"] not in active_system_ids]
        for seat_no, player in zip((seat for seat in range(table["max_seats"]) if seat not in occupied_seats), available[:needed]):
            amount = table["big_blind_units"] * 100
            seat_id = empty_by_seat.get(seat_no, {}).get("id") or uuid.uuid4().hex
            await self.ledger.fund_system_seat(
                player["id"], table["id"], amount,
                f"system:{table['id']}:{player['id']}:{uuid.uuid4().hex}", session=session,
            )
            escrow_id = await self._escrow_id(session, table["id"])
            values = {
                "occupant_kind": "system",
                "user_id": None,
                "system_player_id": player["id"],
                "escrow_account_id": escrow_id,
                "stack_units": amount,
                "state": "seated",
                "disconnected_at": None,
                "hold_until": None,
            }
            if seat_no in empty_by_seat:
                await session.execute(
                    update(table_seats).where(table_seats.c.id == empty_by_seat[seat_no]["id"]).values(**values)
                )
            else:
                await session.execute(table_seats.insert().values(
                    id=seat_id, table_id=table["id"], seat_no=seat_no, **values,
                ))
        return removed

    async def _choose_seat(self, session: AsyncSession, table_id: str, requested_seat: int):
        rows = (
            await session.execute(select(table_seats).where(table_seats.c.table_id == table_id))
        ).mappings().all()
        by_seat = {row["seat_no"]: row for row in rows}

        def free(seat_no: int):
            row = by_seat.get(seat_no)
            if row is not None and row["state"] != "empty":
                return None
            # Reuse the cleared row when there is one; its seat_no is taken.
            return row or {"seat_no": seat_no, "id": None, "occupant_kind": "empty"}

        seat = free(requested_seat)
        if seat is not None:
            return seat
        # Prefer another genuinely free seat before replacing a bot.
        for seat_no in range(6):
            seat = free(seat_no)
            if seat is not None:
                return seat
        system_rows = sorted(
            (row for row in by_seat.values() if row["occupant_kind"] == "system" and row["state"] == "seated"),
            key=lambda row: row["seat_no"],
        )
        # Preserve at least three bots. A fourth human remains queued until a
        # human leaves, instead of silently reducing the game to two bots.
        if len(system_rows) <= MIN_SYSTEM_BOTS:
            return None
        requested = by_seat.get(requested_seat)
        if requested and requested["occupant_kind"] == "system" and requested["state"] == "seated":
            return requested
        return system_rows[-1]

    async def _table(self, session: AsyncSession, table_id: str, lock: bool = False):
        query = select(poker_tables).where(poker_tables.c.id == table_id)
        if lock:
            query = query.with_for_update()
        row = (await session.execute(query)).mappings().first()
        if row is None:
            raise SeatingError("table not found")
        return row

    async def _user_seat(self, session: AsyncSession, user_id: str, table_id: str):
        return (
            await session.execute(
                select(table_seats).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.user_id == user_id,
                    table_seats.c.state.in_(("seated", "held", "leaving")),
                )
            )
        ).mappings().first()

    async def _escrow_id(self, session: AsyncSession, table_id: str):
        return (
            await session.execute(
                select(play_accounts.c.id).where(
                    play_accounts.c.owner_kind == "table",
                    play_accounts.c.owner_id == table_id,
                    play_accounts.c.account_kind == "escrow",
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def _clear_seat(session: AsyncSession, seat_id: str) -> None:
        seat = (
            await session.execute(select(table_seats).where(table_seats.c.id == seat_id))
        ).mappings().first()
        await session.execute(
            update(table_seats).where(table_seats.c.id == seat_id).values(
                occupant_kind="empty",
                user_id=None,
                system_player_id=None,
                escrow_account_id=None,
                stack_units=0,
                state="empty",
                disconnected_at=None,
                hold_until=None,
            )
        )
        # Releasing the seat without retiring the queue row leaves the user a
        # ghost: no seat row, so the API reports them a spectator, while the
        # queue still claims they sit here. Both halves describe one seat, so
        # they have to be released together.
        if seat and seat["occupant_kind"] == "user" and seat["user_id"]:
            await session.execute(
                update(seat_queue).where(
                    seat_queue.c.table_id == seat["table_id"],
                    seat_queue.c.user_id == seat["user_id"],
                    seat_queue.c.state == "seated",
                ).values(state="cancelled")
            )

    @staticmethod
    def _request(row) -> SeatingRequest:
        return SeatingRequest(
            id=row["id"],
            table_id=row["table_id"],
            user_id=row["user_id"],
            seat_no=row["seat_no"],
            requested_buy_in_units=row["requested_buy_in_units"],
            state=row["state"],
            position_seq=row["position_seq"],
        )
