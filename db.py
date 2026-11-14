"""SQLite storage for Problem Sheets: problems, their actions, and two maintained pick lists
(categories, people/champions). One local file, no server."""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

DEFAULT_SEVERITIES = (("Low", "#3B82C4"), ("Medium", "#F2B01E"), ("High", "#D32F2F"))   # name, color; low -> high
PROBLEM_STATUSES = ("Open", "Closed")
ACTIVE = ("Open",)
ACTION_STAGES = ("Planning", "Defined", "Implemented", "Verified")   # completion; open until Verified
ACTION_DONE = "Verified"
DEFAULT_CATEGORIES = ("Quality", "Safety", "Process", "Equipment", "Supplier")
NONE = "(none)"
LISTS = ("projects", "categories", "people")   # maintained pick lists
DEFAULT_PROJECT = "General"

SCHEMA = """
CREATE TABLE IF NOT EXISTS severities (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    color TEXT NOT NULL DEFAULT '#888888',
    sort_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS projects   (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                                         meeting_when TEXT NOT NULL DEFAULT '', meeting_where TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS people     (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS subcategories (
    id INTEGER PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    name TEXT NOT NULL COLLATE NOCASE,
    UNIQUE(category_id, name)
);
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    severity_id INTEGER REFERENCES severities(id) ON DELETE RESTRICT,
    severity TEXT NOT NULL DEFAULT 'Medium',   -- legacy, unused: severity_id replaced it
    description TEXT NOT NULL DEFAULT '',
    root_cause TEXT NOT NULL DEFAULT '',
    category_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT,
    subcategory_id INTEGER REFERENCES subcategories(id) ON DELETE RESTRICT,
    champion_id INTEGER REFERENCES people(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'Open',
    reported_date TEXT NOT NULL,     -- legacy, unused: created_at is the creation date
    due_date TEXT NOT NULL DEFAULT '',   -- legacy, unused: due dates live on actions
    closed_date TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    file TEXT NOT NULL,              -- path relative to the pictures folder
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    owner_id INTEGER REFERENCES people(id) ON DELETE RESTRICT,
    due_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Planning',
    done_date TEXT NOT NULL DEFAULT ''
);
"""


NO_CATEGORY = "(no category)"


def protocol_groups(rows: list[dict]) -> list[tuple]:
    """Problems grouped for the Protocol (screen and PDF):
        [(project, [(category, [problems with no sub-category], [(sub-category, [problems])])])]
    Problems without a sub-category sit directly under their category; problems without a category go
    under NO_CATEGORY, last. Names sort alphabetically, problems by number."""
    tree: dict = {}
    for p in rows:
        tree.setdefault(p["project"] or "", {}).setdefault(p["category"] or NO_CATEGORY, {}) \
            .setdefault(p["subcategory"] or "", []).append(p)
    by_id = lambda ps: sorted(ps, key=lambda r: r["id"])            # noqa: E731
    out = []
    for proj in sorted(tree, key=str.lower):
        cats = []
        for cat in sorted(tree[proj], key=lambda c: (c == NO_CATEGORY, c.lower())):
            subs = tree[proj][cat]
            cats.append((cat, by_id(subs.get("", [])),
                         [(sub, by_id(subs[sub])) for sub in sorted((k for k in subs if k), key=str.lower)]))
        out.append((proj, cats))
    return out


class InUse(Exception):
    """A list entry can't be deleted because records still point at it."""


def data_dir() -> Path:
    if sys.platform.startswith("win"):      # local (not roaming) app data: big files, one machine
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ProblemSheets"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "problem-sheets"


def today() -> str:
    return dt.date.today().isoformat()


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def number(pid: int) -> str:
    return f"TS-{pid:04d}"


def valid_date(text: str) -> bool:
    if not text:
        return True
    try:
        dt.date.fromisoformat(text)
        return len(text) == 10
    except ValueError:
        return False


def is_overdue(due: str, open_: bool = True) -> bool:
    return bool(open_ and due and due < today())


