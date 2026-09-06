"""Signing in from a browser: the bot vouches, the browser keeps playing."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.online import create_app
from cash.access import ensure_cash_access
from online.asyncio_runner import run
from online.schema import auth_sessions
from online.auth import app_link, login_code
from online.config import Settings
from online.telegram import webhook_secret


TOKEN = "424242:AAH-test-bot-token"
SECRET = webhook_secret(TOKEN)


@pytest.fixture
def client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'login.sqlite3'}",
        "POKER8_DEFAULT_BOT_TOKEN": TOKEN,
    })
    with TestClient(create_app(settings)) as test_client:
        # Startup asks Telegram for the bot's name in the background and will
        # not have it here, so the button's own precondition is stood in for.
        test_client.app.state.telegram_login_bots = {
            "poker8": {"username": "TestBot", "app_url": "https://t.me/TestBot?startapp"},
        }
        yield test_client


def _start(client, nonce, *, user_id=5150, first_name="Вера", secret=SECRET, tenant="poker8"):
    """Opening the link. On its own this confirms nothing."""
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret else {}
    return client.post(
        f"/api/telegram/webhook/{tenant}",
        headers=headers,
        json={"message": {
            "chat": {"id": 900}, "from": {"id": user_id, "first_name": first_name},
            "text": f"/start {nonce}",
        }},
    )


def _confirm(client, nonce, *, user_id=5150, first_name="Вера", secret=SECRET, tenant="poker8"):
    """Pressing the button the bot offered."""
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret else {}
    return client.post(
        f"/api/telegram/webhook/{tenant}",
        headers=headers,
        json={"callback_query": {
            "id": "cb1", "from": {"id": user_id, "first_name": first_name},
            "message": {"chat": {"id": 900}}, "data": f"login:{nonce}",
        }},
    )


def test_confirming_in_the_bot_signs_the_browser_in(client):
    opened = client.post("/api/auth/telegram/request").json()
    assert opened["url"] == f"https://t.me/TestBot?start={opened['nonce']}"
    assert opened["code"] == login_code(opened["nonce"])
    # Nobody has pressed anything yet, and that is not an error.
    assert client.post("/api/auth/telegram/claim", json=opened).json() == {"status": "pending"}

    # Opening the link only gets the question asked.
    assert _start(client, opened["nonce"]).status_code == 200
    assert client.post("/api/auth/telegram/claim", json=opened).json() == {"status": "pending"}

    assert _confirm(client, opened["nonce"]).status_code == 200

    claimed = client.post("/api/auth/telegram/claim", json={"nonce": opened["nonce"]})
    assert claimed.status_code == 200
    assert claimed.json()["telegram_user_id"] == 5150
    # And the cookie it set is a session every other endpoint accepts.
    profile = client.get("/api/profile").json()
    assert (profile["telegram_user_id"], profile["display_name"]) == (5150, "Вера")


def test_a_code_buys_one_session_and_no_more(client):
    """The code travels in a link and ends up in somebody's tab history. It has
    to be worth nothing the second time it is presented."""
    opened = client.post("/api/auth/telegram/request").json()
    _confirm(client, opened["nonce"])
    assert client.post("/api/auth/telegram/claim", json=opened).status_code == 200

    assert client.post("/api/auth/telegram/claim", json=opened).status_code == 410


def test_a_code_nobody_opened_confirms_nothing(client):
    """Guessing at codes must not produce a session."""
    invented = "invented-code-nobody-issued"
    assert _start(client, invented).status_code == 200
    assert _confirm(client, invented).status_code == 200
    assert client.post("/api/auth/telegram/claim", json={"nonce": invented}).status_code == 410


def test_the_webhook_answers_only_to_telegram(client):
    """The secret is derived from the bot token, so producing it means already
    having the token."""
    opened = client.post("/api/auth/telegram/request").json()
    assert _confirm(client, opened["nonce"], secret="not-the-secret").status_code == 403
    assert _confirm(client, opened["nonce"], secret=None).status_code == 403
    # And the login it did not confirm is still waiting.
    assert client.post("/api/auth/telegram/claim", json=opened).json() == {"status": "pending"}


def test_an_unknown_tenant_has_no_webhook(client):
    assert client.post(
        "/api/telegram/webhook/somebody-else",
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET}, json={},
    ).status_code == 404


def test_a_bare_start_is_a_greeting_not_a_login(client):
    response = client.post(
        "/api/telegram/webhook/poker8",
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        json={"message": {"chat": {"id": 900}, "from": {"id": 1, "first_name": "Х"}, "text": "/start"}},
    )
    assert response.status_code == 200


def test_updates_that_are_not_a_start_are_shrugged_off(client):
    """Telegram retries anything that fails, and there is nothing here worth
    retrying -- an edited message, a photo, a join event."""
    for update in ({}, {"message": {}}, {"edited_message": {"text": "/start x"}},
                   {"message": {"chat": {"id": 1}, "from": {"id": 1}, "text": "привет"}}):
        assert client.post(
            "/api/telegram/webhook/poker8",
            headers={"X-Telegram-Bot-Api-Secret-Token": SECRET}, json=update,
        ).status_code == 200


def test_the_login_counts_as_telegram_at_the_cashier(client):
    """The bot is Telegram vouching for this person, so the CASH gate has no
    reason to treat them differently from somebody who came via the Mini App.
    The gate reads the session's auth method, so that is what is checked."""
    opened = client.post("/api/auth/telegram/request").json()
    _confirm(client, opened["nonce"])
    assert client.post("/api/auth/telegram/claim", json=opened).status_code == 200

    async def stored_method(factory):
        async with factory() as session:
            return await session.scalar(select(auth_sessions.c.auth_method))

    method = run(stored_method(client.app.state.session_factory))
    assert method == "telegram"
    # Which is the one identity production lets near money at all.
    ensure_cash_access("production", method, 5150)


