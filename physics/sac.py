"""Soft actor-critic — the off-policy half of Season 3's learning code.

**Why this exists alongside `physics/ppo.py`.** Seven training runs with PPO
failed the same way: the policy converges within ~10 updates and then does
not move. In the last one `eval_return` sat in a 653-659 band for **280
updates and 73 million steps** while `explained_variance` held at 0.93 — the
critic modelled that policy accurately, so it was not a learning failure. It
was a converged local optimum the policy could not explore its way out of.

Fuchs et al. (RA-L 2021) name this mechanism directly:

    "PPO required much more training data and suffered from premature
     convergences due to its state-independent exploration."

And every headline racing agent is off-policy: GT Sophy (QR-SAC), Fuchs
(SAC), TC-Driver (SAC), Hildisch (SAC), Evans (TD3). PPO's exploration is a
single state-independent `log_std` vector — the same noise everywhere on the
circuit. SAC's is a **state-dependent** standard deviation the network
outputs per observation, so it can be wide entering an unfamiliar corner and
narrow on a straight it has solved. That is the property this project has
been missing, and no reward or track change substitutes for it.

`ppo.py` is unchanged and stays the reference for Episodes 9-15; nothing here
touches it.

Written in the same spirit as `ppo.py` — a readable implementation rather
than a library import, so the mechanism is inspectable when a run goes wrong.

**Hyperparameters follow the published racing systems** rather than SAC's
MuJoCo defaults, since that is the domain the failure is in:

| | Fuchs (GTS) | GT Sophy | here |
|---|---|---|---|
| gamma | 0.98-0.982 | 0.9896 | 0.98 |
| entropy temp alpha | 0.01 | 0.01 | 0.01 |
| target mix tau | — | 0.005 | 0.005 |
| n-step return | 5 | 7 | 5 |
| minibatch | 4,096 | 1,024 | 1,024 |
| replay | 4e6 | 1e7 | 1e6 |
| hidden | 2 x 256 | 4 x 2048 | 2 x 256 |

Note both use a FIXED alpha rather than the auto-tuned temperature that is
standard elsewhere; alpha = 0.01 is far below SAC's usual ~0.2 because the
reward scale here is progress in metres, not a normalised MuJoCo return.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

LOG_STD_MIN, LOG_STD_MAX = -10.0, 2.0


@dataclass
class SACConfig:
    total_steps: int = 20_000_000
    n_envs: int = 64
    #: Environment steps between gradient updates, per environment. 1 means
    #: one gradient step per environment step collected -- the standard SAC
    #: ratio, and far more updates per sample than PPO's 10 epochs over a
    #: rollout.
    updates_per_step: float = 0.5
    warmup_steps: int = 50_000
    batch_size: int = 1024
    replay_size: int = 1_000_000
    gamma: float = 0.98
    tau: float = 0.005
    alpha: float = 0.01
    #: Learn the entropy temperature instead of fixing it, targeting
    #: ``target_entropy`` (default ``-act_dim``, the SAC standard).
    #:
    #: **Fixing alpha=0.01 failed and the reason is a transplant error.**
    #: Fuchs and GT Sophy both use 0.01, but Fuchs states it as "reward scale
    #: (1/alpha) = 100" -- their rewards are multiplied by 100. Ours are raw
    #: progress in metres, so copying the number without the scale left the
    #: effective temperature ~100x too low. Measured: entropy fell to -11.5
    #: against a -2 target for a 2-D action, i.e. the policy collapsed to
    #: near-deterministic within minutes -- the exact failure SAC was adopted
    #: to escape.
    #:
    #: Auto-tuning removes the guess: alpha is whatever holds entropy at the
    #: target, whatever the reward scale happens to be.
    auto_alpha: bool = True
    target_entropy: float | None = None
    lr: float = 3e-4
    hidden: int = 256
    n_step: int = 5
    seed: int = 0
    eval_every: int = 40
    eval_episodes: int = 4
    max_grad_norm: float = 10.0


def _mlp(i: int, h: int, o: int) -> nn.Sequential:
    return nn.Sequential(nn.Linear(i, h), nn.ReLU(),
                         nn.Linear(h, h), nn.ReLU(),
                         nn.Linear(h, o))


class SquashedGaussianActor(nn.Module):
    """Outputs a per-observation mean AND standard deviation.

    **This is the difference from `ppo.ActorCritic`.** There the standard
    deviation is one learned vector shared across every state; here the
    network emits it from the observation, so exploration can be wide where
    the policy is uncertain and narrow where it is not.
    """

    def __init__(self, obs_dim: int, act_dim: int, hidden: int):
        super().__init__()
        self.net = _mlp(obs_dim, hidden, 2 * act_dim)
        self.act_dim = act_dim

    def forward(self, obs, deterministic: bool = False, with_logp: bool = True):
        mu, log_std = self.net(obs).chunk(2, dim=-1)
        log_std = torch.clamp(log_std, LOG_STD_MIN, LOG_STD_MAX)
        std = log_std.exp()
        if deterministic:
            u = mu
        else:
            u = mu + std * torch.randn_like(mu)
        a = torch.tanh(u)
        if not with_logp:
            return a, None
        # Change of variables for the tanh squash. The numerically stable
        # form: log(1 - tanh(u)^2) = 2*(log 2 - u - softplus(-2u)).
        logp = (-0.5 * (((u - mu) / (std + 1e-8)) ** 2)
                - log_std - 0.5 * math.log(2 * math.pi)).sum(-1)
        logp = logp - (2.0 * (math.log(2.0) - u
                              - F.softplus(-2.0 * u))).sum(-1)
        return a, logp


class TwinQ(nn.Module):
    """Two independent Q networks; the minimum is used as the target.

    Twin critics are not decoration -- a single Q overestimates through the
    max in the bootstrap, and this environment's reward is dominated by a
    progress term that rewards exactly the overestimated direction.
    """

    def __init__(self, obs_dim: int, act_dim: int, hidden: int):
        super().__init__()
        self.q1 = _mlp(obs_dim + act_dim, hidden, 1)
        self.q2 = _mlp(obs_dim + act_dim, hidden, 1)

    def forward(self, obs, act):
        x = torch.cat([obs, act], dim=-1)
        return self.q1(x).squeeze(-1), self.q2(x).squeeze(-1)


class Replay:
    """Flat circular buffer of n-step transitions."""

    def __init__(self, size: int, obs_dim: int, act_dim: int):
        self.obs = np.zeros((size, obs_dim), dtype=np.float32)
        self.act = np.zeros((size, act_dim), dtype=np.float32)
        self.rew = np.zeros(size, dtype=np.float32)
        self.nobs = np.zeros((size, obs_dim), dtype=np.float32)
        self.done = np.zeros(size, dtype=np.float32)
        self.size, self.ptr, self.full = size, 0, False

    def add_batch(self, o, a, r, no, d):
        n = len(o)
        idx = (self.ptr + np.arange(n)) % self.size
        self.obs[idx], self.act[idx], self.rew[idx] = o, a, r
        self.nobs[idx], self.done[idx] = no, d
        self.full = self.full or self.ptr + n >= self.size
        self.ptr = int((self.ptr + n) % self.size)

    def __len__(self):
        return self.size if self.full else self.ptr

    def sample(self, batch: int, rng):
        i = rng.integers(0, len(self), batch)
        t = lambda x: torch.as_tensor(x[i])
        return t(self.obs), t(self.act), t(self.rew), t(self.nobs), t(self.done)


class _NStep:
    """Per-environment rolling window that emits n-step transitions.

    Fuchs changed SAC's default 1-step TD error to a 5-step one "to stabilize
    training"; GT Sophy's own ablation puts 1-step **1.59 s/lap** behind
    n=9 on Maggiore, with the whole penalty concentrated at n=1. So this is
    not a tuning knob -- 1-step is the thing to avoid.
    """

    def __init__(self, n_envs: int, n: int, gamma: float):
        self.n, self.gamma = n, gamma
        self.buf = [[] for _ in range(n_envs)]

    def push(self, i, o, a, r, no, d):
        """Returns a list of ready (obs, act, R_n, next_obs, done) tuples."""
        self.buf[i].append((o, a, r, no, d))
        out = []
        if d:
            # Flush the whole window on termination: every pending transition
            # ends at this terminal state, with the discounted partial return.
            while self.buf[i]:
                out.append(self._collapse(self.buf[i]))
                self.buf[i].pop(0)
        elif len(self.buf[i]) >= self.n:
            out.append(self._collapse(self.buf[i]))
            self.buf[i].pop(0)
        return out

    def _collapse(self, w):
        R, g = 0.0, 1.0
        for (_, _, r, _, d) in w:
            R += g * r
            g *= self.gamma
            if d:
                break
        o, a = w[0][0], w[0][1]
        no, d_last = w[-1][3], w[-1][4]
        return o, a, R, no, float(d_last)


def _evaluate(actor, env, episodes: int, seed0: int = 10_000):
    """Deployed performance: the MEAN action, not a sample (F61, D6)."""
    rets, dists, fins = [], [], []
    for k in range(episodes):
        o = env.reset(seed0 + k)
        done, tot, info = False, 0.0, {}
        while not done:
            with torch.no_grad():
                a, _ = actor(torch.as_tensor(o, dtype=torch.float32),
                             deterministic=True, with_logp=False)
            o, r, done, info = env.step(a.numpy())
            tot += r
        rets.append(tot)
        dists.append(float(getattr(env, "_dist_since_reset", np.nan)))
        fins.append(float(bool(info.get("finished", False))))
    return {"eval_return": float(np.mean(rets)),
            "eval_distance": float(np.mean(dists)),
            "eval_finish_rate": float(np.mean(fins))}


def train(make_batched_env, cfg: SACConfig | None = None, on_update=None,
          make_eval_env=None, init_state_dict=None) -> dict:
    """Train a SAC policy. Returns the actor plus a per-update history."""
    cfg = cfg or SACConfig()
    torch.manual_seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)

    env = make_batched_env(cfg.n_envs)
    obs_dim, act_dim = env.obs_dim, env.act_dim
    actor = SquashedGaussianActor(obs_dim, act_dim, cfg.hidden)
    critic = TwinQ(obs_dim, act_dim, cfg.hidden)
    target = TwinQ(obs_dim, act_dim, cfg.hidden)
    target.load_state_dict(critic.state_dict())
    for p in target.parameters():
        p.requires_grad_(False)
    if init_state_dict is not None:
        actor.load_state_dict(init_state_dict)

    opt_a = torch.optim.Adam(actor.parameters(), lr=cfg.lr)
    opt_c = torch.optim.Adam(critic.parameters(), lr=cfg.lr)
    target_ent = (float(cfg.target_entropy) if cfg.target_entropy is not None
                  else -float(act_dim))
    log_alpha = torch.tensor(float(np.log(cfg.alpha)), requires_grad=True)
    opt_alpha = torch.optim.Adam([log_alpha], lr=cfg.lr)
    buf = Replay(cfg.replay_size, obs_dim, act_dim)
    nstep = _NStep(cfg.n_envs, cfg.n_step, cfg.gamma)
    eval_env = make_eval_env() if make_eval_env is not None else None

    obs = env.reset(cfg.seed)
    history, t0 = [], time.time()
    steps = 0
    upd = 0
    ep_ret = np.zeros(cfg.n_envs)
    fin_ret, fin_off, fin_slip = [], [], []
    grad_budget = 0.0
    best = {"eval_return": -1e30}
    best_state = None

    while steps < cfg.total_steps:
        # --- collect -----------------------------------------------------
        with torch.no_grad():
            if steps < cfg.warmup_steps:
                a = rng.uniform(-1, 1, (cfg.n_envs, act_dim)).astype(np.float32)
            else:
                at, _ = actor(torch.as_tensor(obs, dtype=torch.float32),
                              with_logp=False)
                a = at.numpy()
        nobs, r, d, info = env.step(a)
        steps += cfg.n_envs
        ep_ret += r
        if "episode_return" in info:
            fin_ret.extend(np.atleast_1d(info["episode_return"]).tolist())
            fin_off.extend(np.atleast_1d(info["episode_off_track"]).astype(float).tolist())
            fin_slip.extend(np.atleast_1d(info["episode_worst_slip_deg"]).tolist())

        ready_o, ready_a, ready_r, ready_no, ready_d = [], [], [], [], []
        for i in range(cfg.n_envs):
            for (o_, a_, R_, no_, d_) in nstep.push(i, obs[i], a[i], float(r[i]),
                                                    nobs[i], bool(d[i])):
                ready_o.append(o_); ready_a.append(a_); ready_r.append(R_)
                ready_no.append(no_); ready_d.append(d_)
        if ready_o:
            buf.add_batch(np.asarray(ready_o, dtype=np.float32),
                          np.asarray(ready_a, dtype=np.float32),
                          np.asarray(ready_r, dtype=np.float32),
                          np.asarray(ready_no, dtype=np.float32),
                          np.asarray(ready_d, dtype=np.float32))
        obs = nobs

        # --- learn -------------------------------------------------------
        grad_budget += cfg.updates_per_step * cfg.n_envs
        if len(buf) < cfg.batch_size or steps < cfg.warmup_steps:
            grad_budget = 0.0
            continue
        n_grad = int(grad_budget)
        grad_budget -= n_grad
        q_loss = pi_loss = ent = 0.0
        for _ in range(n_grad):
            bo, ba, br, bno, bd = buf.sample(cfg.batch_size, rng)
            alpha = (log_alpha.exp().detach() if cfg.auto_alpha
                     else torch.tensor(cfg.alpha))
            with torch.no_grad():
                na, nlogp = actor(bno)
                tq1, tq2 = target(bno, na)
                # gamma^n, because the stored reward is an n-step return.
                y = br + (cfg.gamma ** cfg.n_step) * (1.0 - bd) * (
                    torch.min(tq1, tq2) - alpha * nlogp)
            q1, q2 = critic(bo, ba)
            lq = F.mse_loss(q1, y) + F.mse_loss(q2, y)
            opt_c.zero_grad(set_to_none=True)
            lq.backward()
            nn.utils.clip_grad_norm_(critic.parameters(), cfg.max_grad_norm)
            opt_c.step()

            for p in critic.parameters():
                p.requires_grad_(False)
            pa, plogp = actor(bo)
            pq1, pq2 = critic(bo, pa)
            lpi = (alpha * plogp - torch.min(pq1, pq2)).mean()
            opt_a.zero_grad(set_to_none=True)
            lpi.backward()
            nn.utils.clip_grad_norm_(actor.parameters(), cfg.max_grad_norm)
            opt_a.step()
            for p in critic.parameters():
                p.requires_grad_(True)

            if cfg.auto_alpha:
                # Raise alpha while entropy is below target, lower it above.
                la = -(log_alpha.exp()
                       * (plogp.detach() + target_ent)).mean()
                opt_alpha.zero_grad(set_to_none=True)
                la.backward()
                opt_alpha.step()

            with torch.no_grad():
                for p, tp in zip(critic.parameters(), target.parameters()):
                    tp.mul_(1.0 - cfg.tau).add_(cfg.tau * p)
            q_loss += float(lq.detach())
            pi_loss += float(lpi.detach())
            ent += float(-plogp.detach().mean())

        if n_grad == 0:
            continue
        upd += 1
        tail = lambda v: float(np.mean(v[-200:])) if v else float("nan")
        rec = {
            "update": upd, "steps": steps, "wall_s": time.time() - t0,
            "q_loss": q_loss / n_grad, "policy_loss": pi_loss / n_grad,
            "entropy": ent / n_grad, "replay": len(buf),
            "alpha": float(log_alpha.exp().detach()),
            "target_entropy": target_ent,
            "return_mean": tail(fin_ret), "off_track_rate": tail(fin_off),
            "worst_slip_mean_deg": tail(fin_slip),
        }
        if eval_env is not None and upd % cfg.eval_every == 0:
            rec.update(_evaluate(actor, eval_env, cfg.eval_episodes))
            if rec["eval_return"] > best["eval_return"]:
                best = {k: rec[k] for k in rec if k.startswith("eval_")}
                best["update"] = upd
                best_state = {k: v.clone() for k, v in actor.state_dict().items()}
        history.append(rec)
        if on_update is not None:
            on_update(rec)

    if best_state is not None:
        actor.load_state_dict(best_state)
    return {"model": actor, "critic": critic, "history": history,
            "best_eval": best, "best_update": best.get("update")}
