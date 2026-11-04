# Problem Sheets

Problem-solving records with actions, in one local SQLite file. Styled with **Dave-Standard** (`~/Desktop/Dave-Standard/python_customtkinter`): floating panels, flat icon buttons, dark and light themes. `dave_theme.py`, `icons/` and `icon.png` are copies from there; fix the look in Dave-Standard, then copy the file here.

```
python3 main.py --demo            # sample data in a separate demo database
python3 main.py                   # your data
python3 main.py --theme light     # or dark (default; remembered; sun/moon button in the toolbar)
```

## Install with pipx (from the repo)
```
sudo dnf install pipx python3-tkinter          # once; Tk is not on PyPI
pipx install git+https://github.com/KillGorack/problem-sheets      # or: pipx install /path/to/ProblemSheets
problem-sheets                                  # upgrade: pipx upgrade problem-sheets   remove: pipx uninstall problem-sheets
problem-sheets --install-menu                   # optional: adds it to the applications menu (--remove-menu undoes it)
```
pipx keeps the app in its own private environment, so nothing else on the system is touched; your data (`~/.local/share/problem-sheets`) is never removed. pipx only installs the command, so run `problem-sheets --install-menu` once to add the menu entry (run `--remove-menu` before `pipx uninstall`). The tarball (`packaging/build_linux.sh`) adds one by itself. Tested 2026-11-04 from a local folder into a scratch pipx home, in a brand-new home directory.

## Data
- **Project:** the top-level subject (for example Logistics, Production). Every problem belongs to one. It is the first dropdown on the form, a filter on the Problems list (so a meeting can stay on one project), and the title of every exported PDF. You maintain the list in Settings.
- **Severity levels** are an editable list in Settings (default Low, Medium, High): a name, a hex color (for example #D32F2F), and an order. The color is the severity dot: first column of the Problems list, left of the title on the problem form, and on the PDF sheets. Renaming a level carries over to its problems; a level in use can't be removed.
- **Problem:** title, severity (from that list), category, champion, status (Open or Closed), description, root cause, and any number of pictures. **Created** is set once when the problem is created; **Updated** moves whenever the problem, any of its actions, or its pictures change. Neither is editable. Closing stamps the closed date, and warns if actions are not Verified yet.
- **Action** (any number per problem): the action, who does it, when it is due, completion stage (Planning, Defined, Implemented, Verified). An action is open until Verified.
- **Category** and **Champion** come from lists you maintain in Settings. An entry that is in use can't be removed.
- File: `~/.local/share/problem-sheets/problems.db` (Windows: `%APPDATA%\ProblemSheets`). Each problem also has a folder, `PS-0003`, inside the *problem files folder* you choose in Settings (default: `problems-files` beside the database). The app keeps its pictures in that folder's `pictures` sub-folder; everything else in it is yours (evidence, analyses, spreadsheets). The folder icon on the form opens it in your file manager. The app never reads, changes or deletes your own files, even when you delete the problem. Back up the database file and the files folder together.

## Screens
Problems (shows Open by default; search, Project and Open/Closed/All filters, sortable table) · Problem detail (form, actions, pictures) · Settings (theme, Project / Category / Champion lists, severity levels with colors, problem files folder). Toolbar: new problem, export PDF, settings, theme. Shortcuts: Ctrl+N new, Ctrl+F search, Ctrl+, settings, Ctrl +/-/0 text size, Esc back. Feedback (Saved, errors) appears in the toolbar.

## PDF
Print a problem sheet from its detail screen (details, description, root cause, actions, pictures; no sign-off block); print the Problems list as filtered (for example one project's open problems) with Export PDF. Needs `sudo dnf install python3-reportlab`. The save-PDF and add-pictures dialogs open in the folder you used last time (remembered separately).

## Files
`main.py` app shell and navigation · `views.py` screens · `db.py` storage · `pdf_export.py` PDF output · `dave_theme.py` + `icons/` the look (from Dave-Standard).
