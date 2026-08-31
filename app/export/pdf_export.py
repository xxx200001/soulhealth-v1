"""PDF 导出模块：利用 ReportLab 服务端生成排版精美的食补方案与药食同源茶饮方案 PDF。
纯服务端渲染，自带中文字体支持，直接流式下载，彻底告别浏览器端 Canvas/Print 兼容性与空白问题。
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# 注册中文字体（优先微软雅黑，备选黑体/宋体）
FONT_NAME = "SoulHealthFont"
FONT_BOLD = "SoulHealthFontBold"


def _init_fonts():
    candidate_regular = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    candidate_bold = [
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
    ]

    reg_path = next((p for p in candidate_regular if os.path.exists(p)), None)
    bold_path = next((p for p in candidate_bold if os.path.exists(p)), reg_path)

    if reg_path:
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, reg_path))
        except Exception:
            pass
    if bold_path:
        try:
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
        except Exception:
            pass


_init_fonts()

# 品牌色
C_BRAND = colors.HexColor("#2D5F4B")       # 墨绿品牌主色
C_BRAND_LIGHT = colors.HexColor("#EBF5F0") # 浅墨绿底色
C_GOLD = colors.HexColor("#9C6500")        # 雅金
C_GOLD_LIGHT = colors.HexColor("#FDF7E7")  # 浅金底色
C_LINE = colors.HexColor("#E2E8F0")        # 浅边线
C_INK = colors.HexColor("#1A202C")         # 正文深墨
C_MUTED = colors.HexColor("#718096")       # 辅助灰
C_WARN = colors.HexColor("#D69E2E")        # 警示黄
C_DANGER = colors.HexColor("#E53E3E")      # 危险红
C_BG_GRAY = colors.HexColor("#F7FAFC")

GOAL_CN = {
    "liver_care": "肝脏管理",
    "lipid_care": "血脂管理",
    "glucose_care": "血糖管理",
    "uric_care": "尿酸管理",
    "weight_care": "体重管理",
    "bp_care": "血压管理",
    "kidney_care": "肾功能关注",
    "blood_care": "气血养护",
    "general_balance": "均衡养护",
}


def _get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "DocTitle",
        fontName=FONT_BOLD,
        fontSize=18,
        leading=22,
        textColor=C_BRAND,
        alignment=1,  # Center
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "DocSubTitle",
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        textColor=C_MUTED,
        alignment=1,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        "SecTitle",
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=C_BRAND,
        spaceBefore=10,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "CardTitle",
        fontName=FONT_BOLD,
        fontSize=11,
        leading=14,
        textColor=C_INK,
        spaceBefore=4,
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "Body",
        fontName=FONT_NAME,
        fontSize=9.5,
        leading=13.5,
        textColor=C_INK,
    ))
    styles.add(ParagraphStyle(
        "BodyMuted",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=12,
        textColor=C_MUTED,
    ))
    styles.add(ParagraphStyle(
        "TableHeader",
        fontName=FONT_BOLD,
        fontSize=9.5,
        leading=12,
        textColor=C_BRAND,
    ))
    styles.add(ParagraphStyle(
        "TableCell",
        fontName=FONT_NAME,
        fontSize=9,
        leading=12.5,
        textColor=C_INK,
    ))
    styles.add(ParagraphStyle(
        "TagGold",
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=10,
        textColor=C_GOLD,
    ))
    styles.add(ParagraphStyle(
        "Footer",
        fontName=FONT_NAME,
        fontSize=8,
        leading=11,
        textColor=C_MUTED,
        alignment=1,
    ))
    return styles


def _format_patient_bar(profile: dict) -> Table:
    """生成患者信息条"""
    name = profile.get("name") or "用户"
    sex_str = "男" if profile.get("sex") == "male" else ("女" if profile.get("sex") == "female" else "未知")
    age = f"{profile.get('age')}岁" if profile.get("age") else "年龄未填"
    dt_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    text = f"<b>档案主体：</b>{name}（{sex_str} · {age}）　｜　<b>导出时间：</b>{dt_str}　｜　<b>生成系统：</b>SOULHEALTH AI"
    styles = _get_styles()
    p = Paragraph(text, styles["BodyMuted"])
    t = Table([[p]], colWidths=[180 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_BRAND_LIGHT),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.5, C_BRAND),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def generate_diet_pdf(profile: dict, diet: dict) -> bytes:
    """生成食补方案 PDF 二进制流"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = _get_styles()
    story = []

    # 1. 标题与信息条
    story.append(Paragraph("SOULHEALTH · 个性化食补调理方案", styles["DocTitle"]))
    story.append(Paragraph("循证营养干预 · 四类食物池分级管理", styles["DocSubTitle"]))
    story.append(_format_patient_bar(profile))
    story.append(Spacer(1, 4 * mm))

    # 2. 健康目标
    goals = diet.get("goals") or []
    if goals:
        story.append(Paragraph("🎯 本方案针对的核心健康目标", styles["SecTitle"]))
        goal_rows = []
        for g in goals:
            label_p = Paragraph(f"<b>{g.get('label') or ''}</b>", styles["TagGold"])
            why_p = Paragraph(g.get("why") or "", styles["Body"])
            goal_rows.append([label_p, why_p])
        gt = Table(goal_rows, colWidths=[40 * mm, 140 * mm])
        gt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), C_GOLD_LIGHT),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#F6E05E")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(gt)
        story.append(Spacer(1, 4 * mm))

    # 3. 四类食物池
    pools = diet.get("pools") or {}
    pool_meta = [
        ("recommended", "✅ 推荐吃（优先摄入）", colors.HexColor("#22543D"), colors.HexColor("#F0FFF4"), colors.HexColor("#C6F6D5")),
        ("allowed", "🟢 可以吃（正常适量）", colors.HexColor("#2B6CB0"), colors.HexColor("#EBF8FF"), colors.HexColor("#BEE3F8")),
        ("limit", "⚠️ 少吃（控制摄入频次与份量）", colors.HexColor("#B7791F"), colors.HexColor("#FFFAF0"), colors.HexColor("#FEEBC8")),
        ("avoid", "🚫 建议避免（严格忌口）", colors.HexColor("#C53030"), colors.HexColor("#FFF5F5"), colors.HexColor("#FED7D7")),
    ]

    for pkey, plabel, text_color, bg_color, border_color in pool_meta:
        items = pools.get(pkey) or []
        if not items:
            continue
        
        pool_elements = []
        pool_title_style = ParagraphStyle(
            f"PoolTitle_{pkey}",
            parent=styles["SecTitle"],
            textColor=text_color,
            fontSize=11,
            leading=14,
        )
        pool_elements.append(Paragraph(f"{plabel}（共 {len(items)} 种）", pool_title_style))

        food_rows = []
        for f in items:
            name_str = f"<b>{f.get('name') or ''}</b>"
            if f.get("goal"):
                name_str += f" <font color='#9C6500'>[{f.get('goal')}]</font>"
            name_p = Paragraph(name_str, styles["Body"])

            meta_parts = []
            if f.get("portion"):
                meta_parts.append(f"份量：{f.get('portion')}")
            if f.get("frequency"):
                meta_parts.append(f"频率：{f.get('frequency')}")
            meta_str = (" ｜ ".join(meta_parts)) if meta_parts else ""

            desc_text = f.get("why") or ""
            if meta_str:
                desc_text += f"<br/><font color='#718096'>{meta_str}</font>"
            desc_p = Paragraph(desc_text, styles["Body"])

            food_rows.append([name_p, desc_p])

        ft = Table(food_rows, colWidths=[50 * mm, 130 * mm])
        ft.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg_color),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, border_color),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        pool_elements.append(ft)
        pool_elements.append(Spacer(1, 3 * mm))
        story.append(KeepTogether(pool_elements))

    # 4. 推荐菜谱
    recipes = diet.get("recipes") or []
    if recipes:
        recipe_elements = []
        recipe_elements.append(Paragraph("🍲 精选食疗菜谱推荐", styles["SecTitle"]))
        rc_rows = []
        for rc in recipes:
            tag = GOAL_CN.get(rc.get("goal_tag")) or rc.get("goal_tag") or "调理"
            title_p = Paragraph(f"<b>{rc.get('name') or ''}</b> <font color='#9C6500'>[{tag}]</font>", styles["Body"])
            reason_p = Paragraph(rc.get("reason") or "", styles["BodyMuted"])
            rc_rows.append([title_p, reason_p])
        rct = Table(rc_rows, colWidths=[60 * mm, 120 * mm])
        rct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), C_BG_GRAY),
            ("BOX", (0, 0), (-1, -1), 0.5, C_LINE),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, C_LINE),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        recipe_elements.append(rct)
        story.append(KeepTogether(recipe_elements))

    # 5. 免责声明页脚
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_LINE, spaceAfter=3 * mm))
    story.append(Paragraph("💡 本方案为健康管理与食养参考，不构成医疗处方与临床诊断；若有急性不适请及时就医。", styles["Footer"]))

    doc.build(story)
    return buf.getvalue()


