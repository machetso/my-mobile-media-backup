"""Manage backups → "Backups" tab and the program settings' lists (user request 2026-11-10).

Backups tab: the known backups on top; choose one and
  * Phone      – its standard folders (used by "Update backup" on the start screen), update it now,
                 or back up other phone folders once,
  * Drives     – the backup drives of this backup,
  * Import     – folders (old drives, old phone copies) to import into it: sorted into YYYY/YY.MM or
                 with their original folder structure.
"New backup of an old phone / old drive" is a page of its own with a way back.

Program settings: standard folders for new backups and the phones paired with this computer.
"""

import html
import os
import sys
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog,
                               QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QMessageBox, QPushButton, QRadioButton, QScrollArea,
                               QSizePolicy, QStackedWidget, QTabWidget, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout,
                               QWidget)

from . import (APP_NAME, backuplist, companion, completeness, config, generations, history, lastbackup,
               plans, setfolders, ui)
from .backup_anim import ScannerButton
from .gui_flow import WrapLabel, flow_row
from .i18n import N_, tr, trp
from . import theme
from .importer import CAMERA, OTHER, check_selection, guess_kind, scan_folder
from .index import backup_totals, describe_totals
from .locations import detect_drives, find_backups, mount_for_paths_status

GRAY, GREEN, ORANGE = "#808080", "#1f8a4c", "#c76a00"
RED = "#c62828"
CAMERA_FOLDER = backuplist.CAMERA_FOLDER


def _gui():
    from . import gui            # gui imports this module: look it up when used
    return gui


def drive_roots():
    """The attached drives and the home folder (for "Integrate folders…")."""
    roots = [p for p, _free in detect_drives()]
    home = str(Path.home())
    return roots + ([home] if home not in roots else [])


def _fit_height(view, rows_min=2, rows_max=6):
    """A list as high as its rows (between rows_min and rows_max) – no big empty boxes."""
    n = view.topLevelItemCount() if isinstance(view, QTreeWidget) else view.count()
    row = view.sizeHintForRow(0) if n else view.fontMetrics().height() + 8
    row = max(row, view.fontMetrics().height() + 6)
    head = 0
    if isinstance(view, QTreeWidget) and not view.isHeaderHidden():
        # before the list is shown its header has no height yet – the size hint is right then
        head = max(view.header().height(), view.header().sizeHint().height())
    bar = 0
    if view.horizontalScrollBarPolicy() != Qt.ScrollBarAlwaysOff:
        bar = view.horizontalScrollBar().sizeHint().height()    # it must never cover the last row
    view.setFixedHeight(head + row * max(rows_min, min(n, rows_max)) + 2 * view.frameWidth() + bar + 6)


def _size_of_current_only(pages):
    """A QStackedWidget / QTabWidget is as high as its HIGHEST page – which made the Manage backups
    page scroll although the open page fits (user request 2026-11-17). Hidden pages are ignored."""
    def update(_i=None):
        for i in range(pages.count()):
            w = pages.widget(i)
            pol = QSizePolicy.Preferred if i == pages.currentIndex() else QSizePolicy.Ignored
            w.setSizePolicy(pol, pol)
        pages.updateGeometry()
    pages.currentChanged.connect(update)
    update()


class _MinHeightLayout(QVBoxLayout):
    """In a scroll area, a layout with word-wrapped labels makes Qt use the PREFERRED height of the
    content (height-for-width), so the page scrolled although everything fitted. Without
    height-for-width the scroll area uses the minimum height: scroll bars only when really needed."""

    def hasHeightForWidth(self):
        return False


def _short(path):
    parts = Path(path).parts
    return "/".join(parts[-2:]) if len(parts) > 1 else str(path)


class _DayButton(QPushButton):
    """A date: click it and a calendar opens (on today's date), days with an entry carry a small
    dot (user request 2026-11-23 – instead of a date field with a little arrow square)."""

    changed = Signal(str)            # "2026-11-20", "" = no date

    def __init__(self, empty_text):
        super().__init__(empty_text)
        self.empty_text = empty_text
        self._day = ""
        self.marked = set()          # {"2026-11-20", …}
        self.clicked.connect(self._open)

    def day(self):
        return self._day

    def set_day(self, day):
        self._day = day or ""
        self.setText(self._day or self.empty_text)
        self.changed.emit(self._day)

    def _open(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QCalendarWidget, QDialog as _D

        marked = self.marked

        class Cal(QCalendarWidget):
            def paintCell(self, painter, rect, date):
                super().paintCell(painter, rect, date)
                if date.toString("yyyy-MM-dd") in marked:          # a small dot: there is an entry
                    painter.save()
                    painter.setRenderHint(painter.RenderHint.Antialiasing)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor("#000000") if date == self.selectedDate() else QColor(ORANGE))
                    r = max(2.0, rect.height() / 12)
                    painter.drawEllipse(rect.center().x() - r, rect.bottom() - 3 * r, 2 * r, 2 * r)
                    painter.restore()

        dlg = _D(self, Qt.Popup)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(4, 4, 4, 4)
        cal = Cal()
        cal.setGridVisible(False)
        from PySide6.QtCore import QLocale
        from . import i18n
        cal.setLocale(QLocale(i18n.current().code))      # weekdays and months in the program's language
        start = QDate.fromString(self._day, "yyyy-MM-dd") if self._day else QDate.currentDate()
        cal.setSelectedDate(start)
        cal.setCurrentPage(start.year(), start.month())

        def pick(d):
            dlg.accept()
            self.set_day(d.toString("yyyy-MM-dd"))
        cal.clicked.connect(pick)
        cal.activated.connect(pick)
        lay.addWidget(cal)
        none = QPushButton(tr("No date"))
        none.clicked.connect(lambda: (dlg.accept(), self.set_day("")))
        lay.addWidget(none, 0, Qt.AlignRight)
        dlg.adjustSize()
        dlg.move(self.mapToGlobal(QPoint(0, self.height())))
        dlg.exec()


def _media_text(t):
    """"8,014 media · 121.5 GB" – photos and videos, not the files the program writes (user 2026-11-23)."""
    n, size = t
    return tr("%s media · %s", f"{n:,}", ui.human_size(size))


class _DriveProgress:
    """Several drives worked on AT THE SAME TIME (user 2026-11-23: "it runs on both drives, but the
    status shows one"): one progress for all of them, and one line per drive."""

    def __init__(self, channel=""):
        import threading
        self.lock = threading.Lock()
        self.state = {}
        self.p = ui.Progress(0, 0, channel=channel)
        self.p.lines = self._lines

    def callback(self, name, what):
        def cb(n, total, done_b, total_b, path):
            with self.lock:
                self.state[name] = (n, total, done_b, total_b, Path(path).name, what)
                files = sum(v[0] for v in self.state.values())
                self.p.total_files = sum(v[1] for v in self.state.values())
                self.p.total_bytes = sum(v[3] for v in self.state.values())
                add = max(sum(v[2] for v in self.state.values()) - self.p.bytes, 0)
            self.p.update(files_done=files, add_bytes=add)
        return cb

    def _lines(self):
        out = []
        for name, (n, total, done_b, total_b, file, what) in list(self.state.items()):
            pct = 100.0 * done_b / total_b if total_b else 100.0 * n / total if total else 100.0
            out.append(tr("%s – %s: %.0f %% (%s of %s) – %s", name, what, pct, f"{n:,}", f"{total:,}", file))
        return out


def _per_drive(sets, work, what, channel=""):
    """work(set_dir, progress_callback) for every set_dir at the same time (each drive its own
    thread – separate disks read in parallel). Returns {set_dir: result}; runs in a job's thread."""
    from concurrent.futures import ThreadPoolExecutor
    prog = _DriveProgress(channel)
    with ThreadPoolExecutor(max_workers=max(1, len(sets))) as ex:
        futs = {s: ex.submit(work, s, prog.callback(_short(Path(s).parent.parent), what)) for s in sets}
        out = {s: f.result() for s, f in futs.items()}
    prog.p.update(force=True)
    return out


def _progress_to_ui(what):
    """A dedupe progress callback (files_done, files_total, bytes_done, bytes_total, path) shown
    like a copy: percent, files, speed, time left and "Now: <step>: <file>" (user 2026-11-23)."""
    state = {}

    def cb(n, total, done, total_b, path):
        p = state.get("p")
        if p is None or p.total_files != total:
            p = state["p"] = ui.Progress(total, total_b)
        p.update(files_done=n, add_bytes=max(done - p.bytes, 0), current=f"{what}: {Path(path).name}")
    return cb


def _drive_name(root):
    """"veracrypt1", "E:", "Backup HDD" – a drive as people call it."""
    p = Path(root)
    return p.name or str(root).rstrip("\\/") or str(root)


