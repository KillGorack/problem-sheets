"""
Dave-Standard theme for CustomTkinter  —  v0.3
===============================================
Personal look for side projects, taken from LULIM
(002_Software_Projects\\Python\\LULIM): quiet floating panels, flat icon buttons,
neutral charcoal dark theme and a warm parchment light theme.

Do not edit per app. Apps import from here so every side project shares one look.
Colors are (light, dark) tuples; ctk.set_appearance_mode() switches them, and icons
(CTkImage with a light and a dark tint) follow automatically.
"""

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from typing import Callable

if sys.platform.startswith("linux"):
    # CustomTkinter copies its icon font into ~/.fonts at import; with no such folder it fails and
    # drops to rough "circle_shapes" drawing. A fresh user account has no ~/.fonts.
    (Path.home() / ".fonts").mkdir(exist_ok=True)

import customtkinter as ctk  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(__file__).resolve().parent
ICON_DIR = HERE / "icons"

# =============================================================================
# COLOR TOKENS  (light, dark), names and values from LULIM's THEMES dict
# =============================================================================
C = {
    "window":        ("#bdb5a3", "#262626"),   # window background, the gaps between panels
    "surface":       ("#ded6c3", "#171717"),   # panels: content, toolbar, sidebar, sections
    "text":          ("#332d24", "#b1b1b1"),   # normal text, icons
    "text_strong":   ("#252118", "#d4d4d4"),   # headings, emphasized content (LULIM ai_text)
    "muted":         ("#6b6252", "#8f8f8f"),   # hints, notes, placeholders, quiet icons
    "bubble":        ("#c9c0aa", "#2e2e2e"),   # raised chip / chat bubble
    "bubble_text":   ("#252118", "#b1b1b1"),
    "error":         ("#a33a2a", "#f87171"),   # errors, armed delete, recording
    "success":       ("#4d6a2c", "#a3b88a"),   # ok states (LULIM syn_string)
    "link":          ("#2f5d8a", "#8ab4f8"),   # text links / link-buttons
    "rule":          ("#b3a990", "#3a3a3a"),   # 1px dividers, tooltip border
    "button":        ("#8c806b", "#525252"),   # neutral filled buttons, checkbox fill
    "button_hover":  ("#756a58", "#737373"),
    "hover":         ("#cbc2ae", "#333333"),   # list/icon hover, quiet fills (LULIM list_hover)
    "scrollbar":     ("#a89e8a", "#404040"),
    "scrollbar_hover": ("#8c806b", "#525252"),
    # code blocks + syntax (for apps that show code)
    "code_bg":       ("#d1c8b2", "#262626"),
    "code_head":     ("#5c5344", "#9a9a9a"),
    "code_head_bg":  ("#c3b9a1", "#333333"),
    "syn_keyword":   ("#7a3d6c", "#c09bc8"),
    "syn_string":    ("#4d6a2c", "#a3b88a"),
    "syn_comment":   ("#7d725e", "#767676"),
    "syn_number":    ("#8a5220", "#d1a173"),
    "syn_builtin":   ("#2c6863", "#80b3ad"),
    "syn_func":      ("#2f5d8a", "#8eaed4"),
}

GUTTER = 10          # gap between panels and around the window edge
RADIUS = 6           # panel / control corners (CTk default, as in LULIM)
ICON_SIZE = 18       # toolbar icons
LIST_ICON_SIZE = 16  # icons inside list rows
BTN = 32             # square icon button size

FONT_SIZE = 13       # body text; Ctrl +/- zoom, Ctrl+0 resets
FONT_MIN, FONT_MAX = 9, 24


def cur(token: str) -> str:
    """Current-mode value of a color token, for plain Tk widgets (tk.Menu, tk.Frame, tooltips)."""
    light, dark = C[token]
    return dark if ctk.get_appearance_mode() == "Dark" else light


def ui_family() -> str:
    """The platform's UI font (Segoe UI on Windows, Cantarell/Noto on Linux...)."""
    return tkfont.nametofont("TkDefaultFont").actual("family")


def font(size: int | None = None, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=ui_family(), size=size or FONT_SIZE, weight=weight)


# =============================================================================
# THEME SWITCHING
# =============================================================================
_theme_listeners: list[Callable[[], None]] = []


def on_theme_change(fn: Callable[[], None]):
    """Register a callback for things CTk can't recolor itself (tk.Frame dividers, canvases)."""
    _theme_listeners.append(fn)


def set_mode(mode: str):
    """'dark' or 'light'."""
    ctk.set_appearance_mode(mode)
    for fn in list(_theme_listeners):
        try:
            fn()
        except tk.TclError:          # widget was destroyed
            _theme_listeners.remove(fn)


def setup(mode: str = "dark"):
    ctk.set_default_color_theme("blue")   # base only; every widget below sets its colors
    set_mode(mode)


# =============================================================================
# SETTINGS (JSON in the user's app-data folder)
# =============================================================================
def app_dir(app_name: str) -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / app_name


class Settings(dict):
    """dict that saves itself: settings["theme"] = "light" writes settings.json."""

    def __init__(self, app_name: str):
        self.path = app_dir(app_name) / "settings.json"
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        super().__init__(data)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self, indent=2), encoding="utf-8")


# =============================================================================
# ICONS  — Lucide PNG masks (white, 96x96) tinted per theme
# =============================================================================
_mask_cache: dict[str, Image.Image] = {}


def _tint(name: str, color: str) -> Image.Image:
    if name not in _mask_cache:
        _mask_cache[name] = Image.open(ICON_DIR / f"{name}.png").convert("RGBA").getchannel("A")
    mask = _mask_cache[name]
    img = Image.new("RGBA", mask.size, color)
    img.putalpha(mask)
    return img


def icon(name: str, tone: str = "text", size: int = ICON_SIZE) -> ctk.CTkImage:
    """Icon from icons/<name>.png in the given color token; switches with the theme.
    To add icons: convert a Lucide SVG (lucide.dev) to a 96x96 white PNG in icons/."""
    light, dark = C[tone]
    return ctk.CTkImage(light_image=_tint(name, light), dark_image=_tint(name, dark), size=(size, size))


