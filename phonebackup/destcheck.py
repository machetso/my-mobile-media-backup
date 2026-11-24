"""Is a folder allowed as a backup destination? (UI test 2026-11-23, user decision: BLOCK, explain why)

Refused:
- a folder on the phone itself (the backup would land on the phone it should protect),
- a folder inside an existing backup (a backup inside a backup is copied again and again),
- a second folder on a drive that is already in the list (two copies on one drive do not protect
  against that drive failing; also "drive + a folder on it").

No Qt here.
"""

import os
from pathlib import Path

from .i18n import tr
from .index import INTERNAL_DIR


def _norm(p):
    try:
        return str(Path(p).expanduser().resolve(strict=False))
    except (OSError, RuntimeError):
        return str(p)


def _inside(p, root):
    p, root = _norm(p), _norm(root).rstrip("/\\")
    return p == root or p.startswith(root + os.sep) or p.startswith(root + "/")


def on_phone(path, phone_roots=()):
    """The folder is on a phone: under the connected phone's folder, or an MTP mount."""
    s = _norm(path).replace("\\", "/").lower()
    if "/gvfs/mtp:" in s or "/gvfs/gphoto2:" in s or s.startswith("mtp:"):
        return True
    return any(r and _inside(path, r) for r in phone_roots)


def backup_around(path):
    """The backup folder that contains `path` (or is `path`), else ""."""
    p = Path(_norm(path))
    for a in [p] + list(p.parents):
        try:
            if (a / INTERNAL_DIR).is_dir():
                return str(a)
        except OSError:
            continue
    return ""


def _drive_of(path, roots):
    from .findbackup import mount_root
    r = mount_root(_norm(path), [_norm(x) for x in roots])
    if r:
        return r
    p = Path(_norm(path))                     # not an attached drive: the nearest mount point
    for a in [p] + list(p.parents):
        try:
            if a.exists() and os.path.ismount(a):
                return str(a)
        except OSError:
            continue
    return ""


def problem(path, others=(), roots=(), phone_roots=()):
    """Why `path` cannot be a backup destination next to `others` – "" when it can."""
    if on_phone(path, phone_roots):
        return tr("This folder is on the phone. The backup must go to another drive – an external "
                  "drive (or a folder on the computer), never onto the phone it protects.")
    inner = backup_around(path)
    if inner:
        return tr("This folder is inside an existing backup:\n%s\n\nChoose the drive itself (or "
                  "another folder outside the backup) – a backup inside a backup is copied twice.", inner)
    me = _drive_of(path, roots)
    for o in others:
        if not o or str(o).startswith("gdrive:"):
            continue
        if _norm(o) == _norm(path):
            continue                                 # the same entry again: nothing new
        if _inside(path, o) or _inside(o, path) or (me and _drive_of(o, roots) == me):
            return tr("This folder is on the same drive as\n%s\nwhich is already in the list.\n\n"
                      "Two copies on one drive do not help when that drive fails – choose another "
                      "drive.", o)
    return ""
