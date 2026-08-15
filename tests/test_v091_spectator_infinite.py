import pytest
from fastapi.testclient import TestClient

import app.legacy as main
from bots.multiway import MultiwayBot
from persistence.store import TrainingStore


def make_bot_only_store(tmp_path, bot_count=4):
    store = TrainingStore(tmp_path / "spectator.sqlite3")
    # Remove the default human and build a bot-only table.
    store.clear_seat(0)
    # seat 1 is the default bot; add the remaining requested bots.
    store.add_bot(0, "Alpha", "hard")
    next_seats = [2, 3, 4, 5, 6]
    for i, seat in enumerate(next_seats[: max(0, bot_count - 2)], start=2):
        store.add_bot(seat, f"Bot {i}", "normal")
    return store


def test_maximum_six_bots_even_without_humans(tmp_path):
    store = make_bot_only_store(tmp_path, bot_count=6)
    assert sum(1 for r in store.active_seats() if r["occupant_type"] == "bot") == 6
    with pytest.raises(ValueError, match="не больше 6 ботов"):
        store.add_bot(6, "Седьмой", "maximum")


def test_bot_only_hand_starts_paused_for_spectator_and_steps_once(tmp_path, monkeypatch):
    store = make_bot_only_store(tmp_path, bot_count=3)
    bot = MultiwayBot(engine=main.engine, opponent_model_provider=store.bot_opponent_model)

    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "bot", bot)
    monkeypatch.setattr(main, "GAMES", {})
    monkeypatch.setattr(main, "SOLVER_CACHE", {})
    monkeypatch.setattr(main, "ACTIVE_HAND_ID", None)
    monkeypatch.setattr(main, "NEXT_BUTTON_SEAT", 0)

    client = TestClient(main.app)
    started = client.post("/api/game/new")
    assert started.status_code == 200
    state = started.json()
    assert state["spectator_only"] is True
    assert state["human_count"] == 0
    assert state["bot_count"] == 3
    assert state["terminal"] is False
    before_actions = len(state["history"])

    stepped = client.post(f"/api/game/{state['hand_id']}/bot-step")
    assert stepped.status_code == 200
    state2 = stepped.json()
    assert len(state2["history"]) == before_actions + 1 or state2["terminal"]
    assert "last_bot_decision" in state2


def test_bot_step_rejected_when_human_is_seated(tmp_path, monkeypatch):
    store = TrainingStore(tmp_path / "human.sqlite3")
    bot = MultiwayBot(engine=main.engine, opponent_model_provider=store.bot_opponent_model)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "bot", bot)
    monkeypatch.setattr(main, "GAMES", {})
    monkeypatch.setattr(main, "SOLVER_CACHE", {})
    monkeypatch.setattr(main, "ACTIVE_HAND_ID", None)
    monkeypatch.setattr(main, "NEXT_BUTTON_SEAT", 0)

    client = TestClient(main.app)
    started = client.post("/api/game/new")
    assert started.status_code == 200
    state = started.json()
    # In a human table autoplay may stop directly on the human turn.
    stepped = client.post(f"/api/game/{state['hand_id']}/bot-step")
    assert stepped.status_code == 400


def test_busted_bot_leaves_seat_and_enters_cooldown(tmp_path):
    store = make_bot_only_store(tmp_path, bot_count=3)
    bot = [r for r in store.active_seats() if r["occupant_type"] == "bot"][0]
    seat = bot["seat"]
    store.set_balance(bot["id"], 0.25)
    store.set_bot_cooldown_minutes(5)

    busted = store.eject_busted_bots(minimum_stack=1.0)
    assert len(busted) == 1
    assert busted[0]["player_id"] == bot["id"]
    freed = next(r for r in store.get_table() if r["seat"] == seat)
    assert freed["occupant_type"] == "empty"
    assert freed["active"] is False
    waiting = store.bot_cooldowns()
    assert len(waiting) == 1
    assert waiting[0]["remaining_seconds"] > 0


def test_human_can_take_busted_bots_old_seat(tmp_path):
    store = make_bot_only_store(tmp_path, bot_count=3)
    bot = [r for r in store.active_seats() if r["occupant_type"] == "bot"][0]
    old_seat = bot["seat"]
    store.set_balance(bot["id"], 0.0)
    store.eject_busted_bots(minimum_stack=1.0, minutes=5)

    human = store.create_profile("Артём")
    row = store.set_human_seat(old_seat, human["id"])
    assert row["occupant_type"] == "human"
    assert row["profile_id"] == human["id"]
    # Cooldown belongs to the bot, not the chair.
    assert store.bot_cooldowns()[0]["player_id"] == bot["id"]


def test_ready_bot_returns_to_another_free_seat_if_old_one_taken(tmp_path):
    store = make_bot_only_store(tmp_path, bot_count=3)
    bot = [r for r in store.active_seats() if r["occupant_type"] == "bot"][0]
    old_seat = bot["seat"]
    store.set_balance(bot["id"], 0.0)
    store.eject_busted_bots(minimum_stack=1.0, minutes=5)
    human = store.create_profile("Макс")
    store.set_human_seat(old_seat, human["id"])

    # Fast-forward this cooldown without sleeping.
    with store._connect() as con:
        con.execute("UPDATE bot_cooldowns SET return_at='2000-01-01T00:00:00+00:00' WHERE player_id=?", (bot["id"],))
    returned = store.return_ready_bots()
    assert len(returned) == 1
    assert returned[0]["player_id"] == bot["id"]
    assert returned[0]["seat"] != old_seat
    assert store.get_balance(bot["id"]) == 1000.0
    assert next(r for r in store.get_table() if r["seat"] == old_seat)["occupant_type"] == "human"


def test_cooldown_only_accepts_5_10_15(tmp_path):
    store = make_bot_only_store(tmp_path, bot_count=2)
    for minutes in (5, 10, 15):
        assert store.set_bot_cooldown_minutes(minutes) == minutes
        assert store.bot_cooldown_minutes() == minutes
    with pytest.raises(ValueError):
        store.set_bot_cooldown_minutes(7)


def test_instant_rebuy_endpoint_is_disabled(tmp_path, monkeypatch):
    store = TrainingStore(tmp_path / "rebuy-disabled.sqlite3")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "GAMES", {})
    monkeypatch.setattr(main, "ACTIVE_HAND_ID", None)
    client = TestClient(main.app)
    res = client.post("/api/table/rebuy-busted-bots")
    assert res.status_code == 410


def test_cooldown_setting_endpoint(tmp_path, monkeypatch):
    store = TrainingStore(tmp_path / "cooldown-api.sqlite3")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "GAMES", {})
    monkeypatch.setattr(main, "ACTIVE_HAND_ID", None)
    client = TestClient(main.app)
    res = client.post("/api/table/bot-cooldown", json={"minutes": 15})
    assert res.status_code == 200
    assert res.json()["minutes"] == 15
    assert store.bot_cooldown_minutes() == 15
