import asyncio

from sqlalchemy import select

from online.schema import tenants, users


def test_one_telegram_identity_is_global(db_session_factory):
    async def run():
        async with db_session_factory() as session:
            await session.execute(tenants.insert().values(id="t1", slug="poker8", name="Poker8"))
            await session.execute(users.insert().values(
                id="u1", telegram_user_id=777, display_name="One", acquisition_tenant_id="t1"
            ))
            await session.commit()
            rows = (await session.execute(select(users.c.id))).all()
            assert rows == [("u1",)]

    asyncio.run(run())