def _tick_dialog(parent, title, text, items, ok_text):
    """A list to tick (with "Select all", Ctrl/Shift multi-select: space ticks the selected rows).
    items = [(label, value, ticked)]. Returns the ticked values ([] = cancelled)."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    lay = QVBoxLayout(dlg)
    lab = QLabel(text)
    lab.setWordWrap(True)
    lay.addWidget(lab)
    lst = QListWidget()
    lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
    for label, value, on in items:
        it = QListWidgetItem(label)
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked if on else Qt.Unchecked)
        it.setData(Qt.UserRole, value)
        lst.addItem(it)
    lst.setMinimumWidth(min(900, 60 + max((lst.fontMetrics().horizontalAdvance(i[0]) for i in items), default=300)))
    lay.addWidget(lst)
    row = QHBoxLayout()
    sel_all = QPushButton(tr("Select all"))

    def tick_all():
        for i in range(lst.count()):
            lst.item(i).setCheckState(Qt.Checked)
    sel_all.clicked.connect(tick_all)
    row.addWidget(sel_all)
    row.addStretch()
    bb = QDialogButtonBox(QDialogButtonBox.Cancel)
    go = bb.addButton(ok_text, QDialogButtonBox.AcceptRole)
    go.setDefault(True)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    row.addWidget(bb)
    lay.addLayout(row)
    if dlg.exec() != QDialog.Accepted:
        return []
    return [lst.item(i).data(Qt.UserRole) for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked]


def _result_text(status):
    from .report import shown
    if str(status).startswith("COMPLETED"):
        return tr("OK")
    if status == history.RUNNING:
        return tr("not finished (interrupted)")
    return str(shown(status)) or "–"


def _result_html(status):
    ok = str(status).startswith("COMPLETED")
    return f"<span style='color:{GREEN if ok else ORANGE}'>{html.escape(_result_text(status))}</span>"


def _complete_text(state, ref=None):
    """(text, colour) of a drive in the "Up to date" column: compared with the other connected
    drives of the backup (completeness.compare_drives – nothing to mark, user 2026-11-22)."""
    if not state:
        return tr("not checked yet (drive not connected)"), GRAY
    n = state.get("missing", 0)
    if state.get("live"):
        if state.get("alone"):
            # one drive: its own list, and the other drive's last check (user request 2026-11-23)
            own = state.get("own_missing", 0)
            if own:
                return trp("%s file of its list missing", "%s files of its list missing", own, f"{own:,}"), ORANGE
            other, files = state.get("other_files"), state.get("files", 0)
            if other and other > files:
                return tr("%s media fewer than %s (checked %s)", f"{other - files:,}",
                          _short(state.get("other", "")), state.get("other_checked", "")[:10]), ORANGE
            if other is not None:
                return tr("complete – all files of its list are there, at least as many as %s (checked %s)",
                          _short(state.get("other", "")), state.get("other_checked", "")[:10]), GREEN
            return tr("complete – all files of its list are there"), GREEN
        if not n:
            return tr("up to date"), GREEN
        return trp("%s media missing", "%s media missing", n, f"{n:,}"), ORANGE
    when = state.get("checked", "")[:10]
    if not n:
        return tr("up to date (checked %s)", when), GRAY
    return trp("%s media missing (checked %s)", "%s media missing (checked %s)", n, f"{n:,}", when), GRAY


_ROLE_LONG = {"full": N_("Grandfather (full backup)"), "differential": N_("Father (monthly differential)"),
              "incremental": N_("Son (latest complement)")}


def _role_text(mode):
    return tr(_ROLE_LONG[mode]) if mode in _ROLE_LONG else mode


def _generations_html(s):
    """Grandfather / Father / Son of a storage: the newest of each and how many are kept."""
    if not s:
        return html.escape(tr("not known yet – shown after the next backup there"))
    rows = []
    for t in generations.TYPES:
        g = s.get(t) or {}
        if g.get("count"):
            val = trp("%s (%d kept)", "%s (%d kept)", g["count"], g["last"][:10], g["count"])
            color = GREEN
        else:
            val, color = tr("none yet"), GRAY
        rows.append(f"{html.escape(_role_text(t))}: <span style='color:{color}'>{html.escape(val)}</span>")
    return "<br>".join(rows)


# =========================================================================== folder list

class FolderListEditor(QWidget):
    """Phone folders: Camera, Choose folders…, Select all, Remove (several at once)."""
    changed = Signal(list)
    choose_requested = Signal()

    def __init__(self, hint="", choose_text=None):
        super().__init__()
        self._folders = []
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setMinimumWidth(150)
        cam = QPushButton(tr("Camera"))
        cam.setToolTip(tr("Adds the phone's camera folder (%s) – the standard place "
                          "for photos and videos on Android.", CAMERA_FOLDER))
        cam.clicked.connect(self._add_camera)
        choose = QPushButton(choose_text or tr("Choose folders…"))
        choose.setToolTip(tr("Other folders: screenshots, WhatsApp, downloads … (lists the phone's folders "
                             "when it is connected)."))
        choose.clicked.connect(self.choose_requested.emit)
        sel_all = QPushButton(tr("Select all"))
        sel_all.clicked.connect(self.list.selectAll)
        rm = QPushButton(tr("Remove"))
        rm.setToolTip(tr("Removes the selected folders from the list (several: Ctrl- or Shift-click, "
                         "or “Select all”). Nothing on the phone is changed."))
        rm.clicked.connect(self._remove)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        if hint:
            lab = QLabel(hint)
            lab.setWordWrap(True)
            lab.setStyleSheet(f"color:{GRAY}")
            lay.addWidget(lab)
        lay.addWidget(self.list)                  # buttons below, wrapping (user 2026-11-22: they were cut
        lay.addWidget(flow_row(cam, choose, sel_all, rm))   # off on the right in a half-screen window)

    def folders(self):
        return list(self._folders)

    def set_folders(self, folders, emit=False):
        self._folders = list(dict.fromkeys(folders))
        self.list.clear()
        for f in self._folders:
            it = QListWidgetItem(tr("%s   (Camera)", f) if f == CAMERA_FOLDER else f)
            it.setData(Qt.UserRole, f)
            self.list.addItem(it)
        self.list.setFixedHeight(max(4, min(len(self._folders), 6)) * (self.list.fontMetrics().height() + 8) + 8)
        if emit:
            self.changed.emit(self.folders())

    def _add_camera(self):
        if CAMERA_FOLDER not in self._folders:
            self.set_folders([CAMERA_FOLDER] + self._folders, emit=True)

    def _remove(self):
        names = {it.data(Qt.UserRole) for it in self.list.selectedItems()}
        if not names:
            QMessageBox.information(self, tr("Remove"), tr("Select one or more folders in the list first "
                                                       "(Ctrl- or Shift-click, or “Select all”)."))
            return
        rest = [f for f in self._folders if f not in names]
        if not rest:
            QMessageBox.information(self, tr("Remove"), tr("At least one folder must stay in the list."))
            return
        self.set_folders(rest, emit=True)


# =========================================================================== import sources

class ImportSources(QWidget):
    """Folders to import from (old drive, old phone copy) and how they are sorted."""
    changed = Signal()

    HOW_SORT, HOW_KEEP, HOW_MIXED = "sort", "keep", "mixed"

    def __init__(self, into_existing):
        super().__init__()
        self.into_existing = into_existing
        self.roots = []            # in the order added
        self.scans = {}            # root -> [FolderInfo] (read when needed)
        self.choices = {}          # root -> {rel: CAMERA | OTHER}
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("Folder"), tr("Selected")])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.itemDoubleClicked.connect(lambda *_: self.choose())
        btns = QHBoxLayout()
        for text, fn, tip in (
                (tr("Add folder…"), self.add_root, tr("A folder on an old drive, a copy of an old phone, "
                                                      "an SD card …")),
                (tr("Choose folders to import…"), self.choose, tr("Tick the folders inside and how each "
                                                                  "is sorted.")),
                (tr("Select all"), self.tree.selectAll, ""),
                (tr("Remove"), self.remove_selected, tr("Removes the selected folders from this list. "
                                                        "Nothing on the drive is changed."))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            if tip:
                b.setToolTip(tip)
            btns.addWidget(b)
        btns.addStretch()

        self.how_sort = QRadioButton(tr("Sort the photos and videos into year/month folders (YYYY/YY.MM)"))
        self.how_keep = QRadioButton(tr("Keep the original folder structure"))
        self.how_mixed = QRadioButton(tr("Chosen per folder (“Choose folders to import…”)"))
        self.how_group = QButtonGroup(self)
        for i, rb in enumerate((self.how_sort, self.how_keep, self.how_mixed)):
            self.how_group.addButton(rb, i)
        (self.how_sort if into_existing else self.how_mixed).setChecked(True)
        self.how_group.idClicked.connect(self._how_clicked)
        self.other_check = _gui().WrapCheck(tr(
            "Also import other files (documents, audio, …) – they keep their original folder"))
        self.other_check.setChecked(not into_existing)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tree)
        lay.addLayout(btns)
        how = QLabel(tr("How:"))
        how.setStyleSheet("font-weight:600")
        lay.addWidget(how)
        for rb in (self.how_sort, self.how_keep, self.how_mixed):
            lay.addWidget(rb)
        lay.addWidget(self.other_check)
        self.fill()

    # ---- data
    def load(self, roots, choices):
        """Roots and choices from the settings (not read yet – read when needed)."""
        self.roots = [r for r in roots]
        self.scans = {r: s for r, s in self.scans.items() if r in self.roots}
        self.choices = {r: dict(choices.get(r, {})) for r in self.roots}
        self._sync_how()
        self.fill()

    def how(self):
        return {0: self.HOW_SORT, 1: self.HOW_KEEP}.get(self.how_group.checkedId(), self.HOW_MIXED)

    def selections(self):
        return [(root, rel, kind) for root in self.roots for rel, kind in self.choices.get(root, {}).items()]

    def other_files(self):
        return self.other_check.isChecked()

    # ---- view
    def fill(self):
        self.tree.clear()
        if not self.roots:
            it = QTreeWidgetItem([tr("No folder added yet – click “Add folder…”"), ""])
            it.setFlags(Qt.NoItemFlags)
            self.tree.addTopLevelItem(it)
        for root in self.roots:
            chosen = self.choices.get(root, {})
            infos = self.scans.get(root)
            cams = sum(1 for k in chosen.values() if k == CAMERA)
            if infos is None:
                text = (trp("%d folder ticked (%d sorted, %d kept as they are)",
                            "%d folders ticked (%d sorted, %d kept as they are)",
                            len(chosen), len(chosen), cams, len(chosen) - cams)
                        if chosen else tr("nothing ticked yet – “Choose folders to import…”"))
            else:
                ticked = [i for i in infos if i.rel in chosen]
                files = sum(i.files for i in ticked)
                text = (trp("%d of %d folder (%d sorted, %d kept as they are)",
                            "%d of %d folders (%d sorted, %d kept as they are)",
                            len(infos), len(ticked), len(infos), cams, len(ticked) - cams) + ", "
                        + trp("%d file", "%d files", files, files) + ", "
                        + ui.human_size(sum(i.size for i in ticked)))
            it = QTreeWidgetItem([root, text])
            it.setData(0, Qt.UserRole, root)
            it.setToolTip(0, root)
            if not os.path.isdir(root):
                it.setForeground(0, QColor(GRAY))
                it.setText(1, tr("not connected") + ("  ·  " + text if chosen else ""))
            self.tree.addTopLevelItem(it)
        _fit_height(self.tree, 2, 5)

    def _sync_how(self):
        kinds = {k for ch in self.choices.values() for k in ch.values()}
        if kinds == {CAMERA}:
            self.how_sort.setChecked(True)
        elif kinds == {OTHER}:
            self.how_keep.setChecked(True)
        elif kinds:
            self.how_mixed.setChecked(True)

    def _how_clicked(self, _id):
        how = self.how()
        if how == self.HOW_MIXED:
            if self.roots:
                self.choose()
            return
        kind = CAMERA if how == self.HOW_SORT else OTHER
        for root in self.roots:
            self.choices[root] = {rel: kind for rel in self.choices.get(root, {})}
        self.fill()
        self.changed.emit()

    # ---- actions
    def scan(self, root):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ui.info(tr("Reading the folders of %s ...", root))
            QApplication.processEvents()
            infos = scan_folder(root, into_existing=self.into_existing)
        finally:
            QApplication.restoreOverrideCursor()
        self.scans[root] = infos
        return infos

    def _suggest(self, root, infos):
        how = self.how()
        chosen = {}
        for i in infos:
            if i.suggested:
                chosen[i.rel] = (i.kind if how == self.HOW_MIXED else
                                 CAMERA if how == self.HOW_SORT else OTHER)
        self.choices[root] = chosen
        ui.info("  " + trp("%d folder with files, %d suggested.", "%d folders with files, %d suggested.",
                           len(infos), len(infos), len(chosen)))

    def add_root(self):
        drives = detect_drives()
        start = self.roots[0] if self.roots else (drives[0][0] if drives else str(Path.home()))
        p = QFileDialog.getExistingDirectory(self, tr("Choose a folder to import (e.g. the copy of an old phone)"),
                                             start)
        if not p:
            return
        p = str(Path(p).resolve())
        for other in self.roots:
            o = Path(other)
            if Path(p) == o or o in Path(p).parents or Path(p) in o.parents:
                QMessageBox.warning(self, tr("Folder already added"),
                                    tr("%s\noverlaps with the folder already in the list:\n%s\n\n"
                                       "Choose the sub-folders with “Choose folders to import…” instead.",
                                       p, other))
                return
        self.roots.append(p)
        self._suggest(p, self.scan(p))
        self.fill()
        self.changed.emit()
        self.choose()

    def remove_selected(self):
        roots = {it.data(0, Qt.UserRole) for it in self.tree.selectedItems()} - {None}
        if not roots:
            QMessageBox.information(self, tr("Remove"), tr("Select one or more folders in the list first "
                                                       "(Ctrl- or Shift-click, or “Select all”)."))
            return
        self.roots = [r for r in self.roots if r not in roots]
        for r in roots:
            self.scans.pop(r, None)
            self.choices.pop(r, None)
        self.fill()
        self.changed.emit()

    def choose(self):
        if not self.roots:
            self.add_root()
            return
        missing = [r for r in self.roots if not os.path.isdir(r)]
        if missing:
            QMessageBox.warning(self, tr("Folder not found"),
                                tr("These folders are not connected right now:") + "\n\n" + "\n".join(missing))
        roots = [r for r in self.roots if os.path.isdir(r)]
        for r in roots:
            if r not in self.scans:
                old = self.choices.get(r)
                infos = self.scan(r)
                if old is None:
                    self._suggest(r, infos)
        if not roots:
            return
        scans = {r: self.scans[r] for r in roots}
        for infos in scans.values():
            for info in infos:
                guess_kind(info.rel, info, into_existing=self.into_existing)
        dlg = _gui().ImportSelectionDialog(self, scans, {r: self.choices.get(r, {}) for r in roots})
        if dlg.exec() == QDialog.Accepted:
            self.choices.update(dlg.choices())
            self._sync_how()
            self.fill()
            self.changed.emit()

    def check_ready(self):
        """None if it can start, else the reason."""
        if not self.roots:
            return tr("Add the folder(s) to import.")
        if not self.selections():
            return tr("No folder is ticked – click “Choose folders to import…”.")
        gone = [r for r in self.roots if self.choices.get(r) and not os.path.isdir(r)]
        if gone:
            return tr("These folders are not connected right now:") + "\n\n" + "\n".join(gone)
        return None


# =========================================================================== paired phones

class KnownPhonesBox(QWidget):
    """Program settings: the phones paired with this computer (phone app). Delete = unpair."""

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("Phone"), tr("Paired on"), tr("Paired via"), tr("App version")])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        sel_all = QPushButton(tr("Select all"))
        sel_all.clicked.connect(self.tree.selectAll)
        delete = QPushButton(tr("Delete…"))
        delete.setToolTip(tr("Removes the selected phones from this computer. Their backups are NOT "
                             "deleted. To use the phone app again, pair the phone again."))
        delete.clicked.connect(self.delete_selected)
        row = QHBoxLayout()
        row.addWidget(sel_all)
        row.addWidget(delete)
        row.addStretch()
        lab = QLabel(tr("Phones paired with this computer (phone app “My Mobile Media Backup”). "
                        "Select one or more (Ctrl- or Shift-click) to delete them."))
        lab.setWordWrap(True)
        lab.setStyleSheet(f"color:{GRAY}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(lab)
        lay.addWidget(self.tree)
        lay.addLayout(row)
        self.fill()

    def fill(self):
        self.tree.clear()
        phones = companion.phones(self.cfg)
        if not phones:
            it = QTreeWidgetItem([tr("No phone paired yet."), "", "", ""])
            it.setFlags(Qt.NoItemFlags)
            self.tree.addTopLevelItem(it)
        for p in phones:
            via = {"cable": tr("USB cable")}.get(p.get("via", ""), tr("Wi-Fi"))
            it = QTreeWidgetItem([p.get("name") or tr("unknown phone"), p.get("paired", ""), via,
                                  p.get("app_version") or "–"])
            it.setData(0, Qt.UserRole, p.get("phone_id"))
            self.tree.addTopLevelItem(it)
        _fit_height(self.tree, 2, 6)

    def delete_selected(self):
        items = [it for it in self.tree.selectedItems() if it.data(0, Qt.UserRole)]
        if not items:
            QMessageBox.information(self, tr("Known phones"), tr("Select one or more phones first (or “Select all”)."))
            return
        names = "\n".join(it.text(0) for it in items)
        box = QMessageBox(QMessageBox.Warning, tr("Delete phones?"),
                          trp("Are you sure you want to delete this phone from this computer?",
                              "Are you sure you want to delete these %d phones from this computer?",
                              len(items), len(items))
                          + "\n\n" + names + "\n\n"
                          + tr("Their backups are NOT deleted. To back up over Wi-Fi with the phone app "
                               "again, the phone must be paired again."), parent=self)
        yes = box.addButton(tr("Delete"), QMessageBox.DestructiveRole)
        box.addButton(tr("Cancel"), QMessageBox.RejectRole)
        box.setDefaultButton(box.buttons()[-1])
        box.exec()
        if box.clickedButton() is not yes:
            return
        for it in items:
            companion.forget_phone(self.cfg, it.data(0, Qt.UserRole))
        ui.ok(trp("%d phone deleted from this computer.", "%d phones deleted from this computer.",
                  len(items), len(items)))
        self.fill()


# =========================================================================== the Backups tab

class BackupsTabMixin:
    """Methods of the main window for the "Backups" tab (Manage backups)."""

    # ------------------------------------------------------- the drives, read in the background
    # (user 2026-11-23: the start waited for a sleeping drive) – drivescan.py
    _snap = None
    _scan_busy = False
    _scan_again = False
    _drive_sig = None

    def _backup_sets(self):
        """{key: [backup folders on the connected drives]} – from the last background scan; removed
        backups are left out everywhere (user 2026-11-23: a removed backup was still offered in
        "Secure backups")."""
        gone = set(self.cfg.get("phones_hidden", [])) | set(self.cfg.get("phones_removing", []))
        return {k: v for k, v in ((self._snap or {}).get("sets") or {}).items() if k not in gone}

    def _scan_drives(self):
        """Read the drives in the background; the lists update when it is done."""
        from concurrent.futures import ThreadPoolExecutor
        import traceback
        from . import drivescan
        if self._scan_busy:
            self._scan_again = True
            return
        self._scan_busy = True
        work, before = drivescan.copy_settings(self.cfg)
        if getattr(self, "_scan_pool", None) is None:
            self._scan_pool = ThreadPoolExecutor(max_workers=1)

        def run():
            try:
                res, err = drivescan.scan_copy(work, before), None
            except Exception:  # noqa: BLE001
                res, err = None, traceback.format_exc()
            self.bridge.scanned.emit(res, err)
        self._scan_pool.submit(run)

    def _on_scanned(self, res, err):
        from . import drivescan
        self._scan_busy = False
        self._counted_src = None       # the backup's file list may be new: count again (2026-11-23)
        if err:
            ui.warn(tr("The backup drives could not be read: %s", err.strip().splitlines()[-1]))
        else:
            snap, changes = res
            clean = drivescan.apply_changes(self.cfg, changes)
            if changes:
                config.save(self.cfg)
            self._snap = snap
            for e in snap.get("errors", []):
                ui.warn(tr("A backup could not be read completely: %s", e))
            for key, old, new in snap.get("follow", []):
                ui.ok(tr("The backup drive of %s is now at %s (was %s) – followed automatically.", key, new, old))
            if not clean:
                self._scan_again = True
            self._refresh_backups()
            self._update_home()
        if self._scan_again:
            self._scan_again = False
            QTimer.singleShot(0, self._scan_drives)

    def _drives_changed_check(self):
        """Every few seconds (cheap, no drive is read): did drives come or go? Then scan again."""
        from .locations import mount_roots
        sig = []
        for r in mount_roots():
            try:
                st = os.stat(r)
                sig.append((r, st.st_dev, st.st_ino))
            except OSError:
                sig.append((r,))
        sig = tuple(sig)
        if self._drive_sig is not None and sig != self._drive_sig:
            self._scan_drives()
        self._drive_sig = sig
        self._mount_tick = getattr(self, "_mount_tick", 0) + 1
        if self._mount_tick % 5 == 0:     # every ~15 s: a backup drive plugged in but not mounted?
            self._mount_missing()

    def _mount_missing(self):
        """Instead of the "Refresh" button (user 2026-11-23): a backup drive that is plugged in but
        not mounted is mounted in the background, then read. Nothing happens while all are there."""
        from concurrent.futures import ThreadPoolExecutor
        from .locations import mount_for_paths_status
        if getattr(self, "_mounting", False):
            return
        dests = {d for b in backuplist.known(self.cfg, self._backup_sets()) for d in b["drives"]}
        missing = [d for d in dests if not str(d).startswith("gdrive:") and not os.path.isdir(d)]
        if not missing:
            return
        self._mounting = True
        if getattr(self, "_scan_pool", None) is None:
            self._scan_pool = ThreadPoolExecutor(max_workers=1)

        def run():
            try:
                msgs = mount_for_paths_status(missing)
            except Exception:  # noqa: BLE001 - only a convenience
                msgs = []
            self.bridge.mounted.emit(msgs)
        self._scan_pool.submit(run)

    def _on_mounted(self, msgs):
        self._mounting = False
        if getattr(self, "_mount_shown", None) is None:
            self._mount_shown = set()
        shown = self._mount_shown
        new = [m for m in msgs if m[1] not in shown]         # a failing drive: told once, not every 15 s
        shown.update(m[1] for m in new)
        if new:
            _gui()._log_mount_msgs(new)
        if any(ok for ok, _m in msgs):
            self._scan_drives()

    def _build_backups_tab(self):
        self.backups_stack = QStackedWidget()
        self.backups_stack.addWidget(self._build_backups_manage())
        self.backups_stack.addWidget(self._build_old_import_page())
        _size_of_current_only(self.backups_stack)
        w = QWidget()
        lay = _MinHeightLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.backups_stack)
        return w

    # ---------------------------------------------------------------- page 1: your backups
    def _build_backups_manage(self):
        g = _gui()
        w = QWidget()
        lay = QVBoxLayout(w)
        self.backups_tree = QTreeWidget()
        self.backups_tree.setHeaderLabels([tr("Backup"), tr("Last backup"), tr("Size"), tr("Backup drives")])
        self.backups_tree.setRootIsDecorated(False)
        self.backups_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        h = self.backups_tree.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.backups_tree.itemSelectionChanged.connect(self._backup_selected)
        top = QVBoxLayout()
        top.addWidget(self.backups_tree)
        row = QHBoxLayout()
        sel_all = QPushButton(tr("Select all"))
        sel_all.clicked.connect(self.backups_tree.selectAll)
        rm = QPushButton(tr("Remove from list"))
        rm.setToolTip(tr("Removes the selected backups from this list and from the start screen – Undo is "
                         "possible until the program is started again; then the program forgets them "
                         "completely. The backups on the drives are NOT deleted."))
        rm.clicked.connect(self._remove_backups_from_list)
        # no "Also show removed backups" and no "Refresh" any more (user 2026-11-23): removed is
        # removed, the drives are read (and mounted) by themselves
        new_old = QPushButton(tr("New backup…"))                  # was "New backup of an old phone or drive…"
        new_old.setToolTip(tr("Backs up an old phone or an old hard drive like a phone – its own backup."))
        new_old.clicked.connect(lambda: self._show_old_import(True))
        del row                                   # buttons wrap in a narrow window (user 2026-11-22)
        top.addWidget(flow_row(sel_all, rm, new_old))
        self.removed_bar = QWidget()              # "Removed from the list: … [Undo]"
        rb = QHBoxLayout(self.removed_bar)
        rb.setContentsMargins(0, 0, 0, 0)
        self.removed_label = WrapLabel()
        self.removed_label.setStyleSheet(f"color:{ORANGE}")
        undo = QPushButton(tr("Undo"))
        undo.clicked.connect(self._undo_remove_backups)
        rb.addWidget(self.removed_label, 1)
        rb.addWidget(undo, 0, Qt.AlignTop)
        self.removed_bar.hide()
        top.addWidget(self.removed_bar)
        lay.addWidget(g._group(tr("Your backups"), top))

        # ---- the chosen backup
        self.backup_detail_hint = QLabel()
        self.backup_detail_hint.setWordWrap(True)
        self.backup_detail_hint.setStyleSheet(f"color:{GRAY}")
        self.backup_tabs = QTabWidget()
        self.backup_tabs.addTab(self._build_backup_overview_tab(), tr("Overview"))
        # "Destination drives" left of "Phone folders", "Import media" (user request 2026-11-23)
        self.backup_tabs.addTab(self._build_backup_drives_tab(), tr("Destination drives"))
        self.backup_tabs.addTab(self._build_backup_phone_tab(), tr("Phone folders"))
        self.backup_tabs.addTab(self._build_backup_import_tab(), tr("Import media"))
        self.backup_tabs.addTab(self._build_backup_history_tab(), tr("Backup history"))
        _size_of_current_only(self.backup_tabs)
        box = QVBoxLayout()
        box.addWidget(self.backup_detail_hint)
        box.addWidget(self.backup_tabs)
        # the buttons ("Update backup now" …) are pinned below the scroll area (main window): always
        # visible, whichever tab is open (user request 2026-11-10)
        self.backup_actions = QWidget()
        self.backup_actions.setLayout(self._build_backup_actions())
        self.backup_detail = g._group(tr("Selected backup"), box)
        lay.addWidget(self.backup_detail, 1)          # the rest of the height: no empty space below
        self._backups = []
        return w

    def _build_backup_phone_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.backup_folders = FolderListEditor(tr(
            "Standard folders on the phone – “Update backup” on the start screen backs up these folders:"),
            choose_text=tr("Additional folders…"))                      # user request 2026-11-23
        self.backup_folders.changed.connect(self._backup_folders_changed)
        self.backup_folders.choose_requested.connect(
            lambda: self._pick_phone_folders(self.backup_folders.folders(),
                                             lambda f: self.backup_folders.set_folders(f, emit=True)))
        lay.addWidget(self.backup_folders)
        self.backup_keep_check = _gui().WrapCheck(tr("Other folders than Camera: keep the phone's folder "
                                                     "structure instead of sorting them into year/month folders"))
        self.backup_keep_check.toggled.connect(self._backup_keep_changed)
        lay.addWidget(self.backup_keep_check)
        lay.addStretch()
        return w

    def _build_backup_actions(self):
        """Below the tabs (user request 2026-11-10): usable from every tab of the chosen backup."""
        actions = QVBoxLayout()
        row = QHBoxLayout()
        self.backup_update_btn = QPushButton(tr("Update backup now"))
        self.backup_update_btn.setStyleSheet("QPushButton{font-weight:600}")
        self.backup_update_btn.setToolTip(tr("Connect the phone: copies the new photos and videos of the "
                                             "standard folders."))
        self.backup_update_btn.clicked.connect(lambda: self._backup_update_now(False))
        # no "Connect phone…" here any more – it is "Help connect…" on the start screen (user 2026-11-23);
        # no "Back up other phone folders…" either (user 2026-11-23): "Additional folders…" in the tab
        del row
        actions.addWidget(flow_row(self.backup_update_btn))
        self.backup_phone_hint = QLabel()
        self.backup_phone_hint.setWordWrap(True)
        actions.addWidget(self.backup_phone_hint)
        return actions

    def _build_backup_drives_tab(self):
        """Two kinds of drives, clearly apart (user request 2026-11-22): the drives that hold the
        backup itself, and the storages of its secured copies (Grandfather / Father / Son). Compact:
        two drives must fit without scrolling (user 2026-11-22) – explanations are tooltips."""
        g = _gui()
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 4, 0, 0)
        main = QWidget()
        lay = QVBoxLayout(main)
        lay.setContentsMargins(0, 0, 0, 0)
        self.backup_complete_info = WrapLabel()
        self.backup_complete_info.setTextFormat(Qt.RichText)
        self.backup_complete_info.hide()
        lay.addWidget(self.backup_complete_info)
        self.backup_drives = QTreeWidget()
        # "Status" says "up to date" when the drive is connected – no extra column (user 2026-11-23)
        self.backup_drives.setHeaderLabels([tr("Drive"), tr("Status"), tr("This backup")])
        self.backup_drives.setRootIsDecorated(False)
        self.backup_drives.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # two drives without any scrolling (user 2026-11-23): no sideways scroll bar – long texts
        # are shortened with "…", the whole text is in the tooltip
        self.backup_drives.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.backup_drives.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.backup_drives.setTextElideMode(Qt.ElideMiddle)
        h = self.backup_drives.header()
        h.setStretchLastSection(False)
        h.setMinimumSectionSize(60)
        for c, mode in enumerate((QHeaderView.Stretch, QHeaderView.Stretch, QHeaderView.ResizeToContents)):
            h.setSectionResizeMode(c, mode)
        lay.addWidget(self.backup_drives)
        add = QPushButton(tr("Add drive…"))
        self.backup_drive_menu = QMenu(add)
        self.backup_drive_menu.aboutToShow.connect(self._fill_backup_drive_menu)
        add.setMenu(self.backup_drive_menu)
        sel_all = QPushButton(tr("Select all"))
        sel_all.clicked.connect(self.backup_drives.selectAll)
        rm = QPushButton(tr("Remove"))      # short: the row overlapped the list (user 2026-11-22)
        rm.setToolTip(tr("Remove from this backup – nothing on the drive is deleted."))
        rm.clicked.connect(self._remove_backup_drives)
        # "Add drive…" finds the folder by itself; "Integrate folder…" is the way by hand (user 2026-11-23)
        add.setToolTip(tr("Pick an attached drive – the folder of this backup on it is found and checked "
                          "automatically (its mark, the phone, and a sample of its files read with SHA-256)."))
        integ = QPushButton(tr("Integrate folder…"))
        integ.setToolTip(tr("Choose a folder by hand – it is checked the same way before it becomes a backup "
                            "drive of this backup."))
        integ.clicked.connect(self._integrate_folder)
        # glows when the drives do not hold the same files; green and inactive when they do (user
        # request 2026-11-23 – replaces "Update drives" and "Clean up destination folder…")
        self.prepare_btn = ScannerButton(tr("Prepare folders"))
        self.prepare_btn.setToolTip(tr("Moves duplicate files of this backup into a review folder (nothing is "
                                       "deleted) and copies the files a drive is missing from the other "
                                       "drive(s) – checked with SHA-256, the phone is not needed."))
        self.prepare_btn.clicked.connect(lambda _c=False: self._prepare_folders())
        self.prepare_btn.set_glowing(False)
        # only when the logs do not know the SHA-256 of every photo/video (user request 2026-11-23)
        self.check_folder_btn = QPushButton(tr("Check backup folder…"))
        self.check_folder_btn.setToolTip(tr("Reads the photos and videos whose SHA-256 is neither in the backup's "
                                            "list nor in its reports, and remembers it – then every file can be "
                                            "compared and checked without reading it again."))
        self.check_folder_btn.clicked.connect(self._check_backup_folder)
        self.check_folder_btn.hide()
        integrity = QPushButton(tr("Integrity check…"))
        integrity.setToolTip(tr("Reads every photo and video of the backup completely and compares it with "
                                "the checksum on record – finds files that changed or got damaged."))
        integrity.clicked.connect(self._integrity_check)
        lay.addWidget(flow_row(add, integ, sel_all, rm, self.prepare_btn, self.check_folder_btn, integrity))
        box = g._group(tr("Backup drives – the backup itself"), main)
        box.setToolTip(tr("Every backup from the phone is written to these drives – to all of them at the "
                          "same time; each drive holds the complete backup. A drive that is not connected "
                          "catches up with “Prepare folders”."))
        outer.addWidget(box)

        # no "Secure backups" part here any more – it is a menu point of its own (user 2026-11-23)
        outer.addStretch()
        return w

    def _history_runs(self, b, newest_first=True):
        """The backup's history – the reports on its drives as the background scan read them."""
        reports = ((self._snap or {}).get("reports") or {}).get(b["key"], [])
        return history.entries(self.cfg, b["key"], (), newest_first, reports=reports)

    def _secure_targets(self, b):
        """[(target, summary, connected)] – the storages with secured copies of this backup, as
        remembered (the background scan reads the connected ones)."""
        drives = set(b["drives"])
        roots = (self._snap or {}).get("roots") or []
        targets = [t for t in self.cfg.get("export_targets", []) if not str(t).startswith("gdrive:")]
        targets += [t for t in generations.targets(self.cfg, b["key"]) if t not in targets and t not in drives]
        out = []
        for t in targets:
            s, _live = generations.of(self.cfg, b["key"], t, None)
            if s is None:
                continue
            connected = t != generations.GDRIVE and any(str(t).startswith(str(r)) for r in roots)
            out.append((t, s, connected))
        return out

    def _build_backup_import_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lab = QLabel(tr("Adds the photos and videos of old drives, old phones or any folders to this backup. "
                        "Every file is checked with SHA-256, files already in the backup are not copied "
                        "twice, and the old folders are only read – never changed."))
        lab.setWordWrap(True)
        lab.setStyleSheet(f"color:{GRAY}")
        lay.addWidget(lab)
        self.backup_import = ImportSources(into_existing=True)
        self.backup_import.changed.connect(self._backup_import_changed)
        lay.addWidget(self.backup_import)
        row = QHBoxLayout()
        self.backup_import_info = QLabel()
        self.backup_import_info.setWordWrap(True)
        row.addWidget(self.backup_import_info, 1)
        self.start_import_btn = _gui()._big_button(tr("Start"))
        self.start_import_btn.clicked.connect(self._start_import)
        row.addWidget(self.start_import_btn, 0, Qt.AlignBottom)
        lay.addLayout(row)
        lay.addStretch()
        return w

    def _build_backup_overview_tab(self):
        """Latest backup, complete backups, drives, backups of the backup (Grandfather-Father-Son)
        and runs that did not finish (user request 2026-11-17)."""
        w = QWidget()
        lay = QVBoxLayout(w)
        self.backup_overview = QLabel()
        self.backup_overview.setTextFormat(Qt.RichText)
        self.backup_overview.setWordWrap(True)
        self.backup_overview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.backup_overview.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        lay.addWidget(self.backup_overview)
        self.overview_app_update = AppUpdateBox()
        self.overview_app_update.clicked.connect(lambda: self._app_update_clicked(self.overview_app_update))
        lay.addWidget(self.overview_app_update)
        lay.addStretch()
        return w

    def _overview_phone_names(self, b):
        e = (self.cfg.get("phones") or {}).get(b["key"]) or {}
        return [n for n in (b["phone"], e.get("model")) if n]

    def _completeness(self, b, live=False):
        """The drives compared – from the background scan (or as remembered before it); live=True
        reads the drives now (only for an action the user started)."""
        from . import drivescan
        if live:
            return completeness.compare_drives(self.cfg, b["key"], setfolders.rel(b["phone"], b["owner"]),
                                               b["drives"])
        got = ((self._snap or {}).get("comp") or {}).get(b["key"])
        if got is not None and all(str(d) in got or not (self._snap["avail"].get(d)) for d in b["drives"]):
            return got
        return drivescan.remembered_comp(self.cfg, b["key"], b["drives"])

    def _fill_backup_overview(self):
        b = self._current_backup()
        if b is None:
            self.backup_overview.clear()
            self.overview_app_update.hide()
            return
        self._fill_app_update(self.overview_app_update, *self._overview_phone_names(b))
        esc = html.escape
        runs = self._history_runs(b)
        parts = []

        def head(text):
            parts.append(f"<p style='margin:10px 0 2px 0'><b>{esc(text)}</b></p>")

        def table(rows):
            cells = "".join("<tr>" + "".join(f"<td style='padding:1px 14px 1px 0'>{c}</td>" for c in r) + "</tr>"
                            for r in rows)
            parts.append(f"<table cellspacing='0'>{cells}</table>")

        # ---- latest backup + complete
        last = next((e for e in runs if e["kind"] == history.BACKUP), None)
        ref = completeness.reference(self.cfg, b["key"])
        rows = []
        if last:
            rows.append([esc(tr("Latest backup from the phone")) + ":",
                         esc(last["when"][:16].replace("T", " ")) + " – " + _result_html(last.get("status", ""))])
        else:
            rows.append([esc(tr("Latest backup from the phone")) + ":", esc(tr("none yet"))])
        if ref:                              # set automatically after a backup that secured everything
            rows.append([esc(tr("Complete (everything from the phone secured)")) + ":",
                         esc(tr("%s (on %s)", ref["when"][:16], ", ".join(_short(d) for d in ref["drives"])))])
        version, old, _one = self._phone_app_state(*self._overview_phone_names(b))
        if version:
            rows.append([esc(tr("Phone app")) + ":", esc(version) + (
                f" <span style='color:{ORANGE}'>– {esc(tr('update available: %s', companion.APP_VERSION_NAME))}</span>"
                if old else "")])
        table(rows)

        # ---- backup drives
        head(tr("Backup drives"))
        comp = self._completeness(b)
        rows = []
        snap = self._snap or {}
        for d in b["drives"]:
            avail = bool((snap.get("avail") or {}).get(d))        # from the background scan
            ctext, ccolor = _complete_text(comp.get(d), ref)
            plan = (snap.get("plans") or {}).get((b["key"], d)) if avail else None
            plan = plan or plans.plan_of(self.cfg, d)
            rows.append([esc(_short(d)),
                         f"<span style='color:{GREEN if avail else GRAY}'>"
                         f"{esc(tr('connected') if avail else tr('not connected'))}</span>",
                         esc(tr(plans.NAMES[plan])),
                         f"<span style='color:{ccolor}'>{esc(ctext)}</span>"])
            if plan == plans.GFS:
                s, _live = generations.of(self.cfg, b["key"], d, None)   # remembered (scan reads it)
                rows.append(["", _generations_html(s), "", ""])
        if not rows:
            rows.append([esc(tr("No backup drive yet."))])
        table(rows)

        # ---- secured? and how (user request 2026-11-23) – the copies are made on the page "Secure
        # backups"; "Started but not finished" is not here any more (the backup history shows it)
        head(tr("Secured"))
        secure = self._secure_targets(b)
        rows = []
        for t, s_, conn in secure:
            name = tr("Google Drive") if t == generations.GDRIVE else _short(t)
            state = ("" if t == generations.GDRIVE else
                     f" <span style='color:{GREEN if conn else GRAY}'>"
                     f"({esc(tr('connected') if conn else tr('not connected'))})</span>")
            rows.append([esc(name) + state, _generations_html(s_)])
        if rows:
            newest = max((((s_ or {}).get(k) or {}).get("last", "") for _t, s_, _c in secure
                          for k in generations.TYPES), default="")
            parts.append(f"<p style='margin:0'><span style='color:{GREEN}'>{esc(tr('Yes'))}</span> – " + esc(
                tr("newest secure copy: %s", newest[:16].replace("T", " ")) if newest else tr("secure copies exist"))
                + "</p>")
            table(rows)
        else:
            parts.append(f"<p style='margin:0'><span style='color:{ORANGE}'>{esc(tr('No'))}</span> – "
                         + esc(tr("not secured yet: make a copy on the page “Secure backups” (in the menu on "
                                  "the left) – e.g. on a drive kept in another place, or on Google Drive."))
                         + "</p>")
        self.backup_overview.setText("".join(parts))

    def _build_backup_history_tab(self):
        """Every backup from the phone and every addition from another source (user request 2026-11-17)."""
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        lab = QLabel(tr("Everything that was added to this backup: backups from the phone and photos and "
                        "videos added from other sources."))
        lab.setWordWrap(True)
        lab.setStyleSheet(f"color:{GRAY}")
        row.addWidget(lab, 1)
        self.history_order = QComboBox()
        self.history_order.addItem(tr("Newest first"), True)
        self.history_order.addItem(tr("Oldest first"), False)
        self.history_order.setCurrentIndex(0 if self.cfg.get("history_newest_first", True) else 1)
        self.history_order.currentIndexChanged.connect(self._history_order_changed)
        row.addWidget(self.history_order, 0, Qt.AlignTop)
        lay.addLayout(row)
        self.backup_history = QTreeWidget()
        self.backup_history.setHeaderLabels([tr("Date"), tr("What"), tr("From"), tr("New files"),
                                             tr("Result"), tr("Backup drives")])
        self.backup_history.setRootIsDecorated(False)
        self.backup_history.setSelectionMode(QAbstractItemView.ExtendedSelection)
        h = self.backup_history.header()
        for c in range(6):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        lay.addWidget(self.backup_history)
        # delete: everything up to and including a date – marked at once in the list, no single
        # entries in between (user request 2026-11-23)
        self.history_until = _DayButton(tr("choose a date"))       # click → calendar (user 2026-11-23)
        self.history_until.changed.connect(lambda _d: self._mark_history())
        self.history_delete_btn = QPushButton(tr("Delete marked entries"))
        self.history_delete_btn.clicked.connect(self._delete_marked_history)
        self.history_delete_btn.setEnabled(False)
        delete_all = QPushButton(tr("Delete whole history…"))
        delete_all.clicked.connect(self._delete_whole_history)
        self.history_undo_btn = QPushButton(tr("Undo"))         # the last deletion back (user 2026-11-23)
        self.history_undo_btn.setToolTip(tr("Brings back the entries of the last deletion (while the program "
                                            "is running)."))
        self.history_undo_btn.clicked.connect(self._undo_history_delete)
        self.history_undo_btn.setEnabled(False)
        self._history_undo = []                                  # [(key, step)], newest last
        lab = QLabel(tr("Delete entries up to and including:"))
        lay.addWidget(flow_row(lab, self.history_until, self.history_delete_btn, delete_all,
                               self.history_undo_btn))
        return w

    def _history_day(self):
        return self.history_until.day()

    def _mark_history(self):
        """The entries on or before the chosen date are marked (and only they)."""
        day = self._history_day()
        from PySide6.QtGui import QBrush
        tree, n = self.backup_history, 0
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            when = it.data(0, Qt.UserRole) or ""
            on = bool(day) and bool(when) and when[:10] <= day
            n += on
            for c in range(tree.columnCount()):
                # orange and crossed out = will be deleted (a background colour is not shown in the
                # Starship look)
                f = it.font(c)
                f.setStrikeOut(on)
                it.setFont(c, f)
                if on:
                    it.setForeground(c, QColor(ORANGE))
                elif c == 4 and it.data(4, Qt.UserRole):
                    it.setForeground(c, QColor(ORANGE))        # a result that was not OK
                else:
                    it.setForeground(c, QBrush())
        self.history_delete_btn.setText(trp("Delete %s marked entry", "Delete %s marked entries", n, f"{n:,}")
                                         if n else tr("Delete marked entries"))
        self.history_delete_btn.setEnabled(n > 0)

    def _delete_marked_history(self):
        b = self._current_backup()
        day = self._history_day()
        if b is None or not day:
            return
        if QMessageBox.question(self, tr("Backup history"), tr(
                "Delete every entry up to and including %s from the history?", day) + "\n\n" + tr(
                "The reports in the drives' Logs folders stay – they also record the checksums of the "
                "photos and videos.")) != QMessageBox.Yes:
            return
        self._history_undo.append((b["key"], history.delete_up_to(self.cfg, b["key"], day)))
        self.history_until.set_day("")
        self._fill_backup_history()

    def _delete_whole_history(self):
        b = self._current_backup()
        if b is None:
            return
        if QMessageBox.question(self, tr("Backup history"), tr(
                "Delete the whole history of %s?", lastbackup.title({"owner": b["owner"], "phone": b["phone"]}))
                + "\n\n" + tr("The reports in the drives' Logs folders stay – they also record the checksums of "
                               "the photos and videos.")) != QMessageBox.Yes:
            return
        self._history_undo.append((b["key"], history.delete_up_to(self.cfg, b["key"], None)))
        self.history_until.set_day("")
        self._fill_backup_history()

    def _undo_history_delete(self):
        b = self._current_backup()
        mine = [i for i, (k, _s) in enumerate(self._history_undo) if b is not None and k == b["key"]]
        if not mine:
            return
        key, step = self._history_undo.pop(mine[-1])            # the last deletion of THIS backup
        history.undo_delete(self.cfg, key, step)
        self._fill_backup_history()

    def _history_order_changed(self, _i):
        self.cfg["history_newest_first"] = bool(self.history_order.currentData())
        config.save(self.cfg)
        self._fill_backup_history()

    def _fill_backup_history(self):
        tree = self.backup_history
        tree.clear()
        b = self._current_backup()
        if b is None:
            return
        rows = self._history_runs(b, bool(self.history_order.currentData()))
        for e in rows:
            what = (tr("Backup from the phone") if e["kind"] == history.BACKUP
                    else tr("Added from another source"))
            new = describe_totals((e["files"], e["bytes"])) if e["files"] else tr("nothing new")
            status = e.get("status", "")
            ok = status.startswith("COMPLETED")
            result = tr("OK") if ok else _result_text(status)
            src = e.get("source", "")
            if e["kind"] == history.IMPORT:          # folder names only, the full paths in the tooltip
                src = " + ".join(Path(x.strip()).name or x.strip() for x in src.split(" + "))
            it = QTreeWidgetItem([e["when"][:16].replace("T", " "), what, src or "–", new,
                                  result, ", ".join(_short(d) for d in e.get("drives", [])) or "–"])
            it.setData(0, Qt.UserRole, e["when"])
            it.setToolTip(2, e.get("source", ""))
            it.setToolTip(5, "\n".join(e.get("drives", [])))
            if not ok:
                it.setForeground(4, QColor(ORANGE))
                it.setData(4, Qt.UserRole, True)
            tree.addTopLevelItem(it)
        if not rows:
            it = QTreeWidgetItem([tr("No backups recorded yet."), "", "", "", "", ""])
            it.setFlags(Qt.NoItemFlags)
            tree.addTopLevelItem(it)
        self.history_until.marked = {e["when"][:10] for e in rows}     # the dots in the calendar
        self.history_undo_btn.setEnabled(any(k == b["key"] for k, _s in self._history_undo))
        self._mark_history()

    # ---------------------------------------------------------------- list
    _follow_sig = None

    def _follow_drives(self, force=False):
        """A backup drive whose path changed (two VeraCrypt volumes opened in the other order swap
        /media/veracrypt1 ↔ 2; Windows drive letters) is followed to where its MARKED folder is now
        (user request 2026-11-23). Runs when the attached drives change, cheap otherwise."""
        from . import backupid
        roots = [p for p, _free in detect_drives()]
        sig = []
        for r in roots:
            try:
                st = os.stat(r)
                sig.append((r, st.st_dev, st.st_ino, st.st_ctime_ns))
            except OSError:
                sig.append((r,))
        sig = tuple(sig)
        if sig == self._follow_sig and not force:
            return []
        self._follow_sig = sig
        try:
            changes = backupid.follow(self.cfg, roots)
        except OSError:
            return []
        for key, old, new in changes:
            ui.ok(tr("The backup drive of %s is now at %s (was %s) – followed automatically.", key, new, old))
        if changes and not force:
            self._refresh_backups()
        return changes

    def _refresh_backups(self, mount=False):
        if mount:                       # "Refresh": mount, then read the drives in the background
            _gui()._log_mount_msgs(mount_for_paths_status(self.cfg.get("destinations", [])))
            self._scan_drives()
        keep = self._current_backup_key()
        self._backups = backuplist.known(self.cfg, self._backup_sets())
        self._show_removed_bar()
        tree = self.backups_tree
        tree.blockSignals(True)
        tree.clear()
        for b in self._backups:
            e = b["entry"] or {}
            when = e.get("when", "").replace("T", " ") or "–"
            # photos and videos on its drives (from the background scan), else as remembered
            comp = ((self._snap or {}).get("comp") or {}).get(b["key"]) or {}
            sizes = [(v["files"], v["bytes"]) for v in comp.values() if v.get("live") and "bytes" in v]
            if sizes and e and [e.get("media_files"), e.get("media_bytes")] != list(max(sizes)):
                e["media_files"], e["media_bytes"] = max(sizes)       # for when no drive is there
                config.save(self.cfg)
            size = (_media_text(max(sizes)) if sizes else
                    _media_text((e["media_files"], e["media_bytes"])) if e.get("media_files") is not None
                    else "–")
            title = lastbackup.title({"owner": b["owner"], "phone": b["phone"]})
            it = QTreeWidgetItem([title, when, size, ", ".join(_short(d) for d in b["drives"]) or "–"])
            it.setData(0, Qt.UserRole, b["key"])
            it.setToolTip(3, "\n".join(b["drives"]))
            tree.addTopLevelItem(it)
            if b["key"] == keep:
                it.setSelected(True)
                tree.setCurrentItem(it)
        if not self._backups:
            it = QTreeWidgetItem([tr("No backup yet – make one with “New backup…” on the start screen."), "", "", ""])
            it.setFlags(Qt.NoItemFlags)
            tree.addTopLevelItem(it)
        elif not tree.selectedItems():
            tree.topLevelItem(0).setSelected(True)
            tree.setCurrentItem(tree.topLevelItem(0))
        tree.blockSignals(False)
        _fit_height(tree, 2, 6)
        self._backup_selected()

    def _current_backup_key(self):
        sel = [it.data(0, Qt.UserRole) for it in self.backups_tree.selectedItems()]
        sel = [k for k in sel if k]
        return sel[0] if len(sel) == 1 else None

    def _current_backup(self):
        key = self._current_backup_key()
        return next((b for b in self._backups if b["key"] == key), None)

    def _backup_selected(self):
        b = self._current_backup()
        n = len([it for it in self.backups_tree.selectedItems() if it.data(0, Qt.UserRole)])
        self.backup_tabs.setEnabled(b is not None)
        self.backup_actions.setEnabled(b is not None)
        if b is None:
            self.backup_detail.setTitle(tr("Selected backup"))
            self.backup_detail_hint.setText(tr("%d backups selected – choose one to change it.", n) if n > 1
                                            else tr("Choose a backup in the list above."))
            self.backup_detail_hint.show()
            return
        self.backup_detail_hint.hide()
        self.backup_detail.setTitle(tr("Selected backup: %s",
                                       lastbackup.title({"owner": b["owner"], "phone": b["phone"]})))
        prof = backuplist.profile(self.cfg, b["key"])
        self.backup_folders.set_folders(prof["folders"])
        self.backup_keep_check.blockSignals(True)
        self.backup_keep_check.setChecked(bool(prof["keep_structure"]))
        self.backup_keep_check.blockSignals(False)
        self.backup_import.load(prof["import_roots"], prof["import_choices"])
        self._fill_backup_drives()
        self._fill_backup_history()
        self._fill_backup_overview()
        self._update_backup_hints()

    def _update_backup_hints(self):
        b = self._current_backup()
        if b is None:
            return
        e = dict(b["entry"] or {"phone": b["phone"], "owner": b["owner"]})
        e["destinations"] = b["drives"]
        ok, hint = lastbackup.check(e, self._connected_phone())
        if ok:      # no green "Ready – copies only the new …" (user 2026-11-22) – only what needs attention
            hint = hint.replace(tr("Ready – copies only the new photos and videos."), "").strip()
        short = tr("Connect %s.", e["phone"])
        if short in hint:   # just the state (user 2026-11-23)
            hint = hint.replace(short, tr("No smartphone connected."))
        self.backup_phone_hint.setText(f"<span style='color:{GRAY}'>{html.escape(hint)}</span>" if hint and not self.busy else "")
        self.backup_phone_hint.setVisible(bool(hint) and not self.busy)
        self.backup_update_btn.setEnabled(ok and not self.busy)
        copies = [c for c in (backuplist.copy_on(d, b["phone"], b["owner"]) for d in b["drives"]) if c]
        self.backup_import_info.setText(
            trp("Imports into %d copy of this backup: %s", "Imports into %d copies of this backup: %s",
                len(copies), len(copies), ", ".join(_short(Path(c).parent.parent) for c in copies))
            if copies else
            f"<span style='color:{GRAY}'>" + tr("No backup drive of this backup is connected.") + "</span>")

    def _remove_backups_from_list(self):
        keys = [it.data(0, Qt.UserRole) for it in self.backups_tree.selectedItems() if it.data(0, Qt.UserRole)]
        if not keys:
            QMessageBox.information(self, tr("Remove from list"), tr("Select one or more backups first (or “Select all”)."))
            return
        if QMessageBox.question(
                self, tr("Remove from list"),
                tr("Remove these backups from the list?") + "\n\n" + "\n".join(
                    lastbackup.title(b) for b in self._backups if b["key"] in keys) + "\n\n" + tr(
                    "You can undo it until the program is started again – then the program forgets them "
                    "completely (settings, history, everything it knows about them). Their backups on the "
                    "drives are NOT deleted.")) != QMessageBox.Yes:
            return
        lastbackup.mark_removed(self.cfg, keys)
        self._refresh_backups()
        self._update_home()

    def _show_removed_bar(self):
        pending = list(self.cfg.get("phones_removing", []))
        if pending:
            phones = self.cfg.get("phones") or {}
            names = [lastbackup.title(phones[k]) if k in phones else k for k in pending]
            self.removed_label.setText(tr("Removed from the list: %s – gone for good when the program is "
                                          "started again.", ", ".join(names)))
        self.removed_bar.setVisible(bool(pending))

    def _undo_remove_backups(self):
        lastbackup.undo_removed(self.cfg)
        self._refresh_backups()
        self._update_home()

    # ---------------------------------------------------------------- phone tab
    def _backup_folders_changed(self, folders):
        b = self._current_backup()
        if b is None:
            return
        backuplist.save_profile(self.cfg, b["key"], folders=list(folders))
        if self._profile_key() == b["key"]:          # the New backup page shows the same backup
            self._load_profile()

    def _backup_keep_changed(self, on):
        b = self._current_backup()
        if b is not None:
            backuplist.save_profile(self.cfg, b["key"], keep_structure=bool(on))
            if self._profile_key() == b["key"]:
                self._load_profile()

    def _backup_update_now(self, other_folders):
        b = self._current_backup()
        if b is None:
            return
        if not other_folders:
            self._update_latest(b["key"])
            return
        if self.source is None:
            QMessageBox.information(self, tr("Phone folders"), tr("Connect the phone first – its folders are listed then."))
            return
        self._pick_phone_folders([], lambda folders: folders and self._update_latest(b["key"], folders_once=folders),
                                 title=tr("Back up these folders once"))

    def _pick_phone_folders(self, current, done, title=None):
        """The connected phone's folders to tick (or typed ones) → done(list)."""
        src = self.source
        g = _gui()

        def collect():
            if src is None:
                return []
            return g.phone_folders(src)

        def show(candidates):
            dlg = g.FolderDialog(self, candidates or [], current, src is not None)
            if title:
                dlg.setWindowTitle(title)
            if dlg.exec() == QDialog.Accepted and dlg.folders():
                done(dlg.folders())

        self.run_job(collect, show)

    # ---------------------------------------------------------------- drives tab
    def _fill_backup_drives(self):
        """From the background scan only – no drive is read here (user 2026-11-23)."""
        from . import backupid, findbackup
        b = self._current_backup()
        t = self.backup_drives
        t.clear()
        if b is None:
            return
        snap = self._snap
        bid = backupid.stored(self.cfg, b["key"])
        comp = self._completeness(b)
        foreign, unknown, nested = set(), {}, set()
        avail_of = (lambda d: bool(snap["avail"].get(d))) if snap else (lambda d: False)
        for d in sorted(b["drives"], key=lambda d: 0 if avail_of(d) else 1):   # connected first
            avail = avail_of(d)
            copy = snap["copies"].get((b["key"], d)) if snap else None
            st = comp.get(d) or {}
            # photos and videos really in the backup folder – what "Up to date" compares (user 2026-11-23)
            have = (_media_text((st["files"], st["bytes"])) if st.get("live") and "bytes" in st else
                    _media_text((st["files"], st["bytes"])) + "  " + tr("(last check)") if "bytes" in st else
                    tr("not on this drive yet") if avail else "–")
            ctext, ccolor = _complete_text(st or None)
            if st.get("live") and st.get("own_missing") and not st.get("alone"):
                ctext += "  ·  " + trp("%s entry of its list without a file", "%s entries of its list without a file",
                                       st["own_missing"], f"{st['own_missing']:,}")
            if st.get("live") and st.get("unknown"):
                unknown[d] = st["unknown"]
                ctext += "  ·  " + trp("%s media without a checksum in the logs",
                                       "%s media without a checksum in the logs", st["unknown"], f"{st['unknown']:,}")
                ccolor = ORANGE
            if st.get("live") and snap and (snap.get("nested") or {}).get((b["key"], d)):
                nested.add(d)              # a backup built inside the backup (user 2026-11-23: merge it)
                ctext += "  ·  " + tr("a backup inside the backup – “Prepare folders” merges it")
                ccolor = ORANGE
            regroup_n = (snap.get("regroup") or {}).get((b["key"], d), 0) if snap else 0
            if st.get("live") and regroup_n:
                nested.add(d)              # sorted although its folder should keep its structure (2026-11-23)
                ctext += "  ·  " + trp("%s file of an imported folder to put back into its folder",
                                       "%s files of an imported folder to put back into their folder",
                                       regroup_n, f"{regroup_n:,}")
                ccolor = ORANGE
            mark = snap["marks"].get(copy, "") if snap and copy else ""
            if snap is None:
                state, scolor = tr("checking …"), GRAY
            elif avail and bid and mark and mark != bid:
                # same folder names, but another backup's mark (user 2026-11-23: never be fooled)
                state, scolor = tr("another backup!"), RED
                foreign.add(d)
            elif avail:
                state, scolor = tr("connected"), GREEN
            else:
                on = findbackup.mount_root(d, snap.get("roots") or [])
                # the drive is attached but the folder is not there (renamed / moved) – not "not connected"
                missing_folder = bool(on and on != d)
                state, scolor = ((tr("folder not found"), ORANGE) if missing_folder else (tr("not connected"), GRAY))
                if missing_folder:     # an old result of a folder that is not there only confuses (user 2026-11-23)
                    ctext, ccolor = "–", GRAY
            if state == tr("connected"):            # connected: how it is (up to date, missing …)
                state, scolor = ctext, ccolor
            it = QTreeWidgetItem([_short(d), state, have])
            it.setForeground(1, QColor(scolor))
            it.setData(0, Qt.UserRole, d)
            it.setToolTip(0, d)
            it.setToolTip(1, tr("The drive is attached, but the folder is not there (renamed or moved, e.g. "
                                "the drive got another drive letter or mount point) – click “Add drive…” "
                                "and pick the drive.") if state == tr("folder not found") else state)
            it.setToolTip(2, tr("The photos and videos in this backup's folder on the drive – not its logs "
                                "and the program's own files."))
            t.addTopLevelItem(it)
        self._unknown_media = unknown
        self.check_folder_btn.setVisible(bool(unknown))
        self.check_folder_btn.setEnabled(bool(unknown) and not self.busy)
        live = {d: v for d, v in comp.items() if v.get("live") and d not in foreign}
        behind = [d for d, v in live.items() if v.get("missing")]
        for i in range(t.topLevelItemCount()):
            it = t.topLevelItem(i)
            if it.data(0, Qt.UserRole) in behind:
                it.setToolTip(1, tr("Click “Prepare folders” to copy the missing files (checked with SHA-256, "
                                    "the phone is not needed)."))
        self._set_prepare_state(len(live), bool(behind) or bool(nested))
        if not b["drives"]:
            it = QTreeWidgetItem([tr("No backup drive – click “Add drive…”"), "", ""])
            it.setFlags(Qt.NoItemFlags)
            t.addTopLevelItem(it)
        _fit_height(t, 2, 6)

    def _set_prepare_state(self, live, behind):
        """"Prepare folders" (user request 2026-11-23): glows when the connected drives do not hold the
        same files; green and inactive when they do; normal with one drive (duplicates only)."""
        btn = self.prepare_btn
        same = live >= 2 and not behind
        btn.set_glowing(behind and not self.busy)
        btn.setEnabled(not same and live >= 1 and not self.busy)
        btn.setStyleSheet(f"QPushButton:disabled{{background-color:{GREEN};color:rgba(0,0,0,110)}}"
                          if same else "")
        btn.setToolTip(tr("The connected drives hold the same files – nothing to prepare.") if same else
                       tr("The drives do not hold the same files – click to bring them to the same state.")
                       if behind else
                       tr("Moves duplicate files of this backup into a review folder (nothing is deleted) and "
                          "copies the files a drive is missing from the other drive(s) – checked with "
                          "SHA-256, the phone is not needed."))

    # ------------------------------------------------------------- integrate folders (2026-11-23)
    def _integrate_folder(self):
        """A folder chosen by hand: the backup folder itself, its drive folder (MMMB_Vol.2) or any
        folder above it – the backup is searched inside and checked."""
        b = self._current_backup()
        if b is None or self.busy:
            return
        start = next((d for d in b["drives"] if os.path.isdir(d)), "") or next(
            (r for r, _f in detect_drives()), str(Path.home()))
        folder = QFileDialog.getExistingDirectory(self, tr("Integrate folder – %s", lastbackup.title(
            {"owner": b["owner"], "phone": b["phone"]})), start)
        if folder:
            self._run_integrate(b, [folder], new_on=folder, new_here=True)

    def _integrate_all_drives(self):
        """"Add drive…" → "All attached drives": every attached drive searched at once."""
        b = self._current_backup()
        if b is None or self.busy:
            return
        roots = [r for r, _f in detect_drives()]
        if roots:
            self._run_integrate(b, roots)

    def _trusted_copies(self, b, bid):
        """The backup's folders on its connected drives that carry its mark (or, with no id yet, all)."""
        from . import backupid
        rel = setfolders.rel(b["phone"], b["owner"])
        out = []
        for d in b["drives"]:
            p = Path(d) / rel
            if p.is_dir() and (not bid or backupid.id_of(p) in ("", bid)):
                out.append(str(p))
        return out

    def _run_integrate(self, b, roots, new_on=None, new_here=False):
        from . import backupid, findbackup, phoneid
        cancel = self.cancel_event
        cancel.clear()
        rel = setfolders.rel(b["phone"], b["owner"])
        listed = [str(Path(d) / rel) for d in b["drives"]]
        bid, conflict = backupid.resolve(self.cfg, b["key"], listed, create=False)
        trusted = self._trusted_copies(b, bid)
        serials = set()
        for t in trusted:
            rec = phoneid.load(t)
            serials |= set(rec.serials if rec else [])
        ui.title(tr("Search the backup – %s", lastbackup.title({"owner": b["owner"], "phone": b["phone"]})))

        def job():
            found = findbackup.search_any(roots, cancel=cancel, rel=rel)
            ui.info(trp("%d backup folder found – checking it …", "%d backup folders found – checking them …",
                        len(found), len(found)))
            res = []
            for f in found:
                if cancel.is_set():
                    break
                others = [t for t in trusted if Path(t).resolve() != Path(f).resolve()]
                c = backupid.check(f, bid, serials, others)
                ui.info(f"  {f}: " + {backupid.CONFIRMED: tr("this backup"),
                                      backupid.PROBABLE: tr("probably this backup"),
                                      backupid.REJECTED: tr("not this backup")}[c.kind]
                        + (" – " + "; ".join(c.reasons) if c.reasons else ""))
                res.append(c)
            return res

        def done(res):
            self._integrate_result(b, roots, res, conflict, new_on, new_here)

        self.run_job(job, done, awake=N_("Integrate folder"))

    def _integrate_result(self, b, roots, res, conflict, new_on=None, new_here=False):
        from . import backupid, findbackup
        who = lastbackup.title({"owner": b["owner"], "phone": b["phone"]})
        ok = [c for c in res if c.kind != backupid.REJECTED]
        bad = [c for c in res if c.kind == backupid.REJECTED]
        if conflict:
            QMessageBox.warning(self, tr("Integrate folder"), tr(
                "The drives of this backup carry different marks – they are not all the same backup. "
                "Remove the wrong drive from the list first."))
            return
        if not ok and new_on:
            if bad:
                QMessageBox.information(self, tr("Add drive"), tr(
                    "These backup folders are on the drive, but they are not this backup:") + "\n" +
                    "\n".join(f"• {c.set_dir}: {'; '.join(c.reasons)}" for c in bad[:10]))
            self._new_backup_on_drive(b, new_on, here=new_here)
            return
        if not ok:
            text = tr("No folder of %s was found on the chosen drives.", who)
            if bad:
                text += "\n\n" + tr("These backup folders were found, but they are not this backup:") + "\n" + \
                        "\n".join(f"• {c.set_dir}: {'; '.join(c.reasons)}" for c in bad[:10])
            QMessageBox.information(self, tr("Integrate folder"), text)
            return
        all_roots = drive_roots()
        # per drive the folder with the most files is ticked; the others are offered unticked
        best = {}
        for c in ok:
            m = findbackup.mount_root(c.set_dir, all_roots) or c.set_dir
            if m not in best or c.files > best[m].files:
                best[m] = c
        items = []
        for c in sorted(ok, key=lambda c: c.set_dir):
            _base, target, action = findbackup.placed(c.set_dir, b["phone"], b["owner"])
            line = f"{c.set_dir}   (" + trp("%d file", "%d files", c.files, c.files) + ")"
            if c.kind == backupid.PROBABLE:
                line += "   – " + tr("probably this backup: not marked yet")
            if action != findbackup.USE:
                line += "   → " + tr("will be renamed to %s", target)
            items.append((line, c.set_dir, best.get(findbackup.mount_root(c.set_dir, all_roots) or c.set_dir) is c))
        head = tr("Folders of %s found and checked (mark, phone, files read with SHA-256):", who)
        if bad:
            head += "\n\n" + tr("Not used (not this backup):") + "\n" + \
                    "\n".join(f"• {c.set_dir}: {'; '.join(c.reasons)}" for c in bad[:6])
        picked = _tick_dialog(self, tr("Integrate folder"), head, items, tr("Use ticked folders"))
        if not picked:
            return
        by_dir = {c.set_dir: c for c in ok}
        rel = setfolders.rel(b["phone"], b["owner"])
        listed = [str(Path(d) / rel) for d in b["drives"]] + list(picked)
        bid, _c = backupid.resolve(self.cfg, b["key"], listed, create=True)
        drives = list(b["drives"])
        problems = []
        for set_dir in picked:
            base, target, action = findbackup.placed(set_dir, b["phone"], b["owner"])
            try:
                if action != findbackup.USE:
                    findbackup.apply(findbackup.Choice(action, base, target, source=set_dir), self.cfg)
                backupid.write(target, bid, b["owner"], b["phone"])
            except OSError as e:
                problems.append(f"{set_dir}: {e}")
                continue
            drives = findbackup.replace_missing(drives, base, all_roots)
            ui.ok(tr("Integrated: %s", target) + ("" if by_dir[set_dir].kind == backupid.CONFIRMED
                                                  else "  (" + tr("marked now") + ")"))
        # the folders already in the list get the mark too (they are trusted)
        for d in drives:
            p = Path(d) / rel
            if p.is_dir() and not backupid.id_of(p):
                try:
                    backupid.write(p, bid, b["owner"], b["phone"])
                except OSError:
                    pass
        if problems:
            QMessageBox.warning(self, tr("Integrate folder"), "\n".join(problems))
        if drives != b["drives"]:
            self._set_backup_drives(drives)
        else:
            self._fill_backup_drives()

    # ------------------------------------------------------------- prepare folders (2026-11-23)
    def _prepare_folders(self, chosen=None):
        """0. The user chooses the drives (user 2026-11-23). 1. A backup inside the backup is merged
        into it. 2. The missing files – already known from the drives' lists – are copied.
        3. Only if the user wants: the duplicate clean-up. `chosen` = the drives chosen before
        (the steps go on by themselves without asking again)."""
        b = self._current_backup()
        if b is None or self.busy:
            return
        rel = setfolders.rel(b["phone"], b["owner"])
        sets = [str(Path(d) / rel) for d in b["drives"] if (Path(d) / rel).is_dir()]
        if not sets:
            QMessageBox.information(self, tr("Prepare folders"), tr("No drive of this backup is connected."))
            return
        if chosen is None and len(sets) > 1:
            comp = self._completeness(b)
            items = []
            for s in sets:
                d = str(Path(s).parent.parent)
                st = comp.get(d) or {}
                info = _media_text((st["files"], st["bytes"])) if "bytes" in st else ""
                items.append((_short(d) + (f"  –  {info}" if info else ""), s, True))
            chosen = _tick_dialog(self, tr("Prepare folders"), tr("Prepare the backup folder on these drives:"),
                                  items, tr("Prepare"))
            if not chosen:
                return
        if chosen is not None:
            sets = [s for s in sets if s in chosen]
            if not sets:
                return
        self._prepare_chosen = list(sets)
        from . import nestmerge
        nested = {s: nestmerge.inner_sets(s) for s in sets}
        nested = {s: v[0] for s, v in nested.items() if v}
        if nested:                         # first: a backup inside the backup is merged into it
            self._merge_nested(b, nested)
            return
        from . import regroup                # 2. imported folders back into their own structure
        regroups = {s: regroup.plan(s) for s in sets}
        regroups = {s: f for s, f in regroups.items() if f}
        if regroups:
            self._regroup(b, regroups)
            return
        comp = self._completeness(b, live=True)
        live = {d: v for d, v in comp.items() if v.get("live")}
        mine = {str(Path(s).parent.parent) for s in sets}
        behind = {d: v["missing"] for d, v in live.items() if v.get("missing") and d in mine}
        if len(live) < 2 or not behind:
            self._offer_duplicates(b, sets, first=True)
            return
        lines = "\n".join(trp("%s: %s file is missing – it is copied from the other drive",
                              "%s: %s files are missing – they are copied from the other drive", n,
                              _short(d), f"{n:,}") for d, n in behind.items())
        if QMessageBox.question(self, tr("Prepare folders"), lines + "\n\n" + tr(
                "Every copied file is checked with SHA-256; nothing is deleted or overwritten.")) != QMessageBox.Yes:
            return
        from . import reconcile
        cancel = self.cancel_event
        cancel.clear()
        ui.title(tr("Prepare folders – %s", lastbackup.title({"owner": b["owner"], "phone": b["phone"]})))

        def job():
            ui.status(tr("Comparing the drives – which files are missing where …"))
            return reconcile.update_drives(b["drives"], rel, self.cfg, targets=list(behind), cancel=cancel)

        def done(res):
            status, by_drive, problems = res
            copied = sum(r.copied for lst in by_drive.values() for r in lst)
            already = sum(r.already for lst in by_drive.values() for r in lst)
            size = sum(r.bytes for lst in by_drive.values() for r in lst)
            errs = [(d, rel, why) for d, lst in by_drive.items() for r in lst for rel, why in r.errors]
            wanted = sum(behind.values())
            # plain numbers: "0 of 19 copied" – not "0 files copied, 19 errors" (user 2026-11-23)
            text = tr("%s of %s missing files copied (%s) and checked with SHA-256.", f"{copied + already:,}",
                      f"{wanted:,}", ui.human_size(size))
            if not errs and copied + already < wanted:   # duplicates are not spread (UI test 2026-11-23)
                text += "\n" + tr("The others are copies of photos or videos the drive already has – "
                                   "they were not copied again.")
            if errs:
                text += "\n\n" + trp("%s file could NOT be copied:", "%s files could NOT be copied:",
                                       len(errs), f"{len(errs):,}") + "\n" + "\n".join(
                    f"• {Path(rel).name}: {why}" for _d, rel, why in errs[:5]) + (
                    "\n• …" if len(errs) > 5 else "") + "\n\n" + tr(
                    "The whole list is in the report in the Logs folder of %s.",
                    ", ".join(_short(d) for d in {d for d, _r, _w in errs}))
            if problems:
                text += "\n\n" + "\n".join(problems)
            self._fill_backup_drives()
            self._refresh_backups()
            if status != "COMPLETED" or errs:
                QMessageBox.warning(self, tr("Prepare folders"), _gui()._status_text(status) + "\n\n" + text)
                return
            self._offer_duplicates(b, sets, first=False, before=text)

        self.run_job(job, done, awake=N_("Prepare folders"), log_dir=sets[0])

    def _merge_nested(self, b, nested):
        """A backup inside the backup ({set_dir: inner}): plan (read-only), ask, merge – then the
        rest of "Prepare folders" (user request 2026-11-23)."""
        from . import nestmerge
        cancel = self.cancel_event
        cancel.clear()
        ui.title(tr("Prepare folders – %s", lastbackup.title({"owner": b["owner"], "phone": b["phone"]})))

        def plan():
            ui.status(tr("Comparing the backup inside the backup with the backup …"))
            return _per_drive(list(nested), lambda s, cb: nestmerge.plan(s, nested[s], cancel, progress=cb),
                              tr("comparing"))

        def planned(plans_):
            if any(p.cancelled for p in plans_.values()):
                return
            lines = []
            for s, p in plans_.items():
                lines.append(f"{_short(Path(s).parent.parent)}:\n" + "\n".join("   " + x for x in [
                    trp("%s file exists only inside – moved into the backup (%s)",
                        "%s files exist only inside – moved into the backup (%s)",
                        p.count(nestmerge.MOVE) + p.count(nestmerge.RENAME),
                        f"{p.count(nestmerge.MOVE) + p.count(nestmerge.RENAME):,}",
                        ui.human_size(p.size(nestmerge.MOVE) + p.size(nestmerge.RENAME))),
                    trp("%s copy of a file the backup has – into the review folder (%s)",
                        "%s copies of files the backup has – into the review folder (%s)",
                        p.count(nestmerge.DUPLICATE), f"{p.count(nestmerge.DUPLICATE):,}",
                        ui.human_size(p.size(nestmerge.DUPLICATE)))]
                    + ([trp("%s of them with a name that is taken – kept as _1",
                            "%s of them with a name that is taken – kept as _1",
                            p.count(nestmerge.RENAME), f"{p.count(nestmerge.RENAME):,}")]
                       if p.count(nestmerge.RENAME) else [])
                    + ([trp("%s old list entry of a report that is nowhere any more – removed",
                            "%s old list entries of reports that are nowhere any more – removed",
                            len(p.stale), f"{len(p.stale):,}")] if p.stale else [])))
            if QMessageBox.question(self, tr("Prepare folders"), tr(
                    "There is a second backup INSIDE this backup (made by mistake on 2026-11-22):") + "\n\n"
                    + "\n\n".join(lines) + "\n\n" + tr(
                    "Merge it into the backup? Nothing is deleted or overwritten: files are moved on the same "
                    "drive (instant), copies are checked with SHA-256 before they go into the review folder "
                    "“Duplicates <date>”, and “Put back” on the duplicates page undoes everything.")) \
                    != QMessageBox.Yes:
                return
            self._merge_run(b, plans_)

        self.run_job(plan, planned, awake=N_("Prepare folders"))

    def _regroup(self, b, regroups):
        """Photos/videos of an imported folder that were sorted into the year/month folders go back
        into the folder's own structure (user rule 2026-11-23)."""
        from . import regroup
        lines = []
        for s, folders in regroups.items():
            for f in folders:
                lines.append(f"{_short(Path(s).parent.parent)}: “{f.name}” – " + trp(
                    "%s file goes back into the folder", "%s files go back into the folder",
                    len(f.moves), f"{len(f.moves):,}")
                    + (" " + trp("(%s of them from a part of the folder inside a year folder)",
                                 "(%s of them from a part of the folder inside a year folder)",
                                 f.strays, f"{f.strays:,}") if f.strays else "")
                    + " " + tr("(e.g. %s → %s)", f.moves[0][0], f.moves[0][1]))
        if QMessageBox.question(self, tr("Prepare folders"), tr(
                "These imported folders hold other files than photos and videos and their own file names – "
                "they keep their own structure. Their photos and videos were sorted into the year/month "
                "folders by mistake:") + "\n\n" + "\n".join(lines) + "\n\n" + tr(
                "Put them back into their folders? The files are only moved on the same drive (instant), "
                "nothing is deleted or overwritten, and it is recorded so it can be undone.")) != QMessageBox.Yes:
            return
        cancel = self.cancel_event
        cancel.clear()

        def job():
            return _per_drive(list(regroups), lambda s, cb: regroup.apply(s, regroups[s], cancel, progress=cb),
                              tr("putting back"))

        def done(res):
            text = "\n".join(f"{_short(Path(s).parent.parent)}: " + trp(
                "%s file put back into its folder", "%s files put back into their folders", m, f"{m:,}")
                + (trp(" (%d skipped)", " (%d skipped)", len(sk), len(sk)) if sk else "")
                for s, (m, sk, _man) in res.items())
            bad = any(sk for _m, sk, _man in res.values())
            (QMessageBox.warning if bad else QMessageBox.information)(self, tr("Prepare folders"), text)
            if not bad:
                chosen = list(getattr(self, "_prepare_chosen", []))
                QTimer.singleShot(0, lambda: self._prepare_folders(chosen))

        self.run_job(job, done, awake=N_("Prepare folders"), log_dir=next(iter(regroups)))

    def _merge_run(self, b, plans_):
        from . import nestmerge
        cancel = self.cancel_event
        cancel.clear()

        def job():
            ui.info(tr("Merging the backup inside the backup …"))
            return _per_drive(list(plans_), lambda s, cb: nestmerge.merge(plans_[s], cancel, progress=cb),
                              tr("merging"))

        def done(res):
            text = "\n".join(f"{_short(Path(s).parent.parent)}: " + trp(
                "%s file moved into the backup", "%s files moved into the backup", m.moved, f"{m.moved:,}")
                + ", " + trp("%s copy into %s", "%s copies into %s", m.duplicates, f"{m.duplicates:,}", m.review_dir)
                             + (trp(" (%d skipped)", " (%d skipped)", len(m.skipped), len(m.skipped)) if m.skipped else "")
                             for s, m in res.items())
            bad = any(m.skipped or m.cancelled for m in res.values())
            (QMessageBox.warning if bad else QMessageBox.information)(self, tr("Prepare folders"), text)
            if not bad:                           # on with the rest on the same drives
                chosen = list(getattr(self, "_prepare_chosen", []))
                QTimer.singleShot(0, lambda: self._prepare_folders(chosen))

        self.run_job(job, done, awake=N_("Prepare folders"), log_dir=next(iter(plans_)))

    def _offer_duplicates(self, b, sets, first, before=""):
        """The last part: duplicates inside the backup. First a QUICK check with what is on record
        (lists, reports, earlier checks – no file is read, seconds); only if it finds some, the
        user is asked – with the numbers (user 2026-11-23: a blind question right after the
        merge looked like a bug)."""
        from . import dedupe
        cancel = self.cancel_event
        cancel.clear()

        def quick():
            ui.status(tr("Looking for duplicates in the backup's lists …"))
            return _per_drive(sets, lambda s, cb: dedupe.scan(s, cancel, progress=cb, read=False),
                              tr("looking for duplicates"))

        def checked(scans):
            if any(r.cancelled for r in scans.values()):
                return
            if any(r.duplicates for r in scans.values()):
                self._duplicates_confirm(b, sets, scans, before)
                return
            unchecked = sum(r.unchecked for r in scans.values())
            text = (before + "\n\n" if before else "") + tr("The folders are prepared – no duplicates found.")
            if not unchecked:
                QMessageBox.information(self, tr("Prepare folders"), text)
                return
            if QMessageBox.question(self, tr("Prepare folders"), text + "\n\n" + trp(
                    "%s file has the same size as another one but no checksum on record – read it to be sure?",
                    "%s files have the same size as another one but no checksum on record – read them to be sure?",
                    unchecked, f"{unchecked:,}")) == QMessageBox.Yes:
                self.run_job(lambda: _per_drive(sets, lambda s, cb: dedupe.scan(s, cancel, progress=cb),
                                                tr("looking for duplicates")),
                             lambda sc: self._duplicates_confirm(b, sets, sc), awake=N_("Prepare folders"))

        self.run_job(quick, checked, awake=N_("Prepare folders"))

    def _duplicates_confirm(self, b, sets, scans, before=""):
        if any(r.cancelled for r in scans.values()):
            return
        found = {s: r for s, r in scans.items() if r.duplicates}
        if not found:
            QMessageBox.information(self, tr("Prepare folders"), tr("No duplicate files found."))
            return
        example = ""
        g0 = next((g for r in found.values() for g in r.groups), None)
        if g0 is not None and len(g0.entries) > 1:
            example = " " + tr("(e.g. %s and %s)", Path(g0.entries[0].path).name, Path(g0.entries[1].path).name)
        lines = "\n".join(f"{_short(Path(s).parent.parent)}: " + trp(
            "%s photo or video is in this backup twice (%s)", "%s photos and videos are in this backup twice (%s)",
            r.duplicates, f"{r.duplicates:,}", ui.human_size(r.duplicate_bytes)) for s, r in found.items())
        box = QMessageBox(QMessageBox.Question, tr("Prepare folders"), (before + "\n\n" if before else "")
                          + lines + example + "\n\n" + tr(
            "They are moved into a folder “Duplicates <date>” beside the backup folder – nothing is "
            "deleted, they can be put back. Each one is checked completely (SHA-256) right before it "
            "is moved."), parent=self)
        go = box.addButton(tr("Move duplicates"), QMessageBox.AcceptRole)
        details = box.addButton(tr("Look at them first…"), QMessageBox.ActionRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(go)
        box.exec()
        if box.clickedButton() is details:
            if len(found) > 1:                     # one page per drive: which one?
                from PySide6.QtWidgets import QInputDialog
                names = [f"{_short(Path(s).parent.parent)} – " + trp("%d duplicate", "%d duplicates",
                         r.duplicates, r.duplicates) for s, r in found.items()]
                pick, ok = QInputDialog.getItem(self, tr("Prepare folders"), tr("Look at the duplicates on:"),
                                                names, 0, False)
                if not ok:
                    return
                s = list(found)[names.index(pick)]
            else:
                s = next(iter(found))
            self._open_cleanup(b, s, found[s])
            return
        if box.clickedButton() is not go:
            return
        from . import dedupe
        cancel = self.cancel_event
        cancel.clear()

        def job():
            ui.info(tr("Moving duplicates into a review folder …"))
            return _per_drive(list(found), lambda s, cb: dedupe.move(found[s], cancel, progress=cb),
                              tr("moving duplicates"))

        def done(moved):
            text = "\n".join(tr("%s: %d duplicates moved to %s", _short(Path(s).parent.parent), m.moved,
                                m.review_dir) + (trp(" (%d skipped)", " (%d skipped)", len(m.skipped),
                                                     len(m.skipped)) if m.skipped else "")
                             for s, m in moved.items())
            QMessageBox.information(self, tr("Prepare folders"), text or tr("Nothing was moved."))
            self._fill_backup_drives()
            self._refresh_backups()

        self.run_job(job, done, awake=N_("Prepare folders"), log_dir=sets[0])

    def _check_backup_folder(self):
        """Hash the photos and videos no log knows (knownhash.check) – in the background, with the
        file at the bottom; a cancel keeps what was done."""
        from . import knownhash
        b = self._current_backup()
        if b is None or self.busy:
            return
        rel = setfolders.rel(b["phone"], b["owner"])
        drives = [d for d in getattr(self, "_unknown_media", {}) if (Path(d) / rel).is_dir()]
        if not drives:
            return
        n = sum(self._unknown_media[d] for d in drives)
        if QMessageBox.question(self, tr("Check backup folder"), trp(
                "%s photo or video has no checksum in the backup's list or reports.",
                "%s photos and videos have no checksum in the backup's list or reports.", n, f"{n:,}")
                + "\n\n" + tr("Read them now and remember their SHA-256? Nothing is changed or moved; you can "
                               "cancel at any time and keep what was done.")) != QMessageBox.Yes:
            return
        cancel = self.cancel_event
        cancel.clear()
        ui.title(tr("Check backup folder – %s", lastbackup.title({"owner": b["owner"], "phone": b["phone"]})))

        def job():
            ui.status(tr("Looking for the photos and videos without a checksum …"))

            def one(s, cb):
                _known, unknown = knownhash.known(s)
                return knownhash.check(s, unknown, cancel, progress=cb)
            got = _per_drive([str(Path(d) / rel) for d in drives], one, tr("checking"))
            return {str(Path(s).parent.parent): v for s, v in got.items()}

        def done(out):
            hashed = sum(h for h, _e in out.values())
            errs = [(d, rel_, why) for d, (_h, e) in out.items() for rel_, why in e]
            text = trp("%s photo or video read and its checksum remembered.",
                       "%s photos and videos read and their checksums remembered.", hashed, f"{hashed:,}")
            if errs:
                text += "\n\n" + trp("%s could not be read:", "%s could not be read:", len(errs), f"{len(errs):,}") + \
                        "\n" + "\n".join(f"• {Path(r).name}: {w}" for _d, r, w in errs[:5])
            (QMessageBox.warning if errs else QMessageBox.information)(self, tr("Check backup folder"), text)

        self.run_job(job, done, awake=N_("Check backup folder"), log_dir=str(Path(drives[0]) / rel))

    # ------------------------------------------------------------- integrity check (2026-11-23)
    def _integrity_check(self):
        """Choose the drives, read every photo/video, compare with the checksum on record."""
        b = self._current_backup()
        if b is None:
            return
        rel = setfolders.rel(b["phone"], b["owner"])
        comp = self._completeness(b)
        drives = [d for d in b["drives"] if (Path(d) / rel).is_dir()]
        if not drives:
            QMessageBox.information(self, tr("Integrity check"), tr("No drive of this backup is connected."))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Integrity check – %s", lastbackup.title({"owner": b["owner"], "phone": b["phone"]})))
        lay = QVBoxLayout(dlg)
        lab = QLabel(tr("Every photo and video on the ticked drives is read completely and its SHA-256 compared "
                        "with the one on record (the backup's list, its reports, or an earlier check). "
                        "Nothing is changed or moved; a report goes into the drive's Logs folder."))
        lab.setWordWrap(True)
        lay.addWidget(lab)
        lst = QListWidget()
        lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for d in drives:
            st = comp.get(d) or {}
            size = (" – " + _media_text((st["files"], st["bytes"]))) if "bytes" in st else ""
            it = QListWidgetItem(_short(d) + size)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            it.setData(Qt.UserRole, d)
            it.setToolTip(str(Path(d) / rel))
            lst.addItem(it)
        lay.addWidget(lst)
        save = _gui().WrapCheck(tr("Save the new checksums in the backup's checksum table (the backup's list "
                                   "itself is not changed)"))
        save.setChecked(True)
        lay.addWidget(save)
        bg = _gui().WrapCheck(tr("Run in the background – keep using the app meanwhile (the progress is shown "
                                 "at the bottom)"))
        bg.setChecked(True)
        lay.addWidget(bg)
        row = QHBoxLayout()
        sel_all = QPushButton(tr("Select all"))
        sel_all.clicked.connect(lambda: [lst.item(i).setCheckState(Qt.Checked) for i in range(lst.count())])
        row.addWidget(sel_all)
        row.addStretch()
        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        go = bb.addButton(tr("Check"), QDialogButtonBox.AcceptRole)
        go.setDefault(True)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        row.addWidget(bb)
        lay.addLayout(row)
        dlg.resize(620, dlg.sizeHint().height())
        if dlg.exec() != QDialog.Accepted:
            return
        picked = [lst.item(i).data(Qt.UserRole) for i in range(lst.count())
                  if lst.item(i).checkState() == Qt.Checked]
        if not picked:
            return
        self._run_integrity(b, [str(Path(d) / rel) for d in picked], save.isChecked(), bg.isChecked())

    def _run_integrity(self, b, set_dirs, save, background):
        from . import integrity
        title = tr("Integrity check – %s", lastbackup.title({"owner": b["owner"], "phone": b["phone"]}))

        def work(cancel):
            def one(s, cb):
                res = integrity.run(s, cancel, cb)
                if save:
                    integrity.save(res)
                integrity.write_report(res)
                ui.info(f"  {_short(Path(s).parent.parent)}: " + integrity.summary(res))
                return res
            got = _per_drive(set_dirs, one, tr("reading"), channel="background" if background else "")
            return [got[s] for s in set_dirs]

        def done(results):
            bad = any(r.changed or r.gone or r.unreadable for r in results)
            text = "\n\n".join(f"{_short(Path(r.set_dir).parent.parent)}: " + integrity.summary(r) for r in results)
            text += "\n\n" + tr("The reports are in the Logs folder of each drive.")
            if save:
                text += "\n" + tr("The new checksums were saved.")
            box = QMessageBox(QMessageBox.Warning if bad else QMessageBox.Information, title, text, parent=self)
            open_btn = box.addButton(tr("Open report"), QMessageBox.ActionRole) if results else None
            box.addButton(QMessageBox.Ok)
            box.exec()
            if open_btn is not None and box.clickedButton() is open_btn:
                self._open(results[0].report)

        if background:
            ui.title(title + " – " + tr("in the background"))
            self.run_background(title, work, done)
        else:
            cancel = self.cancel_event
            cancel.clear()
            ui.title(title)
            self.run_job(lambda: work(cancel), done, awake=N_("Integrity check"),
                         log_dir=set_dirs[0])

    def _open_cleanup(self, b, set_dir, result=None):
        """The duplicates page (review, keep another copy, put back) for one folder – with the
        search already made, if there is one."""
        if result is not None:
            self.cleanup_tab.show_result(result)
        else:
            self.cleanup_tab.folder.setText(str(set_dir))
        self.cleanup_page.title_label.setText(tr("Duplicates – %s on %s", lastbackup.title(
            {"owner": b["owner"], "phone": b["phone"]}), _short(Path(set_dir).parent.parent)))
        self.pages.setCurrentWidget(self.cleanup_page)

    def _run_update_drives(self, b, targets):
        from . import reconcile
        rel = setfolders.rel(b["phone"], b["owner"])
        cancel = self.cancel_event
        cancel.clear()
        ui.title(tr("Prepare folders – %s", lastbackup.title({"owner": b["owner"], "phone": b["phone"]})))

        def job():
            return reconcile.update_drives(b["drives"], rel, self.cfg, targets=targets, cancel=cancel)

        def done(res):
            status, filled, problems = res
            copied = sum(r.copied for lst in filled.values() for r in lst)
            size = sum(r.bytes for lst in filled.values() for r in lst)
            errors = sum(len(r.errors) for lst in filled.values() for r in lst)
            text = tr("%d files (%s) copied and checked with SHA-256, %d errors.", copied, ui.human_size(size), errors)
            if problems:
                text += "\n\n" + "\n".join(problems)
            ok = status == "COMPLETED"
            (QMessageBox.information if ok else QMessageBox.warning)(
                self, tr("Prepare folders"), _gui()._status_text(status) + "\n\n" + text)
            self._fill_backup_drives()
            self._refresh_backups()

        self.run_job(job, done, awake=N_("Prepare folders"),
                     log_dir=str(Path(targets[0]) / rel))

    def _set_backup_drives(self, drives):
        b = self._current_backup()
        if b is None:
            return
        backuplist.save_profile(self.cfg, b["key"], destinations=list(drives))
        b["drives"] = list(drives)
        self._fill_backup_drives()
        self._update_backup_hints()
        self._refresh_backups()

    def _fill_backup_drive_menu(self):
        """The ATTACHED DRIVES (user request 2026-11-23: "Add drive shows folders, not drives"). Picking
        one searches it for this backup; if it is not there, a new backup folder can be started."""
        from . import findbackup
        m = self.backup_drive_menu
        m.clear()
        b = self._current_backup()
        if b is None:
            return
        drives = detect_drives()
        roots = [r for r, _f in drives]
        used = {}
        for d in b["drives"]:
            r = findbackup.mount_root(d, roots)
            if r and os.path.isdir(d):
                used[r] = d
        m.addSection(tr("Attached drives"))
        if not drives:
            a = m.addAction(tr("No drive attached – attach (or open) the drive first."))
            a.setEnabled(False)
        for root, free in drives:
            label = f"{_drive_name(root)}   –   " + tr("%s free", ui.human_size(free))
            if root in used:
                label += "   –   " + tr("already a drive of this backup (%s)", _short(used[root]))
            a = m.addAction(label)
            a.setEnabled(root not in used)
            a.setToolTip(root)
            a.triggered.connect(lambda _c=False, r=root: self._add_drive(r))
        if len(drives) > 1:
            m.addSeparator()
            m.addAction(tr("All attached drives"), self._integrate_all_drives)

    def _add_drive(self, root):
        """A drive was picked: find this backup on it and check it (backupid.check)."""
        b = self._current_backup()
        if b is None or self.busy:
            return
        self._run_integrate(b, [root], new_on=root)

    def _new_backup_on_drive(self, b, root, here=False):
        """The backup is not on the drive: start its folder there (name suggested from the others,
        e.g. MMMB_Vol.3), mark it and offer to copy the files from the other drive(s)."""
        import re
        from PySide6.QtWidgets import QInputDialog
        from . import backupid
        who = lastbackup.title({"owner": b["owner"], "phone": b["phone"]})
        why = self._dest_problem(str(root), [d for d in b["drives"] if os.path.isdir(d)])
        if why:                                  # user decision 2026-11-23: refused, with the reason
            QMessageBox.warning(self, tr("Not possible as a backup destination"), why)
            return
        nums, prefix = [], "MMMB_Vol."
        for d in b["drives"]:
            mt = re.match(r"^(.*?)(\d+)$", Path(d).name)
            if mt:
                prefix = mt.group(1)
                nums.append(int(mt.group(2)))
        suggest = f"{prefix}{max(nums, default=0) + 1}"
        if here:
            if QMessageBox.question(self, tr("Integrate folder"), tr(
                    "%s is not in %s.\n\nStart it in this folder?", who, root)) != QMessageBox.Yes:
                return
            base = Path(root)
        else:
            name, ok = QInputDialog.getText(
                self, tr("Add drive"),
                tr("%s is not on %s yet.", who, _drive_name(root)) + "\n\n"
                + tr("Start it there in this folder (on the top level of the drive):"), text=suggest)
            name = (name or "").strip().strip("/\\")
            if not ok or not name:
                return
            base = Path(root) / name
        rel = setfolders.rel(b["phone"], b["owner"])
        if (base / rel).exists():
            QMessageBox.warning(self, tr("Add drive"), tr(
                "%s already contains a folder of this backup that did not pass the check – choose "
                "another name.", base))
            return
        try:
            (base / rel).mkdir(parents=True, exist_ok=True)
            bid, _c = backupid.resolve(self.cfg, b["key"], [str(Path(d) / rel) for d in b["drives"]])
            if bid:
                backupid.write(base / rel, bid, b["owner"], b["phone"])
        except OSError as e:
            QMessageBox.warning(self, tr("Add drive"), str(e))
            return
        ui.ok(tr("New backup drive: %s", base))
        self._set_backup_drives(b["drives"] + [str(base)])
        self._offer_fill_drives(b, str(base))

    def _offer_fill_drives(self, b, added):
        """After a drive was added: the drives are compared; if one of them misses files, offer to
        fill each drive from the other(s) (user request 2026-11-22)."""
        if self.busy or not os.path.isdir(added):
            return
        comp = self._completeness(b, live=True)
        live = {d: v for d, v in comp.items() if v.get("live")}
        behind = {d: v["missing"] for d, v in live.items() if v.get("missing")}
        if len(live) < 2:
            return
        if not behind:
            QMessageBox.information(self, tr("Add a backup drive"), tr(
                "%s holds the same backup as the other connected drive(s) – all files are there.",
                _short(added)))
            return
        lines = "\n".join(tr("%s: %d files missing", _short(d), n) for d, n in behind.items())
        if QMessageBox.question(self, tr("Add a backup drive"), tr(
                "Same backup, but the drives do not have the same files:") + "\n\n" + lines + "\n\n"
                + tr("Copy the missing files now – each drive from the other(s)? Each file is checked "
                     "with SHA-256; nothing is deleted or overwritten.")) != QMessageBox.Yes:
            return
        self._run_update_drives(b, list(live))

    def _remove_backup_drives(self):
        b = self._current_backup()
        drives = {it.data(0, Qt.UserRole) for it in self.backup_drives.selectedItems()} - {None}
        if b is None or not drives:
            QMessageBox.information(self, tr("Remove"), tr("Select one or more drives in the list first "
                                                       "(Ctrl- or Shift-click, or “Select all”)."))
            return
        if QMessageBox.question(
                self, tr("Remove from this backup"),
                tr("This backup is no longer written to:") + "\n\n" + "\n".join(sorted(drives)) + "\n\n"
                + tr("Nothing on the drives is deleted.")) != QMessageBox.Yes:
            return
        self._set_backup_drives([d for d in b["drives"] if d not in drives])

    # ---------------------------------------------------------------- import tab
    def _backup_import_changed(self):
        b = self._current_backup()
        if b is not None:
            src = self.backup_import
            backuplist.save_profile(self.cfg, b["key"], import_roots=list(src.roots),
                                    import_choices={r: dict(src.choices.get(r, {})) for r in src.roots})

    def _start_import(self):
        g = _gui()
        b = self._current_backup()
        if b is None:
            QMessageBox.information(self, tr("Import media"), tr("Choose a backup in the list above."))
            return
        why = self.backup_import.check_ready()
        if why:
            QMessageBox.warning(self, tr("Cannot start yet"), why)
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            g._log_mount_msgs(mount_for_paths_status(b["drives"]))
            for d in b["drives"]:
                if os.path.isdir(d):
                    setfolders.relocate(d, self.cfg)
        finally:
            QApplication.restoreOverrideCursor()
        parents = [c for c in (backuplist.copy_on(d, b["phone"], b["owner"]) for d in b["drives"]) if c]
        if not parents:
            QMessageBox.warning(self, tr("Cannot start yet"),
                                tr("No backup drive of this backup is connected. Connect one (tab “Backup "
                                   "drives”) and try again."))
            return
        sel = self.backup_import.selections()
        try:
            check_selection(sel, parents)
        except ValueError as e:
            QMessageBox.warning(self, tr("Cannot start yet"), str(e))
            return
        if not g.ask_layout(self, self.cfg, parents):
            return
        self.last_folder = parents[0]
        other = self.backup_import.other_files()
        ui.title(tr("Import into %s", lastbackup.title({"owner": b["owner"], "phone": b["phone"]})))
        self.run_job(lambda: g.perform_selection_import(sel, parents, self.cfg, other_files=other,
                                                        interactive=True, cancel=self.cancel_event),
                     self._import_done, awake=N_("Import"), log_dir=str(self.last_folder))

    def _import_done(self, res):
        status, paths, _results, verdict = res
        self._finished(status, paths, verdict, N_("Import"))
        self._refresh_backups()
        self._fill_export_sources()

    # ---------------------------------------------------------------- page 2: old phone / drive
    def _build_old_import_page(self):
        g = _gui()
        w = QWidget()
        lay = QVBoxLayout(w)
        head = QHBoxLayout()
        back = QPushButton(tr("← Back to your backups"))
        back.clicked.connect(lambda: self._show_old_import(False))
        title = QLabel(tr("New backup of an old phone or old drive"))
        title.setStyleSheet("font-size:15px;font-weight:600")
        head.addWidget(back)
        head.addSpacing(10)
        head.addWidget(title, 1)
        lay.addLayout(head)
        info = QLabel(tr(
            "Backs up an old phone or an old hard drive like a phone (its own backup “Owner/Name” on the "
            "drive). Add the folder(s) – e.g. the copy of the old phone or the photo folders on the old "
            "drive – and choose how they are sorted. Every file is checked with SHA-256, identical files "
            "are stored only once, and the old folders are only read – never changed."))
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{GRAY}")
        lay.addWidget(info)
        self.old_import = ImportSources(into_existing=False)
        self.old_import.changed.connect(self._update_import_preview)
        lay.addWidget(g._group(tr("Folders to import (one or more, e.g. the old phone and its SD card)"),
                               self.old_import))
        form = QFormLayout()
        self.import_phone_edit = QLineEdit()
        self.import_phone_edit.setPlaceholderText(tr("e.g. Galaxy S7"))
        self.import_owner_edit = QLineEdit(self.cfg.get("owner", ""))
        self.import_owner_edit.setPlaceholderText(tr("e.g. Karen"))
        form.addRow(tr("Name (old phone or drive):"), self.import_phone_edit)
        form.addRow(tr("Owner:"), self.import_owner_edit)
        box = QVBoxLayout()
        box.addLayout(form)
        self.import_dest_list = g.LocationList(
            self.cfg, "destinations", "import_selected_destinations", True, "PhoneBackups",
            tr("Tick the drive(s) to write the new backup to – all ticked drives at the same time."),
            plans_column=True)
        self.import_dest_list.changed.connect(self._update_import_preview)
        box.addWidget(self.import_dest_list)
        self.import_preview = QLabel()
        self.import_preview.setWordWrap(True)
        self.import_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.addWidget(self.import_preview)
        self.import_phone_edit.textChanged.connect(self._update_import_preview)
        self.import_owner_edit.textChanged.connect(self._update_import_preview)
        lay.addWidget(g._group(tr("New backup"), box))
        row = QHBoxLayout()
        row.addStretch()
        self.start_old_import_btn = g._big_button(tr("Start"))
        self.start_old_import_btn.clicked.connect(self._start_old_import)
        row.addWidget(self.start_old_import_btn)
        lay.addLayout(row)
        lay.addStretch()
        self._update_import_preview()
        return w

    def _show_old_import(self, on):
        if on:
            self.import_dest_list.rebuild()
            self._update_import_preview()
        else:
            self._refresh_backups()
        self.backups_stack.setCurrentIndex(1 if on else 0)
        self.backup_actions.setVisible(not on)

    def _update_import_preview(self):
        if not hasattr(self, "import_preview"):
            return
        phone = self.import_phone_edit.text().strip() or tr("<old phone>")
        owner = self.import_owner_edit.text().strip() or tr("<owner>")
        dests = self.import_dest_list.selected_paths()
        base = Path(dests[0]) if dests else Path(tr("<drive>"))
        parent = base / setfolders.rel(phone, owner)
        self.import_preview.setText(
            tr("Sorted folders → %s   (RAW → YEAR/raw/)", parent / tr("YEAR") / tr("YY.MM"))
            + "\n" + tr("Kept folders → %s", parent / tr("<original folder>")))

    def _start_old_import(self):
        g = _gui()
        why = self.old_import.check_ready()
        if why:
            QMessageBox.warning(self, tr("Cannot start yet"), why)
            return
        sel = self.old_import.selections()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._mount_selected(self.import_dest_list)
        finally:
            QApplication.restoreOverrideCursor()
        phone = self.import_phone_edit.text().strip()
        owner = self.import_owner_edit.text().strip()
        dests = self.import_dest_list.selected_available()
        problems = []
        if not phone:
            problems.append(tr("Enter the name of the old phone."))
        if not owner:
            problems.append(tr("Enter the owner's name."))
        if not dests:
            problems.append(tr("Tick at least one connected destination drive."))
        if problems:
            QMessageBox.warning(self, tr("Cannot start yet"), "\n".join(problems))
            return
        name = setfolders.rel(phone, owner)          # 'Sam/Galaxy S7'
        for d in dests:
            setfolders.relocate(d, self.cfg)
        try:
            check_selection(sel, [Path(d) / name for d in dests])
        except ValueError as e:
            QMessageBox.warning(self, tr("Cannot start yet"), str(e))
            return
        existing = [d for d in dests if (Path(d) / name).is_dir()]
        if existing and QMessageBox.question(
                self, tr("Backup already exists"),
                tr("There is already a backup “%s” on", name) + "\n" + "\n".join(existing) + "\n\n" +
                tr("Add the files to it? (Files already in it are not copied twice.)")) != QMessageBox.Yes:
            return
        if not g.ask_layout(self, self.cfg, [Path(d) / name for d in dests]):
            return
        self.last_folder = str(Path(dests[0]) / name)
        other = self.old_import.other_files()
        ui.title(tr("Import old phone %s – %s", phone, owner))
        self.run_job(lambda: g.perform_old_phone_import(sel, phone, owner, dests, self.cfg,
                                                        other_files=other, interactive=True,
                                                        cancel=self.cancel_event),
                     self._import_done, awake=N_("Import"), log_dir=str(self.last_folder))


# =========================================================================== phone app (settings)

class AppUpdateBox(QWidget):
    """"The phone app on this phone is outdated" + one button (user request 2026-11-17): start page
    rows and Manage backups → Overview. Filled by PhoneAppMixin._fill_app_update."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("appUpdateBox")
        self.setStyleSheet(theme.notice_css("appUpdateBox"))
        lay = QHBoxLayout(self)
        theme.bar_margins(lay, 8, 4, 8, 4)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.button = QPushButton()
        self.button.clicked.connect(self.clicked)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.button, 0, Qt.AlignVCenter)
        self.one_click = False
        self.hide()


class PhoneAppMixin:
    """Program settings → "Versions and phone app" (user request 2026-11-10): versions, what the
    phone app does, and installing it by USB cable, QR code or – as a last resort – Bluetooth."""

    def _build_phone_app_box(self):
        from . import __version__
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.versions_label = QLabel()
        self.versions_label.setWordWrap(True)
        self.versions_label.setTextFormat(Qt.RichText)
        self.versions_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.versions_label)
        info = QLabel(
            "<b>" + tr("What the phone app does") + "</b><br>"
            + tr("“My Mobile Media Backup” is a small app for the phone. It may only <b>read</b> photos and videos – "
                 "it cannot delete or change anything, reads no other files, contacts or messages, has no "
                 "ads and talks to no server on the internet. It only answers the computer it is paired "
                 "with (encrypted).") + "<br><br><b>" + tr("What you gain") + "</b><ul>"
            + "<li>" + tr("Backups over Wi-Fi – no cable, no USB debugging, no Developer options.") + "</li>"
            + "<li>" + tr("Fast cable backups: “Allow backup” switches USB debugging on "
                          "just for the backup – and off again afterwards.") + "</li>"
            + "<li>" + tr("“Connect phone…”: scan a QR code instead of searching settings.") + "</li>"
            + "<li>" + tr("The phone is recognised by its own key – a backup never lands in the wrong "
                          "phone's folder.") + "</li></ul><b>"
            + tr("Without the phone app") + "</b><ul>"
            + "<li>" + tr("USB cable with USB debugging switched on by hand (Developer options): fast, "
                          "every file checked on the phone.") + "</li>"
            + "<li>" + tr("Wi-Fi with Android's Wireless debugging (Android 11+, pair once).") + "</li>"
            + "<li>" + tr("USB cable with “File transfer” (MTP): works on every phone, but slower and "
                          "without a check on the phone.") + "</li></ul>")
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        lay.addWidget(info)
        row = QHBoxLayout()
        cable = QPushButton(tr("Install / update over USB cable…"))
        cable.setToolTip(tr("Phone on the USB cable: with “File transfer” the app file is copied onto the "
                            "phone (you install it there); with USB debugging it is installed directly. "
                            "You are asked first."))
        cable.clicked.connect(self._install_app_cable)
        qr = QPushButton(tr("Install with QR code…"))
        qr.setToolTip(tr("Phone and computer in the same Wi-Fi: scan the code, download the app on the "
                         "phone and install it."))
        qr.clicked.connect(self._setup_phone_app)
        bt = QPushButton(tr("Send over Bluetooth…"))
        bt.setToolTip(tr("If nothing else works: sends the app file to a phone paired with this computer "
                         "over Bluetooth. Install it on the phone by tapping the received file."))
        bt.clicked.connect(self._install_app_bluetooth)
        for b in (cable, qr, bt):
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self.auto_update_row = QHBoxLayout()
        self.auto_update_label = QLabel()
        self.auto_update_label.setWordWrap(True)
        ask_again = QPushButton(tr("Ask again before updating the phone app"))
        ask_again.clicked.connect(self._ask_again_before_update)
        self.auto_update_btn = ask_again
        self.auto_update_row.addWidget(self.auto_update_label, 1)
        self.auto_update_row.addWidget(ask_again)
        lay.addLayout(self.auto_update_row)
        self._update_versions()
        return w

    def _phone_app_state(self, *names):
        """(version, outdated, one_click) of the phone app on the phone called `names` (phone name,
        model): the connected phone's live version, else the one seen at its last connection.
        one_click: this phone is connected over ADB (cable or Wireless debugging) – the update can be
        installed right away."""
        g = _gui()
        src = self.source
        here = src is not None and any(companion.same_phone_name(src.device_name, n) for n in names)
        live = ""
        if here:
            live = (src.app_version if isinstance(src, companion.CompanionSource)
                    else getattr(src, "companion_version", ""))
        paired = companion.paired_for(self.cfg, *names)
        version = live or (paired or {}).get("app_version", "")
        one_click = here and isinstance(src, g.AdbSource) and g.apk_path() is not None
        # same version number, other build (the phone app has the program's version): checked by
        # comparing the app file when the phone was connected over ADB (user 2026-11-17)
        old_build = here and bool(getattr(src, "companion_build_differs", False))
        return version, companion.app_outdated(version) or old_build, one_click

    def _fill_app_update(self, box, *names):
        version, old, one_click = self._phone_app_state(*names)
        box.setVisible(old)
        if not old:
            return
        box.one_click = one_click
        if version == companion.APP_VERSION_NAME:
            box.label.setText(tr("Phone app outdated: the phone has an older build of version %s than the one "
                                 "included in this program.", version))
        else:
            box.label.setText(tr("Phone app outdated: version %s on the phone, this program includes version %s.",
                                 version, companion.APP_VERSION_NAME))
        if one_click:
            box.button.setText(tr("Update phone app"))
            box.button.setToolTip(tr("Installs version %s of the phone app on the connected phone now. Your "
                                     "photos, videos and the pairing stay as they are.",
                                     companion.APP_VERSION_NAME))
            box.button.setEnabled(not self.busy)
        else:
            box.button.setText(tr("Phone app settings…"))
            box.button.setToolTip(tr("Connect the phone with the USB cable (USB debugging) or Wireless "
                                     "debugging for a one-click update – or see the other ways to update "
                                     "it in Program settings."))
            box.button.setEnabled(True)

    def _app_update_clicked(self, box):
        if box.one_click and isinstance(self.source, _gui().AdbSource):
            self._install_app_cable(one_click=True)
            return
        self._open_program_settings()
        group = getattr(self, "phone_app_group", None)
        area = group.parentWidget() if group is not None else None
        while area is not None and not isinstance(area, QScrollArea):
            area = area.parentWidget()
        if area is not None:
            area.ensureWidgetVisible(group)

    def _remove_old_app_copies(self, src):
        """Worker thread, phone on ADB: remove every OLD copy of the phone app (earlier package
        name). An old copy keeps running and answers instead of the current app – the program then
        talks to the old app (user 2026-11-17: "phone app 0.7.0" although the app said 0.9.8.4).
        ALWAYS removed, without a question (user decision 2026-11-17): after every install /
        update of the phone app and whenever a phone with an old copy is connected. Its pairing is
        forgotten; the current app is then paired once more (code on the phone)."""
        try:
            olds = src.old_companion_copies()
        except Exception as e:  # noqa: BLE001
            ui.warn(tr("Could not check for old copies of the phone app: %s", e))
            return
        if not olds:
            return
        phone = f"{src.manufacturer} {src.device_name}".strip() or tr("the phone")
        old_versions = [v for _p, v in olds if v]
        # the pairing that belongs to the old copy: the paired phone it answers for
        forget = set()
        try:
            link, _why = companion.link_over_cable(src, self.cfg)
        except Exception:  # noqa: BLE001
            link = None
        if link is not None:
            if link.app_version in old_versions:
                forget.add(link.entry["phone_id"])
            link.close()
        for p in companion.phones(self.cfg):        # old copy not running: same phone, old version
            if p.get("app_version") in old_versions and companion.same_phone_name(p.get("name"), src.device_name):
                forget.add(p["phone_id"])
        for pkg, version in olds:
            ok, msg = src.remove_old_companion(pkg)
            if ok:
                ui.ok(tr("Old copy of the phone app (version %s) removed from %s – it blocked the current "
                         "app.", version or "?", phone))
            else:
                ui.warn(tr("The old copy of the phone app could not be removed: %s – remove “%s” "
                           "(version %s) on the phone by hand.", msg, companion.APP_NAME, version or "?"))
                return
        for phone_id in forget:
            companion.forget_phone(self.cfg, phone_id)

    def _check_same_phone(self, entry, serial=None):
        """Main thread, after a phone was verified (cable: with its serial number) or paired: never
        the same phone twice in "Known phones" (user request 2026-11-17). Same serial number →
        the older pairing is removed; same name without a serial number → asked once."""
        if not entry:
            return
        for p in companion.remember_serial(self.cfg, entry, serial):
            ui.info(tr("Older pairing of %s (from %s) removed – it is the same phone (serial %s).",
                       p.get("name") or tr("the phone"), p.get("paired", "?"), serial))
        _sure, maybe = companion.same_phone_pairings(self.cfg, entry, serial)
        for p in maybe:
            box = QMessageBox(QMessageBox.Question, tr("The same phone?"), tr(
                "“Known phones” lists %s twice: the one connected now (paired %s) and one paired %s. "
                "A phone gets a new pairing when its phone app was installed again.\n\nIs it the same "
                "phone?", p.get("name") or tr("this phone"), entry.get("paired", "?"), p.get("paired", "?")),
                parent=self)
            same = box.addButton(tr("Same phone – remove the old pairing"), QMessageBox.AcceptRole)
            box.addButton(tr("A different phone – keep both"), QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is same:
                companion.forget_phone(self.cfg, p["phone_id"])
                ui.info(tr("Older pairing of %s (from %s) removed.", p.get("name") or "", p.get("paired", "?")))
            else:
                companion.mark_different(self.cfg, entry, p)
        if hasattr(self, "known_phones"):
            self.known_phones.fill()

    def _ask_again_before_update(self):
        self.cfg["companion_auto"] = []
        from . import config
        config.save(self.cfg)
        ui.ok(tr("The program asks again before it installs or updates the phone app."))
        self._update_versions()

    def _update_versions(self):
        from . import __version__
        from .companion import APP_VERSION_NAME, CompanionSource
        lines = [tr("This program: version %s", f"<b>{html.escape(__version__)}</b>"),
                 tr("Phone app included in this program: version %s", f"<b>{APP_VERSION_NAME}</b>")]
        # only the phone connected right now – never phones used before (user request 2026-11-10)
        src = self.source
        now = ""
        if isinstance(src, CompanionSource):
            now = src.app_version
        elif src is not None:
            now = getattr(src, "companion_version", "")
        if now:
            name = f"{getattr(src, 'manufacturer', '')} {src.device_name or ''}".strip() or tr("the connected phone")
            lines.append(tr("Phone app on %s: %s", html.escape(name), f"<b>{html.escape(now)}</b>")
                         + (f" <span style='color:{ORANGE}'>– {tr('an update is available')}</span>"
                            if _older(now, APP_VERSION_NAME) else ""))
        self.versions_label.setText("<br>".join(lines))
        auto = self.cfg.get("companion_auto", [])
        self.auto_update_label.setText(
            trp("The phone app is updated automatically (without asking) on %d phone.",
                "The phone app is updated automatically (without asking) on %d phones.", len(auto), len(auto))
            if auto else "")
        self.auto_update_label.setVisible(bool(auto))
        self.auto_update_btn.setVisible(bool(auto))

    def _remember_app_version(self, entry, version):
        """Save the phone app version of a paired phone (shown on the start page and in Overview)."""
        if not entry or not version:
            return
        for p in companion.phones(self.cfg):
            if p.get("phone_id") == entry.get("phone_id"):
                if p.get("app_version") != version:
                    p["app_version"] = version
                    companion.save_phone(self.cfg, p)
                break
        entry["app_version"] = version
        if hasattr(self, "versions_label"):
            self._update_versions()
        self._update_home()

    # ---- install over the USB cable (always asked first - user rule 2026-11-05)
    def _install_app_cable(self, one_click=False):
        """one_click: the button "Update phone app" (start page / Overview) – its text and tooltip
        say what happens, so no second question (user request 2026-11-17); over the cable or
        Wireless debugging."""
        g = _gui()
        src = self.source
        one_click = one_click and isinstance(src, g.AdbSource)
        if src is not None and hasattr(src, "put_file") and not isinstance(src, g.AdbSource):
            self._copy_app_by_file_transfer(src)
            return
        if not one_click and not (isinstance(src, g.AdbSource) and not src.wireless):
            box = QMessageBox(QMessageBox.Information, tr("Install over USB cable"), tr(
                "Connect the phone with the USB cable, unlock it and choose “File transfer” on the phone – "
                "the program connects by itself. Then click this button again: the app file is copied "
                "onto the phone and you install it there."), parent=self)
            guide = box.addButton(tr("How to switch on USB debugging…"), QMessageBox.ActionRole)
            box.addButton(QMessageBox.Close)
            box.exec()
            if box.clickedButton() is guide:
                self._show_usb_guide()
            return
        apk = g.apk_path()
        if apk is None:
            QMessageBox.warning(self, tr("Phone app"), tr("The phone app is not included in this program."))
            return

        def job():
            state = src.companion_state(apk)
            installed = getattr(src, "companion_version", "")
            phone = f"{src.manufacturer} {src.device_name}".strip() or tr("the phone")
            ask = "reinstall" if state == "ready" else state
            if not one_click:
                title, text, details = g.install_question(ask, phone, src.serial, installed, os.path.getsize(apk))
                if not ui.ask_install(title, text, details):
                    ui.info(tr("Nothing installed on %s.", phone))
                    return False
            ui.info(tr("Installing the phone app “%s” %s on %s (serial %s) …",
                       g.COMPANION_NAME, g.COMPANION_VERSION, phone, src.serial))
            ok, msg = src.install_companion(apk)
            if not ok:
                ui.warn(tr("The phone app could not be set up: %s – Samsung: switch off “Auto "
                           "Blocker”. Xiaomi: switch on “Install via USB” in the Developer options.", msg))
                return False
            src.companion_version = g.COMPANION_VERSION
            src.companion_build_differs = False        # now the bundled build (user 2026-11-17)
            ui.ok(tr("Phone app “%s” %s installed on %s.", g.COMPANION_NAME, g.COMPANION_VERSION, phone))
            self._remove_old_app_copies(src)          # always – never two copies (user 2026-11-17)
            return True

        def done(ok):
            if ok:
                paired = companion.paired_for(self.cfg, src.device_name)
                if paired is not None:
                    paired["app_version"] = g.COMPANION_VERSION
                    companion.save_phone(self.cfg, paired)
            if ok and self.source is src:
                self._companion_asked.discard(src.serial)       # check / pair it like a new phone
                self._cable_setup(src)
            self._update_versions()
            self._update_home()

        self.run_job(job, done)

    def _copy_app_by_file_transfer(self, src, asked=False):
        """Phone on the cable in "File transfer" mode: copy the app file into its Download folder –
        no network, no browser, no USB debugging needed. Asked first (user rule 2026-11-05)."""
        g = _gui()
        apk = g.apk_path()
        if apk is None:
            QMessageBox.warning(self, tr("Phone app"), tr("The phone app is not included in this program."))
            return
        name = f"My-Media-Backup-{g.COMPANION_VERSION}.apk"
        steps = tr("On the phone: open “Files” → “Downloads”, tap “%s” and then “Install” (Android asks once "
                   "to allow installs from “Files”).", name)
        if asked:
            return self._run_app_copy(src, apk, name, steps)
        box = QMessageBox(QMessageBox.Question, tr("Copy the phone app onto the phone?"), tr(
            "This copies the file %s (%s, version %s) into the folder “Download” of %s over the USB "
            "cable. Nothing is installed by itself – you install it on the phone:",
            name, f"{os.path.getsize(apk) / 1e6:.1f} MB", g.COMPANION_VERSION,
            src.device_name or tr("the phone")) + "\n\n" + steps, parent=self)
        yes = box.addButton(tr("Copy onto the phone"), QMessageBox.AcceptRole)
        box.addButton(tr("Not now"), QMessageBox.RejectRole)
        box.setDefaultButton(box.buttons()[-1])
        box.exec()
        if box.clickedButton() is not yes:
            return
        self._run_app_copy(src, apk, name, steps)

    def _run_app_copy(self, src, apk, name, steps):
        def job():
            try:
                return src.put_file(apk, "Download", name), None
            except Exception as e:  # noqa: BLE001
                return None, str(e)

        def done(res):
            where, err = res
            if err:
                QMessageBox.warning(self, tr("Phone app"), tr("The file could not be copied onto the phone: %s", err))
                return
            ui.ok(tr("Phone app copied onto the phone: %s", where))
            QMessageBox.information(self, tr("Phone app copied"), tr("Done.") + "\n\n" + steps + "\n\n" + tr(
                "Then open the app, allow access to photos and videos, and connect it with this computer: "
                "“Connect phone…” on the start screen."))

        self.run_job(job, done)

    # ---- last resort: Bluetooth file transfer
    def _install_app_bluetooth(self):
        from . import btsend
        g = _gui()
        apk = g.apk_path()
        if apk is None:
            QMessageBox.warning(self, tr("Phone app"), tr("The phone app is not included in this program."))
            return
        ok, why = btsend.supported()
        if not ok:
            QMessageBox.warning(self, tr("Send over Bluetooth"), why)
            return
        steps = tr("On the phone: accept the file, open it (notification or Files → Downloads) and tap "
                   "“Install” (Android asks once to allow installs from that app). Then pair the app with "
                   "this computer: “Install with QR code…” or the USB cable.")
        if sys.platform.startswith("win"):
            QMessageBox.information(self, tr("Send over Bluetooth"), tr(
                "Windows opens “Send files via Bluetooth” and shows the app file %s – choose the phone, "
                "then that file.", Path(apk).name) + "\n\n" + steps)
            btsend.windows_wizard(apk)
            return
        try:
            devices = btsend.paired_devices()
        except btsend.BtSendError as e:
            QMessageBox.warning(self, tr("Send over Bluetooth"), str(e))
            return
        if not devices:
            QMessageBox.information(self, tr("Send over Bluetooth"), tr(
                "No phone is paired with this computer over Bluetooth yet. Pair it first in the "
                "computer's Bluetooth settings (switch on Bluetooth on the phone, choose it on the "
                "computer, confirm the code on both), then click this button again."))
            return
        names = [f"{n}  ({a})" for a, n in devices]
        from PySide6.QtWidgets import QInputDialog
        choice, ok = QInputDialog.getItem(self, tr("Send over Bluetooth"),
                                          tr("Send the phone app (%s, version %s) to:",
                                             f"{os.path.getsize(apk) / 1e6:.1f} MB", g.COMPANION_VERSION),
                                          names, 0, False)
        if not ok:
            return
        address = devices[names.index(choice)][0]
        if QMessageBox.question(self, tr("Send over Bluetooth"), tr(
                "Send the app file to %s now?", choice) + "\n\n" + steps) != QMessageBox.Yes:
            return
        ui.info(tr("Sending the phone app over Bluetooth to %s – accept the file on the phone …", choice))

        def job():
            try:
                btsend.send_apk(address, apk, g.COMPANION_VERSION, progress=None, cancel=self.cancel_event)
                return None
            except btsend.BtSendError as e:
                return str(e)

        def done(err):
            if err:
                QMessageBox.warning(self, tr("Send over Bluetooth"), err)
            else:
                ui.ok(tr("Phone app sent. Now install it on the phone by tapping the received file."))
                QMessageBox.information(self, tr("Send over Bluetooth"), tr("Sent.") + "\n\n" + steps)

        self.run_job(job, done)


def _older(a, b):
    """Version a older than b ('0.6.0' < '0.7.0')."""
    def parts(v):
        return [int(x) if x.isdigit() else 0 for x in str(v).split(".")]
    return parts(a) < parts(b)
