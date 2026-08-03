"""The driving environment, stepped N instances at a time.

``physics/rl_env.py`` runs one car per call. That is the readable version and it
stays the reference: every result in Seasons 3 and 4 came out of it, and this
file is checked against it rather than replacing it.

**Why this exists.** Measured on the Episode 14 policies, the single-instance
environment runs at 1,184 steps/s in hybrid mode, 2,491 end-to-end, 3,492 with
no torque vectoring. One 393 m corner takes ~1,300 steps, so five million steps
is hours per seed — and a real circuit is ten to twenty times longer than one
corner. Extending this project past a single turn is a throughput problem before
it is anything else.

The cost is not the arithmetic. It is that every one of those numpy calls is on
a scalar, so the interpreter overhead per operation dwarfs the operation. The
fix is to give every operation ``N`` cars to do at once.

**What made this tractable.** ``physics/tire.py`` already vectorises — ``fy0``,
``fx0``, ``peak_fx``, ``peak_fy`` and ``fy_combined`` all accept arrays and agree
with the scalar loop to the last bit, because the tire model was written against
``physics/mathkit.py``'s namespace so CasADi and numpy could share one set of
formulas. The Magic Formula is the expensive part of a step and it needed no
work at all.

Scope, stated rather than discovered later
------------------------------------------

This implements the paths the reinforcement-learning environment actually
drives, and **raises on the rest instead of quietly doing something else**:

* differential: ``"open"`` only. The LSD and locked devices have four more
  stages with per-wheel branching (F77), they belong to Episode 12's scalar
  sweeps, and nothing batched needs them yet.
* ``tv_mode``: ``"none"`` and ``"end_to_end"``. Hybrid needs the QP allocator
  solved per instance per step; that is a separate problem and is deliberately
  not faked here.
* no design conditioning, no steering noise, no per-instance grip draw yet —
  every instance shares one car and one tire.

Every one of those raises a clear error. A batched environment that silently
models a different car than the reference is worth less than no batched
environment at all.

Differences from the reference that are real, and why
-----------------------------------------------------

``DoubleTrackBackend.derivatives`` converges its acceleration/load fixed point
with an early ``break`` once two successive iterates agree to 1e-9. A
per-instance break cannot survive batching, so this runs the full iteration
count for every instance, every time. Iterating an already-converged fixed point
moves it by less than the convergence tolerance, so the two agree to ~1e-9
rather than bit-for-bit, and ``tests/test_batched_env.py`` asserts that
tolerance rather than equality.
"""

from __future__ import annotations

import math

import numpy as np

from physics import schema
from physics.double_track import CORNERS, DoubleTrackBackend
from physics.rl_env import (
    BRAKE_MAX, DRIVE_MAX, ENVELOPE_SLIP_MAX, PREVIEW_DISTANCES, STEER_MAX,
    STEER_RATE_MAX, EnvConfig,
)
from physics.tire import default_tire

#: Fixed-point iterations for the acceleration/load coupling. The reference
#: allows up to six and breaks early; this always runs six.
FIXED_POINT_ITERS = 6

#: Index of each corner in the [N, 4] per-wheel arrays. Kept as a module
#: constant so nothing here re-derives corner order from a dict, which is how
#: a per-wheel array silently transposes.
CORNER_INDEX = {c: i for i, c in enumerate(CORNERS)}


