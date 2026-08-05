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
#: **Raised from Episode 10's 0.5, and a cross-track term added.** The first
#: Phase 3 run produced a fragility table that was not quotable: 0.47 and 0.54
#: "succeeded" at 12.1-16.7 deg of slip, outside the 12 deg tyre fit, and
#: 0.61's 75% failure rate turned out to be a steering bug — all 48 failures
#: at s = 74-76 m (sd 0.5 m) at 1.6 deg slip, i.e. off the road on the ENTRY
#: STRAIGHT with the tyres idle (F117).
#:
#: 6.0 is F107's measured value, the weakest that put every section inside the
#: fit. 2.0 is F110's, the term that took a policy from 40.7% to 100% lap
#: completion and the most universal term in the racing-RL literature (F105).
#: **Back to Episode 10's own values, and both "improvements" reverted.**
#:
#: `cross_track_penalty` was added to fix F117's 0.61 steering spike. That
#: spike does not exist in Ep10's original policy -- measured, 0/30 failures
#: at 0.61 with 5.7 deg median slip -- so it was a property of one bad
#: training run, not of the environment, and the term was a fix for nothing.
#:
#: Worse, it actively harms this task. Evaluated in an IDENTICAL clean env,
#: the cross-track-trained policy slides 9.6-10.5 deg where Ep10's original
#: slides 5.7-6.0: **70% more, same track, no noise.** Forced toward the
#: centreline the policy cannot use the racing line, so its effective corner
#: radius is the track's own -- tighter -- and it corners harder to hold the
#: line. Evans saw the same thing ("network planners avoid the edges of the
#: track, which causes them to take turns more sharply"); this measures it.
#:
#: The lesson generalises: a cross-track term rescues a policy that CANNOT
#: hold a line (F110, on Spa) and penalises one that can.
#:
#: envelope_penalty likewise returns to 0.5. At 6.0 the run produced 35-43
#: deg peaks at 4-5.8% occupancy -- worse than the 0.5 it replaced.
ENVELOPE_PENALTY = 0.5
CROSS_TRACK_PENALTY = 0.0
SEED = 0

#: 2x only — see the module docstring. `phase1_sweep` uses the same
#: `DRIVE_MAX * mult` construction.
#: Set per run: this now sweeps BOTH levels, because the reward above differs
#: from Episode 10's and F98's published 1x numbers were measured under the
#: old one. Comparing the new 2x against the old 1x would confound power with
#: reward — precisely the confound the whole review exists to avoid.
#: **Defaults to the BASELINE, not the treatment.** `main()` sets this per
#: leg, so the runs are unaffected either way -- but the module default is
#: what any other code gets, and it was 2.0. Importing `phase3_rl` and calling
#: `_cfg()` to re-score a checkpoint then silently built a DOUBLE-POWER car:
#: Episode 10's own committed policy measured 26-28 deg of slip and 100%
#: off-track that way, which reads as "the published policy is terrible"
#: rather than "you are driving the wrong car". Cost an hour of
#: re-verification. A default that reproduces the baseline is the D-A pattern
#: this project uses everywhere else, and 2.0 broke it.
POWER_MULT = 1.0

#: **The unbatched path, and POWER-REVIEW's plan for this was wrong.** The
#: review says "retrain the design-conditioned policy with the batched env
#: (29x throughput makes this an overnight job, not a week)". It cannot:
#: `BatchedDrivingEnv._reject_unsupported` raises on `design_keys` outright —
#: it shares one car across all instances, so per-instance design conditioning
#: is exactly the thing it does not do.
#:
#: That turns out not to matter, though the sizing did: **measured** at
#: ~844 steps/s (design-conditioned) and ~854 (plain), so Episode 10's 5M-step
#: budget is ~99 minutes, not the ~25 an earlier note here claimed from
#: `batched_env`'s quoted 3,492 steps/s. Two corrections worth keeping: that
#: docstring figure does not describe this configuration, and **design
#: conditioning is NOT the cost** — conditioned and plain run at the same
#: rate, so an earlier guess that per-episode backend rebuilds were the
#: slowdown was simply wrong. Still an afternoon rather than a week, which is
#: all the review needed; the batched env was never required here.
TOTAL_STEPS = 5_000_000
N_ENVS, ROLLOUT = 8, 512

#: F98's designs and conditions, unchanged so the comparison is like-for-like.
#: **0.40 included, and its absence invalidated the first two attempts.**
#: Episode 11's 1x fragility lives almost entirely at 0.40 front -- 90-100%
#: failure -- with 0.47 at ~13% and everything else 0%. Sweeping
#: (0.47, 0.54, 0.61, 0.65) omitted the design carrying the effect, so there
#: was nothing for a power conditional to be measured ON.
EVAL_FRACTIONS = (0.40, 0.47, 0.54, 0.61, 0.65)
N_ROLLOUTS = 60
STEER_NOISE_ATTENTIVE, STEER_NOISE_DISTRACTED = 0.01, 0.03
GRIP_SPREAD = 0.20


