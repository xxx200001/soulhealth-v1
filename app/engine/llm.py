"""LLM 薄封装 —— 全系统唯一的模型调用出口（规格书 §8：前端不得直连模型密钥）。

职责边界（规格书 §7）：LLM 只负责自然语言理解、必要追问表达与通俗解释；
医学事实、趋势、分级、食材与克数一律来自规则/知识层，模型不可自由编造。
不可用（unconfigured/mock）时返回 None，调用方必须准备确定性降级路径。
"""
from __future__ import annotations

from typing import Optional

from .. import config


def available() -> bool:
    return config.LLM_MODE == "real" and bool(config.ANTHROPIC_API_KEY or config.OPENAI_API_KEY)


def complete(system: str, user: str, max_tokens: int = 900) -> Optional[str]:
    """单轮补全。支持主通道(Anthropic/刀盾)失败时自动无缝降级至备用通道(OpenAI/FluAPI)。"""
    if not available():
        return None

    # 1. 优先尝试 Anthropic Claude 协议（主通道：如刀盾）
    if config.ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY,
                                         base_url=config.ANTHROPIC_BASE_URL,
                                         timeout=15.0)
            resp = client.messages.create(
                model=config.LLM_MODEL, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}])
            text = "".join(b.text for b in resp.content
                           if getattr(b, "type", "") == "text").strip()
            if text:
                return text
        except Exception as exc:
            print(f"[LLM] 主通道 (Anthropic/刀盾) 调用失败: {exc}，正在尝试自动切换至备用通道 (OpenAI/FluAPI)...")

    # 2. 备选尝试 OpenAI 兼容协议（备用通道：如 FluAPI）
    if config.OPENAI_API_KEY:
        try:
            import json
            import urllib.request
            base = config.OPENAI_BASE_URL.rstrip("/")
            url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
            payload = {
                "model": config.OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            }
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"),
                headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"].strip()
                if content:
                    print("[LLM] 备用通道 (OpenAI/FluAPI) 调用成功！")
                    return content
        except Exception as exc:
            print(f"[LLM] 备用通道 (OpenAI/FluAPI) 调用亦失败: {exc}")

    return None

