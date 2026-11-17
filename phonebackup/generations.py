"""Which Grandfather-Father-Son generations a backup has on a storage (user request 2026-11-17,
Manage backups → Overview). No Qt here.

A storage is a "Backup backups" target (another drive, Google Drive) or a backup drive with the
Grandfather-Father-Son plan; each keeps a catalog of its runs. A summary of it is remembered in
cfg["gfs_summary"][key][target] so the overview also knows it while the storage is not connected
(Google Drive is never asked just for the overview).

summary = {"checked": "...",
           "full": {"count": n, "last": "2026-11-01 10:00:00"},   # Grandfather (full backup)
           "differential": {...},                                    # Father (monthly differential)
           "incremental": {...},                                     # Son (latest complement)
           "unfinished": [{"type": "full", "started": "...", "status": "RUNNING"}, ...]}
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from . import config, gfs
from .export import EXPORT_DIR, Run

GDRIVE = "gdrive"
TYPES = ("full", "differential", "incremental")


def summarize(runs):
    out = {"checked": datetime.now().isoformat(sep=" ", timespec="seconds"), "unfinished": []}
    for t in TYPES:
        done = [r for r in runs if r.type == t and r.status == "COMPLETED"]
        out[t] = {"count": len(done), "last": done[-1].started if done else ""}
    out["unfinished"] = [{"type": r.type, "started": r.started, "status": r.status}
                         for r in runs if r.status not in ("COMPLETED", gfs.REMOVED)]
    return out


def read_runs(set_dir):
    """Runs from the catalog of a folder on a connected drive (read-only); None without catalog."""
    p = Path(set_dir) / EXPORT_DIR / "catalog.sqlite"
    if not p.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            return [Run(*r) for r in db.execute(
                "SELECT id,type,folder,started,finished,status FROM runs ORDER BY id")]
        finally:
            db.close()
    except sqlite3.Error:
        return None


def remember(cfg, key, target, runs):
    cfg.setdefault("gfs_summary", {}).setdefault(key, {})[str(target)] = summarize(runs)
    config.save(cfg)


def of(cfg, key, target, set_dir=None):
    """(summary, live): read from the drive if it is connected, else the remembered one."""
    if set_dir is not None:
        runs = read_runs(set_dir)
        if runs is not None:
            s = summarize(runs)
            old = (cfg.get("gfs_summary") or {}).get(key, {}).get(str(target))
            if old is None or {k: v for k, v in old.items() if k != "checked"} != \
                    {k: v for k, v in s.items() if k != "checked"}:
                remember(cfg, key, target, runs)
            return s, True
    return (cfg.get("gfs_summary") or {}).get(key, {}).get(str(target)), False


def targets(cfg, key):
    """The storages with a remembered summary for this backup."""
    return list(((cfg.get("gfs_summary") or {}).get(key) or {}).keys())
