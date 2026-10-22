"""Find playable files in a folder and turn file names into readable titles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

AUDIO = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus"}
VIDEO = {".mp4", ".mkv", ".mov", ".webm", ".avi"}


@dataclass(frozen=True)
class Track:
    path: Path
    title: str
    artist: str

    @property
    def label(self) -> str:
        return f"{self.artist} · {self.title}" if self.artist else self.title


def _natural_key(path: Path) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def parse_name(path: Path) -> tuple[str, str]:
    """'Artist - Title (Official Audio).mp3' -> ('Title', 'Artist')."""
    stem = re.sub(r"[_]+", " ", path.stem)
    stem = re.sub(r"\s*[\(\[](official|lyrics?|audio|video|hd|hq)[^\)\]]*[\)\]]", "", stem, flags=re.I)
    stem = re.sub(r"\s+", " ", stem).strip(" -")
    stem = re.sub(r"^\d{1,3}(?:\s*[.\-_)]\s*|\s+)(?=\S)", "", stem)  # leading track number: "01 ", "01. ", "01 - "
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return title.strip(), artist.strip()
    return stem, ""


def scan(folder: Path | str) -> list[Track]:
    folder = Path(folder)
    files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO | VIDEO]
    tracks = []
    for path in sorted(files, key=_natural_key):
        title, artist = parse_name(path)
        tracks.append(Track(path=path, title=title, artist=artist))
    return tracks
