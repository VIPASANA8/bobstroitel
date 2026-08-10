from persistence.store import TrainingStore
from poker.engine import PokerEngine
from poker.models import ActionType


def test_bankroll_initializes_to_1000(tmp_path):
    store = TrainingStore(tmp_path / "trainer.sqlite3")
    assert store.get_balances() == {"hero": 1000.0, "bot": 1000.0}


def test_completed_hand_persists_balances_and_history(tmp_path):
    store = TrainingStore(tmp_path / "trainer.sqlite3")
    engine = PokerEngine()
    state = engine.new_hand(button="hero", hero_stack=1000, bot_stack=1000)
    state.difficulty = "normal"

    engine.apply_action(state, "hero", ActionType.FOLD)
    store.save_state(state)

    balances = store.get_balances()
    assert balances["hero"] == 999.5
    assert balances["bot"] == 1000.5
    assert sum(balances.values()) == 2000.0

    profile = store.profile()
    assert profile["hands"] == 1

    recent = store.recent_hands(10)
    assert len(recent) == 1
    assert recent[0]["winner"] == "bot"


def test_bankroll_survives_new_store_instance(tmp_path):
    path = tmp_path / "trainer.sqlite3"
    first = TrainingStore(path)
    first.set_balances(876.25, 1123.75)

    second = TrainingStore(path)
    assert second.get_balances() == {"hero": 876.25, "bot": 1123.75}
