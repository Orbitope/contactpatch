"""Four wheels, and therefore a left and a right.

The upgrade Episode 5 is about. Everything the bicycle model could not represent
comes from having collapsed each axle into one wheel, and this model un-collapses
them:

* **Lateral load transfer.** Cornering moves load from the inside wheels to the
  outside ones. Because peak grip falls with load (F1), an axle carrying its
  weight unevenly makes less grip than one sharing it — so cornering costs grip
  that nothing spent. This is the term F18 estimated at ~2,300 N on the front
  axle at the limit, roughly ten times the front-to-rear transfer.
* **Roll stiffness distribution.** Total transfer is set by mass, height and
  cornering force. How it *divides* between the axles is set by which end is
  stiffer in roll — which is what an anti-roll bar changes. A bicycle model has
  no left and right, so the knob does not exist for it at all.
* **Per-wheel slip angles.** The inside wheel of an axle travels slightly slower
  than the outside one, so their slip angles differ.

What is still missing, and stated rather than discovered later
-------------------------------------------------------------
* **No roll-centre geometry and no unsprung mass.** Real lateral transfer splits
  into a geometric part that acts through the roll centres and an elastic part
  that acts through the springs and bars, and only the elastic part follows roll
  stiffness. We model the total as entirely elastic. That overstates how much
  authority an anti-roll bar has, so treat the ARB *direction* as solid and its
  magnitude as approximate.
* **No roll angle as a state.** Transfer is computed from steady-state moment
  balance, so it responds instantly. A real body takes time to roll, which is a
  transient effect Episode 8's territory would care about.
* **No camber.** The tire file's camber coefficients are degenerate (F5) and the
  model is camber-free throughout.
* **No compliance steer, no aligning torque, no roll steer.** Same as the bicycle
  model. Bundorf attributes a real car's remaining understeer to these, so our
  gradient should still land below a real car's — just less far below.

The interface is :class:`physics.backend.Backend`, identical to the bicycle
model, which is what lets Episode 5 push the same inputs through both.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from . import schema
from .backend import Backend, StepInfo
from .bicycle import AIR_DENSITY, BicycleState
from .tire import MF02Tire, default_tire

#: Corner order, matching ``schema.CORNERS``: front-left, front-right,
#: rear-left, rear-right. The order is load-bearing — D5 indexes it.
CORNERS = schema.CORNERS


@dataclass
class WheelForces:
    """What one wheel produced."""

    fy: float
    fx: float
    alpha: float
    kappa: float
    fz: float


@dataclass
class TrimPoint:
    """One steady-state equilibrium on a constant-radius circle."""

    speed: float
    radius: float
    a_y: float
    a_x: float
    steer: float
    v_y: float
    yaw_rate: float
    ackermann: float
    drive_force: float
    hold_speed: bool
    wheels: dict[str, WheelForces]
    converged: bool
    residual: float

    @property
    def a_y_g(self) -> float:
        return self.a_y / schema.G

    @property
    def steer_deg(self) -> float:
        return math.degrees(self.steer)

    @property
    def understeer_angle_deg(self) -> float:
        return math.degrees(self.steer - self.ackermann)

    @property
    def sideslip_deg(self) -> float:
        return math.degrees(math.atan2(self.v_y, self.speed))

    @property
    def loads(self) -> dict[str, float]:
        return {c: w.fz for c, w in self.wheels.items()}

    @property
    def alpha_front(self) -> float:
        """Load-weighted mean front slip angle, for comparison with the bicycle."""
        fl, fr = self.wheels["fl"], self.wheels["fr"]
        tot = fl.fz + fr.fz
        return (fl.alpha * fl.fz + fr.alpha * fr.fz) / tot if tot else 0.0

    @property
    def alpha_rear(self) -> float:
        rl, rr = self.wheels["rl"], self.wheels["rr"]
        tot = rl.fz + rr.fz
        return (rl.alpha * rl.fz + rr.alpha * rr.fz) / tot if tot else 0.0

    @property
    def lateral_transfer_front(self) -> float:
        """Load moved from the inside front wheel to the outside one, N."""
        return 0.5 * abs(self.wheels["fr"].fz - self.wheels["fl"].fz)

    @property
    def lateral_transfer_rear(self) -> float:
        return 0.5 * abs(self.wheels["rr"].fz - self.wheels["rl"].fz)

    @property
    def min_load(self) -> float:
        return min(w.fz for w in self.wheels.values())


class DoubleTrackBackend(Backend):
    """Four-wheel model. See the module docstring for what it still cannot do."""

    obs_space = schema.OBS_BICYCLE          # same observables; four-wheel log differs
    act_space = schema.ACT_BICYCLE
    wheel_log_space = schema.WHEEL_LOG_DOUBLE_TRACK

    MIN_SPEED = 2.0

    #: Fraction of a wheel's analytic peak longitudinal force treated as usable.
    #: Matches ``optimal_control.py``'s 0.98, so the solver and the simulator agree
    #: about what a wheel can do — F72 found them disagreeing about the drivetrain
    #: and that is the class of divergence that makes a cross-check meaningless.
    DIFF_CAP_FRACTION = 0.98

    #: Torque bias ratio by differential type — the ratio of the higher-torque
    #: wheel's force to the lower's that the device can sustain. This is the ONE
    #: number that distinguishes the three, which is why the model is parameterised
    #: on it rather than on clutch-pack ramp angles and preload we have no source
    #: for. Rung 2 honesty (CLAUDE.md rule 15): enough to show the mechanism, not a
    #: claim about any particular hardware.
    #:
    #: ``open``   1.0  — equal torque to both wheels, always. The pair is therefore
    #:                   limited by twice the WEAKER wheel, which is the entire
    #:                   reason limited-slip differentials exist.
    #: ``lsd``    1.5  — [ASSUMED]. Road-car clutch-pack and helical units are
    #:                   commonly quoted between about 1.3:1 and 2.5:1; 1.5 is a
    #:                   mid-range choice and every claim must be checked against
    #:                   the ends of that range.
    #: ``locked`` inf  — welded. No speed difference permitted, so torque follows
    #:                   grip with no bias limit at all; each wheel is capped only
    #:                   by its own capacity.
    DIFF_BIAS = {"open": 1.0, "lsd": 1.5, "locked": math.inf}

    #: How much of the left/right SPEED difference the device resists, 0 to 1.
    #:
    #: This is the second half of a differential and the half that decides which way
    #: it steers the car. Torque bias (above) says how unequally the device can share
    #: force when grip is unequal. Locking says how hard it fights the wheels turning
    #: at different speeds — and in a corner they must, because the outside wheel
    #: travels further.
    #:
    #: A welded diff resists completely: the inside wheel is dragged faster than it
    #: wants to roll and pushes, the outside is held slower and drags, and the couple
    #: yaws the car OUT of the corner. That is the classic locked-diff push, and a
    #: model without it gets the sign backwards. See FINDINGS F75.
    #:
    #: ``open`` 0.0 — an open diff lets the wheels turn at any speeds they like.
    #: ``lsd``  0.5 — [ASSUMED], and the least defensible number in this model. A
    #:                clutch-pack unit's locking varies with torque and direction;
    #:                0.5 is a mid-range stand-in. Every LSD claim gets re-run at
    #:                0.25 and 0.75 with the conclusion required to hold.
    #: ``locked`` 1.0 — welded, no speed difference permitted at all.
    DIFF_LOCKING = {"open": 0.0, "lsd": 0.5, "locked": 1.0}

    def __init__(self, params: schema.VehicleParams | None = None,
                 tire: MF02Tire | None = None, combined_slip: bool = True,
                 brake_bias: float = 0.65, diff: str = "open",
                 torque_bias_ratio: float | None = None,
                 locking: float | None = None):
        self.combined_slip = combined_slip
        self.brake_bias = brake_bias
        if diff not in self.DIFF_BIAS:
            raise ValueError(f"diff must be one of {sorted(self.DIFF_BIAS)}, "
                             f"got {diff!r}")
        self.diff = diff
        #: Explicit override wins, so a sensitivity sweep over the LSD's ratio does
        #: not require a new diff name.
        self.torque_bias_ratio = (self.DIFF_BIAS[diff] if torque_bias_ratio is None
                                  else float(torque_bias_ratio))
        self.locking = (self.DIFF_LOCKING[diff] if locking is None
                        else float(locking))
        self._tire = tire if tire is not None else default_tire()
        self._params = params if params is not None else schema.RV_1
        self._params.check()
        self.state = BicycleState()
        self._last = {"a_x": 0.0, "a_y": 0.0}
        self._last_wheels: dict[str, WheelForces] | None = None

    # -- design ------------------------------------------------------------

    def set_design(self, params: schema.VehicleParams) -> None:
        params.check()
        self._params = params

    @property
    def params(self) -> schema.VehicleParams:
        return self._params

    @property
    def tire(self) -> MF02Tire:
        return self._tire

    @property
    def envelope(self) -> schema.TireEnvelope:
        return self._tire.envelope

    def __repr__(self) -> str:
        p = self._params
        return (f"DoubleTrackBackend(m={p.mass:.0f} kg, track={p.track_f:.3f}/"
                f"{p.track_r:.3f} m, roll front share="
                f"{p.roll_stiffness_front_share:.2f})")

    # -- loads -------------------------------------------------------------

    def wheel_loads(self, a_x: float = 0.0, a_y: float = 0.0) -> dict[str, float]:
        """Per-wheel vertical load, N. The whole reason this model exists.

        Longitudinal transfer is ``m*a_x*h/L`` between axles, as in the bicycle
        model. Lateral transfer is ``m*a_y*h`` as a moment, divided between the
        axles by roll stiffness and converted to a force by each axle's own
        track width.

        Signs: a left turn is ``a_y > 0``, and the body's inertia then pushes
        load onto the **right**-hand wheels. Braking is ``a_x < 0`` and moves
        load **forward**. Both are asserted in D5.

        The four loads always sum to ``mg`` exactly — transfer moves load, it
        never creates any — which is D5's first and cheapest check.
        """
        p = self._params
        axle_f = p.weight * p.b / p.wheelbase - p.mass * a_x * p.com_height / p.wheelbase
        axle_r = p.weight * p.a / p.wheelbase + p.mass * a_x * p.com_height / p.wheelbase

        moment = p.mass * a_y * p.com_height          # N.m, positive in a left turn
        eps = p.roll_stiffness_front_share
        d_f = eps * moment / p.track_f
        d_r = (1.0 - eps) * moment / p.track_r

        return {
            "fl": 0.5 * axle_f - d_f, "fr": 0.5 * axle_f + d_f,
            "rl": 0.5 * axle_r - d_r, "rr": 0.5 * axle_r + d_r,
        }

    def wheel_lift_a_y(self) -> float:
        """Lateral acceleration at which the first inside wheel lifts, in g.

        Whichever axle runs out first. Compare against the static stability
        factor: a car that lifts a wheel below its SSF has a load-transfer bug,
        because SSF is the rigid-body rollover threshold and no elastic
        distribution can beat it.
        """
        p = self._params
        out = []
        for track, static_half, share in (
            (p.track_f, 0.5 * p.weight * p.b / p.wheelbase,
             p.roll_stiffness_front_share),
            (p.track_r, 0.5 * p.weight * p.a / p.wheelbase,
             1.0 - p.roll_stiffness_front_share),
        ):
            out.append(static_half * track / (share * p.mass * p.com_height))
        return min(out) / schema.G

    # -- kinematics --------------------------------------------------------

    def slip_angles(self, state: BicycleState | None = None) -> dict[str, float]:
        """Per-wheel slip angle, rad.

        The inside wheel of an axle travels slower than the outside one by
        ``r * track/2``, so their slip angles differ. Small, but it is one of
        the things a bicycle model averages away, and averaging it away is a
        choice worth not making silently.

        Both front wheels take the same steer angle — no Ackermann geometry
        difference. That is a real omission; the reference sheet lists an ideal
        rack as an open item, and Chrono will have a real one in Ep 16.
        """
        s = self.state if state is None else state
        p = self._params
        out = {}
        for corner in CORNERS:
            front = corner[0] == "f"
            left = corner[1] == "l"
            arm = p.a if front else -p.b
            track = p.track_f if front else p.track_r
            vy = s.v_y + arm * s.yaw_rate
            vx = max(s.v_x + (-1 if left else 1) * s.yaw_rate * track / 2.0,
                     self.MIN_SPEED)
            d = s.steer if front else 0.0
            out[corner] = math.atan2(vy * math.cos(d) - vx * math.sin(d),
                                     vx * math.cos(d) + vy * math.sin(d))
        return out

    def _wheel(self, corner: str, alpha: float, fz: float,
               fx: float = 0.0) -> WheelForces:
        fz = min(max(fz, 0.0), 5.0 * self._tire.envelope.declared_fz_max)
        if fz <= 0.0:
            # A lifted wheel makes no force at all. That is the physically
            # important case this model can represent and the bicycle one cannot.
            return WheelForces(fy=0.0, fx=0.0, alpha=alpha, kappa=0.0, fz=0.0)
        if fx and self.combined_slip:
            fy = float(self._tire.fy_combined(alpha, fz, fx))
        else:
            fy = float(self._tire.fy0(alpha, fz))
        return WheelForces(fy=fy, fx=fx, alpha=alpha, kappa=0.0, fz=fz)

    def drag(self, v_x: float) -> float:
        p = self._params
        return 0.5 * AIR_DENSITY * p.c_d * p.frontal_area * v_x * abs(v_x)

    # -- steady state ------------------------------------------------------

    def trim_skidpad(self, speed: float, radius: float, max_iter: int = 60,
                     guess: tuple[float, float] | None = None,
                     hold_speed: bool = True) -> TrimPoint:
        """Constant-radius, constant-speed cornering equilibrium.

        Same formulation as the bicycle model's — two unknowns (steer angle and
        body lateral velocity), two residuals (lateral force balance and yaw
        moment balance) — with one extra fixed point inside, because now the
        wheel loads depend on ``a_y`` and ``a_y`` depends on the loads.
        """
        p = self._params
        r = speed / radius
        eps_kappa = None

        def residual(u):
            steer, v_y = float(u[0]), float(u[1])
            st = BicycleState(v_x=speed, v_y=v_y, yaw_rate=r, steer=steer)
            alphas = self.slip_angles(st)
            a_y, a_x, drive = speed * r, 0.0, 0.0
            wheels = {}
            for _ in range(12):
                loads = self.wheel_loads(a_x, a_y)
                # Same differential the integrator uses. Left as a bare 50/50
                # split, the steady-state trim and the step-by-step model would
                # disagree about the drivetrain — and D2's
                # `trim_is_an_equilibrium_of_the_integrator` check exists because
                # that disagreement is exactly what must never be allowed.
                fx = (self.differential_forces(
                          drive, loads,
                          BicycleState(v_x=speed, v_y=0.0, yaw_rate=r, steer=steer))
                      if (hold_speed and drive) else {c: 0.0 for c in CORNERS})
                wheels = {c: self._wheel(c, alphas[c], loads[c], fx[c])
                          for c in CORNERS}
                fy_f = wheels["fl"].fy + wheels["fr"].fy
                fy_r = wheels["rl"].fy + wheels["rr"].fy
                fx_f = wheels["fl"].fx + wheels["fr"].fx
                fy_body = fy_f * math.cos(steer) + fx_f * math.sin(steer) + fy_r
                a_y_new = fy_body / p.mass
                drive_new = (fy_f * math.sin(steer) - p.mass * v_y * r
                             if hold_speed else 0.0)
                a_x_new = (-v_y * r if hold_speed
                           else -fy_f * math.sin(steer) / p.mass)
                done = (abs(a_y_new - a_y) < 1e-10 and abs(a_x_new - a_x) < 1e-10
                        and abs(drive_new - drive) < 1e-8)
                a_y, a_x, drive = a_y_new, a_x_new, drive_new
                if done:
                    break

            fy_f = wheels["fl"].fy + wheels["fr"].fy
            fy_r = wheels["rl"].fy + wheels["rr"].fy
            fx_f = wheels["fl"].fx + wheels["fr"].fx
            fy_body = fy_f * math.cos(steer) + fx_f * math.sin(steer) + fy_r
            m_z = self.yaw_moment(wheels, steer)
            return (np.array([fy_body - p.mass * speed * r, m_z]),
                    wheels, a_x, a_y, drive)

        u = np.array(guess if guess is not None
                     else [p.wheelbase / radius, p.b * r], dtype=float)
        f0 = residual(u)[0]
        for _ in range(max_iter):
            norm0 = float(np.max(np.abs(f0)))
            if norm0 < 1e-8:
                break
            jac = np.zeros((2, 2))
            for j in range(2):
                du = np.zeros(2)
                du[j] = 1e-7
                jac[:, j] = (residual(u + du)[0] - f0) / 1e-7
            try:
                step = np.linalg.solve(jac, f0)
            except np.linalg.LinAlgError:
                break
            lam = 1.0
            for _ in range(30):
                trial = u - lam * step
                f_trial = residual(trial)[0]
                if float(np.max(np.abs(f_trial))) < norm0:
                    u, f0 = trial, f_trial
                    break
                lam *= 0.5
            else:
                break

        res, wheels, a_x, a_y, drive = residual(u)
        return TrimPoint(
            speed=speed, radius=radius, a_y=speed * speed / radius, a_x=a_x,
            steer=float(u[0]), v_y=float(u[1]), yaw_rate=r,
            ackermann=p.wheelbase / radius, drive_force=drive,
            hold_speed=hold_speed, wheels=wheels,
            converged=bool(np.max(np.abs(res)) < 1e-4),
            residual=float(np.max(np.abs(res))),
        )

    def skidpad_sweep(self, radius: float, speeds,
                      hold_speed: bool = True) -> list[TrimPoint]:
        out, guess = [], None
        for v in speeds:
            pt = self.trim_skidpad(float(v), radius, guess=guess,
                                   hold_speed=hold_speed)
            out.append(pt)
            guess = (pt.steer, pt.v_y) if pt.converged else None
        return out

    def max_lateral_g(self, radius: float, lo: float = 5.0, hi: float = 60.0,
                      tol: float = 1e-3, hold_speed: bool = True) -> float:
        while hi - lo > tol:
            mid = 0.5 * (lo + hi)
            if self.trim_skidpad(mid, radius, hold_speed=hold_speed).converged:
                lo = mid
            else:
                hi = mid
        return (lo * lo / radius) / schema.G

    # -- Backend interface -------------------------------------------------

    def reset(self, speed: float, seed: int | None = None) -> np.ndarray:
        if speed < self.MIN_SPEED:
            raise ValueError(f"speed {speed} below MIN_SPEED {self.MIN_SPEED}")
        self.state = BicycleState(v_x=float(speed))
        self._last = {"a_x": 0.0, "a_y": 0.0}
        self._last_wheels = None
        return self.get_obs()

    # -- differential -------------------------------------------------------

    def driven_corners(self) -> tuple[str, str]:
        return ("fl", "fr") if self._params.drive == "fwd" else ("rl", "rr")

    def differential_forces(self, demand: float, loads: dict,
                            state: BicycleState | None = None) -> dict:
        """Longitudinal force per wheel, N. **One mechanism, not two.**

        An earlier version split this into a grip-proportional torque bias and a
        separate speed couple. That counted the same physical effect twice and gave
        the bias the wrong direction — F77. A differential does exactly one thing:
        it resists the two driven wheels rotating at different speeds, and **torque
        flows from the faster-turning wheel to the slower one.**

        That single rule produces both behaviours a differential is known for:

        * **No wheelspin.** The outside wheel travels further round the corner, so
          it turns faster and loses torque to the inside. The car is yawed OUT of
          the corner — the locked-diff push.
        * **Inside wheel spinning.** A light inside wheel turns faster than
          kinematics alone would have it, so torque flows OUT to the wheel that
          still grips. That is the traction an LSD is bought for.

        Opposite outcomes, same rule, selected by which wheel is actually faster.
        A model with a hard-coded bias direction cannot produce both.

        Stages: equal split, then the kinematic locking transfer, then grip caps,
        then an anti-spin transfer of whatever a saturated wheel cannot hold.
        """
        out = {c: 0.0 for c in CORNERS}
        if demand < 0.0:
            # Brakes are not the differential's business.
            for c in CORNERS:
                share = self.brake_bias if c[0] == "f" else 1.0 - self.brake_bias
                out[c] = demand * share / 2.0
            return out
        if demand == 0.0:
            return out

        driven = self.driven_corners()
        cap = {c: self.DIFF_CAP_FRACTION * float(self._tire.peak_fx(loads[c]))
               for c in driven}
        r = self.torque_bias_ratio

        # --- stage 1: equal torque. This is all an open differential ever does.
        if not self.locking and r <= 1.0:
            each = min(demand / 2.0, min(cap[c] for c in driven))
            for c in driven:
                out[c] = each
            return out
        f = {c: demand / 2.0 for c in driven}

        # --- stage 2: the locking transfer, from the faster wheel to the slower.
        # Kinematically the OUTSIDE wheel turns faster, so torque goes inboard.
        track = (self._params.track_f if driven[0][0] == "f"
                 else self._params.track_r)
        inside = outside = None
        if state is not None and state.yaw_rate:
            left = [c for c in driven if c[1] == "l"][0]
            right = [c for c in driven if c[1] == "r"][0]
            inside, outside = ((left, right) if state.yaw_rate > 0.0
                               else (right, left))
            v = max(abs(state.v_x), self.MIN_SPEED)
            k_kappa = 0.5 * sum(
                float(self._tire.longitudinal_slip_stiffness(loads[c]))
                for c in driven)
            d_f = 0.5 * k_kappa * abs(state.yaw_rate) * track / v * self.locking
            f[inside] += d_f
            f[outside] -= d_f

        # --- stage 3: grip caps, and the anti-spin transfer.
        for c in driven:
            other = driven[1] if c == driven[0] else driven[0]
            if f[c] <= cap[c]:
                continue
            excess = f[c] - cap[c]
            f[c] = cap[c]
            # The saturated wheel is spinning, so it is now the faster one and the
            # device moves torque away from it -- limited by the other wheel's grip
            # and by how unequally this device can share at all.
            room = cap[other] - f[other]
            if math.isfinite(r):
                room = min(room, max(0.0, cap[c] * r - f[other]))
            f[other] += max(0.0, min(excess, room))
        # Capped in BOTH directions. A locking device genuinely drags the outside
        # wheel backwards at part throttle -- that is the binding you feel in a
        # welded car -- but a tire cannot produce more rearward force than grip
        # allows any more than it can produce forward force. Left uncapped, the
        # couple invented drag the contact patch could not deliver.
        for c in driven:
            out[c] = max(-cap[c], min(f[c], cap[c]))
        return out

    # -- yaw moment ---------------------------------------------------------

    def wheel_position(self, corner: str) -> tuple[float, float]:
        """Contact-patch position in the body frame, metres.

        ISO 8855: x forward, **y LEFT**. So the left wheels sit at positive y and
        the right wheels at negative y, and that sign is what decides which way a
        drivetrain asymmetry rotates the car.
        """
        p = self._params
        x = p.a if corner[0] == "f" else -p.b
        half = 0.5 * (p.track_f if corner[0] == "f" else p.track_r)
        return x, (half if corner[1] == "l" else -half)

    def body_forces(self, corner: str, w: "WheelForces",
                    steer: float) -> tuple[float, float]:
        """One wheel's force resolved from the wheel frame into the body frame."""
        if corner[0] == "f":
            c, sn = math.cos(steer), math.sin(steer)
            return w.fx * c - w.fy * sn, w.fx * sn + w.fy * c
        return w.fx, w.fy

    def yaw_moment(self, wheels: dict, steer: float) -> float:
        """Yaw moment about the centre of gravity, N.m. Positive = nose left.

        ``M_z = sum over wheels of (x_w * Fy_body - y_w * Fx_body)``

        The second term is the **drivetrain yaw moment**, and it was absent from
        this model for the whole of Seasons 1-3. Both previous ``m_z`` expressions
        carried only the longitudinal moment arms::

            m_z = a * (fy_f * cos(steer) + fx_f * sin(steer)) - b * fy_r

        so moving the entire drive force from the left wheel to the right changed
        the computed yaw moment by exactly zero. **Torque vectoring is that term**,
        which means Season 4 would have measured a null result and nothing would
        have errored. See FINDINGS F72.

        Written as a per-wheel sum rather than by bolting a correction onto the old
        expression, because the sum is provably a superset: expand it under a
        symmetric drive split and the two ``-y_w * Fx_body`` terms cancel, leaving
        the original formula exactly. That is what makes every Season 1-3 result
        unaffected, and it is asserted by a test rather than assumed.
        """
        m = 0.0
        for c, w in wheels.items():
            x, y = self.wheel_position(c)
            fx_b, fy_b = self.body_forces(c, w, steer)
            m += x * fy_b - y * fx_b
        return m

    def derivatives(self, state: BicycleState, drive_force: float,
                    steer_rate: float = 0.0):
        p, s = self._params, state
        alphas = self.slip_angles(s)
        a_x, a_y = self._last["a_x"], self._last["a_y"]
        wheels = {}
        for _ in range(6):
            loads = self.wheel_loads(a_x, a_y)
            fx = self.differential_forces(drive_force, loads, s)
            wheels = {c: self._wheel(c, alphas[c], loads[c], fx[c]) for c in CORNERS}
            fy_f = wheels["fl"].fy + wheels["fr"].fy
            fy_r = wheels["rl"].fy + wheels["rr"].fy
            fx_f = wheels["fl"].fx + wheels["fr"].fx
            fx_r = wheels["rl"].fx + wheels["rr"].fx
            fx_body = (fx_f * math.cos(s.steer) - fy_f * math.sin(s.steer)
                       + fx_r - self.drag(s.v_x))
            fy_body = fy_f * math.cos(s.steer) + fx_f * math.sin(s.steer) + fy_r
            a_x_new, a_y_new = fx_body / p.mass, fy_body / p.mass
            if abs(a_x_new - a_x) < 1e-9 and abs(a_y_new - a_y) < 1e-9:
                a_x, a_y = a_x_new, a_y_new
                break
            a_x, a_y = a_x_new, a_y_new

        m_z = self.yaw_moment(wheels, s.steer)
        d = BicycleState(
            v_x=a_x + s.v_y * s.yaw_rate,
            v_y=a_y - s.v_x * s.yaw_rate,
            yaw_rate=m_z / p.i_zz,
            steer=steer_rate,
            x=s.v_x * math.cos(s.heading) - s.v_y * math.sin(s.heading),
            y=s.v_x * math.sin(s.heading) + s.v_y * math.cos(s.heading),
            heading=s.yaw_rate,
            t=1.0,
        )
        return d, a_x, a_y, wheels

    def step(self, action: np.ndarray, dt: float) -> tuple[np.ndarray, StepInfo]:
        action = np.asarray(action, dtype=float)
        sr = float(self.act_space.select(action, "steer_rate"))
        drive = float(self.act_space.select(action, "drive_force"))
        s0 = self.state
        k1, a_x, a_y, wheels = self.derivatives(s0, drive, sr)
        k2 = self.derivatives(_advance(s0, k1, dt / 2), drive, sr)[0]
        k3 = self.derivatives(_advance(s0, k2, dt / 2), drive, sr)[0]
        k4 = self.derivatives(_advance(s0, k3, dt), drive, sr)[0]
        self.state = _advance(s0, BicycleState(*(
            (a + 2 * b + 2 * c + e) / 6 for a, b, c, e in zip(
                k1.as_array(), k2.as_array(), k3.as_array(), k4.as_array()))), dt)
        self.state.v_x = max(self.state.v_x, self.MIN_SPEED)
        self._last = {"a_x": a_x, "a_y": a_y}
        self._last_wheels = wheels
        log = self._log(wheels)
        return self.get_obs(), StepInfo(
            t=self.state.t, a_x=a_x, a_y=a_y, wheel_log=log,
            position=np.array([self.state.x, self.state.y]),
            heading=self.state.heading,
            envelope_violation=self.envelope_violated(log),
        )

    def _log(self, wheels: dict[str, WheelForces]) -> np.ndarray:
        kw = {}
        for c in CORNERS:
            kw[f"alpha_{c}"] = wheels[c].alpha
            kw[f"kappa_{c}"] = wheels[c].kappa
            kw[f"fz_{c}"] = wheels[c].fz
        return self.wheel_log_space.pack(**kw)

    def wheel_log(self) -> np.ndarray:
        if self._last_wheels is not None:
            return self._log(self._last_wheels)
        alphas = self.slip_angles()
        loads = self.wheel_loads(self._last["a_x"], self._last["a_y"])
        kw = {}
        for c in CORNERS:
            kw[f"alpha_{c}"] = alphas[c]
            kw[f"kappa_{c}"] = 0.0
            kw[f"fz_{c}"] = loads[c]
        return self.wheel_log_space.pack(**kw)

    def get_obs(self) -> np.ndarray:
        s = self.state
        alphas = self.slip_angles()
        loads = self.wheel_loads(self._last["a_x"], self._last["a_y"])
        return self.obs_space.pack(
            v_x=s.v_x, v_y=s.v_y, yaw_rate=s.yaw_rate,
            beta=math.atan2(s.v_y, max(s.v_x, self.MIN_SPEED)),
            a_y=self._last["a_y"],
            alpha_f=0.5 * (alphas["fl"] + alphas["fr"]),
            alpha_r=0.5 * (alphas["rl"] + alphas["rr"]),
            fz_f=loads["fl"] + loads["fr"], fz_r=loads["rl"] + loads["rr"],
            steer=s.steer,
        )


def understeer_gradient(points, a_y_g_max: float = 0.5) -> tuple[float, float]:
    """Fit ``K`` in deg/g from a double-track sweep. Same definition as Ep 3."""
    usable = [p for p in points if p.converged and p.a_y_g <= a_y_g_max]
    if len(usable) < 3:
        raise ValueError(f"need >= 3 converged points below {a_y_g_max} g")
    x = np.array([p.a_y_g for p in usable])
    y = np.array([p.understeer_angle_deg for p in usable])
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return float(slope), 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0


def _advance(s: BicycleState, d: BicycleState, dt: float) -> BicycleState:
    return BicycleState(*(a + b * dt for a, b in zip(s.as_array(), d.as_array())))


__all__ = ["DoubleTrackBackend", "TrimPoint", "WheelForces", "CORNERS",
           "understeer_gradient"]
