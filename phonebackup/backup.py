"""The incremental phone -> external drive(s) backup run."""

import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import ui
from .i18n import N_, tr, trp
from .copier import Cancelled, sha256_file, stream_copy
from .index import INTERNAL_DIR, BackupIndex
from .layout import keep_structure_placement, relative_dir, safe_name, unique_path
from .media import CATEGORY_LABEL, category_for, detect_date
from .report import both, logs_dir, shown, unique_basename, write_reports
from .sources import PhoneHasher

MIN_FREE = 50 * 1024 * 1024     # a drive with less free space than this counts as full
MAX_ATTEMPTS = 3


@dataclass(eq=False)
class Dest:
    label: str
    base: Path
    parent: Path
    index: BackupIndex
    alive: bool = True
    problem: str = ""
    written: int = 0
    written_bytes: int = 0
    errors: int = 0

    plan = "simple"

    @property
    def home(self):
        """The backup folder ('Phone - Owner'); for a GFS plan the run folder is `parent`."""
        return self.parent

    @property
    def report_dir(self):
        return self.parent

    @property
    def tmp(self):
        return self.home / INTERNAL_DIR / "tmp"

    def existing(self, final):
        """The file already at this place in the backup (None if free)."""
        return final if Path(final).exists() else None

    def on_written(self, rel, size, mtime, sha):
        pass


@dataclass
class FileResult:
    sf: object
    category: str
    taken: datetime = None
    date_source: str = ""
    sha: str = ""
    transfer_check: str = ""
    per_dest: dict = field(default_factory=dict)   # label -> (status, location)

    @property
    def ok(self):
        return bool(self.per_dest) and all(not s.startswith("ERROR") for s, _ in self.per_dest.values())

    @property
    def newly_written(self):
        return any(s.startswith("OK") for s, _ in self.per_dest.values())


def _skip_text(source, default=N_("not photo/video")):
    """Why other files are skipped (English in the source object, shown translated)."""
    return tr(getattr(source, "skip_text", default))


def backup_parent_name(phone_name, owner):
    """The backup's NAME in the settings ('Pixel 10 Pro - Sam'). Its folder is
    setfolders.rel(): <Owner>/<Phone> (user request 2026-11-09)."""
    return safe_name(f"{phone_name} - {owner}")


