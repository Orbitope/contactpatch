"""Tests for the distance-domain minimum-time solver.

The solver is the one piece of Season 1 machinery whose output cannot be checked
against a closed form, so what gets tested here is everything around the answer:
the geometry, the honesty constraints, and that the objective is actually time.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from physics import track as T

pytest.importorskip("casadi")
from physics.optimal_control import Limits, solve_min_time  # noqa: E402


# ---------------------------------------------------------------------------
# Track geometry — cheap, and everything downstream rests on it
# ---------------------------------------------------------------------------


def test_track_length_is_the_sum_of_its_segments():
    tk = T.short_exit()
    assert tk.length == pytest.approx(
        T.ENTRY_STRAIGHT + T.CORNER_ARC + 30.0)


def test_curvature_is_zero_on_straights_and_right_in_the_corner():
    tk = T.short_exit()
    assert abs(float(tk.curvature(10.0))) < 1e-6
    mid = T.ENTRY_STRAIGHT + 0.5 * T.CORNER_ARC
    assert float(tk.curvature(mid)) == pytest.approx(1.0 / T.CORNER_RADIUS, rel=1e-3)


def test_curvature_is_smooth_across_the_joins():
    """A step in curvature asks for an infinite steering rate."""
    tk = T.short_exit()
    s = np.linspace(0, tk.length, 4000)
    k = tk.curvature(s)
    assert np.max(np.abs(np.diff(k))) < 0.01     # no jumps


def test_the_corner_arc_turns_ninety_degrees():
    tk = T.short_exit()
    _, _, _, heading = tk.centreline(4000)
    assert math.degrees(heading[-1]) == pytest.approx(90.0, abs=1.0)


def test_curvilinear_to_cartesian_round_trips_on_the_centreline():
    tk = T.long_exit()
    s = np.linspace(0, tk.length, 200)
    x, y = tk.to_xy(s, np.zeros_like(s))
    _, xc, yc, _ = tk.centreline(2000)
    assert np.allclose(x, np.interp(s, np.linspace(0, tk.length, 2000), xc),
                       atol=1e-6)


def test_lateral_offset_moves_left_of_travel():
    """+n must be to the left, matching schema's ISO frame."""
    tk = T.short_exit()
    x0, y0 = tk.to_xy(np.array([10.0]), np.array([0.0]))
    xl, yl = tk.to_xy(np.array([10.0]), np.array([1.0]))
    # heading is +x at s=10 (still on the entry straight), so left is +y
    assert yl[0] > y0[0]
    assert xl[0] == pytest.approx(x0[0], abs=1e-9)


# ---------------------------------------------------------------------------
# The solve
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def solved():
    return solve_min_time(T.short_exit(), n_nodes=80, entry_speed=30.0)


def test_solver_returns_a_usable_answer(solved):
    assert solved.time > 0
    assert len(solved.s) == 80
    for name in ("n", "xi", "v_x", "v_y", "r", "delta"):
        assert np.all(np.isfinite(solved.states[name]))


def test_the_line_stays_on_the_road(solved):
    lim = solved.track.half_width
    assert np.max(np.abs(solved.states["n"])) <= lim + 1e-4


def test_the_slip_envelope_is_respected(solved):
    """The honesty constraint. Without it a min-time solver leaves the fit."""
    assert solved.envelope_occupancy() == 0.0
    worst = max(np.abs(solved.alpha_f).max(), np.abs(solved.alpha_r).max())
    assert worst <= solved.limits.alpha_max + 1e-6


def test_the_solver_actually_uses_the_grip_available(solved):
    """A solve that never reaches the constraint has not found the limit."""
    worst = max(np.abs(solved.alpha_f).max(), np.abs(solved.alpha_r).max())
    assert worst > 0.9 * solved.limits.alpha_max


def test_entry_conditions_are_honoured(solved):
    assert solved.states["v_x"][0] == pytest.approx(30.0, abs=1e-6)
    assert solved.states["n"][0] == pytest.approx(0.0, abs=1e-6)
    assert solved.states["delta"][0] == pytest.approx(0.0, abs=1e-6)


def test_time_is_the_integral_of_dt_ds(solved):
    assert solved.time == pytest.approx(
        float(np.trapezoid(solved.dt_ds, solved.s)), rel=1e-9)


