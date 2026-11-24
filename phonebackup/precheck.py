"""Before a backup starts: how many photos and videos are new, and about how long will it take?
(user request 2026-11-22). No Qt here, nothing is written – only read.

The check reads the phone's file list once and compares it with the backup's list on every
drive (read-only). The file list is handed to the backup afterwards, so the phone is not asked
twice. The user can skip the check; the backup then works it out itself as before.
"""

import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import plans
from .index import INTERNAL_DIR
from .layout import safe_name
from .media import category_for

DRIVE_MBS = 60.0          # drive → drive copy incl. read-back (USB hard disk, conservative)


@dataclass
class Precheck:
    listing: tuple = None             # (files, missing) from source.list_files – reused by the backup
    found: int = 0                    # photos/videos in the chosen folders on the phone
    already: int = 0                  # … on every (simple) drive already
    new: int = 0                      # … to copy from the phone
    new_bytes: int = 0
    from_drive: int = 0               # … another drive of the backup has them: copied drive → drive
    from_drive_bytes: int = 0
    maybe_there: int = 0              # same name + size in a backup folder, not in its list yet
    complete: bool = False            # False: skipped / cancelled before the end
    seconds: float = 0.0              # how long the check took
    gfs: bool = False                 # a Grandfather-Father-Son drive: its count is not included
    per_dest: dict = field(default_factory=dict)

    def estimate_seconds(self, phone_mbs):
        t = self.new_bytes / (phone_mbs * 1e6) if phone_mbs else 0.0
        return t + self.from_drive_bytes / (DRIVE_MBS * 1e6)


def _known(set_dir):
    """{(source_path, size)} of a backup folder whose file is still there (read-only)."""
    p = Path(set_dir) / INTERNAL_DIR / "index.sqlite"
    out = set()
    if not p.is_file():
        return out
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            rows = db.execute("SELECT source_path, size, rel_path FROM files").fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return out
    rels = {}
    for sp, size, rel in rows:
        rels.setdefault(rel, []).append((sp, size))
    for rel, keys in rels.items():
        if os.path.isfile(os.path.join(set_dir, rel)):
            out.update(keys)
    return out


def run(source, folders, dest_bases, parent_name, cfg, progress=None, stop=None, listing=None):
    """progress(phase, done, total): phase "list" (reading the phone) or "compare".
    stop(): True = finish now (skip) – returns what is known so far (complete=False)."""
    t0 = time.monotonic()
    res = Precheck()
    if listing is not None:                     # read just before (phone check)
        files, missing = listing
    else:
        if progress:
            progress("list", 0, 0)
        files, missing = source.list_files(folders)
    res.listing = (files, missing)
    classify = getattr(source, "category_of", None) or (lambda f: category_for(f.name))
    supported = [sf for sf in files if classify(sf)]
    res.found = len(supported)
    if stop and stop():
        res.seconds = time.monotonic() - t0
        return res

    dests = []
    for base in dest_bases:
        set_dir = Path(base) / parent_name
        plan = plans.folder_plan(set_dir) or plans.plan_of(cfg, base)
        if plan == plans.GFS:
            res.gfs = True
            continue
        dests.append(str(set_dir))
    if not dests:
        res.new, res.new_bytes = len(supported), sum(sf.size for sf in supported)
        res.complete = True
        res.seconds = time.monotonic() - t0
        return res
    known = {}
    for i, d in enumerate(dests):
        if progress:
            progress("compare", 0, len(supported))
        known[d] = _known(d)
        if stop and stop():
            res.seconds = time.monotonic() - t0
            return res
    names = {}                                  # set_dir -> {(name, size)} of files outside its list
    total = len(supported)
    for i, sf in enumerate(supported, 1):
        if stop and i % 200 == 0 and stop():
            res.seconds = time.monotonic() - t0
            return res
        if progress and i % 200 == 0:
            progress("compare", i, total)
        key = (sf.source_key, sf.size)
        need = [d for d in dests if key not in known[d]]
        if not need:
            res.already += 1
            continue
        if len(need) < len(dests):              # another drive has it
            res.from_drive += len(need)
            res.from_drive_bytes += sf.size * len(need)
            continue
        maybe = False
        for d in need:
            if d not in names:
                names[d] = _outside_list(d)
            if (safe_name(sf.name).casefold(), sf.size) in names[d]:
                maybe = True
        if maybe:
            res.maybe_there += 1
            continue
        res.new += 1
        res.new_bytes += sf.size
    if progress:
        progress("compare", total, total)
    res.complete = True
    res.seconds = time.monotonic() - t0
    return res


def _outside_list(set_dir):
    from .reconcile import folder_files
    p = Path(set_dir) / INTERNAL_DIR / "index.sqlite"
    listed = set()
    if p.is_file():
        try:
            db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            try:
                listed = {r for (r,) in db.execute("SELECT DISTINCT rel_path FROM files")}
            finally:
                db.close()
        except sqlite3.Error:
            pass
    if not Path(set_dir).is_dir():
        return set()
    return {(rel.rsplit("/", 1)[-1].casefold(), size)
            for rel, (size, _m) in folder_files(set_dir).items() if rel not in listed}
