"""视觉 LLM 抽取引擎：图片/PDF → 结构化 JSON（默认 Claude，可换任何视觉模型）。

要点：
- MOCK 模式（显式 SOULHEALTH_MOCK=1）：按文件名路由本地样例，离线可完整演示。
- 真实模式：前置校验（非空 / 魔数嗅探真实格式 / 体积上限）→ base64 发送 →
  严格 JSON 输出；schema 校验失败时把错误回喂模型自修正一次（共 2 次尝试）。
- **多页 PDF 逐页调用 API**：每页独立发送，合并结果，彻底消除超时风险。
- **智能方向检测**：EXIF 回正 + 横拍自动旋转，确保文字方向正确。
- **影像增强预处理**：X光/CT/MRI 暗背景照片自动增强对比度与锐度。
- **"模型没收到图片"是一类独立故障**：当模型答复表明它未看到任何图像时，
  立刻中止并抛出可执行的诊断信息（而不是含糊的"未通过校验"），并提示用
  /api/selftest/vision 自检。常见成因：所配模型不支持视觉、网关/代理剥离了
  非文本块、密钥指向纯文本端点。
- anthropic 为惰性导入：不装该包也能跑 MOCK 全流程。
"""
from __future__ import annotations

import base64
import json
import re
import struct
import time
import threading
import zlib
from pathlib import Path
from typing import Optional, Tuple

from .. import config
from ..schemas import ExtractionResult, from_dict
from .prompts import EXTRACTION_SYSTEM, extraction_user_prompt, repair_prompt

_LAB_NAME_HINTS = ("lab", "blood", "化验", "肝功", "血", "生化", "检验")
_METABOLIC_HINTS = ("糖", "血脂", "代谢", "尿酸", "metab", "glu")
_MRI_JOINT_HINTS = ("mri", "knee", "膝", "关节", "核磁", "磁共振", "ct", "骨", "半月板", "韧带", "脊柱", "腰椎", "颈椎")

# Anthropic 单图上限约 5MB（base64 后），留出 33% 膨胀余量
MAX_IMAGE_BYTES = 3_600_000
MAX_PDF_BYTES = 50_000_000  # 50MB，支持大体检报告 PDF
MAX_PDF_PAGES = 15  # 支持大体检报告（常见 10~12 页）

# 全局并发锁：限制同时进行的 API 调用数，防止多文件同时上传时触发限流
_api_semaphore = threading.Semaphore(2)

# 魔数 → media_type（不信任扩展名：手机改名、截图另存都可能对不上）
_MAGIC: Tuple[Tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF", "application/pdf"),
)

# 模型表示"我没看到图片"的典型说法（仅在 JSON 解析失败后才做此判断）
_NO_IMAGE_PATTERNS = [
    r"没有(任何)?图片", r"未(收到|提供|附上|看到)(任何)?图片", r"看不到(任何)?图片",
    r"没有图像", r"未见图片", r"只有文字", r"没有可抽取的内容", r"输入缺失",
    r"图片(未|没有)(上传|附加)", r"no image", r"没有单据", r"未附(带)?图",
    r"(cannot|can't|couldn't|unable to)\s+(see|view|access|find)[^.]{0,24}image",
]
_NO_IMAGE_RE = [re.compile(p, re.I) for p in _NO_IMAGE_PATTERNS]


class ExtractionError(RuntimeError):
    pass


class VisionInputError(ExtractionError):
    """文件本身不可用（空文件 / 格式不支持 / 超出体积上限）。"""


class VisionNotSeeingImageError(ExtractionError):
    """请求已送达且模型有回复，但模型表示未收到图像——通常是模型或网关问题。"""


# ---------------------------------------------------------------- MOCK

def _load_mock(file_path: Path) -> ExtractionResult:
    name = file_path.name.lower()
    if any(h in name for h in _MRI_JOINT_HINTS):
        sample = "sample_mri_extraction.json"
    elif any(h in name for h in _METABOLIC_HINTS):
        sample = "sample_metabolic_extraction.json"   # 第二病种：糖脂/尿酸
    elif any(h in name for h in _LAB_NAME_HINTS):
        sample = "sample_lab_extraction.json"
    else:
        sample = "sample_ultrasound_extraction.json"
    data = json.loads((config.SAMPLE_DIR / sample).read_text(encoding="utf-8"))
    data["engine"] = "mock"
    return from_dict(data)


