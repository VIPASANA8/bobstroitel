"""A stable playing style per bot, so a table stops looking like one brain.

Every seat runs the same MultiwayBot, so six of them played a hand exactly
alike: same fold threshold, same bluff rate, same fraction of the pot every
single time. That is the thing a person actually notices -- not that the
strategy is wrong, but that nobody at the table has a character.

The style is derived from the bot's own id, so it never has to be stored and
never drifts: the same opponent tightens up or barrels the same way today as
last week, which is how a regular at a table behaves.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    tightness: float   # -1 loose .. +1 tight -- how readily it lets a hand go
    aggression: float  # -1 passive .. +1 aggressive -- how readily it raises
    bluffiness: float  # 0 .. 2 -- multiplier on the bluff rate
    sizing_bias: float # multiplier on every pot fraction it picks
    patience: float    # multiplier on its think time

    @property
    def label(self) -> str:
        """Only for logs and tests -- players are never shown a bot's style."""
        tight = "tight" if self.tightness > 0.25 else "loose" if self.tightness < -0.25 else "even"
        aggro = "aggressive" if self.aggression > 0.25 else "passive" if self.aggression < -0.25 else "steady"
        return f"{tight}-{aggro}"


def persona_for(player_id: str) -> Persona:
    """Deterministic in the id, and only in the id."""
    digest = hashlib.blake2b(str(player_id).encode("utf-8"), digest_size=8).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    # Bounds are deliberately modest: this varies how a competent player is
    # built, it does not turn anyone into a maniac or a rock.
    return Persona(
        tightness=rng.uniform(-0.7, 0.7),
        aggression=rng.uniform(-0.7, 0.7),
        bluffiness=rng.uniform(0.35, 1.9),
        sizing_bias=rng.uniform(0.78, 1.28),
        patience=rng.uniform(0.7, 1.45),
    )
