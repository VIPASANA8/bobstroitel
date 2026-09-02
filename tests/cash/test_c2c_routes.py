import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from app.dependencies import get_cash_user
from app.online import create_app
from online.config import Settings


def test_all_user_cash_routes_use_cash_identity_gate():
    app = create_app(Settings.from_mapping({"POKER8_ENV": "development"}))
    routes = [route for route in app.routes if isinstance(route, APIRoute) and route.path.startswith("/api/cash/")]
    assert {route.path for route in routes} == {
        "/api/cash/wallet", "/api/cash/deposits", "/api/cash/deposits/{deposit_id}",
        "/api/cash/deposits/{deposit_id}/cancel", "/api/cash/deposits/{deposit_id}/paid",
        "/api/cash/deposits/{deposit_id}/simulate-transfer",
        "/api/cash/fiat-orders", "/api/cash/fiat-orders/active",
        "/api/cash/fiat-orders/{order_id}",
        "/api/cash/fiat-orders/{order_id}/paid", "/api/cash/fiat-orders/{order_id}/cancel",
        "/api/cash/fiat-orders/{order_id}/simulate-trader-confirmation",
        "/api/cash/withdrawals", "/api/cash/withdrawals/{withdrawal_id}",
        "/api/cash/withdrawals/{withdrawal_id}/cancel",
    }
    assert all(any(dependency.call is get_cash_user for dependency in route.dependant.dependencies)
               for route in routes)


def test_mock_cash_refuses_a_sqlite_runtime(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "test", "POKER8_CASH_MODE": "mock",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'cash.sqlite3'}",
    })
    with pytest.raises(RuntimeError, match="requires PostgreSQL"):
        with TestClient(create_app(settings)):
            pass
