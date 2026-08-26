"""请求依赖：当前登录用户、档案越权校验（规格书 §11 数据安全最低要求）。"""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from . import auth
from . import repository as repo


def current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    try:
        token = auth.extract_bearer_token(authorization)
        payload = auth.decode_token(token)
    except auth.AuthError as exc:
        raise HTTPException(401, str(exc))
    user = repo.get_user(payload["uid"])
    if user is None or user.get("disabled"):
        raise HTTPException(401, "账号不存在或已被停用，请重新登录")
    return user


def scoped_profile(pid: str, user: dict) -> dict:
    """取档案并做归属校验。所有涉及 profile_id 的接口都必须走这里。"""
    p = repo.get_profile(pid)
    if p is None:
        raise HTTPException(404, f"档案不存在: {pid}")
    if user["role"] != "admin" and p.get("owner_id") not in (None, user["id"]):
        raise HTTPException(403, "无权访问该档案")
    return p


def scoped_report(rid: str, user: dict) -> dict:
    r = repo.get_report(rid)
    if r is None:
        raise HTTPException(404, f"报告不存在: {rid}")
    scoped_profile(r["profile_id"], user)
    return r
