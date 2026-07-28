"""Tests for the four-wheel model.

The double-track model's whole job is load bookkeeping, so most of what matters
is arithmetic that must be exact. The rest is the degeneracy relationship with
the bicycle model: two independently written models that must agree in the limit
where the extra term vanishes.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from physics import schema
from physics.bicycle import BicycleBackend, BicycleState
from physics.bicycle import understeer_gradient as ug_bicycle
from physics.double_track import CORNERS, DoubleTrackBackend
from physics.double_track import understeer_gradient as ug_dt

SPEEDS = np.arange(6.0, 18.0, 1.0)


@pytest.fixture(scope="module")
def dt():
    return DoubleTrackBackend()


def test_loads_sum_to_weight_under_any_acceleration(dt):
    for a_x in (-8.0, -3.0, 0.0, 3.0, 8.0):
        for a_y in (-10.0, 0.0, 10.0):
            assert sum(dt.wheel_loads(a_x, a_y).values()) == pytest.approx(
                dt.params.weight, abs=1e-9)


def test_static_loads_are_left_right_symmetric(dt):
    L = dt.wheel_loads()
    assert L["fl"] == pytest.approx(L["fr"])
    assert L["rl"] == pytest.approx(L["rr"])
    assert L["fl"] + L["fr"] == pytest.approx(2 * dt.params.static_fz_front)


def test_left_turn_loads_the_right_hand_wheels(dt):
    L = dt.wheel_loads(0.0, 8.0)
    assert L["fr"] > L["fl"] and L["rr"] > L["rl"]
    R = dt.wheel_loads(0.0, -8.0)
    assert R["fl"] > R["fr"] and R["rl"] > R["rr"]


def test_transfer_scales_exactly_with_height_g_and_inverse_track(dt):
    p = dt.params

    def transfer(b, a_y=6.0):
        L = b.wheel_loads(0.0, a_y)
        return 0.5 * (L["fr"] - L["fl"])

    base = transfer(dt)
    assert transfer(DoubleTrackBackend(replace(p, com_height=2 * p.com_height))) \
        == pytest.approx(2 * base, rel=1e-12)
    assert transfer(dt, a_y=12.0) == pytest.approx(2 * base, rel=1e-12)
    assert transfer(DoubleTrackBackend(replace(p, track_f=2 * p.track_f))) \
        == pytest.approx(0.5 * base, rel=1e-12)


def test_roll_share_divides_the_moment(dt):
    p = dt.params
    L = dt.wheel_loads(0.0, 6.0)
    front = 0.5 * (L["fr"] - L["fl"])
    assert front * p.track_f / (p.mass * 6.0 * p.com_height) == pytest.approx(
        p.roll_stiffness_front_share, rel=1e-12)


def test_wheel_lift_sits_below_the_static_stability_factor(dt):
    assert dt.wheel_lift_a_y() < dt.params.static_stability_factor
    assert dt.wheel_lift_a_y() > dt.max_lateral_g(30.0)   # grip runs out first


def test_a_lifted_wheel_makes_no_force(dt):
    w = dt._wheel("fl", math.radians(5.0), 0.0)
    assert w.fy == 0.0 and w.fz == 0.0


def test_inner_and_outer_slip_angles_differ(dt):
    dt.reset(25.0)
    dt.state.yaw_rate = 0.4
    dt.state.steer = math.radians(3.0)
    a = dt.slip_angles()
    assert a["fl"] != a["fr"]
    assert abs(a["fl"] - a["fr"]) < math.radians(0.5)   # small, but not zero


def test_flat_car_reproduces_the_bicycle_model():
    """The degeneracy test. Regression for FINDINGS F32."""
    flat = replace(schema.RV_1, com_height=1e-6)
    k_dt, _ = ug_dt(DoubleTrackBackend(flat).skidpad_sweep(30.0, SPEEDS))
    k_bi, _ = ug_bicycle(BicycleBackend(flat).skidpad_sweep(30.0, SPEEDS))
    assert k_dt == pytest.approx(k_bi, rel=0.02)
    assert DoubleTrackBackend(flat).max_lateral_g(30.0) == pytest.approx(
        BicycleBackend(flat).max_lateral_g(30.0), rel=0.01)


def test_lateral_transfer_costs_grip(dt):
    """Regression for F33: the whole point of the upgrade."""
    g_dt = dt.max_lateral_g(30.0)
    g_bi = BicycleBackend().max_lateral_g(30.0)
    assert g_dt < g_bi
    assert 0.02 < (g_bi - g_dt) / g_bi < 0.12


def test_stiffer_front_bar_adds_understeer():
    ks = []
    for e in (0.40, 0.50, 0.60, 0.70):
        b = DoubleTrackBackend(replace(schema.RV_1,
                                       roll_stiffness_front_share=e))
        ks.append(ug_dt(b.skidpad_sweep(30.0, SPEEDS))[0])
    assert all(y > x for x, y in zip(ks, ks[1:]))


def test_the_bicycle_model_is_blind_to_the_bar():
    """Regression for F30 — the Episode 5 result."""
    ks = []
    for e in (0.40, 0.55, 0.70):
        b = BicycleBackend(replace(schema.RV_1,
                                   roll_stiffness_front_share=e))
        ks.append(ug_bicycle(b.skidpad_sweep(30.0, SPEEDS))[0])
    assert max(ks) - min(ks) == 0.0


def test_trim_is_an_equilibrium_of_the_derivatives():
    nd = DoubleTrackBackend(replace(schema.RV_1, c_d=0.0))
    pt = nd.trim_skidpad(15.0, 30.0)
    assert pt.converged
    nd._last = {"a_x": pt.a_x, "a_y": pt.a_y}
    st = BicycleState(v_x=15.0, v_y=pt.v_y, yaw_rate=pt.yaw_rate, steer=pt.steer)
    d, a_x, a_y, _ = nd.derivatives(st, pt.drive_force, 0.0)
    assert d.v_y == pytest.approx(0.0, abs=1e-5)
    assert d.yaw_rate == pytest.approx(0.0, abs=1e-5)
    assert d.v_x == pytest.approx(0.0, abs=1e-5)


def test_wheel_log_covers_all_four_corners(dt):
    dt.reset(25.0)
    dt.state.steer = math.radians(3.0)
    act = dt.act_space.pack(steer_rate=0.0, drive_force=-4000.0)
    for _ in range(30):
        dt.step(act, 0.002)
    log = dt.wheel_log()
    assert len(log) == 3 * len(CORNERS)
    for c in CORNERS:
        assert abs(float(dt.wheel_log_space.select(log, f"fz_{c}"))) > 100.0


def test_max_lateral_is_still_in_the_plausibility_band(dt):
    assert 0.90 <= dt.max_lateral_g(30.0) <= 1.10


def test_set_design_validates_roll_share(dt):
    with pytest.raises(AssertionError, match="roll stiffness"):
        dt.set_design(replace(schema.RV_1, roll_stiffness_front_share=1.4))
