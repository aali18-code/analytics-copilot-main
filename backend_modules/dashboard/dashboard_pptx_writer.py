"""Dashboard-themed PowerPoint writer for the React KPI dashboard.

The report plan still comes from report_deck. Cards and tables remain editable;
chart PNGs captured from the same ECharts options as the browser are embedded
when supplied. A native chart is used for legacy callers without PNGs.
"""

from __future__ import annotations

import copy
import io
from datetime import date
from typing import Any

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

from backend_modules.dashboard import pptx_writer as legacy_writer

WIDTH, HEIGHT = 13.333, 7.5
FONT = "Aptos"
NAVY = "193744"
NAVY_LIGHT = "254757"
TEAL = "1B8792"
TEAL_LIGHT = "73C6BE"
TEXT = "203844"
MUTED = "71838D"
FAINT = "95A4AC"
PAGE = "F7F9FA"
WHITE = "FFFFFF"
LINE = "DFE8EB"
TEAL_TINT = "EAF5F4"
BLUE_TINT = "EEF4F7"
ROW_TINT = "F8FBFB"
CHART_COLORS = ("1B8792", "60B3B1", "314C61", "9BC9B0", "C6A765", "89A0B3", "BD8F84", "D7CBB5")


def _clean(value: Any) -> str:
    return legacy_writer._clean(value)


def _rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def _shape(slide, x: float, y: float, w: float, h: float, fill: str, line: str | None = None, radius: float = 0.08):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.adjustments[0] = radius
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    shape.line.color.rgb = _rgb(line or fill)
    shape.line.width = Pt(0.8)
    return shape


def _text(slide, x: float, y: float, w: float, h: float, value: Any, *, size: float = 12,
          color: str = TEXT, bold: bool = False, align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.MIDDLE):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    frame.vertical_anchor = valign
    frame.margin_left = frame.margin_right = Inches(0.02)
    frame.margin_top = frame.margin_bottom = 0
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = _clean(value)
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)
    return box


def _new_slide(prs, *, dark: bool = False):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _rgb(NAVY if dark else PAGE)
    return slide


def _period_label(value: str) -> str:
    try:
        day = date.fromisoformat(value)
        return f"{day.day} {day:%b %Y}"
    except (TypeError, ValueError):
        return _clean(value)


def _period_text(value: str) -> str:
    start, separator, end = _clean(value).partition(" to ")
    return f"{_period_label(start)}  –  {_period_label(end)}" if separator else _clean(value)


def _frame(prs, title: str, number: int, source: str = "", period: str = ""):
    slide = _new_slide(prs)
    _text(slide, 0.58, 0.18, 7.8, 0.27, "PERFORMANCE INTELLIGENCE", size=9, color=TEAL, bold=True)
    _text(slide, 0.58, 0.51, 12.1, 0.58, title, size=25, color=TEXT, bold=True)
    _shape(slide, 0.58, 1.19, 12.16, 0.025, TEAL, TEAL, radius=0)
    if period:
        _text(slide, 9.0, 0.19, 3.73, 0.25, period, size=9, color=MUTED, align=PP_ALIGN.RIGHT)
    _text(slide, 0.58, 7.13, 10.8, 0.2, f"Source: {source}" if source else "Analytics Copilot", size=8, color=FAINT)
    _text(slide, 12.06, 7.11, 0.66, 0.22, str(number), size=9, color=MUTED, align=PP_ALIGN.RIGHT)
    return slide


def _cover(prs, deck: dict[str, Any]) -> None:
    slide = _new_slide(prs, dark=True)
    _shape(slide, 0.68, 0.72, 0.08, 5.93, TEAL_LIGHT, TEAL_LIGHT, radius=0)
    _text(slide, 1.03, 1.13, 10.6, 0.32, "PERFORMANCE INTELLIGENCE", size=13, color=TEAL_LIGHT, bold=True)
    _text(slide, 1.01, 2.08, 11.3, 1.22, "Executive dashboard", size=43, color=WHITE, bold=True)
    _text(slide, 1.03, 3.55, 10.8, 0.55, _period_text(deck.get("subtitle", "")), size=22, color=WHITE)
    _text(slide, 1.03, 6.78, 10.6, 0.28, "ANALYTICS COPILOT  /  KPI REPORT", size=10, color="A9C1C6", bold=True)
    for index, source in enumerate(deck.get("sources", [])[:3]):
        x = 1.03 + index * 2.35
        _shape(slide, x, 4.77, 2.14, 0.58, NAVY_LIGHT, "3B5A65")
        _text(slide, x + 0.13, 4.89, 1.88, 0.3, source, size=12, color=WHITE, bold=True)


