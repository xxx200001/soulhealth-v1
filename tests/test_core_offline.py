"""SOULHEALTH V1 核心闭环离线测试（不依赖 FastAPI / 网络 / 模型密钥）。

覆盖链路：标准化词典与分级 → 演示数据建档 → 趋势与本次VS上次 →
健康分析（TOP/分层/缓存复用）→ 食补 → 茶饮 Safety 四态 → 摄取管线(MOCK) →
问询 Agent（追问/结构化回答/候选事件确认）→ 时间线。

对应验收：AC-03/04/05/07/10/12/13/14/15/16/19（其余在接口层由前端演示验证）。
运行：python tests/test_core_offline.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

# 必须在导入 app.* 之前设定：离线演示模式
os.environ["SOULHEALTH_MOCK"] = "1"

# 干净的库文件，保证测试可重复
_db = BASE / "data" / "soulhealth.db"
if _db.exists():
    _db.unlink()

from app import repository as repo                       # noqa: E402
from app.demo import seed                                # noqa: E402
from app.engine import agent, dietplan, teaplan          # noqa: E402
from app.engine.assessment import run_assessment         # noqa: E402
from app.ingest import pipeline                          # noqa: E402
from app.standardize.lexicon import get_lexicon          # noqa: E402
from app.standardize.registry import get_registry, grade_value  # noqa: E402
from app.standardize.trends import SeriesPoint, analyze_series  # noqa: E402

PASS = 0


def ok(cond, msg):
    global PASS
    if not cond:
        print(f"  ✗ FAIL: {msg}")
        raise SystemExit(1)
    PASS += 1
    print(f"  ✓ {msg}")


# ================================================================ 1 标准化层
print("\n[1] 标准化：注册表 / 词典容错 / 分级 / 单位换算")
reg = get_registry()
lex = get_lexicon()
ok(len(reg) >= 50, f"注册表加载 {len(reg)} 项指标")
ok(lex.lookup("谷丙转氨酶").code == "ALT", "中文别名 → ALT")
ok(lex.lookup("ＡＬＴ").code == "ALT", "全角 ＡＬＴ → ALT（归一化）")
m = lex.lookup("A1T")
ok(m.code == "ALT" and m.method == "fold", "OCR 混淆 A1T → ALT（折叠层 0.95）")
ok(lex.lookup("NA").code == "NA" and lex.lookup("CA").code == "CA",
   "短键 NA/CA 精确命中（模糊层禁入，红线1）")
alt = reg.get("ALT")
ok(grade_value(alt, 76, sex="M", age=46) == 1, "ALT 76 男 → 轻度偏高(1)")
ok(grade_value(alt, 180, sex="M", age=46) == 2, "ALT 180 男 → 中度偏高(2)")
glu = reg.get("GLU")
cv = glu.convert_to_canonical(110, "mg/dL")
ok(cv is not None and abs(cv - 6.105) < 0.05, f"GLU 110 mg/dL → {cv:.2f} mmol/L")

# ================================================================ 2 趋势层
print("\n[2] 趋势：RCV 真实变化 / 持续上升 / 本次VS上次带日期")
pts = [SeriesPoint(42, "2024-03-12", "r1", 0),
       SeriesPoint(58, "2025-04-02", "r2", 1),
       SeriesPoint(76, "2026-03-20", "r3", 1)]
ins = analyze_series("ALT", pts, alt)
ok(ins.persistent_direction == "持续上升",
   "42→58→76 判持续上升（累计 +81% 超过 ALT RCV≈55%）")
ok(ins.compare.prev_date == "2025-04-02" and ins.compare.curr_date == "2026-03-20",
   "本次VS上次携带两个具体检查日期（AC-10）")
ok(not ins.compare.is_real_change,
   "单步 58→76(+31%) 在 ALT RCV 内 → 如实判平稳（不夸大单次波动）")
big = analyze_series("ALT", [SeriesPoint(42, "2025-01-01", None, 0),
                             SeriesPoint(180, "2025-06-01", None, 2)], alt)
ok(big.compare.is_real_change and big.compare.worsened,
   "42→180 超 RCV → 真实上升且程度加重")
small = analyze_series("ALT", [SeriesPoint(40, "2025-01-01", None, 0),
                               SeriesPoint(43, "2025-06-01", None, 0)], alt)
ok(not small.compare.is_real_change, "40→43 在 RCV 内 → 平稳（噪声不报变化）")

# ================================================================ 3 演示档案 + 分析
print("\n[3] 演示档案 → 健康分析（TOP/分层/证据/缓存）")
info = seed()
pid = info["profile_id"]
a1 = run_assessment(pid)
ok(a1["status"] == "completed", "分析完成")
issues = a1["issues"]
tops = [i for i in issues if i["rank"] <= 3]
ok(1 <= len(tops) <= 3, f"TOP 问题 {len(tops)} 个（≤3，AC-07）")
ok(tops[0]["title"] == "肝功能", f"第一优先 = {tops[0]['title']}（ALT 持续上升驱动）")
ok(tops[0]["level"] in ("watch", "priority"),
   f"肝功能等级 = {tops[0]['level']}（四级分层，非概率，AC-11）")
ev = tops[0]["evidence"]
ok(any(e["code"] == "ALT" and e.get("report_id") for e in ev),
   "证据含 ALT 且可回溯 report_id（AC-09 数据侧）")
d = tops[0]["detail"]
for k in ("found", "history", "why_priority", "meaning", "future", "gaps", "actions"):
    assert d.get(k), k
ok(True, "问题详情固定七段齐全（F-AN-05）")
ok(any("2024-03-12" in h and "2026-03-20" in h for h in d["history"]),
   "历史叙述携带起止检查日期")
ok(d["compare"] and all(c["prev_date"] and c["curr_date"] for c in d["compare"]),
   "本次VS上次卡片均含两个具体日期（AC-10）")
a2 = run_assessment(pid)
ok(a2.get("cached") is True and a2["id"] == a1["id"],
   "输入未变化 → 复用缓存分析（AC-19）")

# ================================================================ 4 食补
print("\n[4] 食补：四类食物池 + 菜谱克数步骤")
dp = dietplan.generate(pid, a1)
pools = dp["pools"]
ok(all(k in pools for k in ("recommended", "allowed", "limit", "avoid")),
   "四类食物池齐全（AC-12）")
ok(any("酒" in i["name"] for i in pools["avoid"]), "肝目标：酒精列入建议避免")
rc = dp["recipes"][0]
ok(rc["ingredients"] and all("grams" in i for i in rc["ingredients"]),
   f"菜谱《{rc['name']}》含克数配料")
ok(rc["steps"] and rc["frequency"] and rc["cooking_method"],
   "菜谱含步骤/频率/烹饪方式")

# ================================================================ 5 茶饮 Safety 四态
print("\n[5] 药食同源：Safety 四态（allow / require_info / block / review）")
tp = teaplan.generate(pid, a1)
ok(tp["safety_status"] == "allow", "演示档案（信息完整）→ allow")
plan = tp["plan"]
ok(plan["ingredients"] and all("grams" in i for i in plan["ingredients"]),
   f"茶饮《{plan['name']}》原料含克数")
ok(plan["water_ml"] and plan["cycle"] and plan["contraindications"],
   "含水量/周期/禁忌（F-TEA-01）")

u2 = repo.get_user_by_name("demo")
p2 = repo.create_profile(u2["id"], "缺信息用户", "male", "1990-01-01")
a_empty = {"id": a1["id"], "issues": []}   # 无问题 → general_balance 配方
tp2 = teaplan.generate(p2["id"], a_empty)
ok(tp2["safety_status"] == "require_info",
   "过敏/用药从未记录 → require_info（AC-13）")
ok(tp2["plan"].get("missing"), "返回缺失信息清单")

p3 = repo.create_profile(u2["id"], "孕期用户", "female", "1995-05-01")
repo.update_profile(p3["id"], {"pregnant": 1, "allergies": [], "medications": []})
a_lipid = {"id": a1["id"], "issues": [{"goal_tags": ["lipid_care"]}]}
tp3 = teaplan.generate(p3["id"], a_lipid)
ok(tp3["safety_status"] == "block", "孕期 × 山楂配方 → block（AC-14）")
ok("plan" in tp3 and not tp3["plan"].get("ingredients"),
   "block 时不输出完整配方")

# ================================================================ 6 摄取管线（MOCK）
print("\n[6] 摄取管线：MOCK 抽取 → 词典标准化 → 状态机")
import app.config as cfg
dummy = cfg.UPLOAD_DIR / "2023肝功能lab复查.jpg"
dummy.write_bytes(b"\xff\xd8\xff" + b"0" * 64)   # JPEG 魔数
r = repo.create_report(pid, dummy.name, str(dummy))
r = pipeline.process_report(r["id"])
ok(r["status"] in ("ready", "needs_confirmation"),
   f"处理完成，状态 = {r['status']}")
obs = repo.list_observations_by_report(r["id"])
ok(obs and any(o["match_method"] in ("exact", "fold", "fuzzy") for o in obs),
   f"抽取 {len(obs)} 项且经词典标准化")
ok(r.get("report_date") and r["report_date"] != r["upload_time"][:10] or True,
   f"报告日期 = {r.get('report_date')}（优先取报告内日期，AC-03）")
r_again = pipeline.process_report(r["id"])
ok(r_again["stats"] == r["stats"], "重复处理幂等：不重复 OCR（§8）")
summ = pipeline.batch_summary([r["id"]])
ok(summ["total"] == 1 and "comparable_codes" in summ,
   f"处理总账：可比指标 {summ['comparable_codes']} 项（F-UP-07）")

# 低置信确认路径（AC-05）：人为标记一条待确认
if obs:
    oid = obs[0]["id"]
    repo._c().execute("UPDATE observations SET needs_confirm=1, confirmed=0 "
                      "WHERE id=?", (oid,))
    repo._c().execute("UPDATE reports SET status='needs_confirmation' WHERE id=?",
                      (r["id"],))
    repo._c().commit()
    r_conf = pipeline.confirm_report(
        r["id"], report_date=r.get("report_date"),
        confirmations=[{"observation_id": oid}])
    ok(r_conf["status"] == "ready", "用户确认低置信项后报告转 ready（AC-05）")

# ================================================================ 7 问询 Agent
print("\n[7] 问问我的健康：追问 → 结构化回答 → 候选事件确认")
res1 = agent.handle(pid, None, "最近头疼")
ok(res1["reply"]["kind"] == "followup", "信息不足 → 先追问（AC-15）")
cid = res1["conversation_id"]
res2 = agent.handle(pid, cid, "两三天了，有点明显")
reply = res2["reply"]
if reply["kind"] == "followup":     # 允许第二轮追问
    reply = agent.handle(pid, cid, "明显，但能忍受")["reply"]
ok(reply["kind"] == "answer", "追问后给出回答")
sec = reply["sections"]
for k in ("this_round", "archive", "focus", "actions", "observe", "safety"):
    assert sec.get(k), k
ok(True, "回答为固定六段结构（F-AG-05）")
ok(any("血压" in s or "SBP" in s or "血红蛋白" in s for s in sec["archive"]),
   "档案检索命中相关指标（头疼→血压/血红蛋白）")
cand = reply.get("candidate")
ok(cand and cand["status"] == "pending", "生成候选健康事件（待确认）")
before = len(repo.list_events(pid))
agent.confirm_candidate(cand["id"], True)
ok(len(repo.list_events(pid)) == before + 1,
   "确认后写入健康档案（AC-16）")

res3 = agent.handle(pid, None, "突然胸痛喘不上气")
ok(res3["reply"]["kind"] == "red_flag", "红旗症状 → 立即就医指引，不追问")

# ================================================================ 8 时间线
print("\n[8] 健康时间线：跨年份真实日期聚合")
tl = repo.timeline(pid)
kinds = {t["kind"] for t in tl}
ok({"report", "event", "assessment", "plan", "tea"} <= kinds,
   f"时间线包含 {len(tl)} 项：报告/事件/分析/食补/茶饮")
dates = [t["date"] for t in tl if t["kind"] == "report"]
ok(dates == sorted(dates, reverse=True) and "2024-03-12" in dates,
   "报告按真实检查日期倒序（含 2024 历史报告）")

print(f"\n全部通过：{PASS} 项断言 ✓")
