"""Which phone belongs to which backup - never mix up phones (user requirement 2026-11-04).

Every backup folder ("Galaxy A55 - Kim") remembers its phone in .phonebackup/phone.json:
model, the phone's serial numbers (ADB: ro.serialno) and the phone app's ids (its key, paired).
Before a backup the connected phone must match:

* the serial number decides when both sides know it (a different serial = refused); the phone app
  over Wi-Fi gives the serial that was confirmed over the USB cable for its pairing;
* else the same phone-app id = the phone; a different phone-app id alone is NOT refused (the id
  changes when the app is reinstalled / paired again): same model = the user confirms;
* if no id can be compared (e.g. a new connection type), only the same model is accepted, and
  the user has to confirm it; the folder then does not learn new ids from that backup;
* a folder without phone.json (first backup, or made by an older version) is accepted when the
  model matches the backup's phone name or the user confirms it - then the ids are stored.

`identify(source)` reads the ids live from the phone; it is called twice: when Start is clicked and
again right before the first file is read (the phone might have been swapped in between).
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import tr
from .index import INTERNAL_DIR

FILE = "phone.json"
MATCH, PROBABLE, NEW, MISMATCH = "match", "probable", "new", "mismatch"


@dataclass
class PhoneId:
    model: str = ""
    manufacturer: str = ""
    serial: str = ""            # ro.serialno (ADB) - "" if unknown
    app_id: str = ""            # phone app id (key checked) - "" if unknown
    connection: str = ""        # "usb-adb" | "wifi-adb" | "app-wifi" | "app-cable" | "mtp" | "folder"

    @property
    def label(self):
        return " ".join(x for x in (self.manufacturer, self.model) if x).strip() or tr("unknown phone")


@dataclass
class Record:
    model: str = ""
    serials: list = field(default_factory=list)
    app_ids: list = field(default_factory=list)


def identify(src):
    """Ask the connected phone who it is (live, no cached values)."""
    from .companion import CompanionSource
    from .sources import AdbSource
    if isinstance(src, AdbSource):
        model = src.shell("getprop ro.product.model").strip() or src.device_name
        serial = src.shell("getprop ro.serialno").strip() or getattr(src, "hw_serial", "")
        link = getattr(src, "link", None)
        app_id = ""
        if link is not None:
            try:                       # key-checked connection to the phone app (adb forward)
                info = link.client.request("GET", "/info")
                app_id = (info or {}).get("phone_id", "") or link.entry.get("phone_id", "")
            except Exception:  # noqa: BLE001 - app gone: the serial still identifies the phone
                app_id = ""
        return PhoneId(model, src.manufacturer, serial, app_id,
                       "wifi-adb" if src.wireless else "usb-adb")
    if isinstance(src, CompanionSource):
        info = src.client.request("GET", "/info") or {}
        # serial: confirmed over the USB cable for this (key-checked) pairing – companion.remember_serial
        serial = (src.entry or {}).get("serial", "") if getattr(src, "entry", None) else ""
        return PhoneId(info.get("model", "") or src.device_name, info.get("manufacturer", ""),
                       serial, info.get("phone_id", "") or src.entry.get("phone_id", ""), "app-wifi")
    kind = (getattr(src, "kind", "") or "").lower()
    return PhoneId(getattr(src, "device_name", "") or "", "", getattr(src, "serial", "") or "", "",
                   "mtp" if "mtp" in kind else "folder")


def _path(parent):
    return Path(parent) / INTERNAL_DIR / FILE


def load(parent):
    try:
        d = json.loads(_path(parent).read_text(encoding="utf-8"))
        return Record(d.get("model", ""), list(d.get("serials", [])), list(d.get("app_ids", [])))
    except (OSError, ValueError):
        return from_reports(parent)


def report_labels(en):
    """A report field label in every language (reports are written in the interface language of
    the computer that made them): regex alternatives, English first."""
    from .i18n import languages
    found = [en]
    for lang in languages():
        v = lang.texts.get(en)
        if isinstance(v, str) and v.strip() and v not in found:
            found.append(v.strip())
    return "|".join(re.escape(x) for x in found)


def _smartphone_re():
    return re.compile(r"^\s*(?:%s)\s*:\s*(.+?)\s*$" % report_labels("Smartphone"), re.M)


def _serial_re():
    # the "serial" word comes from sources.AdbSource.description ("ADB (%s), serial %s, Android %s")
    from .i18n import languages
    tpl = [lang.texts.get("ADB (%s), serial %s, Android %s") for lang in languages()]
    words = ["serial"] + [m.group(1) for t in tpl if isinstance(t, str)
                          for m in [re.search(r",\s*([^,%]+?)\s+%(?:2\$)?s\s*,", t)] if m]
    return re.compile(r"^\s*(?:%s)\s*:.*?\b(?:%s) ([^\s,]+)"
                      % (report_labels("Connection"), "|".join(re.escape(w) for w in dict.fromkeys(words))),
                      re.M)


def from_reports(parent):
    """Backups made before phone.json existed: the phone from their reports (model + ADB serial
    numbers; Wi-Fi debugging 'serials' are only ip:port and are ignored)."""
    model, serials = "", []
    smartphone_re, serial_re = _smartphone_re(), _serial_re()
    try:
        from .report import report_files
        reports = sorted(report_files(parent), key=lambda p: p.name)
    except OSError:
        return None
    for r in reports:
        try:
            text = r.read_text(encoding="utf-8", errors="replace")[:20000]
        except OSError:
            continue
        m = smartphone_re.search(text)
        model = model or (m.group(1) if m else "")
        for sn in serial_re.findall(text):
            if ":" not in sn and sn not in serials:
                serials.append(sn)
    return Record(model, serials, []) if (model or serials) else None


def save(parent, rec):
    p = _path(parent)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"model": rec.model, "serials": rec.serials, "app_ids": rec.app_ids},
                              indent=2), encoding="utf-8")
    os.replace(tmp, p)


def _same(a, b):
    return bool(a) and bool(b) and a.strip().casefold() == b.strip().casefold()


def compare(rec, pid):
    """MATCH / PROBABLE (only the model agrees) / NEW (folder knows no phone) / MISMATCH."""
    if rec is None or not (rec.model or rec.serials or rec.app_ids):
        return NEW
    # the serial number is the phone itself and decides (user 2026-11-22: the phone app had been
    # paired anew – new app id – and the backup of the SAME phone was refused)
    if pid.serial and rec.serials:
        return MATCH if pid.serial in rec.serials else MISMATCH
    if pid.app_id and rec.app_ids and pid.app_id in rec.app_ids:
        return MATCH
    # a different phone-app id alone is no proof of another phone: the id changes when the phone
    # app is reinstalled or paired again → same model = ask the user, else refused
    return PROBABLE if (_same(rec.model, pid.model) or _same_model_loose(rec.model, pid.model)) else MISMATCH


def _same_model_loose(a, b):
    """"Google Pixel 10 Pro" (file transfer) and "Pixel 10 Pro" (USB debugging / phone app): the same
    model with the maker's name in front – only "probably" (user test 2026-11-23: the backup over
    file transfer was refused as "another phone")."""
    a, b = (a or "").strip().casefold(), (b or "").strip().casefold()
    if not a or not b or a == b:
        return False
    short, long_ = sorted((a, b), key=len)
    return long_.endswith(" " + short)


def learn(parent, pid, result):
    """After a confirmed backup start: remember the phone's ids in the backup folder.
    Only with an exact match (or a new folder) - a model-only match never adds ids."""
    if result not in (MATCH, NEW):
        return
    rec = load(parent) or Record()
    rec.model = rec.model or pid.model
    if pid.serial and pid.serial not in rec.serials:
        rec.serials.append(pid.serial)
    if pid.app_id and pid.app_id not in rec.app_ids:
        rec.app_ids.append(pid.app_id)
    save(parent, rec)


def same_phone(a, b):
    """Is PhoneId b (read again right before copying) the phone a that was confirmed?"""
    if a.serial and b.serial:
        return a.serial == b.serial
    if a.app_id and b.app_id:
        return a.app_id == b.app_id
    return _same(a.model, b.model)


# --------------------------------------------------------------------------- connection speed

def usb_speed_mbit(vendor_names=("04e8", "18d1", "2717", "22b8", "2a70", "22d9", "12d1", "339b",
                                 "0fce", "2d95", "1004", "0bb4", "19d2", "17ef", "2ae5")):
    """Linux: link speed of the phone on the USB cable (480 = USB 2, 5000+ = USB 3), or None."""
    base = Path("/sys/bus/usb/devices")
    if not base.is_dir():
        return None
    for d in base.glob("*"):
        try:
            if (d / "idVendor").read_text().strip() in vendor_names:
                return int((d / "speed").read_text().strip())
        except (OSError, ValueError):
            continue
    return None


def speed_advice(pid, usb_mbit=None, on_cable=""):
    """(is_fastest, text) about the connection and how to make it faster.
    on_cable: a phone that is on the USB cable without USB debugging (adbsetup.detect_usb_phone)."""
    c = pid.connection
    if c == "usb-adb":
        if usb_mbit is not None and usb_mbit < 5000:
            return False, tr("USB cable with USB debugging, but only USB 2 speed (about 20–30 MB/s). "
                             "For about 2× faster: use a USB 3 cable (often blue plugs / “SS”) and a "
                             "USB 3 port on the computer.")
        return True, tr("USB cable with USB debugging – the fastest connection (about 25–50 MB/s).")
    if on_cable and c != "usb-adb":
        if usb_mbit and usb_mbit >= 5000:
            fix = tr("Faster (about 25–50 MB/s): the %s is already on the USB cable (USB 3), only USB "
                     "debugging is off – switch on “Allow backup” in the phone app (or switch on "
                     "USB debugging in the Developer options), then click Start again.", on_cable)
        else:
            fix = tr("Faster (about 25–50 MB/s): the %s is already on the USB cable, only USB "
                     "debugging is off – switch on “Allow backup” in the phone app (or switch on "
                     "USB debugging in the Developer options), then click Start again.", on_cable)
    else:
        fix = tr("Faster (about 25–50 MB/s): plug the phone in with a USB cable and switch on “Allow backup” "
                 "in the phone app (or switch on USB debugging in the Developer options).")
    if c in ("wifi-adb", "app-wifi"):
        return False, tr("Wi-Fi – slower (about 3–30 MB/s, depends on the Wi-Fi).") + " " + fix
    if c == "mtp":
        return False, (tr("USB file transfer (MTP) – slower (about 10–20 MB/s) and without a check on "
                          "the phone.") + " " + fix)
    return True, ""


# --------------------------------------------------------------------------- files in common

@dataclass
class Overlap:
    """Photos/videos of the connected phone that are already in a backup folder (user request
    2026-11-22: "usually there are overlapping files – it is quite likely the right backup")."""
    phone_files: int = 0          # photos/videos in the chosen folders on the phone
    same: int = 0                 # … in the backup with the same phone path and size
    hashed: int = 0               # … of those checked with the SHA-256 calculated on the phone
    hash_same: int = 0            # … identical

    @property
    def strong(self):
        """Clear evidence: several files with identical SHA-256 on the phone and in the backup, or
        (connection without phone hashes) many files with the same path and size."""
        return self.hash_same >= 3 or (self.hashed == 0 and self.same >= 10)

    @property
    def none(self):
        return self.phone_files > 0 and self.same == 0


def _index_rows(parent):
    import sqlite3
    p = Path(parent) / INTERNAL_DIR / "index.sqlite"
    if not p.is_file():
        return {}
    try:
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            return {(sp, size): sha for sp, size, sha in
                    db.execute("SELECT source_path, size, sha256 FROM files")}
        finally:
            db.close()
    except sqlite3.Error:
        return {}


def overlap(src, files, parent, sample=12):
    """Overlap of the phone's file list `files` (SourceFile) with the backup folder `parent`
    (read-only). A sample of the common files is checked with the phone's own SHA-256."""
    from .media import category_for
    classify = getattr(src, "category_of", None) or (lambda f: category_for(f.name))
    media = [sf for sf in files if classify(sf)]
    rows = _index_rows(parent)
    res = Overlap(phone_files=len(media))
    common = [(sf, rows[(sf.source_key, sf.size)]) for sf in media if (sf.source_key, sf.size) in rows]
    res.same = len(common)
    if common and getattr(src, "supports_phone_hash", False):
        step = max(1, len(common) // sample)
        pick = common[::step][:sample]
        try:
            got = src.phone_hashes([sf.rel for sf, _ in pick]) or {}
        except Exception:  # noqa: BLE001 - without hashes: path + size
            got = {}
        for sf, sha in pick:
            if sf.rel in got:
                res.hashed += 1
                res.hash_same += got[sf.rel] == sha
    return res


def overlap_text(o):
    """One paragraph for the "Is this the right phone?" question."""
    if o.none:
        return tr("None of the %d photos and videos on the phone is in this backup – it is probably a "
                  "different phone.", o.phone_files)
    if not o.same:
        return ""
    t = tr("%d of the %d photos and videos on the phone are already in this backup (same place on the "
           "phone, same size).", o.same, o.phone_files)
    if o.hashed:
        t += " " + tr("%d of them were checked with the SHA-256 calculated on the phone: %d identical.",
                      o.hashed, o.hash_same)
    if o.strong:
        t += " " + tr("It is very likely the right phone (a new phone set up from this one's photos could "
                      "also have them).")
    return t
