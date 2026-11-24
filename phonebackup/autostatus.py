"""The status of a running backup – the same title and line on the computer and on the phone
(user request 2026-11-23: "status info on both devices, synchronized in its appearance").
The phone app builds the same texts from the same numbers (BackupProgress.kt). No Qt here."""

from .i18n import tr


def title(auto, finished=False, ok=True):
    if finished:
        if not ok:
            return tr("Automatic backup stopped") if auto else tr("Backup stopped")
        return tr("Automatic backup finished") if auto else tr("Backup finished")
    return tr("Automatic backup running") if auto else tr("Backup running")


def size(n):
    """"1.5 GB" / "321 MB" / "under 1 MB" – exactly as on the phone (BackupStatus.sizeText)."""
    mb = (n or 0) / (1024 * 1024)
    if mb >= 1024:
        return tr("%.1f GB", mb / 1024)
    if mb >= 1:
        return tr("%d MB", round(mb))
    return tr("under 1 MB")


def left(seconds):
    if seconds is None or seconds < 0:
        return ""
    if seconds < 60:
        return tr("less than a minute left")
    return tr("about %d min left", round(seconds / 60))


def line(done, total, bytes_done=0, bytes_total=0, eta=None):
    """"42 of 140 photos and videos · 120 MB of 390 MB · about 3 min left"."""
    parts = [tr("%d of %d photos and videos", done, total)]
    if bytes_total:
        parts.append(tr("%s of %s", size(bytes_done), size(bytes_total)))
    t = left(eta)
    if t:
        parts.append(t)
    return " · ".join(parts)


def result_line(ok, new):
    if not ok:
        return tr("Not everything was copied – look at the computer.")
    if new == 0:
        return tr("Nothing new – everything was already backed up.")
    return tr("%d new photos and videos secured.", new)


def payload(d, auto):
    """What the computer sends to the phone app (POST /progress) – numbers only."""
    return {"state": "running", "auto": bool(auto), "done": int(d.get("files") or 0),
            "total": int(d.get("total_files") or 0), "bytes": int(d.get("bytes") or 0),
            "total_bytes": int(d.get("total_bytes") or 0),
            "eta": int(d["eta"]) if d.get("eta") is not None else -1}
