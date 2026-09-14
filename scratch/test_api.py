# -*- coding: utf-8 -*-
"""验证 .env 配好后，项目代码能否正常调通 LLM"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config

print(f"LLM_MODE:         {config.LLM_MODE}")
print(f"ANTHROPIC_API_KEY: {config.ANTHROPIC_API_KEY[:16]}...")
print(f"ANTHROPIC_BASE_URL:{config.ANTHROPIC_BASE_URL}")
print(f"VISION_MODEL:      {config.VISION_MODEL}")
print(f"LLM_MODEL:         {config.LLM_MODEL}")
print()

from app.engine import llm
print(f"llm.available(): {llm.available()}")
print()

print("测试 llm.complete()...")
result = llm.complete("你是一个测试助手", "请回复'OK'两个字母")
print(f"回复: {result}")
print()
print("[OK] 配置正确，LLM 通道可用!" if result else "[FAIL] LLM 调用失败")
