"""PDF output: one problem sheet, and a table of open items. Needs reportlab
(Fedora: sudo dnf install python3-reportlab). Print output is deliberately neutral
black/white/gray, not the on-screen theme."""
from __future__ import annotations

import datetime as dt
from xml.sax.saxutils import escape

import db


class PdfUnavailable(Exception):
    pass


def _rl():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)
    except ImportError as e:
        raise PdfUnavailable("PDF export needs the reportlab package.\n\nInstall it with:\n"
                             "sudo dnf install python3-reportlab") from e
    return locals()


def _para(text, style):
    from reportlab.platypus import Paragraph
    return Paragraph(escape(text or "").replace("\n", "<br/>") or "&nbsp;", style)


def _dot(color: str, mm_size: float = 3.6):
    """A filled circle flowable in the severity color."""
    from reportlab.graphics.shapes import Circle, Drawing
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    r = mm_size * mm / 2
    d = Drawing(2 * r, 2 * r)
    d.add(Circle(r, r, r, fillColor=HexColor(color), strokeColor=None))
    return d


def _footer(label):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillGray(0.4)
        w, _ = doc.pagesize
        canvas.drawString(doc.leftMargin, 10 * 2.835, f"{label}  |  Printed {db.today()}")
        canvas.drawRightString(w - doc.rightMargin, 10 * 2.835, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def problem_sheet(path: str, p: dict, actions: list[dict], pictures: list | None = None) -> None:
    r = _rl()
    colors, mm = r["colors"], r["mm"]
    Table, TableStyle, Spacer, KeepTogether = r["Table"], r["TableStyle"], r["Spacer"], r["KeepTogether"]
    ss = r["getSampleStyleSheet"]()
    P = r["ParagraphStyle"]
    base = P("base", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=13)
    small = P("small", parent=base, fontSize=8, textColor=colors.Color(.35, .35, .35))
    label = P("label", parent=base, fontName="Helvetica-Bold", fontSize=8, textColor=colors.Color(.35, .35, .35))
    h1 = P("h1", parent=base, fontName="Helvetica-Bold", fontSize=17, leading=21)
    h2 = P("h2", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=10, spaceAfter=3)
    no = db.number(p["id"])
    doc = r["SimpleDocTemplate"](path, pagesize=r["A4"], leftMargin=18 * mm, rightMargin=18 * mm,
                                 topMargin=16 * mm, bottomMargin=18 * mm, title=f"{no} {p['title']}",
                                 author="Problem Sheets")
    width = r["A4"][0] - 36 * mm
    project = p.get("project") or "No project"
    title = P("title", parent=base, fontName="Helvetica-Bold", fontSize=22, leading=30)   # room for descenders
    head = Table([[_dot(p.get("severity_color") or "#888888", 4.2), _para(f"{no}  {p['title']}", h1)]],
                 colWidths=[8 * mm, width - 8 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    story = [_para(project, title), Spacer(1, 4 * mm), head, Spacer(1, 5 * mm)]

    def cell(name, value):
        return [_para(name.upper(), label), _para(value or "-", base)]

    meta = Table([[cell("Severity", p["severity"]), cell("Status", p["status"]), cell("Category", p.get("category")),
                   cell("Champion", p.get("champion"))],
                  [cell("Created", p["created_at"][:10]), cell("Updated", p["updated_at"][:10]),
                   cell("Closed", p["closed_date"]), cell("Open actions", str(p.get("open_actions", "")))]],
                 colWidths=[width / 4] * 4)
    meta.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, colors.Color(.3, .3, .3)),
                              ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.Color(.7, .7, .7)),
                              ("BACKGROUND", (0, 0), (-1, -1), colors.Color(.96, .96, .96)),
                              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [meta, _para("Description", h2), _para(p["description"], base),
              _para("Root cause", h2), _para(p["root_cause"] or "Not yet determined.", base),
              _para("Actions", h2)]

    head = [_para(t, label) for t in ("ACTIONS", "WHO", "DUE", "COMPLETION")]
    rows = [head] + [[_para(a["description"], base), _para(a.get("owner") or "-", base),
                      _para(a["due_date"] or "-", base), _para(a["status"], base)] for a in actions]
    if len(rows) == 1:
        rows.append([_para("No actions recorded.", base), "", "", ""])
    t = Table(rows, colWidths=[width * .52, width * .20, width * .13, width * .15], repeatRows=1)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, colors.Color(.3, .3, .3)),
             ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.Color(.7, .7, .7)),
             ("BACKGROUND", (0, 0), (-1, 0), colors.Color(.85, .85, .85)),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    for i, a in enumerate(actions, start=1):
        if db.is_overdue(a["due_date"], a["status"] != db.ACTION_DONE):
            style.append(("TEXTCOLOR", (2, i), (2, i), colors.Color(.66, .12, .12)))
    t.setStyle(TableStyle(style))
    story.append(t)

    if pictures:
        from PIL import Image as PILImage
        from reportlab.platypus import Image as RLImage
        story.append(_para("Pictures", h2))
        cells, cw, maxh = [], (width - 8 * mm) / 3, 52 * mm
        for pth in pictures:
            try:
                with PILImage.open(pth) as im:
                    w, h = im.size
                k = min(cw / w, maxh / h)
                cells.append(RLImage(str(pth), width=w * k, height=h * k))
            except OSError:
                continue
        rows3 = [cells[i:i + 3] + [""] * (3 - len(cells[i:i + 3])) for i in range(0, len(cells), 3)]
        if rows3:
            pt = Table(rows3, colWidths=[cw + 4 * mm] * 3)
            pt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
            story.append(pt)

    f = _footer(f"{project}  |  {no}")
    doc.build(story, onFirstPage=f, onLaterPages=f)


