# SOULHEALTH V1 —— 长期健康档案 × 报告解析 × 个体化食养

把「SoulHealth 中医健康平台 Demo」与「疾病风险预测平台 Demo」按
《SOULHEALTH 产品方案说明书 V1.2（产品流程冻结版）》与
《SOULHEALTH V1.0 产品与技术需求规格书》融合而成的可运行版本。

一句话定位：**用户上传健康报告 → 系统识别并按真实检查日期归档 →
纵向比较看懂变化 → 输出可解释的四级关注分层 → 落到可执行的
食补方案与药食同源茶饮（含强制安全检查）→ 随时基于档案问询。**

---

## 一、两套 Demo 的融合决策表（对应方案书 §7）

| 模块 | 来源 | V1 去向 | 说明 |
| --- | --- | --- | --- |
| 视觉抽取管线（vision_llm / prompts / 脱敏 deid / schemas） | 第一套 SoulHealth | **保留并增强** | 新增报告状态机 `uploaded→processing→needs_confirmation/ready/failed`、检查日期优先于上传日期、低置信确认、疑似重复提示（F-UP 全组） |
| 账号鉴权（标准库 HMAC token） | 第一套 | **保留** | `app/auth.py` 原样复用 |
| UI 设计系统（松墨绿×陈皮金×宣纸底 / Noto Serif SC） | 第一套 | **延续演化** | 新增四级风险色带、食物池四色、健康脉络时间线、驾驶舱 hero（`web/src/styles/theme.css`） |
| 指标注册表（57 项参考区间 / 单位换算 / 危急值） | 第二套 DRP | **迁移** | `app/standardize/registry.py` + `configs/indicators.yaml` |
| 三层词典匹配（精确 / OCR 折叠 / 模糊 + 三条红线） | 第二套 DRP | **迁移** | `app/standardize/lexicon.py`，报告标准化的核心 |
| RCV 真实变化判定（2.77·√(CVa²+CVi²)） | 第二套 DRP | **迁移并扩展** | 新增「累计变化超 RCV 判持续趋势」，`app/standardize/trends.py` |
| LightGBM / Cox 1Y·3Y·5Y 患病概率 | 第二套 DRP | **删除** | 方案书 §7 明确不做精确概率；改为可解释的规则评分 + 四级分层（F-AN-08 / AC-11） |
| 中医辨证 / 舌诊面诊主线 | 第一套 | **删除** | 方案书 §7 冻结范围外 |
| 医生工作台 / 医生端 | 第二套 | **删除** | V1 仅个人用户 |
| 食补建议 | 第一套（理念） | **重写** | 目标 → 四类食物池（含理由/份量/频率）→ 克数菜谱，规则库可审计（F-DIET） |
| 药食同源茶饮 | 第一套（理念） | **重写** | 知识库配方 + **Safety Engine 四态**（allow / require_info / block / professional_review），前端不可绕过（F-TEA / §10.3） |
| 问询 Agent「问问我的健康」 | 新增 | **新建** | 确定性控制器（意图/红旗/追问≤2轮/档案检索）+ LLM 仅做表达层，可完全降级（F-AG） |
| 健康档案（时间线五区 / 事件 / 候选确认） | 新增 | **新建** | 一切以档案为中心（§6 产品原则） |

## 二、架构

```
web/  Vue3 + Vite + Pinia + ECharts（移动优先，底栏五区：首页/分析/方案/档案/我的）
        │  /api 反向代理
app/
 ├─ api/          FastAPI 路由（auth/profiles/reports/metrics/assessments/plans/ask）
 ├─ ingest/       摄取管线：视觉抽取(真实/MOCK) → 脱敏 → 日期 → 词典标准化 → 状态机
 ├─ standardize/  registry(57指标) · lexicon(三层容错) · trends(RCV+持续趋势)
 ├─ engine/       assessment(评分/四级分层/七段详情/缓存复用)
 │                dietplan(四池合并) · teaplan+safety(四态闸门)
 │                agent(问询控制器) · knowledge(食物池/菜谱/茶方/原料禁忌)
 ├─ repository.py + db.py   SQLite 14 表（全部数据归属 profile）
 └─ config.py / auth.py / demo.py
```

