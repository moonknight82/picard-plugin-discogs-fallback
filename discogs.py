"""Small Discogs API client and conservative release-to-file mapping."""

from __future__ import annotations

import re
from urllib.parse import urlencode

API = "https://api.discogs.com"
USER_AGENT = "PicardDiscogsFallback/0.1 (+https://github.com/moonknight82)"
POSITION = re.compile(r"^(?:(\d+)[-/.])?(\d+)$")


def search_path(artist: str, album: str) -> str:
    if not album.strip():
        raise ValueError("Enter an album title.")
    params = {"type": "release", "release_title": album.strip(), "per_page": 25}
    if artist.strip():
        params["artist"] = artist.strip()
    return "/database/search?" + urlencode(params)


def search_results(payload: dict) -> list[dict]:
    return [item for item in payload.get("results", []) if item.get("type") == "release" and isinstance(item.get("id"), int)]


def release_path(release_id: int) -> str:
    if not isinstance(release_id, int) or release_id <= 0:
        raise ValueError("Invalid Discogs release ID.")
    return "/releases/%d" % release_id


def artist_name(artists: list[dict]) -> str:
    return "".join(str(artist.get("name", "")) + str(artist.get("join", "")) for artist in artists).strip()


def tracks(data: dict) -> list[dict]:
    """Return musical tracks; headings and hidden subtracks are excluded."""
    return [item for item in data.get("tracklist", []) if item.get("type_") == "track" and item.get("title") and item.get("position")]


def track_tags(data: dict, track: dict, ordinal: int, total: int) -> dict[str, str]:
    position = str(track.get("position", ""))
    match = POSITION.fullmatch(position)
    disc = int(match.group(1)) if match and match.group(1) else 1
    number = int(match.group(2)) if match else ordinal
    album_artist = artist_name(data.get("artists", []))
    track_artist = artist_name(track.get("artists", [])) or album_artist
    result = {
        "album": str(data.get("title", "")),
        "albumartist": album_artist,
        "artist": track_artist,
        "title": str(track["title"]),
        "tracknumber": str(number),
        "discnumber": str(disc),
        "discogs_release_id": str(data.get("id", "")),
    }
    if data.get("year"):
        result["date"] = str(data["year"])
    if data.get("labels"):
        result["label"] = str(data["labels"][0].get("name", ""))
    return {key: value for key, value in result.items() if value}


def file_order(files: list) -> list:
    def key(file):
        metadata = file.metadata
        def number(field):
            match = re.match(r"^\d+", str(metadata.get(field, "")))
            return int(match.group()) if match else 0
        natural_name = tuple(int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", str(file.filename)))
        return (number("discnumber"), number("tracknumber"), natural_name)
    return sorted(files, key=key)


def mapping(files: list, data: dict) -> list[tuple[object, dict[str, str]]]:
    listed = tracks(data)
    if len(files) != len(listed):
        raise ValueError("Discogs release has %d tracks; Picard selection has %d files. Choose an exact match." % (len(listed), len(files)))
    return [(file, track_tags(data, track, index, len(listed))) for index, (file, track) in enumerate(zip(file_order(files), listed), 1)]
