"""TRACKS.md staging step 5, revised plan item C follow-up (1) — reduce the
reward's own scale, the last of the three candidate fixes for the dead critic.

Both `fix (b)` candidates failed cleanly: reverting `gamma` to 0.999
(``critic_gamma_test.py``) and unclipping the value head entirely
(``critic_value_clip_test.py``) both left `explained_variance` at ~0.000 for
19 straight updates, ruling out the horizon and the grad-norm clip as the
bottleneck. The critic's difficulty tracking these value targets looks like
a genuine scale/representation problem, not a step-size one.

This tries the remaining candidate: bring `off_track_penalty` down from 500
toward a magnitude closer to what the critic demonstrably COULD track (the
original `off_track_penalty=50` config had explained_variance 0.33-0.72).
`gamma` stays at 0.9995 -- item 11's original reasoning was that the
explicit penalty and gamma's own implicit deterrent (lost future reward,
scaling with how much of the lap remains) were meant to reinforce each
other, not that either alone had to carry the whole weight. Stacking a
large explicit penalty (500) on top of an already-strengthened implicit one
is what this run tests moving away from.

`off_track_penalty=200`: meaningfully below 500, still comfortably above
`stall_penalty=150` (preserving "giving up reads as better than crashing
while pushing", the ordering item 11 explicitly wanted), and 4x the
original under-deterring 50. `stall_penalty` and `progress_scale` held at
their current values (150, 1.5) -- one variable at a time.
`value_max_grad_norm` reverted to the default (0.5, i.e. omitted) since
item 17 found loosening it did nothing; no reason to carry an
unhelpful change into this test.

    python -m experiments.tracks_pilot.critic_penalty_test
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
GAMMA = 0.9995                # unchanged
OFF_TRACK_PENALTY = 200.0     # the ONLY change: 500 -> 200
STALL_PENALTY = 150.0         # unchanged (stays below off_track_penalty)
PROGRESS_SCALE = 1.5          # unchanged
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
    print("TRACKS.md step 5, plan item C follow-up -- off_track_penalty reduction test")
    print(f"  gamma={GAMMA}  off_track_penalty={OFF_TRACK_PENALTY} (down from 500)  "
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
        print("  VERDICT: reducing off_track_penalty recovers the critic. "
             "Reward scale, not gamma or the grad-norm clip, was the cause "
             "all along -- off_track_penalty=200 (or a nearby value) is the "
             "working point, not 500.")
    else:
        print("  VERDICT: still dead even at off_track_penalty=200. Either "
             "the value target scale needs to come down further, or the "
             "problem is not purely about penalty magnitude -- worth "
             "checking whether stall_penalty or progress_scale are also "
             "contributing before assuming off_track_penalty alone "
             "explains it.")

    sections = evaluate_per_section(res["model"])
    distances = np.array([r["distance_travelled"] for r in sections])
    off_rate = np.mean([r["off_track"] for r in sections])
    print(f"\n  per-section: distance mean={distances.mean():.1f} "
         f"std={distances.std():.1f}  off_track_rate={off_rate:.2f}")

    torch.save(res["model"].state_dict(), OUT / "critic_penalty_test_policy.pt")
    (OUT / "critic_penalty_test_history.json").write_text(
        json.dumps(history, indent=2) + "\n")
    (OUT / "critic_penalty_test_config.json").write_text(
        json.dumps(res["config"], indent=2) + "\n")
    (OUT / "critic_penalty_test_summary.json").write_text(json.dumps({
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
    print(f"\n  wrote {OUT.relative_to(ROOT)}/critic_penalty_test_"
         f"{{policy.pt,history.json,config.json,summary.json}}")


if __name__ == "__main__":
    main()