def _overview(prs, deck: dict[str, Any], number: int) -> None:
    overview = deck.get("overview") or {}
    slide = _frame(prs, "Period at a glance", number, period=_period_text(deck.get("subtitle", "")))
    _shape(slide, 0.58, 1.46, 12.16, 1.72, NAVY, NAVY)
    _text(slide, 0.9, 1.69, 10.6, 0.28, "REPORTING PERIOD", size=10, color=TEAL_LIGHT, bold=True)
    _text(slide, 0.9, 2.10, 11.1, 0.54, _period_text(deck.get("subtitle", "")), size=25, color=WHITE, bold=True)
    stats = [
        ("SOURCES LOADED", overview.get("sources_count", len(deck.get("sources", [])))),
        ("KPI VIEWS", overview.get("kpi_count", 0)),
        ("AI INSIGHTS", overview.get("ai_count", 0)),
    ]
    for index, (label, value) in enumerate(stats):
        x = 0.58 + index * 4.11
        _shape(slide, x, 3.52, 3.92, 1.6, WHITE, LINE)
        _text(slide, x + 0.22, 3.78, 3.4, 0.62, value, size=31, color=TEXT, bold=True)
        _text(slide, x + 0.22, 4.50, 3.4, 0.25, label, size=10, color=MUTED, bold=True)
    _text(slide, 0.72, 5.63, 11.85, 0.52, "The following sections use the same saved KPI values and commentary as the dashboard.", size=13, color=MUTED)


def _info_box(slide, x: float, y: float, w: float, h: float, heading: str, body: str, *, tint: str = TEAL_TINT):
    _shape(slide, x, y, w, h, tint, LINE)
    _text(slide, x + 0.16, y + 0.12, w - 0.32, 0.25, heading.upper(), size=9, color=TEAL, bold=True)
    _text(slide, x + 0.16, y + 0.42, w - 0.32, max(0.2, h - 0.54), body, size=11, color=TEXT, valign=MSO_ANCHOR.TOP)


def _card(slide, x: float, y: float, w: float, h: float, card: dict[str, Any]) -> None:
    _shape(slide, x, y, w, h, WHITE, LINE)
    _text(slide, x + 0.22, y + 0.17, w - 0.44, 0.27, card.get("id", ""), size=10, color=TEAL, bold=True)
    _text(slide, x + 0.22, y + 0.53, w - 0.44, 0.64, card.get("value", ""), size=31, color=TEXT, bold=True)
    _text(slide, x + 0.22, y + h - 0.61, w - 0.44, 0.38, card.get("label", ""), size=11, color=MUTED)


def _cards_slide(prs, spec: dict[str, Any], number: int, period: str) -> None:
    slide = _frame(prs, spec.get("title", "Key measures"), number, spec.get("source", ""), period)
    cards = list(spec.get("cards", []))
    if not cards:
        raise ValueError("No KPI cards")
    commentary = any(c.get("insight") or c.get("recommendation") for c in cards)
    if commentary:
        top, gap = 1.47, 0.14
        row_h = (5.48 - gap * (len(cards) - 1)) / len(cards)
        for index, card in enumerate(cards):
            y = top + index * (row_h + gap)
            _card(slide, 0.58, y, 3.18, min(row_h, 2.25), card)
            if card.get("insight"):
                _info_box(slide, 3.94, y, 4.20, row_h, "AI insight", card["insight"])
            if card.get("recommendation"):
                _info_box(slide, 8.32, y, 4.42, row_h, "Recommended action", card["recommendation"], tint=BLUE_TINT)
    else:
        count = len(cards)
        gap = 0.2
        width = (12.16 - gap * (count - 1)) / count
        for index, card in enumerate(cards):
            _card(slide, 0.58 + index * (width + gap), 1.65, width, 2.15, card)
        if spec.get("note"):
            _info_box(slide, 0.58, 4.12, 12.16, 1.1, "Data coverage", _clean(spec["note"]))
    if commentary and spec.get("note"):
        _text(slide, 0.65, 6.94, 11.8, 0.22, spec["note"], size=9, color=MUTED)


def _picture_fit(slide, png: bytes, x: float, y: float, w: float, h: float) -> None:
    with Image.open(io.BytesIO(png)) as picture:
        image_w, image_h = picture.size
    scale = min(w / image_w, h / image_h)
    draw_w, draw_h = image_w * scale, image_h * scale
    slide.shapes.add_picture(io.BytesIO(png), Inches(x + (w - draw_w) / 2), Inches(y + (h - draw_h) / 2),
                             width=Inches(draw_w), height=Inches(draw_h))


