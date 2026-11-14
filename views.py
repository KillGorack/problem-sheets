"""Screens for Problem Sheets. All styling comes from dave_theme; no colors or sizes here."""
from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

import dave_theme as ui
import db
import pdf_export
import widgets
from dave_theme import C, GUTTER
from version import APP_NAME, VERSION

STAGE_RANK = {s: i for i, s in enumerate(db.ACTION_STAGES)}
IN = 14            # inner padding of a panel
GAP = 10           # gap between controls (= GUTTER)


# ---------------------------------------------------------------- shared helpers
ALL_PROJECTS = "All projects"


def project_names(store):
    return [ALL_PROJECTS] + [p["name"] for p in store.items("projects")]


def project_id(store, name):
    return next((p["id"] for p in store.items("projects") if p["name"] == name), None)


def sync_project_select(app, select):
    """Keep a Project filter in step with the app-wide project."""
    names = project_names(app.store)
    select.configure(values=names)
    if app.project not in names:
        app.project = None
    select.set(app.project or ALL_PROJECTS)


def open_path(app, path):
    """Open a folder in the system file manager."""
    import os
    import subprocess
    import sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))                      # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        ui.dialog(app, "Could not open the folder", f"{path}\n\n{e}", ("OK",))


def problem_columns():
    return [
        {"key": "dot", "title": "", "weight": 0.7, "image": True, "size": 14,
         "sortkey": lambda r: -r["severity_rank"]},
        {"key": "no", "title": "No.", "weight": 1, "sortkey": lambda r: r["_id"]},
        {"key": "project", "title": "Project", "weight": 1.5},
        {"key": "title", "title": "Title", "weight": 4, "wrap": 250},
        {"key": "severity", "title": "Severity", "weight": 1.3, "sortkey": lambda r: -r["severity_rank"]},
        {"key": "category", "title": "Category", "weight": 1.5},
        {"key": "subcategory", "title": "Sub-category", "weight": 1.7},
        {"key": "champion", "title": "Champion", "weight": 1.6},
        {"key": "status", "title": "Status", "weight": 1},
        {"key": "open_actions", "title": "Open actions", "weight": 1.7, "anchor": "e"},
    ]


def problem_rows(rows):
    return [{"_id": p["id"], "dot": f"dot:{p['severity_color']}", "severity_rank": p["severity_rank"] or 0,
             "no": db.number(p["id"]), "project": p["project"] or "", "title": p["title"], "severity": p["severity"],
             "category": p["category"] or "", "subcategory": p["subcategory"] or "",
             "champion": p["champion"] or "", "status": p["status"],
             "created": p["created_at"][:10], "updated": p["updated_at"][:10],   # kept for the PDF
             "open_actions": p["open_actions"]} for p in rows]


def problem_color(row, key):
    if row["status"] == "Closed" and key in ("status", "title"):
        return "muted"
    return None


def action_color(row, key):
    if key == "due" and db.is_overdue(row["due"], row["status"] != db.ACTION_DONE):
        return "error"
    if row["status"] == db.ACTION_DONE and key in ("status", "action"):
        return "muted"
    return None


def remembered_dir(app, key):
    """The folder last used for this kind of file dialog, if it still exists."""
    from pathlib import Path
    d = app.settings.get(key)
    return d if d and Path(d).is_dir() else None


def remember_dir(app, key, path):
    from pathlib import Path
    folder = str(Path(path).parent)
    if app.settings.get(key) != folder:
        app.save({key: folder})


