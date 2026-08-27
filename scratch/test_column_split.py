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

SYSTEM_PROMPT = """你是专业的医疗化验单高保真视觉转录引擎。任务是准确转录图像中的真实文字，严禁任何推测。

核心转录准则：
1. 序号与行绝对绑定：化验单左侧印有序号（1~32）。请从序号 1 严格按顺序逐行识别到序号 32，绝不漏行、绝不串行。
2. 测定值与参考范围严格区分：
   - value_num 必须填入该行实际测得的结果数值（纯数字）；
   - 参考区间的上下限分别填入 ref_low 和 ref_high，绝不可把参考区间上下限当成测试值。
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

original = ImageOps.exif_transpose(Image.open(IMAGE_PATH)).convert("RGB")
width, height = original.size

# 左右双分栏切割（保留中间 6% 重叠，防止中缝字符切断）
mid = int(width * 0.51)
overlap = int(width * 0.05)
left_crop = original.crop((0, 0, mid + overlap, height))
right_crop = original.crop((mid - overlap, 0, width, height))

# 图像增强
left_crop = ImageEnhance.Sharpness(ImageOps.autocontrast(left_crop, cutoff=0.5)).enhance(1.3).convert("RGB")
right_crop = ImageEnhance.Sharpness(ImageOps.autocontrast(right_crop, cutoff=0.5)).enhance(1.3).convert("RGB")

content = [
    {"type": "text", "text": "图片 1：化验单【左半栏】（包含左侧序号 1~16 的所有化验项目）。请按 1~16 自上而下逐行识别："},
    image_to_block(left_crop),
    {"type": "text", "text": "图片 2：化验单【右半栏】（包含右侧序号 17~32 的所有化验项目）。请按 17~32 自上而下逐行识别："},
    image_to_block(right_crop),
    {"type": "text", "text": "图片 0：化验单完整原图，用于核实患者信息与日期："},
    image_to_block(original),
    {"type": "text", "text": "请将左栏序号 1~16 和右栏序号 17~32 整合为完整的 32 项 observations 数组，仅输出严格的 JSON 对象。"}
]

request_data = {
    "model": "claude-sonnet-4-6",
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

print("Calling model with Left/Right Column Split...")
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

print(f"\n================ 左右栏精准提取结果 ({len(obs)} 项) ================")
for item in obs:
    seq = item.get("seq", "-")
    name = item.get("display") or item.get("code")
    val = item.get("value_num")
    u = item.get("unit") or ""
    low, high = item.get("ref_low"), item.get("ref_high")
    flag = item.get("abnormal_flag") or ""
    print(f"{seq:>2} | {name:<16}: {str(val):<6} {u:<8} (ref: [{low}, {high}]) flag={flag}")
