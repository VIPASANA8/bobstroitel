from poker.models import ActionType, Street
from ranges.model import RangeModel, canonical_hand, preflop_strength


def test_canonical_hand_labels():
    assert canonical_hand(("As", "Ah")) == "AA"
    assert canonical_hand(("As", "Ks")) == "AKs"
    assert canonical_hand(("As", "Kh")) == "AKo"


def test_preflop_strength_order():
    assert preflop_strength(("As", "Ah")) > preflop_strength(("7s", "6s"))
    assert preflop_strength(("7s", "6s")) > preflop_strength(("7s", "2h"))


def test_blockers_are_removed():
    model = RangeModel(dead_cards=["As", "Kd"])
    assert all("As" not in combo and "Kd" not in combo for combo in model.weights)


def test_raise_shifts_weight_toward_strong_hands():
    model = RangeModel()
    aa = tuple(sorted(("As", "Ah")))
    seven_two = tuple(sorted(("7s", "2h")))

    # combinations() stores cards in deck order, so locate exact keys robustly.
    aa_key = next(k for k in model.weights if set(k) == {"As", "Ah"})
    weak_key = next(k for k in model.weights if set(k) == {"7s", "2h"})
    ratio_before = model.weights[aa_key] / model.weights[weak_key]

    model.update(ActionType.RAISE, amount=3.0, street=Street.PREFLOP, board=[], pot_after=4.5)
    ratio_after = model.weights[aa_key] / model.weights[weak_key]

    assert ratio_after > ratio_before
