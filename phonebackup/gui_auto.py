"""Auto backup on the start screen (user request 2026-11-23): an on/off switch per phone, a "?" with
the help, and a row of blocks – one per requirement (autoready), green when done – each with its
own mouse-over hint."""

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QAbstractButton, QHBoxLayout, QLabel, QMessageBox, QSizePolicy, QToolButton,
                               QVBoxLayout, QWidget)

from . import autoready
from .i18n import tr

ON, OFF, KNOB, DISABLED = "#2fa45a", "#3a3a4a", "#f2dcc4", "#26262f"
DONE, TODO, OPTIONAL = "#2fa45a", "#3a3a4a", "#c76a00"


class ToggleSwitch(QAbstractButton):
    """An on/off switch with its label: [ ◯━━ ] AUTO BACKUP."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        f = QFont(self.font())
        f.setBold(True)
        f.setCapitalization(QFont.AllUppercase)
        self.setFont(f)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def sizeHint(self):
        fm = self.fontMetrics()
        return QSize(46 + 10 + fm.horizontalAdvance(self.text()) + 4, max(24, fm.height() + 6))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        track = QRectF(1, (h - 22) / 2, 44, 22)
        on, enabled = self.isChecked(), self.isEnabled()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(DISABLED if not enabled else ON if on else OFF))
        p.drawRoundedRect(track, 11, 11)
        knob = QRectF(track.right() - 20 if on else track.left() + 2, track.top() + 2, 18, 18)
        p.setBrush(QColor(KNOB if enabled else "#5c5c66"))
        p.drawEllipse(knob)
        p.setPen(QColor("#f2dcc4" if enabled else "#5c5c66"))
        p.drawText(QRectF(track.right() + 10, 0, self.width() - track.right() - 10, h),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())


class BlockBar(QWidget):
    """One block per requirement, in their order: green = done, grey = not yet; hints on each."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(4)
        self.blocks = []
        self.caption = QLabel()
        self.caption.setStyleSheet("color:#9a9aa8")

    def set_reqs(self, reqs):
        if len(self.blocks) != len(reqs):
            while self._lay.count():
                it = self._lay.takeAt(0)
                if it.widget() is not None and it.widget() is not self.caption:
                    it.widget().deleteLater()
            self.blocks = []
            for _r in reqs:
                b = QLabel()
                b.setFixedSize(26, 12)
                self.blocks.append(b)
                self._lay.addWidget(b)
            self._lay.addSpacing(6)
            self._lay.addWidget(self.caption)
        for b, r in zip(self.blocks, reqs):
            # optional and not done: orange, not grey – the switch does not wait for it (2026-11-23)
            color = DONE if r.ok else OPTIONAL if r.optional else TODO
            b.setStyleSheet(f"background:{color};border-radius:4px;"
                            + ("" if r.ok or r.optional else "border:1px solid #5c5c66;"))
            b.setToolTip(r.hint)
        need = [r for r in reqs if not r.optional]
        n = sum(r.ok for r in need)
        text = tr("%d of %d ready", n, len(need))
        if n == len(need):                    # only once it can be used: what the missing options mean
            notes = {"wifi": tr("cable only"), "battery": tr("asks once per backup")}
            text += "".join(" · " + notes[r.id] for r in reqs if r.optional and not r.ok and r.id in notes)
        self.caption.setText(text)
        self.caption.setToolTip("\n\n".join(r.hint for r in reqs))


class AutoBackupRow(QWidget):
    """[switch] [?] [blocks] under a phone's name."""
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 2)
        outer.setSpacing(3)
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        outer.addLayout(lay)
        # the next step in plain words, under the blocks (user request 2026-11-23)
        self.next = QLabel()
        self.next.setWordWrap(True)
        self.next.setStyleSheet("color:#ffcc99")
        outer.addWidget(self.next)
        self.switch = ToggleSwitch(tr("Auto backup"))
        self.switch.toggled.connect(self.toggled.emit)
        self.switch.toggled.connect(self._show_next)
        self._reqs = []
        self.help = QToolButton()
        self.help.setText("?")
        self.help.setToolTip(tr("What Auto backup needs – step by step"))
        self.help.setFixedSize(24, 24)
        self.help.setStyleSheet("QToolButton{border-radius:12px;background:#9999ff;color:#000;font-weight:700}"
                                "QToolButton:hover{background:#ffcc99}")
        self.help.clicked.connect(self.show_help)
        self.bar = BlockBar()
        lay.addWidget(self.switch)
        lay.addWidget(self.help)
        lay.addSpacing(6)
        lay.addWidget(self.bar)
        lay.addStretch(1)

    def update_state(self, reqs, on):
        ready = autoready.ready(reqs)
        self.bar.set_reqs(reqs)
        self._reqs = list(reqs)
        self._show_next(on)
        self.switch.blockSignals(True)
        self.switch.setChecked(bool(on))
        self.switch.blockSignals(False)
        self.switch.setEnabled(ready)
        n = sum(r.ok for r in reqs if not r.optional)
        need = sum(1 for r in reqs if not r.optional)
        self.switch.setToolTip(
            (tr("On: the backup runs by itself when the phone is near (at most once an hour).") if on else
             tr("Off: backups only when you start them.")) if ready else
            tr("Not possible yet – %d of %d steps done. Point at the blocks or click “?”.", n, need))

    def _show_next(self, on):
        nxt = autoready.next_step(self._reqs, bool(on)) if self._reqs else ""
        self.next.setText(nxt)
        self.next.setVisible(bool(nxt))

    def show_help(self):
        box = QMessageBox(QMessageBox.Information, tr("Auto backup"), autoready.help_text(), parent=self)
        box.setTextFormat(Qt.RichText)
        box.exec()
