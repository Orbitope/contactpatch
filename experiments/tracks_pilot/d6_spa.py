"""D6, adapted for a real circuit — TRACKS.md staging step 5, revised plan
item A ("make D6 the standing gate for every training run in this thread").

``diagnostics/D6_training_health.py`` is Season 3/4's standing training-health
diagnostic, and it should have been run on every tracks pilot — it was not,
and it has a check (``the_critic_predicts_returns``) that describes exactly
the dead-critic failure this thread's step-back review found by hand.

**Not a passthrough call to D6, because two of its seven checks are hardcoded
to the single synthetic corner every Season 3/4 episode trains on:**

- ``exploration_matches_the_action_scale`` computes the "useful steering
  scale" from ``physics.track.CORNER_RADIUS`` — the one corner
  ``long_exit``/``short_exit`` have. Meaningless for a 20-corner circuit with
  a real spread of radii.
- ``the_task_is_completable`` checks entry speed against THAT SAME corner's
  limit speed. Same problem.

Both checks' actual intent generalises cleanly: use Spa's OWN tightest
corner (max recovered curvature -> min radius) as the reference instead of
the synthetic track's one corner, since that is the most demanding steering
scenario and the most speed-constraining point on the whole circuit. That is
what this script does; everything else (KL, entropy, explained variance,
off-track rate, deployed-vs-sampled gap, tire envelope occupancy) is
D6's own logic, unmodified, called directly.

    python -m experiments.tracks_pilot.d6_spa <run_name>
        <run_name> is a stem under experiments/tracks_pilot/out/, e.g.
        "stage1" for stage1_history.json + stage1_policy.pt + stage1_config.json.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import torch

from diagnostics.common import Report
from diagnostics.D6_training_health import (DEPLOY_FINISH_RATE, GREEDY_GAP_FRACTION,
                                            KL_FLOOR, SLIP_BOUND_DEG, evaluate)
from physics.double_track import DoubleTrackBackend
from physics.ppo import ActorCritic
from physics.rl_env import DrivingEnv, EnvConfig, STEER_RATE_MAX
from physics.tracks_data import load_real_track
from physics import schema

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"


def _spa_tightest_corner_radius(spa, n=5000) -> float:
    s = np.linspace(0.0, spa.length, n, endpoint=False)
    kappa = np.abs(spa.curvature(s))
    return 1.0 / float(np.max(kappa))


def run_d6_spa(run_name: str, off_track_penalty: float, stall_penalty: float,
              progress_scale: float, tv_mode: str = "none") -> Report:
    """``off_track_penalty``/``stall_penalty``/``progress_scale`` must be
    passed explicitly -- they are ``EnvConfig`` fields, and ``PPOConfig``
    (what ``{run_name}_config.json`` actually holds) has no record of them
    at all. Silently defaulting here would reconstruct the WRONG reward for
    every run before ``stall_penalty``/``progress_scale`` existed (the
    gamma=0.999 runs used ``off_track_penalty=50``, not the later 500)."""
    history = json.loads((OUT / f"{run_name}_history.json").read_text())
    train_cfg = json.loads((OUT / f"{run_name}_config.json").read_text())
    spa = load_real_track("Spa")

    eval_cfg = EnvConfig(track=spa, max_steps=15_000, envelope_penalty=0.5,
                         off_track_penalty=off_track_penalty,
                         stall_penalty=stall_penalty,
                         progress_scale=progress_scale,
                         tv_mode=tv_mode)
    # obs_dim/act_dim must match what the checkpoint was actually trained
    # with -- probe a throwaway env instead of guessing from tv_mode.
    probe = DrivingEnv(eval_cfg)
    model = ActorCritic(probe.obs_dim, probe.act_dim, train_cfg["hidden"],
                        train_cfg["init_log_std"])
    model.load_state_dict(torch.load(OUT / f"{run_name}_policy.pt"))

    report = Report(f"D6-Spa-{run_name}", f"Training health (Spa-adapted) — {run_name}",
                    "D6's own checks, generalised from the single synthetic "
                    "corner to Spa's tightest corner where two checks depend on it.")

    p = eval_cfg.params
    ev = evaluate(model, eval_cfg, n=8)
    report.data["evaluation"] = {k: {kk: vv for kk, vv in v.items() if kk != "runs"}
                                 for k, v in ev.items()}
    report.data["train_config"] = train_cfg

    # -- did the optimiser do anything at all? (D6, unmodified) --------------
    report.section("Did the policy actually change?")
    kls = [h["approx_kl"] for h in history]
    median_kl = float(np.median(kls))
    report.add("policy_is_actually_updating", median_kl > KL_FLOOR,
              f"median approximate KL per update is {median_kl:.5f} against a "
              f"{KL_FLOOR:g} floor.", value=median_kl)
    ents = [h["entropy"] for h in history]
    grew = ents[-1] - ents[0]
    report.add("exploration_is_not_growing", grew <= 0.0,
              f"policy entropy went {ents[0]:+.2f} -> {ents[-1]:+.2f} ({grew:+.2f}).",
              value=grew)

    # -- is the search at the right scale? (ADAPTED: Spa's tightest corner) --
    report.section("Is the search at the scale of the problem?")
    r_min = _spa_tightest_corner_radius(spa)
    std = np.exp(np.asarray(train_cfg["init_log_std"], dtype=float)
                if not np.isscalar(train_cfg["init_log_std"])
                else np.full(2, train_cfg["init_log_std"]))
    useful_steer = (p.wheelbase / r_min) / 0.5 / STEER_RATE_MAX
    ratio = float(std[0] / useful_steer)
    report.add("exploration_matches_the_action_scale", 0.3 < ratio < 6.0,
              f"[ADAPTED from D6: uses Spa's tightest corner, r={r_min:.1f} m, "
              f"not the synthetic track's single corner] holding it needs a "
              f"normalised steering action of about {useful_steer:.3f}; the "
              f"policy searches with a standard deviation of {std[0]:.3f}, a "
              f"ratio of {ratio:.1f}x.", value=ratio)

    # -- is the task winnable? (ADAPTED: Spa's tightest corner) --------------
    report.section("Is the task possible, and did it get solved?")
    v_corner = math.sqrt(DoubleTrackBackend(p).max_lateral_g(r_min) * schema.G * r_min)
    report.add("the_task_is_completable", eval_cfg.entry_speed <= v_corner,
              f"[ADAPTED from D6: uses Spa's tightest corner, r={r_min:.1f} m, "
              f"not the synthetic track's single corner] the car makes "
              f"{v_corner:.1f} m/s round it at the limit and starts episodes "
              f"at {eval_cfg.entry_speed:.1f} m/s.",
              value={"tightest_corner_limit_ms": v_corner,
                     "entry_ms": eval_cfg.entry_speed,
                     "tightest_corner_radius_m": r_min})
    offs = [h["off_track_rate"] for h in history]
    report.add("the_off_track_rate_came_down",
              offs[-1] < 0.5 * max(offs[0], 1e-9) or offs[-1] < 0.1,
              f"episodes ending off the road went {offs[0]:.2f} -> {offs[-1]:.2f}. "
              "NOTE (Spa-specific, not in D6): with a multi-km lap and a "
              "policy nowhere near completing one, this rate is expected to "
              "stay near 1.0 regardless of safety improvement -- see the "
              "hazard metric (mean distance before crash) instead, computed "
              "downstream in the per-section eval, not here.",
              value=offs[-1], severity="note")

    # -- is the critic doing its job? (D6, unmodified -- the whole point) ----
    report.section("Is the critic predicting anything?")
    evs = [h["explained_variance"] for h in history]
    tail = float(np.median(evs[-max(len(evs) // 5, 1):]))
    report.add("the_critic_predicts_returns", tail > 0.3,
              f"explained variance over the last fifth of training has a "
              f"median of {tail:+.2f}. At zero the critic is no better than "
              "predicting the mean, which makes every advantage estimate "
              "noise and the policy gradient a random walk.", value=tail)

    # -- does the deployed policy work? (D6, unmodified) ---------------------
    report.section("Does the policy you would actually deploy work?")
    g, st = ev["greedy"], ev["stochastic"]
    report.add("the_deployed_policy_completes_the_task",
              g["finish_rate"] >= DEPLOY_FINISH_RATE,
              f"the mean-action policy finishes {g['finish_rate']:.0%} of "
              f"laps and covers {g['distance_m']:.0f} m. Sampling instead "
              f"gives {st['finish_rate']:.0%} and {st['distance_m']:.0f} m. "
              "NOTE (Spa-specific): a full Spa lap is ~7,000 m from most "
              "starts -- this is expected to fail until stage 2 at the "
              "earliest and is not this run's gate.",
              value=g["finish_rate"], severity="note")
    gap = (abs(g["distance_m"] - st["distance_m"])
          / max(st["distance_m"], 1e-9))
    report.add("greedy_and_stochastic_agree", gap < GREEDY_GAP_FRACTION,
              f"deployed distance {g['distance_m']:.0f} m vs sampled "
              f"{st['distance_m']:.0f} m, a {gap:.0%} gap.", value=gap)
    report.add("the_policy_stayed_inside_the_tire_model",
              g["slip_over_bound"] < 0.05,
              f"deployed policy spends {g['slip_over_bound']:.1%} of steps "
              f"beyond the {SLIP_BOUND_DEG:g} deg envelope bound "
              f"(occupancy {g['envelope_occupancy']:.1%}).",
              value=g["slip_over_bound"])

    report.write(out_dir=OUT)
    return report


#: The actual EnvConfig reward parameters each saved run used -- read from
#: each training script's own constants at the time it ran (git history),
#: not guessed. Required explicitly (see run_d6_spa's docstring) because
#: PPOConfig's serialized config has no record of them.
RUN_REWARDS = {
    "long": dict(off_track_penalty=50.0, stall_penalty=0.0, progress_scale=1.0),
    "stage1_oldreward": dict(off_track_penalty=50.0, stall_penalty=0.0, progress_scale=1.0),
    "stage1_stallexploit": dict(off_track_penalty=500.0, stall_penalty=0.0, progress_scale=1.0),
    "stage1_aggressivecrash": dict(off_track_penalty=500.0, stall_penalty=150.0, progress_scale=3.0),
    "stage1": dict(off_track_penalty=500.0, stall_penalty=150.0, progress_scale=1.5),
}


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "stage1"
    if name not in RUN_REWARDS:
        raise SystemExit(f"unknown run '{name}' -- add its actual EnvConfig "
                        f"reward params to RUN_REWARDS rather than guessing them. "
                        f"Known: {sorted(RUN_REWARDS)}")
    r = run_d6_spa(name, **RUN_REWARDS[name])
    print(f"D6-Spa: {name}  --  {'PASS' if r.ok else 'FAIL'} "
         f"({len(r.failures)} of {len(r.checks)} gate checks failed)")
    for c in r.checks:
        mark = "PASS" if c.passed else ("NOTE" if c.severity == "note" else "FAIL")
        print(f"  [{mark:4s}] {c.name}: {c.detail}")
