"""健康分析接口：创建（含缓存复用）/ 查询 / TOP 问题 / 问题详情（F-AN）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import repository as repo
from ..deps import current_user, scoped_profile
from ..engine import assessment as engine

router = APIRouter(prefix="/assessments", tags=["健康分析"])


class RunBody(BaseModel):
    profile_id: str
    force: bool = False


@router.post("/run")
def run(body: RunBody, user: dict = Depends(current_user)):
    scoped_profile(body.profile_id, user)
    snap = repo.input_snapshot(body.profile_id)
    if snap["report_count"] == 0 and snap["event_count"] == 0:
        raise HTTPException(409, "档案中还没有可用资料：请先上传健康报告，"
                                 "或通过「问问我的健康」记录健康事件")
    return engine.run_assessment(body.profile_id, force=body.force)


@router.get("/scope")
def scope(profile_id: str, user: dict = Depends(current_user)):
    """分析前展示本次将使用的数据范围（F-UP-08 / AC-06）。"""
    scoped_profile(profile_id, user)
    return repo.input_snapshot(profile_id)


@router.get("/latest")
def latest(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    a = repo.latest_assessment(profile_id)
    if a is None:
        return {"assessment": None}
    a["issues"] = repo.list_issues(a["id"])
    a["prediction"] = a.get("summary", {}).get("prediction")
    a["risk_timeline"] = a.get("summary", {}).get("risk_timeline")
    return {"assessment": a}


@router.get("/risk-timeline")
def risk_timeline(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    from ..engine.prediction import compute_risk_timeline
    return compute_risk_timeline(profile_id)


@router.get("/history")
def history(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    return {"items": repo.list_assessments(profile_id)}


@router.get("/{aid}")
def get_assessment(aid: str, user: dict = Depends(current_user)):
    a = repo.get_assessment(aid)
    if a is None:
        raise HTTPException(404, "分析不存在")
    scoped_profile(a["profile_id"], user)
    a["issues"] = repo.list_issues(aid)
    a["prediction"] = a.get("summary", {}).get("prediction")
    a["risk_timeline"] = a.get("summary", {}).get("risk_timeline")
    return a


@router.get("/issues/{iid}")
def issue_detail(iid: str, user: dict = Depends(current_user)):
    it = repo.get_issue(iid)
    if it is None:
        raise HTTPException(404, "问题不存在")
    a = repo.get_assessment(it["assessment_id"])
    scoped_profile(a["profile_id"], user)
    it["assessment_created_at"] = a["created_at"]
    return it
