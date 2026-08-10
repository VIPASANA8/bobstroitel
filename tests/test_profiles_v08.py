from persistence import TrainingStore
from poker.engine import PokerEngine
from poker.models import ActionType
from bots.multiway import MultiwayBot


def test_profiles_have_independent_bankrolls(tmp_path):
    store = TrainingStore(tmp_path / "profiles.sqlite3")
    original = store.get_profile_record()
    second = store.create_profile("Артём")

    store.activate_profile(second["id"])
    store.set_profile_balance(second["id"], 777.25)
    assert store.get_table()[0]["name"] == "Артём"
    assert store.get_table()[0]["balance"] == 777.25

    store.activate_profile(original["id"])
    assert store.get_table()[0]["name"] == original["name"]
    assert store.get_table()[0]["balance"] == 1000.0


def test_completed_hands_are_isolated_by_profile(tmp_path):
    store = TrainingStore(tmp_path / "hands.sqlite3")
    engine = PokerEngine()
    first_id = store.active_profile_id()

    state = engine.new_hand(store.active_seats(), button_seat=0)
    engine.apply_action(state, "hero", ActionType.FOLD)
    store.save_state(state)
    assert store.profile(first_id)["hands"] == 1

    second = store.create_profile("Макс")
    store.activate_profile(second["id"])
    state2 = engine.new_hand(store.active_seats(), button_seat=0)
    engine.apply_action(state2, "hero", ActionType.FOLD)
    store.save_state(state2)

    assert store.profile(first_id)["hands"] == 1
    assert store.profile(second["id"])["hands"] == 1


def test_training_sample_contains_decision_context(tmp_path):
    store = TrainingStore(tmp_path / "samples.sqlite3")
    engine = PokerEngine()
    state = engine.new_hand(store.active_seats(), button_seat=0)
    engine.apply_action(state, "hero", ActionType.FOLD)
    store.save_state(state)

    samples = store.training_samples(limit=10)
    assert len(samples) == 1
    sample = samples[0]
    assert sample["action"] == "fold"
    assert sample["pot_before"] == 1.5
    assert sample["to_call_before"] == 0.5
    assert sample["live_players_before"] == 2
    assert sample["position"] == "BTN / SB"


def test_long_term_model_builds_traits_and_bot_can_read_it(tmp_path):
    stats = {
        "id": "p_test",
        "name": "Тест",
        "hands": 120,
        "hero_balance": 1000.0,
        "balance": 1000.0,
        "vpip": 52.0,
        "pfr": 24.0,
        "three_bet": 5.0,
        "three_bet_opportunities": 20,
        "fold_to_3bet": 78.0,
        "fold_to_3bet_opportunities": 15,
        "postflop_aggression": 0.9,
        "avg_ev_loss_bb": 0.45,
        "decisions_reviewed": 30,
        "win_rate_hands": 48.0,
    }
    model = TrainingStore._build_model(stats)
    keys = {row["key"] for row in model["traits"]}
    assert "loose" in keys
    assert "overfold_3bet" in keys
    assert model["confidence"] == 0.6

    engine = PokerEngine()
    state = engine.new_hand(button="hero")
    provider = lambda: {
        "name": "Тест",
        "confidence": model["confidence"],
        "exploit": model["exploit"],
    }
    bot = MultiwayBot(engine=engine, opponent_model_provider=provider)
    adj = bot._profile_adjustments(state, "bot", "maximum")
    assert adj["confidence"] > 0
    assert adj["value"] > 0
    assert adj["pressure"] > 0


def test_discard_incomplete_hand_keeps_bankroll_and_removes_lock_record(tmp_path):
    store = TrainingStore(tmp_path / "abort.sqlite3")
    engine = PokerEngine()
    before = store.get_profile_record()["balance"]

    state = engine.new_hand(store.active_seats(), button_seat=0)
    store.save_state(state)
    assert store.discard_incomplete_hand(state.hand_id) is True

    assert store.get_profile_record()["balance"] == before
    assert store.recent_hands(limit=10) == []
    assert store.training_samples(limit=10) == []
    assert store.discard_incomplete_hand(state.hand_id) is False
