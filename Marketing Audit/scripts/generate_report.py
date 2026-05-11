#!/usr/bin/env python3
"""
GoToRetreats Marketing Intelligence Report — PDF Generator

Usage:
    python generate_report.py --data input.json [--output output.pdf]
    python generate_report.py input.json [output.pdf]          # positional fallback

Input:  JSON file with structured audit data (see SKILL.md for schema).
Output: Branded PDF report using GoToRetreats design system.

Branding is loaded from assets/brand-config.json relative to the skill directory.
If the config file is missing, hardcoded GoToRetreats defaults are used.
The audited client's branding is NEVER used — reports are always GoToRetreats-branded.
"""

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        Image,
        NextPageTemplate,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
        KeepTogether,
    )
except ImportError:
    print("reportlab not found. Installing...")
    import subprocess
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "reportlab", "--break-system-packages"],
        stdout=subprocess.DEVNULL,
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        Image,
        NextPageTemplate,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
        KeepTogether,
    )


# ---------------------------------------------------------------------------
# Brand configuration
# ---------------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent.parent
BRAND_CONFIG_PATH = SKILL_DIR / "assets" / "brand-config.json"
LOGO_PATH = SKILL_DIR / "assets" / "gotoretreat-logo.png"

DEFAULTS = {
    "brand_name": "GoToRetreats",
    "tagline": "Marketing Intelligence Report",
    "colors": {
        "primary": "#009E9B",
        "primary_light": "#00D1CE",
        "accent": "#00D1CE",
        "secondary": "#B8BFD1",
        "background": "#FAFAFA",
        "text_dark": "#4A4A4F",
        "text_primary": "#009E9B",
        "button_primary_border": "#006B69",
        "score_strong": "#16A34A",
        "score_moderate": "#D97706",
        "score_weak": "#EA580C",
        "score_critical": "#DC2626",
    },
    "typography": {
        "font_heading": "Helvetica-Bold",
        "font_body": "Helvetica",
    },
}