def open_items(path: str, title: str, columns: list[tuple[str, float]], rows: list[list[str]],
               overdue_rows: set[int] | None = None, project: str = "All projects",
               dots: list[str] | None = None) -> None:
    """columns: [(heading, relative width)]; rows: list of cell-text lists.
    dots: optional severity color (#RRGGBB) per row, drawn as a dot in a first column."""
    r = _rl()
    colors, mm = r["colors"], r["mm"]
    Table, TableStyle, Spacer = r["Table"], r["TableStyle"], r["Spacer"]
    ss = r["getSampleStyleSheet"]()
    P = r["ParagraphStyle"]
    base = P("base", parent=ss["Normal"], fontName="Helvetica", fontSize=8.5, leading=11)
    head = P("head", parent=base, fontName="Helvetica-Bold")
    h1 = P("h1", parent=base, fontName="Helvetica-Bold", fontSize=16, leading=20)
    small = P("small", parent=base, textColor=colors.Color(.35, .35, .35))
    page = r["landscape"](r["A4"])
    doc = r["SimpleDocTemplate"](path, pagesize=page, leftMargin=14 * mm, rightMargin=14 * mm,
                                 topMargin=14 * mm, bottomMargin=16 * mm, title=title, author="Problem Sheets")
    width = page[0] - 28 * mm
    dot_w = 8 * mm if dots else 0
    total = sum(w for _, w in columns)
    data = [[_para(h, head) for h, _ in columns]] + [[_para(c, base) for c in row] for row in rows]
    widths = [(width - dot_w) * w / total for _, w in columns]
    if dots:
        data[0].insert(0, "")
        for r, color in zip(data[1:], dots):
            r.insert(0, _dot(color, 3.0))
        widths.insert(0, dot_w)
    if not rows:
        data.append([_para("Nothing open.", base)] + [""] * (len(data[0]) - 1))
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, colors.Color(.3, .3, .3)),
             ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.Color(.75, .75, .75)),
             ("BACKGROUND", (0, 0), (-1, 0), colors.Color(.85, .85, .85)),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(.96, .96, .96)]),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for i in (overdue_rows or ()):
        style.append(("TEXTCOLOR", (0, i + 1), (-1, i + 1), colors.Color(.66, .12, .12)))
    t.setStyle(TableStyle(style))
    big = P("big", parent=base, fontName="Helvetica-Bold", fontSize=22, leading=30)   # room for descenders
    story = [_para(project, big), Spacer(1, 3 * mm),
             _para(f"{title}   |   {len(rows)} item(s)   |   {dt.date.today().isoformat()}", small),
             Spacer(1, 5 * mm), t]
    f = _footer(f"{project}  |  {title}")
    doc.build(story, onFirstPage=f, onLaterPages=f)
