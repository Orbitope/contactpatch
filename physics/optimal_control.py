"""Minimum-time optimal control in the distance domain, via CasADi/IPOPT.

Given a track and the bicycle model, find the control history that gets from one
end to the other in the least time. The answer is a racing line — but nobody
told it what a racing line looks like. It comes out of the tire model and the
track width and nothing else.

Why the distance domain
-----------------------
The obvious formulation discretises *time*, but then the finish line arrives at
an unknown index and the track boundary constraint has to be interpolated. In the
distance domain the grid is fixed — one node every few metres of track — the
boundary constraint is pointwise, and total time becomes the objective integral::

    dt/ds = (1 - n*kappa) / (v_x cos(xi) - v_y sin(xi))

State (curvilinear, Frenet frame on the centreline):

=========  =====================================================
``n``      lateral offset of the centre of mass from the centreline, m, +left
``xi``     heading of the car relative to the path tangent, rad
``v_x``    longitudinal velocity, body frame, m/s
``v_y``    lateral velocity, body frame, m/s
``r``      yaw rate, rad/s
``delta``  road-wheel steer angle, rad
=========  =====================================================

Controls are steer *rate* and longitudinal force demand, so the steer angle is a
state and cannot jump. That matters: an unconstrained steer angle lets the
optimiser produce lines no driver could execute.

What is enforced
----------------
Track edges, the tire's own load range, and **our imposed slip envelope** —
±12° of slip angle and ±0.20 of slip ratio. That last one is the honesty
constraint: without it a minimum-time solver will happily drive at 30° of slip
where the tire model is extrapolating, and return a lap time that is a statement
about our curve fit rather than about a car.

The tire model is the same one everything else uses, evaluated through
:mod:`physics.mathkit`'s CasADi backend. ``tests/test_casadi_tire.py`` asserts
the two backends agree.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import schema
from .mathkit import casadi_kit
from .tire import MF02Tire, default_tire
from .track import Track

#: Diagnostic hook for attributing lap-time or convergence changes to the F72/F73
#: yaw-moment fix. When True the FOUR-WHEEL model restores the superseded moment
#: expression, which disagreed with the force equations. **Never set for a published
#: solve.** It exists so "did the fix change this?" is answerable by A/B rather than
#: by argument — F79 is the entry that needed it.
_LEGACY_YAW_MOMENT = False

N_STATES = 6
STATE_NAMES = ("n", "xi", "v_x", "v_y", "r", "delta")
CONTROL_NAMES = ("steer_rate", "drive_force")


@dataclass
class Limits:
    """Actuator and honesty limits. Every one of these is a modelling choice."""

    #: Peak drive force at the wheels, N. 250 N.m of engine torque through a
    #: first-gear-ish overall ratio; [ASSUMED], and generous.
    drive_max: float = 4500.0
    #: Peak braking force, N. About 1.1 g of deceleration — a road car on good
    #: tires. [ASSUMED]
    brake_max: float = 15000.0
    steer_max: float = math.radians(30.0)
    steer_rate_max: float = math.radians(200.0)
    v_min: float = 8.0
    v_max: float = 70.0
    #: Ours, not the tire file's. See FINDINGS and schema.TireEnvelope.
    alpha_max: float = math.radians(12.0)
    kappa_max: float = 0.20


@dataclass
class Solution:
    """A solved line, plus everything needed to judge whether to believe it."""

    track: Track
    s: np.ndarray
    states: dict[str, np.ndarray]
    controls: dict[str, np.ndarray]
    time: float
    dt_ds: np.ndarray
    a_x: np.ndarray
    a_y: np.ndarray
    alpha_f: np.ndarray
    alpha_r: np.ndarray
    fz_f: np.ndarray
    fz_r: np.ndarray
    success: bool
    solver_status: str
    limits: Limits
    #: Four-wheel path only: per-corner load, slip angle, forces and
    #: friction-circle utilisation along the whole solve. ``None`` for the
    #: bicycle model, which has no left and right to report.
    per_wheel: dict | None = None
    meta: dict = field(default_factory=dict)

    @property
    def speed(self) -> np.ndarray:
        return np.hypot(self.states["v_x"], self.states["v_y"])

    @property
    def corner_mask(self) -> np.ndarray:
        """Nodes inside the curved part of the track.

        The apex has to be measured here and not over the whole track. On a
        straight the car can drift to the inside edge for free, so a plain
        ``argmin`` over lateral offset finds a point in the exit straight and
        calls it the apex.
        """
        k = np.abs(self.track.curvature(self.s))
        return k > 0.5 * k.max()

    @property
    def apex_index(self) -> int:
        """Where the car is closest to the inside edge, within the corner.

        Defined on lateral offset rather than minimum speed: the two usually
        coincide, and "the apex moved" is a claim about position.
        """
        mask = self.corner_mask
        idx = np.where(mask)[0]
        turn_left = self.track.curvature(self.s)[mask].mean() > 0
        inner = self.states["n"][mask]
        return int(idx[np.argmax(inner) if turn_left else np.argmin(inner)])

    @property
    def apex_offset_nodes(self) -> float:
        """Sub-node correction to ``apex_index``, in node widths, range ±0.5.

        ``apex_index`` is an ``argmax`` over nodes, so on its own the apex can
        only ever land *on* a node. With 100 nodes over this track the corner gets
        about 16 of them, which quantises apex position to ~6.7% of the corner —
        coarser than the effect Episode 7 is trying to measure, and it showed up
        as five different balance settings all reporting exactly 53.3%.

        A parabola through the peak node and its two neighbours has its vertex at
        this offset. Standard three-point peak interpolation, and it is a metric
        computed downstream from the logged arrays rather than anything the solver
        has to know about (CLAUDE.md rule 7).
        """
        k = self.apex_index
        n = self.states["n"]
        if k <= 0 or k >= len(n) - 1:
            return 0.0
        turn_left = self.track.curvature(self.s)[self.corner_mask].mean() > 0
        y0, y1, y2 = (n[k - 1], n[k], n[k + 1]) if turn_left else (
            -n[k - 1], -n[k], -n[k + 1])
        denom = y0 - 2.0 * y1 + y2
        if abs(denom) < 1e-12:
            return 0.0
        off = 0.5 * (y0 - y2) / denom
        # a genuine interior peak cannot be more than half a node away
        return float(off) if abs(off) <= 0.5 else 0.0

    @property
    def apex_fraction_through_corner(self) -> float:
        """0 = corner entry, 1 = corner exit, interpolated between nodes."""
        idx = np.where(self.corner_mask)[0]
        span = max(idx[-1] - idx[0], 1)
        pos = (self.apex_index + self.apex_offset_nodes) - idx[0]
        return float(min(max(pos / span, 0.0), 1.0))

    @property
    def apex_s(self) -> float:
        ds = float(self.s[1] - self.s[0])
        return float(self.s[self.apex_index] + self.apex_offset_nodes * ds)

    def envelope_occupancy(self) -> float:
        """Fraction of nodes outside the imposed envelope. Should be 0."""
        bad = ((np.abs(self.alpha_f) > self.limits.alpha_max + 1e-6)
               | (np.abs(self.alpha_r) > self.limits.alpha_max + 1e-6))
        return float(bad.mean())


def solve_min_time(track: Track, params: schema.VehicleParams | None = None,
                   tire: MF02Tire | None = None, n_nodes: int = 240,
                   limits: Limits | None = None,
                   entry_speed: float | None = None,
                   warm_start: Solution | None = None,
                   four_wheel: bool = False,
                   diff: str = "open",
                   max_iter: int = 2000,
                   steer_rate_weight: float = 0.0,
                   print_level: int = 0) -> Solution:
    """Minimum-time traverse of ``track``. Trapezoidal collocation, IPOPT.

    ``entry_speed`` fixes the speed at the start line; leaving it ``None`` lets
    the optimiser choose, which makes the corner-entry phase meaningless (it
    would arrive at whatever speed suits it). Episode 4 fixes it.

    ``warm_start`` seeds from a previous solution — the mechanism that makes
    design sweeps cheap later.

    ``four_wheel`` switches from the bicycle model to the double-track one, which
    is what Episode 6 needs: per-wheel friction-circle usage only exists if there
    are four wheels, and so does the drivetrain question, because "which axle
    receives drive torque" is meaningless when both are the same wheel.

    ``diff`` selects the differential, and it is not a detail. ``"open"`` splits
    drive torque 50/50 between the driven wheels, so with each wheel capped at its
    own capability the pair is limited by **twice the weaker wheel** — and in a
    corner the inside wheel is nearly unloaded. ``"ideal"`` lets the split float,
    which is the best a limited-slip differential could ever do. The reference car
    has a factory LSD, so the truth is between them, and the gap between the two
    is what Episode 12 is about. Episode 6 reports both, because a drivetrain
    comparison run on cars crippled by their differentials is not a drivetrain
    comparison.

    The four-wheel path carries the centre-of-mass accelerations as **algebraic
    variables** with equality constraints, rather than computing them. Lateral
    load transfer depends on ``a_y``, and ``a_y`` depends on the forces the
    transferred loads produce — implicit. The time-domain model closes that with
    a fixed-point loop; inside an NLP the honest equivalent is a variable and a
    constraint, which IPOPT solves simultaneously and exactly.
    """
    import casadi as ca

    xp = casadi_kit()
    p = params if params is not None else schema.RV_1
    p.check()
    tyre = tire if tire is not None else default_tire()
    lim = limits if limits is not None else Limits()

    s_grid = np.linspace(0.0, track.length, n_nodes)
    ds = float(s_grid[1] - s_grid[0])
    kappa = track.curvature(s_grid)
    n_lim = track.half_width

    opti = ca.Opti()
    X = opti.variable(N_STATES, n_nodes)
    U = opti.variable(2, n_nodes)

    n, xi, v_x, v_y, r, delta = (X[i, :] for i in range(N_STATES))
    steer_rate, drive = U[0, :], U[1, :]
    # Algebraic centre-of-mass accelerations, four-wheel path only. See the
    # docstring: lateral load transfer is implicit in a_y.
    Z = opti.variable(2, n_nodes) if four_wheel else None
    # Fraction of drive torque sent to the LEFT driven wheel. Fixed at 0.5
    # for an open differential; a free variable for an ideal one.
    Ud = opti.variable(1, n_nodes) if (four_wheel and diff == "ideal") \
        else None

    def dynamics(k):
        """State derivatives with respect to DISTANCE at node ``k``."""
        nk, xik = X[0, k], X[1, k]
        vxk, vyk, rk, dk = X[2, k], X[3, k], X[4, k], X[5, k]
        # U[1] carries the longitudinal force in KILONEWTONS. Newtons put a
        # variable of order 1e4 next to angles of order 1e-1, and IPOPT then
        # spends thousands of iterations oscillating at a tolerance it cannot
        # reach. Scaling it is worth more than any solver option.
        sr, fx_total = U[0, k], U[1, k] * 1000.0

        # slip angles, same definition as physics.bicycle
        vy_f = vyk + p.a * rk
        alpha_f = ca.atan2(vy_f * ca.cos(dk) - vxk * ca.sin(dk),
                           vxk * ca.cos(dk) + vy_f * ca.sin(dk))
        alpha_r = ca.atan2(vyk - p.b * rk, vxk)

        # longitudinal load transfer uses the centre of mass's body-x
        # acceleration, Fx/m -- see FINDINGS F14. Solved as a fixed point in the
        # time-domain model; here it is one explicit pass, which is enough
        # because the coupling is weak and the collocation constraint closes it.
        fx_f = fx_total * 0.65 * (0.5 - 0.5 * ca.tanh(1e3 * fx_total))
        fx_r = fx_total - fx_f
        drag = 0.5 * 1.225 * p.c_d * p.frontal_area * vxk * vxk
        a_x_guess = (-drag) / p.mass
        fz_f = p.weight * p.b / p.wheelbase - p.mass * a_x_guess * p.com_height / p.wheelbase
        fz_r = p.weight * p.a / p.wheelbase + p.mass * a_x_guess * p.com_height / p.wheelbase

        fy_f = 2.0 * tyre.fy_combined(alpha_f, fz_f / 2.0, fx_f / 2.0, 0.0, xp)
        fy_r = 2.0 * tyre.fy_combined(alpha_r, fz_r / 2.0, fx_r / 2.0, 0.0, xp)

        fx_body = fx_f * ca.cos(dk) - fy_f * ca.sin(dk) + fx_r - drag
        fy_body = fy_f * ca.cos(dk) + fx_f * ca.sin(dk) + fy_r
        a_x, a_y = fx_body / p.mass, fy_body / p.mass
        # Two-axle model: no left/right, so there is no drivetrain yaw term and no
        # steering-drag term to have. Both are identically zero here. The
        # four-wheel model is where they live (F72, F73).
        m_z = p.a * (fy_f * ca.cos(dk) + fx_f * ca.sin(dk)) - p.b * fy_r

        s_dot = (vxk * ca.cos(xik) - vyk * ca.sin(xik)) / (1.0 - nk * kappa[k])
        dt_ds = 1.0 / s_dot

        dn = (vxk * ca.sin(xik) + vyk * ca.cos(xik)) * dt_ds
        dxi = rk * dt_ds - kappa[k]
        dvx = (a_x + vyk * rk) * dt_ds
        dvy = (a_y - vxk * rk) * dt_ds
        dr = (m_z / p.i_zz) * dt_ds
        ddelta = sr * dt_ds
        return (ca.vertcat(dn, dxi, dvx, dvy, dr, ddelta), dt_ds,
                alpha_f, alpha_r, fz_f, fz_r, a_x, a_y)

    def dynamics_4w(k):
        """Four-wheel dynamics at node ``k``. Returns the same tuple as the
        two-wheel version so everything downstream is unchanged."""
        nk, xik = X[0, k], X[1, k]
        vxk, vyk, rk, dk = X[2, k], X[3, k], X[4, k], X[5, k]
        sr, fx_total = U[0, k], U[1, k] * 1000.0
        a_x, a_y = Z[0, k], Z[1, k]

        # loads: longitudinal transfer between axles, lateral between sides,
        # divided by roll stiffness. Identical algebra to double_track.py.
        axle_f = (p.weight * p.b / p.wheelbase
                  - p.mass * a_x * p.com_height / p.wheelbase)
        axle_r = (p.weight * p.a / p.wheelbase
                  + p.mass * a_x * p.com_height / p.wheelbase)
        moment = p.mass * a_y * p.com_height
        eps = p.roll_stiffness_front_share
        d_f = eps * moment / p.track_f
        d_r = (1.0 - eps) * moment / p.track_r
        fz = {"fl": 0.5 * axle_f - d_f, "fr": 0.5 * axle_f + d_f,
              "rl": 0.5 * axle_r - d_r, "rr": 0.5 * axle_r + d_r}

        # braking acts on all four by bias; drive only on the driven axle
        brake_frac = 0.5 - 0.5 * ca.tanh(1e3 * fx_total)     # 1 when braking
        drive_frac = 1.0 - brake_frac
        split = Ud[0, k] if Ud is not None else 0.5
        fx = {}
        for c in ("fl", "fr", "rl", "rr"):
            bias = 0.65 if c[0] == "f" else 0.35
            driven = (c[0] == "f") if p.drive == "fwd" else (c[0] == "r")
            share = (split if c[1] == "l" else 1.0 - split) if driven else 0.0
            fx[c] = fx_total * (brake_frac * bias / 2.0 + drive_frac * share)

        fy, alpha = {}, {}
        for c in ("fl", "fr", "rl", "rr"):
            front = c[0] == "f"
            arm = p.a if front else -p.b
            track = p.track_f if front else p.track_r
            side = -1.0 if c[1] == "l" else 1.0
            vy_w = vyk + arm * rk
            vx_w = vxk + side * rk * track / 2.0
            dw = dk if front else 0.0
            alpha[c] = ca.atan2(vy_w * ca.cos(dw) - vx_w * ca.sin(dw),
                                vx_w * ca.cos(dw) + vy_w * ca.sin(dw))
            fz_safe = ca.fmax(fz[c], 1.0)
            fy[c] = tyre.fy_combined(alpha[c], fz_safe, fx[c], 0.0, xp)

        drag = 0.5 * 1.225 * p.c_d * p.frontal_area * vxk * vxk
        fy_f, fy_r = fy["fl"] + fy["fr"], fy["rl"] + fy["rr"]
        fx_f, fx_r = fx["fl"] + fx["fr"], fx["rl"] + fx["rr"]
        fx_body = fx_f * ca.cos(dk) - fy_f * ca.sin(dk) + fx_r - drag
        fy_body = fy_f * ca.cos(dk) + fx_f * ca.sin(dk) + fy_r
        # Per-wheel yaw moment: M_z = sum(x_w * Fy_body - y_w * Fx_body). The old
        # expression discarded the longitudinal body-frame component while
        # `fx_body` two lines above resolves it — the same function projecting
        # forces one way and moments another, about the same four wheels. It is the
        # defect the simulator had (F72, F73); leaving it here would put the solver
        # and the simulator into disagreement about yaw.
        if _LEGACY_YAW_MOMENT:
            m_z = p.a * (fy_f * ca.cos(dk) + fx_f * ca.sin(dk)) - p.b * fy_r
        else:
            m_z = 0.0
            for c in ("fl", "fr", "rl", "rr"):
                front = c[0] == "f"
                x_w = p.a if front else -p.b
                y_w = 0.5 * (p.track_f if front else p.track_r) * (
                    1.0 if c[1] == "l" else -1.0)
                if front:
                    fxb = fx[c] * ca.cos(dk) - fy[c] * ca.sin(dk)
                    fyb = fx[c] * ca.sin(dk) + fy[c] * ca.cos(dk)
                else:
                    fxb, fyb = fx[c], fy[c]
                m_z = m_z + x_w * fyb - y_w * fxb

        s_dot = (vxk * ca.cos(xik) - vyk * ca.sin(xik)) / (1.0 - nk * kappa[k])
        dt_ds = 1.0 / s_dot
        dz = ca.vertcat(
            (vxk * ca.sin(xik) + vyk * ca.cos(xik)) * dt_ds,
            rk * dt_ds - kappa[k],
            (a_x + vyk * rk) * dt_ds,
            (a_y - vxk * rk) * dt_ds,
            (m_z / p.i_zz) * dt_ds,
            sr * dt_ds,
        )
        # the two algebraic residuals that make a_x, a_y mean what they say
        resid = ca.vertcat(a_x - fx_body / p.mass, a_y - fy_body / p.mass)
        # friction-circle usage per wheel: the Episode 6 centrepiece
        util = {}
        for c in ("fl", "fr", "rl", "rr"):
            fz_safe = ca.fmax(fz[c], 1.0)
            util[c] = ca.sqrt((fx[c] / tyre.peak_fx(fz_safe, xp)) ** 2
                              + (fy[c] / (tyre.peak_fy(fz_safe, xp) + 1e-9)) ** 2)
        # Indices 0-7 deliberately mirror the two-wheel tuple so the shared
        # extraction below needs no branch. Dicts go after.
        return (dz, dt_ds, alpha["fl"], alpha["rl"],
                fz["fl"] + fz["fr"], fz["rl"] + fz["rr"], a_x, a_y,
                resid, fz, util, alpha, fy, fx)

    dyn = [dynamics_4w(k) if four_wheel else dynamics(k) for k in range(n_nodes)]
    if four_wheel:
        for k in range(n_nodes):
            opti.subject_to(dyn[k][8] == 0)
            # No wheel may be asked for more longitudinal force than it can
            # produce at its own load. Without this the solver demands 1.8x an
            # unloaded inside wheel's capability and gets it for free, and the
            # lap time is fiction. With the torque split fixed at 50/50 this is
            # an OPEN differential: the pair is limited by twice the weaker
            # wheel, which is precisely why limited-slip differentials exist
            # and is Episode 12's subject.
            for c in ("fl", "fr", "rl", "rr"):
                cap = 0.98 * tyre.peak_fx(ca.fmax(dyn[k][9][c], 1.0), xp)
                opti.subject_to(opti.bounded(-cap, dyn[k][13][c], cap))

    # trapezoidal collocation
    for k in range(n_nodes - 1):
        opti.subject_to(X[:, k + 1] == X[:, k] + 0.5 * ds * (dyn[k][0] + dyn[k + 1][0]))

    # objective: total time, plus a small penalty on sawing at the wheel.
    #
    # Time alone leaves the problem DEGENERATE wherever the car has spare road.
    # On the approach straight it must move ~4 m sideways to set up for the
    # corner, and there are thousands of ways to do that which all take the same
    # time -- so the solver picks an arbitrary one, and "arbitrary" came out as
    # the steering reversing direction 4 to 6 times in 70 m, swinging up to 12
    # degrees between adjacent nodes. Through the corner, where time really does
    # depend on the steering, it was already smooth to half a degree per node.
    #
    # That chatter is not a driver and it is not physics.
    #
    # **DEFAULT IS OFF (weight 0), because measuring it showed the cure is worse
    # than the disease.** Swept at 1e-4 / 1e-3 / 1e-2 on the Episode 6 problem the
    # penalty halved the worst jump (10.9 -> 4.8 deg) but removed NONE of the four
    # direction reversals, cost time monotonically (+0.8 / +3.6 / +8.0 ms), and --
    # the deciding part -- turned a cleanly converging solve into one that hits the
    # iteration limit at every nonzero weight. It was added on the theory that the
    # flat direction was hurting conditioning; the opposite happened.
    #
    # Kept as an opt-in parameter because the underlying defect is real and this
    # is the obvious lever to try again with a better formulation -- penalising
    # the second difference of ``delta``, or tightening the road-edge constraint
    # that the car appears to be riding. See FINDINGS F40.
    #
    # The penalty is scaled by ``steer_rate_max`` so the weight is dimensionless
    # and stays meaningful if the actuator limit changes.
    time_obj = sum(0.5 * ds * (dyn[k][1] + dyn[k + 1][1])
                   for k in range(n_nodes - 1))
    smooth = sum((U[0, k] / lim.steer_rate_max) ** 2 for k in range(n_nodes))
    opti.minimize(time_obj + steer_rate_weight * ds * smooth)

    # bounds and the honesty envelope
    opti.subject_to(opti.bounded(-n_lim, n, n_lim))
    opti.subject_to(opti.bounded(-math.radians(60.0), xi, math.radians(60.0)))
    opti.subject_to(opti.bounded(lim.v_min, v_x, lim.v_max))
    opti.subject_to(opti.bounded(-lim.steer_max, delta, lim.steer_max))
    opti.subject_to(opti.bounded(-lim.steer_rate_max, steer_rate, lim.steer_rate_max))
    opti.subject_to(opti.bounded(-lim.brake_max / 1000.0, drive,
                                 lim.drive_max / 1000.0))
    for k in range(n_nodes):
        if four_wheel:
            for a_ in dyn[k][11].values():
                opti.subject_to(opti.bounded(-lim.alpha_max, a_, lim.alpha_max))
        else:
            _, _, af, ar, *_ = dyn[k]
            opti.subject_to(opti.bounded(-lim.alpha_max, af, lim.alpha_max))
            opti.subject_to(opti.bounded(-lim.alpha_max, ar, lim.alpha_max))

    # start on the centreline, pointed down it, at a given speed
    v0 = entry_speed if entry_speed is not None else 30.0
    opti.subject_to(n[0] == 0.0)
    opti.subject_to(xi[0] == 0.0)
    opti.subject_to(v_y[0] == 0.0)
    opti.subject_to(r[0] == 0.0)
    opti.subject_to(delta[0] == 0.0)
    if entry_speed is not None:
        opti.subject_to(v_x[0] == entry_speed)

    # initial guess
    if warm_start is not None:
        # Resample the warm start onto this grid rather than requiring an exact
        # node-count match. The previous form was
        # ``if warm_start is not None and len(warm_start.s) == n_nodes``, which
        # SILENTLY dropped a mismatched warm start and fell through to the cold
        # guess -- no warning, just a solve that mysteriously takes longer or
        # lands somewhere worse. It also made grid refinement needlessly fragile:
        # the only available seed at a new node count was a fresh bicycle solve,
        # when the converged four-wheel answer at a neighbouring count is a far
        # better start. Distance is the independent variable, so interpolating on
        # ``s`` is exact for a state that is already smooth in it.
        s_from = np.asarray(warm_start.s)
        for i, nm in enumerate(STATE_NAMES):
            opti.set_initial(X[i, :], np.interp(s_grid, s_from,
                                                warm_start.states[nm]))
        opti.set_initial(U[0, :], np.interp(s_grid, s_from,
                                            warm_start.controls["steer_rate"]))
        opti.set_initial(U[1, :], np.interp(s_grid, s_from,
                                           warm_start.controls["drive_force"])
                         / 1000.0)
    else:
        opti.set_initial(v_x, v0)
        opti.set_initial(n, 0.0)
        opti.set_initial(delta, kappa * p.wheelbase)
    if four_wheel:
        opti.set_initial(Z[0, :], 0.0)
        opti.set_initial(Z[1, :], kappa * v0 * v0)
        if Ud is not None:
            opti.subject_to(opti.bounded(0.0, Ud, 1.0))
            opti.set_initial(Ud, 0.5)

    # "Solved to acceptable level" is a real answer here, not a failure. A
    # minimum-time problem has flat directions near the optimum -- shaving the
    # last 1e-6 off a 6 second objective is 6 microseconds, far below anything
    # this project reports -- and chasing them costs thousands of iterations.
    opti.solver("ipopt", {
        "print_time": False, "ipopt.print_level": print_level,
        "ipopt.max_iter": max_iter, "ipopt.tol": 1e-6,
        "ipopt.acceptable_tol": 1e-5,
        "ipopt.acceptable_constr_viol_tol": 1e-4,
        "ipopt.acceptable_iter": 10,
        "ipopt.mu_strategy": "adaptive",
    })
    try:
        sol = opti.solve()
        status, ok = opti.stats().get("return_status", "solved"), True
    except RuntimeError as exc:  # keep the last iterate so it can be inspected
        sol = opti.debug
        status = opti.stats().get("return_status", f"failed: {exc}"[:80])
        ok = status in ("Solved_To_Acceptable_Level",)

    val = sol.value
    states = {nm: np.asarray(val(X[i, :])).ravel() for i, nm in enumerate(STATE_NAMES)}
    controls = {nm: np.asarray(val(U[i, :])).ravel()
                for i, nm in enumerate(CONTROL_NAMES)}
    controls["drive_force"] = controls["drive_force"] * 1000.0   # back to newtons
    dt_ds = np.array([float(val(dyn[k][1])) for k in range(n_nodes)])
    per_wheel = None
    if four_wheel:
        per_wheel = {
            "load": {c: np.array([float(val(dyn[k][9][c])) for k in range(n_nodes)])
                     for c in ("fl", "fr", "rl", "rr")},
            "utilisation": {c: np.array([float(val(dyn[k][10][c]))
                                         for k in range(n_nodes)])
                            for c in ("fl", "fr", "rl", "rr")},
            "alpha": {c: np.array([float(val(dyn[k][11][c]))
                                   for k in range(n_nodes)])
                      for c in ("fl", "fr", "rl", "rr")},
            "fy": {c: np.array([float(val(dyn[k][12][c])) for k in range(n_nodes)])
                   for c in ("fl", "fr", "rl", "rr")},
            "fx": {c: np.array([float(val(dyn[k][13][c])) for k in range(n_nodes)])
                   for c in ("fl", "fr", "rl", "rr")},
        }
    total = float(np.trapezoid(dt_ds, s_grid))
    return Solution(
        track=track, s=s_grid, states=states, controls=controls, time=total,
        dt_ds=dt_ds,
        a_x=np.array([float(val(dyn[k][6])) for k in range(n_nodes)]),
        a_y=np.array([float(val(dyn[k][7])) for k in range(n_nodes)]),
        alpha_f=np.array([float(val(dyn[k][2])) for k in range(n_nodes)]),
        alpha_r=np.array([float(val(dyn[k][3])) for k in range(n_nodes)]),
        fz_f=np.array([float(val(dyn[k][4])) for k in range(n_nodes)]),
        fz_r=np.array([float(val(dyn[k][5])) for k in range(n_nodes)]),
        success=ok, solver_status=status, limits=lim, per_wheel=per_wheel,
        meta={"n_nodes": n_nodes, "ds": ds, "entry_speed": entry_speed,
              "four_wheel": four_wheel, "drive": p.drive, "diff": diff,
              "tire": tyre.provenance,
              "vehicle": {"mass": p.mass, "wheelbase": p.wheelbase,
                          "front_mass_fraction": p.front_mass_fraction,
                          "com_height": p.com_height, "i_zz": p.i_zz}},
    )


__all__ = ["Limits", "Solution", "solve_min_time", "STATE_NAMES", "CONTROL_NAMES"]
