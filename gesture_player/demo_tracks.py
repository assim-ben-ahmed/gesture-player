"""Generate a few short, royalty-free demo tracks so the player works out of the box.

`python -m gesture_player.demo_tracks` writes them to media/demo/ (git-ignored, about 3 MB).
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

RATE = 22_050
DEMO_DIR = Path(__file__).resolve().parents[1] / "media" / "demo"
NOTE = {n: 440 * 2 ** ((i - 9) / 12) for i, n in enumerate("C C# D D# E F F# G G# A A# B".split())}

# (file name, beats per minute, chord progression, waveform)
TRACKS = [
    ("01 Demo Band - Morning Loop", 96, [["C", "E", "G"], ["A", "C", "E"], ["F", "A", "C"], ["G", "B", "D"]], "soft"),
    ("02 Demo Band - Night Drive", 112, [["A", "C", "E"], ["F", "A", "C"], ["C", "E", "G"], ["G", "B", "D"]], "pulse"),
    ("03 Demo Band - Slow Waves", 72, [["D", "F", "A"], ["G", "B", "D"], ["C", "E", "G"], ["A", "C", "E"]], "soft"),
]


def _tone(freq: float, seconds: float, kind: str) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    wave_ = np.sin(2 * np.pi * freq * t)
    if kind == "pulse":
        wave_ = 0.6 * wave_ + 0.4 * np.sign(np.sin(2 * np.pi * freq * t)) * 0.3
    envelope = np.minimum(1, t * 20) * np.exp(-t * (1.6 if kind == "pulse" else 0.9))
    return wave_ * envelope


def render(bpm: int, chords: list[list[str]], kind: str, bars: int = 6) -> np.ndarray:
    beat = 60 / bpm
    parts = []
    for bar in range(bars):
        chord = chords[bar % len(chords)]
        for step in range(4):
            note = chord[step % 3]
            arp = _tone(NOTE[note] * (2 if step == 3 else 1), beat, kind)
            pad = sum(_tone(NOTE[n] / 2, beat, "soft") for n in chord) * 0.25
            parts.append(arp * 0.5 + pad)
    audio = np.concatenate(parts)
    return audio / np.max(np.abs(audio)) * 0.8


def write_wav(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes((audio * 32767).astype(np.int16).tobytes())


def ensure_demo_tracks(folder: Path = DEMO_DIR) -> Path:
    for name, bpm, chords, kind in TRACKS:
        path = folder / f"{name}.wav"
        if not path.exists():
            write_wav(path, render(bpm, chords, kind))
    return folder


if __name__ == "__main__":
    print("Demo tracks in", ensure_demo_tracks())
