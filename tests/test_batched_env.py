"""Differential test: the batched environment against the readable one.

``physics/rl_env.py`` is the reference. It produced every Season 3 and Season 4
result, it is the version a reader can follow, and it stays authoritative.
``physics/batched_env.py`` exists only to be faster, so the only question worth
asking of it is **whether it models the same car** — and that question is
answered by driving both and comparing, not by reading the batched code and
agreeing with it.

Three properties, in the order they catch things:

1. **Agreement.** Same actions in, same trajectory out, to a stated tolerance.
2. **Batch independence.** Instance *i*'s trajectory must not depend on what
   instance *j* is doing. This is the one a differential test structurally
   cannot catch, because a differential test runs one instance.
3. **Refusal.** Every configuration the batched version does not implement has
   to raise, not quietly model something else.

**On tolerance rather than bit-equality.** ``DoubleTrackBackend.derivatives``
converges its acceleration/load fixed point with an early ``break``; a
per-instance break cannot be batched, so the batched version always runs the
full iteration count. Iterating a converged fixed point moves it by less than
the convergence tolerance, so the two agree closely but not bitwise. The
tolerances below are set from that and are tight enough that a real modelling
difference — a sign, a moment arm, a transposed corner — would blow through
them immediately.
"""

from __future__ import annotations

import numpy as np
import pytest

from physics.batched_env import BatchedDrivingEnv
from physics.rl_env import DrivingEnv, EnvConfig
from physics.track import CORNER_ARC as ARC, ENTRY_STRAIGHT as ENTRY


def _tracker(obs: np.ndarray) -> np.ndarray:
    """A crude centreline tracker, so the comparison runs a real lap.

    Random actions put the car off the road in a few dozen steps, which tests
    almost none of the corner. This keeps it driving.
    """
    o = np.atleast_2d(obs)
    steer = np.clip(-2.5 * o[:, 1] - 1.5 * o[:, 2], -1.0, 1.0)
    throttle = np.clip(0.6 - 2.0 * np.abs(o[:, 1]), -1.0, 1.0)
    return np.stack([steer, throttle], axis=1)


# ---------------------------------------------------------------------------
# 1. agreement
# ---------------------------------------------------------------------------

def test_reset_observation_matches_the_reference():
    cfg = EnvConfig()
    ref, bat = DrivingEnv(cfg), BatchedDrivingEnv(cfg, n=4, seed=0)
    o_ref, o_bat = ref.reset(0), bat.reset(0)
    assert o_bat.shape == (4, ref.obs_dim)
    for i in range(4):
        assert o_bat[i] == pytest.approx(o_ref, abs=1e-12)


def test_observation_width_matches_the_reference():
    cfg = EnvConfig()
    assert BatchedDrivingEnv(cfg, n=2).obs_dim == DrivingEnv(cfg).obs_dim
    assert BatchedDrivingEnv(cfg, n=2).act_dim == DrivingEnv(cfg).act_dim


def test_a_driven_lap_matches_the_reference():
    """The headline check: drive both with the same closed-loop controller."""
    cfg = EnvConfig()
    ref, bat = DrivingEnv(cfg), BatchedDrivingEnv(cfg, n=1, seed=0)
    o_ref, o_bat = ref.reset(0), bat.reset(0)

    worst_s = worst_n = worst_v = 0.0
    steps = 0
    for _ in range(2000):
        a = _tracker(o_ref)[0]
        o_ref, _, d_ref, i_ref = ref.step(a)
        o_bat, _, d_bat, i_bat = bat.step(a[None, :])
        worst_s = max(worst_s, abs(i_ref["s"] - i_bat["s"][0]))
        worst_n = max(worst_n, abs(i_ref["n"] - i_bat["n"][0]))
        worst_v = max(worst_v, abs(i_ref["speed"] - i_bat["speed"][0]))
        steps += 1
        assert bool(d_ref) == bool(d_bat[0]), (
            f"termination disagreed at step {steps}: "
            f"reference={d_ref} batched={d_bat[0]}")
        if d_ref:
            break

    assert steps > 100, "the lap ended too early to be testing anything"
    assert worst_s < 1e-4, f"distance diverged by {worst_s:.2e} m"
    assert worst_n < 1e-4, f"lateral offset diverged by {worst_n:.2e} m"
    assert worst_v < 1e-4, f"speed diverged by {worst_v:.2e} m/s"


