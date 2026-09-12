"""Support tickets, as the site sees them. The bots talk to the same service."""
from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.dependencies import AuthenticatedUser, get_current_user
from online.support import MAX_PHOTO_BYTES, SupportError


router = APIRouter(prefix="/api/support", tags=["support"])


class Photo(BaseModel):
    """Base64 in JSON rather than multipart: nothing else here uploads a file,
    and 5 MB of base64 is not worth a parser dependency."""

    content_type: str = Field(max_length=64)
    # 4/3 of the byte cap, plus padding.
    data: str = Field(min_length=1, max_length=MAX_PHOTO_BYTES * 4 // 3 + 4)

    def bytes(self) -> bytes:
        try:
            return base64.b64decode(self.data, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="изображение повреждено") from None


class NewTicket(BaseModel):
    topic: str = Field(max_length=16)
    text: str = Field(max_length=2000)
    reference_kind: str | None = Field(default=None, max_length=16)
    reference_id: str | None = Field(default=None, max_length=64)
    photo: Photo | None = None


class NewMessage(BaseModel):
    text: str = Field(default="", max_length=2000)
    photo: Photo | None = None


def _service(request: Request):
    return request.app.state.support


def _photo(body) -> tuple[bytes | None, str | None]:
    if body.photo is None:
        return None, None
    return body.photo.bytes(), body.photo.content_type


async def _call(coro):
    try:
        return await coro
    except SupportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tickets")
async def list_tickets(request: Request, closed: bool = False,
                       user: AuthenticatedUser = Depends(get_current_user)):
    return {"tickets": await _service(request).tickets(user.user_id, closed=closed)}


@router.get("/references")
async def references(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    return {"references": await _service(request).references(user.user_id)}


@router.post("/tickets", status_code=201)
async def open_ticket(body: NewTicket, request: Request,
                      user: AuthenticatedUser = Depends(get_current_user)):
    photo, photo_type = _photo(body)
    return await _call(_service(request).open(
        user_id=user.user_id, tenant_id=user.tenant_id, topic=body.topic, text=body.text,
        reference_kind=body.reference_kind, reference_id=body.reference_id,
        photo=photo, photo_type=photo_type,
    ))


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, request: Request,
                     user: AuthenticatedUser = Depends(get_current_user)):
    ticket = await _service(request).ticket(user.user_id, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="обращение не найдено")
    return ticket


@router.post("/tickets/{ticket_id}/messages", status_code=201)
async def reply(ticket_id: str, body: NewMessage, request: Request,
                user: AuthenticatedUser = Depends(get_current_user)):
    photo, photo_type = _photo(body)
    return await _call(_service(request).user_reply(
        user_id=user.user_id, ticket_id=ticket_id, text=body.text,
        photo=photo, photo_type=photo_type,
    ))


@router.post("/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: str, request: Request,
                       user: AuthenticatedUser = Depends(get_current_user)):
    await _call(_service(request).close(ticket_id, user_id=user.user_id))
    return {"status": "closed"}