def _fallback_chart(slide, spec: dict[str, Any], x: float, y: float, w: float, h: float) -> None:
    legacy_writer._add_chart(slide, spec, x, y, w, h)
    chart = slide.shapes[-1].chart
    chart.font.name = FONT
    chart.font.color.rgb = _rgb(MUTED)
    for index, series in enumerate(chart.plots[0].series):
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = _rgb(CHART_COLORS[index % len(CHART_COLORS)])
        if spec.get("type") == "donut":
            for point_index, point in enumerate(series.points):
                point.format.fill.solid()
                point.format.fill.fore_color.rgb = _rgb(CHART_COLORS[point_index % len(CHART_COLORS)])


def _chart_slide(prs, spec: dict[str, Any], number: int, period: str) -> None:
    slide = _frame(prs, spec.get("title", "Chart"), number, spec.get("source", ""), period)
    insights = list(spec.get("insights") or [])
    recommendations = list(spec.get("recommendation") or [])
    has_commentary = bool(insights or recommendations)
    chart_w = 8.0 if has_commentary else 12.16
    _shape(slide, 0.58, 1.45, chart_w, 5.47, WHITE, LINE)
    _text(slide, 0.84, 1.68, chart_w - 0.52, 0.34, spec.get("chart_title") or spec.get("title"), size=15, color=TEXT, bold=True)
    area = (0.83, 2.13, chart_w - 0.5, 4.37)
    if spec.get("chart_png"):
        _picture_fit(slide, spec["chart_png"], *area)
    else:
        _fallback_chart(slide, spec, *area)
    if has_commentary:
        if insights:
            _info_box(slide, 8.78, 1.45, 3.96, 2.58, "AI insight", "\n\n".join(insights))
        if recommendations:
            _info_box(slide, 8.78, 4.20, 3.96, 2.72, "Recommended action", "\n\n".join(recommendations), tint=BLUE_TINT)


def _table_pages(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(spec.get("rows") or [])
    if not rows:
        return []
    columns = list(spec.get("columns") or [])
    longest = max(len(_clean(value)) for row in rows for value in row)
    per_page = 2 if longest > 160 else 6 if len(columns) >= 7 else 8
    pages = []
    for start in range(0, len(rows), per_page):
        page = copy.copy(spec)
        page["rows"] = rows[start:start + per_page]
        if start:
            page["insights"] = []
            page["recommendation"] = []
        pages.append(page)
    for index, page in enumerate(pages, 1):
        if len(pages) > 1:
            page["title"] = f"{spec.get('title', 'Ranked results')} ({index}/{len(pages)})"
    return pages


def _commentary_slide(prs, spec: dict[str, Any], number: int, period: str) -> None:
    slide = _frame(prs, spec.get("title", "Insights and actions"), number, spec.get("source", ""), period)
    insights = "\n\n".join(_clean(value) for value in spec.get("insights", []) if _clean(value))
    recommendations = "\n\n".join(_clean(value) for value in spec.get("recommendation", []) if _clean(value))
    if insights:
        _info_box(slide, 0.58, 1.48, 5.98, 5.42, "AI insight", insights)
    if recommendations:
        _info_box(slide, 6.75, 1.48, 5.99, 5.42, "Recommended action", recommendations, tint=BLUE_TINT)


def _expanded_specs(original: dict[str, Any]) -> list[dict[str, Any]]:
    kind = original.get("type")
    if kind == "cards":
        cards = list(original.get("cards") or [])
        if any(len(_clean(card.get("insight"))) + len(_clean(card.get("recommendation"))) > 320 for card in cards):
            return [{**original, "title": f"{original.get('title', 'Key measures')} – {card.get('id', '')}", "cards": [card]} for card in cards]
        return [original]
    pages = _table_pages(original) if kind == "table" else [original]
    if kind not in ("table", "bar", "line", "donut"):
        return pages
    insights = list(original.get("insights") or [])
    recommendations = list(original.get("recommendation") or [])
    limit = 260 if kind == "table" else 620
    if sum(len(_clean(value)) for value in insights + recommendations) <= limit:
        return pages
    for page in pages:
        page["insights"] = []
        page["recommendation"] = []
    return pages + [{"type": "commentary", "title": f"{original.get('title', '')}: insights and actions",
                     "source": original.get("source", ""), "insights": insights, "recommendation": recommendations}]


def _cell(cell, value: Any, *, fill: str, color: str, size: float, bold: bool = False, align=PP_ALIGN.LEFT) -> None:
    cell.fill.solid()
    cell.fill.fore_color.rgb = _rgb(fill)
    cell.margin_left = cell.margin_right = Inches(0.08)
    cell.margin_top = cell.margin_bottom = Inches(0.05)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame = cell.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    if isinstance(value, int) and not isinstance(value, bool):
        run.text = f"{value:,}"
    elif isinstance(value, float):
        run.text = f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"
    else:
        run.text = _clean(value)
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)