class Store:
    def __init__(self, path: Path | str, image_dir: Path | str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if image_dir:
            self.image_dir = Path(image_dir)
        else:
            new, old = self.path.parent / f"{self.path.stem}-files", self.path.parent / f"{self.path.stem}-pictures"
            self.image_dir = old if old.exists() and not new.exists() else new
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        # databases from before Projects: add the column, put everything in the default project
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(problems)")}
        if "project_id" not in cols:
            self.db.execute("ALTER TABLE problems ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE RESTRICT")
        if not self.db.execute("SELECT 1 FROM projects").fetchone():
            self.db.execute("INSERT INTO projects(name) VALUES (?)", (DEFAULT_PROJECT,))
        self.db.execute("UPDATE problems SET project_id=(SELECT MIN(id) FROM projects) WHERE project_id IS NULL")
        # severities became an editable list with colors: seed it, then point old problems at it
        if not self.db.execute("SELECT 1 FROM severities").fetchone():
            self.db.executemany("INSERT INTO severities(name, color, sort_order) VALUES (?,?,?)",
                                [(n, c, i + 1) for i, (n, c) in enumerate(DEFAULT_SEVERITIES)])
        if "severity_id" not in cols:
            self.db.execute("ALTER TABLE problems ADD COLUMN severity_id INTEGER REFERENCES severities(id) ON DELETE RESTRICT")
        self.db.execute("UPDATE problems SET severity_id=(SELECT id FROM severities WHERE name=problems.severity) "
                        "WHERE severity_id IS NULL")
        self.db.execute("UPDATE problems SET severity_id=(SELECT id FROM severities ORDER BY sort_order LIMIT 1 OFFSET 1) "
                        "WHERE severity_id IS NULL")
        # actions got a hand-set order (move up / down); older rows keep their creation order
        if "sort_order" not in {r["name"] for r in self.db.execute("PRAGMA table_info(actions)")}:
            self.db.execute("ALTER TABLE actions ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
            self.db.execute("UPDATE actions SET sort_order=id")
        # projects got a meeting time and place (shown on the Protocol)
        pcols = {r["name"] for r in self.db.execute("PRAGMA table_info(projects)")}
        for col in ("meeting_when", "meeting_where"):
            if col not in pcols:
                self.db.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        # sub-categories came later: add the column, left empty
        if "subcategory_id" not in cols:
            self.db.execute("ALTER TABLE problems ADD COLUMN subcategory_id INTEGER "
                            "REFERENCES subcategories(id) ON DELETE RESTRICT")
        # older databases had four problem statuses; there are two now
        self.db.execute("UPDATE problems SET status='Open' WHERE status='In progress'")
        self.db.execute("UPDATE problems SET status='Closed' WHERE status='Resolved'")
        self._ps_to_ts()
        if not self.db.execute("SELECT 1 FROM categories").fetchone():
            self.db.executemany("INSERT INTO categories(name) VALUES (?)", [(c,) for c in DEFAULT_CATEGORIES])
        self.db.commit()

    def _ps_to_ts(self) -> None:
        """Numbers were PS-0003 (problem sheet), now TS-0003 (topic sheet). Rename the old folders and
        the picture paths that point into them. A folder is only renamed when no TS- folder of that
        number exists yet; anything you put in the folder moves with it, untouched."""
        if self.image_dir.is_dir():
            for old in self.image_dir.iterdir():
                if old.is_dir() and re.fullmatch(r"PS-\d{4,}", old.name):
                    new = old.with_name("TS-" + old.name[3:])
                    if not new.exists():
                        old.rename(new)
        for r in self.db.execute("SELECT id, file FROM images WHERE file LIKE 'PS-%'").fetchall():
            new = "TS-" + r["file"][3:]
            if (self.image_dir / new).exists() or not (self.image_dir / r["file"]).exists():
                self.db.execute("UPDATE images SET file=? WHERE id=?", (new, r["id"]))

    # ---- pick lists --------------------------------------------------
    def items(self, table: str) -> list[dict]:
        assert table in LISTS
        return [dict(r) for r in self.db.execute(f"SELECT id, name FROM {table} ORDER BY name")]

    def add_item(self, table: str, name: str) -> int:
        assert table in LISTS
        cur = self.db.execute(f"INSERT INTO {table}(name) VALUES (?)", (name.strip(),))
        self.db.commit()
        return cur.lastrowid

    def rename_item(self, table: str, item_id: int, name: str) -> None:
        assert table in LISTS
        self.db.execute(f"UPDATE {table} SET name=? WHERE id=?", (name.strip(), item_id))
        self.db.commit()

    def delete_item(self, table: str, item_id: int) -> None:
        assert table in LISTS
        try:
            self.db.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
            self.db.commit()
        except sqlite3.IntegrityError as e:
            self.db.rollback()
            raise InUse() from e

    # ---- projects: name plus where and when the team meets ------------
    def projects(self) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT id, name, meeting_when, meeting_where FROM projects ORDER BY name")]

    def save_project(self, name: str, when: str, where: str, pid: int | None = None) -> int:
        if pid:
            self.db.execute("UPDATE projects SET name=?, meeting_when=?, meeting_where=? WHERE id=?",
                            (name.strip(), when.strip(), where.strip(), pid))
        else:
            pid = self.db.execute("INSERT INTO projects(name, meeting_when, meeting_where) VALUES (?,?,?)",
                                  (name.strip(), when.strip(), where.strip())).lastrowid
        self.db.commit()
        return pid

    # ---- sub-categories (each belongs to one category) ----------------
    def subcategories(self, category_id: int | None = None) -> list[dict]:
        sql, args = ("SELECT s.id, s.category_id, s.name, c.name AS category FROM subcategories s "
                     "JOIN categories c ON c.id = s.category_id"), []
        if category_id is not None:
            sql += " WHERE s.category_id = ?"
            args.append(category_id)
        return [dict(r) for r in self.db.execute(sql + " ORDER BY c.name, s.name", args)]

    def add_subcategory(self, category_id: int, name: str) -> int:
        cur = self.db.execute("INSERT INTO subcategories(category_id, name) VALUES (?,?)", (category_id, name.strip()))
        self.db.commit()
        return cur.lastrowid

    def rename_subcategory(self, sid: int, name: str) -> None:
        self.db.execute("UPDATE subcategories SET name=? WHERE id=?", (name.strip(), sid))
        self.db.commit()

    def delete_subcategory(self, sid: int) -> None:
        try:
            self.db.execute("DELETE FROM subcategories WHERE id=?", (sid,))
            self.db.commit()
        except sqlite3.IntegrityError as e:
            self.db.rollback()
            raise InUse() from e

    # ---- severities (editable, ordered, colored) ---------------------
    @staticmethod
    def clean_color(text: str) -> str | None:
        """'#f00', 'ff0000' or '#FF0000' -> '#FF0000'; None if not a hex color."""
        t = text.strip().lstrip("#")
        if len(t) == 3:
            t = "".join(ch * 2 for ch in t)
        if len(t) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in t):
            return "#" + t.upper()
        return None

    def severities(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT id, name, color, sort_order FROM severities ORDER BY sort_order")]

    def add_severity(self, name: str, color: str) -> int:
        nxt = (self.db.execute("SELECT MAX(sort_order) FROM severities").fetchone()[0] or 0) + 1
        cur = self.db.execute("INSERT INTO severities(name, color, sort_order) VALUES (?,?,?)",
                              (name.strip(), color, nxt))
        self.db.commit()
        return cur.lastrowid

    def update_severity(self, sid: int, name: str, color: str) -> None:
        self.db.execute("UPDATE severities SET name=?, color=? WHERE id=?", (name.strip(), color, sid))
        self.db.commit()

    def move_severity(self, sid: int, direction: int) -> None:
        """direction -1 = earlier in the list (lower), +1 = later (higher severity)."""
        rows = self.severities()
        i = next((k for k, r in enumerate(rows) if r["id"] == sid), None)
        j = None if i is None else i + direction
        if i is None or j < 0 or j >= len(rows):
            return
        a, b = rows[i], rows[j]
        self.db.execute("UPDATE severities SET sort_order=? WHERE id=?", (b["sort_order"], a["id"]))
        self.db.execute("UPDATE severities SET sort_order=? WHERE id=?", (a["sort_order"], b["id"]))
        self.db.commit()

    def delete_severity(self, sid: int) -> None:
        try:
            self.db.execute("DELETE FROM severities WHERE id=?", (sid,))
            self.db.commit()
        except sqlite3.IntegrityError as e:
            self.db.rollback()
            raise InUse() from e

    # ---- problems ----------------------------------------------------
    _PROBLEM_SQL = """
        SELECT p.id, p.project_id, p.title, p.severity_id, p.description, p.root_cause, p.category_id, p.subcategory_id,
               p.champion_id, p.status, p.closed_date, p.created_at, p.updated_at,
               sv.name AS severity, sv.color AS severity_color, sv.sort_order AS severity_rank,
               pr.name AS project, c.name AS category, sc.name AS subcategory, h.name AS champion,
               (SELECT COUNT(*) FROM actions a WHERE a.problem_id = p.id AND a.status <> 'Verified') AS open_actions
        FROM problems p
        LEFT JOIN severities sv ON sv.id = p.severity_id
        LEFT JOIN projects pr ON pr.id = p.project_id
        LEFT JOIN categories c ON c.id = p.category_id
        LEFT JOIN subcategories sc ON sc.id = p.subcategory_id
        LEFT JOIN people h ON h.id = p.champion_id
    """

    def problems(self, search: str = "", statuses: tuple[str, ...] | None = None,
                 project_id: int | None = None) -> list[dict]:
        sql, args = self._PROBLEM_SQL + " WHERE 1=1", []
        if project_id:
            sql += " AND p.project_id = ?"
            args.append(project_id)
        for word in search.split():
            sql += (" AND (p.title LIKE ? OR p.description LIKE ? OR p.root_cause LIKE ?"
                    " OR c.name LIKE ? OR sc.name LIKE ? OR h.name LIKE ? OR pr.name LIKE ?"
                    " OR printf('TS-%04d', p.id) LIKE ?)")
            args += [f"%{word}%"] * 8
        if statuses:
            sql += f" AND p.status IN ({','.join('?' * len(statuses))})"
            args += list(statuses)
        return [dict(r) for r in self.db.execute(sql + " ORDER BY p.id DESC", args)]

    def last_project(self) -> str | None:
        """Project of the most recently created problem (the default for the next new one)."""
        row = self.db.execute("SELECT pr.name FROM problems p JOIN projects pr ON pr.id = p.project_id "
                              "ORDER BY p.id DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def get_problem(self, pid: int) -> dict | None:
        row = self.db.execute(self._PROBLEM_SQL + " WHERE p.id = ?", (pid,)).fetchone()
        return dict(row) if row else None

    def touch(self, pid: int) -> None:
        """Mark a problem as updated now (called for any change to it, its actions or pictures)."""
        self.db.execute("UPDATE problems SET updated_at=? WHERE id=?", (_now(), pid))
        self.db.commit()

    def save_problem(self, d: dict) -> int:
        """Insert (no 'id') or update. created_at is set once; updated_at on every save."""
        cols = ("project_id", "title", "severity_id", "description", "root_cause", "category_id", "subcategory_id",
                "champion_id", "status", "closed_date")
        d = {"subcategory_id": None, **d}
        now = _now()
        if d.get("id"):
            self.db.execute(f"UPDATE problems SET {', '.join(c + '=?' for c in cols)}, updated_at=? WHERE id=?",
                            [d[c] for c in cols] + [now, d["id"]])
            pid = d["id"]
        else:
            cur = self.db.execute(
                f"INSERT INTO problems({', '.join(cols)}, reported_date, due_date, created_at, updated_at) "
                f"VALUES ({','.join('?' * len(cols))}, ?, '', ?, ?)",
                [d[c] for c in cols] + [today(), d.get("created_at", now), d.get("updated_at", now)])
            pid = cur.lastrowid
        self.db.commit()
        return pid

    def delete_problem(self, pid: int) -> None:
        """Delete the record, its actions and the pictures the app attached. The problem's folder
        and any files you put there are never touched (only removed if completely empty)."""
        for img in self.images(pid):
            self._remove_file(img["path"])
        self.db.execute("DELETE FROM problems WHERE id=?", (pid,))
        self.db.commit()
        for folder in (self.problem_dir(pid) / "pictures", self.problem_dir(pid)):
            try:
                folder.rmdir()                 # only succeeds when empty
            except OSError:
                pass

    # ---- pictures ----------------------------------------------------
    IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")

    @staticmethod
    def _remove_file(path: Path) -> None:
        try:
            Path(path).unlink()
        except OSError:
            pass

    def problem_dir(self, pid: int, create: bool = False) -> Path:
        """<files folder>/TS-0003 - yours to fill with evidence, analyses, anything. The app only
        keeps its own pictures in the 'pictures' sub-folder."""
        folder = self.image_dir / number(pid)
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    def user_file_count(self, pid: int) -> int:
        """Files in the problem folder that the app did not put there (for the delete warning)."""
        folder = self.problem_dir(pid)
        if not folder.exists():
            return 0
        managed = {img["path"].resolve() for img in self.images(pid)}
        return sum(1 for f in folder.rglob("*") if f.is_file() and f.resolve() not in managed)

    def images(self, pid: int) -> list[dict]:
        rows = self.db.execute("SELECT * FROM images WHERE problem_id=? ORDER BY id", (pid,))
        return [dict(r, path=self.image_dir / r["file"]) for r in rows]

    def first_images(self) -> dict[int, Path]:
        """problem id -> path of its first picture (for list thumbnails)."""
        rows = self.db.execute("SELECT problem_id, file FROM images WHERE id IN "
                               "(SELECT MIN(id) FROM images GROUP BY problem_id)")
        return {r["problem_id"]: self.image_dir / r["file"] for r in rows}

    def add_image(self, pid: int, source: Path | str) -> int:
        """Copy a picture into <pictures folder>/TS-0003/ and attach it to the problem."""
        source = Path(source)
        folder = self.problem_dir(pid) / "pictures"
        folder.mkdir(parents=True, exist_ok=True)
        target, n = folder / source.name, 1
        while target.exists():
            target = folder / f"{source.stem}-{n}{source.suffix}"
            n += 1
        shutil.copy2(source, target)
        cur = self.db.execute("INSERT INTO images(problem_id, file, added_at) VALUES (?,?,?)",
                              (pid, f"{number(pid)}/pictures/{target.name}", today()))
        self.db.commit()
        self.touch(pid)
        return cur.lastrowid

    def delete_image(self, image_id: int) -> None:
        row = self.db.execute("SELECT file, problem_id FROM images WHERE id=?", (image_id,)).fetchone()
        if row:
            self._remove_file(self.image_dir / row["file"])
        self.db.execute("DELETE FROM images WHERE id=?", (image_id,))
        self.db.commit()
        if row:
            self.touch(row["problem_id"])

    def image_count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM images").fetchone()[0]

    def problem_folders(self) -> list[Path]:
        if not self.image_dir.exists():
            return []
        return sorted(p for p in self.image_dir.iterdir() if p.is_dir() and p.name.startswith("TS-"))

    def set_image_dir(self, new_dir: Path | str, move: bool = True) -> None:
        """Point at a new files folder, moving every problem folder (pictures and your own files)."""
        new_dir = Path(new_dir)
        new_dir.mkdir(parents=True, exist_ok=True)
        if move and new_dir.resolve() != self.image_dir.resolve():
            for folder in self.problem_folders():
                target = new_dir / folder.name
                if target.exists():
                    raise OSError(f"{target} already exists; not overwriting it.")
            for folder in self.problem_folders():
                shutil.move(str(folder), str(new_dir / folder.name))
        self.image_dir = new_dir

    # ---- actions -----------------------------------------------------
    _ACTION_SQL = """
        SELECT a.*, h.name AS owner, p.title AS problem_title, p.severity AS problem_severity,
               p.project_id AS project_id, pr.name AS project
        FROM actions a
        JOIN problems p ON p.id = a.problem_id
        LEFT JOIN projects pr ON pr.id = p.project_id
        LEFT JOIN people h ON h.id = a.owner_id
    """

    def actions(self, pid: int) -> list[dict]:
        rows = self.db.execute(self._ACTION_SQL + " WHERE a.problem_id=? ORDER BY a.sort_order, a.id", (pid,))
        return [dict(r) for r in rows]

    def open_actions(self, project_id: int | None = None) -> list[dict]:
        sql, args = self._ACTION_SQL + " WHERE a.status <> 'Verified'", []
        if project_id:
            sql += " AND p.project_id = ?"
            args.append(project_id)
        return [dict(r) for r in self.db.execute(sql + " ORDER BY a.problem_id, a.sort_order, a.id", args)]

    def save_action(self, d: dict) -> int:
        cols = ("problem_id", "description", "owner_id", "due_date", "status", "done_date")
        if d.get("id"):
            self.db.execute(f"UPDATE actions SET {', '.join(c + '=?' for c in cols)} WHERE id=?",
                            [d[c] for c in cols] + [d["id"]])
            aid = d["id"]
        else:
            nxt = (self.db.execute("SELECT MAX(sort_order) FROM actions WHERE problem_id=?",
                                   (d["problem_id"],)).fetchone()[0] or 0) + 1
            cur = self.db.execute(f"INSERT INTO actions({', '.join(cols)}, sort_order) "
                                  f"VALUES ({','.join('?' * len(cols))}, ?)", [d[c] for c in cols] + [nxt])
            aid = cur.lastrowid
        self.db.commit()
        self.touch(d["problem_id"])
        return aid

    def move_action(self, aid: int, step: int) -> bool:
        """Swap an action with its neighbour above (step -1) or below (+1). False at the end of the list."""
        row = self.db.execute("SELECT problem_id FROM actions WHERE id=?", (aid,)).fetchone()
        if not row:
            return False
        ids = [r["id"] for r in self.db.execute(
            "SELECT id FROM actions WHERE problem_id=? ORDER BY sort_order, id", (row["problem_id"],))]
        i, j = ids.index(aid), ids.index(aid) + step
        if not 0 <= j < len(ids):
            return False
        ids[i], ids[j] = ids[j], ids[i]
        self.db.executemany("UPDATE actions SET sort_order=? WHERE id=?", [(n + 1, x) for n, x in enumerate(ids)])
        self.db.commit()
        self.touch(row["problem_id"])
        return True

    def delete_action(self, aid: int) -> None:
        row = self.db.execute("SELECT problem_id FROM actions WHERE id=?", (aid,)).fetchone()
        self.db.execute("DELETE FROM actions WHERE id=?", (aid,))
        self.db.commit()
        if row:
            self.touch(row["problem_id"])

    # ---- demo data ---------------------------------------------------
    def seed_demo(self) -> None:
        if self.db.execute("SELECT 1 FROM problems").fetchone():
            return
        people = {n: self.add_item("people", n) for n in
                  ("Alex Rivera", "Sam Okafor", "Jordan Lee", "Priya Nair", "Maria Santos", "Tom Becker")}
        sev = {r["name"]: r["id"] for r in self.severities()}
        first = self.items("projects")[0]["id"]
        self.rename_item("projects", first, "Production")
        self.save_project("Production", "Mondays at 10:00", "Room 111", first)
        projects = {"Production": first,
                    "Logistics": self.save_project("Logistics", "Wednesdays at 14:00", "Teams"),
                    "Facilities": self.save_project("Facilities", "Every other Friday at 09:00", "Room 204")}
        cats = {c["name"]: c["id"] for c in self.items("categories")}
        subs = {}
        for cat, names in (("Quality", ("Leak", "Documentation", "Dimensional")),
                           ("Safety", ("Near-miss", "Ergonomics", "PPE")),
                           ("Process", ("Scrap", "Cycle time")),
                           ("Equipment", ("Breakdown", "Preventive maintenance")),
                           ("Supplier", ("Delivery", "Incoming quality"))):
            for n in names:
                subs[(cat, n)] = self.add_subcategory(cats[cat], n)
        d = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()   # noqa: E731
        A, S, J, P, M, T = "Alex Rivera", "Sam Okafor", "Jordan Lee", "Priya Nair", "Maria Santos", "Tom Becker"
        # project, title, severity, category, sub-category ("" = none), champion, status, created (days ago),
        # description, root cause, [(action, who, due in days, stage)]
        rows = [
            ("Production", "Seal leaks on pump housing", "High", "Quality", "Leak", A, "Open", 20,
             "Customers report oil weeping at the pump housing seal after about 200 hours.",
             "Seal compound hardens above 90 C; cure step runs too hot.",
             [("Measure oven temperature profile", S, -8, "Verified"),
              ("Trial lower cure temperature on 20 units", A, -1, "Implemented"),
              ("Update work instruction WI-114", P, 6, "Planning")]),
            ("Production", "Scrap rate up on line 2", "Medium", "Process", "Scrap", A, "Open", 3,
             "Scrap rose from 2% to 5% over two weeks.", "", []),
            ("Production", "Label printer jams on night shift", "Low", "Equipment", "Breakdown", S, "Closed", 45,
             "Printer jams about twice a shift on roll changes.", "Roll core diameter differs between vendors.",
             [("Standardize on 76 mm core rolls", S, -35, "Verified")]),
            ("Production", "Calibration records incomplete", "Low", "Quality", "Documentation", J, "Closed", 90,
             "Six gauges missing 2023 calibration entries.", "Records kept in two places.",
             [("Merge calibration logs", J, -62, "Verified")]),
            ("Production", "Bore diameter drifting on CNC 4", "High", "Quality", "Dimensional", M, "Open", 12,
             "Bore measured 0.03 mm over tolerance on 8 of the last 50 parts.", "",
             [("100% inspect bores until fixed", M, -5, "Implemented"),
              ("Check spindle runout", T, 2, "Defined"),
              ("Review tool-wear offsets", M, 7, "Planning")]),
            ("Production", "Customer complaint: scratched covers", "Medium", "Quality", "", P, "Open", 6,
             "Two customers returned covers with surface scratches.", "",
             [("Inspect packaging line for contact points", P, 3, "Defined"),
              ("Add foam separators to packaging", J, 10, "Planning")]),
            ("Production", "Wrong revision drawing at station 7", "Medium", "Quality", "", J, "Open", 4,
             "Operator was building to revision C; current is D.", "Printed copies not withdrawn after release.",
             [("Withdraw old printed drawings", J, -1, "Verified"),
              ("Switch station 7 to screen-only drawings", S, 14, "Planning")]),
            ("Production", "Changeover takes 90 minutes on press 3", "Low", "Process", "Cycle time", T, "Open", 25,
             "Target changeover is 45 minutes.", "",
             [("Video a changeover and list steps", T, -10, "Verified"),
              ("Move tool prep offline", T, 9, "Defined"),
              ("Add quick clamps to die", S, 20, "Planning")]),
            ("Production", "Operators lifting 25 kg housings", "Medium", "Safety", "Ergonomics", A, "Open", 15,
             "Housings lifted by hand from pallet to fixture, about 60 times per shift.", "",
             [("Request quote for vacuum lifter", A, -3, "Defined"),
              ("Interim: two-person lift rule", A, -12, "Verified")]),
            ("Production", "Hydraulic leak on press 1", "High", "Equipment", "Breakdown", T, "Open", 2,
             "Oil on floor under press 1 each morning.", "", [("Replace main cylinder seals", T, 1, "Planning")]),
            ("Production", "Lubrication schedule missed", "Low", "Equipment", "Preventive maintenance", S, "Open", 30,
             "PM checklist shows 4 missed lubrication tasks in October.", "No backup when the technician is off.",
             [("Assign backup technician", S, -15, "Verified"),
              ("Add PM tasks to the shift board", P, -2, "Implemented")]),
            ("Logistics", "Forklift near-miss at dock 3", "High", "Safety", "Near-miss", J, "Open", 5,
             "Forklift and pedestrian came within a meter at the dock 3 crossing.", "",
             [("Install convex mirror at crossing", J, 5, "Planning"),
              ("Paint pedestrian walkway", M, 12, "Planning")]),
            ("Logistics", "Late deliveries from fastener supplier", "Medium", "Supplier", "Delivery", P, "Open", 30,
             "Three of the last five orders arrived 4+ days late.", "Supplier changed shipping carrier without notice.",
             [("Request delivery plan from supplier", P, -10, "Verified"),
              ("Qualify second source", S, 14, "Defined")]),
            ("Logistics", "Bolts arriving with wrong coating", "Medium", "Supplier", "Incoming quality", P, "Open", 9,
             "Zinc-plated bolts received instead of zinc-flake.", "",
             [("Quarantine affected lots", P, -8, "Verified"),
              ("Raise supplier corrective action request", P, 4, "Defined")]),
            ("Logistics", "Pallets stacked above rack limit", "Low", "Safety", "", M, "Open", 7,
             "Rack labels show 3 high; pallets found 4 high in aisle C.", "",
             [("Remind team at shift meeting", M, -4, "Verified"),
              ("Add height marks on rack uprights", T, 6, "Planning")]),
            ("Logistics", "Stock count differences in aisle B", "Low", "Process", "", J, "Open", 18,
             "Cycle counts off by 2-5% on small parts.", "", [("Re-label bins in aisle B", J, -2, "Defined")]),
            ("Logistics", "Truck waiting times over 2 hours", "Medium", "", "", A, "Open", 11,
             "Drivers report long waits at the gate on Mondays.", "", [("Introduce dock booking slots", A, 15, "Planning")]),
            ("Facilities", "Roof leak above warehouse", "High", "Equipment", "", T, "Open", 8,
             "Water dripping near rack row 12 during rain.", "",
             [("Cover affected racks", T, -7, "Verified"), ("Get roofing contractor quote", M, 3, "Defined")]),
            ("Facilities", "Missing safety glasses at entrance", "Low", "Safety", "PPE", M, "Closed", 40,
             "Visitor glasses dispenser often empty.", "No one owned refilling it.",
             [("Add dispenser to the daily 5S round", M, -30, "Verified")]),
            ("Facilities", "Compressed air leaks", "Medium", "", "", S, "Open", 22,
             "Compressor runs at night with production stopped.", "",
             [("Ultrasonic leak survey", S, -6, "Implemented"), ("Fix tagged leaks", T, 8, "Planning")]),
        ]
        for proj, title, sevname, cat, sub, champ, status, ago, desc, rc, acts in rows:
            created = (dt.date.today() - dt.timedelta(days=ago)).isoformat()
            pid = self.save_problem(dict(project_id=projects[proj], title=title, severity_id=sev[sevname],
                                         description=desc, root_cause=rc, category_id=cats.get(cat),
                                         subcategory_id=subs.get((cat, sub)), champion_id=people[champ],
                                         status=status, closed_date=today() if status == "Closed" else "",
                                         created_at=f"{created}T09:00:00"))
            self._demo_pictures(pid, title)
            for text, owner, due_in, st in acts:
                self.save_action(dict(problem_id=pid, description=text, owner_id=people[owner], due_date=d(due_in),
                                      status=st, done_date=today() if st == ACTION_DONE else ""))
            # make "updated" look lived-in: a few days after creation, never in the future
            upd = min(dt.date.today(), dt.date.fromisoformat(created) + dt.timedelta(days=2 + pid % 5))
            self.db.execute("UPDATE problems SET updated_at=? WHERE id=?", (f"{upd.isoformat()}T16:30:00", pid))
            self.db.commit()

    def _demo_pictures(self, pid: int, title: str) -> None:
        """A few generated placeholder pictures so the demo shows thumbnails."""
        if pid not in (1, 2, 3):
            return
        from PIL import Image, ImageDraw
        import tempfile
        palette = [(120, 140, 160), (160, 130, 110), (110, 150, 130)]
        for n in range(2 if pid == 1 else 1):
            im = Image.new("RGB", (640, 420), palette[(pid + n) % 3])
            d = ImageDraw.Draw(im)
            for k in range(0, 640, 40):
                d.line([(k, 0), (k - 200, 420)], fill=(255, 255, 255), width=2)
            d.rectangle((20, 20, 620, 400), outline=(30, 30, 30), width=4)
            d.text((40, 40), f"{number(pid)} photo {n + 1}\n{title}", fill=(20, 20, 20))
            tmp = Path(tempfile.mkdtemp()) / f"demo-{pid}-{n + 1}.png"
            im.save(tmp)
            self.add_image(pid, tmp)
