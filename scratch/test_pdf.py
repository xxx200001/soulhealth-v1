# -*- coding: utf-8 -*-
"""测试 PDF 上传识别"""
import sys, io, os, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import httpx

BASE = "http://localhost:8002"

# 登录
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "demo", "password": "demo123456"}, timeout=10)
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}
pid = httpx.get(f"{BASE}/api/profiles", headers=headers, timeout=10).json()["items"][0]["id"]
print(f"Profile: {pid}")

# 生成测试 PDF
print("生成测试 PDF...")
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdf_path = os.path.join(os.path.dirname(__file__), "test_lab.pdf")
c = canvas.Canvas(pdf_path, pagesize=A4)
w, h = A4

# 尝试注册中文字体
try:
    for fp in [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simsun.ttc"]:
        if os.path.exists(fp):
            pdfmetrics.registerFont(TTFont("CN", fp))
            c.setFont("CN", 14)
            break
    else:
        c.setFont("Helvetica", 12)
except:
    c.setFont("Helvetica", 12)

y = h - 50
lines = [
    ("检验报告单", 18),
    ("", 12),
    ("姓名: 李四   性别: 女   年龄: 45岁", 12),
    ("送检科室: 体检中心   检验日期: 2025-08-20", 12),
    ("", 12),
    ("项目名称              结果      单位       参考范围", 11),
    ("━" * 60, 10),
    ("丙氨酸氨基转移酶(ALT)   38       U/L        0-40", 11),
    ("天冬氨酸氨基转移酶(AST)  28       U/L        0-40", 11),
    ("总胆红素(TBIL)          12.5     umol/L     0-26", 11),
    ("白蛋白(ALB)             42       g/L        40-55", 11),
    ("球蛋白(GLB)             30       g/L        20-40", 11),
    ("尿酸(UA)                480      umol/L     155-357  ↑", 11),
    ("空腹血糖(GLU)           7.2      mmol/L     3.9-6.1  ↑", 11),
    ("甘油三酯(TG)            1.9      mmol/L     0-1.7    ↑", 11),
    ("总胆固醇(TC)            5.5      mmol/L     0-5.2    ↑", 11),
    ("高密度脂蛋白(HDL-C)     1.3      mmol/L     1.0-1.5", 11),
    ("低密度脂蛋白(LDL-C)     3.2      mmol/L     0-3.4", 11),
    ("肌酐(Cr)                68       umol/L     41-73", 11),
    ("尿素氮(BUN)             5.8      mmol/L     2.6-7.5", 11),
]
for text, size in lines:
    try:
        c.setFont("CN", size)
    except:
        c.setFont("Helvetica", size)
    c.drawString(40, y, text)
    y -= size + 8

c.save()
print(f"  PDF: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")

# 上传
print("\n上传 PDF...")
with open(pdf_path, "rb") as f:
    r = httpx.post(
        f"{BASE}/api/reports/upload",
        headers=headers,
        data={"profile_id": pid},
        files={"files": ("test_lab.pdf", f, "application/pdf")},
        timeout=180
    )

print(f"Status: {r.status_code}")
if r.status_code == 200:
    result = r.json()
    rpt = result["reports"][0]
    print(f"状态: {rpt['status']}")
    print(f"指标数: {rpt['stats'].get('observations', 0)}")
    print(f"匹配数: {rpt['stats'].get('matched', 0)}")
    if rpt["status"] == "failed":
        print(f"错误: {rpt.get('error')}")
    else:
        print("PDF 识别成功!")
else:
    print(f"失败: {r.text[:500]}")