def load_brand_config() -> dict:
    config = DEFAULTS.copy()
    if BRAND_CONFIG_PATH.exists():
        try:
            with open(BRAND_CONFIG_PATH, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            for key in ("brand_name", "tagline"):
                if key in file_cfg:
                    config[key] = file_cfg[key]
            if "colors" in file_cfg:
                config["colors"] = {**config["colors"], **file_cfg["colors"]}
            if "typography" in file_cfg:
                config["typography"] = {**config["typography"], **file_cfg["typography"]}
            print(f"Loaded {config['brand_name']} branding from {BRAND_CONFIG_PATH}")
        except (json.JSONDecodeError, KeyError) as exc:
            print(f"Warning: could not parse {BRAND_CONFIG_PATH}, using defaults. ({exc})")
    else:
        print(f"Info: {BRAND_CONFIG_PATH} not found, using hardcoded GoToRetreats defaults.")
    return config


BRAND = load_brand_config()


def hex_to_color(hex_str: str) -> colors.Color:
    h = hex_str.lstrip("#")
    return colors.Color(int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


C_PRIMARY = hex_to_color(BRAND["colors"]["primary"])
C_PRIMARY_LIGHT = hex_to_color(BRAND["colors"]["primary_light"])
C_ACCENT = hex_to_color(BRAND["colors"]["accent"])
C_SECONDARY = hex_to_color(BRAND["colors"]["secondary"])
C_BG = hex_to_color(BRAND["colors"]["background"])
C_TEXT = hex_to_color(BRAND["colors"]["text_dark"])
C_TEXT_PRIMARY = hex_to_color(BRAND["colors"]["text_primary"])
C_BORDER = hex_to_color(BRAND["colors"]["button_primary_border"])
C_WHITE = colors.white

SCORE_COLORS = {
    "Strong": hex_to_color(BRAND["colors"]["score_strong"]),
    "Moderate": hex_to_color(BRAND["colors"]["score_moderate"]),
    "Weak": hex_to_color(BRAND["colors"]["score_weak"]),
    "Critical": hex_to_color(BRAND["colors"]["score_critical"]),
}

FONT_H = BRAND["typography"]["font_heading"]
FONT_B = BRAND["typography"]["font_body"]

# Available content width (letter minus margins)
PAGE_W, PAGE_H = letter
MARGIN = 54
CONTENT_W = PAGE_W - 2 * MARGIN


# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------

def build_styles() -> dict:
    return {
        "cover_brand": ParagraphStyle(
            "cover_brand", fontName=FONT_H, fontSize=24, textColor=C_PRIMARY,
            alignment=TA_LEFT, spaceAfter=6,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", fontName=FONT_H, fontSize=28, textColor=C_TEXT,
            alignment=TA_CENTER, spaceAfter=12,
        ),
        "cover_client": ParagraphStyle(
            "cover_client", fontName=FONT_B, fontSize=18, textColor=C_TEXT,
            alignment=TA_CENTER, spaceAfter=8,
        ),
        "cover_date": ParagraphStyle(
            "cover_date", fontName=FONT_B, fontSize=14, textColor=C_SECONDARY,
            alignment=TA_CENTER, spaceAfter=6,
        ),
        # Section heading text — used INSIDE the left-border table wrapper
        "section_heading_inner": ParagraphStyle(
            "section_heading_inner", fontName=FONT_H, fontSize=14, textColor=C_PRIMARY,
            leading=18,
        ),
        "body": ParagraphStyle(
            "body", fontName=FONT_B, fontSize=10, textColor=C_TEXT,
            leading=14, spaceAfter=10, alignment=TA_LEFT,
        ),
        "body_bold": ParagraphStyle(
            "body_bold", fontName=FONT_H, fontSize=10, textColor=C_TEXT,
            leading=14, spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName=FONT_B, fontSize=10, textColor=C_TEXT,
            leading=14, spaceAfter=4, leftIndent=18, bulletIndent=6,
        ),
        "table_header": ParagraphStyle(
            "table_header", fontName=FONT_H, fontSize=10, textColor=C_WHITE,
            leading=13, alignment=TA_LEFT,
        ),
        "table_cell": ParagraphStyle(
            "table_cell", fontName=FONT_B, fontSize=9, textColor=C_TEXT,
            leading=12, alignment=TA_LEFT,
        ),
        "table_cell_center": ParagraphStyle(
            "table_cell_center", fontName=FONT_B, fontSize=9, textColor=C_TEXT,
            leading=12, alignment=TA_CENTER,
        ),
        "swot_header": ParagraphStyle(
            "swot_header", fontName=FONT_H, fontSize=11, textColor=C_WHITE,
            leading=14, alignment=TA_CENTER,
        ),
        "swot_cell": ParagraphStyle(
            "swot_cell", fontName=FONT_B, fontSize=9, textColor=C_TEXT,
            leading=12, alignment=TA_LEFT,
        ),
        "subsection": ParagraphStyle(
            "subsection", fontName=FONT_H, fontSize=12, textColor=C_TEXT,
            spaceBefore=14, spaceAfter=6, leading=15,
        ),
        "health_label": ParagraphStyle(
            "health_label", fontName=FONT_H, fontSize=13, textColor=C_WHITE,
            alignment=TA_CENTER, leading=16,
        ),
        "badge_text": ParagraphStyle(
            "badge_text", fontName=FONT_H, fontSize=9, textColor=C_WHITE,
            alignment=TA_CENTER, leading=12,
        ),
    }


STYLES = build_styles()


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s-]+", "_", text)


def safe(text) -> str:
    if text is None:
        return ""
    s = str(text)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s


def section_heading(title: str, client_name: str = "") -> list:
    """Build a section heading with a colored left-border accent using a Table."""
    display_title = f"{title} for {client_name}" if client_name else title
    para = Paragraph(safe(display_title), STYLES["section_heading_inner"])
    accent_w = 3
    text_w = CONTENT_W - accent_w - 8
    tbl = Table([[None, para]], colWidths=[accent_w, text_w])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), C_PRIMARY_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [Spacer(1, 20), tbl, Spacer(1, 10)]