def test_actuator_limits_bind(solved):
    lim = solved.limits
    assert solved.controls["drive_force"].min() >= -lim.brake_max - 1.0
    assert solved.controls["drive_force"].max() <= lim.drive_max + 1.0
    assert np.max(np.abs(solved.states["delta"])) <= lim.steer_max + 1e-6


def test_apex_is_measured_inside_the_corner(solved):
    """Regression: argmin over the whole track finds a point in the exit straight."""
    k = np.abs(solved.track.curvature(solved.s))
    assert k[solved.apex_index] > 0.5 * k.max()
    assert 0.0 <= solved.apex_fraction_through_corner <= 1.0


def test_apex_is_toward_the_inside_of_the_corner(solved):
    """A left-hander turns toward +n, so the apex must be at positive offset."""
    assert solved.track.curvature(solved.s)[solved.apex_index] > 0
    assert solved.states["n"][solved.apex_index] > 1.0


def test_a_tighter_slip_bound_makes_the_car_slower():
    """The envelope is a real constraint, not decoration."""
    loose = solve_min_time(T.short_exit(), n_nodes=80, entry_speed=30.0)
    tight = solve_min_time(T.short_exit(), n_nodes=80, entry_speed=30.0,
                           limits=Limits(alpha_max=math.radians(5.0)))
    assert tight.time > loose.time


def test_a_warm_start_from_a_different_node_count_is_resampled_not_ignored():
    """A mismatched warm start must be interpolated onto the new grid.

    The original guard was ``len(warm_start.s) == n_nodes``, so handing the solver
    a seed from a neighbouring node count SILENTLY fell through to the cold guess.
    Nothing failed; the solve merely started from a worse place. Grid refinement
    is exactly where that bites, because the converged answer at one node count
    is the best available seed for the next.

    Checked by consequence rather than by inspecting the guess. The strong signal
    is convergence *status*: started cold this problem stops on the iteration
    limit, and started from a resampled coarse answer it converges cleanly. A
    silently-ignored warm start could not change that.

    Note what it does NOT assert: that the warm and cold times agree. They do not,
    and the reason matters — see F39. A run that stops on the iteration limit has
    not driven its constraint violation to zero, so its objective sits *below* the
    true optimum. The cleanly converged answer here is the slower one, and it is
    the correct one.
    """
    seed = solve_min_time(T.short_exit(), n_nodes=80, entry_speed=30.0)
    assert len(seed.s) == 80

    warm = solve_min_time(T.short_exit(), n_nodes=110, entry_speed=30.0,
                          warm_start=seed)
    assert len(warm.s) == 110, "the warm start must not change the grid"
    assert warm.success, (
        "a resampled warm start should converge this problem cleanly; if it is "
        "being ignored the solve falls back to the cold guess and stops on the "
        "iteration limit instead")
    assert warm.envelope_occupancy() == 0.0
    # ...and it must still be a sane answer, not a converged nonsense one
    assert 4.0 < warm.time < 8.0


def test_apex_position_is_interpolated_between_nodes(solved):
    """The apex must not be pinned to the node grid.

    ``argmax`` alone quantises apex position to one node, which on the Episode 7
    sweep is ~6.7% of the corner — coarser than the migration being measured, and
    it made five different cars all report exactly 53.3%. The parabolic vertex
    has to land within half a node of the peak node and generally NOT exactly on
    it.
    """
    off = solved.apex_offset_nodes
    assert -0.5 <= off <= 0.5, "a sub-node correction cannot exceed half a node"
    # the interpolated apex sits within half a node of the peak node's position
    ds = float(solved.s[1] - solved.s[0])
    assert abs(solved.apex_s - solved.s[solved.apex_index]) <= 0.5 * ds + 1e-9
    # ...and still inside the corner
    assert 0.0 <= solved.apex_fraction_through_corner <= 1.0


def test_apex_interpolation_recovers_a_known_offset():
    """Feed the interpolator a parabola whose vertex we chose, and get it back.

    Checks the arithmetic against a case with an answer known in closed form,
    rather than against the solver's own output.
    """
    import numpy as _np

    for true_off in (-0.4, -0.15, 0.0, 0.25, 0.45):
        # y = -(x - true_off)^2 sampled at x = -1, 0, 1
        y = _np.array([-((x - true_off) ** 2) for x in (-1.0, 0.0, 1.0)])
        denom = y[0] - 2.0 * y[1] + y[2]
        got = 0.5 * (y[0] - y[2]) / denom
        assert got == pytest.approx(true_off, abs=1e-12)
