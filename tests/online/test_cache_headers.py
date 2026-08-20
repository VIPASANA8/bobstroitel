"""Every entry point must be revalidated, or a deploy lands whenever each
viewer's browser-invented freshness window happens to expire."""

import pytest
from fastapi.testclient import TestClient

from app.online import create_app
from online.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'cache.sqlite3'}",
    })
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/", "/table", "/static/mobile.css", "/static/lobby.js"])
def test_the_app_shell_is_never_served_without_being_checked(client, path):
    response = client.get(path)
    assert response.status_code == 200
    directive = response.headers.get("cache-control", "")
    assert "no-cache" in directive or "no-store" in directive, (
        f"{path} carries an ETag but no Cache-Control, which is what triggers "
        "heuristic caching in the first place"
    )


def test_an_unchanged_asset_still_costs_nothing_to_check(client):
    """no-cache means revalidate, not re-download -- so the layer scripts, which
    are the bulk of a page load, come back as an empty 304 when untouched. The
    two HTML shells are a few KB and are simply re-sent; FileResponse does not
    answer If-None-Match, and that is not worth a hand-rolled route for."""
    first = client.get("/static/lobby.js")
    again = client.get("/static/lobby.js", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304
    assert not again.content