def _check_dest_alive(d):
    try:
        if not d.home.is_dir():
            d.alive, d.problem = False, both.tr("drive disconnected or folder no longer reachable")
        elif shutil.disk_usage(d.home).free < MIN_FREE:
            d.alive, d.problem = False, both.tr("drive is full")
    except OSError as e:
        d.alive, d.problem = False, both.tr("drive error: %s", e)


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _copy_one(source, sf, cat, targets, hasher, cfg, prog, cancel=None, placement=None):
    res = FileResult(sf=sf, category=cat)
    stream_sha, wres, last_err = None, None, ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        temps = [d.tmp / f"{uuid.uuid4().hex}.part" for d in targets]
        counted = [0]

        def on_bytes(n):
            counted[0] += n
            prog.update(add_bytes=n, current=sf.name)

        try:
            stream_sha, n, wres = stream_copy(source.open_stream(sf), temps,
                                              fsync=cfg.get("fsync", True), on_bytes=on_bytes,
                                              cancel=cancel)
        except Cancelled:
            for t in temps:
                _remove(t)
            raise
        except Exception as e:  # noqa: BLE001
            if getattr(e, "abort_backup", False):    # the connection hangs: stop, not file after file
                for t in temps:
                    _remove(t)
                raise
            stream_sha, n, wres = None, -1, None
            last_err = both.tr("reading from the source failed: %s", e)
        if stream_sha is not None and n != sf.size:
            last_err = both.tr("incomplete transfer (%d of %d bytes)", n, sf.size)
            stream_sha = None
        if stream_sha is not None and hasher is not None:
            phone_sha = hasher.get(sf.rel)
            if phone_sha is None:
                res.transfer_check = both.tr("n/a (source could not hash this file)")
            elif phone_sha != stream_sha:
                last_err = both.tr("MISMATCH between source hash and received data")
                stream_sha = None
            else:
                res.transfer_check = both.tr("OK (SHA-256 at source = received)")
        elif stream_sha is not None:
            res.transfer_check = both.tr("n/a (%s: no hash on the phone; copies compared with "
                                         "the received data)", source.kind)
        if stream_sha is not None:
            break
        for t in temps:
            _remove(t)
        prog.bytes -= counted[0]
        if attempt < MAX_ATTEMPTS and source.is_connected():
            time.sleep(1)
            continue
        break

    if stream_sha is None:
        for d in targets:
            res.per_dest[d.label] = (both.tr("ERROR: %s", last_err), "")
            d.errors += 1
        res.transfer_check = both.tr("ERROR: %s", last_err)
        return res

    res.sha = stream_sha
    good = []
    for d, w in zip(targets, wres):
        if w.error:
            res.per_dest[d.label] = (both.tr("ERROR: write failed (%s)", w.error), "")
        elif w.sha256 != stream_sha:
            res.per_dest[d.label] = (both.tr("ERROR: verification failed (hash of written copy differs)"), "")
        else:
            good.append((d, w))
            continue
        d.errors += 1
        _remove(w.path)
        _check_dest_alive(d)
    if not good:
        return res

    taken, how = detect_date(good[0][1].path, sf.name, sf.mtime)
    res.taken, res.date_source = taken, how
    placement = placement or getattr(source, "placement", None)
    reldir = placement(sf, taken, cat) if placement else relative_dir(taken, cat)

    for d, w in good:
        try:
            existing = d.index.find_by_sha(stream_sha)
            if existing:
                _remove(w.path)
                d.index.add(sf.source_key, sf.size, sf.mtime, stream_sha, existing, cat, taken, how)
                res.per_dest[d.label] = (both.tr("DUPLICATE: identical file already in backup"), existing)
                continue
            final = d.parent / reldir / safe_name(sf.name)
            status = both.tr("OK - copied and verified")
            there = d.existing(final)
            if there is not None:
                if there.stat().st_size == sf.size and sha256_file(there) == stream_sha:
                    _remove(w.path)
                    rel = final.relative_to(d.parent).as_posix()
                    d.index.add(sf.source_key, sf.size, sf.mtime, stream_sha, rel, cat, taken, how)
                    res.per_dest[d.label] = (both.tr("DUPLICATE: identical file already in backup"), rel)
                    continue
                # GFS: a name is also taken when an earlier backup of the chain has it
                final = unique_path(final, taken=lambda p: d.existing(p) is not None)
                status = both.tr("OK - copied and verified (renamed: name already used by a different file)")
            final.parent.mkdir(parents=True, exist_ok=True)   # year/month folder only when needed
            os.replace(w.path, final)
            if sf.mtime:
                try:
                    os.utime(final, (sf.mtime, sf.mtime))
                except OSError:
                    pass
            rel = final.relative_to(d.parent).as_posix()
            d.index.add(sf.source_key, sf.size, sf.mtime, stream_sha, rel, cat, taken, how)
            d.on_written(rel, sf.size, sf.mtime, stream_sha)
            d.written += 1
            d.written_bytes += sf.size
            res.per_dest[d.label] = (status, rel)
        except OSError as e:
            _remove(w.path)
            d.errors += 1
            res.per_dest[d.label] = (both.tr("ERROR: %s", e), "")
            _check_dest_alive(d)
    return res


class SourceSwitch:
    """A faster connection for a RUNNING backup (user request 2026-11-17): e.g. the backup started
    over Wi-Fi and the user plugs in the USB cable. Another thread offers the new source; the backup
    takes it between two files and continues with the remaining files - same run, same report, the
    change is written in the log and the report. Every phone connection names a file by its path on
    the phone (SourceFile.rel), so the file list and the "already backed up" index stay valid."""

    def __init__(self, patience=None):
        self._lock = threading.Lock()
        self._offer = None
        self._arrived = threading.Event()
        self.taken = 0
        # the connection was lost: the backup waits for another one (user request 2026-11-23: cable
        # pulled → continue over Wi-Fi). patience() -> seconds to wait (the window: longer when a
        # Wi-Fi way to this phone is known)
        self.lost = threading.Event()
        self.patience = patience or (lambda: 60)

    def offer(self, source, on_switch=None):
        """on_switch(old, new) runs in the backup thread right before the new source is used."""
        with self._lock:
            if self._offer is not None:
                return False
            self._offer = (source, on_switch)
            self._arrived.set()
            return True

    def take(self):
        with self._lock:
            got, self._offer = self._offer, None
            self._arrived.clear()
        if got:
            self.taken += 1
        return got

    def wait_for_new(self, cancel=None):
        """Backup thread: the connection is gone – wait for another one (offered by the window's
        watcher). Returns the offer or None (nothing came in time / cancelled)."""
        self.lost.set()
        try:
            end = time.monotonic() + max(0, float(self.patience()))
            while time.monotonic() < end:
                if cancel is not None and cancel.is_set():
                    return None
                if self._arrived.wait(1.0):
                    return self.take()
            return None
        finally:
            self.lost.clear()


