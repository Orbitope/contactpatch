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
from physics.track import CORNER_RADIUS, HALF_WIDTH, SampledTrack, long_exit, short_exit


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


# --- closed loop (TRACKS.md staging step 2) ---------------------------------

def _circle_track(radius=80.0, n=400, half_width=HALF_WIDTH):
    """A circle through the origin, tangent to +x there (heading 0) --
    matching where every synthetic ``Track`` in this file starts. Kept this
    way (rather than centred on the origin) so this fixture stays a clean
    isolation of the closed-loop plumbing (locate/preview/n_laps) from the
    start-pose question below, now that ``drive_lap`` places the car at the
    TRACK's own s=0 pose (TRACKS.md staging step 5) rather than assuming it
    coincides with the world origin."""
    theta = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    x, y = radius * np.sin(theta), radius * (1.0 - np.cos(theta))
    return SampledTrack("circle", x, y, half_width, closed=True, smoothing=0.0)


def _circle_track_off_origin(radius=80.0, n=400, half_width=HALF_WIDTH):
    """A circle CENTRED on the origin -- s=0 is 80 m from world (0, 0), the
    exact case ``drive_lap`` silently got wrong before (it placed the car at
    the world origin regardless of where the track's own s=0 actually was)."""
    theta = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    x, y = radius * np.cos(theta), radius * np.sin(theta)
    return SampledTrack("circle_off_origin", x, y, half_width, closed=True,
                        smoothing=0.0)


def test_locator_inverts_to_xy_across_the_seam_on_a_closed_track():
    """The seam (s=0 == s=length) is exactly where a wraparound bug would
    show up first -- same inverse-map check as the open-track test above,
    straddling s=0/length instead of staying safely in the middle."""
    circle = _circle_track()
    loc = TrackLocator(circle)
    loc.window = circle.length
    for s in (circle.length - 5.0, circle.length - 0.5, 0.5, 5.0):
        for n in (-1.5, 0.0, 1.5):
            x, y = circle.to_xy(np.array([s]), np.array([n]))
            loc._last_i = 0
            s_hat, n_hat, _ = loc.locate(float(x[0]), float(y[0]), 0.0)
            # s is defined mod length on a closed track
            d = min(abs(s_hat - s), abs(s_hat - s + circle.length),
                   abs(s_hat - s - circle.length))
            assert d < 1.0
            assert n_hat == pytest.approx(n, abs=0.05)


def test_preview_wraps_instead_of_flattening_at_the_finish_line():
    """rl_env._curvature_ahead has the same bug fixed the same way: an open
    track's preview is deliberately clamped/extrapolated (see the test
    above), but a closed track's road genuinely continues past s=length, so
    the preview point there must be the START of the next lap, not a
    straight-line extrapolation off into space."""
    circle = _circle_track()
    loc = TrackLocator(circle)
    px, py = loc.preview(circle.length - 5.0, 10.0)         # wraps 5 m in
    qx, qy = loc.preview(5.0, 0.0)                           # same point directly
    assert px == pytest.approx(qx, abs=0.5)
    assert py == pytest.approx(qy, abs=0.5)


def test_drive_lap_completes_two_laps_of_a_closed_track():
    """A circle has constant curvature, so SpeedProfile's single-lap plan
    (TRACKS.md staging step 2 does not extend it across multiple laps) is
    still the right target speed at every s, wrapped or not -- this isolates
    the wraparound plumbing (locate/preview/n_laps termination) from the
    still-open question of multi-lap speed planning."""
    circle = _circle_track()
    b = DoubleTrackBackend(schema.RV_1, diff="open")
    prof = SpeedProfile(circle, a_lat=0.85 * 9.3, a_brake=8.0, a_drive=3.3,
                        v_max=40.0)
    driver = Driver(schema.RV_1, prof, TrackLocator(circle))

    one = drive_lap(b, circle, driver, grip_use=0.85, n_laps=1, max_steps=2000)
    assert one.valid and one.reason == "finished"

    two = drive_lap(b, circle, driver, grip_use=0.85, n_laps=2, max_steps=4000)
    assert two.valid and two.reason == "finished"
    assert two.lap_time == pytest.approx(2 * one.lap_time, rel=0.05)


def test_drive_lap_starts_at_the_tracks_own_pose_not_the_world_origin():
    """TRACKS.md staging step 5: drive_lap silently placed the car at world
    (0, 0, heading 0) regardless of where the track's own s=0 point actually
    was -- harmless for every synthetic Track here (whose centreline
    integrates FROM the origin by construction) but wrong for any track
    whose raw coordinates are not centred on it, which blocked drive_lap on
    Spa entirely (s=0 there is nowhere near world (0, 0))."""
    circle = _circle_track_off_origin()
    b = DoubleTrackBackend(schema.RV_1, diff="open")
    prof = SpeedProfile(circle, a_lat=0.85 * 9.3, a_brake=8.0, a_drive=3.3,
                        v_max=40.0)
    driver = Driver(schema.RV_1, prof, TrackLocator(circle))

    lap = drive_lap(b, circle, driver, grip_use=0.85, n_laps=1, max_steps=2000)
    assert lap.valid and lap.reason == "finished"
    # The very first logged offset must be small -- if the car had started
    # at the world origin instead (80 m from this track's actual road), the
    # locator would report a huge |n| on step one and the lap would break
    # immediately, not finish cleanly.
    assert abs(lap.log["n"][0]) < 1.0


def test_brake_cap_is_the_demonstrated_tyre_capability_not_a_round_number():
    """POWER-REVIEW Phase 0 item 3. The old 12,000 N cap was 0.899 g on
    RV-1's 1,360 kg, below the ~0.985 g the OC solver demonstrates under real
    combined-slip demands -- so above `grip_use` 0.899 the CAP, not the tyre
    and not the design, set the braking demand. Episode 13 and phase2 both
    bisect `grip_use` to the cornering limit, i.e. they measure entirely
    inside that regime.

    Pinned as a g-value rather than a force so it cannot silently drift if
    the reference mass changes."""
    from physics import schema
    g_value = BRAKE_MAX / (schema.RV_1.mass * schema.G)
    assert g_value == pytest.approx(0.985, abs=1e-6), (
        f"brake cap is {g_value:.4f} g, expected 0.985")
    # ...and it must exceed the old cap, or the fix did not take.
    assert BRAKE_MAX > 12000.0


def test_phase2_and_ep13_brake_from_the_same_constant():
    """They did not, and that is the bug this pins. phase2_sweep defined its
    own `BRAKE_MAX_FIXED_N = 0.985 * G * mass` while ep13 used the module's
    12,000 N -- two experiments in one review braking differently, which is
    how F99's staleness began."""
    from experiments.power_review.phase2_sweep import BRAKE_MAX_FIXED_N
    assert BRAKE_MAX_FIXED_N == BRAKE_MAX
