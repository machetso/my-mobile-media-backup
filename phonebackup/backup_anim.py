"""Small animation while a backup runs (user request 2026-11-19): the gold arrow of the app icon
with a bright pulse that moves inside the arrow from its bottom to its tip, again and again
(the first version had a ring around the arrow – user changed it the same day).
The phone app draws the same (BackupArrow in Starship.kt) – keep both alike.
"""

import math
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QPushButton, QWidget

from . import theme

# the arrow of assets/icon.svg, centred on (0, 0): tip at -58, base at 36
ARROW = [(0, -58), (40, -14), (16, -14), (16, 36), (-16, 36), (-16, -14), (-40, -14)]
TIP, NECK, BASE = -58.0, -14.0, 36.0
PERIOD = 1.4          # seconds for one pulse from bottom to top
BAND = 24.0           # half the height of the bright band (icon units)


def pulse_at(t):
    """Centre y of the bright band at time t – it enters below the base and leaves above the tip.
    The same formula as the phone app."""
    p = (t % PERIOD) / PERIOD
    return BASE + BAND - p * (BASE - TIP + 2 * BAND)


class BackupArrow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)
        self._t0 = time.monotonic()
        self.setVisible(False)
        self.setToolTip("")

    def sizeHint(self):
        h = max(44, self.fontMetrics().lineSpacing() * 3)
        return QSize(int(h * 0.85), h)

    def minimumSizeHint(self):
        return self.sizeHint()

    def start(self):
        self._t0 = time.monotonic()
        self.setVisible(True)
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.setVisible(False)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        s = min(w / 110.0, h / 112.0)              # arrow + margin in icon units
        p.translate(w / 2, h / 2 + 3 * s)
        p.scale(s, s)
        y = pulse_at(time.monotonic() - self._t0)
        shape = QPainterPath()
        shape.addPolygon(QPolygonF([QPointF(x, yy) for x, yy in ARROW]))
        shape.closeSubpath()
        p.fillPath(shape, QColor(theme.GOLD))
        bright = QColor("#fffbe6" if theme.starship() else "#fff3c4")
        clear = QColor(bright)
        clear.setAlpha(0)
        grad = QLinearGradient(0, y + BAND, 0, y - BAND)
        grad.setColorAt(0.0, clear)
        grad.setColorAt(0.5, bright)
        grad.setColorAt(1.0, clear)
        p.save()
        p.setClipPath(shape)
        p.fillRect(QRectF(-50, y - BAND, 100, 2 * BAND), grad)
        p.restore()
        p.setPen(QPen(QColor("#000000"), 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(shape)
        p.end()


def draw_scanner(p, color, x0, x1, mid, height, pos, glow_part, dim_alpha=70):
    """The nearby line (user request 2026-11-19): a thin dim line from x0 to x1 at height `mid`
    with a glowing light and a short fading trail. pos(dt) = the light's place 0 … 1 dt seconds
    ago. Also used on the "Connect phone…" button (2026-11-20)."""
    w = x1 - x0
    base = QColor(color)
    base.setAlpha(dim_alpha)
    p.fillRect(QRectF(x0, mid - 1, w, 2), base)              # the dim line
    glow = glow_part * w
    for k, alpha in ((0.12, 50), (0.06, 110), (0.0, 255)):   # the trail: fainter the older
        x = x0 + pos(k) * (w - glow) + glow / 2
        c = QColor(color)
        c.setAlpha(alpha)
        clear = QColor(color)
        clear.setAlpha(0)
        g = QLinearGradient(x - glow / 2, 0, x + glow / 2, 0)
        g.setColorAt(0.0, clear)
        g.setColorAt(0.5, c)
        g.setColorAt(1.0, clear)
        thick = height if k == 0.0 else height * 0.6
        p.fillRect(QRectF(x - glow / 2, mid - thick / 2, glow, thick), g)
    x = x0 + pos(0.0) * (w - glow) + glow / 2                 # a bright core in the middle of the light
    core = QLinearGradient(x - glow / 6, 0, x + glow / 6, 0)
    white = QColor("#fff3dc")
    clear = QColor(white)
    clear.setAlpha(0)
    core.setColorAt(0.0, clear)
    core.setColorAt(0.5, white)
    core.setColorAt(1.0, clear)
    p.fillRect(QRectF(x - glow / 6, mid - 1.5, glow / 3, 3), core)


class ScannerLine(QWidget):
    """"Phone is nearby" (user request 2026-11-19): a thin line with a glowing light that sweeps
    from left to right and back, leaving a short fading trail - in the colour of the box's bar.
    Runs only while it is visible."""

    PERIOD = 2.2          # seconds for one sweep there and back
    GLOW = 0.16           # width of the light as part of the line

    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self.color = QColor(color or theme.GOLD)
        self.setFixedHeight(10)
        self._timer = QTimer(self)
        self._timer.setInterval(40)              # 25 frames/s: smooth enough, half the work (2026-11-20)
        self._timer.timeout.connect(self.update)
        self._t0 = time.monotonic()

    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    @classmethod
    def position(cls, t):
        """0 … 1 … 0: the light's place on the line, slowing down at both ends like a pendulum."""
        import math
        return 0.5 - 0.5 * math.cos(2 * math.pi * (t % cls.PERIOD) / cls.PERIOD)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        draw_scanner(p, QColor(self.color), 0, self.width(), self.height() / 2, self.height(),
                     lambda dt: self.position(time.monotonic() - self._t0 - dt), self.GLOW)
        p.end()


class ScannerButton(QPushButton):
    """"Connect phone…" (user request 2026-11-20, third look the same day): the nearby line's
    light on the button itself – along its top edge and along its bottom edge, the two moving in
    opposite directions, inside the button. Runs only while the button is visible."""

    PERIOD = ScannerLine.PERIOD
    GLOW = 0.22           # width of the light as part of the edge
    THICK = 6.0           # height of the light (px)
    # the nearby line's gold is too close to the orange button – a clearer yellow of the same kind
    YELLOW = "#ffdd33"

    def __init__(self, text="", color=None, parent=None):
        super().__init__(text, parent)
        self.color = QColor(color or self.YELLOW)
        self._timer = QTimer(self)
        self._timer.setInterval(40)              # 25 frames/s, like the nearby line
        self._timer.timeout.connect(self.update)
        self._t0 = time.monotonic()
        self._glowing = True

    def set_glowing(self, on):
        """The light on/off (user request 2026-11-23: "Prepare folders" glows only when the drives
        differ)."""
        on = bool(on)
        if on == self._glowing:
            return
        self._glowing = on
        if on and self.isVisible():
            self._t0 = time.monotonic()
            self._timer.start()
        elif not on:
            self._timer.stop()
        self.update()

    def glowing(self):
        return self._glowing

    def showEvent(self, event):
        if self._glowing:
            self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)                # the normal button (and its text) first
        if not self._glowing:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rad = min(15.0, self.height() / 2)       # the Starship buttons' corners (theme.py: 15px)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), rad, rad)
        p.setClipPath(clip)                      # inside the button only
        t = time.monotonic() - self._t0
        x0, x1 = rad * 0.6, self.width() - rad * 0.6
        top = lambda dt: ScannerLine.position(t - dt)               # noqa: E731 - left → right first
        bottom = lambda dt: 1.0 - ScannerLine.position(t - dt)      # noqa: E731 - the opposite way
        draw_scanner(p, self.color, x0, x1, 2.0, self.THICK, top, self.GLOW, dim_alpha=0)
        draw_scanner(p, self.color, x0, x1, self.height() - 2.0, self.THICK, bottom, self.GLOW, dim_alpha=0)
        p.end()
