"""A driver who reacts — deterministic, hand-built, and pushed until it fails.

Season 1 and 2 drove with a solver that saw the whole road. Season 3 drove with a
learned policy. Episode 13 needs a third thing, and needs it for a specific reason:
**a controller can only be evaluated in closed loop.** A minimum-time solver handed
four independent wheel forces would simply use them optimally, which measures what
torque vectoring is worth to a driver who cannot be surprised — the question
Episode 8 already answered with "almost nothing" (F49). A learned driver would
confound the controller with the training run. What is left is the thing every
chassis engineer actually uses: a repeatable, unintelligent driver model, run with
the aid on and with the aid off.

The driver is deliberately simple and deliberately NOT a racing driver:

* **Steering is pure pursuit on the centreline.** It aims at a point a fixed time
  ahead and turns toward it. It does not know about racing lines, apexes or exit
  speed, and it cannot trade entry for exit. Every configuration therefore drives
  the same geometric path, which is what makes the comparison a comparison — a
  lap-time difference here cannot be a different line, because there is only one.
* **Speed comes from a quasi-steady-state profile.** The classic three passes:
  the cornering limit ``v = sqrt(a_lat / kappa)`` at every point, then a backward
  pass for how early you must brake, then a forward pass for how hard you can
  accelerate. This is the standard lap-time-simulation speed profile and it is a
  *plan*, so the driver is a tracker: feedforward from the profile, PI on the
  error.
* **One knob, ``grip_use``, decides how hard it tries.** The profile is built for
  ``grip_use`` times the car's measured grip. Turn it up and the driver asks for
  more than the tires have; the lap gets quicker until it does not, and then the
  car runs wide or slides past the edge of the tire fit. **The result of an
  experiment is the fastest lap that is still valid**, which is a limit property of
  the car-plus-controller rather than a property of how well the driver was tuned.

Why that last point matters: a single lap at a single aggression measures the
driver's tuning as much as the car's. Sweeping to failure measures where the
failure is. The gains are shared across every configuration and the sweep is
reported in full, so a reader can see the whole curve rather than one point off it.

**What this driver cannot say.** It never brakes in a corner, never trades line for
exit, and has no preview of anything but the centreline. Lap times from it are not
comparable with the optimal-control lap times of Seasons 1-2 in absolute terms
(rule 6) — they are slower, by construction, because a tracking driver is slower
than an optimiser. Comparisons *between* configurations driven by this same driver
are the claim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import schema
from .double_track import CORNERS, BicycleState, DoubleTrackBackend
from .track import Track

#: Control interval, s. 50 Hz, matching the RL environment so the two seasons'
#: drivers are given the same authority over the same car.
DT = 0.02

#: Actuator limits, identical to ``rl_env`` and to the optimal-control problems.
STEER_RATE_MAX = math.radians(200.0)
STEER_MAX = math.radians(30.0)
DRIVE_MAX = 4500.0
BRAKE_MAX = 12000.0

#: The slip bound every minimum-time solve in Seasons 1-2 enforces and the edge of
#: the region the tire file was fitted over. Ours, not the file's (CLAUDE.md rule 4).
ENVELOPE_SLIP_MAX_DEG = 12.0


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------

@dataclass
class SpeedProfile:
    """Target speed against distance: cornering limit, then braking, then power.

    Three passes over the same array, in the order every lap-time simulator has
    done it since the 1980s. The backward pass is the one that matters here — it
    is what makes the driver brake *before* the corner rather than in it, and a
    driver who brakes in the corner is a driver whose lap time is about brake
    modulation rather than about the car.
    """

    track: Track
    a_lat: float          # m/s^2, cornering limit the plan is built for
    a_brake: float        # m/s^2, deceleration the plan asks for (positive)
    a_drive: float        # m/s^2, acceleration the plan asks for
    v_max: float = 32.0   # m/s — the entry speed Seasons 1-2 solve from
    n_points: int = 2000

    def __post_init__(self):
        self.s = np.linspace(0.0, self.track.length, self.n_points)
        ds = float(self.s[1] - self.s[0])
        k = np.abs(np.asarray(self.track.curvature(self.s), dtype=float))
        with np.errstate(divide="ignore"):
            v = np.where(k > 1e-9, np.sqrt(self.a_lat / np.maximum(k, 1e-9)),
                         self.v_max)
        v = np.minimum(v, self.v_max)
        for i in range(len(v) - 2, -1, -1):        # brake into what is coming
            v[i] = min(v[i], math.sqrt(v[i + 1] ** 2 + 2.0 * self.a_brake * ds))
        for i in range(1, len(v)):                 # and only accelerate as hard
            v[i] = min(v[i], math.sqrt(v[i - 1] ** 2 + 2.0 * self.a_drive * ds))
        self.v = v

    def target(self, s: float) -> float:
        return float(np.interp(s, self.s, self.v))

    def slope(self, s: float) -> float:
        """dv/ds at ``s``, which is the feedforward the tracker needs."""
        return float(np.interp(s, self.s[:-1], np.diff(self.v) / np.diff(self.s)))


# ---------------------------------------------------------------------------
# Where am I?
# ---------------------------------------------------------------------------

class TrackLocator:
    """Cartesian pose -> ``(s, n, xi)`` by projection onto the centreline.

    By projection rather than by integrating the curvilinear rates, deliberately.
    The rates are what ``rl_env`` integrates and they are correct there, but they
    accumulate: a small error in ``s`` compounds over 400 m and the driver would be
    aiming at a preview point that is not where it thinks. Projection has no memory
    and therefore no drift. The search is restricted to a window around the last
    fix so a hairpin cannot snap the driver onto the wrong part of the track.
    """

    def __init__(self, track: Track, n_points: int = 4000, window: float = 40.0):
        self.track = track
        self.s_ref, self.x_ref, self.y_ref, self.h_ref = track.centreline(n_points)
        self.window = window
        self._last_i = 0

    def locate(self, x: float, y: float, heading: float) -> tuple[float, float, float]:
        step = self.s_ref[1] - self.s_ref[0]
        w = int(self.window / step)
        lo, hi = max(0, self._last_i - 4), min(len(self.s_ref), self._last_i + w)
        d2 = (self.x_ref[lo:hi] - x) ** 2 + (self.y_ref[lo:hi] - y) ** 2
        i = lo + int(np.argmin(d2))
        self._last_i = i
        s, h = float(self.s_ref[i]), float(self.h_ref[i])
        # +n is to the LEFT of the direction of travel, matching schema's frame
        # and track.to_xy's inverse.
        dx, dy = x - float(self.x_ref[i]), y - float(self.y_ref[i])
        n = -dx * math.sin(h) + dy * math.cos(h)
        xi = _wrap(heading - h)
        return s, n, xi

    def preview(self, s: float, ahead: float) -> tuple[float, float]:
        """Cartesian position of the centreline point ``ahead`` metres along.

        **Extrapolated past the end of the track along its final heading**, which
        is not cosmetic. Clamping the preview point to the last centreline sample
        makes the effective lookahead shrink to zero as the car arrives, and a
        pure-pursuit controller with no lookahead is unstable: the first version
        of this ran a clean lap and then threw the car into a 45-degree slide over
        the last ten metres, every time, on a straight. The road ends; the driver's
        idea of where it goes should not.
        """
        end = float(self.s_ref[-1])
        sp = s + ahead
        if sp <= end:
            return (float(np.interp(sp, self.s_ref, self.x_ref)),
                    float(np.interp(sp, self.s_ref, self.y_ref)))
        over, h = sp - end, float(self.h_ref[-1])
        return (float(self.x_ref[-1]) + over * math.cos(h),
                float(self.y_ref[-1]) + over * math.sin(h))


def _wrap(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------

@dataclass
class Driver:
    """Pure-pursuit steering, profile-tracking speed. Deterministic, no memory but one integral.

    Gains are [ASSUMED] and shared by every configuration compared with them.
    ``experiments/ep13/run.py`` sweeps them and requires the conclusion to survive,
    because a hand-tuned driver is exactly the sort of unstated protocol choice
    CLAUDE.md rule 9 was written about.
    """

    params: schema.VehicleParams
    profile: SpeedProfile
    locator: TrackLocator
    #: Preview time and its bounds, in seconds and metres. Aim this far ahead.
    t_look: float = 0.55
    l_look_min: float = 6.0
    l_look_max: float = 30.0
    #: Cross-track gain, in (m/s) per metre of offset — Stanley's form, applied as
    #: ``atan(k * n / v)``. Pure pursuit alone tracks a path it is already near;
    #: this is what pulls it back when it is not.
    #:
    #: **Scaled by 1/v, and that is the whole reason it is written this way.** As a
    #: plain gain in rad/m it is a fixed steering angle per metre of error, which is
    #: gentle at 16 m/s and violently over-geared at 32: the first version used
    #: 0.06 rad/m and drove a clean corner, then built a divergent weave down the
    #: exit straight and spun the car at 0.98 g on a road with no curvature in it.
    #: A cross-track correction has to get quieter as the car goes faster.
    k_offset: float = 0.5
    #: Speed loop, N per (m/s) of error, and its integral gain.
    k_v: float = 900.0
    k_vi: float = 400.0
    #: Zero-mean Gaussian noise on the commanded steering RATE, as a fraction of
    #: ``STEER_RATE_MAX``. Episode 11's convention and Episode 11's default value
    #: (0.15), so the two seasons' disturbance means the same thing. Applied after
    #: the driver has chosen: it is the hands and the linkage, and unlike a
    #: policy's exploration noise it does not go away at deployment (F54, F61).
    #: [ASSUMED] — a real figure would come from steering-robot repeatability data.
    steer_noise: float = 0.0
    #: POWER-REVIEW D-A, mirrored from ``optimal_control.Limits``: per-instance
    #: overrides of the module-level caps, defaulting to them so every existing
    #: caller is unaffected. ``drive_power`` (W, default ``None``) is additional,
    #: not a replacement — both ``drive_max`` and ``drive_power`` clip
    #: simultaneously when set, exactly as in the OC solver, so
    #: ``F = min(drive_max, drive_power / v)`` falls out of the two bounds
    #: rather than an if/else on which model is "the" model.
    drive_max: float = DRIVE_MAX
    brake_max: float = BRAKE_MAX
    drive_power: float | None = None
    _v_integral: float = 0.0
    _rng: np.random.Generator | None = None

    def reset(self, seed: int | None = None) -> None:
        self._v_integral = 0.0
        self._rng = np.random.default_rng(seed)

    def control(self, state: BicycleState, s: float, n: float, xi: float,
                dt: float) -> tuple[float, float]:
        """Returns ``(steer_rate, drive_force)`` for one control interval."""
        v = max(state.v_x, 1.0)
        ahead = float(np.clip(self.t_look * v, self.l_look_min, self.l_look_max))
        px, py = self.locator.preview(s, ahead)
        # Preview point in the body frame: x forward, y left (ISO 8855).
        dx, dy = px - state.x, py - state.y
        c, sn = math.cos(state.heading), math.sin(state.heading)
        fwd, lat = dx * c + dy * sn, -dx * sn + dy * c
        dist2 = max(fwd * fwd + lat * lat, 1e-6)
        curvature = 2.0 * lat / dist2                     # pure pursuit
        steer_cmd = (math.atan(self.params.wheelbase * curvature)
                     - math.atan(self.k_offset * n / v))
        steer_cmd = float(np.clip(steer_cmd, -STEER_MAX, STEER_MAX))
        steer_rate = float(np.clip((steer_cmd - state.steer) / dt,
                                   -STEER_RATE_MAX, STEER_RATE_MAX))
        if self.steer_noise:
            rng = self._rng if self._rng is not None else np.random.default_rng(0)
            steer_rate = float(np.clip(
                steer_rate + rng.normal(0.0, self.steer_noise * STEER_RATE_MAX),
                -STEER_RATE_MAX, STEER_RATE_MAX))

        v_target = self.profile.target(s)
        err = v_target - v
        self._v_integral = float(np.clip(self._v_integral + err * dt, -8.0, 8.0))
        # Feedforward: the profile already knows the car must be accelerating at
        # v*dv/ds here, so the loop only has to correct what the plan got wrong.
        a_ff = self.profile.slope(s) * v
        force = (self.params.mass * a_ff + self.k_v * err
                 + self.k_vi * self._v_integral)
        drive_cap = self.drive_max
        if self.drive_power is not None:
            # Additional, not replacing: self.drive_max still applies. v is
            # already floored at 1.0 above, so this division is always safe.
            drive_cap = min(drive_cap, self.drive_power / v)
        drive = float(np.clip(force, -self.brake_max, drive_cap))
        return steer_rate, drive


# ---------------------------------------------------------------------------
# One lap
# ---------------------------------------------------------------------------

@dataclass
class Lap:
    """One closed-loop lap, and everything rule 4 requires logged about it."""

    valid: bool
    reason: str
    lap_time: float
    grip_use: float
    log: dict[str, np.ndarray] = field(default_factory=dict)
    tv_log: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def worst_slip_deg(self) -> float:
        return float(np.max(self.log["alpha_max_deg"])) if len(self.log.get("alpha_max_deg", [])) else math.nan

    @property
    def peak_a_y_g(self) -> float:
        return float(np.max(np.abs(self.log["a_y"]))) / schema.G

    @property
    def max_offset(self) -> float:
        return float(np.max(np.abs(self.log["n"])))

    @property
    def mean_utilisation(self) -> float:
        """Mean over the lap of the busiest wheel's friction-ellipse usage."""
        return float(np.mean(self.log["utilisation_max"]))


