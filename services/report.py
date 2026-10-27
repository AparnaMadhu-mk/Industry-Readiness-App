"""PDF report generation with ReportLab (in memory, no temp files)."""
import io
import math

from reportlab.graphics.shapes import Drawing, Line, Polygon, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

import config

PRIMARY = colors.HexColor("#4f46e5")
INK = colors.HexColor("#1e293b")
MUTED = colors.HexColor("#64748b")


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], textColor=PRIMARY, fontSize=26, leading=30),
        "h1": ParagraphStyle("h1", parent=ss["Heading1"], textColor=PRIMARY, fontSize=16, spaceBefore=10),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], textColor=INK, fontSize=12, spaceBefore=8),
        "body": ParagraphStyle("b", parent=ss["BodyText"], textColor=INK, fontSize=9.5, leading=13),
        "small": ParagraphStyle("s", parent=ss["BodyText"], textColor=MUTED, fontSize=8, leading=10),
    }


def _radar(dims):
    items = [(d["label"], d["score"]) for d in dims.values() if d["score"] is not None]
    size, cx, cy, r = 230, 115, 115, 80
    dr = Drawing(size, size)
    n = len(items)
    if n < 3:
        return dr
    for level in (0.25, 0.5, 0.75, 1.0):
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n - math.pi / 2
            pts += [cx + r * level * math.cos(a), cy + r * level * math.sin(a)]
        dr.add(Polygon(pts, strokeColor=colors.HexColor("#cbd5e1"), fillColor=None, strokeWidth=0.5))
    poly = []
    for i, (label, score) in enumerate(items):
        a = 2 * math.pi * i / n - math.pi / 2
        dr.add(Line(cx, cy, cx + r * math.cos(a), cy + r * math.sin(a), strokeColor=colors.HexColor("#e2e8f0")))
        poly += [cx + r * score / 100 * math.cos(a), cy + r * score / 100 * math.sin(a)]
        lx, ly = cx + (r + 14) * math.cos(a), cy + (r + 14) * math.sin(a)
        anchor = "middle" if abs(math.cos(a)) < 0.3 else ("start" if math.cos(a) > 0 else "end")
        dr.add(String(lx, ly - 3, f"{label.split(' ')[0]} {score:.0f}", fontSize=7, textAnchor=anchor, fillColor=INK))
    dr.add(Polygon(poly, strokeColor=PRIMARY, fillColor=colors.Color(0.31, 0.27, 0.9, alpha=0.25), strokeWidth=1.5))
    return dr


def build_pdf(result):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Industry Readiness Report", author="Industry Readiness App")
    st = _styles()
    meta = result.get("_meta", {})
    story = []

    # 1. Cover
    story += [
        Spacer(1, 30 * mm),
        Paragraph("Industry Readiness Report", st["title"]),
        Paragraph(f"Candidate: <b>{meta.get('candidate') or 'Anonymous'}</b>", st["body"]),
        Paragraph(f"Target role: {config.ROLES.get(meta.get('role'), meta.get('role', ''))}", st["body"]),
        Paragraph(f"Date: {meta.get('created_at', '')}", st["body"]),
        Spacer(1, 12 * mm),
    ]
    band = result["band"]
    cover = Table([[Paragraph(f"<font size=44 color='{band['color']}'><b>{result['overall']:.0f}</b></font>"
                              f"<font size=16 color='#64748b'> / 100</font>", st["body"])],
                   [Paragraph(f"<b>{band['label']}</b>", st["h1"])]], colWidths=[120 * mm])
    cover.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                               ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 10)]))
    story += [cover, Spacer(1, 8 * mm), Paragraph(result["disclaimer"], st["small"]), PageBreak()]

    # 2. Score summary
    story.append(Paragraph("Score summary", st["h1"]))
    story.append(_radar(result["dimensions"]))
    rows = [["Dimension", "Score", "Weight", "Band"]]
    for key, d in result["dimensions"].items():
        w = result["weights"].get(key)
        rows.append([d["label"], f"{d['score']:.0f}" if d["score"] is not None else "Not assessed",
                     f"{w:.0f}%" if w else "-", d["band"]["label"] if d["band"] else "-"])
    t = Table(rows, colWidths=[70 * mm, 28 * mm, 28 * mm, 40 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story += [t, PageBreak()]

    # 3. Resume analysis
    ats = result["ats"]
    story.append(Paragraph("Resume analysis (structure, ATS, readability)", st["h1"]))
    story.append(Paragraph(f"Length: {ats['word_count']} words, about {ats['pages']} page(s).", st["body"]))
    story.append(Paragraph("Sections found: " + (", ".join(ats["found_sections"]) or "none"), st["body"]))
    story.append(Paragraph("Sections missing: " + (", ".join(ats["missing_sections"]) or "none"), st["body"]))
    for w in ats["warnings"]:
        story.append(Paragraph("&bull; " + w, st["body"]))

    # 4. Strengths and gaps per dimension
    story.append(Paragraph("Criterion breakdown", st["h1"]))
    for key, d in result["dimensions"].items():
        story.append(Paragraph(f"{d['label']} - {d['score']:.0f}/100" if d["score"] is not None
                               else f"{d['label']} - not assessed", st["h2"]))
        rows = [["Criterion", "Points", "Evidence"]]
        for c in d["criteria"]:
            pts = f"{c['earned']:.0f}/{c['max']}" if c["assessed"] else "n/a"
            rows.append([Paragraph(c["name"], st["small"]), pts, Paragraph(c["evidence"], st["small"])])
        t = Table(rows, colWidths=[48 * mm, 18 * mm, 100 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                               ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        story.append(t)
    story.append(PageBreak())

    # 5. Action plan
    story.append(Paragraph("Action plan (suggested 30-day order)", st["h1"]))
    weeks = ["Week 1", "Week 1", "Week 2", "Week 3", "Week 4"]
    for r in result["recommendations"]:
        wk = weeks[min(r["priority"] - 1, 4)]
        story.append(Paragraph(f"<b>{r['priority']}. {r['title']}</b> ({r['dimension']}, {wk})", st["body"]))
        story.append(Paragraph(f"<i>Why:</i> {r['why']}", st["small"]))
        story.append(Paragraph(f"<i>Fix:</i> {r['fix']}", st["body"]))
        story.append(Spacer(1, 3 * mm))
    if not result["recommendations"]:
        story.append(Paragraph("No major gaps found - keep your CV and projects up to date.", st["body"]))

    # 6. Methodology
    story += [Paragraph("Methodology and disclaimer", st["h1"]),
              Paragraph("Each dimension is scored 0-100 from weighted criteria. Rule-based checks (about 60%) are combined "
                        "with an AI review (about 40%) when available. Criteria that cannot be assessed (e.g. no GitHub link) "
                        "are excluded and the remaining weights rescaled rather than counted as zero.", st["body"]),
              Paragraph("Weights used: " + ", ".join(f"{config.DIMENSION_LABELS[k]} {v:.0f}%" for k, v in result["weights"].items()), st["body"]),
              Spacer(1, 4 * mm), Paragraph(result["disclaimer"], st["small"])]
    if not result.get("ai_used"):
        story.append(Paragraph("Note: AI feedback was unavailable for this run; the score is rule-based only.", st["small"]))

    doc.build(story)
    buf.seek(0)
    return buf
