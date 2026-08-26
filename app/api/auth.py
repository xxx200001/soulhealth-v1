"""认证接口：登录 / 注册 / 当前用户。复用第一套的标准库鉴权实现。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth
from .. import repository as repo
from ..deps import current_user

router = APIRouter(prefix="/auth", tags=["认证"])


class Credentials(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=6, max_length=80)
    display_name: str | None = None


def _public(u: dict) -> dict:
    return {"id": u["id"], "username": u["username"], "role": u["role"],
            "display_name": u.get("display_name")}


@router.post("/register")
def register(body: Credentials):
    if repo.get_user_by_name(body.username):
        raise HTTPException(409, "用户名已存在")
    role = "admin" if repo.count_users() == 0 else "user"
    u = repo.create_user(body.username, auth.hash_password(body.password),
                         role, body.display_name)
    return {"token": auth.create_token(u["id"], u["username"], u["role"]),
            "user": _public(u)}


@router.post("/login")
def login(body: Credentials):
    u = repo.get_user_by_name(body.username)
    if u is None or not auth.verify_password(body.password, u["password_hash"]):
        raise HTTPException(401, "用户名或密码不正确")
    if u.get("disabled"):
        raise HTTPException(401, "账号已停用")
    return {"token": auth.create_token(u["id"], u["username"], u["role"]),
            "user": _public(u)}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"user": _public(user)}
