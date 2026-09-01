from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import update

from app.dependencies import get_cash_operator
from app.online import create_app
from online.config import Settings
from online.schema import cash_operators


def test_operator_config_requires_service_key_and_valid_json():
    with pytest.raises(ValueError, match="API_KEY"):
        Settings.from_mapping({
            "POKER8_CASH_ADMIN_OPERATORS_JSON": '[{"telegram_user_id":1,"role":"admin"}]',
        })
    with pytest.raises(ValueError, match="JSON array"):
        Settings.from_mapping({"POKER8_CASH_ADMIN_OPERATORS_JSON": "{}"})


def test_every_admin_route_uses_backend_operator_dependency():
    app = create_app(Settings.from_mapping({"POKER8_ENV": "development"}))
    routes = [route for route in app.routes if isinstance(route, APIRoute)
              and route.path.startswith("/api/cash-admin")]
    assert len(routes) == 9
    assert all(any(dependency.call is get_cash_operator for dependency in route.dependant.dependencies)
               for route in routes)


@pytest.mark.anyio
@pytest.mark.postgres
async def test_service_key_cannot_impersonate_inactive_or_unknown_operator(cash_db):
    settings = Settings.from_mapping({
        "POKER8_ENV": "test", "POKER8_CASH_MODE": "mock",
        "POKER8_CASH_ADMIN_API_KEY": "test-service-secret",
        "POKER8_DATABASE_URL": "postgresql+psycopg://unused",
    })
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        settings=settings, session_factory=cash_db,
    )))
    with pytest.raises(HTTPException) as bad_key:
        await get_cash_operator(request, "wrong", "1001")
    assert bad_key.value.status_code == 401
    with pytest.raises(HTTPException) as unknown:
        await get_cash_operator(request, "test-service-secret", "9999")
    assert unknown.value.status_code == 403
    operator = await get_cash_operator(request, "test-service-secret", "1001")
    assert operator.role == "operator" and operator.tenant_id == "tenant"
    async with cash_db() as session:
        async with session.begin():
            await session.execute(update(cash_operators).where(
                cash_operators.c.id == "operator"
            ).values(active=False))
    with pytest.raises(HTTPException) as revoked:
        await get_cash_operator(request, "test-service-secret", "1001")
    assert revoked.value.status_code == 403
