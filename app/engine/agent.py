"""「问问我的健康」—— 基于个人健康档案的问询 Agent（方案书 §12 / F-AG）。

架构：问询控制器（确定性） + LLM（仅表达层，可降级）。
  1. 意图识别      关键词规则六分类：症状/指标/报告/饮食/茶饮/一般健康管理
  2. 红旗筛查      胸痛/呼吸困难/意识改变等 → 立即给就医指引，不再追问
  3. 充分性判断    按意图检查槽位（持续时间/严重程度），缺则追问，
                   全程最多 config.AGENT_MAX_FOLLOWUPS 轮（F-AG-03）
  4. 档案检索      只取与当前问题相关的指标序列 / 事件 / 最近分析
                   （上限 config.AGENT_CONTEXT_MAX_OBS，F-AG-04 / §8）
  5. 结构化回答    固定六段：本轮信息→相关档案→更值得关注→可以先做→
                   需要观察/补充→就医安全提示（F-AG-05）。
                   LLM 可用时仅基于给定事实改写为自然段落，不新增事实。
  6. 事件沉淀      对话中的症状信息生成候选事件，用户确认后才入档（F-AG-06）
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .. import config
from .. import repository as repo
from ..standardize.lexicon import get_lexicon
from ..standardize.registry import GRADE_LABELS, get_registry
from ..standardize.trends import SeriesPoint, analyze_series, trend_phrase
from . import llm

# ---------------------------------------------------------------- 意图与红旗
_INTENTS: List[Tuple[str, List[str]]] = [
    ("tea", ["茶饮", "泡什么", "喝什么茶", "药食同源", "代茶"]),
    ("diet", ["吃什么", "怎么吃", "饮食", "食补", "菜谱", "能不能吃", "忌口"]),
    ("report", ["报告", "体检单", "化验单", "看不懂", "解读"]),
    ("indicator", ["指标", "偏高", "偏低", "转氨酶", "血脂", "血糖", "尿酸",
                   "血压", "胆固醇", "血红蛋白", "肌酐"]),
    ("symptom", ["疼", "痛", "晕", "乏力", "累", "睡不好", "失眠", "咳",
                 "胀", "恶心", "拉肚子", "便秘", "心慌", "口渴", "麻"]),
]

_RED_FLAGS = ["胸痛", "胸口压榨", "呼吸困难", "喘不上", "大量出血", "呕血",
              "黑便", "晕倒", "意识不清", "说话不清", "一侧无力", "剧烈头痛",
              "高热不退", "自杀", "轻生"]

_SYMPTOM_TOPIC = {  # 症状 → 相关指标码（档案检索映射）
    "头": ["SBP", "DBP", "HGB"], "晕": ["SBP", "DBP", "HGB", "GLU"],
    "乏力": ["HGB", "GLU", "ALT", "TSH"], "累": ["HGB", "GLU", "ALT"],
    "口渴": ["GLU", "HBA1C"], "多尿": ["GLU", "CREA"],
    "心慌": ["SBP", "DBP", "HGB"], "水肿": ["CREA", "UREA", "ALB"],
    "关节": ["UA", "CRP"], "腹": ["ALT", "AST", "GGT", "AMY"],
    "皮肤黄": ["TBIL", "DBIL", "ALT"], "睡": ["SBP", "DBP"],
}

# 症状 → 具体缓解建议（保守的自我照护措施；就医边界由 observe/safety 段兜底）
# 匹配时按声明顺序扫描，命中的关键词会从待匹配文本中移除，
# 避免「拉肚子」再次命中「肚子」这类子串重复。
_SYMPTOM_RELIEF: List[Tuple[str, List[str]]] = [
    ("拉肚子", ["重点是补水补盐：少量多次喝温水或口服补液盐，先别喝含糖饮料",
               "吃清淡易消化的（粥、软面条），暂停生冷、油腻、奶制品和辛辣"]),
    ("便秘", ["把饮水加到每天 1500–2000 ml，多吃蔬菜、燕麦、火龙果等富含膳食纤维的食物",
             "固定一个时间蹲厕（比如早饭后），配合顺时针揉腹和每天 30 分钟快走"]),
    ("恶心", ["少量多餐、清淡为主，先吃米粥、面条这类好消化的，避开油腻和气味重的食物",
             "可以含一小片姜或喝温姜水，饭后保持坐位半小时再活动"]),
    ("心慌", ["先坐下或靠着休息，做几组缓慢的深呼吸（吸气 4 秒、呼气 6 秒）",
             "数一下 1 分钟脉搏并记下来，今天避开咖啡、浓茶、酒和剧烈活动"]),
    ("口渴", ["规律地少量多次饮水；同时留意是否伴随多尿、体重下降，这些要结合血糖一起看"]),
    ("关节", ["急性疼痛期先让关节休息，48 小时内冷敷、之后改热敷，每次 15–20 分钟",
             "少吃动物内脏、浓肉汤，别喝啤酒——档案里有尿酸问题时尤其要注意"]),
    ("乏力", ["今晚保证 7–8 小时睡眠，白天可以安排一次 20 分钟左右的小憩",
             "三餐规律、别不吃主食，配合散步等轻度活动，比一直躺着更容易恢复"]),
    ("失眠", ["固定上床和起床时间，睡前 1 小时放下手机、把灯光调暗",
             "下午两点后不喝咖啡和浓茶，晚饭别吃太饱，睡前用温水泡脚 10–15 分钟"]),
    ("头", ["找个安静、光线柔和的地方闭眼休息 15–30 分钟，温热毛巾敷颈肩或冷毛巾敷前额",
           "小口多次补水，今天先别碰咖啡、浓茶和酒，减少连续盯屏幕的时间",
           "可以按揉两侧太阳穴和颈后风池穴，每处 1–2 分钟，以酸胀舒适为度"]),
    ("胀", ["饭后别马上坐下或躺平，慢走 10–15 分钟帮助胃肠排气",
           "以肚脐为中心顺时针揉腹 5–10 分钟，配一杯温开水或温姜水小口慢饮",
           "这两天吃饭细嚼慢咽、七八分饱，少吃豆类、洋葱、红薯，暂停碳酸饮料和口香糖"]),
    ("肚子", ["暂停油腻、生冷、辛辣，喝温水，可用热水袋隔着衣服温敷腹部 15–20 分钟",
             "记录疼痛的位置、性质（绞痛还是隐痛）以及和进食的关系，便于就诊时说明"]),
    ("腹", ["暂停油腻、生冷、辛辣，喝温水，可用热水袋隔着衣服温敷腹部 15–20 分钟",
           "记录不适的位置、性质以及和进食的关系，便于就诊时说明"]),
    ("晕", ["感觉头晕时先坐下或躺下防止跌倒；起身放慢动作，先坐 30 秒再站起来",
           "补点水、按时吃饭别空腹硬扛"]),
    ("咳", ["多喝温水润喉，保持室内湿度，远离烟味、油烟和粉尘",
           "睡觉可以把枕头垫高一些，减轻夜间咳嗽"]),
    ("睡", ["固定上床和起床时间，睡前 1 小时放下手机、把灯光调暗",
           "下午两点后不喝咖啡和浓茶，晚饭别吃太饱，睡前用温水泡脚 10–15 分钟"]),
    ("累", ["今晚保证 7–8 小时睡眠，白天可以安排一次 20 分钟左右的小憩",
           "三餐规律、别不吃主食，配合散步等轻度活动，比一直躺着更容易恢复"]),
]

_DUR_RE = re.compile(r"(\d+)\s*(天|日|周|星期|个月|月|年)|今天|昨天|最近|这几天|一直")
_SEV_WORDS = ["轻微", "有点", "略", "明显", "严重", "剧烈", "受不了",
              "影响睡眠", "影响工作", "偶尔", "持续", "阵发"]


# ---------------------------------------------------------------- 主入口
def handle(profile_id: str, conversation_id: Optional[str],
           text: str) -> dict:
    """处理一条用户消息，返回 {conversation_id, reply}。
    reply.kind: red_flag / followup / answer。"""
    conv = (repo.get_conversation(conversation_id)
            if conversation_id else None)
    if conv is None:
        conv = repo.create_conversation(profile_id, title=text[:24])
    repo.add_message(conv["id"], "user", text)
    state = conv.get("state") or {}

    # 1) 红旗最优先（任何轮次）
    hit = [w for w in _RED_FLAGS if w in text]
    if hit:
        reply = _red_flag_reply(hit)
        repo.add_message(conv["id"], "assistant", reply["text"],
                         {"kind": "red_flag"})
        repo.update_conversation_state(conv["id"], {}, title=conv.get("title"))
        return {"conversation_id": conv["id"], "reply": reply}

    # 2) 意图（延续追问上下文，或按本句识别）
    intent = state.get("intent") or _classify(text)
    slots = dict(state.get("slots") or {})
    slots.setdefault("complaint", text if intent == "symptom" else
                     state.get("slots", {}).get("complaint", text))
    _fill_slots(slots, text)
    asked = int(state.get("followups", 0))

    # 3) 充分性判断 → 必要追问（仅症状类需要；限 N 轮）
    need = _missing_slots(intent, slots)
    if need and asked < config.AGENT_MAX_FOLLOWUPS:
        q = _followup_question(need[0])
        repo.update_conversation_state(conv["id"], {
            "intent": intent, "slots": slots, "followups": asked + 1})
        repo.add_message(conv["id"], "assistant", q["text"],
                         {"kind": "followup", "options": q.get("options", [])})
        return {"conversation_id": conv["id"],
                "reply": {"kind": "followup", **q}}

    # 4) 档案检索（只取相关上下文）
    ctx = _retrieve(profile_id, intent, slots, text)

    # 5) 结构化回答
    sections = _compose_sections(profile_id, intent, slots, ctx)
    answer_text = _render(sections)
    polished = _polish(answer_text, sections)

    # 6) 候选事件（症状类，确认后才入档）
    candidate = None
    if intent == "symptom" and slots.get("complaint"):
        content = _candidate_text(slots)
        candidate = repo.add_event_candidate(conv["id"], profile_id, content,
                                             "symptom", repo.today())

    repo.update_conversation_state(conv["id"], {}, title=conv.get("title"))
    reply = {"kind": "answer", "text": polished, "sections": sections,
             "candidate": candidate, "disclaimer": config.DISCLAIMER}
    repo.add_message(conv["id"], "assistant", polished,
                     {"kind": "answer", "sections": sections,
                      "candidate_id": candidate["id"] if candidate else None})
    return {"conversation_id": conv["id"], "reply": reply}


# ---------------------------------------------------------------- 意图与槽位
def _classify(text: str) -> str:
    for intent, kws in _INTENTS:
        if any(k in text for k in kws):
            return intent
    return "general"


def _fill_slots(slots: dict, text: str) -> None:
    if "duration" not in slots:
        m = _DUR_RE.search(text)
        if m:
            slots["duration"] = m.group(0)
    if "severity" not in slots:
        for w in _SEV_WORDS:
            if w in text:
                slots["severity"] = w
                break


def _missing_slots(intent: str, slots: dict) -> List[str]:
    if intent != "symptom":
        return []
    need = []
    if "duration" not in slots:
        need.append("duration")
    if "severity" not in slots:
        need.append("severity")
    return need


def _followup_question(slot: str) -> dict:
    if slot == "duration":
        return {"text": "这个情况持续多久了？",
                "options": ["今天刚出现", "两三天了", "一周以上", "断断续续一个月以上"]}
    return {"text": "程度大概怎样？对日常有影响吗？",
            "options": ["轻微，不影响生活", "明显，但能忍受", "比较严重，影响睡眠或工作"]}


# ---------------------------------------------------------------- 档案检索
def _retrieve(profile_id: str, intent: str, slots: dict, text: str) -> dict:
    registry = get_registry()
    lexicon = get_lexicon()
    codes: List[str] = []

    # 用户点名的指标（词典容错识别）
    for token in re.split(r"[，。,.！？!?\s、的和与]+", text):
        if len(token) < 2:
            continue
        m = lexicon.lookup(token)
        if m.matched and m.code not in codes:
            codes.append(m.code)
    # 症状 → 主题指标
    if intent == "symptom":
        for kw, cs in _SYMPTOM_TOPIC.items():
            if kw in (slots.get("complaint") or "") or kw in text:
                for c in cs:
                    if c not in codes:
                        codes.append(c)
    # 饮食/茶饮/报告/一般 → 用最近分析的重点问题指标
    latest = repo.latest_assessment(profile_id)
    issues = repo.list_issues(latest["id"]) if latest else []
    if intent in ("diet", "tea", "report", "general") and issues:
        for it in issues:
            for c in (it["detail"].get("codes_abnormal") or []):
                if c not in codes:
                    codes.append(c)

    series = []
    total_pts = 0
    for c in codes[:8]:
        rows = repo.series_by_code(profile_id, c)
        if not rows:
            continue
        pts = [SeriesPoint(r["value"], r["observed_at"], r["report_id"],
                           r["grade"] or 0, r["unit"]) for r in rows]
        remain = config.AGENT_CONTEXT_MAX_OBS - total_pts
        if remain <= 0:
            break
        pts = pts[-min(4, remain):]
        total_pts += len(pts)
        ins = analyze_series(c, pts, registry.get(c))
        if ins:
            series.append(ins)

    kw_events = []
    for e in repo.list_events(profile_id,
                              limit=config.AGENT_CONTEXT_MAX_EVENTS * 3):
        if any(k in e["content"] for k in _tokens(text)) or intent == "general":
            kw_events.append(e)
        if len(kw_events) >= config.AGENT_CONTEXT_MAX_EVENTS:
            break

    top_issues = [{"title": it["title"], "level": it["level"],
                   "summary": it["summary"]} for it in issues
                  if it["rank"] <= 3]
    return {"series": series, "events": kw_events, "top_issues": top_issues,
            "has_archive": bool(series or kw_events or top_issues)}


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[，。,.！？!?\s、]+", text) if len(t) >= 2][:6]


# ---------------------------------------------------------------- 结构化回答
def _compose_sections(profile_id: str, intent: str, slots: dict,
                      ctx: dict) -> dict:
    registry = get_registry()

    this_round = []
    if intent == "symptom":
        line = f"你描述的情况：{slots.get('complaint', '')}"
        if slots.get("duration"):
            line += f"；持续时间：{slots['duration']}"
        if slots.get("severity"):
            line += f"；程度：{slots['severity']}"
        this_round.append(line)
    else:
        this_round.append(f"你的问题：{slots.get('complaint', '')}")

    archive = []
    for ins in ctx["series"]:
        meta = registry.get(ins.code)
        name = meta.name_cn if meta else ins.code
        g = ins.latest.grade
        tag = f"，{GRADE_LABELS[g]}" if g else "，在参考范围内"
        archive.append(trend_phrase(ins, name, ins.latest.unit or "") + tag)
    for e in ctx["events"][:3]:
        archive.append(f"既往记录（{e['event_date']}）：{e['content'][:36]}")
    if not archive:
        archive.append("档案中暂无与本问题直接相关的历史记录；"
                       "上传体检报告后，回答会结合你的真实数据")

    focus = []
    abnormal = [i for i in ctx["series"] if i.latest.grade != 0]
    for ins in abnormal[:3]:
        meta = registry.get(ins.code)
        name = meta.name_cn if meta else ins.code
        extra = f"（{ins.persistent_direction}）" if ins.persistent_direction else ""
        focus.append(f"{name}当前{GRADE_LABELS[ins.latest.grade]}{extra}，"
                     f"与本次问题的相关性值得留意")
    for t in ctx["top_issues"][:2]:
        focus.append(f"你档案中的「{t['title']}」当前为"
                     f"{_level_cn(t['level'])}：{t['summary']}")
    if not focus:
        focus.append("结合现有信息，暂未发现需要立即警惕的档案线索")

    actions = _actions_for(intent, abnormal, slots)
    observe = _observe_for(intent, slots)
    safety_line = _safety_for(intent, slots, abnormal)

    return {"this_round": this_round, "archive": archive, "focus": focus,
            "actions": actions, "observe": observe, "safety": safety_line}


def _actions_for(intent: str, abnormal, slots: Optional[dict] = None) -> List[str]:
    if intent == "diet":
        return ["以「方案 → 我的食补」中的四类食物池为准（它基于你的最新分析生成）",
                "本周先执行 1–2 条最容易的（如戒含糖饮料、晚餐先吃菜）"]
    if intent == "tea":
        return ["前往「方案 → 药食同源」查看基于你档案生成的茶饮方案",
                "首次饮用从半量开始，观察 2–3 天无不适再按方案量"]
    if intent == "symptom":
        relief = _relief_actions((slots or {}).get("complaint") or "")
        if relief:
            return relief + ["把本次情况确认保存到健康档案，便于后续对比"]
        return ["先观察记录：发生时间、持续时长、诱因（如熬夜/饮酒/情绪）",
                "规律作息与饮水，暂避酒精与刺激性饮食",
                "把本次情况确认保存到健康档案，便于后续对比"]
    if intent in ("indicator", "report"):
        return ["在「分析」页查看该指标的完整趋势与本次 VS 上次",
                "按对应问题的行动建议执行，并在建议周期内复查"]
    return ["保持记录习惯：新报告及时上传，系统会自动纵向比较",
            "有具体症状或指标疑问可以随时继续问我"]


def _relief_actions(complaint: str) -> List[str]:
    """按主诉匹配具体缓解建议：最多两组症状、合计不超过五条。
    命中的关键词从待匹配文本中移除，避免子串重复命中。"""
    tips: List[str] = []
    probe = complaint
    groups = 0
    for kw, lines in _SYMPTOM_RELIEF:
        if groups >= 2 or len(tips) >= 5:
            break
        if kw in probe:
            probe = probe.replace(kw, "", 1)
            groups += 1
            for line in lines:
                if line not in tips and len(tips) < 5:
                    tips.append(line)
    return tips


def _observe_for(intent: str, slots: dict) -> List[str]:
    if intent == "symptom":
        return ["若 3–5 天无缓解、或程度加重，请安排就诊",
                "留意伴随表现（发热、体重明显变化、夜间痛醒等）并记录"]
    return ["下次体检/复查后上传新报告，观察相关指标的真实变化"]


def _safety_for(intent: str, slots: dict, abnormal) -> str:
    sev = slots.get("severity", "")
    if intent == "symptom" and ("严重" in sev or "影响" in sev):
        return ("你的描述程度较明显：建议尽早就医面诊，而不是仅依赖线上建议；"
                "若出现胸痛、呼吸困难、意识改变等情况请立即急诊。")
    if any(abs(i.latest.grade) >= 3 for i in abnormal):
        return "档案中存在重度异常指标，请优先就医复核，再考虑生活方式调整。"
    return ("以上为健康管理参考，不构成诊断；症状持续、加重或你感到担心时，"
            "请及时就医。")


def _render(s: dict) -> str:
    def block(title, items):
        if isinstance(items, str):
            items = [items]
        return f"**{title}**\n" + "\n".join(f"- {i}" for i in items)
    return "\n\n".join([
        block("本轮信息", s["this_round"]),
        block("相关档案", s["archive"]),
        block("当前更值得关注", s["focus"]),
        block("可以先做什么", s["actions"]),
        block("需要观察 / 补充", s["observe"]),
        block("就医提示", s["safety"]),
    ])


def _polish(text: str, sections: dict) -> str:
    """LLM 仅做表达润色：不得新增事实、不得给诊断承诺；失败即回退模板。"""
    out = llm.complete(
        system=("你是健康档案问询助手。仅基于给定的结构化事实，把内容改写为"
                "更自然流畅的中文回答，保留六个小节标题与全部数值日期；"
                "禁止新增任何事实、数值或病名，禁止诊断与疗效承诺。"),
        user=text, max_tokens=900)
    return out or text


def _candidate_text(slots: dict) -> str:
    parts = [slots.get("complaint", "").strip()[:40]]
    if slots.get("duration"):
        parts.append(f"持续{slots['duration']}")
    if slots.get("severity"):
        parts.append(f"程度：{slots['severity']}")
    return "，".join(p for p in parts if p)


def _red_flag_reply(hits: List[str]) -> dict:
    text = (f"你提到「{hits[0]}」——这类情况属于需要优先排除风险的表现。\n\n"
            "**请现在就做**\n- 若症状正在发生或加重：立即拨打急救电话或前往最近的急诊\n"
            "- 请勿独自驾车前往；如条件允许请让家人陪同\n\n"
            "线上问询不适合处理急症；待情况稳定后，欢迎回来把这次经过"
            "记录进健康档案，便于后续管理。")
    return {"kind": "red_flag", "text": text}


def _level_cn(level: str) -> str:
    return {"stable": "相对稳定", "mild": "轻度关注",
            "watch": "需要留意", "priority": "重点关注"}.get(level, level)


def confirm_candidate(candidate_id: str, accept: bool) -> dict:
    """用户确认/忽略候选事件（AC-16：未确认不得自动入档）。"""
    cand = repo.get_candidate(candidate_id)
    if cand is None:
        raise ValueError("候选事件不存在")
    if not accept:
        return repo.resolve_candidate(candidate_id, "dismissed")
    repo.add_event(cand["profile_id"], cand["event_date"] or repo.today(),
                   cand["type"], cand["content"], "agent_confirmed")
    return repo.resolve_candidate(candidate_id, "confirmed")
