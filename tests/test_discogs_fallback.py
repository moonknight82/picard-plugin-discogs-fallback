"""Discogs fallback behavior without live API requests or music files."""

from types import SimpleNamespace
from pathlib import Path
import os

import pytest

from picard_plugin_discogs_fallback import discogs
from picard_plugin_discogs_fallback.network import DiscogsClient
from picard_plugin_discogs_fallback.picard_items import apply_file_tags, detach_album_files, files_for

_app = None


class ConfigSection:
    """Picard-style section: item access, intentionally no dict.get()."""

    def __init__(self, token):
        self.token = token

    def __getitem__(self, key):
        assert key == "token"
        return self.token

    def __setitem__(self, key, value):
        assert key == "token"
        self.token = value


RELEASE = {
    "id": 42,
    "title": "A Test Album",
    "artists": [{"name": "The Artist", "join": ""}],
    "year": 1997,
    "tracklist": [
        {"type_": "track", "position": "1-1", "title": "First"},
        {"type_": "heading", "position": "", "title": "Disc Two"},
        {"type_": "track", "position": "2-1", "title": "Second"},
    ],
}


def test_mapping_uses_disc_numbers_and_skips_headings():
    second = SimpleNamespace(filename="02.flac", metadata={"discnumber": "2", "tracknumber": "1"})
    first = SimpleNamespace(filename="01.flac", metadata={"discnumber": "1", "tracknumber": "1"})
    mapped = discogs.mapping([second, first], RELEASE)
    assert mapped[0][0] is first
    assert mapped[0][1]["title"] == "First"
    assert mapped[1][1]["discnumber"] == "2"
    assert mapped[1][1]["tracknumber"] == "1"
    assert mapped[1][1]["discogs_release_id"] == "42"


def test_mapping_rejects_mismatched_track_count():
    with pytest.raises(ValueError, match="Discogs release has 2 tracks; Picard selection has 1 files"):
        discogs.mapping([SimpleNamespace(filename="01.flac", metadata={})], RELEASE)


def test_album_files_and_stale_musicbrainz_ids():
    class File:
        metadata = {"musicbrainz_albumid": "old", "genre": "Existing"}
        def update(self):
            self.updated = True

    file = File()
    album = SimpleNamespace(iterfiles=lambda: iter([file]))
    assert files_for(album, True) == [file]
    apply_file_tags(file, {"title": "Discogs title", "discogs_release_id": "42"})
    assert file.metadata == {"genre": "Existing", "title": "Discogs title", "discogs_release_id": "42"}
    assert file.updated


def test_detach_album_files_creates_one_cluster(monkeypatch):
    pytest.importorskip("picard")
    from picard.plugin3 import api as plugin_api

    class Cluster:
        def __init__(self, name, artist):
            self.name, self.artist = name, artist

    class File:
        filename = "one.flac"
        def move(self, target):
            self.target = target
            return True

    class Signal:
        def emit(self, value):
            self.value = value

    file = File()
    album = SimpleNamespace(iterfiles=lambda: iter([file]))
    tagger = SimpleNamespace(clusters=[], cluster_added=Signal())
    monkeypatch.setattr(plugin_api, "Cluster", Cluster)
    cluster = detach_album_files(tagger, album, [file], "Discogs Album", "Artist")
    assert tagger.clusters == [cluster]
    assert tagger.cluster_added.value is cluster
    assert file.target is cluster


def test_search_path_and_results():
    assert "release_title=A+Test+Album" in discogs.search_path("The Artist", "A Test Album")
    assert discogs.search_results({"results": [{"type": "release", "id": 42}, {"type": "master", "id": 43}]}) == [
        {"type": "release", "id": 42}
    ]


def test_network_uses_saved_token_and_picard_service():
    class Service:
        def get_url(self, **kwargs):
            self.request = kwargs
            return "pending"

    service = Service()
    api = SimpleNamespace(plugin_config=ConfigSection("saved-token"), web_service=service)
    received = []
    failed = []
    pending = DiscogsClient(api).search("The Artist", "A Test Album", received.append, failed.append)
    assert pending == "pending"
    assert service.request["url"].startswith("https://api.discogs.com/database/search?")
    assert service.request["headers"]["Authorization"] == "Discogs token=saved-token"
    assert service.request["refresh"] is True
    service.request["handler"]({"results": [{"type": "release", "id": 42}]}, None, None)
    assert received == [[{"type": "release", "id": 42}]]
    assert not failed


