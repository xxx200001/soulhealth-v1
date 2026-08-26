"""SOULHEALTH V1 启动入口：初始化数据库 → 预热注册表 → （可选）播种演示 → 起服务。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import config  # noqa: E402
from app import repository as repo  # noqa: E402
from app.standardize.lexicon import get_lexicon  # noqa: E402


def main() -> None:
    repo.init()
    lex = get_lexicon()
    print(f"[SOULHEALTH] 指标注册表就绪：{len(lex.registry)} 项标准化指标")
    print(f"[SOULHEALTH] LLM 模式：{config.LLM_MODE}"
          + ("（离线演示样例）" if config.MOCK_MODE else ""))
    if os.getenv("SOULHEALTH_SEED_DEMO", "1") == "1":
        from app.demo import seed
        info = seed()
        print(f"[SOULHEALTH] 演示账号 demo/demo123456，档案 {info['profile_id']}")
    import uvicorn
    print(f"[SOULHEALTH] http://localhost:{config.PORT}  "
          f"(接口文档 /docs)")
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()
