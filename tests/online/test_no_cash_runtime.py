from app.online import create_app
from online.config import Settings
from online.ledger import PlayLedger
from online.schema import metadata


def test_online_runtime_is_play_money_only():
    route_paths = {getattr(route, "path", "") for route in create_app(Settings.from_mapping({"POKER8_ENV": "development"})).routes}
    table_names = set(metadata.tables)
    assert PlayLedger.ASSET == "PLAY"
    assert "/api/cash/deposits" in route_paths
    assert "/api/cash/withdrawals" in route_paths
    # The C2C API is user-facing and mock-gated. No provider callback, live-key,
    # KYC, or administrator execution surface is exposed in this package.
    assert not any(path for path in route_paths if any(word in path.lower() for word in ("tron", "provider", "admin", "kyc")))
    assert not any(name for name in table_names if any(word in name.lower() for word in ("private_key", "cash_wallet", "kyc")))