# =============================================================================
# TOOLTIP
# =============================================================================
class Tooltip:
    """Small label under a widget after the pointer rests on it. text may be a function
    (for toggles whose meaning changes). Polls instead of trusting <Leave>, because CTk
    widgets are several Tk widgets and send Leave while the pointer is still inside."""

    DELAY = 500

    def __init__(self, widget, text: str | Callable[[], str]):
        self.widget, self.text = widget, text
        self.tip = self.job = None
        self.waited, self.clicked = 0, False
        for w in (widget, *widget.winfo_children()):
            tk.Misc.bind(w, "<Enter>", self._enter, add="+")
            tk.Misc.bind(w, "<ButtonPress>", self._click, add="+")

    def _inside(self) -> bool:
        w = self.widget
        if not w.winfo_exists() or not w.winfo_ismapped():
            return False
        x, y = w.winfo_pointerxy()
        return (w.winfo_rootx() <= x < w.winfo_rootx() + w.winfo_width()
                and w.winfo_rooty() <= y < w.winfo_rooty() + w.winfo_height())

    def _enter(self, _e=None):
        if self.job is None:
            self.waited, self.clicked = 0, False
            self.job = self.widget.after(100, self._watch)

    def _click(self, _e=None):
        self.clicked = True
        self._hide()

    def _watch(self):
        self.job = None
        if not self._inside():
            self._hide()
            return
        self.waited += 100
        if self.tip is None and not self.clicked and self.waited >= self.DELAY:
            self._show()
        self.job = self.widget.after(100, self._watch)

    def _show(self):
        text = self.text() if callable(self.text) else self.text
        if not text:
            return
        w = self.widget
        self.tip = tk.Toplevel(w)
        self.tip.overrideredirect(True)
        tk.Label(self.tip, text=text, bg=cur("surface"), fg=cur("text"), padx=6, pady=2,
                 highlightthickness=1, highlightbackground=cur("rule"),
                 font=(ui_family(), 10)).pack()
        self.tip.update_idletasks()
        x = w.winfo_rootx() + (w.winfo_width() - self.tip.winfo_width()) // 2
        x = max(0, min(x, w.winfo_screenwidth() - self.tip.winfo_width()))
        self.tip.geometry(f"+{x}+{w.winfo_rooty() + w.winfo_height() + 4}")

    def _hide(self):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


# =============================================================================
# BASIC COMPONENTS
# =============================================================================
class Panel(ctk.CTkFrame):
    """The building block: a rounded surface floating on the window color."""

    def __init__(self, master, **kw):
        kw.setdefault("fg_color", C["surface"])
        kw.setdefault("corner_radius", RADIUS)
        super().__init__(master, **kw)


def icon_button(master, name: str, command=None, tooltip: str | Callable[[], str] = "",
                tone: str = "text", size: int = ICON_SIZE) -> ctk.CTkButton:
    """Flat icon-only button: just the icon, hover fill. The everyday toolbar control."""
    b = ctk.CTkButton(master, text="", image=icon(name, tone, size), width=BTN, height=BTN,
                      corner_radius=RADIUS, fg_color="transparent", hover_color=C["hover"])
    b.configure(command=command)
    if tooltip:
        Tooltip(b, tooltip)
    return b


def set_icon(button: ctk.CTkButton, name: str, tone: str = "text", size: int = ICON_SIZE):
    """Swap a button's icon (toggles: sun/moon, volume-2/volume-x, mic red while on)."""
    button.configure(image=icon(name, tone, size))


def button(master, text: str, command=None, width: int = 80, **kw) -> ctk.CTkButton:
    """Neutral filled button (Save, Cancel, Test). There is no loud accent color on purpose."""
    return ctk.CTkButton(master, text=text, command=command, width=width, corner_radius=RADIUS,
                         fg_color=C["button"], hover_color=C["button_hover"],
                         text_color=C["text"], text_color_disabled=C["muted"], font=font(), **kw)


def link(master, text: str, command=None, tone: str = "link") -> ctk.CTkLabel:
    """Text link (Copy, Retry, Speak under content). Underlines on hover."""
    lbl = ctk.CTkLabel(master, text=text, text_color=C[tone], cursor="hand2",
                       font=font(FONT_SIZE - 1), height=18)
    if command:
        lbl.bind("<Button-1>", lambda _e: command())
    lbl.bind("<Enter>", lambda _e: lbl.configure(font=ctk.CTkFont(family=ui_family(), size=FONT_SIZE - 1, underline=True)))
    lbl.bind("<Leave>", lambda _e: lbl.configure(font=font(FONT_SIZE - 1)))
    return lbl


def label(master, text: str, muted: bool = False, size: int | None = None, bold: bool = False, **kw):
    return ctk.CTkLabel(master, text=text, anchor="w", justify="left",
                        text_color=C["muted"] if muted else C["text"],
                        font=font(size, "bold" if bold else "normal"), **kw)


def search_entry(master, placeholder: str = "Search", **kw) -> ctk.CTkEntry:
    """Borderless entry on the hover tone, like LULIM's 'Search chats'."""
    return ctk.CTkEntry(master, placeholder_text=placeholder, border_width=0, corner_radius=RADIUS,
                        fg_color=C["hover"], text_color=C["text"],
                        placeholder_text_color=C["muted"], font=font(), **kw)


def entry(master, placeholder: str = "", **kw) -> ctk.CTkEntry:
    return search_entry(master, placeholder, **kw)


def textbox(master, **kw) -> ctk.CTkTextbox:
    """Big text area (content / input). Same surface as panels, themed scrollbar."""
    kw.setdefault("fg_color", C["surface"])
    return ctk.CTkTextbox(master, wrap="word", corner_radius=RADIUS, font=font(),
                          text_color=C["text"], scrollbar_button_color=C["scrollbar"],
                          scrollbar_button_hover_color=C["scrollbar_hover"], border_width=0, **kw)


def quiet_select(master, values: list[str], command=None, width: int = 200) -> ctk.CTkOptionMenu:
    """One-tone pill dropdown (LULIM's model picker)."""
    return ctk.CTkOptionMenu(master, values=values, command=command, width=width,
                             corner_radius=RADIUS, font=font(), dropdown_font=font(),
                             fg_color=C["hover"], button_color=C["hover"],
                             button_hover_color=C["scrollbar"], text_color=C["text"],
                             dropdown_fg_color=C["surface"], dropdown_hover_color=C["hover"],
                             dropdown_text_color=C["text"])


def checkbox(master, text: str, checked: bool = False, **kw) -> ctk.CTkCheckBox:
    cb = ctk.CTkCheckBox(master, text=text, font=font(), text_color=C["text"], fg_color=C["button"],
                         hover_color=C["button_hover"], border_color=C["muted"],
                         checkmark_color=C["text"], corner_radius=4, border_width=2, **kw)
    if checked:
        cb.select()
    return cb


