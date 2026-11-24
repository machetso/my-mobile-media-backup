"""Tab "Clean up": find duplicate files in a folder and move them into a review folder – nothing is
deleted (user request 2026-11-22). The work itself is in dedupe.py."""

import html
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLineEdit,
                               QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import APP_NAME, dedupe, ui
from .i18n import N_, tr, trp
from .gui_flow import WrapLabel, flow_row
from .locations import detect_drives
from .gui_backups import GRAY, GREEN, ORANGE

SHOW_GROUPS = 3000          # more groups are moved too, but not all are listed


def _when(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


class CleanupTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.result = None
        self.last_review = None
        from . import gui                # gui imports this module: look it up when used
        g = gui._group
        lay = QVBoxLayout(self)
        intro = WrapLabel(tr(
            "Finds files that are in the chosen folder (and its subfolders) more than once – identical "
            "content, checked with SHA-256. One copy of each stays; the others are MOVED into a review "
            "folder “Duplicates <date>” on the same drive, nothing is deleted. Look at the review "
            "folder afterwards and delete it yourself – or put everything back."))
        intro.setStyleSheet(f"color:{GRAY}")
        lay.addWidget(intro)

        row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText(tr("a backup folder, a drive or any folder"))
        self.folder.textChanged.connect(self._folder_changed)
        choose = QPushButton(tr("Choose folder…"))
        choose.clicked.connect(self._choose)
        row.addWidget(self.folder, 1)
        row.addWidget(choose)
        lay.addWidget(g(tr("Folder to check"), row))

        res = QVBoxLayout()
        self.summary = WrapLabel(tr("Not checked yet – choose a folder and click “Check for duplicates”."))
        self.summary.setTextFormat(Qt.RichText)
        res.addWidget(self.summary)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("File"), tr("What happens"), tr("Size"), tr("Changed")])
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.tree.setMinimumHeight(220)
        self.tree.setTextElideMode(Qt.ElideMiddle)     # the start and the file name stay visible
        self.tree.itemDoubleClicked.connect(self._make_keep)
        res.addWidget(self.tree, 1)
        hint = WrapLabel(tr("The copy that stays is chosen by rules: the one in the backup's list, then the "
                            "one in the real backup folder (not in a structure built inside it), then the "
                            "one in the year/month folders, then the shorter path, then the older file. "
                            "Double-click another copy to keep that one instead."))
        hint.setStyleSheet(f"color:{GRAY}")
        res.addWidget(hint)
        self.move_btn = QPushButton(tr("Move duplicates to the review folder…"))
        self.move_btn.clicked.connect(self._move)
        self.put_back_btn = QPushButton(tr("Put back…"))
        self.put_back_btn.setToolTip(tr("Moves the files of a review folder back to where they were and "
                                        "undoes the changes in the backup lists."))
        self.put_back_btn.clicked.connect(self._put_back)
        self.open_btn = QPushButton(tr("Open review folder"))
        self.open_btn.clicked.connect(self._open_review)
        res.addWidget(flow_row(self.move_btn, self.put_back_btn, self.open_btn))
        lay.addWidget(g(tr("Duplicates"), res), 1)

        same = QVBoxLayout()
        lab = WrapLabel(tr("Same file name, but different content – different photos or videos. They are "
                           "only listed, never moved."))
        lab.setStyleSheet(f"color:{GRAY}")
        same.addWidget(lab)
        self.same_tree = QTreeWidget()
        self.same_tree.setHeaderLabels([tr("File"), tr("Size"), tr("Changed")])
        h = self.same_tree.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.same_tree.setMinimumHeight(120)
        self.same_tree.setTextElideMode(Qt.ElideMiddle)
        same.addWidget(self.same_tree)
        lay.addWidget(g(tr("Same name, other content"), same))

        self.check_btn = gui._big_button(tr("Check for duplicates"))
        self.check_btn.clicked.connect(self._check)
        self._update_buttons()

    def show_result(self, res):
        """Show a search made before ("Prepare folders" → "Look at them first…", user 2026-11-23:
        the page opened empty) – without searching again."""
        self.folder.blockSignals(True)            # a new folder text would clear the result
        self.folder.setText(str(res.root))
        self.folder.blockSignals(False)
        self.result = res
        self._fill()

    # ------------------------------------------------------------------ helpers
    def _folder_changed(self, _t=None):
        self.result = None
        self.tree.clear()
        self.same_tree.clear()
        self.summary.setText(html.escape(tr("Not checked yet – choose a folder and click “Check for duplicates”.")))
        self._update_buttons()

    def _update_buttons(self):
        root = self.folder.text().strip()
        self.move_btn.setEnabled(bool(self.result and self.result.groups))
        self.open_btn.setEnabled(bool(self.last_review and os.path.isdir(self.last_review)))
        self.put_back_btn.setEnabled(bool(root) and os.path.isdir(root))

    def _choose(self):
        drives = detect_drives()
        start = self.folder.text().strip() or (drives[0][0] if drives else str(Path.home()))
        p = QFileDialog.getExistingDirectory(self, tr("Choose the folder to check for duplicates"), start)
        if p:
            self.folder.setText(str(Path(p)))

    # ------------------------------------------------------------------ check
    def _check(self):
        root = self.folder.text().strip()
        if not root or not os.path.isdir(root):
            QMessageBox.information(self, APP_NAME, tr("Choose an existing folder first."))
            return
        if self.win.busy:
            return
        cancel = self.win.cancel_event
        ui.title(tr("Duplicate check – %s", root))
        state = {"p": None}

        def progress(files, files_total, done, total, path):
            if state["p"] is None:
                state["p"] = ui.Progress(files_total, total)
            p = state["p"]
            p.update(files_done=files, add_bytes=done - p.bytes, current=os.path.basename(path),
                     force=files >= files_total)

        def job():
            ui.info(tr("Reading the folders …"))
            return dedupe.scan(root, cancel=cancel, progress=progress)

        def done(res):
            self.result = res
            self._fill()
            if res.cancelled:
                ui.warn(tr("Duplicate check cancelled – the list is not complete."))
            ui.info(self._summary_text(plain=True))
        self.win.run_job(job, done, awake=N_("Duplicate check"))

    def _summary_text(self, plain=False):
        r = self.result
        text = tr("%d files checked (%s).", r.files, ui.human_size(r.bytes))
        if getattr(r, "known", 0):
            text += " " + tr("%d of them have the same size as another file: %d SHA-256 taken from the backup "
                             "lists and reports, %d read (beginning and end).", r.known + r.hashed, r.known, r.hashed)
        else:
            text += " " + tr("%d of them were read for the comparison (same size as another file).", r.hashed)
        if r.groups:
            dup = trp("%d duplicate (%s) in %d group – it can be moved into the review folder.",
                      "%d duplicates (%s) in %d groups – they can be moved into the review folder.",
                      r.duplicates, r.duplicates, ui.human_size(r.duplicate_bytes), len(r.groups))
        else:
            dup = tr("No duplicates found.")
        if plain:
            return text + " " + dup
        color = ORANGE if r.groups else GREEN
        extra = ""
        if len(r.groups) > SHOW_GROUPS:
            extra = "<br>" + html.escape(tr("The list shows the %d biggest groups; all of them are moved.", SHOW_GROUPS))
        if r.errors:
            extra += "<br><span style='color:%s'>%s</span>" % (ORANGE, html.escape(
                tr("%d files could not be read (see the log).", len(r.errors))))
        if r.cancelled:
            extra += "<br><span style='color:%s'>%s</span>" % (ORANGE, html.escape(
                tr("Cancelled – the list is not complete.")))
        return html.escape(text) + f"<br><b style='color:{color}'>" + html.escape(dup) + "</b>" + extra

    def _fill(self):
        r = self.result
        self.tree.clear()
        self.same_tree.clear()
        self.summary.setText(self._summary_text())
        root = r.root
        for gi, g in enumerate(r.groups[:SHOW_GROUPS]):
            # the folder all copies share is in the group line, each copy shows only what differs
            common = os.path.commonpath([os.path.dirname(e.path) for e in g.entries])
            shared = os.path.relpath(common, root)
            title = trp("%d identical files", "%d identical files", len(g.entries), len(g.entries))
            if shared != ".":
                title += "  –  " + tr("in %s", shared)
            top = QTreeWidgetItem([title, "", ui.human_size(g.size), ""])
            top.setToolTip(0, ("SHA-256 " + g.sha) if g.sha else
                           tr("Same size and same beginning and end – checked completely (SHA-256) right "
                              "before it is moved."))
            top.setFlags(Qt.ItemIsEnabled)
            f = QFont(top.font(0))
            f.setBold(True)
            top.setFont(0, f)
            for ei, e in enumerate(g.entries):
                ch = QTreeWidgetItem([os.path.relpath(e.path, common), "", ui.human_size(e.size), _when(e.mtime)])
                ch.setData(0, Qt.UserRole, (gi, ei))
                ch.setToolTip(0, e.path)
                top.addChild(ch)
            self._mark(top, g)
            self.tree.addTopLevelItem(top)
            if gi < 30:
                top.setExpanded(True)
        for name, lst in r.same_name[:SHOW_GROUPS]:
            top = QTreeWidgetItem([trp("%s – %d files", "%s – %d files", len(lst), name, len(lst)), "", ""])
            top.setFlags(Qt.ItemIsEnabled)
            for e in lst:
                ch = QTreeWidgetItem([os.path.relpath(e.path, root), ui.human_size(e.size), _when(e.mtime)])
                ch.setToolTip(0, e.path)
                top.addChild(ch)
            self.same_tree.addTopLevelItem(top)
        if not r.same_name:
            it = QTreeWidgetItem([tr("None found."), "", ""])
            it.setFlags(Qt.NoItemFlags)
            self.same_tree.addTopLevelItem(it)
        self._update_buttons()

    def _mark(self, top, g):
        for i in range(top.childCount()):
            ch = top.child(i)
            keep = i == g.keep
            e = g.entries[i]
            why = tr("stays") + (" " + tr("(in the backup's list)") if e.indexed else "")
            ch.setText(1, why if keep else tr("moves to the review folder"))
            ch.setForeground(1, QColor(GREEN if keep else ORANGE))
            f = QFont(ch.font(0))
            f.setBold(keep)
            ch.setFont(0, f)

    def _make_keep(self, item, _col=0):
        data = item.data(0, Qt.UserRole)
        if not data or self.result is None:
            return
        gi, ei = data
        g = self.result.groups[gi]
        g.keep = ei
        self._mark(item.parent(), g)

    # ------------------------------------------------------------------ move / put back
    def _move(self):
        r = self.result
        if not r or not r.groups or self.win.busy:
            return
        base = dedupe.review_base(r.root)
        if QMessageBox.question(self, tr("Move duplicates"), tr(
                "Move %d duplicates (%s) into a new review folder in\n%s ?\n\nRight before each move the "
                "file and the copy that stays are read again (SHA-256) – only true copies are moved. "
                "Nothing is deleted. A report and “Put back” are in the review folder.",
                r.duplicates, ui.human_size(r.duplicate_bytes), str(base))) != QMessageBox.Yes:
            return
        cancel = self.win.cancel_event
        ui.title(tr("Move duplicates – %s", r.root))
        state = {"p": None}

        def progress(files, files_total, done, total, path):
            if state["p"] is None:
                state["p"] = ui.Progress(files_total, total)
            p = state["p"]
            p.update(files_done=files, add_bytes=done - p.bytes, current=os.path.basename(path),
                     force=files >= files_total)

        def job():
            return dedupe.move(r, cancel=cancel, progress=progress)

        def done(mv):
            self.last_review = mv.review_dir
            self.result = None
            self.tree.clear()
            text = tr("%d files (%s) moved into the review folder:\n%s",
                      mv.moved, ui.human_size(mv.bytes), mv.review_dir)
            if mv.skipped:
                text += "\n\n" + trp("%d file was not moved (see the report):",
                                     "%d files were not moved (see the report):", len(mv.skipped), len(mv.skipped))
                text += "\n" + "\n".join(f"{p}: {tr(why)}" for p, why in mv.skipped[:8])
            if mv.cancelled:
                text += "\n\n" + tr("Cancelled – the rest stays where it is.")
            text += "\n\n" + tr("Check the review folder; delete it when you are sure – or use “Put back”.")
            ui.info(text.replace("\n\n", " "))
            self.summary.setText(html.escape(text).replace("\n", "<br>"))
            self._update_buttons()
            (QMessageBox.information if not mv.skipped else QMessageBox.warning)(
                self, tr("Move duplicates"), text)
        self.win.run_job(job, done, awake=N_("Move duplicates"))

    def _put_back(self):
        root = self.folder.text().strip()
        if self.win.busy or not root:
            return
        found = dedupe.review_dirs(dedupe.review_base(root))
        start = str(found[0]) if found else str(dedupe.review_base(root))
        p = QFileDialog.getExistingDirectory(self, tr("Choose the review folder to put back"), start)
        if not p:
            return
        if not dedupe.is_review_dir(p):
            QMessageBox.warning(self, tr("Put back"), tr("This is not a review folder of this program."))
            return
        if QMessageBox.question(self, tr("Put back"), tr(
                "Move the files of\n%s\nback to where they were? A file whose place is taken now stays "
                "in the review folder.", p)) != QMessageBox.Yes:
            return

        from . import nestmerge
        if (Path(p) / nestmerge.MANIFEST).is_file():      # the review folder of a merge (2026-11-23)
            def mjob():
                return nestmerge.undo(p)

            def mdone(res):
                back, skipped = res
                text = tr("%d files put back – the backup inside the backup is as it was.", back)
                if skipped:
                    text += "\n\n" + tr("Not put back (the place is taken):") + "\n" + "\n".join(skipped[:8])
                (QMessageBox.information if not skipped else QMessageBox.warning)(self, tr("Put back"), text)
                self._folder_changed()
            self.win.run_job(mjob, mdone, awake=N_("Put back"))
            return

        def job():
            return dedupe.put_back(p)

        def done(pb):
            text = tr("%d files put back.", pb.restored)
            if pb.skipped:
                text += "\n\n" + tr("Not put back:") + "\n" + "\n".join(f"{x}: {tr(why)}" for x, why in pb.skipped[:8])
            ui.info(text.replace("\n", " "))
            (QMessageBox.information if not pb.skipped else QMessageBox.warning)(self, tr("Put back"), text)
            self._folder_changed()
        self.win.run_job(job, done, awake=N_("Put back"))

    def _open_review(self):
        if self.last_review and os.path.isdir(self.last_review):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_review))
