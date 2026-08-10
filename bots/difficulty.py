from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DifficultyProfile:
    key: str
    label: str
    iterations: int
    policy_power: float
    mistake_rate: float
    max_mistake_ev_bb: float
    description: str

    def public_dict(self) -> dict:
        data = asdict(self)
        # Internal tuning parameters do not need to clutter the client UI.
        return {
            "key": data["key"],
            "label": data["label"],
            "iterations": data["iterations"],
            "mistake_rate": data["mistake_rate"],
            "description": data["description"],
        }


DIFFICULTIES: dict[str, DifficultyProfile] = {
    "easy": DifficultyProfile(
        key="easy",
        label="Лёгкий",
        iterations=70,
        policy_power=0.55,
        mistake_rate=0.38,
        max_mistake_ev_bb=2.50,
        description="Чаще отклоняется от сильной линии и допускает заметные, но правдоподобные ошибки.",
    ),
    "normal": DifficultyProfile(
        key="normal",
        label="Нормальный",
        iterations=180,
        policy_power=0.82,
        mistake_rate=0.14,
        max_mistake_ev_bb=1.10,
        description="Стабильный соперник для регулярной тренировки: иногда ошибается, но редко дарит крупные банки.",
    ),
    "hard": DifficultyProfile(
        key="hard",
        label="Сложный",
        iterations=420,
        policy_power=1.0,
        mistake_rate=0.025,
        max_mistake_ev_bb=0.40,
        description="Почти не делает искусственных ошибок и считает споты заметно точнее.",
    ),
    "maximum": DifficultyProfile(
        key="maximum",
        label="Максимальный",
        iterations=950,
        policy_power=1.0,
        mistake_rate=0.0,
        max_mistake_ev_bb=0.0,
        description="Максимум CFR-lite итераций без специально добавленных ошибок. Самый сильный режим этой версии.",
    ),
}

ALIASES = {
    "easy": "easy",
    "light": "easy",
    "легкий": "easy",
    "лёгкий": "easy",
    "normal": "normal",
    "medium": "normal",
    "нормальный": "normal",
    "hard": "hard",
    "сложный": "hard",
    "maximum": "maximum",
    "max": "maximum",
    "максимальный": "maximum",
}


def normalize_difficulty(value: str | None) -> str:
    if not value:
        return "normal"
    return ALIASES.get(str(value).strip().lower(), "normal")


def get_difficulty(value: str | None) -> DifficultyProfile:
    return DIFFICULTIES[normalize_difficulty(value)]
