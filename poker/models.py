from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4


class Street(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    COMPLETE = "complete"


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class PlayerState:
    id: str
    name: str
    seat: int
    stack: float
    is_bot: bool = False
    profile_id: str | None = None
    difficulty: str = "normal"
    position: str = ""
    hole_cards: list[str] = field(default_factory=list)
    street_invested: float = 0.0
    total_invested: float = 0.0
    folded: bool = False
    all_in: bool = False


@dataclass
class Action:
    player_id: str
    action: ActionType
    amount: float = 0.0
    street: Street = Street.PREFLOP
    pot_after: float = 0.0
    pot_before: float = 0.0
    to_call_before: float = 0.0
    live_players_before: int = 0


@dataclass
class GameState:
    hand_id: str = field(default_factory=lambda: uuid4().hex[:12])
    street: Street = Street.PREFLOP
    pot: float = 0.0
    board: list[str] = field(default_factory=list)
    players: dict[str, PlayerState] = field(default_factory=dict)
    seat_order: list[str] = field(default_factory=list)

    button: str = "hero"
    acting_player: Optional[str] = None
    small_blind_player: Optional[str] = None
    big_blind_player: Optional[str] = None

    current_bet: float = 1.0
    min_raise_size: float = 1.0
    last_aggressor: Optional[str] = None
    pending_actions: set[str] = field(default_factory=set)

    winner: Optional[str] = None
    winners: list[str] = field(default_factory=list)
    result_text: str = ""
    result_details: list[dict] = field(default_factory=list)
    terminal: bool = False

    history: list[Action] = field(default_factory=list)
    decision_reviews: list[dict] = field(default_factory=list)
    difficulty: str = "normal"  # legacy HU solver compatibility
    starting_stacks: dict[str, float] = field(default_factory=dict)

    deck: object | None = None

    def active_ids(self, include_folded: bool = False) -> list[str]:
        ids = []
        for pid in self.seat_order:
            p = self.players[pid]
            if include_folded or not p.folded:
                ids.append(pid)
        return ids

    def live_ids(self) -> list[str]:
        return [pid for pid in self.seat_order if not self.players[pid].folded]

    def actionable_ids(self) -> list[str]:
        return [
            pid for pid in self.seat_order
            if not self.players[pid].folded and not self.players[pid].all_in
        ]

    def opponent_of(self, player_id: str) -> str:
        """Compatibility helper for the heads-up CFR-lite solver."""
        others = [pid for pid in self.live_ids() if pid != player_id]
        if len(others) != 1:
            raise ValueError("opponent_of доступен только в heads-up споте")
        return others[0]

    def to_dict(self, viewer_player_id: str | None = None, reveal_bots: bool = False):
        """Public state for one local viewer.

        During a hand only the currently controlled human receives their private
        cards. At showdown all non-folded hands are revealed.
        """
        players = {}
        for pid in self.seat_order:
            player = self.players[pid]
            reveal = False
            if self.terminal:
                reveal = not player.folded
            elif viewer_player_id == pid:
                reveal = True
            elif reveal_bots and player.is_bot:
                reveal = True
            cards = player.hole_cards if reveal else ["??", "??"]

            players[pid] = {
                "id": player.id,
                "profile_id": player.profile_id,
                "name": player.name,
                "seat": player.seat,
                "stack": round(player.stack, 2),
                "is_bot": player.is_bot,
                "difficulty": player.difficulty,
                "position": player.position,
                "hole_cards": cards,
                "street_invested": round(player.street_invested, 2),
                "total_invested": round(player.total_invested, 2),
                "folded": player.folded,
                "all_in": player.all_in,
            }

        return {
            "viewer_player_id": viewer_player_id,
            "hand_id": self.hand_id,
            "street": self.street.value,
            "pot": round(self.pot, 2),
            "board": self.board,
            "players": players,
            "seat_order": self.seat_order,
            "button": self.button,
            "small_blind_player": self.small_blind_player,
            "big_blind_player": self.big_blind_player,
            "acting_player": self.acting_player,
            "current_bet": round(self.current_bet, 2),
            "min_raise_size": round(self.min_raise_size, 2),
            "winner": self.winner,
            "winners": self.winners,
            "result_text": self.result_text,
            "result_details": self.result_details,
            "terminal": self.terminal,
            "starting_stacks": {k: round(v, 2) for k, v in self.starting_stacks.items()},
            "history": [
                {
                    "player_id": a.player_id,
                    "action": a.action.value,
                    "amount": round(a.amount, 2),
                    "street": a.street.value,
                    "pot_after": round(a.pot_after, 2),
                    "pot_before": round(a.pot_before, 2),
                    "to_call_before": round(a.to_call_before, 2),
                    "live_players_before": a.live_players_before,
                }
                for a in self.history
            ],
        }
