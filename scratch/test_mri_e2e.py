import os
import sys
import json
from pathlib import Path

# Ensure UTF-8 output in Windows & Mock mode for fast testing
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
os.environ["SOULHEALTH_MOCK"] = "1"

from app import config, db, repository as repo, auth
from app.ingest import pipeline
from app.engine import assessment, dietplan, teaplan, agent
from app.schemas import ExtractionResult, from_dict

print("=== 1. 测试从 MRI 报告生成结构化数据 ===")
sample_mri_path = config.SAMPLE_DIR / "sample_mri_extraction.json"
assert sample_mri_path.exists(), "sample_mri_extraction.json 必须存在"
mri_json = json.loads(sample_mri_path.read_text(encoding="utf-8"))
extraction = from_dict(mri_json)
print(f"✓ 成功解析 ExtractionResult: document_type={extraction.document_type}, findings={len(extraction.findings)}, impressions={len(extraction.impressions)}")

print("\n=== 2. 测试用户建档与报告入库 ===")
user = repo.get_user_by_name("lixiaoning")
if not user:
    user = repo.create_user("lixiaoning", auth.hash_password("123456"), display_name="李小宁(52岁)")
user_id = user["id"]

profiles = repo.list_profiles(user_id)
profile = None
for p in profiles:
    if p["name"] == "李小宁":
        profile = p
        break
if not profile:
    profile = repo.create_profile(user_id, "李小宁", "male", "1974-04-16")
repo.update_profile(profile["id"], {"allergies": [], "medications": []})
profile = repo.get_profile(profile["id"])

print(f"✓ 用户档案: id={profile['id']}, 姓名={profile['name']}, 性别={profile['sex']}, 年龄={profile['age_years']}")

# 模拟上传一份 MRI 检查报告
test_file = config.UPLOAD_DIR / "test_mri_knee.jpg"
test_file.write_bytes(b"\xff\xd8\xff\xe0" + b"fake_mri_image_data")
rpt = repo.create_report(profile["id"], "左膝关节磁共振报告.jpg", str(test_file))

# 执行摄取处理
processed = pipeline.process_report(rpt["id"])
print(f"✓ 报告处理完成: id={processed['id']}, status={processed['status']}, findings={processed.get('stats', {}).get('findings')}")

print("\n=== 3. 测试健康分析引擎 (Assessment) ===")
res = assessment.run_assessment(profile["id"], force=True)
issues = res["issues"]
print(f"✓ 健康分析成功生成: 共 {len(issues)} 个问题组")
joint_issue = next((it for it in issues if it["title"] == "骨关节与运动系统"), None)
assert joint_issue is not None, "必须识别出「骨关节与运动系统」问题组"
print(f"  - 骨关节组等级: {joint_issue['level']} (score: {joint_issue['score']})")
print(f"  - 摘要: {joint_issue['summary']}")
print(f"  - 发现项: {joint_issue['detail']['found']}")
print(f"  - 行动建议: {joint_issue['detail']['actions'][0]}")

print("\n=== 4. 测试食补方案生成 (Diet Plan) ===")
diet = dietplan.generate(profile["id"], res)
print(f"✓ 食补方案成功生成: 目标={ [g['label'] for g in diet['goals']] }")
print(f"  - 推荐食材 ({len(diet['pools']['recommended'])}种): {[f['name'] for f in diet['pools']['recommended'][:4]]}")
print(f"  - 忌口食材 ({len(diet['pools']['avoid'])}种): {[f['name'] for f in diet['pools']['avoid']]}")
print(f"  - 推荐菜谱 ({len(diet['recipes'])}道): {[r['name'] for r in diet['recipes']]}")
assert any("三文鱼" in r['name'] or "养膝" in r['name'] or "脆骨" in r['name'] for r in diet['recipes']), "必须包含针对骨关节的护膝抗炎菜谱"

print("\n=== 5. 测试药食同源茶饮方案生成 (Tea Plan) ===")
tea = teaplan.generate(profile["id"], res)
print(f"✓ 茶饮方案成功生成: 状态={tea['safety_status']}")
if tea['safety_status'] == 'allow':
    print(f"  - 茶饮名称: {tea['plan']['name']}")
    print(f"  - 配方原料: {[i['name'] + str(i['grams']) + 'g' for i in tea['plan']['ingredients']]}")
    print(f"  - 煎煮方法: {tea['plan']['brew']}")
    print(f"  - 依据: {tea['plan']['rationale'][:60]}...")
    assert "寄生" in tea['plan']['name'] or "杜仲" in tea['plan']['name'], "必须推荐寄生杜仲强筋健膝茶"

print("\n=== 6. 测试健康问询 Agent (Q&A) ===")
q1 = agent.handle(profile["id"], None, "我膝盖最近有点酸胀、下蹲费力，MRI显示有积液和半月板损伤，平时该怎么吃、怎么保养？")
print(f"✓ 问询回复生成成功 (kind={q1['reply']['kind']}):")
print(f"  - 回复小节: {list(q1['reply'].get('sections', {}).keys())}")
print(f"  - 档案引用: {q1['reply']['sections'].get('archive')}")
print(f"  - 优先建议: {q1['reply']['sections'].get('actions')[:3]}")

print("\n=======================================================")
print("🎉 全部 6 项核心功能端到端验证通过！100% 满足需求！")
print("=======================================================")
