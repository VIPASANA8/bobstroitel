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


def _room(client, name="Вечерний стол", level="micro", password=None):
    return client.post("/api/lobby/rooms", json={
        "name": name, "level": level, "password": password,
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


def test_a_password_room_is_listed_for_everyone_but_only_seats_the_right_password(client):
    """The old link-only room hid from the listing but had no actual gate on
    the join path -- anyone holding the URL got in for free. A password is a
    real gate on the one action that matters (taking a seat, i.e. putting
    chips at risk); the room itself stays listed and spectating stays open,
    same as it always was."""
    client.post("/api/auth/dev/101")
    room = _room(client, name="Только свои", password="letmein").json()["room"]
    assert room["has_password"] is True
    assert "password_hash" not in room, "the hash must never reach the client"

    client.post("/api/auth/dev/102")
    theirs = client.get("/api/lobby/tables?per_page=100").json()["tables"]
    assert room["id"] in {row["id"] for row in theirs}, "listed for everyone, not hidden"
    matching = next(row for row in theirs if row["id"] == room["id"])
    assert matching["has_password"] is True
    assert "password_hash" not in matching

    # Spectating (viewing the snapshot) needs no password -- only seating does.
    snapshot = client.get(f"/api/tables/{room['id']}")
    assert snapshot.status_code == 200
    assert "password_hash" not in snapshot.json()["table"]

    wrong = client.post(f"/api/tables/{room['id']}/ready", json={
        "seat_no": 1, "buy_in_units": 4_000, "request_id": "r-wrong", "password": "guess",
    })
    assert wrong.status_code == 403
    assert wrong.json()["detail"]["code"] == "wrong_password"

    missing = client.post(f"/api/tables/{room['id']}/ready", json={
        "seat_no": 1, "buy_in_units": 4_000, "request_id": "r-missing",
    })
    assert missing.status_code == 403
    assert missing.json()["detail"]["code"] == "wrong_password"

    right = client.post(f"/api/tables/{room['id']}/ready", json={
        "seat_no": 1, "buy_in_units": 4_000, "request_id": "r-right", "password": "letmein",
    })
    assert right.status_code == 200


def test_a_room_with_no_password_needs_none_to_seat(client):
    client.post("/api/auth/dev/101")
    room = _room(client, name="Открытая").json()["room"]
    assert room["has_password"] is False

    client.post("/api/auth/dev/102")
    ready = client.post(f"/api/tables/{room['id']}/ready", json={
        "seat_no": 1, "buy_in_units": 4_000, "request_id": "r-open",
    })
    assert ready.status_code == 200


def test_quick_play_never_lands_on_a_password_room(client):
    client.post("/api/auth/dev/101")
    _room(client, name="Закрытая", password="letmein")

    client.post("/api/auth/dev/102")
    for _ in range(10):
        chosen = client.post("/api/lobby/quick-play")
        if chosen.status_code != 200:
            continue
        assert chosen.json()["table"]["has_password"] is False


def test_a_password_must_be_a_real_length_not_a_single_character(client):
    client.post("/api/auth/dev/101")
    too_short = _room(client, name="Слишком короткий", password="ab")
    assert too_short.status_code == 400


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
    """The creator picks a name, stakes and an optional password. Seat count
    is fixed at six and bots are not a setting, so neither appears in the
    form."""
    markup = Path("static/lobby.html").read_text(encoding="utf-8")
    script = Path("static/lobby.js").read_text(encoding="utf-8")

    assert 'id="createRoom"' in markup
    for field in ('id="roomName"', 'id="roomLevel"', 'id="roomPassword"'):
        assert field in markup
    form = markup[markup.index('id="roomDialog"'):markup.index("</dialog>", markup.index('id="roomDialog"'))]
    assert "бот" not in form.lower() and "bot" not in form.lower()
    assert "мест" not in form.lower() or "шесть мест" in form.lower()

    # No more copying a link out -- a password protects the seat instead.
    assert "data-copy-room" not in script and "copyRoomLink" not in script
    assert "data-close-room" in script
    # And a second attempt goes to the room they already have, not a refusal.
    assert 'detail.code === "room_limit_reached"' in script


def test_the_owner_gets_a_way_to_close_the_room_from_the_table():
    """Lives in the table's own menu -- the creator is at the table, not the
    lobby, when they want to shut the room down. The invite-link twin of this
    button is gone: the room is always listed now, and a password protects
    the seat instead of a link protecting the listing."""
    markup = Path("static/index.html").read_text(encoding="utf-8")
    script = Path("static/online-table.js").read_text(encoding="utf-8")

    assert 'id="mobileDrawerInvite"' not in markup
    assert "copyInviteLink" not in script
    assert 'id="mobileDrawerCloseRoom"' in markup
    # Hidden by default: everyone else at the table must never see it.
    assert markup[markup.index('id="mobileDrawerCloseRoom"'):].split(">", 1)[0].endswith("hidden")
    assert "mobileDrawerCloseRoom" in script

    # Ownership is asked from the endpoint the lobby already uses, not guessed
    # from a snapshot that never says who is looking.
    assert '"/api/lobby/rooms/mine"' in script
    assert "/close" in script


def test_bots_are_seeded_and_renamed_with_names_a_person_could_have(client):
    """"Room Player 19" gives the game away at a glance -- no amount of work on
    how a bot plays survives its name tag. This is the roster at rest; the name
    a bot actually shows is borrowed when it sits down (test_bot_nicknames)."""
    import asyncio

    from sqlalchemy import select

    from online.bot_names import BOT_NAMES
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