#: **Episode 10 trains with 10 m of start jitter and this file did not.**
#: Attempt 4 matched Episode 10 on reward, design range, PPO budget and seed,
#: differed ONLY here, and produced a policy at 169 deg of slip with 0/60
#: failures at every design -- against Episode 10's 5.5-7.1 deg and its 90%
#: failure at 0.40. Without jitter every episode starts at the same point, so
#: the policy sees one trajectory distribution and a degenerate spinning
#: solution survives, because it only ever has to work from that one start.
#: A full field-by-field diff of the two EnvConfigs is how this was found;
#: reading the two files side by side had already missed it three times.
START_JITTER_M = 10.0


def _cfg(**over):
    base = dict(design_keys=DESIGN_KEYS, design_ranges=DESIGN_RANGES,
                envelope_penalty=ENVELOPE_PENALTY,
                cross_track_penalty=CROSS_TRACK_PENALTY,
                start_jitter_m=START_JITTER_M,
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


def main(power_mult: float = POWER_MULT, seed: int | None = None) -> int:
    global POWER_MULT, SEED
    POWER_MULT = power_mult
    # Rule 5 wants >=3 seeds and F123 makes that the blocking question:
    # one seed cannot distinguish 'the corrected environment trains a
    # robust policy' from 'this seed happened to'. Settable here so the
    # seeds do not need a file edit between runs, which is when
    # transcription errors get made.
    if seed is not None:
        SEED = int(seed)
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
    def _progress(rec):
        # Omitted on the first run, which left 99 minutes with no way to see
        # EV climbing or catch a dead critic before the end.
        if rec["update"] % 25 == 0:
            print(f"    upd {rec['update']:4d} steps={rec['steps']:>10,} "
                 f"EV={rec['explained_variance']:+.3f} "
                 f"ret={rec['return_mean']:8.1f} "
                 f"off={rec['off_track_rate']:.2f}", flush=True)

    t0 = time.time()
    res = train(make_env=lambda i: DrivingEnv(_cfg(), seed=SEED + i), cfg=cfg,
                on_update=_progress)
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

    # `_quick` in the name, always. A 200k-step smoke run once wrote
    # `phase3_1x_results.json` and sat there looking exactly like a result --
    # 3 minutes of wall time and 6 rollouts per cell, indistinguishable from
    # the real thing at a glance. A cleanup `rm` that should have removed it
    # silently did nothing (zsh aborts the whole command when any glob in it
    # matches nothing), so it survived to be read as Phase 3's 1x answer.
    tag = (f"phase3_{POWER_MULT:g}x"
           + (f"_s{SEED}" if SEED != 0 else "")     # seed 0 keeps the original name
           + ("_quick" if quick else ""))
    # --- baseline reproduction gate ------------------------------------
    # NOTE ON WHAT THIS DOES AND DOES NOT CHECK. It compares the retrained
    # policy's FRAGILITY STRUCTURE against Episode 10's, measured by scoring
    # Ep10's committed policy under CURRENT code (2026-08-04, 30 rollouts per
    # design, F118). It deliberately does not compare training histories:
    # Ep10's `history.json` is not reproducible under current code and should
    # not be expected to be. F110 changed termination from absolute `s` to
    # distance travelled, so with `start_jitter_m=10.0` an episode now runs a
    # full 393 m instead of `393 - s0`. Training is otherwise bit-reproducible
    # at a fixed seed (verified: two identical 120k runs agree to every
    # decimal), so a history divergence means the ENVIRONMENT changed, which
    # it did, on purpose.
    # TWO SEPARATE QUESTIONS, reported separately. The first version asked
    # only the second and voided the run on it, which conflated two failures
    # that need different responses:
    #
    #   A. "Is this a driver at all?"  -- rule 4 and D6. Attempt 4 failed this
    #      at 169.1 deg of slip while spinning, and no number from such a run
    #      is usable for anything.
    #   B. "Does it reproduce Episode 10?" -- the bands below. Attempt 5 failed
    #      this while being clean: 10.0 deg worst slip, occupancy 0.0000,
    #      EV +0.720.
    #
    # **This split was made after a run failed B while passing A, which is the
    # dangerous direction to change a criterion in.** The justification is the
    # logic, not the outcome: the original consequence -- "treat both legs as
    # void" -- does not follow. The 1x and 2x legs are trained under identical
    # configurations, so the comparison BETWEEN them is unaffected by whether
    # either matches a policy trained under an older environment. What a B
    # failure invalidates is tying either leg back to F98's published numbers,
    # and that is exactly what is now reported. No threshold was loosened; A
    # is new and strictly additional.
    if abs(POWER_MULT - 1.0) < 1e-9:
        worst = max(v["worst_slip_deg"] for v in rows.values())
        occ = max(v["envelope_occupancy"] for v in rows.values())
        # DISTANCE FIRST. The 2x leg passed every other part of this check
        # while travelling 20 m of a 393 m track: a car that does not move has
        # low slip, zero envelope occupancy, and a critic that trivially
        # predicts a constant return, so "0/60 failures" meant "never got
        # anywhere". Slip and occupancy are constraints on HOW it drives and
        # say nothing about WHETHER it does. This is D6's
        # `the_deployed_policy_completes_the_task`, which this gate should
        # have carried from the start (F61: Episode 9 was written around an
        # 88% sampled finish rate whose deployed figure was 0%).
        # MAX across designs, not min. The question here is whether the
        # policy can drive AT ALL; whether it drives every design is what the
        # fragility table below measures, and a design that legitimately fails
        # 20% of the time drags a min-based check under the threshold for the
        # right reason. A crawler's best design still only reaches ~23 m.
        # HALF the track, not 90%. The discriminator is enormous -- the
        # crawling 2x leg reached 22.7 m (5.8%), a real driver reaches 393 m
        # (100%) -- so the threshold only has to land somewhere in between,
        # and it should sit far from both. At 90% it misfired on seed 1, whose
        # best design averages 353.2 m against a 353.7 m bar: that policy
        # drives the track and fails ~18% of the time, which drags the MEAN
        # down and is a fragility result, not a failure to move. How often it
        # fails is check B's business and the table's; check A only asks
        # whether the thing drives.
        L = _cfg().track.length
        dist = max(v["mean_distance"] for v in rows.values())
        crawls = dist < 0.5 * L
        broken = crawls or worst > 12.0 or occ > 0.0 or ev <= 0.3
        print(f"\n  A. Is it a driver?  best mean distance {dist:.1f} m of "
              f"{L:.0f} ({100*dist/L:.0f}%), worst slip {worst:.1f}° "
              f"(limit 12), occupancy {occ:.4f}, EV tail {ev:+.3f}")
        if crawls:
            print(f"       *** IT DOES NOT DRIVE. Every failure rate below is "
                  f"an artefact of not moving.")
        print(f"       -> {'NO — nothing here is usable' if broken else 'yes'}")

        exp = {0.40: (0.70, 1.00), 0.47: (0.02, 0.35),
               0.54: (0.0, 0.10), 0.61: (0.0, 0.10), 0.65: (0.0, 0.10)}
        bad = []
        for v in rows.values():
            if v["condition"] != "attentive":
                continue
            lo, hi = exp.get(round(v["design"], 2), (0.0, 1.0))
            if not (lo <= v["failure_rate"] <= hi):
                bad.append(f"{v['design']:.2f}: {v['failure_rate']:.0%} "
                          f"outside the expected {lo:.0%}-{hi:.0%}")
        if bad:
            print("  B. Reproduces Episode 10?  NO:")
            for b in bad:
                print(f"        {b}")
            if broken:
                print("      Both A and B failed. The run is void.")
            else:
                print("      B alone. The 1x-vs-2x comparison stands — both "
                      "legs share a configuration — but NEITHER leg may be "
                      "tied back to F98's published 1x numbers, and the "
                      "difference from Episode 10 needs >=3 seeds (rule 5) "
                      "before it is anything at all.")
        else:
            print("  B. Reproduces Episode 10?  yes — committed fragility "
                  "structure recovered.")

    torch.save(res["model"].state_dict(), OUT / f"{tag}_policy.pt")
    (OUT / f"{tag}_history.json").write_text(json.dumps(h, indent=2) + "\n")
    (OUT / f"{tag}_results.json").write_text(json.dumps({
        "power_mult": POWER_MULT, "drive_max_n": DRIVE_MAX * POWER_MULT,
        "total_steps": steps, "n_envs": N_ENVS, "seed": SEED, "wall_s": wall,
        "explained_variance_tail": ev, "passes_d6_ev_gate": bool(ev > 0.3),
        "n_rollouts_per_cell": n_roll, "cells": rows,
        "note": "POWER-REVIEW Phase 3. 1x comparison is experiments/ep11/"
                "out/results.json (F98). Rank ordering only across power "
                "levels -- rule 6.",
    }, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/{tag}_*")
    return 0


if __name__ == "__main__":
    # Both power levels under the SAME reward, so the comparison is power.
    mults = [float(a) for a in sys.argv[1:] if not a.startswith("--")] or [1.0, 2.0]
    seeds = None
    for a in sys.argv[1:]:
        if a.startswith("--seeds="):
            seeds = [int(x) for x in a.split("=", 1)[1].split(",")]
    for sd in (seeds or [None]):
        for mult in mults:
            print("=" * 70)
            main(mult, seed=sd)
    raise SystemExit(0)
