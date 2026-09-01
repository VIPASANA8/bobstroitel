import pytest
from sqlalchemy import insert, select

from cash.access import CashAccessDenied, ensure_cash_access
from online.auth import AuthService
from online.config import Settings
from online.schema import auth_sessions, tenants


def test_cash_mode_is_off_by_default_and_mock_is_isolated():
    assert Settings.from_mapping({}).cash_mode == "off"
    assert Settings.from_mapping({}).legacy_play_rooms_enabled is False
    assert Settings.from_mapping({"POKER8_ENV": "test", "POKER8_CASH_MODE": "mock"}).cash_mode == "mock"


def test_optional_cash_allowlist_is_strictly_parsed_and_enforced():
    settings = Settings.from_mapping({
        "POKER8_ENV": "test", "POKER8_CASH_MODE": "mock",
        "POKER8_CASH_ALLOWLIST": "101, 202",
    })
    assert settings.cash_allowlist == (101, 202)
    ensure_cash_access("mock", "telegram", 101, settings.cash_allowlist)
    with pytest.raises(CashAccessDenied, match="allowlist"):
        ensure_cash_access("mock", "telegram", 303, settings.cash_allowlist)
    with pytest.raises(ValueError, match="positive Telegram IDs"):
        Settings.from_mapping({"POKER8_CASH_ALLOWLIST": "101,nope"})
    for values in (
        {"POKER8_ENV": "production", "POKER8_DATABASE_URL": "postgresql+psycopg://db/poker", "POKER8_DEFAULT_BOT_TOKEN": "x", "POKER8_CASH_MODE": "mock"},
        {"POKER8_CASH_MODE": "live"}, {"POKER8_CASH_MODE": "yes"},
    ):
        with pytest.raises(ValueError, match="POKER8_CASH_MODE"):
            Settings.from_mapping(values)


@pytest.mark.parametrize("environment", ["production", "staging", "qa"])
def test_legacy_play_room_escape_hatch_only_works_locally(environment):
    values = {
        "POKER8_ENV": environment,
        "POKER8_LEGACY_PLAY_ROOMS": "1",
    }
    if environment == "production":
        values.update({
            "POKER8_DATABASE_URL": "postgresql+psycopg://db/poker",
            "POKER8_DEFAULT_BOT_TOKEN": "x",
        })
    assert Settings.from_mapping(values).legacy_play_rooms_enabled is False


@pytest.mark.parametrize("method", ["telegram", "dev", "guest"])
def test_mock_accepts_known_test_identities(method):
    ensure_cash_access("mock", method)


@pytest.mark.parametrize("mode,method", [
    ("off", "telegram"), ("off", "dev"), ("mock", "legacy"), ("mock", "unknown"),
])
def test_off_and_unverifiable_sessions_are_denied(mode, method):
    with pytest.raises(CashAccessDenied):
        ensure_cash_access(mode, method)


@pytest.mark.anyio
async def test_authentication_records_how_identity_was_verified(db_session_factory):
    async with db_session_factory() as session:
        await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
        await session.commit()
    service = AuthService(db_session_factory, {}, now=lambda: 1_770_000_000)
    await service.authenticate_dev("poker8", 101, "Dev")
    await service.authenticate_guest("poker8")
    async with db_session_factory() as session:
        methods = set((await session.execute(select(auth_sessions.c.auth_method))).scalars())
    assert methods == {"dev", "guest"}
