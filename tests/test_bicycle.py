"""Unit tests for the bicycle model's plumbing — the parts D2/D3 do not cover."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from physics import schema
from physics.bicycle import BicycleBackend, BicycleState, understeer_gradient


@pytest.fixture(scope="module")
def b():
    return BicycleBackend()


def test_reset_refuses_speeds_where_slip_angle_is_meaningless(b):
    with pytest.raises(ValueError, match="MIN_SPEED"):
        b.reset(0.5)


def test_obs_and_log_match_their_declared_spaces(b):
    obs = b.reset(20.0)
    assert obs.shape == (len(b.obs_space),)
    assert b.wheel_log().shape == (len(b.wheel_log_space),)
    assert b.obs_space.select(obs, "v_x") == pytest.approx(20.0)


def test_axle_loads_conserve_weight_at_any_acceleration(b):
    for a_x in (-9.0, -3.0, 0.0, 3.0, 9.0):
        f, r = b.axle_loads(a_x)
        assert f + r == pytest.approx(b.params.weight)


def test_kappa_inversion_returns_the_demanded_force(b):
    fz = 3600.0
    for fx in (-2000.0, -500.0, 0.0, 800.0, 2500.0):
        k = b._kappa_for(fx, fz)
        assert float(b.tire.fx0(k, fz)) == pytest.approx(fx, abs=1.0)


def test_kappa_inversion_clamps_at_the_imposed_envelope(b):
    k = b._kappa_for(1e6, 3600.0)
    assert k == pytest.approx(b.envelope.imposed_kappa_max)


def test_slip_angles_are_zero_running_straight(b):
    b.reset(25.0)
    assert b.slip_angles() == (pytest.approx(0.0), pytest.approx(0.0))


def test_steering_left_gives_negative_front_slip(b):
    b.reset(25.0)
    b.state.steer = math.radians(2.0)
    alpha_f, alpha_r = b.slip_angles()
    assert alpha_f < 0 and alpha_r == pytest.approx(0.0)


def test_trim_reproduces_ackermann_at_negligible_speed(b):
    pt = b.trim_skidpad(5.0, 60.0)
    assert pt.converged
    assert pt.steer == pytest.approx(pt.ackermann, rel=0.01)


@pytest.mark.parametrize("hold_speed", [True, False])
def test_trim_is_an_equilibrium_of_the_derivatives(hold_speed):
    nd = BicycleBackend(replace(schema.RV_1, c_d=0.0))
    pt = nd.trim_skidpad(15.0, 30.0, hold_speed=hold_speed)
    nd._last["a_x"] = pt.a_x
    st = BicycleState(v_x=15.0, v_y=pt.v_y, yaw_rate=pt.yaw_rate, steer=pt.steer)
    d, a_x, _, _, _ = nd.derivatives(st, pt.drive_force, 0.0)
    assert d.v_y == pytest.approx(0.0, abs=1e-6)
    assert d.yaw_rate == pytest.approx(0.0, abs=1e-6)
    assert a_x == pytest.approx(pt.a_x, abs=1e-6)


def test_protocol_changes_the_measured_balance():
    """Regression for FINDINGS F17.

    Holding speed and coasting are different experiments, not rounding. Coasting
    lets the steered front tire decelerate the car, which shifts load forward,
    unloads the rear and inverts the terminal balance.
    """
    b = BicycleBackend()
    sp = np.arange(5.0, 19.0, 0.5)
    held = [p for p in b.skidpad_sweep(30.0, sp, hold_speed=True) if p.converged]
    coast = [p for p in b.skidpad_sweep(30.0, sp, hold_speed=False) if p.converged]
    k_held, _ = understeer_gradient(held)
    k_coast, _ = understeer_gradient(coast)
    assert k_held > k_coast * 1.10                      # materially different
    # "Holding speed" means dv_x/dt = 0, which needs a_x = -v_y*r, not a_x = 0.
    # Its SIGN flips with sideslip: at low speed the nose points out of the
    # corner (v_y > 0) and a_x is negative; past the crossover it reverses.
    assert all(p.a_x == pytest.approx(-p.v_y * p.yaw_rate, rel=1e-6) for p in held)
    assert any(p.a_x < 0 for p in held) and any(p.a_x > 0 for p in held)
    assert all(p.a_x < 0.0 for p in coast)              # coasting always decelerates
    # understeer survives to the limit only under the correct protocol
    und_h = [p.understeer_angle_deg for p in held]
    und_c = [p.understeer_angle_deg for p in coast]
    assert und_h.index(max(und_h)) == len(und_h) - 1
    assert und_c.index(max(und_c)) < len(und_c) - 1


def test_load_transfer_uses_force_not_dvx_dt():
    """Regression for FINDINGS F14.

    Load transfer follows the centre of mass's body-axis acceleration, Fx/m. If
    the centripetal term v_y*r leaks in, a cornering car appears to decelerate
    several times harder than it does.
    """
    nd = BicycleBackend(replace(schema.RV_1, c_d=0.0))
    pt = nd.trim_skidpad(17.0, 30.0)
    st = BicycleState(v_x=17.0, v_y=pt.v_y, yaw_rate=pt.yaw_rate, steer=pt.steer)
    _, a_x, _, front, _ = nd.derivatives(st, 0.0, 0.0)
    expected = -front.fy * math.sin(pt.steer) / nd.params.mass
    assert a_x == pytest.approx(expected, rel=1e-6)
    assert abs(a_x - (expected + pt.v_y * pt.yaw_rate)) > 1e-3  # the wrong answer


def test_sweep_marks_points_past_the_limit_as_unconverged(b):
    pts = b.skidpad_sweep(30.0, np.arange(15.0, 22.0, 0.5))
    assert any(p.converged for p in pts) and any(not p.converged for p in pts)


def test_max_lateral_g_is_inside_the_plausibility_band(b):
    assert 0.95 <= b.max_lateral_g(30.0) <= 1.10


def test_understeer_gradient_needs_enough_points(b):
    with pytest.raises(ValueError, match="need >= 3"):
        understeer_gradient(b.skidpad_sweep(30.0, [17.0]))


def test_zero_load_axle_makes_no_force(b):
    forces = b._axle(math.radians(5.0), 0.0)
    assert forces.fy == 0.0 and forces.fz_per_tire == 0.0


def test_set_design_validates(b):
    with pytest.raises(AssertionError):
        b.set_design(replace(schema.RV_1, front_mass_fraction=1.5))


# ---------------------------------------------------------------------------
# Combined slip — the friction ellipse (FINDINGS D9, closes O2)
# ---------------------------------------------------------------------------


def test_friction_ellipse_costs_lateral_grip(b):
    fz, alpha = 3600.0, math.radians(5.0)
    pure = abs(float(b.tire.fy0(alpha, fz)))
    budget = float(b.tire.peak_fx(fz))
    last = pure + 1
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        got = abs(float(b.tire.fy_combined(alpha, fz, -frac * budget)))
        assert got < last                      # strictly decreasing
        assert got == pytest.approx(
            pure * math.sqrt(max(1 - frac**2, 1e-6)), rel=1e-9)
        last = got


def test_friction_ellipse_is_symmetric_in_braking_and_driving(b):
    fz, alpha = 3600.0, math.radians(4.0)
    for fx in (500.0, 2000.0):
        assert float(b.tire.fy_combined(alpha, fz, fx)) == pytest.approx(
            float(b.tire.fy_combined(alpha, fz, -fx)))


def test_over_budget_longitudinal_force_leaves_a_negligible_floor(b):
    """A saturated tire keeps 0.1% of its lateral force, not exactly zero.

    sqrt(0) has an infinite derivative, which is a NaN in the Jacobian the
    moment an optimiser asks a fully-braked tire for cornering force. The
    radicand is floored at 1e-6 instead — see MF02Tire.fy_combined.
    """
    pure = abs(float(b.tire.fy0(math.radians(5.0), 3600.0)))
    got = abs(float(b.tire.fy_combined(math.radians(5.0), 3600.0, 1e6)))
    assert got == pytest.approx(pure * 1e-3, rel=1e-6)
    assert got < 0.002 * pure


def test_peak_force_helpers_match_the_swept_values(b):
    for fz in (1000.0, 3929.0, 9000.0):
        assert float(b.tire.peak_fy(fz)) == pytest.approx(
            b.tire.peak_lateral(fz).fy_peak, rel=1e-9)
        assert float(b.tire.peak_fx(fz)) == pytest.approx(
            b.tire.peak_longitudinal(fz)[0] * fz, rel=2e-3)


def test_combined_slip_nudges_a_rwd_car_toward_oversteer():
    """The throttle that holds skidpad speed costs the REAR axle grip.

    Less rear grip is less understeer, so the car needs slightly LESS steering,
    not more — power oversteer in miniature. Tiny here because the drive force is
    only a few percent of the axle's longitudinal budget.
    """
    on = BicycleBackend(combined_slip=True).trim_skidpad(16.0, 30.0)
    off = BicycleBackend(combined_slip=False).trim_skidpad(16.0, 30.0)
    assert on.converged and off.converged
    assert on.drive_force > 0.0
    assert on.steer < off.steer
    assert abs(on.steer_deg - off.steer_deg) < 0.1     # and it is a small effect
    assert 0.0 < on.drive_force_fraction < 0.15


def test_braking_is_split_across_both_axles_by_the_bias():
    bb = BicycleBackend(brake_bias=0.7)
    bb.reset(25.0)
    d, a_x, _, front, rear = bb.derivatives(bb.state, -4000.0, 0.0)
    assert front.fx == pytest.approx(-2800.0)
    assert rear.fx == pytest.approx(-1200.0)
    assert a_x < 0.0


def test_trim_holds_speed_exactly():
    """dv_x/dt must be zero at a constant-speed trim, not merely Fx/m.

    Regression for the audit finding: forcing Fx/m = 0 leaves
    dv_x/dt = v_y*r, the car slowly changes speed, and it drifts 0.19% off the
    commanded radius over a single lap.
    """
    nd = BicycleBackend(replace(schema.RV_1, c_d=0.0))
    pt = nd.trim_skidpad(15.0, 30.0, hold_speed=True)
    st = BicycleState(v_x=15.0, v_y=pt.v_y, yaw_rate=pt.yaw_rate, steer=pt.steer)
    nd._last["a_x"] = pt.a_x
    d, _, _, _, _ = nd.derivatives(st, pt.drive_force, 0.0)
    assert d.v_x == pytest.approx(0.0, abs=1e-9)
    assert pt.a_x == pytest.approx(-pt.v_y * pt.yaw_rate, rel=1e-6)


def test_the_car_actually_drives_the_commanded_circle():
    """Validates the pose integration, which nothing else touches.

    If x/y/heading were wrong, every trajectory figure and every lap time from
    Episode 4 on would be wrong and no other check would notice.
    """
    nd = BicycleBackend(replace(schema.RV_1, c_d=0.0))
    R, V = 30.0, 15.0
    pt = nd.trim_skidpad(V, R)
    nd.reset(V)
    nd.state = BicycleState(v_x=V, v_y=pt.v_y, yaw_rate=pt.yaw_rate, steer=pt.steer)
    nd._last["a_x"] = pt.a_x
    act = nd.act_space.pack(steer_rate=0.0, drive_force=pt.drive_force)
    xs, ys = [], []
    for _ in range(int((2 * math.pi * R / V) / 0.001)):
        _, info = nd.step(act, 0.001)
        xs.append(info.position[0])
        ys.append(info.position[1])
    xs, ys = np.array(xs), np.array(ys)
    A = np.c_[2 * xs, 2 * ys, np.ones(len(xs))]
    sol, *_ = np.linalg.lstsq(A, xs**2 + ys**2, rcond=None)
    radii = np.hypot(xs - sol[0], ys - sol[1])
    assert math.sqrt(sol[2] + sol[0]**2 + sol[1]**2) == pytest.approx(R, rel=1e-4)
    assert float(radii.max() - radii.min()) < 1e-6      # a circle, not a spiral
    assert math.degrees(nd.state.heading) == pytest.approx(360.0, abs=0.05)
    assert nd.state.v_x == pytest.approx(V, abs=1e-9)


def test_wheel_log_reports_real_slip_ratios(b):
    """Regression: it used to hardcode kappa = 0.

    Backend.envelope_violated() defaults to this accessor, so a zeroed channel
    made slip-ratio envelope violations invisible — and envelope occupancy is
    what decides whether a lap time counts at all (non-negotiable #1).
    """
    bb = BicycleBackend()
    bb.reset(25.0)
    bb.state.steer = math.radians(4.0)
    act = bb.act_space.pack(steer_rate=0.0, drive_force=-6000.0)
    for _ in range(50):
        bb.step(act, 0.002)
    log = bb.wheel_log()
    assert abs(float(bb.wheel_log_space.select(log, "kappa_f"))) > 1e-3
    assert abs(float(bb.wheel_log_space.select(log, "kappa_r"))) > 1e-3
    # and a genuinely over-the-bound slip ratio must be flagged
    bb.wheel_log_space  # noqa
    over = bb.wheel_log_space.pack(
        alpha_f=0.0, kappa_f=0.9, fz_f=3600.0,
        alpha_r=0.0, kappa_r=0.0, fz_r=3600.0)
    assert bb.envelope_violated(over)


def test_fresh_backend_reports_zero_slip_ratio(b):
    bb = BicycleBackend()
    bb.reset(20.0)
    assert float(bb.wheel_log_space.select(bb.wheel_log(), "kappa_f")) == 0.0
    assert not bb.envelope_violated()
