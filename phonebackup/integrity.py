"""Integrity check of a backup folder (user request 2026-11-23): every photo and video is read
completely, its SHA-256 compared with the one on record, the result written as a report into
the folder's Logs, and – if wanted – the new checksums saved in the program's own table
(.phonebackup/checked.sqlite, knownhash). The backup's list (index) is never changed: its SHA-256
from the time of the backup stays as the evidence when a file has changed.

On record, the first that knows the place wins:
  list     the backup's list – newest entry of the place with the same size (also when the
           file's time changed: a changed file is exactly what the check is for)
  report   the report CSVs in its Logs folder (one SHA-256 for this place and size)
  checked  an earlier check / "Check backup folder…" (same size)
A backup folder inside the backup folder is looked up in its own list and reports.

No Qt here.
"""

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import knownhash
from .copier import HashCancelled, sha256_file
from .i18n import tr

OK, CHANGED, NEW, GONE, UNREADABLE = "ok", "changed", "new", "gone", "unreadable"


@dataclass
class Result:
    set_dir: str
    ok: int = 0
    bytes: int = 0
    changed: list = field(default_factory=list)      # [(rel, expected, actual, source)]
    new: list = field(default_factory=list)          # [rel] – no SHA-256 on record before
    gone: list = field(default_factory=list)         # [rel] – in the list, but no file
    unreadable: list = field(default_factory=list)   # [(rel, why)]
    rows: list = field(default_factory=list)         # [(rel, sha, size, mtime)] measured now
    cancelled: bool = False
    report: str = ""

    @property
    def checked(self):
        return self.ok + len(self.changed) + len(self.new)


def expected(set_dir, files):
    """{rel: (sha, source)} on record for the media `files` ({rel: (size, mtime)})."""
    set_dir = Path(set_dir)
    inner = knownhash._inner_sets(set_dir)
    sources = {}
    checked = knownhash.checked_rows(set_dir)
    out = {}
    for rel, (size, mtime) in files.items():
        base, sub = set_dir, rel
        for prefix, path in inner:
            if rel.startswith(prefix):
                base, sub = path, rel[len(prefix):]
                break
        key = str(base)
        if key not in sources:
            sources[key] = (knownhash._list_rows(base), knownhash._report_rows(base))
        lst, reps = sources[key]
        got = lst.get(sub)
        if got and got[1] == size:
            out[rel] = (got[0], "list")
            continue
        shas = {sha for sha, sz, _w in reps.get(sub, []) if sz == size}
        if len(shas) == 1:
            out[rel] = (shas.pop(), "report")
            continue
        got = checked.get(rel)
        if got and got[1] == size:
            out[rel] = (got[0], "checked")
    return out


def gone_from_list(set_dir, files):
    """Media places named in the backup's list (newest entry) whose file is not there."""
    rows = knownhash._list_rows(set_dir)
    return sorted(rel for rel in rows if knownhash.is_media(rel.rsplit("/", 1)[-1]) and rel not in files)


def run(set_dir, cancel=None, progress=None):
    """Read every photo and video of the folder and compare. progress(files_done, files_total,
    bytes_done, bytes_total, path). Nothing is changed (see save())."""
    set_dir = Path(set_dir)
    res = Result(str(set_dir))
    files = knownhash.media_files(set_dir)
    want = expected(set_dir, files)
    res.gone = gone_from_list(set_dir, files)
    total = sum(size for size, _m in files.values())
    done = 0
    for i, (rel, (size, mtime)) in enumerate(sorted(files.items()), 1):
        if cancel is not None and cancel.is_set():
            res.cancelled = True
            break
        try:
            sha = sha256_file(set_dir / rel, cancel)
        except HashCancelled:
            res.cancelled = True
            break
        except OSError as e:
            res.unreadable.append((rel, str(e)))
            continue
        done += size
        res.rows.append((rel, sha, size, mtime))
        exp = want.get(rel)
        if exp is None:
            res.new.append(rel)
        elif exp[0] == sha:
            res.ok += 1
            res.bytes += size
        else:
            res.changed.append((rel, exp[0], sha, exp[1]))
        if progress:
            progress(i, len(files), done, total, str(set_dir / rel))
    return res


def save(res):
    """The checksums measured now into the program's own table (knownhash.remember). Files that
    do NOT match their record are saved too (as what they are now) – the backup's list keeps the
    original SHA-256, so the difference stays visible."""
    if res.rows:
        knownhash.remember(res.set_dir, res.rows)


def write_report(res, when=None):
    """Integrity check <date>.txt + .csv in the folder's Logs. Returns the txt path."""
    from .report import LOGS_DIR, unique_basename
    when = when or datetime.now()
    logs = Path(res.set_dir) / LOGS_DIR
    logs.mkdir(parents=True, exist_ok=True)
    base = unique_basename(logs, "Integrity check", when)
    lines = [tr("Integrity check – %s", when.strftime("%Y-%m-%d %H:%M")), "=" * 50, "",
             tr("Backup folder : %s", res.set_dir),
             tr("Status        : %s", tr("cancelled – not complete") if res.cancelled else tr("complete")),
             tr("Unchanged     : %d", res.ok),
             tr("CHANGED       : %d (the content is not the one on record)", len(res.changed)),
             tr("No record yet : %d (read now; checksum saved if chosen)", len(res.new)),
             tr("Missing       : %d (in the backup's list, but no file)", len(res.gone)),
             tr("Unreadable    : %d", len(res.unreadable)), ""]
    for title, items in ((tr("CHANGED"), [f"{r}  (on record {e[:16]}… from the {s}, now {a[:16]}…)"
                                          for r, e, a, s in res.changed]),
                         (tr("Missing"), res.gone),
                         (tr("Unreadable"), [f"{r}: {w}" for r, w in res.unreadable]),
                         (tr("No record yet"), res.new)):
        if items:
            lines += [f"{title} ({len(items)})", "-" * 40] + [f"  {x}" for x in items] + [""]
    txt = logs / f"{base}.txt"
    txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(logs / f"{base}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([tr("Result"), tr("File"), tr("SHA-256 on record"), tr("SHA-256 now"), tr("Recorded in")])
        for r, e, a, s in res.changed:
            w.writerow([CHANGED, r, e, a, s])
        for r in res.gone:
            w.writerow([GONE, r, "", "", "list"])
        for r, why in res.unreadable:
            w.writerow([UNREADABLE, r, "", why, ""])
        for r in res.new:
            w.writerow([NEW, r, "", next((s for rr, s, _z, _m in res.rows if rr == r), ""), ""])
    res.report = str(txt)
    return str(txt)


def summary(res):
    """One short text for a message box."""
    parts = [tr("%s photos and videos unchanged", f"{res.ok:,}")]
    if res.changed:
        parts.append(tr("%s CHANGED (not the content on record)", f"{len(res.changed):,}"))
    if res.gone:
        parts.append(tr("%s in the list but missing", f"{len(res.gone):,}"))
    if res.new:
        parts.append(tr("%s had no checksum on record yet", f"{len(res.new):,}"))
    if res.unreadable:
        parts.append(tr("%s could not be read", f"{len(res.unreadable):,}"))
    if res.cancelled:
        parts.append(tr("cancelled – not every file was read"))
    return ", ".join(parts) + "."