def test_the_mini_app_link_is_the_side_door_not_the_main_one():
    assert app_link("DonbassWinBot", True) == "https://t.me/DonbassWinBot?startapp"
    # No main Mini App: the chat, where the menu button opens it.
    assert app_link("DonbassWinBot", False) == "https://t.me/DonbassWinBot"


def test_the_page_can_offer_the_button_before_it_asks_for_a_session():
    """tg-login.js has to be parsed by the time ensureSession looks for it."""
    for name in ("lobby.html", "cube.html", "profile.html", "index.html"):
        page = Path("static", name).read_text(encoding="utf-8")
        # The tags, not any mention: index.html names auth-client.js in a
        # comment about load order well before it loads it.
        loaded = re.findall(r'<script src="/static/(tg-login|auth-client)\.js', page)
        assert loaded == ["tg-login", "auth-client"], (name, loaded)
    assert "Poker8TgLogin?.prompt(config)" in Path(
        "static/auth-client.js"
    ).read_text(encoding="utf-8")


def test_the_card_waits_for_the_bot_and_never_asks_for_a_phone_number():
    source = Path("static/tg-login.js").read_text(encoding="utf-8")
    assert "/api/auth/telegram/request" in source and "/api/auth/telegram/claim" in source
    # The widget is the flow that wanted a phone number and a code.
    assert "telegram-widget.js" not in source
    assert "visibilitychange" in source, "coming back to the tab is when to ask"


def test_a_forwarded_link_cannot_hand_somebody_elses_session_over(client):
    """The attack this flow has to survive: open a login here, send the link to
    somebody else, and be given a session as whoever pressed the button.

    Nothing in the protocol can stop a person from confirming, so what stops it
    is that they can see what they are confirming -- the bot shows the code the
    page is displaying, and it is not on their screen. The mechanism this test
    pins is that opening the link binds nothing at all; only the confirmation
    does, and the code goes with it."""
    victim_facing = client.post("/api/auth/telegram/request").json()
    assert _start(client, victim_facing["nonce"], user_id=999_111).status_code == 200
    # Still nobody's login, because Start is not consent.
    assert client.post("/api/auth/telegram/claim", json=victim_facing).json() == {"status": "pending"}
    # And what the bot puts in front of them is the attacker's code, not one
    # they have anywhere on screen.
    assert victim_facing["code"] == login_code(victim_facing["nonce"])


def test_one_networks_bot_cannot_confirm_another_networks_login(client, tmp_path):
    """A code belongs to the site that issued it. Another tenant's bot has no
    business vouching for a login here, however it came to know the code."""
    opened = client.post("/api/auth/telegram/request").json()
    other = "poker8-other"
    client.app.state.settings.tenant_configs[other] = {
        "hosts": [], "name": "Other", "support_url": None, "branding": {}, "token": TOKEN,
    }

    # Same bot token, so the webhook secret matches and the door opens -- and
    # the login still does not move, because it is not that tenant's.
    assert _confirm(client, opened["nonce"], tenant=other).status_code in (200, 404)
    assert client.post("/api/auth/telegram/claim", json=opened).json() == {"status": "pending"}


def test_the_operator_panel_answers_only_operators(client, monkeypatch):
    """A stranger guessing /admin gets nothing back at all -- a refusal would
    tell them the command is there."""
    sent = []

    async def record(token, chat_id, text, reply_markup=None, parse_mode=None):
        sent.append(text)

    monkeypatch.setattr("app.routers.telegram.send_message", record)
    response = client.post(
        "/api/telegram/webhook/poker8",
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        json={"message": {"chat": {"id": 900}, "from": {"id": 4242, "first_name": "Кто-то"},
                          "text": "/admin"}},
    )
    assert response.status_code == 200
    assert sent == []


def test_the_operator_panel_never_moves_money_behind_the_audit_log(client):
    """Every decision has to land on CashAdminService, because that is what
    writes the reason into the audit log and enforces the role. A shortcut to
    the ledger from here would be the same money with less of a record."""
    source = Path("online/opsbot.py").read_text(encoding="utf-8")
    assert "self.admin." in source
    for shortcut in ("CashLedger", "cash_accounts", "session.execute(update", "insert("):
        assert shortcut not in source, shortcut
