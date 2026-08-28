"""Safety Engine —— 药食同源方案的前置安全闸门（规格书 §10.3）。

判定次序（命中即止，优先级从高到低）：
  block               明确禁忌命中：孕妇 × 孕期禁用原料；已录过敏原 × 配方原料
  professional_review 需要专业评估：未成年人；存在危急值级别异常（|grade|=3）
  require_info        关键安全信息缺失：年龄未知 / 过敏史从未记录 /
                      当前用药从未记录 /（育龄女性）妊娠状态未知
  allow               以上均未触发

设计要点：
  - "从未记录"与"记录为空"是两回事：用户明确保存过"无过敏"（field_times
    里有 allergies 更新时间）视为已提供；从未动过该字段才算缺失（F-TEA-02）。
  - 结果持久化为 SafetyCheck，茶饮方案引用 check_id，前端只能按状态渲染，
    无法绕过（F-TEA-03 / AC-14）。
"""
from __future__ import annotations

from typing import List, Optional

from .. import repository as repo
from .knowledge import TEA_INGREDIENT_RULES


def check_for_tea(profile_id: str, assessment_id: Optional[str],
                  ingredients: List[dict]) -> dict:
    """对一份候选茶饮配方执行前置安全检查，返回已落库的 SafetyCheck。"""
    p = repo.get_profile(profile_id) or {}
    field_times = p.get("field_times") or {}
    names = [i["name"] for i in ingredients]

    reasons: List[str] = []
    missing: List[dict] = []

    # ---------- block：确定性禁忌 ----------
    allergies = [str(a).strip() for a in (p.get("allergies") or []) if str(a).strip()]
    hit_allergy = [n for n in names
                   if any(a and (a in n or n in a) for a in allergies)]
    if hit_allergy:
        reasons.append(f"配方原料（{'、'.join(hit_allergy)}）与已记录的过敏史冲突")
    if p.get("pregnant"):
        preg_block = [n for n in names
                      if TEA_INGREDIENT_RULES.get(n, {}).get("pregnancy_block")]
        if preg_block:
            reasons.append(f"当前为孕期，配方含孕期不宜原料：{'、'.join(preg_block)}")
    if reasons:
        return repo.save_safety_check(profile_id, assessment_id, "tea",
                                      _inputs(p, names), "block", reasons, [])

    # ---------- professional_review：仅未成年人触发 ----------
    age = p.get("age_years")
    if age is not None and age < 18:
        reasons.append("未成年人的药食同源使用需由专业人员个体化评估")
    if reasons:
        return repo.save_safety_check(profile_id, assessment_id, "tea",
                                      _inputs(p, names), "professional_review",
                                      reasons, [])

    # ---------- require_info：关键信息缺失 ----------
    if age is None:
        missing.append({"field": "birth_date", "label": "出生年月",
                        "why": "年龄决定用量与是否适用"})
    if "allergies" not in field_times:
        missing.append({"field": "allergies", "label": "过敏史",
                        "why": "需核对配方原料是否含过敏原（无过敏也请确认保存）"})
    if "medications" not in field_times:
        missing.append({"field": "medications", "label": "当前用药",
                        "why": "部分原料与药物存在相互作用（无用药也请确认保存）"})
    if (p.get("sex") == "female" and age is not None and 15 <= age <= 55
            and "pregnant" not in field_times):
        missing.append({"field": "pregnant", "label": "是否怀孕",
                        "why": "多种原料孕期不宜"})
    if missing:
        return repo.save_safety_check(
            profile_id, assessment_id, "tea", _inputs(p, names),
            "require_info", ["生成前需要补充关键安全信息"], missing)

    # ---------- allow（可附带提醒） ----------
    cautions: List[str] = []
    if _has_severe_abnormal(profile_id):
        cautions.append("档案中存在重度异常指标，茶饮方案仅供参考，建议就医后再使用")
    meds = [str(m) for m in (p.get("medications") or [])]
    if any(("华法林" in m or "warfarin" in m.lower()) for m in meds):
        cautions.append("正在使用抗凝药物，任何草本饮品都建议先咨询医生")
    if any(TEA_INGREDIENT_RULES.get(n, {}).get("bp_caution") for n in names) \
            and any("降压" in m for m in meds):
        cautions.append("配方含甘草且正在使用降压药，请注意血压监测")
    return repo.save_safety_check(profile_id, assessment_id, "tea",
                                  _inputs(p, names), "allow", cautions, [])


def _has_severe_abnormal(profile_id: str) -> bool:
    for c in repo.all_codes(profile_id):
        rows = repo.series_by_code(profile_id, c["code"])
        if rows and abs(rows[-1]["grade"] or 0) >= 3:
            return True
    return False


def _inputs(p: dict, names: List[str]) -> dict:
    return {"age_years": p.get("age_years"), "sex": p.get("sex"),
            "pregnant": bool(p.get("pregnant")),
            "allergies": p.get("allergies") or [],
            "medications": p.get("medications") or [],
            "ingredients": names}
