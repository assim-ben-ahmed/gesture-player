"""Main window: camera view with the hand skeleton, now playing, controls, gesture legend and playlist."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .camera import FRAME_H, FRAME_W, GestureWorker
from .player import Player
from .poses import LABELS, Pose
from .tracker import ACTIONS, Command, Event, State

LEGEND = [
    (Pose.OPEN_PALM, "🖐", "Open palm", "Play / pause"),
    (Pose.POINT_RIGHT, "👉", "Point right", "Next track"),
    (Pose.POINT_LEFT, "👈", "Point left", "Previous track"),
    (Pose.PINCH, "👌", "Pinch, move up / down", "Volume"),
    (Pose.FIST, "✊", "Fist", "Mute / unmute"),
    (Pose.VICTORY, "✌️", "Victory (hold 1.5 s)", "Quit"),
]
TOASTS = {
    Command.NEXT: "⏭  Next track",
    Command.PREVIOUS: "⏮  Previous track",
    Command.QUIT: "✌️  Bye!",
}

STYLE = """
QMainWindow, QWidget { background: #12141c; color: #e8eaf2; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 14px; }
QFrame#card { background: #1b1e2a; border: 1px solid #262a3a; border-radius: 14px; }
QLabel#video { background: #0b0c12; border-radius: 14px; }
QLabel#eyebrow { color: #8b90a8; font-size: 12px; letter-spacing: 1px; }
QLabel#title { font-size: 21px; font-weight: 700; color: #ffffff; }
QLabel#artist { font-size: 15px; color: #5eead4; }
QLabel#time { color: #8b90a8; font-size: 12px; }
QLabel#pose { font-size: 16px; font-weight: 600; color: #fbbf24; }
QLabel#hint { color: #8b90a8; }
QLabel#toast { background: rgba(10, 12, 18, 200); color: #ffffff; font-size: 22px; font-weight: 700;
               border-radius: 14px; padding: 10px 22px; }
