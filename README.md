# Discogs Fallback for MusicBrainz Picard 3

This separate plugin adds **Search Discogs…** to the context menu of a Picard cluster **and a release on the right side**. Use it when MusicBrainz has no suitable release. It leaves the Library Repair plugin independent.

## Install

In **Picard 3 → Options → Plugins → Install Plugin… → URL**, enter this repository URL:

```text
https://github.com/moonknight82/picard-plugin-discogs-fallback
```

Install and enable **Discogs Fallback**.

For a local install, follow these steps:

Extract `Discogs-Fallback-Picard-3.zip` to a permanent location. In Picard 3, choose **Options → Plugins → Install Plugin… → Local** and select the extracted `picard_plugin_discogs_fallback` folder (the one containing `MANIFEST.toml`). Install and enable **Discogs Fallback**. Keep that folder in place because Picard loads the local plugin from it.

## Use

1. Get a personal access token from [Discogs Developer settings](https://www.discogs.com/settings/developers). The token stays in the search window and is cleared when it closes.
2. Load files into Picard, then right-click either their cluster on the left or their release on the right and choose **Discogs Fallback → Search Discogs…**.
3. Search by artist and album. Select a specific release, inspect its source page and the file-to-track preview, then choose **Apply tags in Picard**. The Discogs release must have the same number of listed tracks as the selected Picard item has files.
4. Review the resulting tags in Picard and save the files yourself. The plugin does not fetch images or change audio files during search.

When applying from a release on the right, the plugin moves its files into a new cluster on the left before changing tags. This detaches them from the MusicBrainz release so Picard does not restore the MusicBrainz metadata. The plugin clears existing `musicbrainz_*` identifier tags, then updates album, album artist, artist, title, track number, disc number, release year, label, and a custom `discogs_release_id` tag when available. It preserves other tags. File mapping uses existing disc and track numbers, then filename order. Check the preview carefully for releases with nonstandard track positions or gaps.

This application uses Discogs’ API but is not affiliated with, sponsored or endorsed by Discogs. ‘Discogs’ is a trademark of Zink Media, LLC. Data provided by Discogs is linked to each release in the plugin window.

Licensed under GPL-2.0-or-later. See `COPYING.txt`.
