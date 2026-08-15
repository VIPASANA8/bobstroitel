from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bots.multiway import MultiwayBot
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
from poker.models import ActionType, GameState


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


class TableRuntimeManager:
    """Authoritative, durable command processor for one or more poker tables."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ledger: PlayLedger,
        engine: PokerEngine | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.ledger = ledger
        self.engine = engine or PokerEngine()
        self._locks: dict[str, asyncio.Lock] = {}
        self._tables: dict[str, _LoadedTable] = {}
        self._action_counts: dict[str, int] = {}

    def _lock(self, table_id: str) -> asyncio.Lock:
        return self._locks.setdefault(table_id, asyncio.Lock())

    async def load(self, table_id: str) -> _LoadedTable | None:
        async with self._lock(table_id):
            return await self._load_locked(table_id)

    async def start_hand(self, table_id: str, *, button_seat: int | None = None) -> dict[str, Any]:
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
                    state = self.engine.new_hand(
                        engine_seats,
                        button_seat=seats[0]["seat_no"] if button_seat is None else button_seat,
                    )
                    payload = serialize_state(state)
                    revision = 1
                    runtime_values = {
                        "revision": revision,
                        "phase": "active",
                        "private_state_json": payload,
                        "public_payload_json": state.to_dict(),
                        "paused_reason": None,
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
                            start_stack_units=round(state.starting_stacks[participant_id] * table["big_blind_units"]),
                        ))
                    await append_integrity_event(
                        session, event_type="hand_started", table_id=table_id, hand_id=state.hand_id,
                        payload={"revision": revision, "players": len(state.players)},
                    )
                    loaded = _LoadedTable(revision, "active", state)
                    self._tables[table_id] = loaded
                    self._action_counts[table_id] = 0
                    return self._snapshot_for_state(loaded, None)

    async def public_snapshot(self, table_id: str, viewer_user_id: str | None) -> dict[str, Any]:
        loaded = self._tables.get(table_id)
        if loaded is None:
            loaded = await self._load_locked(table_id)
        if loaded is None:
            raise RuntimeErrorBase("table runtime not found")
        participant_id = await self._participant_for_user(table_id, viewer_user_id) if viewer_user_id else None
        return self._snapshot_for_state(loaded, participant_id)

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
                try:
                    self.engine.apply_action(loaded.state, participant_id, engine_action, engine_amount)
                    loaded.revision += 1
                    snapshot = self._snapshot_for_state(loaded, participant_id)
                    result = RuntimeActionResult(
                        command_id=command_id,
                        table_id=table_id,
                        revision=loaded.revision,
                        action=engine_action.value,
                        legal_actions=legal_before,
                        snapshot=snapshot,
                    )
                    await self._persist_action(session, loaded, result, expected_revision, user_id, amount_units)
                    await session.commit()
                    self._action_counts[table_id] = self._action_counts.get(table_id, 0) + 1
                    return result
                except Exception as error:
                    loaded.state = deserialize_state(before)
                    loaded.revision = max(0, loaded.revision - 1)
                    await session.rollback()
                    await self._pause_after_failure(table_id, loaded, str(error))
                    raise

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
            decision = bot.decide(loaded.state, actor)
            if decision.action not in legal:
                decision.action = legal[0]
            async with self.session_factory() as session:
                table = await self._table(session, table_id)
                amount_units = round(decision.amount * table["big_blind_units"])
            user_id = actor
            command_id = f"system:{loaded.state.hand_id}:{loaded.revision}"
            # Re-enter through action without deadlocking this table lock.
        result = await self.action(
            table_id,
            user_id,
            command_id,
            loaded.revision,
            decision.action.value,
            amount_units,
        )
        return RuntimeActionResult(
            result.command_id, result.table_id, result.revision, result.action, [item.value for item in legal], result.snapshot
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
                    transfers: dict[tuple[str, str, str], int] = {}
                    user_start_total = 0
                    for participant_id, player in loaded.state.players.items():
                        seat = by_participant[participant_id]
                        start_units = round(loaded.state.starting_stacks[participant_id] * table["big_blind_units"])
                        end_units = round(player.stack * table["big_blind_units"])
                        if seat["occupant_kind"] == "user":
                            user_start_total += start_units
                            transfers[("user", participant_id, "wallet")] = end_units
                        else:
                            transfers[("system", participant_id, "escrow")] = end_units - start_units
                        await session.execute(
                            update(hand_players)
                            .where(
                                hand_players.c.hand_id == loaded.state.hand_id,
                                hand_players.c.participant_id == participant_id,
                            )
                            .values(end_stack_units=end_units, net_units=end_units - start_units, shown=not player.folded)
                        )
                        await session.execute(
                            update(table_seats).where(table_seats.c.id == seat["id"]).values(stack_units=end_units)
                        )
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
                    transfers[("table", table_id, "escrow")] = -user_start_total
                    settlement = await self.ledger.settle_hand_transfers(
                        loaded.state.hand_id, transfers, session=session
                    )
                    completed_at = datetime.now(timezone.utc)
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
                            updated_at=completed_at,
                        )
                    )
                    await append_integrity_event(
                        session, event_type="hand_settled", table_id=table_id,
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
            self._tables[row["table_id"]] = _LoadedTable(row["revision"], row["phase"], state)
            self._locks.setdefault(row["table_id"], asyncio.Lock())
            restored.append(row["table_id"])
        return restored

    async def _persist_action(
        self,
        session: AsyncSession,
        loaded: _LoadedTable,
        result: RuntimeActionResult,
        expected_revision: int,
        user_id: str,
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
                updated_at=datetime.now(timezone.utc),
            )
        )
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
                await append_integrity_event(
                    session, event_type="runtime_paused", table_id=table_id,
                    hand_id=loaded.state.hand_id, payload={"reason": reason[:200]},
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
        loaded = _LoadedTable(row["revision"], row["phase"], deserialize_state(row["private_state_json"]))
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

    def _snapshot_for_state(self, loaded: _LoadedTable, participant_id: str | None) -> dict[str, Any]:
        state = loaded.state.to_dict(viewer_player_id=participant_id)
        for player in state["players"].values():
            player.pop("difficulty", None)
        legal = [item.value for item in self.engine.legal_actions(loaded.state, participant_id)] if participant_id else []
        state.update({
            "phase": loaded.phase,
            "revision": loaded.revision,
            "legal_actions": legal,
            "action_deadline": None,
            "occupancy": len(loaded.state.players),
        })
        return state

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
