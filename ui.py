"""Search and preview Discogs releases from a Picard cluster or release."""

from __future__ import annotations

from html import escape

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .discogs import mapping
from .network import DiscogsClient
from .picard_items import apply_file_tags, detach_album_files, files_for


class DiscogsDialog(QDialog):
    def __init__(self, source, parent=None, *, api=None, tagger=None, source_is_album=False):
        super().__init__(parent)
        self.source = source
        self.api = api
        self.client = DiscogsClient(api) if api else None
        self.tagger = tagger
        self.source_is_album = source_is_album
        self.results = []
        self.selected_release = None
        self.proposed = []
        self.pending = None
        self.busy = False
        self.setWindowTitle("Discogs Fallback")
        self.resize(900, 680)
        layout = QVBoxLayout(self)
        context = "release" if source_is_album else "cluster"
        layout.addWidget(QLabel("Search Discogs for this %s. Review the exact release and file order before applying tags." % context))

        form = QFormLayout()
        layout.addWidget(QLabel("Set your API token in Options → Plugins → Discogs Fallback."))
        metadata = source.metadata
        self.artist = QLineEdit(str(metadata.get("albumartist") or metadata.get("artist") or ""))
        self.album = QLineEdit(str(metadata.get("album") or ""))
        form.addRow("Artist", self.artist)
        form.addRow("Album", self.album)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.search_button = QPushButton("Search Discogs")
        self.search_button.clicked.connect(self.start_search)
        self.open_button = QPushButton("Open release on Discogs")
        self.open_button.clicked.connect(self.open_release)
        self.open_button.setEnabled(False)
        actions.addWidget(self.search_button)
        actions.addWidget(self.open_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Release", "Year", "Format", "Country"])
        self.table.setColumnWidth(0, 520)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 160)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.select_result)
        layout.addWidget(self.table, 2)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a release to see the track-to-file mapping.")
        layout.addWidget(self.preview, 3)
        self.status = QLabel("Data provided by Discogs. Select a result to open its source page.")
        self.status.setOpenExternalLinks(True)
        layout.addWidget(self.status)
        footer = QHBoxLayout()
        self.apply_button = QPushButton("Apply tags in Picard")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_tags)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        footer.addStretch()
        footer.addWidget(self.apply_button)
        footer.addWidget(close_button)
        layout.addLayout(footer)

    def _start(self, request, args, callback):
        if self.busy:
            return
        if not self.client:
            self.show_error("Discogs network service is unavailable.")
            return
        self.busy = True
        self.search_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.table.setEnabled(False)

        def finished():
            self.pending = None
            self.busy = False
            self.search_button.setEnabled(True)
            self.table.setEnabled(True)

        def succeeded(data):
            finished()
            callback(data)

        def failed(message):
            finished()
            self.show_error(message)

        self.pending = request(*args, succeeded, failed)

    def start_search(self):
        self.results = []
        self.selected_release = None
        self.proposed = []
        self.table.setRowCount(0)
        self.preview.clear()
        self.open_button.setEnabled(False)
        self.status.setText("Searching Discogs…")
        self._start(self.client.search if self.client else None, (self.artist.text(), self.album.text()), self.show_results)

    def show_results(self, results):
        self.results = results
        self.table.setRowCount(len(results))
        for row, item in enumerate(results):
            values = (item.get("title", ""), item.get("year", ""), ", ".join(item.get("format", [])), item.get("country", ""))
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.status.setText("%d releases found. Data provided by Discogs." % len(results))

    def select_result(self):
        rows = self.table.selectionModel().selectedRows()
        self.selected_release = None
        self.proposed = []
        self.apply_button.setEnabled(False)
        if not rows:
            return
        item = self.results[rows[0].row()]
        self.open_button.setEnabled(bool(item.get("uri")))
        self.preview.setPlainText("Loading release details…")
        self._start(self.client.release if self.client else None, (item["id"],), self.show_release)

    def show_release(self, data):
        self.selected_release = data
        source = data.get("uri", "")
        lines = ["%s — %s" % (data.get("artists_sort", ""), data.get("title", "")),
                 "Data provided by Discogs: %s" % source, ""]
        try:
            self.proposed = mapping(files_for(self.source, self.source_is_album), data)
        except ValueError as exc:
            lines.append(str(exc))
            lines.append("This release can be viewed but cannot be applied to the selected files.")
        else:
            for file, tags in self.proposed:
                lines.append("%s  →  %s. %s — %s" % (file.filename, tags["tracknumber"], tags["title"], tags["artist"]))
            lines.append("\nMusicBrainz IDs will be cleared from these files. Save manually after review.")
            if self.source_is_album:
                lines.append("The files will move from this MusicBrainz release to a new Discogs cluster before tags are applied.")
            self.apply_button.setEnabled(True)
        self.preview.setPlainText("\n".join(lines))
        if source.startswith("https://www.discogs.com/"):
            safe_source = escape(source, quote=True)
            self.status.setText('Data provided by Discogs: <a href="%s">%s</a>' % (safe_source, escape(source)))
        else:
            self.status.setText("Data provided by Discogs.")

    def open_release(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            url = self.results[rows[0].row()].get("uri", "")
            if url.startswith("https://www.discogs.com/"):
                QDesktopServices.openUrl(QUrl(url))

    def apply_tags(self):
        if not self.proposed or not self.selected_release:
            return
        current_files = files_for(self.source, self.source_is_album)
        if set(current_files) != {file for file, _ in self.proposed}:
            QMessageBox.warning(self, "Selection changed", "The files changed. Search again before applying tags.")
            self.apply_button.setEnabled(False)
            return
        if self.source_is_album:
            try:
                cluster = detach_album_files(
                    self.tagger, self.source, current_files,
                    self.selected_release.get("title", "Discogs release"),
                    self.selected_release.get("artists_sort", ""),
                )
            except (RuntimeError, ValueError) as exc:
                QMessageBox.warning(self, "Could not detach files", str(exc))
                self.apply_button.setEnabled(False)
                return
        else:
            cluster = self.source
        for file, tags in self.proposed:
            apply_file_tags(file, tags)
        cluster.update()
        self.parent().refresh_metadatabox()
        self.status.setText("Tags applied in Picard. Review and save the files when ready.")
        self.apply_button.setEnabled(False)

    def show_error(self, message):
        self.status.setText(message)
        self.preview.setPlainText(message)

    def closeEvent(self, event):
        if self.pending and self.api:
            self.api.web_service.abort_task(self.pending)
            self.pending = None
        super().closeEvent(event)
