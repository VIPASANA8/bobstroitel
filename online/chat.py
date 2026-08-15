from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.schema import chat_messages


class ChatError(ValueError):
    pass


class ChatRateLimited(ChatError):
    pass


@dataclass(frozen=True)
class ChatMessage:
    id: str
    table_id: str
    user_id: str
    text: str
    created_at: datetime


class ChatService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def post(
        self,
        table_id: str,
        user_id: str,
        text: str,
        *,
        now: datetime | int | float | None = None,
        enforce_rate_limit: bool = True,
    ) -> ChatMessage:
        text = text.strip()
        if not text or len(text) > 300 or any(ord(char) < 32 for char in text):
            raise ChatError("message must contain 1–300 printable characters")
        current = self._datetime(now)
        async with self.session_factory() as session:
            async with session.begin():
                if enforce_rate_limit:
                    recent = (
                        await session.execute(
                            select(chat_messages.c.id)
                            .where(
                                chat_messages.c.table_id == table_id,
                                chat_messages.c.user_id == user_id,
                                chat_messages.c.created_at >= current - timedelta(seconds=10),
                            )
                        )
                    ).all()
                    if len(recent) >= 5:
                        raise ChatRateLimited("five messages per ten seconds")
                message = ChatMessage(uuid.uuid4().hex, table_id, user_id, text, current)
                await session.execute(chat_messages.insert().values(
                    id=message.id, table_id=table_id, user_id=user_id, text=text, created_at=current,
                ))
                return message

    async def recent(self, table_id: str, limit: int = 50) -> list[ChatMessage]:
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(chat_messages)
                    .where(chat_messages.c.table_id == table_id)
                    .order_by(desc(chat_messages.c.created_at), desc(chat_messages.c.id))
                    .limit(max(1, min(limit, 50)))
                )
            ).mappings().all()
        return [
            ChatMessage(row["id"], row["table_id"], row["user_id"], row["text"], row["created_at"])
            for row in reversed(rows)
        ]

    @staticmethod
    def _datetime(value: datetime | int | float | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
