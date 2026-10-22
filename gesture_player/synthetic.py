"""Synthetic hands: plausible 21-landmark skeletons for each pose, at any position, size and angle.

Used by the tests (no camera needed) and by the --simulate demo, which replays a scripted sequence of gestures.
"""

from __future__ import annotations

import math

from .hand import Hand
from .poses import Pose

# Knuckle positions relative to the wrist, in hand lengths (y up is negative, palm facing the camera).
MCP = {"index": (-0.36, -0.95), "middle": (0.0, -1.0), "ring": (0.3, -0.93), "pinky": (0.56, -0.8)}
LENGTH = {"index": 0.85, "middle": 0.95, "ring": 0.88, "pinky": 0.68}
THUMB_OUT = [(-0.32, -0.22), (-0.58, -0.42), (-0.78, -0.62), (-0.92, -0.82)]
THUMB_IN = [(-0.3, -0.25), (-0.42, -0.5), (-0.3, -0.66), (-0.12, -0.72)]


def _finger(name: str, up: bool) -> list[tuple[float, float]]:
    mx, my = MCP[name]
    norm = math.hypot(mx, my)
    ux, uy = mx / norm, my / norm
    length = LENGTH[name]
    if up:
        return [(mx, my)] + [(mx + ux * length * k, my + uy * length * k) for k in (0.45, 0.75, 1.0)]
    pip = (mx + ux * length * 0.35, my + uy * length * 0.35)
    dip = (pip[0] - ux * 0.12 + uy * 0.08, pip[1] - uy * 0.12 - ux * 0.08)
    tip = (mx - ux * 0.05, my - uy * 0.05)
    return [(mx, my), pip, dip, tip]


def skeleton(pose: Pose) -> list[tuple[float, float]]:
    """21 points in hand lengths around the wrist, for a hand pointing up."""
    up = {
        Pose.OPEN_PALM: {"index", "middle", "ring", "pinky"},
        Pose.VICTORY: {"index", "middle"},
        Pose.POINT_LEFT: {"index"},
        Pose.POINT_RIGHT: {"index"},
        Pose.PINCH: {"middle", "ring", "pinky"},
        Pose.FIST: set(),
        Pose.NONE: {"index", "pinky"},
    }[pose]
    thumb = THUMB_OUT if pose in (Pose.OPEN_PALM, Pose.NONE) else THUMB_IN
    pts = [(0.0, 0.0)] + thumb
    for name in ("index", "middle", "ring", "pinky"):
        pts += _finger(name, name in up)
    if pose == Pose.PINCH:  # the 👌 circle: index bent forward, its tip meeting the thumb tip
        meet = (-0.76, -1.15)
        pts[2], pts[3], pts[4] = (-0.55, -0.48), (-0.72, -0.8), (meet[0] - 0.03, meet[1] + 0.06)
        pts[6], pts[7], pts[8] = (-0.5, -1.32), (-0.68, -1.33), meet
    return pts


def make_hand(pose: Pose, cx: float = 0.5, cy: float = 0.75, size: float = 0.28, angle_deg: float | None = None,
              aspect: float = 16 / 9) -> Hand:
    """Place a pose in the image: wrist at (cx, cy) normalised, `size` = hand length as a fraction of the height."""
    if angle_deg is None:
        angle_deg = {Pose.POINT_RIGHT: -90.0, Pose.POINT_LEFT: 90.0}.get(pose, 0.0)
    a = math.radians(angle_deg)
    cos, sin = math.cos(a), math.sin(a)
    points = []
    for x, y in skeleton(pose):
        rx, ry = x * cos + y * sin, -x * sin + y * cos  # rotate (negative angle = clockwise on screen)
        points.append((cx + rx * size / aspect, cy + ry * size))
    return Hand(points=points, aspect=aspect)


# The --simulate demo: (pose, seconds, wrist start, wrist end) - the pinch moves up to raise the volume.
SCRIPT = [
    (Pose.NONE, 1.2, (0.5, 0.8), (0.5, 0.8)),
    (Pose.OPEN_PALM, 1.4, (0.5, 0.78), (0.5, 0.78)),
    (Pose.NONE, 0.8, (0.5, 0.8), (0.5, 0.8)),
    (Pose.POINT_RIGHT, 1.0, (0.42, 0.62), (0.44, 0.62)),
    (Pose.NONE, 0.8, (0.5, 0.8), (0.5, 0.8)),
    (Pose.PINCH, 2.4, (0.52, 0.9), (0.52, 0.62)),
    (Pose.NONE, 0.8, (0.5, 0.8), (0.5, 0.8)),
    (Pose.POINT_LEFT, 1.0, (0.58, 0.62), (0.56, 0.62)),
    (Pose.NONE, 0.8, (0.5, 0.8), (0.5, 0.8)),
    (Pose.FIST, 1.4, (0.5, 0.75), (0.5, 0.75)),
    (Pose.NONE, 0.8, (0.5, 0.8), (0.5, 0.8)),
    (Pose.FIST, 1.4, (0.5, 0.75), (0.5, 0.75)),
    (Pose.NONE, 1.0, (0.5, 0.8), (0.5, 0.8)),
]
SCRIPT_LENGTH = sum(s[1] for s in SCRIPT)


def scripted_hand(t: float) -> tuple[Pose, Hand]:
    """The simulated hand at time t (seconds), looping over SCRIPT."""
    t %= SCRIPT_LENGTH
    for pose, duration, start, end in SCRIPT:
        if t < duration:
            k = t / duration
            cx = start[0] + (end[0] - start[0]) * k
            cy = start[1] + (end[1] - start[1]) * k
            wobble = 0.004 * math.sin(t * 9)  # a little natural movement
            return pose, make_hand(pose, cx + wobble, cy)
        t -= duration
    return Pose.NONE, make_hand(Pose.NONE)
