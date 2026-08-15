from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app.routers import auth, health, lobby, profiles, realtime
from online.auth import AuthService
from online.catalogue import Catalogue
from online.config import Settings
from online.database import create_database
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.seating import SeatingService
from online.schema import metadata, tenant_bots, tenants


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
EXPECTED_MIGRATION_REVISION = "20260814_0003"


async def _ensure_foundation(session_factory, settings: Settings) -> None:
    tenant_id = f"tenant-{settings.default_tenant_slug}"
    async with session_factory() as session:
        async with session.begin():
            tenant = (
                await session.execute(select(tenants).where(tenants.c.slug == settings.default_tenant_slug))
            ).mappings().first()
            if tenant is None:
                await session.execute(tenants.insert().values(
                    id=tenant_id,
                    slug=settings.default_tenant_slug,
                    name="Poker8",
                    status="active",
                ))
            else:
                tenant_id = tenant["id"]
            if settings.default_bot_token:
                bot = (
                    await session.execute(
                        select(tenant_bots.c.id).where(
                            tenant_bots.c.tenant_id == tenant_id,
                            tenant_bots.c.secret_ref == "POKER8_DEFAULT_BOT_TOKEN",
                        )
                    )
                ).scalar_one_or_none()
                if bot is None:
                    await session.execute(tenant_bots.insert().values(
                        id=f"bot-{settings.default_tenant_slug}",
                        tenant_id=tenant_id,
                        telegram_bot_id=0,
                        secret_ref="POKER8_DEFAULT_BOT_TOKEN",
                        enabled=True,
                    ))


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, session_factory = create_database(settings.database_url)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.expected_migration_revision = EXPECTED_MIGRATION_REVISION
        if settings.environment == "development":
            async with engine.begin() as connection:
                await connection.run_sync(metadata.create_all)
        else:
            async with engine.connect() as connection:
                revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
                if revision != EXPECTED_MIGRATION_REVISION:
                    raise RuntimeError("database migration revision mismatch")

        await _ensure_foundation(session_factory, settings)
        ledger = PlayLedger(session_factory)
        await ledger.ensure_faucet()
        catalogue = Catalogue(session_factory)
        await catalogue.seed_defaults()
        app.state.ledger = ledger
        app.state.catalogue = catalogue
        app.state.runtime = TableRuntimeManager(session_factory, ledger)
        app.state.seating = SeatingService(session_factory, ledger)
        await app.state.runtime.restore_all()
        app.state.connection_hub = realtime.ConnectionHub()
        app.state.tenant_hosts = {}
        app.state.auth_service = AuthService(
            session_factory,
            ({settings.default_tenant_slug: settings.default_bot_token}
             if settings.default_bot_token else {}),
            session_ttl_seconds=settings.session_ttl_seconds,
            telegram_auth_max_age_seconds=settings.telegram_auth_max_age_seconds,
        )
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Poker8 Online", version="1.0.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(auth.router)
    app.include_router(lobby.router)
    app.include_router(profiles.router)
    app.include_router(health.router)
    app.include_router(realtime.router)

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    return app