关键机制：
- **成本与稳定（§8）**：分析输入做快照哈希，未变化直接复用（AC-19）；
  报告重复处理幂等，不重复 OCR；Agent 检索上限截断。
- **可回溯（AC-09）**：任何证据、趋势点都带 `report_id` 与来源标签，
  一路点回原始报告原件。
- **安全边界（§10.3）**：茶饮生成前强制 Safety 检查并持久化结果，
  block / professional_review 状态下后端不产出完整配方。

## 三、快速开始

```bash
# 1) 后端（Python 3.10+）
cd soulhealth-v1
cp .env.example .env            # 默认 MOCK 离线演示模式
pip install -r requirements.txt
python run.py                   # http://localhost:8001（自动播种演示账号）

# 2) 前端开发模式（Node 18+）
cd web
npm install
npm run dev                     # http://localhost:5173（/api 已代理到 8001）

# 或：单端口部署
npm run build                   # 产物在 web/dist，后端自动托管
# 直接访问 http://localhost:8001
```

演示账号：**demo / demo123456**（内置李国栋 2024–2026 三年三份体检数据，
ALT 42→58→76 持续上升 + 脂肪肝所见 + 血脂/尿酸/血糖异常）。

接入真实模型（可选）：在 `.env` 配置 `ANTHROPIC_API_KEY` 并将
`SOULHEALTH_MOCK=0`，即可识别真实报告照片/PDF，问询回答由 LLM 润色
（事实仍全部来自规则与档案）。

## 四、10 分钟演示脚本（对应 AC-20）

1. 登录 demo → 首页驾驶舱：第一优先「肝功能 · 重点关注」+ 四级计数
2. 上传健康资料 → 多选几张图片（MOCK 模式按文件名含 `lab/超声/体检` 路由样例）
3. 观察逐份状态与总账；对「待确认」项就地补日期/核对数值 → 确认入档
4. 「开始健康分析」→ TOP1-3 每张卡都带排序理由与证据（含来源标签）
5. 点开肝功能 → 固定七段详情；「本次VS上次」卡显示 **两个真实检查日期**
6. 证据表点「检验报告 ›」→ 回到原始报告原件与逐项提取结果
7. 趋势页：ALT 曲线（X 轴为真实日期）+ 参考带 + 持续上升洞察
8. 方案页-食补：目标徽章 → 四类食物池（每项有理由）→ 菜谱克数与步骤
9. 方案页-茶饮：demo 档案信息完整 → allow 完整配方；
   新建档案不填过敏/用药 → require_info 补充清单；
   女性档案勾选怀孕后生成血脂茶 → block 拦截演示
10. 问问我的健康：「最近头疼」→ 追问 → 六段结构化回答（引用档案中的
    血压/血红蛋白趋势）→ 候选事件「保存入档」→ 档案时间线出现该事件

## 五、测试

```bash
python tests/test_core_offline.py   # 48 项断言，无需网络/密钥/FastAPI
```

覆盖：词典容错（含 OCR 混淆与短键红线）、单位换算与分级、RCV 判定、
持续趋势、TOP 排序与四级分层、缓存复用、四类食物池、茶饮四态、
摄取状态机与低置信确认、Agent 追问/红旗/候选事件、时间线聚合。

## 六、配置项（.env）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| SOULHEALTH_MOCK | 1 | 离线演示模式（内置样例抽取结果） |
| ANTHROPIC_API_KEY | 空 | 配置后启用真实视觉抽取与问询润色 |
| SOULHEALTH_LLM_MODEL | claude-sonnet-4-6 | 模型名 |
| SOULHEALTH_SEED_DEMO | 1 | 启动时播种演示账号 |
| SOULHEALTH_PORT | 8001 | 后端端口（前端代理同步读取） |
| SOULHEALTH_SECRET | 请修改 | Token 签名密钥 |

## 七、服务边界

本系统提供健康管理信息与生活方式建议，不构成医疗诊断、治疗方案或处方；
不输出未经验证的患病概率；检测到危急值或红旗症状时一律引导就医。
