from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.schema import hand_players, hands, poker_tables, system_players, users


LEVEL_THRESHOLDS = (0, 10, 50, 100, 200, 500)


@dataclass(frozen=True)
class HandParticipantRecord:
    participant_id: str
    system_player_id: str | None
    seat_no: int
    net_units: int
    hole_cards: list[str] = field(default_factory=list)
    shown: bool = False

    @property
    def user_id(self) -> str | None:
        return None if self.system_player_id else self.participant_id


@dataclass(frozen=True)
class HandRecord:
    hand_id: str
    table_id: str
    participants: list[HandParticipantRecord]
    board: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProfileStats:
    user_id: str
    hands_played: int
    wins: int
    level: int


class HistoryService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def record(self, hand: HandRecord) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                exists = (
                    await session.execute(select(hands.c.id).where(hands.c.id == hand.hand_id))
                ).scalar_one_or_none()
                if not exists:
                    await session.execute(hands.insert().values(
                        id=hand.hand_id,
                        table_id=hand.table_id,
                        revision_started=0,
                        button_seat=hand.participants[0].seat_no if hand.participants else 0,
                        board_json=hand.board,
                        terminal=True,
                        result_json={"terminal": True},
                    ))
                    for participant in hand.participants:
                        await session.execute(hand_players.insert().values(
                            hand_id=hand.hand_id,
                            participant_id=participant.participant_id,
                            user_id=participant.user_id,
                            system_player_id=participant.system_player_id,
                            seat_no=participant.seat_no,
                            position="",
                            start_stack_units=0,
                            end_stack_units=participant.net_units,
                            hole_cards_json=participant.hole_cards,
                            shown=participant.shown,
                            net_units=participant.net_units,
                        ))
                        if participant.user_id:
                            await session.execute(
                                update(users)
                                .where(users.c.id == participant.user_id)
                                .values(
                                    hands_played=users.c.hands_played + 1,
                                    wins=users.c.wins + (1 if participant.net_units > 0 else 0),
                                )
                            )
                        elif participant.system_player_id:
                            await session.execute(
                                update(system_players)
                                .where(system_players.c.id == participant.system_player_id)
                                .values(
                                    hands_played=system_players.c.hands_played + 1,
                                    wins=system_players.c.wins + (1 if participant.net_units > 0 else 0),
                                )
                            )

    async def profile(self, user_id: str) -> ProfileStats:
        async with self.session_factory() as session:
            row = (
                await session.execute(select(users).where(users.c.id == user_id))
            ).mappings().first()
        if row is None:
            raise ValueError("user not found")
        return ProfileStats(
            user_id=user_id,
            hands_played=row["hands_played"],
            wins=row["wins"],
            level=self.level_for(row["wins"]),
        )

    async def last_hands(
        self, user_id: str, limit: int = 20, asset: str | None = None,
    ) -> list[dict[str, Any]]:
        """Practice hands and cash hands are separate histories -- the money
        they are counted in is not the same money. `asset` picks one; without
        it the caller gets both, as before."""
        async with self.session_factory() as session:
            query = (
                select(hand_players.c.hand_id, hands.c.completed_at, hands.c.started_at)
                .join(hands, hands.c.id == hand_players.c.hand_id)
                .join(poker_tables, poker_tables.c.id == hands.c.table_id)
                .where(hand_players.c.user_id == user_id)
            )
            if asset is not None:
                query = query.where(poker_tables.c.asset == asset)
            hand_ids = (
                await session.execute(
                    query.order_by(hands.c.completed_at.desc(), hands.c.started_at.desc())
                    .limit(max(1, min(limit, 20)))
                )
            ).all()
            output = []
            for hand_id, completed_at, started_at in hand_ids:
                rows = (
                    await session.execute(
                        select(hand_players).where(hand_players.c.hand_id == hand_id).order_by(hand_players.c.seat_no)
                    )
                ).mappings().all()
                players = []
                for row in rows:
                    you = row["user_id"] == user_id
                    visible = you or bool(row["shown"])
                    players.append({
                        # A shown opponent's cards are visible too, so "has
                        # hole_cards" never identified the viewer -- which left
                        # the history unable to say whose result it was, and it
                        # printed a hand id and a player count instead.
                        "you": you,
                        "participant_id": row["participant_id"],
                        "seat_no": row["seat_no"],
                        "net_units": row["net_units"],
                        "net_micros": row["net_micros"],
                        "hole_cards": list(row["hole_cards_json"] or []) if visible else None,
                    })
                output.append({"hand_id": hand_id, "completed_at": completed_at, "started_at": started_at, "players": players})
            return output

    @staticmethod
    def level_for(wins: int) -> int:
        return max(index for index, threshold in enumerate(LEVEL_THRESHOLDS) if wins >= threshold)
