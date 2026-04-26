"""
sync.py — YouTube Music search → ~/Music .m3u tree
Called from the web UI; yields log lines so the UI can stream progress.
"""

import re
from pathlib import Path
from typing import Generator

from ytmusicapi import YTMusic

from config import MUSIC_DIR, PROXY_BASE


def _slugify(name: str) -> str:
    name = name.replace("/", "-").replace("\\", "-")
    name = re.sub(r'[<>:"|?*]', "", name)
    name = name.replace(" ", "-")
    return name.strip()


def _find_album(api: YTMusic, artist: str, album: str) -> dict | None:
    results = api.search(f"{artist} {album}", filter="albums", limit=5)
    if not results:
        return None
    al = album.lower()
    ar = artist.lower()
    for r in results:
        if al in r.get("title", "").lower() and any(
            ar in a.get("name", "").lower() for a in r.get("artists", [])
        ):
            return r
    return results[0]


def sync_albums(albums: list[dict]) -> Generator[str, None, None]:
    """Yield human-readable log lines while syncing. Designed for SSE streaming."""
    if not albums:
        yield "nothing to sync — add some albums first\n"
        return

    yield f"syncing {len(albums)} album(s) to {MUSIC_DIR}\n"
    api = YTMusic()
    ok = 0

    for entry in albums:
        artist = entry.get("artist", "").strip()
        album = entry.get("album", "").strip()
        if not artist or not album:
            yield f"[skip] malformed entry: {entry}\n"
            continue

        yield f"[search] {artist} — {album}\n"
        result = _find_album(api, artist, album)
        if not result:
            yield f"[miss]  {artist} — {album}: not found on YouTube Music\n"
            continue

        browse_id = result.get("browseId")
        if not browse_id:
            yield f"[miss]  {artist} — {album}: no browseId\n"
            continue

        details = api.get_album(browse_id)
        tracks = details.get("tracks", [])
        if not tracks:
            yield f"[miss]  {artist} — {album}: no tracks returned\n"
            continue

        canonical_artist = (details.get("artists") or [{}])[0].get("name", artist)
        canonical_album = details.get("title", album)

        MUSIC_DIR.mkdir(parents=True, exist_ok=True)

        m3u_path = MUSIC_DIR / f"{_slugify(canonical_artist)} - {_slugify(canonical_album)}.m3u"

        lines = ["#EXTM3U"]
        for track in tracks:
            video_id = track.get("videoId")
            if not video_id:
                continue
            title = track.get("title", "Unknown")
            duration = track.get("duration_seconds") or 0
            track_artist = (track.get("artists") or [{}])[0].get("name", canonical_artist)
            lines.append(f"#EXTINF:{duration},{track_artist} - {title}")
            slug = _slugify(f"{track_artist} - {title}")
            lines.append(f"{PROXY_BASE}/{video_id}/{slug}")

        m3u_path.write_text("\n".join(lines) + "\n")
        track_count = len([l for l in lines if not l.startswith("#")])
        yield f"[ok]    {canonical_artist} — {canonical_album} ({track_count} tracks)\n"
        ok += 1

    yield f"\ndone: {ok}/{len(albums)} albums synced\n"