def _connection_text(source):
    return f"{source.kind} - {source.description}"


def perform_backup(source, phone_name, owner, folders, dest_bases, cfg, interactive=True, cancel=None,
                   parent_name=None, mode="backup", source_label="", keep_structure=False, switch=None,
                   listing=None):
    """Run one backup (or, with mode="import", an import of a folder into an existing backup).

    Returns (status, report paths, file results, verdict text). status and verdict are English
    (the program compares them); the verdict is a report.Shown – show it with report.shown().
    """
    started = datetime.now()
    t0 = time.monotonic()
    # keep_structure: folders other than the camera folder keep their path (user request 2026-11-04)
    placement = keep_structure_placement(folders) if keep_structure else None

    from . import migrate, plans, setfolders  # backup plan per drive: simple or Grandfather-Father-Son
    parent_name = parent_name or setfolders.rel(phone_name, owner)       # 'Sam/Pixel 10 Pro'
    _start_history(cfg, source, phone_name, mode, parent_name, started, dest_bases)
    # the backup's mark (backupid, user request 2026-11-23): a folder with the same names but the mark
    # of ANOTHER backup is never written to; a folder of this backup without a mark gets it
    from . import backupid
    m_phone, m_owner = setfolders.split_rel(parent_name)
    bid, conflict = backupid.resolve(cfg, setfolders.key_of_rel(parent_name),
                                     [str(Path(b) / parent_name) for b in dest_bases], create=True)
    if conflict:
        ui.warn(tr("The backup drives carry different marks – check them in Manage backups → Destination drives "
                   "(“Add drive…”)."))
    dests = []
    for i, base in enumerate(dest_bases, 1):
        setfolders.relocate(base, cfg)                # old 'Phone - Owner' folders -> Owner/Phone
        set_dir = Path(base) / parent_name            # old month folders -> 2026/26.02 (user's choice)
        mark = backupid.id_of(set_dir)
        if bid and mark and mark != bid:
            ui.warn("  " + tr("Destination %d: %s is another backup (its mark differs) – this drive is "
                              "skipped.", i, set_dir))
            continue
        migrate.ensure_converted(set_dir, tr("Destination %d", i), migrate.effective_keep(cfg, set_dir))
        want = plans.plan_of(cfg, base)
        have = plans.folder_plan(Path(base) / parent_name)
        if have and have != want and mode != "import":
            ui.warn("  " + tr("Destination %d: %s – this backup uses the plan “%s” of the existing "
                              "folder.", i, plans.check_switch(base, parent_name, want),
                              tr(plans.NAMES[have])))
        if (have or want) == plans.GFS:
            d = plans.open_gfs(both.tr("Destination %d", i), base, parent_name, started)
        else:
            parent = Path(base) / parent_name
            parent.mkdir(parents=True, exist_ok=True)
            d = Dest(both.tr("Destination %d", i), Path(base), parent, BackupIndex(parent))
            if bid and not mark:
                try:
                    backupid.write(parent, bid, m_owner, m_phone)
                except OSError as e:
                    ui.warn("  " + tr("Destination %d: could not mark the backup folder: %s", i, e))
        shutil.rmtree(d.tmp, ignore_errors=True)          # leftovers of an interrupted run
        d.tmp.mkdir(parents=True, exist_ok=True)
        dests.append(d)
    if not dests:
        raise RuntimeError(tr("No backup drive of this backup can be used (each one is another backup)."))
    if hasattr(source, "staging"):
        source.staging = dests[0].home / INTERNAL_DIR / "staging"

    if listing is not None:                  # read just before by the check (precheck.run)
        files, missing = listing
    else:
        ui.info(tr("Reading the file list of the source folder ...") if mode == "import"
                else tr("Reading the file list from the phone ..."))
        files, missing = source.list_files(folders)
    for m in missing:
        ui.warn("  " + (tr("Folder not found in the source folder: %s", m or source.root)
                        if mode == "import" else tr("Folder not found on the phone: %s", m or source.root)))
    supported, unsupported = [], []
    classify = getattr(source, "category_of", None) or (lambda f: category_for(f.name))
    for sf in files:
        cat = classify(sf)
        (supported if cat else unsupported).append((sf, cat))

    from . import reconcile
    status = "COMPLETED"
    # a backup folder that is not completely known (copied by hand, index lost …): phone files that
    # are already in it are recognised and not copied again (user request 2026-11-22)
    adopted = {}
    try:
        for d in dests:
            if d.alive and reconcile.simple(d):
                pend = [(sf, cat) for sf, cat in supported if not d.index.has(sf.source_key, sf.size)]
                adopted[d] = reconcile.adopt(d, pend, source, cancel)[0]
    except (KeyboardInterrupt, Cancelled):
        status = "CANCELLED by user"

    # a drive added later: what another drive of this backup already has comes drive to drive
    # after the phone part (reconcile.fill_all), only the new files come from the phone
    todo, already, later = [], 0, {}
    for sf, cat in supported:
        need = [d for d in dests if not d.index.has(sf.source_key, sf.size)]
        own = [d for d in need if not reconcile.held_by_other(dests, d, sf)]
        for d in need:
            if d not in own:
                later[d] = later.get(d, 0) + 1
        if own:
            todo.append((sf, cat, own))
        else:
            already += 1
    if status != "COMPLETED":
        todo = []
    total_bytes = sum(sf.size for sf, _, _ in todo)

    if mode == "import":
        ui.info("  " + trp("%d photo/video in the source folder, %d already backed up, %d new (%s).",
                           "%d photos/videos in the source folder, %d already backed up, %d new (%s).",
                           len(supported), len(supported), already, len(todo),
                           ui.human_size(total_bytes)))
    else:
        ui.info("  " + trp("%d photo/video on the phone, %d already backed up, %d new (%s).",
                           "%d photos/videos on the phone, %d already backed up, %d new (%s).",
                           len(supported), len(supported), already, len(todo),
                           ui.human_size(total_bytes)))
    if unsupported:
        ui.info("  " + trp("%d other file is skipped (%s).", "%d other files are skipped (%s).",
                           len(unsupported), len(unsupported), _skip_text(source)))
    for d, n in later.items():
        ui.info("  " + trp("%s: %d file is already on another drive of this backup – it is copied from "
                           "there after the new files (faster than from the phone).",
                           "%s: %d files are already on another drive of this backup – they are copied "
                           "from there after the new files (faster than from the phone).",
                           n, shown(d.label), n))

    for d in dests:
        needed = sum(sf.size for sf, _, need in todo if d in need) + plans.carry_bytes(d)
        free = shutil.disk_usage(d.home).free
        if needed > free - MIN_FREE:
            ui.warn("  " + tr("%s (%s) has only %s free, needs %s.", shown(d.label), d.base,
                              ui.human_size(free), ui.human_size(needed)))
            if interactive and not ui.ask_yes_no("  " + tr("Use this drive anyway (copies until it is full)?"),
                                                 False):
                d.alive, d.problem = False, both.tr("skipped: not enough free space")

    results = []
    hasher = None
    switches = []                 # connection changes during the run (SourceSwitch)
    first_connection = _connection_text(source)
    prog = ui.Progress(len(todo), total_bytes)
    if not any(d.alive for d in dests) and status == "COMPLETED":
        status = "ABORTED (no usable destination)"
        todo = []
    try:
        if todo and source.supports_phone_hash:
            hasher = PhoneHasher(source, [sf.rel for sf, _, _ in todo])
            hasher.start()
        if todo and hasattr(source, "prefetch"):     # Wi-Fi phone app: fetch ahead
            source.prefetch([sf for sf, _, _ in todo])
        def use(got, i):
            """Continue over another connection from file i on (same run, same report)."""
            nonlocal source, hasher
            new, on_switch = got
            if hasher:
                hasher.stop()
                hasher = None
            old = source
            try:
                if on_switch:
                    on_switch(old, new)
            finally:
                try:
                    old.close()
                except Exception:  # noqa: BLE001 - the old connection may be gone already
                    pass
            source = new
            rest = todo[i - 1:]
            if source.supports_phone_hash:
                hasher = PhoneHasher(source, [s.rel for s, _, _ in rest])
                hasher.start()
            if hasattr(source, "prefetch"):
                source.prefetch([s for s, _, _ in rest])
            switches.append(both.tr("%s: %s → %s (after %d of %d files)", f"{datetime.now():%H:%M:%S}",
                                    old.kind, new.kind, i - 1, len(todo)))
            ui.ok(tr("Connection switched to %s – the backup continues (%d of %d files were already done).",
                     tr(new.kind), i - 1, len(todo)))

        for i, (sf, cat, need) in enumerate(todo, 1):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            got = switch.take() if switch is not None else None
            if got:                                   # faster connection: continue over it
                use(got, i)
            targets = [d for d in need if d.alive]
            if not targets:
                r = FileResult(sf=sf, category=cat)
                for d in need:
                    r.per_dest[d.label] = (both.tr("ERROR: destination unavailable (%s)", d.problem), "")
                results.append(r)
                continue
            r = _copy_one(source, sf, cat, targets, hasher, cfg, prog, cancel, placement)
            # the connection was lost during this file: wait for another one (e.g. cable pulled →
            # Wi-Fi) and copy the file again over it – the backup is not incomplete (2026-11-23)
            while (not r.ok and r.transfer_check.startswith("ERROR") and switch is not None
                   and mode != "import" and not source.is_connected()):
                ui.warn(tr("The connection to the phone was lost – looking for another way (e.g. Wi-Fi) …"))
                got = switch.wait_for_new(cancel)
                if not got:
                    break
                use(got, i)
                r = _copy_one(source, sf, cat, targets, hasher, cfg, prog, cancel, placement)
            for d in need:
                if d not in targets:
                    r.per_dest[d.label] = (both.tr("ERROR: destination unavailable (%s)", d.problem), "")
            results.append(r)
            prog.update(files_done=i, current=sf.name)
            if not any(d.alive for d in dests):
                status = "ABORTED (no destination drive left)"
                break
            if not r.ok and r.transfer_check.startswith("ERROR") and not source.is_connected():
                status = ("ABORTED (source folder no longer reachable)" if mode == "import"
                          else "ABORTED (phone disconnected)")
                break
    except (KeyboardInterrupt, Cancelled):
        status = "CANCELLED by user"
    finally:
        prog.finish()
        if hasher:
            hasher.stop()
        source.close()
        for d in dests:
            shutil.rmtree(d.tmp, ignore_errors=True)
            if hasattr(source, "staging"):
                shutil.rmtree(d.home / INTERNAL_DIR / "staging", ignore_errors=True)
    filled = {}
    if not status.startswith("CANCELLED"):    # drives of this backup completed from each other
        try:
            filled = reconcile.fill_all(dests, cfg, cancel)
        except (KeyboardInterrupt, Cancelled):
            status = "CANCELLED by user"
        finally:
            for d in dests:
                shutil.rmtree(d.tmp, ignore_errors=True)
    for d in dests:                           # everything in the index file before others read it
        d.index.commit()
    for d in dests:                           # GFS: full/differential also get the earlier files
        if d.plan == plans.GFS:
            status = plans.finish_gfs(d, status, cfg, cancel)

    finished = datetime.now()
    duration = time.monotonic() - t0
    paths, verdict = _write_backup_reports(source, phone_name, owner, folders, missing, dests, results,
                                           unsupported, len(supported), already, status, started,
                                           finished, duration, mode, source_label, parent_name,
                                           first_connection, switches, adopted, filled)
    for d in dests:
        d.index.close()
        plans.close(d)
    _record_history(cfg, source, phone_name, mode, parent_name, started, status, results, dests)
    return status, paths, results, verdict


