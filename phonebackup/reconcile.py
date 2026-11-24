"""Backup folders the program does not fully know, and backup drives added later (user request
2026-11-22). No Qt here.

1. Folder not completely known ("adopt")
   A backup folder can hold files that are not in its index (.phonebackup/index.sqlite): the folder
   was copied by hand, the index was lost, or it was made by another program. Before such files
   are copied from the phone again, the phone's file list is compared with the folder:

   * the folder's own reports (Logs/*.csv) name, for every file written, the phone path, the size,
     the SHA-256 and the place in the backup → the strongest hint (the exact phone path);
   * otherwise a file with the same name and size in the folder is a candidate;
   * a candidate's SHA-256 comes from the report (size must match) or is calculated from the file;
   * when the connection can hash on the phone (USB/Wi-Fi debugging, phone app) the phone's
     SHA-256 must be the same, otherwise name + size (+ report) decide.
   Accepted files get index rows: they count as backed up and are not copied again.
   Only done when the folder has files outside the index and the phone has files that are not in
   the index – a fully known folder costs nothing.

2. A backup drive added later ("fill")
   The new photos and videos from the phone are written to all drives at the same time (as before).
   Files that another drive of the same backup already has are NOT read from the phone again for
   the new drive; after the phone part, every file the other drive has and this drive is missing is
   copied drive → drive: written as a temporary file, flushed, read back, SHA-256 compared with the
   source file and with the index of the source drive; only then renamed into place. A source file
   whose hash no longer matches its index is reported and NOT copied (damaged copy).
"""

import csv
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import ui
from .copier import Cancelled, file_chunks, sha256_file, stream_copy
from .i18n import tr, trp
from .index import INTERNAL_DIR
from .layout import safe_name, unique_path
from .report import LOGS_DIR

EXPORT_DIR = ".phonebackup-export"
_SHA = re.compile(r"^[0-9a-f]{64}$")
# fixed columns of a backup report (backup._write_backup_reports); per destination 2 more
COL_BYTES, COL_PATH, COL_SHA, FIRST_DEST = 4, 7, 9, 10


# ----------------------------------------------------------------------------- report facts

@dataclass
class Fact:
    phone_path: str        # "" for imports (their key is not the shown path)
    size: int
    sha: str


def _cell(v):
    """Undo safety.csv_cell (formula guard) on a report cell."""
    v = (v or "").strip()
    if len(v) > 1 and v[0] == "'" and v[1] in "=+-@\t\r":
        return v[1:]
    return v


def report_csvs(set_dir):
    set_dir = Path(set_dir)
    return list((set_dir / LOGS_DIR).glob("*.csv")) + list(set_dir.glob("*.csv"))


def log_facts(set_dir, files=None):
    """{location in the backup: [Fact]} from every report CSV of the folder (Logs/ and, for old
    backups, next to the year folders) – or only from `files`. Columns are read by position – the
    headers are in the language of the computer that wrote the report."""
    out = {}
    files = report_csvs(set_dir) if files is None else files
    for p in files:
        importing = p.name.startswith("Import ")
        try:
            with open(p, encoding="utf-8-sig", newline="", errors="replace") as f:
                rows = list(csv.reader(f, delimiter=";"))
        except OSError:
            continue
        if len(rows) < 2 or len(rows[0]) < FIRST_DEST + 2:
            continue
        n_dest = (len(rows[0]) - FIRST_DEST) // 2
        for row in rows[1:]:
            if len(row) < FIRST_DEST + 2 * n_dest:
                continue
            sha = _cell(row[COL_SHA]).lower()
            try:
                size = int(_cell(row[COL_BYTES]))
            except ValueError:
                continue
            if not _SHA.match(sha):
                continue
            fact = Fact("" if importing else _cell(row[COL_PATH]), size, sha)
            for k in range(n_dest):
                loc = _cell(row[FIRST_DEST + 2 * k + 1]).replace("\\", "/")
                if loc and not loc.startswith(("/", "..")) and ".." not in loc.split("/"):
                    lst = out.setdefault(loc, [])
                    if fact not in lst:
                        lst.append(fact)
    return out


# ----------------------------------------------------------------------------- folder scan

def _skip_dir(rel_dir, name):
    return name.startswith(".") or (not rel_dir and name == LOGS_DIR)


