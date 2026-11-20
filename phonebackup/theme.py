"""The look of the window (user request 2026-11-18): "Starship" – a control-panel look inspired by
TV science fiction from the late 1980s (black background, rounded colour bars, an elbow frame
around the window, narrow capitals) – or "Classic" (the plain system look).

Everything visual lives here: the style sheet, the colours used in texts, and the frame with the
side navigation. The window code only asks `starship()` and uses the names below.
"""

import atexit
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QGroupBox, QStyle, QStyleOptionGroupBox, QHeaderView, QLabel, QPushButton, QSizePolicy, QTabBar, QToolButton,
                               QVBoxLayout, QWidget)

STARSHIP, CLASSIC = "starship", "classic"
THEMES = (STARSHIP, CLASSIC)

# control-panel colours
ORANGE = "#ff9966"
GOLD = "#ffaa33"
PEACH = "#ffcc99"
LILAC = "#cc99cc"
LAVENDER = "#9999ff"
BLUE = "#99ccff"
RED = "#ee5555"
MAUVE = "#cc6699"
BLACK = "#000000"
TEXT = "#f2dcc4"               # body text: a warm off-white, easy to read on black
DIM = "#8a8a99"

# status colours readable on black (the classic ones are made for a light background)
STATUS = {"GREEN": "#55dd88", "ORANGE": "#ffaa33", "RED": "#ff6655", "GRAY": "#9a9aa8"}

_current = CLASSIC


def choice(cfg):
    """Always Starship: the user no longer chooses the look (user request 2026-11-19). The classic
    look stays in the code (the window without apply(), e.g. in the tests)."""
    return STARSHIP


def starship():
    return _current == STARSHIP


def _family():
    """A narrow font, as on the panels: the first one installed (Bahnschrift comes with Windows 10+)."""
    have = set(QFontDatabase.families())
    for fam in ("Antonio", "Oswald", "Bahnschrift SemiCondensed", "Bahnschrift", "Fira Sans Condensed",
                "Roboto Condensed", "Ubuntu Condensed", "Liberation Sans Narrow", "Arial Narrow",
                "DejaVu Sans Condensed"):
        if fam in have:
            return fam
    return ""


def apply(app, name):
    """Set the look for the whole program (before the window is built)."""
    global _current
    _current = name
    if name != STARSHIP:
        return
    fam = _family()
    base = QFont(app.font())
    if fam:
        base.setFamily(fam)
    base.setPointSizeF(max(base.pointSizeF(), 10.0) + 1.5)
    app.setFont(base)
    global _caps_filter
    _caps_filter = _Capitals(app)
    app.installEventFilter(_caps_filter)

    pal = QPalette()
    for role, col in ((QPalette.Window, BLACK), (QPalette.WindowText, TEXT), (QPalette.Base, "#0b0b10"),
                      (QPalette.AlternateBase, "#14141c"), (QPalette.Text, TEXT), (QPalette.Button, ORANGE),
                      (QPalette.ButtonText, BLACK), (QPalette.Highlight, ORANGE),
                      (QPalette.HighlightedText, BLACK), (QPalette.ToolTipBase, BLACK),
                      (QPalette.ToolTipText, PEACH), (QPalette.Link, BLUE), (QPalette.LinkVisited, LILAC),
                      (QPalette.Mid, "#3a3a4a"), (QPalette.PlaceholderText, DIM), (QPalette.BrightText, PEACH)):
        pal.setColor(role, QColor(col))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#5c5c66"))
    app.setPalette(pal)
    app.setStyleSheet(STYLE.replace("@ARROWS@", _arrow_dir()))


_caps_filter = None


