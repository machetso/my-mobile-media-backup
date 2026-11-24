"""Backup history (user request 2026-11-17): every backup of a phone and every addition from another
source (old drive, old phone, folders) is remembered per backup. No Qt here.

Stored in the settings as cfg["backup_history"][key] (key = setfolders.key, "Pixel 10 Pro - Sam"):
a list of entries

  when      start of the run, "2026-11-17T09:30:12"
  kind      "backup" (from the phone) | "import" (added from another source)
  source    phone model / connection, or the imported folder(s)
  files     new files secured in this run
  bytes     their size
  status    English status ("COMPLETED", "CANCELLED by user", ...) – shown with report.shown
  drives    the backup drives (base folders) written to

Runs made before this version (or on another computer) are read from the reports in the backup's
Logs folder on a connected drive, so the history is complete as far as the reports go.
"""

import re
from datetime import datetime
from pathlib import Path

from . import config

BACKUP, IMPORT = "backup", "import"
MAX_ENTRIES = 1000


RUNNING = "RUNNING"          # status while a run is going on – left behind if it never finished


def record(cfg, key, kind, when, source, files, size, status, drives=()):
    """Add a run – or complete the RUNNING entry of the same run (see start())."""
    if isinstance(when, datetime):
        when = when.isoformat(timespec="seconds")
    lst = cfg.setdefault("backup_history", {}).setdefault(key, [])
    entry = {"when": when, "kind": kind, "source": str(source), "files": int(files),
             "bytes": int(size), "status": str(status), "drives": [str(d) for d in drives]}
    same = [i for i, e in enumerate(lst) if e.get("when") == when and e.get("kind") == kind]
    if same:
        lst[same[-1]] = entry
    else:
        lst.append(entry)
    del lst[:-MAX_ENTRIES]
    config.save(cfg)


def start(cfg, key, kind, when, source, drives=()):
    """A run begins: if the program stops before record() (crash, power cut, closed), the history
    shows it as not finished."""
    record(cfg, key, kind, when, source, 0, 0, RUNNING, drives)


def unfinished(entries_):
    """Runs that were started but did not finish normally (interrupted, cancelled, failed)."""
    return [e for e in entries_ if not str(e.get("status", "")).startswith("COMPLETED")]


# ------------------------------------------------------------------ old runs from the reports

_FIELDS = ("Smartphone", "Status", "Started", "Imported folder", "Connection", "Total secured this run")


def _read_fields(text):
    from .phoneid import report_labels
    out = {}
    for en in _FIELDS:
        m = re.search(r"^\s*(?:%s)\s*:\s*(.+?)\s*$" % report_labels(en), text, re.M)
        if m:
            out[en] = m.group(1)
    return out


def _numbers(total):
    """'12 files, 48.3 MB (50,612,345 bytes)' (any language) -> (12, 50612345)."""
    m = re.match(r"\s*(\d+)", total or "")
    files = int(m.group(1)) if m else 0
    b = re.search(r"\(([\d,.\s  ']+)[^()]*\)\s*$", total or "")
    size = int(re.sub(r"\D", "", b.group(1)) or 0) if b else 0
    return files, size


def from_report(path, drive=""):
    """One history entry read from a report .txt (None if it is not a backup/import report)."""
    from .report import english
    name = Path(path).name
    kind = IMPORT if name.startswith("Import ") else BACKUP if name.startswith("Backup ") else None
    if kind is None:
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            fields = _read_fields(f.read(20000))
    except OSError:
        return None
    started = fields.get("Started", "")
    try:
        when = datetime.strptime(started[:19], "%Y-%m-%d %H:%M:%S").isoformat(timespec="seconds")
    except ValueError:
        return None
    if kind == IMPORT:
        source = fields.get("Imported folder", "")
    else:
        source = fields.get("Smartphone", "")
        conn = fields.get("Connection", "").split(" - ")[0].strip()
        if conn:
            source = f"{source} ({conn})" if source else conn
    files, size = _numbers(fields.get("Total secured this run", ""))
    return {"when": when, "kind": kind, "source": source, "files": files, "bytes": size,
            "status": english(fields.get("Status", "")), "drives": [str(drive)] if drive else []}