def slider(master, from_: float, to: float, steps: int, value: float,
           fmt: Callable[[float], str] = lambda v: f"{v:.1f}", width: int = 170):
    """Slider + live value label. Returns (frame, slider)."""
    box = ctk.CTkFrame(master, fg_color="transparent")
    val = ctk.CTkLabel(box, width=44, anchor="w", text_color=C["text"], font=font())
    s = ctk.CTkSlider(box, from_=from_, to=to, number_of_steps=steps, width=width,
                      fg_color=C["hover"], progress_color=C["button"], button_color=C["text"],
                      button_hover_color=C["text_strong"],
                      command=lambda v: val.configure(text=fmt(v)))
    s.set(value)
    val.configure(text=fmt(value))
    s.grid(row=0, column=0)
    val.grid(row=0, column=1, padx=(8, 0))
    return box, s


def divider(master, vertical: bool = True, length: int = 18) -> tk.Frame:
    """1px rule between toolbar groups. Plain tk.Frame: CTk won't draw 1px wide."""
    d = tk.Frame(master, width=1 if vertical else length, height=length if vertical else 1,
                 bd=0, bg=cur("rule"))
    on_theme_change(lambda: d.configure(bg=cur("rule")))
    return d


def autohide_scrollbar(sf: ctk.CTkScrollableFrame):
    """Show a CTkScrollableFrame's scrollbar only when its content overflows."""
    def check(_e=None):
        try:
            canvas = sf._parent_canvas
            need = sf.winfo_reqheight() > canvas.winfo_height() + 1
            bar = sf._scrollbar
            if need and not bar.winfo_ismapped():
                bar.grid()
            elif not need and bar.winfo_ismapped():
                bar.grid_remove()
                canvas.yview_moveto(0)
        except tk.TclError:
            pass
    sf.bind("<Configure>", lambda _e: sf.after_idle(check), add="+")
    sf._parent_canvas.bind("<Configure>", lambda _e: sf.after_idle(check), add="+")
    sf.after_idle(check)
    return sf


def themed_menu(master) -> tk.Menu:
    """Right-click menu in theme colors. Build it fresh each time it opens."""
    return tk.Menu(master, tearoff=0, bg=cur("surface"), fg=cur("text"),
                   activebackground=cur("hover"), activeforeground=cur("text"),
                   borderwidth=1, relief="flat", font=(ui_family(), 10))


def popup(menu: tk.Menu, event):
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


# =============================================================================
# COMPOSITE COMPONENTS
# =============================================================================
class Toolbar(Panel):
    """Horizontal bar of icon buttons in groups, a stretchy middle for a status note,
    and a right side. Usage:
        bar = Toolbar(parent)
        bar.add(icon_button(bar, "panel-left", ...)); bar.add(icon_button(bar, "square-pen"))
        bar.divider()
        bar.stretch()                       # status note lives here
        bar.add(quiet_select(bar, [...]))
        bar.divider(); bar.add(icon_button(bar, "settings")); bar.add(theme_btn, last=True)
    """

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._col = 0
        self.status = ctk.CTkLabel(self, text="", anchor="e", font=font(), text_color=C["muted"])
        self._note_job = None

    def add(self, widget, last: bool = False):
        first = self._col == 0
        widget.grid(row=0, column=self._col, pady=6,
                    padx=(6 if first else 0, 6 if last else 2))
        self._col += 1
        return widget

    def divider(self):
        divider(self).grid(row=0, column=self._col, padx=6)
        self._col += 1

    def stretch(self):
        self.grid_columnconfigure(self._col, weight=1)
        self.status.grid(row=0, column=self._col, sticky="e", padx=8)
        self._col += 1

    def note(self, text: str, tone: str = "muted", ms: int = 3000):
        """Brief message in the bar's middle (e.g. 'Saved', 'Text size 15'). ms=0 keeps it."""
        if self._note_job:
            self.after_cancel(self._note_job)
            self._note_job = None
        self.status.configure(text=text, text_color=C[tone])
        if ms:
            self._note_job = self.after(ms, lambda: self.status.configure(text=""))


class ItemList(Panel):
    """Sidebar list: search box on top, rows with a title button and a trash icon.
    Trash needs two clicks (first click arms it red), like LULIM's chat list.
    Right-click a row for a menu built by menu_items(item) -> [(label, fn), ...].

    items:      list of objects; title(item) gives the row text
    on_open:    called with the item when its row is clicked
    on_delete:  called with the item after the second trash click
    matches:    matches(item, words) for search (default: all words in the title)
    """

    def __init__(self, master, title: Callable, on_open: Callable, on_delete: Callable,
                 menu_items: Callable | None = None, matches: Callable | None = None,
                 placeholder: str = "Search", empty_text: str = "Nothing here yet"):
        super().__init__(master)
        self.title, self.on_open, self.on_delete = title, on_open, on_delete
        self.menu_items, self.empty_text = menu_items, empty_text
        self.matches = matches or (lambda it, words: all(w in title(it).lower() for w in words))
        self.items: list = []
        self.selected = None
        self._armed = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.search = search_entry(self, placeholder)
        self.search.grid(row=0, column=0, sticky="ew", padx=GUTTER, pady=(GUTTER, 0))
        self._job = None
        self.search.bind("<KeyRelease>", self._debounce)
        self.search.bind("<Escape>", lambda _e: (self.search.delete(0, "end"), self.refresh()))
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                           scrollbar_button_color=C["scrollbar"],
                                           scrollbar_button_hover_color=C["scrollbar_hover"])
        self.list.grid(row=1, column=0, sticky="nsew", padx=5, pady=(4, GUTTER))
        self.list.grid_columnconfigure(0, weight=1)
        autohide_scrollbar(self.list)

    def set_items(self, items: list):
        self.items = items
        self.refresh()

    def _debounce(self, _e=None):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(150, self.refresh)

    def refresh(self):
        self._job = None
        self._armed = None
        for w in self.list.winfo_children():
            w.destroy()
        words = self.search.get().lower().split()
        shown = [it for it in self.items if not words or self.matches(it, words)]
        if not shown:
            label(self.list, "No matches" if words else self.empty_text, muted=True).grid(
                row=0, column=0, sticky="w", padx=GUTTER, pady=4)
        for i, it in enumerate(shown):
            on = it is self.selected
            # No selected background: the open item only gets stronger text (hover still fills).
            b = ctk.CTkButton(self.list, text=self.title(it), anchor="w", font=font(),
                              fg_color="transparent", hover_color=C["hover"],
                              text_color=C["text_strong"] if on else C["text"],
                              corner_radius=RADIUS, command=lambda it=it: self._open(it))
            b.grid(row=i, column=0, sticky="ew", pady=1)
            trash = ctk.CTkButton(self.list, text="", image=icon("trash-2", "muted", LIST_ICON_SIZE),
                                  width=28, fg_color="transparent", hover_color=C["hover"],
                                  corner_radius=RADIUS)
            trash.configure(command=lambda it=it, t=trash: self._trash(it, t))
            trash.grid(row=i, column=1, pady=1)
            Tooltip(trash, lambda t=trash: "Click again to delete" if self._armed and self._armed[1] is t
                    else "Delete (click twice)")
            if self.menu_items:
                b.bind("<Button-3>", lambda e, it=it: self._menu(e, it))

    def _open(self, it):
        self.selected = it
        self.on_open(it)
        self.refresh()

    def _trash(self, it, btn):
        if self._armed and self._armed[0] is it:
            self._armed = None
            self.on_delete(it)
            return
        if self._armed:                     # disarm the previous one
            try:
                self._armed[1].configure(image=icon("trash-2", "muted", LIST_ICON_SIZE))
            except tk.TclError:
                pass
        self._armed = (it, btn)
        btn.configure(image=icon("trash-2", "error", LIST_ICON_SIZE))
        btn.after(3000, lambda: self._disarm(it, btn))

    def _disarm(self, it, btn):
        if self._armed and self._armed[0] is it:
            self._armed = None
            try:
                btn.configure(image=icon("trash-2", "muted", LIST_ICON_SIZE))
            except tk.TclError:
                pass

    def _menu(self, event, it):
        m = themed_menu(self)
        for text, fn in self.menu_items(it):
            m.add_command(label=text, command=fn)
        popup(m, event)


