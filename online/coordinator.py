from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from online.catalogue import Catalogue
from online.integrity import EscrowIntegrityMonitor
from online.runtime import TableRuntimeManager, bot_think_delay
from online.seating import SeatingService


logger = logging.getLogger(__name__)


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

    async def _tick_table(self, table_id: str) -> None:
        before = self._signature(table_id)
        await self._advance_table(table_id)
        if self.on_change is not None and self._signature(table_id) != before:
            await self.on_change(table_id)

    async def _advance_table(self, table_id: str) -> None:
        now = self.now()
        loaded = await self.runtime.load(table_id)
        if loaded is None or loaded.phase == "waiting":
            await self.seating.process_boundary(table_id, now=now)
            loaded = await self.runtime.load(table_id)
            if loaded is None or loaded.phase == "waiting":
                if 2 <= await self.seating.active_seat_count(table_id) <= 6:
                    await self.runtime.start_hand(table_id)
            return

        if loaded.phase == "active":
            if loaded.state.terminal:
                await self.runtime.finish_and_settle(table_id)
            elif loaded.state.acting_player:
                actor = loaded.state.players[loaded.state.acting_player]
                if actor.is_bot:
                    # Paced to a human-like think time instead of firing on
                    # every 250ms tick -- see bot_think_delay's docstring.
                    if loaded.next_bot_action_at is None or loaded.next_bot_action_at <= now:
                        street = loaded.state.street.value
                        await self.runtime.system_step(table_id)
                        delay = bot_think_delay(actor.difficulty, street)
                        loaded.next_bot_action_at = now + timedelta(seconds=delay)
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
            if 2 <= await self.seating.active_seat_count(table_id) <= 6:
                await self.runtime.start_hand(table_id)
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
