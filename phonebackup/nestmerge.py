"""A backup folder INSIDE the backup folder is merged into it (user request 2026-11-23).

How it happened: on 2026-11-22 a new folder structure <set>/<Owner>/<Phone>/… (with its own list
.phonebackup and its own Logs) was built inside the existing backup folder <set>. It holds mostly
copies of files the backup already has, but also files that exist ONLY there.

plan()  read-only – per file of the inner backup:
          DUPLICATE  the same content (SHA-256) is already in the outer backup
          MOVE       not there: it goes to the same place in the outer backup
          RENAME     another file with that name is already at that place: it goes there as _1
        The SHA-256 comes from the lists / reports / earlier checks (knownhash) – a file whose
        SHA-256 is not on record is read.
merge() carries the plan out:
          MOVE / RENAME  os.rename (same drive: instant, nothing copied)
          DUPLICATE      the inner copy is MOVED into a review folder (both unchanged since the
                         plan compared their SHA-256: not read again; else read completely)
                         "Duplicates <date>" beside the backup folder – nothing is deleted
          its list       entries of moved files are taken into the outer list (new place); entries
                         of duplicates point to the copy that stays; the inner list itself is kept
                         in the review folder
          its Logs       its reports go into the outer Logs folder
          old entries    entries of the outer list for a report/log file that is nowhere any more
                         are removed (they are not photos or videos)
        Everything is written into a manifest in the review folder – undo() puts it all back.
No Qt here.
"""

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import knownhash
from .copier import HashCancelled, sha256_file
from .index import INTERNAL_DIR
from .report import LOGS_DIR

DUPLICATE, MOVE, RENAME = "duplicate", "move", "rename"
MANIFEST = ".msmb-merge.json"
REVIEW_PREFIX = "Duplicates "


@dataclass
class Item:
    rel: str               # place inside the inner backup
    size: int
    action: str
    target: str = ""       # place in the outer backup (MOVE / RENAME) or the copy that stays (DUPLICATE)
    sha: str = ""
    sha_from: str = ""     # "list" / "report" / "checked" / "read"


@dataclass
class Plan:
    outer: str
    inner: str
    items: list = field(default_factory=list)
    logs: list = field(default_factory=list)          # report files of the inner backup → outer Logs
    stale: list = field(default_factory=list)         # outer list places (not media) whose file is gone
    cancelled: bool = False
    made: float = 0.0                                 # when the plan was made (time.time())

    def count(self, action):
        return sum(1 for i in self.items if i.action == action)

    def size(self, action):
        return sum(i.size for i in self.items if i.action == action)


def inner_sets(set_dir):
    """Backup folders inside the backup folder (the outermost of them first)."""
    return [p for _prefix, p in sorted(knownhash._inner_sets(set_dir), key=lambda x: len(x[0]))]


def _files(root):
    """{rel: (size, mtime)} of every file below root, without its .phonebackup, Logs, review
    folders and the program's own reports at its top level."""
    from .reconcile import folder_files
    return folder_files(root)


def _report_files(inner):
    out = []
    logs = Path(inner) / LOGS_DIR
    if logs.is_dir():
        out += [p for p in sorted(logs.iterdir()) if p.is_file()]
    out += [p for p in sorted(Path(inner).iterdir()) if p.is_file() and p.name.startswith(("Backup ", "Import "))
            and p.suffix.lower() in (".txt", ".html", ".csv")]
    return out


def _sha(path, size, known, cancel):
    if known:
        return known
    return sha256_file(path, cancel), "read"


