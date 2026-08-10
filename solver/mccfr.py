from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import random
from typing import Iterable

from poker.engine import PokerEngine
from poker.evaluator import HandEvaluator
from poker.models import ActionType, GameState, Street
from ranges.model import RangeModel, postflop_strength, preflop_strength
from solver.action_abstraction import ActionOption, build_action_abstraction


@dataclass
class _ChanceSample:
    villain: tuple[str, str]
    runout: list[str]
    outcome: str
    villain_bucket: int


class LocalMCCFRSolver:
    """
    Depth-limited, chance-sampled regret-matching solver for one current spot.

    This is deliberately CFR-lite, not a full-game GTO solver. It solves a
    compact local betting tree:
      - current player chooses an abstract action;
      - after aggression the opponent can fold/call;
      - after check the opponent can check or bet 1/3 / 2/3 pot;
      - versus that bet the current player can fold/call;
      - future streets are rolled out directly to showdown.

    Hidden opponent cards and future board cards are sampled from the inferred
    weighted range. Regrets are accumulated separately for opponent strength
    buckets, so responses can adapt to hidden hand quality.
    """

    def __init__(self, engine: PokerEngine | None = None):
        self.engine = engine or PokerEngine()
        self.evaluator = HandEvaluator()

    @staticmethod
    def _regret_strategy(regrets: dict[str, float], actions: Iterable[str]) -> dict[str, float]:
        actions = list(actions)
        positive = {a: max(0.0, regrets.get(a, 0.0)) for a in actions}
        total = sum(positive.values())
        if total <= 1e-12:
            p = 1.0 / max(1, len(actions))
            return {a: p for a in actions}
        return {a: positive[a] / total for a in actions}

    @staticmethod
    def _bucket(strength: float) -> int:
        return max(0, min(5, int(strength * 6.0)))

    @staticmethod
    def _showdown_utility(
        pot_before: float,
        hero_cost: float,
        opponent_additional: float,
        outcome: str,
    ) -> float:
        final_pot = pot_before + hero_cost + opponent_additional
        if outcome == "hero":
            return final_pot - hero_cost
        if outcome == "tie":
            return final_pot * 0.5 - hero_cost
        return -hero_cost

    def _sample_chance(
        self,
        state: GameState,
        player_id: str,
        opponent_range: RangeModel,
    ) -> _ChanceSample | None:
        hero_cards = state.players[player_id].hole_cards
        known = set(hero_cards + state.board)
        villain = opponent_range.sample(excluded=known)
        if villain is None:
            return None

        excluded = known | set(villain)
        remaining = [
            r + s
            for r in "23456789TJQKA"
            for s in "shdc"
            if r + s not in excluded
        ]
        missing = 5 - len(state.board)
        extra = random.sample(remaining, missing) if missing > 0 else []
        runout = list(state.board) + extra

        hero_score = self.evaluator.score(hero_cards, runout)
        villain_score = self.evaluator.score(list(villain), runout)
        if hero_score > villain_score:
            outcome = "hero"
        elif hero_score == villain_score:
            outcome = "tie"
        else:
            outcome = "villain"

        if state.street == Street.PREFLOP:
            strength = preflop_strength(villain)
        else:
            strength = postflop_strength(villain, list(state.board))

        return _ChanceSample(
            villain=villain,
            runout=runout,
            outcome=outcome,
            villain_bucket=self._bucket(strength),
        )

    def _aggression_costs(self, state: GameState, player_id: str, option: ActionOption):
        hero = state.players[player_id]
        villain = state.players[state.opponent_of(player_id)]

        if option.action == ActionType.BET:
            hero_cost = min(hero.stack, option.amount)
            target = hero.street_invested + hero_cost
        elif option.action == ActionType.RAISE:
            target = min(hero.street_invested + hero.stack, option.amount)
            hero_cost = max(0.0, target - hero.street_invested)
        elif option.action == ActionType.ALL_IN:
            hero_cost = hero.stack
            target = hero.street_invested + hero_cost
        else:
            raise ValueError("not an aggressive action")

        villain_additional = max(0.0, min(villain.stack, target - villain.street_invested))
        return hero_cost, villain_additional

    def _check_branch(
        self,
        state: GameState,
        player_id: str,
        sample: _ChanceSample,
        root_reach: float,
        regrets: dict[str, dict[str, float]],
        strategy_sums: dict[str, dict[str, float]],
    ) -> float:
        pot = state.pot
        opponent = state.players[state.opponent_of(player_id)]
        hero = state.players[player_id]

        bet_sizes = [
            min(opponent.stack, max(self.engine.BIG_BLIND, pot * 0.33)),
            min(opponent.stack, max(self.engine.BIG_BLIND, pot * 0.66)),
        ]
        unique_bets = []
        for b in bet_sizes:
            b = round(b, 2)
            if b > 0 and b not in unique_bets:
                unique_bets.append(b)

        opp_actions = ["check"] + [f"bet:{b:.2f}" for b in unique_bets]
        opp_key = f"after_check:b{sample.villain_bucket}"
        opp_strategy = self._regret_strategy(regrets[opp_key], opp_actions)

        hero_values: dict[str, float] = {
            "check": self._showdown_utility(pot, 0.0, 0.0, sample.outcome)
        }

        for b in unique_bets:
            action_key = f"bet:{b:.2f}"
            response_key = f"vs_check_bet:{b:.2f}"
            response_actions = ["fold", "call"]
            response_strategy = self._regret_strategy(regrets[response_key], response_actions)

            fold_u = 0.0
            call_cost = min(hero.stack, b)
            opp_additional = min(opponent.stack, hero.stack, b)
            call_u = self._showdown_utility(
                pot,
                call_cost,
                opp_additional,
                sample.outcome,
            )
            response_values = {"fold": fold_u, "call": call_u}
            response_ev = sum(response_strategy[a] * response_values[a] for a in response_actions)
            hero_values[action_key] = response_ev

            reach = root_reach * opp_strategy[action_key]
            if reach > 0:
                for a in response_actions:
                    regrets[response_key][a] += reach * (response_values[a] - response_ev)
                    strategy_sums[response_key][a] += reach * response_strategy[a]

        node_ev = sum(opp_strategy[a] * hero_values[a] for a in opp_actions)

        # Opponent minimizes hero utility in this zero-sum local abstraction.
        if root_reach > 0:
            for a in opp_actions:
                regrets[opp_key][a] += root_reach * (node_ev - hero_values[a])
                strategy_sums[opp_key][a] += root_reach * opp_strategy[a]

        return node_ev

    def _aggression_branch(
        self,
        state: GameState,
        player_id: str,
        option: ActionOption,
        sample: _ChanceSample,
        root_reach: float,
        regrets: dict[str, dict[str, float]],
        strategy_sums: dict[str, dict[str, float]],
    ) -> float:
        hero_cost, villain_additional = self._aggression_costs(state, player_id, option)
        fold_u = state.pot
        call_u = self._showdown_utility(
            state.pot,
            hero_cost,
            villain_additional,
            sample.outcome,
        )

        node_key = f"respond:{option.key}:b{sample.villain_bucket}"
        responses = ["fold", "call"]
        response_strategy = self._regret_strategy(regrets[node_key], responses)
        values = {"fold": fold_u, "call": call_u}
        hero_ev = sum(response_strategy[a] * values[a] for a in responses)

        if root_reach > 0:
            for a in responses:
                # Opponent utility is -hero utility.
                regrets[node_key][a] += root_reach * (hero_ev - values[a])
                strategy_sums[node_key][a] += root_reach * response_strategy[a]

        return hero_ev

    def _root_action_values(
        self,
        state: GameState,
        player_id: str,
        options: list[ActionOption],
        sample: _ChanceSample,
        root_strategy: dict[str, float],
        regrets: dict[str, dict[str, float]],
        strategy_sums: dict[str, dict[str, float]],
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        to_call = self.engine.to_call(state, player_id)

        for option in options:
            action = option.action
            root_reach = root_strategy.get(option.key, 0.0)

            if action == ActionType.FOLD:
                values[option.key] = 0.0
            elif action == ActionType.CALL:
                values[option.key] = self._showdown_utility(
                    state.pot,
                    min(state.players[player_id].stack, to_call),
                    0.0,
                    sample.outcome,
                )
            elif action == ActionType.CHECK:
                values[option.key] = self._check_branch(
                    state,
                    player_id,
                    sample,
                    root_reach,
                    regrets,
                    strategy_sums,
                )
            elif action in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
                values[option.key] = self._aggression_branch(
                    state,
                    player_id,
                    option,
                    sample,
                    root_reach,
                    regrets,
                    strategy_sums,
                )
            else:
                values[option.key] = 0.0

        return values

    def solve(
        self,
        state: GameState,
        player_id: str,
        iterations: int = 420,
        extra_action: ActionType | None = None,
        extra_amount: float = 0.0,
    ) -> dict:
        if state.terminal or state.acting_player != player_id:
            raise ValueError("Сейчас для этого игрока нет решения")

        options = build_action_abstraction(
            state,
            player_id,
            self.engine,
            extra_action=extra_action,
            extra_amount=extra_amount,
        )
        if not options:
            raise ValueError("Нет доступных действий для анализа")

        opponent_id = state.opponent_of(player_id)
        opponent_range = RangeModel.from_state(
            state,
            opponent_id=opponent_id,
            observer_id=player_id,
        )

        regrets: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        strategy_sums: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        ev_sums = defaultdict(float)
        ev_counts = defaultdict(int)
        showdown_points = 0.0
        chance_count = 0

        root_key = "root"
        root_actions = [o.key for o in options]
        burn_in = max(25, int(iterations * 0.18))

        for i in range(max(40, iterations)):
            sample = self._sample_chance(state, player_id, opponent_range)
            if sample is None:
                continue

            chance_count += 1
            showdown_points += 1.0 if sample.outcome == "hero" else 0.5 if sample.outcome == "tie" else 0.0

            root_strategy = self._regret_strategy(regrets[root_key], root_actions)
            values = self._root_action_values(
                state,
                player_id,
                options,
                sample,
                root_strategy,
                regrets,
                strategy_sums,
            )
            root_ev = sum(root_strategy[k] * values[k] for k in root_actions)

            for k in root_actions:
                regrets[root_key][k] += values[k] - root_ev
                strategy_sums[root_key][k] += root_strategy[k]
                if i >= burn_in:
                    ev_sums[k] += values[k]
                    ev_counts[k] += 1

        root_total = sum(strategy_sums[root_key].values())
        if root_total <= 0:
            frequencies = {k: 1.0 / len(root_actions) for k in root_actions}
        else:
            frequencies = {k: strategy_sums[root_key][k] / root_total for k in root_actions}

        action_rows = []
        for option in options:
            count = ev_counts[option.key]
            ev = ev_sums[option.key] / count if count else 0.0
            action_rows.append({
                "key": option.key,
                "action": option.action.value,
                "amount": round(option.amount, 2),
                "label": option.label,
                "frequency": round(frequencies.get(option.key, 0.0), 4),
                "ev_bb": round(ev, 3),
                "regret": round(regrets[root_key][option.key], 3),
            })

        action_rows.sort(key=lambda row: row["frequency"], reverse=True)
        best = max(action_rows, key=lambda row: row["ev_bb"])

        return {
            "method": "CFR-lite · chance-sampled regret matching",
            "iterations": max(40, iterations),
            "street": state.street.value,
            "pot_bb": round(state.pot, 2),
            "to_call_bb": round(self.engine.to_call(state, player_id), 2),
            "raw_showdown_equity": round(showdown_points / chance_count, 4) if chance_count else 0.0,
            "range": {
                "effective_combos": round(opponent_range.effective_combo_count(), 1),
                "top_hand_classes": opponent_range.top_hands(10),
            },
            "actions": action_rows,
            "best_action_key": best["key"],
            "best_action": best,
            "best_ev_bb": best["ev_bb"],
            "warning": (
                "Локальная depth-limited CFR-аппроксимация: будущие улицы после первого ответа "
                "докручиваются до вскрытия, а дерево использует ограниченный набор сайзингов. "
                "Это тренажёр решений, а не полный GTO-солвер всего NLHE."
            ),
        }

    @staticmethod
    def _find_chosen(result: dict, action: ActionType, amount: float) -> dict | None:
        candidates = [r for r in result["actions"] if r["action"] == action.value]
        if not candidates:
            return None
        if action in (ActionType.FOLD, ActionType.CHECK, ActionType.CALL, ActionType.ALL_IN):
            return candidates[0]
        return min(candidates, key=lambda r: abs(float(r["amount"]) - float(amount)))

    def review_action(
        self,
        result: dict,
        action: ActionType,
        amount: float,
        street: Street,
        board: list[str],
    ) -> dict:
        chosen = self._find_chosen(result, action, amount)
        best = result["best_action"]
        if chosen is None:
            chosen = best

        loss = max(0.0, float(best["ev_bb"]) - float(chosen["ev_bb"]))
        if loss < 0.06:
            grade = "Отличное решение"
        elif loss < 0.25:
            grade = "Небольшая неточность"
        elif loss < 0.90:
            grade = "Ошибка"
        else:
            grade = "Крупная ошибка"

        return {
            "street": street.value,
            "board": list(board),
            "chosen": chosen,
            "best": best,
            "ev_loss_bb": round(loss, 3),
            "grade": grade,
            "solver": result,
        }
