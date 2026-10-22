"""Turn the pose seen in each frame into player commands.

- A command fires once when its pose has been held long enough, then waits until the hand changes pose
  ("release") before it can fire again: holding an open palm never toggles play/pause in a loop.
- Pinch is continuous: moving the pinched hand up or down changes the volume, measured in hand lengths so the
  speed does not depend on the distance to the camera.
- Short tracking glitches (a lost hand for a few frames) are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .poses import Pose


class Command(str, Enum):
    PLAY_PAUSE = "play_pause"
    NEXT = "next"
    PREVIOUS = "previous"
    MUTE = "mute"
    QUIT = "quit"
    VOLUME = "volume"


ACTIONS = {
    Pose.OPEN_PALM: Command.PLAY_PAUSE,
    Pose.POINT_RIGHT: Command.NEXT,
    Pose.POINT_LEFT: Command.PREVIOUS,
    Pose.FIST: Command.MUTE,
    Pose.VICTORY: Command.QUIT,
}
HOLD_S = {  # how long a pose must be held before it fires
    Pose.OPEN_PALM: 0.45,
    Pose.POINT_RIGHT: 0.30,
    Pose.POINT_LEFT: 0.30,
    Pose.FIST: 0.80,
    Pose.VICTORY: 1.50,  # quitting must be deliberate
}
PINCH_SETTLE_S = 0.12
VOLUME_PER_HAND = 60.0   # volume points per hand length of vertical movement
LOST_GRACE_S = 0.35


@dataclass
class Event:
    command: Command
    value: float = 0.0


@dataclass
class State:
    pose: Pose = Pose.NONE
    progress: float = 0.0        # 0..1 towards firing the current pose
    latched: bool = False        # fired; waiting for the hand to change pose
    volume_mode: bool = False


@dataclass
class GestureTracker:
    state: State = field(default_factory=State)
    _pose: Pose = Pose.NONE
    _since: float = 0.0
    _last_seen: float = 0.0
    _pinch_ref: float | None = None
    _pinch_carry: float = 0.0

    def reset(self) -> None:
        self.state = State()
        self._pose, self._pinch_ref, self._pinch_carry = Pose.NONE, None, 0.0

    def update(self, pose: Pose, now: float, pinch_y: float | None = None, hand_size: float = 1.0) -> list[Event]:
        """Feed one frame. `pinch_y` is the pinch point's height (normalised) and `hand_size` the hand length,
        both only needed while pinching."""
        if pose == Pose.NONE and self._pose != Pose.NONE and now - self._last_seen < LOST_GRACE_S:
            return []  # brief tracking loss: keep the current gesture alive
        if pose != Pose.NONE:
            self._last_seen = now

        if pose != self._pose:
            self._pose, self._since = pose, now
            self.state = State(pose=pose)
            self._pinch_ref, self._pinch_carry = None, 0.0
            return []

        held = now - self._since
        if pose == Pose.PINCH:
            return self._pinch(held, pinch_y, hand_size)
        if pose in ACTIONS and not self.state.latched:
            self.state.progress = min(1.0, held / HOLD_S[pose])
            if held >= HOLD_S[pose]:
                self.state.latched = True
                return [Event(ACTIONS[pose])]
        return []

    def _pinch(self, held: float, y: float | None, size: float) -> list[Event]:
        if held < PINCH_SETTLE_S or y is None:
            return []
        self.state.volume_mode = True
        self.state.progress = 1.0
        if self._pinch_ref is None:
            self._pinch_ref = y
            return []
        # Up on screen (smaller y) raises the volume.
        delta = (self._pinch_ref - y) / max(size, 1e-6) * VOLUME_PER_HAND + self._pinch_carry
        self._pinch_ref = y
        steps = int(delta)  # whole volume points only; keep the remainder for smooth slow moves
        self._pinch_carry = delta - steps
        return [Event(Command.VOLUME, steps)] if steps else []