def folder_files(set_dir):
    """{rel: (size, mtime)} of every file in the backup folder (not .phonebackup*, not Logs/)."""
    set_dir = Path(set_dir)
    out = {}
    for dirpath, dirnames, filenames in os.walk(set_dir):
        rel_dir = Path(dirpath).relative_to(set_dir).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        dirnames[:] = sorted(d for d in dirnames if not _skip_dir(rel_dir, d))
        for fn in filenames:
            if fn.startswith(".") or (not rel_dir and fn.lower().endswith((".txt", ".html", ".csv"))
                                      and fn.startswith(("Backup ", "Import "))):
                continue
            full = os.path.join(dirpath, fn)
            try:
                st = os.stat(full)
            except OSError:
                continue
            out[f"{rel_dir}/{fn}" if rel_dir else fn] = (st.st_size, int(st.st_mtime))
    return out


def indexed_rels(index):
    return {r for (r,) in index.db.execute("SELECT DISTINCT rel_path FROM files")}


def unknown_files(set_dir, index):
    """Files in the folder that the index does not know: {rel: (size, mtime)}."""
    known = indexed_rels(index)
    return {r: v for r, v in folder_files(set_dir).items() if r not in known}


@dataclass
class Adopted:
    found: int = 0             # phone files recognised in the folder
    by_log: int = 0            # … of them with the phone path from a report
    by_phone_hash: int = 0     # … confirmed with the SHA-256 calculated on the phone
    hashed: int = 0            # backup files whose SHA-256 had to be calculated
    rejected: int = 0          # same name + size, but a different SHA-256
    unknown: int = 0           # files in the folder that the index did not know


def adopt(dest, pending, source, cancel=None):
    """Recognise phone files in a folder that is not completely known.

    pending: [(SourceFile, category)] that dest's index does not have. Returns (Adopted,
    set of SourceFile.source_key recognised); the index rows are added to dest.index."""
    stats = Adopted()
    got = set()
    if not pending:
        return stats, got
    set_dir = Path(dest.home)
    unknown = unknown_files(set_dir, dest.index)
    stats.unknown = len(unknown)
    if not unknown:
        return stats, got
    ui.info("  " + trp("%s: %d file in the backup folder is not in its list yet – comparing it with "
                       "the phone's files …",
                       "%s: %d files in the backup folder are not in its list yet – comparing them "
                       "with the phone's files …", len(unknown), _label(dest), len(unknown)))
    facts = log_facts(set_dir)
    by_name = {}
    for rel, (size, _m) in unknown.items():
        by_name.setdefault((rel.rsplit("/", 1)[-1].casefold(), size), []).append(rel)
    by_phone_path = {}
    for loc, lst in facts.items():
        if loc in unknown:
            for f in lst:
                if f.phone_path and f.size == unknown[loc][0]:
                    by_phone_path.setdefault((f.phone_path, f.size), []).append((loc, f.sha))

    cands = []                     # (sf, cat, rel, sha or None, from_log)
    used = set()
    for sf, cat in pending:
        hit = None
        for loc, sha in by_phone_path.get((sf.rel, sf.size), []):
            if loc not in used:
                hit = (loc, sha, True)
                break
        if hit is None:
            for loc in by_name.get((safe_name(sf.name).casefold(), sf.size), []):
                if loc not in used:
                    sha = next((f.sha for f in facts.get(loc, []) if f.size == sf.size), None)
                    hit = (loc, sha, False)
                    break
        if hit is not None:
            used.add(hit[0])
            cands.append((sf, cat) + hit)
    if not cands:
        return stats, got

    phone = {}
    if getattr(source, "supports_phone_hash", False):
        try:
            for i in range(0, len(cands), 200):
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                phone.update(source.phone_hashes([c[0].rel for c in cands[i:i + 200]]) or {})
        except Cancelled:
            raise
        except Exception as e:  # noqa: BLE001 - without phone hashes: name + size + backup hash
            ui.warn("  " + tr("The phone could not calculate the SHA-256 (%s) – files are recognised "
                              "by name, size and the backup's own hash.", e))
            phone = {}
    for sf, cat, rel, sha, from_log in cands:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        if sha is None:
            try:
                sha = sha256_file(set_dir / rel, cancel)
            except OSError:
                continue
            stats.hashed += 1
        ph = phone.get(sf.rel)
        if ph is not None and ph != sha:
            stats.rejected += 1
            continue
        mtime = unknown[rel][1]
        dest.index.add(sf.source_key, sf.size, sf.mtime or mtime, sha, rel, cat, None,
                       "found in the backup folder")
        got.add(sf.source_key)
        stats.found += 1
        stats.by_log += bool(from_log)
        stats.by_phone_hash += ph is not None
    dest.index.commit()
    if stats.found:
        how = []
        if stats.by_phone_hash:
            how.append(tr("%d checked with the SHA-256 on the phone", stats.by_phone_hash))
        if stats.by_log:
            how.append(tr("%d with the phone path from the backup's reports", stats.by_log))
        ui.ok("  " + trp("%s: %d photo/video of the phone is already in the backup folder – not copied again",
                         "%s: %d photos/videos of the phone are already in the backup folder – not copied again",
                         stats.found, _label(dest), stats.found)
              + (f" ({'; '.join(how)})" if how else "") + ".")
    if stats.rejected:
        ui.warn("  " + trp("%s: %d file has the same name and size as a phone file but different content – "
                           "the phone's file is copied (the old one stays).",
                           "%s: %d files have the same name and size as a phone file but different content – "
                           "the phone's files are copied (the old ones stay).",
                           stats.rejected, _label(dest), stats.rejected))
    return stats, got


