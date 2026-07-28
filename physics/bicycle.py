"""The simplest car that can understeer: two axles, one track.

Episodes 1-4 run on this. It is deliberately underpowered, and the places where
it is wrong are the point — Episode 5 is the comparison against the double-track
model that motivates the upgrade.

What it has
-----------
* Two axles, each with a real MF 2002 tire.
* Longitudinal load transfer, so braking loads the front and accelerating loads
  the rear.
* Aerodynamic drag.
* A steady-state trim solver, so the skidpad is solved rather than simulated.

What it does not have, and why that matters
-------------------------------------------
* **No track width, so no lateral load transfer.** This is the big one. A real
  car in a corner puts more load on its outside tires and less on its inside
  ones, and because peak grip falls with load (FINDINGS F1) that costs the axle
  grip. A bicycle model cannot represent it, and therefore cannot represent an
  anti-roll bar, a roll-stiffness split, or anything else that works by moving
  load side to side. Expect the understeer gradient to come out **low** for that
  reason — see the D3 diagnostic, which measures how low.
* **No suspension compliance, no aligning torque, no roll camber, no roll
  steer.** The Bundorf decomposition in ``docs/vehicle-reference-parameters.md``
  §4 attributes roughly 3 of a real car's 4.1 deg/g to exactly these. We model
  none of them, so our number must land below a real car's.
* **Combined slip is a friction ellipse, not a fitted model.** A tire braking
  and cornering at once loses lateral force for the longitudinal force it makes
  — that much is certain, and it is modelled. The *shape* of the trade-off is an
  assumption; MF 2002's own fitted weighting functions are not in this file. See
  ``MF02Tire.fy_combined`` and open item O2.

Each axle is modelled as **two tires each carrying half the axle load**, not one
tire carrying all of it. With load sensitivity in play those are materially
different — one tire at 7,200 N makes far less than two at 3,600 N — and the
real car has two.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from . import schema
from .backend import Backend, StepInfo
from .tire import MF02Tire, default_tire

AIR_DENSITY = 1.225  # kg/m^3, sea level, 15 C [ASSUMED]


@dataclass
class BicycleState:
    """Body-frame velocities plus ground-frame pose."""

    v_x: float = 20.0
    v_y: float = 0.0
    yaw_rate: float = 0.0
    steer: float = 0.0
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0
    t: float = 0.0

    def as_array(self) -> np.ndarray:
        return np.array([self.v_x, self.v_y, self.yaw_rate, self.steer,
                         self.x, self.y, self.heading, self.t])


@dataclass
class AxleForces:
    """What one axle produced, for both tires together."""

    fy: float          # N, body-frame lateral (before the steer rotation)
    fx: float          # N, along the wheel's own heading
    alpha: float       # rad, slip angle
    kappa: float       # dimensionless, slip ratio
    fz_per_tire: float  # N


class BicycleBackend(Backend):
    """Two-axle model. See the module docstring for what it cannot do."""

    obs_space = schema.OBS_BICYCLE
    act_space = schema.ACT_BICYCLE
    wheel_log_space = schema.WHEEL_LOG_BICYCLE

    #: Below this speed the slip-angle definition (which divides by v_x) is
    #: meaningless. The .tir file declares its own VXLOW = 1 m/s for the same
    #: reason; we use a slightly larger value and refuse rather than fudge.
    MIN_SPEED = 2.0

    def __init__(self, params: schema.VehicleParams | None = None,
                 tire: MF02Tire | None = None, combined_slip: bool = True,
                 brake_bias: float = 0.65):
        #: Whether a tire making longitudinal force loses lateral force for it.
        #: On by default — off would make trail braking look like free grip.
        #: Friction ellipse, the placeholder; see MF02Tire.fy_combined and O2.
        self.combined_slip = combined_slip
        #: Fraction of braking effort at the front axle. 0.65 is conventional for
        #: a road car [ASSUMED]; braking is applied at both axles, unlike drive.
        self.brake_bias = brake_bias
        self._tire = tire if tire is not None else default_tire()
        self._params = params if params is not None else schema.RV_1
        self._params.check()
        self.state = BicycleState()
        self._last = {"a_x": 0.0, "a_y": 0.0}
        self._last_axles: tuple[AxleForces, AxleForces] | None = None

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
        return (f"BicycleBackend(m={p.mass:.0f} kg, L={p.wheelbase:.3f} m, "
                f"front={p.front_mass_fraction:.2f}, Izz={p.i_zz:.0f})")

    # -- physics -----------------------------------------------------------

    def axle_loads(self, a_x: float = 0.0) -> tuple[float, float]:
        """Per-axle vertical load (N), including longitudinal transfer.

        Gate 1 invariant #4: braking (``a_x < 0``) must move load **forward**.
        With ``transfer = m*a_x*h/L`` subtracted from the front, braking gives a
        negative ``a_x``, so the front gains. That sign is asserted in D2.
        """
        p = self._params
        static_f = p.weight * p.b / p.wheelbase
        static_r = p.weight * p.a / p.wheelbase
        transfer = p.mass * a_x * p.com_height / p.wheelbase
        return static_f - transfer, static_r + transfer

    def slip_angles(self, state: BicycleState | None = None) -> tuple[float, float]:
        """``(alpha_front, alpha_rear)`` in rad, per the schema's sign convention.

        ``alpha = arctan(v_y / v_x)`` in each wheel's own frame, so a wheel whose
        contact point slides left has a positive slip angle and the tire pushes
        back to the right.
        """
        s = self.state if state is None else state
        p = self._params
        v_x = max(s.v_x, self.MIN_SPEED)

        # front: rotate the contact-point velocity into the steered wheel frame
        vy_f = s.v_y + p.a * s.yaw_rate
        alpha_f = math.atan2(vy_f * math.cos(s.steer) - v_x * math.sin(s.steer),
                             v_x * math.cos(s.steer) + vy_f * math.sin(s.steer))
        alpha_r = math.atan2(s.v_y - p.b * s.yaw_rate, v_x)
        return alpha_f, alpha_r

    def _axle(self, alpha: float, fz_axle: float, fx_demand: float = 0.0) -> AxleForces:
        """Forces from one axle. Two tires, each carrying half the axle load."""
        # The Newton line search explores wildly non-physical states on its way
        # somewhere sane, and MF's exp(PKX3*dfz) overflows for absurd loads. Clamp
        # the evaluation to a generous multiple of the file's own declared maximum:
        # those samples are rejected by the line search anyway, and a float
        # overflow warning in the middle of a sweep hides real problems.
        fz_tire = min(max(fz_axle, 0.0) / 2.0,
                      5.0 * self._tire.envelope.declared_fz_max)
        if fz_tire <= 0.0:
            # A lifted axle makes no force. Worth handling explicitly rather than
            # letting the Magic Formula divide by a zero peak force — the solver's
            # line search does explore states like this on its way somewhere sane.
            return AxleForces(fy=0.0, fx=0.0, alpha=alpha, kappa=0.0, fz_per_tire=0.0)
        if fx_demand and self.combined_slip:
            # The tire is being asked to brake or drive AND corner at the same
            # time, and it has one force budget for both. Without this the model
            # would report trail braking as free grip — see FINDINGS D9.
            fy = 2.0 * float(
                self._tire.fy_combined(alpha, fz_tire, fx_demand / 2.0)
            )
        else:
            fy = 2.0 * float(self._tire.fy0(alpha, fz_tire))
        kappa = self._kappa_for(fx_demand / 2.0, fz_tire) if fx_demand else 0.0
        return AxleForces(fy=fy, fx=fx_demand, alpha=alpha, kappa=kappa,
                          fz_per_tire=fz_tire)

    def _kappa_for(self, fx_per_tire: float, fz_tire: float,
                   tol: float = 1e-3) -> float:
        """Invert ``Fx0(kappa, Fz)`` for the slip ratio that delivers ``fx_per_tire``.

        CLAUDE.md forbids modelling coasting as ``kappa = 0`` — for a tire with
        the file's offsets that would produce free thrust (FINDINGS F7), and even
        offset-free it is the wrong causal direction: a driver commands force,
        and slip is what results. Bisection, because the curve is monotone over
        the range we allow and this is not a hot loop.
        """
        if fz_tire <= 0.0:
            return 0.0
        lo, hi = -self.envelope.imposed_kappa_max, self.envelope.imposed_kappa_max
        f_lo = float(self._tire.fx0(lo, fz_tire))
        f_hi = float(self._tire.fx0(hi, fz_tire))
        if fx_per_tire <= f_lo:
            return lo
        if fx_per_tire >= f_hi:
            return hi
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if float(self._tire.fx0(mid, fz_tire)) < fx_per_tire:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol * 1e-3:
                break
        return 0.5 * (lo + hi)

    def drag(self, v_x: float) -> float:
        """Aerodynamic drag force, N, always opposing motion. No downforce."""
        p = self._params
        return 0.5 * AIR_DENSITY * p.c_d * p.frontal_area * v_x * abs(v_x)

    def derivatives(self, state: BicycleState, drive_force: float,
                    steer_rate: float = 0.0):
        """``(dstate, a_x, a_y, front, rear)`` — the equations of motion.

        Body frame, ISO 8855. ``drive_force`` is the net longitudinal demand at
        the driven axle, in newtons, before drag.
        """
        p = self._params
        s = state
        alpha_f, alpha_r = self.slip_angles(s)

        # Load transfer depends on a_x, which depends on the forces, which depend
        # on the loads. One fixed-point pass is plenty: the coupling is weak
        # (a 0.5 g change moves the split by ~9%) and iterating to convergence
        # buys nothing measurable. D2 checks the residual.
        a_x_guess = self._last["a_x"]
        for _ in range(3):
            fz_f, fz_r = self.axle_loads(a_x_guess)
            if drive_force < 0.0:
                # Braking acts on all four wheels, split by the brake bias.
                fx_f = drive_force * self.brake_bias
                fx_r = drive_force * (1.0 - self.brake_bias)
            else:
                fx_f = drive_force if p.drive == "fwd" else 0.0
                fx_r = drive_force if p.drive == "rwd" else 0.0
            front = self._axle(alpha_f, fz_f, fx_f)
            rear = self._axle(alpha_r, fz_r, fx_r)
            fx_body = (front.fx * math.cos(s.steer) - front.fy * math.sin(s.steer)
                       + rear.fx - self.drag(s.v_x))
            # Load transfer is caused by the acceleration of the centre of mass
            # along the body x-axis, which is Fx/m — NOT by dv_x/dt. The two
            # differ by the centripetal term v_y*r, which is kinematics, not a
            # force, and including it here double-counts. Getting this wrong
            # inverts the car's limit balance: it made a hard corner appear to
            # decelerate three times harder than it does, shifting enough load
            # forward to turn terminal understeer into terminal oversteer.
            a_x_new = fx_body / p.mass
            if abs(a_x_new - a_x_guess) < 1e-6:
                a_x_guess = a_x_new
                break
            a_x_guess = a_x_new

        fy_body = front.fy * math.cos(s.steer) + front.fx * math.sin(s.steer) + rear.fy
        # Likewise a_y is the centre of mass's lateral acceleration — what an
        # accelerometer reads, and what "lateral g" means everywhere in the docs.
        a_y = fy_body / p.mass
        m_z = (p.a * (front.fy * math.cos(s.steer) + front.fx * math.sin(s.steer))
               - p.b * rear.fy)

        d = BicycleState(
            v_x=a_x_guess + s.v_y * s.yaw_rate,
            v_y=a_y - s.v_x * s.yaw_rate,
            yaw_rate=m_z / p.i_zz,
            steer=steer_rate,
            x=s.v_x * math.cos(s.heading) - s.v_y * math.sin(s.heading),
            y=s.v_x * math.sin(s.heading) + s.v_y * math.cos(s.heading),
            heading=s.yaw_rate,
            t=1.0,
        )
        return d, a_x_guess, a_y, front, rear

    # -- Backend interface -------------------------------------------------

    def reset(self, speed: float, seed: int | None = None) -> np.ndarray:
        if speed < self.MIN_SPEED:
            raise ValueError(
                f"speed {speed} m/s is below MIN_SPEED {self.MIN_SPEED}; the slip "
                "angle definition divides by v_x and stops meaning anything here."
            )
        self.state = BicycleState(v_x=float(speed))
        self._last = {"a_x": 0.0, "a_y": 0.0}
        self._last_axles = None
        return self.get_obs()

    def step(self, action: np.ndarray, dt: float) -> tuple[np.ndarray, StepInfo]:
        action = np.asarray(action, dtype=float)
        steer_rate = float(self.act_space.select(action, "steer_rate"))
        drive_force = float(self.act_space.select(action, "drive_force"))

        # Classic RK4. D2's timestep-convergence check is what justifies it over
        # something cheaper.
        s0 = self.state
        k1, a_x, a_y, front, rear = self.derivatives(s0, drive_force, steer_rate)
        k2 = self.derivatives(_advance(s0, k1, dt / 2), drive_force, steer_rate)[0]
        k3 = self.derivatives(_advance(s0, k2, dt / 2), drive_force, steer_rate)[0]
        k4 = self.derivatives(_advance(s0, k3, dt), drive_force, steer_rate)[0]
        self.state = _advance(
            s0,
            BicycleState(*(
                (a + 2 * b + 2 * c + d) / 6
                for a, b, c, d in zip(k1.as_array(), k2.as_array(),
                                      k3.as_array(), k4.as_array())
            )),
            dt,
        )
        self.state.v_x = max(self.state.v_x, self.MIN_SPEED)
        self._last = {"a_x": a_x, "a_y": a_y}
        self._last_axles = (front, rear)

        log = self._wheel_log(front, rear)
        return self.get_obs(), StepInfo(
            t=self.state.t,
            a_x=a_x,
            a_y=a_y,
            wheel_log=log,
            position=np.array([self.state.x, self.state.y]),
            heading=self.state.heading,
            envelope_violation=self.envelope_violated(log),
        )

    def get_obs(self) -> np.ndarray:
        s = self.state
        alpha_f, alpha_r = self.slip_angles()
        fz_f, fz_r = self.axle_loads(self._last["a_x"])
        return self.obs_space.pack(
            v_x=s.v_x, v_y=s.v_y, yaw_rate=s.yaw_rate,
            beta=math.atan2(s.v_y, max(s.v_x, self.MIN_SPEED)),
            a_y=self._last["a_y"],
            alpha_f=alpha_f, alpha_r=alpha_r,
            fz_f=fz_f, fz_r=fz_r, steer=s.steer,
        )

    def _wheel_log(self, front: AxleForces, rear: AxleForces) -> np.ndarray:
        return self.wheel_log_space.pack(
            alpha_f=front.alpha, kappa_f=front.kappa, fz_f=front.fz_per_tire,
            alpha_r=rear.alpha, kappa_r=rear.kappa, fz_r=rear.fz_per_tire,
        )

    def wheel_log(self) -> np.ndarray:
        """Current per-wheel slip angle, slip ratio and load.

        Returns what the last :meth:`step` actually produced. It used to
        recompute the slip angles and hardcode the slip ratios to zero, which
        meant :meth:`Backend.envelope_violated` — whose default path is this
        method — could never see a slip-ratio violation. Non-negotiable #1 says
        envelope instrumentation is core-loop; a logger that silently reports
        zero for one of its three channels is worse than none, because it makes
        the occupancy statistic look clean.
        """
        if self._last_axles is not None:
            return self._wheel_log(*self._last_axles)
        # Nothing stepped yet: report the current kinematic state at zero
        # longitudinal force, which is what a freshly reset car is doing.
        alpha_f, alpha_r = self.slip_angles()
        fz_f, fz_r = self.axle_loads(self._last["a_x"])
        return self.wheel_log_space.pack(
            alpha_f=alpha_f, kappa_f=0.0, fz_f=fz_f / 2,
            alpha_r=alpha_r, kappa_r=0.0, fz_r=fz_r / 2,
        )

    # -- steady state ------------------------------------------------------

    def trim_skidpad(self, speed: float, radius: float, max_iter: int = 60,
                     guess: tuple[float, float] | None = None,
                     hold_speed: bool = True) -> "SkidpadPoint":
        """Solve the constant-radius, constant-speed cornering equilibrium.

        Solved rather than simulated: at steady state the transients are gone by
        definition, and a two-variable Newton solve gives the answer to machine
        precision in milliseconds instead of integrating for ten seconds and
        hoping. Sweeping speed on a fixed radius then gives the understeer
        gradient directly.

        ``hold_speed`` selects the protocol, and it is not a detail. A real
        constant-radius test (SAE J266) is run at **constant speed**: the driver
        holds the throttle so the net longitudinal force is zero, and there is no
        longitudinal load transfer. That is the default.

        Coasting instead — ``hold_speed=False`` — lets the steered front tire drag
        the car down at about 0.04 g, which shifts load forward, unloads the rear
        and tips the car into terminal oversteer at 86% of its grip. That is a
        property of the *protocol*, not of the car, and getting the two confused
        is exactly the kind of error this project exists to avoid.

        What ``hold_speed`` does not model is the grip the balancing drive force
        costs the rear tires, because combined slip is open item O2. Check
        ``drive_force_fraction`` on the result: while it stays small the omission
        is small too.

        Unknowns are the road-wheel steer angle and the body lateral velocity;
        the residuals are lateral force balance and yaw moment balance.
        """
        p = self._params
        r = speed / radius            # yaw rate for a left turn, rad/s
        a_y_target = speed * speed / radius

        def residual(u):
            steer, v_y = float(u[0]), float(u[1])
            st = BicycleState(v_x=speed, v_y=v_y, yaw_rate=r, steer=steer)
            alpha_f, alpha_r = self.slip_angles(st)
            # A steered front tire's lateral force has a rearward component,
            # -Fy_f*sin(delta), so the car decelerates even with no drive and no
            # drag — which transfers load forward. Small (about 0.04 g at 0.5 g
            # of cornering) but it is exactly what the integrator sees, and
            # ignoring it here would make the trim a solution to a slightly
            # different problem. Same fixed point as `derivatives`.
            a_x, drive = 0.0, 0.0
            for _ in range(8):
                fz_f, fz_r = self.axle_loads(a_x)
                # The drive force that holds speed costs the driven axle lateral
                # grip (friction ellipse), and less lateral grip means less drag
                # from the steered front tire, which changes the drive force.
                # One fixed point covers both.
                fx_f = drive if p.drive == "fwd" else 0.0
                fx_r = drive if p.drive == "rwd" else 0.0
                front = self._axle(alpha_f, fz_f, fx_f)
                rear = self._axle(alpha_r, fz_r, fx_r)
                # "Constant speed" means dv_x/dt = 0, and dv_x/dt = Fx/m + v_y*r.
                # So the body-axis acceleration is -v_y*r, NOT zero: in a circle
                # with sideslip, the purely centripetal acceleration of the centre
                # of mass has a small component along the body x-axis. Setting
                # Fx/m = 0 instead leaves dv_x/dt = v_y*r and the car slowly
                # changes speed, so the "steady state" is not one — it drifts
                # 0.2% off the commanded radius over a single lap.
                drive_new = (front.fy * math.sin(steer) - p.mass * v_y * r
                             if hold_speed else 0.0)
                # hold_speed models the real test: the driver keeps the speed
                # constant, so the net longitudinal force is zero and there is no
                # load transfer. Coasting instead lets the steered front tire drag
                # the car down, shifting load forward.
                a_x_new = (-v_y * r if hold_speed
                           else -front.fy * math.sin(steer) / p.mass)
                # Both must converge. Watching a_x alone silently accepted the
                # first iterate when holding speed, because a_x is identically
                # zero there and the drive force had not settled yet.
                done = abs(a_x_new - a_x) < 1e-12 and abs(drive_new - drive) < 1e-9
                a_x, drive = a_x_new, drive_new
                if done:
                    break
            fy = front.fy * math.cos(steer) + rear.fy
            m_z = p.a * front.fy * math.cos(steer) - p.b * rear.fy
            return (np.array([fy - p.mass * speed * r, m_z]),
                    front, rear, alpha_f, alpha_r, a_x, drive)

        # Kinematic starting guess: Ackermann steer, and the sideslip that makes
        # the rear slip angle zero. That is v_y = +b*r, the low-speed limit — the
        # sign matters, and getting it backwards sends the solver off to 90 deg
        # of slip where the tire curve has no gradient left to follow.
        u = np.array(guess if guess is not None
                     else [p.wheelbase / radius, p.b * r], dtype=float)

        # Newton with backtracking. Undamped Newton on a saturating tire curve
        # will happily step past the peak into the falling side, where the
        # gradient points the wrong way and it never comes back.
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
                break  # no downhill step exists: no equilibrium at this speed

        res, front, rear, alpha_f, alpha_r, a_x, drive = residual(u)
        converged = bool(np.max(np.abs(res)) < 1e-4)
        return SkidpadPoint(
            speed=speed, radius=radius, a_y=a_y_target,
            steer=float(u[0]), v_y=float(u[1]), yaw_rate=r,
            alpha_f=alpha_f, alpha_r=alpha_r,
            fz_f_per_tire=front.fz_per_tire, fz_r_per_tire=rear.fz_per_tire,
            fy_f=front.fy, fy_r=rear.fy,
            ackermann=p.wheelbase / radius, a_x=a_x,
            drive_force=drive, hold_speed=hold_speed,
            drive_axle_fx_peak=float(
                2 * self._tire.peak_fx(
                    (rear if p.drive == "rwd" else front).fz_per_tire)),
            converged=converged, residual=float(np.max(np.abs(res))),
        )


    def skidpad_sweep(self, radius: float, speeds,
                      hold_speed: bool = True) -> list["SkidpadPoint"]:
        """Trim a whole constant-radius sweep, warm-starting each solve.

        Continuation: each point starts from its neighbour's answer. Cheap, and
        it is what keeps the solve on the grippy side of the tire curve as the
        car approaches the limit. Points past the limit come back
        ``converged=False`` — that is the measurement of maximum lateral
        acceleration, not a failure.
        """
        out: list[SkidpadPoint] = []
        guess = None
        for v in speeds:
            pt = self.trim_skidpad(float(v), radius, guess=guess,
                                   hold_speed=hold_speed)
            out.append(pt)
            guess = (pt.steer, pt.v_y) if pt.converged else None
        return out

    def max_lateral_g(self, radius: float, lo: float = 5.0, hi: float = 60.0,
                      tol: float = 1e-3, hold_speed: bool = True) -> float:
        """Highest sustainable lateral acceleration on this radius, in g.

        Bisects on speed for the fastest still-solvable equilibrium. Past it no
        steer angle balances both equations at once — the car cannot hold the
        circle at all, which is the physical meaning of the limit.
        """
        while hi - lo > tol:
            mid = 0.5 * (lo + hi)
            if self.trim_skidpad(mid, radius, hold_speed=hold_speed).converged:
                lo = mid
            else:
                hi = mid
        return (lo * lo / radius) / schema.G


@dataclass
class SkidpadPoint:
    """One equilibrium on a constant-radius circle."""

    speed: float
    radius: float
    a_y: float
    steer: float
    v_y: float
    yaw_rate: float
    alpha_f: float
    alpha_r: float
    fz_f_per_tire: float
    fz_r_per_tire: float
    fy_f: float
    fy_r: float
    ackermann: float
    a_x: float
    #: Longitudinal force the driven axle must supply to hold speed, N. Zero when
    #: coasting. Its grip cost is NOT modelled — combined slip is open item O2 —
    #: so check `drive_force_fraction` before trusting a near-limit result.
    drive_force: float
    hold_speed: bool
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
        """``delta - Ackermann`` in degrees. Its slope against ``a_y`` is ``K``."""
        return math.degrees(self.steer - self.ackermann)

    #: Peak longitudinal force the driven axle could make at its current load,
    #: N. Set by the trim so `drive_force_fraction` means something.
    drive_axle_fx_peak: float = 0.0

    @property
    def drive_force_fraction(self) -> float:
        """Drive force as a fraction of the driven axle's longitudinal capability.

        How much of the tire's force budget the throttle is spending. This is the
        argument to the friction ellipse, so it is also how hard combined slip is
        working: at 0.05 the lateral cost is 0.1%, at 0.5 it is 13%.
        """
        return abs(self.drive_force) / max(self.drive_axle_fx_peak, 1.0)

    @property
    def sideslip_deg(self) -> float:
        return math.degrees(math.atan2(self.v_y, self.speed))


def understeer_gradient(points, a_y_g_max: float = 0.5) -> tuple[float, float]:
    """Fit ``K`` in deg/g from a skidpad sweep, over ``|a_y| <= a_y_g_max``.

    Returns ``(K, r_squared)``. The ±0.5 g window is the definition used in
    ``docs/vehicle-reference-parameters.md`` §4, and it matters: past that the
    curve bends and a single slope stops describing it.
    """
    usable = [p for p in points if p.converged and p.a_y_g <= a_y_g_max]
    if len(usable) < 3:
        raise ValueError(
            f"need >= 3 converged points below {a_y_g_max} g, got {len(usable)}"
        )
    x = np.array([p.a_y_g for p in usable])
    y = np.array([p.understeer_angle_deg for p in usable])
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return float(slope), 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0


def _advance(s: BicycleState, d: BicycleState, dt: float) -> BicycleState:
    return BicycleState(*(a + b * dt for a, b in zip(s.as_array(), d.as_array())))


__all__ = [
    "BicycleBackend",
    "BicycleState",
    "AxleForces",
    "SkidpadPoint",
    "understeer_gradient",
    "AIR_DENSITY",
]
