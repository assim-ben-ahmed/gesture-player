"""Background thread: read frames, find the hand, read the gesture, send frames and commands to the window."""

from __future__ import annotations

import time

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from . import synthetic
from .detector import draw_hand, draw_progress
from .hand import INDEX_TIP, THUMB_TIP
from .poses import Pose, classify
from .tracker import GestureTracker

FRAME_W, FRAME_H = 960, 540


class GestureWorker(QThread):
    frame_ready = Signal(QImage)
    state_changed = Signal(object)     # tracker.State
    command = Signal(object)           # tracker.Event
    failed = Signal(str)

    def __init__(self, source: int | str = 0, simulate: bool = False, mirror: bool = True):
        super().__init__()
        self.source, self.simulate, self.mirror = source, simulate, mirror
        self.tracker = GestureTracker()
        self._running = True

    def stop(self) -> None:
        self._running = False
        self.wait(2000)

    def run(self) -> None:
        try:
            self._simulate() if self.simulate else self._camera()
        except Exception as exc:  # noqa: BLE001 - shown to the user instead of a silent dead thread
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    # ── sources ──
    def _camera(self) -> None:
        from .detector import HandDetector

        detector = HandDetector()
        cap = cv2.VideoCapture(self.source)
        if isinstance(self.source, int):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        if not cap.isOpened():
            self.failed.emit(f"Cannot open the camera or video: {self.source}")
            return
        start = time.monotonic()
        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    if isinstance(self.source, str):  # a video file: loop it
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    time.sleep(0.01)
                    continue
                if self.mirror:
                    frame = cv2.flip(frame, 1)
                now = time.monotonic()
                hand = detector.detect(frame, int((now - start) * 1000))
                self._handle(frame, hand, classify(hand), now)
        finally:
            cap.release()
            detector.close()

    def _simulate(self) -> None:
        start = time.monotonic()
        while self._running:
            now = time.monotonic()
            pose, hand = synthetic.scripted_hand(now - start)
            frame = _backdrop()
            cv2.putText(frame, "SIMULATED HAND (demo mode)", (24, FRAME_H - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (140, 140, 160), 1, cv2.LINE_AA)
            self._handle(frame, hand, classify(hand), now)
            time.sleep(1 / 30)

    # ── shared ──
    def _handle(self, frame: np.ndarray, hand, pose: Pose, now: float) -> None:
        pinch_y = size = None
        if hand is not None and pose == Pose.PINCH:
            pinch_y = (hand.points[THUMB_TIP][1] + hand.points[INDEX_TIP][1]) / 2
            size = hand.size
        for event in self.tracker.update(pose, now, pinch_y, size or 1.0):
            self.command.emit(event)
        state = self.tracker.state
        if hand is not None:
            draw_hand(frame, hand, active=state.progress > 0 and not state.latched)
            if not state.latched and not state.volume_mode:
                draw_progress(frame, hand, state.progress)
        self.state_changed.emit(state)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        self.frame_ready.emit(QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())


def _backdrop() -> np.ndarray:
    """Background for the simulated hand: the video panel's own colour with a soft light in the middle."""
    yy, xx = np.mgrid[0:FRAME_H, 0:FRAME_W]
    r = np.hypot((xx - FRAME_W / 2) / FRAME_W, (yy - FRAME_H / 2) / FRAME_H)
    glow = np.clip(1 - r * 1.6, 0, 1)[..., None]
    base, light = np.array([18, 12, 11]), np.array([40, 30, 26])  # BGR; base = #0b0c12, the panel colour
    return np.ascontiguousarray((base + (light - base) * glow).astype(np.uint8))
