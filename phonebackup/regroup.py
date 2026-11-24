"""Put the photos and videos of an imported folder back into the folder's own structure (user
request 2026-11-23: "pixel10pro -dateien" – Download, Pictures, PDFs … – had been split: its
other files kept the folder structure, its photos and videos were sorted into YYYY/YY.MM).

The rule (the same as importer.keep_mixed_folders): an imported top-level folder that holds files
other than photos/videos AND whose photos/videos mostly do not have camera names keeps its
structure. The backup's list knows where every file came from ("import:<folder>/<path>") – the
sorted files go back to <folder name>/<path> inside the backup, next to the other files.

plan()  read-only: which folders, which files, from where to where
apply() os.rename on the same drive + the list entries changed; a manifest in .phonebackup lets
        undo() put everything back. Nothing is deleted or overwritten (a name that is taken → _1).
No Qt here.
"""

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .importer import CAMERA_NAME
from .index import INTERNAL_DIR
from .knownhash import is_media


@dataclass
class Folder:
    name: str                    # "pixel10pro -dateien"
    origin: str                  # where it was imported from (its parent folder)
    kept: int = 0                # files already in its structure
    media: int = 0
    camera_named: int = 0
    other: int = 0
    moves: list = field(default_factory=list)      # [(rel now, rel in its structure)]
    strays: int = 0              # of them from a part of the folder inside a year folder


def _split(source_path):
    """'import:C:/x/Google/pixel10pro -dateien/Download/a.jpg' → ('C:/x/Google', 'pixel10pro -dateien',
    'Download/a.jpg'); None for anything that is not an import."""
    if not source_path.startswith("import:"):
        return None
    raw = source_path[len("import:"):]
    return raw


def plan(set_dir):
    """[Folder] whose photos/videos were sorted although the folder should keep its structure."""
    set_dir = Path(set_dir)
    db = sqlite3.connect(f"file:{set_dir / INTERNAL_DIR / 'index.sqlite'}?mode=ro", uri=True)
    try:
        newest = {}
        for src, rel in db.execute("SELECT source_path, rel_path FROM files ORDER BY rowid"):
            newest[rel] = src
    finally:
        db.close()
    # the kept files tell which imported folder lives where: rel "<name>/<sub>" ↔ source ".../<name>/<sub>"
    folders = {}
    for rel, src in newest.items():
        raw = _split(src)
        if raw is None:
            continue
        top = rel.split("/", 1)[0]
        if top.isdigit() or top.startswith("."):         # the year folders are the program's own
            continue
        marker = "/" + top + "/"
        norm = raw.replace("\\", "/")
        if marker in norm and norm.endswith("/" + rel.split("/", 1)[-1]) and "/" in rel:
            origin = norm[:norm.index(marker)]
            f = folders.setdefault((origin, top), Folder(top, origin))
            f.kept += 1
    for rel, src in newest.items():
        raw = _split(src)
        if raw is None:
            continue
        norm = raw.replace("\\", "/")
        for (origin, top), f in folders.items():
            prefix = origin + "/" + top + "/"
            if not norm.startswith(prefix):
                continue
            name = norm.rsplit("/", 1)[-1]
            if is_media(name):
                f.media += 1
                if CAMERA_NAME.match(name):
                    f.camera_named += 1
            else:
                f.other += 1
            want = top + "/" + norm[len(prefix):]
            if rel != want and not rel.startswith(top + "/") and (set_dir / rel).is_file():
                f.moves.append((rel, want))
            break
    keep = [f for f in folders.values() if f.other and f.camera_named * 2 < f.media]
    # a part of the same folder that ended up INSIDE a year folder – "2026/pixel10pro -dateien/…"
    # (user 2026-11-23: two folders of that name; made on 2026-11-11, not in the list)
    planned = {r for f in keep for r, _w in f.moves}
    for f in keep:
        for year in sorted(e.name for e in os.scandir(set_dir) if e.is_dir() and e.name.isdigit()):
            for stray in [set_dir / year / f.name] + sorted((set_dir / year).glob("*/" + f.name)):
                if not stray.is_dir():
                    continue
                for dirpath, _dirs, files in os.walk(stray):
                    for fn in sorted(files):
                        full = Path(dirpath) / fn
                        rel = full.relative_to(set_dir).as_posix()
                        if rel not in planned:
                            f.moves.append((rel, f.name + "/" + full.relative_to(stray).as_posix()))
                            f.strays += 1
    return [f for f in keep if f.moves]