def pick_pdf_path(app, name):
    path = filedialog.asksaveasfilename(parent=app, title="Save PDF", initialfile=name,
                                        initialdir=remembered_dir(app, "last_pdf_dir"),
                                        defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
    if path:
        remember_dir(app, "last_pdf_dir", path)
    return path


def run_pdf(app, make, name):
    """Ask for a path, run make(path); report problems in a dialog and the toolbar note."""
    path = pick_pdf_path(app, name)
    if not path:
        return
    try:
        make(path)
    except pdf_export.PdfUnavailable as e:
        ui.dialog(app, "PDF export unavailable", str(e), ("OK",))
        return
    except OSError as e:
        ui.dialog(app, "Could not save PDF", str(e), ("OK",))
        return
    app.note(f"Saved {path}", "success")


def title_label(parent, text):
    return ctk.CTkLabel(parent, text=text, anchor="w", height=0, text_color=C["text_strong"],
                        font=ui.font(ui.FONT_SIZE + 4, "bold"))


def title_only(parent, text, icon=None):
    """Title bar for a page with no buttons on it: same height as the ones that have icon buttons.
    The icon sits where the + sits on Problems, so the titles line up from page to page."""
    top = ui.Panel(parent)
    if icon:
        ctk.CTkLabel(top, text="", image=ui.icon(icon), width=ui.BTN, height=ui.BTN).pack(
            side="left", padx=(8, 0), pady=6)
    lbl = title_label(top, text)
    lbl.configure(height=ui.BTN)
    lbl.pack(side="left", padx=(2, 0) if icon else IN, pady=6)
    return top


def single(fn):
    """Let only one dialog open at a time. A dialog grabs the mouse a moment after it appears; until
    then, quick extra clicks (a double-click on a row, a second click on a pencil) would open more."""
    import functools

    @functools.wraps(fn)
    def run(*a, **kw):
        if single.busy:
            return None
        single.busy = True
        try:
            return fn(*a, **kw)
        finally:
            single.busy = False
    return run


single.busy = False


def danger(btn):
    btn.configure(text_color=C["error"])
    return btn


def button(parent, text, command=None, **kw):
    return ui.button(parent, text, command, width=100, **kw)


# ---------------------------------------------------------------- left bar
SECTIONS = (("Topics", "clipboard-list"), ("Protocol", "scroll-text"), ("Agenda", "calendar"))


class Sidebar(ui.Panel):
    """Left bar with the app's sections. The current one gets stronger text (no fill), hover fills."""
    WIDTH = 180

    def __init__(self, app, parent):
        super().__init__(parent, width=self.WIDTH)
        self.app = app
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        self.buttons = {}
        for i, (name, icon) in enumerate(SECTIONS):
            b = ctk.CTkButton(self, text=name, anchor="w", image=ui.icon(icon, "muted"), compound="left",
                              font=ui.font(), fg_color="transparent", hover_color=C["hover"],
                              text_color=C["text"], corner_radius=ui.RADIUS, height=34,
                              command=lambda n=name: app.guard(lambda: app.show(n)))
            b.grid(row=i, column=0, sticky="ew", padx=6, pady=(6 if i == 0 else 1, 0))
            self.buttons[name] = (b, icon)

    def mark(self, current):
        for name, (b, icon) in self.buttons.items():
            on = name == current
            b.configure(text_color=C["text_strong"] if on else C["text"],
                        font=ui.font(None, "bold" if on else "normal"),
                        image=ui.icon(icon, "text_strong" if on else "muted"))


# The report accent (light theme, dark theme): Category, Sub-category and problem titles, screen and PDF.
REPORT_ACCENT = ("#1E7F6E", "#5CC8B0")


def report_accent():
    light, dark = REPORT_ACCENT
    return dark if ctk.get_appearance_mode() == "Dark" else light


def meeting_line(project):
    """'When: Mondays at 10:00   |   Where: Room 111' (only the parts that are filled in)."""
    parts = [(k, (project or {}).get(f)) for k, f in (("When", "meeting_when"), ("Where", "meeting_where"))]
    return "   |   ".join(f"{k}: {v}" for k, v in parts if v)


def attendees(rows):
    """Everyone named on an action of these problems, once each, A-Z."""
    return sorted({a["owner"] for p in rows for a in p.get("_actions", []) if a["owner"]}, key=str.lower)


class ProtocolView(ctk.CTkFrame):
    """A grouped, read-only report, like an Access report:
        Project > Category > Sub-category > Problem (title, description) > its actions.
    Problems without a sub-category sit directly under their Category (before the sub-categories);
    problems without a category go under "(no category)" at the end."""
    NAME, ICON = "Protocol", "scroll-text"
    DETAIL = True                   # description and actions under each problem (the Agenda leaves them out)
    FILTERS = ("Open", "Closed", "All")
    STEP = 26                       # indent per level, pixels

    def __init__(self, app, parent):
        super().__init__(parent, fg_color="transparent")
        self.app, self.store = app, app.store
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        top = title_only(self, self.NAME, self.ICON)
        top.grid(row=0, column=0, sticky="ew", padx=(0, GUTTER), pady=(0, GUTTER))
        ui.icon_button(top, "file-down", self.export, f"Save the {self.NAME.lower()} as PDF").pack(side="right", padx=(0, 6), pady=6)
        self.filter = ui.quiet_select(top, list(self.FILTERS), lambda _v: self.refresh(), width=110)
        self.filter.set("Open")
        self.filter.pack(side="right", padx=(GAP, GAP), pady=6)
        self.project = ui.quiet_select(top, project_names(self.store), self._project_changed, width=170)
        self.project.pack(side="right", pady=6)
        self.count = ui.label(top, "", muted=True, height=0)
        self.count.pack(side="right", padx=(0, GAP))

        body = ui.Panel(self)
        body.grid(row=1, column=0, sticky="nsew", padx=(0, GUTTER))
        self.text = ui.textbox(body)
        self.text.pack(fill="both", expand=True, padx=6, pady=6)
        self.text.configure(state="disabled")
        ui.on_theme_change(self.render)
        self.rows = []
        self._width = 0
        self.text.bind("<Configure>", self._resized)

    def _resized(self, e):
        """Action columns depend on the page width: lay out again when it changes (debounced)."""
        if abs(e.width - self._width) > 4:
            self._width = e.width
            if getattr(self, "_job", None):
                self.after_cancel(self._job)
            self._job = self.after(120, self.render)

    def _project_changed(self, value):
        self.app.project = None if value == ALL_PROJECTS else value
        self.refresh()

    def export(self):
        """The report as on screen (same project and filter) as a PDF."""
        import re
        self.refresh()
        project, f = self.app.project, self.filter.get()
        subtitle = "All topics" if f == "All" else f"{f} topics"
        slug = re.sub(r"[^a-z0-9]+", "-", (project or "all projects").lower()).strip("-")
        meeting = meeting_line(next((p for p in self.store.projects() if p["name"] == project), None))
        run_pdf(self.app, lambda path: pdf_export.protocol(
            path, project or ALL_PROJECTS, subtitle, self.rows, meeting, REPORT_ACCENT[0],   # paper is light
            title=self.NAME, detail=self.DETAIL, attendees=None if self.DETAIL else attendees(self.rows)),
                f"{self.NAME.lower()}-{slug}.pdf")

    def refresh(self):
        sync_project_select(self.app, self.project)
        f = self.filter.get()
        self.rows = self.store.problems("", None if f == "All" else (f,), project_id(self.store, self.app.project))
        for p in self.rows:
            p["_actions"] = self.store.actions(p["id"])
        n = len(self.rows)
        self.count.configure(text=f"{n} topic{'s' if n != 1 else ''}")
        self.render()

    def _tags(self):
        t, step = self.text._textbox, self.STEP
        big, mid, base = ui.FONT_SIZE + 6, ui.FONT_SIZE + 2, ui.FONT_SIZE
        styles = {
            "title":    dict(font=ui.font(big + 4), foreground=ui.cur("text_strong"), spacing1=4, spacing3=2),
            "titlebold": dict(font=ui.font(big + 4, "bold")),
            "project":  dict(font=ui.font(big, "bold"), foreground=ui.cur("text_strong"), spacing1=18, spacing3=4),
            "meeting":  dict(font=ui.font(base), foreground=ui.cur("muted"), spacing3=4),
            "category": dict(font=ui.font(mid + 1, "bold"), foreground=report_accent(), spacing1=12),
            "sub":      dict(font=ui.font(base, "bold"), foreground=report_accent(), spacing1=8),
            "problem":  dict(font=ui.font(base), foreground=report_accent(), spacing1=8),
            "action":   dict(font=ui.font(base), foreground=ui.cur("text"), spacing1=2),
            "acthead":  dict(font=ui.font(base, "bold"), foreground=ui.cur("text_strong"), spacing1=6),
            "names":    dict(font=ui.font(base - 1), foreground=ui.cur("muted"), spacing1=1),
            "desc":     dict(font=ui.font(base), foreground=ui.cur("text"), spacing1=3, spacing3=4),
            "muted":    dict(foreground=ui.cur("muted")),
            "bold":     dict(font=ui.font(base, "bold")),
            "late":     dict(foreground=ui.cur("error")),
            "empty":    dict(font=ui.font(base), foreground=ui.cur("muted"), spacing1=6),
        }
        for name, kw in styles.items():
            t.tag_configure(name, **kw)
        for level in range(6):                       # wrapped lines keep their indent
            t.tag_configure(f"L{level}", lmargin1=6 + level * step, lmargin2=6 + level * step + 18)
        for level in range(6):                       # descriptions: wrapped lines align with the first line
            t.tag_configure(f"F{level}", lmargin1=6 + level * step, lmargin2=6 + level * step)
        t.tag_raise("muted"); t.tag_raise("late")

    def _columns(self):
        """Tab stops for the action columns  Action | Who | Stage | Due, measured from the widget's
        left edge so every action in the report lines up, whatever its indent. Returns (tabs, action width)."""
        f, gap = ui.font(ui.FONT_SIZE, "bold"), 28      # bold: the header row is the widest case
        acts = [a for p in self.rows for a in p["_actions"]]
        who_w = max([f.measure(a["owner"] or "") for a in acts] + [f.measure("Who")])
        stage_w = max(f.measure(s) for s in db.ACTION_STAGES + ("Stage",))
        due_w = f.measure("2026-12-31")
        x_action = 6 + 4 * self.STEP                    # one step in from the deepest problem
        room = max(self.text._textbox.winfo_width(), 700) - x_action - who_w - stage_w - due_w - 3 * gap - 30
        action_w = max(220, min(max([f.measure(a["description"]) for a in acts] + [0]), room))
        x_who = x_action + action_w + gap
        x_stage = x_who + who_w + gap
        x_due = x_stage + stage_w + gap
        return (x_action, x_who, x_stage, x_due), action_w

    @staticmethod
    def _wrap(text, width, f):
        """Split text into lines that fit width pixels (the action column)."""
        lines, cur = [], ""
        for word in text.split():
            trial = f"{cur} {word}".strip()
            if cur and f.measure(trial) > width:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        return lines + [cur] if cur else lines or [""]

    def render(self):
        t = self.text._textbox
        self.text.configure(state="normal")
        t.delete("1.0", "end")
        self._tags()
        tabs, action_w = self._columns()
        t.tag_configure("cols", tabs=tabs)
        f = ui.font(ui.FONT_SIZE)

        def line(level, style, *parts):
            """parts: text or (text, extra tag) pieces on one line."""
            for part in parts:
                text, extra = part if isinstance(part, tuple) else (part, None)
                tags = ((style, f"L{level}") + ((f"F{level}",) if style in ("desc", "names") else ())
                        + (("cols",) if style in ("action", "acthead") else ()) + ((extra,) if extra else ()))
                t.insert("end", text, tags)
            t.insert("end", "\n", (style, f"L{level}") + (("cols",) if style in ("action", "acthead") else ()))

        def problem(p, level):
            info = "   " + "  |  ".join(x for x in (p["severity"], p["champion"],
                                                    p["status"] if p["status"] != "Open" else "") if x)
            if not self.DETAIL:                     # agenda: the title and who discusses it (its action owners)
                line(level, "problem", f"{db.number(p['id'])}   {p['title']}")
                who = ", ".join(attendees([p]))
                if who:                                             # names under the title, same indent
                    line(level, "names", who)
                return
            line(level, "problem", f"{db.number(p['id'])}   {p['title']}", (info, "muted"))
            if p["description"].strip():
                line(level, "desc", p["description"].strip())
            if not p["_actions"]:
                line(0, "action", ("\tNo actions.", "muted"))
            else:
                line(0, "acthead", "\tAction\tWho\tStage\tDue")
            for a in p["_actions"]:
                done = a["status"] == db.ACTION_DONE
                late = db.is_overdue(a["due_date"], not done)
                dim = "muted" if done else None
                first, *more = self._wrap(a["description"], action_w, f)
                line(0, "action", (f"\t{first}", dim), (f"\t{a['owner'] or '-'}", dim),
                     (f"\t{a['status']}", dim), (f"\t{a['due_date'] or '-'}", "late" if late else dim))
                for rest in more:                                    # wrapped action text stays in its column
                    line(0, "action", (f"\t{rest}", dim))

        project = self.app.project
        line(0, "title", (self.NAME, "titlebold"), f"  \u2013  {project or ALL_PROJECTS}")
        meeting = meeting_line(next((p for p in self.store.projects() if p["name"] == project), None))
        if meeting:
            line(0, "meeting", meeting)
        if not self.DETAIL and attendees(self.rows):
            line(0, "meeting", ("Attendees:  ", "bold"), ", ".join(attendees(self.rows)))
        groups = db.protocol_groups(self.rows)
        if not self.rows:
            line(0, "empty", "No topics match this project and filter.")
        for proj, cats in groups:
            if project is None:                     # one project: the title already names it
                line(0, "project", proj)
            for cat, direct, subs in cats:                          # one step in from the project / title
                line(1, "category", cat)
                for p in direct:                                    # no sub-category: right under it
                    problem(p, 2)
                for sub, problems in subs:
                    line(2, "sub", sub)
                    for p in problems:
                        problem(p, 3)
        self.text.configure(state="disabled")


class AgendaView(ProtocolView):
    """The Protocol, stripped: same grouping and indentation, problem titles only, and the attendees
    (everyone named on an action of the listed problems)."""
    NAME, ICON = "Agenda", "calendar"
    DETAIL = False


# ---------------------------------------------------------------- problems list
class ProblemsView(ctk.CTkFrame):
    FILTERS = ("Open", "Closed", "All")

    def __init__(self, app, parent):
        super().__init__(parent, fg_color="transparent")
        self.app, self.store = app, app.store
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # title in its own panel, like Settings
        top = ui.Panel(self)
        top.grid(row=0, column=0, sticky="ew", padx=(0, GUTTER), pady=(0, GUTTER))
        ui.icon_button(top, "plus", lambda: app.guard(lambda: app.open_problem(None)),
                       "New topic (Ctrl+N)").pack(side="left", padx=(8, 0), pady=6)
        title_label(top, "Topics").pack(side="left", padx=(2, 0))
        ui.icon_button(top, "file-down", self.export, "Export the list as PDF").pack(side="right", padx=(0, 6), pady=6)
        self.count = ui.label(top, "", muted=True, height=0)
        self.count.pack(side="right", padx=(0, GAP))

        p = ui.Panel(self)
        p.grid(row=1, column=0, sticky="nsew", padx=(0, GUTTER))
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)

        bar = ctk.CTkFrame(p, fg_color="transparent", height=0)
        bar.grid(row=1, column=0, sticky="ew", padx=IN, pady=(IN, GAP))
        self.search = ui.search_entry(bar, "Search topics", width=300)
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", lambda _e: self.refresh())
        self.search.bind("<Escape>", lambda _e: (self.search.delete(0, "end"), self.refresh()))
        self.project = ui.quiet_select(bar, project_names(self.store), self._project_changed, width=170)
        self.project.pack(side="left", padx=(GAP, 0))
        self.filter = ui.quiet_select(bar, list(self.FILTERS), lambda _v: self.refresh(), width=110)
        self.filter.set("Open")
        self.filter.pack(side="left", padx=(GAP, 0))

        self.table = ui.data_table(p, problem_columns(), color_fn=problem_color, sort=("no", True),
                                   on_open=lambda r: app.open_problem(r["_id"]),
                                   empty_text="No topics match. Press Ctrl+N to add one.")
        self.table.grid(row=2, column=0, sticky="nsew", padx=IN, pady=0)
        ui.label(p, "Click a column to sort. Double-click a row to open it.", muted=True,
                 size=ui.FONT_SIZE - 2, height=0).grid(row=3, column=0, sticky="w", padx=IN, pady=(GAP, IN))

    def _project_changed(self, value):
        self.app.project = None if value == ALL_PROJECTS else value
        self.refresh()

    def refresh(self):
        sync_project_select(self.app, self.project)
        f = self.filter.get()
        statuses = None if f == "All" else (f,)
        rows = problem_rows(self.store.problems(self.search.get(), statuses,
                                                project_id(self.store, self.app.project)))
        self.table.set_rows(rows)
        self.count.configure(text=f"{len(rows)} topic{'s' if len(rows) != 1 else ''}")

    def export(self):
        """Print the list as it is on screen: same project, status filter, search and sort order."""
        shown = self.table._sorted()
        cols = [("No.", 1), ("Title", 4), ("Severity", 1), ("Category", 1.5), ("Sub-category", 1.6),
                ("Champion", 1.7), ("Status", 1.1), ("Created", 1.3), ("Updated", 1.3), ("Open actions", 1.7)]
        keys = ["no", "title", "severity", "category", "subcategory", "champion", "status", "created", "updated",
                "open_actions"]
        project = self.app.project
        if project is None:                                 # several projects on one sheet: say which
            cols.insert(1, ("Project", 1.4))
            keys.insert(1, "project")
        f = self.filter.get()
        title = "All topics" if f == "All" else f"{f} topics"
        data = [[str(r.get(k, "")) for k in keys] for r in shown]
        dots = [r["dot"][4:] for r in shown]
        run_pdf(self.app, lambda path: pdf_export.open_items(path, title, cols, data, set(),
                                                             project or ALL_PROJECTS, dots),
                f"{f.lower()}-topics.pdf")


