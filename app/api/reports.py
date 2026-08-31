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
    for rid in rids:
        pipeline.process_report(rid)
    return pipeline.batch_summary(rids)


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
    conn = repo._c()
    conn.execute("DELETE FROM observations WHERE report_id=?", (rid,))
    conn.execute("DELETE FROM findings WHERE report_id=?", (rid,))
    conn.execute("DELETE FROM reports WHERE id=?", (rid,))
    conn.commit()
    p = Path(r.get("stored_path") or "")
    if p.exists():
        p.unlink()
    return {"deleted": rid}
