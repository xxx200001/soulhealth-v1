"""SQLite 连接与统一 Schema —— 规格书 §6「核心数据对象」的落地。

融合说明
--------
第一套 Demo 的 patients/documents/observations 与第二套 Demo 的
reports/labs 两组表在语义上重叠，这里按规格书统一为一套：

  users                    登录账户（复用第一套鉴权）
  profiles                 HealthProfile：健康数据主体（F-ON-02）
  reports                  Report：原始健康资料 + 状态机（F-UP，§10.1）
  observations             Observation：结构化指标，standardized_code 归一（F-DATA）
  findings                 影像/检查所见（超声描述等，作为证据来源之一）
  health_events            HealthEvent：仅存用户确认后的健康事件（F-REC-04）
  assessments              Assessment：一次健康分析 + 输入快照（F-AN-01，§10.2）
  health_issues            HealthIssue：TOP/其他健康问题（F-AN-03/05）
  diet_plans / recipes     DietPlan + Recipe：食补方案版本化（F-DIET）
  tea_plans                TeaPlan：药食同源茶饮版本化（F-TEA）
  safety_checks            SafetyCheck：安全闸门结果（§10.3，不可被前端绕过）
  conversations / conv_messages    问询会话（F-AG）
  event_candidates         ConversationEventCandidate：待确认入档信息（F-AG-06）

设计要点
- 趋势与比较一律基于 observations.observed_at（真实检查日期，F-DATA-05 /
  AC-03）；reports.upload_time 只做资料管理，绝不进医学趋势。
- 每条 observation 同时保留 original_name / 原始单位 / 原始参考范围
  （F-DATA-01/02/03），standardized 值另存，可追溯可回滚。
- 方案表只增不改：新版本插入新行（F-DIET-05 / F-TEA-04 / AC-18）。
"""
import sqlite3

from . import config