def from_reports(set_dirs):
    """Entries from the reports of the backup's folders <drive>/<Owner>/<Phone> on the connected
    drives (also those in the run folders of a Grandfather-Father-Son plan)."""
    from .report import LOGS_DIR, report_files
    out = []
    for d in set_dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        folders = [d] + [r for r in _subdirs(d) if (r / LOGS_DIR).is_dir()]
        for folder in folders:
            for pattern in ("Backup *.txt", "Import *.txt"):
                for p in report_files(folder, pattern):
                    e = from_report(p, d.parent.parent)
                    if e:            # every report (it was only the last one – and an error when
                        out.append(e)    # a folder had none, user 2026-11-23)
    return out


def _subdirs(d):
    try:
        return [p for p in d.iterdir() if p.is_dir() and not p.name.startswith(".")]
    except OSError:
        return []


def entries(cfg, key, set_dirs=(), newest_first=True, reports=None):
    """The history of a backup: remembered runs plus runs only known from reports. The same run
    (same kind, same start minute) on several drives is listed once, with all its drives.
    reports = from_reports(...) read before (drivescan, in the background) – then no drive is read."""
    merged = {}
    if reports is None:
        reports = from_reports(set_dirs)
    cut = cut_of(cfg, key)
    for e in list((cfg.get("backup_history") or {}).get(key, [])) + list(reports):
        if cut and e.get("when", "") <= cut:          # deleted from the history (user 2026-11-23)
            continue
        k = (e["kind"], e["when"][:16])
        if k not in merged:
            merged[k] = dict(e, drives=list(e.get("drives", [])))
        else:
            have = merged[k]["drives"]
            have += [d for d in e.get("drives", []) if d not in have]
    order = list(enumerate(merged.values()))    # runs started in the same second keep their order
    order.sort(key=lambda x: (x[1]["when"], x[0]), reverse=newest_first)
    return [e for _, e in order]


# ---- deleting the history (user request 2026-11-23): everything up to and including a date. The
# entries the program keeps are deleted; the reports in the drives' Logs folders stay (they also
# record the photos' checksums) – entries read from them up to that date are not shown any more.

def cut_of(cfg, key):
    """'2026-11-20T23:59:59' – entries up to this moment are deleted ('' = none)."""
    return ((cfg.get("history_cut") or {}).get(key)) or ""


def delete_up_to(cfg, key, day):
    """Delete the history of backup `key` up to and including `day` ('2026-11-20'); None = all.
    Returns what undo_delete() needs: (the cut before, the deleted entries)."""
    before = cut_of(cfg, key)
    cut = (day + "T23:59:59") if day else datetime.now().isoformat(timespec="seconds")
    cut = max(cut, before)
    cfg.setdefault("history_cut", {})[key] = cut
    runs = (cfg.get("backup_history") or {}).get(key)
    removed = []
    if runs is not None:
        removed = [e for e in runs if e.get("when", "") <= cut]
        cfg["backup_history"][key] = [e for e in runs if e.get("when", "") > cut]
    config.save(cfg)
    return before, removed


def undo_delete(cfg, key, step):
    """Undo one delete_up_to() (user request 2026-11-23)."""
    before, removed = step
    if before:
        cfg.setdefault("history_cut", {})[key] = before
    else:
        (cfg.get("history_cut") or {}).pop(key, None)
    if removed:
        runs = cfg.setdefault("backup_history", {}).setdefault(key, [])
        runs.extend(e for e in removed if e not in runs)
        runs.sort(key=lambda e: e.get("when", ""))
    config.save(cfg)