def _label(dest):
    from .report import shown
    return str(shown(dest.label))


# ----------------------------------------------------------------------------- second drive

def simple(d):
    return getattr(d, "plan", "simple") == "simple"


def held_by_other(dests, d, sf):
    """Another (simple, connected) drive of this backup already has the phone file → the new
    drive gets it drive to drive after the phone part, not from the phone."""
    if not simple(d):
        return False
    return any(e is not d and e.alive and simple(e) and e.index.has(sf.source_key, sf.size)
               for e in dests)


@dataclass
class Filled:
    source_label: str = ""
    copied: int = 0
    bytes: int = 0
    already: int = 0           # the file was there (index or same hash) – only the list was updated
    errors: list = field(default_factory=list)   # (rel, reason)


def _rows_for(index, rel):
    """The list entries of a place, the OLDEST first (ORDER BY rowid): a place can have an old entry
    with other content (e.g. an import of an old drive, then a new backup from the phone with the
    same name and size – user 2026-11-23: 19 RAW files were called "damaged" because the old
    entry's SHA-256 was taken). The newest entry is the last one."""
    return index.db.execute("SELECT source_path, size, mtime, sha256, rel_path, category, taken, "
                            "date_source FROM files WHERE rel_path=? ORDER BY rowid", (rel,)).fetchall()


def _add_rows(index, rows, rel):
    from datetime import datetime
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    for r in rows:
        index.db.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?,?)",
                         (r[0], r[1], r[2], r[3], rel, r[5], r[6], r[7], now))
    index._maybe_commit()


def fill_plan(src, dst):
    """[(rel, size, mtime)] of files in src's backup folder that dst may be missing."""
    have = indexed_rels(dst.index)
    # only content that is REALLY on dst counts: a file in dst's list that was deleted from the
    # drive must be copied back (UI test 2026-11-23: "4 missing" promised, 1 copied)
    dst_files = folder_files(dst.home)
    dst_shas = {sha for rel, sha in dst.index.db.execute("SELECT rel_path, sha256 FROM files")
                if rel in dst_files}
    src_sha = {}
    for rel, size, sha in src.index.db.execute("SELECT rel_path, size, sha256 FROM files ORDER BY rowid"):
        src_sha[(rel, size)] = sha
    sizes = {size for (rel, size), sha in src_sha.items() if sha in dst_shas}   # content sizes on dst
    todo = []
    for rel, (size, mtime) in sorted(folder_files(src.home).items()):
        if rel in have and (Path(dst.home) / rel).is_file():
            continue
        sha = src_sha.get((rel, size))
        if sha is not None and sha in dst_shas:
            continue                          # same content on dst under another name
        if sha is None:                       # not in src's list: same place + size on dst = there
            if dst_files.get(rel, (None,))[0] == size:
                continue
            if size in sizes:                 # maybe a copy of content dst has: read only these
                try:
                    sha = sha256_file(Path(src.home) / rel)
                except OSError:
                    sha = None
                if sha is not None and sha in dst_shas:
                    continue
        if sha is not None:                   # a duplicate on src is not spread to dst (2026-11-23)
            dst_shas.add(sha)
            sizes.add(size)
        todo.append((rel, size, mtime))
    return todo