class BatchedDrivingEnv:
    """``n`` independent cars on the same track, stepped together.

    The public surface mirrors :class:`physics.rl_env.DrivingEnv` where it can:
    ``reset() -> obs[N, obs_dim]``, ``step(actions[N, act_dim]) -> (obs,
    rewards[N], dones[N], info)``. It differs in one way that matters and is
    therefore not hidden: **instances auto-reset**. An instance that finishes,
    crashes, stalls or times out is restarted in place and the observation
    returned for it is the first of its next episode, with the terminal values
    reported in ``info`` — the arrangement on-policy training expects.
    """

    def __init__(self, cfg: EnvConfig | None = None, n: int = 8,
                 seed: int = 0, bank=None):
        """``bank``: an optional :class:`physics.track_bank.TrackBank`. When
        given, each instance is assigned its own circuit from the bank and
        redrawn on every reset, so a rollout covers many circuits rather than
        one. ``cfg.track`` is then used only for its scalar geometry defaults
        and MUST NOT be read for curvature or width -- every such lookup is
        routed through the bank below.

        ``None`` (the default) reproduces every existing single-track run
        bit-for-bit: the bank branches are skipped entirely.
        """
        cfg = cfg or EnvConfig()
        self.bank = bank
        self._reject_unsupported(cfg)
        self.cfg, self.n = cfg, int(n)
        self.rng = np.random.default_rng(seed)

        # One car, one tire, shared by every instance. Design conditioning is
        # rejected above rather than silently ignored.
        self._ref = DoubleTrackBackend(cfg.params, tire=default_tire(),
                                       diff=cfg.diff)
        self.tire = self._ref.tire
        p = self._ref.params
        self.p = p

        # Per-corner geometry as [4] constants, in CORNERS order.
        front = np.array([c[0] == "f" for c in CORNERS])
        left = np.array([c[1] == "l" for c in CORNERS])
        self._arm = np.where(front, p.a, -p.b)                  # [4]
        self._track = np.where(front, p.track_f, p.track_r)     # [4]
        self._side = np.where(left, -1.0, 1.0)                  # [4]
        self._is_front = front
        self._driven = np.array(
            [c in self._ref.driven_corners() for c in CORNERS])
        self._brake_share = np.where(
            front, self._ref.brake_bias, 1.0 - self._ref.brake_bias) / 2.0
        self._fz_cap = 5.0 * self.tire.envelope.declared_fz_max

        self.obs_dim = len(self.observe_one_probe())
        self.act_dim = {"none": 2, "end_to_end": 5}[cfg.tv_mode]
        self._alloc()

    # -- geometry, routed through the bank when there is one ---------------

    def _kappa_at(self, s_arr: np.ndarray) -> np.ndarray:
        if self.bank is None:
            return np.asarray(self.cfg.track.curvature(s_arr))
        return self.bank.curvature(self.track_id, s_arr)

    def _halfwidth_at(self, s_arr: np.ndarray) -> np.ndarray:
        if self.bank is None:
            return np.asarray(self.cfg.track.half_width_at(s_arr))
        return self.bank.half_width_at(self.track_id, s_arr)

    def _track_length(self) -> np.ndarray | float:
        if self.bank is None:
            return self.cfg.track.length
        return self.bank.length_of(self.track_id)

    # -- setup -----------------------------------------------------------

    @staticmethod
    def _reject_unsupported(cfg: EnvConfig) -> None:
        if cfg.diff != "open":
            raise NotImplementedError(
                f"batched env implements the open differential only, got "
                f"{cfg.diff!r}. The LSD and locked devices carry four more "
                f"stages of per-wheel branching (F77) and belong to Episode "
                f"12's scalar sweeps.")
        if cfg.tv_mode not in ("none", "end_to_end"):
            raise NotImplementedError(
                f"batched env implements tv_mode 'none' and 'end_to_end', got "
                f"{cfg.tv_mode!r}. Hybrid needs the QP allocator solved per "
                f"instance per step, which is not batched yet.")
        if cfg.design_keys:
            raise NotImplementedError(
                "batched env shares one car across instances; design "
                "conditioning is not batched yet.")
        if cfg.steer_noise:
            raise NotImplementedError(
                "batched env does not implement steering noise yet.")

    def observe_one_probe(self) -> np.ndarray:
        """Observation width, taken from the reference so the two cannot drift."""
        preview = self.cfg.preview_distances or PREVIEW_DISTANCES
        return np.concatenate([np.zeros(6), np.zeros(len(preview))])

    def _alloc(self) -> None:
        z = lambda: np.zeros(self.n, dtype=float)
        self.v_x, self.v_y, self.yaw_rate, self.steer = z(), z(), z(), z()
        self.s, self.n_off, self.xi = z(), z(), z()
        self._start_s = z()
        # Which circuit each instance is currently driving. All zeros without
        # a bank, and then never read.
        self.track_id = np.zeros(self.n, dtype=np.int64)
        self.steps = np.zeros(self.n, dtype=np.int64)
        self.a_x, self.a_y = z(), z()
        self.wheel_fz = np.zeros((self.n, 4), dtype=float)
        self.wheel_fx = np.zeros((self.n, 4), dtype=float)
        self.wheel_fy = np.zeros((self.n, 4), dtype=float)
        self.alpha = np.zeros((self.n, 4), dtype=float)
        self._fractions = np.zeros((self.n, 4), dtype=float)
        # Per-episode accumulators. The single-instance env keeps a full log and
        # reads these off it when the episode ends; a batched env auto-resets in
        # place and that log is gone, so the statistics D6 reads have to be
        # accumulated as the episode runs.
        self._ep_return = np.zeros(self.n, dtype=float)
        self._ep_max_slip = np.zeros(self.n, dtype=float)

    # -- reset -----------------------------------------------------------

    def reset(self, seed: int | None = None) -> np.ndarray:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self._reset_mask(np.ones(self.n, dtype=bool))
        return self.observe()

    def _reset_mask(self, m: np.ndarray) -> None:
        """Re-initialise the instances where ``m`` is True, leaving the rest
        untouched.

        Draws are made for the WHOLE batch and then masked. Drawing only for the
        selected instances would make the stream depend on how many happened to
        terminate together, which is the kind of order dependence that makes a
        run irreproducible without ever looking wrong.
        """
        # New circuit per reset, drawn for the WHOLE batch then masked, like
        # every other draw here -- so the stream cannot depend on how many
        # instances happened to terminate together (see this method's
        # docstring).
        if self.bank is not None:
            draw = self.rng.integers(0, len(self.bank), size=self.n)
            self.track_id = np.where(m, draw, self.track_id)

        jitter = self.rng.uniform(0.0, max(self.cfg.start_jitter_m, 1e-12),
                                  size=self.n)
        # Jitter is a FRACTION of each circuit's own length when banked --
        # circuits differ in length, and a fixed metre jitter would start
        # short circuits several laps in.
        if self.bank is not None and self.cfg.start_jitter_m > 0:
            jitter = (self.rng.uniform(0.0, 1.0, size=self.n)
                      * self.bank.length_of(self.track_id))
        s0 = jitter if self.cfg.start_jitter_m > 0 else np.zeros(self.n)
        self.s = np.where(m, s0, self.s)
        # Per-instance start position, so `finished`/`episode_distance` can
        # be measured relative to it -- see the comment at `finished` in
        # `step()`. Set on EVERY reset (not just the first), mirroring `s0`
        # above: an instance that auto-resets mid-training gets a fresh
        # baseline just like a fresh start does.
        self._start_s = np.where(m, s0, self._start_s)
        self.n_off = np.where(m, 0.0, self.n_off)
        self.xi = np.where(m, 0.0, self.xi)
        # Spawn speed, per instance -- mirrors rl_env._spawn_speed. Computed
        # for the WHOLE batch and then masked, like every other draw here, so
        # the result cannot depend on how many instances happened to reset
        # together (see this method's own docstring).
        if self.cfg.spawn_speed_from_curvature:
            kappa = np.abs(self._kappa_at(s0) if self.bank is not None
                           else self.cfg.track.curvature(s0))
            v_corner = np.sqrt(self.cfg.spawn_lat_budget
                               / np.maximum(kappa, 1e-9))
            v0 = np.minimum(self.cfg.entry_speed,
                           np.maximum(v_corner, self.cfg.min_speed + 1.0))
        else:
            v0 = np.full(self.n, self.cfg.entry_speed, dtype=float)
        self.v_x = np.where(m, v0, self.v_x)
        self.v_y = np.where(m, 0.0, self.v_y)
        self.yaw_rate = np.where(m, 0.0, self.yaw_rate)
        self.steer = np.where(m, 0.0, self.steer)
        self.steps = np.where(m, 0, self.steps)
        self.a_x = np.where(m, 0.0, self.a_x)
        self.a_y = np.where(m, 0.0, self.a_y)
        # [N] mask against [N, 4] state: unsqueeze explicitly. Broadcasting a
        # bare [N] against [N, 4] is either wrong along the corner axis or an
        # accidental [N, N], and the batch-independence test is what catches
        # the second one.
        m4 = m[:, None]
        for arr in (self.wheel_fz, self.wheel_fx, self.wheel_fy, self.alpha,
                    self._fractions):
            arr[...] = np.where(m4, 0.0, arr)

    # -- physics ---------------------------------------------------------

    def wheel_loads(self, a_x: np.ndarray, a_y: np.ndarray) -> np.ndarray:
        """[N, 4] vertical load. Mirrors ``DoubleTrackBackend.wheel_loads``."""
        p = self.p
        axle_f = (p.weight * p.b / p.wheelbase
                  - p.mass * a_x * p.com_height / p.wheelbase)
        axle_r = (p.weight * p.a / p.wheelbase
                  + p.mass * a_x * p.com_height / p.wheelbase)
        moment = p.mass * a_y * p.com_height
        eps = p.roll_stiffness_front_share
        d_f = eps * moment / p.track_f
        d_r = (1.0 - eps) * moment / p.track_r
        return np.stack([0.5 * axle_f - d_f, 0.5 * axle_f + d_f,
                         0.5 * axle_r - d_r, 0.5 * axle_r + d_r], axis=1)

    def slip_angles(self, v_x, v_y, yaw_rate, steer) -> np.ndarray:
        """[N, 4] slip angle. Mirrors ``DoubleTrackBackend.slip_angles``."""
        vy = v_y[:, None] + self._arm[None, :] * yaw_rate[:, None]
        vx = np.maximum(
            v_x[:, None] + self._side[None, :] * yaw_rate[:, None]
            * self._track[None, :] / 2.0,
            DoubleTrackBackend.MIN_SPEED)
        d = np.where(self._is_front[None, :], steer[:, None], 0.0)
        cd, sd = np.cos(d), np.sin(d)
        return np.arctan2(vy * cd - vx * sd, vx * cd + vy * sd)

    def _tire_forces(self, alpha, fz, fx):
        """[N, 4] lateral force, with lifted wheels making nothing.

        ``fz`` is clamped BEFORE the tire call, not after: ``np.where`` computes
        both branches, so a negative load reaching the Magic Formula would
        evaluate it out of range on the discarded side and can poison the
        result with a NaN that the mask no longer hides.
        """
        fz_c = np.clip(fz, 0.0, self._fz_cap)
        live = fz_c > 0.0
        fz_safe = np.where(live, fz_c, 1.0)
        if self._ref.combined_slip:
            fy = self.tire.fy_combined(alpha, fz_safe, fx)
        else:
            fy = self.tire.fy0(alpha, fz_safe)
        fy = np.where(live, fy, 0.0)
        return fy, np.where(live, fx, 0.0), fz_c

    def _long_forces(self, demand: np.ndarray, loads: np.ndarray) -> np.ndarray:
        """[N, 4] longitudinal force for an OPEN differential.

        The open device is three branches of ``differential_forces``: brakes
        split by bias, zero demand makes nothing, and drive is an equal split
        capped by the weaker driven wheel. The LSD and locked stages are
        rejected in ``_reject_unsupported`` rather than approximated.
        """
        if self.cfg.tv_mode == "end_to_end":
            # Variant E: four raw fractions scaled by each wheel's own capacity.
            cap = DoubleTrackBackend.DIFF_CAP_FRACTION * self.tire.peak_fx(
                np.clip(loads, 0.0, self._fz_cap))
            return np.clip(self._fractions, -1.0, 1.0) * cap

        d = demand[:, None]
        brake = d * self._brake_share[None, :]

        cap = DoubleTrackBackend.DIFF_CAP_FRACTION * self.tire.peak_fx(
            np.clip(loads, 0.0, self._fz_cap))
        # min over the DRIVEN wheels only; +inf elsewhere so it cannot win the min
        driven_cap = np.where(self._driven[None, :], cap, np.inf).min(axis=1)
        each = np.minimum(demand / 2.0, driven_cap)[:, None]
        drive = np.where(self._driven[None, :], each, 0.0)

        return np.where(d < 0.0, brake, np.where(d > 0.0, drive, 0.0))

    def _derivatives(self, v_x, v_y, yaw_rate, steer, heading,
                     demand, steer_rate, a_x0, a_y0):
        p = self.p
        alpha = self.slip_angles(v_x, v_y, yaw_rate, steer)
        a_x, a_y = a_x0, a_y0
        fy = fx = fz = None
        # Full iteration count for every instance: the reference's early break
        # is per-instance and cannot be batched. See the module docstring.
        for _ in range(FIXED_POINT_ITERS):
            loads = self.wheel_loads(a_x, a_y)
            fx_cmd = self._long_forces(demand, loads)
            fy, fx, fz = self._tire_forces(alpha, loads, fx_cmd)
            f_idx = self._is_front[None, :]
            fy_f = np.where(f_idx, fy, 0.0).sum(axis=1)
            fy_r = np.where(~f_idx, fy, 0.0).sum(axis=1)
            fx_f = np.where(f_idx, fx, 0.0).sum(axis=1)
            fx_r = np.where(~f_idx, fx, 0.0).sum(axis=1)
            cs, ss = np.cos(steer), np.sin(steer)
            drag = (0.5 * 1.225 * p.c_d * p.frontal_area * v_x * np.abs(v_x))
            fx_body = fx_f * cs - fy_f * ss + fx_r - drag
            fy_body = fy_f * cs + fx_f * ss + fy_r
            a_x, a_y = fx_body / p.mass, fy_body / p.mass

        # yaw moment: sum over wheels of x*Fy_body - y*Fx_body  (F72)
        x_w = self._arm[None, :]
        y_w = np.where(self._side[None, :] < 0, self._track[None, :] / 2.0,
                       -self._track[None, :] / 2.0)
        cs4 = np.where(self._is_front[None, :], np.cos(steer)[:, None], 1.0)
        ss4 = np.where(self._is_front[None, :], np.sin(steer)[:, None], 0.0)
        fx_b = fx * cs4 - fy * ss4
        fy_b = fx * ss4 + fy * cs4
        m_z = (x_w * fy_b - y_w * fx_b).sum(axis=1)

        d = {
            "v_x": a_x + v_y * yaw_rate,
            "v_y": a_y - v_x * yaw_rate,
            "yaw_rate": m_z / p.i_zz,
            "steer": steer_rate,
            "heading": yaw_rate,
        }
        return d, a_x, a_y, alpha, fy, fx, fz

    # -- the loop --------------------------------------------------------

    def step(self, actions: np.ndarray):
        """One policy decision per instance; see EnvConfig.action_repeat.

        Auto-reset makes the repeat subtler than the reference's: an instance
        that terminates mid-repeat has already been restarted, so continuing
        to apply the held action would drive its NEXT episode with the
        previous one's control. Terminated instances are therefore frozen for
        the remainder of the repeat by zeroing their action, and their
        terminal info is preserved from the step that ended them."""
        if self.cfg.action_repeat > 1:
            total = np.zeros(self.n)
            any_done = np.zeros(self.n, dtype=bool)
            keep = {}
            act = actions.copy()
            for _ in range(self.cfg.action_repeat):
                obs, r, done, info = self._step_once(act)
                total = total + np.where(any_done, 0.0, r)
                for k, v in info.items():
                    if k.startswith("episode_"):
                        keep.setdefault(k, []).append(v)
                any_done = any_done | done
                if any_done.all():
                    break
                act = np.where(any_done[:, None], 0.0, act)
            for k, v in keep.items():
                info[k] = np.concatenate(v) if len(v) else v
            return obs, total, any_done, info
        return self._step_once(actions)

    def _step_once(self, actions: np.ndarray):
        a = np.clip(np.asarray(actions, dtype=float), -1.0, 1.0)
        if a.shape != (self.n, self.act_dim):
            raise ValueError(f"expected actions {(self.n, self.act_dim)}, "
                             f"got {a.shape}")

        steer_rate = a[:, 0] * STEER_RATE_MAX
        if self.cfg.tv_mode == "end_to_end":
            self._fractions = a[:, 1:5].copy()
            demand = np.zeros(self.n)
        else:
            drive = a[:, 1]
            if self.cfg.speed_cap is not None:
                # Mirrors rl_env.step: above the cap, no positive drive.
                v_now = np.hypot(self.v_x, self.v_y)
                drive = np.where(v_now >= self.cfg.speed_cap,
                                 np.minimum(drive, 0.0), drive)
            dmax = self.cfg.drive_max or DRIVE_MAX
            demand = np.where(drive >= 0, drive * dmax, drive * BRAKE_MAX)

        dt = self.cfg.dt
        st = (self.v_x, self.v_y, self.yaw_rate, self.steer,
              np.zeros(self.n))

        def deriv(state, ax, ay):
            return self._derivatives(*state, demand, steer_rate, ax, ay)

        def advance(state, d, h):
            return (state[0] + d["v_x"] * h, state[1] + d["v_y"] * h,
                    state[2] + d["yaw_rate"] * h, state[3] + d["steer"] * h,
                    state[4] + d["heading"] * h)

        k1, a_x, a_y, alpha, fy, fx, fz = deriv(st, self.a_x, self.a_y)
        k2 = deriv(advance(st, k1, dt / 2), a_x, a_y)[0]
        k3 = deriv(advance(st, k2, dt / 2), a_x, a_y)[0]
        k4 = deriv(advance(st, k3, dt), a_x, a_y)[0]

        for key, cur in (("v_x", self.v_x), ("v_y", self.v_y),
                         ("yaw_rate", self.yaw_rate), ("steer", self.steer)):
            inc = (k1[key] + 2 * k2[key] + 2 * k3[key] + k4[key]) / 6.0
            setattr(self, key, cur + inc * dt)
        self.v_x = np.maximum(self.v_x, DoubleTrackBackend.MIN_SPEED)
        self.a_x, self.a_y = a_x, a_y
        self.alpha, self.wheel_fy = alpha, fy
        self.wheel_fx, self.wheel_fz = fx, fz

        # curvilinear kinematics, all rates from the pre-integration state
        kappa = self._kappa_at(self.s)
        s_dot = ((self.v_x * np.cos(self.xi) - self.v_y * np.sin(self.xi))
                 / np.maximum(1.0 - self.n_off * kappa, 1e-3))
        n_dot = self.v_x * np.sin(self.xi) + self.v_y * np.cos(self.xi)
        xi_dot = self.yaw_rate - kappa * s_dot
        self.s = self.s + s_dot * dt
        self.n_off = self.n_off + n_dot * dt
        self.xi = (self.xi + xi_dot * dt + np.pi) % (2 * np.pi) - np.pi
        self.steps += 1

        speed = np.hypot(self.v_x, self.v_y)
        off = np.abs(self.n_off) > self._halfwidth_at(self.s)
        # Relative to each instance's OWN start, not absolute position --
        # see rl_env.DrivingEnv.step's comment on the same bug. An instance
        # starting late in the lap (start_jitter_m, or the eval harness's
        # manually-set probe start) must otherwise cover only
        # `length - start_s` to be called "finished", inflating both the
        # training-time finish signal and every per-section eval reading it.
        finished = ((self.s - self._start_s)
                   >= self._track_length() * self.cfg.n_laps)
        stalled = speed < self.cfg.min_speed
        timeout = self.steps >= self.cfg.max_steps
        done = off | finished | stalled | timeout

        # **Post-step** slip angles, because that is what the reference uses.
        # ``rl_env.step`` calls ``backend.slip_angles()`` with no argument
        # AFTER integrating, so it reads the new state; ``alpha`` above is from
        # the first RK4 stage and belongs to the old one. Using the latter
        # silently changed both the envelope penalty and the logged slip, and
        # the reward differential test is what caught it — the trajectories
        # still agreed, because the penalty does not feed back into the physics.
        alpha_post = self.slip_angles(self.v_x, self.v_y, self.yaw_rate,
                                      self.steer)
        worst_deg = np.degrees(np.abs(alpha_post).max(axis=1))

        reward = s_dot * dt * self.cfg.progress_scale
        reward = reward - np.where(off, self.cfg.off_track_penalty, 0.0)
        if self.cfg.stall_penalty > 0.0:
            reward = reward - np.where(stalled, self.cfg.stall_penalty, 0.0)
        pscale = 1.0
        if self.cfg.speed_scaled_penalties:
            pscale = speed / max(self.cfg.penalty_speed_ref, 1e-9)
        if self.cfg.cross_track_penalty > 0.0:
            use_ct = np.abs(self.n_off) / np.maximum(
                self._halfwidth_at(self.s), 1e-9)
            reward = reward - (self.cfg.cross_track_penalty * dt * use_ct
                              * pscale)
        if self.cfg.edge_penalty > 0.0:
            # Mirrors rl_env.step exactly -- see EnvConfig.edge_penalty.
            thr = self.cfg.edge_threshold
            use = np.abs(self.n_off) / np.maximum(
                self._halfwidth_at(self.s), 1e-9)
            ramp = np.clip((use - thr) / max(1.0 - thr, 1e-9), 0.0, 1.0)
            reward = reward - (self.cfg.edge_penalty * dt
                               * speed * speed * ramp)
        if self.cfg.envelope_penalty > 0.0:
            excess = np.maximum(
                0.0, worst_deg - math.degrees(ENVELOPE_SLIP_MAX))
            rel = excess / math.degrees(ENVELOPE_SLIP_MAX)
            reward = reward - (pscale * self.cfg.envelope_penalty
                               * rel ** self.cfg.envelope_exponent)
        if self.cfg.workload_penalty > 0.0:
            # Mean squared friction-ellipse utilisation, from the FIRST RK4
            # stage's wheel forces — which is what ``_last_wheels`` holds in
            # the reference, so the two rewards are computed from the same
            # instant rather than from two different points in the step.
            fz_safe = np.maximum(fz, 1.0)
            ux = fx / self.tire.peak_fx(fz_safe)
            uy = fy / self.tire.peak_fy(fz_safe)
            reward = reward - self.cfg.workload_penalty * (
                ux * ux + uy * uy).mean(axis=1)

        self._ep_return += reward
        self._ep_max_slip = np.maximum(self._ep_max_slip, worst_deg)

        info = {
            "s": self.s.copy(), "n": self.n_off.copy(),
            "speed": speed, "off_track": off, "finished": finished,
            "stalled": stalled, "timeout": timeout,
            "alpha_max_deg": worst_deg,
            "a_y": self.a_y.copy(),
            # Completed episodes only — the terminal values, captured before the
            # reset wipes them. Empty arrays on a step where nothing ended.
            "episode_return": self._ep_return[done].copy(),
            "episode_distance": (self.s - self._start_s)[done].copy(),
            "episode_worst_slip_deg": self._ep_max_slip[done].copy(),
            "episode_off_track": off[done].copy(),
        }
        # Terminal values are captured above; the observation returned for a
        # terminated instance is the FIRST of its next episode.
        if done.any():
            self._ep_return = np.where(done, 0.0, self._ep_return)
            self._ep_max_slip = np.where(done, 0.0, self._ep_max_slip)
            self._reset_mask(done)
        return self.observe(), reward, done, info

    # -- observation -----------------------------------------------------

    def observe(self) -> np.ndarray:
        speed = np.hypot(self.v_x, self.v_y)
        beta = np.arctan2(self.v_y, np.maximum(self.v_x, 1e-3))
        # See rl_env.DrivingEnv._curvature_ahead: a closed track wraps s %
        # length internally, so clamping to `length` here would flatten the
        # preview at the finish line instead of showing the next corner. An
        # open Track has no wraparound and must stay clamped.
        closed = getattr(self.cfg.track, "closed", False)
        preview = self.cfg.preview_distances or PREVIEW_DISTANCES
        ahead = np.stack(
            [self._kappa_at(
                self.s + d if closed else
                np.minimum(self.s + d, self.cfg.track.length))
             for d in preview], axis=1) * 40.0
        return np.concatenate([
            np.stack([
                speed / 50.0,
                self.n_off / self._halfwidth_at(self.s),
                self.xi / math.radians(60.0),
                self.yaw_rate / 2.0,
                beta / math.radians(30.0),
                self.steer / STEER_MAX,
            ], axis=1),
            ahead,
        ], axis=1)


__all__ = ["BatchedDrivingEnv", "FIXED_POINT_ITERS", "CORNER_INDEX"]