# ---------------------------------------------------------------- 工具

def _strip_to_json(text: str) -> str:
    """剥掉可能出现的 ```json 围栏，截取首个 { 到最后一个 }。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"输出中未找到 JSON 对象：{(text or '')[:120]!r}...")
    return t[start:end + 1]


def _looks_like_no_image(text: str) -> bool:
    return any(p.search(text or "") for p in _NO_IMAGE_RE)


def sniff_media_type(data: bytes, file_path: Path) -> Optional[str]:
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    # 魔数不识别时退回扩展名（少数被处理过的图片会丢头部特征）
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp", ".gif": "image/gif",
            ".pdf": "application/pdf"}.get(file_path.suffix.lower())


# ---------------------------------------------------------------- 图像智能预处理

def _auto_orient(im):
    """智能方向检测：如果图片明显是横拍（宽 >> 高），自动旋转 90° 使文字变正。
    
    判定逻辑：宽 > 高 × 1.5 时，认为是横拍的竖向文档，逆时针旋转 90°。
    对于化验单/体检报告这类竖向文档，这个策略非常有效。
    """
    try:
        from PIL import Image
        w, h = im.size
        # 宽高比 > 1.5 说明横拍了竖向文档
        if w > h * 1.5:
            im = im.transpose(Image.Transpose.ROTATE_90)
    except Exception:
        pass
    return im


def _enhance_medical_image(im):
    """针对 X光/CT/MRI 屏幕拍照的专项增强预处理。
    
    医学影像特征：整体偏暗、低对比度、可能有屏幕反光。
    处理策略：
    1. 检测图片整体亮度，若偏暗则加强对比度
    2. 自适应直方图均衡化增强细节
    3. 适度锐化提高文字和边缘清晰度
    """
    try:
        import io
        import numpy as np
        from PIL import Image, ImageEnhance, ImageOps
        
        # 计算平均亮度（灰度均值）
        gray = im.convert("L")
        pixels = list(gray.getdata())
        avg_brightness = sum(pixels) / len(pixels)
        
        if avg_brightness < 100:
            # 暗图：X光/CT 黑底白字类，大幅增强对比度
            im = ImageOps.autocontrast(im, cutoff=1.0)
            im = ImageEnhance.Contrast(im).enhance(1.5)
            im = ImageEnhance.Brightness(im).enhance(1.2)
        elif avg_brightness < 140:
            # 中等暗度：拍屏幕的报告，适度增强
            im = ImageOps.autocontrast(im, cutoff=0.5)
            im = ImageEnhance.Contrast(im).enhance(1.2)
        else:
            # 正常亮度：常规增强即可
            im = ImageOps.autocontrast(im, cutoff=0.3)
        
        # 统一锐化
        im = ImageEnhance.Sharpness(im).enhance(1.3)
        
    except Exception:
        pass
    return im


def _is_likely_medical_imaging(file_path: Path) -> bool:
    """根据文件名猜测是否为医学影像类照片（X光/CT/MRI 拍屏等）。"""
    name = file_path.name.lower()
    imaging_hints = ("xray", "x光", "x_ray", "ct", "mri", "影像", "拍片",
                     "胸片", "dr", "骨密度", "透视")
    return any(h in name for h in imaging_hints)


def _optimize_image(raw_bytes: bytes, max_dim: int = 1200, quality: int = 75,
                    do_exif: bool = True) -> Tuple[bytes, str]:
    """智能预处理：EXIF回正 + 方向检测 + 压缩分辨率与字节。"""
    try:
        import io
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(raw_bytes))
        
        # EXIF 回正（修复手机拍照方向信息）
        if do_exif:
            im = ImageOps.exif_transpose(im)
        
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            if im.mode == "P":
                im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")

        # 智能方向检测
        im = _auto_orient(im)

        w, h = im.size
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        im.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue(), "image/jpeg"
    except Exception:
        return raw_bytes, "image/jpeg"


# ---------------------------------------------------------------- PDF 逐页渲染

def _render_pdf_pages(data: bytes, file_path: Path) -> list:
    """将 PDF 渲染为逐页的 base64 图片块列表。
    
    返回: list of (image_block_dict, page_index)
    每个 image_block 可单独发送给 API。
    """
    import fitz  # PyMuPDF
    import io
    from PIL import Image, ImageOps, ImageEnhance

    doc = fitz.open(stream=data, filetype="pdf")
    pages_to_process = min(len(doc), MAX_PDF_PAGES)
    page_blocks = []

    for page_idx in range(pages_to_process):
        page = doc[page_idx]
        # 150 DPI 足够识别文字，省内存
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")

        im = Image.open(io.BytesIO(img_data)).convert("RGB")
        w, h = im.size
        max_dim = 1200  # PDF 页面限制 1200px
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        
        # 增强处理
        im = _enhance_medical_image(im)

        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=65, optimize=True)
        page_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        
        block = {"type": "image",
                 "source": {"type": "base64", "media_type": "image/jpeg",
                            "data": page_b64}}
        page_blocks.append((block, page_idx))

    doc.close()
    return page_blocks


def _build_source_blocks(file_path: Path) -> Tuple[list, dict]:
    """前置校验并构造内容块。返回 (blocks_or_pages, diagnostics)。
    
    对于 PDF：返回 list of (block, page_idx) 用于逐页调用。
    对于图片：返回 [block] 单图。
    diag["is_pdf_pages"] 标记是否为 PDF 逐页模式。
    """
    data = file_path.read_bytes()
    if not data:
        raise VisionInputError(
            f"{file_path.name} 是空文件（0 字节），无法抽取。请重新上传原始图片。")

    media_type = sniff_media_type(data, file_path)
    if media_type is None:
        raise VisionInputError(
            f"{file_path.name} 的实际格式无法识别（文件头 {data[:8]!r}）。"
            "支持 jpg / png / webp / gif / pdf；若是 HEIC 等手机原生格式，"
            "请先转存为 JPG 或 PNG 再上传。")

    is_pdf = media_type == "application/pdf"
    limit = MAX_PDF_BYTES if is_pdf else MAX_IMAGE_BYTES
    if len(data) > limit:
        raise VisionInputError(
            f"{file_path.name} 体积 {len(data) / 1e6:.1f}MB 超出上限 "
            f"{limit / 1e6:.1f}MB。请压缩后重试（手机拍照建议导出为"
            "「中等质量」JPG，一般 1MB 以内即可清晰识别）。")

    diag = {"filename": file_path.name, "bytes": len(data),
            "media_type": media_type, "model": config.VISION_MODEL}

    if is_pdf:
        try:
            page_blocks = _render_pdf_pages(data, file_path)
            diag["blocks_count"] = len(page_blocks)
            diag["pdf_pages_total"] = len(page_blocks)
            diag["is_pdf_pages"] = True
            return (page_blocks, diag)
        except ImportError:
            print("[Vision] PyMuPDF 未安装，回退为原始 document 方式")
        except Exception as exc:
            print(f"[Vision] PDF 转图片失败({exc})，回退为原始 document 方式")

        # 回退：原始 PDF document 方式（token 消耗极高，仅作兜底）
        b64 = base64.b64encode(data).decode("ascii")
        diag["b64_len"] = len(b64)
        diag["fallback"] = "raw_document"
        diag["is_pdf_pages"] = False
        return ([{"type": "document",
                  "source": {"type": "base64", "media_type": media_type, "data": b64}}],
                diag)

    # ---- 图像智能高效预处理 ----
    # EXIF 自动回正 + 方向检测 + 对比度/锐度增强
    is_medical = _is_likely_medical_imaging(file_path)
    try:
        import io
        from PIL import Image, ImageOps, ImageEnhance
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        
        # 智能方向检测（横拍自动旋转）
        im = _auto_orient(im)
        
        w, h = im.size
        # 限制长边至 1600px
        max_dim = 1600
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        
        # 根据图片类型选择增强策略
        if is_medical:
            im = _enhance_medical_image(im)
        else:
            im_enh = ImageEnhance.Sharpness(ImageOps.autocontrast(im, cutoff=0.3)).enhance(1.15)
            im = im_enh
        
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=80, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        
        diag["blocks_count"] = 1
        diag["is_pdf_pages"] = False
        diag["medical_enhanced"] = is_medical
        return ([{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}], diag)
    except Exception:
        # 回退路径也做 EXIF 回正和方向检测
        opt_data, opt_mime = _optimize_image(data, max_dim=1568, quality=80, do_exif=True)
        b64 = base64.b64encode(opt_data).decode("ascii")
        diag["is_pdf_pages"] = False
        return ([{"type": "image", "source": {"type": "base64", "media_type": opt_mime, "data": b64}}], diag)


def _diag_text(diag: dict) -> str:
    return (f"（诊断：文件 {diag['filename']}，{diag['bytes']} 字节，"
            f"media_type={diag['media_type']}，"
            f"模型 {diag['model']}）")


def _friendly_error(err, diag: dict) -> str:
    """将技术错误转换为用户能看懂的提示信息。"""
    err_str = str(err).lower()
    filename = diag.get('filename', '文件')
    
    if 'timed out' in err_str or 'timeout' in err_str:
        return (f"识别 {filename} 超时，可能是文件内容较复杂。"
                "建议：请将 PDF 转为图片后重新上传（手机截图或拍照均可），或减少 PDF 页数后重试。")
    if 'connection' in err_str or 'network' in err_str or 'urlopen' in err_str:
        return "网络连接异常，AI 识别服务暂时不可用。请稍后重试。"
    if '429' in err_str or '限流' in err_str or 'rate' in err_str:
        return "AI 识别服务繁忙，请等待 30 秒后重试。"
    if '503' in err_str or '502' in err_str or 'bad gateway' in err_str:
        return "AI 识别服务暂时维护中，请稍后重试。"
    if '401' in err_str or '403' in err_str or 'unauthorized' in err_str:
        return "AI 识别服务授权失败，请联系管理员检查配置。"
    if 'json' in err_str or 'schema' in err_str:
        return (f"{filename} 的内容无法被正确识别。"
                "建议：请确认上传的是清晰的体检报告/化验单；若为 PDF，可尝试转为图片后重新上传。")
    if 'pymupdf' in err_str or 'fitz' in err_str:
        return (f"{filename} 格式不兼容，无法解析此 PDF。"
                "建议：请将 PDF 中的报告页截图保存为图片后重新上传。")
    # 通用兜底
    return (f"识别 {filename} 时遇到问题。"
            "建议：请尝试将文件转为清晰的图片（JPG/PNG）后重新上传，或稍后重试。")


# ---------------------------------------------------------------- 多页结果合并

def _merge_page_results(page_results: list) -> dict:
    """合并多页 PDF 的逐页抽取结果为一个完整的报告数据。
    
    合并策略：
    - document_type / exam_date / patient：取第一个非空值
    - exam_info：取第一个非空值
    - observations：所有页合并，按 code 去重（保留完整度更高的）
    - findings：所有页直接拼接
    - impressions：所有页去重拼接
    - notes：所有页拼接
    """
    if not page_results:
        return {}
    if len(page_results) == 1:
        return page_results[0]
    
    merged = {
        "document_type": None,
        "exam_date": None,
        "patient": None,
        "exam_info": None,
        "findings": [],
        "impressions": [],
        "observations": [],
        "notes": None,
        "deidentified": True,
        "engine": "vision_llm",
    }
    
    seen_obs_codes = {}  # code -> observation dict
    seen_impressions = set()
    
    for pr in page_results:
        # 取第一个非空值
        if not merged["document_type"] and pr.get("document_type"):
            merged["document_type"] = pr["document_type"]
        if not merged["exam_date"] and pr.get("exam_date"):
            merged["exam_date"] = pr["exam_date"]
        if not merged["patient"] and pr.get("patient"):
            merged["patient"] = pr["patient"]
        if not merged["exam_info"] and pr.get("exam_info"):
            merged["exam_info"] = pr["exam_info"]
        
        # observations：按 code 去重，保留字段更完整的
        for obs in pr.get("observations") or []:
            code = (obs.get("code") or "").upper()
            display = obs.get("display") or ""
            key = code or display
            if not key:
                continue
            if key in seen_obs_codes:
                # 已有同名指标：保留 value_num 不为空的那个
                existing = seen_obs_codes[key]
                if obs.get("value_num") is not None and existing.get("value_num") is None:
                    seen_obs_codes[key] = obs
            else:
                seen_obs_codes[key] = obs
        
        # findings：直接追加
        for f in pr.get("findings") or []:
            merged["findings"].append(f)
        
        # impressions：去重追加
        for imp in pr.get("impressions") or []:
            if imp and imp not in seen_impressions:
                seen_impressions.add(imp)
                merged["impressions"].append(imp)
        
        # notes 拼接
        if pr.get("notes"):
            if merged["notes"]:
                merged["notes"] += "；" + pr["notes"]
            else:
                merged["notes"] = pr["notes"]
    
    merged["observations"] = list(seen_obs_codes.values())
    return merged


# ---------------------------------------------------------------- API 调用

def _extract_via_anthropic(source_blocks: list, diag: dict,
                           doc_type_hint: Optional[str]) -> Tuple[Optional[dict], Optional[Exception]]:
    if not config.ANTHROPIC_API_KEY:
        return None, None
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY,
                                 base_url=config.ANTHROPIC_BASE_URL,
                                 timeout=60.0)
    messages = [{
        "role": "user",
        "content": [*source_blocks,
                    {"type": "text", "text": extraction_user_prompt(doc_type_hint)}],
    }]

    # 主备视觉模型轮询表
    primary_model = config.VISION_MODEL
    candidate_models = [primary_model]
    for m in ("claude-sonnet-5", "claude-sonnet-4-6", "claude-opus-4-8"):
        if m not in candidate_models:
            candidate_models.append(m)

    last_error: Optional[Exception] = None
    for model_name in candidate_models:
        for attempt in range(2):
            try:
                resp = client.messages.create(
                    model=model_name,
                    max_tokens=4500,
                    system=EXTRACTION_SYSTEM,
                    messages=messages,
                )
                text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                data = json.loads(_strip_to_json(text))
                data["engine"] = "vision_llm"
                return data, None
            except Exception as exc:
                err_str = str(exc)
                text = locals().get("text", "")
                if _looks_like_no_image(text):
                    return None, VisionNotSeeingImageError(
                        f"请求已送达模型，但模型答复未收到图像。{_diag_text(diag)} "
                        f"模型原话：{(text or '').strip()[:160]}"
                    )
                last_error = exc
                # 若遇到 429 负载限流或 400/502 服务不可用，适度退避
                if any(k in err_str for k in ("429", "400", "502", "503", "token负载", "暂时不可用", "Bad Gateway")):
                    time.sleep(1.5)
                    break  # 尝试切换下一个候选模型
                messages.append({"role": "assistant", "content": text or "(空)"})
                messages.append({"role": "user", "content": repair_prompt(err_str)})
    return None, last_error


def _extract_via_openai(source_blocks: list, diag: dict,
                        doc_type_hint: Optional[str]) -> Tuple[Optional[dict], Optional[Exception]]:
    if not config.OPENAI_API_KEYS:
        return None, None
    import urllib.request
    base = config.OPENAI_BASE_URL.rstrip("/")
    url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
    
    # 将 Anthropic 格式的 source_blocks 转换为 OpenAI 格式的 image_url 内容块
    content_parts = []
    for blk in source_blocks:
        if blk.get("type") == "image":
            src = blk["source"]
            mime = src.get("media_type", "image/jpeg")
            b64 = src["data"]
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            })
        elif blk.get("type") == "document":
            return None, ExtractionError("OpenAI 兼容协议不支持直接发送 PDF document，请确保 PyMuPDF 已安装")
    if not content_parts:
        return None, ExtractionError("无有效图像内容块")
    content_parts.append({"type": "text", "text": extraction_user_prompt(doc_type_hint)})
    payload = {
        "model": config.OPENAI_MODEL,
        "max_tokens": 4500,
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM},
            {"role": "user", "content": content_parts},
        ],
    }
    
    # 多 Key 轮换：逐个尝试，余额不足/限流时自动切换下一个
    last_err = None
    for _attempt in range(len(config.OPENAI_API_KEYS)):
        api_key = config.next_openai_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"),
                headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                txt = res_data["choices"][0]["message"]["content"]
                data = json.loads(_strip_to_json(txt))
                data["engine"] = "vision_llm"
                return data, None
        except Exception as exc:
            last_err = exc
            err_str = str(exc)
            # 401/402/429：Key 失效或余额不足或限流，切换下一个 Key
            if any(k in err_str for k in ("401", "402", "429", "insufficient", "quota", "balance")):
                print(f"[Vision OCR] Key ...{api_key[-8:]} 不可用({err_str[:60]})，切换下一个 Key...")
                time.sleep(0.5)
                continue
            # 其他错误（超时、网络等）不切 Key，直接返回
            break
    return None, last_err


def _call_single_extraction(source_blocks: list, diag: dict,
                            doc_type_hint: Optional[str]) -> Tuple[Optional[dict], Optional[Exception]]:
    """对单组 source_blocks 调用 API（先 Anthropic 后 OpenAI），带并发锁。"""
    with _api_semaphore:
        data, anthropic_err = _extract_via_anthropic(source_blocks, diag, doc_type_hint)
        if data:
            return data, None
        
        if anthropic_err:
            print(f"[Vision OCR] 主通道 (Anthropic) 失败: {anthropic_err}，切换至备用通道...")
        
        if config.OPENAI_API_KEY:
            data, openai_err = _extract_via_openai(source_blocks, diag, doc_type_hint)
            if data:
                return data, None
            return None, openai_err or anthropic_err
        
        return None, anthropic_err


# ---------------------------------------------------------------- 主流程

def extract_from_file(file_path, doc_type_hint: Optional[str] = None) -> ExtractionResult:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))

    if config.MOCK_MODE:
        return _load_mock(file_path)

    if not config.ANTHROPIC_API_KEY and not config.OPENAI_API_KEY:
        raise ExtractionError(
            "AI 识别服务未配置，暂时无法识别报告。请联系管理员开启服务。"
        )

    source_blocks, diag = _build_source_blocks(file_path)

    # ---- PDF 逐页模式：每页单独调 API，最后合并 ----
    if diag.get("is_pdf_pages") and len(source_blocks) > 1:
        print(f"[Vision OCR] PDF 逐页模式：共 {len(source_blocks)} 页，逐页调用 API...")
        page_results = []
        last_err = None
        
        for block, page_idx in source_blocks:
            page_data = None
            page_err = None
            
            # 每页最多重试 3 次（含首次）
            for retry in range(3):
                if retry > 0:
                    wait = 3 * retry  # 3秒, 6秒
                    print(f"[Vision OCR] 第 {page_idx + 1} 页第 {retry + 1} 次重试（等待 {wait}s）...")
                    time.sleep(wait)
                
                print(f"[Vision OCR] 正在处理第 {page_idx + 1}/{len(source_blocks)} 页...")
                page_data, page_err = _call_single_extraction(
                    [block], diag, doc_type_hint)
                
                if page_data:
                    break  # 成功，跳出重试循环
                
                # 判断是否值得重试
                err_str = str(page_err).lower()
                if any(k in err_str for k in ('timed out', 'timeout', '429', '502', '503', 'rate')):
                    continue  # 超时/限流，值得重试
                else:
                    break  # 其他错误（如格式问题），不重试
            
            if page_data:
                page_results.append(page_data)
                print(f"[Vision OCR] 第 {page_idx + 1} 页抽取成功"
                      f"（{len(page_data.get('observations', []))} 项指标，"
                      f"{len(page_data.get('findings', []))} 项发现）")
            else:
                last_err = page_err
                print(f"[Vision OCR] 第 {page_idx + 1} 页抽取失败（已重试）: {page_err}")
            
            # 页间间隔，避免 API 限流（多页时间隔更长）
            if page_idx < len(source_blocks) - 1:
                time.sleep(1.5 if len(source_blocks) > 5 else 0.8)
        
        if page_results:
            merged = _merge_page_results(page_results)
            print(f"[Vision OCR] PDF 合并完成：共 {len(merged.get('observations', []))} 项指标，"
                  f"{len(merged.get('findings', []))} 项发现，"
                  f"{len(merged.get('impressions', []))} 条诊断")
            return from_dict(merged)
        
        # 所有页都失败了
        raise ExtractionError(_friendly_error(last_err, diag))
    
    # ---- 单页 PDF 或普通图片：单次调用 ----
    # 对于 PDF 逐页模式只有 1 页的情况，解包
    actual_blocks = source_blocks
    if diag.get("is_pdf_pages") and len(source_blocks) == 1:
        actual_blocks = [source_blocks[0][0]]  # 解包 (block, page_idx) 元组
    
    data, err = _call_single_extraction(actual_blocks, diag, doc_type_hint)
    if data:
        return from_dict(data)
    
    if isinstance(err, VisionNotSeeingImageError):
        raise err
    raise ExtractionError(_friendly_error(err, diag))


# ---------------------------------------------------------------- 视觉自检

def _probe_png(color: Tuple[int, int, int] = (220, 30, 30), size: int = 48) -> bytes:
    """纯标准库生成一张纯色 PNG，用于探测链路是否真的支持图像输入。"""
    raw = b"".join(b"\x00" + bytes(color) * size for _ in range(size))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return (struct.pack(">I", len(payload)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBB B", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def vision_selftest() -> dict:
    """发一张已知颜色的纯色图问模型看到什么颜色，判定链路是否支持视觉。

    返回 {ok, mode, model, reply, reason}；不抛异常，供接口与命令行直接展示。
    """
    base = {"model": config.VISION_MODEL, "mode": config.LLM_MODE}
    if config.MOCK_MODE:
        return {**base, "ok": False,
                "reason": "当前为显式 MOCK 模式，未连接真实模型，无需也无法自检视觉。"}
    if not config.ANTHROPIC_API_KEY:
        return {**base, "ok": False,
                "reason": "未配置 ANTHROPIC_API_KEY，无法自检。"}
    try:
        import anthropic
    except ImportError:
        return {**base, "ok": False,
                "reason": "未安装 anthropic 包：pip install -r requirements.txt"}

    png = _probe_png()
    b64 = base64.b64encode(png).decode("ascii")
    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY,
                                 base_url=config.ANTHROPIC_BASE_URL)
        resp = client.messages.create(
            model=config.VISION_MODEL, max_tokens=64,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/png", "data": b64}},
                {"type": "text", "text": "这张图是什么颜色？只回答颜色名，两个字以内。"
                                         "如果你没有收到图片，请直接回答「无图」。"}]}],
        )
        reply = "".join(b.text for b in resp.content
                        if getattr(b, "type", "") == "text").strip()
    except Exception as exc:
        return {**base, "ok": False, "reply": None,
                "reason": f"调用失败：{exc}。请检查密钥、模型名与出网连通性。"}

    if _looks_like_no_image(reply) or "无图" in reply:
        return {**base, "ok": False, "reply": reply,
                "reason": f"模型收不到图像：{config.VISION_MODEL} 可能不支持视觉输入，"
                          "或中间网关剥离了图像块。请改用视觉模型"
                          "（VISION_MODEL=claude-opus-4-6）或检查代理配置。"}
    if any(k in reply for k in ("红", "赤", "red", "Red")):
        return {**base, "ok": True, "reply": reply,
                "reason": "视觉链路正常：模型正确识别了探测图颜色，可正常上传报告图片。"}
    return {**base, "ok": False, "reply": reply,
            "reason": "模型有回复但未能正确识别探测图颜色（预期为红色），"
                      "视觉链路可疑，请结合上面的原始回复排查。"}