class _Capitals(QObject):
    """Buttons, tabs and table headers in capitals, as on the panels. Style sheets cannot do that
    and replace class fonts, so each such widget gets its own font when it is first shown."""

    KINDS = (QPushButton, QToolButton, QTabBar, QHeaderView)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Paint and isinstance(obj, QGroupBox):
            paint_elbow(obj)
            return False                 # the group box then draws its title over it
        # tab bars: their tab widget hands its own font down after polishing, so again when shown
        if (event.type() == QEvent.Polish or (event.type() == QEvent.Show and isinstance(obj, QTabBar))) \
                and isinstance(obj, self.KINDS):
            f = obj.font()
            if f.capitalization() != QFont.AllUppercase:
                f = QFont(f)
                f.setCapitalization(QFont.AllUppercase)
                f.setLetterSpacing(QFont.PercentageSpacing, 100)
                obj.setFont(f)
        return False


def paint_elbow(box, color=LILAC):
    """The elbow of a group box: a thick bar on the left bending into a thin bar along the top, with a
    smooth outer and inner curve (user request 2026-11-19: no visible corner where they meet)."""
    opt = QStyleOptionGroupBox()
    box.initStyleOption(opt)
    frame = box.style().subControlRect(QStyle.CC_GroupBox, opt, QStyle.SC_GroupBoxFrame, box)
    side, top, outer, inner = 10.0, 4.0, 22.0, 12.0
    x0, y0, w, h = float(frame.x()), float(frame.y()), float(frame.width()), float(frame.height())
    if box.title():       # the thin bar through the middle of the title letters (user request 2026-11-19)
        label = box.style().subControlRect(QStyle.CC_GroupBox, opt, QStyle.SC_GroupBoxLabel, box)
        fm = box.fontMetrics()
        baseline = label.y() + (label.height() - fm.height()) / 2 + fm.ascent()
        mid = baseline - fm.capHeight() / 2 - top / 2
        h += y0 - mid
        y0 = mid
    if box.layoutDirection() == Qt.RightToLeft:
        x0, w = 0.0, float(box.width())
    path = QPainterPath()
    path.moveTo(0, h)
    path.lineTo(0, outer)
    path.cubicTo(0, outer * 0.45, outer * 0.45, 0, outer, 0)
    path.lineTo(w, 0)
    path.lineTo(w, top)
    path.lineTo(side + inner, top)
    path.cubicTo(side + inner * 0.45, top, side, top + inner * 0.45, side, top + inner)
    path.lineTo(side, h)
    path.closeSubpath()
    p = QPainter(box)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(x0, y0)
    if box.layoutDirection() == Qt.RightToLeft:      # Hebrew: the elbow on the right
        p.translate(w, 0)
        p.scale(-1, 1)
    p.fillPath(path, QColor(color))
    p.end()


def _arrow_dir():
    """Small arrow pictures for combo and spin boxes (style sheets need files for that)."""
    d = Path(tempfile.mkdtemp(prefix="msmb-theme-"))
    atexit.register(shutil.rmtree, d, ignore_errors=True)
    for name, pts in (("down", "1,3 11,3 6,9"), ("up", "1,9 11,9 6,3")):
        (d / f"{name}.svg").write_text(f"<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12'>"
                                       f"<polygon points='{pts}' fill='{BLACK}'/></svg>", encoding="utf-8")
    return d.as_posix()


def recolor(*modules):
    """Status colours (GREEN, ORANGE, RED, GRAY in the window modules) readable on black."""
    if not starship():
        return
    for mod in modules:
        for key, val in STATUS.items():
            if hasattr(mod, key):
                setattr(mod, key, val)


# boxes with a coloured bar on the left: a straight line, rounded only on the right, and the
# text kept a little away from it (user request 2026-11-19 – the rounded bar looked like a bracket)
BAR = 8
BAR_GAP = 12
_STRAIGHT = "border-radius:0;border-top-right-radius:10px;border-bottom-right-radius:10px;"


def bar_margins(layout, left, top, right, bottom):
    """Content margins of a box with the left bar: the text starts BAR_GAP after the line."""
    if starship():
        left = BAR + BAR_GAP
    layout.setContentsMargins(left, top, right, bottom)