def test_termination_reasons_agree():
    """Not just *that* it ended, but why — off-track and finished are different
    outcomes and are rewarded differently."""
    cfg = EnvConfig()
    ref, bat = DrivingEnv(cfg), BatchedDrivingEnv(cfg, n=1, seed=0)
    o = ref.reset(0)
    bat.reset(0)
    for _ in range(2000):
        a = _tracker(o)[0]
        o, _, d, i_ref = ref.step(a)
        _, _, d_bat, i_bat = bat.step(a[None, :])
        if d:
            for key in ("off_track", "finished", "stalled", "timeout"):
                assert bool(i_ref[key]) == bool(i_bat[key][0]), (
                    f"{key} disagreed: {i_ref[key]} vs {i_bat[key][0]}")
            return
    pytest.fail("never terminated")


def _reward_divergence(steps: int = 400, policy=_tracker, **cfg_kwargs) -> float:
    cfg = EnvConfig(**cfg_kwargs)
    ref, bat = DrivingEnv(cfg), BatchedDrivingEnv(cfg, n=1, seed=0)
    o = ref.reset(0)
    bat.reset(0)
    worst = 0.0
    for _ in range(steps):
        a = policy(o)[0]
        o, r_ref, d, _ = ref.step(a)
        _, r_bat, _, _ = bat.step(a[None, :])
        worst = max(worst, abs(r_ref - r_bat[0]))
        if d:
            break
    return worst


def test_progress_reward_matches_the_reference():
    """With no envelope penalty the reward is pure progress, so this tracks the
    trajectory divergence directly and is the tighter of the two bounds."""
    assert _reward_divergence(envelope_penalty=0.0) < 1e-6


def test_reward_with_the_envelope_penalty_matches_the_reference():
    """Looser than the progress-only bound, for a reason worth stating.

    The penalty is ``envelope_penalty * excess_degrees / 12``, and a slip angle
    expressed in degrees magnifies a residual in radians by 57x before it ever
    reaches the reward. Measured, the penalty term costs about one order of
    magnitude against the progress-only case (5.4e-7 -> 5.2e-6) — consistent
    with the fixed-point residual being amplified rather than with a modelling
    difference, which would not care whether the penalty was switched on.

    Both bounds are asserted so that a real divergence cannot hide behind the
    looser one: it would break the progress test too.
    """
    assert _reward_divergence(envelope_penalty=0.5) < 1e-5


def test_the_envelope_penalty_uses_post_step_slip_angles():
    """A regression test for a bug the reward comparison found.

    ``rl_env.step`` computes the penalty from ``backend.slip_angles()`` AFTER
    integrating, so it reads the new state. The batched version originally used
    the slip angles from the first RK4 stage, which belong to the old one. The
    trajectories still agreed — the penalty does not feed back into the physics
    — so only the reward showed it, and it was off by 0.18 rather than 5e-6.
    """
    assert (_reward_divergence(envelope_penalty=0.5)
           < 100 * _reward_divergence(envelope_penalty=0.0))


def test_progress_scale_matches_the_reference():
    """TRACKS.md staging step 5: progress_scale multiplies ds*dt in both
    implementations identically."""
    assert _reward_divergence(progress_scale=3.0, envelope_penalty=0.0) < 1e-5


def _full_brake(obs: np.ndarray) -> np.ndarray:
    """Steer straight, brake hard -- forces a stall within the test window,
    which _tracker's normal driving would not do on its own."""
    o = np.atleast_2d(obs)
    return np.stack([np.zeros(len(o)), np.full(len(o), -1.0)], axis=1)


def _hug_the_edge(obs: np.ndarray) -> np.ndarray:
    """Steer hard one way so the car runs out to the track edge, where
    edge_penalty actually fires -- _tracker deliberately stays centred and
    would never trigger it."""
    o = np.atleast_2d(obs)
    return np.stack([np.full(len(o), 0.35), np.full(len(o), 0.5)], axis=1)