def fill_from(src, dst, cfg, cancel=None, prog=None, plan=None, done_before=0):
    """Copy every file of src's backup folder that dst is missing (drive → drive, verified)."""
    from .backup import _check_dest_alive, _remove
    res = Filled(source_label=_label(src))
    plan = fill_plan(src, dst) if plan is None else plan
    tmp_dir = Path(dst.home) / INTERNAL_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for i, (rel, size, mtime) in enumerate(plan):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        if prog is not None and i:
            prog.update(files_done=done_before + i)
        if not (src.alive and dst.alive):
            res.errors.append((rel, dst.problem or src.problem or tr("drive not reachable")))
            continue
        src_file = Path(src.home) / rel
        rows = _rows_for(src.index, rel)
        want = next((r[3] for r in reversed(rows) if r[1] == size), None)   # the NEWEST entry's SHA-256
        if prog is not None:                    # "IMG_1.jpg → MMMB_Vol.2" (user 2026-11-23)
            prog.update(current=f"{src_file.name} → {_label(dst)}")
        try:
            if want:
                there = dst.index.find_by_sha(want)
                if there:                       # same content already on dst (other name/place)
                    _add_rows(dst.index, rows, there)
                    res.already += 1
                    if prog is not None:
                        prog.update(add_bytes=size)
                    continue
            final = Path(dst.home) / rel
            if final.exists():
                same = final.stat().st_size == size and (want or sha256_file(src_file, cancel)) == sha256_file(final, cancel)
                if same:
                    _add_rows(dst.index, rows, rel)
                    res.already += 1
                    if prog is not None:
                        prog.update(add_bytes=size)
                    continue
                final = unique_path(final)
            t = tmp_dir / f"{uuid.uuid4().hex}.part"
            counted = [0]

            def on_bytes(n, counted=counted):
                counted[0] += n
                if prog is not None:
                    prog.update(add_bytes=n)
            stream_sha, n, wres = stream_copy(file_chunks(src_file), [t], fsync=cfg.get("fsync", True),
                                              on_bytes=on_bytes, cancel=cancel)
            w = wres[0]
            problem = None
            if n != size:
                problem = tr("incomplete read (%d of %d bytes)", n, size)
            elif want and stream_sha != want:
                problem = tr("the file on %s is damaged (its SHA-256 differs from the backup list) – "
                             "not copied", res.source_label)
            elif w.error:
                problem = tr("write failed (%s)", w.error)
            elif w.sha256 != stream_sha:
                problem = tr("verification failed (hash of written copy differs)")
            if problem:
                _remove(t)
                res.errors.append((rel, problem))
                if prog is not None:
                    prog.bytes -= counted[0]
                _check_dest_alive(dst)
                continue
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(t, final)
            try:
                os.utime(final, (mtime, mtime))
            except OSError:
                pass
            new_rel = final.relative_to(dst.home).as_posix()
            if rows:
                _add_rows(dst.index, rows, new_rel)
            dst.on_written(new_rel, size, mtime, stream_sha)
            res.copied += 1
            res.bytes += size
        except Cancelled:
            raise
        except OSError as e:
            res.errors.append((rel, str(e)))
            _check_dest_alive(dst)
    dst.index.commit()
    return res


def fill_all(dests, cfg, cancel=None, targets=None):
    """Make every connected simple drive of the backup hold every file of the others (only the
    drives in `targets`, if given). Returns {dest: [Filled, ...]}."""
    out = {}
    simple_dests = [d for d in dests if simple(d)]
    if len(simple_dests) < 2:
        return out
    pairs = []
    for dst in simple_dests:
        if targets is not None and dst not in targets:
            continue
        for src in simple_dests:
            if src is dst or not (src.alive and dst.alive):
                continue
            plan = fill_plan(src, dst)
            if plan:
                pairs.append((src, dst, plan))
    if not pairs:
        return out
    from .backup import MIN_FREE
    import shutil
    total_n = sum(len(p) for _s, _d, p in pairs)
    total_b = sum(sz for _s, _d, p in pairs for _r, sz, _m in p)
    ui.info(trp("Backup drives of this backup are completed from each other: %d file (%s) to check/copy …",
                "Backup drives of this backup are completed from each other: %d files (%s) to check/copy …",
                total_n, total_n, ui.human_size(total_b)))
    for src, dst, plan in pairs:
        need = sum(sz for _r, sz, _m in plan)
        try:
            free = shutil.disk_usage(dst.home).free
        except OSError:
            free = 0
        if need > free - MIN_FREE:
            ui.warn("  " + tr("%s has only %s free, %s are missing there – it is filled until it is full.",
                              _label(dst), ui.human_size(free), ui.human_size(need)))
    prog = ui.Progress(total_n, total_b)
    done = 0
    try:
        for src, dst, plan in pairs:
            r = fill_from(src, dst, cfg, cancel, prog, plan, done)
            done += len(plan)
            prog.update(files_done=done)
            out.setdefault(dst, []).append(r)
            if r.copied or r.already:
                ui.ok("  " + tr("%s: %d files (%s) copied from %s and verified with SHA-256%s.",
                                _label(dst), r.copied, ui.human_size(r.bytes), r.source_label,
                                tr(", %d were already there", r.already) if r.already else ""))
            for rel, why in r.errors[:20]:
                ui.warn("  " + tr("%s: %s – %s", _label(dst), rel, why))
            if len(r.errors) > 20:
                ui.warn("  " + tr("… and %d more errors", len(r.errors) - 20))
    finally:
        prog.finish()
    return out


