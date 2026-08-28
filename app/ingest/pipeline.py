"""摄取管线：文件 → 视觉抽取 → 脱敏 → 指标标准化 → 状态落库。

两套 Demo 在此汇合：
  - 抽取引擎来自第一套（vision_llm：图片/PDF → 结构化 JSON，MOCK 可离线演示）；
  - 标准化来自第二套（lexicon 三层容错匹配 + registry 单位换算与分级）。

Report 状态机（规格书 §10.1）：
  uploaded → processing → needs_confirmation / ready / failed
  - 低置信关键数值不得静默当作确定值（F-UP-05）：needs_confirm=1，
    对应报告整体进入 needs_confirmation，用户确认后转 ready；
  - 日期优先取报告内检查/检验日期（F-UP-03）；抽取不到时暂以上传日期占位
    且 date_confirmed=0，前端要求用户确认，医学趋势只用已确认日期；
  - 疑似重复（同日期+同类型）只提示不删除（F-UP-06）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .. import config
from .. import repository as repo
from ..standardize.lexicon import get_lexicon
from ..standardize.registry import get_registry, grade_from_ref, grade_value
from . import deid
from .vision_llm import ExtractionError, extract_from_file

# 抽取置信度低于该值的观测进入"需要确认"（词典 fuzzy 命中 0.85 恰在线上）
_CONFIRM_BELOW = 0.9


def process_report(report_id: str) -> dict:
    """处理一份已登记的报告。同一报告重复调用是幂等的：
    ready 状态直接返回已有结果，不重复 OCR（规格书 §8 成本控制）。"""
    rpt = repo.get_report(report_id)
    if rpt is None:
        raise ValueError(f"报告不存在: {report_id}")
    if rpt["status"] == "ready":
        return rpt
    repo.set_report_status(report_id, "processing")

    try:
        extraction = extract_from_file(Path(rpt["stored_path"]),
                                       rpt.get("report_type"))
    except ExtractionError as exc:
        repo.set_report_status(report_id, "failed", error=str(exc))
        return repo.get_report(report_id)
    except Exception as exc:  # 不可预期错误也要落到状态机，禁止悄悄丢单
        repo.set_report_status(report_id, "failed", error=f"抽取失败：{exc}")
        return repo.get_report(report_id)

    extraction = deid.scrub_extraction(extraction)
    ext = extraction.to_dict()

    # ---- 报告日期：优先报告内日期；缺失以上传日期占位并要求确认 ----
    report_date = ext.get("exam_date")
    date_confirmed = 1 if report_date else 0
    if not report_date:
        report_date = (rpt["upload_time"] or "")[:10]

    profile = repo.get_profile(rpt["profile_id"]) or {}
    sex = {"female": "F", "male": "M"}.get(profile.get("sex"), "U")
    age = profile.get("age_years")

    registry = get_registry()
    lexicon = get_lexicon()

    n_obs = n_matched = n_low = 0
    for o in ext.get("observations") or []:
        raw_name = o.get("display") or o.get("code") or ""
        match = lexicon.lookup(o.get("code") or raw_name)
        if not match.matched and raw_name:
            match = lexicon.lookup(raw_name)

        raw_val = o.get("value_num")
        value_num = None
        if raw_val is not None and str(raw_val).strip() != "":
            try:
                value_num = float(raw_val)
            except (ValueError, TypeError):
                value_num = None

        unit = o.get("unit")
        canonical_value = canonical_unit = None
        grade = 0
        code = (o.get("code") or "").upper() or None
        method = "passthrough"
        confidence = 1.0

        if match.matched:
            code = match.code
            method = match.method
            confidence = match.confidence
            meta = registry.get(code)
            if meta and value_num is not None:
                cv = meta.convert_to_canonical(value_num, unit)
                # 量级自动纠错（迁移自第二套：magnitude_fix）
                if cv is not None and not meta.is_plausible(cv) and meta.magnitude_fix:
                    for f in (0.001, 1000.0):
                        if meta.is_plausible(cv * f):
                            cv, confidence = cv * f, min(confidence, 0.8)
                            break
                if cv is not None and meta.is_plausible(cv):
                    canonical_value = cv
                    canonical_unit = meta.canonical_unit
                    grade = grade_value(meta, cv, sex=sex, age=age)
                elif cv is not None:
                    confidence = 0.0  # 超生理极限：拒绝入趋势，仅原样留档
        elif value_num is not None:
            # 未标准化：以报告自带参考范围兜底分级，仍可展示但不进跨报告比较
            grade = grade_from_ref(value_num, o.get("ref_low"),
                                   o.get("ref_high"))

        needs_confirm = 1 if (0 < confidence < _CONFIRM_BELOW) else 0
        if confidence == 0.0:
            needs_confirm = 1
        n_obs += 1
        n_matched += 1 if match.matched else 0
        n_low += needs_confirm

        repo.add_observation(
            rpt["profile_id"], report_id, report_date,
            code=code, original_name=raw_name or code,
            value_num=value_num, value_text=o.get("value_text"), unit=unit,
            canonical_value=canonical_value, canonical_unit=canonical_unit,
            ref_low=o.get("ref_low"), ref_high=o.get("ref_high"),
            flag=o.get("abnormal_flag"), grade=grade,
            match_method=method, confidence=confidence,
            needs_confirm=needs_confirm)

    n_findings = 0
    for f in ext.get("findings") or []:
        repo.add_finding(rpt["profile_id"], report_id, f.get("organ", ""),
                         f.get("description", ""), f.get("flags") or [],
                         report_date)
        n_findings += 1
    for imp in ext.get("impressions") or []:
        repo.add_finding(rpt["profile_id"], report_id, "检查提示", imp,
                         ["impression"], report_date)
        n_findings += 1

    dup = repo.find_duplicate(rpt["profile_id"], ext.get("exam_date"),
                              ext.get("document_type"), report_id)

    status = "needs_confirmation" if (n_low > 0 or not date_confirmed) else "ready"
    repo.set_report_status(
        report_id, status,
        report_type=ext.get("document_type"),
        report_date=report_date, date_confirmed=date_confirmed,
        engine=extraction.engine or config.OCR_ENGINE,
        extraction=ext,
        stats={"observations": n_obs, "matched": n_matched,
               "low_confidence": n_low, "findings": n_findings},
        duplicate_of=dup)
    return repo.get_report(report_id)


def confirm_report(report_id: str, report_date: Optional[str] = None,
                   confirmations: Optional[list] = None) -> dict:
    """用户确认低置信项 / 报告日期后，报告转 ready（AC-05）。

    confirmations: [{observation_id, value_num?}]，仅确认列出的项；
    未确认项保持 needs_confirm，不进入关键分析（§10.1）。
    """
    rpt = repo.get_report(report_id)
    if rpt is None:
        raise ValueError(f"报告不存在: {report_id}")
    if report_date:
        repo.set_report_status(report_id, rpt["status"],
                               report_date=report_date, date_confirmed=1)
        # 同步该报告全部观测的真实检查日期
        for o in repo.list_observations_by_report(report_id):
            repo._c().execute("UPDATE observations SET observed_at=? WHERE id=?",
                              (report_date, o["id"]))
        repo._c().commit()
    for c in confirmations or []:
        repo.confirm_observation(c["observation_id"], c.get("value_num"))

    rpt = repo.get_report(report_id)
    remaining = [o for o in repo.list_observations_by_report(report_id)
                 if o["needs_confirm"] and not o["confirmed"]]
    if not remaining and rpt.get("date_confirmed"):
        repo.set_report_status(report_id, "ready")
    return repo.get_report(report_id)


def batch_summary(report_ids: list) -> dict:
    """本次处理总账（F-UP-07 / AC-02）：份数、成功、待确认、失败、
    覆盖时间、提取指标数、可历史比较指标数。"""
    reports = [repo.get_report(rid) for rid in report_ids]
    reports = [r for r in reports if r]
    ok = [r for r in reports if r["status"] == "ready"]
    pending = [r for r in reports if r["status"] == "needs_confirmation"]
    failed = [r for r in reports if r["status"] == "failed"]
    dates = sorted(r["report_date"] for r in reports if r.get("report_date"))
    total_obs = sum((r.get("stats") or {}).get("observations", 0) for r in reports)
    comparable = 0
    if reports:
        codes = repo.all_codes(reports[0]["profile_id"])
        comparable = sum(1 for c in codes if c["n"] >= 2)
    return {
        "total": len(reports), "ready": len(ok),
        "needs_confirmation": len(pending), "failed": len(failed),
        "date_span": [dates[0], dates[-1]] if dates else None,
        "observations": total_obs, "comparable_codes": comparable,
        "reports": [{"id": r["id"], "status": r["status"],
                     "source_filename": r["source_filename"],
                     "report_date": r.get("report_date"),
                     "date_confirmed": bool(r.get("date_confirmed")),
                     "report_type": r.get("report_type"),
                     "error": r.get("error"),
                     "duplicate_of": r.get("duplicate_of"),
                     "stats": r.get("stats") or {}} for r in reports],
    }
