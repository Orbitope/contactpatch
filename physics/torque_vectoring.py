"""The classical torque-vectoring controller: two layers, and they are separable.

Episode 13. A differential (Episode 12) *reacts* — it resists a speed difference
the corner forces on it, and the yaw moment that falls out is a side effect. This
is the other thing: a controller that decides how much the car should be rotating
and then buys that rotation from whichever tires can most afford it.

The split is the episode
------------------------

**Upper layer — how much do you want to rotate?** A reference model turns the
driver's steering angle and the car's speed into a desired yaw rate, and a PID
closes the gap between that and the measured one. Its output is a single number:
a desired yaw moment ``Mz``, in N.m. It knows nothing about wheels.

**Lower layer — which wheels pay for it?** A control allocator turns that one
number into four longitudinal forces, subject to also delivering the total
longitudinal force the driver asked for, and to no tire being asked for more than
it has. Between those constraints there are two degrees of freedom left over, and
the allocator spends them on minimising tire workload. It knows nothing about yaw
rate, reference models or drivers.

That separation is what the series plan calls "20 years of engineering consensus",
and it is worth being explicit about why it is a good idea rather than just a
common one: the upper layer is where the vehicle-dynamics judgement lives and it
is two-dimensional (yaw rate in, moment out), so it can be tuned, plotted and
argued about. The lower layer is a convex optimisation with a unique answer given
its inputs. Neither half has to know how the other works.

What the allocator actually solves
----------------------------------

A weighted least-squares control allocation — the standard formulation (Härkegård,
and every four-motor-EV paper since), and a quadratic program::

    minimise    s_fx * (Fx_total(x) - Fx_demand)^2
              + s_mz * (Mz(x) - Mz_demand)^2 / (track/2)^2
              + eps  * sum_i (x_i / cap_i)^2
    subject to  -cap_i <= x_i <= cap_i

where ``x`` is the four per-wheel longitudinal forces. The two demands enter as
weighted residuals rather than hard equalities, which is not a shortcut: at the
limit they routinely *cannot* both be met, and a hard-constrained formulation has
to answer "which one do I give up?" with a branch. Here the answer is a ratio,
``s_fx`` against ``s_mz``, it is one number, and CLAUDE.md rule 9 requires the
sensitivity to it to be reported rather than assumed. The third term is the tire
workload and it is what picks a single point out of the two-dimensional family
that satisfies both demands equally well.

``cap_i`` is what the tire has left, longitudinally, given what it is already
doing laterally — the friction ellipse of FINDINGS D9, evaluated on the previous
step's lateral force. A real controller reads last-instant sensors too.

Sign convention, which is the whole ballgame
--------------------------------------------

ISO 8855, as everywhere else in this project: **y is positive to the LEFT**, a
positive yaw moment turns the nose left. The moment a longitudinal force makes is
``-y_w * Fx``, so **more force on the RIGHT wheel yaws the car LEFT**. That is one
sign and it has been wrong in this project before in three different places
(F36 and its two relatives), so ``tests/test_torque_vectoring.py`` pins it against
the backend's own ``yaw_moment`` rather than against a restatement of this
paragraph.

Fidelity: rung 2 (CLAUDE.md rule 15)
------------------------------------

Four independently commanded wheel forces is a four-motor electric car, not RV-1's
rear-drive combustion driveline. ``effectors="rear"`` is the other thing a real car
can be: a torque-vectoring differential on the driven axle only, one degree of
freedom, no QP needed. Both are simulated on a model with no roll camber, no roll
steer and no compliance steer, which is why every number here is a trend and not a
specification (rules 6 and 15).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import schema
from .double_track import CORNERS, BicycleState, DoubleTrackBackend

#: Fraction of a wheel's analytic peak longitudinal force the allocator is allowed
#: to command. Matches ``DoubleTrackBackend.DIFF_CAP_FRACTION`` and
#: ``optimal_control.py``, so the differential, the allocator and the solver all
#: agree about what a wheel can do. F72 found two of them disagreeing and that is
#: the class of divergence that makes a comparison meaningless.
CAP_FRACTION = 0.98

#: Floor on a wheel's usable longitudinal capacity, N. A tire at the limit of its
#: lateral grip has essentially no longitudinal capacity left, and 1/cap^2 as a
#: cost weight goes to infinity there. The floor keeps the QP conditioned; it is
#: far below any force the allocator would want to send to such a wheel anyway.
CAP_FLOOR = 50.0


# ---------------------------------------------------------------------------
# Upper layer
# ---------------------------------------------------------------------------

@dataclass
class ReferenceModel:
    """What yaw rate *should* this steering angle produce at this speed?

    The linear single-track relation every textbook opens with::

        r_ref = v * steer / (L + K * v^2)

    ``K`` is the understeer gradient in rad per m/s^2 — the same number Episode 3
    introduced in deg/g and Episode 5 measured on four wheels. Setting ``K`` to the
    car's own measured value asks the controller to make the car behave *linearly*,
    not neutrally: understeer that is present at 0.2 g stays present at 0.9 g,
    instead of growing as the front tires saturate. Setting it lower asks for a
    pointier car than the chassis is.

    **The saturation matters more than the gain.** ``a_y_max`` caps the reference
    at a yaw rate the tires can actually sustain, ``r_max = a_y_max / v``. Without
    it the reference model happily demands a yaw rate implying 1.6 g on a car that
    makes 0.97, the PID sees a permanent error, the allocator saturates, and the
    car is dragged into a spin by its own driver aid. That failure is not
    hypothetical — it is what the first configuration here did.
    """

    wheelbase: float
    #: Understeer gradient the controller *asks* for, rad/(m/s^2).
    k_us: float
    #: Grip ceiling used to saturate the reference, m/s^2. [MEASURED] from our own
    #: model — see ``measure_grip_ceiling``.
    a_y_max: float
    #: Fraction of that ceiling the reference is allowed to ask for. Below 1.0 the
    #: controller deliberately under-asks near the limit, which is what production
    #: stability systems do. [ASSUMED].
    a_y_margin: float = 1.0

    def yaw_rate(self, speed: float, steer: float) -> float:
        v = max(abs(speed), 1.0)
        r = v * steer / (self.wheelbase + self.k_us * v * v)
        r_max = self.a_y_margin * self.a_y_max / v
        return float(np.clip(r, -r_max, r_max))


@dataclass
class YawController:
    """PID on yaw-rate error. Output is a desired yaw moment, N.m.

    Gains are sized from the task rather than from convention, which is the one
    diagnosis that worked every time in Season 3 (F52, and the D6 checks that came
    out of it): a yaw-rate error of 0.05 rad/s should be worth correcting inside
    about 0.2 s, so the demanded yaw acceleration is ~0.25 rad/s^2, so the moment
    is ~0.25 * i_zz ~ 500 N.m, so ``k_p`` is ~10,000 N.m per rad/s. The default
    below is that number, and the experiment sweeps it.
    """

    k_p: float = 10_000.0
    k_i: float = 20_000.0
    k_d: float = 0.0
    #: Largest moment the upper layer will ask for, N.m. The allocator will refuse
    #: anything the tires cannot deliver anyway; this stops the integrator winding
    #: up against a demand that was never physical.
    mz_max: float = 6000.0
    _integral: float = 0.0
    _last_error: float = 0.0

    def reset(self) -> None:
        self._integral = 0.0
        self._last_error = 0.0

    def update(self, r_ref: float, r: float, dt: float) -> float:
        e = r_ref - r
        d = (e - self._last_error) / dt if dt > 0 else 0.0
        raw = self.k_p * e + self.k_i * self._integral + self.k_d * d
        mz = float(np.clip(raw, -self.mz_max, self.mz_max))
        # Conditional integration: stop accumulating when the output is already
        # saturated and the error would push it further out. Without this the
        # integral fills up during the one corner where the car is grip-limited
        # and then commands a large moment on the following straight, where the
        # error has long since gone away.
        if abs(raw) < self.mz_max or raw * e < 0.0:
            self._integral += e * dt
        self._last_error = e
        return mz


# ---------------------------------------------------------------------------
# Lower layer
# ---------------------------------------------------------------------------

def _bounded_least_squares(h: np.ndarray, g: np.ndarray, lo: np.ndarray,
                           hi: np.ndarray, max_iter: int = 20) -> np.ndarray:
    """Minimise ``0.5 x'Hx + g'x`` subject to ``lo <= x <= hi``. Active set.

    H is symmetric positive definite here (the workload term guarantees it), so
    the unconstrained solution is unique and the active-set loop terminates: each
    pass either accepts the current active set or clamps at least one more
    variable, and variables are released only when their multiplier's sign says
    the bound is holding them the wrong way.

    Written out rather than taken from a library because the whole solver is
    fifteen lines and the alternative is a dependency for a 4x4 problem.
    """
    n = len(g)
    free = np.ones(n, dtype=bool)
    x = np.zeros(n)
    for _ in range(max_iter):
        if free.any():
            idx = np.where(free)[0]
            rhs = -(g[idx] + h[np.ix_(idx, ~free)] @ x[~free])
            try:
                x[idx] = np.linalg.solve(h[np.ix_(idx, idx)], rhs)
            except np.linalg.LinAlgError:
                x[idx] = np.linalg.lstsq(h[np.ix_(idx, idx)], rhs, rcond=None)[0]
        violated = (x < lo - 1e-9) | (x > hi + 1e-9)
        if violated.any():
            x = np.clip(x, lo, hi)
            free &= ~violated
            continue
        # KKT: a clamped variable stays clamped only if the gradient pushes it
        # further into its bound. Otherwise release it and re-solve.
        grad = h @ x + g
        release = (((~free) & (np.isclose(x, lo)) & (grad < -1e-9))
                   | ((~free) & (np.isclose(x, hi)) & (grad > 1e-9)))
        if not release.any():
            return x
        free |= release
    return np.clip(x, lo, hi)


@dataclass
class Allocation:
    """What the lower layer decided, and what it cost."""

    forces: dict[str, float]
    fx_demand: float
    fx_delivered: float
    mz_demand: float
    mz_delivered: float
    caps: dict[str, float]
    #: max over wheels of |fx| / cap — 1.0 means at least one wheel is at the
    #: longitudinal capacity the friction ellipse leaves it.
    peak_workload: float

    @property
    def mz_shortfall(self) -> float:
        return self.mz_demand - self.mz_delivered

    @property
    def fx_shortfall(self) -> float:
        return self.fx_demand - self.fx_delivered


@dataclass
class Allocator:
    """Four per-wheel longitudinal forces from two demands. The QP of the docstring.

    ``effectors``:
        ``"four"`` — four independently commanded wheels. A four-motor EV, and the
                     form Episode 14's end-to-end policy is given.
        ``"rear"``  — a torque-vectoring differential on the driven axle. The total
                     force is placed by the ordinary rules and only the left/right
                     split is free, so there is one degree of freedom and no
                     optimisation to do. This is what a real rear-drive car with a
                     TV differential has, and it is the honest comparison for RV-1.
    """

    params: schema.VehicleParams
    tire: object
    effectors: str = "four"
    #: Priority weights on the two demands. Equal by default; the ratio is a
    #: modelling choice and rule 9 requires its sensitivity to be measured.
    s_fx: float = 1.0
    s_mz: float = 1.0
    #: Weight on the tire-workload term, relative to the demands. Small: it is a
    #: tie-breaker among allocations that meet both demands, not a third demand.
    s_workload: float = 1e-3
    #: Brake distribution used for the parts of the demand the allocator does not
    #: get to place (``effectors="rear"`` only).
    brake_bias: float = 0.65

    def capacities(self, loads: dict[str, float],
                   lateral: dict[str, float] | None = None) -> dict[str, float]:
        """Longitudinal force each wheel has left, N, given what it is doing laterally.

        The friction ellipse, evaluated per wheel::

            cap = 0.98 * Fx_peak(Fz) * sqrt(1 - (Fy / Fy_peak(Fz))^2)

        ``lateral`` is the previous control step's lateral forces. A controller on
        a real car reads a yaw-rate sensor and a load estimate one instant late as
        well; using this step's values would require solving the tire model and
        the allocator simultaneously, which is not a thing an ECU does.
        """
        caps = {}
        for c in CORNERS:
            fz = max(loads[c], 0.0)
            if fz <= 0.0:
                caps[c] = CAP_FLOOR
                continue
            fx_peak = float(self.tire.peak_fx(fz))
            if lateral:
                fy_peak = float(self.tire.peak_fy(fz))
                used = min(abs(lateral.get(c, 0.0)) / fy_peak, 1.0) if fy_peak else 0.0
                fx_peak *= math.sqrt(max(0.0, 1.0 - used * used))
            caps[c] = max(CAP_FRACTION * fx_peak, CAP_FLOOR)
        return caps

    def _rows(self, steer: float) -> tuple[np.ndarray, np.ndarray]:
        """Body-frame total-force and yaw-moment coefficients for each wheel's Fx.

        Derived from ``DoubleTrackBackend.body_forces`` and ``.yaw_moment``, so the
        allocator's model of what a force does is the simulator's model of what a
        force does. A front wheel's longitudinal force is steered along with the
        wheel: it pushes the car forward by ``cos(steer)`` and *sideways* by
        ``sin(steer)``, and both of those make yaw.
        """
        c, s = math.cos(steer), math.sin(steer)
        a_fx, a_mz = [], []
        for corner in CORNERS:
            x, y = (self.params.a if corner[0] == "f" else -self.params.b), 0.0
            half = 0.5 * (self.params.track_f if corner[0] == "f"
                          else self.params.track_r)
            y = half if corner[1] == "l" else -half
            if corner[0] == "f":
                a_fx.append(c)                 # fx_body = fx cos(steer) - fy sin
                a_mz.append(x * s - y * c)     # x * fy_body - y * fx_body
            else:
                a_fx.append(1.0)
                a_mz.append(-y)
        return np.asarray(a_fx), np.asarray(a_mz)

    def allocate(self, fx_demand: float, mz_demand: float,
                 loads: dict[str, float], steer: float = 0.0,
                 lateral: dict[str, float] | None = None) -> Allocation:
        caps = self.capacities(loads, lateral)
        a_fx, a_mz = self._rows(steer)
        scale = 2.0 / self.params.track_r        # moment residual, in newtons

        if self.effectors == "rear":
            x = self._allocate_rear(fx_demand, mz_demand, caps, a_fx, a_mz)
        else:
            cap = np.array([caps[c] for c in CORNERS])
            # Both residuals are divided by a reference force so every term in the
            # objective is dimensionless. Without it the demand terms are in N^2
            # (up to 1e7) and the workload term is O(1), which puts a condition
            # number of ~1e10 into a 4x4 solve: the tie-break the workload term
            # exists to provide was being computed below the floating-point noise
            # of the terms it was tie-breaking, and a left/right symmetric problem
            # came back visibly asymmetric.
            f_ref = float(np.mean(cap))
            u_fx, u_mz = a_fx / f_ref, a_mz * scale / f_ref
            w = np.diag((1.0 / cap) ** 2)
            h = 2.0 * (self.s_fx * np.outer(u_fx, u_fx)
                       + self.s_mz * np.outer(u_mz, u_mz)
                       + self.s_workload * w)
            g = -2.0 * (self.s_fx * (fx_demand / f_ref) * u_fx
                        + self.s_mz * (mz_demand * scale / f_ref) * u_mz)
            x = _bounded_least_squares(h, g, -cap, cap)

        forces = {c: float(x[i]) for i, c in enumerate(CORNERS)}
        cap_arr = np.array([caps[c] for c in CORNERS])
        return Allocation(
            forces=forces, fx_demand=float(fx_demand),
            fx_delivered=float(a_fx @ x), mz_demand=float(mz_demand),
            mz_delivered=float(a_mz @ x), caps=caps,
            peak_workload=float(np.max(np.abs(x) / cap_arr)),
        )

    def _allocate_rear(self, fx_demand: float, mz_demand: float,
                       caps: dict[str, float], a_fx: np.ndarray,
                       a_mz: np.ndarray) -> np.ndarray:
        """One degree of freedom: the left/right split on the driven axle.

        Not a QP, and saying so is the point of including it. A torque-vectoring
        differential has exactly as many effectors as demands minus one, so there
        is nothing left to optimise — the allocation is determined, and the second
        layer collapses to a division. The QP earns its place only when there are
        more effectors than demands, which on a car means brakes at every corner
        or a motor at every corner.
        """
        x = np.zeros(4)
        driven = ("rl", "rr") if self.params.drive == "rwd" else ("fl", "fr")
        idx = {c: i for i, c in enumerate(CORNERS)}
        if fx_demand < 0.0:
            for c in CORNERS:
                share = self.brake_bias if c[0] == "f" else 1.0 - self.brake_bias
                x[idx[c]] = fx_demand * share / 2.0
        else:
            for c in driven:
                x[idx[c]] = fx_demand / 2.0
        # The moment arm of a left/right asymmetry on the driven axle.
        arm = abs(a_mz[idx[driven[1]]] - a_mz[idx[driven[0]]])
        d = mz_demand / arm if arm else 0.0
        left, right = (driven[0], driven[1]) if driven[0][1] == "l" else (driven[1], driven[0])
        # Positive moment = nose left = more force on the RIGHT wheel.
        x[idx[right]] += d
        x[idx[left]] -= d
        for c in CORNERS:
            x[idx[c]] = float(np.clip(x[idx[c]], -caps[c], caps[c]))
        return x


# ---------------------------------------------------------------------------
# The two layers, wired together
# ---------------------------------------------------------------------------

@dataclass
class TorqueVectoring:
    """Reference model + PID + allocator, updated once per control step.

    **The controller updates once per control interval and its output is held
    constant through the integrator's substeps**, which is not a detail. The
    backend integrates with RK4, so ``derivatives`` is evaluated four times per
    step; running the PID inside it would integrate the error four times with the
    wrong dt and produce a controller that does not exist. A real ECU runs at a
    fixed rate and holds its output — zero-order hold — and so does this.
    """

    reference: ReferenceModel
    controller: YawController
    allocator: Allocator
    #: Set to False to run the allocator with a zero moment demand. This is the
    #: control condition that separates "the allocator distributes force better
    #: than a differential does" from "the controller vectors torque": both
    #: replace the diff, only one of them asks for yaw. Without it a lap-time gain
    #: cannot be attributed to torque vectoring at all.
    yaw_control: bool = True
    #: Latest command, held across the integrator's substeps.
    mz_command: float = 0.0
    last: Allocation | None = None
    _held: dict[str, float] | None = None
    log: dict[str, list] = field(default_factory=lambda: {
        k: [] for k in ("r_ref", "r", "mz_demand", "mz_delivered", "fx_demand",
                        "fx_delivered", "peak_workload")})

    def reset(self) -> None:
        self.controller.reset()
        self.mz_command = 0.0
        self.last = None
        self._held = None
        for v in self.log.values():
            v.clear()

    def update(self, state: BicycleState, dt: float, demand: float | None = None,
               loads: dict[str, float] | None = None,
               lateral: dict[str, float] | None = None) -> float:
        """Run BOTH layers once, and hold the answer for the whole control step.

        Returns the moment demand. If ``demand`` and ``loads`` are given, the
        allocation is solved here too and the four forces are held constant until
        the next call — which is what a real ECU does, and what the integrator
        needs: ``derivatives`` is evaluated four times per RK4 step and iterates
        internally, so leaving the allocator to be called from inside it solved the
        same QP up to twenty-four times per control interval and let the commanded
        forces chase the substeps around. Zero-order hold on both layers is one
        decision per interval, which is the thing being modelled.
        """
        if self.yaw_control:
            speed = max(state.v_x, 1.0)
            r_ref = self.reference.yaw_rate(speed, state.steer)
            self._r_ref = r_ref
            self.mz_command = self.controller.update(r_ref, state.yaw_rate, dt)
        else:
            self.mz_command = 0.0
            self._r_ref = state.yaw_rate
        if demand is not None and loads is not None:
            self._held = self._solve(demand, loads, state, lateral)
        return self.mz_command

    def _solve(self, demand: float, loads: dict[str, float],
               state: BicycleState, lateral: dict[str, float] | None
               ) -> dict[str, float]:
        alloc = self.allocator.allocate(demand, self.mz_command, loads,
                                        steer=state.steer, lateral=lateral)
        self.last = alloc
        return alloc.forces

    def forces(self, demand: float, loads: dict[str, float],
               state: BicycleState, lateral: dict[str, float] | None = None
               ) -> dict[str, float]:
        """The backend's per-wheel longitudinal force hook.

        Returns whatever ``update`` decided for this control interval. Solves on
        the spot only if nothing has been held — which happens in tests that
        exercise the allocator directly, never inside a driven lap.
        """
        if self._held is not None:
            return self._held
        return self._solve(demand, loads, state, lateral)

    def record(self, state: BicycleState) -> None:
        """Log one control step. Called by the driver loop, not by the physics."""
        a = self.last
        self.log["r_ref"].append(float(getattr(self, "_r_ref", state.yaw_rate)))
        self.log["r"].append(float(state.yaw_rate))
        self.log["mz_demand"].append(float(a.mz_demand) if a else 0.0)
        self.log["mz_delivered"].append(float(a.mz_delivered) if a else 0.0)
        self.log["fx_demand"].append(float(a.fx_demand) if a else 0.0)
        self.log["fx_delivered"].append(float(a.fx_delivered) if a else 0.0)
        self.log["peak_workload"].append(float(a.peak_workload) if a else 0.0)

    def history(self) -> dict[str, np.ndarray]:
        return {k: np.asarray(v) for k, v in self.log.items()}


# ---------------------------------------------------------------------------
# Construction helpers
# ---------------------------------------------------------------------------

def measure_grip_ceiling(backend: DoubleTrackBackend, radius: float = 40.0) -> float:
    """Largest steady lateral acceleration this car makes, m/s^2. [MEASURED]."""
    return float(backend.max_lateral_g(radius) * schema.G)


def measure_understeer_gradient(backend: DoubleTrackBackend,
                                radius: float = 30.0) -> float:
    """The car's own understeer gradient, rad/(m/s^2). [MEASURED].

    Same definition and same sweep as Episode 3 and Episode 5, converted out of
    deg/g into the units the reference model wants.
    """
    from .double_track import understeer_gradient
    speeds = np.linspace(5.0, 15.0, 9)
    k_deg_per_g, _ = understeer_gradient(backend.skidpad_sweep(radius, speeds))
    return math.radians(k_deg_per_g) / schema.G


def build(backend: DoubleTrackBackend, *, effectors: str = "four",
          k_us: float | None = None, a_y_max: float | None = None,
          yaw_control: bool = True, k_p: float = 10_000.0,
          k_i: float = 20_000.0, k_d: float = 0.0, mz_max: float = 6000.0,
          s_fx: float = 1.0, s_mz: float = 1.0,
          a_y_margin: float = 1.0) -> TorqueVectoring:
    """Assemble a controller for ``backend``'s car, measuring what it needs."""
    p = backend.params
    return TorqueVectoring(
        reference=ReferenceModel(
            wheelbase=p.wheelbase,
            k_us=(measure_understeer_gradient(backend) if k_us is None else k_us),
            a_y_max=(measure_grip_ceiling(backend) if a_y_max is None else a_y_max),
            a_y_margin=a_y_margin),
        controller=YawController(k_p=k_p, k_i=k_i, k_d=k_d, mz_max=mz_max),
        allocator=Allocator(params=p, tire=backend.tire, effectors=effectors,
                            s_fx=s_fx, s_mz=s_mz,
                            brake_bias=backend.brake_bias),
        yaw_control=yaw_control,
    )


__all__ = ["ReferenceModel", "YawController", "Allocator", "Allocation",
           "TorqueVectoring", "build", "measure_grip_ceiling",
           "measure_understeer_gradient", "CAP_FRACTION"]
