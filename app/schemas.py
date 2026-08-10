from pydantic import BaseModel, Field
from poker.models import ActionType


class PlayerActionRequest(BaseModel):
    action: ActionType
    amount: float = Field(default=0.0, ge=0.0)


class BotSeatRequest(BaseModel):
    name: str | None = Field(default=None, max_length=24)
    difficulty: str = "normal"


class HumanSeatRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)


class ProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=24)


class ProfileRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=24)


class SavedTableRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class SavedTableRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class BotCooldownRequest(BaseModel):
    minutes: int = Field(ge=5, le=15)
