from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from bisect import bisect_left
import random

from poker.evaluator import HandEvaluator, RANK_VALUE
from poker.models import ActionType, GameState, Street


RANKS = "23456789TJQKA"
SUITS = "shdc"
ALL_CARDS = [r + s for r in RANKS for s in SUITS]


def canonical_hand(cards: tuple[str, str] | list[str]) -> str:
    a, b = cards
    ra, rb = a[0], b[0]
    va, vb = RANK_VALUE[ra], RANK_VALUE[rb]

    if va == vb:
        return f"{ra}{rb}"

    if vb > va:
        a, b = b, a
        ra, rb = a[0], b[0]

    suited = "s" if a[1] == b[1] else "o"
    return f"{ra}{rb}{suited}"


def preflop_strength(cards: tuple[str, str] | list[str]) -> float:
    """Fast 0..1 heuristic used for range likelihoods, not as a solver."""
    a, b = cards
    va, vb = RANK_VALUE[a[0]], RANK_VALUE[b[0]]
    hi, lo = max(va, vb), min(va, vb)
    pair = hi == lo
    suited = a[1] == b[1]
    gap = hi - lo

    if pair:
        # 22 ~ .52, AA = 1.0
        return min(1.0, 0.44 + (hi - 2) * 0.04)

    score = 0.12
    score += (hi - 2) / 12 * 0.43
    score += (lo - 2) / 12 * 0.16

    if suited:
        score += 0.08

    if gap == 1:
        score += 0.07
    elif gap == 2:
        score += 0.035
    elif gap >= 5:
        score -= 0.05

    if hi >= 11 and lo >= 10:
        score += 0.09
    elif hi >= 12 and lo >= 8:
        score += 0.035

    # Ace-wheel suited hands retain playability.
    if hi == 14 and lo <= 5 and suited:
        score += 0.04

    return max(0.02, min(0.99, score))


def _has_flush_draw(cards: list[str]) -> bool:
    counts = {s: 0 for s in SUITS}
    for c in cards:
        counts[c[1]] += 1
    return max(counts.values()) == 4


def _has_straight_draw(cards: list[str]) -> bool:
    ranks = {RANK_VALUE[c[0]] for c in cards}
    if 14 in ranks:
        ranks.add(1)

    for start in range(1, 11):
        window = set(range(start, start + 5))
        if len(window & ranks) == 4:
            return True
    return False


def postflop_strength(cards: tuple[str, str] | list[str], board: list[str]) -> float:
    evaluator = HandEvaluator()
    all_cards = list(cards) + board

    if len(all_cards) < 5:
        return preflop_strength(cards)

    category = evaluator.score(list(cards), board)[0]
    base = {
        0: 0.18,
        1: 0.40,
        2: 0.57,
        3: 0.68,
        4: 0.76,
        5: 0.80,
        6: 0.88,
        7: 0.96,
        8: 0.995,
    }[category]

    # Draws matter mostly when the current made hand is weak.
    if category <= 1:
        if _has_flush_draw(all_cards):
            base += 0.13
        if _has_straight_draw(all_cards):
            base += 0.10

    # Overcards / strong hole-card quality are a small tiebreaker.
    base += (preflop_strength(cards) - 0.5) * 0.08
    return max(0.02, min(0.995, base))


@dataclass
class RangeEntry:
    cards: tuple[str, str]
    weight: float


