"""「问问我的健康」接口：消息 / 会话 / 候选事件确认（F-AG）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import repository as repo
from ..deps import current_user, scoped_profile
from ..engine import agent

router = APIRouter(prefix="/ask", tags=["问问我的健康"])


class AskBody(BaseModel):
    profile_id: str
    conversation_id: str | None = None
    text: str = Field(min_length=1, max_length=1000)


@router.post("")
def ask(body: AskBody, user: dict = Depends(current_user)):
    scoped_profile(body.profile_id, user)
    return agent.handle(body.profile_id, body.conversation_id,
                        body.text.strip())


@router.get("/conversations")
def conversations(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    return {"items": repo.list_conversations(profile_id)}


@router.get("/conversations/{cid}")
def messages(cid: str, user: dict = Depends(current_user)):
    conv = repo.get_conversation(cid)
    if conv is None:
        raise HTTPException(404, "会话不存在")
    scoped_profile(conv["profile_id"], user)
    return {"conversation": conv, "messages": repo.list_messages(cid)}
