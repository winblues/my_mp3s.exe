"""
config.py — shared paths and library.yml read/write
"""

import os
from pathlib import Path

import yaml

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", "/music"))
LIBRARY_FILE = DATA_DIR / "library.yml"
PROXY_BASE = "http://localhost:6969/stream"


def load_albums() -> list[dict]:
    if not LIBRARY_FILE.exists():
        return []
    data = yaml.safe_load(LIBRARY_FILE.read_text()) or {}
    return data.get("albums") or []


def save_albums(albums: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_FILE.write_text(yaml.dump({"albums": albums}, default_flow_style=False))