class FormWindow(ctk.CTkToplevel):
    """Settings-style dialog: stacked panels ('sections'), label column on the left,
    controls on the right, a muted note under a control, Cancel/Save at the bottom right.
    Ported from LULIM's settings window.

        win = FormWindow(app, "Settings", on_save=lambda values: ...)
        win.section("Display")
        win.field("Text size", win.slider("font_size", 9, 24, 15, 13, lambda v: f"{v:.0f}"))
        win.field("", win.check("compact", "Compact rows", False), "Takes effect right away.")
        win.finish()
    """

    def __init__(self, master, title: str, on_save: Callable[[dict], None], label_width: int = 110):
        super().__init__(master, fg_color=C["window"])
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self._on_save = on_save
        self._get: dict[str, Callable] = {}
        self._sec = None
        self._row = 0
        self._sections = 0
        self._label_width = label_width
        self.bind("<Escape>", lambda _e: self.destroy())

    def section(self, title: str):
        self._sec = Panel(self)
        self._sec.grid(row=self._sections, column=0, sticky="ew", padx=GUTTER, pady=(GUTTER, 0))
        self._sec.grid_columnconfigure(0, minsize=self._label_width)
        self._sections += 1
        label(self._sec, title, bold=True).grid(row=0, column=0, columnspan=2, sticky="w",
                                                 padx=14, pady=(8, 2))
        self._row = 1
        return self._sec

    def field(self, text: str, widget, note: str = ""):
        label(self._sec, text).grid(row=self._row, column=0, sticky="w", padx=(14, 12), pady=4)
        widget.grid(row=self._row, column=1, sticky="w", padx=(0, 14), pady=4)
        self._row += 1
        if note:
            label(self._sec, note, muted=True, size=FONT_SIZE - 2, height=16).grid(
                row=self._row, column=1, sticky="w", padx=(0, 14), pady=(0, 4))
            self._row += 1
        self._sec.grid_rowconfigure(self._row, minsize=8)

    # value builders: each registers how to read its value back on Save
    def menu(self, key: str, choices: list[tuple[str, object]], current):
        labels = [c[0] for c in choices]
        m = quiet_select(self._sec, labels, width=220)
        m.set(next((lbl for lbl, v in choices if v == current), labels[0]))
        self._get[key] = lambda: dict(choices)[m.get()]
        return m

    def slider(self, key: str, lo, hi, steps, current, fmt=lambda v: f"{v:.1f}"):
        box, s = slider(self._sec, lo, hi, steps, current, fmt)
        self._get[key] = lambda: round(s.get(), 2)
        return box

    def check(self, key: str, text: str, current: bool):
        c = checkbox(self._sec, text, current)
        self._get[key] = lambda: bool(c.get())
        return c

    def text(self, key: str, current: str, placeholder: str = "", width: int = 220):
        e = entry(self._sec, placeholder, width=width)
        if current:
            e.insert(0, current)
        self._get[key] = lambda: e.get().strip()
        return e

    def finish(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=self._sections, column=0, sticky="e", padx=GUTTER, pady=GUTTER)
        button(row, "Cancel", self.destroy).grid(row=0, column=0, padx=(0, 6))
        button(row, "Save", self._save).grid(row=0, column=1)
        self.after(150, self.focus)   # CTkToplevel finishes setting up after a moment

    def _save(self):
        self._on_save({k: fn() for k, fn in self._get.items()})
        self.destroy()


def toggle_window(owner, key: str, build: Callable[[], ctk.CTkToplevel]):
    """A toolbar button that opens a window toggles it: the first click opens it, the next
    click closes it. A button never stacks up copies.
        icon_button(bar, "settings", lambda: ui.toggle_window(self, "settings", self.build_settings))
    `build` creates and returns the window."""
    windows = owner.__dict__.setdefault("_ui_windows", {})
    win = windows.get(key)
    if win is not None and win.winfo_exists():
        win.destroy()
        windows.pop(key, None)
        return None
    win = windows[key] = build()
    return win


def ask(master, title: str, message: str, ok: str = "OK", danger: bool = False) -> bool:
    """Small modal yes/no in the same style. Returns True on OK."""
    result = {"ok": False}
    win = ctk.CTkToplevel(master, fg_color=C["window"])
    win.title(title)
    win.resizable(False, False)
    win.transient(master)
    p = Panel(win)
    p.pack(fill="both", expand=True, padx=GUTTER, pady=(GUTTER, 0))
    label(p, title, bold=True).pack(anchor="w", padx=14, pady=(10, 2))
    label(p, message, muted=True, wraplength=320).pack(anchor="w", padx=14, pady=(0, 12))
    row = ctk.CTkFrame(win, fg_color="transparent")
    row.pack(anchor="e", padx=GUTTER, pady=GUTTER)

    def done(v):
        result["ok"] = v
        win.destroy()

    button(row, "Cancel", lambda: done(False)).pack(side="left", padx=(0, 6))
    okb = button(row, ok, lambda: done(True))
    if danger:
        okb.configure(text_color=C["error"])
    okb.pack(side="left")
    win.bind("<Escape>", lambda _e: done(False))
    win.bind("<Return>", lambda _e: done(True))
    win.after(150, lambda: (win.focus(), win.grab_set()))
    master.wait_window(win)
    return result["ok"]


