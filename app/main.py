"""SOULHEALTH V1 —— FastAPI 装配入口。

启动：python run.py（或 uvicorn app.main:app --port 8001）
本文件只做装配：中间件、路由挂载、静态托管、启动自检。

接口总览
--------
  认证   POST /api/auth/login|register        GET /api/auth/me
  档案   GET|POST /api/profiles               GET|PATCH /api/profiles/{pid}
         GET /api/profiles/{pid}/timeline|events|candidates
         POST /api/profiles/{pid}/events|candidates/{cid}
  资料   POST /api/reports/upload（多文件）    GET /api/reports?profile_id=
         GET /api/reports/{rid}[/file]        POST /api/reports/{rid}/confirm|retry
  指标   GET /api/metrics/codes|series
  分析   POST /api/assessments/run            GET /api/assessments/latest|scope|history
         GET /api/assessments/{aid}           GET /api/assessments/issues/{iid}
  方案   POST /api/plans/diet|tea/generate    GET /api/plans/diet|tea/active|history
         GET /api/plans/recipes/{rcid}
  问询   POST /api/ask                        GET /api/ask/conversations[/{cid}]
  状态   GET /api/health
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from . import repository as repo
from .api import ask, assessments, auth, metrics, plans, profiles, reports
from .standardize.lexicon import get_lexicon
from .standardize.registry import get_registry

app = FastAPI(
    title="SOULHEALTH",
    version=config.VERSION,
    description="长期健康档案 × 报告解析 × 纵向比较 × 个体化食补与药食同源茶饮",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

for _router in (auth.router, profiles.router, reports.router, metrics.router,
                assessments.router, plans.router, ask.router):
    app.include_router(_router, prefix="/api")


@app.on_event("startup")
def _startup() -> None:
    repo.init()
    get_lexicon()   # 预热注册表与词典（一次性建索引）


@app.get("/api/health", tags=["状态"])
def health() -> dict:
    registry = get_registry()
    return {
        "status": "ok",
        **config.runtime_info(),
        "indicators": len(registry),
        "capabilities": {
            "vision_extract": config.LLM_MODE in ("real", "mock"),
            "agent_llm": config.LLM_MODE == "real",
            "standardize": True,
            "assessment": True,
            "plans": True,
        },
        "disclaimer": config.DISCLAIMER,
    }


if config.WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(config.WEB_DIST), html=True),
              name="web")