def _history_source(source, phone_name, mode):
    from . import history
    if mode == "import":
        return history.IMPORT, getattr(source, "folders_text", "") or str(getattr(source, "root", "") or "")
    what = phone_name or ""
    if getattr(source, "kind", ""):
        what = f"{what} ({source.kind})" if what else source.kind
    return history.BACKUP, what


def _start_history(cfg, source, phone_name, mode, parent_name, started, dest_bases):
    from . import history, setfolders
    kind, what = _history_source(source, phone_name, mode)
    try:
        history.start(cfg, setfolders.key_of_rel(parent_name), kind, started, what, dest_bases)
    except Exception:  # noqa: BLE001 - never stop a backup because of the history
        pass


def _record_history(cfg, source, phone_name, mode, parent_name, started, status, results, dests):
    """Backup history of the backup (Manage backups → Backup history, user request 2026-11-17)."""
    from . import history, setfolders
    new = [r for r in results if r.ok and r.newly_written]
    kind, what = _history_source(source, phone_name, mode)
    try:
        history.record(cfg, setfolders.key_of_rel(parent_name), kind, started, what, len(new),
                       sum(r.sf.size for r in new), status, [d.base for d in dests])
    except Exception as e:  # noqa: BLE001 - the backup itself is done; never fail because of this
        ui.warn(tr("Could not save the backup history: %s", e))


