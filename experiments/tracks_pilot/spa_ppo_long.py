"""TRACKS.md staging step 5 — the long run: does the policy ever get past the
first corner or two on Spa, and does it start completing laps?

The 5M-step pilot (``spa_ppo_pilot.py``) proved the batched-training path
works end to end but stayed entirely inside the "learn not to crash within
the first few hundred metres" regime the whole time (``off_track_rate``
0.94-1.00 throughout, ~200-step average episodes against a ~10,000-step
lap) — nowhere near answering whether the rollout/step-budget choices are
adequate for an actual lap. This run uses the full scoped production budget
(~38.5M steps, "same experience budget as Episode 10" scaled by Spa's
lap-length ratio) to see whether that regime shift ever happens, rather than
guessing from a run too short to show it.

``n_envs=1024`` (not the pilot's 256) — measured faster for the full loop
(52,003 vs 46,999 steps/s), a free speedup, no tradeoff. ``rollout_steps``
held at 1024 — measured NOT to help throughput at 4096, so there is no
throughput reason to move it, and its adequacy for reporting is exactly one
of the things this run's ``off_track_rate`` trend will show directly rather
than guessed.

    python -m experiments.tracks_pilot.spa_ppo_long
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from physics.ppo import PPOConfig, train
from experiments.tracks_pilot.spa_ppo_pilot import make_batched_env

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

N_ENVS = 1024
ROLLOUT_STEPS = 1024
TOTAL_STEPS = 38_500_000
GAMMA = 0.999
SEED = 0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("TRACKS.md step 5 -- long run, PPO on Spa, batched env")
    print(f"  n_envs={N_ENVS}  rollout_steps={ROLLOUT_STEPS}  "
         f"total_steps={TOTAL_STEPS:,}  gamma={GAMMA}\n")

    cfg = PPOConfig(total_steps=TOTAL_STEPS, n_envs=N_ENVS,
                    rollout_steps=ROLLOUT_STEPS, gamma=GAMMA, seed=SEED)

    def on_update(rec):
        print(f"  update {rec['update']:4d}  steps={rec['steps']:>11,}  "
             f"wall={rec['wall_s']:7.1f}s  "
             f"episodes_finished={rec['episodes_finished']:6d}  "
             f"return_mean={rec['return_mean']:8.2f}  "
             f"distance_mean={rec['distance_mean']:8.1f}  "
             f"off_track_rate={rec['off_track_rate']:.2f}  "
             f"explained_var={rec['explained_variance']:+.2f}  "
             f"approx_kl={rec['approx_kl']:.4f}", flush=True)

    t0 = time.time()
    res = train(make_batched_env=make_batched_env, cfg=cfg, on_update=on_update)
    wall_s = time.time() - t0

    history = res["history"]
    final = history[-1] if history else {}
    steps_per_s = cfg.total_steps / wall_s if wall_s > 0 else float("nan")

    print(f"\n  done: {len(history)} updates, {wall_s:.1f}s wall-clock "
         f"({steps_per_s:,.0f} steps/s)")
    print(f"  final: episodes_finished={final.get('episodes_finished')}  "
         f"return_mean={final.get('return_mean')}  "
         f"distance_mean={final.get('distance_mean')}  "
         f"off_track_rate={final.get('off_track_rate')}")

    torch.save(res["model"].state_dict(), OUT / "long_policy.pt")
    (OUT / "long_history.json").write_text(json.dumps(history, indent=2) + "\n")
    (OUT / "long_config.json").write_text(json.dumps(res["config"], indent=2) + "\n")
    (OUT / "long_summary.json").write_text(json.dumps({
        "n_envs": N_ENVS, "rollout_steps": ROLLOUT_STEPS,
        "total_steps": TOTAL_STEPS, "gamma": GAMMA,
        "wall_s": wall_s, "n_updates": len(history),
        "steps_per_s_full_loop": steps_per_s,
        "final": final,
    }, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/long_{{policy.pt,history.json,"
         f"config.json,summary.json}}")


if __name__ == "__main__":
    main()
