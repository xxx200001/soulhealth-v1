"""方案接口：食补（四类食物池+菜谱）与药食同源茶饮（含 Safety 闸门）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import repository as repo
from ..deps import current_user, scoped_profile
from ..engine import assessment as assess_engine
from ..engine import dietplan, teaplan

router = APIRouter(prefix="/plans", tags=["健康方案"])


class GenBody(BaseModel):
    profile_id: str


def _ready_assessment(profile_id: str) -> dict:
    a = assess_engine.run_assessment(profile_id)   # 输入未变时命中缓存（AC-19）
    if a["status"] not in ("completed", "partial"):
        raise HTTPException(409, "健康分析未完成，无法生成方案")
    return a


# ---------------------------------------------------------------- 食补
@router.post("/diet/generate")
def diet_generate(body: GenBody, user: dict = Depends(current_user)):
    scoped_profile(body.profile_id, user)
    a = _ready_assessment(body.profile_id)
    return dietplan.generate(body.profile_id, a)


@router.get("/diet/active")
def diet_active(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    return {"plan": repo.active_diet_plan(profile_id)}


@router.get("/diet/history")
def diet_history(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    return {"items": repo.list_diet_plans(profile_id)}


@router.get("/diet/{dpid}")
def diet_get(dpid: str, user: dict = Depends(current_user)):
    p = repo.get_diet_plan(dpid)
    if p is None:
        raise HTTPException(404, "方案不存在")
    scoped_profile(p["profile_id"], user)
    return p


@router.get("/recipes/{rcid}")
def recipe(rcid: str, user: dict = Depends(current_user)):
    rc = repo.get_recipe(rcid)
    if rc is None:
        raise HTTPException(404, "菜谱不存在")
    plan = repo.get_diet_plan(rc["diet_plan_id"])
    scoped_profile(plan["profile_id"], user)
    return rc


# ---------------------------------------------------------------- 茶饮
@router.post("/tea/generate")
def tea_generate(body: GenBody, user: dict = Depends(current_user)):
    """生成前必经 Safety Engine；缺关键信息返回 require_info（AC-13），
    block / professional_review 不输出完整方案（AC-14）。"""
    scoped_profile(body.profile_id, user)
    a = _ready_assessment(body.profile_id)
    return teaplan.generate(body.profile_id, a)


@router.get("/tea/active")
def tea_active(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    plan = repo.active_tea_plan(profile_id)
    if plan and plan.get("safety_check_id"):
        plan["safety_check"] = repo.get_safety_check(plan["safety_check_id"])
    return {"plan": plan}


@router.get("/tea/history")
def tea_history(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    return {"items": repo.list_tea_plans(profile_id)}


@router.get("/tea/{tid}")
def tea_get(tid: str, user: dict = Depends(current_user)):
    p = repo.get_tea_plan(tid)
    if p is None:
        raise HTTPException(404, "方案不存在")
    scoped_profile(p["profile_id"], user)
    if p.get("safety_check_id"):
        p["safety_check"] = repo.get_safety_check(p["safety_check_id"])
    return p
