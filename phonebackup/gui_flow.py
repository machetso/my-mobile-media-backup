"""A row of buttons that wraps onto the next line when the window is narrow (user 2026-11-22: in a
half-screen window the buttons on the right were cut off and the page scrolled sideways)."""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLabel, QLayout, QSizePolicy, QWidget, QWidgetItem


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def addWidget(self, w):                        # noqa: N802 - Qt name
        super().addWidget(w)

    def addStretch(self, *_a):                     # noqa: N802 - rows written for QHBoxLayout
        pass

    def addLayout(self, layout):                   # noqa: N802 - a nested row: its widgets join the flow
        holder = QWidget()
        holder.setLayout(layout)
        self.addWidget(holder)

    def count(self):
        return len(self._items)

    def itemAt(self, i):                           # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):                           # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):                 # noqa: N802
        return Qt.Orientations(0)

    def hasHeightForWidth(self):                   # noqa: N802
        return True

    def heightForWidth(self, width):               # noqa: N802
        return self._do(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):                   # noqa: N802
        super().setGeometry(rect)
        need = self._do(rect, False)
        # a wrapped second line needs room: tell the parent layout, otherwise the next line was drawn
        # over the widgets below (user 2026-11-22, Backup drives tab)
        holder = self.parentWidget()
        if holder is not None and holder.minimumHeight() != need:
            holder.setMinimumHeight(need)

    def sizeHint(self):                            # noqa: N802
        return self.minimumSize()

    def minimumSize(self):                         # noqa: N802
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test):
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line = r.x(), r.y(), 0
        for it in self._items:
            w = it.widget()
            if w is not None and w.isHidden():
                continue
            hint = it.sizeHint()
            nx = x + hint.width() + self._spacing
            if nx - self._spacing > r.right() + 1 and line > 0:
                x, y = r.x(), y + line + self._spacing
                nx, line = x + hint.width() + self._spacing, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x, line = nx, max(line, hint.height())
        return y + line - rect.y() + m.bottom()


def flow_row(*widgets):
    """A wrapping row with these widgets (QWidget to put into a layout)."""
    holder = QWidget()
    holder.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    lay = FlowLayout(holder)
    for w in widgets:
        if isinstance(w, QWidgetItem):
            lay.addItem(w)
        else:
            lay.addWidget(w)
    return holder


class WrapLabel(QLabel):
    """A word-wrapped label that asks for the height of ALL its lines. Pages that use minimum heights
    (gui_backups._MinHeightLayout) gave a wrapped label only one line, so the widgets below were drawn
    over its text (user 2026-11-22, Drives tab)."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)

    def resizeEvent(self, event):                  # noqa: N802
        super().resizeEvent(event)
        need = self.heightForWidth(self.width()) if self.text() else 0
        if need > 0 and self.minimumHeight() != need:
            self.setMinimumHeight(need)

    def setText(self, text):                       # noqa: N802
        super().setText(text)
        need = self.heightForWidth(self.width()) if text and self.width() > 0 else 0
        self.setMinimumHeight(max(need, 0))