def plan(outer, inner=None, cancel=None, progress=None):
    """What merge() would do (read-only)."""
    outer = Path(outer)
    inner = Path(inner) if inner else inner_sets(outer)[0]
    prefix = inner.relative_to(outer).as_posix() + "/"
    import time
    p = Plan(str(outer), str(inner), made=time.time())
    # the outer backup's content without the inner one: SHA-256 → place
    outer_files = {r: v for r, v in _files(outer).items() if not r.startswith(prefix)}
    outer_known, _unknown = knownhash.known(outer, {r: v for r, v in outer_files.items()
                                                     if knownhash.is_media(r.rsplit("/", 1)[-1])})
    by_sha = {}
    for r, (sha, _src) in outer_known.items():
        by_sha.setdefault(sha, r)
    inner_files = _files(inner)
    inner_known, _u = knownhash.known(inner, {r: v for r, v in inner_files.items()
                                              if knownhash.is_media(r.rsplit("/", 1)[-1])})
    total = len(inner_files)
    for n, (rel, (size, _mtime)) in enumerate(sorted(inner_files.items()), 1):
        if cancel is not None and cancel.is_set():
            p.cancelled = True
            return p
        try:
            sha, src = _sha(inner / rel, size, inner_known.get(rel), cancel)
        except HashCancelled:
            p.cancelled = True
            return p
        except OSError:
            continue
        keep = by_sha.get(sha)
        if keep is None and rel in outer_files and outer_files[rel][0] == size:
            # same place and size in the outer backup, its SHA-256 not on record: read it
            try:
                if sha256_file(outer / rel, cancel) == sha:
                    keep = rel
            except (OSError, HashCancelled):
                pass
        if keep is not None:
            p.items.append(Item(rel, size, DUPLICATE, keep, sha, src))
        elif rel in outer_files or (outer / rel).exists():
            p.items.append(Item(rel, size, RENAME, "", sha, src))
        else:
            p.items.append(Item(rel, size, MOVE, rel, sha, src))
        if progress:
            progress(n, total, 0, 0, str(inner / rel))
    p.logs = [str(x) for x in _report_files(inner)]
    rows = knownhash._list_rows(outer)
    p.stale = sorted(r for r in rows if not r.startswith(prefix) and not knownhash.is_media(r.rsplit("/", 1)[-1])
                     and not (outer / r).exists())
    return p


# ------------------------------------------------------------------------------- carrying it out

@dataclass
class Merged:
    review_dir: str = ""
    moved: int = 0
    duplicates: int = 0
    skipped: list = field(default_factory=list)      # [(rel, why)]
    cancelled: bool = False


def _review_dir(outer, when):
    base = Path(outer).parent                         # beside the backup folder, never inside it
    name = f"{REVIEW_PREFIX}{when:%Y-%m-%d %H-%M}"
    d, n = base / name, 1
    while d.exists():
        n += 1
        d = base / f"{name} ({n})"
    return d


def _unique(path):
    from .layout import unique_path
    return unique_path(path)


def _rows(db, rel):
    cols = [r[1] for r in db.execute("PRAGMA table_info(files)")]
    return cols, [dict(zip(cols, r)) for r in
                  db.execute(f"SELECT {', '.join(cols)} FROM files WHERE rel_path=? ORDER BY rowid", (rel,))]


