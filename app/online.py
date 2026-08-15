from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app.routers import auth, chat, config, health, lobby, profiles, realtime, tables
from online.auth import AuthService
from online.catalogue import Catalogue
from online.config import Settings
from online.coordinator import OnlineCoordinator
from online.database import create_database
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.seating import SeatingService
from online.chat import ChatService
from online.history import HistoryService
from online.schema import metadata, tenant_bots, tenants


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
EXPECTED_MIGRATION_REVISION = "20260814_0004"


async def _ensure_foundation(session_factory, settings: Settings) -> None:
    async with session_factory() as session:
        async with session.begin():
            for slug, config in settings.tenant_configs.items():
                tenant_id = f"tenant-{slug}"
                tenant = (await session.execute(select(tenants).where(tenants.c.slug == slug))).mappings().first()
                if tenant is None:
                    await session.execute(tenants.insert().values(
                        id=tenant_id, slug=slug, name=config["name"], status="active",
                        branding_json=config["branding"], support_url=config["support_url"],
                    ))
                else:
                    tenant_id = tenant["id"]
                if config.get("token"):
                    bot = (await session.execute(select(tenant_bots.c.id).where(
                        tenant_bots.c.tenant_id == tenant_id, tenant_bots.c.secret_ref == f"POKER8_{slug.upper()}_BOT_TOKEN",
                    ))).scalar_one_or_none()
                    if bot is None:
                        await session.execute(tenant_bots.insert().values(
                            id=f"bot-{slug}", tenant_id=tenant_id, telegram_bot_id=0,
                            secret_ref=f"POKER8_{slug.upper()}_BOT_TOKEN", enabled=True,
                        ))


def create_app(
    settings: Settings,
    *,
    fixture: Callable[[FastAPI], Awaitable[None]] | None = None,
) -> FastAPI:
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
        app.state.chat = ChatService(session_factory)
        app.state.history = HistoryService(session_factory)
        app.state.runtime = TableRuntimeManager(session_factory, ledger)
        app.state.seating = SeatingService(session_factory, ledger)
        await app.state.runtime.restore_all()
        if fixture is not None:
            await fixture(app)
        app.state.coordinator = OnlineCoordinator(app.state.runtime, app.state.seating, catalogue)
        app.state.coordinator_task = None
        if settings.coordinator_enabled:
            app.state.coordinator_task = asyncio.create_task(app.state.coordinator.run())
        app.state.restore_completed = True
        app.state.connection_hub = realtime.ConnectionHub()
        app.state.tenant_hosts = {
            host.lower(): slug
            for slug, config in settings.tenant_configs.items()
            for host in config.get("hosts", [])
        }
        tenant_tokens = {
            slug: str(config["token"])
            for slug, config in settings.tenant_configs.items()
            if config.get("token")
        }
        app.state.auth_service = AuthService(
            session_factory,
            tenant_tokens,
            session_ttl_seconds=settings.session_ttl_seconds,
            telegram_auth_max_age_seconds=settings.telegram_auth_max_age_seconds,
        )
        try:
            yield
        finally:
            if app.state.coordinator_task is not None:
                await app.state.coordinator.stop()
                app.state.coordinator_task.cancel()
                try:
                    await app.state.coordinator_task
                except asyncio.CancelledError:
                    pass
            await engine.dispose()

    app = FastAPI(title="Poker8 Online", version="1.0.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(auth.router)
    app.include_router(lobby.router)
    app.include_router(profiles.router)
    app.include_router(health.router)
    app.include_router(realtime.router)
    app.include_router(tables.router)
    app.include_router(chat.router)
    app.include_router(config.router)

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "lobby.html")

    @app.get("/table")
    async def table_page():
        return FileResponse(STATIC_DIR / "index.html")

    return app
