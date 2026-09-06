"""CUBE: the dice game lifted out of CASE8, settled here on PLAY chips.

Pick one to three faces of a six-sided die and stake on them. A face pays what
its share of the cube is worth -- x6, x3, x2 for one, two or three faces -- so
the payout is honest arithmetic. The house keeps its 20% in the *chance*
instead: a chosen face comes up only 80% as often as an honest die would give
it, which is what holds the game at the 80% RTP the economy was designed
around. Both halves are CASE8's, from src/features/cube/game/game.ts.

What was left behind is the risk pool. There it throttles the win chance
further whenever the pool cannot cover the payout, because there the payout is
money someone has to have. Here the counterparty is the play faucet, which
mints chips and is allowed to go negative by design, so a pool that can never
run dry would only ever multiply the chance by one.

Amounts are PLAY units, and a unit is a cent: the same integers the lobby and
the tables count in, so a stake needs no conversion on either side of the wire.
"""
from __future__ import annotations

import secrets
from typing import Iterable, Sequence


FACES = (1, 2, 3, 4, 5, 6)
#: The smallest stake and the grid every stake sits on -- $0.05.
STAKE_STEP = 5
MAX_STAKE = 100_000
#: Payout per unit staked, in tenths, by how many faces were picked.
MULTIPLIER_TENTHS = {1: 60, 2: 30, 3: 20}
TARGET_RTP = 0.8
MAX_SELECTED = 3


class CubeError(ValueError):
    """A round the rules refuse. The message is shown to the player as-is."""


def potential_payout(stake_units: int, selected_count: int) -> int:
    """What a winning round pays, rounded half-up like CASE8 rounds it."""
    return (stake_units * MULTIPLIER_TENTHS[selected_count] + 5) // 10


def validate(stake_units: int, selected: Iterable[int]) -> tuple[int, ...]:
    """The selection as a sorted tuple, or CubeError naming what is wrong."""
    faces = tuple(sorted(set(selected)))
    chosen = list(selected)
    if not 1 <= len(chosen) <= MAX_SELECTED or len(faces) != len(chosen) or any(
        face not in FACES for face in faces
    ):
        raise CubeError("Выберите от 1 до 3 уникальных граней от 1 до 6.")
    if (
        stake_units < STAKE_STEP
        or stake_units > MAX_STAKE
        or stake_units % STAKE_STEP != 0
    ):
        raise CubeError("Ставка должна быть от $0.05 до $1000 с шагом $0.05.")
    return faces


def roll_face(selected: Sequence[int], rng: secrets.SystemRandom | None = None) -> int:
    """The face this round comes up on.

    The draw decides the *outcome* first and the face second: a win lands on
    one of the chosen faces, a loss on one of the others. Rolling an honest die
    and paying honest odds would return the whole 100% to the player, so the
    edge has to live somewhere, and CASE8 put it here rather than in the
    payout, where the player would have to read it off a coefficient.
    """
    source = rng or secrets.SystemRandom()
    win_chance = len(selected) / 6 * TARGET_RTP
    pool = (
        sorted(selected)
        if source.random() < win_chance
        else [face for face in FACES if face not in selected]
    )
    return source.choice(pool)


def demo() -> None:
    """Odds and payouts hold over a long run -- the one thing worth checking."""
    for count in (1, 2, 3):
        selected = FACES[:count]
        stake = 100
        assert potential_payout(stake, count) == stake * MULTIPLIER_TENTHS[count] // 10
        rounds = 200_000
        wins = sum(roll_face(selected) in selected for _ in range(rounds))
        expected = count / 6 * TARGET_RTP
        assert abs(wins / rounds - expected) < 0.01, (count, wins / rounds, expected)
        # Honest payout times a throttled chance is the 80% the economy expects.
        rtp = expected * MULTIPLIER_TENTHS[count] / 10
        assert abs(rtp - TARGET_RTP) < 1e-9, (count, rtp)
    assert potential_payout(5, 1) == 30 and potential_payout(5, 3) == 10
    for bad in ((4, (1,)), (5, ()), (5, (1, 2, 3, 4)), (5, (0,)), (100_005, (1,))):
        try:
            validate(*bad)
        except CubeError:
            continue
        raise AssertionError(f"accepted {bad!r}")
    print("cube ok")


if __name__ == "__main__":
    demo()