def _table_slide(prs, spec: dict[str, Any], number: int, period: str) -> None:
    slide = _frame(prs, spec.get("title", "Ranked results"), number, spec.get("source", ""), period)
    columns = [_clean(c) for c in spec.get("columns", [])]
    rows = list(spec.get("rows") or [])
    if not columns or not rows:
        raise ValueError("Empty ranked table")
    insights = list(spec.get("insights") or [])
    recommendations = list(spec.get("recommendation") or [])
    has_commentary = bool(insights or recommendations)
    _shape(slide, 0.58, 1.45, 12.16, 5.52 if not has_commentary else 4.42, WHITE, LINE)
    _text(slide, 0.83, 1.64, 11.65, 0.27, "RANKED RESULTS", size=10, color=TEAL, bold=True)
    x, y, width = 0.83, 2.05, 11.66
    header_h = 0.62
    available = 4.58 if not has_commentary else 3.47
    row_h = min(1.45, max(0.46, (available - header_h) / len(rows)))
    graphic = slide.shapes.add_table(len(rows) + 1, len(columns), Inches(x), Inches(y), Inches(width), Inches(header_h + row_h * len(rows)))
    table = graphic.table
    weights = []
    for i, name in enumerate(columns):
        max_content = max(len(_clean(row[i])) if i < len(row) else 0 for row in rows)
        weight = max(9, min(30, len(name) + max_content / 6))
        if i == 0 and max_content > 35:
            weight *= 1.8
        weights.append(weight)
    total = sum(weights)
    for i, weight in enumerate(weights):
        table.columns[i].width = Inches(width * weight / total)
    table.rows[0].height = Inches(header_h)
    for row_index in range(1, len(table.rows)):
        table.rows[row_index].height = Inches(row_h)
    for i, name in enumerate(columns):
        _cell(table.cell(0, i), name, fill="F2F6F7", color="536775", size=10, bold=True)
    for row_index, values in enumerate(rows, 1):
        for col_index in range(len(columns)):
            value = values[col_index] if col_index < len(values) else ""
            align = PP_ALIGN.RIGHT if isinstance(value, (int, float)) else PP_ALIGN.LEFT
            _cell(table.cell(row_index, col_index), value, fill=WHITE if row_index % 2 else ROW_TINT,
                  color=TEXT, size=10 if len(columns) < 7 else 9, align=align)
    if has_commentary:
        if insights:
            _info_box(slide, 0.58, 6.05, 5.98, 0.88, "AI insight", " ".join(insights))
        if recommendations:
            _info_box(slide, 6.75, 6.05, 5.99, 0.88, "Recommended action", " ".join(recommendations), tint=BLUE_TINT)


def _closing(prs, number: int) -> None:
    slide = _new_slide(prs, dark=True)
    _shape(slide, 0.70, 1.42, 0.08, 4.65, TEAL_LIGHT, TEAL_LIGHT, radius=0)
    _text(slide, 1.08, 2.35, 10.8, 0.38, "ANALYTICS COPILOT", size=12, color=TEAL_LIGHT, bold=True)
    _text(slide, 1.05, 3.0, 11.0, 1.2, "End of report", size=43, color=WHITE, bold=True)
    _text(slide, 1.08, 4.31, 10.7, 0.48, "Review the saved dashboard for interactive exploration and full source detail.", size=16, color="A9C1C6")
    _text(slide, 12.03, 7.11, 0.66, 0.22, str(number), size=9, color="A9C1C6", align=PP_ALIGN.RIGHT)


def build_deck(deck: dict[str, Any]) -> tuple[bytes, list[str]]:
    """Build an editable dashboard-style deck; return PPTX bytes and warnings."""
    prs = Presentation()
    prs.slide_width = Inches(WIDTH)
    prs.slide_height = Inches(HEIGHT)
    prs.core_properties.title = "Executive dashboard"
    prs.core_properties.author = "Analytics Copilot"
    _cover(prs, deck)
    _overview(prs, deck, 2)
    number = 2
    period = _period_text(deck.get("subtitle", ""))
    for original in deck.get("slides", []):
        specs = _expanded_specs(original)
        for spec in specs:
            number += 1
            kind = spec.get("type")
            if kind == "cards":
                _cards_slide(prs, spec, number, period)
            elif kind == "table":
                _table_slide(prs, spec, number, period)
            elif kind in ("bar", "line", "donut"):
                _chart_slide(prs, spec, number, period)
            elif kind == "commentary":
                _commentary_slide(prs, spec, number, period)
            else:
                raise ValueError(f"Unsupported dashboard slide type: {kind}")
    _closing(prs, number + 1)
    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue(), []
