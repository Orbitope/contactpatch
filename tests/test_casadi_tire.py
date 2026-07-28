"""The CasADi and numpy evaluations of the tire must be the same tire.

Episode 4 puts the Magic Formula inside an optimisation. If the symbolic version
differed from the numpy one — even slightly — the optimiser would find the
difference and exploit it, and the result would look like a finding rather than a
bug. `physics.mathkit` exists so there is one set of formulas; this file is the
proof that the two backends agree over the whole operating envelope.
"""

from __future__ import annotations

import numpy as np
import pytest

from physics import mathkit
from physics.tire import default_tire

ca = pytest.importorskip("casadi")


@pytest.fixture(scope="module")
def tire():
    return default_tire()


@pytest.fixture(scope="module")
def kit():
    return mathkit.casadi_kit()


def _sym(tire, kit, method, *args):
    """Build a CasADi function for one tire method and evaluate it."""
    syms = [ca.SX.sym(f"x{i}") for i in range(len(args))]
    expr = getattr(tire, method)(*syms, xp=kit)
    f = ca.Function("f", syms, [expr])
    return np.array([float(f(*vals)) for vals in zip(*[np.atleast_1d(a) for a in args])])


#: The envelope we actually drive in, plus a margin. Slip angle to +/-15 deg
#: (imposed bound is 12), slip ratio to +/-0.3 (imposed 0.20), load across the
#: file's own declared range.
ALPHAS = np.radians(np.linspace(-15.0, 15.0, 41))
KAPPAS = np.linspace(-0.3, 0.3, 41)
LOADS = np.linspace(300.0, 9500.0, 13)


def test_lateral_force_agrees_across_the_envelope(tire, kit):
    for fz in LOADS:
        ref = np.asarray(tire.fy0(ALPHAS, fz), dtype=float)
        got = _sym(tire, kit, "fy0", ALPHAS, np.full_like(ALPHAS, fz),
                   np.zeros_like(ALPHAS))
        assert np.allclose(got, ref, rtol=1e-9, atol=1e-6), (
            f"lateral force disagrees at Fz={fz:.0f} N, worst "
            f"{np.max(np.abs(got - ref)):.3e} N"
        )


def test_longitudinal_force_agrees_across_the_envelope(tire, kit):
    for fz in LOADS:
        ref = np.asarray(tire.fx0(KAPPAS, fz), dtype=float)
        got = _sym(tire, kit, "fx0", KAPPAS, np.full_like(KAPPAS, fz),
                   np.zeros_like(KAPPAS))
        assert np.allclose(got, ref, rtol=1e-9, atol=1e-6), (
            f"longitudinal force disagrees at Fz={fz:.0f} N, worst "
            f"{np.max(np.abs(got - ref)):.3e} N"
        )


def test_combined_slip_agrees(tire, kit):
    for fz in (1000.0, 3600.0, 7000.0):
        budget = float(tire.peak_fx(fz))
        for frac in (0.0, 0.3, 0.6, 0.9):
            fx = -frac * budget
            ref = np.asarray(tire.fy_combined(ALPHAS, fz, fx), dtype=float)
            got = _sym(tire, kit, "fy_combined", ALPHAS, np.full_like(ALPHAS, fz),
                       np.full_like(ALPHAS, fx), np.zeros_like(ALPHAS))
            assert np.allclose(got, ref, rtol=1e-9, atol=1e-6)


def test_the_smooth_sign_matters_only_at_exactly_zero(tire, kit):
    """The one deliberate difference between the backends, bounded.

    CasADi's ``sign()`` returns 0 at exactly 0, which kills the Ey curvature
    term rather than picking a branch and leaves the solver on a discontinuity.
    We substitute a steep ``tanh``. It must be indistinguishable everywhere a
    slip angle could plausibly sit.
    """
    tiny = np.array([1e-7, 1e-6, 1e-4, 1e-2])
    for fz in (1000.0, 3600.0, 9000.0):
        ref = np.asarray(tire.fy0(tiny, fz), dtype=float)
        got = _sym(tire, kit, "fy0", tiny, np.full_like(tiny, fz),
                   np.zeros_like(tiny))
        assert np.allclose(got, ref, rtol=1e-7, atol=1e-7)


def test_casadi_expressions_are_differentiable(tire, kit):
    """An expression the solver cannot differentiate is useless to it."""
    alpha, fz = ca.SX.sym("alpha"), ca.SX.sym("fz")
    fy = tire.fy0(alpha, fz, 0.0, xp=kit)
    jac = ca.Function("j", [alpha, fz], [ca.jacobian(fy, alpha)])
    # compare against a numpy central difference
    h = 1e-7
    for a in np.radians([-8.0, -2.0, 0.5, 4.0, 11.0]):
        fd = (float(tire.fy0(a + h, 3600.0)) - float(tire.fy0(a - h, 3600.0))) / (2 * h)
        assert float(jac(a, 3600.0)) == pytest.approx(fd, rel=1e-4)


def test_numpy_path_is_untouched_by_the_refactor(tire):
    """The default backend must behave exactly as it did before mathkit existed."""
    assert float(tire.fy0(0.0, 3929.0)) == 0.0
    assert float(tire.fy0(np.radians(4.0), 3929.0)) < 0.0
    assert tire.fy0(ALPHAS, 3929.0).shape == ALPHAS.shape
    assert tire.peak_lateral(3929.0).mu_peak == pytest.approx(1.0489, abs=1e-3)
