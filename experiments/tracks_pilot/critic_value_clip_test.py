"""TRACKS.md staging step 5, revised plan item C follow-up (2) — fix the
value network's ability to track the current reward scale, reward untouched.

Item C (``critic_gamma_test.py``) isolated the dead critic to penalty
magnitude, not the `gamma=0.9995` horizon: reverting gamma alone left
`explained_variance` at -0.001 for 19 straight updates, no recovery at all.

F51's own fix already separates the actor's and critic's gradient clips SO
ONE CANNOT THROTTLE THE OTHER — but a single FIXED cap (0.5) still throttles
the critic on its OWN once return magnitude changes, which is exactly what
happened: F51's own case had returns of order 40 (value loss ~1600, raw
grad norm ~150, clipped by 0.5 to an effective 0.0033x scale); the current
penalties (`off_track_penalty=500`, `stall_penalty=150`) push typical
returns into the hundreds-to-low-thousands, a proportionally larger raw
gradient the SAME fixed clip would throttle even harder.

This is the cleaner of the two candidate fixes to try first (reward left
completely alone -- gamma stays at the CURRENT 0.9995, penalties stay at
their CURRENT values): `value_max_grad_norm` set effectively unbounded
(1e6, i.e. "does removing the throttle recover the critic at all", not yet
a tuned finite value) via `physics/ppo.py`'s new, D-A `value_max_grad_norm`
field. If EV recovers, the mechanism is confirmed and a properly-tuned
finite clip can replace this unbounded diagnostic value; if EV still does
not move, the clip was never the bottleneck and value-target normalisation
(the other candidate from item 16) is next.

    python -m experiments.tracks_pilot.critic_value_clip_test
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
GAMMA = 0.9995                # unchanged from the current stage-1 run
OFF_TRACK_PENALTY = 500.0     # unchanged
STALL_PENALTY = 150.0         # unchanged
PROGRESS_SCALE = 1.5          # unchanged
VALUE_MAX_GRAD_NORM = 1e6     # the ONLY change: effectively unclip the critic
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
    print("TRACKS.md step 5, plan item C follow-up -- value grad-norm clip test")
    print(f"  gamma={GAMMA}  off_track_penalty={OFF_TRACK_PENALTY}  "
         f"stall_penalty={STALL_PENALTY}  progress_scale={PROGRESS_SCALE}  "
         f"value_max_grad_norm={VALUE_MAX_GRAD_NORM:g} (vs default 0.5)  "
         f"total_steps={TOTAL_STEPS:,}\n")

    cfg = PPOConfig(total_steps=TOTAL_STEPS, n_envs=N_ENVS,
                    rollout_steps=ROLLOUT_STEPS, gamma=GAMMA, seed=SEED,
                    eval_every=EVAL_EVERY, eval_episodes=EVAL_EPISODES,
                    value_max_grad_norm=VALUE_MAX_GRAD_NORM)

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
        print("  VERDICT: the value grad-norm clip was the bottleneck. "
             "Removing it recovers the critic under the current reward "
             "scale -- next step is finding a properly-tuned finite value "
             "(1e6 here is a diagnostic, not a production setting).")
    else:
        print("  VERDICT: unclipping the value head did not fix it either. "
             "The clip was not the bottleneck (or not the only one) -- "
             "value-target normalisation is the remaining candidate, or "
             "the reward scale itself needs to come down (item 16's other "
             "option).")

    sections = evaluate_per_section(res["model"])
    distances = np.array([r["distance_travelled"] for r in sections])
    off_rate = np.mean([r["off_track"] for r in sections])
    print(f"\n  per-section: distance mean={distances.mean():.1f} "
         f"std={distances.std():.1f}  off_track_rate={off_rate:.2f}")

    torch.save(res["model"].state_dict(), OUT / "critic_value_clip_test_policy.pt")
    (OUT / "critic_value_clip_test_history.json").write_text(
        json.dumps(history, indent=2) + "\n")
    (OUT / "critic_value_clip_test_config.json").write_text(
        json.dumps(res["config"], indent=2) + "\n")
    (OUT / "critic_value_clip_test_summary.json").write_text(json.dumps({
        "gamma": GAMMA, "off_track_penalty": OFF_TRACK_PENALTY,
        "stall_penalty": STALL_PENALTY, "progress_scale": PROGRESS_SCALE,
        "value_max_grad_norm": VALUE_MAX_GRAD_NORM,
        "total_steps": TOTAL_STEPS, "wall_s": wall_s, "n_updates": n,
        "explained_variance_tail_median": tail,
        "passes_d6_gate": bool(tail > 0.3),
        "section_distance_mean": float(distances.mean()),
        "section_distance_std": float(distances.std()),
        "section_off_track_rate": float(off_rate),
        "best_update": res.get("best_update"),
        "best_eval": res.get("best_eval"),
    }, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/critic_value_clip_test_"
         f"{{policy.pt,history.json,config.json,summary.json}}")


if __name__ == "__main__":
    main()
