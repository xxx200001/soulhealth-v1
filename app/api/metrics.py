"""指标中心接口：跨报告历史序列、趋势与本次 VS 上次（F-DATA / F-REC-03）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import repository as repo
from ..deps import current_user, scoped_profile
from ..standardize.registry import GRADE_LABELS, get_registry
from ..standardize.trends import SeriesPoint, analyze_series

router = APIRouter(prefix="/metrics", tags=["指标中心"])


@router.get("/codes")
def codes(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    registry = get_registry()
    items = []
    for c in repo.all_codes(profile_id):
        meta = registry.get(c["code"]) if c["code"] else None
        items.append({**c, "name_cn": meta.name_cn if meta else c["code"],
                      "unit": meta.canonical_unit if meta else ""})
    return {"items": items}


@router.get("/series")
def series(profile_id: str, code: str, user: dict = Depends(current_user)):
    """单指标完整序列 + 趋势洞察（真实检查日期，每点可回溯 report_id）。"""
    p = scoped_profile(profile_id, user)
    registry = get_registry()
    meta = registry.get(code)
    rows = repo.series_by_code(profile_id, code)
    pts = [SeriesPoint(r["value"], r["observed_at"], r["report_id"],
                       r["grade"] or 0, r["unit"]) for r in rows]
    ins = analyze_series(code, pts, meta)
    sex = {"female": "F", "male": "M"}.get(p.get("sex"), "U")
    iv = meta.match_interval(sex, p.get("age_years")) if meta else None
    return {
        "code": code,
        "name_cn": meta.name_cn if meta else code,
        "unit": meta.canonical_unit if meta else (rows[-1]["unit"] if rows else ""),
        "ref": {"low": iv.lower, "high": iv.upper} if iv else None,
        "grade_labels": GRADE_LABELS,
        "insight": ins.to_dict() if ins else None,
    }