def _unique(path):
    from .layout import unique_path
    return unique_path(path)


def _same(a, b):
    from .copier import sha256_file
    try:
        return a.stat().st_size == b.stat().st_size and sha256_file(a) == sha256_file(b)
    except OSError:
        return False


def apply(set_dir, folders, cancel=None, progress=None):
    """Move the files back into their folders. A file whose place is taken by an IDENTICAL file
    goes into a review folder "Duplicates <date>" beside the backup folder; another file of that
    name stays as _1. Returns (moved, skipped, manifest path)."""
    set_dir = Path(set_dir)
    when = datetime.now()
    man_path = set_dir / INTERNAL_DIR / f"regroup {when:%Y-%m-%d %H-%M-%S}.json"
    man = {"set_dir": str(set_dir), "when": when.isoformat(timespec="seconds"), "moves": []}
    review = set_dir.parent / f"Duplicates {when:%Y-%m-%d %H-%M-%S}"

    def save():
        tmp = man_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, man_path)
    save()
    db = sqlite3.connect(str(set_dir / INTERNAL_DIR / "index.sqlite"))
    moved, skipped = 0, []
    todo = [m for f in folders for m in f.moves]
    try:
        for n, (rel, want) in enumerate(todo, 1):
            if cancel is not None and cancel.is_set():
                break
            src, dst = set_dir / rel, set_dir / want
            if not src.is_file():
                skipped.append((rel, "gone"))
                continue
            new_rel = want
            if dst.exists():
                if _same(src, dst):                    # already there: the copy to the review folder
                    dst = review / set_dir.name / rel
                else:
                    dst = _unique(dst)
                    new_rel = dst.relative_to(set_dir).as_posix()
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.rename(src, dst)
            except OSError as e:
                skipped.append((rel, str(e)))
                continue
            rowids = [r for (r,) in db.execute("SELECT rowid FROM files WHERE rel_path=?", (rel,))]
            with db:
                db.executemany("UPDATE files SET rel_path=? WHERE rowid=?", [(new_rel, r) for r in rowids])
            man["moves"].append([str(src), str(dst), rel, new_rel, rowids])
            moved += 1
            if progress:
                progress(n, len(todo), 0, 0, str(dst))
            if n % 50 == 0:
                save()
        for _src, _dst, rel, _new, _ids in man["moves"]:     # folders left empty by the move
            d = (set_dir / rel).parent
            while d != set_dir and set_dir in d.parents:
                try:
                    d.rmdir()
                except OSError:
                    break
                d = d.parent
        if review.is_dir():
            (review / ".msmb-regroup").write_text(str(man_path), encoding="utf-8")
    finally:
        db.close()
        save()
    return moved, skipped, str(man_path)


def undo(manifest):
    """Put every moved file back where it was (only if the place is free)."""
    man = json.loads(Path(manifest).read_text(encoding="utf-8"))
    set_dir = Path(man["set_dir"])
    db = sqlite3.connect(str(set_dir / INTERNAL_DIR / "index.sqlite"))
    back, skipped = 0, []
    try:
        for src, dst, rel, _new_rel, rowids in reversed(man["moves"]):
            src, dst = Path(src), Path(dst)
            if not dst.is_file() or src.exists():
                skipped.append(str(dst))
                continue
            src.parent.mkdir(parents=True, exist_ok=True)
            os.rename(dst, src)
            with db:                                   # exactly the entries that were changed
                db.executemany("UPDATE files SET rel_path=? WHERE rowid=?", [(rel, r) for r in rowids])
            back += 1
    finally:
        db.close()
    return back, skipped
