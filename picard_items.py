"""Picard item handling for Discogs fallback application."""

from __future__ import annotations


def files_for(source, source_is_album: bool) -> list:
    return list(source.iterfiles()) if source_is_album else list(source.files)


def detach_album_files(tagger, album, files: list, discogs_title: str, discogs_artist: str):
    """Detach MB-linked files before editing them; preserve a single new cluster."""
    from picard.plugin3.api import Cluster

    if not files or set(files_for(album, True)) != set(files):
        raise ValueError("The release files changed. Search again before applying tags.")
    cluster = Cluster(discogs_title, discogs_artist)
    tagger.clusters.append(cluster)
    tagger.cluster_added.emit(cluster)
    for file in files:
        if not file.move(cluster):
            raise RuntimeError("Could not move %s into the Discogs cluster." % file.filename)
    return cluster


def apply_file_tags(file, tags: dict[str, str]):
    """Clear stale MusicBrainz IDs and stage Discogs tags in Picard."""
    for key in list(file.metadata):
        if key.startswith("musicbrainz_"):
            del file.metadata[key]
    for key, value in tags.items():
        file.metadata[key] = value
    file.update()
