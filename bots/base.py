from abc import ABC, abstractmethod
from pydantic import BaseModel

from poker.models import GameState, ActionType


class BotDecision(BaseModel):
    action: ActionType
    amount: float = 0.0
    confidence: float = 0.0
    reason: str = ""


class PokerBot(ABC):
    @abstractmethod
    def decide(self, state: GameState, player_id: str) -> BotDecision:
        ...