def score_badge(score: str):
    """Return a Table-based colored pill badge (reliable across ReportLab versions)."""
    bg = SCORE_COLORS.get(score, C_SECONDARY)
    para = Paragraph(safe(score), STYLES["badge_text"])
    tbl = Table([[para]], colWidths=[70], rowHeights=[18])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), bg),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (0, 0), 2),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("LEFTPADDING", (0, 0), (0, 0), 4),
        ("RIGHTPADDING", (0, 0), (0, 0), 4),
    ]))
    return tbl


def score_badge_inline(score: str) -> str:
    """Return inline XML for a score label (text-only fallback for mixed paragraphs)."""
    color = SCORE_COLORS.get(score, C_SECONDARY)
    hex_c = f"#{int(color.red*255):02x}{int(color.green*255):02x}{int(color.blue*255):02x}"
    return f'<font face="{FONT_H}" size="10" color="{hex_c}">{safe(score)}</font>'


def impact_color(impact: str) -> str:
    mapping = {"High": BRAND["colors"]["score_critical"],
               "Medium": BRAND["colors"]["score_moderate"],
               "Low": BRAND["colors"]["score_strong"]}
    return mapping.get(impact, BRAND["colors"]["secondary"])


def effort_label(effort: str) -> str:
    color_map = {
        "Quick Win": BRAND["colors"]["score_strong"],
        "Medium Lift": BRAND["colors"]["score_moderate"],
        "Strategic": BRAND["colors"]["score_weak"],
    }
    hex_c = color_map.get(effort, BRAND["colors"]["text_dark"])
    return f'<font face="{FONT_H}" color="{hex_c}">{safe(effort)}</font>'


# ---------------------------------------------------------------------------
# Page templates (header / footer)
# ---------------------------------------------------------------------------

def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = letter

    # Logo PNG (contains icon + "goto retreats" text)
    logo_h = 28
    if LOGO_PATH.exists():
        from reportlab.lib.utils import ImageReader
        img = ImageReader(str(LOGO_PATH))
        iw, ih = img.getSize()
        logo_w = logo_h * (iw / ih)
        canvas.drawImage(str(LOGO_PATH), MARGIN, h - 48, width=logo_w, height=logo_h, mask="auto")
    else:
        canvas.setFont(FONT_H, 10)
        canvas.setFillColor(C_PRIMARY)
        canvas.drawString(MARGIN, h - 40, BRAND["brand_name"])

    canvas.setFont(FONT_B, 10)
    canvas.setFillColor(C_SECONDARY)
    canvas.drawRightString(w - MARGIN, h - 40, BRAND["tagline"])

    canvas.setStrokeColor(C_PRIMARY)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 45, w - MARGIN, 45)

    canvas.setFont(FONT_B, 9)
    canvas.setFillColor(C_SECONDARY)
    canvas.drawCentredString(w / 2, 32, f"{doc.page}")

    canvas.restoreState()


def _blank_page(canvas, doc):
    pass


# ---------------------------------------------------------------------------
# Cover page builder
# ---------------------------------------------------------------------------

