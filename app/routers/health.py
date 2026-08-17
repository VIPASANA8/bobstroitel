from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select, text

from online.schema import integrity_events, poker_tables, table_runtimes, table_seats


router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live():
    return {"status": "live"}


@router.get("/health/ready")
async def ready(request: Request):
    try:
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            if request.app.state.settings.environment == "production":
                revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
                if revision != request.app.state.expected_migration_revision:
                    raise RuntimeError("migration revision mismatch")
            if not getattr(request.app.state, "restore_completed", True):
                raise RuntimeError("runtime restore is incomplete")
            runtimes = getattr(request.app.state, "runtime", None)
            if runtimes and any(table.phase == "paused" for table in runtimes._tables.values()):
                raise RuntimeError("a table runtime is paused")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="service not ready") from exc
    return {"status": "ready"}


@router.get("/health/metrics")
async def metrics(request: Request):
    now = datetime.now(timezone.utc)
    async with request.app.state.session_factory() as session:
        phase_rows = (
            await session.execute(
                select(table_runtimes.c.phase, func.count())
                .group_by(table_runtimes.c.phase)
            )
        ).all()
        total_tables = (await session.execute(select(func.count()).select_from(poker_tables))).scalar_one()
        active_seats = (
            await session.execute(
                select(func.count()).select_from(table_seats).where(
                    table_seats.c.state.in_(("seated", "held")),
                )
            )
        ).scalar_one()
        integrity_events_24h = (
            await session.execute(
                select(func.count()).select_from(integrity_events).where(
                    integrity_events.c.created_at >= now - timedelta(hours=24),
                    integrity_events.c.event_type.in_((
                        "runtime_paused",
                        "escrow_stack_mismatch",
                        "escrow_stack_mismatch_resolved",
                    )),
                )
            )
        ).scalar_one()

    coordinator = getattr(request.app.state, "coordinator", None)
    monitor = getattr(request.app.state, "integrity_monitor", None)
    return {
        "generated_at": now.isoformat(),
        "tables": {
            "total": int(total_tables),
            "active_seats": int(active_seats),
            "phases": {phase: int(count) for phase, count in phase_rows},
        },
        "coordinator": {
            "interval_ms": round(float(getattr(coordinator, "interval_seconds", 0)) * 1000, 2),
            "last_tick_at": coordinator.last_tick_at.isoformat() if getattr(coordinator, "last_tick_at", None) else None,
            "last_tick_duration_ms": getattr(coordinator, "last_tick_duration_ms", None),
        },
        "integrity": {
            "interval_seconds": getattr(monitor, "interval_seconds", None),
            "last_check_at": monitor.last_check_at.isoformat() if getattr(monitor, "last_check_at", None) else None,
            "last_check_duration_ms": getattr(monitor, "last_check_duration_ms", None),
            "last_finding_count": getattr(monitor, "last_finding_count", None),
            "last_error": getattr(monitor, "last_error", None),
            "events_last_24h": int(integrity_events_24h),
            "webhook_configured": bool(getattr(monitor, "webhook_url", "")),
            "telegram_configured": bool(
                getattr(monitor, "telegram_bot_token", "")
                and getattr(monitor, "telegram_chat_id", "")
            ),
        },
    }
