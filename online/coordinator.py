from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from online.catalogue import Catalogue
from online.integrity import EscrowIntegrityMonitor
from online.runtime import TableRuntimeManager, bot_think_delay
from online.schema import game_commands, integrity_events
from online.seating import SeatingService


logger = logging.getLogger(__name__)

# How long a player's room may sit without a single human before it is retired.
# Short on purpose: an abandoned room holds its owner's one-room slot and sits
# in the lobby offering a table nobody is at. Short enough that opening a room
# and then dawdling before taking a seat can lose it -- the create flow drops
# you straight onto the table, so that is a matter of one tap.
ROOM_IDLE_TTL = timedelta(seconds=90)

# Two logs grow with every hand and nothing ever removed a row from either. On
# the live database: game_commands at 907k rows and 1134 MB, integrity_events
# at 1.06M rows and 288 MB, in a database of 1811 MB -- almost all of it bots
# playing each other overnight.
#
# game_commands exists to recognise a command_id that arrives twice, which only
# happens when a client retries a request it already sent. A day is generous.
COMMAND_LOG_TTL = timedelta(hours=24)
# The event log is the money audit trail and escrow findings stay in it for
# good. These three are the volume -- 167k command_accepted alone in a day --
# and nothing reads them back.
EVENT_LOG_TTL = timedelta(days=7)
NOISY_EVENT_TYPES = ("command_accepted", "hand_started", "hand_settled")
# Rarely, and a bounded bite each time: the first sweep on a database that has
# never been swept has a million rows to get through, and a single statement
# that size would hold locks for the length of it.
LOG_SWEEP_EVERY = timedelta(minutes=30)
LOG_SWEEP_BATCH = 2000