QPushButton { background: #262a3a; border: none; border-radius: 22px; font-size: 18px; min-width: 44px; min-height: 44px; }
QPushButton:hover { background: #31364a; }
QPushButton#play { background: #5eead4; color: #12141c; min-width: 56px; min-height: 56px; border-radius: 28px; font-size: 22px; }
QPushButton#play:hover { background: #99f6e4; }
QSlider::groove:horizontal { height: 6px; background: #31364a; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #5eead4; border-radius: 3px; }
QSlider::handle:horizontal { background: #ffffff; width: 14px; margin: -5px 0; border-radius: 7px; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 7px 8px; border-radius: 8px; color: #c9cce0; }
QListWidget::item:selected { background: #2a2f44; color: #ffffff; }
QProgressBar { background: #262a3a; border: none; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: #fbbf24; border-radius: 3px; }
QFrame#card QLabel, QFrame#row QLabel { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #31364a; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { height: 0; background: none; }
QFrame#row { border-radius: 10px; }
QFrame#row[active="true"] { background: #2a2f44; }
"""


def fmt(ms: int) -> str:
    s = max(0, ms) // 1000
    return f"{s // 60}:{s % 60:02d}"


class MainWindow(QMainWindow):
    def __init__(self, player: Player, worker: GestureWorker, source_label: str):
        super().__init__()
        self.player, self.worker = player, worker
        self.setWindowTitle("Gesture Player")
        self.setStyleSheet(STYLE)
        self.resize(1400, 800)
        self._seeking = False

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(18)

        # ── left: camera ──
        left = QVBoxLayout()
        self.video = QLabel(objectName="video")
        self.video.setMinimumSize(QSize(640, 360))
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast = QLabel("", self.video, objectName="toast")
        self.toast.hide()
        left.addWidget(self.video, 1)
        strip = QHBoxLayout()
        self.pose_lbl = QLabel("Show your hand to the camera", objectName="pose")
        self.hint_lbl = QLabel(source_label, objectName="hint")
        strip.addWidget(self.pose_lbl)
        strip.addStretch(1)
        strip.addWidget(self.hint_lbl)
        left.addLayout(strip)
        layout.addLayout(left, 1)

        # ── right: player ──
        side = QVBoxLayout()
        side.setSpacing(14)
        layout.addLayout(side)
        side.addWidget(self._now_playing())
        side.addWidget(self._legend())
        side.addWidget(self._playlist(), 1)

        # ── wiring ──
        player.track_changed.connect(self._on_track)
        player.playing_changed.connect(lambda p: self.play_btn.setText("⏸" if p else "▶"))
        player.volume_changed.connect(self._on_volume)
        player.position_changed.connect(self._on_position)
        worker.frame_ready.connect(self._on_frame)
        worker.state_changed.connect(self._on_state)
        worker.command.connect(self.on_command)
        worker.failed.connect(lambda msg: self.pose_lbl.setText(f"⚠️ {msg}"))
        self._on_track(player.index)
        self._on_volume(player.volume, player.muted)

    # ── panels ──
    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(objectName="card")
        card.setFixedWidth(400)
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)
        return card, box

    def _now_playing(self) -> QFrame:
        card, box = self._card()
        box.addWidget(QLabel("NOW PLAYING", objectName="eyebrow"))
        self.title_lbl = QLabel("", objectName="title")
        self.title_lbl.setWordWrap(True)
        self.artist_lbl = QLabel("", objectName="artist")
        box.addWidget(self.title_lbl)
        box.addWidget(self.artist_lbl)

        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self.seek.sliderReleased.connect(self._on_seek)
        times = QHBoxLayout()
        self.pos_lbl, self.dur_lbl = QLabel("0:00", objectName="time"), QLabel("0:00", objectName="time")
        times.addWidget(self.pos_lbl)
        times.addStretch(1)
        times.addWidget(self.dur_lbl)
        box.addSpacing(6)
        box.addWidget(self.seek)
        box.addLayout(times)

        controls = QHBoxLayout()
        controls.addStretch(1)
        prev_btn, self.play_btn, next_btn = QPushButton("⏮"), QPushButton("▶", objectName="play"), QPushButton("⏭")
        prev_btn.clicked.connect(self.player.previous)
        self.play_btn.clicked.connect(self.player.toggle)
        next_btn.clicked.connect(self.player.next)
        for b in (prev_btn, self.play_btn, next_btn):
            controls.addWidget(b)
        controls.addStretch(1)
        box.addLayout(controls)

        vol = QHBoxLayout()
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.clicked.connect(self.player.toggle_mute)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.valueChanged.connect(lambda v: self.player.set_volume(v) if v != self.player.volume else None)
        self.vol_lbl = QLabel("", objectName="time")
        self.vol_lbl.setFixedWidth(40)
        vol.addWidget(self.mute_btn)
        vol.addWidget(self.vol_slider, 1)
        vol.addWidget(self.vol_lbl)
        box.addLayout(vol)
        return card

    def _legend(self) -> QFrame:
        card, box = self._card()
        box.addWidget(QLabel("GESTURES", objectName="eyebrow"))
        self.rows: dict[Pose, tuple[QFrame, QProgressBar]] = {}
        for pose, emoji, name, action in LEGEND:
            row = QFrame(objectName="row")
            grid = QGridLayout(row)
            grid.setContentsMargins(8, 5, 8, 5)
            icon = QLabel(emoji)
            icon.setStyleSheet("font-size: 20px;")
            grid.addWidget(icon, 0, 0, 2, 1)
            grid.addWidget(QLabel(name), 0, 1)
            act = QLabel(action, objectName="hint")
            act.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(act, 0, 2)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setValue(0)
            grid.addWidget(bar, 1, 1, 1, 2)
            grid.setColumnStretch(1, 1)
            box.addWidget(row)
            self.rows[pose] = (row, bar)
        return card

    def _playlist(self) -> QFrame:
        card, box = self._card()
        box.addWidget(QLabel(f"PLAYLIST · {len(self.player.tracks)} TRACKS", objectName="eyebrow"))
        self.list = QListWidget()
        for t in self.player.tracks:
            self.list.addItem(t.label)
        self.list.itemDoubleClicked.connect(lambda item: self.player.play_index(self.list.row(item)))
        box.addWidget(self.list, 1)
        return card

    # ── player events ──
    def _on_track(self, index: int) -> None:
        track = self.player.tracks[index]
        self.title_lbl.setText(track.title)
        self.artist_lbl.setText(track.artist or Path(track.path).suffix.upper().lstrip("."))
        self.list.setCurrentRow(index)

    def _on_volume(self, volume: int, muted: bool) -> None:
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(volume)
        self.vol_slider.blockSignals(False)
        self.vol_lbl.setText("muted" if muted else f"{volume}%")
        self.mute_btn.setText("🔇" if muted else "🔊")

    def _on_position(self, pos: int, duration: int) -> None:
        if duration > 0 and not self._seeking:
            self.seek.setRange(0, duration)
            self.seek.setValue(pos)
        self.pos_lbl.setText(fmt(pos))
        self.dur_lbl.setText(fmt(duration))

    def _on_seek(self) -> None:
        self._seeking = False
        self.player.seek(self.seek.value())

    # ── gesture events ──
    def _on_frame(self, image: QImage) -> None:
        pix = QPixmap.fromImage(image).scaled(self.video.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
        self.video.setPixmap(pix)

    def _on_state(self, state: State) -> None:
        if state.pose == Pose.NONE:
            self.pose_lbl.setText("Show your hand to the camera")
        elif state.volume_mode:
            self.pose_lbl.setText(f"👌 Volume mode · {self.player.volume}%  (move up / down)")
        else:
            self.pose_lbl.setText(LABELS[state.pose] + ("  ✓" if state.latched else ""))
        for pose, (row, bar) in self.rows.items():
            active = pose == state.pose
            row.setProperty("active", "true" if active else "false")
            row.style().unpolish(row)
            row.style().polish(row)
            bar.setValue(int(100 * state.progress) if active and (pose in ACTIONS or state.volume_mode) else 0)

    def on_command(self, event: Event) -> None:
        c = event.command
        if c == Command.PLAY_PAUSE:
            was_playing = self.player.playing  # read before toggling: Qt updates the state asynchronously
            self.player.toggle()
            self.show_toast("⏸  Pause" if was_playing else "▶  Play")
            return
        if c == Command.NEXT:
            self.player.next()
        elif c == Command.PREVIOUS:
            self.player.previous()
        elif c == Command.MUTE:
            self.player.toggle_mute()
            self.show_toast("🔇  Muted" if self.player.muted else "🔊  Sound on")
            return
        elif c == Command.VOLUME:
            self.player.change_volume(event.value)
            return
        elif c == Command.QUIT:
            self.show_toast(TOASTS[c])
            QTimer.singleShot(900, self.close)
            return
        self.show_toast(TOASTS[c])

    def show_toast(self, text: str) -> None:
        self.toast.setText(text)
        self.toast.adjustSize()
        self.toast.move((self.video.width() - self.toast.width()) // 2, 24)
        self.toast.show()
        self.toast.raise_()
        QTimer.singleShot(1200, self.toast.hide)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.worker.stop()
        self.player.stop()
        super().closeEvent(event)


__all__ = ["FRAME_H", "FRAME_W", "MainWindow"]