def test_network_requires_saved_token():
    class Service:
        def get_url(self, **kwargs):
            raise AssertionError("request should not be sent")

    api = SimpleNamespace(plugin_config=ConfigSection(""), web_service=Service())
    errors = []
    assert DiscogsClient(api).search("Artist", "Album", lambda _: None, errors.append) is None
    assert "Options" in errors[0]


def test_network_reports_tls_error_without_disabling_verification():
    class Service:
        def get_url(self, **kwargs):
            self.request = kwargs
            return "pending"

    class Reply:
        def attribute(self, kind):
            return None
        def errorString(self):
            return "certificate verify failed"

    service = Service()
    api = SimpleNamespace(plugin_config=ConfigSection("saved-token"), web_service=service)
    errors = []
    DiscogsClient(api).release(42, lambda _: None, errors.append)
    service.request["handler"](b"", Reply(), RuntimeError("TLS error"))
    assert errors == ["Discogs network error: certificate verify failed"]


def test_options_page_persists_token(monkeypatch):
    global _app
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("picard")
    from PyQt6.QtWidgets import QApplication
    from picard.ui import options as picard_options
    from picard_plugin_discogs_fallback.settings import DiscogsOptionsPage

    _app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(picard_options, "tagger_instance", lambda: None)
    config = ConfigSection("old-token")
    DiscogsOptionsPage.api = SimpleNamespace(plugin_config=config)
    page = DiscogsOptionsPage()
    page.load()
    assert page.token.text() == "old-token"
    page.token.setText("new-token")
    page.save()
    assert config["token"] == "new-token"
    page.close()


def test_picard_3_load_enable_disable(tmp_path):
    global _app
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("picard")
    from PyQt6.QtWidgets import QApplication
    from picard import config
    from picard.plugin3.plugin import Plugin, PluginState

    _app = QApplication.instance() or QApplication([])
    config.setup_config(_app, str(tmp_path / "picard.ini"))
    directory = Path(__file__).parents[1]
    plugin = Plugin(directory.parent, directory.name)
    plugin.read_manifest()
    plugin.load_module()

    class Tagger:
        window = None

    plugin.enable(Tagger())
    assert plugin.state is PluginState.ENABLED
    plugin.disable()
    assert plugin.state is PluginState.DISABLED


def test_apply_stages_tags_without_saving_files():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QWidget
    from picard_plugin_discogs_fallback.ui import DiscogsDialog

    app = QApplication.instance() or QApplication([])

    class Window(QWidget):
        def refresh_metadatabox(self):
            self.refreshed = True

    class File:
        filename = "01.flac"
        def __init__(self):
            self.metadata = {"genre": "Existing"}
            self.updated = False
        def update(self):
            self.updated = True

    class Cluster:
        metadata = {"album": "Old"}
        def __init__(self, file):
            self.files = [file]
            self.updated = False
        def update(self):
            self.updated = True

    file = File()
    cluster = Cluster(file)
    window = Window()
    dialog = DiscogsDialog(cluster, window)
    dialog.selected_release = {"id": 42}
    dialog.proposed = [(file, {"title": "New", "discogs_release_id": "42"})]
    dialog.apply_tags()
    assert file.metadata == {"genre": "Existing", "title": "New", "discogs_release_id": "42"}
    assert file.updated and cluster.updated and window.refreshed
    dialog.close()


def test_apply_from_right_side_detaches_before_editing(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QWidget
    from picard_plugin_discogs_fallback import ui

    app = QApplication.instance() or QApplication([])

    class Window(QWidget):
        def refresh_metadatabox(self):
            pass

    class File:
        filename = "01.flac"
        def __init__(self):
            self.metadata = {"musicbrainz_albumid": "old"}
        def update(self):
            pass

    file = File()
    album = SimpleNamespace(metadata={"album": "Wrong MB match"}, iterfiles=lambda: iter([file]))
    new_cluster = SimpleNamespace(update=lambda: None)
    detached = []
    def detach(tagger, source, files, title, artist):
        detached.append((source, files, title, artist))
        return new_cluster

    monkeypatch.setattr(ui, "detach_album_files", detach)
    window = Window()
    dialog = ui.DiscogsDialog(album, window, tagger=object(), source_is_album=True)
    dialog.selected_release = {"id": 42, "title": "Right Release", "artists_sort": "Artist"}
    dialog.proposed = [(file, {"title": "Discogs title"})]
    dialog.apply_tags()
    assert detached[0][0] is album
    assert detached[0][1] == [file]
    assert file.metadata == {"title": "Discogs title"}
    dialog.close()
