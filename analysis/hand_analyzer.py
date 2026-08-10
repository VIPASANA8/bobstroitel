from poker.models import GameState


class HandAnalyzer:
    def analyze(self, state: GameState):
        hero = state.players.get("hero")
        total_loss = sum(float(r.get("ev_loss_bb", 0.0)) for r in state.decision_reviews)
        return {
            "hand_id": state.hand_id,
            "complete": state.terminal,
            "players": len(state.seat_order),
            "winner": state.winner,
            "winners": state.winners,
            "result": state.result_text,
            "side_pots": state.result_details,
            "hero_total_invested": round(hero.total_invested, 2) if hero else 0.0,
            "trainer_summary": {
                "decisions_reviewed": len(state.decision_reviews),
                "total_ev_loss_bb": round(total_loss, 3),
                "reviews": state.decision_reviews,
            },
            "actions": [
                {
                    "street": a.street.value,
                    "player": a.player_id,
                    "action": a.action.value,
                    "amount": round(a.amount, 2),
                }
                for a in state.history
            ],
            "note": (
                "v0.8 поддерживает 2–7 игроков и отдельные профили. CFR-lite разбор остаётся heads-up; "
                "multiway решения ботов используют Monte Carlo equity и pot odds."
            ),
        }