def test_edge_penalty_matches_the_reference():
    """TRACKS.md item 19h: the dense speed-scaled edge cost must fire
    identically in both implementations, or the batched path trains against
    a different reward than the one being designed."""
    div = _reward_divergence(steps=300, policy=_hug_the_edge,
                             edge_penalty=0.15, envelope_penalty=0.0)
    assert div < 1e-4


def test_edge_penalty_actually_fires_on_this_trajectory():
    """Guards the test above: a divergence test passes trivially if the term
    is never exercised. Checks the penalty changes the reward at all."""
    base = EnvConfig(edge_penalty=0.0, envelope_penalty=0.0)
    pen = EnvConfig(edge_penalty=0.15, envelope_penalty=0.0)
    a, b = DrivingEnv(base), DrivingEnv(pen)
    o_a, o_b = a.reset(0), b.reset(0)
    diff = 0.0
    for _ in range(300):
        act = _hug_the_edge(o_a)[0]
        o_a, r_a, d_a, _ = a.step(act)
        o_b, r_b, d_b, _ = b.step(act)
        diff = max(diff, abs(r_a - r_b))
        if d_a or d_b:
            break
    assert diff > 1e-6, "edge_penalty never fired -- the divergence test is vacuous"


def test_spawn_speed_from_curvature_matches_the_reference():
    """Both implementations must pick the same spawn speed, or the batched
    path starts every episode from a different state than the reference."""
    cfg = EnvConfig(spawn_speed_from_curvature=True, start_jitter_m=200.0)
    ref, bat = DrivingEnv(cfg), BatchedDrivingEnv(cfg, n=1, seed=0)
    ref.reset(3)
    bat.reset(3)
    # Same seed -> same drawn s0 -> same curvature -> same spawn speed.
    assert ref.s == pytest.approx(float(bat.s[0]), abs=1e-9)
    assert ref.backend.state.v_x == pytest.approx(float(bat.v_x[0]), abs=1e-9)


def test_spawn_speed_from_curvature_actually_slows_the_spawn_in_a_corner():
    """Guards the test above from passing vacuously: dropped inside
    long_exit's 40 m corner, the capped spawn must be BELOW entry_speed
    (sqrt(7.6 * 40) = 17.4 m/s here, under the 20 m/s asked for)."""
    cfg = EnvConfig(spawn_speed_from_curvature=True, entry_speed=20.0)
    env = DrivingEnv(cfg)
    env.reset(0)
    env.s = ENTRY + 0.5 * ARC          # mid-corner
    assert env._spawn_speed() < cfg.entry_speed
    # ...and unchanged on the straight, where no cap should apply.
    env.s = 10.0
    assert env._spawn_speed() == pytest.approx(cfg.entry_speed)


def test_stall_penalty_matches_the_reference():
    """TRACKS.md staging step 5: the loophole off_track_penalty=500 found
    (coasting to a stop was free) is closed by stall_penalty -- and it must
    fire identically in both implementations, or training on the batched
    path would optimise a different reward than the one being designed."""
    div = _reward_divergence(steps=200, policy=_full_brake, stall_penalty=150.0,
                             envelope_penalty=0.0)
    assert div < 1e-5


# ---------------------------------------------------------------------------
# 2. batch independence — the property a differential test cannot see
# ---------------------------------------------------------------------------

def test_an_instance_is_unaffected_by_its_neighbours():
    """Instance 0 does the same thing whether it runs alone or in a crowd.

    A ``[N]`` mask broadcast against ``[N, 4]`` state can silently produce an
    ``[N, N]``, which mixes instances together. Nothing else in this file would
    notice, because everything else runs one instance.
    """
    cfg = EnvConfig()
    alone = BatchedDrivingEnv(cfg, n=1, seed=0)
    crowd = BatchedDrivingEnv(cfg, n=6, seed=0)
    o_a, o_c = alone.reset(0), crowd.reset(0)
    rng = np.random.default_rng(3)

    for step in range(300):
        a0 = _tracker(o_a[0])[0]
        a_crowd = rng.uniform(-1.0, 1.0, size=(6, cfg_act(cfg)))
        a_crowd[0] = a0                     # neighbours do something else
        o_a, _, _, i_a = alone.step(a0[None, :])
        o_c, _, _, i_c = crowd.step(a_crowd)
        assert i_a["s"][0] == pytest.approx(i_c["s"][0], abs=1e-12), (
            f"instance 0 changed with neighbours at step {step}")


