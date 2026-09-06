"""Signing in from a browser, where there is no Mini App to hand over initData."""
import hashlib
import hmac
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.online import create_app
from online.auth import AuthenticationError, app_link, verify_login_widget
from online.config import Settings


TOKEN = "424242:AAH-test-bot-token"


def _signed(token=TOKEN, **overrides):
    fields = {
        "id": 5150,
        "first_name": "Вера",
        "username": "vera",
        "auth_date": int(time.time()),
        **overrides,
    }
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hashlib.sha256(token.encode()).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return fields


@pytest.fixture
def client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'login.sqlite3'}",
        "POKER8_DEFAULT_BOT_TOKEN": TOKEN,
    })
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_a_signed_widget_login_becomes_a_session(client):
    response = client.post("/api/auth/telegram/widget", json=_signed())

    assert response.status_code == 200
    assert response.json()["telegram_user_id"] == 5150
    # And the cookie it set is a session every other endpoint accepts.
    assert client.get("/api/profile").json()["telegram_user_id"] == 5150


def test_the_web_login_counts_as_telegram_not_as_a_guest(client):
    """The CASH gate reads the auth method, and this person really is who
    Telegram says: a widget login must not be second class at the cashier."""
    client.post("/api/auth/telegram/widget", json=_signed())
    assert client.get("/api/profile").json()["display_name"] == "Вера"


@pytest.mark.parametrize("broken", [
    {"first_name": "Кто-то ещё"},          # a field changed after signing
    {"id": 9999},
    {"auth_date": int(time.time()) - 10_000},
    {"hash": "0" * 64},
])
def test_anything_but_the_signature_telegram_produced_is_refused(client, broken):
    fields = {**_signed(), **broken}
    assert client.post("/api/auth/telegram/widget", json=fields).status_code == 401


def test_a_login_signed_with_another_bots_token_is_refused(client):
    assert client.post(
        "/api/auth/telegram/widget", json=_signed(token="999:someone-elses-bot"),
    ).status_code == 401


def test_an_extra_field_cannot_be_smuggled_past_the_check():
    """Telegram signs exactly what it sends. A field it did not send is either
    a forgery or a version we have not read yet, and both are a refusal."""
    fields = {**_signed(), "is_admin": "1"}
    with pytest.raises(AuthenticationError):
        verify_login_widget(fields, TOKEN, int(time.time()), 900)


def test_initdata_and_widget_do_not_share_a_secret():
    """The two envelopes derive their key differently. Checking one with the
    other's key would verify nothing at all, which is why they stayed apart."""
    fields = _signed()
    supplied = fields.pop("hash")
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    webapp_key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    assert hmac.new(webapp_key, check.encode(), hashlib.sha256).hexdigest() != supplied


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


def test_the_button_goes_into_the_app_when_the_bot_has_one():
    """Telegram's browser login wants a phone number and a code before it says
    who you are. A player with Telegram on the same device should not be sent
    the long way round, so the card leads with the app itself."""
    assert app_link("DonbassWinBot", True) == "https://t.me/DonbassWinBot?startapp"
    # No main Mini App: the chat, where the menu button opens it.
    assert app_link("DonbassWinBot", False) == "https://t.me/DonbassWinBot"


def test_the_card_leads_with_the_app_and_keeps_the_browser_login_behind_it():
    source = Path("static/tg-login.js").read_text(encoding="utf-8")
    assert source.index("tg-gate-open") < source.index("tg-gate-alt")
    assert "telegram-widget.js" in source, "the browser login is still offered"
    # And the widget is only fetched once somebody asks for it.
    assert source.index('addEventListener("click"') < source.index("telegram-widget.js")
