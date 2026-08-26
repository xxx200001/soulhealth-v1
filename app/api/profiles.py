"""档案接口：最小建档 / 渐进补充 / 时间线 / 健康事件 / 待确认项。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import repository as repo
from ..deps import current_user, scoped_profile
from ..engine import agent as agent_engine

router = APIRouter(prefix="/profiles", tags=["健康档案"])


class ProfileCreate(BaseModel):
    name: str
    sex: str | None = None          # female | male
    birth_date: str | None = None   # YYYY-MM-DD


class ProfilePatch(BaseModel):
    name: str | None = None
    sex: str | None = None
    birth_date: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    pregnant: bool | None = None
    allergies: list[str] | None = None
    medications: list[str] | None = None
    conditions: list[str] | None = None
    surgeries: list[str] | None = None
    smoking: str | None = None
    alcohol: str | None = None
    diet_pref: list[str] | None = None


@router.get("")
def list_profiles(user: dict = Depends(current_user)):
    return {"items": repo.list_profiles(user["id"])}


@router.post("")
def create_profile(body: ProfileCreate, user: dict = Depends(current_user)):
    """最小建档（F-ON-02）：仅姓名/昵称、性别、出生年月即可开始。"""
    if not body.name.strip():
        raise HTTPException(422, "请填写姓名或昵称")
    p = repo.create_profile(user["id"], body.name.strip(), body.sex,
                            body.birth_date)
    return p


@router.get("/{pid}")
def get_profile(pid: str, user: dict = Depends(current_user)):
    p = scoped_profile(pid, user)
    repo.touch_profile(pid)
    return p


@router.patch("/{pid}")
def patch_profile(pid: str, body: ProfilePatch,
                  user: dict = Depends(current_user)):
    scoped_profile(pid, user)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if "pregnant" in patch:
        patch["pregnant"] = 1 if patch["pregnant"] else 0
    return repo.update_profile(pid, patch)


@router.get("/{pid}/timeline")
def timeline(pid: str, user: dict = Depends(current_user)):
    """健康时间线：按真实发生日期串联报告/事件/分析/方案（F-REC-01）。"""
    scoped_profile(pid, user)
    return {"items": repo.timeline(pid)}


class EventIn(BaseModel):
    event_date: str
    type: str = "note"
    content: str


@router.get("/{pid}/events")
def list_events(pid: str, user: dict = Depends(current_user)):
    scoped_profile(pid, user)
    return {"items": repo.list_events(pid)}


@router.post("/{pid}/events")
def add_event(pid: str, body: EventIn, user: dict = Depends(current_user)):
    scoped_profile(pid, user)
    if not body.content.strip():
        raise HTTPException(422, "内容不能为空")
    return repo.add_event(pid, body.event_date, body.type,
                          body.content.strip(), "user_entry")


@router.get("/{pid}/candidates")
def pending_candidates(pid: str, user: dict = Depends(current_user)):
    scoped_profile(pid, user)
    return {"items": repo.pending_candidates(pid)}


class CandidateResolve(BaseModel):
    accept: bool


@router.post("/{pid}/candidates/{cid}")
def resolve_candidate(pid: str, cid: str, body: CandidateResolve,
                      user: dict = Depends(current_user)):
    scoped_profile(pid, user)
    cand = repo.get_candidate(cid)
    if cand is None or cand["profile_id"] != pid:
        raise HTTPException(404, "候选事件不存在")
    return agent_engine.confirm_candidate(cid, body.accept)
