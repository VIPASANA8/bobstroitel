from __future__ import annotations

import random

from bots.base import PokerBot, BotDecision
from poker.engine import PokerEngine
from poker.equity import estimate_equity_vs_range
from poker.models import ActionType, Street
from ranges.model import RangeModel, preflop_strength


class StrategicRangeBot(PokerBot):
    """
    v0.3 range-aware opponent.

    Not a GTO solver yet. Decisions combine:
    - weighted opponent range inferred from observed actions;
    - equity vs that range;
    - pot odds;
    - position;
    - mixed frequencies and practical bet sizing.
    """

    def __init__(self):
        self.engine = PokerEngine()

    def decide(self, state, player_id: str) -> BotDecision:
        legal = self.engine.legal_actions(state, player_id)
        if not legal:
            raise ValueError("У бота нет доступных действий")

        player = state.players[player_id]
        opponent_id = state.opponent_of(player_id)
        to_call = self.engine.to_call(state, player_id)

        opponent_range = RangeModel.from_state(
            state,
            opponent_id=opponent_id,
            observer_id=player_id,
        )

        if state.street == Street.PREFLOP:
            return self._preflop_decision(
                state, player_id, legal, to_call, opponent_range
            )

        equity = estimate_equity_vs_range(
            player.hole_cards,
            state.board,
            opponent_range,
            samples=220,
        )
        return self._postflop_decision(
            state, player_id, legal, to_call, equity
        )

    def _preflop_decision(self, state, player_id, legal, to_call, opponent_range):
        player = state.players[player_id]
        s = preflop_strength(player.hole_cards)
        on_button = state.button == player_id

        # If we are closing action in BB vs limp, punish stronger hands and
        # check a wide remainder.
        if to_call <= 0:
            raise_freq = max(0.0, min(0.92, (s - 0.43) * 1.75))
            if not on_button:
                raise_freq += 0.05

            if ActionType.BET in legal and random.random() < raise_freq:
                amount = min(player.stack, max(2.5, state.pot * 1.5))
                return BotDecision(
                    action=ActionType.BET,
                    amount=round(amount, 2),
                    confidence=0.68,
                    reason=f"префлоп-сила={s:.2f}; изоляционный рейз",
                )

            if ActionType.CHECK in legal:
                return BotDecision(
                    action=ActionType.CHECK,
                    confidence=0.60,
                    reason=f"префлоп-сила={s:.2f}; чек",
                )

        # Facing a bet/raise: calculate equity against the inferred range.
        equity = estimate_equity_vs_range(
            player.hole_cards,
            [],
            opponent_range,
            samples=180,
        )
        pot_odds = to_call / max(state.pot + to_call, 1e-9)

        # Premium region + mixed 3-bets.
        if ActionType.RAISE in legal:
            three_bet_freq = max(0.0, min(0.90, (equity - 0.54) * 2.6))
            # Add a small polarized bluff tail with playable hands.
            if 0.40 < s < 0.55:
                three_bet_freq += 0.08

            if random.random() < three_bet_freq:
                target = max(
                    self.engine.min_raise_to(state, player_id),
                    state.current_bet * (3.2 if not on_button else 3.0),
                )
                target = min(player.street_invested + player.stack, target)
                return BotDecision(
                    action=ActionType.RAISE,
                    amount=round(target, 2),
                    confidence=0.74,
                    reason=f"equity против диапазона={equity:.2f}; 3-бет",
                )

        # Calls are deliberately wide in HU.
        margin = 0.015 if on_button else 0.025
        if equity + margin >= pot_odds and ActionType.CALL in legal:
            return BotDecision(
                action=ActionType.CALL,
                amount=round(to_call, 2),
                confidence=0.68,
                reason=f"equity={equity:.2f}; pot odds={pot_odds:.2f}",
            )

        if ActionType.FOLD in legal:
            return BotDecision(
                action=ActionType.FOLD,
                confidence=0.76,
                reason=f"equity={equity:.2f} ниже требуемой",
            )

        return BotDecision(action=legal[0], confidence=0.2, reason="резервное действие")

    def _postflop_decision(self, state, player_id, legal, to_call, equity):
        player = state.players[player_id]
        pot = max(state.pot, 0.01)
        spr = player.stack / pot

        # Facing aggression.
        if to_call > 0:
            pot_odds = to_call / max(state.pot + to_call, 1e-9)

            if equity < pot_odds - 0.035 and ActionType.FOLD in legal:
                return BotDecision(
                    action=ActionType.FOLD,
                    confidence=0.80,
                    reason=f"equity={equity:.2f}; pot odds={pot_odds:.2f}",
                )

            # Value raises become more common with equity and lower SPR.
            if ActionType.RAISE in legal:
                raise_threshold = 0.72 if spr > 3 else 0.66
                raise_freq = max(0.0, min(0.88, (equity - raise_threshold) * 3.4))

                # Small semi-bluff component around coin-flip equity.
                if 0.42 <= equity <= 0.55:
                    raise_freq += 0.06

                if random.random() < raise_freq:
                    min_to = self.engine.min_raise_to(state, player_id)
                    target = max(min_to, state.current_bet + state.pot * 0.65)
                    target = min(player.street_invested + player.stack, target)

                    if target >= player.street_invested + player.stack - 1e-9:
                        return BotDecision(
                            action=ActionType.ALL_IN,
                            amount=player.stack,
                            confidence=0.80,
                            reason=f"сильный диапазон; equity={equity:.2f}; низкий SPR",
                        )

                    return BotDecision(
                        action=ActionType.RAISE,
                        amount=round(target, 2),
                        confidence=0.73,
                        reason=f"value/semi-bluff raise; equity={equity:.2f}",
                    )

            if equity + 0.018 >= pot_odds and ActionType.CALL in legal:
                return BotDecision(
                    action=ActionType.CALL,
                    amount=round(to_call, 2),
                    confidence=0.70,
                    reason=f"колл: equity={equity:.2f}; pot odds={pot_odds:.2f}",
                )

            if ActionType.FOLD in legal:
                return BotDecision(
                    action=ActionType.FOLD,
                    confidence=0.70,
                    reason="пограничная рука без достаточных pot odds",
                )

        # Checked to us: use a polarized-ish betting strategy.
        if ActionType.BET in legal:
            bet_freq = 0.0
            sizing = 0.50

            if equity >= 0.78:
                bet_freq, sizing = 0.90, 0.72
            elif equity >= 0.64:
                bet_freq, sizing = 0.76, 0.55
            elif equity >= 0.52:
                bet_freq, sizing = 0.43, 0.38
            elif equity <= 0.34:
                bet_freq, sizing = 0.16, 0.40

            # River bluffs less frequently than flop/turn.
            if state.street == Street.RIVER and equity < 0.45:
                bet_freq *= 0.60

            if random.random() < bet_freq:
                amount = min(player.stack, max(1.0, state.pot * sizing))

                if player.stack <= state.pot * 0.85 and equity >= 0.72:
                    return BotDecision(
                        action=ActionType.ALL_IN,
                        amount=player.stack,
                        confidence=0.78,
                        reason=f"value shove; equity={equity:.2f}",
                    )

                return BotDecision(
                    action=ActionType.BET,
                    amount=round(amount, 2),
                    confidence=0.68,
                    reason=f"ставка по диапазону; equity={equity:.2f}",
                )

        if ActionType.CHECK in legal:
            return BotDecision(
                action=ActionType.CHECK,
                confidence=0.66,
                reason=f"чек; equity={equity:.2f}",
            )

        return BotDecision(action=legal[0], confidence=0.2, reason="резервное действие")
