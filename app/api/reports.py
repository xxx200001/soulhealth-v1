"""报告接口：多文件上传 / 逐份状态 / 低置信确认 / 原件访问（F-UP 全组）。"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import (APIRouter, Depends, File, Form, HTTPException,
                     UploadFile)
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import config
from .. import repository as repo
from ..deps import current_user, scoped_profile, scoped_report
from ..ingest import pipeline
from ..ingest.vision_llm import get_progress, clear_progress
import threading

router = APIRouter(prefix="/reports", tags=["健康资料"])


@router.post("/upload")
def upload(profile_id: str = Form(...),
           files: list[UploadFile] = File(...),
           user: dict = Depends(current_user)):
    """一次多份上传（AC-02）：每份独立 report 记录，同步处理并返回总账。
    原件先落盘再处理（F-UP-02），处理失败原件仍在，可重试。"""
    scoped_profile(profile_id, user)
    if not files:
        raise HTTPException(422, "请至少选择一份文件")
    if len(files) > config.MAX_UPLOAD_BATCH:
        raise HTTPException(
            422, f"一次最多上传 {config.MAX_UPLOAD_BATCH} 份"
                 f"（本次收到 {len(files)} 份），请分批上传")
    rids: list[str] = []
    for f in files:
        safe = f"{uuid.uuid4().hex[:8]}_{Path(f.filename or 'file').name}"
        dest = config.UPLOAD_DIR / safe
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        r = repo.create_report(profile_id, f.filename, str(dest))
        rids.append(r["id"])

    def _process_bg():
        for rid in rids:
            try:
                pipeline.process_report(rid)
            except Exception as exc:
                print(f"[Upload] Background process error for {rid}: {exc}")
            finally:
                clear_progress(rid)

    thread = threading.Thread(target=_process_bg, daemon=True)
    thread.start()

    # Return immediately with report IDs in 'uploaded' status
    reports = []
    for rid in rids:
        rpt = repo.get_report(rid)
        if rpt:
            reports.append(rpt)
    return {
        "total": len(rids),
        "ready": 0,
        "needs_confirmation": 0,
        "failed": 0,
        "observations": 0,
        "comparable_codes": 0,
        "date_span": None,
        "reports": reports,
        "async": True,
    }


@router.get("/progress/{rid}")
def progress(rid: str):
    """查询报告处理进度（PDF 逐页进度）。"""
    p = get_progress(rid)
    if p:
        return p
    # No active progress - check DB for final status
    rpt = repo.get_report(rid)
    if rpt and rpt['status'] in ('ready', 'needs_confirmation'):
        return {'page': 0, 'total': 0, 'stage': 'done', 'pct': 100}
    if rpt and rpt['status'] == 'failed':
        return {'page': 0, 'total': 0, 'stage': 'failed', 'pct': 100,
                'error': rpt.get('error', '')}
    return {'page': 0, 'total': 0, 'stage': 'waiting', 'pct': 0}


@router.get("")
def list_reports(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    return {"items": repo.list_reports(profile_id)}


@router.get("/{rid}")
def get_report(rid: str, user: dict = Depends(current_user)):
    r = scoped_report(rid, user)
    r["observations"] = repo.list_observations_by_report(rid)
    r["findings"] = repo.list_findings_by_report(rid)
    return r


@router.post("/{rid}/retry")
def retry(rid: str, user: dict = Depends(current_user)):
    r = scoped_report(rid, user)
    if r["status"] not in ("failed", "uploaded"):
        raise HTTPException(409, f"当前状态 {r['status']} 无需重试")
    repo.set_report_status(rid, "uploaded", error="")
    try:
        return pipeline.process_report(rid)
    except HTTPException:
        raise
    except Exception as exc:
        repo.set_report_status(rid, "failed", error=str(exc))
        raise HTTPException(500, f"识别处理失败：{exc}")


class Confirmation(BaseModel):
    report_date: str | None = None
    confirmations: list[dict] | None = None   # [{observation_id, value_num?}]


@router.post("/{rid}/confirm")
def confirm(rid: str, body: Confirmation,
            user: dict = Depends(current_user)):
    """确认报告日期 / 低置信数值后转 ready（F-UP-05 / AC-05）。"""
    scoped_report(rid, user)
    return pipeline.confirm_report(rid, body.report_date, body.confirmations)


@router.get("/{rid}/file")
def original_file(rid: str, user: dict = Depends(current_user)):
    """原件访问（F-UP-02 / AC-09：任一关键数据可回到原始报告）。"""
    r = scoped_report(rid, user)
    path = Path(r.get("stored_path") or "")
    if not path.exists():
        raise HTTPException(404, "原件文件缺失")
    return FileResponse(path, filename=r.get("source_filename") or path.name)


@router.delete("/{rid}")
def delete_report(rid: str, user: dict = Depends(current_user)):
    r = scoped_report(rid, user)
    profile_id = r["profile_id"]
    conn = repo._c()
    # 级联删除报告关联的所有数据
    conn.execute("DELETE FROM observations WHERE report_id=?", (rid,))
    conn.execute("DELETE FROM findings WHERE report_id=?", (rid,))
    conn.execute("DELETE FROM reports WHERE id=?", (rid,))
    
    # 检查该档案是否还有其他报告
    remaining = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE profile_id=?", (profile_id,)
    ).fetchone()[0]
    
    if remaining == 0:
        # 该档案下没有报告了，清理所有派生数据
        conn.execute("DELETE FROM assessments WHERE profile_id=?", (profile_id,))
        conn.execute("DELETE FROM health_issues WHERE profile_id=?", (profile_id,))
        conn.execute("DELETE FROM health_events WHERE profile_id=?", (profile_id,))
        conn.execute("DELETE FROM event_candidates WHERE profile_id=?", (profile_id,))
        # diet_plans / tea_plans 及其子表
        for plan_row in conn.execute(
            "SELECT id FROM diet_plans WHERE profile_id=?", (profile_id,)
        ).fetchall():
            plan_id = plan_row[0]
            conn.execute("DELETE FROM recipes WHERE plan_id=?", (plan_id,))
            conn.execute("DELETE FROM safety_checks WHERE plan_id=?", (plan_id,))
        conn.execute("DELETE FROM diet_plans WHERE profile_id=?", (profile_id,))
        conn.execute("DELETE FROM tea_plans WHERE profile_id=?", (profile_id,))
        # 对话记录
        for conv_row in conn.execute(
            "SELECT id FROM conversations WHERE profile_id=?", (profile_id,)
        ).fetchall():
            conn.execute("DELETE FROM conv_messages WHERE conversation_id=?", (conv_row[0],))
        conn.execute("DELETE FROM conversations WHERE profile_id=?", (profile_id,))
    
    conn.commit()
    p = Path(r.get("stored_path") or "")
    if p.exists():
        p.unlink()
    return {"deleted": rid, "profile_data_cleared": remaining == 0}

