from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.schema import chat_messages, users


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
    # Who to put in front of the message. Without it the client had nothing to
    # show but user_id, so every line in the chat was signed with a
    # thirty-two character hex string instead of a person's name.
    display_name: str = ""


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
        # Newlines are allowed now -- a fenced code block needs them, and the
        # renderer turns them into <br>. Every other control character stays
        # out. The cap is 1000 rather than 300 because the markers count
        # against it: ``` around eight lines is most of the old limit.
        if not text or len(text) > 1000 or any(ord(char) < 32 and char != chr(10) for char in text):
            raise ChatError("message must contain 1–1000 printable characters")
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
                name = (await session.execute(
                    select(users.c.display_name).where(users.c.id == user_id)
                )).scalar_one_or_none()
                message = ChatMessage(
                    uuid.uuid4().hex, table_id, user_id, text, current, name or "Игрок")
                await session.execute(chat_messages.insert().values(
                    id=message.id, table_id=table_id, user_id=user_id, text=text, created_at=current,
                ))
                return message

    async def recent(self, table_id: str, limit: int = 50) -> list[ChatMessage]:
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(chat_messages, users.c.display_name)
                    .select_from(
                        chat_messages.join(users, users.c.id == chat_messages.c.user_id, isouter=True)
                    )
                    .where(chat_messages.c.table_id == table_id)
                    .order_by(desc(chat_messages.c.created_at), desc(chat_messages.c.id))
                    .limit(max(1, min(limit, 50)))
                )
            ).mappings().all()
        return [
            ChatMessage(
                row["id"], row["table_id"], row["user_id"], row["text"], row["created_at"],
                # Outer join: a message outlives the account that wrote it.
                row["display_name"] or "Игрок",
            )
            for row in reversed(rows)
        ]

    @staticmethod
    def _datetime(value: datetime | int | float | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
