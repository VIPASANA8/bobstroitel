from app.online import create_app
from online.config import Settings
from online.ledger import PlayLedger
from online.schema import metadata


def test_online_runtime_is_play_money_only():
    route_paths = {getattr(route, "path", "") for route in create_app(Settings.from_mapping({"POKER8_ENV": "development"})).routes}
    table_names = set(metadata.tables)
    assert PlayLedger.ASSET == "PLAY"
    assert not any(path for path in route_paths if any(word in path.lower() for word in ("deposit", "withdraw", "kyc", "blockchain", "cash")))
    assert not any(name for name in table_names if any(word in name.lower() for word in ("deposit", "withdraw", "kyc", "blockchain", "cash_wallet", "payout")))