# ----------------------------------------------------------------------------- without the phone

def update_drives(bases, rel, cfg, targets=None, cancel=None):
    """"Update from the other drive" (user request 2026-11-22): the backup drives `targets` (default:
    all) get every file the other connected drives of the backup have – drive to drive, verified –
    without the phone. Writes a report into each updated drive's Logs folder.
    Returns (status, {base: [Filled]}, problems) – status English: COMPLETED / CANCELLED by user /
    COMPLETED WITH ERRORS."""
    from datetime import datetime
    from . import plans
    from .backup import Dest
    from .index import BackupIndex
    started = datetime.now()
    targets = [str(t) for t in (targets or bases)]
    dests, problems = [], []
    for base in bases:
        base = str(base)
        set_dir = Path(base) / rel
        if not Path(base).is_dir():
            continue
        if plans.folder_plan(set_dir) == plans.GFS:
            problems.append(tr("%s uses the Grandfather-Father-Son plan – it is not updated this way.", base))
            continue
        if not set_dir.is_dir() and base not in targets:
            continue
        set_dir.mkdir(parents=True, exist_ok=True)
        label = Path(base).name or base
        dests.append(Dest(label, Path(base), set_dir, BackupIndex(set_dir)))
    want = [d for d in dests if str(d.base) in targets]
    status, filled = "COMPLETED", {}
    try:
        if len(dests) < 2:
            problems.append(tr("At least two connected backup drives of this backup are needed."))
        else:
            filled = fill_all(dests, cfg, cancel, targets=want)
            if not filled:
                ui.ok(tr("The backup drives are already up to date – nothing to copy."))
    except (KeyboardInterrupt, Cancelled):
        status = "CANCELLED by user"
    finally:
        for d in dests:
            import shutil
            shutil.rmtree(d.tmp, ignore_errors=True)
            d.index.close()
    errors = sum(len(r.errors) for lst in filled.values() for r in lst)
    if status == "COMPLETED" and (errors or problems):
        status = "COMPLETED WITH ERRORS"
    out = {str(d.base): lst for d, lst in filled.items()}
    for d, lst in filled.items():
        _drive_report(d, lst, started, status)
    return status, out, problems


def _drive_report(d, lst, started, status):
    from datetime import datetime
    from .report import logs_dir, unique_basename, write_reports
    ok = status == "COMPLETED"
    copied = sum(r.copied for r in lst)
    size = sum(r.bytes for r in lst)
    errors = [(r.source_label, rel, why) for r in lst for rel, why in r.errors]
    verdict = (tr("EVERYTHING COPIED CORRECTLY - %d files (%s) copied from the other backup drive and verified "
                  "with SHA-256.", copied, ui.human_size(size)) if not errors else
               tr("ATTENTION - %d files could not be copied from the other backup drive", len(errors)))
    general = [(tr("Backup drive"), str(d.base)), (tr("Backup folder"), str(d.home)),
               (tr("Started"), f"{started:%Y-%m-%d %H:%M:%S}"),
               (tr("Finished"), f"{datetime.now():%Y-%m-%d %H:%M:%S}"), (tr("Status"), status)]
    for r in lst:
        general.append((tr("Copied from %s", r.source_label),
                        tr("%d files, %s – read back and SHA-256 compared; %d were already there; %d errors",
                           r.copied, ui.human_size(r.bytes), r.already, len(r.errors))))
    rows = [[i, src, rel, why] for i, (src, rel, why) in enumerate(errors, 1)]
    try:
        rdir = logs_dir(d.home)
        base = unique_basename(rdir, "Drive update", started)
        write_reports(rdir, base, tr("Update from the other backup drive - %s", f"{started:%Y-%m-%d %H:%M}"),
                      ok and not errors, verdict, [(tr("General"), general)],
                      [tr("Nr"), tr("From"), tr("File"), tr("Problem")], rows)
    except OSError as e:
        ui.warn(tr("Could not write report to %s: %s", d.home, e))
