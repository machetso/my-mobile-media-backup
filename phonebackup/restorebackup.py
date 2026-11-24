"""Restore from the NORMAL backup (user decision 2026-11-23): choose a backup → its folders (year/
month, kept phone folders) → into a new or empty folder.

Every file is copied and checked with SHA-256 (the copy read back = the original read, and – when
the backup's list knows the file – the checksum on record). Nothing is ever overwritten: an
identical file in the target is skipped, a different one with the same name gets "_1".
Optionally the files go back into the phone's own folders (e.g. DCIM/Camera) instead of the
backup's year/month folders – the place on the phone is in the backup's list.

No Qt here.
"""

import os
import sqlite3
from pathlib import Path

from . import ui
from .copier import Cancelled, file_chunks, sha256_file, stream_copy
from .i18n import tr, trp
from .index import INTERNAL_DIR
from .layout import unique_path

LOGS_DIR = "Logs"


def _files(set_dir):
    """{rel: size} of the photos/videos of a backup folder (not its list, logs or hidden files)."""
    set_dir = Path(set_dir)
    out = {}
    for dirpath, dirnames, filenames in os.walk(set_dir):
        rel_dir = Path(dirpath).relative_to(set_dir).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and not (not rel_dir and d == LOGS_DIR))
        for fn in sorted(filenames):
            if fn.startswith(".") or not rel_dir:        # files directly in the backup folder: reports
                continue
            try:
                out[f"{rel_dir}/{fn}"] = os.path.getsize(os.path.join(dirpath, fn))
            except OSError:
                continue
    return out


def folders(set_dir):
    """[(folder, files, bytes)] – every folder of the backup that holds photos/videos, sorted."""
    acc = {}
    for rel, size in _files(set_dir).items():
        d = rel.rsplit("/", 1)[0]
        n, b = acc.get(d, (0, 0))
        acc[d] = (n + 1, b + size)
    return [(d, n, b) for d, (n, b) in sorted(acc.items())]


def _records(set_dir):
    """{rel_path: (sha256, source_path)} from the backup's list (the newest entry of a place)."""
    p = Path(set_dir) / INTERNAL_DIR / "index.sqlite"
    if not p.is_file():
        return {}
    try:
        db = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=5)
        try:
            rows = db.execute("SELECT rel_path, sha256, source_path FROM files ORDER BY rowid").fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return {}
    return {rel: (sha, src) for rel, sha, src in rows}


def restore(set_dir, chosen, dest, phone_layout=False, cancel=None):
    """Copy the files of the folders `chosen` (from folders()) into `dest`.
    Returns (status, paths, verdict) like the other jobs (status English)."""
    set_dir, dest = Path(set_dir), Path(dest)
    chosen = set(chosen)
    files = {rel: size for rel, size in _files(set_dir).items() if rel.rsplit("/", 1)[0] in chosen}
    rec = _records(set_dir)
    total_b = sum(files.values())
    ui.info(trp("%d file (%s) to restore into %s.", "%d files (%s) to restore into %s.", len(files),
                len(files), ui.human_size(total_b), dest))
    dest.mkdir(parents=True, exist_ok=True)
    prog = ui.Progress(len(files), total_b)
    copied = same = 0
    errors, damaged = [], []
    status = "COMPLETED"
    for rel, size in files.items():
        if cancel is not None and cancel.is_set():
            status = "CANCELLED by user"
            break
        sha_rec, src_path = rec.get(rel, (None, None))
        target_rel = src_path.strip("/") if phone_layout and src_path and not src_path.startswith("import:") else rel
        target = dest / target_rel
        src = set_dir / rel
        tok = prog.begin(Path(rel).name)
        try:
            if target.exists():
                if target.stat().st_size == size and sha256_file(target, cancel) == (sha_rec or sha256_file(src, cancel)):
                    same += 1                                  # already there, identical
                    continue
                target = unique_path(target)                   # never overwrite
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".part")
            sha, n, results = stream_copy(file_chunks(src), [str(tmp)], fsync=False, cancel=cancel)
            r = results[0]
            if r.error or r.sha256 != sha or n != size:
                errors.append((rel, r.error or tr("the copy differs from the original")))
                try:
                    tmp.unlink()
                except OSError:
                    pass
                continue
            os.replace(tmp, target)
            try:
                st = src.stat()
                os.utime(target, (st.st_atime, st.st_mtime))
            except OSError:
                pass
            copied += 1
            if sha_rec and sha_rec != sha:
                damaged.append(rel)                            # copied, but not what was backed up
        except Cancelled:
            status = "CANCELLED by user"
            break
        except OSError as e:
            errors.append((rel, f"{type(e).__name__}: {e}"))
        finally:
            prog.update(add_bytes=size)
            prog.end(tok)                                      # counts the file
    prog.finish()
    for rel, why in errors[:20]:
        ui.warn(f"  {rel}: {why}")
    for rel in damaged[:20]:
        ui.warn("  " + tr("%s: its content differs from the checksum on record – the file in the backup "
                          "may be damaged (run the integrity check).", rel))
    if status == "COMPLETED" and (errors or damaged):
        status = "COMPLETED WITH ERRORS"
    if status == "COMPLETED":
        verdict = trp("RESTORE OK - %d file copied and verified with SHA-256.",
                      "RESTORE OK - %d files copied and verified with SHA-256.", copied, copied)
        if same:
            verdict += " " + trp("%d was already there (identical).", "%d were already there (identical).",
                                 same, same)
    else:
        verdict = (tr("ATTENTION - %s", status) + " · " +
                   trp("%d file copied", "%d files copied", copied, copied) +
                   (" · " + trp("%d file could not be restored", "%d files could not be restored",
                                len(errors), len(errors)) if errors else "") +
                   (" · " + trp("%d file differs from the checksum on record",
                                "%d files differ from the checksum on record", len(damaged), len(damaged))
                    if damaged else ""))
    ui.info(verdict)
    return status, [], verdict
