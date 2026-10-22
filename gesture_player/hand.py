"""A detected hand (21 landmarks) and the geometry used to read its pose.

Coordinates are normalised to the image (x right, y down) on the mirrored "selfie" view the user sees.
Every threshold is relative to the hand's own size, so detection works near or far from the camera, and fingers
are judged by distance to the wrist rather than by "tip above joint", so it works whatever the hand's angle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

WRIST = 0
THUMB_IP, THUMB_TIP = 3, 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_PIP, RING_TIP = 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20

FINGERS = {  # finger -> (pip joint, tip)
    "index": (INDEX_PIP, INDEX_TIP),
    "middle": (MIDDLE_PIP, MIDDLE_TIP),
    "ring": (RING_PIP, RING_TIP),
    "pinky": (PINKY_PIP, PINKY_TIP),
}

Point = tuple[float, float]


def dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class Hand:
    points: list[Point]          # 21 landmarks, normalised image coordinates
    handedness: str = "Right"    # as seen by the user in the mirrored view
    aspect: float = 16 / 9       # image width / height, so distances are measured in the same unit on both axes

    def p(self, i: int) -> Point:
        x, y = self.points[i][:2]
        return (x * self.aspect, y)

    @property
    def size(self) -> float:
        """Wrist to middle-finger knuckle: the hand's own length unit."""
        return max(dist(self.p(WRIST), self.p(MIDDLE_MCP)), 1e-6)

    def extended(self, finger: str) -> bool:
        pip, tip = FINGERS[finger]
        wrist = self.p(WRIST)
        return dist(self.p(tip), wrist) > 1.12 * dist(self.p(pip), wrist)

    def thumb_out(self) -> bool:
        return dist(self.p(THUMB_TIP), self.p(INDEX_MCP)) > 0.55 * self.size

    def pinch_gap(self) -> float:
        """Thumb tip to index tip, in hand lengths."""
        return dist(self.p(THUMB_TIP), self.p(INDEX_TIP)) / self.size

    def index_reach(self) -> float:
        """Index tip to index knuckle, in hand lengths (small when the index is curled into the palm)."""
        return dist(self.p(INDEX_TIP), self.p(INDEX_MCP)) / self.size

    def index_direction(self) -> Point:
        (x0, y0), (x1, y1) = self.p(INDEX_MCP), self.p(INDEX_TIP)
        return (x1 - x0, y1 - y0)
