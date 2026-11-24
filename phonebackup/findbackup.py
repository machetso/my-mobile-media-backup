"""Choose a backup folder by hand, and find a backup that was moved or renamed (user request
2026-11-22: "the app does not recognise my backup from last week"). No Qt here.

The program keeps a backup in <drive folder>/<Owner>/<Phone>. When the user picks a folder by hand
it may be the drive folder, the owner folder, the backup folder itself, or a backup folder with
another name (copied or renamed by hand). `resolve()` works out which one and what to do:

  USE    the backup is there: <base>/<Owner>/<Phone>
  MOVE   the chosen folder is a backup but has another name/place → it is moved (renamed on the
         same drive, nothing copied or deleted) to <its parent>/<Owner>/<Phone>
  MERGE  like MOVE, but that place exists already → merged (setfolders._merge: identical files
         recognised, nothing overwritten or deleted)
  NEW    no backup of this phone in the folder → a new backup folder <chosen>/<Owner>/<Phone>;
         files that are already somewhere in it are NOT recognised (only inside the backup folder)

A folder whose files are not all in its list is compared with the phone at the next backup
(reconcile.adopt).
"""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import setfolders
from .index import INTERNAL_DIR
from .report import LOGS_DIR

USE, MOVE, MERGE, NEW = "use", "move", "merge", "new"


@dataclass
class Choice:
    action: str
    base: str                       # the folder to save as backup drive folder
    set_dir: str                    # where the backup folder is / will be
    source: str = ""                # MOVE / MERGE: the folder that is moved
    others: list = field(default_factory=list)   # other backups found in the chosen folder


def _is_year(name):
    return len(name) == 4 and name.isdigit() and 1990 <= int(name) <= 2100


def looks_like_backup(path):
    """A backup folder of this program: its list, its Logs folder with reports, or year folders."""
    p = Path(path)
    if (p / INTERNAL_DIR / "index.sqlite").is_file():
        return True
    if any((p / LOGS_DIR).glob("Backup *.txt")) or any(p.glob("Backup *.txt")):
        return True
    try:
        years = [e for e in os.scandir(p) if e.is_dir() and _is_year(e.name)]
    except OSError:
        return False
    return bool(years)


def _sets_inside(p, depth=2):
    """Backup folders below p (at most `depth` levels): [Path]."""
    out = []
    p = Path(p)

    def walk(d, level):
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError:
            return
        for e in entries:
            if not e.is_dir() or e.name.startswith(".") or e.name == LOGS_DIR or _is_year(e.name):
                continue
            if (Path(e.path) / INTERNAL_DIR / "index.sqlite").is_file():
                out.append(Path(e.path))
            elif level < depth:
                walk(e.path, level + 1)
    walk(p, 1)
    return out


def resolve(chosen, phone, owner):
    """What to do with the folder the user chose for the backup <owner>/<phone>."""
    p = Path(chosen)
    rel = Path(setfolders.rel(phone, owner))
    owner_dir, phone_dir = rel.parts
    if (p / rel).is_dir():
        return Choice(USE, str(p), str(p / rel))
    if len(p.parts) > 2 and p.name == phone_dir and p.parent.name == owner_dir:
        return Choice(USE, str(p.parent.parent), str(p))
    if p.name == owner_dir and (p / phone_dir).is_dir():
        return Choice(USE, str(p.parent), str(p / phone_dir))
    if looks_like_backup(p):
        target = p.parent / rel
        return Choice(MERGE if target.exists() else MOVE, str(p.parent), str(target), source=str(p))
    others = [str(s) for s in _sets_inside(p)]
    return Choice(NEW, str(p), str(p / rel), others=others)


