from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.dependencies import AuthenticatedUser
from cash.access import CashAccessDenied, ensure_cash_access
from cash.game import CashCommandConflict, CashIntegrityError
from online.catalogue import CASH_USDT, PLAY
from online.schema import auth_sessions, poker_tables, users
from online.runtime import StaleRevision, TablePaused
from poker.models import ActionType


router = APIRouter(tags=["realtime"])


class ConnectionHub:
    def __init__(self, seating=None) -> None:
        self.connections: dict[str, dict[WebSocket, AuthenticatedUser]] = defaultdict(dict)
        # Needed to release a seat whose socket turns out to be dead; see
        # _drop_dead. Optional so tests can build a bare hub.
        self.seating = seating

    def add(self, table_id: str, socket: WebSocket, user: AuthenticatedUser) -> None:
        self.connections[table_id][socket] = user

    def remove(self, table_id: str, socket: WebSocket) -> int:
        sockets = self.connections.get(table_id, {})
        sockets.pop(socket, None)
        if not sockets:
            self.connections.pop(table_id, None)
        return sum(1 for user in sockets.values() if user.user_id == getattr(socket.state, "user_id", None))

    def user_connections(self, table_id: str, user_id: str) -> int:
        return sum(1 for user in self.connections.get(table_id, {}).values() if user.user_id == user_id)

    async def _drop_dead(
        self, table_id: str, socket: WebSocket, *, manage_seating: bool = True, runtime=None,
    ) -> None:
        """Forget a socket whose peer has gone, and start its seat's hold.

        A failed send is the only signal a vanished client gives: nothing pings
        it back, and receive_json on a half-open connection can block for as
        long as the OS keeps it. Swallowing that failure left the socket in the
        hub forever, so mark_disconnected never ran -- the seat stayed `seated`,
        the table kept timing the player out hand after hand, and the lobby
        still offered them an "active session" hours after they closed the app.

        Marking them disconnected only starts the 30s hold, so a client that
        merely hit a transient send error reconnects straight back into its
        seat, exactly like any other reconnect.
        """
        viewer = self.connections.get(table_id, {}).get(socket)
        if viewer is None:
            return
        self.connections.get(table_id, {}).pop(socket, None)
        if not self.connections.get(table_id):
            self.connections.pop(table_id, None)
        if not manage_seating:
            if runtime is not None and not self.user_connections(table_id, viewer.user_id):
                try:
                    await _leave_cash(runtime, table_id, viewer.user_id)
                except Exception:
                    pass
            return
        if self.seating is None or self.user_connections(table_id, viewer.user_id):
            return
        try:
            await self.seating.mark_disconnected(viewer.user_id, table_id, datetime.now(timezone.utc))
        except Exception:
            pass

    async def broadcast(
        self, table_id: str, runtime, reason: str = "state_changed", *, manage_seating: bool = True,
    ) -> None:
        """Push the table state to every viewer, each with their own hole cards."""
        for socket, viewer in list(self.connections.get(table_id, {}).items()):
            try:
                snapshot = await runtime.public_snapshot(table_id, viewer.user_id)
            except Exception:
                # A table-side failure says nothing about this socket.
                continue
            try:
                await socket.send_json(_snapshot_message(snapshot, reason))
            except Exception:
                await self._drop_dead(
                    table_id, socket, manage_seating=manage_seating, runtime=runtime,
                )

    async def broadcast_json(self, table_id: str, message: dict) -> None:
        for socket in list(self.connections.get(table_id, {})):
            try:
                await socket.send_json(message)
            except Exception:
                await self._drop_dead(table_id, socket)


async def _authenticate(websocket: WebSocket) -> AuthenticatedUser | None:
    token = websocket.cookies.get(websocket.app.state.settings.session_cookie_name)
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    async with websocket.app.state.session_factory() as session:
        row = (
            await session.execute(
                select(
                    auth_sessions.c.user_id,
                    auth_sessions.c.tenant_id,
                    users.c.telegram_user_id,
                    users.c.display_name,
                    auth_sessions.c.auth_method,
                )
                .join(users, users.c.id == auth_sessions.c.user_id)
                .where(
                    auth_sessions.c.token_hash == token_hash,
                    auth_sessions.c.revoked_at.is_(None),
                    auth_sessions.c.expires_at > now,
                )
            )
        ).mappings().first()
    return AuthenticatedUser(**row) if row else None


def _snapshot_message(snapshot: dict, reason: str) -> dict:
    return {
        "type": "snapshot",
        "reason": reason,
        "revision": snapshot["revision"],
        "state": snapshot,
    }


