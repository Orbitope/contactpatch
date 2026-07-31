"""TRACKS.md staging step 5 — reward sweep, not another single guess.

Three full 40M-step runs have now each surfaced a real, different reward
defect: `off_track_penalty=50` under-deterred (§4 item 10/11); `=500` alone
taught the policy to coast to a stop (stalling was free); `stall_penalty=150`
+ `progress_scale=3.0` fixed the stall exploit but swung the other way --
`return_mean` climbed to a peak of 2985 specifically BY crashing more often
(`off_track_rate` 0.88-1.00 during the climb), and the per-section eval came
back 100% off-track, same as the very first run. Guessing a fourth
combination at full budget (~20 min) risks the same one-shot miss a fourth
time.

This sweeps `progress_scale` at a REDUCED budget (15M steps, ~1/3 of
production) with `off_track_penalty=500` and `stall_penalty=150` held fixed
-- both already validated as necessary (differential-tested, and the
stalling exploit is specifically what `stall_penalty` closes). The question
this answers is purely "how much progress incentive is too much", not
whether the other two terms are right.

15M steps is a real methodology choice, stated rather than assumed: the
stalling collapse in run 2 was visible by ~15.7M steps, and the aggressive-
crash climb in run 3 began around 22M and peaked at 28M -- so 15M may catch
an EARLY trend (is off_track_rate falling or rising over the run's second
half) without the full magnitude of either degenerate pattern. Reported as
a trend, not a verdict, for exactly that reason.

    python -m experiments.tracks_pilot.reward_sweep
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
TOTAL_STEPS = 15_000_000
GAMMA = 0.9995
OFF_TRACK_PENALTY = 500.0
STALL_PENALTY = 150.0
SEED = 0
MAX_STEPS = 15_000
ENVELOPE_PENALTY = 0.5
EVAL_EVERY = 2
EVAL_EPISODES = 8
N_SECTIONS = 16  # fewer than stage1's 24 -- this is a screen, not the gate

PROGRESS_SCALES = (1.0, 1.5, 2.0, 2.5, 3.0)


def make_batched_env(n_envs, progress_scale, seed=SEED):
    spa = load_real_track("Spa")
    cfg = EnvConfig(track=spa, max_steps=MAX_STEPS,
                    envelope_penalty=ENVELOPE_PENALTY,
                    off_track_penalty=OFF_TRACK_PENALTY,
                    stall_penalty=STALL_PENALTY,
                    progress_scale=progress_scale,
                    start_jitter_m=spa.length)
    return BatchedDrivingEnv(cfg, n=n_envs, seed=seed)


def make_eval_env(progress_scale):
    spa = load_real_track("Spa")
    return DrivingEnv(EnvConfig(track=spa, max_steps=MAX_STEPS,
                               envelope_penalty=ENVELOPE_PENALTY,
                               off_track_penalty=OFF_TRACK_PENALTY,
                               stall_penalty=STALL_PENALTY,
                               progress_scale=progress_scale,
                               start_jitter_m=spa.length))


def evaluate_per_section(model, progress_scale, n_sections=N_SECTIONS):
    spa = load_real_track("Spa")
    starts = np.linspace(0.0, spa.length, n_sections, endpoint=False)
    policy = greedy_policy(model)
    rows = []
    for s0 in starts:
        env = DrivingEnv(EnvConfig(track=spa, max_steps=MAX_STEPS,
                                   envelope_penalty=ENVELOPE_PENALTY,
                                   off_track_penalty=OFF_TRACK_PENALTY,
                                   stall_penalty=STALL_PENALTY,
                                   progress_scale=progress_scale,
                                   start_jitter_m=0.0))
        env.reset(0)
        env.s = float(s0)
        obs = env.observe()
        while not env.done:
            obs, r, done, info = env.step(policy(obs))
        h = env.history()
        distance = float(h["s"][-1]) - float(s0)
        off_track = bool(abs(h["n"][-1]) > float(spa.half_width_at(h["s"][-1])))
        stalled = bool(info["stalled"])
        rows.append({"start_s": float(s0), "distance_travelled": distance,
                    "off_track": off_track, "stalled": stalled,
                    "steps": int(env.steps)})
    return rows


def run_one(progress_scale):
    print(f"\n=== progress_scale={progress_scale} ===", flush=True)
    cfg = PPOConfig(total_steps=TOTAL_STEPS, n_envs=N_ENVS,
                    rollout_steps=ROLLOUT_STEPS, gamma=GAMMA, seed=SEED,
                    eval_every=EVAL_EVERY, eval_episodes=EVAL_EPISODES)

    def on_update(rec):
        ev = f"  eval_return={rec['eval_return']:8.2f}" if "eval_return" in rec else ""
        print(f"  update {rec['update']:3d}  off_track_rate={rec['off_track_rate']:.2f}  "
             f"return_mean={rec['return_mean']:9.2f}{ev}", flush=True)

    t0 = time.time()
    res = train(make_batched_env=lambda n: make_batched_env(n, progress_scale),
               cfg=cfg, on_update=on_update,
               make_eval_env=lambda: make_eval_env(progress_scale))
    wall_s = time.time() - t0
    history = res["history"]

    # Trend, not verdict (see module docstring): compare the first half's
    # mean off_track_rate against the second half's.
    n = len(history)
    first_half = np.mean([h["off_track_rate"] for h in history[:n // 2]])
    second_half = np.mean([h["off_track_rate"] for h in history[n // 2:]])

    sections = evaluate_per_section(res["model"], progress_scale)
    distances = np.array([r["distance_travelled"] for r in sections])
    off_rate = np.mean([r["off_track"] for r in sections])
    stall_rate = np.mean([r["stalled"] for r in sections])

    print(f"  done: {wall_s:.1f}s, {n} updates. off_track_rate first-half="
         f"{first_half:.2f} second-half={second_half:.2f} "
         f"({'RISING -- trending toward more crashing' if second_half > first_half + 0.05 else 'falling or flat'})")
    print(f"  per-section: distance mean={distances.mean():.1f} std={distances.std():.1f}  "
         f"off_track_rate={off_rate:.2f}  stall_rate={stall_rate:.2f}")

    return {
        "progress_scale": progress_scale, "wall_s": wall_s, "n_updates": n,
        "off_track_rate_first_half": float(first_half),
        "off_track_rate_second_half": float(second_half),
        "section_distance_mean": float(distances.mean()),
        "section_distance_std": float(distances.std()),
        "section_off_track_rate": float(off_rate),
        "section_stall_rate": float(stall_rate),
        "best_update": res.get("best_update"),
        "best_eval_return": res.get("best_eval", {}).get("eval_return"),
        "final_return_mean": history[-1]["return_mean"] if history else None,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("TRACKS.md step 5 -- reward sweep over progress_scale")
    print(f"  fixed: off_track_penalty={OFF_TRACK_PENALTY} stall_penalty={STALL_PENALTY} "
         f"gamma={GAMMA} total_steps={TOTAL_STEPS:,}\n")

    results = [run_one(ps) for ps in PROGRESS_SCALES]

    print("\n\n=== SWEEP SUMMARY ===")
    print(f"{'progress_scale':>14}  {'dist_mean':>10}  {'dist_std':>9}  "
         f"{'off_track':>10}  {'stall':>6}  {'otr_1st_half':>13}  {'otr_2nd_half':>13}")
    for r in results:
        print(f"{r['progress_scale']:>14.1f}  {r['section_distance_mean']:>10.1f}  "
             f"{r['section_distance_std']:>9.1f}  {r['section_off_track_rate']:>10.2f}  "
             f"{r['section_stall_rate']:>6.2f}  {r['off_track_rate_first_half']:>13.2f}  "
             f"{r['off_track_rate_second_half']:>13.2f}")

    (OUT / "reward_sweep_results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/reward_sweep_results.json")


if __name__ == "__main__":
    main()
