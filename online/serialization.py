from __future__ import annotations

from poker.deck import Deck
from poker.models import Action, ActionType, GameState, PlayerState, Street


def serialize_state(state: GameState) -> dict:
    return {
        "hand_id": state.hand_id,
        "street": state.street.value,
        "pot": state.pot,
        "board": list(state.board),
        "players": {
            pid: {
                "id": player.id,
                "name": player.name,
                "seat": player.seat,
                "stack": player.stack,
                "is_bot": player.is_bot,
                "profile_id": player.profile_id,
                "difficulty": player.difficulty,
                "position": player.position,
                "hole_cards": list(player.hole_cards),
                "street_invested": player.street_invested,
                "total_invested": player.total_invested,
                "folded": player.folded,
                "all_in": player.all_in,
            }
            for pid, player in state.players.items()
        },
        "seat_order": list(state.seat_order),
        "button": state.button,
        "acting_player": state.acting_player,
        "small_blind_player": state.small_blind_player,
        "big_blind_player": state.big_blind_player,
        "current_bet": state.current_bet,
        "min_raise_size": state.min_raise_size,
        "last_aggressor": state.last_aggressor,
        "pending_actions": sorted(state.pending_actions),
        "winner": state.winner,
        "winners": list(state.winners),
        "result_text": state.result_text,
        "result_details": list(state.result_details),
        "terminal": state.terminal,
        "history": [
            {
                "player_id": action.player_id,
                "action": action.action.value,
                "amount": action.amount,
                "street": action.street.value,
                "pot_after": action.pot_after,
                "pot_before": action.pot_before,
                "to_call_before": action.to_call_before,
                "live_players_before": action.live_players_before,
            }
            for action in state.history
        ],
        "decision_reviews": list(state.decision_reviews),
        "difficulty": state.difficulty,
        "starting_stacks": dict(state.starting_stacks),
        "deck_cards": list(state.deck.cards) if state.deck is not None else None,
    }


def deserialize_state(payload: dict) -> GameState:
    players = {
        pid: PlayerState(
            id=value["id"],
            name=value["name"],
            seat=value["seat"],
            stack=value["stack"],
            is_bot=value.get("is_bot", False),
            profile_id=value.get("profile_id"),
            difficulty=value.get("difficulty", "normal"),
            position=value.get("position", ""),
            hole_cards=list(value.get("hole_cards", [])),
            street_invested=value.get("street_invested", 0.0),
            total_invested=value.get("total_invested", 0.0),
            folded=value.get("folded", False),
            all_in=value.get("all_in", False),
        )
        for pid, value in payload["players"].items()
    }
    history = [
        Action(
            player_id=value["player_id"],
            action=ActionType(value["action"]),
            amount=value.get("amount", 0.0),
            street=Street(value.get("street", Street.PREFLOP.value)),
            pot_after=value.get("pot_after", 0.0),
            pot_before=value.get("pot_before", 0.0),
            to_call_before=value.get("to_call_before", 0.0),
            live_players_before=value.get("live_players_before", 0),
        )
        for value in payload.get("history", [])
    ]
    deck_cards = payload.get("deck_cards")
    return GameState(
        hand_id=payload["hand_id"],
        street=Street(payload["street"]),
        pot=payload["pot"],
        board=list(payload["board"]),
        players=players,
        seat_order=list(payload["seat_order"]),
        button=payload["button"],
        acting_player=payload.get("acting_player"),
        small_blind_player=payload.get("small_blind_player"),
        big_blind_player=payload.get("big_blind_player"),
        current_bet=payload["current_bet"],
        min_raise_size=payload["min_raise_size"],
        last_aggressor=payload.get("last_aggressor"),
        pending_actions=set(payload.get("pending_actions", [])),
        winner=payload.get("winner"),
        winners=list(payload.get("winners", [])),
        result_text=payload.get("result_text", ""),
        result_details=list(payload.get("result_details", [])),
        terminal=payload.get("terminal", False),
        history=history,
        decision_reviews=list(payload.get("decision_reviews", [])),
        difficulty=payload.get("difficulty", "normal"),
        starting_stacks=dict(payload.get("starting_stacks", {})),
        deck=Deck.from_remaining(deck_cards) if deck_cards is not None else None,
    )
