"""演示档案播种 —— 规格书 §12「演示稳定性」与 AC-20 的固定演示流程。

创建演示用户与档案，并按真实历史日期写入三年三份体检数据：
  2024-03-12 企业体检 → 2025-04-02 医院检验 → 2026-03-20 年度体检
覆盖：ALT 持续上升序列（42→58→76→103，对应方案书 §8.3 示例）、
血脂/尿酸/血糖异常、脂肪肝超声所见、既往健康事件。

演示账号：demo / demo123456
"""
from __future__ import annotations

from . import auth
from . import repository as repo
from .standardize.registry import get_registry, grade_value

_REPORTS = [
    {"date": "2024-03-12", "type": "checkup", "file": "2024年度企业体检.pdf",
     "obs": [("ALT", 42, "U/L"), ("AST", 31, "U/L"), ("GGT", 58, "U/L"),
             ("TC", 5.4, "mmol/L"), ("TG", 1.9, "mmol/L"),
             ("LDLC", 3.3, "mmol/L"), ("HDLC", 1.1, "mmol/L"),
             ("GLU", 5.7, "mmol/L"), ("UA", 428, "umol/L"),
             ("HGB", 152, "g/L"), ("BMI", 26.1, "kg/m^2")],
     "findings": []},
    {"date": "2025-04-02", "type": "lab_report", "file": "2025肝功能复查.jpg",
     "obs": [("ALT", 58, "U/L"), ("AST", 42, "U/L"), ("GGT", 84, "U/L"),
             ("TG", 2.4, "mmol/L"), ("GLU", 6.1, "mmol/L"),
             ("UA", 455, "umol/L")],
     "findings": [("肝脏", "肝实质回声增强、致密，符合轻-中度脂肪肝声像", ["fatty"])]},
    {"date": "2026-03-20", "type": "checkup", "file": "2026年度体检.pdf",
     "obs": [("ALT", 76, "U/L"), ("AST", 55, "U/L"), ("GGT", 112, "U/L"),
             ("TC", 5.9, "mmol/L"), ("TG", 2.9, "mmol/L"),
             ("LDLC", 3.7, "mmol/L"), ("HDLC", 0.98, "mmol/L"),
             ("GLU", 6.4, "mmol/L"), ("HBA1C", 6.0, "%"),
             ("UA", 487, "umol/L"), ("HGB", 149, "g/L"),
             ("BMI", 27.3, "kg/m^2")],
     "findings": [("肝脏", "脂肪肝声像较前相仿，肝内未见占位", ["fatty"])]},
]


def seed() -> dict:
    """幂等：demo 用户已存在则直接返回其首个档案。"""
    repo.init()
    u = repo.get_user_by_name("demo")
    if u:
        ps = repo.list_profiles(u["id"])
        if ps:
            return {"user": "demo", "profile_id": ps[0]["id"], "created": False}
    else:
        u = repo.create_user("demo", auth.hash_password("demo123456"),
                             "user", "演示用户")
    p = repo.create_profile(u["id"], "李国栋", "male", "1978-06-15")
    repo.update_profile(p["id"], {
        "height_cm": 173, "weight_kg": 81.5,
        "allergies": [], "medications": [],
        "conditions": [], "smoking": "none", "alcohol": "occasional"})

    registry = get_registry()
    for spec in _REPORTS:
        r = repo.create_report(p["id"], spec["file"], stored_path=None,
                               report_type=spec["type"])
        n = 0
        for code, value, unit in spec["obs"]:
            meta = registry.get(code)
            cv = meta.convert_to_canonical(value, unit) if meta else None
            g = grade_value(meta, cv, sex="M", age=46) if (meta and cv is not None) else 0
            iv = meta.match_interval("M", 46) if meta else None
            repo.add_observation(
                p["id"], r["id"], spec["date"], code=code,
                original_name=meta.name_cn if meta else code,
                value_num=value, unit=unit, canonical_value=cv,
                canonical_unit=meta.canonical_unit if meta else unit,
                ref_low=iv.lower if iv else None,
                ref_high=iv.upper if iv else None,
                flag="H" if g > 0 else ("L" if g < 0 else "N"),
                grade=g, match_method="exact", confidence=1.0)
            n += 1
        for organ, desc, flags in spec["findings"]:
            repo.add_finding(p["id"], r["id"], organ, desc, flags, spec["date"])
        repo.set_report_status(
            r["id"], "ready", report_type=spec["type"],
            report_date=spec["date"], date_confirmed=1, engine="demo_seed",
            stats={"observations": n, "matched": n, "low_confidence": 0,
                   "findings": len(spec["findings"])})

    repo.add_event(p["id"], "2025-11-08", "symptom",
                   "近两周晚间右上腹隐胀，饮酒后明显", "user_entry")
    repo.add_event(p["id"], "2026-01-05", "lifestyle",
                   "开始每周三次快走 40 分钟", "user_entry")
    return {"user": "demo", "profile_id": p["id"], "created": True}


if __name__ == "__main__":
    print(seed())
