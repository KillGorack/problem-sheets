#!/usr/bin/env python3
"""Problem Sheets - problem-solving records with actions, kept in a local SQLite file.

    python3 main.py                      # your data
    python3 main.py --demo               # sample data in a separate demo database
    python3 main.py --theme light        # lor dark (default; remembered in settings)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import tkinter as tk
from tkinter import filedialog

import dave_theme as ui         # first: it prepares ~/.fonts before customtkinter is imported
import customtkinter as ctk     # noqa: E402
import db
import views
from dave_theme import C, GUTTER
from version import APP_NAME, VERSION

MODES = ("dark", "light")


def app_icon() -> Path:
    """The window icon: next to dave_theme.py (source and PyInstaller builds) or inside icons/ (pip installs)."""
    for p in (ui.HERE / "icon.png", ui.ICON_DIR / "icon.png"):
        if p.exists():
            return p
    return ui.HERE / "icon.png"


class App(ctk.CTk):
    def __init__(self, store: db.Store, settings_file: Path, mode: str) -> None:
        super().__init__()
        self.store, self.settings_file = store, settings_file
        self.settings = load_settings(settings_file)
        ui.FONT_SIZE = int(self.settings.get("font_size", ui.FONT_SIZE))
        self.mode = mode
        self.title(APP_NAME)
        self.geometry(self.settings.get("geometry", "1240x800"))
        self.minsize(1000, 640)
        self.configure(fg_color=C["window"])
        try:
            self._icon = tk.PhotoImage(file=app_icon())
            self.iconphoto(True, self._icon)
        except tk.TclError:
            pass
        ui.install_wheel(self)
        self.detail = None
        self.current = "Topics"
        self.section = "Topics"         # the left-bar section last shown
        self.project = None            # the Project the lists are filtered to (None = all projects)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = views.Sidebar(self, self)
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=(GUTTER, 0), pady=(GUTTER, 0))   # pages keep the right GUTTER themselves
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # toolbar:  left bar | note | settings, theme
        bar = self.bar = ui.Toolbar(self)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=GUTTER, pady=GUTTER)
        bar.add(ui.icon_button(bar, "panel-left", self.toggle_sidebar, "Show or hide the left bar"))
        bar.divider()
        bar.stretch()
        bar.divider()
        self.settings_btn = ui.icon_button(bar, "settings", self.toggle_settings, "Settings (Ctrl+,)")
        bar.add(self.settings_btn)
        self.theme_btn = ui.icon_button(bar, self.theme_icon(), self.toggle_theme,
                                        lambda: "Light theme" if self.mode == "dark" else "Dark theme")
        bar.add(self.theme_btn, last=True)

        self.set_sidebar(self.settings.get("sidebar", True))
        self.build_pages()
        self.bind("<Control-n>", lambda _e: self.guard(lambda: self.open_problem(None)))
        self.bind("<Control-f>", lambda _e: self.focus_search())
        self.bind("<Control-s>", lambda _e: self.detail.save() if self.detail is not None else None)
        self.bind("<Control-comma>", lambda _e: self.toggle_settings())
        self.bind("<Escape>", lambda _e: self.escape())
        for key, step in (("plus", 1), ("equal", 1), ("KP_Add", 1), ("minus", -1),
                          ("KP_Subtract", -1), ("Key-0", 0)):
            self.bind(f"<Control-{key}>", lambda _e, s=step: self.zoom(s))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(300, lambda: (self.lift(), self.focus_force()))

    # ---- layout ------------------------------------------------------
    def build_pages(self) -> None:
        for w in self.container.winfo_children():
            w.destroy()
        self.detail = None
        self.pages = {}
        for name, cls in (("Topics", views.ProblemsView), ("Protocol", views.ProtocolView),
                          ("Agenda", views.AgendaView), ("Settings", views.SettingsView)):
            page = cls(self, self.container)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page
        self.show(self.current if self.current in self.pages else "Topics")

    # ---- navigation --------------------------------------------------
    def show(self, name: str) -> None:
        if self.detail is not None:
            self.detail.destroy()
            self.detail = None
        self.current = name
        if name != "Settings":
            self.section = name            # where Settings / Esc return to
        self.sidebar.mark(name)
        page = self.pages[name]
        if hasattr(page, "refresh"):
            page.refresh()
        page.tkraise()

    def toggle_sidebar(self) -> None:
        self.set_sidebar(not self.sidebar.winfo_ismapped())
        self.save({"sidebar": bool(self.sidebar.winfo_ismapped())})

    def set_sidebar(self, show: bool) -> None:
        if show:
            self.sidebar.grid(row=0, column=0, sticky="ns", padx=(GUTTER, 0), pady=(GUTTER, 0))
        else:
            self.sidebar.grid_remove()
        self.update_idletasks()

    def toggle_settings(self) -> None:
        if self.current == "Settings" and self.detail is None:
            self.guard(lambda: self.show(self.section))
        else:
            self.guard(lambda: self.show("Settings"))

    def open_problem(self, pid) -> None:
        def go():
            if self.detail is not None:
                self.detail.destroy()
            self.detail = views.DetailView(self, self.container, pid)
            self.detail.grid(row=0, column=0, sticky="nsew")
            self.detail.tkraise()
        if self.detail is not None and self.detail.dirty():
            self.guard(go)
        else:
            go()

    def close_detail(self) -> None:
        self.show("Topics")

    def escape(self) -> None:
        if self.detail is not None:
            self.guard(self.close_detail)
        elif self.current == "Settings":
            self.show(self.section)

    def focus_search(self) -> None:
        if self.detail is None and self.current == "Topics":
            self.pages["Topics"].search.focus_set()

    def guard(self, proceed) -> None:
        """Run proceed(), but first ask if the open problem has unsaved changes."""
        if self.detail is not None and self.detail.dirty():
            if ui.dialog(self, "Discard changes?", "This topic has unsaved changes.",
                         ("Keep editing", "Discard"), danger=True) != "Discard":
                return
        proceed()

    # ---- feedback ----------------------------------------------------
    def note(self, text: str, tone: str = "muted") -> None:
        """Brief message in the toolbar. tone: muted | success | error."""
        self.bar.note(text, tone)

    # ---- theme and text size -----------------------------------------
    def theme_icon(self) -> str:
        return "sun" if self.mode == "dark" else "moon"

    def set_theme(self, mode: str) -> None:
        self.mode = mode
        ui.set_mode(mode)
        ui.set_icon(self.theme_btn, self.theme_icon())
        self.save({"theme": mode})

    def toggle_theme(self) -> None:
        self.set_theme("light" if self.mode == "dark" else "dark")
        sel = getattr(self.pages["Settings"], "theme_select", None)
        if sel is not None:
            sel.set(self.mode.capitalize())

    def zoom(self, step: int) -> None:
        if self.detail is not None and self.detail.dirty():
            self.note("Save the topic before changing the text size.")
            return
        size = ui.FONT_SIZE + step if step else 13
        size = max(ui.FONT_MIN, min(ui.FONT_MAX, size))
        if size == ui.FONT_SIZE:
            return
        ui.FONT_SIZE = size
        self.save({"font_size": size})
        pid = self.detail.pid if self.detail is not None else None
        self.build_pages()
        if pid:
            self.open_problem(pid)
        self.note(f"Text size {size}")

    def save(self, values: dict) -> None:
        self.settings.update(values)
        save_settings(self.settings_file, dict(load_settings(self.settings_file), **values))

    def close(self) -> None:
        if self.detail is not None and self.detail.dirty():
            if ui.dialog(self, "Discard changes?", "This topic has unsaved changes.",
                         ("Keep editing", "Discard"), danger=True) != "Discard":
                return
        self.save({"geometry": self.geometry()})
        self.destroy()

    def choose_image_dir(self) -> None:
        new = filedialog.askdirectory(parent=self, title="Topic files folder", initialdir=str(self.store.image_dir),
                                      mustexist=False)
        if not new or Path(new) == self.store.image_dir:
            return
        n = len(self.store.problem_folders())
        if n and ui.dialog(self, "Move topic folders?", f"Move the {n} existing topic folder"
                           f"{'s' if n != 1 else ''} (pictures and any files you added) to the new folder?",
                           ("Cancel", "Move folders")) != "Move folders":
            return
        try:
            self.store.set_image_dir(new, move=True)
        except OSError as e:
            ui.dialog(self, "Could not change folder", str(e), ("OK",))
            return
        self.save({"image_dir": str(new)})
        self.current = "Settings"
        self.after(10, self.build_pages)


def load_settings(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _menu_paths(size: int) -> tuple[Path, Path]:
    import os
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return (data / "applications" / "problem-sheets.desktop",
            data / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "problem-sheets.png")


def install_menu() -> int:
    """Add (or refresh) the applications-menu entry for a pip/pipx install. Linux only, per user."""
    import os
    import shutil
    import subprocess
    from PIL import Image
    if not sys.platform.startswith("linux"):
        print("Menu entries are for Linux. On Windows use the MSI installer.")
        return 1
    exe = shutil.which("problem-sheets") or str(Path(sys.argv[0]).resolve())
    with Image.open(app_icon()) as im:
        size = im.width
    desktop, icon = _menu_paths(size)
    icon.parent.mkdir(parents=True, exist_ok=True)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(app_icon(), icon)
    desktop.write_text(
        "[Desktop Entry]\nType=Application\n"
        f"Name={APP_NAME}\nComment=Problem-solving records with actions\n"
        f"Exec={exe}\nIcon={icon}\nTerminal=false\nCategories=Office;\nStartupWMClass=problem-sheets\n")
    desktop.chmod(0o755)
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(desktop.parent)], capture_output=True)
    print(f"Menu entry added: {desktop}\nLaunches: {exe}")
    return 0


def remove_menu() -> int:
    from PIL import Image
    with Image.open(app_icon()) as im:
        size = im.width
    removed = False
    for p in _menu_paths(size):
        if p.exists():
            p.unlink()
            removed = True
    print("Menu entry removed." if removed else "No menu entry was installed.")
    return 0


def selftest() -> int:
    """Check that a build is complete: resources, database, PDF, imaging. No display needed."""
    import tempfile

    import pdf_export
    problems = []
    for name in ("settings", "plus", "trash-2", "sun", "moon", "file-down", "folder-open", "save", "undo-2",
                 "image-plus", "panel-left", "clipboard-list", "scroll-text", "calendar"):
        if not (ui.ICON_DIR / f"{name}.png").exists():
            problems.append(f"missing icon: {name}")
    if not app_icon().exists():
        problems.append("missing icon.png")
    folder = Path(tempfile.mkdtemp())
    store = db.Store(folder / "selftest.db")
    store.seed_demo()
    if len(store.problems()) < 3:
        problems.append("database round-trip failed")
    try:
        p = store.get_problem(1)
        pdf_export.problem_sheet(str(folder / "sheet.pdf"), p, store.actions(1),
                                 [i["path"] for i in store.images(1)])
        if not (folder / "sheet.pdf").stat().st_size > 1000:
            problems.append("PDF came out empty")
    except pdf_export.PdfUnavailable as e:
        problems.append(f"PDF library missing: {e}")
    try:
        from PIL import ImageTk  # noqa: F401
    except ImportError:
        problems.append("Pillow ImageTk missing")
    print(f"{APP_NAME} {VERSION} selftest: " + ("OK" if not problems else "FAILED"))
    for line in problems:
        print("  -", line)
    return 1 if problems else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=f"{APP_NAME} {VERSION}")
    ap.add_argument("--selftest", action="store_true", help="check this install is complete, then exit")
    ap.add_argument("--install-menu", action="store_true", help="add an applications-menu entry (Linux, per user)")
    ap.add_argument("--remove-menu", action="store_true", help="remove that applications-menu entry")
    ap.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    ap.add_argument("--theme", choices=MODES)
    ap.add_argument("--demo", action="store_true", help="use a separate demo database with sample data")
    ap.add_argument("--db", help="database file (default: your data folder)")
    ap.add_argument("--page", choices=("Topics", "Protocol", "Agenda", "Settings"))
    ap.add_argument("--open", type=int, metavar="ID", help="open this topic on start")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if a.install_menu:
        sys.exit(install_menu())
    if a.remove_menu:
        sys.exit(remove_menu())

    folder = db.data_dir()
    path = Path(a.db) if a.db else folder / ("demo.db" if a.demo else "problems.db")
    settings_file = folder / "settings.json"
    saved = load_settings(settings_file)
    # the saved pictures folder belongs to your real database, never the demo or a --db file
    store = db.Store(path, saved.get("image_dir") if not (a.demo or a.db) else None)
    if a.demo:
        store.seed_demo()
    mode = a.theme or saved.get("theme", "dark")
    mode = {"corporate": "light"}.get(mode, mode)       # themes from the old kit
    if mode not in MODES:
        mode = "dark"
    ui.setup(mode)
    app = App(store, settings_file, mode)
    if a.page:
        app.current = a.page
        app.show(a.page)
    if a.open:
        app.open_problem(a.open)
    app.mainloop()


if __name__ == "__main__":
    main()
