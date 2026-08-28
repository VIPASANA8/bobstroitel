from __future__ import annotations

import asyncio
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bots.multiway import MultiwayBot
from bots.persona import persona_for
from online.events import append_integrity_event
from online.ledger import PlayLedger
from online.schema import (
    game_commands,
    hand_actions,
    hand_players,
    hands,
    poker_tables,
    system_players,
    table_runtimes,
    table_seats,
    users,
)
from online.serialization import deserialize_state, serialize_state
from poker.engine import InvalidAction, PokerEngine
from poker.models import ActionType, GameState, Street


logger = logging.getLogger(__name__)


class RuntimeErrorBase(RuntimeError):
    pass


class StaleRevision(RuntimeErrorBase):
    def __init__(self, current_revision: int):
        super().__init__(f"stale revision; current revision is {current_revision}")
        self.current_revision = current_revision


class TablePaused(RuntimeErrorBase):
    pass


@dataclass(frozen=True)
class RuntimeActionResult:
    command_id: str
    table_id: str
    revision: int
    action: str
    legal_actions: list[str]
    snapshot: dict[str, Any]


@dataclass
class _LoadedTable:
    revision: int
    phase: str
    state: GameState
    action_deadline: datetime | None = None
    result_clear_at: datetime | None = None
    next_hand_at: datetime | None = None
    # In-memory only: cleared by a restart, same as the rest of this dataclass
    # (restore_all rebuilds it from the DB). A bot with no deadline yet acts
    # on the very next tick, matching today's behavior until it gets one.
    next_bot_action_at: datetime | None = None
    # Who has asked to leave and is still owed a turn in the hand that is
    # running. Folding them the moment the engine reaches them is the whole
    # difference between a few seconds and thirty per remaining street.
    leaving_participants: set[str] = field(default_factory=set)


#: Base think-time band in seconds, before difficulty/street scaling. Mirrors
#: static/app.js's BOT_SPEED_RANGES.normal, ported server-side because the
#: online coordinator (unlike the legacy client-paced table) was giving every
#: bot zero think time -- one coordinator tick (250ms), uniformly.
_BOT_THINK_BAND = (1.0, 2.2)
# Wider and slower than the think band: confirming you want to play the next
# hand is a lazier gesture than acting on a live one, and the spread is what
# keeps six checkmarks from landing together.
_BOT_READY_BAND = (0.9, 6.0)
#: Slots the ready band is divided into -- one per bot a table can hold, so
#: the gap between two checkmarks is never smaller than half a slot.
MAX_READY_SLOTS = 4
#: Missing ready-up sits a human out of just that one hand -- the seat and
#: stack are untouched, and they are asked again next time (_may_start_hand's
#: own docstring). That is deliberately soft: PokerStars gives an AFK player
#: 15 minutes or two full orbits of missed blinds before it acts, nothing
#: close to one 30s window. This is the harder consequence for genuinely not
#: being there, at roughly the same patience -- three hands running is about
#: half an orbit at a six-max table, not one slow response.
AFK_EVICT_STREAK = 3
_BOT_DIFFICULTY_FACTOR = {"easy": 0.84, "normal": 1.0, "hard": 1.12, "maximum": 1.25}
_BOT_STREET_FACTOR = {"preflop": 0.88, "flop": 1.0, "turn": 1.10, "river": 1.22}
# How often a bot stops dead over a spot that did not look hard. People do
# this constantly -- a table where nobody ever hesitates reads as machinery.
# What a table with no hand behind it looks like to a viewer.
EMPTY_SNAPSHOT = {
    "phase": "waiting", "revision": 0, "occupancy": 0,
    "legal_actions": [], "players": {}, "action_deadline": None,
}
_BOT_TANK_RATE = 0.07
# A real tank can run half a minute; at this table that reads as a frozen
# client, and it crowds the 30s deadline a waiting human is held to.
_BOT_THINK_CAP = 12.0


def bot_ready_delay(*, rng: random.Random | None = None) -> float:
    """Seconds a bot waits before marking itself ready for the next hand. Real
    players don't all confirm on the same frame, so each bot gets its own
    uneven beat instead of every checkmark appearing at once."""
    lo, hi = _BOT_READY_BAND
    return (rng or random).uniform(lo, hi)


def bot_think_delay(
    difficulty: str,
    street: str,
    *,
    pressure: float = 0.0,
    patience: float = 1.0,
    rng: random.Random | None = None,
) -> float:
    """Seconds a bot should sit before acting, so the table doesn't beat with
    a uniform 250ms robotic pulse. Pure and clock-free so it's directly
    testable; the caller adds the result to its own notion of "now".

    A person's pause says something about the spot: nothing to call is waved
    through, a bet worth most of the stack gets stared at, and once in a while
    somebody tanks over a decision that looked easy. `pressure` is what is being
    asked for as a share of the pot, and `patience` is the individual bot's own
    tempo -- fast players stay fast across every street.
    """
    lo, hi = _BOT_THINK_BAND
    jitter = (rng or random).uniform(lo, hi)
    difficulty_factor = _BOT_DIFFICULTY_FACTOR.get(difficulty, 1.0)
    street_factor = _BOT_STREET_FACTOR.get(street, 1.0)
    # Free to continue: snap it off. Being asked for the pot: take a while.
    spot_factor = 0.55 + min(1.5, max(0.0, pressure)) * 0.75
    delay = jitter * difficulty_factor * street_factor * spot_factor * max(0.4, patience)
    if (rng or random).random() < _BOT_TANK_RATE:
        delay *= (rng or random).uniform(1.8, 3.2)
    return min(delay, _BOT_THINK_CAP)


