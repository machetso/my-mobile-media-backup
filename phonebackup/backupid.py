"""Which folder on a drive really is THIS backup (user request 2026-11-23: "I just pick the drive and
the app finds the right folders – it must not be fooled by someone who recreates the folder
structure"). No Qt here.

Folder names never decide. A folder is this backup only if it passes these checks:

  1. It is a backup folder of the program: .phonebackup/index.sqlite (its list of files).
  2. Its mark .phonebackup/backup.json carries the backup's id – a random 128-bit number that is
     kept in the program's settings (backup_profiles[key]["backup_id"]) and in the marks of its
     drives. A folder with ANOTHER id is another backup. Folders made before the mark existed have
     none: they can only be "probably this backup" and the user decides once; then they get the mark.
  3. The phone: the serial numbers in .phonebackup/phone.json must not contradict the phone of
     this backup.
  4. The list belongs to the files: a sample of the files is read and must have exactly the
     SHA-256 its list names (a copied list next to other files fails), and most listed files
     must be there.
  5. Compared with the backup's other drives (SHA-256 of all files), it must be the same backup
     (findbackup.compare: not DIFFERENT).

A copy of the whole folder (e.g. a drive cloned by hand) passes – it IS the same backup.
The mark also names the owner and the phone (for people looking at the drive).
"""

import json
import os
import random
import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .i18n import tr
from .index import INTERNAL_DIR

FILE = "backup.json"
CONFIRMED, PROBABLE, REJECTED = "confirmed", "probable", "rejected"
SAMPLE = 12                       # files read for the check
SAMPLE_MAX_SIZE = 32 * 1024 ** 2  # prefer files up to 32 MB (quick to read)


def new_id():
    return secrets.token_hex(16)


def _path(set_dir):
    return Path(set_dir) / INTERNAL_DIR / FILE


