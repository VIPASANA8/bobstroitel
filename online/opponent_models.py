from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from online.schema import hand_actions, hands, hand_players


@dataclass(frozen=True)
class OpponentModel:
    user_id: str
    sample_count: int
    recency_weight: float
    confidence: float
    vpip: float
    pfr: float
    three_bet: float
    fold_to_three_bet: float
    postflop_aggression: float
    traits: dict[str, str]
    exploit: dict[str, float]


class OnlineOpponentModel:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def model_for(self, user_id: str) -> OpponentModel:
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(hand_actions, hands.c.started_at)
                    .join(hand_players, hand_players.c.hand_id == hand_actions.c.hand_id)
                    .join(hands, hands.c.id == hand_actions.c.hand_id)
                    .where(hand_players.c.user_id == user_id, hand_players.c.participant_id == hand_actions.c.participant_id)
                    .order_by(hands.c.started_at.desc(), hand_actions.c.sequence)
                )
            ).mappings().all()

        hand_order = []
        for row in rows:
            if row["hand_id"] not in hand_order:
                hand_order.append(row["hand_id"])
        sample_count = len(hand_order)
        weights = {hand_id: math.exp(-index / 3.0) for index, hand_id in enumerate(hand_order)}
        recency_weight = sum(weights.values())
        preflop = [row for row in rows if row["street"] == "preflop"]
        by_hand = {hand_id: [row for row in preflop if row["hand_id"] == hand_id] for hand_id in hand_order}
        decisions = [hand_id for hand_id, actions in by_hand.items() if actions]
        vpip_hands = [hand_id for hand_id, actions in by_hand.items() if any(row["action"] in {"call", "bet", "raise", "all_in"} for row in actions)]
        pfr_hands = [hand_id for hand_id, actions in by_hand.items() if any(row["action"] in {"bet", "raise", "all_in"} for row in actions)]
        postflop = [row for row in rows if row["street"] != "preflop"]
        aggressive_postflop = sum(row["action"] in {"bet", "raise", "all_in"} for row in postflop)
        postflop_aggression = aggressive_postflop / len(postflop) if postflop else 0.0
        denominator = max(1, len(decisions))
        confidence = min(1.0, recency_weight / 20.0)
        return OpponentModel(
            user_id=user_id,
            sample_count=sample_count,
            recency_weight=recency_weight,
            confidence=confidence,
            vpip=len(vpip_hands) / denominator,
            pfr=len(pfr_hands) / denominator,
            three_bet=0.0,
            fold_to_three_bet=0.0,
            postflop_aggression=postflop_aggression,
            traits={"style": "aggressive" if len(pfr_hands) > len(decisions) / 2 else "balanced"},
            exploit={"value_widen": 0.0, "bluff_pressure": 0.0, "call_down": 0.0, "preflop_passivity": max(0.0, 1.0 - len(pfr_hands) / denominator)},
        )
