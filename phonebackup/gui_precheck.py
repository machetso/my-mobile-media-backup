"""Before the backup starts: which photos and videos are new, how long will it take – with
"Skip check" (user request 2026-11-22). The check runs in the background (precheck.run)."""

import threading
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QProgressBar, QPushButton,
                               QVBoxLayout)

from . import precheck, ui
from .gui_flow import WrapLabel
from .i18n import tr, trp


def _speed(src, cfg):
    """Expected MB/s of the current connection (measured before, else from the link)."""
    from . import adbsetup, connspeed, phoneid
    key = connspeed.current_key(adbsetup.source_key(src))
    usb = wifi = None
    try:
        if key in ("adb_usb", "mtp"):
            usb = phoneid.usb_speed_mbit()
        else:
            wifi = connspeed.wifi_link_mbit()
    except Exception:  # noqa: BLE001
        pass
    return connspeed.estimate(key, usb_mbit=usb, wifi_mbit=wifi, seen=cfg.get("speed_seen")), key


class PrecheckDialog(QDialog):
    progressed = Signal(str, int, int)
    finished_check = Signal(object, float, str)
    failed = Signal(str)

    def __init__(self, parent, src, folders, dests, parent_name, cfg, header="", warn=False, listing=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Start backup?"))
        self.setMinimumWidth(520)
        self.result_check = None
        self._stop = False
        self._skipping = False
        self._t0 = time.monotonic()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 22)   # the buttons were half covered by the bottom edge (2026-11-23)
        if header:
            h = WrapLabel(header)          # reports its full height: the window grows with it
            if warn:
                h.setStyleSheet("color:#c77700")
            lay.addWidget(h)
        self.status = WrapLabel(tr("Checking which photos and videos are new …"))
        lay.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        lay.addWidget(self.bar)
        self.result = WrapLabel("")
        self.result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.result.hide()
        lay.addWidget(self.result)
        box = QDialogButtonBox()
        self.start_btn = QPushButton(tr("Start backup"))
        self.skip_btn = QPushButton(tr("Skip check – start now"))
        self.skip_btn.setToolTip(tr("Start the backup right away; it works out the new files itself."))
        cancel = QPushButton(tr("Cancel"))
        box.addButton(self.start_btn, QDialogButtonBox.AcceptRole)
        box.addButton(self.skip_btn, QDialogButtonBox.ActionRole)
        box.addButton(cancel, QDialogButtonBox.RejectRole)
        self.start_btn.hide()
        self.start_btn.clicked.connect(self.accept)
        self.skip_btn.clicked.connect(self._skip)
        cancel.clicked.connect(self._cancel)
        lay.addWidget(box)
        self.progressed.connect(self._on_progress)
        self.finished_check.connect(self._on_done)
        self.failed.connect(self._on_failed)
        args = (src, folders, dests, parent_name, cfg, listing)
        self.thread = threading.Thread(target=self._work, args=args, daemon=True)
        self.thread.start()

    # ----------------------------------------------------------------- background
    def _work(self, src, folders, dests, parent_name, cfg, listing=None):
        try:
            mbs, key = _speed(src, cfg)
            res = precheck.run(src, folders, dests, parent_name, cfg,
                               progress=lambda ph, d, t: self.progressed.emit(ph, d, t),
                               stop=lambda: self._stop, listing=listing)
            self.finished_check.emit(res, mbs, key)
        except Exception as e:  # noqa: BLE001 - the backup itself reports problems with the phone
            self.failed.emit(str(e))

    # ----------------------------------------------------------------- GUI thread
    def _on_progress(self, phase, done, total):
        if self._skipping:
            return
        if phase == "list":
            self.status.setText(tr("Reading the file list from the phone …"))
            self.bar.setRange(0, 0)
            return
        self.bar.setRange(0, max(total, 1))
        self.bar.setValue(done)
        text = tr("Comparing %d photos/videos with the backup …", total)
        el = time.monotonic() - self._t0
        if done and total > done and el > 2:
            text += " " + tr("about %s left", ui.human_duration(el / done * (total - done)))
        self.status.setText(text)
        self._fit()

    def _fit(self):
        """The window as high as its texts (2026-11-23: texts and buttons were cut off)."""
        self.layout().activate()
        self.resize(self.width(), max(self.height(), self.sizeHint().height()))

    def _skip(self):
        self._skipping = self._stop = True
        self.skip_btn.setEnabled(False)
        self.status.setText(tr("Skipping the check – the backup starts as soon as the phone has "
                               "answered …"))

    def _cancel(self):
        self._stop = True
        self.result_check = None
        self.reject()

    def _on_failed(self, msg):
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.status.setText(tr("The check did not work (%s). The backup can start anyway – it works "
                               "out the new files itself.", msg))
        self.skip_btn.hide()
        self.start_btn.show()
        self.start_btn.setDefault(True)
        self._fit()
        if self._skipping:
            self.accept()

    def _on_done(self, res, mbs, key):
        self.result_check = res
        if self._skipping or not res.complete:
            self.accept()
            return
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.status.setText(tr("Check finished in %s.", ui.human_duration(res.seconds)))
        self.result.setText(describe(res, mbs, key))
        self.result.show()
        self.skip_btn.hide()
        self.start_btn.show()
        self.start_btn.setDefault(True)
        self.start_btn.setFocus()
        self._fit()


