from __future__ import annotations

import random

from bots.base import PokerBot, BotDecision
from bots.difficulty import get_difficulty
from poker.equity import estimate_multiway_equity
from poker.models import ActionType, Street


class MultiwayBot(PokerBot):
    """Fast local opponent for 3-7 handed pots.

    v0.8 uses a multiway equity/pot-odds policy instead of
    pretending the heads-up CFR-lite tree is a 7-max solver.
    """

    def __init__(self, engine=None, opponent_model_provider=None):
        if engine is None:
            from poker.engine import PokerEngine
            engine = PokerEngine()
        self.engine = engine
        self.opponent_model_provider = opponent_model_provider

    def _profile_adjustments(self, state, player_id: str, difficulty_key: str) -> dict:
        """Confidence-gated exploit adjustment against the most relevant human.

        v0.9 can have several real profiles in one pot. If the last aggressor is a
        human, that profile is the primary target; otherwise we use the live human
        with the most mature model.
        """
        empty = {
            "confidence": 0.0, "value": 0.0, "pressure": 0.0,
            "call_down": 0.0, "passivity": 0.0, "name": "", "profile_id": None,
        }
        if not callable(self.opponent_model_provider):
            return empty

        humans = [
            p for pid, p in state.players.items()
            if pid != player_id and not p.is_bot and not p.folded and (p.profile_id or p.id == "hero")
        ]
        if not humans:
            return empty

        ordered = humans
        if state.last_aggressor in state.players:
            aggr = state.players[state.last_aggressor]
            if not aggr.is_bot and aggr.profile_id:
                ordered = [aggr] + [p for p in humans if p.id != aggr.id]

        candidates = []
        for human in ordered:
            try:
                try:
                    model = self.opponent_model_provider(human.profile_id) or {}
                except TypeError:
                    model = self.opponent_model_provider() or {}
            except Exception:
                continue
            candidates.append((human, model))
        if not candidates:
            return empty

        # Prefer last human aggressor; otherwise the highest-confidence profile.
        if state.last_aggressor and candidates[0][0].id == state.last_aggressor:
            human, model = candidates[0]
        else:
            human, model = max(candidates, key=lambda x: float(x[1].get("confidence", 0.0)))

        scale_by_level = {"easy": 0.15, "normal": 0.40, "hard": 0.75, "maximum": 1.0}
        confidence = float(model.get("confidence", 0.0)) * scale_by_level.get(difficulty_key, 0.4)
        exploit = model.get("exploit", {}) or {}
        return {
            "confidence": confidence,
            "value": float(exploit.get("value_widen", 0.0)) * confidence,
            "pressure": float(exploit.get("bluff_pressure", 0.0)) * confidence,
            "call_down": float(exploit.get("call_down", 0.0)) * confidence,
            "passivity": float(exploit.get("preflop_passivity", 0.0)) * confidence,
            "name": str(model.get("name", human.name)),
            "profile_id": human.profile_id or ("legacy_hero" if human.id == "hero" else None),
        }

    SAMPLE_COUNT = {
        "easy": 90,
        "normal": 180,
        "hard": 360,
        "maximum": 700,
    }

    @staticmethod
    def _preflop_bonus(cards: list[str]) -> float:
        values = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
                  "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
        a, b = cards
        r1, r2 = values[a[0]], values[b[0]]
        hi, lo = max(r1, r2), min(r1, r2)
        suited = a[1] == b[1]
        pair = r1 == r2
        bonus = 0.0
        if pair:
            bonus += 0.08 + max(0, hi - 8) * 0.008
        if suited:
            bonus += 0.018
        if hi >= 13:
            bonus += 0.025
        if hi >= 11 and lo >= 10:
            bonus += 0.025
        if abs(r1 - r2) <= 1 and hi >= 8:
            bonus += 0.012
        return bonus

    def decide(self, state, player_id: str) -> BotDecision:
        player = state.players[player_id]
        profile = get_difficulty(player.difficulty)
        legal = self.engine.legal_actions(state, player_id)
        exploit = self._profile_adjustments(state, player_id, profile.key)

        live_opponents = max(1, len([pid for pid in state.live_ids() if pid != player_id]))
        samples = self.SAMPLE_COUNT[profile.key]
        equity = estimate_multiway_equity(
            player.hole_cards,
            state.board,
            opponents=live_opponents,
            samples=samples,
        )
        if state.street == Street.PREFLOP:
            equity = min(1.0, equity + self._preflop_bonus(player.hole_cards))

        engine = self.engine
        to_call = engine.to_call(state, player_id)
        pot_odds = to_call / max(state.pot + to_call, 1e-9) if to_call > 0 else 0.0
        baseline = 1.0 / (live_opponents + 1)

        # Difficulty: easier bots over-fold, under-value-bet and occasionally
        # choose a nearby inferior line. Maximum has no artificial mistake.
        mistake = random.random() < profile.mistake_rate
        noise = {
            "easy": 0.075,
            "normal": 0.035,
            "hard": 0.012,
            "maximum": 0.0,
        }[profile.key]
        perceived = max(0.0, min(1.0, equity + random.uniform(-noise, noise)))
        # Against a historically aggressive human, stronger bots defend a little wider.
        if state.last_aggressor in state.players and not state.players[state.last_aggressor].is_bot:
            perceived = max(0.0, min(1.0, perceived + exploit["call_down"] * 0.025))

        profile_note = f", модель {exploit['confidence'] * 100:.0f}%" if exploit["confidence"] > 0.02 else ""

        if to_call > 0:
            fold_threshold = pot_odds * (1.10 if profile.key == "easy" else 0.97)
            if perceived < fold_threshold and ActionType.FOLD in legal:
                return BotDecision(action=ActionType.FOLD, confidence=0.7,
                                   reason=f"equity {equity:.2f}, pot odds {pot_odds:.2f}")

            strong_threshold = max(baseline + 0.13, pot_odds + 0.20) - max(0.0, exploit["value"]) * 0.035
            strong = perceived > strong_threshold

            # If this profile has repeatedly over-folded to 3-bets, strong bots add
            # a low-frequency exploitative re-raise with hands just below value range.
            pressure_reraise = (
                state.street == Street.PREFLOP
                and state.last_aggressor in state.players
                and not state.players[state.last_aggressor].is_bot
                and ActionType.RAISE in legal
                and exploit["pressure"] > 0.10
                and perceived > max(pot_odds + 0.06, baseline - 0.02)
                and random.random() < 0.10 * exploit["pressure"]
            )
            if (strong or pressure_reraise) and ActionType.RAISE in legal and not (mistake and profile.key in {"easy", "normal"}):
                target = max(engine.min_raise_to(state, player_id), state.current_bet + state.pot * 0.48)
                target = min(player.street_invested + player.stack, target)
                return BotDecision(action=ActionType.RAISE, amount=round(target, 2), confidence=0.72,
                                   reason=f"multiway value/pressure raise, equity {equity:.2f}{profile_note}")

            if mistake and profile.key == "easy" and ActionType.FOLD in legal and random.random() < 0.4:
                return BotDecision(action=ActionType.FOLD, confidence=0.3, reason="учебная ошибка")

            return BotDecision(action=ActionType.CALL, amount=round(min(player.stack, to_call), 2), confidence=0.58,
                               reason=f"call, equity {equity:.2f}, pot odds {pot_odds:.2f}{profile_note}")

        if ActionType.BET in legal:
            value_threshold = baseline + (0.16 if live_opponents >= 3 else 0.12)
            value_threshold -= max(0.0, exploit["value"]) * 0.035
            if perceived > value_threshold and not (mistake and profile.key == "easy"):
                fraction = 0.42 if live_opponents >= 3 else 0.55
                if perceived > baseline + 0.30:
                    fraction = 0.72
                amount = min(player.stack, max(engine.BIG_BLIND, state.pot * fraction))
                return BotDecision(action=ActionType.BET, amount=round(amount, 2), confidence=0.65,
                                   reason=f"multiway value/protection, equity {equity:.2f}{profile_note}")

            bluff_rate = {"easy": 0.03, "normal": 0.06, "hard": 0.08, "maximum": 0.09}[profile.key]
            bluff_rate += max(0.0, exploit["pressure"]) * 0.025 + max(0.0, exploit["passivity"]) * 0.012
            bluff_rate /= max(1, live_opponents)
            if random.random() < bluff_rate:
                amount = min(player.stack, max(engine.BIG_BLIND, state.pot * 0.33))
                return BotDecision(action=ActionType.BET, amount=round(amount, 2), confidence=0.35,
                                   reason="редкий multiway bluff")

        if ActionType.CHECK in legal:
            return BotDecision(action=ActionType.CHECK, confidence=0.55, reason=f"check, equity {equity:.2f}")
        if ActionType.CALL in legal:
            return BotDecision(action=ActionType.CALL, amount=round(min(player.stack, to_call), 2), confidence=0.45)
        if ActionType.FOLD in legal:
            return BotDecision(action=ActionType.FOLD, confidence=0.4)
        return BotDecision(action=legal[0], confidence=0.2)
