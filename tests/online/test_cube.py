"""CUBE settles on the server, against the same PLAY wallet the tables pay from."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.online import create_app
from online import cube
from online.config import Settings
from online.ledger import InsufficientPlayBalance, PlayLedger
from online.schema import tenants, users


@pytest.fixture
def client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'cube.sqlite3'}",
        "POKER8_DEV_PROFILES": "101:Dev Player",
    })
    with TestClient(create_app(settings)) as test_client:
        test_client.post("/api/auth/dev/101")
        yield test_client


def _roll(client, request_id, *, stake_units=100, selected=(2, 5)):
    return client.post("/api/cube/roll", json={
        "stake_units": stake_units, "selected": list(selected), "request_id": request_id,
    })


def _balance(client):
    return client.get("/api/profile").json()["available_units"]


def test_a_round_moves_the_wallet_by_exactly_what_it_paid(client):
    before = _balance(client)
    body = _roll(client, "round-1").json()

    assert body["roll"] in range(1, 7)
    assert body["won"] == (body["roll"] in body["selected"])
    assert body["payout_units"] == (
        cube.potential_payout(100, 2) if body["won"] else 0
    )
    assert body["balance_units"] == before - 100 + body["payout_units"]
    assert _balance(client) == body["balance_units"]


def test_the_same_request_id_is_the_same_round_not_a_second_one(client):
    """A retried post must be answered with the face that settled. Redrawing it
    would show the player a result their balance never saw."""
    first = _roll(client, "round-1").json()
    before = _balance(client)
    second = _roll(client, "round-1").json()

    assert second["round_id"] == first["round_id"]
    assert (second["roll"], second["payout_units"]) == (first["roll"], first["payout_units"])
    assert _balance(client) == before


@pytest.mark.anyio
async def test_a_stake_past_the_balance_never_posts(db_session_factory):
    """The wallet row is locked for the whole round, so this is the last word
    even if the balance was still there when the face was drawn."""
    async with db_session_factory() as session:
        await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
        await session.execute(insert(users).values(
            id="u1", telegram_user_id=1, display_name="Player", acquisition_tenant_id="tenant",
        ))
        await session.commit()

    ledger = PlayLedger(db_session_factory)
    await ledger.grant("u1", 100, "grant:u1")
    with pytest.raises(InsufficientPlayBalance):
        # A losing round for more than the wallet holds: the player's leg is -200.
        await ledger.settle_cube_round("u1", "r1", 200, 0, "cube:u1:r1")
    assert await ledger.available_units("u1") == 100


@pytest.mark.anyio
async def test_a_won_round_is_minted_by_the_faucet(db_session_factory):
    async with db_session_factory() as session:
        await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
        await session.execute(insert(users).values(
            id="u1", telegram_user_id=1, display_name="Player", acquisition_tenant_id="tenant",
        ))
        await session.commit()

    ledger = PlayLedger(db_session_factory)
    await ledger.grant("u1", 100, "grant:u1")
    result = await ledger.settle_cube_round("u1", "r1", 100, 600, "cube:u1:r1")
    assert result.available_units == 600
    # Same key twice is the same round, not a second payout.
    again = await ledger.settle_cube_round("u1", "r1", 100, 600, "cube:u1:r1")
    assert again.available_units == 600


@pytest.mark.parametrize("stake_units,selected", [
    (100, [2, 2]),          # the same face twice is not two faces
    (100, [1, 2, 3, 4]),    # four of six would pay less than it costs
    (100, [7]),             # off the die
    (103, [2]),             # off the $0.05 grid
])
def test_the_rules_are_enforced_on_the_server(client, stake_units, selected):
    before = _balance(client)
    assert _roll(client, "bad", stake_units=stake_units, selected=selected).status_code in (400, 422)
    assert _balance(client) == before


def test_the_house_edge_lives_in_the_chance_not_in_the_payout():
    """x6 on one face of six is an honest payout; the 20% is taken by dealing
    that face 80% as often. Both together are the 80% RTP CASE8 designed for."""
    for count in (1, 2, 3):
        honest = cube.MULTIPLIER_TENTHS[count] / 10
        assert abs(honest * count / 6 - 1) < 1e-9
        assert abs(honest * (count / 6 * cube.TARGET_RTP) - cube.TARGET_RTP) < 1e-9
