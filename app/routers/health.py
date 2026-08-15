from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text


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
    except Exception as exc:
        raise HTTPException(status_code=503, detail="service not ready") from exc
    return {"status": "ready"}
