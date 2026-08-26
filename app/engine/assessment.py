"""健康分析引擎 —— TOP 问题识别、优先级排序与风险分层。

替代关系（方案书 §7）：第二套 Demo 的 1Y/3Y/5Y LightGBM/Cox 概率预测
**不再作为核心输出**（F-AN-08 / AC-11）；改为基于其标准化层（分级 + RCV
趋势）的规则分层，每个等级都有可追溯依据（F-AN-04）。

评分与排序完全确定性、可复现（F-AN-02 / §7"排序结果需可解释"）：
  单项异常分   |grade| × 2
  连续异常加分  末尾连续异常 ≥2 次 +2、≥3 次 +3
  真实恶化加分  RCV 判定的持续上升/下降（朝坏方向）+2；本次较上次分级加重 +1
  危急值        +6 且等级直接 priority
  检查所见      命中问题组关键词（如"脂肪肝"）每条 +2（封顶 +4）

等级映射：0 → stable｜1–3 → mild｜4–7 → watch｜≥8 → priority
（相对稳定 / 轻度关注 / 需要留意 / 重点关注）

缓存复用（AC-19 / §8）：input_snapshot 哈希未变化时直接返回已完成分析。
"""
from __future__ import annotations

from typing import List, Optional

from .. import repository as repo
from ..standardize.registry import GRADE_LABELS, get_registry
from ..standardize.trends import (SeriesInsight, SeriesPoint, analyze_series,
                                  trend_phrase)

LEVELS = ("stable", "mild", "watch", "priority")
LEVEL_CN = {"stable": "相对稳定", "mild": "轻度关注",
            "watch": "需要留意", "priority": "重点关注"}

