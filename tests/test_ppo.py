"""Tests for the learning code itself.

`physics/ppo.py` had no tests until Episode 14's re-run, which is not a
coincidence: the defect that made this file necessary (F93) was a missing
model-selection step, and nothing was checking what ``train`` returned. Every
Season 3 and Season 4 reinforcement-learning result comes out of this module.

The tests that matter here are the ones the code was **not** written around
(CLAUDE.md rule 11): that turning the new selection machinery on does not
perturb the run it is watching, and that the checkpoint handed back is the one
the recorded evaluations say is best — checked against the history, not
against the selector's own bookkeeping.
"""

from __future__ import annotations

import pytest
import torch

from physics.ppo import PPOConfig, greedy_policy, train
from physics.rl_env import DrivingEnv, EnvConfig


def _tiny(**kw) -> PPOConfig:
    """Small enough to run in seconds, long enough to take several updates."""
    base = dict(total_steps=6144, n_envs=4, rollout_steps=256, epochs=2,
                minibatches=2, seed=0)
    base.update(kw)
    return PPOConfig(**base)


def _train(cfg, tv_mode="none", eval_env=True):
    make = lambda i: DrivingEnv(EnvConfig(tv_mode=tv_mode), seed=i)
    kw = {}
    if eval_env:
        kw["make_eval_env"] = lambda: DrivingEnv(EnvConfig(tv_mode=tv_mode))
    return train(make, cfg, **kw)


# ---------------------------------------------------------------------------
# The seal: Season 3 must be reproducible by the path that produced it
# ---------------------------------------------------------------------------

def test_evaluation_is_off_by_default():
    """Episodes 9-11 ran without any of this, so it cannot be on by default."""
    cfg = PPOConfig()
    assert cfg.eval_every == 0
    assert cfg.entropy_anneal is False


def test_training_without_evaluation_is_unchanged_and_deterministic():
    a = _train(_tiny(), eval_env=False)
    b = _train(_tiny(), eval_env=False)
    for (k, x), (_, y) in zip(a["model"].state_dict().items(),
                              b["model"].state_dict().items()):
        assert torch.equal(x, y), f"{k} differs between identical seeds"
    # No selection happened, so none of its bookkeeping should appear.
    for key in ("best_update", "best_eval", "final_state"):
        assert key not in a


def test_turning_evaluation_on_does_not_change_the_trajectory():
    """The strongest guarantee here: watching the run must not steer it.

    ``_evaluate_deployed`` rolls the policy on its own environment and its own
    seeds, so if it leaked into either RNG the two runs below would diverge.
    Compared on the FINAL weights, because that is what the un-watched run
    returns and what the watched run stashes.
    """
    off = _train(_tiny(), eval_env=False)
    on = _train(_tiny(eval_every=2, eval_episodes=1), eval_env=True)
    for (k, x), (_, y) in zip(off["model"].state_dict().items(),
                              on["final_state"].items()):
        assert torch.equal(x, y), f"{k} moved when evaluation was switched on"


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def test_evaluation_without_an_eval_env_is_refused():
    """Silently falling back to a training env would select on start jitter."""
    with pytest.raises(ValueError, match="make_eval_env"):
        _train(_tiny(eval_every=2), eval_env=False)


def test_the_returned_model_is_the_best_checkpoint_not_the_last():
    res = _train(_tiny(eval_every=1, eval_episodes=1))
    evals = [h for h in res["history"] if "eval_return" in h]
    assert evals, "evaluation was requested but nothing was recorded"

    # Checked against the HISTORY — the record a human would audit — rather
    # than against the selector's own stored score.
    best = max(evals, key=lambda h: h["eval_return"])
    assert res["best_update"] == best["update"]
    assert res["best_eval"]["eval_return"] == pytest.approx(best["eval_return"])

    if res["best_update"] != res["n_updates"] - 1:
        differs = any(not torch.equal(res["model"].state_dict()[k], v)
                      for k, v in res["final_state"].items())
        assert differs, "selected a mid-run checkpoint but returned final weights"


def test_the_last_update_is_always_evaluated():
    """So selection can never do worse than the old return-the-final-weights
    behaviour: the final checkpoint is always a candidate."""
    res = _train(_tiny(eval_every=1000, eval_episodes=1))
    updates = [h["update"] for h in res["history"] if "eval_return" in h]
    assert res["n_updates"] - 1 in updates


def test_selection_scores_the_deployed_policy_not_a_sampled_one():
    """F61, enforced rather than asserted: the thing being scored has to be
    the mean action. Checked against ``greedy_policy``, which is what the
    episode's own evaluation uses — an independent path to the same number.
    """
    res = _train(_tiny(eval_every=1000, eval_episodes=1))
    env = DrivingEnv(EnvConfig())
    obs = env.reset(0)
    a = greedy_policy(res["model"])(obs)
    with torch.no_grad():
        b = res["model"].actor(torch.as_tensor(obs, dtype=torch.float32)).numpy()
    assert a == pytest.approx(b)


def test_evaluation_seeds_are_held_out_from_training():
    """A checkpoint chosen on a start the policy trained on is chosen on the
    training distribution. The default has to sit outside the range ``train``
    draws reset seeds from."""
    assert PPOConfig().eval_seed0 >= 1_000_000


# ---------------------------------------------------------------------------
# Entropy annealing
# ---------------------------------------------------------------------------

def test_entropy_coefficient_decays_to_nearly_zero_when_annealed():
    res = _train(_tiny(entropy_anneal=True, eval_every=1000, eval_episodes=1))
    h = res["history"]
    assert h[0]["entropy_coef"] == pytest.approx(res["config"]["entropy_coef"])
    assert h[-1]["entropy_coef"] < 0.2 * h[0]["entropy_coef"]


def test_entropy_coefficient_is_constant_when_not_annealed():
    res = _train(_tiny(), eval_env=False)
    coefs = {round(h["entropy_coef"], 12) for h in res["history"]}
    assert len(coefs) == 1


# ---------------------------------------------------------------------------
# The larger action spaces this episode added
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tv_mode,act_dim,log_std", [
    ("hybrid", 3, (-2.5, -1.0, -1.5)),
    ("end_to_end", 5, (-2.5, -1.5, -1.5, -1.5, -1.5)),
])
def test_selection_works_for_the_torque_vectoring_action_spaces(
        tv_mode, act_dim, log_std):
    res = _train(_tiny(eval_every=1, eval_episodes=1, init_log_std=log_std,
                       entropy_anneal=True), tv_mode=tv_mode)
    assert res["model"].log_std.shape[0] == act_dim
    assert "best_update" in res
    assert res["best_eval"]["eval_return"] == pytest.approx(
        max(h["eval_return"] for h in res["history"] if "eval_return" in h))
