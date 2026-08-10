import pytest

from persistence.store import TrainingStore
from poker.engine import PokerEngine
from poker.models import ActionType


def make_two_human_table(store):
    second = store.create_profile("Артём")
    store.clear_seat(1)
    store.set_human_seat(1, second["id"])
    return second


def test_three_human_profiles_can_share_one_table(tmp_path):
    store = TrainingStore(tmp_path / "v09.sqlite3")
    p2 = store.create_profile("Артём")
    p3 = store.create_profile("Макс")
    store.set_human_seat(2, p2["id"])
    store.set_human_seat(4, p3["id"])

    humans = [r for r in store.active_seats() if r["occupant_type"] == "human"]
    assert {r["profile_id"] for r in humans} == {"profile_default", p2["id"], p3["id"]}

    with pytest.raises(ValueError):
        store.set_human_seat(5, p2["id"])


def test_hotseat_public_state_only_reveals_current_human(tmp_path):
    store = TrainingStore(tmp_path / "privacy.sqlite3")
    p2 = make_two_human_table(store)
    engine = PokerEngine()
    state = engine.new_hand(store.active_seats(), button_seat=0)

    assert state.acting_player == "hero"
    other_id = next(pid for pid in state.seat_order if pid != "hero")
    first_view = state.to_dict(viewer_player_id="hero")
    assert first_view["players"]["hero"]["hole_cards"] != ["??", "??"]
    assert first_view["players"][other_id]["hole_cards"] == ["??", "??"]

    engine.apply_action(state, "hero", ActionType.CALL)
    assert state.acting_player == other_id
    second_view = state.to_dict(viewer_player_id=other_id)
    assert second_view["players"]["hero"]["hole_cards"] == ["??", "??"]
    assert second_view["players"][other_id]["hole_cards"] != ["??", "??"]


def test_completed_multi_human_hand_updates_both_profiles(tmp_path):
    store = TrainingStore(tmp_path / "balances.sqlite3")
    p2 = make_two_human_table(store)
    engine = PokerEngine()
    state = engine.new_hand(store.active_seats(), button_seat=0)

    engine.apply_action(state, "hero", ActionType.FOLD)
    assert state.terminal
    store.save_state(state)

    assert store.get_profile_record("profile_default")["balance"] == 999.5
    assert store.get_profile_record(p2["id"])["balance"] == 1000.5
    assert store.profile("profile_default")["hands"] == 1
    assert store.profile(p2["id"])["hands"] == 1


def test_saved_tables_keep_independent_compositions(tmp_path):
    store = TrainingStore(tmp_path / "tables.sqlite3")
    p2 = store.create_profile("Артём")
    store.set_human_seat(2, p2["id"])
    table_a = store.save_current_table("Стол A", button_seat=2)

    # Save a copy first; it becomes the current autosaved table.
    table_b = store.save_current_table("Стол B", button_seat=0)
    store.clear_seat(2)
    store.add_bot(3, "Ruby", "hard")

    store.load_saved_table(table_a["id"])
    seats_a = store.get_table()
    assert next(r for r in seats_a if r["seat"] == 2)["profile_id"] == p2["id"]
    assert not next(r for r in seats_a if r["seat"] == 3)["active"]

    store.load_saved_table(table_b["id"])
    seats_b = store.get_table()
    assert not next(r for r in seats_b if r["seat"] == 2)["active"]
    assert next(r for r in seats_b if r["seat"] == 3)["name"] == "Ruby"


def test_saved_table_restores_bot_balance(tmp_path):
    store = TrainingStore(tmp_path / "botbalance.sqlite3")
    store.set_balance("bot_1", 1234.5)
    saved = store.save_current_table("Балансный стол", button_seat=0)
    store.set_balance("bot_1", 800.0)
    # The current saved table autosaves only on table mutations, not raw balance writes.
    store.load_saved_table(saved["id"])
    bot = next(r for r in store.get_table() if r["seat"] == 1)
    assert bot["balance"] == 1234.5
