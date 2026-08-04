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

import copy
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
    #: Separate grad-norm clip for the value head. ``None`` (the default)
    #: reuses ``max_grad_norm``, reproducing every existing run exactly.
    #:
    #: TRACKS.md staging step 5: F51's own fix already separates the actor's
    #: and critic's clips SO one cannot throttle the other, but a single
    #: fixed cap still throttles the critic on its own once return
    #: magnitude changes — measured directly: reverting `gamma` 0.9995 ->
    #: 0.999 with `off_track_penalty=500` left `explained_variance` at
    #: -0.001 for 19 straight updates (no recovery at all), ruling out the
    #: horizon and pointing at the reward scale itself. Returns of order 40
    #: (F51's own case) make a value loss near 1600 and a raw gradient norm
    #: of ~150 against a 0.5 clip; the current penalties push typical
    #: returns into the hundreds-to-low-thousands, a proportionally larger
    #: raw gradient the same fixed 0.5 clip would throttle even harder.
    value_max_grad_norm: float | None = None
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

    # --- Episode 14: model selection. Both default to OFF, so every Season 3
    # result is reproduced bit-for-bit by the code path it was produced with.
    #
    #: Evaluate the DEPLOYED (mean-action) policy every N updates and keep the
    #: best checkpoint. 0 disables it and ``train`` returns the final weights,
    #: which is what Episodes 9-11 did.
    #:
    #: **This exists because not doing it produced a wrong published result.**
    #: Episode 14's first production run trained six policies, every one of
    #: which passed through a window where it drove the full 393 m inside the
    #: tire's own +/-12 deg fit with a ~0% off-track rate — and then kept
    #: drifting, because nothing was watching. Only the final weights were
    #: saved, so six healthy policies were reported as "RL does not converge."
    #: The project already had the rule that would have caught it (F61: a
    #: reinforcement-learning result is the DEPLOYED policy's performance); it
    #: was applied once at the end instead of throughout. See FINDINGS F93.
    #:
    #: Selection is on mean deployed **return** — the objective the reward
    #: already defines, envelope penalty included — and NOT on "did it stay
    #: inside the envelope". Selecting on the envelope would be selecting on
    #: the thing D6 then independently checks, which is how a gate becomes a
    #: formality.
    eval_every: int = 0
    #: Deployed-policy evaluation episodes per checkpoint. Each is a full lap,
    #: so this is the dominant cost of turning evaluation on (~6% of wall-clock
    #: at ``eval_every=20``).
    eval_episodes: int = 4
    #: First seed for evaluation episodes. Held out from training by being far
    #: outside the range ``train`` draws its own reset seeds from, so a policy
    #: cannot be selected on a start it was trained on.
    eval_seed0: int = 1_000_000
    #: Decay the entropy bonus linearly to zero over training. Off reproduces
    #: Season 3. On, the policy can actually sharpen late: with a constant
    #: bonus the log standard deviation sits where it was initialised for the
    #: whole run (measured, Episodes 10 and 14 alike), which leaves the
    #: mean-action policy you would ship a different driver from the sampled
    #: one the training curves describe — D6's ``greedy_and_stochastic_agree``.
    entropy_anneal: bool = False


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


def _evaluate_deployed(model, env, episodes: int, seed0: int) -> dict:
    """Roll the DEPLOYED (mean-action) policy on held-out seeds.

    Deliberately uses only ``reset``/``step``, so this stays as
    environment-agnostic as the rest of this module. Consumes neither the
    training RNG nor torch's, so turning evaluation on cannot change the
    trajectory of the run it is watching.
    """
    rets, dists, fins = [], [], []
    for k in range(episodes):
        o = env.reset(seed0 + k)
        done, total, info = False, 0.0, {}
        while not done:
            with torch.no_grad():
                a = model.actor(torch.as_tensor(o, dtype=torch.float32)).numpy()
            o, r, done, info = env.step(a)
            total += r
        rets.append(total)
        # `info["s"]` is ABSOLUTE track position; on a closed circuit with a
        # non-zero start that is not distance covered (F110). The env tracks
        # the start-relative figure itself.
        dists.append(float(getattr(env, "_dist_since_reset", float("nan"))))
        fins.append(float(bool(info.get("finished", False))))
    return {"eval_return": float(np.mean(rets)),
            "eval_distance": float(np.mean(dists)),
            "eval_finish_rate": float(np.mean(fins))}


