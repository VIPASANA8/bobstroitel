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


PRODUCTION = {
    "POKER8_ENV": "production",
    "POKER8_DATABASE_URL": "postgresql+psycopg://db/poker",
    "POKER8_DEFAULT_BOT_TOKEN": "x",
    "POKER8_CASH_MODE": "production",
    "POKER8_CASH_FIAT_API_URL": "https://partner.example/api",
    "POKER8_CASH_FIAT_TOKEN": "t" * 20,
    "POKER8_CASH_TRC20_API_URL": "https://tron.example/api",
    "POKER8_CASH_TRC20_ADDRESS": "T" + "1" * 33,
    "POKER8_CASH_TRC20_CONTRACT": "T" + "2" * 33,
    "POKER8_CASH_PAYOUT_PROVIDER": "somebody",
}


def test_production_cash_needs_a_production_environment():
    """Real money does not borrow the test environment the mock had to use."""
    for environment in ("development", "test", "staging"):
        with pytest.raises(ValueError, match="requires POKER8_ENV=production"):
            Settings.from_mapping({**PRODUCTION, "POKER8_ENV": environment})
    assert Settings.from_mapping(PRODUCTION).cash_mode == "production"


@pytest.mark.parametrize("missing", [
    "POKER8_CASH_FIAT_API_URL", "POKER8_CASH_FIAT_TOKEN", "POKER8_CASH_TRC20_API_URL",
    "POKER8_CASH_TRC20_ADDRESS", "POKER8_CASH_TRC20_CONTRACT", "POKER8_CASH_PAYOUT_PROVIDER",
])
def test_production_refuses_to_start_with_a_hole_in_the_money_path(missing):
    values = dict(PRODUCTION)
    values[missing] = ""
    with pytest.raises(ValueError) as refusal:
        Settings.from_mapping(values)
    # The TRC20 trio has its own older "set together" rule that fires first;
    # either way the boot stops and the message names the variables at fault.
    assert missing in str(refusal.value) or "_ADDRESS and _CONTRACT" in str(refusal.value)


def test_the_partner_endpoint_must_be_https():
    with pytest.raises(ValueError, match="must be HTTPS"):
        Settings.from_mapping({**PRODUCTION, "POKER8_CASH_FIAT_API_URL": "http://partner.example"})


def test_production_has_no_payout_provider_yet_and_says_so():
    """The one thing standing between this mode and real money.

    Falling back to MockPayoutExecutor here would mean a production deployment
    that reports payouts as submitted and sends nothing, so it refuses instead.
    """
    from app.online import PAYOUT_PROVIDERS, _payout_executor

    assert PAYOUT_PROVIDERS == {}
    with pytest.raises(RuntimeError, match="cannot start with a mock executor"):
        _payout_executor(Settings.from_mapping(PRODUCTION))
    # Every other mode keeps its mock, and says so by asking for the default.
    assert _payout_executor(Settings.from_mapping({"POKER8_CASH_MODE": "off"})) is None


def test_only_a_real_telegram_identity_reaches_real_money():
    for method in ("dev", "guest", "legacy"):
        with pytest.raises(CashAccessDenied, match="verified identity"):
            ensure_cash_access("production", method, 101)
    for absent in (None, 0, -1, "101"):
        with pytest.raises(CashAccessDenied, match="verified Telegram identity"):
            ensure_cash_access("production", "telegram", absent)
    ensure_cash_access("production", "telegram", 101)
