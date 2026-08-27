"""「问问我的健康」接口：消息 / 会话 / 候选事件确认（F-AG）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import config, repository as repo
from ..deps import current_user, scoped_profile
from ..engine import agent, llm

router = APIRouter(prefix="/ask", tags=["问问我的健康"])


class AskBody(BaseModel):
    profile_id: str
    conversation_id: str | None = None
    text: str = Field(min_length=1, max_length=1000)


class GeneralAskBody(BaseModel):
    """通用健康问答（不绑定档案），首页入口使用。"""
    text: str = Field(min_length=1, max_length=1000)


@router.post("")
def ask(body: AskBody, user: dict = Depends(current_user)):
    scoped_profile(body.profile_id, user)
    return agent.handle(body.profile_id, body.conversation_id,
                        body.text.strip())


@router.post("/general")
def ask_general(body: GeneralAskBody, _user: dict = Depends(current_user)):
    """通用健康问答：不查档案、不追问槽位，直接用 LLM 回答常见健康问题。
    适用于首页入口，让用户无需任何历史数据也能获得有价值的健康指导。"""
    text = body.text.strip()

    # 红旗检测（紧急情况无论在哪个入口都要拦截）
    red = [w for w in agent._RED_FLAGS if w in text]
    if red:
        reply = agent._red_flag_reply(red)
        return {"reply": reply}

    # LLM 可用时走大模型
    system = (
        "你是一位专业、温暖的健康管理顾问。用户向你咨询日常健康问题，"
        "请用通俗易懂的中文直接回答。回答应当：\n"
        "1. 简明扼要，条理清晰，适当分段\n"
        "2. 给出具体可操作的生活建议（饮食、运动、作息等）\n"
        "3. 涉及症状时提醒就医边界（什么情况应该去看医生）\n"
        "4. 不做诊断、不开处方、不编造数据\n"
        "5. 回答末尾附一句简短的免责提示\n"
        "保持亲切专业的语气，像一位靠谱的健康顾问朋友在给建议。"
    )
    answer = llm.complete(system=system, user=text, max_tokens=800)

    # LLM 不可用时返回确定性降级回答
    if not answer:
        answer = _general_fallback(text)

    return {
        "reply": {
            "kind": "answer",
            "text": answer,
            "disclaimer": config.DISCLAIMER,
        }
    }


def _general_fallback(text: str) -> str:
    """LLM 不可用时的确定性降级：根据关键词返回结构化通用建议。"""
    # 尝试匹配症状缓解建议
    relief = agent._relief_actions(text)
    if relief:
        lines = ["根据你描述的情况，以下是一些建议：", ""]
        for tip in relief:
            lines.append(f"• {tip}")
        lines.append("")
        lines.append("💡 如果症状持续超过 3-5 天或加重，建议及时就医。")
        lines.append("")
        lines.append(f"_{config.DISCLAIMER}_")
        return "\n".join(lines)

    # 通用健康回答
    return (
        "感谢你的健康咨询！\n\n"
        "关于你的问题，以下是一些通用的健康管理建议：\n\n"
        "• **均衡饮食**：每日摄入充足的蔬果、优质蛋白和全谷物\n"
        "• **适量运动**：每周至少 150 分钟中等强度有氧运动\n"
        "• **规律作息**：保证 7-8 小时睡眠，固定起居时间\n"
        "• **定期体检**：建议每年至少一次全面体检\n\n"
        "如果你有具体的症状或指标疑问，可以上传体检报告后使用"
        "「结合档案问一问」获得更精准的个性化解答。\n\n"
        f"_{config.DISCLAIMER}_"
    )


@router.get("/conversations")
def conversations(profile_id: str, user: dict = Depends(current_user)):
    scoped_profile(profile_id, user)
    return {"items": repo.list_conversations(profile_id)}


@router.get("/conversations/{cid}")
def messages(cid: str, user: dict = Depends(current_user)):
    conv = repo.get_conversation(cid)
    if conv is None:
        raise HTTPException(404, "会话不存在")
    scoped_profile(conv["profile_id"], user)
    return {"conversation": conv, "messages": repo.list_messages(cid)}
