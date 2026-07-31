"""TRACKS.md staging step 5 — pilot: is PPO trainable on a real circuit at all,
with the batched env and the proposed hyperparameters, before committing to a
~38.5M-step production run.

This is cross-episode infrastructure, not itself an episode — it lives outside
``experiments/epNN/`` for the same reason ``experiments/power_review/`` does
(see that directory's own docstring). This pilot is Episode 19's technical
prerequisite, scoped in ``TRACKS.md`` step 5 before any training ran.

Deliberately small and fast, not a scaled-down production run: ``n_envs=256``,
``rollout_steps=1024`` (~10% of a Spa lap), ``total_steps=5,000,000`` (~19
updates). The question this answers is "does it train, does the batched path
work end to end, does the reporting stay informative" — not "what lap time does
the policy reach", which is the production run's question.

Answers directly rather than assumed, per TRACKS.md's own recorded caveats:
- ``gamma=0.999`` (the scoping doc's proposed starting point, vs. the old
  ``0.995``): does training stay stable at the higher-variance advantage
  estimate this trades for?
- ``rollout_steps=1024`` against a ~10,000-step lap: does ``return_mean``/
  ``off_track_rate`` stay informative, or does it sit ``nan``/stale for most
  of the run (TRACKS.md's concern, not yet checked against a real run)?
- Wall-clock: env-stepping alone was measured at ~78,559 instance-steps/s for
  ``n_envs=256`` on Spa; this pilot measures the FULL loop (including the PPO
  gradient update, not previously measured for this setup).

    python -m experiments.tracks_pilot.spa_ppo_pilot
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.batched_env import BatchedDrivingEnv
from physics.ppo import PPOConfig, train
from physics.rl_env import EnvConfig
from physics.tracks_data import load_real_track

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

N_ENVS = 256
ROLLOUT_STEPS = 1024
TOTAL_STEPS = 5_000_000
GAMMA = 0.999
SEED = 0
#: One full Spa lap is ~10,000 steps at 15-45 m/s; give real margin so a slow
#: or wandering early-training policy is not truncated before "off track" or
#: "finished" has a chance to fire on its own terms.
MAX_STEPS = 15_000
#: Episode 10's established protocol value — kept, not reinvented, so this
#: pilot is not silently a different task than the production run will be.
ENVELOPE_PENALTY = 0.5
#: Spreads the 256 parallel instances around the lap rather than starting them
#: in lockstep, which is what let step 5's throughput benchmark get away with
#: an all-identical action: with jitter, instances finish laps at different
#: times, which is exactly the asynchronous-completion behaviour this pilot
#: needs to see to answer the "does return_mean stay informative" question.
START_JITTER_M = 300.0


def make_batched_env(n_envs: int, seed: int = SEED) -> BatchedDrivingEnv:
    spa = load_real_track("Spa")
    cfg = EnvConfig(track=spa, max_steps=MAX_STEPS,
                    envelope_penalty=ENVELOPE_PENALTY,
                    start_jitter_m=START_JITTER_M)
    return BatchedDrivingEnv(cfg, n=n_envs, seed=seed)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("TRACKS.md step 5 pilot -- PPO on Spa, batched env")
    print(f"  n_envs={N_ENVS}  rollout_steps={ROLLOUT_STEPS}  "
         f"total_steps={TOTAL_STEPS:,}  gamma={GAMMA}\n")

    cfg = PPOConfig(total_steps=TOTAL_STEPS, n_envs=N_ENVS,
                    rollout_steps=ROLLOUT_STEPS, gamma=GAMMA, seed=SEED)

    def on_update(rec):
        print(f"  update {rec['update']:3d}  steps={rec['steps']:>10,}  "
             f"wall={rec['wall_s']:6.1f}s  "
             f"episodes_finished={rec['episodes_finished']:4d}  "
             f"return_mean={rec['return_mean']:8.2f}  "
             f"off_track_rate={rec['off_track_rate']:.2f}  "
             f"explained_var={rec['explained_variance']:+.2f}  "
             f"approx_kl={rec['approx_kl']:.4f}")

    t0 = time.time()
    res = train(make_batched_env=make_batched_env, cfg=cfg, on_update=on_update)
    wall_s = time.time() - t0

    history = res["history"]
    n_updates = len(history)
    final = history[-1] if history else {}
    steps_per_s = cfg.total_steps / wall_s if wall_s > 0 else float("nan")

    print(f"\n  done: {n_updates} updates, {wall_s:.1f}s wall-clock "
         f"({steps_per_s:,.0f} steps/s, full PPO loop incl. gradient updates)")
    print(f"  first update with episodes_finished > 0: "
         f"{next((h['update'] for h in history if h['episodes_finished'] > 0), None)}")
    print(f"  final: episodes_finished={final.get('episodes_finished')}  "
         f"return_mean={final.get('return_mean')}  "
         f"off_track_rate={final.get('off_track_rate')}")

    torch.save(res["model"].state_dict(), OUT / "pilot_policy.pt")
    (OUT / "pilot_history.json").write_text(json.dumps(history, indent=2) + "\n")
    (OUT / "pilot_config.json").write_text(json.dumps(res["config"], indent=2) + "\n")
    (OUT / "pilot_summary.json").write_text(json.dumps({
        "n_envs": N_ENVS, "rollout_steps": ROLLOUT_STEPS,
        "total_steps": TOTAL_STEPS, "gamma": GAMMA,
        "wall_s": wall_s, "n_updates": n_updates,
        "steps_per_s_full_loop": steps_per_s,
        "env_stepping_steps_per_s_measured_separately": 78559,
        "final": final,
    }, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/pilot_{{policy.pt,history.json,"
         f"config.json,summary.json}}")


if __name__ == "__main__":
    main()
