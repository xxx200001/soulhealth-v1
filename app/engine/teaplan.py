"""药食同源茶饮引擎（方案书 §11 / F-TEA）。

流程：目标 → 知识库配方 → Safety Engine 前置检查 → 按状态输出：
  allow               输出完整方案（原料克数/水量/制作/频率/周期/依据/禁忌）
  require_info        不生成完整方案，返回缺失信息清单（AC-13）
  block               停止生成，说明拦截原因
  professional_review 停止生成，提示咨询专业人员

配方全部来自 knowledge.TEA_FORMULAS（规则可替换，F-TEA-05）；
LLM 不参与原料与克数决定。
"""
from __future__ import annotations

from typing import List

from .. import repository as repo
from .knowledge import TEA_FORMULAS, TEA_INGREDIENT_RULES
from . import safety


def generate(profile_id: str, assessment: dict) -> dict:
    """按分析目标生成茶饮方案；Safety 结果与方案一同版本化保存。"""
    tag = _primary_goal(assessment)
    formula = TEA_FORMULAS.get(tag) or TEA_FORMULAS["general_balance"]

    check = safety.check_for_tea(profile_id, assessment["id"],
                                 formula["ingredients"])
    status = check["result"]

    if status == "allow":
        plan = _full_plan(formula, check["reasons"])
    elif status == "require_info":
        plan = {"goal_tag": tag, "goal_label": formula["goal_label"],
                "name": formula["name"],
                "message": "生成完整茶饮方案前，需要先补充以下安全信息",
                "missing": check["missing"]}
    elif status == "block":
        plan = {"goal_tag": tag, "goal_label": formula["goal_label"],
                "message": "基于当前档案信息，本配方已被安全规则拦截，"
                           "不提供完整方案", "reasons": check["reasons"]}
    else:  # professional_review
        plan = {"goal_tag": tag, "goal_label": formula["goal_label"],
                "message": "当前情况建议先咨询医生或具备资质的专业人员，"
                           "暂不自动生成茶饮方案", "reasons": check["reasons"]}

    return repo.save_tea_plan(profile_id, assessment["id"], check["id"],
                              status, plan)


def _full_plan(formula: dict, cautions: List[str]) -> dict:
    ingredients = []
    for ing in formula["ingredients"]:
        rule = TEA_INGREDIENT_RULES.get(ing["name"], {})
        ingredients.append({**ing, "caution": rule.get("notes", "")})
    return {
        "goal_label": formula["goal_label"],
        "name": formula["name"],
        "ingredients": ingredients,
        "water_ml": formula["water_ml"],
        "brew": formula["brew"],
        "frequency": formula["frequency"],
        "cycle": formula["cycle"],
        "rationale": formula["rationale"],
        "contraindications": formula["contraindications"],
        "cautions": cautions,
        "note": "本茶饮为健康管理参考，不是疾病治疗处方；饮用期间如有不适请停用并咨询专业人员。",
    }


def _primary_goal(assessment: dict) -> str:
    for it in assessment.get("issues") or []:
        for t in it.get("goal_tags") or []:
            if t in TEA_FORMULAS:
                return t
    return "general_balance"
