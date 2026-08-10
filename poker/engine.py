from __future__ import annotations

from poker.deck import Deck
from poker.evaluator import HandEvaluator
from poker.models import GameState, PlayerState, Action, ActionType, Street


class InvalidAction(ValueError):
    pass


POSITION_MAP = {
    2: ["BTN / SB", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "CO"],
    5: ["BTN", "SB", "BB", "HJ", "CO"],
    6: ["BTN", "SB", "BB", "UTG", "HJ", "CO"],
    7: ["BTN", "SB", "BB", "UTG", "UTG+1", "HJ", "CO"],
}


class PokerEngine:
    STARTING_STACK = 1000.0
    SMALL_BLIND = 0.5
    BIG_BLIND = 1.0
    EPS = 1e-9

    def __init__(self):
        self.evaluator = HandEvaluator()

    @staticmethod
    def _rotate(order: list[str], start_id: str) -> list[str]:
        idx = order.index(start_id)
        return order[idx:] + order[:idx]

    def next_in_order(self, state: GameState, after_id: str, candidates: set[str] | None = None) -> str | None:
        order = state.seat_order
        if not order:
            return None
        idx = order.index(after_id)
        for step in range(1, len(order) + 1):
            pid = order[(idx + step) % len(order)]
            if candidates is None or pid in candidates:
                return pid
        return None

    def new_hand(
        self,
        seats: list[dict] | None = None,
        button_seat: int | None = None,
        *,
        button: str | None = None,
        hero_stack: float | None = None,
        bot_stack: float | None = None,
    ) -> GameState:
        """Create a 2-7 player hand.

        `button/hero_stack/bot_stack` are retained for the old HU tests and
        CFR-lite components. New 7-max code passes `seats` directly.
        """
        if seats is None:
            hero_stack = self.STARTING_STACK if hero_stack is None else float(hero_stack)
            bot_stack = self.STARTING_STACK if bot_stack is None else float(bot_stack)
            seats = [
                {"id": "hero", "name": "Вы", "seat": 0, "stack": hero_stack, "is_bot": False, "difficulty": "normal"},
                {"id": "bot", "name": "Бот", "seat": 1, "stack": bot_stack, "is_bot": True, "difficulty": "normal"},
            ]
            button_seat = 1 if button == "bot" else 0

        occupied = sorted(seats, key=lambda row: int(row["seat"]))
        if not 2 <= len(occupied) <= 7:
            raise InvalidAction("За столом должно быть от 2 до 7 игроков")

        for row in occupied:
            if float(row.get("stack", row.get("balance", 0.0))) < self.BIG_BLIND:
                raise InvalidAction(f"У игрока {row['name']} недостаточно фишек для новой раздачи")

        deck = Deck()
        players: dict[str, PlayerState] = {}
        seat_order: list[str] = []
        starts: dict[str, float] = {}

        for row in occupied:
            pid = str(row["id"])
            stack = float(row.get("stack", row.get("balance", self.STARTING_STACK)))
            players[pid] = PlayerState(
                id=pid,
                name=str(row["name"]),
                seat=int(row["seat"]),
                stack=stack,
                is_bot=bool(row.get("is_bot", False)),
                profile_id=row.get("profile_id"),
                difficulty=str(row.get("difficulty", "normal")),
                hole_cards=deck.draw(2),
            )
            seat_order.append(pid)
            starts[pid] = stack

        if button_seat is None or button_seat not in [int(r["seat"]) for r in occupied]:
            button_id = seat_order[0]
        else:
            button_id = next(pid for pid in seat_order if players[pid].seat == button_seat)

        n = len(seat_order)
        if n == 2:
            sb_id = button_id
            bb_id = self.next_from_order(seat_order, button_id)
        else:
            sb_id = self.next_from_order(seat_order, button_id)
            bb_id = self.next_from_order(seat_order, sb_id)

        state = GameState(
            street=Street.PREFLOP,
            pot=0.0,
            board=[],
            players=players,
            seat_order=seat_order,
            button=button_id,
            small_blind_player=sb_id,
            big_blind_player=bb_id,
            current_bet=self.BIG_BLIND,
            min_raise_size=self.BIG_BLIND,
            last_aggressor=bb_id,
            deck=deck,
            starting_stacks=starts,
        )

        self._assign_positions(state)
        self._post_blind(state, sb_id, self.SMALL_BLIND)
        self._post_blind(state, bb_id, self.BIG_BLIND)

        state.pending_actions = set(state.actionable_ids())
        # Preflop action starts left of BB. In heads-up this is the button/SB.
        state.acting_player = self.next_in_order(state, bb_id, state.pending_actions)
        if state.acting_player is None:
            self._runout_and_showdown(state)
        return state

    @staticmethod
    def next_from_order(order: list[str], after_id: str) -> str:
        idx = order.index(after_id)
        return order[(idx + 1) % len(order)]

    def _assign_positions(self, state: GameState):
        rotated = self._rotate(state.seat_order, state.button)
        labels = POSITION_MAP[len(rotated)]
        for pid, label in zip(rotated, labels):
            state.players[pid].position = label

    def _post_blind(self, state: GameState, player_id: str, amount: float):
        player = state.players[player_id]
        paid = min(player.stack, amount)
        self._put_chips(state, player, paid)

    def to_call(self, state: GameState, player_id: str) -> float:
        p = state.players[player_id]
        return max(0.0, state.current_bet - p.street_invested)

    def legal_actions(self, state: GameState, player_id: str) -> list[ActionType]:
        if state.terminal or state.acting_player != player_id:
            return []
        p = state.players[player_id]
        if p.folded or p.all_in:
            return []

        to_call = self.to_call(state, player_id)
        if to_call > self.EPS:
            legal = [ActionType.FOLD, ActionType.CALL]
            if p.stack > to_call + self.EPS:
                legal += [ActionType.RAISE, ActionType.ALL_IN]
            return legal

        legal = [ActionType.CHECK]
        if p.stack > self.EPS:
            if state.current_bet <= self.EPS:
                legal += [ActionType.BET, ActionType.ALL_IN]
            elif p.street_invested + p.stack > state.current_bet + self.EPS:
                legal += [ActionType.RAISE, ActionType.ALL_IN]
        return legal


    def timeout_fold(self, state: GameState, player_id: str) -> GameState:
        """Fold the acting player on clock expiry, even when a check was available."""
        if state.terminal:
            raise InvalidAction("Раздача уже завершена")
        if state.acting_player != player_id:
            raise InvalidAction("Сейчас ход другого игрока")
        player = state.players[player_id]
        if player.folded or player.all_in:
            raise InvalidAction("Игрок уже не может действовать")

        pot_before = state.pot
        live_players_before = len(state.live_ids())
        to_call = self.to_call(state, player_id)
        player.folded = True
        state.pending_actions.discard(player_id)
        state.history.append(Action(
            player_id=player_id, action=ActionType.FOLD, amount=0.0, street=state.street,
            pot_after=state.pot, pot_before=pot_before, to_call_before=to_call,
            live_players_before=live_players_before,
        ))
        if len(state.live_ids()) == 1:
            self._award_last_player(state)
            return state
        self._sanitize_pending(state)
        if not state.pending_actions:
            self._finish_betting_round(state)
            return state
        next_actor = self.next_in_order(state, player_id, state.pending_actions)
        if next_actor is None:
            self._finish_betting_round(state)
        else:
            state.acting_player = next_actor
        return state

    def min_raise_to(self, state: GameState, player_id: str) -> float:
        p = state.players[player_id]
        return min(p.street_invested + p.stack, state.current_bet + state.min_raise_size)

    def apply_action(self, state: GameState, player_id: str, action: ActionType, amount: float = 0.0) -> GameState:
        if state.terminal:
            raise InvalidAction("Раздача уже завершена")
        if state.acting_player != player_id:
            raise InvalidAction("Сейчас ход другого игрока")
        if action not in self.legal_actions(state, player_id):
            raise InvalidAction("Это действие сейчас недоступно")

        player = state.players[player_id]
        to_call = self.to_call(state, player_id)
        pot_before = state.pot
        live_players_before = len(state.live_ids())
        paid = 0.0

        if action == ActionType.FOLD:
            player.folded = True
            state.pending_actions.discard(player_id)

        elif action == ActionType.CHECK:
            state.pending_actions.discard(player_id)

        elif action == ActionType.CALL:
            paid = min(player.stack, to_call)
            self._put_chips(state, player, paid)
            state.pending_actions.discard(player_id)

        elif action == ActionType.BET:
            if state.current_bet > self.EPS:
                raise InvalidAction("Здесь нужен рейз, а не новая ставка")
            if amount <= 0:
                raise InvalidAction("Размер ставки должен быть больше нуля")
            target = min(player.street_invested + player.stack, amount)
            min_bet = min(self.BIG_BLIND, player.stack)
            if target + self.EPS < min_bet and target + self.EPS < player.street_invested + player.stack:
                raise InvalidAction(f"Минимальная ставка: {min_bet:.2f} ББ")
            paid = target - player.street_invested
            self._put_chips(state, player, paid)
            state.current_bet = player.street_invested
            state.min_raise_size = max(self.BIG_BLIND, state.current_bet)
            state.last_aggressor = player_id
            self._reset_pending_after_aggression(state, player_id)

        elif action == ActionType.RAISE:
            if amount <= state.current_bet + self.EPS:
                raise InvalidAction("Размер рейза должен быть больше текущей ставки")
            max_total = player.street_invested + player.stack
            target = min(float(amount), max_total)
            min_total = self.min_raise_to(state, player_id)
            is_all_in = target >= max_total - self.EPS
            if target + self.EPS < min_total and not is_all_in:
                raise InvalidAction(f"Минимальный рейз до {min_total:.2f} ББ")

            previous_bet = state.current_bet
            paid = target - player.street_invested
            self._put_chips(state, player, paid)
            raise_size = target - previous_bet
            state.current_bet = target
            if raise_size + self.EPS >= state.min_raise_size:
                state.min_raise_size = raise_size
            state.last_aggressor = player_id
            self._reset_pending_after_aggression(state, player_id)

        elif action == ActionType.ALL_IN:
            previous_bet = state.current_bet
            target = player.street_invested + player.stack
            paid = player.stack
            self._put_chips(state, player, paid)
            if target > previous_bet + self.EPS:
                raise_size = target - previous_bet
                state.current_bet = target
                if raise_size + self.EPS >= state.min_raise_size:
                    state.min_raise_size = raise_size
                state.last_aggressor = player_id
                self._reset_pending_after_aggression(state, player_id)
            else:
                state.pending_actions.discard(player_id)

        state.history.append(Action(
            player_id=player_id, action=action, amount=paid, street=state.street,
            pot_after=state.pot, pot_before=pot_before, to_call_before=to_call,
            live_players_before=live_players_before,
        ))

        if len(state.live_ids()) == 1:
            self._award_last_player(state)
            return state

        self._sanitize_pending(state)
        if not state.pending_actions:
            self._finish_betting_round(state)
            return state

        next_actor = self.next_in_order(state, player_id, state.pending_actions)
        if next_actor is None:
            self._finish_betting_round(state)
        else:
            state.acting_player = next_actor
        return state

    def _reset_pending_after_aggression(self, state: GameState, aggressor_id: str):
        state.pending_actions = {
            pid for pid in state.actionable_ids()
            if pid != aggressor_id
        }

    def _sanitize_pending(self, state: GameState):
        state.pending_actions = {
            pid for pid in state.pending_actions
            if pid in state.players and not state.players[pid].folded and not state.players[pid].all_in
        }

    def _put_chips(self, state: GameState, player: PlayerState, amount: float):
        amount = max(0.0, min(float(amount), player.stack))
        player.stack -= amount
        player.street_invested += amount
        player.total_invested += amount
        state.pot += amount
        if player.stack <= self.EPS:
            player.stack = 0.0
            player.all_in = True

    def _finish_betting_round(self, state: GameState):
        self._refund_uncalled_overage(state)
        if state.street == Street.RIVER:
            self._showdown(state)
            return

        actionable = state.actionable_ids()
        if len(actionable) <= 1:
            self._runout_and_showdown(state)
            return

        self._advance_street(state)

    def _advance_street(self, state: GameState):
        if state.street == Street.PREFLOP:
            state.board.extend(state.deck.draw(3))
            state.street = Street.FLOP
        elif state.street == Street.FLOP:
            state.board.append(state.deck.draw())
            state.street = Street.TURN
        elif state.street == Street.TURN:
            state.board.append(state.deck.draw())
            state.street = Street.RIVER
        else:
            self._showdown(state)
            return

        for p in state.players.values():
            p.street_invested = 0.0
        state.current_bet = 0.0
        state.min_raise_size = self.BIG_BLIND
        state.last_aggressor = None
        state.pending_actions = set(state.actionable_ids())

        if not state.pending_actions:
            self._runout_and_showdown(state)
            return

        # Postflop action starts left of button.
        state.acting_player = self.next_in_order(state, state.button, state.pending_actions)

    def _runout_and_showdown(self, state: GameState):
        self._refund_uncalled_overage(state)
        while len(state.board) < 5:
            if len(state.board) == 0:
                state.board.extend(state.deck.draw(3))
                state.street = Street.FLOP
            elif len(state.board) == 3:
                state.board.append(state.deck.draw())
                state.street = Street.TURN
            elif len(state.board) == 4:
                state.board.append(state.deck.draw())
                state.street = Street.RIVER
        self._showdown(state)

    def _refund_uncalled_overage(self, state: GameState):
        contributions = sorted(
            ((p.total_invested, pid) for pid, p in state.players.items() if p.total_invested > self.EPS),
            reverse=True,
        )
        if len(contributions) < 2:
            return
        highest, highest_id = contributions[0]
        second = contributions[1][0]
        over = highest - second
        if over <= self.EPS:
            return
        p = state.players[highest_id]
        p.total_invested -= over
        p.street_invested = max(0.0, p.street_invested - over)
        p.stack += over
        p.all_in = p.stack <= self.EPS
        state.pot -= over
        if state.current_bet > p.street_invested:
            state.current_bet = max(x.street_invested for x in state.players.values())

    def build_side_pots(self, state: GameState) -> list[dict]:
        contrib = {pid: p.total_invested for pid, p in state.players.items() if p.total_invested > self.EPS}
        levels = sorted(set(round(v, 10) for v in contrib.values()))
        pots = []
        previous = 0.0
        for level in levels:
            contributors = [pid for pid, value in contrib.items() if value + self.EPS >= level]
            amount = (level - previous) * len(contributors)
            if amount > self.EPS:
                eligible = [pid for pid in contributors if not state.players[pid].folded]
                pots.append({
                    "amount": amount,
                    "contributors": contributors,
                    "eligible": eligible,
                })
            previous = level
        return pots

    def _award_last_player(self, state: GameState):
        self._refund_uncalled_overage(state)
        winner_id = state.live_ids()[0]
        won = state.pot
        state.players[winner_id].stack += won
        state.winner = winner_id
        state.winners = [winner_id]
        state.result_text = f"{state.players[winner_id].name} выигрывает {won:.2f} ББ — остальные игроки сделали пас"
        state.result_details = [{"pot": "Банк", "amount": round(won, 2), "winners": [winner_id]}]
        state.pot = 0.0
        state.acting_player = None
        state.pending_actions.clear()
        state.street = Street.COMPLETE
        state.terminal = True

    def _showdown(self, state: GameState):
        self._refund_uncalled_overage(state)
        state.street = Street.SHOWDOWN
        side_pots = self.build_side_pots(state)
        details = []
        all_winners: list[str] = []

        for index, pot in enumerate(side_pots):
            eligible = pot["eligible"]
            if not eligible:
                continue
            scores = {
                pid: self.evaluator.score(state.players[pid].hole_cards, state.board)
                for pid in eligible
            }
            best = max(scores.values())
            winners = [pid for pid, score in scores.items() if score == best]
            share = pot["amount"] / len(winners)
            for pid in winners:
                state.players[pid].stack += share
                if pid not in all_winners:
                    all_winners.append(pid)

            details.append({
                "pot": "Главный банк" if index == 0 else f"Побочный банк {index}",
                "amount": round(pot["amount"], 2),
                "winners": winners,
                "winner_names": [state.players[pid].name for pid in winners],
            })

        state.winners = all_winners
        state.winner = all_winners[0] if len(all_winners) == 1 else ("tie" if all_winners else None)

        descriptions = []
        for pid in state.live_ids():
            p = state.players[pid]
            descriptions.append(f"{p.name}: {self.evaluator.describe(p.hole_cards, state.board)}")

        if len(details) == 1 and len(details[0]["winners"]) == 1:
            pid = details[0]["winners"][0]
            state.result_text = (
                f"{state.players[pid].name} выигрывает {details[0]['amount']:.2f} ББ — "
                + " · ".join(descriptions)
            )
        else:
            payouts = []
            for row in details:
                names = ", ".join(row["winner_names"])
                payouts.append(f"{row['pot']}: {row['amount']:.2f} ББ → {names}")
            state.result_text = " | ".join(payouts) + (" — " + " · ".join(descriptions) if descriptions else "")

        state.result_details = details
        state.pot = 0.0
        state.acting_player = None
        state.pending_actions.clear()
        state.street = Street.COMPLETE
        state.terminal = True