# =============================================================================
# v0.2 ADDITIONS (first used by Problem Sheets): scrolling, forms, tables, dialogs
# =============================================================================
CELL_X, CELL_Y = 12, 7       # table cell padding


class ScrollFrame(ctk.CTkScrollableFrame):
    """CTkScrollableFrame that (1) scrolls with the mouse wheel on Tk 9 (CTk only listens for the
    old Button-4/5 events on Linux; see install_wheel), (2) has no built-in 6px padding, and
    (3) draws its scrollbar as an overlay on the right edge, only when the content overflows.
    The bar never takes layout width, so showing or hiding it can't shift or resize anything
    (re-gridding a real scrollbar made tables 'vibrate'). `track` is the color token behind
    the bar; `bar_width` 10 (= GUTTER) lets it sit in the window margin beside the panels."""

    def __init__(self, master, bar_width: int = 8, track: str = "surface", **kw):
        kw.setdefault("corner_radius", 0)
        super().__init__(master, **kw)
        self._bar_shown, self._sync_job = False, None
        bar = self._scrollbar
        bar.configure(fg_color=C[track], width=bar_width)
        tk.Grid.grid_forget(bar)
        self.bind("<Configure>", lambda _e: self.sync_later(), add="+")
        self._parent_canvas.bind("<Configure>", lambda _e: self.sync_later(), add="+")

    def sync_later(self):
        """Debounced: while the layout settles the canvas reports transient sizes (1px, 200px)."""
        if self._sync_job:
            self.after_cancel(self._sync_job)
        self._sync_job = self.after(120, self.sync_bar)

    def sync_bar(self):
        self._sync_job = None
        try:
            top, bottom = self._parent_canvas.yview()
            need = (bottom - top) < 0.999
            if need and not self._bar_shown:
                self._scrollbar.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne")
                self._scrollbar.lift()
            elif not need and self._bar_shown:
                self._scrollbar.place_forget()
                self._parent_canvas.yview_moveto(0)
            self._bar_shown = need
        except tk.TclError:
            pass

    def _mouse_wheel_all(self, event):      # CTk's own handler, replaced by the app-wide one
        pass

    def can_scroll(self, direction: int) -> bool:
        top, bottom = self._parent_canvas.yview()
        return top > 0.0 if direction < 0 else bottom < 1.0

    def scroll(self, steps: int) -> None:
        self._parent_canvas.yview_scroll(steps, "units")


def install_wheel(root) -> None:
    """Call once on the root window. One mouse-wheel handler for the whole window: it scrolls the
    innermost ScrollFrame under the pointer that can still move that way, so the wheel falls
    through from a short table to the page around it. Text boxes that can scroll keep their wheel."""
    if getattr(root, "_dave_wheel", False):
        return
    root._dave_wheel = True

    def on_wheel(event):
        if getattr(event, "num", 0) == 4:
            direction, steps = -1, 1
        elif getattr(event, "num", 0) == 5:
            direction, steps = 1, 1
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return
            direction = -1 if delta > 0 else 1
            steps = max(1, abs(delta) // 120)
        try:
            w = root.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return
        while w is not None:
            if isinstance(w, tk.Text):
                top, bottom = w.yview()
                if (top > 0.0) if direction < 0 else (bottom < 1.0):
                    return                      # the text box scrolls itself
            elif isinstance(w, ScrollFrame) and w.can_scroll(direction):
                w.scroll(direction * steps * 2)
                return
            w = getattr(w, "master", None)

    for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        root.bind_all(ev, on_wheel, add="+")


def scroll_frame(master, **kw) -> ScrollFrame:
    """Transparent scrolling area for a page of panels. Its scrollbar overlays the right edge, in
    the window margin: give it the full width to the window edge, and give each panel inside a
    right margin of GUTTER, so the panels line up with the fixed panels above and below it."""
    kw.setdefault("fg_color", "transparent")
    kw.setdefault("bar_width", GUTTER)
    kw.setdefault("track", "window")
    sf = ScrollFrame(master, scrollbar_button_color=C["scrollbar"],
                     scrollbar_button_hover_color=C["scrollbar_hover"], **kw)
    sf.grid_columnconfigure(0, weight=1)
    return sf


def section(master, title: str | None = None, on_add: Callable | None = None, add_tip: str = "") -> Panel:
    """A Panel with an optional bold title. Put content in `.body`.
    on_add: puts a + icon button to the left of the title (it replaces an "Add" button below the content).
    The header row is `.head` (add a hint beside the title there), the + is `.add_button`."""
    p = Panel(master)
    p.head = p.add_button = None
    if on_add:
        p.head = ctk.CTkFrame(p, fg_color="transparent", height=0)
        p.head.pack(anchor="w", padx=(8, 14), pady=(6, 0))
        p.add_button = icon_button(p.head, "plus", on_add, add_tip)
        p.add_button.pack(side="left", pady=(2, 0))   # the icon box sits 1px high against the label font
        label(p.head, title or "", bold=True, height=0).pack(side="left", padx=(2, 0))
    elif title:
        label(p, title, bold=True, height=0).pack(anchor="w", padx=14, pady=(10, 0))
    p.body = ctk.CTkFrame(p, fg_color="transparent", height=0)
    p.body.pack(fill="both", expand=True, padx=14, pady=(8, 12))
    return p


def field(master, text: str, make: Callable, required: bool = False, hint: str | None = None,
          reserve: bool = True):
    """Label above a control, with a line below for an error (or hint). `make(parent)` builds the control.
    Returns (frame, control, set_error).
    reserve: keep that line's room even while it is empty, so an error replaces blank space instead of
    growing the form (a fixed-size dialog would push its buttons out of the window). Pass False for a
    field that can never show an error."""
    frame = ctk.CTkFrame(master, fg_color="transparent", height=0)
    row = ctk.CTkFrame(frame, fg_color="transparent", height=0)
    row.pack(anchor="w")
    label(row, text, muted=True, size=FONT_SIZE - 1, height=0).pack(side="left")
    if required:
        ctk.CTkLabel(row, text=" *", font=font(FONT_SIZE - 1, "bold"), text_color=C["error"],
                     height=0).pack(side="left")
    ctl = make(frame)
    ctl.pack(fill="x", pady=(4, 0))
    err = label(frame, "", muted=True, size=FONT_SIZE - 2, height=0)

    def set_error(msg=None):
        txt = msg or hint or ("\u00a0" if reserve else "")
        err.configure(text=txt, text_color=C["error" if msg else "muted"])
        if txt:
            err.pack(anchor="w", pady=(3, 0))
        else:
            err.pack_forget()

    set_error()
    return frame, ctl, set_error


# ---- images -----------------------------------------------------------------
_img_cache: dict = {}


def dot(color: str, size: int = 14) -> Image.Image:
    """Anti-aliased filled circle (RGBA PIL image), e.g. a severity dot."""
    key = ("dot", color, size)
    if key not in _img_cache:
        from PIL import ImageDraw
        k = 8                                              # draw big, shrink: smooth edge
        big = Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0))
        ImageDraw.Draw(big).ellipse((k, k, size * k - k, size * k - k), fill=color)
        _img_cache[key] = big.resize((size, size), Image.LANCZOS)
    return _img_cache[key]


