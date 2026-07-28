"""One set of tire formulas, two evaluation backends.

Episode 4 needs the tire model inside a CasADi optimisation, which means the
Magic Formula has to be built out of symbolic operations rather than numpy calls.
The obvious way to get there is to write the equations a second time in CasADi.
**Do not do that.** This project has already spent real time on bugs that came
from two things drifting apart, and a duplicated tire model is the worst possible
place for that: the optimiser would exploit the difference and the result would
look like a finding.

Instead the formulas take an array namespace. Both backends expose the same
handful of operations under the same names, ``physics.tire`` is written against
those names, and ``tests/test_casadi_tire.py`` asserts the two agree to machine
precision across the whole operating envelope.

Naming follows numpy where the two disagree (``arctan`` not ``atan``,
``minimum`` not ``fmin``), because numpy is the default and the common case.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MathKit:
    """The operations the Magic Formula needs, and nothing else."""

    name: str
    arctan: Callable[[Any], Any]
    sin: Callable[[Any], Any]
    cos: Callable[[Any], Any]
    exp: Callable[[Any], Any]
    sqrt: Callable[[Any], Any]
    minimum: Callable[[Any, Any], Any]
    maximum: Callable[[Any, Any], Any]
    abs: Callable[[Any], Any]
    sign: Callable[[Any], Any]

    def clip(self, x, lo, hi):
        return self.minimum(self.maximum(x, lo), hi)


def _numpy_kit() -> MathKit:
    import numpy as np

    return MathKit(
        name="numpy", arctan=np.arctan, sin=np.sin, cos=np.cos, exp=np.exp,
        sqrt=np.sqrt, minimum=np.minimum, maximum=np.maximum, abs=np.abs,
        sign=np.sign,
    )


def _casadi_kit() -> MathKit:
    import casadi as ca

    # CasADi's sign() returns 0 at exactly 0, and the Magic Formula's Ey term
    # multiplies by sign(alpha_y). At alpha_y = 0 that kills the curvature term
    # rather than picking a branch, which is a discontinuity the solver can get
    # stuck on. tanh with a steep slope is a smooth stand-in that agrees with
    # sign() to within 1e-9 for |x| > 1e-8 — far below any slip angle that
    # matters — and gives the optimiser a gradient everywhere.
    def smooth_sign(x):
        return ca.tanh(1e8 * x)

    return MathKit(
        name="casadi", arctan=ca.atan, sin=ca.sin, cos=ca.cos, exp=ca.exp,
        sqrt=ca.sqrt, minimum=ca.fmin, maximum=ca.fmax, abs=ca.fabs,
        sign=smooth_sign,
    )


NUMPY = _numpy_kit()


def casadi_kit() -> MathKit:
    """The CasADi namespace, imported lazily so numpy-only runs stay light."""
    return _casadi_kit()


__all__ = ["MathKit", "NUMPY", "casadi_kit"]
