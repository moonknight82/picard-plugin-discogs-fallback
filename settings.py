"""Discogs token settings page in Picard's Plugins options."""

from PyQt6.QtWidgets import QFormLayout, QLabel, QLineEdit, QVBoxLayout
from picard.plugin3.api import OptionsPage


class DiscogsOptionsPage(OptionsPage):
    NAME = "discogs_fallback"
    TITLE = "Discogs Fallback"
    PARENT = "plugins"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText("Discogs personal access token")
        form.addRow("API token", self.token)
        layout.addLayout(form)
        note = QLabel(
            "Create a personal access token in your Discogs developer settings. "
            "Picard stores this token in its local plugin configuration."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

    def load(self):
        self.token.setText(self.api.plugin_config.get("token", "") or "")

    def save(self):
        self.api.plugin_config["token"] = self.token.text().strip()
