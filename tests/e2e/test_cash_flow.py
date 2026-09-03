from decimal import Decimal

import pytest
from playwright.sync_api import BrowserContext, sync_playwright


pytestmark = [pytest.mark.e2e, pytest.mark.postgres]


def _post(context: BrowserContext, base_url: str, path: str, data: dict | None = None) -> dict:
    response = context.request.post(f"{base_url}{path}", data=data)
    assert response.ok, response.text()
    return response.json()


def _get(context: BrowserContext, base_url: str, path: str) -> dict:
    response = context.request.get(f"{base_url}{path}")
    assert response.ok, response.text()
    return response.json()


def test_two_players_complete_mock_cash_flow(cash_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        alice = browser.new_context()
        bob = browser.new_context()

        alice_auth = _post(alice, cash_server, "/api/auth/dev/101")
        bob_auth = _post(bob, cash_server, "/api/auth/dev/202")
        assert alice_auth["user_id"] != bob_auth["user_id"]

        page = alice.new_page()
        page.goto(f"{cash_server}/static/lobby.html#cash", wait_until="networkidle")
        assert page.get_by_text("USDT TRC20 mock", exact=False).first.is_visible()

        alice_deposit = _post(alice, cash_server, "/api/cash/deposits", {
            "amount_usdt": "10", "request_id": "alice-deposit",
        })
        paid = _post(alice, cash_server, f'/api/cash/deposits/{alice_deposit["id"]}/paid')
        assert paid["status"] == "awaiting_transfer"
        assert _get(alice, cash_server, "/api/cash/wallet")["available_usdt"] == "0"

        bob_deposit = _post(bob, cash_server, "/api/cash/deposits", {
            "amount_usdt": "12", "request_id": "bob-deposit",
        })
        for context, deposit in ((alice, alice_deposit), (bob, bob_deposit)):
            credited = _post(
                context, cash_server, f'/api/cash/deposits/{deposit["id"]}/simulate-transfer'
            )
            assert credited["status"] == "credited"

        assert _get(alice, cash_server, "/api/cash/wallet")["available_usdt"] == "10"
        assert _get(bob, cash_server, "/api/cash/wallet")["available_usdt"] == "12"

        for context, seat_no, player in ((alice, 0, "alice"), (bob, 1, "bob")):
            seated = _post(context, cash_server, "/api/tables/cash-micro-test/ready", {
                "seat_no": seat_no,
                "buy_in_units": 400,
                "request_id": f"{player}-cash-seat",
            })
            assert seated["viewer_state"] == "seated"
            wallet = _get(context, cash_server, "/api/cash/wallet")
            assert wallet["escrow_usdt"] == "4"

        active = _get(alice, cash_server, "/api/tables/cash-micro-test")
        assert active["state"]["phase"] == "active"
        assert active["state"]["occupancy"] == 2
        assert all(not player["is_bot"] for player in active["state"]["players"].values())

        contexts = {alice_auth["user_id"]: alice, bob_auth["user_id"]: bob}
        actor = active["state"]["acting_player"]
        _post(contexts[actor], cash_server, "/api/tables/cash-micro-test/leave")
        other = next(context for user_id, context in contexts.items() if user_id != actor)
        _post(other, cash_server, "/api/tables/cash-micro-test/leave")

        alice_wallet = _get(alice, cash_server, "/api/cash/wallet")
        bob_wallet = _get(bob, cash_server, "/api/cash/wallet")
        assert alice_wallet["escrow_usdt"] == bob_wallet["escrow_usdt"] == "0"
        # Nobody reached a flop, so no flop no drop: every chip comes back.
        assert Decimal(alice_wallet["available_usdt"]) + Decimal(bob_wallet["available_usdt"]) == 22

        withdrawal = _post(alice, cash_server, "/api/cash/withdrawals", {
            "amount_usdt": "0.5",
            "address": "TMockCashFlowDestination",
            "request_id": "alice-withdrawal",
        })
        assert withdrawal == {
            **withdrawal,
            "status": "reserved",
            "network": "TRC20",
            "amount_usdt": "0.5",
            "amount_units": "5",
        }
        reserved = _get(alice, cash_server, "/api/cash/wallet")
        assert reserved["withdrawal_usdt"] == "0.5"
        assert Decimal(reserved["available_usdt"]) == Decimal(alice_wallet["available_usdt"]) - Decimal("0.5")

        browser.close()
