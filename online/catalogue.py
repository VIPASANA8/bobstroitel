from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.schema import poker_tables, system_players, table_seats


DEFAULT_TABLES = (
    ("micro-a", "Micro A", 50, 100),
    ("micro-b", "Micro B", 50, 100),
    ("low-a", "Low A", 100, 200),
    ("low-b", "Low B", 100, 200),
    ("mid-a", "Mid A", 500, 1000),
    ("mid-b", "Mid B", 500, 1000),
)


@dataclass(frozen=True)
class TableSummary:
    id: str
    name: str
    scope: str
    small_blind_units: int
    big_blind_units: int
    min_buy_in_units: int
    max_buy_in_units: int
    max_seats: int
    occupied_count: int
    human_count: int
    system_count: int
    human_join_available: bool
    join_mode: str = "buy_in"

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


class Catalogue:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def seed_defaults(self) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                existing_tables = set(
                    (
                        await session.execute(
                            select(poker_tables.c.id).where(poker_tables.c.scope == "network")
                        )
                    ).scalars()
                )
                for table_id, name, small_blind, big_blind in DEFAULT_TABLES:
                    if table_id in existing_tables:
                        continue
                    await session.execute(poker_tables.insert().values(
                        id=table_id,
                        scope="network",
                        name=name,
                        small_blind_units=small_blind,
                        big_blind_units=big_blind,
                        min_buy_in_bb=40,
                        max_buy_in_bb=100,
                        max_seats=6,
                    ))

                existing_players = set(
                    (
                        await session.execute(select(system_players.c.id))
                    ).scalars()
                )
                difficulties = ("easy", "normal", "hard", "maximum")
                for number in range(1, 37):
                    player_id = f"system-{number:02d}"
                    if player_id in existing_players:
                        continue
                    await session.execute(system_players.insert().values(
                        id=player_id,
                        name=f"Room Player {number:02d}",
                        difficulty=difficulties[(number - 1) % len(difficulties)],
                        active=True,
                    ))

    async def list_tables(self, page: int = 1, per_page: int = 6) -> list[TableSummary]:
        page = max(1, page)
        per_page = max(1, min(per_page, 100))
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(poker_tables)
                    .where(poker_tables.c.scope == "network")
                    .order_by(poker_tables.c.big_blind_units, poker_tables.c.id)
                    .offset((page - 1) * per_page)
                    .limit(per_page)
                )
            ).mappings().all()
            return [await self._summary(session, row) for row in rows]

    async def quick_play(self, user_id: str, available_units: int) -> TableSummary:
        rows = await self.list_tables(page=1, per_page=100)
        affordable = [row for row in rows if row.min_buy_in_units <= available_units]
        if not affordable:
            raise LookupError("no affordable table")
        chosen = min(
            affordable,
            key=lambda row: (
                not row.human_join_available,
                row.big_blind_units,
                -row.occupied_count,
                row.id,
            ),
        )
        return replace(chosen, join_mode="buy_in" if chosen.human_join_available else "queue")

    async def _summary(self, session: AsyncSession, row) -> TableSummary:
        seats = (
            await session.execute(
                select(table_seats.c.occupant_kind, table_seats.c.state)
                .where(table_seats.c.table_id == row["id"])
            )
        ).all()
        active = [seat for seat in seats if seat.state != "empty" and seat.occupant_kind != "empty"]
        human_count = sum(seat.occupant_kind == "user" for seat in active)
        system_count = sum(seat.occupant_kind == "system" for seat in active)
        occupied_count = len(active)
        return TableSummary(
            id=row["id"],
            name=row["name"],
            scope=row["scope"],
            small_blind_units=row["small_blind_units"],
            big_blind_units=row["big_blind_units"],
            min_buy_in_units=row["big_blind_units"] * row["min_buy_in_bb"],
            max_buy_in_units=row["big_blind_units"] * row["max_buy_in_bb"],
            max_seats=row["max_seats"],
            occupied_count=occupied_count,
            human_count=human_count,
            system_count=system_count,
            human_join_available=occupied_count < row["max_seats"] or system_count > 0,
        )
