from __future__ import annotations

from datetime import datetime, timedelta, timezone

from online.runtime import RuntimeActionResult, TableRuntimeManager
from poker.models import ActionType


class TableScheduler:
    """Small persistent-deadline coordinator; production can call tick periodically."""

    def __init__(self, runtime: TableRuntimeManager, *, clock=None, seating=None) -> None:
        self.runtime = runtime
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.seating = seating
        self.deadlines: dict[str, datetime] = {}
        self._fired: set[tuple[str, int]] = set()
        self.result_clear_at: dict[str, datetime] = {}
        self.next_hand_at: dict[str, datetime] = {}
        self.phases: dict[str, str] = {}
        self.public_state_has_cards = True
        self.last_action: str | None = None
        self.action_count = 0
        self.new_hand_count = 0

    def now(self) -> datetime:
        return self.clock() if callable(self.clock) else self.clock.now()

    def now_plus(self, *, seconds: float) -> datetime:
        return self.now() + timedelta(seconds=seconds)

    @property
    def action_deadline(self) -> datetime | None:
        return self.deadlines.get("t1")

    async def start_hand(self, table_id: str):
        snapshot = await self.runtime.start_hand(table_id)
        loaded = self.runtime._tables[table_id]
        if loaded.state.acting_player and not loaded.state.players[loaded.state.acting_player].is_bot:
            self.deadlines[table_id] = self.now_plus(seconds=30)
        return snapshot

    async def advance(self, seconds: float) -> None:
        if hasattr(self.clock, "advance"):
            self.clock.advance(seconds)
        await self.tick()

    async def fire_timeout(self, table_id: str) -> RuntimeActionResult | None:
        loaded = self.runtime._tables.get(table_id) or await self.runtime.load(table_id)
        if loaded is None:
            return None
        key = (table_id, loaded.revision)
        if key in self._fired:
            return None
        self._fired.add(key)
        result = await self.runtime.timeout_current_actor(table_id, self.now())
        self.deadlines.pop(table_id, None)
        if result is not None:
            self.last_action = result.action
            self.action_count += 1
            if self.runtime._tables[table_id].state.terminal:
                await self.mark_terminal(table_id)
        return result

    async def mark_terminal(self, table_id: str) -> None:
        now = self.now()
        self.deadlines.pop(table_id, None)
        self.phases[table_id] = "result"
        self.result_clear_at[table_id] = now + timedelta(seconds=4)
        self.next_hand_at[table_id] = now + timedelta(seconds=7)
        self.public_state_has_cards = True

    async def finish_hand(self, table_id: str):
        result = await self.runtime.finish_and_settle(table_id)
        await self.mark_terminal(table_id)
        return result

    async def tick(self) -> None:
        now = self.now()
        for table_id, deadline in list(self.deadlines.items()):
            if deadline <= now:
                await self.fire_timeout(table_id)
        for table_id, clear_at in list(self.result_clear_at.items()):
            if self.phases.get(table_id) == "result" and clear_at <= now:
                self.phases[table_id] = "countdown"
                self.public_state_has_cards = False
        for table_id, next_at in list(self.next_hand_at.items()):
            if self.phases.get(table_id) == "countdown" and next_at <= now:
                await self.runtime.prepare_next_hand(table_id)
                await self.runtime.start_hand(table_id)
                self.new_hand_count += 1
                self.phases[table_id] = "active"
                self.result_clear_at.pop(table_id, None)
                self.next_hand_at.pop(table_id, None)
                self.public_state_has_cards = True