def merge(p, cancel=None, progress=None, when=None):
    """Carry out a plan. Every step goes into the manifest (undo())."""
    when = when or datetime.now()
    outer, inner = Path(p.outer), Path(p.inner)
    out = Merged()
    review = _review_dir(outer, when)
    review.mkdir(parents=True)
    out.review_dir = str(review)
    man = {"outer": str(outer), "inner": str(inner), "when": when.isoformat(timespec="seconds"),
           "files": [], "rows_added": [], "rows_removed": [], "logs": [], "inner_list": ""}

    def save_manifest():
        tmp = review / (MANIFEST + ".tmp")
        tmp.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, review / MANIFEST)
    save_manifest()
    cache = {}
    outer_db = sqlite3.connect(str(outer / INTERNAL_DIR / "index.sqlite"))
    inner_db_path = inner / INTERNAL_DIR / "index.sqlite"
    inner_db = sqlite3.connect(f"file:{inner_db_path}?mode=ro", uri=True) if inner_db_path.is_file() else None
    total = sum(i.size for i in p.items)
    done = 0
    try:
        for n, it in enumerate(p.items, 1):
            if cancel is not None and cancel.is_set():
                out.cancelled = True
                break
            src = inner / it.rel
            done += it.size
            try:
                st = src.stat()
            except OSError:
                out.skipped.append((it.rel, "gone"))
                continue
            if st.st_size != it.size:
                out.skipped.append((it.rel, "changed since the plan"))
                continue
            if it.action == DUPLICATE:
                keep = outer / it.target
                try:
                    if _unchanged_since(keep, it.size, p.made) and _unchanged_since(src, it.size, p.made):
                        # the plan compared their SHA-256 on record and neither changed since: no
                        # reading (user 2026-11-23: it took ages). They only go into the review
                        # folder – nothing is deleted, "Put back" undoes it.
                        keep_sha = dup_sha = it.sha
                    else:
                        keep_sha = _listed(outer, it.target, cache) or sha256_file(keep, cancel)
                        dup_sha = _listed(inner, it.rel, cache) or sha256_file(src, cancel)
                except HashCancelled:
                    out.cancelled = True
                    break
                except OSError as e:
                    out.skipped.append((it.rel, str(e)))
                    continue
                if keep_sha != dup_sha:
                    out.skipped.append((it.rel, "not identical after all – left where it is"))
                    continue
                dst = review / inner.relative_to(outer.parent) / it.rel
                new_rel = it.target                     # the list entries point to the copy that stays
            else:
                dst = outer / it.rel
                if dst.exists():
                    dst = _unique(dst)
                new_rel = dst.relative_to(outer).as_posix()
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.rename(src, dst)
            except OSError as e:
                out.skipped.append((it.rel, str(e)))
                continue
            man["files"].append({"from": str(src), "to": str(dst), "action": it.action})
            if it.action == DUPLICATE:
                out.duplicates += 1
            else:
                out.moved += 1
            if inner_db is not None:                    # its list entries into the outer list
                _cols, rows = _rows(inner_db, it.rel)
                with outer_db:
                    for r in rows:
                        old = outer_db.execute("SELECT * FROM files WHERE source_path=? AND size=?",
                                               (r["source_path"], r["size"])).fetchone()
                        if old is not None and it.action == DUPLICATE:
                            continue                    # the outer list knows this phone file already
                        r = dict(r, rel_path=new_rel)
                        if old is not None:
                            man["rows_removed"].append(list(old))
                        outer_db.execute("INSERT OR REPLACE INTO files VALUES (%s)" % ",".join("?" * len(r)),
                                         list(r.values()))
                        man["rows_added"].append([r["source_path"], r["size"], new_rel])
            if progress:
                progress(n, len(p.items), done, total, str(src))
            if n % 50 == 0:
                save_manifest()
        if not out.cancelled:
            logs = outer / LOGS_DIR                     # its reports into the outer Logs
            logs.mkdir(exist_ok=True)
            for f in p.logs:
                f = Path(f)
                if not f.is_file():
                    continue
                dst = _unique(logs / f.name)
                os.rename(f, dst)
                man["logs"].append({"from": str(f), "to": str(dst)})
            with outer_db:                              # old entries of reports that are nowhere
                for rel in p.stale:
                    for row in outer_db.execute("SELECT * FROM files WHERE rel_path=?", (rel,)).fetchall():
                        man["rows_removed"].append(list(row))
                    outer_db.execute("DELETE FROM files WHERE rel_path=?", (rel,))
            if inner_db is not None:
                inner_db.close()
                inner_db = None
            keep_list = review / "list of the inner backup"
            if (inner / INTERNAL_DIR).is_dir():
                os.rename(inner / INTERNAL_DIR, keep_list)
                man["inner_list"] = str(keep_list)
            for dirpath, _d, _f in sorted(os.walk(inner.parent), reverse=True):   # empty folders
                try:
                    os.rmdir(dirpath)
                except OSError:
                    pass
    finally:
        if inner_db is not None:
            inner_db.close()
        outer_db.close()
        save_manifest()
    return out


def _unchanged_since(path, size, when):
    try:
        st = os.stat(path)
    except OSError:
        return False
    return st.st_size == size and st.st_mtime <= when + 1


def _listed(set_dir, rel, cache):
    """SHA-256 from the list when the file is unchanged since its backup, else ""."""
    from .dedupe import Entry, _listed_sha
    try:
        st = os.stat(Path(set_dir) / rel)
    except OSError:
        return ""
    return _listed_sha(Entry(str(Path(set_dir) / rel), st.st_size, st.st_mtime, str(set_dir)), cache)


def undo(review_dir):
    """Put everything of a merge back (only where the place is free). Returns (back, skipped)."""
    review_dir = Path(review_dir)
    man = json.loads((review_dir / MANIFEST).read_text(encoding="utf-8"))
    outer, inner = Path(man["outer"]), Path(man["inner"])
    back, skipped = 0, []
    if man.get("inner_list") and Path(man["inner_list"]).is_dir() and not (inner / INTERNAL_DIR).exists():
        inner.mkdir(parents=True, exist_ok=True)
        os.rename(man["inner_list"], inner / INTERNAL_DIR)
    for f in reversed(man["logs"] + man["files"]):
        src, dst = Path(f["to"]), Path(f["from"])
        if not src.exists() or dst.exists():
            skipped.append(str(src))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.rename(src, dst)
        back += 1
    db = sqlite3.connect(str(outer / INTERNAL_DIR / "index.sqlite"))
    try:
        with db:
            for source_path, size, rel in man["rows_added"]:
                db.execute("DELETE FROM files WHERE source_path=? AND size=? AND rel_path=?", (source_path, size, rel))
            for row in man["rows_removed"]:
                db.execute("INSERT OR REPLACE INTO files VALUES (%s)" % ",".join("?" * len(row)), row)
    finally:
        db.close()
    return back, skipped
