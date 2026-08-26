"""食补引擎 —— 把健康管理目标转化为"今天怎么吃"（方案书 §10 / F-DIET）。

决策链：assessment.goal_tags → 各目标食物池合并 → 冲突消解 → 菜谱挑选。
冲突消解规则（确定性）：同一食材在多个目标出现时取更严格池——
  avoid > limit > allowed > recommended
（例：尿酸目标把海鲜列 avoid，即使血脂目标推荐深海鱼，也按 avoid 呈现，
并保留原因说明，用户能看懂"为什么这里不同"。）
"""
from __future__ import annotations

from typing import Dict, List

from .. import repository as repo
from .knowledge import FOOD_POOLS, GOALS, RECIPES

_POOL_ORDER = ("avoid", "limit", "allowed", "recommended")   # 严格 → 宽松


def generate(profile_id: str, assessment: dict) -> dict:
    """按一次分析结果生成新版本食补方案（旧版自动标记 superseded，仍可追溯）。"""
    tags = _goal_tags(assessment)
    goals = [{"tag": t, "label": GOALS[t]["label"], "why": GOALS[t]["why"]}
             for t in tags]

    merged: Dict[str, list] = {k: [] for k in
                               ("recommended", "allowed", "limit", "avoid")}
    placed: Dict[str, str] = {}   # 食材名 → 已落入的池
    for pool in _POOL_ORDER:      # 先放严格池，宽松池遇到同名即让位
        for tag in tags:
            for item in FOOD_POOLS.get(tag, {}).get(pool, []):
                name = item["name"]
                if name in placed:
                    continue
                placed[name] = pool
                merged[pool].append({**item, "goal": GOALS[tag]["label"]})

    recipes: List[dict] = []
    for tag in tags:
        for rc in RECIPES.get(tag, [])[:2]:
            recipes.append({**rc, "goal_tag": tag})
    if not recipes:
        recipes = [dict(rc, goal_tag="general_balance")
                   for rc in RECIPES["general_balance"]]

    return repo.save_diet_plan(profile_id, assessment["id"], goals,
                               merged, recipes)


def _goal_tags(assessment: dict) -> List[str]:
    tags: List[str] = []
    for it in assessment.get("issues") or []:
        for t in it.get("goal_tags") or []:
            if t not in tags:
                tags.append(t)
    return tags[:3] or ["general_balance"]
