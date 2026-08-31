"""统一数据访问层 —— 全部业务对象的存取都走这里，路由层不直接写 SQL。

融合说明：替代第一套 Demo 的 archive/repository.py 与第二套 Demo 的
app/db.py 两套并存的持久化，对应新 Schema（app/db.py）。
时间统一存 ISO 字符串；json 字段进出统一 loads/dumps。
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from . import db

_local = threading.local()
_lock = threading.Lock()


def init() -> None:
    """确保当前线程有独立的 SQLite 连接（线程安全）。"""
    if not getattr(_local, "conn", None):
        _local.conn = db.connect()
        db.init_db(_local.conn)


def _c():
    if not getattr(_local, "conn", None):
        init()
    return _local.conn


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _j(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def _row(r) -> Optional[dict]:
    return dict(r) if r is not None else None


def _rows(rs) -> List[dict]:
    return [dict(r) for r in rs]


def _loads(s, default):
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


# ================================================================ users
def create_user(username: str, password_hash: str, role: str = "user",
                display_name: str | None = None) -> dict:
    with _lock:
        uid = _id("u")
        _c().execute(
            "INSERT INTO users(id,username,password_hash,role,display_name,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (uid, username, password_hash, role, display_name, now()))
        _c().commit()
    return get_user(uid)


def get_user(uid: str) -> Optional[dict]:
    return _row(_c().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())


def get_user_by_name(username: str) -> Optional[dict]:
    return _row(_c().execute("SELECT * FROM users WHERE username=?",
                             (username,)).fetchone())


def count_users() -> int:
    return _c().execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ================================================================ profiles
_PROFILE_JSON = ("allergies_json", "medications_json", "conditions_json",
                 "surgeries_json", "diet_pref_json")
_PROFILE_FIELDS = ("name", "sex", "birth_date", "height_cm", "weight_kg", "pregnant",
                   "smoking", "alcohol") + _PROFILE_JSON


def create_profile(owner_id: str, name: str, sex: str | None,
                   birth_date: str | None, **extra) -> dict:
    with _lock:
        pid = _id("p")
        t = now()
        _c().execute(
            "INSERT INTO profiles(id,owner_id,name,sex,birth_date,created_at,"
            "updated_at,last_seen_at,field_times_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (pid, owner_id, name, sex, birth_date, t, t, t,
             _j({k: t for k in ("name", "sex", "birth_date")})))
        _c().commit()
    if extra:
        update_profile(pid, extra)
    return get_profile(pid)


def get_profile(pid: str) -> Optional[dict]:
    p = _row(_c().execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone())
    if p is None:
        return None
    for k in _PROFILE_JSON:
        p[k.replace("_json", "")] = _loads(p.pop(k), [])
    p["field_times"] = _loads(p.pop("field_times_json"), {})
    p["age_years"] = _age_from_birth(p.get("birth_date"))
    return p


def _age_from_birth(birth: str | None) -> Optional[int]:
    if not birth:
        return None
    try:
        b = datetime.strptime(birth[:10], "%Y-%m-%d")
        t = datetime.now()
        return t.year - b.year - ((t.month, t.day) < (b.month, b.day))
    except ValueError:
        return None


def list_profiles(owner_id: str) -> List[dict]:
    rows = _rows(_c().execute(
        "SELECT id FROM profiles WHERE owner_id=? ORDER BY last_seen_at DESC",
        (owner_id,)))
    return [get_profile(r["id"]) for r in rows]


def update_profile(pid: str, patch: dict) -> Optional[dict]:
    cur = _row(_c().execute("SELECT field_times_json FROM profiles WHERE id=?",
                            (pid,)).fetchone())
    if cur is None:
        return None
    times = _loads(cur["field_times_json"], {})
    sets, vals = [], []
    for key, value in patch.items():
        col = key if key in _PROFILE_FIELDS else (
            f"{key}_json" if f"{key}_json" in _PROFILE_JSON else None)
        if col is None:
            continue
        sets.append(f"{col}=?")
        vals.append(_j(value) if col.endswith("_json") else value)
        times[key.replace("_json", "")] = now()
    if not sets:
        return get_profile(pid)
    sets += ["updated_at=?", "field_times_json=?"]
    vals += [now(), _j(times), pid]
    with _lock:
        _c().execute(f"UPDATE profiles SET {', '.join(sets)} WHERE id=?", vals)
        _c().commit()
    return get_profile(pid)


def touch_profile(pid: str) -> None:
    with _lock:
        _c().execute("UPDATE profiles SET last_seen_at=? WHERE id=?", (now(), pid))
        _c().commit()


# ================================================================ reports
def create_report(profile_id: str, source_filename: str | None,
                  stored_path: str | None, report_type: str | None = None) -> dict:
    with _lock:
        rid = _id("r")
        t = now()
        _c().execute(
            "INSERT INTO reports(id,profile_id,report_type,upload_time,"
            "source_filename,stored_path,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (rid, profile_id, report_type, t, source_filename, stored_path,
             "uploaded", t))
        _c().commit()
    return get_report(rid)


def get_report(rid: str) -> Optional[dict]:
    r = _row(_c().execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone())
    if r is None:
        return None
    r["stats"] = _loads(r.pop("stats_json"), {})
    r["extraction"] = _loads(r.pop("extraction_json"), None)
    return r


def set_report_status(rid: str, status: str, *, error: str | None = None,
                      report_type: str | None = None,
                      report_date: str | None = None,
                      date_confirmed: int | None = None,
                      engine: str | None = None,
                      extraction: dict | None = None,
                      stats: dict | None = None,
                      duplicate_of: str | None = None) -> None:
    sets, vals = ["status=?"], [status]
    if error is not None:
        sets.append("error=?"); vals.append(error)
    if report_type is not None:
        sets.append("report_type=?"); vals.append(report_type)
    if report_date is not None:
        sets.append("report_date=?"); vals.append(report_date)
    if date_confirmed is not None:
        sets.append("date_confirmed=?"); vals.append(date_confirmed)
    if engine is not None:
        sets.append("engine=?"); vals.append(engine)
    if extraction is not None:
        sets.append("extraction_json=?"); vals.append(_j(extraction))
    if stats is not None:
        sets.append("stats_json=?"); vals.append(_j(stats))
    if duplicate_of is not None:
        sets.append("duplicate_of=?"); vals.append(duplicate_of)
    vals.append(rid)
    with _lock:
        _c().execute(f"UPDATE reports SET {', '.join(sets)} WHERE id=?", vals)
        _c().commit()


def list_reports(profile_id: str) -> List[dict]:
    rows = _c().execute(
        "SELECT id,profile_id,report_type,report_date,date_confirmed,upload_time,"
        "source_filename,status,error,engine,stats_json,duplicate_of "
        "FROM reports WHERE profile_id=? "
        "ORDER BY COALESCE(report_date, substr(upload_time,1,10)) DESC, upload_time DESC",
        (profile_id,)).fetchall()
    out = []
    for r in _rows(rows):
        r["stats"] = _loads(r.pop("stats_json"), {})
        out.append(r)
    return out


def find_duplicate(profile_id: str, report_date: str | None,
                   report_type: str | None, exclude_rid: str) -> Optional[str]:
    """疑似重复：同档案 + 同报告日期 + 同类型（F-UP-06，仅提示不删除）。"""
    if not report_date:
        return None
    row = _c().execute(
        "SELECT id FROM reports WHERE profile_id=? AND report_date=? "
        "AND IFNULL(report_type,'')=IFNULL(?,'') AND id<>? AND status IN "
        "('ready','needs_confirmation') LIMIT 1",
        (profile_id, report_date, report_type, exclude_rid)).fetchone()
    return row["id"] if row else None


# ================================================================ observations
def add_observation(profile_id: str, report_id: str | None, observed_at: str,
                    **kw) -> str:
    with _lock:
        oid = _id("o")
        _c().execute(
            "INSERT INTO observations(id,report_id,profile_id,code,original_name,"
            "value_num,value_text,unit,canonical_value,canonical_unit,ref_low,"
            "ref_high,flag,grade,match_method,confidence,needs_confirm,confirmed,"
            "observed_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (oid, report_id, profile_id, kw.get("code"), kw.get("original_name"),
             kw.get("value_num"), kw.get("value_text"), kw.get("unit"),
             kw.get("canonical_value"), kw.get("canonical_unit"),
             kw.get("ref_low"), kw.get("ref_high"), kw.get("flag"),
             kw.get("grade", 0), kw.get("match_method"),
             kw.get("confidence", 1.0), int(kw.get("needs_confirm", 0)),
             int(kw.get("confirmed", 0)), observed_at, now()))
        _c().commit()
    return oid


def list_observations_by_report(report_id: str) -> List[dict]:
    return _rows(_c().execute(
        "SELECT * FROM observations WHERE report_id=? ORDER BY code", (report_id,)))


def get_observation(oid: str) -> Optional[dict]:
    return _row(_c().execute("SELECT * FROM observations WHERE id=?", (oid,)).fetchone())


def confirm_observation(oid: str, value_num: float | None = None) -> Optional[dict]:
    sets, vals = ["needs_confirm=0", "confirmed=1"], []
    if value_num is not None:
        sets += ["value_num=?", "canonical_value=?"]
        vals += [value_num, value_num]
    vals.append(oid)
    with _lock:
        _c().execute(f"UPDATE observations SET {', '.join(sets)} WHERE id=?", vals)
        _c().commit()
    return get_observation(oid)


def series_by_code(profile_id: str, code: str) -> List[dict]:
    """同一标准化指标跨报告的历史序列（真实日期升序；每个数据点带 report_id
    可回溯来源，F-DATA-04 / F-REC-03）。只取可比数据：canonical_value 非空。"""
    return _rows(_c().execute(
        "SELECT id,report_id,code,original_name,canonical_value AS value,"
        "canonical_unit AS unit,ref_low,ref_high,flag,grade,observed_at,"
        "needs_confirm,confirmed FROM observations "
        "WHERE profile_id=? AND code=? AND canonical_value IS NOT NULL "
        "AND (needs_confirm=0 OR confirmed=1) "
        "ORDER BY observed_at, created_at", (profile_id, code)))


def all_codes(profile_id: str) -> List[dict]:
    """档案内出现过的全部标准化指标 + 记录次数（指标中心索引）。"""
    return _rows(_c().execute(
        "SELECT code, COUNT(*) AS n, MAX(observed_at) AS last_date "
        "FROM observations WHERE profile_id=? AND canonical_value IS NOT NULL "
        "GROUP BY code ORDER BY n DESC, code", (profile_id,)))


def pending_confirmations(profile_id: str) -> List[dict]:
    return _rows(_c().execute(
        "SELECT * FROM observations WHERE profile_id=? AND needs_confirm=1 "
        "AND confirmed=0 ORDER BY created_at", (profile_id,)))


# ================================================================ findings
def add_finding(profile_id: str, report_id: str | None, organ: str,
                description: str, flags: list, observed_at: str) -> str:
    with _lock:
        fid = _id("f")
        _c().execute(
            "INSERT INTO findings(id,report_id,profile_id,organ,description,"
            "flags_json,observed_at,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (fid, report_id, profile_id, organ, description, _j(flags),
             observed_at, now()))
        _c().commit()
    return fid


def list_findings(profile_id: str) -> List[dict]:
    out = _rows(_c().execute(
        "SELECT * FROM findings WHERE profile_id=? ORDER BY observed_at DESC",
        (profile_id,)))
    for f in out:
        f["flags"] = _loads(f.pop("flags_json"), [])
    return out


def list_findings_by_report(report_id: str) -> List[dict]:
    out = _rows(_c().execute(
        "SELECT * FROM findings WHERE report_id=? ORDER BY created_at",
        (report_id,)))
    for f in out:
        f["flags"] = _loads(f.pop("flags_json"), [])
    return out


# ================================================================ health events
def add_event(profile_id: str, event_date: str, etype: str, content: str,
              source: str) -> dict:
    with _lock:
        eid = _id("e")
        _c().execute(
            "INSERT INTO health_events(id,profile_id,event_date,type,content,"
            "source,confirmed,created_at) VALUES(?,?,?,?,?,?,1,?)",
            (eid, profile_id, event_date, etype, content, source, now()))
        _c().commit()
    return _row(_c().execute("SELECT * FROM health_events WHERE id=?",
                             (eid,)).fetchone())


def list_events(profile_id: str, limit: int = 200) -> List[dict]:
    return _rows(_c().execute(
        "SELECT * FROM health_events WHERE profile_id=? "
        "ORDER BY event_date DESC, created_at DESC LIMIT ?", (profile_id, limit)))


# ================================================================ assessments
def input_snapshot(profile_id: str) -> dict:
    """本次分析将使用的数据范围（F-UP-08 / F-AN-01 / AC-06）。"""
    reports = [r for r in list_reports(profile_id) if r["status"] == "ready"]
    codes = all_codes(profile_id)
    events = list_events(profile_id, limit=50)
    prof = get_profile(profile_id) or {}
    dates = [r["report_date"] for r in reports if r.get("report_date")]
    return {
        "profile_fields": {k: prof.get(k) for k in
                           ("sex", "birth_date", "height_cm", "weight_kg")},
        "reports": [{"id": r["id"], "type": r["report_type"],
                     "date": r["report_date"]} for r in reports],
        "report_count": len(reports),
        "date_span": [min(dates), max(dates)] if dates else None,
        "indicator_codes": [c["code"] for c in codes],
        "comparable_codes": [c["code"] for c in codes if c["n"] >= 2],
        "event_count": len(events),
    }


def snapshot_hash(snap: dict) -> str:
    return hashlib.sha256(_j(snap).encode("utf-8")).hexdigest()[:16]


def latest_assessment(profile_id: str, status: str | None = "completed") -> Optional[dict]:
    q = "SELECT * FROM assessments WHERE profile_id=?"
    args: list = [profile_id]
    if status:
        q += " AND status=?"
        args.append(status)
    q += " ORDER BY created_at DESC LIMIT 1"
    r = _row(_c().execute(q, args).fetchone())
    if r:
        r["input_snapshot"] = _loads(r.pop("input_snapshot_json"), {})
        r["summary"] = _loads(r.pop("summary_json"), {})
    return r


def get_assessment(aid: str) -> Optional[dict]:
    r = _row(_c().execute("SELECT * FROM assessments WHERE id=?", (aid,)).fetchone())
    if r:
        r["input_snapshot"] = _loads(r.pop("input_snapshot_json"), {})
        r["summary"] = _loads(r.pop("summary_json"), {})
    return r


def create_assessment(profile_id: str, snap: dict, ihash: str) -> dict:
    with _lock:
        aid = _id("a")
        _c().execute(
            "INSERT INTO assessments(id,profile_id,status,input_snapshot_json,"
            "input_hash,created_at) VALUES(?,?,?,?,?,?)",
            (aid, profile_id, "processing", _j(snap), ihash, now()))
        _c().commit()
    return get_assessment(aid)


def finish_assessment(aid: str, status: str, summary: dict | None = None,
                      error: str | None = None) -> None:
    with _lock:
        _c().execute(
            "UPDATE assessments SET status=?, summary_json=?, error=? WHERE id=?",
            (status, _j(summary or {}), error, aid))
        _c().commit()


def list_assessments(profile_id: str) -> List[dict]:
    rows = _rows(_c().execute(
        "SELECT id,profile_id,status,input_hash,summary_json,created_at "
        "FROM assessments WHERE profile_id=? ORDER BY created_at DESC",
        (profile_id,)))
    for r in rows:
        r["summary"] = _loads(r.pop("summary_json"), {})
    return rows


def save_issues(aid: str, issues: List[dict]) -> None:
    with _lock:
        for it in issues:
            _c().execute(
                "INSERT INTO health_issues(id,assessment_id,rank,title,level,score,"
                "summary,goal_tags_json,evidence_json,detail_json)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (_id("i"), aid, it["rank"], it["title"], it["level"], it["score"],
                 it.get("summary"), _j(it.get("goal_tags", [])),
                 _j(it.get("evidence", [])), _j(it.get("detail", {}))))
        _c().commit()


def list_issues(aid: str) -> List[dict]:
    rows = _rows(_c().execute(
        "SELECT * FROM health_issues WHERE assessment_id=? ORDER BY rank", (aid,)))
    for r in rows:
        r["goal_tags"] = _loads(r.pop("goal_tags_json"), [])
        r["evidence"] = _loads(r.pop("evidence_json"), [])
        r["detail"] = _loads(r.pop("detail_json"), {})
    return rows


def get_issue(iid: str) -> Optional[dict]:
    r = _row(_c().execute("SELECT * FROM health_issues WHERE id=?", (iid,)).fetchone())
    if r:
        r["goal_tags"] = _loads(r.pop("goal_tags_json"), [])
        r["evidence"] = _loads(r.pop("evidence_json"), [])
        r["detail"] = _loads(r.pop("detail_json"), {})
    return r


# ================================================================ diet / tea plans
def next_plan_version(table: str, profile_id: str) -> int:
    row = _c().execute(
        f"SELECT MAX(version) AS v FROM {table} WHERE profile_id=?",
        (profile_id,)).fetchone()
    return (row["v"] or 0) + 1


def save_diet_plan(profile_id: str, assessment_id: str, goals: list,
                   pools: dict, recipes: List[dict]) -> dict:
    with _lock:
        _c().execute("UPDATE diet_plans SET status='superseded' "
                     "WHERE profile_id=? AND status='active'", (profile_id,))
        pid_ = _id("dp")
        ver = next_plan_version("diet_plans", profile_id)
        _c().execute(
            "INSERT INTO diet_plans(id,profile_id,assessment_id,version,goals_json,"
            "pools_json,status,created_at) VALUES(?,?,?,?,?,?, 'active', ?)",
            (pid_, profile_id, assessment_id, ver, _j(goals), _j(pools), now()))
        for rc in recipes:
            _c().execute(
                "INSERT INTO recipes(id,diet_plan_id,name,goal_tag,reason,"
                "ingredients_json,steps_json,serving,frequency,cooking_method,"
                "avoid_methods_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (_id("rc"), pid_, rc["name"], rc.get("goal_tag"), rc.get("reason"),
                 _j(rc.get("ingredients", [])), _j(rc.get("steps", [])),
                 rc.get("serving"), rc.get("frequency"), rc.get("cooking_method"),
                 _j(rc.get("avoid_methods", []))))
        _c().commit()
    return get_diet_plan(pid_)


def get_diet_plan(dpid: str) -> Optional[dict]:
    r = _row(_c().execute("SELECT * FROM diet_plans WHERE id=?", (dpid,)).fetchone())
    if r is None:
        return None
    r["goals"] = _loads(r.pop("goals_json"), [])
    r["pools"] = _loads(r.pop("pools_json"), {})
    r["recipes"] = []
    for rc in _rows(_c().execute(
            "SELECT * FROM recipes WHERE diet_plan_id=?", (dpid,))):
        rc["ingredients"] = _loads(rc.pop("ingredients_json"), [])
        rc["steps"] = _loads(rc.pop("steps_json"), [])
        rc["avoid_methods"] = _loads(rc.pop("avoid_methods_json"), [])
        r["recipes"].append(rc)
    return r


def get_recipe(rcid: str) -> Optional[dict]:
    rc = _row(_c().execute("SELECT * FROM recipes WHERE id=?", (rcid,)).fetchone())
    if rc is None:
        return None
    rc["ingredients"] = _loads(rc.pop("ingredients_json"), [])
    rc["steps"] = _loads(rc.pop("steps_json"), [])
    rc["avoid_methods"] = _loads(rc.pop("avoid_methods_json"), [])
    return rc


def active_diet_plan(profile_id: str) -> Optional[dict]:
    r = _c().execute("SELECT id FROM diet_plans WHERE profile_id=? AND "
                     "status='active' ORDER BY version DESC LIMIT 1",
                     (profile_id,)).fetchone()
    return get_diet_plan(r["id"]) if r else None


def list_diet_plans(profile_id: str) -> List[dict]:
    rows = _rows(_c().execute(
        "SELECT id,version,status,assessment_id,created_at,goals_json "
        "FROM diet_plans WHERE profile_id=? ORDER BY version DESC", (profile_id,)))
    for r in rows:
        r["goals"] = _loads(r.pop("goals_json"), [])
    return rows


def save_safety_check(profile_id: str, assessment_id: str | None, check_type: str,
                      inputs: dict, result: str, reasons: list,
                      missing: list) -> dict:
    with _lock:
        cid = _id("sc")
        _c().execute(
            "INSERT INTO safety_checks(id,profile_id,assessment_id,check_type,"
            "inputs_json,result,reasons_json,missing_json,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (cid, profile_id, assessment_id, check_type, _j(inputs), result,
             _j(reasons), _j(missing), now()))
        _c().commit()
    return get_safety_check(cid)


def get_safety_check(cid: str) -> Optional[dict]:
    r = _row(_c().execute("SELECT * FROM safety_checks WHERE id=?", (cid,)).fetchone())
    if r:
        r["inputs"] = _loads(r.pop("inputs_json"), {})
        r["reasons"] = _loads(r.pop("reasons_json"), [])
        r["missing"] = _loads(r.pop("missing_json"), [])
    return r


def save_tea_plan(profile_id: str, assessment_id: str, safety_check_id: str | None,
                  safety_status: str, plan: dict) -> dict:
    with _lock:
        _c().execute("UPDATE tea_plans SET status='superseded' "
                     "WHERE profile_id=? AND status='active'", (profile_id,))
        tid = _id("tp")
        ver = next_plan_version("tea_plans", profile_id)
        _c().execute(
            "INSERT INTO tea_plans(id,profile_id,assessment_id,safety_check_id,"
            "version,safety_status,plan_json,status,created_at)"
            " VALUES(?,?,?,?,?,?,?, 'active', ?)",
            (tid, profile_id, assessment_id, safety_check_id, ver,
             safety_status, _j(plan), now()))
        _c().commit()
    return get_tea_plan(tid)


def get_tea_plan(tid: str) -> Optional[dict]:
    r = _row(_c().execute("SELECT * FROM tea_plans WHERE id=?", (tid,)).fetchone())
    if r:
        r["plan"] = _loads(r.pop("plan_json"), {})
    return r


def active_tea_plan(profile_id: str) -> Optional[dict]:
    r = _c().execute("SELECT id FROM tea_plans WHERE profile_id=? AND "
                     "status='active' ORDER BY version DESC LIMIT 1",
                     (profile_id,)).fetchone()
    return get_tea_plan(r["id"]) if r else None


def list_tea_plans(profile_id: str) -> List[dict]:
    rows = _rows(_c().execute(
        "SELECT id,version,status,safety_status,assessment_id,created_at "
        "FROM tea_plans WHERE profile_id=? ORDER BY version DESC", (profile_id,)))
    return rows


# ================================================================ conversations
def create_conversation(profile_id: str, title: str | None = None) -> dict:
    with _lock:
        cid = _id("c")
        t = now()
        _c().execute(
            "INSERT INTO conversations(id,profile_id,title,created_at,updated_at)"
            " VALUES(?,?,?,?,?)", (cid, profile_id, title, t, t))
        _c().commit()
    return get_conversation(cid)


def get_conversation(cid: str) -> Optional[dict]:
    r = _row(_c().execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone())
    if r:
        r["state"] = _loads(r.pop("state_json"), {})
    return r


def update_conversation_state(cid: str, state: dict, title: str | None = None) -> None:
    with _lock:
        if title:
            _c().execute("UPDATE conversations SET state_json=?, title=?, "
                         "updated_at=? WHERE id=?", (_j(state), title, now(), cid))
        else:
            _c().execute("UPDATE conversations SET state_json=?, updated_at=? "
                         "WHERE id=?", (_j(state), now(), cid))
        _c().commit()


def list_conversations(profile_id: str, limit: int = 30) -> List[dict]:
    return _rows(_c().execute(
        "SELECT id,title,created_at,updated_at FROM conversations "
        "WHERE profile_id=? ORDER BY updated_at DESC LIMIT ?", (profile_id, limit)))


def add_message(cid: str, role: str, content: str, meta: dict | None = None) -> dict:
    with _lock:
        mid = _id("m")
        _c().execute(
            "INSERT INTO conv_messages(id,conversation_id,role,content,meta_json,"
            "created_at) VALUES(?,?,?,?,?,?)",
            (mid, cid, role, content, _j(meta or {}), now()))
        _c().execute("UPDATE conversations SET updated_at=? WHERE id=?", (now(), cid))
        _c().commit()
    r = _row(_c().execute("SELECT * FROM conv_messages WHERE id=?", (mid,)).fetchone())
    r["meta"] = _loads(r.pop("meta_json"), {})
    return r


def list_messages(cid: str) -> List[dict]:
    rows = _rows(_c().execute(
        "SELECT * FROM conv_messages WHERE conversation_id=? ORDER BY created_at",
        (cid,)))
    for r in rows:
        r["meta"] = _loads(r.pop("meta_json"), {})
    return rows


def add_event_candidate(cid: str, profile_id: str, content: str,
                        etype: str, event_date: str | None) -> dict:
    with _lock:
        eid = _id("ec")
        _c().execute(
            "INSERT INTO event_candidates(id,conversation_id,profile_id,event_date,"
            "type,content,status,created_at) VALUES(?,?,?,?,?,?, 'pending', ?)",
            (eid, cid, profile_id, event_date, etype, content, now()))
        _c().commit()
    return _row(_c().execute("SELECT * FROM event_candidates WHERE id=?",
                             (eid,)).fetchone())


def get_candidate(eid: str) -> Optional[dict]:
    return _row(_c().execute("SELECT * FROM event_candidates WHERE id=?",
                             (eid,)).fetchone())


def resolve_candidate(eid: str, status: str) -> Optional[dict]:
    with _lock:
        _c().execute("UPDATE event_candidates SET status=? WHERE id=?", (status, eid))
        _c().commit()
    return get_candidate(eid)


def pending_candidates(profile_id: str) -> List[dict]:
    return _rows(_c().execute(
        "SELECT * FROM event_candidates WHERE profile_id=? AND status='pending' "
        "ORDER BY created_at DESC", (profile_id,)))


# ================================================================ timeline
def timeline(profile_id: str) -> List[dict]:
    """按真实发生日期串联报告 / 健康事件 / 方案更新（F-REC-01）。"""
    items: List[dict] = []
    for r in list_reports(profile_id):
        if r["status"] not in ("ready", "needs_confirmation"):
            continue
        d = r.get("report_date") or (r["upload_time"] or "")[:10]
        items.append({"date": d, "kind": "report", "id": r["id"],
                      "title": _report_title(r),
                      "sub": f"提取指标 {r['stats'].get('observations', 0)} 项",
                      "date_confirmed": bool(r.get("date_confirmed"))})
    for e in list_events(profile_id):
        items.append({"date": e["event_date"], "kind": "event", "id": e["id"],
                      "title": e["content"][:40], "sub": _event_type_cn(e["type"])})
    for a in list_assessments(profile_id):
        if a["status"] != "completed":
            continue
        top = (a["summary"].get("top_titles") or ["健康分析"])[0]
        items.append({"date": a["created_at"][:10], "kind": "assessment",
                      "id": a["id"], "title": "健康分析更新",
                      "sub": f"当前第一关注：{top}"})
    for p in list_diet_plans(profile_id):
        items.append({"date": p["created_at"][:10], "kind": "plan", "id": p["id"],
                      "title": f"食补方案 V{p['version']}",
                      "sub": "、".join(g.get("label", "") for g in p["goals"][:2])})
    for t in list_tea_plans(profile_id):
        items.append({"date": t["created_at"][:10], "kind": "tea", "id": t["id"],
                      "title": f"药食同源茶饮 V{t['version']}",
                      "sub": _safety_cn(t["safety_status"])})
    items.sort(key=lambda x: (x["date"] or ""), reverse=True)
    return items


_RT_CN = {"lab_report": "检验报告", "ultrasound_report": "超声检查",
          "checkup": "体检报告", "other": "健康资料"}


def _report_title(r: dict) -> str:
    return _RT_CN.get(r.get("report_type") or "other", "健康资料")


def _event_type_cn(t: str) -> str:
    return {"symptom": "症状记录", "lifestyle": "生活方式",
            "medical": "医疗事件", "note": "健康记录"}.get(t, "健康事件")


def _safety_cn(s: str) -> str:
    return {"allow": "已通过安全检查", "require_info": "待补充安全信息",
            "block": "已安全拦截", "professional_review": "建议专业人员评估"}.get(s, s)