def _write_backup_reports(source, phone_name, owner, folders, missing, dests, results,
                          unsupported, n_supported, already, status, started, finished, duration,
                          mode="backup", source_label="", parent_name="", first_connection=None, switches=(),
                          adopted=None, filled=None):
    """Reports in the chosen language; the report FILE name, the status and the verdict's English
    value stay English (the verdict is a report.Shown)."""
    importing = mode == "import"
    secured = [r for r in results if r.ok and r.newly_written]
    duplicates = [r for r in results if r.ok and not r.newly_written]
    failed = [r for r in results if not r.ok]
    by_cat = {c: [0, 0] for c in CATEGORY_LABEL}
    for r in secured:
        by_cat[r.category][0] += 1
        by_cat[r.category][1] += r.sf.size
    total_n = sum(v[0] for v in by_cat.values())
    total_b = sum(v[1] for v in by_cat.values())

    def files_size(n, b):
        return trp("%d file, %s", "%d files, %s", n, n, ui.human_size(b))

    adopted, filled = adopted or {}, filled or {}
    fill_errors = [(d, r.source_label, rel, why) for d, lst in filled.items() for r in lst
                   for rel, why in r.errors]
    all_ok = status == "COMPLETED" and not failed and not fill_errors and all(d.alive for d in dests)
    if all_ok:
        filled_n = sum(r.copied for lst in filled.values() for r in lst)
        if total_n == 0 and not filled_n:      # plain words, no "0 new files" (UI test 2026-11-23)
            verdict = both.trp("EVERYTHING ALREADY BACKED UP - no new photos or videos on the phone "
                               "(checked on %d drive).",
                               "EVERYTHING ALREADY BACKED UP - no new photos or videos on the phone "
                               "(checked on %d drives).", len(dests), len(dests))
        elif len(dests) == 1:
            verdict = both.trp("EVERYTHING COPIED CORRECTLY - %d new file (%s) secured and verified "
                               "with SHA-256 on 1 drive.",
                               "EVERYTHING COPIED CORRECTLY - %d new files (%s) secured and verified "
                               "with SHA-256 on 1 drive.",
                               total_n, total_n, ui.human_size(total_b))
        else:
            verdict = both.trp("EVERYTHING COPIED CORRECTLY - %d new file (%s) secured and verified "
                               "with SHA-256 on %d drives.",
                               "EVERYTHING COPIED CORRECTLY - %d new files (%s) secured and verified "
                               "with SHA-256 on %d drives.",
                               total_n, total_n, ui.human_size(total_b), len(dests))
        if duplicates:
            verdict = verdict + " " + both.trp(
                "%d identical duplicate was recognised and not stored twice.",
                "%d identical duplicates were recognised and not stored twice.",
                len(duplicates), len(duplicates))
    else:
        problems = []
        if status != "COMPLETED":
            problems.append(status)
        if failed:
            problems.append(both.trp("%d file with errors (see list)", "%d files with errors (see list)",
                                     len(failed), len(failed)))
        if fill_errors:
            problems.append(both.trp("%d file could not be copied from the other backup drive",
                                     "%d files could not be copied from the other backup drive",
                                     len(fill_errors), len(fill_errors)))
        for d in dests:
            if not d.alive:
                problems.append(both.tr("%s: %s", d.label, d.problem))
        verdict = both.tr("ATTENTION - %s", both.join("; ", problems))

    speed = total_b / duration if duration > 0 else 0
    if importing:
        general = [(tr("Imported folder"), getattr(source, "folders_text", "") or str(source.root))]
        if phone_name:
            general += [(tr("Smartphone"), phone_name), (tr("Owner"), owner)]
        general += [(tr("Imported into backup"), parent_name),
                    (tr("Import date"), f"{started:%Y-%m-%d}")]
    else:
        general = [(tr("Smartphone"), phone_name),
                   (tr("Owner"), owner),
                   (tr("Backup date"), f"{started:%Y-%m-%d}")]
    general += [
        (tr("Status"), status),                     # English value, translated by write_reports
        (tr("Started"), f"{started:%Y-%m-%d %H:%M:%S}"),
        (tr("Finished"), f"{finished:%Y-%m-%d %H:%M:%S}"),
        (tr("Duration"), ui.human_duration(duration)),
    ]
    if not importing:
        general.append((tr("Connection"), first_connection or _connection_text(source)))
        if switches:
            general.append((tr("Connection changes"), "; ".join(str(shown(s)) for s in switches)))
    if getattr(source, "fallback_reason", None):
        general.append((tr("ADB fallback"), tr("ADB did not work (%s); %s was used instead",
                                               source.fallback_reason, source.kind)))
    if not importing:
        general.append((tr("Folders on phone"), ", ".join(folders)))
    if missing:
        general.append((tr("Folders NOT found"), ", ".join(missing)))

    data = [
        (tr("Total secured this run"), tr("%s (%s bytes)", files_size(total_n, total_b), f"{total_b:,}")),
        (tr("Photos"), files_size(*by_cat["photo"])),
        (tr("Videos"), files_size(*by_cat["video"])),
        (tr("RAW"), files_size(*by_cat["raw"])),
    ] + [
        (tr("%s (other/)", tr(CATEGORY_LABEL[c])), files_size(*by_cat[c]))
        for c in ("other-photo", "other-video", "other-file") if by_cat[c][0]
    ] + [
        (tr("Average speed"), tr("%s/s", ui.human_size(speed))),
        (tr("Photos/videos found in the source") if importing else tr("Photos/videos found on phone"),
         str(n_supported)),
        (tr("Already backed up before (skipped)"), str(already)),
        (tr("Identical duplicates (not stored twice)"), str(len(duplicates))),
        (tr("Files with errors"), str(len(failed))),
        (tr("Other files skipped (%s)", _skip_text(source)), str(len(unsupported))),
    ]
    dest_items = []
    for d in dests:
        state = both.tr("OK") if d.alive else both.tr("PROBLEM: %s", d.problem)
        tot = d.index.totals()
        content = ", ".join(tr("%s: %d files / %s", tr(CATEGORY_LABEL.get(c, c)), n, ui.human_size(b))
                            for c, (n, b) in sorted(tot.items()))
        label = shown(d.label)
        dest_items += [(label, str(d.parent)),
                       (tr("%s backup plan", label), d.describe() if hasattr(d, "describe") else
                        tr("Simple – one folder, only new files are added")),
                       (tr("%s state", label), state),
                       (tr("%s this run", label),
                        tr("%d files written, %s, %d errors", d.written, ui.human_size(d.written_bytes),
                           d.errors)),
                       (tr("%s whole backup", label), content or tr("empty"))]
        a = adopted.get(d)
        if a is not None and a.found:
            dest_items.append((tr("%s already in the folder", label),
                               tr("%d photos/videos recognised in the backup folder (not in its list before) – "
                                  "%d by the phone path in the backup's reports, %d checked with the SHA-256 "
                                  "on the phone, %d by name, size and SHA-256 of the backup file",
                                  a.found, a.by_log, a.by_phone_hash, a.found - a.by_log - a.by_phone_hash)))
        if a is not None and a.rejected:
            dest_items.append((tr("%s same name, different content", label),
                               tr("%d files (the phone's files were copied, the old ones stay)", a.rejected)))
        for fr in filled.get(d, []):
            dest_items.append((tr("%s copied from %s", label, fr.source_label),
                               tr("%d files, %s – read back and SHA-256 compared; %d were already there; "
                                  "%d errors", fr.copied, ui.human_size(fr.bytes), fr.already, len(fr.errors))))
        if getattr(d, "carried", 0):
            from .gfs import mode_name
            dest_items.append((tr("%s earlier files in this %s backup", label, mode_name(d.mode)),
                               tr("%d files, %s (copied on the drive)", d.carried,
                                  ui.human_size(d.carried_bytes))))
    if source.supports_phone_hash:
        how = (tr("SHA-256 of every source file calculated separately and compared with the copied data")
               if importing else tr("SHA-256 calculated on the phone and compared with the received data"))
    else:
        how = tr("%s: SHA-256 of the received data (no hash possible on the phone with this connection)",
                 source.kind)
    method = [(tr("Source -> computer") if importing else tr("Phone -> computer"), how),
              (tr("Computer -> drive"), tr("every copy is flushed to disk, read back and its SHA-256 compared")),
              (tr("Interrupted copies"), tr("files are written as temporary files and only renamed after a "
                                            "successful check - there are no half-copied files"))]
    if filled:
        method.append((tr("Drive -> drive"), tr("files another backup drive already has are copied from it: "
                                                "the source file's SHA-256 must match that drive's list, the "
                                                "copy is flushed, read back and compared")))
    sections = [(tr("General"), general), (tr("Data secured"), data), (tr("Destinations"), dest_items),
                (tr("Verification method"), method)]
    if fill_errors:
        sections.append((tr("Not copied from the other backup drive"),
                         [(f"{shown(d.label)}: {rel}", tr("from %s: %s", src, why))
                          for d, src, rel, why in fill_errors[:500]]))

    columns = [tr("Nr"), tr("File"), tr("Type"), tr("Size"), tr("Bytes"), tr("Date taken"), tr("Date from"),
               tr("Path in source") if importing else tr("Phone path"),
               tr("Transfer check"), tr("SHA-256")]
    for d in dests:
        columns += [tr("%s status", shown(d.label)), tr("%s location", shown(d.label))]
    not_needed = both.tr("not needed (already backed up on this drive)")
    rows = []
    for i, r in enumerate(results, 1):
        row = [i, r.sf.name, tr(CATEGORY_LABEL[r.category]), ui.human_size(r.sf.size), r.sf.size,
               f"{r.taken:%Y-%m-%d %H:%M:%S}" if r.taken else "", tr(r.date_source) if r.date_source else "",
               r.sf.rel, r.transfer_check, r.sha]
        for d in dests:
            st, loc = r.per_dest.get(d.label, (not_needed, ""))
            row += [st, loc]
        rows.append(row)
    n = len(rows)
    skipped = both.tr("skipped (%s)", tr(getattr(source, "skip_text", N_("not a photo/video file"))))
    for sf, _ in unsupported:
        n += 1
        rows.append([n, sf.name, tr("other"), ui.human_size(sf.size), sf.size, "", "", sf.rel,
                     "", ""] + [skipped, ""] * len(dests))

    # the report FILE names stay English (report_base); the title inside is translated
    if importing:
        title = tr("Import %s into %s - %s", source_label, parent_name, f"{started:%Y-%m-%d %H:%M}")
        report_base = f"Import {source_label}"
    else:
        title = tr("Backup %s - %s - %s", phone_name, owner, f"{started:%Y-%m-%d %H:%M}")
        report_base = f"Backup {phone_name} {owner}"
    paths = []
    basename = None
    for d in dests:
        rdir = logs_dir(d.report_dir)
        try:
            if basename is None or (rdir / (basename + ".txt")).exists():
                basename = unique_basename(rdir, report_base, started)
            paths += write_reports(rdir, basename, title, all_ok, verdict, sections, columns, rows)
        except OSError as e:
            ui.error(tr("Could not write report to %s: %s", rdir, e))
    if all_ok:
        ui.ok(verdict)
    else:
        ui.error(verdict)
    return paths, verdict
