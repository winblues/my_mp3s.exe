# my_mp3s.exe

A local [yt-dlp](https://github.com/yt-dlp/yt-dlp) HTTP proxy that populates `~/Music` with full album playlists. Like the pre-streaming
 days, but above board this time.

<img width="1920" height="1080" alt="Screenshot_2026-04-28_10-30-41" src="https://github.com/user-attachments/assets/28fe4bd3-fa5b-4b40-875c-459091d222f6" />

## Install

Preferred method is via quadlet:

```
[Unit]
Description=my_mp3s.exe — YouTube Music library + audio proxy
After=network-online.target
Wants=network-online.target

[Container]
Image=ghcr.io/winblues/my_mp3s.exe:latest
PublishPort=127.0.0.1:6969:6969
PublishPort=127.0.0.1:6970:6970
Volume=%h/.local/share/my_mp3s.exe:/app/data:Z
Volume=%h/Music:/music:z
Environment=DATA_DIR=/app/data
Environment=MUSIC_DIR=/music
UserNS=keep-id
AutoUpdate=registry

[Service]
ExecStartPre=mkdir -p %h/.local/share/my_mp3s.exe
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Save it as `~/.config/containers/systemd/my_mp3s.container` and start it with `systemctl`:

```bash
systemctl --user daemon-reload
systemctl --user start my_mp3s
```
