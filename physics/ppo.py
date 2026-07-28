"""A small PPO, written out rather than imported.

There are good PPO implementations available and this is not trying to beat them.
It is here because Episode 9's subject is *what the policy learned and why*, and
that argument is much easier to make — and much harder to get wrong — when the
learning code is two hundred readable lines in the repository rather than a
dependency whose defaults nobody in the audience can see.

Scope, stated so nobody expects more: continuous actions, diagonal Gaussian
policy, generalised advantage estimation, clipped surrogate objective, separate
value head. No recurrence, no observation normalisation beyond what the
environment already does, no learning-rate schedule beyond linear decay. It is
enough to drive a corner and not much more.

Everything that matters for reproducibility is in :class:`PPOConfig`, and every
run writes its own config into the results file, because "which hyperparameters
was that?" is the question you cannot answer three months later.
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass, field

import numpy as np
import torch
import torch.nn as nn


@dataclass
class PPOConfig:
    total_steps: int = 300_000
    n_envs: int = 8
    rollout_steps: int = 512
    epochs: int = 10
    minibatches: int = 4
    gamma: float = 0.995          # long corner, sparse-ish progress reward
    gae_lambda: float = 0.95
    clip: float = 0.2
    lr: float = 3e-4
    value_coef: float = 0.5
    #: Small on purpose. The default 0.01 is tuned for discrete-action problems
    #: where entropy is bounded; here it pushes log_std UP without limit, and at
    #: 0.004 it beat the policy gradient outright — entropy rose from 1.84 to 1.88
    #: over 250k steps while the policy learned nothing. See FINDINGS F51.
    entropy_coef: float = 0.0005
    max_grad_norm: float = 0.5
    hidden: int = 64
    #: Initial policy standard deviation, log units, PER ACTION DIMENSION.
    #:
    #: **Set from the scale of a useful action, not from convention — and the two
    #: dimensions differ by an order of magnitude, so one number cannot serve
    #: both.**
    #:
    #: *Steering rate.* Holding the 40 m corner needs about 3.7 deg of steer,
    #: reached over half a second: ~7.4 deg/s against 200 deg/s of authority, a
    #: normalised action of 0.037. The usual -0.5 is a standard deviation of
    #: 0.61, sixteen times the signal being searched for; the policy sawed the
    #: wheel and left an 8 m road within a second, every episode. -2.5 gives
    #: 0.082, roughly twice the useful magnitude.
    #:
    #: *Throttle.* The useful range is the whole interval — full brake to full
    #: power. At 0.082 the policy converged to full throttle and then never
    #: sampled braking at all, arriving at the corner around 25 m/s where 19.5 is
    #: the physical limit, and sat in that local optimum for half a million
    #: steps. -1.0 gives 0.37, enough to actually try lifting off.
    #:
    #: See FINDINGS F52. A scalar is still accepted and broadcast.
    init_log_std: tuple[float, ...] = (-2.5, -1.0)
    seed: int = 0
    #: Linearly decay the learning rate to zero over training.
    anneal_lr: bool = True


class ActorCritic(nn.Module):
    """Two small MLPs and a state-independent action standard deviation.

    Separate trunks rather than a shared one: with a 12-dimensional observation
    there is nothing to gain from sharing, and separate networks make the value
    loss unable to disturb the policy features — one less thing to be confused by
    when a run goes wrong.
    """

    def __init__(self, obs_dim: int, act_dim: int, hidden: int = 64,
                 init_log_std: float | tuple[float, ...] = -0.5):
        super().__init__()
        self.actor = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.Tanh(),
            nn.Linear(hidden, hidden), nn.Tanh(),
            nn.Linear(hidden, act_dim),
        )
        self.critic = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.Tanh(),
            nn.Linear(hidden, hidden), nn.Tanh(),
            nn.Linear(hidden, 1),
        )
        ls = (torch.full((act_dim,), float(init_log_std))
              if np.isscalar(init_log_std)
              else torch.tensor(list(init_log_std), dtype=torch.float32))
        assert ls.shape == (act_dim,), (
            f"init_log_std has {tuple(ls.shape)} entries for {act_dim} actions")
        self.log_std = nn.Parameter(ls)
        # Small final-layer weights so the initial policy is nearly zero-mean:
        # a fresh policy that immediately saturates the steering is a fresh
        # policy that spends its first ten thousand steps in a ditch.
        for module, gain in ((self.actor, 0.01), (self.critic, 1.0)):
            last = [m for m in module if isinstance(m, nn.Linear)][-1]
            nn.init.orthogonal_(last.weight, gain)
            nn.init.zeros_(last.bias)

    @property
    def policy_parameters(self):
        """Actor weights plus the action spread — everything the policy is."""
        return list(self.actor.parameters()) + [self.log_std]

    @property
    def value_parameters(self):
        return list(self.critic.parameters())

    def distribution(self, obs: torch.Tensor) -> torch.distributions.Normal:
        return torch.distributions.Normal(self.actor(obs), self.log_std.exp())

    def value(self, obs: torch.Tensor) -> torch.Tensor:
        return self.critic(obs).squeeze(-1)

    def act(self, obs: torch.Tensor):
        dist = self.distribution(obs)
        a = dist.sample()
        return a, dist.log_prob(a).sum(-1), self.value(obs)

    def evaluate(self, obs: torch.Tensor, act: torch.Tensor):
        dist = self.distribution(obs)
        return (dist.log_prob(act).sum(-1), dist.entropy().sum(-1),
                self.value(obs))


def _gae(rewards, values, dones, last_value, gamma, lam):
    """Generalised advantage estimation over a [T, N] rollout."""
    T = rewards.shape[0]
    adv = np.zeros_like(rewards)
    running = np.zeros(rewards.shape[1], dtype=np.float64)
    next_value = last_value
    for t in reversed(range(T)):
        mask = 1.0 - dones[t]
        delta = rewards[t] + gamma * next_value * mask - values[t]
        running = delta + gamma * lam * mask * running
        adv[t] = running
        next_value = values[t]
    return adv, adv + values


def train(make_env, cfg: PPOConfig | None = None, on_update=None) -> dict:
    """Train a policy. ``make_env(i)`` builds environment ``i``.

    Returns the trained model plus a per-update history — the raw material D6
    reads. Nothing here decides whether training *went well*; that judgement is
    the diagnostic's job, computed downstream from this history (CLAUDE.md
    rule 7).
    """
    cfg = cfg or PPOConfig()
    torch.manual_seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)

    envs = [make_env(i) for i in range(cfg.n_envs)]
    obs_dim, act_dim = envs[0].obs_dim, envs[0].act_dim
    model = ActorCritic(obs_dim, act_dim, cfg.hidden, cfg.init_log_std)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr, eps=1e-5)

    obs = np.stack([e.reset(int(rng.integers(1 << 30))) for e in envs])
    n_updates = max(cfg.total_steps // (cfg.n_envs * cfg.rollout_steps), 1)
    history: list[dict] = []
    # Episode statistics have to be collected as episodes end, because an
    # environment resets the moment it terminates and its log is gone.
    finished_returns: list[float] = []
    finished_distance: list[float] = []
    finished_slip: list[float] = []
    finished_offtrack: list[float] = []
    t_start = time.time()

    for update in range(n_updates):
        if cfg.anneal_lr:
            for g in opt.param_groups:
                g["lr"] = cfg.lr * (1.0 - update / n_updates)

        buf_obs = np.zeros((cfg.rollout_steps, cfg.n_envs, obs_dim))
        buf_act = np.zeros((cfg.rollout_steps, cfg.n_envs, act_dim))
        buf_logp = np.zeros((cfg.rollout_steps, cfg.n_envs))
        buf_rew = np.zeros((cfg.rollout_steps, cfg.n_envs))
        buf_val = np.zeros((cfg.rollout_steps, cfg.n_envs))
        buf_done = np.zeros((cfg.rollout_steps, cfg.n_envs))

        for t in range(cfg.rollout_steps):
            with torch.no_grad():
                ot = torch.as_tensor(obs, dtype=torch.float32)
                a, logp, v = model.act(ot)
            a_np = a.numpy()
            buf_obs[t], buf_act[t] = obs, a_np
            buf_logp[t], buf_val[t] = logp.numpy(), v.numpy()

            for i, e in enumerate(envs):
                o, r, done, info = e.step(a_np[i])
                buf_rew[t, i] = r
                buf_done[t, i] = float(done)
                if done:
                    h = e.history()
                    finished_returns.append(float(np.sum(h["reward"])))
                    finished_distance.append(float(h["s"][-1]))
                    finished_slip.append(float(np.max(h["alpha_max_deg"])))
                    finished_offtrack.append(float(bool(info["off_track"])))
                    o = e.reset(int(rng.integers(1 << 30)))
                obs[i] = o

        with torch.no_grad():
            last_v = model.value(
                torch.as_tensor(obs, dtype=torch.float32)).numpy()
        adv, ret = _gae(buf_rew, buf_val, buf_done, last_v, cfg.gamma,
                        cfg.gae_lambda)

        b_obs = torch.as_tensor(buf_obs.reshape(-1, obs_dim), dtype=torch.float32)
        b_act = torch.as_tensor(buf_act.reshape(-1, act_dim), dtype=torch.float32)
        b_logp = torch.as_tensor(buf_logp.reshape(-1), dtype=torch.float32)
        b_adv = torch.as_tensor(adv.reshape(-1), dtype=torch.float32)
        b_ret = torch.as_tensor(ret.reshape(-1), dtype=torch.float32)

        n = b_obs.shape[0]
        idx = np.arange(n)
        mb = n // cfg.minibatches
        stats = {"policy_loss": [], "value_loss": [], "entropy": [],
                 "approx_kl": [], "clip_fraction": []}
        for _ in range(cfg.epochs):
            rng.shuffle(idx)
            for start in range(0, n, mb):
                j = idx[start:start + mb]
                logp, ent, v = model.evaluate(b_obs[j], b_act[j])
                ratio = (logp - b_logp[j]).exp()
                a_norm = (b_adv[j] - b_adv[j].mean()) / (b_adv[j].std() + 1e-8)
                l1 = ratio * a_norm
                l2 = torch.clamp(ratio, 1 - cfg.clip, 1 + cfg.clip) * a_norm
                pol_loss = -torch.min(l1, l2).mean()
                val_loss = ((v - b_ret[j]) ** 2).mean()
                loss = (pol_loss + cfg.value_coef * val_loss
                        - cfg.entropy_coef * ent.mean())
                opt.zero_grad()
                loss.backward()
                # Clip the actor and the critic SEPARATELY. Clipping them
                # together is the default in most implementations and it silently
                # broke this one: progress reward makes returns of order 40, so
                # the value loss starts near 1600 and its gradient norm is ~150
                # against the policy's ~1. A single clip at 0.5 then scales
                # everything by 0.0067, giving the policy an effective learning
                # rate of 2e-6. Training ran, cost curves moved, and the policy
                # did not update at all — approximate KL sat at 0.0000.
                #
                # The two networks share no parameters, so separating the clips
                # costs nothing and removes the coupling entirely. See FINDINGS
                # F51.
                nn.utils.clip_grad_norm_(model.policy_parameters,
                                         cfg.max_grad_norm)
                nn.utils.clip_grad_norm_(model.value_parameters,
                                         cfg.max_grad_norm)
                opt.step()
                with torch.no_grad():
                    stats["policy_loss"].append(float(pol_loss))
                    stats["value_loss"].append(float(val_loss))
                    stats["entropy"].append(float(ent.mean()))
                    # Schulman's low-variance KL estimator; the naive
                    # (old - new).mean() is unbiased but noisy enough to be
                    # useless as a health signal on minibatches this size.
                    lr_ = b_logp[j] - logp
                    stats["approx_kl"].append(float(
                        ((lr_.exp() - 1) - lr_).mean()))
                    stats["clip_fraction"].append(float(
                        ((ratio - 1).abs() > cfg.clip).float().mean()))

        rec = {
            "update": update,
            "steps": (update + 1) * cfg.n_envs * cfg.rollout_steps,
            "wall_s": time.time() - t_start,
            "lr": opt.param_groups[0]["lr"],
            "log_std": model.log_std.detach().numpy().tolist(),
            "explained_variance": _explained_variance(buf_val.ravel(),
                                                      ret.ravel()),
            **{k: float(np.mean(v)) for k, v in stats.items()},
            "episodes_finished": len(finished_returns),
            "return_mean": _tail_mean(finished_returns),
            "distance_mean": _tail_mean(finished_distance),
            "worst_slip_mean_deg": _tail_mean(finished_slip),
            "off_track_rate": _tail_mean(finished_offtrack),
        }
        history.append(rec)
        if on_update is not None:
            on_update(rec)

    return {"model": model, "history": history, "config": asdict(cfg)}


def _tail_mean(xs, n: int = 50) -> float:
    return float(np.mean(xs[-n:])) if xs else float("nan")


def _explained_variance(pred, target) -> float:
    """1 − Var(target − pred)/Var(target). Below 0 means worse than a constant."""
    var = np.var(target)
    return float("nan") if var == 0 else float(1.0 - np.var(target - pred) / var)


def greedy_policy(model: ActorCritic):
    """The mean action, no sampling. What the policy would do if you drove it."""
    def act(obs):
        with torch.no_grad():
            return model.actor(
                torch.as_tensor(obs, dtype=torch.float32)).numpy()
    return act


__all__ = ["PPOConfig", "ActorCritic", "train", "greedy_policy"]
