"""
端到端验证：多份体检报告时序录入 + DRP 概率预测 + SHAP 归因 + 临床比值 + 风险走势轨迹
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import repository as repo
from app.engine import assessment
from app.engine.prediction import compute_risk_prediction, compute_risk_timeline

def run_full_drp_test():
    user = repo.create_user("13800000001", "pass123")
    profile = repo.create_profile(user["id"], "王建国", "male", "1972-04-12", height_cm=175, weight_kg=82)
    pid = profile["id"]
    print(f"1. 创建测试用户: {profile['name']} (id={pid}, age={profile['age_years']})")

    # 录入 2 份历史化验单
    # 第 1 份：2025-05-10
    r1 = repo.create_report(pid, "lab_report", "report_20250510.jpg", "/dummy/path1")
    repo.set_report_status(r1["id"], "ready", report_date="2025-05-10", date_confirmed=1)
    repo.add_observation(pid, r1["id"], "2025-05-10", code="TG", original_name="甘油三酯", value_num=2.2, unit="mmol/L", canonical_value=2.2, canonical_unit="mmol/L")
    repo.add_observation(pid, r1["id"], "2025-05-10", code="ALT", original_name="丙氨酸转氨酶", value_num=45.0, unit="U/L", canonical_value=45.0, canonical_unit="U/L")
    repo.add_observation(pid, r1["id"], "2025-05-10", code="GLU", original_name="空腹血糖", value_num=5.8, unit="mmol/L", canonical_value=5.8, canonical_unit="mmol/L")
    repo.add_observation(pid, r1["id"], "2025-05-10", code="CREA", original_name="肌酐", value_num=82.0, unit="umol/L", canonical_value=82.0, canonical_unit="umol/L")

    # 第 2 份：2026-08-20
    r2 = repo.create_report(pid, "lab_report", "report_20260820.jpg", "/dummy/path2")
    repo.set_report_status(r2["id"], "ready", report_date="2026-08-20", date_confirmed=1)
    repo.add_observation(pid, r2["id"], "2026-08-20", code="TG", original_name="甘油三酯", value_num=3.4, unit="mmol/L", canonical_value=3.4, canonical_unit="mmol/L")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="ALT", original_name="丙氨酸转氨酶", value_num=72.0, unit="U/L", canonical_value=72.0, canonical_unit="U/L")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="AST", original_name="天门冬氨酸转氨酶", value_num=48.0, unit="U/L", canonical_value=48.0, canonical_unit="U/L")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="GLU", original_name="空腹血糖", value_num=7.1, unit="mmol/L", canonical_value=7.1, canonical_unit="mmol/L")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="HBA1C", original_name="糖化血红蛋白", value_num=6.7, unit="%", canonical_value=6.7, canonical_unit="%")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="SBP", original_name="收缩压", value_num=145.0, unit="mmHg", canonical_value=145.0, canonical_unit="mmHg")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="DBP", original_name="舒张压", value_num=92.0, unit="mmHg", canonical_value=92.0, canonical_unit="mmHg")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="UA", original_name="血尿酸", value_num=465.0, unit="umol/L", canonical_value=465.0, canonical_unit="umol/L")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="CREA", original_name="肌酐", value_num=88.0, unit="umol/L", canonical_value=88.0, canonical_unit="umol/L")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="HDLC", original_name="高密度脂蛋白", value_num=0.92, unit="mmol/L", canonical_value=0.92, canonical_unit="mmol/L")
    repo.add_observation(pid, r2["id"], "2026-08-20", code="PLT", original_name="血小板", value_num=220.0, unit="10^9/L", canonical_value=220.0, canonical_unit="10^9/L")

    print("2. 成功录入 2 份历史化验单（2025-05-10 与 2026-08-20）")

    # 运行健康分析
    res = assessment.run_assessment(pid, force=True)
    print("3. 健康分析生成成功:")
    print(f"   - 问题组数: {len(res['issues'])}")
    pred = res.get("prediction")
    assert pred is not None, "DRP prediction must not be None"
    print(f"   - DRP 1Y/3Y/5Y 概率:")
    for h in pred["horizons"]:
        print(f"     * {h['horizon_label']}: {h['percentage']} ({h['tier_cn']}) | {h['follow_up_advice']}")

    print(f"   - Top 风险推高/降低驱动因子:")
    for d in pred["top_drivers"]:
        print(f"     * [{d['direction_cn']}] {d['name']}: {d['reason']}")

    print(f"   - 临床衍生比值 ({len(pred['ratios'])} 项):")
    for r in pred["ratios"]:
        print(f"     * {r['name']} = {r['value']} {r['unit']} ({r['interpretation']})")

    # 检验时序轨迹
    timeline = compute_risk_timeline(pid)
    print(f"\n4. 风险演进轨迹生成成功:")
    print(f"   - 历史时间点数: {len(timeline['history'])}")
    for hp in timeline["history"]:
        print(f"     * 历史点 {hp['date']}: {hp['percentage']} ({hp['tier_cn']})")
    print(f"   - 未来预测点数: {len(timeline['future'])}")
    for fp in timeline["future"]:
        print(f"     * 未来点 {fp['date']}: {fp.get('percentage', '起点')} ({fp.get('tier_cn', '')})")

    print("\n=======================================================")
    print("[PASS] DRP 端到端完整多报告时序与预测全链路验证通过！")
    print("=======================================================")

if __name__ == "__main__":
    run_full_drp_test()