class RangeModel:
    """
    Weighted combo range for one opponent.

    The model starts from every unblocked 2-card combination and applies
    action-likelihood updates. It is intentionally lightweight: it gives the
    bot a coherent range model now and can later be replaced by solver priors.
    """

    def __init__(self, dead_cards: list[str] | None = None):
        dead = set(dead_cards or [])
        self.weights: dict[tuple[str, str], float] = {
            combo: 1.0
            for combo in combinations(ALL_CARDS, 2)
            if combo[0] not in dead and combo[1] not in dead
        }
        self._sample_combos = []
        self._sample_cumulative = []
        self._sample_total = 0.0
        self.normalize()

    @classmethod
    def from_state(
        cls,
        state: GameState,
        opponent_id: str,
        observer_id: str,
    ) -> "RangeModel":
        dead = list(state.players[observer_id].hole_cards) + list(state.board)
        model = cls(dead_cards=dead)

        for action in state.history:
            if action.player_id != opponent_id:
                continue
            model.update(
                action=action.action,
                amount=action.amount,
                street=action.street,
                board=_board_at_street(state.board, action.street),
                pot_after=action.pot_after,
            )

        # Current-board blockers may have appeared after earlier actions.
        model.remove_blocked(dead)
        model.normalize()
        return model

    def remove_blocked(self, dead_cards: list[str]):
        dead = set(dead_cards)
        self.weights = {
            combo: w
            for combo, w in self.weights.items()
            if combo[0] not in dead and combo[1] not in dead
        }

    def update(
        self,
        action: ActionType,
        amount: float,
        street: Street,
        board: list[str],
        pot_after: float = 0.0,
    ):
        new_weights = {}

        for combo, old_weight in self.weights.items():
            strength = (
                preflop_strength(combo)
                if street == Street.PREFLOP
                else postflop_strength(combo, board)
            )

            likelihood = self._action_likelihood(
                action=action,
                strength=strength,
                amount=amount,
                pot_after=pot_after,
                street=street,
            )
            new_weights[combo] = old_weight * max(0.002, likelihood)

        self.weights = new_weights
        self.normalize()

    def _action_likelihood(
        self,
        action: ActionType,
        strength: float,
        amount: float,
        pot_after: float,
        street: Street,
    ) -> float:
        s = strength

        if street == Street.PREFLOP:
            if action == ActionType.CALL:
                # Calls cluster in the middle but include traps.
                return 0.18 + 0.95 * (1.0 - abs(s - 0.58) * 1.35) + 0.18 * s
            if action in (ActionType.RAISE, ActionType.BET):
                # Strong hands raise often; suited/connected weak hands survive as bluffs.
                return 0.08 + 1.40 * (s ** 2.15) + 0.10 * (1.0 - s)
            if action == ActionType.ALL_IN:
                return 0.01 + 2.8 * (s ** 5.0)
            if action == ActionType.CHECK:
                return 0.35 + 0.85 * (1.0 - s) + 0.15 * s
            if action == ActionType.FOLD:
                return 0.10 + 1.45 * ((1.0 - s) ** 2.0)

        # Postflop. Larger bets polarize the range slightly more.
        sizing = 0.0
        if pot_after > 0 and amount > 0:
            pot_before_approx = max(0.5, pot_after - amount)
            sizing = min(2.0, amount / pot_before_approx)

        if action == ActionType.CHECK:
            # Mostly weak/medium, with a small slow-play tail.
            return 0.35 + 0.95 * (1.0 - s) + 0.18 * (s ** 4)
        if action == ActionType.CALL:
            return 0.12 + 1.15 * (1.0 - abs(s - 0.62) * 1.45) + 0.18 * s
        if action == ActionType.BET:
            value = 0.12 + 1.15 * (s ** (1.45 + 0.25 * sizing))
            bluff = 0.11 + 0.16 * (1.0 - s) * (0.7 + sizing)
            return value + bluff
        if action == ActionType.RAISE:
            value = 0.04 + 1.8 * (s ** (2.2 + 0.25 * sizing))
            bluff = 0.04 + 0.11 * (1.0 - s) * min(1.4, 0.6 + sizing)
            return value + bluff
        if action == ActionType.ALL_IN:
            return 0.015 + 2.5 * (s ** 4.2) + 0.05 * (1.0 - s)
        if action == ActionType.FOLD:
            return 0.08 + 1.4 * ((1.0 - s) ** 1.8)

        return 1.0

    def normalize(self):
        total = sum(self.weights.values())
        if total <= 0:
            self._rebuild_sampler()
            return
        inv = 1.0 / total
        for combo in list(self.weights):
            self.weights[combo] *= inv
        self._rebuild_sampler()

    def _rebuild_sampler(self):
        self._sample_combos = []
        self._sample_cumulative = []
        running = 0.0
        for combo, weight in self.weights.items():
            if weight <= 0:
                continue
            running += weight
            self._sample_combos.append(combo)
            self._sample_cumulative.append(running)
        self._sample_total = running

    def sample(self, excluded: set[str] | None = None) -> tuple[str, str] | None:
        if not self._sample_combos or self._sample_total <= 0:
            return None

        excluded = excluded or set()
        # Usually blockers were already removed when the range was built, so
        # this succeeds on the first draw and sampling is O(log N).
        for _ in range(12):
            target = random.random() * self._sample_total
            idx = min(bisect_left(self._sample_cumulative, target), len(self._sample_combos) - 1)
            combo = self._sample_combos[idx]
            if combo[0] not in excluded and combo[1] not in excluded:
                return combo

        # Rare fallback if caller supplied new blockers after sampler creation.
        viable = [(c, w) for c, w in self.weights.items() if c[0] not in excluded and c[1] not in excluded]
        if not viable:
            return None
        total = sum(w for _, w in viable)
        target = random.random() * total
        running = 0.0
        for combo, weight in viable:
            running += weight
            if running >= target:
                return combo
        return viable[-1][0]

    def top_hands(self, limit: int = 12) -> list[dict]:
        by_class: dict[str, float] = {}
        for combo, weight in self.weights.items():
            label = canonical_hand(combo)
            by_class[label] = by_class.get(label, 0.0) + weight

        ranked = sorted(by_class.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [
            {"hand": hand, "weight": round(weight, 4)}
            for hand, weight in ranked
        ]

    def effective_combo_count(self) -> float:
        # Inverse Simpson index: useful summary of how concentrated the range is.
        denom = sum(w * w for w in self.weights.values())
        return 1.0 / denom if denom > 0 else 0.0


def _board_at_street(full_board: list[str], street: Street) -> list[str]:
    if street == Street.PREFLOP:
        return []
    if street == Street.FLOP:
        return full_board[:3]
    if street == Street.TURN:
        return full_board[:4]
    return full_board[:5]
