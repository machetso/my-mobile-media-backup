"""Find duplicate files in a folder and its subfolders, and clean them up WITHOUT deleting anything
(user request 2026-11-22: a backup got many double files when a new folder structure was built
inside the old one). No Qt here.

Method
  1. scan(): every file below the chosen folder (not the program's own data: .phonebackup, Logs,
     earlier review folders). Only files of the SAME SIZE can be duplicates. Their SHA-256 is
     taken, without reading the file, from (user 2026-11-23: reading 114 GB per drive took hours)
       a) its backup list (index), if the file is unchanged since then (same size and time) –
          it was checked with SHA-256 when it was written;
       b) else the reports in its backup's Logs folder, if they name exactly one SHA-256 for
          this place and size and the file is not newer than the report.
     Only where a file of a size group is not known this way, a fingerprint (the first and the
     last 64 KB) of the whole group is read. Same SHA-256 / same fingerprint = probably
     duplicates; different = surely different. Same name with DIFFERENT content is only listed.
  2. In each group one copy is kept, by rules (the user can change it before moving):
     the copy in a backup's list (index) → the copy in the outermost backup folder (not in a
     structure built inside another one) → the copy in the program's YYYY/YY.MM structure →
     the shorter path → the older file.
  3. move(): right before each move both SHA-256 are confirmed and must be identical – only true
     copies are moved. Each one comes from its backup list when the file is still unchanged since
     its backup (a), else the file is read COMPLETELY; a SHA-256 from a report (b) alone is never
     enough to move something. They go into a review folder "Duplicates <date>" OUTSIDE the
     backup folders (so no backup, comparison or secure backup ever sees them), with their
     original subfolders. On the same drive this is a rename: instant, no extra space.
     A report (txt/html/csv) and a manifest (for "Put back") lie in the review folder.
     A backup list (index) that names a moved file is pointed to the kept copy (same backup
     folder) or the entry is removed; each change is recorded so that put_back() undoes it.
  4. put_back(): every file back to its place (only if the place is free) + index changes undone.
  The user deletes the review folder after checking it.
"""

import json
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .copier import HashCancelled, sha256_file
from .i18n import N_, tr
from .index import INTERNAL_DIR
from .report import LOGS_DIR

REVIEW_PREFIX = "Duplicates "
MANIFEST = ".msmb-duplicates.json"     # marks a review folder; holds what was moved (Put back)
_STRUCTURE = re.compile(r"^(19|20)\d\d/(raw/)?\d\d\.\d\d(/|-)")


def is_review_dir(path):
    """A review folder of the duplicate clean-up or of a merge (nestmerge)."""
    return any((Path(path) / m).is_file() for m in (MANIFEST, ".msmb-merge.json", ".msmb-regroup"))


@dataclass
class Entry:
    path: str
    size: int
    mtime: float
    set_dir: str = ""          # the backup folder (with index) the file is in, "" none
    depth: int = 0             # how many backup folders it is inside (2 = a backup inside a backup)
    indexed: bool = False      # named in that backup's list
    sha: str = ""              # SHA-256 already known (user 2026-11-23: no reading needed) …
    sha_from: str = ""         # … from "list" (its backup list, file unchanged) or "report" (Logs)


@dataclass
class Group:
    sha: str                   # SHA-256 – "" until move() read it (the scan reads fingerprints only)
    size: int
    entries: list              # [Entry], entries[keep] is kept
    keep: int = 0
    fp: str = ""               # fingerprint (size + first and last 64 KB)

    @property
    def extra(self):
        return [e for i, e in enumerate(self.entries) if i != self.keep]


@dataclass
class ScanResult:
    root: str
    groups: list = field(default_factory=list)       # [Group]
    same_name: list = field(default_factory=list)    # [(name, [Entry])] same name, other content
    files: int = 0
    bytes: int = 0
    hashed: int = 0            # fingerprints read
    known: int = 0             # SHA-256 taken from backup lists / reports (not read)
    unchecked: int = 0         # scan(read=False): files of the same size whose SHA-256 is not on record
    errors: list = field(default_factory=list)
    cancelled: bool = False

    @property
    def duplicates(self):
        return sum(len(g.entries) - 1 for g in self.groups)

    @property
    def duplicate_bytes(self):
        return sum(g.size * (len(g.entries) - 1) for g in self.groups)


