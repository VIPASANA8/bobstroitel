import pytest
from fastapi.testclient import TestClient

from app.online import create_app
from online.config import Settings


def test_production_requires_database_and_bot_token():
    with pytest.raises(ValueError, match="POKER8_DATABASE_URL"):
        Settings.from_mapping({"POKER8_ENV": "production"})


def test_open_access_is_not_allowed_in_production():
    settings = Settings.from_mapping({
        "POKER8_ENV": "production",
        "POKER8_DATABASE_URL": "postgresql+psycopg://poker8:poker8@db/poker8",
        "POKER8_DEFAULT_BOT_TOKEN": "token",
        "POKER8_OPEN_ACCESS": "1",
    })
    assert settings.open_access is False


def test_development_accepts_named_profiles_without_bot_token():
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "POKER8_DEV_PROFILES": "101:Марта,202:Илья",
    })
    assert settings.environment == "development"
    assert settings.dev_profiles == {101: "Марта", 202: "Илья"}
    assert settings.default_tenant_slug == "poker8"


def test_public_config_uses_request_host_tenant_branding(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'tenant.sqlite3'}",
        "POKER8_TENANTS_JSON": '[{"slug":"poker8","hosts":["poker.local"],"name":"Poker8"},{"slug":"partner-b","hosts":["partner.local"],"name":"Partner B","branding":{"accent":"violet"}}]',
    })
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/config", headers={"host": "partner.local"})
    assert response.json()["tenant"] == {
        "slug": "partner-b", "name": "Partner B", "support_url": None,
        "branding": {"accent": "violet"},
    }