# a highlighted box ("a known phone is near", "an update for the phone app") – both looks
def notice_css(object_name):
    if starship():
        return (f"#{object_name}{{background:#1c1408;border:none;border-left:{BAR}px solid {GOLD};"
                f"{_STRAIGHT}}} #{object_name} QLabel{{color:{PEACH};background:transparent}}")
    return (f"#{object_name}{{background:#fff4d6;border:1px solid #e0b84a;border-radius:6px}}"
            f"#{object_name} QLabel{{color:#4a3800}}")


def tip_css():
    if starship():
        return (f"QLabel{{background:#1c1408;color:{PEACH};border-left:{BAR}px solid {GOLD};{_STRAIGHT}"
                f"padding:8px 8px 8px {BAR_GAP}px}}")
    return "QLabel{background:#fff4c2;color:#3a2e00;border-radius:6px;padding:8px}"


def card_css(object_name):
    if starship():
        return f"#{object_name}{{background:#0b0b12;border:none;border-left:{BAR}px solid {LAVENDER};{_STRAIGHT}}}"
    return f"#{object_name}{{border:1px solid palette(mid);border-radius:6px}}"


# whole status banner coloured by how well the phone is connected (bg, text, symbol)
def banner_levels(classic):
    if not starship():
        return classic
    return {"none": (RED, BLACK, "✕"), "possible": (GOLD, BLACK, "▲"),
            "slow": (LAVENDER, BLACK, "●"), "fast": ("#77dd99", BLACK, "●")}


