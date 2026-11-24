"""Complete backups (user request 2026-11-17). No Qt here.

After a backup from the phone that secured every photo and video of its folders (no errors, every
drive reachable, all checked with SHA-256) the backup is complete – the program decides that itself,
nothing is asked (user 2026-11-22; until then the user was asked "Is this backup complete?"). That
backup is the reference: the drives it was written to are complete (as of that moment). Every other backup drive of the same backup is compared
with the reference file by file (SHA-256 from the drives' index): a drive that has every file of
the reference is complete too, otherwise the number of missing files is shown.

Settings:
  cfg["complete_ref"][key]    {"when": "2026-11-17 09:30:12", "drives": [base, ...]} – newest "Yes"
  cfg["complete_state"][key]  {base: {"complete": bool, "missing": n, "checked": "..."}} – the last
                              result per drive, shown while a drive is not connected
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config
from .index import INTERNAL_DIR


def _now():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def mark_complete(cfg, key, drives, when=None):
    """The user answered "Yes": the backup on `drives` is complete."""
    when = when or _now()
    cfg.setdefault("complete_ref", {})[key] = {"when": when, "drives": [str(d) for d in drives]}
    state = cfg.setdefault("complete_state", {}).setdefault(key, {})
    for d in drives:
        state[str(d)] = {"complete": True, "missing": 0, "checked": when}
    config.save(cfg)


def reference(cfg, key):
    return (cfg.get("complete_ref") or {}).get(key)


def hashes(set_dir, upto=None):
    """SHA-256 of every file in a backup folder (from its index); None without an index.
    upto: only files backed up until then ("2026-11-17 09:30:12")."""
    p = Path(set_dir) / INTERNAL_DIR / "index.sqlite"
    if not p.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            if upto:
                rows = db.execute("SELECT sha256 FROM files WHERE backed_up_at IS NULL OR backed_up_at <= ?",
                                  (upto,))
            else:
                rows = db.execute("SELECT sha256 FROM files")
            return {r[0] for r in rows}
        finally:
            db.close()
    except sqlite3.Error:
        return None


def listed_and_present(set_dir):
    """(listed, present): SHA-256 of the files its list names (per place the newest entry) and of
    those really there now. None without an index."""
    set_dir = Path(set_dir)
    p = set_dir / INTERNAL_DIR / "index.sqlite"
    if not p.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            last = {rel: sha for rel, sha in db.execute("SELECT rel_path, sha256 FROM files ORDER BY rowid")}
        finally:
            db.close()
    except sqlite3.Error:
        return None
    listed, out = {}, set()
    for rel, sha in last.items():
        folder, name = os.path.split(rel)
        if folder not in listed:
            try:
                listed[folder] = set(os.listdir(set_dir / folder))
            except OSError:
                listed[folder] = set()
        if name in listed[folder]:
            out.add(sha)
    return set(last.values()), out


def present_hashes(set_dir):
    """SHA-256 of the files that are really in a backup folder now: per place the newest index
    entry, and only if the file is there (user 2026-11-22: an old entry – e.g. a file that was
    later backed up again with other content, or a file removed by hand – made a new drive look
    like it missed more files than the other drive has). None without an index."""
    set_dir = Path(set_dir)
    p = set_dir / INTERNAL_DIR / "index.sqlite"
    if not p.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            last = {rel: sha for rel, sha in db.execute("SELECT rel_path, sha256 FROM files ORDER BY rowid")}
        finally:
            db.close()
    except sqlite3.Error:
        return None
    listed, out = {}, set()
    for rel, sha in last.items():
        folder, name = os.path.split(rel)
        if folder not in listed:
            try:
                listed[folder] = set(os.listdir(set_dir / folder))
            except OSError:
                listed[folder] = set()
        if name in listed[folder]:
            out.add(sha)
    return out


def check(cfg, key, rel, drives):
    """{base: {"complete", "missing", "checked", "live"}} for the backup's drives. `rel` = the
    backup's folder below a drive ("Sam/Pixel 10 Pro"). Drives that cannot be checked now (not
    connected, or the reference drive is not connected) keep their last result (live=False)."""
    ref = reference(cfg, key)
    state = cfg.setdefault("complete_state", {}).setdefault(key, {})
    out = {}
    ref_set = None
    if ref:
        for d in ref["drives"]:
            ref_set = hashes(Path(d) / rel, ref["when"])
            if ref_set is not None:
                break
    changed = False
    for d in drives:
        d = str(d)
        if ref and d in ref["drives"]:
            out[d] = {"complete": True, "missing": 0, "checked": ref["when"], "live": True}
            continue
        have = hashes(Path(d) / rel) if ref_set is not None else None
        if have is not None:
            missing = len(ref_set - have)
            res = {"complete": missing == 0, "missing": missing, "checked": _now()}
            if {k: v for k, v in (state.get(d) or {}).items() if k != "checked"} != \
                    {k: v for k, v in res.items() if k != "checked"}:
                changed = True
            state[d] = res
            out[d] = dict(res, live=True)
        elif d in state:
            out[d] = dict(state[d], live=False)
    if changed:
        config.save(cfg)
    return out


# ----------------------------------------------------------------------- drives compared with each other

def folder_state(set_dir):
    """What a backup folder really holds (user 2026-11-23: the drive list said "up to date" while
    the file counts differed): one walk of the folder plus its list.

    Returns {"listed": SHA-256 its list names (newest entry per place), "present": those of them
    whose file is there, "content": one key per file – ("sha", …) for listed files, ("file",
    place, size) for files the list does not name (e.g. a backup built inside the backup),
    "files"/"bytes": every file in the folder} – or None without a list."""
    from . import knownhash
    set_dir = Path(set_dir)
    p = set_dir / INTERNAL_DIR / "index.sqlite"
    if not p.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            last = {rel: sha for rel, sha in db.execute("SELECT rel_path, sha256 FROM files ORDER BY rowid")}
        finally:
            db.close()
    except sqlite3.Error:
        return None
    # only photos and videos count – not the logs, reports and files of the program (user 2026-11-23)
    disk = knownhash.media_files(set_dir)
    last = {rel: sha for rel, sha in last.items() if knownhash.is_media(rel.rsplit("/", 1)[-1])}
    present = {sha for rel, sha in last.items() if rel in disk}
    content = {("sha", sha) for sha in present}
    content |= {("file", rel, size) for rel, (size, _m) in disk.items() if rel not in last}
    _known, unknown = knownhash.known(set_dir, disk)
    return {"listed": set(last.values()), "present": present, "content": content,
            "files": len(disk), "bytes": sum(size for size, _m in disk.values()), "unknown": unknown}


def compare_drives(cfg, key, rel, drives):
    """Are the backup drives of a backup up to date with each other? Every connected drive is
    compared with EVERYTHING any connected drive of the backup holds: the files of the lists by
    SHA-256, the other files in the backup folder by place and size (user 2026-11-23).

    Returns {base: {"missing": n, "files": n, "bytes": n, "checked": "...", "live": bool,
    "alone": bool}}; a drive that is not connected keeps its last result (live=False)."""
    state = cfg.setdefault("drive_state", {}).setdefault(key, {})
    have, info = {}, {}
    for d in drives:
        d = str(d)
        p = Path(d) / rel
        if not Path(d).is_dir():
            continue
        st = folder_state(p) if p.is_dir() else None          # a new drive: nothing there yet
        info[d] = st or {"listed": set(), "present": set(), "content": set(), "files": 0, "bytes": 0,
                         "unknown": []}
        have[d] = info[d]["content"]
    union = set().union(*have.values()) if have else set()
    out, changed, now = {}, False, _now()
    alone = len(have) < 2
    for d in drives:
        d = str(d)
        if d in have:
            res = {"missing": len(union - have[d]), "files": info[d]["files"], "bytes": info[d]["bytes"],
                   "unknown": len(info[d].get("unknown", [])), "checked": now}
            old = state.get(d) or {}
            if [old.get(k) for k in ("missing", "files", "bytes", "unknown")] != \
                    [res[k] for k in ("missing", "files", "bytes", "unknown")]:
                changed = True
            state[d] = res
            out[d] = dict(res, live=True, alone=alone)
            # entries of its list whose file is nowhere in the folder (shown, not "missing")
            out[d]["own_missing"] = len(info[d]["listed"] - info[d]["present"])
            if alone:
                # one drive (user request 2026-11-23): compared with its own list and with what is
                # known of the backup's other drives from their last check
                others = [(v.get("files", 0), v.get("checked", ""), o) for o, v in state.items()
                          if o != d and o in [str(x) for x in drives]]
                if others:
                    files, when, o = max(others)
                    out[d]["other_files"], out[d]["other_checked"], out[d]["other"] = files, when, o
        elif d in state:
            out[d] = dict(state[d], live=False, alone=False)
    if changed:
        config.save(cfg)
    return out
