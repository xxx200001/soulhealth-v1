"""SOULHEALTH V1 全局配置：路径、环境变量、运行模式判定。

融合说明
--------
本文件延续第一套 Demo（SoulHealth）的"唯一配置入口"原则；
第二套 Demo（DRP 预测平台）的参考区间/校验规则总表迁入 configs/indicators.yaml，
由 standardize.registry 加载。按《产品方案说明书 V1.2》：
  - 中医知识库、舌面诊、生物计算相关配置整体移出 V1；
  - 1Y/3Y/5Y 概率模型不再加载，风险表达改为规则分层（engine/assessment.py）。

运行模式语义（真实优先）
- LLM_MODE:
    real          配置了 ANTHROPIC_API_KEY → 图片抽取 / 健康问询 / 通俗解释走真实模型；
    mock          显式 SOULHEALTH_MOCK=1   → 使用离线演示样例（演示稳定性要求，见规格书 §12）；
    unconfigured  两者皆无 → 相关接口返回明确配置指引，绝不悄悄给假答案。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
SAMPLE_DIR = DATA_DIR / "samples"
DB_PATH = DATA_DIR / "soulhealth.db"
INDICATORS_YAML = BASE_DIR / "configs" / "indicators.yaml"
WEB_DIST = BASE_DIR / "web" / "dist"

for _d in (DATA_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

VERSION = "1.0.0"


def _load_dotenv() -> None:
    """极简 .env 加载（不覆盖已有环境变量）。"""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

# ---------------------------------------------------------------- 服务端口
HOST: str = os.getenv("SOULHEALTH_HOST", "0.0.0.0").strip()
PORT: int = int(os.getenv("SOULHEALTH_PORT", "8001"))

# ---------------------------------------------------------------- 大模型
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL",
                                    "https://api.anthropic.com").strip()
LLM_MODEL: str = (os.getenv("SOULHEALTH_LLM_MODEL")
                  or os.getenv("VISION_MODEL")
                  or os.getenv("LLM_MODEL")
                  or "claude-sonnet-5").strip()

# 备用通道 (OpenAI 兼容协议)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL",
                                 "https://api.openai.com/v1").strip()
OPENAI_MODEL: str = (os.getenv("OPENAI_VISION_MODEL")
                     or os.getenv("OPENAI_LLM_MODEL")
                     or os.getenv("LLM_MODEL")
                     or "claude-sonnet-5").strip()

MOCK_MODE: bool = os.getenv("SOULHEALTH_MOCK", "").strip() == "1"
LLM_MODE: str = "mock" if MOCK_MODE else ("real" if (ANTHROPIC_API_KEY or OPENAI_API_KEY) else "unconfigured")

OCR_ENGINE: str = os.getenv("SOULHEALTH_OCR_ENGINE", "vision_llm").strip() or "vision_llm"

# LLM 上下文与成本控制（规格书 §8）
AGENT_CONTEXT_MAX_OBS: int = int(os.getenv("SOULHEALTH_AGENT_MAX_OBS", "24"))
AGENT_CONTEXT_MAX_EVENTS: int = int(os.getenv("SOULHEALTH_AGENT_MAX_EVENTS", "10"))
AGENT_MAX_FOLLOWUPS: int = int(os.getenv("SOULHEALTH_AGENT_MAX_FOLLOWUPS", "2"))

# ---------------------------------------------------------------- 鉴权
SECRET_KEY: str = os.getenv("SOULHEALTH_SECRET", "dev-secret-change-me").strip()
TOKEN_TTL_HOURS: int = int(os.getenv("SOULHEALTH_TOKEN_TTL_HOURS", "72"))

# ---------------------------------------------------------------- 展示
APP_NAME = "SOULHEALTH"
DISCLAIMER = ("本内容为健康管理信息服务，不构成医疗诊断或处方；"
              "如有不适或指标显著异常，请及时就医并咨询专业人员。")


def runtime_info() -> dict:
    return {
        "version": VERSION,
        "llm_mode": LLM_MODE,
        "llm_model": LLM_MODEL if LLM_MODE == "real" else None,
        "ocr_engine": OCR_ENGINE,
        "mock": MOCK_MODE,
    }
