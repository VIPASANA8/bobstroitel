from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.online import create_app
from online.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'rooms.sqlite3'}",
        "POKER8_DEV_PROFILES": "101:Dev Player,102:Second Player",
    })
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _room(client, name="Вечерний стол", level="micro", visibility="public"):
    return client.post("/api/lobby/rooms", json={
        "name": name, "level": level, "visibility": visibility,
    })


def test_a_player_opens_a_room_and_it_appears_in_the_lobby(client):
    client.post("/api/auth/dev/101")
    created = _room(client)
    assert created.status_code == 200
    room = created.json()["room"]
    assert room["name"] == "Вечерний стол"
    assert room["max_seats"] == 6, "seat count is not a room setting"

    listed = client.get("/api/lobby/tables?per_page=100").json()["tables"]
    assert room["id"] in {row["id"] for row in listed}


def test_only_one_open_room_per_player_and_the_refusal_names_it(client):
    client.post("/api/auth/dev/101")
    first = _room(client).json()["room"]

    second = _room(client, name="Второй стол")
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["code"] == "room_limit_reached"
    # Enough to send the player to the room they already have.
    assert detail["table_id"] == first["id"]

    # Closing it frees the slot.
    assert client.post(f"/api/lobby/rooms/{first['id']}/close").status_code == 200
    assert _room(client, name="Второй стол").status_code == 200


def test_a_link_only_room_is_hidden_from_the_lobby_but_not_from_its_url(client):
    client.post("/api/auth/dev/101")
    room = _room(client, name="Только свои", visibility="link").json()["room"]

    mine = client.get("/api/lobby/tables?per_page=100").json()["tables"]
    assert room["id"] in {row["id"] for row in mine}, "its owner still sees it"

    client.post("/api/auth/dev/102")
    theirs = client.get("/api/lobby/tables?per_page=100").json()["tables"]
    assert room["id"] not in {row["id"] for row in theirs}, "nobody else does"
    # The door is open to anyone holding the link -- visibility governs listing.
    assert client.get(f"/api/tables/{room['id']}").status_code == 200


def test_a_closed_room_disappears_for_everyone(client):
    client.post("/api/auth/dev/101")
    room = _room(client).json()["room"]
    client.post(f"/api/lobby/rooms/{room['id']}/close")
    listed = client.get("/api/lobby/tables?per_page=100").json()["tables"]
    assert room["id"] not in {row["id"] for row in listed}


def test_a_room_cannot_be_closed_by_somebody_else(client):
    client.post("/api/auth/dev/101")
    room = _room(client).json()["room"]
    client.post("/api/auth/dev/102")
    assert client.post(f"/api/lobby/rooms/{room['id']}/close").status_code == 400


def test_a_refused_close_never_reaches_the_eviction(client):
    """Closing empties every seat, and that is not part of the close
    transaction -- nothing rolls it back. So the ownership refusal has to come
    first: otherwise naming any table and swallowing the 400 that follows is
    enough to throw everyone off it."""
    client.post("/api/auth/dev/101")
    _room(client)

    evicted = []
    real = client.app.state.seating.evict_table

    async def spy(table_id):
        evicted.append(table_id)
        return await real(table_id)

    client.app.state.seating.evict_table = spy
    try:
        client.post("/api/auth/dev/102")
        assert client.post("/api/lobby/rooms/micro-a/close").status_code == 400
        assert evicted == [], "a table nobody owns was cleared before the refusal"
    finally:
        client.app.state.seating.evict_table = real


def test_blind_levels_are_offered_and_free_form_ones_refused(client):
    client.post("/api/auth/dev/101")
    levels = client.get("/api/lobby/room-levels").json()["levels"]
    assert {row["key"] for row in levels} == {"micro", "low", "mid"}
    assert _room(client, level="whatever").status_code == 400


def test_bots_are_never_a_room_setting():
    """The creator picks name, stakes and who may see it -- nothing about bots."""
    source = Path("app/routers/lobby.py").read_text(encoding="utf-8")
    fields = source[source.index("class CreateRoomRequest"):source.index("router = APIRouter")]
    assert "bot" not in fields.lower()


def test_the_lobby_offers_room_creation_without_mentioning_bots():
    """The creator picks a name, stakes and who may see it. Seat count is fixed
    at six and bots are not a setting, so neither appears in the form."""
    markup = Path("static/lobby.html").read_text(encoding="utf-8")
    script = Path("static/lobby.js").read_text(encoding="utf-8")

    assert 'id="createRoom"' in markup
    for field in ('id="roomName"', 'id="roomLevel"', 'id="roomVisibility"'):
        assert field in markup
    form = markup[markup.index('id="roomDialog"'):markup.index("</dialog>", markup.index('id="roomDialog"'))]
    assert "бот" not in form.lower() and "bot" not in form.lower()
    assert "мест" not in form.lower() or "шесть мест" in form.lower()

    # Its owner can hand out the link and close it again.
    assert "data-copy-room" in script and "data-close-room" in script
    # And a second attempt goes to the room they already have, not a refusal.
    assert 'detail.code === "room_limit_reached"' in script


def test_the_owner_gets_an_invite_link_and_a_way_to_close_it_from_the_table():
    """Both live in the table's own menu -- the creator is at the table, not in
    the lobby, when they want to invite somebody or shut the room down."""
    markup = Path("static/index.html").read_text(encoding="utf-8")
    script = Path("static/online-table.js").read_text(encoding="utf-8")

    for button in ("mobileDrawerInvite", "mobileDrawerCloseRoom"):
        assert f'id="{button}"' in markup
        # Hidden by default: everyone else at the table must never see them.
        assert markup[markup.index(f'id="{button}"'):].split(">", 1)[0].endswith("hidden")
        assert button in script

    # Ownership is asked from the endpoint the lobby already uses, not guessed
    # from a snapshot that never says who is looking.
    assert '"/api/lobby/rooms/mine"' in script
    assert "/close" in script


def test_bots_are_seeded_and_renamed_with_names_a_person_could_have(client):
    """"Room Player 19" gives the game away at a glance -- no amount of work on
    how a bot plays survives its name tag."""
    import asyncio

    from sqlalchemy import select

    from online.catalogue import BOT_NAMES
    from online.schema import system_players

    async def roster():
        async with client.app.state.session_factory() as session:
            return (await session.execute(
                select(system_players.c.id, system_players.c.name)
            )).all()

    rows = asyncio.run(roster())
    assert rows, "the roster is seeded"
    names = [name for _, name in rows]
    assert not any(name.startswith("Room Player") for name in names)
    assert set(names) <= set(BOT_NAMES)
    # Six at a table, so a table never seats two of the same name.
    assert len(set(names)) == len(names)