STYLE = f"""
QWidget {{ color: {TEXT}; }}
QMainWindow, QDialog, QMessageBox, QScrollArea, QScrollArea > QWidget > QWidget, QStackedWidget {{
    background: {BLACK};
}}
QToolTip {{ background: {BLACK}; color: {PEACH}; border: 2px solid {ORANGE}; border-radius: 8px; padding: 6px; }}

/* buttons: rounded colour pills with black capitals */
QPushButton {{
    background: {ORANGE}; color: {BLACK}; border: none; border-radius: 15px;
    padding: 6px 13px; min-height: 20px; font-weight: 600;
}}
QPushButton:hover {{ background: {PEACH}; }}
QPushButton:pressed {{ background: #ffffff; }}
QPushButton:default, QPushButton[role="primary"] {{ background: {GOLD}; }}
QPushButton:disabled {{ background: #3a2e28; color: #77685c; }}
QPushButton:checked {{ background: {LILAC}; }}
QDialogButtonBox QPushButton, QMessageBox QPushButton {{ min-width: 90px; }}

QToolButton {{
    background: {LILAC}; color: {BLACK}; border: none; border-radius: 12px; padding: 4px 8px; font-weight: 600;
}}
QToolButton:hover {{ background: {PEACH}; }}
QToolButton:pressed {{ background: #ffffff; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

/* side navigation of the frame */
QPushButton#lcarsNav {{
    border-radius: 0; text-align: right; padding: 4px 10px 4px 6px; min-height: 44px;
}}
QPushButton#lcarsNav[current="true"] {{ background: #ffffff; }}
QFrame#lcarsFill {{ border: none; }}

/* tabs: blocks in a row, the open one bright */
QTabWidget::pane {{ border: none; border-top: 4px solid {LAVENDER}; top: -2px; }}
QTabBar::tab {{
    background: {LAVENDER}; color: {BLACK}; border: none; padding: 7px 18px; margin: 0 4px 4px 0;
    font-weight: 600; min-width: 60px;
}}
QTabBar::tab:first {{ border-top-left-radius: 14px; border-bottom-left-radius: 14px; }}
QTabBar::tab:last {{ border-top-right-radius: 14px; border-bottom-right-radius: 14px; }}
QTabBar::tab:only-one {{ border-radius: 14px; }}
QTabBar::tab:selected {{ background: {ORANGE}; }}
QTabBar::tab:hover:!selected {{ background: {BLUE}; }}

/* group boxes: the elbow (thick left bar + top bar) is painted by _Capitals (paint_elbow) –
   style sheets draw a visible corner where a thick and a thin border meet; the title sits in the gap */
QGroupBox {{
    border: none; margin-top: 16px; padding: 18px 6px 6px 22px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left; left: 26px; top: 3px;
    padding: 0 8px; color: {ORANGE}; background: {BLACK};
}}

/* input fields */
QLineEdit, QSpinBox, QComboBox, QTextEdit, QTextBrowser, QPlainTextEdit {{
    background: #0b0b10; color: {TEXT}; border: 2px solid #34344a; border-radius: 10px; padding: 4px 8px;
    selection-background-color: {ORANGE}; selection-color: {BLACK};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{ border-color: {ORANGE}; }}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{ color: #5c5c66; border-color: #222230; }}
QComboBox::drop-down {{ border: none; width: 26px; background: {LAVENDER};
    border-top-right-radius: 8px; border-bottom-right-radius: 8px; }}
QComboBox::down-arrow {{ image: url(@ARROWS@/down.svg); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {BLACK}; border: 2px solid {ORANGE}; border-radius: 0;
    selection-background-color: {ORANGE}; selection-color: {BLACK}; }}
QSpinBox::up-button, QSpinBox::down-button {{ background: {LAVENDER}; border: none; width: 18px; }}
QSpinBox::up-button {{ border-top-right-radius: 8px; }}
QSpinBox::down-button {{ border-bottom-right-radius: 8px; }}
QSpinBox::up-arrow {{ image: url(@ARROWS@/up.svg); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url(@ARROWS@/down.svg); width: 10px; height: 10px; }}

/* lists and tables */
QListWidget, QTreeWidget, QTableWidget, QListView, QTreeView {{
    background: #07070b; alternate-background-color: #101018; color: {TEXT};
    border: 2px solid #34344a; border-radius: 12px; padding: 4px; outline: none;
}}
QListWidget::item, QTreeWidget::item {{ padding: 3px 4px; border-radius: 6px; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: {ORANGE}; color: {BLACK}; }}
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {{ background: #1e1e2c; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: {LAVENDER}; color: {BLACK}; border: none; padding: 4px 8px;
    margin-right: 3px; font-weight: 600; }}
QHeaderView::section:first {{ border-top-left-radius: 9px; border-bottom-left-radius: 9px; }}

/* check boxes and radio buttons */
QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 2px solid {LAVENDER};
    background: {BLACK}; }}
QCheckBox::indicator:checked {{ background: {ORANGE}; border-color: {ORANGE}; }}
QCheckBox::indicator:disabled {{ border-color: #34344a; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 10px; border: 2px solid {LAVENDER};
    background: {BLACK}; }}
QRadioButton::indicator:checked {{ background: {ORANGE}; border-color: {ORANGE}; }}

/* progress: a segmented bar */
QProgressBar {{ background: #121218; border: none; border-radius: 9px; min-height: 18px; max-height: 18px;
    color: {BLACK}; text-align: center; padding: 2px; }}
QProgressBar::chunk {{ background: {GOLD}; width: 12px; margin-right: 3px; border-radius: 3px; }}

/* scroll bars: slim rounded handles */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle {{ background: {LAVENDER}; border-radius: 4px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {PEACH}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* menus */
QMenu {{ background: {BLACK}; border: 2px solid {ORANGE}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ color: {PEACH}; padding: 6px 26px 6px 18px; border-radius: 9px; }}
QMenu::item:selected {{ background: {ORANGE}; color: {BLACK}; }}
QMenu::separator {{ height: 3px; background: {LILAC}; margin: 5px 8px; }}
QMenu::indicator {{ width: 12px; height: 12px; border-radius: 6px; margin-left: 4px; }}
QMenu::indicator:checked {{ background: {GOLD}; }}

QSplitter::handle {{ background: {BLACK}; }}
QSplitter::handle:vertical {{ height: 8px; image: none; border-top: 3px solid #34344a; margin: 2px 40px; }}
QFrame[frameShape="4"], QFrame[frameShape="5"] {{ color: {LILAC}; }}
QLabel {{ background: transparent; }}
"""


# =========================================================================== frame