class TableRuntimeManager:
    """Authoritative, durable command processor for one or more poker tables."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ledger: PlayLedger,
        engine: PokerEngine | None = None,
        now=None,
    ) -> None:
        self.session_factory = session_factory
        self.ledger = ledger
        self.engine = engine or PokerEngine()
        self.clock = now or (lambda: datetime.now(timezone.utc))
        self._locks: dict[str, asyncio.Lock] = {}
        self._tables: dict[str, _LoadedTable] = {}
        self._action_counts: dict[str, int] = {}
        # Ready-up state lives here rather than on _LoadedTable: a brand new
        # table with no runtime row yet (nobody has ever started a hand on it)
        # still needs to gate its very first hand on readiness, and there's no
        # _LoadedTable to hold it until start_hand has actually run once.
        # In-memory, like the rest of this manager's per-table state -- a
        # restart clears it and players just click ready again.
        self._ready_seats: dict[str, set[int]] = {}
        self._ready_deadline: dict[str, datetime] = {}
        self._hand_starts_at: dict[str, datetime] = {}
        # When each bot seat "decides" to click ready this cycle. Bots used to
        # be implicitly ready, so their checkmarks appeared all at once the
        # instant a table opened -- obviously machines. Cleared with the rest
        # of the ready cycle, so every hand gets a fresh set of beats.
        self._bot_ready_at: dict[str, dict[int, datetime]] = {}
        # Consecutive hands a seated human has missed ready-up for, in a row.
        # Same lifetime as the rest of this manager's state: in-memory, gone
        # on restart, and a restart is a fresh start for this exactly like it
        # is for ready_seats.
        self._afk_streak: dict[str, dict[int, int]] = {}

    def _lock(self, table_id: str) -> asyncio.Lock:
        return self._locks.setdefault(table_id, asyncio.Lock())

    def ready_seats(self, table_id: str) -> set[int]:
        return self._ready_seats.get(table_id, set())

    def ready_deadline(self, table_id: str) -> datetime | None:
        return self._ready_deadline.get(table_id)

    def hand_starts_at(self, table_id: str) -> datetime | None:
        return self._hand_starts_at.get(table_id)

    def arm_ready_deadline(self, table_id: str, when: datetime) -> None:
        self._ready_deadline.setdefault(table_id, when)

    def arm_hand_starts_at(self, table_id: str, when: datetime) -> None:
        self._hand_starts_at.setdefault(table_id, when)

    def clear_ready_cycle(self, table_id: str) -> None:
        self._ready_seats.pop(table_id, None)
        self._ready_deadline.pop(table_id, None)
        self._hand_starts_at.pop(table_id, None)
        self._bot_ready_at.pop(table_id, None)

    def record_ready_outcome(self, table_id: str, human_seats: set[int], sit_out: set[int]) -> set[int]:
        """Bumps each human seat's consecutive-miss count and resets it for
        anyone who was ready this time. Returns the seats that just reached
        AFK_EVICT_STREAK -- call only once a hand is actually about to start,
        the one moment `sit_out` means something (see _may_start_hand).
        """
        streak = self._afk_streak.setdefault(table_id, {})
        for seat_no in list(streak):
            if seat_no not in human_seats:
                streak.pop(seat_no, None)  # stood up or already evicted
        evict = set()
        for seat_no in human_seats:
            if seat_no in sit_out:
                streak[seat_no] = streak.get(seat_no, 0) + 1
                if streak[seat_no] >= AFK_EVICT_STREAK:
                    evict.add(seat_no)
            else:
                streak.pop(seat_no, None)
        return evict

    def schedule_bot_ready(self, table_id: str, seat_nos: set[int], now: datetime) -> None:
        """Give each bot seat its own moment to click ready.

        A slot each, taken in turn, with jitter that cannot reach the next one.
        Independent draws from the band were what this used to do, and four of
        them across four seconds collide: measured on the live site, the last
        two checkmarks landed in the same frame on every single cycle. Only
        seats without a slot yet are assigned one, so a bot's beat stays put
        across ticks and a bot that sits down late queues behind the rest.
        """
        slots = self._bot_ready_at.setdefault(table_id, {})
        low, high = _BOT_READY_BAND
        span = (high - low) / max(1, MAX_READY_SLOTS)
        for seat_no in sorted(seat_nos):
            if seat_no in slots:
                continue
            base = low + span * min(len(slots), MAX_READY_SLOTS - 1)
            slots[seat_no] = now + timedelta(seconds=base + random.uniform(0, span * 0.5))

    def release_due_bot_ready(self, table_id: str, now: datetime) -> None:
        """Move every bot whose moment has arrived into the ready set, which is
        what the client renders checkmarks from."""
        due = {seat_no for seat_no, when in self._bot_ready_at.get(table_id, {}).items() if when <= now}
        if due:
            self._ready_seats.setdefault(table_id, set()).update(due)

    async def toggle_ready(self, table_id: str, seat_no: int) -> bool:
        """Returns the seat's new ready state. Any change un-arms the 5s
        pre-deal countdown -- it only re-arms once every human is ready again,
        which self-corrects if the toggle just broke a full-ready set."""
        async with self._lock(table_id):
            seats = self._ready_seats.setdefault(table_id, set())
            if seat_no in seats:
                seats.discard(seat_no)
                ready = False
            else:
                seats.add(seat_no)
                ready = True
            self._hand_starts_at.pop(table_id, None)
            return ready

    async def load(self, table_id: str) -> _LoadedTable | None:
        async with self._lock(table_id):
            return await self._load_locked(table_id)

    async def start_hand(
        self, table_id: str, *, button_seat: int | None = None, sit_out_seat_nos: set[int] | None = None,
    ) -> dict[str, Any]:
        async with self._lock(table_id):
            current = await self._load_locked(table_id)
            if current and current.phase in {"active", "result", "countdown", "paused"}:
                return await self.public_snapshot(table_id, None)

            async with self.session_factory() as session:
                async with session.begin():
                    table = await self._table(session, table_id)
                    seats = (
                        await session.execute(
                            select(table_seats)
                            .where(table_seats.c.table_id == table_id, table_seats.c.state == "seated")
                            .order_by(table_seats.c.seat_no)
                        )
                    ).mappings().all()
                    if sit_out_seat_nos:
                        # A human who never readied up keeps their seat and
                        # stack -- sitting out is per-hand, not a DB seat
                        # state, so it can never collide with the disconnect
                        # hold/leaving pipeline and its eventual eviction.
                        seats = [seat for seat in seats if seat["seat_no"] not in sit_out_seat_nos]
                    if not 2 <= len(seats) <= 6:
                        raise RuntimeErrorBase("a hand requires between 2 and 6 seated players")
                    details = await self._participant_details(session, seats)
                    engine_seats = []
                    for seat in seats:
                        participant_id = self._participant_id(seat)
                        engine_seats.append({
                            "id": participant_id,
                            "name": details[participant_id]["name"],
                            "seat": seat["seat_no"],
                            "stack": seat["stack_units"] / table["big_blind_units"],
                            "is_bot": seat["occupant_kind"] == "system",
                            "profile_id": seat["user_id"],
                            "difficulty": details[participant_id]["difficulty"],
                        })
                    if button_seat is None:
                        button_seat = self._next_button_seat(
                            table["button_seat"], [seat["seat_no"] for seat in seats]
                        )
                    state = self.engine.new_hand(engine_seats, button_seat=button_seat)
                    payload = serialize_state(state)
                    revision = 1
                    # Bots are on the same clock as anybody else. Withholding it
                    # was a tell: the ring around the avatar had nothing to count,
                    # so a bot's turn looked different from a person's. Nothing
                    # times a bot out in practice -- the coordinator hands them
                    # their move first, and bot_think_delay is capped at 12s,
                    # well inside this -- so the clock is what a watcher sees,
                    # not a new way to lose a hand.
                    action_deadline = (
                        self._now() + timedelta(seconds=30) if state.acting_player else None
                    )
                    runtime_values = {
                        "revision": revision,
                        "phase": "active",
                        "private_state_json": payload,
                        "public_payload_json": state.to_dict(),
                        "paused_reason": None,
                        "action_deadline": action_deadline,
                        "result_clear_at": None,
                        "next_hand_at": None,
                    }
                    existing_runtime = (
                        await session.execute(
                            select(table_runtimes.c.table_id).where(table_runtimes.c.table_id == table_id)
                        )
                    ).scalar_one_or_none()
                    if existing_runtime:
                        await session.execute(
                            update(table_runtimes).where(table_runtimes.c.table_id == table_id).values(**runtime_values)
                        )
                    else:
                        await session.execute(table_runtimes.insert().values(table_id=table_id, **runtime_values))
                    await session.execute(
                        update(poker_tables).where(poker_tables.c.id == table_id).values(
                            button_seat=state.players[state.button].seat
                        )
                    )
                    if self._worth_recording(state):
                        await session.execute(hands.insert().values(
                            id=state.hand_id,
                            table_id=table_id,
                            revision_started=revision,
                            button_seat=state.players[state.button].seat,
                            board_json=[],
                            result_json=None,
                            terminal=False,
                        ))
                        for participant_id in state.seat_order:
                            player = state.players[participant_id]
                            seat = next(row for row in seats if self._participant_id(row) == participant_id)
                            await session.execute(hand_players.insert().values(
                                hand_id=state.hand_id,
                                participant_id=participant_id,
                                user_id=seat["user_id"],
                                system_player_id=seat["system_player_id"],
                                seat_no=player.seat,
                                position=player.position,
                                start_stack_units=round(
                                    state.starting_stacks[participant_id] * table["big_blind_units"]
                                ),
                            ))
                        await append_integrity_event(
                            session, event_type="hand_started", table_id=table_id, hand_id=state.hand_id,
                            payload={"revision": revision, "players": len(state.players)},
                        )
                    loaded = _LoadedTable(revision, "active", state, action_deadline=action_deadline)
                    self._tables[table_id] = loaded
                    self._action_counts[table_id] = 0
                    return self._snapshot_for_state(loaded, None, table_id)

    async def public_snapshot(self, table_id: str, viewer_user_id: str | None) -> dict[str, Any]:
        loaded = self._tables.get(table_id)
        if loaded is None:
            loaded = await self._load_locked(table_id)
        if loaded is None:
            # A table that has never dealt a hand has no runtime row, which is
            # an ordinary state, not a failure: a freshly opened room sits in it
            # until somebody sits down and the first hand starts. Raising here
            # killed the websocket before it sent anything -- the REST route
            # caught it and rendered an empty table, but the socket did not, so
            # the client reconnected forever and the owner of a new room could
            # only watch it say "reconnecting".
            #
            # It still has to say who is sitting where. Without current_seats a
            # player who had just taken a seat in a brand-new room was invisible
            # to themselves: the ring drew every place as empty and offered them
            # their own seat back, until the first hand finally landed a minute
            # or more later.
            participant_id = (
                await self._participant_for_user(table_id, viewer_user_id) if viewer_user_id else None
            )
            return EMPTY_SNAPSHOT | {
                "viewer_state": "seated" if participant_id else "spectator",
                "viewer_player_id": participant_id,
                "current_seats": await self._current_seating(table_id),
            }
        participant_id = await self._participant_for_user(table_id, viewer_user_id) if viewer_user_id else None
        # A seat row can vanish while its owner is still a player in the hand
        # that is running -- leave processing and bot rebalance both clear seats
        # outright, and the engine keeps asking that player to act regardless.
        # Without this fallback they are demoted to a spectator mid-hand: no
        # hole cards, no viewer_player_id, so the client hides every action
        # control while the turn timer keeps auto-folding them, hand after hand.
        if participant_id is None and viewer_user_id and viewer_user_id in loaded.state.players:
            participant_id = viewer_user_id
        # A seat only joins state.players at the next hand boundary -- whether
        # because no hand exists yet (waiting for ready-up, countdown) or
        # because one was already running when this player bought in, so they
        # are sitting out the hand in progress. Either way state.players has
        # nothing for them yet, so they'd have no avatar to render and nothing
        # to click ready on. This is sourced independently from the actual
        # seating instead, whenever that gap applies to this specific viewer
        # (not fetched for everyone on every poll -- only the one case that
        # actually needs it).
        # Also whenever no hand is running. state.players is the roster of the
        # last hand that was dealt, and a table that cannot deal again -- one
        # bot has nobody to play -- keeps presenting it for good: micro-a sat
        # there showing four players who had long since left. While the table
        # is idle the seating is the only truthful answer, so it goes to
        # everyone watching, not just to a viewer caught between hands.
        current_seats = (
            await self._current_seating(table_id)
            if (participant_id is not None and participant_id not in loaded.state.players)
            or loaded.phase == "waiting"
            else None
        )
        return self._snapshot_for_state(loaded, participant_id, table_id, current_seats)

    async def private_snapshot(self, table_id: str) -> dict[str, Any]:
        loaded = self._tables.get(table_id) or await self._load_locked(table_id)
        if loaded is None:
            raise RuntimeErrorBase("table runtime not found")
        return serialize_state(loaded.state)

    async def action(
        self,
        table_id: str,
        user_id: str,
        command_id: str,
        expected_revision: int,
        action: str,
        amount_units: int,
    ) -> RuntimeActionResult:
        async with self._lock(table_id):
            loaded = await self._load_locked(table_id)
            if loaded is None:
                raise RuntimeErrorBase("table runtime not found")
            if loaded.phase == "paused":
                raise TablePaused("table runtime is paused")

            async with self.session_factory() as session:
                existing = (
                    await session.execute(
                        select(game_commands).where(
                            game_commands.c.table_id == table_id,
                            game_commands.c.command_id == command_id,
                        )
                    )
                ).mappings().first()
                if existing:
                    return self._result_from_json(existing["result_json"])
                if expected_revision != loaded.revision:
                    raise StaleRevision(loaded.revision)

                participant_id = await self._participant_for_user(table_id, user_id, session=session)
                if participant_id is None and user_id in loaded.state.players and loaded.state.players[user_id].is_bot:
                    participant_id = user_id
                if participant_id not in loaded.state.players:
                    raise InvalidAction("user is not a participant in this hand")
                legal_before = [item.value for item in self.engine.legal_actions(loaded.state, participant_id)]
                engine_action = ActionType(action)
                if engine_action not in self.engine.legal_actions(loaded.state, participant_id):
                    raise InvalidAction("action is not legal for this participant")
                table = await self._table(session, table_id)
                engine_amount = float(amount_units) / float(table["big_blind_units"])
                before = serialize_state(loaded.state)
                # Decrementing on failure would walk the revision backwards when
                # the action was refused before it ever incremented, leaving the
                # in-memory table behind the stored one.
                revision_before = loaded.revision
                try:
                    self.engine.apply_action(loaded.state, participant_id, engine_action, engine_amount)
                    loaded.revision += 1
                    if loaded.state.terminal:
                        loaded.phase = "result"
                        loaded.action_deadline = None
                    else:
                        loaded.action_deadline = (
                            self._now() + timedelta(seconds=30) if loaded.state.acting_player else None
                        )
                    snapshot = self._snapshot_for_state(loaded, participant_id, table_id)
                    result = RuntimeActionResult(
                        command_id=command_id,
                        table_id=table_id,
                        revision=loaded.revision,
                        action=engine_action.value,
                        legal_actions=legal_before,
                        snapshot=snapshot,
                    )
                    audit_user_id = None if loaded.state.players[participant_id].is_bot else user_id
                    await self._persist_action(
                        session, loaded, result, expected_revision, audit_user_id, amount_units
                    )
                    await session.commit()
                    self._action_counts[table_id] = self._action_counts.get(table_id, 0) + 1
                    return result
                except InvalidAction:
                    # The engine validates before it mutates, so a refused action
                    # leaves the hand intact. Pausing here would let one bad
                    # command — from a bot or a client — wedge the table for good.
                    loaded.state = deserialize_state(before)
                    loaded.revision = revision_before
                    await session.rollback()
                    raise
                except Exception as error:
                    loaded.state = deserialize_state(before)
                    loaded.revision = revision_before
                    await session.rollback()
                    await self._pause_after_failure(table_id, loaded, str(error))
                    raise

    def next_bot_spot(self, table_id: str) -> dict:
        """What the player about to act is facing, as bot_think_delay's inputs.

        Read off the loaded state, so it costs nothing: no equity is simulated
        just to decide how long to pause. When nobody is acting -- the hand
        ended on that move -- the defaults give an ordinary beat before the
        next hand's first decision.
        """
        loaded = self._tables.get(table_id)
        actor = None if loaded is None else loaded.state.acting_player
        if loaded is None or actor is None or actor not in loaded.state.players:
            return {"difficulty": "normal", "street": "flop"}
        player = loaded.state.players[actor]
        to_call = self.engine.to_call(loaded.state, actor)
        return {
            "difficulty": player.difficulty,
            "street": loaded.state.street.value,
            "pressure": to_call / max(loaded.state.pot, 1e-9),
            "patience": persona_for(actor).patience if player.is_bot else 1.0,
        }

    async def system_step(self, table_id: str) -> RuntimeActionResult:
        async with self._lock(table_id):
            loaded = await self._load_locked(table_id)
            if loaded is None:
                raise RuntimeErrorBase("table runtime not found")
            actor = loaded.state.acting_player
            if actor is None or not loaded.state.players[actor].is_bot:
                raise InvalidAction("system player is not acting")
            legal = self.engine.legal_actions(loaded.state, actor)
            bot = MultiwayBot(engine=self.engine)
            bot_view_payload = serialize_state(loaded.state)
            bot_view_payload["deck_cards"] = None
            for participant_id, player in bot_view_payload["players"].items():
                if participant_id != actor:
                    player["hole_cards"] = ["??", "??"]
            # Off the event loop. A bot's decision is a Monte Carlo equity
            # estimate in plain Python: measured at 32ms for an easy bot, 127ms
            # for a hard one and 268ms for maximum -- longer than the whole
            # coordinator interval. Run inline it froze every other table, every
            # websocket broadcast and every request for that quarter second, and
            # six tables of bots meant it was doing so constantly. A worker
            # thread does not beat the GIL, but it lets the interpreter switch
            # away mid-estimate instead of holding the loop for the duration.
            decision = await asyncio.to_thread(bot.decide, deserialize_state(bot_view_payload), actor)
            if decision.action not in legal:
                decision.action = legal[0]
            async with self.session_factory() as session:
                table = await self._table(session, table_id)
            # An under-sized bot raise is rejected by the engine, and a rejected
            # action pauses the table for good. Clamp in whole units, because the
            # engine works in float big blinds and rounding a clamped big-blind
            # amount can land back outside the range it just fit.
            amount_units = round(decision.amount * table["big_blind_units"])
            if decision.action in (ActionType.RAISE, ActionType.BET):
                player = loaded.state.players[actor]
                ceiling = math.floor((player.street_invested + player.stack) * table["big_blind_units"])
                floor = math.ceil(
                    min(self.engine.min_raise_to(loaded.state, actor), player.street_invested + player.stack)
                    * table["big_blind_units"]
                )
                amount_units = min(max(amount_units, min(floor, ceiling)), ceiling)
            user_id = actor
            command_id = f"system:{loaded.state.hand_id}:{loaded.revision}"
            # Re-enter through action without deadlocking this table lock.
        try:
            result = await self.action(
                table_id, user_id, command_id, loaded.revision, decision.action.value, amount_units,
            )
        except InvalidAction as error:
            # A bot that cannot be made to act must not wedge a table full of
            # real players. Fall back to the safest legal move instead.
            fallback = next(
                (item for item in (ActionType.CHECK, ActionType.CALL, ActionType.FOLD) if item in legal),
                legal[0],
            )
            logger.warning(
                "bot action %s for %s units rejected (%s), falling back to %s",
                decision.action.value, amount_units, error, fallback.value,
                extra={"table_id": table_id},
            )
            result = await self.action(
                table_id, user_id, f"{command_id}:fallback", loaded.revision, fallback.value, 0,
            )
        return RuntimeActionResult(
            result.command_id, result.table_id, result.revision, result.action, [item.value for item in legal], result.snapshot
        )

    async def timeout_current_actor(self, table_id: str, now: datetime) -> RuntimeActionResult | None:
        async with self._lock(table_id):
            loaded = await self._load_locked(table_id)
            if loaded is None or loaded.state.terminal or loaded.state.acting_player is None:
                return None
            actor = loaded.state.acting_player
            legal = self.engine.legal_actions(loaded.state, actor)
            timeout_action = ActionType.CHECK if ActionType.CHECK in legal else ActionType.FOLD
            command_id = f"timeout:{loaded.state.hand_id}:{loaded.revision}"
            revision = loaded.revision
            user_id = actor
        return await self.action(table_id, user_id, command_id, revision, timeout_action.value, 0)

    async def mark_leaving(self, table_id: str, user_id: str) -> bool:
        """Note that this player is on their way out. Returns whether they are
        actually in the hand that is running.

        A player who is not -- somebody who sat down mid-hand, or between hands
        -- has nothing to wait for, and the caller releases their seat there and
        then instead of at the next boundary. One who is stays until the hand
        settles, but is folded the instant the engine reaches them: waiting out
        the full thirty-second clock on every street they are still owed is
        what made walking out take the best part of a minute.
        """
        loaded = self._tables.get(table_id)
        if loaded is None or loaded.state.terminal:
            return False
        participant_id = await self._participant_for_user(table_id, user_id)
        if participant_id is None or participant_id not in loaded.state.players:
            return False
        loaded.leaving_participants.add(participant_id)
        return True

    def is_leaving(self, table_id: str, participant_id: str) -> bool:
        loaded = self._tables.get(table_id)
        return bool(loaded and participant_id in loaded.leaving_participants)

    async def fold_if_acting(self, table_id: str, user_id: str) -> RuntimeActionResult | None:
        """Leaving mid-hand must not let a player keep their cards and wait out
        the 30s clock -- fold immediately instead, same as if they had pressed
        the button themselves. A no-op if it isn't currently their turn.
        """
        async with self._lock(table_id):
            loaded = await self._load_locked(table_id)
            if loaded is None or loaded.state.terminal or loaded.state.acting_player is None:
                return None
            async with self.session_factory() as session:
                participant_id = await self._participant_for_user(table_id, user_id, session=session)
            if participant_id is None or participant_id != loaded.state.acting_player:
                return None
            command_id = f"leave-fold:{loaded.state.hand_id}:{loaded.revision}"
            revision = loaded.revision
        try:
            return await self.action(table_id, user_id, command_id, revision, ActionType.FOLD.value, 0)
        except (StaleRevision, InvalidAction, TablePaused):
            # Someone else's action landed first, or fold genuinely isn't
            # legal right now (e.g. already all-in) -- leaving still proceeds.
            return None

    async def prepare_next_hand(self, table_id: str) -> None:
        async with self._lock(table_id):
            loaded = await self._load_locked(table_id)
            if loaded is None:
                raise RuntimeErrorBase("table runtime not found")
            loaded.phase = "waiting"
            # The hand they were waiting on is over; the seat goes at the
            # boundary that follows, so nothing is owed to anyone next hand.
            loaded.leaving_participants.clear()
            async with self.session_factory() as session:
                async with session.begin():
                    await session.execute(
                        update(table_runtimes).where(table_runtimes.c.table_id == table_id).values(
                            phase="waiting", result_clear_at=None, next_hand_at=None,
                            action_deadline=None,
                        )
                    )
            loaded.result_clear_at = None
            loaded.next_hand_at = None
            loaded.action_deadline = None

    async def mark_countdown(self, table_id: str) -> None:
        async with self._lock(table_id):
            loaded = await self._load_locked(table_id)
            if loaded is None or loaded.phase != "result":
                return
            loaded.phase = "countdown"
            async with self.session_factory() as session:
                async with session.begin():
                    await session.execute(
                        update(table_runtimes).where(table_runtimes.c.table_id == table_id).values(
                            phase="countdown", updated_at=self._now()
                        )
                    )

    async def finish_and_settle(self, table_id: str):
        async with self._lock(table_id):
            loaded = await self._load_locked(table_id)
            if loaded is None:
                raise RuntimeErrorBase("table runtime not found")
            if not loaded.state.terminal:
                raise RuntimeErrorBase("hand is not terminal")
            async with self.session_factory() as session:
                async with session.begin():
                    table = await self._table(session, table_id)
                    seats = (
                        await session.execute(
                            select(table_seats).where(table_seats.c.table_id == table_id).order_by(table_seats.c.seat_no)
                        )
                    ).mappings().all()
                    by_participant = {self._participant_id(seat): seat for seat in seats}
                    recorded = self._worth_recording(loaded.state)
                    starts, ends = self._settlement_units(loaded.state, table["big_blind_units"])
                    transfers: dict[tuple[str, str, str], int] = {}
                    user_net_total = 0
                    for participant_id, player in loaded.state.players.items():
                        seat = by_participant[participant_id]
                        start_units = starts[participant_id]
                        end_units = ends[participant_id]
                        if seat["occupant_kind"] == "user":
                            # A seated user's stack stays in the table escrow between
                            # hands. Only the net change against system players moves
                            # through the shared table account; paying the full stack
                            # to the wallet here would double-count it on the next hand.
                            user_net_total += end_units - start_units
                        else:
                            transfers[("system", participant_id, "escrow")] = end_units - start_units
                        if recorded:
                            await session.execute(
                                update(hand_players)
                                .where(
                                    hand_players.c.hand_id == loaded.state.hand_id,
                                    hand_players.c.participant_id == participant_id,
                                )
                                .values(
                                    end_stack_units=end_units,
                                    net_units=end_units - start_units,
                                    hole_cards_json=list(player.hole_cards),
                                    shown=not player.folded,
                                )
                            )
                        # The seat's stack is the game, not the record, and is
                        # written whoever was playing.
                        await session.execute(
                            update(table_seats).where(table_seats.c.id == seat["id"]).values(stack_units=end_units)
                        )
                        if recorded:
                            # A bot's tally of hands and wins against other bots
                            # counts nothing and is read by nothing -- 331,757
                            # hands and 74,406 wins had accumulated across 36 of
                            # them before this stopped.
                            profile_table = users if seat["occupant_kind"] == "user" else system_players
                            profile_id = seat["user_id"] or seat["system_player_id"]
                            await session.execute(
                                update(profile_table)
                                .where(profile_table.c.id == profile_id)
                                .values(
                                    hands_played=profile_table.c.hands_played + 1,
                                    wins=profile_table.c.wins + (1 if end_units > start_units else 0),
                                )
                            )
                    transfers[("table", table_id, "escrow")] = user_net_total
                    settlement = await self.ledger.settle_hand_transfers(
                        loaded.state.hand_id, transfers, session=session
                    )
                    completed_at = self._now()
                    loaded.result_clear_at = completed_at + timedelta(seconds=4)
                    loaded.next_hand_at = completed_at + timedelta(seconds=7)
                    if recorded:
                        await session.execute(
                            update(hands).where(hands.c.id == loaded.state.hand_id).values(
                                board_json=loaded.state.board,
                                result_json=loaded.state.to_dict(),
                                terminal=True,
                                completed_at=completed_at,
                            )
                        )
                    loaded.phase = "result"
                    await session.execute(
                        update(table_runtimes).where(table_runtimes.c.table_id == table_id).values(
                            phase="result",
                            private_state_json=serialize_state(loaded.state),
                            public_payload_json=loaded.state.to_dict(),
                            result_clear_at=loaded.result_clear_at,
                            next_hand_at=loaded.next_hand_at,
                            updated_at=completed_at,
                        )
                    )
                    if recorded:
                        await append_integrity_event(
                            session, event_type="hand_settled", table_id=table_id,
                            hand_id=loaded.state.hand_id, payload={"revision": loaded.revision},
                        )
                    return settlement

    async def abandon_hand(self, table_id: str) -> None:
        """Wash a stuck hand: refund every seat exactly what it started with.

        A paused table has no recovery path — start_hand refuses to run while
        phase=="paused", and nothing else advances it — so a table stays stuck
        forever, its buy-ins locked in escrow. Rather than trying to replay or
        guess the hand's outcome, every participant gets back their starting
        stack, through the same ledger transfer finish_and_settle uses, so the
        books stay balanced and the table can resume on the next tick.
        """
        async with self._lock(table_id):
            loaded = await self._load_locked(table_id)
            if loaded is None:
                raise RuntimeErrorBase("table runtime not found")
            if loaded.state.terminal:
                return
            async with self.session_factory() as session:
                async with session.begin():
                    table = await self._table(session, table_id)
                    seats = (
                        await session.execute(
                            select(table_seats).where(table_seats.c.table_id == table_id).order_by(table_seats.c.seat_no)
                        )
                    ).mappings().all()
                    by_participant = {self._participant_id(seat): seat for seat in seats}
                    starts = {
                        pid: round(loaded.state.starting_stacks[pid] * table["big_blind_units"])
                        for pid in loaded.state.players
                    }
                    recorded = self._worth_recording(loaded.state)
                    transfers: dict[tuple[str, str, str], int] = {}
                    for participant_id in loaded.state.players:
                        seat = by_participant.get(participant_id)
                        start_units = starts[participant_id]
                        if recorded:
                            await session.execute(
                                update(hand_players)
                                .where(
                                    hand_players.c.hand_id == loaded.state.hand_id,
                                    hand_players.c.participant_id == participant_id,
                                )
                                .values(end_stack_units=start_units, net_units=0, shown=False)
                            )
                        if seat is None:
                            # The seat was already reused by the time recovery ran; the
                            # escrow row for it is gone too, so credit the wallet direct
                            # and pull the same amount out of the table's shared escrow.
                            transfers[("user", participant_id, "wallet")] = start_units
                            transfers[("table", table_id, "escrow")] = (
                                transfers.get(("table", table_id, "escrow"), 0) - start_units
                            )
                            continue
                        # Every seat that's still there gets exactly its starting
                        # stack back; nothing moves through the ledger for it.
                        await session.execute(
                            update(table_seats).where(table_seats.c.id == seat["id"]).values(stack_units=start_units)
                        )
                    settlement = (
                        await self.ledger.settle_hand_transfers(loaded.state.hand_id, transfers, session=session)
                        if transfers else None
                    )
                    completed_at = self._now()
                    loaded.state.terminal = True
                    loaded.state.street = Street.COMPLETE
                    loaded.state.acting_player = None
                    loaded.state.pending_actions.clear()
                    loaded.state.winner = None
                    loaded.state.winners = []
                    loaded.state.result_text = "Раздача отменена — сбой синхронизации, фишки возвращены"
                    loaded.state.result_details = []
                    if recorded:
                        await session.execute(
                            update(hands).where(hands.c.id == loaded.state.hand_id).values(
                                board_json=loaded.state.board,
                                result_json=loaded.state.to_dict(),
                                terminal=True,
                                completed_at=completed_at,
                            )
                        )
                    loaded.phase = "waiting"
                    loaded.action_deadline = None
                    loaded.result_clear_at = None
                    loaded.next_hand_at = None
                    await session.execute(
                        update(table_runtimes).where(table_runtimes.c.table_id == table_id).values(
                            phase="waiting",
                            private_state_json=serialize_state(loaded.state),
                            public_payload_json=loaded.state.to_dict(),
                            paused_reason=None,
                            action_deadline=None,
                            result_clear_at=None,
                            next_hand_at=None,
                            updated_at=completed_at,
                        )
                    )
                    if recorded:
                        await append_integrity_event(
                            session, event_type="hand_abandoned", table_id=table_id,
                            hand_id=loaded.state.hand_id, payload={"revision": loaded.revision},
                        )
                    return settlement

    def engine_action_count(self, table_id: str) -> int:
        return self._action_counts.get(table_id, 0)

    async def restore_all(self) -> list[str]:
        async with self.session_factory() as session:
            rows = (await session.execute(select(table_runtimes))).mappings().all()
        restored = []
        for row in rows:
            state = deserialize_state(row["private_state_json"])
            action_deadline = self._utc(row["action_deadline"])
            if row["phase"] == "active" and action_deadline is not None:
                grace = self._now() + timedelta(seconds=10)
                if action_deadline < grace:
                    action_deadline = grace
                    async with self.session_factory() as session:
                        async with session.begin():
                            await session.execute(
                                update(table_runtimes).where(table_runtimes.c.table_id == row["table_id"]).values(
                                    action_deadline=action_deadline,
                                )
                            )
            self._tables[row["table_id"]] = _LoadedTable(
                row["revision"], row["phase"], state,
                action_deadline=action_deadline,
                result_clear_at=self._utc(row["result_clear_at"]),
                next_hand_at=self._utc(row["next_hand_at"]),
            )
            self._locks.setdefault(row["table_id"], asyncio.Lock())
            restored.append(row["table_id"])
        return restored

    async def _persist_action(
        self,
        session: AsyncSession,
        loaded: _LoadedTable,
        result: RuntimeActionResult,
        expected_revision: int,
        user_id: str | None,
        amount_units: int,
    ) -> None:
        payload = serialize_state(loaded.state)
        await session.execute(
            update(table_runtimes)
            .where(table_runtimes.c.table_id == result.table_id)
            .values(
                revision=result.revision,
                private_state_json=payload,
                public_payload_json=loaded.state.to_dict(),
                phase="result" if loaded.state.terminal else "active",
                action_deadline=loaded.action_deadline,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if not self._worth_recording(loaded.state):
            # Nobody will read a bot-only hand back, and the two logs it fills
            # are the bulk of the database. The revision check above is what
            # actually stops a command being applied twice; this row only lets
            # a client retry get the same answer, and a bot never retries.
            return
        await session.execute(game_commands.insert().values(
            table_id=result.table_id,
            command_id=result.command_id,
            user_id=user_id,
            expected_revision=expected_revision,
            command_type="action",
            payload_json={"action": result.action, "amount_units": amount_units},
            status="accepted",
            result_json=self._result_json(result),
        ))
        latest = loaded.state.history[-1]
        await session.execute(hand_actions.insert().values(
            hand_id=loaded.state.hand_id,
            sequence=len(loaded.state.history) - 1,
            participant_id=latest.player_id,
            street=latest.street.value,
            action=latest.action.value,
            amount_units=round(latest.amount * 100),
            pot_before_units=round(latest.pot_before * 100),
            pot_after_units=round(latest.pot_after * 100),
            to_call_before_units=round(latest.to_call_before * 100),
        ))
        await append_integrity_event(
            session, event_type="command_accepted", table_id=result.table_id,
            hand_id=loaded.state.hand_id, user_id=user_id,
            payload={"command_id": result.command_id, "revision": result.revision, "action": result.action},
        )

    async def _pause_after_failure(self, table_id: str, loaded: _LoadedTable, reason: str) -> None:
        loaded.phase = "paused"
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(update(table_runtimes).where(table_runtimes.c.table_id == table_id).values(
                    phase="paused", private_state_json=serialize_state(loaded.state), paused_reason=reason,
                ))
                # A wedged table is worth recording whoever was sitting at it.
                # The hand itself may not be in the books, and integrity_events
                # has a foreign key to hands -- so name the table, not the hand.
                await append_integrity_event(
                    session, event_type="runtime_paused", table_id=table_id,
                    hand_id=loaded.state.hand_id if self._worth_recording(loaded.state) else None,
                    payload={"reason": reason[:200], "hand_id": loaded.state.hand_id},
                )

    async def _load_locked(self, table_id: str) -> _LoadedTable | None:
        loaded = self._tables.get(table_id)
        if loaded is not None:
            return loaded
        async with self.session_factory() as session:
            row = (
                await session.execute(select(table_runtimes).where(table_runtimes.c.table_id == table_id))
            ).mappings().first()
        if row is None:
            return None
        loaded = _LoadedTable(
            row["revision"], row["phase"], deserialize_state(row["private_state_json"]),
            action_deadline=self._utc(row["action_deadline"]),
            result_clear_at=self._utc(row["result_clear_at"]),
            next_hand_at=self._utc(row["next_hand_at"]),
        )
        self._tables[table_id] = loaded
        self._locks.setdefault(table_id, asyncio.Lock())
        return loaded

    async def _table(self, session: AsyncSession, table_id: str):
        row = (await session.execute(select(poker_tables).where(poker_tables.c.id == table_id))).mappings().first()
        if row is None:
            raise RuntimeErrorBase("table not found")
        return row

    async def _participant_details(self, session: AsyncSession, seats) -> dict[str, dict[str, str]]:
        user_rows = (await session.execute(select(users))).mappings().all()
        bot_rows = (await session.execute(select(system_players))).mappings().all()
        details = {
            row["id"]: {"name": row["display_name"], "difficulty": "normal"}
            for row in user_rows
        }
        details.update({
            row["id"]: {"name": row["name"], "difficulty": row["difficulty"]}
            for row in bot_rows
        })
        return {self._participant_id(seat): details[self._participant_id(seat)] for seat in seats}

    @staticmethod
    def _settlement_units(state: GameState, big_blind_units: int) -> tuple[dict[str, int], dict[str, int]]:
        """Chip counts in units, conserved.

        The engine keeps stacks as floats in big blinds, so a split pot lands
        on thirds. Rounding each stack on its own then loses or invents a unit
        and settle_hand_transfers refuses the whole hand, which wedges the
        table forever. The odd unit goes to the biggest stack instead.
        """
        starts = {
            pid: round(state.starting_stacks[pid] * big_blind_units) for pid in state.players
        }
        ends = {pid: round(player.stack * big_blind_units) for pid, player in state.players.items()}
        residue = sum(starts.values()) - sum(ends.values())
        if residue:
            ends[max(ends, key=lambda pid: ends[pid])] += residue
        return starts, ends

    @staticmethod
    def _next_button_seat(previous: int | None, seated: list[int]) -> int:
        """Move the button to the next seated player, so the blinds rotate."""
        if previous is None:
            return seated[0]
        return next((seat for seat in sorted(seated) if seat > previous), min(seated))

    @staticmethod
    def _worth_recording(state) -> bool:
        """Whether this hand goes in the books at all.

        A hand with nobody but bots in it is written down for no reader: on the
        live database 908,238 of the 908,696 recorded actions were bots, against
        458 by people. Nothing consults a bot's history -- not the history
        service, not the profile, not the bots themselves, which do not model
        each other and are built without an opponent-model provider at all.

        A hand with a person in it is recorded whole, opponents included: their
        moves are what makes the record worth having.
        """
        return any(not player.is_bot for player in state.players.values())

    @staticmethod
    def _participant_id(seat) -> str:
        return seat["user_id"] or seat["system_player_id"]

    async def _participant_for_user(self, table_id: str, user_id: str | None, *, session: AsyncSession | None = None):
        if not user_id:
            return None

        async def query(db: AsyncSession):
            row = (
                await db.execute(
                    select(table_seats).where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.user_id == user_id,
                        table_seats.c.state.in_(("seated", "held", "leaving")),
                    )
                )
            ).mappings().first()
            return row["user_id"] if row else None

        if session is not None:
            return await query(session)
        async with self.session_factory() as db:
            return await query(db)

    def _snapshot_for_state(
        self,
        loaded: _LoadedTable,
        participant_id: str | None,
        table_id: str | None = None,
        current_seats: dict[int, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        state = loaded.state.to_dict(viewer_player_id=participant_id)
        for player in state["players"].values():
            player.pop("difficulty", None)
        legal = [item.value for item in self.engine.legal_actions(loaded.state, participant_id)] if participant_id else []
        ready_deadline = self.ready_deadline(table_id) if table_id else None
        hand_starts_at = self.hand_starts_at(table_id) if table_id else None
        state.update({
            "phase": loaded.phase,
            "revision": loaded.revision,
            "legal_actions": legal,
            "action_deadline": loaded.action_deadline.isoformat() if loaded.action_deadline else None,
            "result_clear_at": loaded.result_clear_at.isoformat() if loaded.result_clear_at else None,
            "next_hand_at": loaded.next_hand_at.isoformat() if loaded.next_hand_at else None,
            "occupancy": len(loaded.state.players),
            # Ready-up: who has clicked ready this hand, the AFK sit-out
            # deadline, and the 5s beat once everyone's in. All None once a
            # hand is actually running -- see clear_ready_cycle.
            "ready_seats": sorted(self.ready_seats(table_id)) if table_id else [],
            "ready_deadline": ready_deadline.isoformat() if ready_deadline else None,
            "hand_starts_at": hand_starts_at.isoformat() if hand_starts_at else None,
            # Who is actually sitting where right now, independent of the last
            # hand's roster -- see public_snapshot for why this exists.
            "current_seats": current_seats,
        })
        return state

    async def _current_seating(self, table_id: str) -> dict[int, dict[str, Any]]:
        async with self.session_factory() as session:
            seats = (
                await session.execute(
                    select(table_seats).where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.state.in_(("seated", "held", "leaving")),
                    )
                )
            ).mappings().all()
            if not seats:
                return {}
            details = await self._participant_details(session, seats)
            table = await self._table(session, table_id)
        return {
            seat["seat_no"]: {
                "id": self._participant_id(seat),
                "name": details[self._participant_id(seat)]["name"],
                # Between hands the client draws seats from here rather than
                # from the last hand's roster, so without the seat's real stack
                # every player reads "0" until the next deal lands.
                "stack": seat["stack_units"] / table["big_blind_units"],
                "is_bot": seat["occupant_kind"] == "system",
                # "seated" is not the only state in here: a seat queued for
                # the next boundary is "held", and one being vacated is
                # "leaving". The client cannot tell them apart without this,
                # and reading a held seat as its own made it offer "mark
                # ready" to somebody the server does not consider seated yet
                # -- which came back as "take a seat before marking ready".
                "state": seat["state"],
            }
            for seat in seats
        }

    @staticmethod
    def _result_json(result: RuntimeActionResult) -> dict[str, Any]:
        return {
            "command_id": result.command_id,
            "table_id": result.table_id,
            "revision": result.revision,
            "action": result.action,
            "legal_actions": result.legal_actions,
            "snapshot": result.snapshot,
        }

    @staticmethod
    def _result_from_json(payload: dict[str, Any]) -> RuntimeActionResult:
        return RuntimeActionResult(
            command_id=payload["command_id"], table_id=payload["table_id"], revision=payload["revision"],
            action=payload["action"], legal_actions=list(payload.get("legal_actions", [])),
            snapshot=payload["snapshot"],
        )

    def _now(self) -> datetime:
        return self.clock() if callable(self.clock) else self.clock.now()

    @staticmethod
    def _utc(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)
