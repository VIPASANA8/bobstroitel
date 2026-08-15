from fastapi.testclient import TestClient

import app.legacy as main
from bots.multiway import MultiwayBot
from persistence.store import TrainingStore


def test_mixed_table_advances_bots_one_step_at_a_time(tmp_path, monkeypatch):
    store = TrainingStore(tmp_path / "v10_mixed.sqlite3")
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
    assert state["human_count"] == 1
    assert state["bot_count"] == 1

    # Default two-seat table starts with the human on the button/SB.
    assert state["acting_human_player_id"] is not None
    action = "call" if "call" in state["human_legal_actions"] else state["human_legal_actions"][0]
    acted = client.post(f"/api/game/{state['hand_id']}/action", json={"action": action, "amount": 0})
    assert acted.status_code == 200
    after_human = acted.json()

    # v0.10 must expose the bot turn instead of instantly autoplaying it.
    assert after_human["terminal"] is False
    assert after_human["acting_human_player_id"] is None
    bot_id = after_human["acting_player"]
    assert after_human["players"][bot_id]["is_bot"] is True
    before = len(after_human["history"])

    stepped = client.post(f"/api/game/{state['hand_id']}/bot-step")
    assert stepped.status_code == 200
    after_bot = stepped.json()
    assert len(after_bot["history"]) == before + 1 or after_bot["terminal"]
    assert "last_bot_decision" in after_bot
