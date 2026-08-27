import os
import io
import time
import json
import base64
import urllib.request
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance

IMAGE_PATH = Path("data/uploads/972936fa_eda492d63643ee2dfbb320e316949436.jpg")
URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.openasi.bitmiracle.cn") + "/v1/messages"
API_KEY = os.getenv("ANTHROPIC_API_KEY", "openasi-Nh2R5vLXgtlXC0dy1stQ7H5zoAUJkcVU0ol0Hw1gQNE")

SYSTEM_PROMPT = """你是专业的医疗化验单高保真视觉转录引擎。任务是准确转录图像中的真实文字，严禁任何推测或伪造。

核心转录准则：
1. 序号与行锚定：化验单左侧印有序号。请从上到下按序号顺序逐行提取，确保序号、项目名称、测定值、单位、参考区间来自同一行，绝不漏行、绝不串行。
2. 测定值与参考范围严格区分：
   - value_num 必须填入该行实际测得的结果数值（如 4.07, 139, 101, 2.29, 1.17, 2.3, 10.5, 5.4, 5.1, 74.1, 48.0, 26.1, 1.8, 94, 59, 0.63, 103, 36, 250, 5.14, 2.54, 56, 330, 4.79, 2.13, 0.98, 2.08, 77, 12, 28, 47, 27.8 等实际测量值）；
   - 参考区间（如 3.50-5.30）上下限分别填入 ref_low 和 ref_high，绝不可把参考区间上下限当成测试值。
3. 异常标记：单据上标注 ↑ 或 H 记 "H"，↓ 或 L 记 "L"，无标注或在参考范围内记 "N"。
4. 无法确认时：value_num 填 null，并把原始文字保存在 raw_line 中。
5. 仅输出一个标准的 JSON 对象，格式为：
{
  "document_type": "lab_report",
  "exam_date": "YYYY-MM-DD",
  "observations": [
    {
      "seq": 1,
      "display": "中文项目名",
      "code": "英文缩写",
      "raw_line": "该行原始文字",
      "value_num": 4.07,
      "unit": "mmol/L",
      "ref_low": 3.50,
      "ref_high": 5.30,
      "abnormal_flag": "N"
    }
  ]
}
"""

def resize_for_model(image, limit=1568):
    image = image.copy()
    image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
    return image

def image_to_block(image):
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": encoded
        }
    }

def build_image_content(path, bands=3, overlap_ratio=0.12):
    original = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    width, height = original.size
    content = []

    # 图片 0：整页概览（全局版式与上下文）
    content.extend([
        {"type": "text", "text": "图片 0：化验单整页全貌，用于确认多栏排版与项目总览。"},
        image_to_block(resize_for_model(original))
    ])

    # 局部重叠高清切片（保留微小字符、小数点、细箭头细节）
    band_height = height / bands
    overlap = int(band_height * overlap_ratio)

    for i in range(bands):
        top = max(0, int(i * band_height) - overlap)
        bottom = min(height, int((i + 1) * band_height) + overlap)
        crop = original.crop((0, top, width, bottom))
        crop = ImageOps.autocontrast(crop, cutoff=0.5)
        crop = ImageEnhance.Sharpness(crop).enhance(1.3).convert("RGB")
        crop = resize_for_model(crop)
        content.extend([
            {"type": "text", "text": f"图片 {i + 1}：化验单第 {i + 1}/{bands} 个局部高清切片。"},
            image_to_block(crop)
        ])

    content.append({
        "type": "text",
        "text": "请结合整页与局部切片，按序号自上而下提取所有化验项目。仅输出符合 schema 的 JSON。"
    })
    return content

print("Building multi-band content...")
content = build_image_content(IMAGE_PATH, bands=3)

request_data = {
    "model": "claude-opus-4-6",
    "max_tokens": 4000,
    "temperature": 0,
    "system": SYSTEM_PROMPT,
    "messages": [{
        "role": "user",
        "content": content
    }]
}

headers = {
    "x-api-key": API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
}

print("Calling model with multi-band high-res slicing...")
t0 = time.time()
req = urllib.request.Request(URL, data=json.dumps(request_data).encode("utf-8"), headers=headers, method="POST")
with urllib.request.urlopen(req, timeout=90) as response:
    result = json.loads(response.read().decode("utf-8"))

elapsed = time.time() - t0
print(f"Model returned in {elapsed:.2f}s!")

text = result["content"][0]["text"]
s = text[text.find("{"):text.rfind("}")+1]
parsed = json.loads(s)
obs = parsed.get("observations", [])

print(f"\n================ 提取结果 ({len(obs)} 项) ================")
for item in obs:
    seq = item.get("seq", "-")
    name = item.get("display") or item.get("code")
    val = item.get("value_num")
    u = item.get("unit") or ""
    low, high = item.get("ref_low"), item.get("ref_high")
    flag = item.get("abnormal_flag") or ""
    print(f"{seq:>2} | {name:<16}: {str(val):<6} {u:<8} (ref: [{low}, {high}]) flag={flag}")
