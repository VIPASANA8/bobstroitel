import pytest

from online.config import Settings


def test_production_requires_database_and_bot_token():
    with pytest.raises(ValueError, match="POKER8_DATABASE_URL"):
        Settings.from_mapping({"POKER8_ENV": "production"})


def test_development_accepts_named_profiles_without_bot_token():
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "POKER8_DEV_PROFILES": "101:Марта,202:Илья",
    })
    assert settings.environment == "development"
    assert settings.dev_profiles == {101: "Марта", 202: "Илья"}
    assert settings.default_tenant_slug == "poker8"
