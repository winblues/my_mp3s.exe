"""
proxy.py — audio stream proxy (port 6969)
GET /stream/{video_id}[/Artist%20-%20Title] → streams audio from YouTube CDN

Instead of redirecting, we stream the bytes through so we can:
  - set icy-name to the URL-decoded display title, giving Audacious the
    correct "Artist - Title" string without it needing to probe external URLs
  - respond to HEAD requests instantly (headers only, no body download)
    so Audacious populates track durations without freezing on startup

Range requests are forwarded so seeking works normally.
yt-dlp CDN URL resolution is cached in-process for 1 hour.
"""

import asyncio
import subprocess
import time
from contextlib import asynccontextmanager
from threading import Lock
from urllib.parse import unquote

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response, StreamingResponse

CACHE_TTL = 3600
_cache: dict[str, tuple[str, float]] = {}
_lock = Lock()
_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    _http_client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    yield
    await _http_client.aclose()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


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


@app.api_route("/stream/{path:path}", methods=["GET", "HEAD"])
async def stream(path: str, request: Request):
    # path is "video_id" or "video_id/Artist%20-%20Title"
    video_id = path.split("/")[0]
    parts = path.split("/", 1)
    title = unquote(parts[1]) if len(parts) > 1 else video_id

    cdn_url = await asyncio.to_thread(_resolve, video_id)
    if not cdn_url:
        return PlainTextResponse("yt-dlp could not resolve this video", status_code=502)

    upstream_headers = {}
    if range_header := request.headers.get("range"):
        upstream_headers["Range"] = range_header

    upstream = await _http_client.send(
        _http_client.build_request(request.method, cdn_url, headers=upstream_headers),
        stream=True,
    )

    response_headers = {"icy-name": title, "Accept-Ranges": "bytes"}
    for h in ("content-type", "content-length", "content-range"):
        if h in upstream.headers:
            response_headers[h] = upstream.headers[h]

    if request.method == "HEAD":
        await upstream.aclose()
        return Response(headers=response_headers, status_code=upstream.status_code)

    async def generate():
        try:
            async for chunk in upstream.aiter_bytes(65536):
                yield chunk
        finally:
            await upstream.aclose()

    return StreamingResponse(
        generate(),
        status_code=upstream.status_code,
        headers=response_headers,
    )
