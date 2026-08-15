from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from online.catalogue import Catalogue
from online.runtime import TableRuntimeManager
from online.seating import SeatingService


class OnlineCoordinator:
    """Durable table lifecycle loop for production network tables."""

    def __init__(
        self,
        runtime: TableRuntimeManager,
        seating: SeatingService,
        catalogue: Catalogue,
        *,
        interval_seconds: float = 0.25,
    ) -> None:
        self.runtime = runtime
        self.seating = seating
        self.catalogue = catalogue
        self.interval_seconds = interval_seconds
        self._stop = asyncio.Event()

    def now(self) -> datetime:
        return self.runtime._now()

    async def tick(self) -> None:
        tables = await self.catalogue.list_tables(page=1, per_page=100)
        for table in tables:
            await self._tick_table(table.id)

    async def _tick_table(self, table_id: str) -> None:
        now = self.now()
        loaded = await self.runtime.load(table_id)
        if loaded is None or loaded.phase == "waiting":
            await self.seating.expire_holds(table_id, now)
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
                    await self.runtime.system_step(table_id)
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

    async def run(self) -> None:
        while not self._stop.is_set():
            await self.tick()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

    async def stop(self) -> None:
        self._stop.set()
