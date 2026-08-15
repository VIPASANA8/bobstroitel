from pathlib import Path


def test_profile_page_has_wallet_history_and_return_slot():
    html = Path("static/profile.html").read_text(encoding="utf-8")
    for element_id in ("profileName", "levelProgress", "walletBalance", "handHistory", "returnToTable"):
        assert f'id="{element_id}"' in html
