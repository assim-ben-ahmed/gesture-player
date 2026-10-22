import pytest

from gesture_player.poses import Pose, classify
from gesture_player.synthetic import SCRIPT, make_hand, scripted_hand
from gesture_player.tracker import HOLD_S, Command, GestureTracker

REAL_POSES = [p for p in Pose if p != Pose.NONE]


@pytest.mark.parametrize("pose", list(Pose))
@pytest.mark.parametrize("size", [0.12, 0.3, 0.5])         # far from / close to the camera
@pytest.mark.parametrize("tilt", [-15, 0, 15])             # hand slightly rotated
@pytest.mark.parametrize("aspect", [16 / 9, 4 / 3])        # camera format
def test_poses_are_recognised_at_any_size_and_angle(pose, size, tilt, aspect):
    base = {Pose.POINT_RIGHT: -90, Pose.POINT_LEFT: 90}.get(pose, 0)
    assert classify(make_hand(pose, size=size, angle_deg=base + tilt, aspect=aspect)) == pose


def test_fist_is_not_mistaken_for_a_pinch():
    fist = make_hand(Pose.FIST)
    assert fist.pinch_gap() < 0.35 and fist.index_reach() < 0.2  # thumb near the index, index curled
    assert classify(fist) == Pose.FIST


def test_pointing_up_does_nothing_and_no_hand_is_none():
    assert classify(make_hand(Pose.POINT_RIGHT, angle_deg=0)) == Pose.NONE
    assert classify(None) == Pose.NONE


def run(tracker, pose, start, seconds, fps=30, **kw):
    events = []
    for i in range(int(seconds * fps)):
        events += tracker.update(pose, start + i / fps, **kw)
    return events


def test_holding_a_pose_fires_once_not_in_a_loop():
    t = GestureTracker()
    events = run(t, Pose.OPEN_PALM, 0.0, 5.0)  # palm held for 5 seconds
    assert [e.command for e in events] == [Command.PLAY_PAUSE]
    assert t.state.latched


def test_pose_must_be_held_long_enough():
    t = GestureTracker()
    assert run(t, Pose.POINT_RIGHT, 0.0, HOLD_S[Pose.POINT_RIGHT] * 0.6) == []


def test_changing_pose_rearms():
    t = GestureTracker()
    first = run(t, Pose.POINT_RIGHT, 0.0, 1.0)
    run(t, Pose.OPEN_PALM, 1.0, 0.2)  # a different pose (shorter than its hold time) in between
    second = run(t, Pose.POINT_RIGHT, 1.2, 1.0)
    assert [e.command for e in first + second] == [Command.NEXT, Command.NEXT]


def test_brief_tracking_loss_does_not_reset_a_hold():
    t = GestureTracker()
    run(t, Pose.FIST, 0.0, 0.5)
    run(t, Pose.NONE, 0.5, 0.15)        # hand lost for 150 ms
    events = run(t, Pose.FIST, 0.65, 0.4)
    assert [e.command for e in events] == [Command.MUTE]


def test_victory_needs_a_long_hold_to_quit():
    t = GestureTracker()
    assert run(t, Pose.VICTORY, 0.0, 1.0) == []
    assert [e.command for e in run(t, Pose.VICTORY, 1.0, 1.0)] == [Command.QUIT]


def test_pinch_moving_up_raises_volume_independently_of_hand_size():
    def total(size):
        t = GestureTracker()
        events = []
        for i in range(60):  # 2 s at 30 fps, moving up by one hand length
            y = 0.8 - size * i / 59
            events += t.update(Pose.PINCH, i / 30, pinch_y=y, hand_size=size)
        return sum(e.value for e in events if e.command == Command.VOLUME)

    near, far = total(0.4), total(0.15)
    assert 50 <= near <= 62 and abs(near - far) <= 2


def test_pinch_moving_down_lowers_volume():
    t = GestureTracker()
    events = []
    for i in range(30):
        events += t.update(Pose.PINCH, i / 30, pinch_y=0.4 + 0.004 * i, hand_size=0.3)
    assert sum(e.value for e in events) < 0


def test_demo_script_uses_every_control_gesture():
    poses = {p for p, *_ in SCRIPT}
    assert {Pose.OPEN_PALM, Pose.POINT_RIGHT, Pose.POINT_LEFT, Pose.PINCH, Pose.FIST} <= poses
    pose, hand = scripted_hand(1.5)
    assert pose == Pose.OPEN_PALM and classify(hand) == Pose.OPEN_PALM