def _sets_above(path, memo):
    """Backup folders (with index) that contain `path`, the outermost first. memo: {dir: bool}."""
    out = []
    p = Path(path).parent
    for d in reversed([p] + list(p.parents)):
        key = str(d)
        if key not in memo:
            memo[key] = (d / INTERNAL_DIR / "index.sqlite").is_file()
        if memo[key]:
            out.append(d)
    return out


def _indexed(set_dir, cache):
    """rel_paths named in a backup folder's list (cached per folder)."""
    key = str(set_dir)
    if key not in cache:
        rels = set()
        try:
            db = sqlite3.connect(f"file:{Path(set_dir) / INTERNAL_DIR / 'index.sqlite'}?mode=ro", uri=True)
            try:
                rels = {r[0] for r in db.execute("SELECT rel_path FROM files")}
            finally:
                db.close()
        except sqlite3.Error:
            pass
        cache[key] = rels
    return cache[key]


CHUNK = 64 * 1024


def fingerprint(path, size):
    """SHA-256 of the size, the first and the last 64 KB (a small file: all of it)."""
    import hashlib
    h = hashlib.sha256(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(CHUNK))
        if size > 2 * CHUNK:
            f.seek(size - CHUNK)
        h.update(f.read(CHUNK))
    return h.hexdigest()


def _read_cost(size):
    return min(size, 2 * CHUNK)


def _listed_sha(e, cache):
    """The SHA-256 its backup list names for this file – only if the file is unchanged since that
    backup (same size and modification time). "" otherwise."""
    if not e.set_dir:
        return ""
    key = ("sha", e.set_dir)
    if key not in cache:
        rows = {}
        try:
            db = sqlite3.connect(f"file:{Path(e.set_dir) / INTERNAL_DIR / 'index.sqlite'}?mode=ro", uri=True)
            try:
                for rel, sha, size, mtime in db.execute(
                        "SELECT rel_path, sha256, size, mtime FROM files ORDER BY rowid"):
                    rows[rel] = (sha, size, mtime)
            finally:
                db.close()
        except sqlite3.Error:
            pass
        cache[key] = rows
    rel = os.path.relpath(e.path, e.set_dir).replace(os.sep, "/")
    got = cache[key].get(rel)
    if not got:
        return ""
    sha, size, mtime = got
    try:
        st = os.stat(e.path)
    except OSError:
        return ""
    if st.st_size == size == e.size and mtime and int(st.st_mtime) == int(mtime):
        return sha
    return ""


def _report_sha(e, cache):
    """The SHA-256 the reports in its backup's Logs folder name for this place – only if they name
    exactly one for this size and the file is not newer than the newest such report. "" else."""
    if not e.set_dir:
        return ""
    from .reconcile import log_facts, report_csvs
    key = ("reports", e.set_dir)
    if key not in cache:
        by_loc = {}
        for csv_path in report_csvs(e.set_dir):
            try:
                when = csv_path.stat().st_mtime
            except OSError:
                continue
            for loc, facts in log_facts(e.set_dir, [csv_path]).items():
                for f in facts:
                    by_loc.setdefault(loc, []).append((f.sha, f.size, when))
        cache[key] = by_loc
    rel = os.path.relpath(e.path, e.set_dir).replace(os.sep, "/")
    got = [(sha, when) for sha, size, when in cache[key].get(rel, []) if size == e.size]
    shas = {sha for sha, _w in got}
    if len(shas) != 1 or e.mtime > max(w for _s, w in got) + 2:
        return ""
    return shas.pop()