# ---------------------------------------------------------------- action dialog
def action_dialog(app, action, problem_id, people, default_owner=""):
    """Add/edit one action. Returns a dict for Store.save_action, or None if cancelled."""
    dlg = ui.modal(app, "Edit action" if action else "Add action")
    result = {"v": None}
    panel = ui.Panel(dlg)
    panel.pack(fill="both", expand=True, padx=GUTTER, pady=(GUTTER, 0))
    body = ctk.CTkFrame(panel, fg_color="transparent", height=0)
    body.pack(fill="both", expand=True, padx=IN, pady=IN)
    names = [db.NONE] + [p["name"] for p in people]
    f_what, what, err_what = ui.field(body, "Action",
                                      lambda p: ui.textbox(p, fg_color=C["hover"], height=70), required=True)
    f_what.pack(fill="x", pady=(0, GAP))
    row = ctk.CTkFrame(body, fg_color="transparent", height=0)
    row.pack(fill="x", pady=(0, GAP))
    row.columnconfigure((0, 1), weight=1, uniform="a")
    f_who, who, _ = ui.field(row, "Who does it", lambda p: ui.quiet_select(p, names), reserve=False)
    f_due, due, err_due = ui.field(row, "When is it due", lambda p: ui.date_entry(p))
    f_who.grid(row=0, column=0, sticky="new", padx=(0, GAP))
    f_due.grid(row=0, column=1, sticky="new")
    f_stage, stage, _ = ui.field(body, "Completion", lambda p: ui.quiet_select(p, list(db.ACTION_STAGES)), reserve=False)
    f_stage.pack(fill="x")

    a = action or {}
    what.insert("1.0", a.get("description", ""))
    who.set(a.get("owner") or default_owner or db.NONE)
    due.set(a.get("due_date", ""))
    stage.set(a.get("status", db.ACTION_STAGES[0]))

    def ok():
        text, d = what.get("1.0", "end").strip(), due.get().strip()
        bad = False
        if not text:
            err_what("Describe the action."); bad = True
        else:
            err_what()
        if not db.valid_date(d):
            err_due("Use YYYY-MM-DD."); bad = True
        else:
            err_due()
        if bad:
            return
        owner = next((p["id"] for p in people if p["name"] == who.get()), None)
        st = stage.get()
        result["v"] = dict(id=a.get("id"), problem_id=problem_id, description=text, owner_id=owner, due_date=d,
                           status=st, done_date=(a.get("done_date") or db.today()) if st == db.ACTION_DONE else "")
        dlg.destroy()

    def delete():
        if ui.dialog(dlg, "Delete action?", (a.get("description") or "")[:120], ("Cancel", "Delete"),
                     danger=True) == "Delete":
            result["v"] = "delete"
            dlg.destroy()

    bar = ctk.CTkFrame(dlg, fg_color="transparent", height=0)
    bar.pack(fill="x", padx=GUTTER, pady=GUTTER)
    if a.get("id"):
        d = button(bar, "Delete", delete)
        d.configure(text_color=C["error"])
        d.pack(side="left")
    button(bar, "Save", ok).pack(side="right")
    button(bar, "Cancel", dlg.destroy).pack(side="right", padx=(0, 6))
    ui.run_modal(dlg, app, 480)
    return result["v"]


