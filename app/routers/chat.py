from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field

from app.dependencies import AuthenticatedUser, get_current_user
from online.chat import CHAT_TEXT_MAX, ChatError, ChatRateLimited


router = APIRouter(prefix="/api/tables/{table_id}/chat", tags=["chat"])


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=CHAT_TEXT_MAX)


@router.get("")
async def recent_chat(table_id: str, request: Request, limit: int = Query(50, ge=1, le=50), user: AuthenticatedUser = Depends(get_current_user)):
    rows = await request.app.state.chat.recent(table_id, limit)
    return {"messages": [{"id": row.id, "user_id": row.user_id, "display_name": row.display_name, "text": row.text, "created_at": row.created_at.isoformat()} for row in rows]}


@router.post("")
async def post_chat(table_id: str, payload: ChatRequest, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    try:
        row = await request.app.state.chat.post(table_id, user.user_id, payload.text)
    except ChatRateLimited as exc:
        raise HTTPException(status_code=429, detail={"code": "chat_rate_limited", "message": str(exc)}) from exc
    except ChatError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_chat", "message": str(exc)}) from exc
    message = {"id": row.id, "user_id": row.user_id, "display_name": row.display_name, "text": row.text, "created_at": row.created_at.isoformat()}
    hub = getattr(request.app.state, "connection_hub", None)
    if hub is not None:
        # Nothing else reloads the log, so without this only the sender sees it.
        await hub.broadcast_json(table_id, {"type": "chat", "message": message})
    return message
