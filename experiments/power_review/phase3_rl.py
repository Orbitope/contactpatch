"""POWER-REVIEW Phase 3 — Season 3 RL at 2x power.

Phases 0-2 are done. This is the last one, and it is deliberately cheapest-last:
RL training is the only place in the review where the full 1x/1.5x/2x curve is
not affordable, so it runs at **2x only** and leans on Phase 1/2's curves for
shape (POWER-REVIEW §4, Phase 3).

**Lives here, not in `experiments/ep10/`, for the same reason phase1 and phase2
do.** Episode 10 writes its policy to a fixed `out/policy.pt`; retraining in
place would destroy the published 1x artefact that every Episode 10 and 11
number rests on. The 1x results stay exactly where they are and this writes
alongside them.

**What it answers, both pre-registered in POWER-REVIEW before it was run:**

1. **The RL-vs-OC trend cross-check at the new power.** Episode 10's claim is
   that a design-conditioned policy ranks designs the same way the optimal-
   control solver does. Rank ordering is what this project is allowed to claim
   across methods (rule 6), so the question is whether the *ordering* survives
   at 2x, not whether the seconds match.

2. **F98's fragility ordering.** At 1x, the quickest design (47% front) is the
   only one that ever fails — 10/108 rollouts, 9.3%, with every other design at
   0/119. **Pre-registered expectation: the gap should WIDEN with power**, since
   more power means more rear-axle demand on corner exit. If it instead closes,
   F98 gains a power conditional — and that is a finding, not a failure.

**Power enters through `EnvConfig.drive_max`,** which had to be added for this
(it was a module constant, so Episodes 9-11 could only ever be measured at 1x).
Like `BRAKE_MAX` it scales the ACTION, so a 1x policy cannot simply be evaluated
at 2x — it would be asked for forces it never learned to command. Hence a
retrain rather than a re-evaluation.

    python -m experiments.power_review.phase3_rl [--quick]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

from physics.ppo import ActorCritic, PPOConfig, greedy_policy, train
from physics.rl_env import DRIVE_MAX, DrivingEnv, EnvConfig

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "power_review" / "out"

#: Matches Episode 10 exactly, so the only difference is power.
DESIGN_KEYS = ("front_mass_fraction",)
DESIGN_RANGES = {"front_mass_fraction": (0.40, 0.65)}
ENVELOPE_PENALTY = 0.5
SEED = 0

#: 2x only — see the module docstring. `phase1_sweep` uses the same
#: `DRIVE_MAX * mult` construction.
POWER_MULT = 2.0

#: **The unbatched path, and POWER-REVIEW's plan for this was wrong.** The
#: review says "retrain the design-conditioned policy with the batched env
#: (29x throughput makes this an overnight job, not a week)". It cannot:
#: `BatchedDrivingEnv._reject_unsupported` raises on `design_keys` outright —
#: it shares one car across all instances, so per-instance design conditioning
#: is exactly the thing it does not do.
#:
#: That turns out not to matter. The single-instance env runs ~3,500 steps/s
#: with no torque vectoring, so Episode 10's own 5M-step budget is ~25 minutes,
#: not an overnight job. The batched env was never needed here; the review
#: assumed a capability rather than checking for one.
TOTAL_STEPS = 5_000_000
N_ENVS, ROLLOUT = 8, 512

#: F98's designs and conditions, unchanged so the comparison is like-for-like.
EVAL_FRACTIONS = (0.47, 0.54, 0.61, 0.65)
N_ROLLOUTS = 60
STEER_NOISE_ATTENTIVE, STEER_NOISE_DISTRACTED = 0.01, 0.03
GRIP_SPREAD = 0.20


def _cfg(**over):
    base = dict(design_keys=DESIGN_KEYS, design_ranges=DESIGN_RANGES,
                envelope_penalty=ENVELOPE_PENALTY,
                drive_max=DRIVE_MAX * POWER_MULT)
    base.update(over)
    return EnvConfig(**base)


def _rollout(env, pol, seed):
    obs = env.reset(seed)
    total = 0.0
    while not env.done:
        obs, r, _, info = env.step(pol(obs))
        total += r
    h = env.history()
    return {
        "return": total,
        "distance": float(getattr(env, "_dist_since_reset", np.nan)),
        "finished": bool(info["finished"]),
        "off_track": bool(info["off_track"]),
        "worst_slip_deg": float(np.max(h["alpha_max_deg"])),
        "envelope_occupancy": float(np.mean(h["envelope_violation"])),
    }


def main() -> int:
    quick = "--quick" in sys.argv
    steps = 200_000 if quick else TOTAL_STEPS
    n_roll = 6 if quick else N_ROLLOUTS
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"POWER-REVIEW Phase 3 — Season 3 RL at {POWER_MULT:g}x power")
    print(f"  drive_max {DRIVE_MAX:.0f} -> {DRIVE_MAX*POWER_MULT:.0f} N")
    print(f"  {steps:,} steps, design conditioned on front_mass_fraction "
         f"{DESIGN_RANGES['front_mass_fraction']}\n")

    cfg = PPOConfig(total_steps=steps, n_envs=N_ENVS, rollout_steps=ROLLOUT,
                    epochs=10, seed=SEED)
    t0 = time.time()
    res = train(make_env=lambda i: DrivingEnv(_cfg(), seed=SEED + i), cfg=cfg)
    wall = time.time() - t0
    h = res["history"]
    ev = float(np.median([r["explained_variance"]
                          for r in h[-max(len(h)//5, 1):]]))
    print(f"  trained: {len(h)} updates, {wall/60:.1f} min, EV tail {ev:+.3f}")
    if ev <= 0.3:
        print(f"  *** EV {ev:+.3f} FAILS D6's gate (>0.3). Everything below is "
             f"measured on a policy whose critic did not learn.")

    pol = greedy_policy(res["model"])
    rows = {}
    print(f"\n  {'design':>8} {'condition':>12} {'fail':>8} {'rate':>7} "
         f"{'worst slip':>11} {'occupancy':>10}")
    for ff in EVAL_FRACTIONS:
        for cond, sn in (("attentive", STEER_NOISE_ATTENTIVE),
                         ("distracted", STEER_NOISE_DISTRACTED)):
            runs = []
            for k in range(n_roll):
                env = DrivingEnv(_cfg(start_jitter_m=0.0, steer_noise=sn,
                                      grip_spread=GRIP_SPREAD), seed=k)
                env.set_design(front_mass_fraction=ff)
                runs.append(_rollout(env, pol, seed=k))
            fails = sum(1 for r in runs if r["off_track"])
            slip = max(r["worst_slip_deg"] for r in runs)
            occ = float(np.mean([r["envelope_occupancy"] for r in runs]))
            rows[f"{ff:.2f}/{cond}"] = {
                "design": ff, "condition": cond, "n": len(runs),
                "failures": fails, "failure_rate": fails / len(runs),
                "worst_slip_deg": slip, "envelope_occupancy": occ,
                "mean_distance": float(np.mean([r["distance"] for r in runs])),
            }
            print(f"  {ff:>8.2f} {cond:>12} {fails:>4}/{len(runs):<3} "
                 f"{100*fails/len(runs):>6.1f}% {slip:>10.1f}° {occ:>10.4f}")

    torch.save(res["model"].state_dict(), OUT / "phase3_policy_2x.pt")
    (OUT / "phase3_history.json").write_text(json.dumps(h, indent=2) + "\n")
    (OUT / "phase3_results.json").write_text(json.dumps({
        "power_mult": POWER_MULT, "drive_max_n": DRIVE_MAX * POWER_MULT,
        "total_steps": steps, "n_envs": N_ENVS, "wall_s": wall,
        "explained_variance_tail": ev, "passes_d6_ev_gate": bool(ev > 0.3),
        "n_rollouts_per_cell": n_roll, "cells": rows,
        "note": "POWER-REVIEW Phase 3. 1x comparison is experiments/ep11/"
                "out/results.json (F98). Rank ordering only across power "
                "levels -- rule 6.",
    }, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/phase3_*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
