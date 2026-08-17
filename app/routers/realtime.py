from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.dependencies import AuthenticatedUser
from online.schema import auth_sessions, users
from online.runtime import StaleRevision, TablePaused


router = APIRouter(tags=["realtime"])


class ConnectionHub:
    def __init__(self) -> None:
        self.connections: dict[str, dict[WebSocket, AuthenticatedUser]] = defaultdict(dict)

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

    async def broadcast(self, table_id: str, runtime, reason: str = "state_changed") -> None:
        """Push the table state to every viewer, each with their own hole cards."""
        for socket, viewer in list(self.connections.get(table_id, {}).items()):
            try:
                snapshot = await runtime.public_snapshot(table_id, viewer.user_id)
                await socket.send_json(_snapshot_message(snapshot, reason))
            except Exception:
                continue

    async def broadcast_json(self, table_id: str, message: dict) -> None:
        for socket in list(self.connections.get(table_id, {})):
            try:
                await socket.send_json(message)
            except Exception:
                continue


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


@router.websocket("/ws/tables/{table_id}")
async def table_socket(websocket: WebSocket, table_id: str) -> None:
    user = await _authenticate(websocket)
    if user is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub: ConnectionHub = websocket.app.state.connection_hub
    hub.add(table_id, websocket, user)
    websocket.state.user_id = user.user_id
    await websocket.app.state.seating.reconnect(user.user_id, table_id)
    try:
        snapshot = await websocket.app.state.runtime.public_snapshot(table_id, user.user_id)
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
                if previous == 1 and hasattr(websocket.app.state, "seating"):
                    await websocket.app.state.seating.mark_disconnected(
                        user.user_id, table_id, datetime.now(timezone.utc)
                    )
                await websocket.send_json({"type": "presence", "status": "disconnected", "remaining": max(0, previous - 1)})
                await websocket.close(code=1000)
                return
            if message_type == "resync":
                snapshot = await websocket.app.state.runtime.public_snapshot(table_id, user.user_id)
                await websocket.send_json(_snapshot_message(snapshot, "resync"))
                continue
            if message_type != "action":
                await websocket.send_json({"type": "command_rejected", "reason": "unknown_message"})
                continue
            try:
                await websocket.app.state.runtime.action(
                    table_id=table_id,
                    user_id=user.user_id,
                    command_id=str(message["command_id"]),
                    expected_revision=int(message["expected_revision"]),
                    action=str(message["action"]),
                    amount_units=int(message.get("amount_units", 0)),
                )
                await hub.broadcast(table_id, websocket.app.state.runtime)
            except StaleRevision as error:
                snapshot = await websocket.app.state.runtime.public_snapshot(table_id, user.user_id)
                await websocket.send_json(_snapshot_message(snapshot, "stale_revision"))
            except TablePaused:
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
        if previous == 1 and hasattr(websocket.app.state, "seating"):
            await websocket.app.state.seating.mark_disconnected(user.user_id, table_id, datetime.now(timezone.utc))
