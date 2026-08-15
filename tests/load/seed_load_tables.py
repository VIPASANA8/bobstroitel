from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select

from online.database import create_database
from online.schema import auth_sessions, metadata, poker_tables, system_players, tenants, users


DEFAULT_DATABASE_URL = "postgresql+psycopg://poker8:poker8@127.0.0.1:5433/poker8_test"


def parse_args():
    parser = argparse.ArgumentParser(description="Seed test-only Poker8 WebSocket load fixtures")
    parser.add_argument("--database-url", default=os.environ.get("POKER8_TEST_DATABASE_URL", DEFAULT_DATABASE_URL))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--connections", type=int, default=100)
    return parser.parse_args()


async def seed(args) -> int:
    if os.environ.get("POKER8_ENV") != "test":
        raise SystemExit("refusing to seed load tables unless POKER8_ENV=test")
    if args.tables < 1 or args.connections < 1:
        raise SystemExit("tables and connections must be positive")

    engine, session_factory = create_database(args.database_url)
    now = datetime.now(timezone.utc)
    manifest = []
    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        async with session_factory() as session:
            async with session.begin():
                tenant = (await session.execute(select(tenants).where(tenants.c.slug == "poker8"))).mappings().first()
                if tenant is None:
                    await session.execute(tenants.insert().values(
                        id="tenant-poker8", slug="poker8", name="Poker8", status="active",
                        branding_json={}, support_url=None,
                    ))
                    tenant_id = "tenant-poker8"
                else:
                    tenant_id = tenant["id"]

                for table_number in range(1, args.tables + 1):
                    table_id = f"load-{table_number:03d}"
                    existing = await session.execute(select(poker_tables.c.id).where(poker_tables.c.id == table_id))
                    if existing.scalar_one_or_none() is None:
                        blind = 50 if table_number <= max(1, args.tables // 2) else 100
                        await session.execute(poker_tables.insert().values(
                            id=table_id, tenant_id=tenant_id, scope="network", name=f"Load {table_number:02d}",
                            small_blind_units=blind, big_blind_units=blind * 2,
                            min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
                        ))
                    for seat in range(6):
                        player_id = f"load-{table_number:03d}-bot-{seat + 1}"
                        existing = await session.execute(select(system_players.c.id).where(system_players.c.id == player_id))
                        if existing.scalar_one_or_none() is None:
                            await session.execute(system_players.insert().values(
                                id=player_id, name=f"Load Bot {table_number:02d}/{seat + 1}",
                                difficulty="normal", active=True,
                            ))

                for index in range(args.connections):
                    telegram_id = 900_000_000 + index
                    user_id = f"load-user-{index + 1:03d}"
                    existing_user = await session.execute(
                        select(users.c.id).where(users.c.id == user_id)
                    )
                    if existing_user.scalar_one_or_none() is None:
                        await session.execute(users.insert().values(
                            id=user_id, telegram_user_id=telegram_id,
                            display_name=f"Load User {index + 1:03d}",
                            acquisition_tenant_id=tenant_id, created_at=now, updated_at=now,
                        ))
                    token = secrets.token_urlsafe(32)
                    await session.execute(auth_sessions.insert().values(
                        id=uuid.uuid4().hex, user_id=user_id, tenant_id=tenant_id,
                        token_hash=hashlib.sha256(token.encode()).hexdigest(),
                        expires_at=now + timedelta(hours=2), created_at=now,
                    ))
                    manifest.append({
                        "table_id": f"load-{(index % args.tables) + 1:03d}",
                        "cookie": f"poker8_session={token}",
                    })
        with open(args.manifest, "w", encoding="utf-8") as output:
            json.dump({"base_url": "http://127.0.0.1:8000", "sessions": manifest}, output, indent=2)
        print(json.dumps({"manifest": args.manifest, "tables": args.tables, "connections": args.connections}))
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    return asyncio.run(seed(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
