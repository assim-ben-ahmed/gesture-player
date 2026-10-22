"""Read a static pose from one frame. Checks run in priority order so poses never overlap."""

from __future__ import annotations

from enum import Enum

from .hand import Hand

PINCH_GAP = 0.32     # thumb-index tip distance (in hand lengths) under which the hand is pinching
SIDEWAYS = 1.3       # pointing must be this much more horizontal than vertical
INDEX_REACH = 0.35   # index tip to its knuckle (in hand lengths): above it the index is not curled into the palm


class Pose(str, Enum):
    NONE = "none"
    PINCH = "pinch"
    VICTORY = "victory"
    POINT_LEFT = "point_left"
    POINT_RIGHT = "point_right"
    OPEN_PALM = "open_palm"
    FIST = "fist"


LABELS = {
    Pose.NONE: "",
    Pose.PINCH: "👌 Pinch",
    Pose.VICTORY: "✌️ Victory",
    Pose.POINT_LEFT: "👈 Point left",
    Pose.POINT_RIGHT: "👉 Point right",
    Pose.OPEN_PALM: "🖐 Open palm",
    Pose.FIST: "✊ Fist",
}


def classify(hand: Hand | None) -> Pose:
    if hand is None:
        return Pose.NONE
    up = {f: hand.extended(f) for f in ("index", "middle", "ring", "pinky")}
    n_up = sum(up.values())

    # Pinch = thumb and index tips touching while the index stays out (the 👌 circle). In a fist the thumb also
    # rests near the index, but the index is curled into the palm, so its reach tells the two apart.
    if hand.pinch_gap() < PINCH_GAP and hand.index_reach() > INDEX_REACH and n_up < 4:
        return Pose.PINCH
    if up["index"] and up["middle"] and not up["ring"] and not up["pinky"]:
        return Pose.VICTORY
    if up["index"] and n_up == 1:
        dx, dy = hand.index_direction()
        if abs(dx) > SIDEWAYS * abs(dy):
            return Pose.POINT_RIGHT if dx > 0 else Pose.POINT_LEFT
        return Pose.NONE  # pointing up or down means nothing
    if n_up == 4:
        return Pose.OPEN_PALM
    if n_up == 0 and not hand.thumb_out():
        return Pose.FIST
    return Pose.NONE
