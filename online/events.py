from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from online.schema import integrity_events


async def append_integrity_event(
    session: AsyncSession,
    *,
    event_type: str,
    table_id: str | None = None,
    hand_id: str | None = None,
    user_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    await session.execute(integrity_events.insert().values(
        id=uuid.uuid4().hex,
        table_id=table_id,
        hand_id=hand_id,
        user_id=user_id,
        event_type=event_type,
        public_payload_json=payload or {},
    ))
