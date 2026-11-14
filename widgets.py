"""Problem Sheets' own widgets (not general enough for Dave-Standard): the severity level and project forms."""
from __future__ import annotations

import customtkinter as ctk

from dave_theme import entry


def severity_dialog(app, title: str, name: str = "", color: str = "") -> tuple[str, str] | None:
    """Modal for a severity level: name + hex color with a live swatch. Returns (name, '#RRGGBB') or None."""
    import db
    from dave_theme import C, GUTTER, Panel, button, field, modal, run_modal
    dlg = modal(app, title)
    result = {"v": None}
    panel = Panel(dlg)
    panel.pack(fill="both", expand=True, padx=GUTTER, pady=(GUTTER, 0))
    body = ctk.CTkFrame(panel, fg_color="transparent", height=0)
    body.pack(fill="x", padx=14, pady=14)
    f_name, ent, err_name = field(body, "Name", lambda p: entry(p), required=True)
    f_name.pack(fill="x", pady=(0, GUTTER))
    crow = ctk.CTkFrame(body, fg_color="transparent", height=0)
    crow.pack(fill="x")
    f_col, col, err_col = field(crow, "Color (hex, e.g. #D32F2F)", lambda p: entry(p, "#RRGGBB"), required=True)
    f_col.pack(side="left", fill="x", expand=True)
    swatch = ctk.CTkFrame(crow, width=28, height=28, corner_radius=14, fg_color=C["hover"])
    swatch.pack(side="left", padx=(GUTTER, 0), pady=(18, 0))
    ent.insert(0, name)
    col.insert(0, color)

    def preview(_e=None):
        c = db.Store.clean_color(col.get())
        if c:
            swatch.configure(fg_color=c)

    col.bind("<KeyRelease>", preview)
    preview()

    def ok(_e=None):
        n, c = ent.get().strip(), db.Store.clean_color(col.get())
        err_name(None if n else "Type a name.")
        err_col(None if c else "Use hex, like #D32F2F.")
        if n and c:
            result["v"] = (n, c)
            dlg.destroy()

    bar = ctk.CTkFrame(dlg, fg_color="transparent", height=0)
    bar.pack(anchor="e", padx=GUTTER, pady=GUTTER)
    button(bar, "Cancel", dlg.destroy).pack(side="left", padx=(0, 6))
    button(bar, "Save", ok).pack(side="left")
    dlg.bind("<Return>", ok)
    dlg.after(200, ent.focus_set)
    run_modal(dlg, app, 380)
    return result["v"]


def project_dialog(app, title: str, name: str = "", when: str = "", where: str = "") -> tuple[str, str, str] | None:
    """Modal for a project: name, plus when and where its meeting is (shown on the Protocol).
    Returns (name, when, where) or None."""
    from dave_theme import GUTTER, Panel, button, field, modal, run_modal
    dlg = modal(app, title)
    result = {"v": None}
    panel = Panel(dlg)
    panel.pack(fill="both", expand=True, padx=GUTTER, pady=(GUTTER, 0))
    body = ctk.CTkFrame(panel, fg_color="transparent", height=0)
    body.pack(fill="x", padx=14, pady=14)
    f_name, ent, err_name = field(body, "Name", lambda p: entry(p), required=True)
    f_name.pack(fill="x", pady=(0, 4))
    f_when, ent_when, _ = field(body, "When", lambda p: entry(p, "e.g. Mondays at 10:00"), reserve=False)
    f_when.pack(fill="x", pady=(0, GUTTER))
    f_where, ent_where, _ = field(body, "Where", lambda p: entry(p, "e.g. Room 111, or Teams"), reserve=False)
    f_where.pack(fill="x")
    for e, v in ((ent, name), (ent_when, when), (ent_where, where)):
        if v:
            e.insert(0, v)

    def ok(_e=None):
        n = ent.get().strip()
        err_name(None if n else "Type a name.")
        if n:
            result["v"] = (n, ent_when.get().strip(), ent_where.get().strip())
            dlg.destroy()

    bar = ctk.CTkFrame(dlg, fg_color="transparent", height=0)
    bar.pack(anchor="e", padx=GUTTER, pady=GUTTER)
    button(bar, "Cancel", dlg.destroy).pack(side="left", padx=(0, 6))
    button(bar, "Save", ok).pack(side="left")
    dlg.bind("<Return>", ok)
    dlg.after(200, ent.focus_set)
    run_modal(dlg, app, 420)
    return result["v"]