def describe(res, mbs, key):
    from . import connspeed
    lines = []
    if res.new:
        line = trp("%d new photo/video to back up (%s)", "%d new photos/videos to back up (%s)",
                   res.new, res.new, ui.human_size(res.new_bytes))
        if mbs:
            secs = res.new_bytes / (mbs * 1e6)
            how = tr(connspeed.LABELS.get(key, key)) if key else tr("this connection")
            if secs < 1:                       # not "about 0 s" (UI test 2026-11-23)
                line += " – " + tr("takes only a moment over %s", how)
            else:
                line += " – " + tr("about %s over %s (about %s MB/s)", ui.human_duration(secs), how, f"{mbs:g}")
        lines.append(line + ".")
    elif not res.from_drive and not res.maybe_there:
        lines.append(tr("No new photos or videos – everything is already backed up."))
    if res.from_drive:
        lines.append(trp("%d file is missing on a backup drive and is copied from the other drive "
                         "(%s, about %s).",
                         "%d files are missing on a backup drive and are copied from the other drive "
                         "(%s, about %s).", res.from_drive, res.from_drive,
                         ui.human_size(res.from_drive_bytes),
                         ui.human_duration(res.from_drive_bytes / (precheck.DRIVE_MBS * 1e6))))
    if res.maybe_there:
        lines.append(trp("%d more has the same name and size as a file in the backup folder that is "
                         "not in its list – it is compared at the start (SHA-256) and probably not "
                         "copied.",
                         "%d more have the same name and size as files in the backup folder that are "
                         "not in its list – they are compared at the start (SHA-256) and probably not "
                         "copied.", res.maybe_there, res.maybe_there))
    lines.append(tr("%d photos/videos in the chosen folders on the phone, %d of them already backed up.",
                    res.found, res.already))
    if res.gfs:
        lines.append(tr("Grandfather-Father-Son drives are not included in this count."))
    total = res.estimate_seconds(mbs)
    if res.new and res.from_drive and total:
        lines.append(tr("Altogether about %s.", ui.human_duration(total)))
    return "\n\n".join(lines)


def ask(parent, src, folders, dests, parent_name, cfg, header="", warn=False, listing=None):
    """Run the check with the dialog. Returns the Precheck (maybe incomplete when skipped, None
    when the check failed but the user starts anyway – then the backup reads the list itself), or
    False when the user cancelled."""
    prev = getattr(parent, "_precheck_thread", None)
    if prev is not None and prev.is_alive():          # an earlier, cancelled check still asks the phone
        prev.join(timeout=30)
    dlg = PrecheckDialog(parent, src, folders, dests, parent_name, cfg, header, warn, listing)
    parent._precheck_thread = dlg.thread
    ok = dlg.exec() == QDialog.Accepted
    if not ok:
        return False
    if dlg.thread.is_alive():                          # skipped while the phone still answers
        dlg.thread.join(timeout=120)
    return dlg.result_check
