"""Playlist player on Qt Multimedia (no external media player to install)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from .playlist import Track

RESTART_THRESHOLD_MS = 3000  # "previous" restarts the current track if it has played longer than this


class Player(QObject):
    track_changed = Signal(int)
    playing_changed = Signal(bool)
    volume_changed = Signal(int, bool)   # volume 0-100, muted
    position_changed = Signal(int, int)  # position ms, duration ms

    def __init__(self, tracks: list[Track], volume: int = 60):
        super().__init__()
        if not tracks:
            raise ValueError("The playlist is empty.")
        self.tracks = tracks
        self.index = 0
        self._audio = QAudioOutput()
        self._media = QMediaPlayer()
        self._media.setAudioOutput(self._audio)
        self._media.playbackStateChanged.connect(
            lambda s: self.playing_changed.emit(s == QMediaPlayer.PlaybackState.PlayingState))
        self._media.positionChanged.connect(lambda p: self.position_changed.emit(p, self._media.duration()))
        self._media.mediaStatusChanged.connect(self._on_status)
        self.set_volume(volume)
        self._load(0)

    # ── state ──
    @property
    def current(self) -> Track:
        return self.tracks[self.index]

    @property
    def playing(self) -> bool:
        return self._media.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def volume(self) -> int:
        return round(self._audio.volume() * 100)

    @property
    def muted(self) -> bool:
        return self._audio.isMuted()

    # ── commands ──
    def toggle(self) -> None:
        self._media.pause() if self.playing else self._media.play()

    def next(self) -> None:
        self.play_index((self.index + 1) % len(self.tracks))

    def previous(self) -> None:
        if self._media.position() > RESTART_THRESHOLD_MS:
            self._media.setPosition(0)
        else:
            self.play_index((self.index - 1) % len(self.tracks))

    def play_index(self, index: int) -> None:
        self._load(index)
        self._media.play()

    def seek(self, ms: int) -> None:
        self._media.setPosition(ms)

    def set_volume(self, volume: float) -> None:
        self._audio.setVolume(max(0.0, min(100.0, volume)) / 100)
        self.volume_changed.emit(self.volume, self.muted)

    def change_volume(self, delta: float) -> None:
        if self.muted and delta > 0:
            self._audio.setMuted(False)
        self.set_volume(self.volume + delta)

    def toggle_mute(self) -> None:
        self._audio.setMuted(not self._audio.isMuted())
        self.volume_changed.emit(self.volume, self.muted)

    def stop(self) -> None:
        self._media.stop()

    # ── internals ──
    def _load(self, index: int) -> None:
        self.index = index
        self._media.setSource(QUrl.fromLocalFile(str(self.current.path)))
        self.track_changed.emit(index)

    def _on_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next()