# 问题组定义：codes 参与评分；low_bad 表示"偏低才是坏方向"的指标
ISSUE_GROUPS: List[dict] = [
    {"key": "liver", "title": "肝功能", "goal": "liver_care",
     "codes": ["ALT", "AST", "GGT", "ALP", "TBIL", "DBIL"],
     "finding_kw": ["脂肪肝", "肝内", "肝脏", "肝区"],
     "meaning": "转氨酶等肝功能指标反映肝细胞当前的负担与损伤程度。持续偏高最常见的"
                "背景是脂肪肝、饮酒、药物或病毒等因素叠加，多数在早期通过生活方式"
                "调整可以明显改善。",
     "future": "若饮酒、高油高糖饮食与久坐等因素持续，指标进一步上升的可能性较大；"
               "反之在戒酒、控制体重后，多数人 8–12 周内可见回落。",
     "actions": ["严格戒酒，避免不必要的药物与保健品叠加",
                 "按食补方案调整饮食结构，控制晚餐油脂",
                 "每周 ≥150 分钟中等强度运动，优先快走/游泳",
                 "6–8 周后复查肝功能；如伴乏力、眼黄、尿色加深请尽早就医"]},
    {"key": "lipid", "title": "血脂", "goal": "lipid_care",
     "codes": ["TC", "TG", "LDLC", "HDLC"], "low_bad": ["HDLC"],
     "finding_kw": ["动脉", "斑块", "内膜"],
     "meaning": "血脂谱反映血液中胆固醇与甘油三酯的水平，长期偏高与动脉粥样硬化"
                "风险相关，是可以通过饮食与运动显著改变的指标。",
     "future": "维持当前饮食结构时血脂多呈缓慢上行；减少饱和脂肪与精制糖后，"
               "甘油三酯通常 4–8 周即可见变化，胆固醇改变相对更慢。",
     "actions": ["减少红肉/油炸/反式脂肪，每周 2 次深海鱼",
                 "主食一半换全谷杂豆，增加可溶性纤维",
                 "规律有氧运动并控制腰围",
                 "8–12 周复查血脂四项；如既往有心脑血管病史请遵医嘱评估"]},
    {"key": "glucose", "title": "血糖", "goal": "glucose_care",
     "codes": ["GLU", "HBA1C", "INS"],
     "finding_kw": ["胰腺", "胰岛"],
     "meaning": "空腹血糖与糖化血红蛋白共同反映血糖控制情况：前者是当下的快照，"
                "后者是过去 2–3 个月的平均水平。",
     "future": "若主食精制、含糖饮料与久坐持续，指标趋势多为缓慢上行；"
               "早期通过饮食顺序调整与运动干预，逆转空间较大。",
     "actions": ["先菜后饭、每餐蔬菜打底，戒含糖饮料",
                 "主食一半换低升糖全谷杂豆",
                 "餐后散步 15–20 分钟",
                 "3 个月复查空腹血糖与糖化；若空腹多次 ≥7.0 mmol/L 请及时就医"]},
    {"key": "uric", "title": "尿酸", "goal": "uric_care",
     "codes": ["UA"],
     "meaning": "血尿酸升高提示嘌呤代谢或排泄失衡，长期偏高与痛风发作及肾脏"
                "负担相关，饮食与饮水是最直接的可调因素。",
     "future": "继续饮酒、浓汤海鲜与含糖饮料时数值多维持高位或继续上行；"
               "限酒+足量饮水后多数人 4–8 周内可见回落。",
     "actions": ["严格限酒（尤其啤酒），戒含糖饮料",
                 "避免内脏与浓肉汤，海鲜控制频次",
                 "每日饮水 2000ml 以上（心肾功能正常前提）",
                 "如出现关节红肿热痛，属痛风发作表现，请及时就医"]},
    {"key": "kidney", "title": "肾功能", "goal": "kidney_care",
     "codes": ["CREA", "UREA", "UACR"],
     "finding_kw": ["肾", "输尿管"],
     "meaning": "肌酐、尿素与尿微量白蛋白反映肾脏滤过与屏障功能，异常时需要"
                "结合血压、血糖与用药情况综合判断。",
     "future": "肾功能指标的变化通常缓慢，关键在于控制血压血糖并避免肾毒性因素；"
               "持续异常建议由医生评估分期。",
     "actions": ["控盐（每日 <5g），慎用不明成分保健品与止痛药",
                 "同步管理血压与血糖",
                 "复查尿常规与肾功能；持续异常请肾内科就诊"]},
    {"key": "blood", "title": "血常规", "goal": "blood_care",
     "codes": ["HGB", "RBC", "WBC", "PLT"], "low_bad": ["HGB", "RBC", "PLT"],
     "meaning": "血常规反映携氧能力、免疫与凝血的基础状态；血红蛋白偏低最常见"
                "原因是铁摄入不足或慢性失血。",
     "future": "膳食铁与维生素C补充到位后，血红蛋白通常 4–8 周可见回升；"
               "若持续下降需排查失血来源。",
     "actions": ["按食补方案增加血红素铁与同餐维C",
                 "浓茶咖啡与正餐间隔 1 小时以上",
                 "4–8 周复查血常规；持续偏低或伴明显乏力请就医查因"]},
    {"key": "bp", "title": "血压", "goal": "bp_care",
     "codes": ["SBP", "DBP"],
     "meaning": "血压是心脑血管健康最重要的日常可测指标，单次偏高需要多次"
                "复测确认，持续偏高才有管理意义。",
     "future": "限盐、减重与规律运动通常可使收缩压下降 5–10 mmHg；"
               "持续偏高不干预则并发风险随时间累积。",
     "actions": ["家庭自测：每日早晚各一次、静坐 5 分钟后测量并记录",
                 "限盐 + 高钾蔬果（DASH 方向）",
                 "若多次 ≥140/90 mmHg，请就医评估是否需要进一步干预"]},
    {"key": "weight", "title": "体重与代谢", "goal": "weight_care",
     "codes": ["BMI"],
     "meaning": "BMI 反映总体能量平衡，超重是脂肪肝、血脂血糖异常共同的上游因素，"
                "也是干预收益最集中的一环。",
     "future": "每减重 5%，肝酶、血脂与血糖通常都会同步改善；不干预则相关指标"
               "多随体重缓慢上行。",
     "actions": ["以每周 0.5kg 的速度温和减重",
                 "执行食补方案中的能量结构调整",
                 "力量训练每周 2 次以保住肌肉"]},
    {"key": "inflam", "title": "炎症指标", "goal": "general_balance",
     "codes": ["CRP"],
     "meaning": "C反应蛋白是非特异性的炎症标志，轻度升高常见于近期感染、"
                "劳累或慢性炎症状态，需结合症状判断。",
     "future": "一过性升高多在诱因消除后 1–2 周回落；持续升高需要就医查因。",
     "actions": ["观察是否有感染/牙龈炎等诱因", "规律作息，2–4 周复查",
                 "持续升高或伴发热请及时就医"]},
]

_SRC_CN = {"lab_report": "检验报告", "ultrasound_report": "检查报告",
           "checkup": "体检报告", "other": "健康资料"}


