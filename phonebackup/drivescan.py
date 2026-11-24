"""Everything the window shows about the backup drives, read in ONE background job (user request
2026-11-23: "the app waited at the start for a drive to be ready – that should not happen").

A sleeping hard drive needs seconds to spin up; whatever reads it in the window's own thread
freezes the window meanwhile. So the window never reads the drives for showing them: it shows
this snapshot – or, before the first one is there, what the settings remember – and the snapshot
is made in the background: at the start, on "Refresh", after jobs and when drives come and go.

No Qt here.
"""

import os
from pathlib import Path

from . import (backupid, backuplist, completeness, generations, history, knownlist, lastbackup,
               plans, setfolders)
from .index import backup_totals


def scan(cfg, roots, cancel=None):
    """The snapshot (a dict). Also does what needs the drives anyway: backups made before the phone
    list (lastbackup.discover) and drives whose path changed (backupid.follow). May change and
    save the settings."""
    from .locations import find_backups
    snap = {"roots": list(roots), "sets": {}, "totals": {}, "comp": {}, "avail": {}, "marks": {},
            "copies": {}, "plans": {}, "reports": {}, "follow": []}
    lastbackup.discover(cfg)
    try:
        snap["follow"] = backupid.follow(cfg, roots)
    except OSError:
        pass
    for p in find_backups(cfg):
        snap["sets"].setdefault(setfolders.key_of(p), []).append(p)
    snap["errors"] = []
    for b in backuplist.known(cfg, snap["sets"]):          # removed backups are not read
        if cancel is not None and cancel.is_set():
            break
        try:
            _scan_backup(cfg, b, snap)
        except Exception as e:  # noqa: BLE001 - one backup that cannot be read must not stop the others
            snap["errors"].append(f"{b['key']}: {type(e).__name__}: {e}")
    return snap


def _scan_backup(cfg, b, snap):
    """One backup: its drives, comparison, reports, secured copies (into `snap`)."""
    rel = setfolders.rel(b["phone"], b["owner"])
    for c in b["copies"]:
        snap["totals"][c] = backup_totals(c)
    for d in b["drives"]:
        avail = os.path.isdir(d)
        snap["avail"][d] = avail
        set_dir = Path(d) / rel
        copy = str(set_dir) if avail and set_dir.is_dir() else None
        snap["copies"][(b["key"], d)] = copy
        if copy:
            snap["totals"].setdefault(copy, backup_totals(copy))
            snap["marks"][copy] = backupid.id_of(copy)
            from .nestmerge import inner_sets
            from .regroup import plan as regroup_plan
            snap.setdefault("nested", {})[(b["key"], d)] = [str(x) for x in inner_sets(copy)]
            snap.setdefault("regroup", {})[(b["key"], d)] = sum(len(f.moves) for f in regroup_plan(copy))
            snap["plans"][(b["key"], d)] = plans.folder_plan(set_dir)
            if snap["plans"][(b["key"], d)] == plans.GFS:
                generations.of(cfg, b["key"], d, set_dir)        # remembered in the settings
    snap["comp"][b["key"]] = completeness.compare_drives(cfg, b["key"], rel, b["drives"])
    # the newest file list of the connected drives: "not backed up yet" on the phone (2026-11-23)
    knownlist.refresh(b["key"], [c for (k, _d), c in snap["copies"].items() if k == b["key"] and c])
    snap["reports"][b["key"]] = history.from_reports(b["copies"])
    drives = set(b["drives"])                                      # secured copies: remembered
    targets = [t for t in cfg.get("export_targets", []) if not str(t).startswith("gdrive:")]
    targets += [t for t in generations.targets(cfg, b["key"]) if t not in targets and t not in drives]
    for t in targets:
        if t == generations.GDRIVE:
            continue
        set_dir = Path(t) / rel
        if set_dir.is_dir():
            generations.of(cfg, b["key"], t, set_dir)


def remembered_comp(cfg, key, drives):
    """The comparison as the settings remember it (before the first snapshot): never live."""
    state = (cfg.get("drive_state") or {}).get(key) or {}
    return {str(d): dict(state[str(d)], live=False, alone=False) for d in drives if str(d) in state}


# keys of the settings the scan may change (discover, follow, comparison, secured copies)
KEYS = ("phones", "backup_profiles", "destinations", "drive_state", "gfs_summary")


def copy_settings(cfg):
    """In the window's thread, right before the scan: (work copy, the keys as they were)."""
    import copy
    return copy.deepcopy(cfg), {k: copy.deepcopy(cfg.get(k)) for k in KEYS}


def scan_copy(work, before, cancel=None):
    """Run in a background thread: scan() on the COPY of the settings, nothing saved. Returns
    (snapshot, {key: (value before, value after)} for the keys the scan changed)."""
    from . import config
    from .locations import detect_drives
    with config.not_saved():
        roots = [r for r, _f in detect_drives()]
        snap = scan(work, roots, cancel)
    changes = {k: (before[k], work.get(k)) for k in KEYS if work.get(k) != before[k]}
    return snap, changes


def apply_changes(cfg, changes):
    """In the window's thread: take the scan's changes over – a key the window changed meanwhile
    is left as it is (returns False then: scan again)."""
    clean = True
    for k, (was, now) in changes.items():
        if cfg.get(k) != was:
            clean = False
            continue
        cfg[k] = now
    return clean
