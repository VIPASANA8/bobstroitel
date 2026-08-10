from poker.evaluator import HandEvaluator


def test_two_pair_description_includes_pairs_and_kicker():
    evaluator = HandEvaluator()
    board = ["Kh", "Kd", "Tc", "2s", "3d"]
    text = evaluator.describe(["Ts", "Ah"], board)

    assert "две пары" in text
    assert "короли" in text
    assert "десятки" in text
    assert "кикер туз" in text


def test_same_two_pair_can_be_decided_by_kicker():
    evaluator = HandEvaluator()
    board = ["Kh", "Kd", "Tc", "Ts", "3d"]

    assert evaluator.compare(["Ah", "2c"], ["Qh", "Jc"], board) == "hero"
    assert evaluator.class_name(["Ah", "2c"], board) == "две пары"
    assert evaluator.class_name(["Qh", "Jc"], board) == "две пары"
