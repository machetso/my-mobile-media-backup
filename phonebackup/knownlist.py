"""What is backed up already: the backup's file list for the phone (user request 2026-11-23).

"Not backed up yet" is counted against the FILE LIST of the backup, not against the date of the
last backup: the list of a connected backup drive (the newest one, if there are several), else
the newest list this computer has seen on a backup drive (kept next to the settings).

The phone gets the list in a compact form – for each file (phone path, size) an 8-byte digest,
sorted – once, and again only when it changes ("k" = version). It then counts its photos and
videos that are not in it itself (MediaIndex.countNotIn), also later without the computer.

No Qt here.
"""

import base64
import hashlib
import json
import os
import sqlite3
import struct
from pathlib import Path

from .config import config_path, write_private

INTERNAL = ".phonebackup"


def digest(source_path, size):
    """8 bytes for one file: the same on the phone (MediaIndex.digest)."""
    h = hashlib.sha256(f"{str(source_path).strip('/')}\0{int(size)}".encode("utf-8")).digest()
    return struct.unpack(">q", h[:8])[0]


def pack(digests):
    """Sorted, unique, 8 bytes each (big endian, signed – Kotlin Long)."""
    return b"".join(struct.pack(">q", d) for d in sorted(set(digests)))


def version(blob):
    return hashlib.sha256(blob).hexdigest()[:16]


def _db(set_dir):
    p = Path(set_dir) / INTERNAL / "index.sqlite"
    if not p.is_file():
        return None
    return sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=5)


def newest_of(set_dir):
    """When the list of this backup folder was changed last ("" = no list)."""
    try:
        db = _db(set_dir)
        if db is None:
            return ""
        try:
            row = db.execute("SELECT max(backed_up_at) FROM files").fetchone()
        finally:
            db.close()
    except sqlite3.Error:
        return ""
    return (row[0] or "") if row else ""


def read_list(set_dir):
    """The packed list of a backup folder, or None."""
    try:
        db = _db(set_dir)
        if db is None:
            return None
        try:
            rows = db.execute("SELECT source_path, size FROM files").fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return None
    return pack(digest(p, s) for p, s in rows)


def _cache_dir():
    return config_path().parent / "known"


def _cache_file(key):
    safe = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return _cache_dir() / f"{safe}.json"


def load(key):
    """The remembered list of backup `key`: {"at", "from", "k", "blob"} or None."""
    try:
        d = json.loads(_cache_file(key).read_text(encoding="utf-8"))
        d["blob"] = base64.b64decode(d["d"])
        return d
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _save(key, at, src, blob):
    _cache_dir().mkdir(parents=True, exist_ok=True)
    write_private(_cache_file(key), json.dumps({"key": key, "at": at, "from": src, "k": version(blob),
                                               "d": base64.b64encode(blob).decode("ascii")}))


def refresh(key, set_dirs):
    """Background (the drives are read): take the newest list of the connected backup folders of
    `key` and remember it if it is newer than the remembered one. Returns the remembered entry."""
    have = load(key)
    best, best_at = None, ""
    for s in set_dirs:
        if not os.path.isdir(s):
            continue
        at = newest_of(s)
        if at and at > best_at:
            best, best_at = s, at
    if best is not None and (have is None or best_at != have.get("at") or best != have.get("from")):
        blob = read_list(best)
        if blob is not None:
            _save(key, best_at, best, blob)
            have = load(key)
    return have


def current(key):
    """(version, base64 list) to tell the phone, or ("", "") – no list known: the phone counts by date."""
    have = load(key)
    if not have or not have.get("blob"):
        return "", ""
    return have["k"], have["d"]


# ---------------------------------------------------- counted on the computer (no phone app)
# ADB or MTP without the phone app: the computer reads the phone's file list itself and compares
# it with the backup's list. Over MTP that takes long, so the phone's list of last time is
# remembered: the count is shown at once from it, and checked with the real list in the
# background (user request 2026-11-23).

def count(files, blob):
    """(photos, videos, bytes) of `files` [(phone path, size)] that are not in the list `blob`.
    RAW photos count as photos; other files are not counted."""
    from .media import category_for
    have = set(struct.unpack(f">{len(blob) // 8}q", blob)) if blob else set()
    p = v = size = 0
    for rel, sz in files:
        cat = category_for(rel)
        if cat is None or digest(rel, sz) in have:
            continue
        if cat == "video":
            v += 1
        else:
            p += 1
        size += int(sz)
    return p, v, size


def _phone_file(key):
    safe = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return _cache_dir() / f"{safe}.phone.json"


def save_phone(key, files, folders):
    """Remember the phone's file list [(phone path, size)] of these folders."""
    _cache_dir().mkdir(parents=True, exist_ok=True)
    write_private(_phone_file(key), json.dumps({"key": key, "folders": list(folders),
                                                "files": [[r, int(s)] for r, s in files]}))


def load_phone(key, folders):
    """The remembered phone file list for these folders, or None."""
    try:
        d = json.loads(_phone_file(key).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if sorted(d.get("folders") or []) != sorted(folders):
        return None
    return [(r, s) for r, s in d.get("files") or []]