def train(make_env=None, cfg: PPOConfig | None = None, on_update=None,
          make_eval_env=None, make_batched_env=None,
          init_state_dict=None) -> dict:
    """Train a policy. ``make_env(i)`` builds environment ``i``.

    Returns the trained model plus a per-update history — the raw material D6
    reads. Nothing here decides whether training *went well*; that judgement is
    the diagnostic's job, computed downstream from this history (CLAUDE.md
    rule 7).

    ``make_eval_env()`` builds the environment the deployed policy is scored
    on when ``cfg.eval_every > 0``. It should be the environment the policy
    will actually be *evaluated* in — no start jitter, no training-only
    perturbation — because a checkpoint selected on the training distribution
    is not selected on the thing being reported.

    With ``cfg.eval_every == 0`` (the default) this is exactly the function
    Episodes 9-11 called: no evaluation, no selection, final weights returned.

    ``init_state_dict`` (TRACKS.md staging step 5's training schedule,
    stage 2): warm-start the actor-critic from a prior checkpoint's weights
    instead of a fresh random init. **``None`` (the default) reproduces every
    existing call bit-for-bit** — the model is constructed exactly as before
    and nothing here touches it. The optimiser is always fresh (Adam's own
    moment estimates do not transfer across a changed reward/observation
    distribution the way the weights do), and the learning-rate anneal and
    entropy schedule both restart from update 0 — a warm start changes where
    training begins, not what a training run's own schedule means.
    """
    cfg = cfg or PPOConfig()
    torch.manual_seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)

    # Two rollout paths, one learning algorithm. ``make_batched_env`` builds an
    # environment that steps all ``cfg.n_envs`` cars per call
    # (``physics/batched_env.py``); without it the original list-of-envs loop
    # runs, unchanged, and every Season 3 and Season 4 result reproduces.
    batched = make_batched_env(cfg.n_envs) if make_batched_env is not None else None
    if batched is not None:
        envs = []
        obs_dim, act_dim = batched.obs_dim, batched.act_dim
    else:
        envs = [make_env(i) for i in range(cfg.n_envs)]
        obs_dim, act_dim = envs[0].obs_dim, envs[0].act_dim
    model = ActorCritic(obs_dim, act_dim, cfg.hidden, cfg.init_log_std)
    if init_state_dict is not None:
        model.load_state_dict(init_state_dict)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr, eps=1e-5)

    obs = (batched.reset(int(rng.integers(1 << 30))) if batched is not None
           else np.stack([e.reset(int(rng.integers(1 << 30))) for e in envs]))
    n_updates = max(cfg.total_steps // (cfg.n_envs * cfg.rollout_steps), 1)
    history: list[dict] = []
    # Episode statistics have to be collected as episodes end, because an
    # environment resets the moment it terminates and its log is gone.
    finished_returns: list[float] = []
    finished_distance: list[float] = []
    finished_slip: list[float] = []
    finished_offtrack: list[float] = []
    #: Mean speed over the rollout, every step of every instance. Rollout-level
    #: rather than per-episode on purpose: "is the policy pinned against the
    #: cap" is a question about the whole distribution of driving, not about
    #: how episodes happened to end.
    step_speeds: list[float] = []
    t_start = time.time()

    eval_env = None
    if cfg.eval_every > 0:
        if make_eval_env is None:
            raise ValueError(
                "cfg.eval_every > 0 needs make_eval_env — the environment the "
                "DEPLOYED policy is scored on. Reusing a training env would "
                "select the checkpoint on the training distribution (start "
                "jitter and all), which is not what gets reported.")
        eval_env = make_eval_env()
    best = {"score": -float("inf"), "state": None, "update": -1, "eval": None}

    for update in range(n_updates):
        if cfg.anneal_lr:
            for g in opt.param_groups:
                g["lr"] = cfg.lr * (1.0 - update / n_updates)
        ent_coef = (cfg.entropy_coef * (1.0 - update / n_updates)
                    if cfg.entropy_anneal else cfg.entropy_coef)

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

            if batched is not None:
                obs, r, done, info = batched.step(a_np)
                buf_rew[t], buf_done[t] = r, done.astype(float)
                # The batched env auto-resets and reports the terminal values
                # of whatever ended this step, so these are the same statistics
                # the single-instance path reads off each env's own log.
                finished_returns.extend(info["episode_return"].tolist())
                finished_distance.extend(info["episode_distance"].tolist())
                finished_slip.extend(info["episode_worst_slip_deg"].tolist())
                finished_offtrack.extend(
                    info["episode_off_track"].astype(float).tolist())
                if "speed" in info:
                    step_speeds.append(float(np.mean(info["speed"])))
            else:
                for i, e in enumerate(envs):
                    o, r, done, info = e.step(a_np[i])
                    buf_rew[t, i] = r
                    buf_done[t, i] = float(done)
                    if "speed" in info:
                        step_speeds.append(float(info["speed"]))
                    if done:
                        h = e.history()
                        finished_returns.append(float(np.sum(h["reward"])))
                        # start-relative, not h["s"][-1] -- see F110
                        finished_distance.append(
                            float(getattr(e, "_dist_since_reset", np.nan)))
                        finished_slip.append(float(np.max(h["alpha_max_deg"])))
                        finished_offtrack.append(float(bool(info["off_track"])))
                        # MUST stay under `if done`. Adding the speed logging
                        # above once left this line indented under
                        # `if "speed" in info`, which is true on EVERY step --
                        # so the env reset every step, every episode was one
                        # step long, `done` never fired, and a 112-minute
                        # POWER-REVIEW Phase 3 run trained on nothing.
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
                        - ent_coef * ent.mean())
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
                nn.utils.clip_grad_norm_(
                    model.value_parameters,
                    cfg.max_grad_norm if cfg.value_max_grad_norm is None
                    else cfg.value_max_grad_norm)
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
            "speed_mean": (float(np.mean(step_speeds)) if step_speeds
                          else float("nan")),
            "entropy_coef": ent_coef,
        }

        # Score the deployed policy and keep the best one. The last update is
        # always evaluated, so "best" is never worse than the final weights
        # this function used to return unconditionally.
        if eval_env is not None and (update % cfg.eval_every == 0
                                     or update == n_updates - 1):
            ev = _evaluate_deployed(model, eval_env, cfg.eval_episodes,
                                    cfg.eval_seed0)
            rec.update(ev)
            if ev["eval_return"] > best["score"]:
                best = {"score": ev["eval_return"],
                        "state": copy.deepcopy(model.state_dict()),
                        "update": update, "eval": ev}

        history.append(rec)
        if on_update is not None:
            on_update(rec)

    out = {"model": model, "history": history, "config": asdict(cfg)}
    if best["state"] is not None:
        # ``model`` is left holding the SELECTED weights, so every caller that
        # simply used the returned model gets the checkpoint that was chosen.
        # The final weights stay reachable for the comparison that shows why
        # selection was needed at all.
        out["final_state"] = copy.deepcopy(model.state_dict())
        model.load_state_dict(best["state"])
        out["best_update"] = best["update"]
        out["best_eval"] = best["eval"]
        out["n_updates"] = n_updates
    return out


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
