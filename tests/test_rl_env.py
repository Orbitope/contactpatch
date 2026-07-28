"""The driving environment, checked before anything is trained in it.

A reinforcement-learning result is only as good as the environment underneath it,
and an environment with wrong kinematics still produces smooth, plausible-looking
trajectories and a policy that learns something. These are the checks that would
catch that — mostly by comparing against geometry the environment does not know
about, rather than against itself.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from physics import schema
from physics import track as T
from physics.rl_env import (DrivingEnv, EnvConfig, STEER_MAX, rollout)


def _straight_env(**kw):
    return DrivingEnv(EnvConfig(track=T.long_exit(), **kw))


# ---------------------------------------------------------------------------
# Kinematics — checked against the road, which the integrator does not see
# ---------------------------------------------------------------------------


def test_straight_ahead_on_a_straight_road_stays_on_the_centreline():
    """No steering on the entry straight must mean no meaningful drift.

    Not asserted to machine zero, and the reason is worth stating. The project
    tire is offset-free (FINDINGS D1/F6) but not *exactly* zero-force at zero
    slip — the fitted shape leaves a residual of order a hundredth of a newton.
    Over two seconds that integrates to about 20 microns of lateral movement on
    an 8 m road. A tolerance of 1 mm is still four hundred times tighter than
    anything that could matter and would catch a real sign or coupling error,
    which would put the car metres off line, not microns.
    """
    env = _straight_env()
    env.reset(0)
    for _ in range(100):                      # 2 s, well inside the 70 m straight
        env.step(np.array([0.0, 0.0]))
        if env.done:
            break
    assert abs(env.n) < 1e-3, "drifted off a straight road with no steering input"
    assert abs(env.xi) < 1e-4
    # 2 s at the 15 m/s entry speed is ~30 m; the point is that the car
    # moved a real distance, not the specific number
    assert env.s > 25.0, "should have covered real distance"


def test_distance_travelled_matches_speed_times_time():
    """s must advance at the speed the car is actually going.

    Independent of the Frenet machinery: on a straight, with no steering, the
    arc-length rate reduces to v_x, so integrating speed over time has to give
    the same answer as the environment's own s.
    """
    env = _straight_env()
    env.reset(0)
    travelled = 0.0
    for _ in range(80):
        _, _, done, info = env.step(np.array([0.0, 0.0]))
        travelled += info["speed"] * env.cfg.dt
        if done:
            break
    assert env.s == pytest.approx(travelled, rel=2e-3)


def test_following_the_corner_keeps_the_car_near_the_centreline():
    """Steer at roughly the Ackermann angle and the car should track the road.

    This is the check that catches a wrong curvilinear integration. If the
    ``xi_dot = r - kappa * s_dot`` coupling is wrong — and an earlier version used
    ``kappa * speed`` and integrated in the wrong order — the car will drift off
    the centreline through the corner even while steering correctly, because the
    road's own rotation is not being subtracted properly.
    """
    p = schema.RV_1
    env = DrivingEnv(EnvConfig(entry_speed=15.0))   # gentle: stay near linear
    env.reset(0)
    target = p.wheelbase / T.CORNER_RADIUS          # Ackermann steer for the arc
    worst = 0.0
    for _ in range(env.cfg.max_steps):
        kappa_now = float(env.cfg.track.curvature(env.s))
        want = target * (kappa_now * T.CORNER_RADIUS)      # 0 on straights
        # simple proportional servo on steer angle, plus centreline correction
        err = want - env.backend.state.steer
        cmd = np.clip(8.0 * err - 0.35 * env.n - 1.2 * env.xi, -1.0, 1.0)
        _, _, done, _ = env.step(np.array([cmd, 0.0]))
        if env.s > 20.0:
            worst = max(worst, abs(env.n))
        if done:
            break
    assert env.s > 200.0, f"never got round the corner, reached {env.s:.0f} m"
    assert worst < 2.0, (
        f"drifted {worst:.2f} m from the centreline while following the corner; "
        "the curvilinear kinematics are not tracking the road")


def test_lateral_offset_sign_matches_the_iso_frame():
    """+n is to the LEFT of travel, as everywhere else in the project."""
    env = _straight_env()
    env.reset(0)
    for _ in range(30):
        env.step(np.array([0.6, 0.0]))     # positive steer rate = left in ISO
        if env.done:
            break
    assert env.n > 0.0, "a left steer must move the car to positive n"


# ---------------------------------------------------------------------------
# The task
# ---------------------------------------------------------------------------


def test_reward_is_progress_and_nothing_else():
    """Summed reward over a clean episode must equal distance covered."""
    env = _straight_env()
    env.reset(0)
    total = 0.0
    for _ in range(60):
        _, r, done, _ = env.step(np.array([0.0, 0.2]))
        total += r
        if done:
            break
    assert total == pytest.approx(env.s, rel=1e-6), (
        "reward has picked up a term that is not progress")


def test_leaving_the_road_ends_the_episode_and_costs_more_than_it_earns():
    env = _straight_env()
    env.reset(0)
    last = 0.0
    for _ in range(env.cfg.max_steps):
        _, last, done, info = env.step(np.array([1.0, 0.5]))
        if done:
            break
    assert info["off_track"], "hard steering lock should run out of road"
    assert last < 0.0, "the terminal step must be a net loss, or leaving pays"


def test_a_stalled_car_terminates():
    env = _straight_env()
    env.reset(0)
    for _ in range(env.cfg.max_steps):
        _, _, done, info = env.step(np.array([0.0, -1.0]))
        if done:
            break
    assert info["stalled"] or info["off_track"]


# ---------------------------------------------------------------------------
# The envelope — instrumented, deliberately NOT enforced
# ---------------------------------------------------------------------------


def test_the_envelope_is_measured_every_step():
    env = _straight_env()
    env.reset(0)
    for _ in range(40):
        env.step(np.array([0.3, 0.5]))
        if env.done:
            break
    h = env.history()
    for key in ("alpha_max_deg", "load_min", "load_max", "envelope_violation"):
        assert len(h[key]) == env.steps, f"{key} not logged every step"
        assert np.all(np.isfinite(h[key].astype(float)))


def test_the_envelope_is_not_enforced():
    """The defining property of this environment, asserted so it cannot drift.

    Seasons 1 and 2 constrain slip to ±12° inside the solver. Here nothing does,
    because Episode 9 is about what a learner finds when the physics is wrong
    somewhere nobody fenced off. If a future change adds a constraint, this test
    should fail loudly and the episode's premise be revisited — not the test
    quietly deleted.
    """
    env = _straight_env()
    env.reset(0)
    for _ in range(env.cfg.max_steps):
        env.step(np.array([1.0, 1.0]))       # lock it over and floor it
        if env.done:
            break
    h = env.history()
    assert h["alpha_max_deg"].max() > 12.0, (
        "the car never exceeded the ±12° slip bound even under a steering lock; "
        "either the environment is clamping slip, or this manoeuvre no longer "
        "saturates the tires")


def test_rollout_reports_envelope_occupancy_without_hiding_it():
    env = _straight_env()
    r = rollout(env, lambda o: np.array([0.9, 1.0]), seed=0)
    assert 0.0 <= r["envelope_occupancy"] <= 1.0
    assert r["worst_slip_deg"] >= 0.0
    assert r["steps"] == len(r["s"])
    assert "slip_over_12deg_fraction" in r


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


def test_observation_is_finite_bounded_and_the_right_shape():
    env = _straight_env()
    obs = env.reset(0)
    assert obs.shape == (env.obs_dim,)
    for _ in range(50):
        obs, _, done, _ = env.step(env.rng.uniform(-1, 1, env.act_dim))
        assert obs.shape == (env.obs_dim,)
        assert np.all(np.isfinite(obs)), "a non-finite observation will poison PPO"
        if done:
            break


def test_the_policy_cannot_see_the_whole_road():
    """The observation must not smuggle in global information.

    A policy that can see where it is on the track, or how much time has passed,
    is doing a worse-conditioned version of the optimal-control problem rather
    than driving. Only the preview window and local state are allowed.
    """
    env = _straight_env()
    a = env.reset(0)
    env.s = 150.0          # teleport along the road, keep the car state identical
    b = env.observe()
    # the first six entries are car state and must be unchanged by position alone
    assert np.allclose(a[:6], b[:6])


def test_reset_clears_the_log():
    env = _straight_env()
    env.reset(0)
    for _ in range(10):
        env.step(np.array([0.0, 0.3]))
    env.reset(0)
    assert env.steps == 0
    assert all(len(v) == 0 for v in env.log.values())


def test_two_envs_with_the_same_seed_agree():
    """Reproducibility, without which no training comparison means anything."""
    def go(seed):
        e = DrivingEnv(EnvConfig(start_jitter_m=5.0))
        return rollout(e, lambda o: np.array([0.2 * o[1], 0.4]), seed=seed)
    a, b = go(7), go(7)
    assert a["distance_m"] == pytest.approx(b["distance_m"], rel=1e-12)
    assert a["steps"] == b["steps"]


# --- Episode 11: perturbations ------------------------------------------------
#
# These knobs change what the physics does, so each one is pinned by a property
# that would fail if the wiring were wrong in a way that still ran.


def test_perturbations_default_to_off_and_change_nothing():
    """Every Episode 9 and 10 number must be reproducible after Episode 11.

    The risk of adding perturbation knobs to a shared environment is that they
    quietly alter the runs of episodes already written up. This asserts
    bit-for-bit identity, not approximate agreement.
    """
    a = DrivingEnv(EnvConfig(), seed=0)
    b = DrivingEnv(EnvConfig(steer_noise=0.0, grip_spread=0.0), seed=0)
    a.reset(0)
    b.reset(0)
    ra = rb = 0.0
    for _ in range(60):
        _, r1, d1, _ = a.step(np.array([0.02, 0.5]))
        _, r2, d2, _ = b.step(np.array([0.02, 0.5]))
        ra += r1
        rb += r2
        if d1 or d2:
            break
    assert ra == rb
    assert a.grip == 1.0


def test_grip_scaling_goes_through_LMUY_and_leaves_every_P_coefficient_alone():
    """The hard invariant: retarget through ``[SCALING_COEFFICIENTS]``, never P*.

    Checked on the tire's actual output rather than on the coefficient, so it
    fails if ``LMUY`` were applied somewhere it does not reach peak grip.
    """
    from physics.tire import default_tire

    base = default_tire()
    env = DrivingEnv(EnvConfig(grip_spread=0.1), seed=0)
    scaled = env._tire_for(0.9)

    assert scaled.scaling.lmuy == pytest.approx(base.scaling.lmuy * 0.9)
    for name in dir(base):
        if name.startswith("P") and name.isupper():
            assert getattr(scaled, name) == getattr(base, name), name

    fz = 4000.0
    alphas = np.radians(np.linspace(0.0, 12.0, 80))
    peak = lambda t: max(abs(float(t.fy0(al, fz))) for al in alphas)
    assert peak(scaled) / peak(base) == pytest.approx(0.9, abs=2e-3)


def test_grip_is_drawn_once_per_episode_not_once_per_step():
    """A damp patch is a surface, not a per-step dice roll.

    If grip were resampled inside ``step`` the car would be driving on a
    different surface every 20 ms, which is not a condition any car meets and
    would average out instead of being a hazard.
    """
    env = DrivingEnv(EnvConfig(grip_spread=0.15), seed=7)
    env.reset(11)
    held = env.grip
    for _ in range(25):
        _, _, done, _ = env.step(np.array([0.0, 0.4]))
        assert env.grip == held
        if done:
            break
    draws = []
    for i in range(12):
        env.reset(200 + i)
        draws.append(env.grip)
    assert len(set(draws)) == len(draws)          # varies between episodes
    assert min(draws) >= 0.85 - 1e-12 and max(draws) <= 1.15 + 1e-12


def test_steer_noise_perturbs_steering_and_leaves_throttle_untouched():
    """Steering only. Mixing in throttle jitter would make the result
    unattributable to a mechanism."""
    quiet = DrivingEnv(EnvConfig(steer_noise=0.0), seed=0)
    noisy = DrivingEnv(EnvConfig(steer_noise=0.05), seed=0)
    for env in (quiet, noisy):
        env.reset(0)
        for _ in range(40):
            env.step(np.array([0.0, 0.5]))
    assert np.std(quiet.log["steer"]) == 0.0
    assert np.std(noisy.log["steer"]) > 1e-4
    # commanded drive is identical: same action, same throttle path
    assert np.allclose(quiet.log["drive"], noisy.log["drive"])
