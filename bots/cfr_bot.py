from __future__ import annotations

import math
import random

from bots.base import PokerBot, BotDecision
from bots.difficulty import get_difficulty
from poker.models import ActionType
from solver.mccfr import LocalMCCFRSolver


class CFRLiteBot(PokerBot):
    """CFR-lite bot with four configurable skill levels."""

    def __init__(self):
        self.solver = LocalMCCFRSolver()

    @staticmethod
    def _weighted_choice(rows: list[dict], weights: list[float]) -> dict:
        total = sum(max(0.0, w) for w in weights)
        if total <= 1e-12:
            return random.choice(rows)

        target = random.random() * total
        cumulative = 0.0
        for row, weight in zip(rows, weights):
            cumulative += max(0.0, weight)
            if target <= cumulative:
                return row
        return rows[-1]

    def _sample_policy(self, rows: list[dict], policy_power: float) -> dict:
        # Power < 1 flattens the strategy and creates more human-like variance
        # without turning the opponent into a purely random bot.
        weights = [max(1e-6, float(row["frequency"])) ** policy_power for row in rows]
        return self._weighted_choice(rows, weights)

    def _sample_plausible_mistake(self, rows: list[dict], max_loss: float) -> dict | None:
        best_ev = max(float(row["ev_bb"]) for row in rows)
        candidates = []
        weights = []

        for row in rows:
            loss = max(0.0, best_ev - float(row["ev_bb"]))
            if loss <= 0.025 or loss > max_loss:
                continue
            candidates.append(row)
            # Prefer smaller mistakes, while retaining some strategy frequency.
            scale = max(0.18, max_loss * 0.42)
            weight = math.exp(-loss / scale) * (0.20 + float(row["frequency"]))
            weights.append(weight)

        if not candidates:
            return None
        return self._weighted_choice(candidates, weights)

    def decide(self, state, player_id: str) -> BotDecision:
        profile = get_difficulty(getattr(state, "difficulty", "normal"))
        result = self.solver.solve(state, player_id, iterations=profile.iterations)
        rows = result["actions"]

        chosen = None
        artificial_mistake = False

        if profile.mistake_rate > 0 and random.random() < profile.mistake_rate:
            chosen = self._sample_plausible_mistake(rows, profile.max_mistake_ev_bb)
            artificial_mistake = chosen is not None

        if chosen is None:
            chosen = self._sample_policy(rows, profile.policy_power)

        action = ActionType(chosen["action"])
        amount = float(chosen["amount"])
        suffix = " · учебное отклонение" if artificial_mistake else ""

        return BotDecision(
            action=action,
            amount=amount,
            confidence=max(0.20, float(chosen["frequency"])),
            reason=(
                f"{profile.label} · CFR-lite {profile.iterations} ит.: "
                f"частота {chosen['frequency'] * 100:.1f}%, "
                f"EV {chosen['ev_bb']:+.2f} ББ{suffix}"
            ),
        )