# ---------------------------------------------------------------- problem detail
class DetailView(ctk.CTkFrame):
    def __init__(self, app, parent, pid):
        super().__init__(parent, fg_color="transparent")
        self.app, self.store, self.pid = app, app.store, pid
        self.people = self.store.items("people")
        self.cats = self.store.items("categories")
        self.subs = self.store.subcategories()
        self.projects = self.store.items("projects")
        self.sevs = self.store.severities()
        self.fields: dict[str, tuple] = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ui.Panel(self)
        top.grid(row=0, column=0, sticky="ew", padx=(0, GUTTER), pady=(0, GUTTER))
        self.dot_label = ctk.CTkLabel(top, text="", height=0)
        self.dot_label.pack(side="left", padx=(IN, 6), pady=6)
        self.heading = title_label(top, "")
        self.heading.pack(side="left")
        # actions, right side, left to right: delete | PDF, folder, save, + picture | back to list
        tools = ctk.CTkFrame(top, fg_color="transparent", height=0)
        tools.pack(side="right", padx=(GAP, 6), pady=6)
        self.delete_btn = ui.icon_button(tools, "trash-2", self.delete, "Delete this topic", tone="error")
        self.delete_btn.pack(side="left")
        ui.divider(tools).pack(side="left", padx=6)
        for name, cmd, tip in (("file-down", self.print_pdf, "Print this topic as PDF"),
                               ("folder-open", self.open_folder, "Open this topic's folder"),
                               ("save", self.save, "Save (Ctrl+S)")):
            ui.icon_button(tools, name, cmd, tip).pack(side="left", padx=(0, 2))
        self.add_pic_btn = ui.icon_button(tools, "image-plus", self.add_pictures, "Add pictures")
        self.add_pic_btn.pack(side="left")
        ui.divider(tools).pack(side="left", padx=6)
        ui.icon_button(tools, "undo-2", lambda: app.guard(app.close_detail), "Back to the list (Esc)").pack(side="left")

        scroll = self.scroll = ui.scroll_frame(self)
        scroll.grid(row=1, column=0, sticky="nsew")
        self._problem_card(scroll)
        self._actions_card(scroll)
        self._pictures_card(scroll)


        self._load()

    # ---- building ----------------------------------------------------
    def _field(self, parent, key, label, make, **kw):
        f, ctl, err = ui.field(parent, label, make, reserve=False, **kw)   # scrolling page: no fixed-size window to protect
        self.fields[key] = (ctl, err)
        return f

    def _problem_card(self, parent):
        card = ui.section(parent, "Topic")
        card.pack(fill="x", padx=(0, GUTTER), pady=(0, GUTTER))
        b = card.body
        b.columnconfigure(tuple(range(5)), weight=1, uniform="p")
        gap, low = (0, GAP), (0, GAP)
        proj_names = [p["name"] for p in self.projects]
        cat_names = [db.NONE] + [c["name"] for c in self.cats]
        ppl_names = [db.NONE] + [p["name"] for p in self.people]
        self._field(b, "project", "Project", lambda p: ui.quiet_select(p, proj_names), required=True).grid(
            row=0, column=0, sticky="ew", padx=gap, pady=low)
        self._field(b, "title", "Title", lambda p: ui.entry(p), required=True).grid(
            row=0, column=1, columnspan=4, sticky="ew", pady=low)
        sev_names = [x["name"] for x in self.sevs]
        small = [("severity", "Severity", lambda p: ui.quiet_select(p, sev_names, lambda _v: self._update_dot())),
                 ("category", "Category", lambda p: ui.quiet_select(p, cat_names, lambda _v: self._sync_subs())),
                 ("subcategory", "Sub-category", lambda p: ui.quiet_select(p, [db.NONE])),
                 ("champion", "Champion", lambda p: ui.quiet_select(p, ppl_names)),
                 ("status", "Status", lambda p: ui.quiet_select(p, list(db.PROBLEM_STATUSES)))]
        for i, (key, label, make) in enumerate(small):
            self._field(b, key, label, make).grid(row=1, column=i, sticky="ew",
                                                  padx=gap if i < len(small) - 1 else 0, pady=low)
        self._field(b, "description", "Description",
                    lambda p: ui.textbox(p, fg_color=C["hover"], height=96)).grid(
            row=2, column=0, columnspan=3, sticky="ew", padx=gap)
        self._field(b, "root_cause", "Root cause",
                    lambda p: ui.textbox(p, fg_color=C["hover"], height=96)).grid(
            row=2, column=3, columnspan=2, sticky="ew")

    def _sync_subs(self, keep=None):
        """Offer only the chosen Category's sub-categories; keep the current pick if it still fits."""
        ctl = self.fields["subcategory"][0]
        names = [db.NONE] + [s["name"] for s in self.subs if s["category"] == self._get("category")]
        current = keep if keep is not None else ctl.get()
        ctl.configure(values=names, state="normal" if len(names) > 1 else "disabled")
        ctl.set(current if current in names else db.NONE)

    def _pictures_card(self, parent):
        card = ui.section(parent, "Pictures")
        card.pack(fill="x", padx=(0, GUTTER))
        self.pic_hint = ui.label(card.body, "", muted=True, size=ui.FONT_SIZE - 2, height=0)
        self.pic_hint.pack(anchor="w")
        self.pic_grid = ctk.CTkFrame(card.body, fg_color="transparent", height=0)
        self.pic_grid.pack(fill="x", pady=(GAP, 0))
        self._pic_refs: list = []

    def _actions_card(self, parent):
        card = ui.section(parent, "Actions", on_add=self.add_action, add_tip="Add action")
        add = card.add_button
        card.pack(fill="x", padx=(0, GUTTER), pady=(0, GUTTER))
        cols = [
            {"key": "no", "title": "#", "weight": 0.5, "nosort": True},
            {"key": "action", "title": "Actions", "weight": 6, "wrap": 460, "nosort": True},
            {"key": "owner", "title": "Who", "weight": 2, "nosort": True},
            {"key": "due", "title": "Due", "weight": 1.5, "nosort": True},
            {"key": "status", "title": "Completion", "weight": 1.8, "nosort": True},
            {"key": "up", "title": "", "weight": 0.35, "nosort": True, "anchor": "center", "icon": "arrow-up",
             "skip": "first", "click": lambda rid: self.move_action(rid, -1)},
            {"key": "down", "title": "", "weight": 0.35, "nosort": True, "anchor": "center", "icon": "arrow-down",
             "skip": "last", "click": lambda rid: self.move_action(rid, 1)},
        ]   # no header sorting: the row order is the order on the sheet (set with the arrows)
        self.abtns = {"Add action": add}
        self.atable = ui.data_table(card.body, cols, color_fn=action_color, height=170,
                                    on_open=lambda _r: self.edit_action(), empty_text="No actions yet.")
        self.atable.pack(fill="x")
        self.ahint = ui.label(card.body, "", muted=True, size=ui.FONT_SIZE - 2, height=0)
        self.ahint.pack(anchor="w", pady=(6, 0))

    # ---- values ------------------------------------------------------
    def _get(self, key):
        ctl = self.fields[key][0]
        return ctl.get("1.0", "end").strip() if isinstance(ctl, ctk.CTkTextbox) else ctl.get().strip()

    def _set(self, key, value):
        ctl = self.fields[key][0]
        if isinstance(ctl, ctk.CTkTextbox):
            ctl.delete("1.0", "end")
            ctl.insert("1.0", value or "")
        elif isinstance(ctl, ctk.CTkOptionMenu):
            ctl.set(value or db.NONE)
        else:
            ctl.delete(0, "end")
            ctl.insert(0, value or "")

    def values(self):
        return {k: self._get(k) for k in self.fields}

    def dirty(self):
        return self.values() != self.snapshot

    def _load(self):
        p = self.store.get_problem(self.pid) if self.pid else None
        default_project = (self.app.project or self.store.last_project()
                           or (self.projects[0]["name"] if self.projects else ""))
        names = [x["name"] for x in self.sevs]
        default_sev = "Medium" if "Medium" in names else (names[len(names) // 2] if names else "")
        init = {"project": default_project, "severity": default_sev, "status": "Open", "category": db.NONE,
                "subcategory": db.NONE, "champion": db.NONE} if p is None else {
            "project": p["project"], "title": p["title"], "severity": p["severity"], "category": p["category"],
            "subcategory": p["subcategory"], "champion": p["champion"],
            "status": p["status"], "description": p["description"], "root_cause": p["root_cause"]}
        for k in self.fields:
            if k != "subcategory":
                self._set(k, init.get(k, ""))
        self._sync_subs(keep=init.get("subcategory") or db.NONE)
        self.snapshot = self.values()
        self.record = p
        self._update_dot()
        self._refresh_header()
        self.refresh_actions()
        self.refresh_pictures()

    def _update_dot(self):
        """Severity dot to the left of the title, following the Severity dropdown."""
        color = next((x["color"] for x in self.sevs if x["name"] == self._get("severity")), None)
        self.dot_label.configure(image=ui.dot_image(color, 18) if color else None)

    def _refresh_header(self):
        if self.pid:
            self.heading.configure(text=f"{db.number(self.pid)}   {self._get('title') or 'Untitled'}")
        else:
            self.heading.configure(text="New topic")
        self.delete_btn.configure(state="normal" if self.pid else "disabled")

    # ---- save / delete / print ----------------------------------------
    def save(self):
        v = self.values()
        errors = {}
        if not any(p["name"] == v["project"] for p in self.projects):
            errors["project"] = "Choose a project (add projects in Settings)."
        if not v["title"]:
            errors["title"] = "Give the topic a title."
        for k, (_c, err) in self.fields.items():
            err(errors.get(k))
        if errors:
            self.app.note("Fix the highlighted fields", "error")
            return False
        if self.pid and v["status"] == "Closed" and (self.record or {}).get("status") != "Closed":
            n = sum(1 for a in self.store.actions(self.pid) if a["status"] != db.ACTION_DONE)
            if n and ui.dialog(self.app, "Close with open actions?",
                               f"{n} action{'s are' if n != 1 else ' is'} not verified yet.",
                               ("Cancel", "Close anyway"), danger=True) != "Close anyway":
                return False
        cat = next((c["id"] for c in self.cats if c["name"] == v["category"]), None)
        sub = next((s["id"] for s in self.subs if s["category_id"] == cat and s["name"] == v["subcategory"]), None)
        champ = next((p["id"] for p in self.people if p["name"] == v["champion"]), None)
        was_closed = (self.record or {}).get("closed_date", "")
        closed = (was_closed or db.today()) if v["status"] == "Closed" else ""
        proj = next((p["id"] for p in self.projects if p["name"] == v["project"]), None)
        sev = next((x["id"] for x in self.sevs if x["name"] == v["severity"]), None)
        self.pid = self.store.save_problem(dict(
            id=self.pid, project_id=proj, title=v["title"], severity_id=sev, description=v["description"],
            root_cause=v["root_cause"], category_id=cat, subcategory_id=sub, champion_id=champ, status=v["status"],
            closed_date=closed))
        self.record = self.store.get_problem(self.pid)
        self.snapshot = v
        self._refresh_header()
        self.refresh_actions()
        self.refresh_pictures()
        self.app.note(f"Saved {db.number(self.pid)}", "success")
        return True

    @single
    def delete(self):
        n = len(self.store.actions(self.pid))
        extra = f" and its {n} action{'s' if n != 1 else ''}" if n else ""
        mine = self.store.user_file_count(self.pid)
        keep = (f"\n\nThe folder {db.number(self.pid)} and the {mine} file{'s' if mine != 1 else ''} you added "
                "there are not deleted." if mine else "")
        if ui.dialog(self.app, f"Delete {db.number(self.pid)}?", f"This deletes the topic{extra} and the "
                     f"pictures attached to it. It cannot be undone.{keep}", ("Cancel", "Delete"),
                     danger=True) == "Delete":
            self.store.delete_problem(self.pid)
            self.snapshot = self.values()
            self.app.note(f"Deleted {db.number(self.pid)}")
            self.app.close_detail()

    def print_pdf(self):
        if not self.pid:
            self.app.note("Save the topic first.")
            return
        if self.dirty() and not self.save():
            return
        p, acts = self.store.get_problem(self.pid), self.store.actions(self.pid)
        pics = [i["path"] for i in self.store.images(self.pid) if i["path"].exists()]
        run_pdf(self.app, lambda path: pdf_export.problem_sheet(path, p, acts, pics), f"{db.number(self.pid)}.pdf")

    # ---- folder ------------------------------------------------------
    def open_folder(self):
        if not self.pid:
            self.app.note("Save the topic first.")
            return
        open_path(self.app, self.store.problem_dir(self.pid, create=True))

    # ---- pictures ----------------------------------------------------
    THUMB = 92

    def refresh_pictures(self):
        self._sync_record()
        for w in self.pic_grid.winfo_children():
            w.destroy()
        self._pic_refs = []
        self.add_pic_btn.configure(state="normal" if self.pid else "disabled")
        images = self.store.images(self.pid) if self.pid else []
        self.pic_hint.configure(text="Save the topic first, then add pictures." if not self.pid else
                                "No pictures yet. Add them with the picture icon, top right." if not images else
                                "Click a picture to enlarge it.  Other files go in the topic folder (folder icon, top right).")
        for i, img in enumerate(images):
            pil = ui.thumb(img["path"], self.THUMB)
            image = ctk.CTkImage(pil, size=(self.THUMB, self.THUMB)) if pil is not None else None
            self._pic_refs.append(image)
            b = ctk.CTkButton(self.pic_grid, text="" if image else "missing", image=image,
                              width=self.THUMB + 8, height=self.THUMB + 8, fg_color="transparent",
                              hover_color=C["hover"], border_width=1, border_color=C["rule"],
                              text_color=C["muted"], font=ui.font(ui.FONT_SIZE - 2),
                              corner_radius=ui.RADIUS, command=lambda img=img: self.view_picture(img))
            b.grid(row=i // 9, column=i % 9, padx=(0, GAP), pady=(0, GAP))

    @single
    def add_pictures(self):
        files = filedialog.askopenfilenames(
            parent=self.app, title="Add pictures", initialdir=remembered_dir(self.app, "last_pictures_dir"),
            filetypes=[("Pictures", " ".join(f"*{e}" for e in db.Store.IMAGE_TYPES)), ("All files", "*")])
        if files:
            remember_dir(self.app, "last_pictures_dir", files[0])
        added = 0
        for f in files:
            try:
                self.store.add_image(self.pid, f)
                added += 1
            except OSError as e:
                ui.dialog(self.app, "Could not add picture", f"{f}\n\n{e}", ("OK",))
        if added:
            self.refresh_pictures()
            self.app.note(f"Added {added} picture{'s' if added != 1 else ''}")

    @single
    def view_picture(self, img):
        dlg = ui.modal(self.app, img["path"].name)
        image = ui.fit_image(img["path"], 860, 560)
        panel = ui.Panel(dlg)
        panel.pack(padx=GUTTER, pady=(GUTTER, 0))
        if image is not None:
            ctk.CTkLabel(panel, text="", image=image, height=0).pack(padx=IN, pady=(IN, 0))
        else:
            ui.label(panel, "This picture file is missing or unreadable.").pack(padx=IN, pady=IN)
            panel.winfo_children()[-1].configure(text_color=C["error"])
        ui.label(panel, f"{img['path'].name}   |   added {img['added_at']}", muted=True,
                 size=ui.FONT_SIZE - 2, height=0).pack(anchor="w", padx=IN, pady=(GAP, IN))
        choice = {"v": None}

        def pick(v):
            choice["v"] = v
            dlg.destroy()

        bar = ctk.CTkFrame(dlg, fg_color="transparent", height=0)
        bar.pack(anchor="e", padx=GUTTER, pady=GUTTER)
        danger(button(bar, "Remove", lambda: pick("remove"))).pack(side="left", padx=(0, 6))
        button(bar, "Close", lambda: pick(None)).pack(side="left")
        ui.run_modal(dlg, self.app, 420)
        if choice["v"] == "remove" and ui.dialog(self.app, "Remove picture?", img["path"].name,
                                                 ("Cancel", "Remove"), danger=True) == "Remove":
            self.store.delete_image(img["id"])
            self.refresh_pictures()

    # ---- actions -----------------------------------------------------
    def _sync_record(self):
        """Re-read the saved problem so the Created/Updated line reflects action and picture changes."""
        if self.pid:
            self.record = self.store.get_problem(self.pid)
            self._refresh_header()

    def refresh_actions(self):
        self._sync_record()
        rows = []
        if self.pid:
            rows = [{"_id": a["id"], "no": n, "action": a["description"], "owner": a["owner"] or "",
                     "due": a["due_date"], "status": a["status"], "_raw": a}
                    for n, a in enumerate(self.store.actions(self.pid), start=1)]
        self.atable.set_rows(rows)
        enabled = bool(self.pid)
        for b in self.abtns.values():
            b.configure(state="normal" if enabled else "disabled")
        self.ahint.configure(text="Double-click an action to edit it or change its stage." if enabled else "Save the topic first, then add its actions.")

    def _selected(self):
        row = self.atable.selected_row()
        if row is None:
            self.app.note("Select an action first.")
        return row

    @single
    def add_action(self):
        a = action_dialog(self.app, None, self.pid, self.people, self._get("champion"))
        if isinstance(a, dict):
            self.store.save_action(a)
            self.refresh_actions()

    @single
    def edit_action(self):
        row = self._selected()
        if row:
            a = action_dialog(self.app, row["_raw"], self.pid, self.people)
            if a == "delete":
                self.store.delete_action(row["_id"])
                self.refresh_actions()
            elif a:
                self.store.save_action(a)
                self.refresh_actions()

    def move_action(self, aid, step):
        if self.store.move_action(aid, step):
            self.refresh_actions()


# ---------------------------------------------------------------- settings
class SettingsView(ctk.CTkFrame):
    def __init__(self, app, parent):
        super().__init__(parent, fg_color="transparent")
        self.app, self.store = app, app.store
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        title_only(self, "Settings", "settings").grid(row=0, column=0, sticky="ew", padx=(0, GUTTER), pady=(0, GUTTER))
        self.body = ui.scroll_frame(self)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure((0, 1), weight=1, uniform="s")
        # the window margin on the right, where the scrollbar sits when the page overflows
        ctk.CTkFrame(self.body, width=GUTTER, height=1, fg_color="transparent").grid(row=1, column=2)

        self._project_editor(1)
        self._editor("Categories", "category", "categories", 2, 0,
                     on_change=lambda: getattr(self, "_subs_refresh", lambda: None)())
        self._subcategory_editor(2, 1)
        self._editor("People", "person", "people", 3, 0)
        self._severity_editor(3, 1)

        look = ui.section(self.body, "Appearance")
        look.grid(row=4, column=0, sticky="nsew", padx=(0, GUTTER), pady=(GUTTER, 0))
        f, self.theme_select, _ = ui.field(look.body, "Theme", lambda p: ui.quiet_select(
            p, ["Dark", "Light"], lambda v: app.set_theme(v.lower()), width=200), reserve=False)
        self.theme_select.set(app.mode.capitalize())
        f.pack(anchor="w")
        ui.label(look.body, "Text size: Ctrl + and Ctrl -  (Ctrl 0 resets).", muted=True,
                 size=ui.FONT_SIZE - 2, height=0).pack(anchor="w", pady=(GAP, 0))

        files = ui.section(self.body, "Topic files")
        files.grid(row=4, column=1, sticky="nsew", pady=(GUTTER, 0))
        ui.label(files.body, "Every topic gets a folder here named by its number (TS-0003). Pictures you "
                 "attach live in its pictures sub-folder. Anything else you put in the folder is yours: "
                 "evidence, analyses, notes. The app never reads, changes or deletes it.", muted=True,
                 size=ui.FONT_SIZE - 2, wraplength=330, height=0).pack(anchor="w")
        button(files.body, "Choose folder", app.choose_image_dir).pack(anchor="w", pady=(GAP, 6))
        ui.label(files.body, str(self.store.image_dir), wraplength=330, height=0).pack(anchor="w")

        data = ui.section(self.body, "Data")
        data.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(GUTTER, 0))
        ui.label(data.body, f"Database file:  {self.store.path}", height=0).pack(anchor="w")
        ui.label(data.body, "Everything is stored in this one SQLite file. Copy it to back up.", muted=True,
                 size=ui.FONT_SIZE - 2, height=0).pack(anchor="w", pady=(3, 0))
        ui.label(data.body, f"{APP_NAME} {VERSION}", muted=True, size=ui.FONT_SIZE - 2, height=0).pack(
            anchor="w", pady=(6, 0))

    def _severity_editor(self, row, col):
        """Severity levels, lowest first (the order is the ranking). + adds; per row: arrows, pencil, trash.
        The color is the dot used on the Problems list, the form and the PDFs."""
        app, store = self.app, self.store
        card = ui.section(self.body, "Severity levels", on_add=lambda: add_level(), add_tip="Add severity level")
        card.grid(row=row, column=col, sticky="nsew", padx=(0, GUTTER) if col == 0 else 0, pady=(GUTTER, 0))

        def refresh():
            tbl.set_rows([{"_id": x["id"], "dot": f"dot:{x['color']}", "name": x["name"], "color": x["color"]}
                          for x in store.severities()])

        def lookup(rid):
            return next(x for x in store.severities() if x["id"] == rid)

        @single
        def add_level():
            got = widgets.severity_dialog(app, "Add severity level")
            if got:
                try:
                    store.add_severity(*got)
                except sqlite3.IntegrityError:
                    app.note(f"'{got[0]}' already exists.", "error")
                refresh()

        @single
        def edit(rid):
            cur = lookup(rid)
            got = widgets.severity_dialog(app, "Edit severity level", cur["name"], cur["color"])
            if got and got != (cur["name"], cur["color"]):
                try:
                    store.update_severity(rid, *got)
                except sqlite3.IntegrityError:
                    app.note(f"'{got[0]}' already exists.", "error")
                refresh()

        def move(rid, direction):
            store.move_severity(rid, direction)
            refresh()

        @single
        def remove(rid):
            cur = lookup(rid)
            if ui.dialog(app, f"Delete '{cur['name']}'?", "It will no longer be offered.",
                         ("Cancel", "Delete"), danger=True) != "Delete":
                return
            try:
                store.delete_severity(rid)
            except db.InUse:
                ui.dialog(app, "Still in use", f"Topics still use '{cur['name']}'. Change those "
                          "topics first, or rename this level instead.", ("OK",))
                return
            refresh()

        small = {"weight": 0.35, "nosort": True, "anchor": "center"}
        cols = [{"key": "dot", "title": "", "weight": 0.5, "image": True, "size": 14, "nosort": True},
                {"key": "name", "title": "Name (lowest first)", "weight": 3, "nosort": True},
                {"key": "up", "title": "", "icon": "arrow-up", "skip": "first",
                 "click": lambda rid: move(rid, -1), **small},
                {"key": "down", "title": "", "icon": "arrow-down", "skip": "last",
                 "click": lambda rid: move(rid, 1), **small},
                {"key": "edit", "title": "", "icon": "pencil", "click": edit, **small},
                {"key": "del", "title": "", "icon": "trash-2", "click": remove, **small}]
        tbl = ui.data_table(card.body, cols, height=150, empty_text="No severity levels.")
        tbl.pack(fill="x")
        refresh()

    def _project_editor(self, row):
        """Projects across the full width: name, and when / where the team meets (printed on the Protocol)."""
        app, store = self.app, self.store
        card = ui.section(self.body, "Projects", on_add=lambda: add(), add_tip="Add project")
        card.grid(row=row, column=0, columnspan=2, sticky="nsew")

        def refresh():
            tbl.set_rows([{"_id": p["id"], "name": p["name"], "when": p["meeting_when"], "where": p["meeting_where"]}
                          for p in store.projects()])

        def save(got, pid=None):
            try:
                store.save_project(*got, pid=pid)
            except sqlite3.IntegrityError:
                app.note(f"'{got[0]}' already exists.", "error")
                return
            refresh()

        @single
        def add():
            got = widgets.project_dialog(app, "Add project")
            if got:
                save(got)

        @single
        def edit(pid):
            cur = next(p for p in store.projects() if p["id"] == pid)
            got = widgets.project_dialog(app, "Edit project", cur["name"], cur["meeting_when"], cur["meeting_where"])
            if got and got != (cur["name"], cur["meeting_when"], cur["meeting_where"]):
                save(got, pid)

        @single
        def remove(pid):
            cur = next(p["name"] for p in store.projects() if p["id"] == pid)
            if ui.dialog(app, f"Delete '{cur}'?", "It will no longer be offered in lists.",
                         ("Cancel", "Delete"), danger=True) != "Delete":
                return
            try:
                store.delete_item("projects", pid)
            except db.InUse:
                ui.dialog(app, "Still in use", f"'{cur}' still has topics. Move them to another project first, "
                          "or rename this one.", ("OK",))
                return
            refresh()

        small = {"weight": 0.4, "nosort": True, "anchor": "center"}
        cols = [{"key": "name", "title": "Name", "weight": 3},
                {"key": "when", "title": "When", "weight": 3},
                {"key": "where", "title": "Where", "weight": 3},
                {"key": "edit", "title": "", "icon": "pencil", "click": edit, **small},
                {"key": "del", "title": "", "icon": "trash-2", "click": remove, **small}]
        tbl = ui.data_table(card.body, cols, height=130, sort=("name", False),
                            empty_text="Empty. Use + to add the first project.")
        tbl.pack(fill="x")
        refresh()

    def _subcategory_editor(self, row, col):
        """Sub-categories of one category at a time: pick the category, then + / pencil / trash as usual."""
        app, store = self.app, self.store
        card = ui.section(self.body, "Sub-categories", on_add=lambda: add(), add_tip="Add sub-category")
        card.grid(row=row, column=col, sticky="nsew", padx=(0, GUTTER) if col == 0 else 0, pady=(GUTTER, 0))
        none_yet = "(add a category first)"

        def cat_id():
            return next((c["id"] for c in store.items("categories") if c["name"] == pick.get()), None)

        def refresh():
            names = [c["name"] for c in store.items("categories")]
            pick.configure(values=names or [none_yet])
            if pick.get() not in names:
                pick.set(names[0] if names else none_yet)
            cid = cat_id()
            card.add_button.configure(state="normal" if cid else "disabled")
            tbl.set_rows([{"_id": x["id"], "name": x["name"]} for x in store.subcategories(cid)] if cid else [])

        def current(sid):
            return next(x["name"] for x in store.subcategories() if x["id"] == sid)

        def save(name, sid=None):
            try:
                store.rename_subcategory(sid, name) if sid else store.add_subcategory(cat_id(), name)
            except sqlite3.IntegrityError:
                app.note(f"'{name}' already exists under {pick.get()}.", "error")
                return
            refresh()

        @single
        def add():
            if cat_id():
                name = ui.prompt(app, f"Add sub-category to {pick.get()}")
                if name:
                    save(name)

        @single
        def rename(sid):
            cur = current(sid)
            name = ui.prompt(app, "Rename sub-category", value=cur)
            if name and name != cur:
                save(name, sid)

        @single
        def remove(sid):
            cur = current(sid)
            if ui.dialog(app, f"Delete '{cur}'?", "It will no longer be offered in lists.",
                         ("Cancel", "Delete"), danger=True) != "Delete":
                return
            try:
                store.delete_subcategory(sid)
            except db.InUse:
                ui.dialog(app, "Still in use", f"Topics still use '{cur}'. Rename it, or change those "
                          "topics first.", ("OK",))
                return
            refresh()

        f, pick, _ = ui.field(card.body, "Category", lambda p: ui.quiet_select(p, [], lambda _v: refresh()),
                              reserve=False)
        f.pack(fill="x", pady=(0, GAP))
        cols = [{"key": "name", "title": "Name", "weight": 6},
                {"key": "edit", "title": "", "weight": 0.4, "nosort": True, "anchor": "center",
                 "icon": "pencil", "click": rename},
                {"key": "del", "title": "", "weight": 0.4, "nosort": True, "anchor": "center",
                 "icon": "trash-2", "click": remove}]
        tbl = ui.data_table(card.body, cols, height=150, sort=("name", False),
                            empty_text="No sub-categories. Use + to add one.")
        tbl.pack(fill="x")
        self._subs_refresh = refresh
        refresh()

    def _editor(self, title, noun, table, row, col, on_change=None):
        """A maintained list: + by the title adds, a pencil renames and a trash can deletes, per row."""
        app, store = self.app, self.store
        card = ui.section(self.body, title, on_add=lambda: add(), add_tip=f"Add {noun}")
        card.grid(row=row, column=col, sticky="nsew", padx=(0, GUTTER) if col == 0 else 0,
                  pady=(GUTTER, 0) if row > 1 else 0)

        def refresh():
            tbl.set_rows([{"_id": i["id"], "name": i["name"]} for i in store.items(table)])
            if on_change:
                on_change()

        def save(name, item_id=None):
            try:
                store.rename_item(table, item_id, name) if item_id else store.add_item(table, name)
            except sqlite3.IntegrityError:
                app.note(f"'{name}' already exists.", "error")
                return
            refresh()

        @single
        def add():
            name = ui.prompt(app, f"Add {noun}")
            if name:
                save(name)

        @single
        def rename(rid):
            cur = next(i["name"] for i in store.items(table) if i["id"] == rid)
            name = ui.prompt(app, f"Rename {noun}", value=cur)
            if name and name != cur:
                save(name, rid)

        @single
        def remove(rid):
            cur = next(i["name"] for i in store.items(table) if i["id"] == rid)
            if ui.dialog(app, f"Delete '{cur}'?", "It will no longer be offered in lists.",
                         ("Cancel", "Delete"), danger=True) != "Delete":
                return
            try:
                store.delete_item(table, rid)
            except db.InUse:
                why = ("still has sub-categories or is used by existing topics" if table == "categories"
                       else "is used by existing topics or actions")
                ui.dialog(app, "Still in use", f"'{cur}' {why}. Rename it, or change those records first.", ("OK",))
                return
            refresh()

        cols = [{"key": "name", "title": "Name", "weight": 6},
                {"key": "edit", "title": "", "weight": 0.4, "nosort": True, "anchor": "center",
                 "icon": "pencil", "click": rename},
                {"key": "del", "title": "", "weight": 0.4, "nosort": True, "anchor": "center",
                 "icon": "trash-2", "click": remove}]
        tbl = ui.data_table(card.body, cols, height=150, sort=("name", False),
                                empty_text="Empty. Use + to add the first entry.")
        tbl.pack(fill="x")
        refresh()