def dot_image(color: str, size: int = 16) -> ctk.CTkImage:
    return ctk.CTkImage(dot(color, size), size=(size, size))


def thumb(path, size: int = 64):
    """Square, center-cropped PIL thumbnail of an image file (EXIF-rotated); None if unreadable."""
    if not path:
        return None
    key = ("thumb", str(path), size)
    if key not in _img_cache:
        try:
            from PIL import ImageOps
            with Image.open(path) as im:
                _img_cache[key] = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"),
                                               (size, size), Image.LANCZOS)
        except (OSError, ValueError):
            _img_cache[key] = None
    return _img_cache[key]


def fit_image(path, max_w: int, max_h: int):
    """Whole picture scaled to fit max_w x max_h, as a CTkImage; None if unreadable."""
    try:
        from PIL import ImageOps
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
    except (OSError, ValueError):
        return None
    k = min(max_w / im.width, max_h / im.height, 1)
    return ctk.CTkImage(im, size=(max(1, round(im.width * k)), max(1, round(im.height * k))))


# ---- table ------------------------------------------------------------------
class DataTable(ctk.CTkFrame):
    """Flat (no frame): sits directly on a panel. Sortable, scrollable, selectable table. Stripes `hover`, mouse-over `rule`,
    selected `button`, bold header over a 1px `rule`.

    columns: dicts {"key", "title", "weight"=1, "anchor"="w", "wrap"=px, "sortkey"=fn(row)->value,
             "nosort": True, "image": True, "size": 14 -> the value is "dot:#RRGGBB" (colored dot)
             or an image file path (square thumbnail),
             "icon": "pencil", "click": fn(row_id), "skip": "first"|"last" -> a small clickable icon in
             every row (edit, trash, move arrows; skip = none on the first / last row). The click
             selects the row, then calls click(row_id).}
    rows:    dicts keyed by column key; "_id" identifies the record.
    Click a header to sort (again to reverse), click a row to select, double-click to open.
    color_fn(row, key) -> color token ("muted", "error"...) or None, for per-cell text color.
    """

    def __init__(self, master, columns, on_select=None, on_open=None, color_fn=None,
                 empty_text="Nothing to show.", sort=None, height=300):
        super().__init__(master, fg_color="transparent", corner_radius=0)   # flat: no frame of its own
        self.columns, self.on_select, self.on_open, self.color_fn = columns, on_select, on_open, color_fn
        self.empty_text = empty_text
        self.rows: list[dict] = []
        self.sort_key, self.sort_desc = sort if sort else (None, False)
        self.selected = None              # "_id" of the selected row
        self._lines: list[list[tk.Label]] = []
        self._order: list[dict] = []
        self._photos: list = []
        self.head = tk.Frame(self, bg=cur("surface"), bd=0, highlightthickness=0)
        self.head.pack(fill="x")
        self.rule = tk.Frame(self, height=1, bd=0, bg=cur("rule"))
        self.rule.pack(fill="x")
        self.body = ScrollFrame(self, fg_color="transparent", height=height,
                                scrollbar_button_color=C["scrollbar"],
                                scrollbar_button_hover_color=C["scrollbar_hover"])
        self.body.pack(fill="both", expand=True)
        for i, col in enumerate(columns):
            w = max(1, round(col.get("weight", 1) * 10))
            self.head.columnconfigure(i, weight=w, uniform="c")
            self.body.columnconfigure(i, weight=w, uniform="c")
        self._build_header()
        on_theme_change(self._retheme)

    # ---- public
    def set_rows(self, rows):
        self.rows = list(rows)
        if self.selected not in {r["_id"] for r in self.rows}:
            self.selected = None
        self._render()

    def selected_row(self):
        return next((r for r in self.rows if r["_id"] == self.selected), None)

    # ---- internals
    def _retheme(self):
        if not self.winfo_exists():
            raise tk.TclError("gone")
        self.head.configure(bg=cur("surface"))
        self.rule.configure(bg=cur("rule"))
        self._build_header()
        self._render()

    def _build_header(self):
        for w in self.head.winfo_children():
            w.destroy()
        self._heads = []
        for i, col in enumerate(self.columns):
            lab = tk.Label(self.head, text=col["title"], anchor=col.get("anchor", "w"), bd=0,
                           bg=cur("surface"), fg=cur("text_strong"), font=font(FONT_SIZE, "bold"),
                           padx=CELL_X, pady=CELL_Y, cursor="" if col.get("nosort") else "hand2")
            lab.grid(row=0, column=i, sticky="nsew")
            if not col.get("nosort"):
                lab.bind("<Button-1>", lambda _e=None, k=col["key"]: self._sort_by(k))
            self._heads.append(lab)
        self._update_header()

    def _update_header(self):
        for lab, col in zip(self._heads, self.columns):
            arrow = ("  ▼" if self.sort_desc else "  ▲") if col["key"] == self.sort_key else ""
            lab.configure(text=col["title"] + arrow)

    def _sort_by(self, key):
        self.sort_desc = (not self.sort_desc) if key == self.sort_key else False
        self.sort_key = key
        self._update_header()
        self._render()

    def _sorted(self):
        if not self.sort_key:
            return list(self.rows)
        col = next(c for c in self.columns if c["key"] == self.sort_key)
        fn = col.get("sortkey") or (lambda r: r.get(self.sort_key))

        def key(r):
            v = fn(r)
            if v is None or v == "":
                return (1, 0, "")            # empty values always last
            if isinstance(v, (int, float)):
                return (0, v, "")
            return (0, 0, str(v).lower())

        present = [r for r in self.rows if key(r)[0] == 0]
        empty = [r for r in self.rows if key(r)[0] == 1]
        present.sort(key=key, reverse=self.sort_desc)
        return present + empty

    def _paint(self, r, state="normal"):
        row = self._order[r]
        for i, lab in enumerate(self._lines[r]):
            if state == "selected":
                lab.configure(bg=cur("button"), fg=cur("text_strong"))
                continue
            bg = cur("rule") if state == "hover" else cur("hover") if r % 2 else cur("surface")
            tok = self.color_fn(row, self.columns[i]["key"]) if self.color_fn else None
            lab.configure(bg=bg, fg=cur(tok) if tok else cur("text"))

    def _cell_image(self, value, size):
        try:
            if isinstance(value, str) and value.startswith("dot:"):
                from PIL import ImageTk
                return ImageTk.PhotoImage(dot(value[4:], size))
            pil = thumb(value, size)
            if pil is not None:
                from PIL import ImageTk
                return ImageTk.PhotoImage(pil)
        except (ValueError, ImportError):
            pass
        return None

    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        self._order = self._sorted()
        self._lines, self._photos = [], []
        if not self._order:
            tk.Label(self.body, text=self.empty_text, bd=0, bg=cur("surface"), fg=cur("muted"),
                     font=font(), pady=24).grid(row=0, column=0, columnspan=len(self.columns), sticky="ew")
            self.body.sync_later()
            return
        for r, row in enumerate(self._order):
            line = []
            for i, col in enumerate(self.columns):
                if col.get("image"):
                    photo = self._cell_image(row.get(col["key"]), col.get("size", 32))
                    self._photos.append(photo)
                    lab = tk.Label(self.body, image=photo, text="" if photo else " ", anchor="center", bd=0,
                                   padx=CELL_X, pady=3)
                else:
                    val = row.get(col["key"])
                    lab = tk.Label(self.body, text="" if val is None else str(val), bd=0,
                                   anchor=col.get("anchor", "w"), font=font(), justify="left",
                                   wraplength=col.get("wrap", 0), padx=CELL_X, pady=CELL_Y)
                lab.grid(row=r, column=i, sticky="nsew")
                lab.bind("<Button-1>", lambda _e=None, r=r: self._click(r))
                lab.bind("<Double-Button-1>", lambda _e=None, r=r: self._open(r))
                lab.bind("<Enter>", lambda _e=None, r=r: self._hover(r, True))
                lab.bind("<Leave>", lambda _e=None, r=r: self._hover(r, False))
                line.append(lab)
            self._lines.append(line)
            self._paint(r, "selected" if row["_id"] == self.selected else "normal")
        self._row_icons()
        self.body.sync_later()

    def _row_icons(self):
        """Put the clickable icons of "icon" columns into the rows just drawn."""
        from PIL import ImageTk
        self._icon_photos = []
        last = len(self._lines) - 1
        for r, line in enumerate(self._lines):
            for i, col in enumerate(self.columns):
                name = col.get("icon")
                if not name or (col.get("skip") == "first" and r == 0) or (col.get("skip") == "last" and r == last):
                    continue
                photo = ImageTk.PhotoImage(_tint(name, cur("muted")).resize((14, 14), Image.LANCZOS))
                self._icon_photos.append(photo)
                line[i].configure(image=photo, text="", cursor="hand2")
                line[i].bind("<Button-1>", lambda _e, r=r, c=col["click"]: self._hit(r, c))

    def _hit(self, r, click):
        rid = self._order[r]["_id"]
        self._click(r)
        click(rid)

    def _hover(self, r, on):
        if r < len(self._order) and self._order[r]["_id"] != self.selected:
            self._paint(r, "hover" if on else "normal")

    def _click(self, r):
        prev = next((i for i, row in enumerate(self._order) if row["_id"] == self.selected), None)
        self.selected = self._order[r]["_id"]
        if prev is not None and prev != r:
            self._paint(prev)
        self._paint(r, "selected")
        if self.on_select:
            self.on_select(self._order[r])

    def _open(self, r):
        self._click(r)
        if self.on_open:
            self.on_open(self._order[r])