def apply(choice, cfg=None):
    """Carry out MOVE / MERGE (USE / NEW need nothing). Returns the backup folder."""
    if choice.action == MOVE:
        target = Path(choice.set_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.rename(choice.source, target)              # same drive: only the folder entry moves
    elif choice.action == MERGE:
        setfolders._merge(Path(choice.source), Path(choice.set_dir))
    return choice.set_dir


# ----------------------------------------------------------------------------- search on drives
# only for "Add drive…" and "Integrate folders…" (user request 2026-11-23: never by itself)

def _is_set(path):
    return (Path(path) / INTERNAL_DIR / "index.sqlite").is_file()


def _subdirs(d):
    """The folders in d a search may go into (not hidden, not system "$…")."""
    out = []
    try:
        entries = list(os.scandir(d))
    except OSError:
        return out
    for e in entries:
        try:
            if e.is_dir(follow_symlinks=False) and not e.name.startswith((".", "$")):
                out.append(Path(e.path))
        except OSError:
            continue
    return out


def _likely(path):
    """Folders the program's backups are probably in come first (MMMB_Vol.2, PhoneBackups …)."""
    n = path.name.lower()
    return 0 if any(k in n for k in ("mmmb", "msmb", "backup", "phone", "handy", "smartphone")) else 1


def search_any(roots, max_depth=4, time_limit=20.0, max_dirs=40000, cancel=None, rel=None):
    """EVERY backup folder of this program on the drives, whatever its folders are called (user
    request 2026-11-23: names never decide – backupid.check does).

    1. Quick: the places the program itself uses – <drive>/<folder>/<rel> and
       <drive>/<folder>/<folder>/<rel> (rel = "Owner/Phone" of the wanted backup, if given).
    2. Then level by level (all folders of level 1, then of level 2 …), the likely names first,
       with its own time limit per drive – a big other folder on the drive (user 2026-11-23: a
       "Backups" folder with thousands of folders) cannot use up the time any more.
    Does not go into backup folders, year folders, Logs, review folders or hidden folders.
    Returns [set_dir]."""
    from collections import deque
    from .dedupe import is_review_dir
    found = []

    def add(p):
        if str(p) not in found:
            found.append(str(p))

    for root in roots:                                    # 1. the program's own places
        if _is_set(root):                  # a folder chosen by hand may be the backup folder itself
            add(Path(root))
            continue
        if rel and _is_set(Path(root) / rel):
            add(Path(root) / rel)
        if rel:
            for d1 in _subdirs(root):
                if _is_set(d1 / rel):
                    add(d1 / rel)
                for d2 in _subdirs(d1):
                    if _is_set(d2 / rel):
                        add(d2 / rel)
    quick = {r for r in roots if any(f.startswith(str(Path(r)).rstrip("/\\") + os.sep) for f in found)}
    for root in roots:                                    # 2. level by level
        if root in quick:          # the backup is in the program's own place there – no long search
            continue
        t_end = time.monotonic() + time_limit
        seen = 0
        queue = deque([(Path(root), 0)])
        while queue:
            if time.monotonic() > t_end or seen > max_dirs or (cancel is not None and cancel.is_set()):
                break
            d, level = queue.popleft()
            seen += 1
            for path in sorted(_subdirs(d), key=lambda p: (_likely(p), p.name.lower())):
                if _is_set(path):
                    add(path)
                    continue
                if _is_year(path.name) or path.name == LOGS_DIR or is_review_dir(path):
                    continue
                if level + 1 < max_depth:
                    queue.append((path, level + 1))
    return found


def placed(set_dir, phone, owner):
    """Where a found backup folder belongs: (base, target, action) – USE when it already is
    <base>/<Owner>/<Phone>, else MOVE (renamed in place, nothing copied) / MERGE (that place exists)
    to <its parent's parent>/<Owner>/<Phone>."""
    p = Path(set_dir)
    rel = Path(setfolders.rel(phone, owner))
    owner_dir, phone_dir = rel.parts
    if p.name == phone_dir and p.parent.name == owner_dir:
        return str(p.parent.parent), str(p), USE
    base = p.parent.parent if p.parent.parent != p.parent else p.parent
    target = base / rel
    return str(base), str(target), (MERGE if target.exists() else MOVE)


def base_of(set_dir):
    """<base> of a backup folder <base>/<Owner>/<Phone>."""
    return str(Path(set_dir).parent.parent)


def mount_root(path, roots):
    """The drive (one of `roots`) a path is on – also for a path that does not exist any more."""
    best = ""
    p = str(path)
    for r in roots:
        r = str(r).rstrip("/\\")
        if (p == r or p.startswith(r + os.sep) or p.startswith(r + "/")) and len(r) > len(best):
            best = r
    return best


def replace_missing(dests, new, roots):
    """The drive folders of a backup after `new` was chosen: folders that do not exist any more
    and were on the same drive as `new` are replaced (the folder was moved/renamed there)."""
    root = mount_root(new, roots)
    out = []
    for d in dests:
        if d == new:
            continue
        if root and not os.path.isdir(d) and mount_root(d, roots) == root:
            continue
        out.append(d)
    return out + [new]


# ------------------------------------------------- the backups in a folder, and are two the same?
# (user request 2026-11-22: "I only want to choose the program's folder and then pick the backup;
# a backup on a second drive should be compared with the first one – is it the same backup?")

@dataclass
class SetInfo:
    set_dir: str
    name: str                 # "Owner / Phone" as the folders are named
    files: int = 0
    size: int = 0
    last: str = ""            # newest "backed up at" in its list ("2026-11-22 01:10:00"), "" unknown


def set_info(set_dir):
    """Name, files, size and newest backup of a backup folder (read from its list, read-only)."""
    import sqlite3
    p = Path(set_dir)
    info = SetInfo(str(p), setfolders.shown(setfolders.rel_of(p)))
    db_path = p / INTERNAL_DIR / "index.sqlite"
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            last = {}
            for rel, size, when in db.execute("SELECT rel_path, size, backed_up_at FROM files ORDER BY rowid"):
                last[rel] = (size, when)
        finally:
            db.close()
    except sqlite3.Error:
        return info
    info.files = len(last)
    info.size = sum(s or 0 for s, _w in last.values())
    info.last = max((w for _s, w in last.values() if w), default="")
    return info


def sets_in(folder, depth=3):
    """The backup folders in a chosen folder: the folder itself if it is one, else every backup
    folder up to `depth` levels below it. Returns [SetInfo], sorted by name."""
    p = Path(folder)
    if (p / INTERNAL_DIR / "index.sqlite").is_file():
        return [set_info(p)]
    return sorted((set_info(s) for s in _sets_inside(p, depth)), key=lambda i: i.name.lower())


SAME, BEHIND, DIFFERENT, ALONE = "same", "behind", "different", "alone"


@dataclass
class Comparison:
    kind: str                 # SAME | BEHIND (same backup, files missing somewhere) | DIFFERENT | ALONE
    shared: int = 0           # identical files (SHA-256) in both
    only_here: int = 0        # files only in the chosen backup
    only_there: int = 0       # files only in the other backup(s)
    other_phone: bool = False  # DIFFERENT because the phones' serial numbers differ


def compare(chosen, others):
    """Is the backup folder `chosen` the same backup as the folders `others` (the backup on the
    other drives)? Compares the files that are really there by SHA-256 and, when both know it,
    the phone's serial number. Read-only."""
    from . import completeness, phoneid
    here = Path(chosen).resolve()
    others = [Path(o) for o in others if Path(o).is_dir() and Path(o).resolve() != here]
    if not others:
        return Comparison(ALONE)
    mine = completeness.present_hashes(here) or set()
    theirs = set()
    for o in others:
        theirs |= completeness.present_hashes(o) or set()
    shared = len(mine & theirs)
    c = Comparison(SAME, shared, len(mine - theirs), len(theirs - mine))

    def serials(p):
        rec = phoneid.load(p)
        return {s for s in (rec.serials if rec else []) if s}
    a = serials(here)
    b = set().union(*(serials(o) for o in others))
    if a and b and not a & b:
        c.kind, c.other_phone = DIFFERENT, True
    elif mine and theirs and shared < max(3, 0.2 * min(len(mine), len(theirs))):
        c.kind = DIFFERENT
    elif c.only_here or c.only_there:
        c.kind = BEHIND
    return c
