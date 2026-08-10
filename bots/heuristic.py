import random

from bots.base import PokerBot, BotDecision
from poker.engine import PokerEngine
from poker.equity import estimate_equity
from poker.models import ActionType, Street


class HeuristicBot(PokerBot):
    """
    Baseline opponent for v0.2.
    It is intentionally NOT called GTO.
    """

    def __init__(self):
        self.engine = PokerEngine()

    def decide(self, state, player_id):
        legal = self.engine.legal_actions(state, player_id)
        player = state.players[player_id]
        to_call = self.engine.to_call(state, player_id)

        equity = estimate_equity(
            player.hole_cards,
            state.board,
            samples=450 if state.street == Street.PREFLOP else 650,
        )

        # Small noise so the bot is not perfectly deterministic.
        e = max(0.0, min(1.0, equity + random.uniform(-0.025, 0.025)))

        if to_call > 0:
            pot_odds = to_call / max(state.pot + to_call, 1e-9)

            if e + 0.03 < pot_odds and ActionType.FOLD in legal:
                return BotDecision(
                    action=ActionType.FOLD,
                    confidence=0.72,
                    reason=f"equity={equity:.2f}, pot_odds={pot_odds:.2f}",
                )

            if e > 0.72 and ActionType.RAISE in legal:
                raise_to = state.current_bet + max(
                    state.min_raise_size,
                    state.pot * 0.55,
                )
                raise_to = min(
                    player.street_invested + player.stack,
                    raise_to,
                )
                return BotDecision(
                    action=ActionType.RAISE,
                    amount=round(raise_to, 2),
                    confidence=0.70,
                    reason=f"strong range-equity proxy={equity:.2f}",
                )

            if e > 0.92 and ActionType.ALL_IN in legal and player.stack < state.pot * 1.2:
                return BotDecision(
                    action=ActionType.ALL_IN,
                    amount=player.stack,
                    confidence=0.78,
                    reason=f"very strong equity={equity:.2f}",
                )

            return BotDecision(
                action=ActionType.CALL,
                amount=round(to_call, 2),
                confidence=0.58,
                reason=f"call: equity={equity:.2f}, pot_odds={pot_odds:.2f}",
            )

        if ActionType.BET in legal:
            if e > 0.67:
                amount = max(1.0, state.pot * (0.66 if e > 0.80 else 0.45))
                amount = min(player.stack, amount)
                return BotDecision(
                    action=ActionType.BET,
                    amount=round(amount, 2),
                    confidence=0.64,
                    reason=f"value/protection; equity={equity:.2f}",
                )

            # A little bluffing.
            if e < 0.38 and random.random() < 0.18:
                amount = min(player.stack, max(1.0, state.pot * 0.40))
                return BotDecision(
                    action=ActionType.BET,
                    amount=round(amount, 2),
                    confidence=0.35,
                    reason="low-frequency bluff",
                )

        if ActionType.CHECK in legal:
            return BotDecision(
                action=ActionType.CHECK,
                confidence=0.55,
                reason=f"check; equity={equity:.2f}",
            )

        # Defensive fallback.
        return BotDecision(
            action=legal[0],
            confidence=0.1,
            reason="fallback",
        )