def data_table(master, columns, **kw) -> DataTable:
    return DataTable(master, columns, **kw)


# ---- windows ----------------------------------------------------------------
def modal(master, title: str) -> ctk.CTkToplevel:
    """Empty modal window in theme colors; fill it, then call run_modal()."""
    dlg = ctk.CTkToplevel(master, fg_color=C["window"])
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.transient(master)
    return dlg


def run_modal(dlg, master, min_width: int = 420):
    """Size to content, center over the owner, grab input, wait until closed."""
    dlg.update_idletasks()
    w, h = max(min_width, dlg.winfo_reqwidth()), dlg.winfo_reqheight()
    x = master.winfo_rootx() + (master.winfo_width() - w) // 2
    y = master.winfo_rooty() + (master.winfo_height() - h) // 3
    dlg.geometry(f"{w}x{h}+{x}+{y}")
    dlg.bind("<Escape>", lambda _e: dlg.destroy())
    dlg.after(150, lambda: (dlg.grab_set(), dlg.focus_force()))
    master.wait_window(dlg)


def dialog(master, title: str, message: str, buttons=("Cancel", "OK"), danger: bool = False):
    """Modal message with any number of buttons. The last one is the main action (red text if
    `danger`). Returns the label clicked, or None if closed with Esc."""
    result = {"v": None}
    win = modal(master, title)
    p = Panel(win)
    p.pack(fill="both", expand=True, padx=GUTTER, pady=(GUTTER, 0))
    label(p, title, bold=True).pack(anchor="w", padx=14, pady=(10, 2))
    label(p, message, muted=True, wraplength=340).pack(anchor="w", padx=14, pady=(0, 12))
    row = ctk.CTkFrame(win, fg_color="transparent")
    row.pack(anchor="e", padx=GUTTER, pady=GUTTER)

    def done(v):
        result["v"] = v
        win.destroy()

    for i, b in enumerate(buttons):
        btn = button(row, b, lambda b=b: done(b))
        if danger and i == len(buttons) - 1:
            btn.configure(text_color=C["error"])
        btn.pack(side="left", padx=(6 if i else 0, 0))
    run_modal(win, master, 380)
    return result["v"]


# =============================================================================
# v0.3 ADDITIONS (first used by Problem Sheets): date picker, one-line prompt
# =============================================================================


