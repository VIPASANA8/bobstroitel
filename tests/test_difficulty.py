from bots.cfr_bot import CFRLiteBot
from bots.difficulty import DIFFICULTIES, get_difficulty, normalize_difficulty
from poker.engine import PokerEngine


def test_all_four_difficulties_exist():
    assert list(DIFFICULTIES) == ["easy", "normal", "hard", "maximum"]
    assert DIFFICULTIES["easy"].iterations < DIFFICULTIES["normal"].iterations
    assert DIFFICULTIES["normal"].iterations < DIFFICULTIES["hard"].iterations
    assert DIFFICULTIES["hard"].iterations < DIFFICULTIES["maximum"].iterations


def test_russian_aliases():
    assert normalize_difficulty("лёгкий") == "easy"
    assert normalize_difficulty("нормальный") == "normal"
    assert normalize_difficulty("сложный") == "hard"
    assert normalize_difficulty("максимальный") == "maximum"
    assert normalize_difficulty("unknown") == "normal"


def test_profile_is_publicly_serializable():
    data = get_difficulty("hard").public_dict()
    assert data["key"] == "hard"
    assert data["label"] == "Сложный"
    assert data["iterations"] == 420
    assert "description" in data


def test_bot_action_is_legal_on_each_level():
    engine = PokerEngine()
    bot = CFRLiteBot()

    for level in DIFFICULTIES:
        # With bot on the button it acts first preflop.
        state = engine.new_hand(button="bot")
        state.difficulty = level
        legal = engine.legal_actions(state, "bot")
        decision = bot.decide(state, "bot")
        assert decision.action in legal