# ================================================================ 入口
def run_assessment(profile_id: str, force: bool = False) -> dict:
    """创建（或复用）一次健康分析。返回 assessment 行 + issues。"""
    snap = repo.input_snapshot(profile_id)
    ihash = repo.snapshot_hash(snap)

    if not force:
        latest = repo.latest_assessment(profile_id)
        if latest and latest["input_hash"] == ihash:
            latest["issues"] = repo.list_issues(latest["id"])
            latest["cached"] = True
            return latest

    a = repo.create_assessment(profile_id, snap, ihash)
    try:
        issues = _build_issues(profile_id)
        repo.save_issues(a["id"], issues)
        counts = {lv: 0 for lv in LEVELS}
        for it in issues:
            counts[it["level"]] += 1
        top_titles = [it["title"] for it in issues if it["rank"] <= 3]
        repo.finish_assessment(a["id"], "completed",
                               {"counts": counts, "top_titles": top_titles})
    except Exception as exc:
        repo.finish_assessment(a["id"], "failed", error=str(exc))
        raise
    out = repo.get_assessment(a["id"])
    out["issues"] = repo.list_issues(a["id"])
    out["cached"] = False
    return out


# ================================================================ 问题构建
def _build_issues(profile_id: str) -> List[dict]:
    registry = get_registry()
    findings = repo.list_findings(profile_id)
    codes_present = {c["code"] for c in repo.all_codes(profile_id) if c["code"]}

    scored: List[dict] = []
    for grp in ISSUE_GROUPS:
        insights: dict[str, SeriesInsight] = {}
        for code in grp["codes"]:
            if code not in codes_present:
                continue
            rows = repo.series_by_code(profile_id, code)
            pts = [SeriesPoint(value=r["value"], date=r["observed_at"],
                               report_id=r["report_id"], grade=r["grade"] or 0,
                               unit=r["unit"]) for r in rows]
            ins = analyze_series(code, pts, registry.get(code))
            if ins:
                insights[code] = ins
        grp_findings = [f for f in findings
                        if any(kw in (f["organ"] + f["description"])
                               for kw in grp.get("finding_kw", []))]
        if not insights and not grp_findings:
            continue
        score, why_parts, critical = _score_group(grp, insights, grp_findings,
                                                  registry)
        level = _level_of(score, critical)
        scored.append(_compose_issue(grp, insights, grp_findings, score,
                                     level, why_parts, registry))

    scored.sort(key=lambda x: (-x["score"], x["title"]))
    rank = 1
    for it in scored:
        if it["level"] != "stable" and rank <= 3:
            it["rank"] = rank
            rank += 1
        else:
            it["rank"] = 100 + scored.index(it)   # 折叠展示区（F-AN 相对稳定项）
    return scored


def _bad_direction(grp: dict, code: str) -> str:
    return "下降" if code in grp.get("low_bad", []) else "上升"


def _score_group(grp, insights, grp_findings, registry):
    score = 0.0
    why: List[str] = []
    critical = False
    for code, ins in insights.items():
        meta = registry.get(code)
        name = meta.name_cn if meta else code
        g = ins.latest.grade
        if g != 0:
            score += abs(g) * 2
            why.append(f"{name}当前{GRADE_LABELS.get(g, '')}"
                       f"（{ins.latest.value:g}{ins.latest.unit or ''}，"
                       f"{ins.latest.date}）")
        if ins.abnormal_streak >= 3:
            score += 3
            why.append(f"{name}已连续 {ins.abnormal_streak} 次记录异常")
        elif ins.abnormal_streak >= 2:
            score += 2
            why.append(f"{name}连续 {ins.abnormal_streak} 次记录异常")
        bad = _bad_direction(grp, code)
        if ins.persistent_direction == f"持续{bad}":
            score += 2
            why.append(f"{name}多次记录呈{ins.persistent_direction}")
        c = ins.compare
        if c and c.is_real_change and c.worsened and c.direction == bad:
            score += 1
        if meta and meta.is_critical(ins.latest.value):
            score += 6
            critical = True
            why.append(f"{name}达到危急值水平，请优先就医复核")
    if grp_findings:
        add = min(4, 2 * len(grp_findings))
        score += add
        why.append("检查报告存在相关所见："
                   + "；".join(f["description"][:24] for f in grp_findings[:2]))
    return score, why, critical


def _level_of(score: float, critical: bool) -> str:
    if critical:
        return "priority"
    if score >= 8:
        return "priority"
    if score >= 4:
        return "watch"
    if score >= 1:
        return "mild"
    return "stable"


