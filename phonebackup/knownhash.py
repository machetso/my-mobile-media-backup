"""Which photos and videos of a backup folder have a SHA-256 on record – without reading them
(user request 2026-11-23: "check in the background whether the logs are complete; if not, offer
to check the folder and hash only the media that have no hash in the logs or elsewhere").

Sources, the first that knows a file wins:
  list     the backup's list (.phonebackup/index.sqlite), newest entry of the place, same size
           (and the same modification time, when the list knows it)
  report   the report CSVs in the backup's Logs folder: exactly one SHA-256 for this place and
           size, and the file is not newer than the report
  checked  .phonebackup/checked.sqlite – files this program read and hashed itself ("Check backup
           folder…"), same size and modification time

A backup folder built inside the backup (<set>/<Owner>/<Phone>/… with its own .phonebackup) is
looked up in ITS list and reports. No Qt here.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .index import INTERNAL_DIR
from .media import category_for

CHECKED = "checked.sqlite"


def is_media(name):
    return category_for(name) is not None


def media_files(set_dir):
    """{rel: (size, mtime)} of the photos and videos in the backup folder – no logs, reports or
    other files of the program."""
    from .reconcile import folder_files
    return {rel: v for rel, v in folder_files(set_dir).items() if is_media(rel.rsplit("/", 1)[-1])}


# ------------------------------------------------------------------------- the sources

def _list_rows(set_dir):
    """{rel: (sha, size, mtime)} – the newest entry per place."""
    p = Path(set_dir) / INTERNAL_DIR / "index.sqlite"
    out = {}
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            for rel, sha, size, mtime in db.execute("SELECT rel_path, sha256, size, mtime FROM files ORDER BY rowid"):
                out[rel] = (sha, size, mtime)
        finally:
            db.close()
    except sqlite3.Error:
        pass
    return out


def _report_rows(set_dir):
    """{rel: [(sha, size, report time)]} from every report CSV of the folder."""
    from .reconcile import log_facts, report_csvs
    out = {}
    for csv_path in report_csvs(set_dir):
        try:
            when = csv_path.stat().st_mtime
        except OSError:
            continue
        for loc, facts in log_facts(set_dir, [csv_path]).items():
            for f in facts:
                out.setdefault(loc, []).append((f.sha, f.size, when))
    return out


def checked_rows(set_dir):
    """{rel: (sha, size, mtime)} hashed by this program itself."""
    p = Path(set_dir) / INTERNAL_DIR / CHECKED
    if not p.is_file():
        return {}
    out = {}
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            for rel, sha, size, mtime in db.execute("SELECT rel_path, sha256, size, mtime FROM checked"):
                out[rel] = (sha, size, mtime)
        finally:
            db.close()
    except sqlite3.Error:
        pass
    return out


def remember(set_dir, rows):
    """Store hashes this program computed: rows = [(rel, sha, size, mtime)]."""
    p = Path(set_dir) / INTERNAL_DIR / CHECKED
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(p))
    try:
        db.execute("CREATE TABLE IF NOT EXISTS checked(rel_path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, "
                   "size INTEGER NOT NULL, mtime INTEGER, checked_at TEXT)")
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        with db:
            db.executemany("INSERT OR REPLACE INTO checked VALUES (?,?,?,?,?)",
                           [(rel, sha, size, int(mtime), now) for rel, sha, size, mtime in rows])
    finally:
        db.close()


def _same_time(a, b):
    return a is not None and b is not None and int(a) == int(b)


# ------------------------------------------------------------------------- all together

def _inner_sets(set_dir):
    """Backup folders inside the backup folder (rel prefix → path), the deepest first."""
    from .findbackup import _sets_inside
    inner = []
    for s in _sets_inside(set_dir, depth=4):
        inner.append((Path(s).relative_to(set_dir).as_posix() + "/", Path(s)))
    return sorted(inner, key=lambda x: -len(x[0]))


def known(set_dir, files=None):
    """{rel: (sha, source)} for the media of the folder whose SHA-256 is on record, and the list
    of those that are not: (known, unknown). files = media_files(set_dir) if already read."""
    set_dir = Path(set_dir)
    files = media_files(set_dir) if files is None else files
    sources = {}

    def src(base):
        key = str(base)
        if key not in sources:
            sources[key] = (_list_rows(base), _report_rows(base))
        return sources[key]
    checked = checked_rows(set_dir)
    inner = _inner_sets(set_dir)
    out, unknown = {}, []
    for rel, (size, mtime) in files.items():
        base, sub = set_dir, rel
        for prefix, path in inner:
            if rel.startswith(prefix):
                base, sub = path, rel[len(prefix):]
                break
        lst, reps = src(base)
        got = lst.get(sub)
        if got and got[1] == size and (got[2] is None or _same_time(got[2], mtime) or not got[2]):
            out[rel] = (got[0], "list")
            continue
        facts = [(sha, when) for sha, sz, when in reps.get(sub, []) if sz == size]
        if facts and len({s for s, _w in facts}) == 1 and mtime <= max(w for _s, w in facts) + 2:
            out[rel] = (facts[0][0], "report")
            continue
        got = checked.get(rel)
        if got and got[1] == size and _same_time(got[2], mtime):
            out[rel] = (got[0], "checked")
            continue
        unknown.append(rel)
    return out, unknown


def check(set_dir, rels, cancel=None, progress=None, batch=50):
    """Read and hash the media `rels` (those with no SHA-256 on record) and remember them.
    progress(done_files, total_files, done_bytes, total_bytes, path). Returns (hashed, errors)."""
    from .copier import HashCancelled, sha256_file
    set_dir = Path(set_dir)
    todo = []
    for rel in rels:
        try:
            st = os.stat(set_dir / rel)
        except OSError:
            continue
        todo.append((rel, st.st_size, st.st_mtime))
    total = sum(s for _r, s, _m in todo)
    done_b, rows, hashed, errors = 0, [], 0, []
    try:
        for i, (rel, size, mtime) in enumerate(todo, 1):
            if cancel is not None and cancel.is_set():
                break
            try:
                sha = sha256_file(set_dir / rel, cancel)
            except HashCancelled:
                break
            except OSError as e:
                errors.append((rel, str(e)))
                continue
            rows.append((rel, sha, size, mtime))
            hashed += 1
            done_b += size
            if progress:
                progress(i, len(todo), done_b, total, str(set_dir / rel))
            if len(rows) >= batch:               # saved as it goes: a cancel keeps what was done
                remember(set_dir, rows)
                rows = []
    finally:
        if rows:
            remember(set_dir, rows)
    return hashed, errors