def build_cover(data: dict) -> list:
    elements = []
    elements.append(Spacer(1, 0.8 * inch))

    # Logo PNG centered on cover
    if LOGO_PATH.exists():
        from reportlab.lib.utils import ImageReader
        img_reader = ImageReader(str(LOGO_PATH))
        iw, ih = img_reader.getSize()
        cover_logo_h = 1.4 * inch
        cover_logo_w = cover_logo_h * (iw / ih)
        logo_img = Image(str(LOGO_PATH), width=cover_logo_w, height=cover_logo_h)
        logo_img.hAlign = "CENTER"
        elements.append(logo_img)
    else:
        elements.append(Paragraph(safe(BRAND["brand_name"]), STYLES["cover_brand"]))
    elements.append(Spacer(1, 0.5 * inch))

    # Centered decorative divider
    divider = Table([[""]], colWidths=[4 * inch], rowHeights=[3])
    divider.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_PRIMARY_LIGHT),
    ]))
    divider.hAlign = "CENTER"
    elements.append(divider)
    elements.append(Spacer(1, 0.5 * inch))

    elements.append(Paragraph(safe(BRAND["tagline"]), STYLES["cover_title"]))
    elements.append(Spacer(1, 0.5 * inch))

    biz = data.get("business_name", "Unknown Business")
    elements.append(Paragraph(safe(biz), STYLES["cover_client"]))
    elements.append(Spacer(1, 0.3 * inch))

    audit_date = data.get("audit_date", "")
    elements.append(Paragraph(safe(audit_date), STYLES["cover_date"]))

    # Template switch BEFORE the PageBreak
    elements.append(NextPageTemplate("content"))
    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_executive_summary(data: dict, client_name: str = "") -> list:
    elements = []
    elements.extend(section_heading("Executive Summary", client_name))

    es = data.get("executive_summary", {})

    # Overall health — use inline colored text (not a table badge) within a paragraph
    health = data.get("overall_health", "Unknown")
    badge_text = score_badge_inline(health)
    elements.append(Paragraph(f"Overall Marketing Health: {badge_text}", STYLES["body_bold"]))
    elements.append(Spacer(1, 6))

    overview = es.get("overview", "")
    if overview:
        elements.append(Paragraph(safe(overview), STYLES["body"]))

    strengths = es.get("top_strengths", [])
    if strengths:
        elements.append(Paragraph("Top Strengths", STYLES["body_bold"]))
        for s in strengths:
            elements.append(Paragraph(f"&bull; {safe(s)}", STYLES["bullet"]))

    gaps = es.get("top_gaps", [])
    if gaps:
        elements.append(Spacer(1, 4))
        elements.append(Paragraph("Top Gaps", STYLES["body_bold"]))
        for g in gaps:
            elements.append(Paragraph(f"&bull; {safe(g)}", STYLES["bullet"]))

    return elements


def build_channel_scores(data: dict, client_name: str = "") -> list:
    elements = []
    elements.extend(section_heading("Channel Scores", client_name))

    scores = data.get("channel_scores", [])
    if not scores:
        elements.append(Paragraph("No channel score data available.", STYLES["body"]))
        return elements

    header = [
        Paragraph("Channel", STYLES["table_header"]),
        Paragraph("Score", STYLES["table_header"]),
        Paragraph("Evidence", STYLES["table_header"]),
    ]

    rows = [header]
    for item in scores:
        channel = Paragraph(safe(item.get("channel", "")), STYLES["table_cell"])
        score_val = item.get("score", "")
        badge = score_badge(score_val)
        evidence = Paragraph(safe(item.get("evidence", "")), STYLES["table_cell"])
        rows.append([channel, badge, evidence])

    col_widths = [2.0 * inch, 1.0 * inch, CONTENT_W - 2.0 * inch - 1.0 * inch]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        *[("BACKGROUND", (0, i), (-1, i), C_BG if i % 2 == 0 else C_WHITE)
          for i in range(1, len(rows))],
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.85, 0.85)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    return elements


def build_narrative(data: dict, client_name: str = "") -> list:
    elements = []
    elements.extend(section_heading("Narrative Analysis", client_name))

    narratives = data.get("narrative_analysis", [])
    if not narratives:
        elements.append(Paragraph("No narrative analysis data available.", STYLES["body"]))
        return elements

    for item in narratives:
        channel = item.get("channel", "")
        content = item.get("content", "")
        elements.append(Paragraph(safe(channel), STYLES["subsection"]))
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for p in paragraphs:
            p = p.replace("\n", " ")
            elements.append(Paragraph(safe(p), STYLES["body"]))

    return elements