class OnlineCoordinator:
    """Durable table lifecycle loop for production network tables."""

    def __init__(
        self,
        runtime: TableRuntimeManager,
        seating: SeatingService,
        catalogue: Catalogue,
        *,
        interval_seconds: float = 0.25,
        integrity_monitor: EscrowIntegrityMonitor | None = None,
        on_change=None,
    ) -> None:
        self.runtime = runtime
        self.seating = seating
        self.catalogue = catalogue
        self.interval_seconds = interval_seconds
        self.integrity_monitor = integrity_monitor
        # Bot moves, timeouts and hand boundaries all happen here rather than on
        # a client command, so without this the only way a viewer learns about
        # them is the slow fallback poll.
        self.on_change = on_change
        self.last_tick_at: datetime | None = None
        self.last_tick_duration_ms: float | None = None
        # Since when each player room has been empty of humans. In memory: a
        # restart just starts the clock again.
        self._room_idle_since: dict[str, datetime] = {}
        # A bot's move in flight, one per table. Thinking is a Monte Carlo
        # estimate on a worker thread; awaiting it inside the tick made the
        # tick as long as the thinking -- 571ms measured against a 250ms
        # interval. Started here and collected on a later tick instead, so
        # one table's bot never holds up another table's clock.
        self._bot_moves: dict[str, asyncio.Task] = {}
        self._last_log_sweep: datetime | None = None
        self._stop = asyncio.Event()

    def now(self) -> datetime:
        return self.runtime._now()

    async def tick(self) -> None:
        started = time.perf_counter()
        try:
            if self.integrity_monitor is not None:
                try:
                    await self.integrity_monitor.maybe_check()
                except Exception:
                    logger.exception("poker8 escrow integrity monitor failed")
            await self._retire_idle_rooms()
            await self._sweep_logs()
            tables = await self.catalogue.list_tables(page=1, per_page=100)
            for table in tables:
                # A corrupted or temporarily underfunded table must not prevent
                # the coordinator from advancing every other independent table.
                try:
                    await self._tick_table(table.id)
                except Exception:
                    logger.exception("online coordinator table tick failed", extra={"table_id": table.id})
        finally:
            self.last_tick_at = datetime.now(timezone.utc)
            self.last_tick_duration_ms = round((time.perf_counter() - started) * 1000, 2)

    def _signature(self, table_id: str):
        loaded = self.runtime._tables.get(table_id)
        return None if loaded is None else (loaded.revision, loaded.phase, loaded.state.acting_player)

    async def _sweep_logs(self) -> None:
        """Drop the rows in the two write-only logs that nothing will read again.

        Bounded on purpose: a bite at a time, on a long interval, so the first
        sweep of a database that has never been swept does not hold locks for
        the length of a million-row delete.
        """
        now = self.now()
        if self._last_log_sweep is not None and now - self._last_log_sweep < LOG_SWEEP_EVERY:
            return
        self._last_log_sweep = now
        try:
            async with self.runtime.session_factory() as session:
                async with session.begin():
                    stale = (
                        await session.execute(
                            select(game_commands.c.table_id, game_commands.c.command_id)
                            .where(game_commands.c.created_at < now - COMMAND_LOG_TTL)
                            .limit(LOG_SWEEP_BATCH)
                        )
                    ).all()
                    for table_id, command_id in stale:
                        await session.execute(
                            delete(game_commands).where(
                                game_commands.c.table_id == table_id,
                                game_commands.c.command_id == command_id,
                            )
                        )
                    noisy = (
                        await session.execute(
                            select(integrity_events.c.id)
                            .where(
                                integrity_events.c.event_type.in_(NOISY_EVENT_TYPES),
                                integrity_events.c.created_at < now - EVENT_LOG_TTL,
                            )
                            .limit(LOG_SWEEP_BATCH)
                        )
                    ).scalars().all()
                    if noisy:
                        await session.execute(
                            delete(integrity_events).where(integrity_events.c.id.in_(noisy))
                        )
            if stale or noisy:
                logger.info(
                    "poker8_log_sweep",
                    extra={"commands": len(stale), "events": len(noisy)},
                )
        except Exception:
            # Housekeeping must never be the reason a table stops advancing.
            logger.exception("poker8 log sweep failed")

    async def _retire_idle_rooms(self) -> None:
        """Close a player's room once it has sat without a human long enough.

        The clock lives in memory: a restart simply starts it again, and a room
        that outlives one restart is not worth a schema column. Every seat is
        emptied first -- a closed table stops being advanced, so anything left
        seated would keep its chips locked in the table's escrow.
        """
        idle_now = set(await self.catalogue.idle_room_ids())
        for table_id in list(self._room_idle_since):
            if table_id not in idle_now:
                self._room_idle_since.pop(table_id, None)
        now = self.now()
        for table_id in idle_now:
            since = self._room_idle_since.setdefault(table_id, now)
            if now - since < ROOM_IDLE_TTL:
                continue
            self._room_idle_since.pop(table_id, None)
            await self.seating.evict_table(table_id)
            await self.catalogue.close_room(table_id)
            logger.info("poker8_room_retired", extra={"table_id": table_id})

    async def _bot_move(self, table_id: str) -> None:
        """One bot action, off the tick. It tells viewers itself: the tick that
        starts it sees no change, and the tick that collects it sees a state
        that already changed, so neither would have broadcast anything.
        """
        await self.runtime.system_step(table_id)
        if self.on_change is not None:
            await self.on_change(table_id)

    async def _tick_table(self, table_id: str) -> None:
        before = self._signature(table_id)
        await self._advance_table(table_id)
        if self.on_change is not None and self._signature(table_id) != before:
            await self.on_change(table_id)

    async def _may_start_hand(self, table_id: str, now: datetime) -> tuple[bool, set[int]]:
        """Returns (should_start, sit_out_seat_nos). Seat count in range and
        every seated human ready -- or, past the 30s AFK deadline, excluded
        from just this hand instead of blocking the table forever. Bots are
        implicitly ready. Sitting out never touches the seat's DB state (that
        pipeline ends in eviction); it only narrows who start_hand deals in,
        so the seat and stack are untouched and everyone's asked again next
        hand. The single gate for both places a hand can start, so the
        cold-start and post-countdown paths can't drift apart.
        """
        # One query for all three questions -- see seated_composition.
        human_seats, bot_seats = await self.seating.seated_composition(table_id)
        if not (2 <= len(human_seats) + len(bot_seats) <= 6):
            return False, set()

        if not human_seats:
            return True, set()

        # Bots confirm on their own uneven beat rather than being implicitly
        # ready, so their checkmarks appear one at a time like people's do.
        # They are never sat out for it -- the AFK deadline below only ever
        # excludes humans, and a bot's slot always lands well inside it.
        self.runtime.schedule_bot_ready(table_id, bot_seats, now)
        self.runtime.release_due_bot_ready(table_id, now)

        ready = self.runtime.ready_seats(table_id)
        if (human_seats | bot_seats).issubset(ready):
            starts_at = self.runtime.hand_starts_at(table_id)
            if starts_at is None:
                # A beat between "everyone's in" and the cards actually
                # landing -- the client's ready countdown ring times this.
                self.runtime.arm_hand_starts_at(table_id, now + timedelta(seconds=5))
                return False, set()
            return starts_at <= now, set()

        deadline = self.runtime.ready_deadline(table_id)
        if deadline is None:
            self.runtime.arm_ready_deadline(table_id, now + timedelta(seconds=30))
            return False, set()
        if deadline <= now:
            sit_out = human_seats - ready
            # The count above included the very people about to be sat out.
            # With one bot arrived and the only human asleep, start_hand was
            # asked to deal to a single player, refused, and the tick logged a
            # traceback four times a second until somebody else sat down --
            # 139 of them in four minutes on the live site. Staggering the
            # bots' arrival did not create this, it just made it common.
            if len(human_seats | bot_seats) - len(sit_out) < 2:
                return False, set()
            return True, sit_out
        return False, set()

    async def _advance_table(self, table_id: str) -> None:
        now = self.now()
        loaded = await self.runtime.load(table_id)
        if loaded is None or loaded.phase == "waiting":
            await self.seating.process_boundary(table_id, now=now)
            loaded = await self.runtime.load(table_id)
            if loaded is None or loaded.phase == "waiting":
                should_start, sit_out = await self._may_start_hand(table_id, now)
                if should_start:
                    await self.runtime.start_hand(table_id, sit_out_seat_nos=sit_out)
                    self.runtime.clear_ready_cycle(table_id)
            return

        if loaded.phase == "active":
            if loaded.state.terminal:
                await self.runtime.finish_and_settle(table_id)
            elif loaded.state.acting_player:
                actor = loaded.state.players[loaded.state.acting_player]
                if actor.is_bot:
                    move = self._bot_moves.get(table_id)
                    if move is not None:
                        if not move.done():
                            return  # still thinking; nothing else to do here
                        self._bot_moves.pop(table_id, None)
                        try:
                            move.result()
                        except Exception:
                            logger.exception("bot move failed", extra={"table_id": table_id})
                        # The pause that follows a move is the *next* player's
                        # thinking, so it is measured from their spot and their
                        # own tempo -- not from the one who just acted.
                        delay = bot_think_delay(**self.runtime.next_bot_spot(table_id))
                        loaded.next_bot_action_at = now + timedelta(seconds=delay)
                        return
                    # Paced to a human-like think time instead of firing on
                    # every 250ms tick -- see bot_think_delay's docstring.
                    if loaded.next_bot_action_at is None or loaded.next_bot_action_at <= now:
                        self._bot_moves[table_id] = asyncio.create_task(self._bot_move(table_id))
                elif self.runtime.is_leaving(table_id, loaded.state.acting_player):
                    # They already asked to go. Holding the hand for their
                    # thirty seconds, on this street and every one after, is
                    # what made walking out take the best part of a minute.
                    await self.runtime.timeout_current_actor(table_id, now)
                elif loaded.action_deadline is not None and loaded.action_deadline <= now:
                    await self.runtime.timeout_current_actor(table_id, now)
            return

        if loaded.phase == "result":
            if loaded.result_clear_at is None or loaded.next_hand_at is None:
                await self.runtime.finish_and_settle(table_id)
            elif loaded.result_clear_at <= now:
                await self.runtime.mark_countdown(table_id)
            return

        if loaded.phase == "countdown" and loaded.next_hand_at is not None and loaded.next_hand_at <= now:
            await self.runtime.prepare_next_hand(table_id)
            await self.seating.process_boundary(table_id, now=now)
            should_start, sit_out = await self._may_start_hand(table_id, now)
            if should_start:
                await self.runtime.start_hand(table_id, sit_out_seat_nos=sit_out)
                self.runtime.clear_ready_cycle(table_id)
            return

        if loaded.phase == "paused":
            # Nothing else ever advances a paused table — start_hand refuses to
            # run while it stays this way, so every buy-in on it would otherwise
            # be locked up for good. Refund the stuck hand and resume play.
            await self.runtime.abandon_hand(table_id)

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("online coordinator tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

    async def stop(self) -> None:
        self._stop.set()
        for task in list(self._bot_moves.values()):
            task.cancel()
        self._bot_moves.clear()