class DateEntry(ctk.CTkFrame):
    """YYYY-MM-DD entry with a small calendar popup (calendar icon at the right).
    Type a date or pick one. Same get / set / insert / delete as an entry."""

    def __init__(self, master, placeholder: str = "YYYY-MM-DD", **kw):
        super().__init__(master, fg_color="transparent", height=0, **kw)
        self.columnconfigure(0, weight=1)
        self.entry = entry(self, placeholder)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.btn = icon_button(self, "calendar", self.open, "Pick a date", tone="muted", size=LIST_ICON_SIZE)
        self.btn.configure(width=28, height=28)
        self.btn.grid(row=0, column=1, padx=(4, 0))
        self.pop = None

    # entry-compatible
    def get(self) -> str:
        return self.entry.get()

    def insert(self, index, text):
        self.entry.insert(index, text)

    def delete(self, a, b=None):
        self.entry.delete(a, b)

    def set(self, value: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, value or "")

    # popup
    def _current(self):
        import datetime as dt
        try:
            return dt.date.fromisoformat(self.entry.get().strip())
        except ValueError:
            return None

    def open(self):
        import calendar
        import datetime as dt
        if self.pop is not None:
            self.close()
            return
        today, picked = dt.date.today(), self._current()
        shown = {"y": (picked or today).year, "m": (picked or today).month}
        pop = self.pop = tk.Toplevel(self)
        pop.overrideredirect(True)
        box = tk.Frame(pop, bg=cur("surface"), highlightthickness=1, highlightbackground=cur("rule"), bd=0)
        box.pack()
        head = tk.Frame(box, bg=cur("surface"))
        head.pack(fill="x", padx=8, pady=(8, 4))
        title = tk.Label(head, bg=cur("surface"), fg=cur("text_strong"), font=font(FONT_SIZE, "bold"))
        grid = tk.Frame(box, bg=cur("surface"))
        grid.pack(padx=8)

        def nav(txt, step):
            b = tk.Label(head, text=txt, bg=cur("surface"), fg=cur("muted"), font=font(FONT_SIZE + 3, "bold"),
                         width=2, cursor="hand2")
            b.bind("<ButtonRelease-1>", lambda _e: go(step))
            b.bind("<Enter>", lambda _e: b.configure(bg=cur("hover")))
            b.bind("<Leave>", lambda _e: b.configure(bg=cur("surface")))
            return b

        def go(step):
            m = shown["m"] - 1 + step
            shown["y"] += m // 12
            shown["m"] = m % 12 + 1
            draw()

        nav("‹", -1).pack(side="left")
        title.pack(side="left", expand=True)
        nav("›", 1).pack(side="right")

        def choose(d):
            # Picks act on mouse RELEASE: closing on press let the release fall through to whatever
            # sat under the popup - in a dialog that could be the Save button (CTk buttons fire on release).
            self.set(d.isoformat())
            self.close()

        def draw():
            for w in grid.winfo_children():
                w.destroy()
            title.configure(text=f"{calendar.month_name[shown['m']]} {shown['y']}")
            for i, n in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
                tk.Label(grid, text=n, width=3, bg=cur("surface"), fg=cur("muted"),
                         font=font(FONT_SIZE - 2)).grid(row=0, column=i)
            weeks = calendar.Calendar(0).monthdatescalendar(shown["y"], shown["m"])
            for r, week in enumerate(weeks, start=1):
                for i, d in enumerate(week):
                    sel, now, other = d == picked, d == today, d.month != shown["m"]
                    lab = tk.Label(grid, text=str(d.day), width=3, bg=cur("button") if sel else cur("surface"),
                                   fg=cur("text_strong") if sel or now else cur("muted") if other else cur("text"),
                                   font=font(FONT_SIZE - 1, "bold" if now else "normal"), cursor="hand2")
                    lab.grid(row=r, column=i, pady=1)
                    if not sel:
                        lab.bind("<Enter>", lambda _e, l=lab: l.configure(bg=cur("hover")))
                        lab.bind("<Leave>", lambda _e, l=lab: l.configure(bg=cur("surface")))
                    lab.bind("<ButtonRelease-1>", lambda _e, d=d: choose(d))   # release: see choose()

        draw()
        foot = tk.Frame(box, bg=cur("surface"))
        foot.pack(fill="x", padx=8, pady=(4, 8))
        for txt, fn in (("Today", lambda: choose(today)), ("Clear", lambda: (self.set(""), self.close()))):
            b = tk.Label(foot, text=txt, bg=cur("surface"), fg=cur("link"), font=font(FONT_SIZE - 1), cursor="hand2")
            b.bind("<ButtonRelease-1>", lambda _e, fn=fn: fn())
            b.pack(side="left" if txt == "Today" else "right")

        pop.update_idletasks()
        x = self.winfo_rootx() + self.winfo_width() - pop.winfo_reqwidth()
        y = self.winfo_rooty() + self.winfo_height() + 2
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        if y + pop.winfo_reqheight() > sh:
            y = self.winfo_rooty() - pop.winfo_reqheight() - 2
        pop.geometry(f"+{max(0, min(x, sw - pop.winfo_reqwidth()))}+{max(0, y)}")
        pop.bind("<Escape>", lambda _e: self.close())
        self._outside = self.winfo_toplevel().bind("<Button-1>", self._click_away, add="+")   # undone in close()
        pop.focus_set()

    def _click_away(self, e):
        if self.pop is not None and not str(e.widget).startswith(str(self.pop)) and e.widget is not self.btn._canvas \
                and not str(e.widget).startswith(str(self.btn)):
            self.close()

    def close(self):
        if self.pop is not None:
            self.pop.destroy()
            self.pop = None
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._outside)
            except tk.TclError:
                pass


def date_entry(master, placeholder: str = "YYYY-MM-DD") -> DateEntry:
    return DateEntry(master, placeholder)


def prompt(master, title: str, label_text: str = "Name", value: str = "", ok: str = "Save") -> str | None:
    """Small modal asking for one line of text (add / rename). Returns the text, or None if cancelled.
    Enter saves, Esc cancels; an empty answer shows an error instead of closing."""
    dlg = modal(master, title)
    result = {"v": None}
    panel = Panel(dlg)
    panel.pack(fill="both", expand=True, padx=GUTTER, pady=(GUTTER, 0))
    f, ent, err = field(panel, label_text, lambda p: entry(p), required=True)
    f.pack(fill="x", padx=14, pady=14)
    ent.insert(0, value)

    def done(_e=None):
        if not ent.get().strip():
            err("Type a name.")
            return
        result["v"] = ent.get().strip()
        dlg.destroy()

    bar = ctk.CTkFrame(dlg, fg_color="transparent", height=0)
    bar.pack(anchor="e", padx=GUTTER, pady=GUTTER)
    button(bar, "Cancel", dlg.destroy).pack(side="left", padx=(0, 6))
    button(bar, ok, done).pack(side="left")
    ent.bind("<Return>", done)
    dlg.after(200, ent.focus_set)
    run_modal(dlg, master, 360)
    return result["v"]
