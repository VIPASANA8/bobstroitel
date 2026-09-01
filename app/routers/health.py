from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select, text

from online.schema import (
    cash_deposits, cash_fiat_events, cash_fiat_orders, cash_partner_cursors,
    cash_withdrawals, integrity_events, poker_tables, table_runtimes, table_seats,
)


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
        # Open tables only, both of them. A retired room keeps its runtime row,
        # frozen at whatever phase it died in, so counting every row reported
        # seven "active" tables on a network that has six -- and the number
        # grew with every room anyone had ever opened.
        phase_rows = (
            await session.execute(
                select(table_runtimes.c.phase, func.count())
                .select_from(
                    table_runtimes.join(poker_tables, poker_tables.c.id == table_runtimes.c.table_id)
                )
                .where(poker_tables.c.status == "open")
                .group_by(table_runtimes.c.phase)
            )
        ).all()
        total_tables = (
            await session.execute(
                select(func.count()).select_from(poker_tables).where(poker_tables.c.status == "open")
            )
        ).scalar_one()
        active_seats = (
            await session.execute(
                select(func.count())
                .select_from(
                    table_seats.join(poker_tables, poker_tables.c.id == table_seats.c.table_id)
                )
                .where(
                    table_seats.c.state.in_(("seated", "held")),
                    poker_tables.c.status == "open",
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
        expired_deposits = await session.scalar(
            select(func.count()).select_from(cash_deposits).where(
                cash_deposits.c.status == "awaiting_transfer",
                cash_deposits.c.expires_at < now,
            )
        )
        unknown_withdrawals = await session.scalar(
            select(func.count()).select_from(cash_withdrawals).where(
                cash_withdrawals.c.status == "unknown",
            )
        )
        fiat_orders_attention = await session.scalar(
            select(func.count()).select_from(cash_fiat_orders).where(
                cash_fiat_orders.c.status.in_(("requesting", "clarifying", "review_required")),
            )
        )
        fiat_events_review = await session.scalar(
            select(func.count()).select_from(cash_fiat_events).where(
                cash_fiat_events.c.status == "review_required",
            )
        )
        paused_cash_tables = await session.scalar(
            select(func.count()).select_from(
                table_runtimes.join(poker_tables, poker_tables.c.id == table_runtimes.c.table_id)
            ).where(
                poker_tables.c.asset == "CASH_USDT",
                poker_tables.c.status == "open",
                table_runtimes.c.phase == "paused",
            )
        )
        partner_offset = await session.scalar(
            select(cash_partner_cursors.c.offset).where(
                cash_partner_cursors.c.provider == "case8-p2p",
            )
        )

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
        "cash": {
            "expired_deposits_pending_reconciliation": int(expired_deposits or 0),
            "unknown_withdrawals": int(unknown_withdrawals or 0),
            "fiat_orders_requiring_attention": int(fiat_orders_attention or 0),
            "fiat_events_requiring_review": int(fiat_events_review or 0),
            "paused_tables": int(paused_cash_tables or 0),
            "partner_event_offset": int(partner_offset or 0),
        },
    }
