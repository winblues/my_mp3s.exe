"""
webui.py — album management UI (port 6970)
"""

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
import threading
import re
from concurrent.futures import ThreadPoolExecutor

from config import load_albums, save_albums, MUSIC_DIR
from sync import sync_albums
import proxy as _proxy

app = FastAPI(docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory="/app/templates")

# Simple in-process sync state
_sync_lock = threading.Lock()
_sync_running = False
_sync_log: list[str] = []


class Album(BaseModel):
    artist: str
    album: str


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    albums = load_albums()
    synced = _get_synced_albums()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"albums": albums, "synced": synced},
    )


@app.get("/api/albums")
def list_albums():
    return {"albums": load_albums()}


@app.post("/api/albums", status_code=201)
def add_album(album: Album):
    albums = load_albums()
    entry = {"artist": album.artist.strip(), "album": album.album.strip()}
    if entry not in albums:
        albums.append(entry)
        save_albums(albums)
    return {"albums": albums}


@app.delete("/api/albums/{index}")
def remove_album(index: int):
    albums = load_albums()
    if 0 <= index < len(albums):
        albums.pop(index)
        save_albums(albums)
    return {"albums": albums}


@app.post("/api/sync")
def trigger_sync(background_tasks: BackgroundTasks):
    global _sync_running, _sync_log
    with _sync_lock:
        if _sync_running:
            return {"status": "already running"}
        _sync_running = True
        _sync_log = []
    background_tasks.add_task(_run_sync)
    return {"status": "started"}


@app.get("/api/sync/status")
def sync_status():
    with _sync_lock:
        return {"running": _sync_running, "log": list(_sync_log)}


@app.get("/api/sync/stream")
def sync_stream():
    """SSE endpoint — streams log lines as sync runs."""
    def generate():
        sent = 0
        while True:
            with _sync_lock:
                lines = _sync_log[sent:]
                running = _sync_running
            for line in lines:
                yield f"data: {line}\n\n"
                sent += 1
            if not running and sent >= len(_sync_log):
                break
            import time
            time.sleep(0.2)
        yield "data: [done]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _run_sync():
    global _sync_running
    albums = load_albums()
    for line in sync_albums(albums):
        with _sync_lock:
            _sync_log.append(line.rstrip())
    _prefetch_cache()
    with _sync_lock:
        _sync_running = False


def _prefetch_cache():
    """Pre-warm the proxy cache for every video ID found in synced .m3u files."""
    if not MUSIC_DIR.exists():
        return
    video_ids: list[str] = []
    # Match proxy URLs: http://host:port/stream/<video_id>/...
    _url_re = re.compile(r"/stream/([A-Za-z0-9_-]{11})")
    for m3u in MUSIC_DIR.rglob("*.m3u"):
        try:
            text = m3u.read_text(errors="replace")
        except OSError:
            continue
        for match in _url_re.finditer(text):
            vid = match.group(1)
            if vid not in video_ids:
                video_ids.append(vid)

    if not video_ids:
        return

    with _sync_lock:
        _sync_log.append(f"[prefetch] warming cache for {len(video_ids)} track(s)…")

    def _warm(vid: str):
        _proxy._resolve(vid)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(_warm, video_ids))

    with _sync_lock:
        _sync_log.append("[prefetch] done")


def _get_synced_albums() -> set[str]:
    """Return set of 'Artist — Album' strings that have an .m3u in MUSIC_DIR."""
    synced = set()
    if not MUSIC_DIR.exists():
        return synced
    for m3u in MUSIC_DIR.glob("*.m3u"):
        # Filename is "Artist - Album.m3u"; split on first " - "
        stem = m3u.stem
        if " - " in stem:
            artist, album = stem.split(" - ", 1)
            synced.add(f"{artist} — {album}")
    return synced
