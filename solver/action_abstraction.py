from __future__ import annotations

from dataclasses import dataclass
import math

from poker.engine import PokerEngine
from poker.models import ActionType, GameState, Street


@dataclass(frozen=True)
class ActionOption:
    key: str
    action: ActionType
    amount: float
    label: str


def _key(action: ActionType, amount: float = 0.0) -> str:
    if action in (ActionType.FOLD, ActionType.CHECK, ActionType.CALL):
        return action.value
    if action == ActionType.ALL_IN:
        return "all_in"
    return f"{action.value}:{amount:.2f}"


def _label(action: ActionType, amount: float = 0.0, pot: float = 0.0) -> str:
    if action == ActionType.FOLD:
        return "Пас"
    if action == ActionType.CHECK:
        return "Чек"
    if action == ActionType.CALL:
        return "Колл"
    if action == ActionType.ALL_IN:
        return "Олл-ин"

    pct = (amount / pot * 100.0) if pot > 0 else 0.0
    name = "Ставка" if action == ActionType.BET else "Рейз до"
    if action == ActionType.BET:
        return f"{name} {amount:.2f} ББ · {pct:.0f}% банка"
    return f"{name} {amount:.2f} ББ"


def _add_unique(options: list[ActionOption], action: ActionType, amount: float, pot: float):
    amount = max(0.0, amount)
    # A minimum raise like 8.625 must become 8.63, never 8.62. Normal
    # rounding could otherwise turn a legal solver action into an illegal one.
    if action == ActionType.RAISE:
        amount = math.ceil((amount - 1e-10) * 100.0) / 100.0
    else:
        amount = round(amount, 2)
    key = _key(action, amount)
    if any(o.key == key for o in options):
        return
    options.append(ActionOption(key, action, amount, _label(action, amount, pot)))


def build_action_abstraction(
    state: GameState,
    player_id: str,
    engine: PokerEngine,
    extra_action: ActionType | None = None,
    extra_amount: float = 0.0,
) -> list[ActionOption]:
    legal = engine.legal_actions(state, player_id)
    player = state.players[player_id]
    opponent = state.players[state.opponent_of(player_id)]
    pot = max(state.pot, 0.01)
    to_call = engine.to_call(state, player_id)
    options: list[ActionOption] = []

    if ActionType.FOLD in legal:
        _add_unique(options, ActionType.FOLD, 0.0, pot)
    if ActionType.CHECK in legal:
        _add_unique(options, ActionType.CHECK, 0.0, pot)
    if ActionType.CALL in legal:
        _add_unique(options, ActionType.CALL, to_call, pot)

    max_total = player.street_invested + player.stack
    if ActionType.BET in legal:
        fractions = (0.33, 0.66, 1.00)
        for frac in fractions:
            amount = min(player.stack, max(engine.BIG_BLIND, pot * frac))
            _add_unique(options, ActionType.BET, amount, pot)

    if ActionType.RAISE in legal:
        min_to = engine.min_raise_to(state, player_id)
        targets: list[float] = [min_to]

        if state.street == Street.PREFLOP:
            if state.current_bet <= 1.01:
                targets.extend([2.5, 3.0])
            else:
                multiplier = 3.0 if state.button == player_id else 3.4
                targets.extend([
                    state.current_bet * multiplier,
                    state.current_bet * (multiplier + 0.8),
                ])
        else:
            targets.extend([
                state.current_bet + pot * 0.60,
                state.current_bet + pot * 1.00,
            ])

        for target in targets:
            # The engine validates raises against the acting player's maximum
            # total commitment. Do not cap a normal raise below min_raise_to
            # merely because the opponent is shorter; that created illegal
            # non-all-in targets. Unmatched chips are handled by the simplified
            # HU model at the response layer.
            target = min(max_total, max(min_to, target))
            is_all_in_target = target >= max_total - 1e-9
            if target > state.current_bet + 1e-9 and (target >= min_to - 1e-9 or is_all_in_target):
                _add_unique(options, ActionType.RAISE, target, pot)

    # Shoves matter most at lower SPR or when already facing a large bet.
    effective_stack = min(player.stack, opponent.stack)
    include_shove = (
        ActionType.ALL_IN in legal
        and (
            effective_stack <= pot * 2.5
            or to_call >= max(1.0, player.stack * 0.20)
            or state.street == Street.RIVER
        )
    )
    if include_shove:
        _add_unique(options, ActionType.ALL_IN, player.stack, pot)

    if extra_action in legal:
        if extra_action in (ActionType.BET, ActionType.RAISE):
            if extra_amount > 0:
                _add_unique(options, extra_action, extra_amount, pot)
        elif extra_action == ActionType.ALL_IN:
            _add_unique(options, extra_action, player.stack, pot)
        else:
            _add_unique(options, extra_action, to_call if extra_action == ActionType.CALL else 0.0, pot)

    return options
