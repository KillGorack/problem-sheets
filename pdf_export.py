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


def _cover_picture(pth, box_w, box_h, dpi=220):
    """The picture cropped from the centre to the box's shape and scaled to fill it exactly
    (like CSS object-fit: cover - no stretching). None if the file can't be read."""
    import io
    from PIL import Image as PILImage
    from reportlab.platypus import Image as RLImage
    try:
        with PILImage.open(pth) as im:
            im = im.convert("RGB")
            w, h = im.size
            box_ratio = box_w / box_h
            if w / h > box_ratio:                      # too wide: trim the sides
                cw = round(h * box_ratio)
                im = im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
            else:                                      # too tall: trim top and bottom
                ch = round(w / box_ratio)
                im = im.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))
            px = (round(box_w / 72 * dpi), round(box_h / 72 * dpi))
            if im.width > px[0]:
                im = im.resize(px, PILImage.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=88)
    except OSError:
        return None
    buf.seek(0)
    return RLImage(buf, width=box_w, height=box_h)


def problem_sheet(path: str, p: dict, actions: list[dict], pictures: list | None = None) -> None:
    """One problem on a landscape page, laid out like a standard form:
        [dot] TS-0003  Title
        Category >> Sub-category | Created / Updated             | picture box
        Champion                 |                               |
        Description              | Root cause                    |
        Actions table (Actions, Who, Due, Completion)
        footer: Project ............ Open | Printed <date>   or   Closed <date> | Printed <date>
    The picture box is the same size on every sheet: the first picture fills it (cropped, never
    stretched), or it stays empty. Other pictures are not printed."""
    r = _rl()
    colors, mm = r["colors"], r["mm"]
    Table, TableStyle, Spacer = r["Table"], r["TableStyle"], r["Spacer"]
    from reportlab.platypus import Paragraph
    ss = r["getSampleStyleSheet"]()
    P = r["ParagraphStyle"]
    gray, rule = colors.Color(.35, .35, .35), colors.Color(.55, .6, .7)
    base = P("base", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=12.5)
    info = P("info", parent=base, fontSize=10.5, leading=14)
    info_bold = P("infob", parent=info, fontName="Helvetica-Bold")
    label = P("label", parent=base, fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=gray, spaceBefore=6)
    h1 = P("h1", parent=base, fontSize=18, leading=23)
    cell = P("cell", parent=base, fontSize=9.5, leading=12.5)
    cell_head = P("cellh", parent=cell, fontName="Helvetica-Bold", fontSize=8.5, textColor=gray)
    no = db.number(p["id"])
    project = p.get("project") or "No project"

    page = r["landscape"](r["A4"])
    margin = 10 * mm
    doc = r["SimpleDocTemplate"](path, pagesize=page, leftMargin=margin, rightMargin=margin,
                                 topMargin=margin, bottomMargin=margin + 9 * mm,
                                 title=f"{no} {p['title']}", author="Problem Sheets")
    width = page[0] - 2 * margin
    flat = [("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]

    # ---- header: dot, number and title (the status is in the footer)
    head = Table([[_dot(p.get("severity_color") or "#888888", 4.6),
                   Paragraph(f"{escape(no)}&nbsp;&nbsp;&nbsp;{escape(p['title'])}", h1)]],
                 colWidths=[9 * mm, width - 9 * mm])
    head.setStyle(TableStyle(flat + [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                                     ("LINEBELOW", (0, 0), (-1, -1), 0.8, rule)]))

    # ---- body: three columns
    pic_w, pic_h = 78 * mm, 56 * mm
    text_w = (width - pic_w - 12 * mm) / 2
    where = " \u00bb ".join(x for x in (p.get("category"), p.get("subcategory")) if x) or "No category"
    # two rows - info lines, then the texts - so DESCRIPTION and ROOT CAUSE always line up
    left_info = [Paragraph(escape(where), info),
                 Paragraph(f"Champion: {escape(p.get('champion') or '-')}", info_bold)]
    dates = [f"Created: {p['created_at'][:10]}", f"Updated: {p['updated_at'][:10]}"]   # Closed: in the footer
    mid_info = [Paragraph(escape(d), info) for d in dates]
    left_text = [_para("DESCRIPTION", label), _para(p["description"] or "-", base)]
    mid_text = [_para("ROOT CAUSE", label), _para(p["root_cause"] or "Not yet determined.", base)]
    first = next((im for im in (_cover_picture(x, pic_w, pic_h) for x in (pictures or [])) if im), "")
    picture = Table([[first]], colWidths=[pic_w], rowHeights=[pic_h])     # fixed box, empty or filled
    picture.setStyle(TableStyle(flat + [("BOX", (0, 0), (-1, -1), 0.6, colors.Color(.45, .45, .45))]))
    texts = Table([[left_info, mid_info], [left_text, mid_text]], colWidths=[text_w + 6 * mm] * 2)
    texts.setStyle(TableStyle(flat + [("VALIGN", (0, 0), (-1, -1), "TOP"), ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
                                      ("TOPPADDING", (0, 1), (-1, 1), 3 * mm)]))
    body = Table([[texts, picture]], colWidths=[2 * (text_w + 6 * mm), pic_w])   # the picture can't stretch the text rows
    body.setStyle(TableStyle(flat + [("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                                     ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                                     ("LINEBELOW", (0, 0), (-1, -1), 0.8, rule)]))

    # ---- actions
    rows = [[_para(t, cell_head) for t in ("ACTIONS", "WHO", "DUE", "COMPLETION")]]
    cell_late = P("celllate", parent=cell, textColor=colors.Color(.66, .12, .12))
    rows += [[_para(a["description"], cell), _para(a.get("owner") or "-", cell),
              _para(a["due_date"] or "-", cell_late if db.is_overdue(a["due_date"], a["status"] != db.ACTION_DONE)
                    else cell), _para(a["status"], cell)] for a in actions]
    if len(rows) == 1:
        rows.append([_para("No actions recorded.", cell), "", "", ""])
    # Due and Completion are tucked to their contents (a date; the longest stage name or the heading),
    # Who keeps a fixed share, Action takes the rest
    from reportlab.pdfbase.pdfmetrics import stringWidth
    gap = 9 * mm
    due_w = max(stringWidth("2026-12-31", "Helvetica", cell.fontSize),
                stringWidth("DUE", "Helvetica-Bold", cell_head.fontSize)) + gap
    stage_w = max([stringWidth(s, "Helvetica", cell.fontSize) for s in db.ACTION_STAGES] +
                  [stringWidth("COMPLETION", "Helvetica-Bold", cell_head.fontSize)]) + 4 * mm   # a little slack
    who_w = width * .18
    acts = Table(rows, colWidths=[width - who_w - due_w - stage_w, who_w, due_w, stage_w], repeatRows=1)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),                    # no box, no shading: rules only
             ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.Color(.35, .35, .35)),
             ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.Color(.8, .8, .8)),
             ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    acts.setStyle(TableStyle(style))

    story = [head, body, Spacer(1, 6 * mm), acts]

    def frame(canvas, doc):
        canvas.saveState()
        w, h = doc.pagesize
        canvas.setStrokeColor(rule)
        canvas.setLineWidth(0.8)
        foot_y = margin + 6 * mm
        canvas.line(margin, foot_y, w - margin, foot_y)
        canvas.setFont("Helvetica", 10)
        canvas.setFillGray(0.1)
        canvas.drawString(margin, margin + 1 * mm, project)
        # right side, drawn right to left:  <b>Status</b> [closed date]   |   Printed <date>
        x = w - margin
        canvas.setFillGray(0.3)
        closed = f" {p['closed_date']}" if p["status"] == "Closed" and p.get("closed_date") else ""
        for text, font in reversed([(p["status"], "Helvetica-Bold"), (f"{closed}   |   ", "Helvetica"),
                                    (f"Printed {db.today()}", "Helvetica")]):
            canvas.setFont(font, 9)
            x -= canvas.stringWidth(text, font, 9)
            canvas.drawString(x, margin + 1 * mm, text)
        canvas.restoreState()

    doc.build(story, onFirstPage=frame, onLaterPages=frame)


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


def protocol(path: str, project: str, subtitle: str, rows: list[dict], meeting: str = "",
             accent: str = "#000000", title: str = "Protocol", detail: bool = True,
             attendees: list[str] | None = None) -> None:
    """The Protocol report: Project > Category > Sub-category > Problem (title, description) > actions.
    rows: problems from Store.problems, each with its actions under "_actions".
    Every action table sits at the same indent with the same column widths, so the columns line up
    down the whole document.
    Title: "Protocol - <project>"; meeting: the 'When: ... | Where: ...' line under it. accent: the color of
    Category (larger, bold), Sub-category (bold) and problem titles.
    The Agenda is the same report with title="Agenda", detail=False (problem titles only) and the
    attendees listed under the meeting line."""
    r = _rl()
    colors, mm = r["colors"], r["mm"]
    Table, TableStyle, Spacer, KeepTogether = r["Table"], r["TableStyle"], r["Spacer"], r["KeepTogether"]
    from reportlab.platypus import Indenter, Paragraph
    ss = r["getSampleStyleSheet"]()
    P = r["ParagraphStyle"]
    gray = colors.Color(.4, .4, .4)
    base = P("base", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=12.5)
    small = P("small", parent=base, fontSize=8.5, textColor=gray)
    big = P("big", parent=base, fontName="Helvetica-Bold", fontSize=22, leading=30)
    h_proj = P("hp", parent=base, fontName="Helvetica-Bold", fontSize=15, leading=19, spaceBefore=10, spaceAfter=2)
    tint = colors.HexColor(accent)
    h_cat = P("hc", parent=base, fontName="Helvetica-Bold", fontSize=13, leading=17, spaceBefore=9, spaceAfter=1,
              textColor=tint)
    h_sub = P("hs", parent=base, fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=6, textColor=tint)
    names = P("names", parent=base, fontSize=8.5, leading=11, textColor=gray)
    meet = P("meet", parent=base, fontSize=10, textColor=gray, spaceAfter=2)
    h_prob = P("hpr", parent=base, fontName="Helvetica", fontSize=10, leading=13, spaceBefore=7, textColor=tint)
    cell = P("cell", parent=base, fontSize=9, leading=11.5)
    cell_head = P("cellh", parent=cell, fontName="Helvetica-Bold")
    cell_gray = P("cellg", parent=cell, textColor=gray)
    cell_late = P("celll", parent=cell, textColor=colors.Color(.66, .12, .12))

    page = r["A4"]
    doc = r["SimpleDocTemplate"](path, pagesize=page, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm,
                                 bottomMargin=18 * mm, title=f"Protocol {project}", author="Problem Sheets")
    width = page[0] - 32 * mm
    step = 6 * mm                                   # indent per level
    act_level = 4                                   # action tables: one step past the deepest problem
    act_w = width - act_level * step
    col_w = [act_w * .52, act_w * .19, act_w * .15, act_w * .14]

    title_style = P("ptitle", parent=big, fontName="Helvetica")
    story = [Paragraph(f"<b>{escape(title)}</b>&nbsp;&nbsp;\u2013&nbsp;&nbsp;{escape(project)}", title_style)]
    if meeting:
        story.append(_para(meeting, meet))
    if attendees:
        story.append(Paragraph(f"<b>Attendees:</b>&nbsp;&nbsp;{escape(', '.join(attendees))}", meet))
    story += [Spacer(1, 2 * mm),
             _para(f"{subtitle}   |   {len(rows)} topic(s)   |   {db.today()}", small),
             Spacer(1, 3 * mm)]

    def at(level, flowables):
        """The flowables, indented to a level."""
        return [Indenter(left=level * step)] + flowables + [Indenter(left=-level * step)]

    pending = []                                    # headings waiting for their first problem

    def heading(text, style, level):
        """Group headings ride along in the next problem's keep-together block, so a heading never
        ends up alone at the bottom of a page."""
        pending.append(_para(text, P(f"{style.name}{level}", parent=style, leftIndent=level * step)))

    def problem(p, level):
        info = "  |  ".join(x for x in (p["severity"], p.get("champion"),
                                        p["status"] if p["status"] != "Open" else "") if x)
        head = (f"{escape(db.number(p['id']))}&nbsp;&nbsp;&nbsp;{escape(p['title'])}&nbsp;&nbsp;&nbsp;"
                f'<font name="Helvetica" size="8.5" color="#666666">{escape(info)}</font>')
        if not detail:                        # agenda: the title and who discusses it (its action owners)
            who = sorted({a["owner"] for a in p.get("_actions", []) if a.get("owner")}, key=str.lower)
            head = f"{escape(db.number(p['id']))}&nbsp;&nbsp;&nbsp;{escape(p['title'])}"
            block = pending + at(level, [Paragraph(head, h_prob)] +
                                 ([_para(", ".join(who), names)] if who else []))   # names under the title
            pending.clear()
            return [KeepTogether(block)]
        block = at(level, [Paragraph(head, h_prob)])
        if (p["description"] or "").strip():
            block += at(level, [_para(p["description"].strip(), base)])
        acts = p.get("_actions", [])
        if acts:
            data = [[Paragraph(h, cell_head) for h in ("Action", "Who", "Stage", "Due")]]
            for a in acts:
                done = a["status"] == db.ACTION_DONE
                st = cell_gray if done else cell
                late = db.is_overdue(a["due_date"], not done)
                data.append([_para(a["description"], st), _para(a.get("owner") or "-", st), _para(a["status"], st),
                             _para(a["due_date"] or "-", cell_late if late else st)])
            t = Table(data, colWidths=col_w, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.Color(.35, .35, .35)),
                                   ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.Color(.8, .8, .8)),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                   ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            block += [Spacer(1, 1.5 * mm)] + at(act_level, [t])
        else:
            block += [Spacer(1, 1 * mm)] + at(act_level, [_para("No actions.", cell_gray)])
        block = pending + block
        pending.clear()
        return [KeepTogether(block)]          # a problem never splits from its actions across pages

    if not rows:
        story.append(_para("No topics match this project and filter.", base))
    groups = db.protocol_groups(rows)
    for proj, cats in groups:
        if len(groups) > 1 or proj != project:            # one project: the page title already names it
            heading(proj, h_proj, 0)
        for cat, direct, subs in cats:
            heading(cat, h_cat, 1)            # one step in from the project / title
            for p in direct:                  # no sub-category: right under the category
                story += problem(p, 2)
            for sub, problems in subs:
                heading(sub, h_sub, 2)
                for p in problems:
                    story += problem(p, 3)

    f = _footer(f"{project}  |  {title}")
    doc.build(story, onFirstPage=f, onLaterPages=f)