def build_gap_analysis(data: dict, client_name: str = "") -> list:
    elements = []
    elements.extend(section_heading("Gap Analysis", client_name))

    gaps = data.get("gap_analysis", [])
    if not gaps:
        elements.append(Paragraph("No gap analysis data available.", STYLES["body"]))
        return elements

    header = [
        Paragraph("Channel", STYLES["table_header"]),
        Paragraph("Current State", STYLES["table_header"]),
        Paragraph("Best Practice", STYLES["table_header"]),
        Paragraph("Impact", STYLES["table_header"]),
    ]

    rows = [header]
    for item in gaps:
        ic = impact_color(item.get("impact", ""))
        impact_html = (
            f'<font face="{FONT_H}" color="{ic}">'
            f'{safe(item.get("impact", ""))}</font>'
        )
        rows.append([
            Paragraph(safe(item.get("channel", "")), STYLES["table_cell"]),
            Paragraph(safe(item.get("current_state", "")), STYLES["table_cell"]),
            Paragraph(safe(item.get("best_practice", "")), STYLES["table_cell"]),
            Paragraph(impact_html, STYLES["table_cell_center"]),
        ])

    col_widths = [1.6 * inch, 1.7 * inch, CONTENT_W - 1.6 * inch - 1.7 * inch - 0.7 * inch, 0.7 * inch]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        *[("BACKGROUND", (0, i), (-1, i), C_BG if i % 2 == 0 else C_WHITE)
          for i in range(1, len(rows))],
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.85, 0.85)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    return elements