def load(set_dir):
    """The mark of a backup folder: {"id", "owner", "phone", ...} or None."""
    try:
        d = json.loads(_path(set_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("id"), str) and d["id"] else None


def id_of(set_dir):
    m = load(set_dir)
    return m["id"] if m else ""


def write(set_dir, backup_id, owner, phone):
    """Mark a backup folder (atomic). Keeps the date it was first marked."""
    p = _path(set_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    old = load(set_dir) or {}
    data = {"id": backup_id, "owner": owner, "phone": phone,
            "program": "My Mobile Media Backup",
            "marked": old.get("marked") if old.get("id") == backup_id and old.get("marked")
            else datetime.now().isoformat(timespec="seconds")}
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def stored(cfg, key):
    return ((cfg.get("backup_profiles") or {}).get(key) or {}).get("backup_id", "")


def resolve(cfg, key, set_dirs, create=True):
    """The backup's id: from the settings; else taken over from the marks of its folders (e.g. the
    backup was marked on another computer) when they agree; else a new one (create=True).
    Saved in the settings. Returns (id, conflict) – conflict = its folders carry different ids."""
    from . import backuplist
    have = stored(cfg, key)
    if have:
        return have, False
    ids = {i for i in (id_of(s) for s in set_dirs if Path(s).is_dir()) if i}
    if len(ids) > 1:
        return "", True
    bid = ids.pop() if ids else (new_id() if create else "")
    if bid:
        backuplist.save_profile(cfg, key, backup_id=bid)
    return bid, False


# ------------------------------------------------------------------------------- the check

@dataclass
class Check:
    set_dir: str
    kind: str = REJECTED
    reasons: list = field(default_factory=list)     # translated, why REJECTED / why only PROBABLE
    files: int = 0                                  # files of its list that are there
    listed: int = 0                                 # places in its list
    sampled: int = 0
    mark_id: str = ""


def _newest_rows(set_dir):
    """{rel_path: (sha256, size)} – per place the newest entry of the list. None: no list."""
    p = Path(set_dir) / INTERNAL_DIR / "index.sqlite"
    if not p.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            return {rel: (sha, size) for rel, sha, size in
                    db.execute("SELECT rel_path, sha256, size FROM files ORDER BY rowid")}
        finally:
            db.close()
    except sqlite3.Error:
        return None


def verify_files(set_dir, rows, n=SAMPLE, rng=None):
    """(present, sampled, bad): how many listed files are there, how many were read, and the
    ones whose content is not what the list says."""
    from .copier import sha256_file
    set_dir = Path(set_dir)
    listed, present = {}, []
    for rel, (sha, size) in rows.items():
        folder, name = os.path.split(rel)
        if folder not in listed:
            try:
                listed[folder] = set(os.listdir(set_dir / folder))
            except OSError:
                listed[folder] = set()
        if name in listed[folder]:
            present.append((rel, sha, size or 0))
    rng = rng or random.SystemRandom()
    small = [r for r in present if r[2] <= SAMPLE_MAX_SIZE]
    pool = small if len(small) >= min(n, len(present)) else sorted(present, key=lambda r: r[2])[:max(n, 1) * 4]
    pick = rng.sample(pool, min(n, len(pool)))
    bad = []
    for rel, sha, _size in pick:
        try:
            if sha256_file(set_dir / rel) != sha:
                bad.append(rel)
        except OSError:
            bad.append(rel)
    return len(present), len(pick), bad


def check(set_dir, backup_id, serials=(), others=(), n=SAMPLE):
    """Is `set_dir` this backup? backup_id = the backup's id ("" = not known yet), serials = the
    phone's known serial numbers, others = the backup's folders on its other drives (already
    trusted). Read-only. Returns a Check."""
    from . import findbackup, phoneid
    c = Check(str(set_dir))
    rows = _newest_rows(set_dir)
    if rows is None:
        c.reasons.append(tr("no backup list (.phonebackup) – not a backup of this program"))
        return c
    c.listed = len(rows)
    c.mark_id = id_of(set_dir)
    if c.mark_id and backup_id and c.mark_id != backup_id:
        c.reasons.append(tr("its mark belongs to another backup"))
        return c
    rec = phoneid.load(set_dir)
    mine = {s for s in (rec.serials if rec else []) if s}
    known = {s for s in serials if s}
    if mine and known and not mine & known:
        c.reasons.append(tr("it is the backup of another phone (other serial number)"))
        return c
    c.files, c.sampled, bad = verify_files(set_dir, rows, n)
    if bad:
        c.reasons.append(tr("%d of %d checked files do not have the content its list names (SHA-256)",
                            len(bad), c.sampled))
        return c
    if c.listed and c.files < 0.5 * c.listed:
        c.reasons.append(tr("most files of its list are missing (%d of %d there)", c.files, c.listed))
        return c
    if not c.listed and not (c.mark_id and c.mark_id == backup_id):
        c.reasons.append(tr("its list is empty"))
        return c
    others = [o for o in others if Path(o).is_dir()]
    if others:
        cmp = findbackup.compare(set_dir, others)
        if cmp.kind == findbackup.DIFFERENT:
            c.reasons.append(tr("its files are not those of this backup on the other drive "
                                "(only %d the same)", cmp.shared))
            return c
    if c.mark_id and c.mark_id == backup_id:
        c.kind = CONFIRMED
    else:
        c.kind = PROBABLE
        c.reasons.append(tr("not marked yet (made by an older version or on another computer)"))
    return c


# ----------------------------------------------------------- follow a drive whose path changed
# (user request 2026-11-23: two VeraCrypt volumes opened in the other order swapped their mount
# points /media/veracrypt1 ↔ /media/veracrypt2; on Windows drive letters change the same way)

def _moved_to(old_base, rel, bid, roots, exclude=()):
    """Where the drive folder `old_base` of the backup with id `bid` is now: the same folder path
    on another attached drive, and only if its backup folder carries THIS backup's mark. ""=none."""
    parts = Path(old_base).parts
    for k in range(1, len(parts)):               # the longest tail first: "2nd Backup/MMMB_Vol.1" …
        tail = Path(*parts[k:])
        for r in roots:
            cand = str(Path(r) / tail)
            if cand == str(old_base) or cand in exclude:
                continue
            if id_of(Path(cand) / rel) == bid:
                return cand
    return ""


def follow(cfg, roots):
    """Every backup with an id whose drive folder is gone (or holds ANOTHER backup now) is pointed
    to where its marked folder is now. Unmarked folders are never followed (→ "Add drive…" / "Integrate folder…").
    Saves the settings. Returns [(key, old_base, new_base)]."""
    from . import backuplist, setfolders
    changes = []
    for key, prof in list((cfg.get("backup_profiles") or {}).items()):
        bid, dests = prof.get("backup_id"), list(prof.get("destinations") or [])
        if not bid or not dests:
            continue
        phone, owner = setfolders.split_old(key, cfg)
        rel = setfolders.rel(phone, owner)
        new, mine = list(dests), []
        for i, d in enumerate(dests):
            set_dir = Path(d) / rel
            if set_dir.is_dir() and id_of(set_dir) in ("", bid):
                continue                          # there (marked, or not marked yet): nothing to do
            to = _moved_to(d, rel, bid, roots, exclude=set(new))
            if to:
                new[i] = to
                mine.append((key, d, to))
        if mine:
            backuplist.save_profile(cfg, key, destinations=new)
            changes += mine
    return changes
