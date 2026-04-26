IMAGE := "localhost/my_mp3s.exe"
REGISTRY_IMAGE := "ghcr.io/winblues/my_mp3s.exe"

DATA_DIR := `echo $HOME/.local/share/my_mp3s.exe`
MUSIC_DIR := `echo $HOME/Music`

# List available recipes
default:
    @just --list

# Build the container image locally
build:
    podman build -t {{IMAGE}} .

# Run against your real data dirs (same as the quadlet, but foreground)
run: _ensure-dirs
    podman run --rm \
        --userns=keep-id \
        -p 127.0.0.1:6969:6969 \
        -p 127.0.0.1:6970:6970 \
        -v {{DATA_DIR}}:/app/data:Z \
        -v {{MUSIC_DIR}}:/music:z \
        -e DATA_DIR=/app/data \
        -e MUSIC_DIR=/music \
        --name my_mp3s \
        {{IMAGE}}

# Run against throwaway temp dirs — safe to hammer without touching real data
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    TMPDIR=$(mktemp -d /tmp/my_mp3s_dev.XXXXXX)
    mkdir -p "$TMPDIR/data" "$TMPDIR/music"
    echo "dev dirs: $TMPDIR"
    trap "podman stop my_mp3s_dev 2>/dev/null; rm -rf $TMPDIR" EXIT
    podman run --rm \
        --userns=keep-id \
        -p 127.0.0.1:6969:6969 \
        -p 127.0.0.1:6970:6970 \
        -v "$TMPDIR/data":/app/data:Z \
        -v "$TMPDIR/music":/music:Z \
        -e DATA_DIR=/app/data \
        -e MUSIC_DIR=/music \
        --name my_mp3s_dev \
        {{IMAGE}}

# Rebuild and restart the dev container in one shot
dev-rebuild: build dev

# Print logs from the running container (use after `just run` in another terminal)
logs:
    podman logs -f my_mp3s

# Stop a running container
stop:
    podman stop my_mp3s 2>/dev/null || podman stop my_mp3s_dev 2>/dev/null || true

# Install the quadlet and start the systemd user service
install:
    mkdir -p ~/.config/containers/systemd
    cp quadlet/my_mp3s.container ~/.config/containers/systemd/
    sed -i 's|ghcr.io/winblues/my_mp3s.exe:latest|{{IMAGE}}|' \
        ~/.config/containers/systemd/my_mp3s.container
    systemctl --user daemon-reload
    systemctl --user start my_mp3s
    @echo "service started — web UI at http://localhost:6970"

# Install quadlet pointing at the registry image (for normal use, not dev)
install-release:
    mkdir -p ~/.config/containers/systemd
    cp quadlet/my_mp3s.container ~/.config/containers/systemd/
    systemctl --user daemon-reload
    systemctl --user start my_mp3s
    @echo "service started — web UI at http://localhost:6970"

# Uninstall the systemd service and quadlet
uninstall:
    systemctl --user stop my_mp3s 2>/dev/null || true
    systemctl --user disable my_mp3s 2>/dev/null || true
    rm -f ~/.config/containers/systemd/my_mp3s.container
    systemctl --user daemon-reload

_ensure-dirs:
    mkdir -p {{DATA_DIR}} {{MUSIC_DIR}}
