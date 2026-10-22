"""Entry point: `python -m gesture_player [MEDIA_FOLDER] [--camera N | --video FILE | --simulate]`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .camera import GestureWorker
from .demo_tracks import ensure_demo_tracks
from .player import Player
from .playlist import scan
from .poses import Pose
from .tracker import Command, Event, State
from .ui import MainWindow


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="gesture_player", description="Control your music with hand gestures.")
    p.add_argument("media", nargs="?", help="folder with your music or videos (asked if missing)")
    source = p.add_mutually_exclusive_group()
    source.add_argument("--camera", type=int, default=0, help="webcam index (default 0)")
    source.add_argument("--video", help="use a video file instead of the webcam")
    source.add_argument("--simulate", action="store_true", help="demo with a simulated hand, no camera needed")
    p.add_argument("--demo", action="store_true", help="use the generated demo tracks")
    p.add_argument("--no-mirror", action="store_true", help="do not mirror the camera image")
    p.add_argument("--volume", type=int, default=60)
    p.add_argument("--screenshots", type=Path, help=argparse.SUPPRESS)  # used by scripts/screenshots.py
    return p.parse_args(argv)


def choose_folder(args: argparse.Namespace) -> Path:
    if args.demo:
        return ensure_demo_tracks()
    if args.media:
        return Path(args.media)
    folder = QFileDialog.getExistingDirectory(None, "Choose a folder with your music")
    return Path(folder) if folder else ensure_demo_tracks()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Gesture Player")

    folder = choose_folder(args)
    tracks = scan(folder) if folder.is_dir() else []
    if not tracks:
        QMessageBox.warning(None, "Gesture Player", f"No audio or video files in {folder}.\nUsing the demo tracks.")
        tracks = scan(ensure_demo_tracks())

    if args.simulate:
        worker, label = GestureWorker(simulate=True), "Demo: simulated hand"
    elif args.video:
        worker, label = GestureWorker(source=args.video, mirror=not args.no_mirror), f"Video: {Path(args.video).name}"
    else:
        worker, label = GestureWorker(source=args.camera, mirror=not args.no_mirror), f"Webcam {args.camera}"

    player = Player(tracks, volume=args.volume)
    window = MainWindow(player, worker, label)
    window.show()
    worker.start()
    player.play_index(0)
    if args.screenshots:
        schedule_screenshots(window, args.screenshots)
    return app.exec()


SHOTS = ("open_palm_hold", "next_track", "volume_pinch", "muted")


def schedule_screenshots(window: MainWindow, folder: Path) -> None:
    """Capture the README images at the moments the gestures actually happen (driven by the app's own events,
    not by a clock, so the images always show what their names say)."""
    folder.mkdir(parents=True, exist_ok=True)
    taken: set[str] = set()

    def shoot(name: str, delay_ms: int = 0) -> None:
        if name in taken:
            return
        taken.add(name)
        QTimer.singleShot(delay_ms, lambda: window.grab().save(str(folder / f"{name}.png")))
        if len(taken) == len(SHOTS):
            QTimer.singleShot(delay_ms + 600, window.close)

    def on_state(state: State) -> None:
        if state.pose == Pose.OPEN_PALM and 0.6 <= state.progress < 1:
            shoot("open_palm_hold")
        elif state.volume_mode and window.player.volume >= 70:
            shoot("volume_pinch")

    def on_command(event: Event) -> None:
        if event.command == Command.NEXT:
            shoot("next_track", 250)    # let the toast appear
        elif event.command == Command.MUTE:
            shoot("muted", 250)         # the first fist mutes, the second unmutes

    window.worker.state_changed.connect(on_state)
    window.worker.command.connect(on_command)
    QTimer.singleShot(30_000, window.close)  # safety net


if __name__ == "__main__":
    sys.exit(main())
