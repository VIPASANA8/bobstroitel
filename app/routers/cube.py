from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import AuthenticatedUser, get_current_user
from online import cube
from online.ledger import InsufficientPlayBalance
from online.schema import cube_rounds


router = APIRouter(prefix="/api/cube", tags=["cube"])


class RollRequest(BaseModel):
    stake_units: int = Field(ge=cube.STAKE_STEP, le=cube.MAX_STAKE)
    selected: list[int] = Field(min_length=1, max_length=cube.MAX_SELECTED)
    request_id: str = Field(min_length=1, max_length=200)


def _round_payload(row, balance_units: int) -> dict[str, object]:
    return {
        "round_id": row["id"],
        "stake_units": int(row["stake_units"]),
        "selected": [int(face) for face in row["selected"].split(",")],
        "roll": int(row["roll"]),
        "payout_units": int(row["payout_units"]),
        "won": int(row["payout_units"]) > 0,
        "balance_units": balance_units,
    }


@router.post("/roll")
async def roll(
    payload: RollRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Draw one CUBE round and settle it against the player's PLAY wallet.

    The browser never decides anything: it posts a stake and a selection and is
    told the face. Drawing it client-side is what the standalone game does with
    its own play wallet; here the wallet is the same one the poker tables pay
    from, so the draw belongs on this side of the wire.

    Everything below happens in one transaction with the wallet row locked --
    the balance is read, the face is drawn against it, and the money moves --
    so a stake cannot be spent twice by a player sitting at a table in another
    tab. The round row goes in before the money so a repeated request_id
    collides on its unique constraint, rolls the whole thing back, and is
    answered with the round that did settle.
    """
    ledger = request.app.state.ledger
    try:
        selected = cube.validate(payload.stake_units, payload.selected)
    except cube.CubeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async with request.app.state.session_factory() as session:
        try:
            async with session.begin():
                await ledger.ensure_user_wallet(user.user_id, session=session)
                balance = await ledger.available_units(user.user_id, session=session)
                if payload.stake_units > balance:
                    raise InsufficientPlayBalance("Недостаточно средств на балансе.")

                face = cube.roll_face(selected)
                payout = (
                    cube.potential_payout(payload.stake_units, len(selected))
                    if face in selected
                    else 0
                )
                round_id = uuid.uuid4().hex
                await session.execute(cube_rounds.insert().values(
                    id=round_id,
                    user_id=user.user_id,
                    request_id=payload.request_id,
                    stake_units=payload.stake_units,
                    selected=",".join(str(value) for value in selected),
                    roll=face,
                    payout_units=payout,
                ))
                result = await ledger.settle_cube_round(
                    user.user_id,
                    round_id,
                    payload.stake_units,
                    payout,
                    f"cube:{user.user_id}:{payload.request_id}",
                    session=session,
                )
        except IntegrityError:
            settled = await _replay(request, user, payload.request_id)
            if settled is None:
                raise
            return settled
        except InsufficientPlayBalance as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        row = (await session.execute(
            select(cube_rounds).where(cube_rounds.c.id == round_id)
        )).mappings().one()
        return _round_payload(row, result.available_units)


async def _replay(
    request: Request, user: AuthenticatedUser, request_id: str
) -> dict[str, object] | None:
    """The round this request_id already settled, if that is what collided."""
    async with request.app.state.session_factory() as session:
        row = (await session.execute(
            select(cube_rounds).where(
                cube_rounds.c.user_id == user.user_id,
                cube_rounds.c.request_id == request_id,
            )
        )).mappings().first()
        if row is None:
            return None
        balance = await request.app.state.ledger.available_units(
            user.user_id, session=session
        )
        return _round_payload(row, balance)
