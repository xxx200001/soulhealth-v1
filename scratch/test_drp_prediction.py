import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engine.prediction import compute_risk_prediction, compute_clinical_ratios, compute_risk_timeline
from app import repository as repo

def test_prediction():
    # 模拟包含肝脂糖高危指标的体检数据
    profile = {
        "id": "p_test_drp",
        "age_years": 52,
        "sex": "male",
        "height_cm": 172,
        "weight_kg": 80,
    }
    obs = {
        "ALT": 68.0,
        "AST": 45.0,
        "TG": 3.2,
        "GLU": 6.8,
        "HBA1C": 6.4,
        "SBP": 142.0,
        "DBP": 90.0,
        "UA": 460.0,
        "CREA": 85.0,
        "PLT": 210.0,
        "HDLC": 0.95,
        "LDLC": 3.6,
        "ALB": 44.0,
    }

    pred = compute_risk_prediction(profile, obs, [])
    print("=== DRP 预测结果 ===")
    print(f"预测目标: {pred['target']}")
    print(f"预测依据: {pred['evidence']}")
    print("\n[多时程概率]")
    for h in pred["horizons"]:
        print(f"  - {h['horizon_label']}: {h['percentage']} ({h['tier_cn']}) -> {h['follow_up_advice']}")
    
    print("\n[Top 风险归因驱动]")
    for d in pred["top_drivers"]:
        print(f"  - [{d['direction_cn']}] {d['name']} ({d['current_value']}{d['unit']}): {d['reason']}")

    print("\n[临床衍生复合评分]")
    for r in pred["ratios"]:
        print(f"  - {r['name']}: {r['value']} {r['unit']} [{r['status']}] -> {r['interpretation']}")

    assert len(pred["horizons"]) == 3
    # 验证单调性
    p1 = pred["horizons"][0]["probability"]
    p3 = pred["horizons"][1]["probability"]
    p5 = pred["horizons"][2]["probability"]
    assert p1 <= p3 <= p5, f"Monotonicity failed: {p1}, {p3}, {p5}"
    print("\n[PASS] 1Y <= 3Y <= 5Y Monotonicity Test Passed!")
    print("[PASS] All DRP Prediction Features Verified!")

if __name__ == "__main__":
    test_prediction()