def generate_tea_pdf(profile: dict, tea: dict) -> bytes:
    """生成药食同源茶饮方案 PDF 二进制流"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = _get_styles()
    story = []

    plan = tea.get("plan") or tea  # 兼容外层/内层结构
    tea_name = plan.get("name") or "药食同源茶饮方"
    goal_label = plan.get("goal_label") or "体质调理"
    version = tea.get("version") or 1

    # 1. 标题与信息条
    story.append(Paragraph(f"SOULHEALTH · {tea_name}", styles["DocTitle"]))
    story.append(Paragraph(f"广式地道药食同源 · {goal_label}（第 {version} 版）", styles["DocSubTitle"]))
    story.append(_format_patient_bar(profile))
    story.append(Spacer(1, 4 * mm))

    # 2. 原料配方表
    ingredients = plan.get("ingredients") or []
    if ingredients:
        story.append(Paragraph("🌿 配方原料与用量", styles["SecTitle"]))
        table_data = [[
            Paragraph("原料名称", styles["TableHeader"]),
            Paragraph("标准用量", styles["TableHeader"]),
            Paragraph("配伍说明 / 炮制建议", styles["TableHeader"]),
        ]]
        for ing in ingredients:
            name_str = f"<b>{ing.get('name') or ''}</b>"
            if ing.get("note"):
                name_str += f" <font color='#718096'>({ing.get('note')})</font>"
            name_p = Paragraph(name_str, styles["TableCell"])
            grams_p = Paragraph(f"<b>{ing.get('grams')} g</b>", styles["TableCell"])
            caution_p = Paragraph(ing.get("caution") or "—", styles["TableCell"])
            table_data.append([name_p, grams_p, caution_p])

        ing_table = Table(table_data, colWidths=[55 * mm, 30 * mm, 95 * mm])
        ing_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_BRAND_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, C_BRAND),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, C_LINE),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(ing_table)
        story.append(Spacer(1, 4 * mm))

    # 3. 制作与用法
    story.append(Paragraph("🍵 制作方法与用法周期", styles["SecTitle"]))
    grid_data = [
        [
            Paragraph(f"<b>建议水量：</b>{plan.get('water_ml') or '—'} ml", styles["Body"]),
            Paragraph(f"<b>饮用频率：</b>{plan.get('frequency') or '—'}", styles["Body"]),
        ],
        [
            Paragraph(f"<b>制作方法：</b>{plan.get('brew') or '—'}", styles["Body"]),
            Paragraph(f"<b>建议周期：</b>{plan.get('cycle') or '—'}", styles["Body"]),
        ],
    ]
    grid_table = Table(grid_data, colWidths=[90 * mm, 90 * mm])
    grid_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_BG_GRAY),
        ("BOX", (0, 0), (-1, -1), 0.5, C_LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, C_LINE),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(grid_table)
    story.append(Spacer(1, 4 * mm))

    # 4. 配伍依据
    if plan.get("rationale"):
        story.append(Paragraph("📜 组方辨证配伍依据", styles["SecTitle"]))
        rat_p = Paragraph(plan.get("rationale"), styles["Body"])
        rat_table = Table([[rat_p]], colWidths=[180 * mm])
        rat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), C_GOLD_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECC94B")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(rat_table)
        story.append(Spacer(1, 4 * mm))

    # 5. 禁忌与注意事项
    contras = plan.get("contraindications") or []
    if isinstance(contras, str):
        contras = [c.strip() for c in contras.replace(";", "；").split("；") if c.strip()]
    cautions = plan.get("cautions") or []
    if isinstance(cautions, str):
        cautions = [c.strip() for c in cautions.replace(";", "；").split("；") if c.strip()]

    if contras or cautions:
        story.append(Paragraph("⚠️ 禁忌人群与安全注意", styles["SecTitle"]))
        warn_lines = []
        for c in contras:
            warn_lines.append(f"<font color='#E53E3E'><b>[禁忌]</b></font> {c}")
        for c in cautions:
            warn_lines.append(f"<font color='#D69E2E'><b>[注意]</b></font> {c}")
        
        warn_p = Paragraph("<br/>".join(warn_lines), styles["Body"])
        warn_table = Table([[warn_p]], colWidths=[180 * mm])
        warn_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF5F5")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#FEB2B2")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(warn_table)

    # 6. 额外说明
    if plan.get("note"):
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"💡 <b>提示：</b>{plan.get('note')}", styles["BodyMuted"]))

    # 7. 页脚
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_LINE, spaceAfter=3 * mm))
    story.append(Paragraph("💡 本茶饮方案为药食同源养生建议，经 Safety 规则引擎校验；非药品处方，严重不适请就医。", styles["Footer"]))

    doc.build(story)
    return buf.getvalue()
