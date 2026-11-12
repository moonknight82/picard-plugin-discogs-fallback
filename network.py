"""Discogs requests through Picard's Qt network service and certificate store."""

from PyQt6.QtNetwork import QNetworkRequest

from .discogs import API, USER_AGENT, release_path, search_path, search_results


class DiscogsClient:
    def __init__(self, api):
        self.api = api

    def _get(self, path, succeeded, failed):
        token = (self.api.plugin_config.get("token", "") or "").strip()
        if not token:
            failed("Set your Discogs API token in Picard Options → Plugins → Discogs Fallback.")
            return None

        def handle(document, reply, error):
            if error:
                code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                if code in (401, 403):
                    failed("Discogs rejected the configured token (HTTP %s)." % code)
                elif code == 429:
                    failed("Discogs rate limit reached. Wait and retry.")
                elif code:
                    failed("Discogs request failed (HTTP %s)." % code)
                else:
                    failed("Discogs network error: %s" % reply.errorString())
                return
            if not isinstance(document, dict):
                failed("Discogs returned an invalid response.")
                return
            succeeded(document)

        return self.api.web_service.get_url(
            url=API + path,
            handler=handle,
            parse_response_type="json",
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": "Discogs token=%s" % token,
            },
            refresh=True,
        )

    def search(self, artist, album, succeeded, failed):
        try:
            path = search_path(artist, album)
        except ValueError as exc:
            failed(str(exc))
            return None
        return self._get(path, lambda document: succeeded(search_results(document)), failed)

    def release(self, release_id, succeeded, failed):
        try:
            path = release_path(release_id)
        except ValueError as exc:
            failed(str(exc))
            return None
        return self._get(path, succeeded, failed)
