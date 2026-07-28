"""The drivetrain yaw moment — the term Season 4 is entirely about.

For the whole of Seasons 1-3 this model computed its yaw moment as

    m_z = a * (fy_f * cos(steer) + fx_f * sin(steer)) - b * fy_r

which has no track-width term at all, so moving the entire drive force from one
wheel to the other changed the computed yaw by exactly zero. Torque vectoring IS
that asymmetry, so Season 4 would have measured a null result silently. See
FINDINGS F72.

These tests work the GEOMETRY rather than restating the implementation's formula.
CLAUDE.md requires that of every frame conversion because all three of the existing
ones have been wrong at least once and all three failed silently — a wrong sign
renders a plausible picture of a car doing something it never did (F36).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from physics import schema
from physics.double_track import CORNERS, DoubleTrackBackend, WheelForces


def _wheels(**fx) -> dict:
    """Four wheels carrying only the longitudinal forces given."""
    return {c: WheelForces(fy=0.0, fx=float(fx.get(c, 0.0)), alpha=0.0,
                           kappa=0.0, fz=4000.0) for c in CORNERS}


def test_left_wheels_are_at_positive_y_because_ISO_8855_y_points_left():
    b = DoubleTrackBackend(schema.RV_1)
    for corner in ("fl", "rl"):
        assert b.wheel_position(corner)[1] > 0.0, corner
    for corner in ("fr", "rr"):
        assert b.wheel_position(corner)[1] < 0.0, corner
    # front wheels ahead of the CoG, rear behind it
    assert b.wheel_position("fl")[0] > 0.0
    assert b.wheel_position("rl")[0] < 0.0


def test_driving_the_right_wheel_yaws_the_car_left():
    """Worked from the geometry: a forward force on the right-hand side of the car
    pushes that side forward, which rotates the nose to the LEFT. Under ISO 8855 a
    left turn is positive yaw, so m_z must be positive."""
    b = DoubleTrackBackend(schema.RV_1)
    assert b.yaw_moment(_wheels(rr=3000.0), 0.0) > 0.0
    assert b.yaw_moment(_wheels(rl=3000.0), 0.0) < 0.0


def test_the_moment_arm_is_half_the_track_of_the_axle_that_produced_it():
    """Magnitude, not just sign. Force F on one rear wheel acts at track_r / 2."""
    p = schema.RV_1
    b = DoubleTrackBackend(p)
    f = 2500.0
    assert b.yaw_moment(_wheels(rr=f), 0.0) == pytest.approx(f * p.track_r / 2.0)
    assert b.yaw_moment(_wheels(fr=f), 0.0) == pytest.approx(f * p.track_f / 2.0)
    # and the two tracks differ, so using the wrong one is detectable
    assert p.track_f != p.track_r


def test_a_symmetric_split_produces_no_drivetrain_yaw_at_all():
    """The reason every Season 1-3 result is untouched. Asserted, not assumed."""
    b = DoubleTrackBackend(schema.RV_1)
    assert b.yaw_moment(_wheels(rl=1500.0, rr=1500.0), 0.0) == pytest.approx(0.0)
    assert b.yaw_moment(_wheels(fl=900.0, fr=900.0), 0.0) == pytest.approx(0.0)


def test_only_the_DIFFERENCE_between_the_wheels_matters():
    """Adding the same force to both wheels of an axle changes thrust, not yaw."""
    b = DoubleTrackBackend(schema.RV_1)
    a = b.yaw_moment(_wheels(rl=500.0, rr=2000.0), 0.0)
    c = b.yaw_moment(_wheels(rl=1500.0, rr=3000.0), 0.0)
    assert a == pytest.approx(c)


def test_the_new_formula_is_the_old_one_plus_exactly_two_named_terms():
    """The superseded expression, decomposed, so the change is auditable.

    ``m_z`` used to be ``a*(fy_f*cos + fx_f*sin) - b*fy_r``. The per-wheel sum adds
    exactly two things, and BOTH are real:

    1. the **drivetrain** moment, ``(track/2) * (fx_right - fx_left)`` per axle,
       which is what torque vectoring is (F72); and
    2. the **steering-drag** moment, ``(track_f/2) * sin(steer) * (fy_fl - fy_fr)``
       — a steered front tire's lateral force has a rearward body-frame component,
       and the more heavily loaded outside tire is dragged back harder than the
       inside one, which yaws the car out of the corner.

    The second is why the understeer gradient moved 0.172 -> 0.220 deg/g. It is not
    new physics bolted on: the model's FORCE equations already carried
    ``fx_body = fx_f*cos(steer) - fy_f*sin(steer)``, so the old moment was
    inconsistent with the forces the same model computed. See FINDINGS F73.
    """
    p = schema.RV_1
    b = DoubleTrackBackend(p)
    rng = np.random.default_rng(11)
    for _ in range(60):
        steer = float(rng.uniform(-0.4, 0.4))
        w = {c: WheelForces(fy=float(rng.uniform(-3000, 3000)),
                            fx=float(rng.uniform(-2000, 2000)),
                            alpha=0.0, kappa=0.0, fz=4000.0) for c in CORNERS}
        fy_f, fy_r = w["fl"].fy + w["fr"].fy, w["rl"].fy + w["rr"].fy
        fx_f = w["fl"].fx + w["fr"].fx
        superseded = (p.a * (fy_f * math.cos(steer) + fx_f * math.sin(steer))
                      - p.b * fy_r)
        drivetrain = (0.5 * p.track_r * (w["rr"].fx - w["rl"].fx)
                      + 0.5 * p.track_f * math.cos(steer)
                      * (w["fr"].fx - w["fl"].fx))
        steering_drag = (0.5 * p.track_f * math.sin(steer)
                         * (w["fl"].fy - w["fr"].fy))
        assert b.yaw_moment(w, steer) == pytest.approx(
            superseded + drivetrain + steering_drag, abs=1e-9)


def test_the_moment_is_consistent_with_the_force_equations():
    """The actual defect: forces were projected into the body frame and moments
    were not. Any wheel force must contribute to m_z using the SAME body-frame
    components the model uses for acceleration."""
    p = schema.RV_1
    b = DoubleTrackBackend(p)
    steer = math.radians(15.0)
    w = {c: WheelForces(fy=1200.0, fx=600.0, alpha=0.0, kappa=0.0, fz=4000.0)
         for c in CORNERS}
    for c in CORNERS:
        fx_b, fy_b = b.body_forces(c, w[c], steer)
        if c[0] == "f":
            assert fx_b == pytest.approx(600.0 * math.cos(steer)
                                         - 1200.0 * math.sin(steer))
            assert fy_b == pytest.approx(600.0 * math.sin(steer)
                                         + 1200.0 * math.cos(steer))
        else:
            assert (fx_b, fy_b) == pytest.approx((600.0, 1200.0))


def test_a_steered_front_asymmetry_is_projected_into_the_body_frame():
    """A steered wheel's longitudinal force is not along the car's x axis, so its
    yaw contribution shrinks by cos(steer). Checked against the projection worked
    by hand, not against the implementation."""
    p = schema.RV_1
    b = DoubleTrackBackend(p)
    f, steer = 2000.0, math.radians(20.0)
    got = b.yaw_moment(_wheels(fr=f), steer)
    # body-frame longitudinal component of a pure wheel-frame fx is fx*cos(steer);
    # the lateral component fx*sin(steer) acts at the front axle, arm a.
    expect = f * math.cos(steer) * p.track_f / 2.0 + p.a * f * math.sin(steer)
    assert got == pytest.approx(expect)


def test_yaw_acceleration_from_a_realistic_asymmetry_is_not_negligible():
    """Sanity on the size of the thing that was missing: if it were tiny, the
    omission would not have mattered much. It is not tiny."""
    p = schema.RV_1
    b = DoubleTrackBackend(p)
    m_z = b.yaw_moment(_wheels(rr=3000.0), 0.0)
    assert abs(m_z / p.i_zz) > 1.0        # rad/s^2


def test_the_conclusion_survives_the_track_width_uncertainty():
    """``track_f``/``track_r`` are only [LIKELY]. CLAUDE.md requires every
    torque-vectoring magnitude claim to be re-run at +/-3% track with the
    CONCLUSION intact."""
    f = 3000.0
    base = DoubleTrackBackend(schema.RV_1).yaw_moment(_wheels(rr=f), 0.0)
    for factor in (0.97, 1.03):
        scaled = DoubleTrackBackend(
            schema.RV_1.scaled_track(factor)).yaw_moment(_wheels(rr=f), 0.0)
        assert scaled == pytest.approx(base * factor, rel=1e-9)
        assert scaled > 0.0                        # sign, i.e. the conclusion
        assert abs(scaled / schema.RV_1.i_zz) > 1.0


# --- the differential ---------------------------------------------------------
#
# ONE mechanism, not two. An earlier version had a grip-proportional torque bias and
# a separate speed couple; that counted the same physical effect twice and gave the
# bias the wrong direction (F77). A differential resists the driven wheels turning at
# different speeds, and torque flows from the FASTER wheel to the SLOWER one. Which
# wheel is faster decides everything, and it changes with throttle.

import math

from physics.double_track import BicycleState


def _corner(a_y=9.0, radius=40.0) -> tuple[BicycleState, dict]:
    """A self-consistent steady left-hand corner.

    An earlier sweep varied lateral acceleration while holding yaw rate fixed, which
    is not a corner any car can be in: a steady corner ties a_y = v^2/R. At 25 m/s on
    40 m it implied 1.59 g on a 0.97 g car. F77.
    """
    v = math.sqrt(a_y * radius)
    st = BicycleState(v_x=v, v_y=0.0, yaw_rate=v / radius, steer=0.0)
    return st, DoubleTrackBackend(schema.RV_1).wheel_loads(1.5, a_y)


def _fx(diff, demand, st, loads, **kw):
    return DoubleTrackBackend(schema.RV_1, diff=diff, **kw).differential_forces(
        demand, loads, st)


def test_an_open_differential_always_feeds_both_wheels_equally():
    st, loads = _corner()
    for demand in (500.0, 2000.0, 6000.0):
        fx = _fx("open", demand, st, loads)
        assert fx["rl"] == pytest.approx(fx["rr"]), demand


def test_an_open_differential_is_limited_by_twice_the_weaker_wheel():
    """The one-sentence reason the other two devices exist."""
    st, loads = _corner()
    b = DoubleTrackBackend(schema.RV_1, diff="open")
    cap_in = b.DIFF_CAP_FRACTION * float(b._tire.peak_fx(min(loads["rl"], loads["rr"])))
    fx = _fx("open", 6000.0, st, loads)
    assert fx["rl"] + fx["rr"] == pytest.approx(2.0 * cap_in, rel=1e-6)
    assert fx["rl"] + fx["rr"] < 6000.0 * 0.75


def test_at_part_throttle_a_locking_diff_pushes_the_car_WIDE():
    """Neither wheel is saturated, so kinematics decides: the outside wheel turns
    faster, loses torque to the inside, and the car is yawed out of the corner."""
    st, loads = _corner()
    for diff in ("lsd", "locked"):
        fx = _fx(diff, 1000.0, st, loads)
        assert fx["rl"] > fx["rr"], diff          # inside gains, outside loses
        w = {c: WheelForces(fy=0.0, fx=fx[c], alpha=0.0, kappa=0.0, fz=loads[c])
             for c in CORNERS}
        assert DoubleTrackBackend(schema.RV_1).yaw_moment(w, 0.0) < 0.0, diff


def test_at_full_throttle_the_same_device_turns_the_car_IN():
    """The inside wheel saturates and spins, so it becomes the faster one and the
    device sends torque outboard instead. Same rule, opposite outcome — and a model
    with a hard-coded bias direction cannot produce both."""
    st, loads = _corner()
    fx = _fx("locked", 6000.0, st, loads)
    assert fx["rr"] > fx["rl"]
    w = {c: WheelForces(fy=0.0, fx=fx[c], alpha=0.0, kappa=0.0, fz=loads[c])
         for c in CORNERS}
    assert DoubleTrackBackend(schema.RV_1).yaw_moment(w, 0.0) > 0.0


def test_more_locking_means_more_push_at_part_throttle():
    st, loads = _corner()
    mz = []
    for diff in ("open", "lsd", "locked"):
        fx = _fx(diff, 1000.0, st, loads)
        w = {c: WheelForces(fy=0.0, fx=fx[c], alpha=0.0, kappa=0.0, fz=loads[c])
             for c in CORNERS}
        mz.append(DoubleTrackBackend(schema.RV_1).yaw_moment(w, 0.0))
    assert mz[0] > mz[1] > mz[2]


def test_no_wheel_is_asked_for_more_force_than_it_has_grip_for_either_way():
    """A locking device really does drag the outside wheel backwards at part
    throttle, but a contact patch cannot deliver more rearward force than forward."""
    st, loads = _corner()
    b = DoubleTrackBackend(schema.RV_1, diff="locked")
    for demand in (500.0, 1000.0, 3000.0, 6000.0):
        fx = b.differential_forces(demand, loads, st)
        for c in ("rl", "rr"):
            cap = b.DIFF_CAP_FRACTION * float(b._tire.peak_fx(loads[c]))
            assert -cap - 1e-6 <= fx[c] <= cap + 1e-6, (demand, c)


def test_the_effect_mirrors_between_a_left_and_a_right_hand_corner():
    _, loads = _corner()
    v = math.sqrt(9.0 * 40.0)
    left = _fx("locked", 1000.0,
               BicycleState(v_x=v, v_y=0.0, yaw_rate=+v / 40.0, steer=0.0), loads)
    right = _fx("locked", 1000.0,
                BicycleState(v_x=v, v_y=0.0, yaw_rate=-v / 40.0, steer=0.0), loads)
    # loads are the same, so mirroring the corner swaps which wheel is inside
    assert left["rl"] == pytest.approx(right["rr"])
    assert left["rr"] == pytest.approx(right["rl"])


def test_no_device_does_anything_in_a_straight_line():
    """No yaw rate, no speed difference, nothing to resist — which is why a welded
    diff is tolerable on a motorway and awful in a car park."""
    _, loads = _corner(a_y=0.0)
    st = BicycleState(v_x=25.0, v_y=0.0, yaw_rate=0.0, steer=0.0)
    got = [_fx(d, 4000.0, st, loads) for d in ("open", "lsd", "locked")]
    for fx in got:
        assert fx["rl"] == pytest.approx(fx["rr"])
    assert got[0]["rl"] == pytest.approx(got[1]["rl"]) == pytest.approx(got[2]["rl"])


def test_braking_is_not_the_differentials_business():
    st, loads = _corner()
    for diff in ("open", "lsd", "locked"):
        fx = _fx(diff, -8000.0, st, loads)
        assert fx["fl"] == pytest.approx(fx["fr"])
        assert fx["rl"] == pytest.approx(fx["rr"])
        assert fx["fl"] < 0.0 and fx["rl"] < 0.0
