# AGENTS.md — my_mp3s.exe

## What This Project Is

`my_mp3s.exe` is a YouTube Music → local file browser bridge for
[Blue95](https://github.com/winblues/blue95). It recreates the pre-streaming workflow of
browsing a `~/Music/` folder and dragging an `.m3u` file into Winamp
(here: Audacious with the Chicago95 Winamp skin).

The name is intentionally chaotic.

Everything runs inside a single container. The user installs one Quadlet file,
which mounts their `~/Music` and `~/.local/share/my_mp3s.exe` directories into the
container, and gets:

- **Audio proxy** on `localhost:6969` — `.m3u` files contain stable
  `http://localhost:6969/stream/<video_id>/<Artist---Title>` URLs. On request, `yt-dlp`
  resolves a fresh YouTube CDN audio URL and the proxy returns a `302` redirect.
  Results are cached in-process for 1 hour.

- **Web UI** on `localhost:6970` — a Windows 98-styled (98.css) interface for managing
  the album library, triggering syncs, and watching live sync output.

## Repository Layout

```
Containerfile                     # single image: python:3.12-slim + ffmpeg + yt-dlp + deps
app/
  main.py                         # entry point — runs proxy (6969) and web UI (6970) via asyncio
  proxy.py                        # FastAPI app: GET /stream/{path:path} → 302
  webui.py                        # FastAPI app: album CRUD, sync trigger, SSE log stream
  sync.py                         # YouTube Music search logic, .m3u file generation
  config.py                       # DATA_DIR / MUSIC_DIR env vars, library.yml read/write
  templates/
    index.html                    # 98.css single-page UI
quadlet/
  my_mp3s.container               # Podman Quadlet — drop into ~/.config/containers/systemd/
justfile                          # all dev commands (build, dev, run, install, uninstall)
example-library.yml               # annotated example config
```

## Developer Commands

All commands use `just`. There is no test suite or linter.

| Command | Description |
|---|---|
| `just build` | Build the container image locally |
| `just dev` | Run against a throwaway temp dir — safe to hammer, no real data touched |
| `just dev-rebuild` | `build` + `dev` in one shot |
| `just run` | Run against your real `~/Music` and `~/.local/share/my_mp3s.exe` |
| `just stop` | Stop a running container |
| `just install` | Install the quadlet (pointing at the local image) and start the service |
| `just install-release` | Install the quadlet pointing at the registry image |
| `just uninstall` | Stop and remove the systemd service |

`just dev` uses `--userns=keep-id` so the container user's UID matches the host, allowing writes to the volume-mounted data dir. The temp dir is cleaned up on exit.

The published image is `ghcr.io/winblues/my_mp3s.exe:latest`, built and pushed by CI on
every push to `main`.

## Key Conventions

- **Everything runs inside the container.** There are no host-side scripts. Do not
  create files meant to run outside the container.

- **Two FastAPI apps, one process.** `main.py` runs both with `asyncio.gather` over two
  `uvicorn.Server` instances. Do not split them into separate processes or containers.

- **Ports are 6969 (proxy) and 6970 (web UI) and are hardcoded.** If you change them,
  update `main.py`, `quadlet/my_mp3s.container`, and the `PROXY_BASE` constant in
  `config.py`.

- **The proxy route is `GET /stream/{path:path}`.** The first path segment is the
  `video_id`; anything after it (e.g. a slugified track title) is ignored server-side.
  It exists so Audacious can display a human-readable track name parsed from the URL.
  **Do not add a file extension to the URL** (e.g. `.opus`) — Audacious will try to
  decode the 302 response directly with an extension-specific plugin instead of
  following the redirect.

- **Config and music output are injected via environment variables:**
  - `DATA_DIR` (default `/app/data`) — where `library.yml` lives
  - `MUSIC_DIR` (default `/music`) — where `.m3u` files are written
  - Both are set in the Quadlet file via volume mounts

- **The Quadlet binds both ports to `127.0.0.1` only.** Do not change this to
  `0.0.0.0` in the Quadlet; the container itself binds to `0.0.0.0` internally, which
  is correct.

- **The web UI uses 98.css from unpkg CDN.** The container needs outbound network
  access (it already does for yt-dlp and ytmusicapi). Do not bundle 98.css locally
  unless there is a specific reason.

- **`ytmusicapi` is used unauthenticated** for album search. Do not add OAuth flows
  unless there is a concrete reason.

- **The M3U format is Extended M3U** (`#EXTM3U`, `#EXTINF:duration,Title` per track).
  Audacious does not always honour `#EXTINF` metadata and may fall back to parsing the
  URL for a display title — which is why the title slug is embedded in the proxy URL.

- **Playlists are written flat into the root of `MUSIC_DIR`**, named
  `Artist - Album.m3u`. There is no subdirectory hierarchy.

- **After every sync, the proxy cache is pre-warmed** for all video IDs found in
  `MUSIC_DIR/*.m3u`. This is done in `webui.py:_prefetch_cache()` using a
  `ThreadPoolExecutor(max_workers=4)` calling `proxy._resolve()` directly (same
  process, no HTTP round-trip). CDN URLs expire in ~6 hours; pre-warming at sync time
  covers the immediate listening session.

- **Blue95 is the primary client.** The only change Blue95 needs is
  `audacious-plugins-ffaudio` in its recipe to decode opus/m4a streams. Do not bleed
  other my_mp3s.exe concerns into the Blue95 repo.

## User Workflow (for context)

1. Drop `quadlet/my_mp3s.container` into `~/.config/containers/systemd/`
2. `systemctl --user daemon-reload && systemctl --user start my_mp3s`
3. Open `http://localhost:6970` in a browser
4. Add albums, click "Sync now", watch the log
5. Open Thunar, browse `~/Music/`
6. Drag an `.m3u` to Audacious — music plays
