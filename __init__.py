"""Manual Discogs fallback for MusicBrainz Picard 3."""

_dialogs = []


def enable(api):
    from picard.plugin3.api import BaseAction, Album
    from .settings import DiscogsOptionsPage
    from .ui import DiscogsDialog

    api.plugin_config.register_option("token", "")
    api.register_options_page(DiscogsOptionsPage)

    class SearchDiscogs(BaseAction):
        TITLE = "Search Discogs…"
        MENU = ("Discogs Fallback",)

        def callback(self, objs):
            if len(objs) != 1:
                return
            source = objs[0]
            dialog = DiscogsDialog(source, self.api.tagger.window, api=self.api, tagger=self.api.tagger, source_is_album=isinstance(source, Album))
            _dialogs.append(dialog)
            dialog.finished.connect(lambda: _dialogs.remove(dialog) if dialog in _dialogs else None)
            dialog.show()

    api.register_cluster_action(SearchDiscogs)
    api.register_album_action(SearchDiscogs)


def disable():
    for dialog in list(_dialogs):
        dialog.close()
