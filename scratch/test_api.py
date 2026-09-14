# -*- coding: utf-8 -*-
"""端到端测试：登录 → 上传图片 → 等处理 → 看结果"""
import sys, io, os, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import httpx

BASE = "http://localhost:8002"

# 1. 登录
print("=" * 50)
print("[1] 登录...")
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "demo", "password": "demo123456"}, timeout=10)
assert r.status_code == 200, f"登录失败: {r.status_code} {r.text}"
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"  OK, token={token[:20]}...")

# 2. 获取 profile
print("\n[2] 获取档案...")
r = httpx.get(f"{BASE}/api/profiles", headers=headers, timeout=10)
profiles = r.json().get("items", r.json()) if isinstance(r.json(), dict) else r.json()
pid = profiles[0]["id"] if profiles else None
print(f"  Profile: {pid}")
assert pid, "没有档案!"

# 3. 创建一张测试图片（模拟化验单）
print("\n[3] 创建测试图片...")
try:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(img)
    # 画一些文字模拟化验单
    lines = [
        "检验报告单",
        "姓名: 张三   性别: 男   年龄: 54",
        "检验日期: 2025-06-15",
        "",
        "项目名称          结果    单位     参考范围",
        "─" * 50,
        "谷丙转氨酶(ALT)    45     U/L      0-40     ↑",
        "谷草转氨酶(AST)    32     U/L      0-40",
        "总胆红素(TBIL)     15.2   umol/L   0-26",
        "直接胆红素(DBIL)   5.1    umol/L   0-8",
        "总蛋白(TP)         72     g/L      65-85",
        "白蛋白(ALB)        45     g/L      40-55",
        "球蛋白(GLB)        27     g/L      20-40",
        "尿酸(UA)           520    umol/L   208-428  ↑",
        "空腹血糖(GLU)      6.8    mmol/L   3.9-6.1  ↑",
        "甘油三酯(TG)       2.3    mmol/L   0-1.7    ↑",
        "总胆固醇(TC)       5.8    mmol/L   0-5.2    ↑",
        "高密度脂蛋白(HDL-C) 1.1   mmol/L   1.0-1.5",
        "低密度脂蛋白(LDL-C) 3.8   mmol/L   0-3.4    ↑",
    ]
    y = 20
    for line in lines:
        draw.text((30, y), line, fill="black")
        y += 35
    
    test_img_path = os.path.join(os.path.dirname(__file__), "test_lab_report.jpg")
    img.save(test_img_path, "JPEG", quality=90)
    print(f"  已生成测试图片: {test_img_path}")
except ImportError:
    print("  PIL 不可用，尝试用现有样本文件...")
    test_img_path = None

# 4. 上传
print("\n[4] 上传文件...")
if test_img_path and os.path.exists(test_img_path):
    with open(test_img_path, "rb") as f:
        files = {"files": ("test_lab_report.jpg", f, "image/jpeg")}
        r = httpx.post(
            f"{BASE}/api/reports/upload",
            headers=headers,
            data={"profile_id": pid},
            files=files,
            timeout=120
        )
else:
    print("  没有测试文件可上传!")
    sys.exit(1)

print(f"  Status: {r.status_code}")
if r.status_code != 200:
    print(f"  FAIL: {r.text[:500]}")
    sys.exit(1)

upload_result = r.json()
print(f"  上传结果: {json.dumps(upload_result, ensure_ascii=False, indent=2)[:800]}")

# 5. 检查报告状态
report_ids = [rr["id"] for rr in upload_result.get("reports", [])]
if not report_ids:
    print("\n  没有返回 report id!")
    sys.exit(1)

rid = report_ids[0]
print(f"\n[5] 检查报告状态: {rid}")
for i in range(10):
    time.sleep(2)
    r = httpx.get(f"{BASE}/api/reports/{rid}", headers=headers, timeout=10)
    if r.status_code == 200:
        rpt = r.json()
        status = rpt.get("status")
        print(f"  [{i+1}] status={status}")
        if status in ("ready", "needs_confirmation", "failed"):
            print(f"\n  最终状态: {status}")
            if status == "failed":
                print(f"  错误: {rpt.get('error', '未知')}")
            elif status in ("ready", "needs_confirmation"):
                stats = rpt.get("stats", {})
                print(f"  识别指标数: {stats.get('observations', 0)}")
                print(f"  匹配指标数: {stats.get('matched', 0)}")
            break
    else:
        print(f"  查询失败: {r.status_code}")

print("\n测试完毕!")