def _compose_issue(grp, insights, grp_findings, score, level, why_parts,
                   registry) -> dict:
    # 证据：每条可回溯 report_id + 真实日期 + 来源标签（F-AN-06 / AC-09）
    evidence: List[dict] = []
    for code, ins in insights.items():
        meta = registry.get(code)
        for p in ins.points[-4:]:
            src = _source_of(p.report_id)
            evidence.append({"code": code,
                             "name": meta.name_cn if meta else code,
                             "value": p.value, "unit": p.unit or "",
                             "date": p.date, "grade": p.grade,
                             "report_id": p.report_id, "source": src})
    for f in grp_findings[:3]:
        evidence.append({"code": "finding", "name": f["organ"],
                         "value": None, "unit": "", "date": f["observed_at"],
                         "grade": 0, "report_id": f.get("report_id"),
                         "source": _source_of(f.get("report_id")),
                         "text": f["description"]})

    # 发现了什么：最新异常事实
    found = []
    for code, ins in insights.items():
        meta = registry.get(code)
        name = meta.name_cn if meta else code
        g = ins.latest.grade
        if g != 0:
            found.append(f"{name} {ins.latest.value:g}{ins.latest.unit or ''}"
                         f"（{GRADE_LABELS.get(g, '')}，{ins.latest.date}）")
    for f in grp_findings[:2]:
        found.append(f"{f['organ']}：{f['description']}（{f['observed_at']}）")
    if not found:
        found.append("该组指标当前均在参考范围内")

    # 过去怎么变化：趋势短语 + 本次VS上次（两个具体日期，AC-10）
    history = []
    compare_cards = []
    for code, ins in insights.items():
        meta = registry.get(code)
        name = meta.name_cn if meta else code
        if len(ins.points) >= 2:
            history.append(trend_phrase(ins, name, ins.latest.unit or ""))
            if ins.compare:
                compare_cards.append({"code": code, "name": name,
                                      **ins.compare.to_dict(),
                                      "unit": ins.latest.unit or ""})
    if not history:
        history.append("历史记录不足两次，暂无法进行纵向比较；"
                       "补充既往报告后趋势会自动更新")

    gaps = _gaps_of(grp, insights)
    top_abnormal = [c for c, i in insights.items() if i.latest.grade != 0]
    summary = _summary_line(grp, insights, registry)

    return {
        "rank": 999, "title": grp["title"], "level": level,
        "score": round(score, 1), "summary": summary,
        "goal_tags": [grp["goal"]] if level != "stable" else [],
        "evidence": evidence,
        "detail": {
            "found": found,
            "history": history,
            "compare": compare_cards,
            "why_priority": why_parts or ["该组当前无明显异常，仅作常规展示"],
            "meaning": grp["meaning"],
            "future": grp["future"] + "（以上为条件式趋势说明，不构成对疾病结局的预测）",
            "gaps": gaps,
            "actions": grp["actions"],
            "codes_abnormal": top_abnormal,
        },
    }


def _summary_line(grp, insights, registry) -> str:
    abnormal = [(c, i) for c, i in insights.items() if i.latest.grade != 0]
    if not abnormal:
        return "当前记录均在参考范围内"
    parts = []
    for code, ins in abnormal[:2]:
        meta = registry.get(code)
        name = meta.name_cn if meta else code
        tag = f"，{ins.persistent_direction}" if ins.persistent_direction else ""
        parts.append(f"{name} {ins.latest.value:g}{ins.latest.unit or ''}{tag}")
    more = f" 等 {len(abnormal)} 项" if len(abnormal) > 2 else ""
    return "；".join(parts) + more


def _gaps_of(grp, insights) -> List[str]:
    gaps = []
    single = [c for c, i in insights.items() if len(i.points) < 2]
    if single:
        gaps.append("以下指标只有单次记录，补充历史报告可判断是偶发还是持续："
                    + "、".join(single))
    missing = [c for c in grp["codes"] if c not in insights]
    if missing:
        gaps.append("本组还可关注但档案中暂无记录的指标：" + "、".join(missing[:4]))
    if not gaps:
        gaps.append("当前信息基本完整，按建议周期复查即可")
    return gaps


def _source_of(report_id: Optional[str]) -> str:
    if not report_id:
        return "历史记录"
    r = repo.get_report(report_id)
    if r is None:
        return "历史记录"
    return _SRC_CN.get(r.get("report_type") or "other", "健康资料")
