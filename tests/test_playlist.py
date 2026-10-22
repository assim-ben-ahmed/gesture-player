from pathlib import Path

import numpy as np
import pytest

from gesture_player.demo_tracks import render, write_wav
from gesture_player.playlist import parse_name, scan


@pytest.mark.parametrize("name, expected", [
    ("Adele - Hello.mp3", ("Hello", "Adele")),
    ("01 Demo Band - Morning Loop.wav", ("Morning Loop", "Demo Band")),
    ("03. Artist - Song (Official Video).mp4", ("Song", "Artist")),
    ("my_voice_memo.m4a", ("my voice memo", "")),
])
def test_parse_name(name, expected):
    assert parse_name(Path(name)) == expected


def test_scan_finds_media_in_natural_order(tmp_path):
    for name in ["track 10.mp3", "track 2.mp3", "notes.txt", "clip.MP4", "sub/track 1.flac"]:
        f = tmp_path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
    names = [t.path.name for t in scan(tmp_path)]
    assert "notes.txt" not in names
    assert names.index("track 2.mp3") < names.index("track 10.mp3")
    assert len(names) == 4


def test_demo_track_is_a_valid_wav(tmp_path):
    audio = render(120, [["C", "E", "G"]], "soft", bars=1)
    assert np.max(np.abs(audio)) <= 0.81
    write_wav(tmp_path / "t.wav", audio)
    assert (tmp_path / "t.wav").stat().st_size > 40_000
