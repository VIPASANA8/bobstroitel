from poker.engine import PokerEngine
from poker.models import ActionType
from solver.mccfr import LocalMCCFRSolver


def test_solver_returns_normalized_strategy_preflop():
    engine = PokerEngine()
    solver = LocalMCCFRSolver(engine)
    state = engine.new_hand(button="hero")

    result = solver.solve(state, "hero", iterations=80)

    assert result["actions"]
    total = sum(row["frequency"] for row in result["actions"])
    assert abs(total - 1.0) < 0.02
    assert result["best_action_key"]


def test_solver_contains_exact_custom_raise_size():
    engine = PokerEngine()
    solver = LocalMCCFRSolver(engine)
    state = engine.new_hand(button="hero")

    result = solver.solve(
        state,
        "hero",
        iterations=60,
        extra_action=ActionType.RAISE,
        extra_amount=3.7,
    )

    assert any(
        row["action"] == "raise" and abs(row["amount"] - 3.7) < 1e-9
        for row in result["actions"]
    )


def test_review_has_nonnegative_ev_loss():
    engine = PokerEngine()
    solver = LocalMCCFRSolver(engine)
    state = engine.new_hand(button="hero")

    result = solver.solve(state, "hero", iterations=70)
    review = solver.review_action(
        result,
        ActionType.CALL,
        0.5,
        street=state.street,
        board=state.board,
    )

    assert review["ev_loss_bb"] >= 0
    assert review["grade"]
    assert review["chosen"]["action"] == "call"
