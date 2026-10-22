"""Hand detection with MediaPipe's Hand Landmarker (Tasks API), plus the skeleton overlay."""

from __future__ import annotations

import urllib.request
from pathlib import Path

import cv2
import numpy as np

from .hand import Hand

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/"
             "hand_landmarker.task")
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "hand_landmarker.task"

CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
               (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]
TIPS = {4, 8, 12, 16, 20}


def ensure_model(path: Path = MODEL_PATH) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading the hand model (7.8 MB) to {path} ...")
        urllib.request.urlretrieve(MODEL_URL, path)
    return path


class HandDetector:
    """Detects one hand per frame. Frames must be the mirrored view (what the user sees)."""

    def __init__(self, model_path: Path = MODEL_PATH, min_confidence: float = 0.6):
        from mediapipe.tasks.python import BaseOptions, vision  # imported here so tests do not need mediapipe

        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(ensure_model(model_path))),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=min_confidence,
            min_hand_presence_confidence=min_confidence,
            min_tracking_confidence=min_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_ts = -1

    def detect(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Hand | None:
        import mediapipe as mp

        timestamp_ms = max(timestamp_ms, self._last_ts + 1)  # the API needs strictly increasing timestamps
        self._last_ts = timestamp_ms
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms)
        if not result.hand_landmarks:
            return None
        h, w = frame_bgr.shape[:2]
        points = [(lm.x, lm.y) for lm in result.hand_landmarks[0]]
        side = result.handedness[0][0].category_name if result.handedness else "Right"
        return Hand(points=points, handedness=side, aspect=w / h)

    def close(self) -> None:
        self._landmarker.close()


def draw_hand(frame: np.ndarray, hand: Hand, active: bool) -> None:
    """Skeleton overlay: teal when idle, warm when a gesture is being held."""
    h, w = frame.shape[:2]
    pts = [(int(x * w), int(y * h)) for x, y in hand.points]
    line = (80, 200, 255) if active else (200, 220, 120)   # BGR
    for a, b in CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], line, 3, cv2.LINE_AA)
    for i, p in enumerate(pts):
        cv2.circle(frame, p, 7 if i in TIPS else 5, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, p, 7 if i in TIPS else 5, line, 2, cv2.LINE_AA)


def draw_progress(frame: np.ndarray, hand: Hand, progress: float) -> None:
    """A ring around the wrist that fills while a gesture is held."""
    if progress <= 0:
        return
    h, w = frame.shape[:2]
    cx, cy = int(hand.points[0][0] * w), int(hand.points[0][1] * h)
    cv2.ellipse(frame, (cx, cy), (34, 34), -90, 0, 360, (70, 70, 70), 5, cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy), (34, 34), -90, 0, int(360 * progress), (80, 200, 255), 5, cv2.LINE_AA)
