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
    """通用健康问答（不绑定档案），首页入口使用。支持多轮连续对话上下文。"""
    text: str = Field(min_length=1, max_length=1000)
    messages: list[dict] | None = None


@router.post("")
def ask(body: AskBody, user: dict = Depends(current_user)):
    scoped_profile(body.profile_id, user)
    return agent.handle(body.profile_id, body.conversation_id,
                        body.text.strip())


@router.post("/general")
def ask_general(body: GeneralAskBody, _user: dict = Depends(current_user)):
    """通用健康问答：不查档案，结合多轮对话上下文历史，直接用 LLM 智能解答。
    适用于首页入口，让用户无需任何历史数据也能获得连贯、有深度、个性化的健康指导。"""
    text = body.text.strip()

    # 红旗检测（紧急情况无论在哪个入口都要拦截）
    red = [w for w in agent._RED_FLAGS if w in text]
    if red:
        reply = agent._red_flag_reply(red)
        return {"reply": reply}

    # 构造包含多轮上下文历史的对话列表
    chat_messages = []
    if body.messages:
        for m in body.messages[-10:]:  # 保留最近 10 轮对话上下文
            r = "assistant" if m.get("role") in ("assistant", "ai") else "user"
            c = str(m.get("content") or "").strip()
            if c:
                chat_messages.append({"role": r, "content": c})

    # 确保当前这条在消息末尾
    if not chat_messages or chat_messages[-1].get("content") != text:
        chat_messages.append({"role": "user", "content": text})

    # LLM 可用时走多轮大模型问答
    system = (
        "你是一位专业、温暖、严谨的健康管理顾问。用户正在与你进行多轮连续健康咨询，"
        "你必须结合之前的对话历史来理解用户的回答、补充描述与连续提问。\n\n"
        "回答要求：\n"
        "1. 【上下文记忆与承接】：紧密结合前文已知信息（如用户前文提到的部位、发病时长、症状特点等）。"
        "若前文已经明确了部位（如已说过右侧肋骨/左肋骨等），绝对不要再重复询问「是哪个部位」，而是直接基于该部位展开深入分析！\n"
        "2. 【针对性分析】：分析当前具体症状表现（如持续钝痛 vs 阵发绞痛）对应的可能原因、生理机制与器官关联。\n"
        "3. 【生活与自我照护】：给出清晰实用的日常建议（饮食禁忌、体位姿势、休息与活动注意点）。\n"
        "4. 【明确就医边界】：列出需要立即去医院就诊的警示指征及建议挂号科室（如普外科/消化内科/骨科/胸外科等）。\n"
        "5. 【严谨负责】：不做确定性临床诊断，不开处方药，不编造数据。\n"
        "6. 回答末尾附一句简短的免责提示。\n"
        "请用清晰排版、有重点标注的 Markdown 中文直接作答。"
    )
    answer = llm.chat(system=system, messages=chat_messages, max_tokens=900)

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