async def _leave_cash(runtime, table_id: str, user_id: str) -> None:
    """Fold a disconnected actor, then preserve/release escrow via leave()."""
    snapshot = await runtime.public_snapshot(table_id, user_id)
    if snapshot.get("acting_player") == user_id and "fold" in snapshot.get("legal_actions", []):
        try:
            await runtime.act(
                table_id, user_id, ActionType.FOLD, amount_micros=0,
                command_id=f"disconnect-fold:{uuid4().hex}",
                expected_revision=snapshot["revision"],
            )
        except CashCommandConflict:
            pass
    await runtime.leave(user_id, table_id, f"disconnect:{uuid4().hex}")


@router.websocket("/ws/tables/{table_id}")
async def table_socket(websocket: WebSocket, table_id: str) -> None:
    user = await _authenticate(websocket)
    if user is None:
        await websocket.close(code=4401)
        return
    async with websocket.app.state.session_factory() as session:
        table = (await session.execute(select(
            poker_tables.c.asset, poker_tables.c.chip_micros,
        ).where(poker_tables.c.id == table_id))).mappings().one_or_none()
    if table is None:
        await websocket.close(code=4404)
        return
    asset = table["asset"]
    if asset == CASH_USDT:
        try:
            ensure_cash_access(
                websocket.app.state.settings.cash_mode, user.auth_method,
                user.telegram_user_id, getattr(websocket.app.state.settings, "cash_allowlist", ()),
            )
        except CashAccessDenied:
            await websocket.close(code=4403)
            return
    elif asset != PLAY:
        await websocket.close(code=4409)
        return
    await websocket.accept()
    hub: ConnectionHub = websocket.app.state.connection_hub
    hub.add(table_id, websocket, user)
    websocket.state.user_id = user.user_id
    cash = asset == CASH_USDT
    runtime = websocket.app.state.cash_game if cash else websocket.app.state.runtime
    if not cash:
        await websocket.app.state.seating.reconnect(user.user_id, table_id)
    try:
        snapshot = await runtime.public_snapshot(table_id, user.user_id)
        await websocket.send_json(_snapshot_message(snapshot, "connected"))
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "ping":
                await websocket.send_json({"type": "pong", "sent_at": message.get("sent_at")})
                continue
            if message_type == "disconnect":
                websocket.state.disconnect_handled = True
                previous = hub.user_connections(table_id, user.user_id)
                hub.connections.get(table_id, {}).pop(websocket, None)
                if cash and previous == 1:
                    await _leave_cash(runtime, table_id, user.user_id)
                elif previous == 1 and hasattr(websocket.app.state, "seating"):
                    await websocket.app.state.seating.mark_disconnected(
                        user.user_id, table_id, datetime.now(timezone.utc)
                    )
                await websocket.send_json({"type": "presence", "status": "disconnected", "remaining": max(0, previous - 1)})
                await websocket.close(code=1000)
                return
            if message_type == "resync":
                snapshot = await runtime.public_snapshot(table_id, user.user_id)
                await websocket.send_json(_snapshot_message(snapshot, "resync"))
                continue
            if message_type != "action":
                await websocket.send_json({"type": "command_rejected", "reason": "unknown_message"})
                continue
            try:
                if cash:
                    await runtime.act(
                        table_id, user.user_id, ActionType(str(message["action"])),
                        amount_micros=int(message.get("amount_units", 0)) * table["chip_micros"],
                        command_id=str(message["command_id"]),
                        expected_revision=int(message["expected_revision"]),
                    )
                    await hub.broadcast(table_id, runtime, manage_seating=False)
                else:
                    await runtime.action(
                        table_id=table_id,
                        user_id=user.user_id,
                        command_id=str(message["command_id"]),
                        expected_revision=int(message["expected_revision"]),
                        action=str(message["action"]),
                        amount_units=int(message.get("amount_units", 0)),
                    )
                    await hub.broadcast(table_id, runtime)
            except StaleRevision:
                snapshot = await runtime.public_snapshot(table_id, user.user_id)
                await websocket.send_json(_snapshot_message(snapshot, "stale_revision"))
            except CashCommandConflict as error:
                if "stale cash revision" in str(error):
                    snapshot = await runtime.public_snapshot(table_id, user.user_id)
                    await websocket.send_json(_snapshot_message(snapshot, "stale_revision"))
                else:
                    await websocket.send_json({"type": "command_rejected", "reason": str(error)})
            except (TablePaused, CashIntegrityError):
                await websocket.send_json({"type": "command_rejected", "reason": "table_paused"})
            except Exception as error:
                await websocket.send_json({"type": "command_rejected", "reason": str(error)})
    except WebSocketDisconnect:
        pass
    finally:
        if getattr(websocket.state, "disconnect_handled", False):
            return
        previous = hub.user_connections(table_id, user.user_id)
        hub.connections.get(table_id, {}).pop(websocket, None)
        if cash and previous == 1:
            try:
                await _leave_cash(runtime, table_id, user.user_id)
            except Exception:
                pass
        elif previous == 1 and hasattr(websocket.app.state, "seating"):
            await websocket.app.state.seating.mark_disconnected(user.user_id, table_id, datetime.now(timezone.utc))