class _NavButton(QPushButton):
    """A side button whose label wraps (long words in German …), right-aligned and vertically centred."""

    def __init__(self, text, icon=None):
        super().__init__()
        self.setAccessibleName(text)
        self.label = QLabel(text.upper())
        self.label.setWordWrap(True)
        # vertically centred in its box, right-aligned (user request 2026-11-19)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        # bigger than the tabs (user request 2026-11-19); smaller only if one word would not fit
        base = QApplication.font()
        f = QFont(base)
        f.setWeight(QFont.DemiBold)
        f.setPointSizeF(base.pointSizeF() * 1.3 if base.pointSizeF() > 0 else 15)
        words = self.label.text().split() or [""]
        while (f.pointSizeF() > base.pointSizeF() and
               max(QFontMetrics(f).horizontalAdvance(w) for w in words) > LcarsFrame.SIDE - 16):
            f.setPointSizeF(f.pointSizeF() - 0.5)
        self.label.setFont(f)
        self.label.setStyleSheet(f"color:{BLACK};font-weight:600;background:transparent")
        if icon is not None:            # a symbol instead of the word (the gear – user request 2026-11-19)
            self.label.setPixmap(icon.pixmap(26, 26))
            self.setToolTip(text)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 3, 9, 4)
        lay.addWidget(self.label)

    def sizeHint(self):
        return QSize(LcarsFrame.SIDE, max(44, self.label.heightForWidth(LcarsFrame.SIDE - 15) + 8))

    def minimumSizeHint(self):
        return self.sizeHint()


class _GlobeButton(QToolButton):
    """A mini globe in the frame colours; a click opens the language menu."""

    SIZE = 28

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setPopupMode(QToolButton.InstantPopup)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName("Language")
        self.setStyleSheet("QToolButton{border:none;background:transparent}"
                           "QToolButton::menu-indicator{image:none;width:0}")

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hot = self.underMouse() or self.isDown()
        r = QRectF(1.5, 1.5, self.SIZE - 3, self.SIZE - 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(PEACH if hot else LILAC))
        p.drawEllipse(r)
        pen = QPen(QColor(BLACK), 1.6)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        c, rad = r.center(), r.width() / 2
        p.drawEllipse(QRectF(c.x() - rad * 0.45, r.top(), rad * 0.9, r.height()))     # meridian
        p.drawLine(QPointF(c.x(), r.top()), QPointF(c.x(), r.bottom()))
        p.drawLine(QPointF(r.left(), c.y()), QPointF(r.right(), c.y()))                # equator
        for dy in (-0.5, 0.5):                                                          # parallels
            y = c.y() + dy * rad
            half = rad * (1 - dy * dy) ** 0.5
            p.drawLine(QPointF(c.x() - half, y), QPointF(c.x() + half, y))
        p.end()


