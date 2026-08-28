"""LLM 薄封装 —— 全系统唯一的模型调用出口（规格书 §8：前端不得直连模型密钥）。

职责边界（规格书 §7）：LLM 只负责自然语言理解、必要追问表达与通俗解释；
医学事实、趋势、分级、食材与克数一律来自规则/知识层，模型不可自由编造。
不可用（unconfigured/mock）时返回 None，调用方必须准备确定性降级路径。
"""
from __future__ import annotations

import time
from typing import Optional

from .. import config


def available() -> bool:
    return config.LLM_MODE == "real" and bool(config.ANTHROPIC_API_KEY or config.OPENAI_API_KEY)


def chat(system: str, messages: list[dict], max_tokens: int = 1000) -> Optional[str]:
    """多轮对话补全。支持完整上下文历史，优先 Anthropic，失败自动切换 OpenAI 协议。"""
    if not available() or not messages:
        return None

    # 清理并规范化 messages 格式，确保只包含 role (user/assistant) 和 content (str)
    formatted = []
    for m in messages:
        role = "assistant" if m.get("role") in ("assistant", "ai") else "user"
        content = str(m.get("content") or "").strip()
        if content:
            formatted.append({"role": role, "content": content})

    if not formatted:
        return None

    # 1. 优先尝试 Anthropic Claude 协议
    if config.ANTHROPIC_API_KEY:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY,
                                     base_url=config.ANTHROPIC_BASE_URL,
                                     timeout=15.0)
        candidate_models = [config.LLM_MODEL]
        for m in ("claude-sonnet-4-6", "claude-sonnet-5"):
            if m not in candidate_models:
                candidate_models.append(m)

        for model_name in candidate_models:
            try:
                resp = client.messages.create(
                    model=model_name, max_tokens=max_tokens, system=system,
                    messages=formatted)
                text = "".join(b.text for b in resp.content
                               if getattr(b, "type", "") == "text").strip()
                if text:
                    return text
            except Exception as exc:
                err_str = str(exc)
                if any(k in err_str for k in ("429", "400", "502", "503", "token负载", "暂时不可用")):
                    time.sleep(1.0)
                    continue
                print(f"[LLM] 主通道 (Anthropic - {model_name}) 调用失败: {exc}")

    # 2. 备选尝试 OpenAI 兼容协议 (DeepSeek / FluAPI 等)
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
                    *formatted,
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
                    return content
        except Exception as exc:
            print(f"[LLM] 备用通道 (OpenAI) 调用失败: {exc}")

    return None


def complete(system: str, user: str, max_tokens: int = 900) -> Optional[str]:
    """单轮补全。"""
    return chat(system=system, messages=[{"role": "user", "content": user}], max_tokens=max_tokens)