def _swot_grid(competitor: dict) -> list:
    elements = []

    name = competitor.get("competitor_name", "Competitor")
    website = competitor.get("website", "")
    positioning = competitor.get("positioning", "")

    elements.append(Paragraph(safe(name), STYLES["subsection"]))
    if website:
        elements.append(Paragraph(f"Website: {safe(website)}", STYLES["body"]))
    if positioning:
        elements.append(Paragraph(safe(positioning), STYLES["body"]))

    def bullet_list(items: list) -> str:
        if not items:
            return "No data available."
        return "<br/>".join(f"&bull; {safe(i)}" for i in items)

    s_content = Paragraph(bullet_list(competitor.get("strengths", [])), STYLES["swot_cell"])
    w_content = Paragraph(bullet_list(competitor.get("weaknesses", [])), STYLES["swot_cell"])
    o_content = Paragraph(bullet_list(competitor.get("opportunities", [])), STYLES["swot_cell"])
    t_content = Paragraph(bullet_list(competitor.get("threats", [])), STYLES["swot_cell"])

    s_header = Paragraph("Strengths", STYLES["swot_header"])
    w_header = Paragraph("Weaknesses", STYLES["swot_header"])
    o_header = Paragraph("Opportunities", STYLES["swot_header"])
    t_header = Paragraph("Threats", STYLES["swot_header"])

    grid_data = [
        [s_header, w_header],
        [s_content, w_content],
        [o_header, t_header],
        [o_content, t_content],
    ]

    half_width = (CONTENT_W - 4) / 2
    grid = Table(grid_data, colWidths=[half_width, half_width])
    grid.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), C_PRIMARY_LIGHT),
        ("BACKGROUND", (1, 0), (1, 0), C_PRIMARY_LIGHT),
        ("BACKGROUND", (0, 2), (0, 2), C_PRIMARY_LIGHT),
        ("BACKGROUND", (1, 2), (1, 2), C_PRIMARY_LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("TEXTCOLOR", (0, 2), (-1, 2), C_WHITE),
        ("BACKGROUND", (0, 1), (0, 1), C_WHITE),
        ("BACKGROUND", (1, 1), (1, 1), C_WHITE),
        ("BACKGROUND", (0, 3), (0, 3), C_WHITE),
        ("BACKGROUND", (1, 3), (1, 3), C_WHITE),
        ("GRID", (0, 0), (-1, -1), 1, colors.Color(0.85, 0.85, 0.85)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(grid)
    elements.append(Spacer(1, 14))
    return elements


def build_competitor_swot(data: dict, client_name: str = "") -> list:
    elements = []
    elements.extend(section_heading("Competitor SWOT Analysis", client_name))

    competitors = data.get("competitor_swot", [])
    if not competitors:
        elements.append(Paragraph("No competitor data available.", STYLES["body"]))
        return elements

    for comp in competitors:
        elements.extend(_swot_grid(comp))

    return elements


def build_recommendations(data: dict, client_name: str = "") -> list:
    elements = []
    elements.extend(section_heading("Recommendations", client_name))

    recs = data.get("recommendations", [])
    if not recs:
        elements.append(Paragraph("No recommendations available.", STYLES["body"]))
        return elements

    header = [
        Paragraph("#", STYLES["table_header"]),
        Paragraph("Channel", STYLES["table_header"]),
        Paragraph("Recommendation", STYLES["table_header"]),
        Paragraph("Impact", STYLES["table_header"]),
        Paragraph("Effort", STYLES["table_header"]),
    ]

    rows = [header]
    for idx, rec in enumerate(recs, 1):
        rows.append([
            Paragraph(str(idx), STYLES["table_cell_center"]),
            Paragraph(safe(rec.get("channel", "")), STYLES["table_cell"]),
            Paragraph(safe(rec.get("action", "")), STYLES["table_cell"]),
            Paragraph(safe(rec.get("impact", "")), STYLES["table_cell"]),
            Paragraph(effort_label(rec.get("effort", "")), STYLES["table_cell_center"]),
        ])

    rec_col = CONTENT_W - 0.3 * inch - 1.6 * inch - 0.7 * inch - 0.9 * inch
    col_widths = [0.3 * inch, 1.6 * inch, rec_col, 0.7 * inch, 0.9 * inch]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        *[("BACKGROUND", (0, i), (-1, i), C_BG if i % 2 == 0 else C_WHITE)
          for i in range(1, len(rows))],
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.85, 0.85)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    return elements


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def build_pdf(data: dict, output_path: str):
    margin = MARGIN

    doc = BaseDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin + 16,
        bottomMargin=margin + 10,
        title=f"{BRAND['tagline']} — {data.get('business_name', '')}",
        author=BRAND["brand_name"],
    )

    content_frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        PAGE_W - doc.leftMargin - doc.rightMargin,
        PAGE_H - doc.topMargin - doc.bottomMargin,
        id="content",
    )

    cover_frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        PAGE_W - doc.leftMargin - doc.rightMargin,
        PAGE_H - doc.topMargin - doc.bottomMargin,
        id="cover",
    )

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame], onPage=_blank_page),
        PageTemplate(id="content", frames=[content_frame], onPage=_header_footer),
    ])

    client_name = data.get("business_name", "")

    elements = []
    elements.extend(build_cover(data))

    elements.extend(build_executive_summary(data, client_name))
    elements.append(Spacer(1, 10))
    elements.extend(build_channel_scores(data, client_name))
    elements.append(Spacer(1, 10))
    elements.extend(build_narrative(data, client_name))
    elements.append(Spacer(1, 10))
    elements.extend(build_gap_analysis(data, client_name))
    elements.append(Spacer(1, 10))
    elements.extend(build_competitor_swot(data, client_name))
    elements.append(Spacer(1, 10))
    elements.extend(build_recommendations(data, client_name))

    doc.build(elements)
    print(f"PDF generated: {output_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a GoToRetreats-branded marketing audit PDF.",
    )
    parser.add_argument("data_positional", nargs="?", help="Input JSON path (positional)")
    parser.add_argument("output_positional", nargs="?", help="Output PDF path (positional)")
    parser.add_argument("--data", help="Input JSON path")
    parser.add_argument("--brand", help="Brand config path (default: auto-detected from skill dir)")
    parser.add_argument("--output", help="Output PDF path")

    args = parser.parse_args()

    # Resolve input: --data takes precedence over positional
    input_path = args.data or args.data_positional
    if not input_path:
        parser.error("Input JSON path required (--data or positional argument)")

    if not os.path.isfile(input_path):
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    # Override brand config path if provided
    if args.brand:
        global BRAND_CONFIG_PATH
        BRAND_CONFIG_PATH = Path(args.brand)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {input_path}: {exc}")
        sys.exit(1)

    # Resolve output: --output takes precedence over positional
    output_path = args.output or args.output_positional
    if not output_path:
        biz_name = data.get("business_name", "unknown")
        output_path = f"marketing_audit_{slugify(biz_name)}.pdf"

    build_pdf(data, output_path)


if __name__ == "__main__":
    main()