class LcarsFrame(QWidget):
    """The window frame: an elbow at the top and at the bottom (a thick bar on the left that bends
    into a thin bar along the edge), the program name in the top bar and the side navigation in
    between. `content` (the real pages) sits inside the frame."""

    navigate = Signal(str)

    SIDE = 150            # width of the left column
    TOP = 22              # thickness of the top bar
    BOTTOM = 14           # thickness of the bottom bar
    ELBOW_TOP = 74        # height of the top elbow block
    ELBOW_BOTTOM = 46
    GAP = 6

    def __init__(self, content, title, subtitle, nav, bottom=None, lower=()):
        """nav: [(key, text), …] for the side buttons; lower: the same, placed at the foot of the
        column right above `bottom` (Manual – user request 2026-11-20); bottom: (key, text) for the
        red button at the foot of the column (About – user request 2026-11-19), None = a plain red
        block."""
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.title = title.upper()
        self.subtitle = subtitle.upper()
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(0)
        side = QVBoxLayout()
        side.setContentsMargins(0, self.ELBOW_TOP + self.GAP, 0, self.ELBOW_BOTTOM + self.GAP)
        side.setSpacing(self.GAP)
        colors = [GOLD, LILAC, LAVENDER, ORANGE, BLUE, MAUVE]
        self.buttons = {}
        fill = QFrame()                  # the rest of the column: a plain bar with a code number
        fill.setObjectName("lcarsFill")
        fill.setFixedWidth(self.SIDE)
        fill.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        fill.setStyleSheet(f"QFrame#lcarsFill{{background:{LILAC}}}")
        items = [(item, False) for item in nav] + [(item, True) for item in lower]
        for i, ((key, text, *icon), low) in enumerate(items):
            if low and side.indexOf(fill) < 0:          # the filler bar before the lower buttons
                side.addWidget(fill, 1)
            b = _NavButton(text, icon[0] if icon else None)
            b.setObjectName("lcarsNav")
            b.setFixedWidth(self.SIDE)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton#lcarsNav{{background:{colors[i % len(colors)]}}}"
                            f"QPushButton#lcarsNav:hover{{background:{PEACH}}}"
                            f"QPushButton#lcarsNav[current=\"true\"]{{background:#ffffff}}")
            b.clicked.connect(lambda _c=False, k=key: self.navigate.emit(k))
            side.addWidget(b)
            self.buttons[key] = b
        if side.indexOf(fill) < 0:
            side.addWidget(fill, 1)
        if bottom:
            key, text = bottom
            short = _NavButton(text)
            short.setObjectName("lcarsNav")
            short.setFixedWidth(self.SIDE)
            short.setCursor(Qt.PointingHandCursor)
            short.setStyleSheet(f"QPushButton#lcarsNav{{background:{RED}}}"
                                f"QPushButton#lcarsNav:hover{{background:{PEACH}}}")
            short.clicked.connect(lambda _c=False, k=key: self.navigate.emit(k))
            self.buttons[key] = short
        else:
            short = QFrame()
            short.setObjectName("lcarsFill")
            short.setFixedSize(self.SIDE, 26)
            short.setStyleSheet(f"QFrame#lcarsFill{{background:{RED}}}")
        side.addWidget(short)
        grid.addLayout(side, 0, 0)
        body = QVBoxLayout()
        body.setContentsMargins(10, self.TOP + 30, 10, self.BOTTOM + self.GAP + 4)
        body.addWidget(content)
        grid.addLayout(body, 0, 1)
        grid.setColumnStretch(1, 1)
        # the language: a small globe at the right end of the top bar (user request 2026-11-19)
        self.globe = _GlobeButton(self)
        self.globe.setToolTip("Language")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        g = self.globe
        x = 2 if self.layoutDirection() == Qt.RightToLeft else self.width() - g.width() - 2
        g.move(x, 0)
        g.raise_()

    def set_current(self, key):
        for k, b in self.buttons.items():
            b.setProperty("current", "true" if k == key else "false")
            b.style().unpolish(b)
            b.style().polish(b)

    def paintEvent(self, _event):
        """The frame is drawn once into a picture and only copied afterwards (user 2026-11-20: the
        program felt slow while the nearby line moved – every animation step repainted the whole
        frame, paths and texts included)."""
        dpr = self.devicePixelRatioF()
        key = (self.width(), self.height(), dpr, self.layoutDirection(), self.title, self.subtitle,
               self.font().key())
        if getattr(self, "_cache_key", None) != key:
            pix = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
            pix.setDevicePixelRatio(dpr)
            pix.fill(QColor(BLACK))
            self._paint_frame(pix)
            self._cache, self._cache_key = pix, key
        p = QPainter(self)
        p.drawPixmap(0, 0, self._cache)
        p.end()

    def _paint_frame(self, device):
        p = QPainter(device)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(BLACK))
        w, h = self.width(), self.height()
        if self.layoutDirection() == Qt.RightToLeft:     # Hebrew: the frame on the right
            p.translate(w, 0)
            p.scale(-1, 1)
        S, T, B = self.SIDE, self.TOP, self.BOTTOM

        # top elbow: outer corner big, inner corner small
        title_font = QFont(self.font())
        title_font.setCapitalization(QFont.AllUppercase)
        title_font.setPixelSize(30)
        title_font.setWeight(QFont.DemiBold)
        sub_font = QFont(title_font)
        sub_font.setPixelSize(15)
        p.setFont(title_font)
        tw = p.fontMetrics().horizontalAdvance(self.title)
        p.setFont(sub_font)
        sw = p.fontMetrics().horizontalAdvance(self.subtitle)
        cap = _GlobeButton.SIZE + 4               # the globe at the right end
        text_end = w - cap - 10
        text_start = text_end - tw - sw - 30
        bar_end = max(S + 60, text_start - 10)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ORANGE))
        p.drawPath(self._elbow(0, 0, S, self.ELBOW_TOP, bar_end, T, top=True))
        # a short coloured block in the top bar, as on the panels
        seg = QRectF(min(bar_end - 90, S + 260), 0, 70, T)
        if seg.left() > S + 80:
            p.fillRect(seg.adjusted(-self.GAP, 0, self.GAP, 0), QColor(BLACK))
            p.fillRect(seg, QColor(LAVENDER))
        # the program name next to the bar, the version small after it
        if self.layoutDirection() == Qt.RightToLeft:
            p.resetTransform()
            text_start, text_end = w - text_end, w - text_start
        p.setPen(QColor(ORANGE))
        p.setFont(title_font)
        p.drawText(QRectF(text_start, -6, tw + 4, 40), Qt.AlignLeft | Qt.AlignTop, self.title)
        # the version on the same base line as the name (user request 2026-11-19)
        base = -6 + p.fontMetrics().ascent()
        p.setPen(QColor(LILAC))
        p.setFont(sub_font)
        p.drawText(QPointF(text_start + tw + 14, base), self.subtitle)
        if self.layoutDirection() == Qt.RightToLeft:
            p.translate(w, 0)
            p.scale(-1, 1)

        # bottom elbow
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(LAVENDER))
        p.drawPath(self._elbow(0, h - self.ELBOW_BOTTOM, S, self.ELBOW_BOTTOM, w * 0.55, B, top=False))
        p.fillRect(QRectF(w * 0.55 + self.GAP, h - B, w * 0.2, B), QColor(ORANGE))
        end = QPainterPath()
        end.setFillRule(Qt.WindingFill)        # the overlap is filled, not a hole (the "little circle")
        end.addRoundedRect(QRectF(w * 0.75 + 2 * self.GAP, h - B, w * 0.25 - 2 * self.GAP - 2, B), B / 2, B / 2)
        end.addRect(QRectF(w * 0.75 + 2 * self.GAP, h - B, B, B))
        p.fillPath(end.simplified(), QColor(GOLD))
        p.end()

    @staticmethod
    def _elbow(x, y, side, height, bar_end, bar, top):
        """A thick block `side` wide and `height` high bending into a thin bar to `bar_end`."""
        ro = min(side, height) * 0.75          # outer radius
        ri = bar * 1.4                         # inner radius
        path = QPainterPath()
        if top:
            path.moveTo(x, y + height)
            path.lineTo(x, y + ro)
            path.arcTo(QRectF(x, y, 2 * ro, 2 * ro), 180, -90)
            path.lineTo(bar_end, y)
            path.lineTo(bar_end, y + bar)
            path.lineTo(x + side + ri, y + bar)
            path.arcTo(QRectF(x + side, y + bar, 2 * ri, 2 * ri), 90, 90)
            path.lineTo(x + side, y + height)
        else:
            path.moveTo(x, y)
            path.lineTo(x, y + height - ro)
            path.arcTo(QRectF(x, y + height - 2 * ro, 2 * ro, 2 * ro), 180, 90)
            path.lineTo(bar_end, y + height)
            path.lineTo(bar_end, y + height - bar)
            path.lineTo(x + side + ri, y + height - bar)
            path.arcTo(QRectF(x + side, y + height - bar - 2 * ri, 2 * ri, 2 * ri), 270, -90)
            path.lineTo(x + side, y)
        path.closeSubpath()
        return path