def cfg_act(cfg) -> int:
    return {"none": 2, "end_to_end": 5}[cfg.tv_mode]


def test_instances_reset_independently():
    """One instance terminating must not disturb the others' state."""
    cfg = EnvConfig()
    env = BatchedDrivingEnv(cfg, n=4, seed=0)
    env.reset(0)
    # Drive instance 0 straight off the road, hold the rest on the centreline.
    for _ in range(200):
        o = env.observe()
        a = _tracker(o)
        a[0] = np.array([1.0, 1.0])          # full lock, full throttle
        s_before = env.s.copy()
        _, _, done, _ = env.step(a)
        if done[0]:
            assert not done[1:].any(), "a neighbour terminated at the same time"
            assert env.s[0] < s_before[0] + 1e-9 or env.s[0] < 20.0, \
                "instance 0 did not reset"
            assert (env.s[1:] > 0).all(), "neighbours were reset too"
            return
    pytest.fail("instance 0 never left the road")


# ---------------------------------------------------------------------------
# 3. refusal — unsupported configurations must raise, not approximate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kw,match", [
    ({"diff": "lsd"}, "open differential"),
    ({"diff": "locked"}, "open differential"),
    ({"tv_mode": "hybrid"}, "hybrid"),
    ({"steer_noise": 0.05}, "steering noise"),
])
def test_unsupported_configurations_raise(kw, match):
    with pytest.raises(NotImplementedError, match=match):
        BatchedDrivingEnv(EnvConfig(**kw), n=2)


def test_end_to_end_mode_has_five_actions_and_runs():
    cfg = EnvConfig(tv_mode="end_to_end")
    env = BatchedDrivingEnv(cfg, n=4, seed=0)
    assert env.act_dim == 5
    env.reset(0)
    o, r, d, i = env.step(np.zeros((4, 5)))
    assert o.shape == (4, env.obs_dim)
    assert r.shape == (4,) and d.shape == (4,)


def test_wrong_action_shape_is_refused():
    env = BatchedDrivingEnv(EnvConfig(), n=4, seed=0)
    env.reset(0)
    with pytest.raises(ValueError, match="expected actions"):
        env.step(np.zeros((3, 2)))


# ---------------------------------------------------------------------------
# physics spot-checks against the reference's own methods
# ---------------------------------------------------------------------------

def test_wheel_loads_match_the_reference():
    """External check (rule 11): compared against DoubleTrackBackend's own
    method, not against a restatement of the batched formula."""
    from physics.double_track import CORNERS, DoubleTrackBackend
    cfg = EnvConfig()
    env = BatchedDrivingEnv(cfg, n=5, seed=0)
    ref = DoubleTrackBackend(cfg.params)
    rng = np.random.default_rng(1)
    a_x = rng.uniform(-8.0, 8.0, 5)
    a_y = rng.uniform(-10.0, 10.0, 5)
    got = env.wheel_loads(a_x, a_y)
    for i in range(5):
        want = ref.wheel_loads(float(a_x[i]), float(a_y[i]))
        for j, c in enumerate(CORNERS):
            assert got[i, j] == pytest.approx(want[c], rel=1e-12)


def test_slip_angles_match_the_reference():
    from physics.double_track import CORNERS, DoubleTrackBackend
    from physics.bicycle import BicycleState
    cfg = EnvConfig()
    env = BatchedDrivingEnv(cfg, n=5, seed=0)
    ref = DoubleTrackBackend(cfg.params)
    rng = np.random.default_rng(2)
    v_x = rng.uniform(8.0, 30.0, 5)
    v_y = rng.uniform(-3.0, 3.0, 5)
    r = rng.uniform(-1.0, 1.0, 5)
    st = rng.uniform(-0.4, 0.4, 5)
    got = env.slip_angles(v_x, v_y, r, st)
    for i in range(5):
        s = BicycleState(v_x=float(v_x[i]), v_y=float(v_y[i]),
                         yaw_rate=float(r[i]), steer=float(st[i]))
        want = ref.slip_angles(s)
        for j, c in enumerate(CORNERS):
            assert got[i, j] == pytest.approx(want[c], rel=1e-12)