def drive_lap(backend: DoubleTrackBackend, track: Track, driver: Driver,
              tv=None, dt: float = DT, max_steps: int = 4000,
              grip_use: float = 1.0, seed: int | None = None) -> Lap:
    """Drive one lap and return it, valid or not.

    Ordering inside the loop is load-bearing: the driver chooses, then the upper
    layer of the controller updates ONCE, then the physics integrates with that
    command held constant across its four RK4 substeps (see
    ``TorqueVectoring``'s docstring). Everything is logged from the arrays
    afterwards, never computed inside the loop (rule 7).
    """
    locator = driver.locator
    locator._last_i = 0
    driver.reset(seed)
    if tv is not None:
        tv.reset()
        backend.attach_torque_vectoring(tv)
    backend.reset(driver.profile.target(0.0))
    log = {k: [] for k in
           ("t", "s", "n", "xi", "speed", "v_target", "steer", "drive", "yaw_rate",
            "a_x", "a_y", "alpha_max_deg", "load_min", "utilisation_max",
            "envelope_violation")}
    for c in CORNERS:
        log[f"fx_{c}"] = []
        log[f"fy_{c}"] = []
        log[f"fz_{c}"] = []
        log[f"util_{c}"] = []

    reason, steps = "", 0
    s = n = xi = 0.0
    for steps in range(1, max_steps + 1):
        st = backend.state
        s, n, xi = locator.locate(st.x, st.y, st.heading)
        steer_rate, drive = driver.control(st, s, n, xi, dt)
        if tv is not None:
            # Both layers, once, on what the car's sensors could know at the top
            # of the interval: the loads implied by the last accelerations and the
            # lateral forces the tires were making. Held for the whole step.
            prev = backend._last_wheels
            tv.update(st, dt, demand=drive,
                      loads=backend.wheel_loads(backend._last["a_x"],
                                                backend._last["a_y"]),
                      lateral=({c: w.fy for c, w in prev.items()} if prev
                               else None))
        action = backend.act_space.pack(steer_rate=steer_rate, drive_force=drive)
        _, info = backend.step(action, dt)
        if tv is not None:
            tv.record(backend.state)

        wheels = backend._last_wheels or {}
        loads = {c: wheels[c].fz for c in CORNERS} if wheels else backend.wheel_loads()
        util = {}
        for c in CORNERS:
            w = wheels.get(c)
            fz = max(loads[c], 1.0)
            fx_p = float(backend.tire.peak_fx(fz))
            fy_p = float(backend.tire.peak_fy(fz))
            fx, fy = (w.fx, w.fy) if w else (0.0, 0.0)
            util[c] = math.hypot(fx / fx_p, fy / fy_p)
            log[f"fx_{c}"].append(float(fx))
            log[f"fy_{c}"].append(float(fy))
            log[f"fz_{c}"].append(float(fz))
            log[f"util_{c}"].append(float(util[c]))
        alphas = backend.slip_angles()
        log["t"].append(steps * dt)
        log["s"].append(s)
        log["n"].append(n)
        log["xi"].append(xi)
        log["speed"].append(float(backend.state.v_x))
        log["v_target"].append(driver.profile.target(s))
        log["steer"].append(float(backend.state.steer))
        log["drive"].append(float(drive))
        log["yaw_rate"].append(float(backend.state.yaw_rate))
        log["a_x"].append(float(info.a_x))
        log["a_y"].append(float(info.a_y))
        log["alpha_max_deg"].append(
            math.degrees(max(abs(v) for v in alphas.values())))
        log["load_min"].append(min(loads.values()))
        log["utilisation_max"].append(max(util.values()))
        log["envelope_violation"].append(bool(info.envelope_violation))

        if abs(n) > track.half_width:
            reason = "off track"
            break
        if backend.state.v_x < 3.0:
            reason = "stalled"
            break
        if abs(math.degrees(math.atan2(backend.state.v_y,
                                       max(backend.state.v_x, 1.0)))) > 45.0:
            reason = "spun"
            break
        if s >= track.length - 1.0:
            reason = "finished"
            break
    else:
        reason = "timed out"

    arrays = {k: np.asarray(v) for k, v in log.items()}
    worst_slip = (float(np.max(arrays["alpha_max_deg"]))
                  if len(arrays["alpha_max_deg"]) else math.inf)
    valid = reason == "finished"
    # Rule 4, and it is a per-LAP rule (F70's third lesson): a lap that left the
    # region the tire file supports is discarded whole, and only that lap.
    if valid and worst_slip > ENVELOPE_SLIP_MAX_DEG:
        valid, reason = False, f"outside the tire fit ({worst_slip:.1f} deg)"
    if tv is not None:
        backend.attach_torque_vectoring(None)
    # Interpolated across the finish rather than counted in steps. Counting
    # quantises every lap time to 0.02 s, and the differences this episode is
    # about are a few hundredths — F47 is the same defect in a different variable
    # (an apex snapped to the node grid), and it reached a published figure.
    lap_time = steps * dt
    if valid and len(arrays["s"]) > 1:
        lap_time = float(np.interp(track.length - 1.0, arrays["s"], arrays["t"]))
    return Lap(valid=valid, reason=reason, lap_time=lap_time,
               grip_use=grip_use, log=arrays,
               tv_log=(tv.history() if tv is not None else {}))


__all__ = ["Driver", "SpeedProfile", "TrackLocator", "Lap", "drive_lap",
           "DT", "STEER_MAX", "STEER_RATE_MAX", "DRIVE_MAX", "BRAKE_MAX",
           "ENVELOPE_SLIP_MAX_DEG"]
