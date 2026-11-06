# Changelog

## 1.2.0 - 2026-11-06  (tidy-up)
- Actions: reorder with the arrows in each row (order shows in the sheet and the PDF, new `#` column); double-click
  edits and sets the stage; Delete lives in the action form; date picker on the due date; Edit / Next stage / Remove buttons gone.
- A + by the card title replaces the Add buttons (Actions, Pictures, Problems, and every Settings list).
- Settings rearranged; Projects, Categories, People and Severity levels edit in place with a pencil and trash can per row.
- Fixed: a bad date pushed the action form's buttons out of the window.
- Existing databases upgrade themselves (actions get a sort order); data is untouched.

## 1.1.1 - 2026-11-04
- `problem-sheets --install-menu` adds an applications-menu entry for pip/pipx installs (`--remove-menu` undoes it).
- README: pipx install command with the repo address.

## 1.1.0 - 2026-11-04  (restyle)
- "What is to be done" is now just "Actions" (list, dialog, PDF). The PDF no longer prints "PROBLEM SHEET".
- Save PDF and Add pictures dialogs remember the last folder (separately).
- Restyled with Dave-Standard (replaces the Design_Requirements kit): floating panels, flat icon toolbar, dark (default) and light themes.
- Feedback now shows in the toolbar note instead of pop-up toasts; no status bar.
- Toolbar and shortcuts: Ctrl+N, Ctrl+F, Ctrl+, (settings), Ctrl +/-/0 (text size, remembered), Esc (back).
- App moved to its own folder (`~/Documents/Python/ProblemSheets`). Data and database are unchanged.
- Old themes map to the new ones (corporate becomes light, dave-web becomes dark).

## 1.0.0 - 2026-11-03  (first release)
- Problem records with Project, severity (editable levels with hex colors and a dot), category and champion (maintained lists), status Open/Closed, description, root cause, created/updated dates.
- Actions per problem: what, who, due, completion stage (Planning, Defined, Implemented, Verified).
- Pictures per problem; a folder per problem (`PS-0003`) for your own evidence files, opened with one click.
- Problems list: search, Project and Open/Closed/All filters, sortable, Export PDF of the list as filtered.
- PDF problem sheet (with pictures) and PDF problem list; the Project is the title on every sheet.
- Settings: theme (corporate / dave-web), Project/Category/Champion lists, severity levels, problem files folder.
- Local SQLite file; older databases are migrated automatically.
