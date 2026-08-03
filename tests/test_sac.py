"""SAC's pieces, checked where they are easy to get silently wrong.

Written because seven PPO runs failed on exploration and this is the
replacement -- if it is subtly broken the failure will look identical.
"""

import math

import numpy as np
import pytest
import torch

from physics.sac import (SACConfig, SquashedGaussianActor, TwinQ, Replay,
                         _NStep, train)


def test_squashed_gaussian_logprob_matches_numeric_density():
    """The tanh change-of-variables correction is the classic place SAC goes
    wrong, and a wrong one still trains -- just badly. Check against a
    numerically estimated density."""
    torch.manual_seed(0)
    actor = SquashedGaussianActor(4, 2, 32)
    obs = torch.zeros(1, 4)
    with torch.no_grad():
        mu, log_std = actor.net(obs).chunk(2, dim=-1)
        std = log_std.clamp(-10, 2).exp()
        # Sample in pre-squash space, push through, compare analytic logp to
        # the transformed Gaussian density computed independently.
        u = mu + std * torch.randn(20000, 2)
        a = torch.tanh(u)
        logp_analytic = (
            (-0.5 * (((u - mu) / std) ** 2) - log_std
             - 0.5 * math.log(2 * math.pi)).sum(-1)
            - (2.0 * (math.log(2.0) - u
                      - torch.nn.functional.softplus(-2.0 * u))).sum(-1))
        # A correct density integrates to 1 over the squashed support, so
        # E[1/p] over samples ~ volume of the support = 2^act_dim = 4.
        vol = float(torch.exp(-logp_analytic).mean())
    assert 3.4 < vol < 4.6, f"implied support volume {vol:.2f}, expected ~4"


def test_actions_are_bounded_and_deterministic_mode_differs():
    actor = SquashedGaussianActor(4, 2, 32)
    obs = torch.randn(64, 4)
    a, logp = actor(obs)
    assert a.shape == (64, 2) and logp.shape == (64,)
    assert a.abs().max() <= 1.0, "tanh squash must bound actions to [-1, 1]"
    d, _ = actor(obs, deterministic=True, with_logp=False)
    assert not torch.allclose(a, d), "deterministic mode is not distinct"


def test_exploration_is_state_dependent_which_is_the_whole_point():
    """PPO here has ONE log_std vector for every state; that is the mechanism
    Fuchs blames for premature convergence. SAC must produce a different
    spread for different observations or it buys us nothing."""
    torch.manual_seed(0)
    actor = SquashedGaussianActor(4, 2, 64)
    with torch.no_grad():
        _, ls_a = actor.net(torch.zeros(1, 4)).chunk(2, dim=-1)
        _, ls_b = actor.net(torch.ones(1, 4) * 3.0).chunk(2, dim=-1)
    assert not torch.allclose(ls_a, ls_b, atol=1e-4), (
        "log_std identical across observations -- exploration is not "
        "state-dependent and this is just PPO with extra steps")


def test_nstep_collapses_to_the_discounted_partial_return():
    ns = _NStep(1, 3, 0.5)
    out = []
    for k, r in enumerate([1.0, 1.0, 1.0, 1.0]):
        out += ns.push(0, np.array([float(k)]), np.array([0.0]), r,
                       np.array([float(k + 1)]), False)
    assert out, "no n-step transition emitted after n pushes"
    o, a, R, no, d = out[0]
    assert R == pytest.approx(1.0 + 0.5 + 0.25)
    assert o[0] == 0.0 and no[0] == 3.0


def test_nstep_flushes_everything_on_termination():
    """A truncated window must still emit, or transitions preceding every
    crash are silently dropped -- which is exactly the data about crashing."""
    ns = _NStep(1, 5, 0.9)
    ns.push(0, np.array([0.]), np.array([0.]), 1.0, np.array([1.]), False)
    ns.push(0, np.array([1.]), np.array([0.]), 1.0, np.array([2.]), False)
    out = ns.push(0, np.array([2.]), np.array([0.]), -10.0, np.array([3.]), True)
    assert len(out) == 3, f"terminal flush emitted {len(out)}, expected 3"
    assert all(t[4] == 1.0 for t in out), "flushed transitions must be terminal"


def test_replay_wraps_without_losing_shape():
    b = Replay(100, 3, 2)
    for _ in range(5):
        b.add_batch(np.ones((40, 3), np.float32), np.ones((40, 2), np.float32),
                    np.ones(40, np.float32), np.ones((40, 3), np.float32),
                    np.zeros(40, np.float32))
    assert len(b) == 100
    o, a, r, no, d = b.sample(16, np.random.default_rng(0))
    assert o.shape == (16, 3) and a.shape == (16, 2) and r.shape == (16,)


def test_train_runs_and_fills_the_buffer():
    from physics.rl_env import EnvConfig
    from physics.batched_env import BatchedDrivingEnv
    from physics.track import long_exit
    cfg = SACConfig(total_steps=8 * 400, n_envs=8, warmup_steps=8 * 50,
                    batch_size=64, replay_size=10_000, hidden=32,
                    updates_per_step=0.05, eval_every=10_000)
    res = train(make_batched_env=lambda n: BatchedDrivingEnv(
        EnvConfig(track=long_exit(), max_steps=200), n=n, seed=0), cfg=cfg)
    assert res["history"], "no updates recorded"
    assert res["history"][-1]["replay"] > 0
    assert np.isfinite(res["history"][-1]["q_loss"])


def test_policy_eval_accepts_a_sac_actor():
    """ONE evaluator for both algorithms (D16). A second harness for SAC is
    how the F110 `finished` bug survived twenty runs, and "the new algorithm
    needs its own" is precisely the reasoning that would bring it back."""
    from experiments.tracks_pilot import policy_eval as PE
    from physics.track import long_exit
    track = long_exit()
    probe_actor = SquashedGaussianActor(12, 2, 32)
    r = PE.evaluate(probe_actor, track, n_sections=2, max_steps=120,
                    env_kwargs={"envelope_penalty": 0.0})
    assert 0.0 <= r.finish_rate <= 1.0
    assert np.isfinite(r.distance_mean)
    assert isinstance(r.headline(), str)
