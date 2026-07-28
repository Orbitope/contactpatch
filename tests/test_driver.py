"""The closed-loop driver: does it know where it is, and does it drive.

The locator test is the important one. ``TrackLocator.locate`` and ``Track.to_xy``
are inverse maps between the curvilinear and Cartesian frames, written months apart
for different purposes, and this project's standing lesson is that a frame
conversion which is wrong renders a perfectly plausible picture of a car doing
something it never did (F36). Checking one against the other is the cheap version
of the check that was missing then.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from physics import schema
from physics.double_track import DoubleTrackBackend
from physics.driver import (BRAKE_MAX, DRIVE_MAX, Driver, SpeedProfile,
                            TrackLocator, drive_lap)
from physics.track import CORNER_RADIUS, long_exit, short_exit


@pytest.fixture
def track():
    return long_exit()


def _driver(track, grip_use=0.9, **kw):
    prof = SpeedProfile(track, a_lat=grip_use * 9.3, a_brake=8.0, a_drive=3.3)
    return Driver(schema.RV_1, prof, TrackLocator(track), **kw)


# --- where am I ------------------------------------------------------------

def test_the_locator_inverts_the_drawing_map(track):
    """``to_xy(s, n)`` then ``locate`` must come back to ``(s, n)``."""
    loc = TrackLocator(track)
    for s in (10.0, 75.0, 100.0, 130.0, 250.0):
        for n in (-2.0, 0.0, 1.5):
            x, y = track.to_xy(np.array([s]), np.array([n]))
            loc._last_i = 0
            loc.window = track.length            # search the whole track
            s_hat, n_hat, _ = loc.locate(float(x[0]), float(y[0]), 0.0)
            assert s_hat == pytest.approx(s, abs=1.0)
            assert n_hat == pytest.approx(n, abs=0.05)


def test_positive_offset_is_to_the_left(track):
    """+n is left of the direction of travel, as ``schema`` and ``track`` say."""
    loc = TrackLocator(track)
    # 10 m along the opening straight, which runs along +x with heading 0.
    s_hat, n_hat, _ = loc.locate(10.0, 1.0, 0.0)
    assert n_hat == pytest.approx(1.0, abs=0.05)


def test_the_preview_point_keeps_going_after_the_road_ends(track):
    """Clamping it instead cost a clean lap and a 45-degree slide, every time."""
    loc = TrackLocator(track)
    x1, y1 = loc.preview(track.length - 1.0, 20.0)
    x2, y2 = loc.preview(track.length - 1.0, 40.0)
    assert math.hypot(x2 - x1, y2 - y1) == pytest.approx(20.0, rel=0.02)


# --- the plan --------------------------------------------------------------

def test_the_speed_profile_respects_the_cornering_limit(track):
    prof = SpeedProfile(track, a_lat=9.0, a_brake=8.0, a_drive=3.3)
    k = np.abs(np.asarray(track.curvature(prof.s)))
    corner = k > 1e-6
    assert np.all(prof.v[corner] <= np.sqrt(9.0 / k[corner]) + 1e-6)
    assert prof.target(90.0) == pytest.approx(math.sqrt(9.0 * CORNER_RADIUS),
                                              rel=0.02)


def test_the_profile_brakes_before_the_corner_not_in_it(track):
    prof = SpeedProfile(track, a_lat=9.0, a_brake=8.0, a_drive=3.3)
    assert prof.target(0.0) > prof.target(40.0) > prof.target(69.0)
    assert prof.slope(40.0) < 0.0


def test_a_longer_run_up_lets_the_car_arrive_faster(track):
    """A property of the backward pass, not of any particular number."""
    short = SpeedProfile(short_exit(), a_lat=9.0, a_brake=8.0, a_drive=3.3)
    assert short.target(0.0) == pytest.approx(SpeedProfile(
        track, a_lat=9.0, a_brake=8.0, a_drive=3.3).target(0.0), rel=1e-9)


# --- driving ---------------------------------------------------------------

def test_a_moderate_lap_finishes_inside_the_tire_fit(track):
    b = DoubleTrackBackend(schema.RV_1, diff="open")
    lap = drive_lap(b, track, _driver(track, 0.9), grip_use=0.9)
    assert lap.valid and lap.reason == "finished"
    assert lap.worst_slip_deg < 12.0
    assert lap.max_offset < 1.0                     # it stayed on the centreline


def test_asking_for_more_grip_than_the_car_has_ends_badly(track):
    b = DoubleTrackBackend(schema.RV_1, diff="open")
    lap = drive_lap(b, track, _driver(track, 1.3), grip_use=1.3)
    assert not lap.valid


def test_a_harder_lap_is_a_quicker_lap_while_it_is_still_valid(track):
    b = DoubleTrackBackend(schema.RV_1, diff="open")
    times = []
    for gu in (0.8, 0.9, 1.0):
        lap = drive_lap(b, track, _driver(track, gu), grip_use=gu)
        assert lap.valid
        times.append(lap.lap_time)
    assert times[0] > times[1] > times[2]


def test_the_lap_is_deterministic(track):
    b = DoubleTrackBackend(schema.RV_1, diff="open")
    a = drive_lap(b, track, _driver(track, 0.95), grip_use=0.95)
    c = drive_lap(b, track, _driver(track, 0.95), grip_use=0.95)
    assert a.lap_time == c.lap_time
    assert np.allclose(a.log["speed"], c.log["speed"])


def test_steering_noise_is_seeded_and_actually_perturbs(track):
    b = DoubleTrackBackend(schema.RV_1, diff="open")
    kw = dict(grip_use=0.9)
    d = _driver(track, 0.9, steer_noise=0.15)
    one = drive_lap(b, track, d, seed=1, **kw)
    two = drive_lap(b, track, d, seed=1, **kw)
    three = drive_lap(b, track, d, seed=2, **kw)
    assert np.allclose(one.log["steer"], two.log["steer"])
    assert not np.allclose(one.log["steer"][:200], three.log["steer"][:200])


def test_the_lap_logs_everything_rule_4_asks_for(track):
    b = DoubleTrackBackend(schema.RV_1, diff="open")
    lap = drive_lap(b, track, _driver(track, 0.9), grip_use=0.9)
    for key in ("alpha_max_deg", "load_min", "utilisation_max",
                "envelope_violation", "a_y"):
        assert key in lap.log and len(lap.log[key]) == len(lap.log["t"])
    for c in ("fl", "fr", "rl", "rr"):
        assert f"fz_{c}" in lap.log and f"util_{c}" in lap.log
    # The file's own load bound, enforced (rule 4).
    assert lap.log["load_min"].min() >= 0.0
    assert lap.log["fz_fl"].max() < 10_125.0