def known_sha(e, cache):
    """(sha, source) of a file without reading it: its backup list, else its backup's reports."""
    sha = _listed_sha(e, cache)
    if sha:
        return sha, "list"
    sha = _report_sha(e, cache)
    return (sha, "report") if sha else ("", "")


def _walk(root, cancel=None):
    """[(path, size, mtime)] below root, without the program's data and review folders."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        if cancel is not None and cancel.is_set():
            break
        keep = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            if d.startswith(".") or d == LOGS_DIR or d.startswith("$") or is_review_dir(full):
                continue
            keep.append(d)
        dirnames[:] = sorted(keep)
        for fn in filenames:
            if fn.startswith("."):
                continue
            full = os.path.join(dirpath, fn)
            try:
                st = os.stat(full, follow_symlinks=False)
            except OSError:
                continue
            if not os.path.isfile(full) or os.path.islink(full) or st.st_size == 0:
                continue
            out.append((full, st.st_size, st.st_mtime))
    return out


def _rank(e):
    """Lower = kept first (see the module text)."""
    rel = os.path.relpath(e.path, e.set_dir).replace(os.sep, "/") if e.set_dir else ""
    return (0 if e.indexed else 1, e.depth if e.depth else 99, 0 if _STRUCTURE.match(rel) else 1,
            len(Path(e.path).parts), len(e.path), e.mtime, e.path)


def choose_keep(group):
    group.keep = min(range(len(group.entries)), key=lambda i: _rank(group.entries[i]))
    return group.keep


def scan(root, cancel=None, progress=None, read=True):
    """Find duplicates below `root` (read-only). progress(files_done, files_total, bytes_done,
    bytes_total, path) is called while reading."""
    root = str(Path(root))
    res = ScanResult(root)
    files = _walk(root, cancel)
    res.files = len(files)
    res.bytes = sum(s for _p, s, _m in files)
    by_size = defaultdict(list)
    for f in files:
        by_size[f[1]].append(f)
    cache, memo = {}, {}

    def entry(path, size, mtime):
        sets = _sets_above(path, memo)
        e = Entry(path, size, mtime, str(sets[-1]) if sets else "", len(sets))
        if e.set_dir:
            rel = os.path.relpath(path, e.set_dir).replace(os.sep, "/")
            e.indexed = rel in _indexed(e.set_dir, cache)
            e.sha, e.sha_from = known_sha(e, cache)
        return e
    # every file of the same size as another one; its SHA-256 from the backup list / the reports
    # when they know it (user 2026-11-23) – only the others are read (fingerprint)
    groups_by_size = [[entry(*f) for f in sorted(lst)] for lst in by_size.values() if len(lst) > 1]
    res.known = sum(1 for g in groups_by_size for e in g if e.sha)
    need = [any(not e.sha for e in g) for g in groups_by_size]
    total = sum(_read_cost(e.size) for g, n in zip(groups_by_size, need) if n for e in g)
    done, n_need = 0, sum(len(g) for g, n in zip(groups_by_size, need) if n)
    hashes_of = {}
    for g, unknown in zip(groups_by_size, need):
        if res.cancelled:
            break
        keyed = defaultdict(list)
        if unknown and not read:            # quick check (read=False): only what is on record –
            res.unchecked += sum(1 for e in g if not e.sha)     # the others are still compared
            g = [e for e in g if e.sha]
            unknown = False
        if unknown:                         # someone unknown: compare everyone by fingerprint
            for e in g:
                if cancel is not None and cancel.is_set():
                    res.cancelled = True
                    break
                try:
                    fp = fingerprint(e.path, e.size)
                except OSError as err:
                    res.errors.append(f"{e.path}: {err}")
                    continue
                res.hashed += 1
                done += _read_cost(e.size)
                keyed[fp].append(e)
                if progress:
                    progress(res.hashed, n_need, done, total, e.path)
            for fp, lst in keyed.items():
                known = {e.sha for e in lst if e.sha}
                if len(known) <= 1:          # one content as far as anyone knows
                    parts = {"": lst}
                else:                        # known SHA-256 that differ are never duplicates
                    parts = defaultdict(list)
                    for e in lst:
                        parts[e.sha].append(e)   # unknown ones ("") stay together, checked in move()
                for sha, part in parts.items():
                    for e in part:
                        hashes_of[e.path] = f"{fp}:{sha}"
                    if len(part) > 1:
                        whole = {e.sha for e in part}
                        grp = Group(whole.pop() if len(whole) == 1 else "", part[0].size, part, fp=fp)
                        choose_keep(grp)
                        res.groups.append(grp)
        else:                               # everyone known: nothing is read
            for e in g:
                keyed[e.sha].append(e)
            for sha, lst in keyed.items():
                for e in lst:
                    hashes_of[e.path] = sha
                if len(lst) > 1:
                    grp = Group(sha, lst[0].size, lst)
                    choose_keep(grp)
                    res.groups.append(grp)
    res.groups.sort(key=lambda g: (-g.size * (len(g.entries) - 1), g.entries[g.keep].path))
    # same name, different content: only listed. A file that was not read (unique size) has
    # other content than every other file anyway.
    by_name = defaultdict(list)
    for path, size, mtime in files:
        by_name[os.path.basename(path).lower()].append((path, size, mtime))
    for name, lst in sorted(by_name.items()):
        if len(lst) < 2:
            continue
        contents = {hashes_of.get(p) or f"size:{s}:{p}" for p, s, _m in lst}
        if len(contents) > 1:
            res.same_name.append((os.path.basename(lst[0][0]), [Entry(p, s, m) for p, s, m in sorted(lst)]))
    return res


# ----------------------------------------------------------------------------------- moving

def review_base(root):
    """Where the review folder goes: next to the OUTERMOST backup folder that contains `root` (or
    `root` itself), else into `root` – never inside a backup folder."""
    root = Path(root)
    sets = [d for d in [root] + list(root.parents) if (d / INTERNAL_DIR / "index.sqlite").is_file()]
    return sets[-1].parent if sets else root


def _new_review_dir(base, when):
    for name in (f"{REVIEW_PREFIX}{when:%Y-%m-%d}", f"{REVIEW_PREFIX}{when:%Y-%m-%d %H-%M}",
                 f"{REVIEW_PREFIX}{when:%Y-%m-%d %H-%M-%S}"):
        p = Path(base) / name
        if not p.exists():
            return p
    i = 2
    while (Path(base) / f"{REVIEW_PREFIX}{when:%Y-%m-%d %H-%M-%S} ({i})").exists():
        i += 1
    return Path(base) / f"{REVIEW_PREFIX}{when:%Y-%m-%d %H-%M-%S} ({i})"


def _fix_index(dup, keep, log):
    """The backup list of the moved file `dup`: point it to the kept copy (same backup folder) or
    remove the entry. Every change goes into `log` (for put_back)."""
    if not dup.set_dir:
        return
    db_path = Path(dup.set_dir) / INTERNAL_DIR / "index.sqlite"
    rel = os.path.relpath(dup.path, dup.set_dir).replace(os.sep, "/")
    same = keep.set_dir == dup.set_dir
    new_rel = os.path.relpath(keep.path, keep.set_dir).replace(os.sep, "/") if same else None
    db = sqlite3.connect(str(db_path))
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(files)")]
        rows = db.execute(f"SELECT {', '.join(cols)} FROM files WHERE rel_path = ?", (rel,)).fetchall()
        if not rows:
            return
        with db:
            for row in rows:
                d = dict(zip(cols, row))
                if same:
                    db.execute("UPDATE files SET rel_path = ? WHERE source_path = ? AND size = ?",
                               (new_rel, d["source_path"], d["size"]))
                    log.append({"db": str(db_path), "op": "update", "source_path": d["source_path"],
                                "size": d["size"], "old": rel, "new": new_rel})
                else:
                    db.execute("DELETE FROM files WHERE source_path = ? AND size = ?",
                               (d["source_path"], d["size"]))
                    log.append({"db": str(db_path), "op": "delete", "row": d})
    finally:
        db.close()


@dataclass
class MoveResult:
    review_dir: str = ""
    moved: int = 0
    bytes: int = 0
    skipped: list = field(default_factory=list)      # [(path, reason)]
    reports: list = field(default_factory=list)
    cancelled: bool = False


def move(result, cancel=None, progress=None, when=None):
    """Move the duplicates of a ScanResult (all but each group's kept copy) into a new review
    folder. Every pair is read again first; nothing is deleted or overwritten."""
    when = when or datetime.now()
    out = MoveResult()
    root = Path(result.root)
    base = review_base(root)
    review = _new_review_dir(base, when)
    review.mkdir(parents=True)
    out.review_dir = str(review)
    manifest = {"root": str(root), "base": str(base), "when": when.isoformat(timespec="seconds"),
                "moved": [], "index": []}

    def save_manifest():
        tmp = review / (MANIFEST + ".tmp")
        tmp.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, review / MANIFEST)
    save_manifest()
    rows = []
    total = sum(g.size * len(g.extra) for g in result.groups)
    done = 0
    cache = {}
    try:
        for g in result.groups:
            if cancel is not None and cancel.is_set():
                out.cancelled = True
                break
            keep = g.entries[g.keep]
            keep_sha = ""
            try:
                if os.path.getsize(keep.path) == g.size and (not g.fp or fingerprint(keep.path, g.size) == g.fp):
                    # from its backup list (unchanged since it was checked), else read completely;
                    # a SHA-256 from a report alone is never enough to move something
                    keep_sha = _listed_sha(keep, cache) or sha256_file(keep.path, cancel)
            except OSError:
                keep_sha = ""
            except HashCancelled:
                out.cancelled = True
                break
            keep_ok = bool(keep_sha) and (not g.sha or keep_sha == g.sha)
            if keep_ok:
                g.sha = keep_sha
            for dup in g.extra:
                if cancel is not None and cancel.is_set():
                    out.cancelled = True
                    break
                done += g.size
                if not keep_ok:
                    out.skipped.append((dup.path, N_("the kept copy changed or is gone")))
                    continue
                try:
                    listed = _listed_sha(dup, cache)          # unchanged since its backup: not read again
                    same = os.path.getsize(dup.path) == g.size and (listed or sha256_file(dup.path, cancel)) == g.sha
                except OSError:
                    same = False
                except HashCancelled:
                    out.cancelled = True
                    break
                if not same:
                    out.skipped.append((dup.path, N_("the file changed since the check")))
                    continue
                target = review / os.path.relpath(dup.path, base)
                if target.exists():
                    out.skipped.append((dup.path, N_("a file with this name is already in the review folder")))
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.rename(dup.path, target)        # same drive: only the folder entry moves
                except OSError as e:
                    out.skipped.append((dup.path, str(e)))
                    continue
                try:
                    _fix_index(dup, keep, manifest["index"])
                except sqlite3.Error as e:
                    out.skipped.append((dup.path, tr("moved, but its backup list was not changed: %s", e)))
                manifest["moved"].append({"from": dup.path, "to": str(target), "sha256": g.sha,
                                          "size": g.size, "kept": keep.path})
                rows.append([dup.path, str(target), keep.path, g.size, g.sha])
                out.moved += 1
                out.bytes += g.size
                if progress:
                    progress(out.moved, len(result.groups) and result.duplicates, done, total, dup.path)
                if out.moved % 50 == 0:
                    save_manifest()
    finally:
        save_manifest()
        _remove_empty_dirs([m["from"] for m in manifest["moved"]], root)
        out.reports = write_report(out, result, rows, when)
    return out


def _remove_empty_dirs(paths, root):
    """Folders left EMPTY by the move (e.g. the structure built inside the old one) – only empty
    ones, never `root` itself; put_back() makes them again."""
    root = Path(root)
    dirs = set()
    for p in paths:
        for d in Path(p).parents:
            if d == root or root not in d.parents:
                break
            dirs.add(d)
    for d in sorted(dirs, key=lambda d: -len(d.parts)):
        try:
            d.rmdir()
        except OSError:
            pass


def write_report(out, result, rows, when):
    from .report import write_reports
    from . import ui
    sections = [(tr("Duplicate check"), [
        (tr("Folder checked"), result.root),
        (tr("Review folder"), out.review_dir),
        (tr("Files checked"), str(result.files)),
        (tr("Moved into the review folder"), f"{out.moved} ({ui.human_size(out.bytes)})"),
        (tr("Not moved"), str(len(out.skipped))),
        (tr("Same name, other content (not moved)"), str(len(result.same_name))),
    ])]
    if out.skipped:
        sections.append((tr("Not moved"), [(p, tr(r)) for p, r in out.skipped[:500]]))
    if result.same_name:
        sections.append((tr("Same name, other content (not moved)"),
                         [(name, " | ".join(e.path for e in lst)) for name, lst in result.same_name[:500]]))
    ok = not out.skipped and not out.cancelled
    verdict = (N_("CANCELLED by user") if out.cancelled else
               N_("COMPLETED") if ok else N_("COMPLETED WITH ERRORS"))
    return [str(p) for p in write_reports(
        out.review_dir, f"Duplicates {when:%Y-%m-%d %H-%M}", tr("Duplicates moved"), ok, verdict, sections,
        [tr("Was"), tr("Now in the review folder"), tr("Kept copy"), tr("Size"), "SHA-256"], rows)]


# --------------------------------------------------------------------------------- put back

@dataclass
class PutBackResult:
    restored: int = 0
    skipped: list = field(default_factory=list)


def put_back(review_dir):
    """Undo a move: every file back to its place (only if that place is free) and the backup
    lists as they were."""
    review = Path(review_dir)
    manifest = json.loads((review / MANIFEST).read_text(encoding="utf-8"))
    out = PutBackResult()
    back = set()
    left = []
    for m in manifest.get("moved", []):
        src, dst = Path(m["to"]), Path(m["from"])
        if not src.is_file():
            out.skipped.append((str(dst), N_("not in the review folder any more")))
            left.append(m)
            continue
        if dst.exists():
            out.skipped.append((str(dst), N_("its place is taken by another file")))
            left.append(m)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.rename(src, dst)
        except OSError as e:
            out.skipped.append((str(dst), str(e)))
            left.append(m)
            continue
        back.add(str(dst))
        out.restored += 1
    keep_index = []
    for ch in reversed(manifest.get("index", [])):
        try:
            db = sqlite3.connect(ch["db"])
            try:
                with db:
                    if ch["op"] == "update":
                        db.execute("UPDATE files SET rel_path = ? WHERE source_path = ? AND size = ? "
                                   "AND rel_path = ?", (ch["old"], ch["source_path"], ch["size"], ch["new"]))
                    else:
                        row = ch["row"]
                        cols = list(row)
                        db.execute(f"INSERT OR IGNORE INTO files({', '.join(cols)}) VALUES "
                                   f"({', '.join('?' for _ in cols)})", [row[c] for c in cols])
            finally:
                db.close()
        except sqlite3.Error as e:
            out.skipped.append((ch["db"], str(e)))
            keep_index.append(ch)
    manifest["moved"], manifest["index"] = left, list(reversed(keep_index))
    (review / MANIFEST).write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    if not left:          # empty folders of the review folder (the reports stay)
        for dirpath, _d, _f in sorted(os.walk(review), reverse=True):
            if Path(dirpath) != review:
                try:
                    os.rmdir(dirpath)
                except OSError:
                    pass
    return out


def review_dirs(base):
    """Review folders directly in `base` (newest first)."""
    try:
        found = [Path(e.path) for e in os.scandir(base) if e.is_dir() and e.name.startswith(REVIEW_PREFIX)
                 and is_review_dir(e.path)]
    except OSError:
        return []
    return sorted(found, key=lambda p: p.name, reverse=True)