DDL = """
CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    role           TEXT NOT NULL DEFAULT 'user',
    display_name   TEXT,
    created_at     TEXT NOT NULL,
    disabled       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

CREATE TABLE IF NOT EXISTS profiles (
    id               TEXT PRIMARY KEY,
    owner_id         TEXT REFERENCES users(id),
    name             TEXT NOT NULL,
    sex              TEXT,                -- female | male | unknown
    birth_date       TEXT,                -- YYYY-MM-DD（最小建档三要素之一）
    height_cm        REAL,
    weight_kg        REAL,
    pregnant         INTEGER DEFAULT 0,
    allergies_json   TEXT DEFAULT '[]',
    medications_json TEXT DEFAULT '[]',
    conditions_json  TEXT DEFAULT '[]',   -- 已知疾病
    surgeries_json   TEXT DEFAULT '[]',
    smoking          TEXT,                -- none | quit | current
    alcohol          TEXT,                -- none | occasional | frequent
    diet_pref_json   TEXT DEFAULT '[]',
    field_times_json TEXT DEFAULT '{}',   -- 各字段最近更新时间（F-REC-05）
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    last_seen_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_profiles_owner ON profiles(owner_id);

CREATE TABLE IF NOT EXISTS reports (
    id              TEXT PRIMARY KEY,
    profile_id      TEXT NOT NULL REFERENCES profiles(id),
    report_type     TEXT,                 -- lab_report | ultrasound_report | checkup | other
    report_date     TEXT,                 -- 报告内检查/检验日期（可空=待确认）
    date_confirmed  INTEGER DEFAULT 0,    -- 日期来源：1=报告内识别/用户确认 0=待确认
    upload_time     TEXT NOT NULL,
    source_filename TEXT,
    stored_path     TEXT,                 -- 原件路径（F-UP-02：不可因 OCR 完成而丢弃）
    engine          TEXT,
    status          TEXT NOT NULL DEFAULT 'uploaded',
                    -- uploaded → processing → needs_confirmation / ready / failed
    error           TEXT,
    extraction_json TEXT,                 -- 原始抽取结果整体留档
    stats_json      TEXT,                 -- {observations, findings, low_confidence, matched}
    duplicate_of    TEXT,                 -- 疑似重复提示（F-UP-06，不自动删除）
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_profile ON reports(profile_id, report_date);

CREATE TABLE IF NOT EXISTS observations (
    id             TEXT PRIMARY KEY,
    report_id      TEXT REFERENCES reports(id),
    profile_id     TEXT NOT NULL REFERENCES profiles(id),
    code           TEXT NOT NULL,         -- standardized_code（F-DATA-01）
    original_name  TEXT,                  -- 报告原始名称，保留可追溯
    value_num      REAL,
    value_text     TEXT,
    unit           TEXT,                  -- 报告原始单位（F-DATA-02）
    canonical_value REAL,                 -- 标准化值（可安全换算时）
    canonical_unit TEXT,
    ref_low        REAL,                  -- 当次报告参考范围（F-DATA-03）
    ref_high       REAL,
    flag           TEXT,                  -- H / L / N（报告原始标记）
    grade          INTEGER,               -- 规则分级 -3..3（standardize.registry）
    match_method   TEXT,                  -- exact / fold / fuzzy / passthrough
    confidence     REAL DEFAULT 1.0,
    needs_confirm  INTEGER DEFAULT 0,     -- 低置信（F-UP-05）
    confirmed      INTEGER DEFAULT 0,
    observed_at    TEXT NOT NULL,         -- 真实检查日期（F-DATA-05）
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_obs_profile_code
    ON observations(profile_id, code, observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_report ON observations(report_id);

CREATE TABLE IF NOT EXISTS findings (
    id          TEXT PRIMARY KEY,
    report_id   TEXT REFERENCES reports(id),
    profile_id  TEXT NOT NULL REFERENCES profiles(id),
    organ       TEXT NOT NULL,
    description TEXT NOT NULL,
    flags_json  TEXT NOT NULL DEFAULT '[]',
    observed_at TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_profile ON findings(profile_id);

CREATE TABLE IF NOT EXISTS health_events (
    id          TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles(id),
    event_date  TEXT NOT NULL,
    type        TEXT NOT NULL,            -- symptom | lifestyle | medical | note
    content     TEXT NOT NULL,
    source      TEXT NOT NULL,            -- agent_confirmed | user_entry
    confirmed   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_profile ON health_events(profile_id, event_date);

CREATE TABLE IF NOT EXISTS assessments (
    id                  TEXT PRIMARY KEY,
    profile_id          TEXT NOT NULL REFERENCES profiles(id),
    status              TEXT NOT NULL DEFAULT 'queued',
                        -- queued → processing → completed / partial / failed
    error               TEXT,
    input_snapshot_json TEXT NOT NULL,    -- 本次使用的数据范围（F-UP-08 / F-AN-01）
    input_hash          TEXT NOT NULL,    -- 输入未变化时复用缓存（AC-19）
    summary_json        TEXT,             -- {counts:{priority,watch,mild,stable}, top_titles}
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assess_profile ON assessments(profile_id, created_at);

CREATE TABLE IF NOT EXISTS health_issues (
    id               TEXT PRIMARY KEY,
    assessment_id    TEXT NOT NULL REFERENCES assessments(id),
    rank             INTEGER NOT NULL,    -- 1..3 为 TOP，>=100 为相对稳定折叠区
    title            TEXT NOT NULL,
    level            TEXT NOT NULL,       -- stable | mild | watch | priority
    score            REAL NOT NULL,
    summary          TEXT,
    goal_tags_json   TEXT DEFAULT '[]',   -- 健康管理目标 → 供食补/茶饮引擎
    evidence_json    TEXT NOT NULL,       -- [{code,value,unit,date,report_id,source}]
    detail_json      TEXT NOT NULL        -- 固定结构：发现/历史/为何优先/意味着/趋势/缺口/行动
);
CREATE INDEX IF NOT EXISTS idx_issues_assess ON health_issues(assessment_id, rank);

CREATE TABLE IF NOT EXISTS diet_plans (
    id            TEXT PRIMARY KEY,
    profile_id    TEXT NOT NULL REFERENCES profiles(id),
    assessment_id TEXT NOT NULL REFERENCES assessments(id),
    version       INTEGER NOT NULL,
    goals_json    TEXT NOT NULL,          -- [{tag,label,why}]
    pools_json    TEXT NOT NULL,          -- {recommended:[],allowed:[],limit:[],avoid:[]}
    status        TEXT NOT NULL DEFAULT 'active',   -- active | superseded
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_diet_profile ON diet_plans(profile_id, version);

CREATE TABLE IF NOT EXISTS recipes (
    id            TEXT PRIMARY KEY,
    diet_plan_id  TEXT NOT NULL REFERENCES diet_plans(id),
    name          TEXT NOT NULL,
    goal_tag      TEXT,
    reason        TEXT,
    ingredients_json TEXT NOT NULL,       -- [{name, grams, note}]
    steps_json    TEXT NOT NULL,          -- [str]
    serving       TEXT,
    frequency     TEXT,
    cooking_method TEXT,
    avoid_methods_json TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_recipes_plan ON recipes(diet_plan_id);

CREATE TABLE IF NOT EXISTS tea_plans (
    id              TEXT PRIMARY KEY,
    profile_id      TEXT NOT NULL REFERENCES profiles(id),
    assessment_id   TEXT NOT NULL REFERENCES assessments(id),
    safety_check_id TEXT REFERENCES safety_checks(id),
    version         INTEGER NOT NULL,
    safety_status   TEXT NOT NULL,        -- allow | require_info | block | professional_review
    plan_json       TEXT NOT NULL,        -- 目标/原料克数/水量/制作/频率/周期/依据/禁忌
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tea_profile ON tea_plans(profile_id, version);

CREATE TABLE IF NOT EXISTS safety_checks (
    id            TEXT PRIMARY KEY,
    profile_id    TEXT NOT NULL REFERENCES profiles(id),
    assessment_id TEXT REFERENCES assessments(id),
    check_type    TEXT NOT NULL,          -- tea | diet
    inputs_json   TEXT NOT NULL,
    result        TEXT NOT NULL,          -- allow | require_info | block | professional_review
    reasons_json  TEXT NOT NULL DEFAULT '[]',
    missing_json  TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles(id),
    title       TEXT,
    state_json  TEXT DEFAULT '{}',        -- 问询控制器状态（意图/追问轮次/已收集槽位）
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_profile ON conversations(profile_id, updated_at);

CREATE TABLE IF NOT EXISTS conv_messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role            TEXT NOT NULL,        -- user | assistant
    content         TEXT NOT NULL,
    meta_json       TEXT DEFAULT '{}',    -- 结构化回答分节 / 引用 / 追问选项
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON conv_messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS event_candidates (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    profile_id      TEXT NOT NULL REFERENCES profiles(id),
    event_date      TEXT,
    type            TEXT NOT NULL,
    content         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | confirmed | dismissed
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cand_profile ON event_candidates(profile_id, status);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    own = conn is None
    conn = conn or connect()
    conn.executescript(DDL)
    conn.commit()
    if own:
        conn.close()
