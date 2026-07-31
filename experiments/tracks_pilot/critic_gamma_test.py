"""TRACKS.md staging step 5, revised plan item C — single-variable critic test.

The step-back review (item 13) found `explained_variance` collapsed from
0.33-0.72 (the two `gamma=0.999` runs) to ~0.00-0.01 in every run since
`gamma` went to 0.9995 AND the penalties went to their current scale
(`off_track_penalty=500`, `stall_penalty=150`, `progress_scale` 1.5-3.0) --
changed together, which broke this schedule's own pre-registered "one at a
time" rule (item 8) and left two candidate causes confounded: the ~40 s
`gamma=0.9995` horizon against an observation whose curvature preview only
reaches ~55 m (~3-5 s at speed), or the value targets' scale (rare +-500
spikes among ~0.1-scale steps) fighting the value head's own 0.5 grad-norm
clip (F51).

This changes ONLY `gamma` back to 0.999, holding the current reward exactly
(`off_track_penalty=500`, `stall_penalty=150`, `progress_scale=1.5`) fixed.
Two clean outcomes: if EV recovers, the horizon was the poison and 0.999
stays; if EV stays ~0, penalty magnitude is implicated and the next single
change is scaling penalties down or normalising value targets -- not
another coefficient guess.

Budget: ~20M steps, not the full 40M. The reference `gamma=0.999` run
(`long_history.json`) crossed D6's own EV>0.3 gate by update 12-15 of 36
(~13-16M steps) and kept climbing -- this is a diagnostic run, not a
production one, and only needs to show whether EV is clearly recovering,
not converge fully.

    python -m experiments.tracks_pilot.critic_gamma_test
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.batched_env import BatchedDrivingEnv
from physics.ppo import PPOConfig, greedy_policy, train
from physics.rl_env import DrivingEnv, EnvConfig
from physics.tracks_data import load_real_track

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

N_ENVS = 1024
ROLLOUT_STEPS = 1024
TOTAL_STEPS = 20_000_000
GAMMA = 0.999                 # the ONLY change from the current stage-1 run
OFF_TRACK_PENALTY = 500.0
STALL_PENALTY = 150.0
PROGRESS_SCALE = 1.5
SEED = 0
MAX_STEPS = 15_000
ENVELOPE_PENALTY = 0.5
EVAL_EVERY = 2
EVAL_EPISODES = 8
N_SECTIONS = 16


def make_batched_env(n_envs, seed=SEED):
    spa = load_real_track("Spa")
    cfg = EnvConfig(track=spa, max_steps=MAX_STEPS,
                    envelope_penalty=ENVELOPE_PENALTY,
                    off_track_penalty=OFF_TRACK_PENALTY,
                    stall_penalty=STALL_PENALTY,
                    progress_scale=PROGRESS_SCALE,
                    start_jitter_m=spa.length)
    return BatchedDrivingEnv(cfg, n=n_envs, seed=seed)


def make_eval_env():
    spa = load_real_track("Spa")
    return DrivingEnv(EnvConfig(track=spa, max_steps=MAX_STEPS,
                               envelope_penalty=ENVELOPE_PENALTY,
                               off_track_penalty=OFF_TRACK_PENALTY,
                               stall_penalty=STALL_PENALTY,
                               progress_scale=PROGRESS_SCALE,
                               start_jitter_m=spa.length))


def evaluate_per_section(model, n_sections=N_SECTIONS):
    spa = load_real_track("Spa")
    starts = np.linspace(0.0, spa.length, n_sections, endpoint=False)
    policy = greedy_policy(model)
    rows = []
    for s0 in starts:
        env = DrivingEnv(EnvConfig(track=spa, max_steps=MAX_STEPS,
                                   envelope_penalty=ENVELOPE_PENALTY,
                                   off_track_penalty=OFF_TRACK_PENALTY,
                                   stall_penalty=STALL_PENALTY,
                                   progress_scale=PROGRESS_SCALE,
                                   start_jitter_m=0.0))
        env.reset(0)
        env.s = float(s0)
        obs = env.observe()
        while not env.done:
            obs, r, done, info = env.step(policy(obs))
        h = env.history()
        distance = float(h["s"][-1]) - float(s0)
        off_track = bool(abs(h["n"][-1]) > float(spa.half_width_at(h["s"][-1])))
        rows.append({"start_s": float(s0), "distance_travelled": distance,
                    "off_track": off_track, "steps": int(env.steps)})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("TRACKS.md step 5, plan item C -- single-variable critic test")
    print(f"  gamma={GAMMA} (reverted from 0.9995)  off_track_penalty={OFF_TRACK_PENALTY}  "
         f"stall_penalty={STALL_PENALTY}  progress_scale={PROGRESS_SCALE}  "
         f"total_steps={TOTAL_STEPS:,}\n")

    cfg = PPOConfig(total_steps=TOTAL_STEPS, n_envs=N_ENVS,
                    rollout_steps=ROLLOUT_STEPS, gamma=GAMMA, seed=SEED,
                    eval_every=EVAL_EVERY, eval_episodes=EVAL_EPISODES)

    def on_update(rec):
        ev = f"  eval_return={rec['eval_return']:8.2f}" if "eval_return" in rec else ""
        print(f"  update {rec['update']:3d}  steps={rec['steps']:>11,}  "
             f"return_mean={rec['return_mean']:9.2f}  "
             f"off_track_rate={rec['off_track_rate']:.2f}  "
             f"explained_var={rec['explained_variance']:+.3f}  "
             f"approx_kl={rec['approx_kl']:.4f}{ev}", flush=True)

    t0 = time.time()
    res = train(make_batched_env=make_batched_env, cfg=cfg, on_update=on_update,
               make_eval_env=make_eval_env)
    wall_s = time.time() - t0
    history = res["history"]

    n = len(history)
    tail = float(np.median([h["explained_variance"]
                           for h in history[-max(n // 5, 1):]]))
    print(f"\n  done: {n} updates, {wall_s:.1f}s wall-clock "
         f"({cfg.total_steps/wall_s:,.0f} steps/s)")
    print(f"  explained_variance, median over the last fifth: {tail:+.3f} "
         f"({'PASSES' if tail > 0.3 else 'FAILS'} D6's >0.3 gate)")
    if tail > 0.3:
        print("  VERDICT: gamma was the poison. Reverting to 0.999 recovers "
             "the critic under the current penalty scale -- keep 0.999 going "
             "forward, do not also try scaling penalties down.")
    else:
        print("  VERDICT: gamma alone did not fix it. Penalty magnitude is "
             "implicated -- next single change is scaling penalties down or "
             "normalising value targets, not another coefficient guess.")

    sections = evaluate_per_section(res["model"])
    distances = np.array([r["distance_travelled"] for r in sections])
    off_rate = np.mean([r["off_track"] for r in sections])
    print(f"\n  per-section: distance mean={distances.mean():.1f} "
         f"std={distances.std():.1f}  off_track_rate={off_rate:.2f}")

    torch.save(res["model"].state_dict(), OUT / "critic_gamma_test_policy.pt")
    (OUT / "critic_gamma_test_history.json").write_text(
        json.dumps(history, indent=2) + "\n")
    (OUT / "critic_gamma_test_config.json").write_text(
        json.dumps(res["config"], indent=2) + "\n")
    (OUT / "critic_gamma_test_summary.json").write_text(json.dumps({
        "gamma": GAMMA, "off_track_penalty": OFF_TRACK_PENALTY,
        "stall_penalty": STALL_PENALTY, "progress_scale": PROGRESS_SCALE,
        "total_steps": TOTAL_STEPS, "wall_s": wall_s, "n_updates": n,
        "explained_variance_tail_median": tail,
        "passes_d6_gate": bool(tail > 0.3),
        "section_distance_mean": float(distances.mean()),
        "section_distance_std": float(distances.std()),
        "section_off_track_rate": float(off_rate),
        "best_update": res.get("best_update"),
        "best_eval": res.get("best_eval"),
    }, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/critic_gamma_test_"
         f"{{policy.pt,history.json,config.json,summary.json}}")


if __name__ == "__main__":
    main()
