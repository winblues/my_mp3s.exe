"""
proxy.py — audio stream proxy (port 6969)
GET /stream/{video_id}[/any-title.ext] → yt-dlp resolve → 302 to YouTube CDN audio URL
The optional title suffix is ignored server-side; it exists so Audacious can parse
a human-readable track name from the URL when #EXTINF metadata is not honoured.
Results cached in-process for 1 hour so replaying a track doesn't re-invoke yt-dlp.
"""

import subprocess
import time
from threading import Lock

from fastapi import FastAPI
from fastapi.responses import RedirectResponse, PlainTextResponse

app = FastAPI(docs_url=None, redoc_url=None)

CACHE_TTL = 3600
_cache: dict[str, tuple[str, float]] = {}
_lock = Lock()


def _resolve(video_id: str) -> str | None:
    now = time.time()
    with _lock:
        if video_id in _cache:
            url, ts = _cache[video_id]
            if now - ts < CACHE_TTL:
                return url

    yt_url = f"https://youtube.com/watch?v={video_id}"
    try:
        result = subprocess.run(
            ["yt-dlp", "-f", "bestaudio", "-g", "--no-playlist", yt_url],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            url = result.stdout.strip().splitlines()[0]
            with _lock:
                _cache[video_id] = (url, now)
            return url
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


@app.get("/stream/{path:path}")
def stream(path: str):
    # path is "video_id" or "video_id/Artist - Title.opus" — only the first segment matters
    video_id = path.split("/")[0]
    url = _resolve(video_id)
    if url:
        return RedirectResponse(url, status_code=302)
    return PlainTextResponse("yt-dlp could not resolve this video", status_code=502)
