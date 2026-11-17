"""Complete backups (user request 2026-11-17). No Qt here.

Only the user knows whether a backup holds ALL photos and videos of the phone, so after every
backup from the phone the program asks. A "Yes" makes that backup the reference: the drives it was
written to are complete (as of that moment). Every other backup drive of the same backup is compared
with the reference file by file (SHA-256 from the drives' index): a drive that has every file of
the reference is complete too, otherwise the number of missing files is shown.

Settings:
  cfg["complete_ref"][key]    {"when": "2026-11-17 09:30:12", "drives": [base, ...]} – newest "Yes"
  cfg["complete_state"][key]  {base: {"complete": bool, "missing": n, "checked": "..."}} – the last
                              result per drive, shown while a drive is not connected
"""

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
