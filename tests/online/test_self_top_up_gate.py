"""Nobody grants themselves chips on a deployment."""

import pytest
from fastapi.testclient import TestClient

from app.online import create_app
from online.config import Settings


def _client(tmp_path, **extra):
    settings = Settings.from_mapping({
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'topup.sqlite3'}",
        "POKER8_DEV_PROFILES": "101:Dev Player",
        **extra,
    })
    return TestClient(create_app(settings))


def _top_up(client, request_id):
    return client.post("/api/profile/play-top-up", json={
        "amount_units": 100_000_000, "request_id": request_id,
    })


def test_the_switch_is_off_anywhere_but_development():
    """Production is the case that matters; test and staging get it too, so a
    box nobody thinks of as production does not quietly keep the door open."""
    for environment in ("production", "test", "staging"):
        settings = Settings.from_mapping({
            "POKER8_ENV": environment,
            "POKER8_DATABASE_URL": "sqlite+aiosqlite:///./x.sqlite3",
            "POKER8_DEFAULT_BOT_TOKEN": "token",
        })
        assert settings.self_top_up_enabled is False, environment


def test_with_the_switch_off_a_guest_cannot_print_themselves_a_fortune(tmp_path):
    """The caller names the amount and the request id, so the idempotency guard
    caps nothing: on the live site three calls took a brand-new guest from
    100 000 units to 300 100 000."""
    with _client(tmp_path, POKER8_ENV="development", POKER8_SELF_TOP_UP="0") as client:
        client.post("/api/auth/dev/101")
        before = client.get("/api/profile").json()["available_units"]

        assert _top_up(client, "probe-1").status_code == 404
        assert _top_up(client, "probe-2").status_code == 404

        assert client.get("/api/profile").json()["available_units"] == before


def test_development_keeps_it_so_a_fixture_balance_stays_easy(tmp_path):
    with _client(tmp_path, POKER8_ENV="development") as client:
        client.post("/api/auth/dev/101")
        before = client.get("/api/profile").json()["available_units"]

        assert _top_up(client, "probe-1").status_code == 200
        assert client.get("/api/profile").json()["available_units"] > before
