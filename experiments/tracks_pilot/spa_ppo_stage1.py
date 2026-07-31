"""TRACKS.md staging step 5, training schedule stage 1 — learn the road
everywhere, not just the opening sector.

The long run (``spa_ppo_long.py``) trained 38.5M steps entirely from Spa's
first ~300 m (`start_jitter_m=0`, the environment default) and only ever saw
the rest of the circuit by surviving into it — which it barely did (final
`distance_mean` ~365 m against a ~7,000 m lap). This stage changes exactly
one thing: `start_jitter_m = track.length`, so every reset lands uniformly
around the whole lap. `BatchedDrivingEnv._reset_mask` already draws `s0`
per instance from `uniform(0, start_jitter_m)` — no new environment code.
Because the curvature-ahead preview is local (55 m), driving skill learned
anywhere on the lap transfers everywhere; this just makes sure every part of
the lap actually gets driven during training, not only the part nearest s=0.

Gate (checked in a separate analysis pass after training, downstream from
logged rollouts -- CLAUDE.md rule 7, never computed inside the training
loop): per-start-section survival should be roughly uniform, not
concentrated near s=0 the way an unjittered run's would be. Off-track rate
should sit clearly below the long run's 0.22-0.54 band once averaged over
a comparable number of steps.

**Checkpoint selection is on (`eval_every`, F93/D12) after the first run
without it showed exactly the pattern F93 was written about**: return_mean
peaked mid-run then genuinely declined (not noise -- a sustained ~15-update
regression) while off_track_rate worsened alongside it, and only the FINAL
(worse) weights had been saved. The eval env matches training's own jittered
distribution (`start_jitter_m = track.length`) rather than a from-the-line
task, because stage 1's own question is "does it survive from anywhere",
not stage 2's "does it complete a lap from the start" -- selecting against
the wrong distribution would be selecting on a different stage's question.

**Reward re-tuned (protocol change, rule 9) after decomposing the corrected
run's own reward: `distance - total_reward` averaged 49.90 (std 0.73)
across 30 rollouts -- essentially the entire non-progress cost is the flat
`off_track_penalty=50`, and the envelope term barely fired at all (the
policy wasn't yet pushing near 12 deg). 50 points is only ~10% of a typical
episode's reward (497.3 mean) -- and that fraction SHRINKS as the policy
improves, since the penalty is a flat constant against a growing progress
total. `off_track_penalty: 50 -> 500` makes leaving the road cost far more
of what has been banked; `gamma: 0.999 -> 0.9995` (~2,000-step / 40 s
horizon) makes the IMPLICIT deterrent -- lost future reward -- scale with
how much of the lap remains, rather than staying a fixed number that
dilutes as episodes lengthen. `envelope_penalty` unchanged: it was not the
active constraint in the previous run and there is no evidence yet that it
needs to be.

**A second reward defect found before this run, not after**:
`off_track_penalty=500` alone (checked directly, one rollout of the
resulting checkpoint) taught the policy to brake steadily from the 15 m/s
entry speed down to a dead stop every episode -- `stalled=True`, never
`off_track`. Stalling carried NO penalty at all, so once leaving the road
got expensive enough, coasting to a stop became strictly safer than
driving, and per-section survival collapsed from ~537 m to ~73 m (a car
decelerating from 15 m/s to a stop covers almost exactly that distance).
Fixed with two more changes, both by explicit user decision after
reviewing the tradeoff: `stall_penalty=150` (`physics/rl_env.py`,
`physics/batched_env.py` -- new, D-A pattern, 0.0 default reproduces every
prior episode) closes the loophole directly; `progress_scale=3.0` (same
files) grows the reward for actually covering ground faster than the
now-larger fixed penalties shrink in relative terms, since neither penalty
scales with it. Both differential-tested against the reference
implementation (`tests/test_batched_env.py`) and unit-tested for D-A
default safety (`tests/test_rl_env.py`) before this run.

    python -m experiments.tracks_pilot.spa_ppo_stage1
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.ppo import PPOConfig, greedy_policy, train
from physics.rl_env import DrivingEnv, EnvConfig
from physics.tracks_data import load_real_track

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

N_ENVS = 1024
ROLLOUT_STEPS = 1024
TOTAL_STEPS = 40_000_000
#: All four changed together, by explicit user decision, after decomposing
#: the previous two runs' own rewards (see module docstring for both
#: measurements).
GAMMA = 0.9995
OFF_TRACK_PENALTY = 500.0
#: Closes the "coast to a stop instead of driving" loophole off_track_penalty
#: alone opened. Smaller than OFF_TRACK_PENALTY by convention (not enforced)
#: so a crash while genuinely pushing the limit still reads as worse than
#: giving up, matching the stated priority order: on-track, then inside the
#: slip envelope, then fast.
STALL_PENALTY = 150.0
#: Grows the reward for covering ground faster than the two (now larger)
#: fixed penalties shrink in relative terms -- neither penalty scales with
#: this, so it changes the balance from the other side.
PROGRESS_SCALE = 3.0
SEED = 0
MAX_STEPS = 15_000
ENVELOPE_PENALTY = 0.5
#: The whole point of stage 1: uniform starts around the entire lap, not the
#: long run's start_jitter_m=300.
START_JITTER_M = None  # filled in from track.length in make_batched_env

#: Per-section survival probes, evenly spaced around the lap. 24 points is
#: enough to see whether survival concentrates near s=0 without being an
#: expensive evaluation pass (24 rollouts, not 24*N).
N_SECTIONS = 24

#: Checkpoint selection (F93/D12) -- added after the first stage-1 run showed
#: EXACTLY the pattern F93 was written about: return_mean peaked at update 25
#: (834) then genuinely declined to ~320-400 by the final update, off_track
#: worsening from 0.92 back to 0.96-1.00 alongside it -- not noise, a
#: sustained regression, and the run had saved only the final (worse)
#: weights. eval_every=2 re-evaluates often enough to catch a peak between
#: 38-40 updates without dominating wall-clock (each eval is EVAL_EPISODES
#: single-instance rollouts, small next to a 1024-instance batched update).
EVAL_EVERY = 2
EVAL_EPISODES = 8


def make_eval_env():
    """The SAME jittered-start distribution training uses -- selection has to
    be on the thing stage 1 is actually for (surviving from anywhere on the
    lap), not on the from-the-line task that stage 2 owns."""
    spa = load_real_track("Spa")
    return DrivingEnv(EnvConfig(track=spa, max_steps=MAX_STEPS,
                               envelope_penalty=ENVELOPE_PENALTY,
                               off_track_penalty=OFF_TRACK_PENALTY,
                               stall_penalty=STALL_PENALTY,
                               progress_scale=PROGRESS_SCALE,
                               start_jitter_m=spa.length))


def make_batched_env(n_envs: int, seed: int = SEED):
    from physics.batched_env import BatchedDrivingEnv
    spa = load_real_track("Spa")
    cfg = EnvConfig(track=spa, max_steps=MAX_STEPS,
                    envelope_penalty=ENVELOPE_PENALTY,
                    off_track_penalty=OFF_TRACK_PENALTY,
                    stall_penalty=STALL_PENALTY,
                    progress_scale=PROGRESS_SCALE,
                    start_jitter_m=spa.length)
    return BatchedDrivingEnv(cfg, n=n_envs, seed=seed)


def evaluate_per_section(model, n_sections: int = N_SECTIONS) -> list[dict]:
    """Deployed policy, dropped at ``n_sections`` evenly-spaced points around
    Spa, one rollout each. Distance travelled from EACH probe's own start
    (not absolute ``s`` — TRACKS.md's own stated caveat: `episode_distance`
    is absolute, and that is the wrong number once starts are not all 0).
    """
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
        env.s = float(s0)  # drop the car at this section instead of s=0
        obs = env.observe()  # observation depends on s; reset()'s is stale
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
    print("TRACKS.md step 5, stage 1 -- learn the road everywhere")
    print(f"  n_envs={N_ENVS}  rollout_steps={ROLLOUT_STEPS}  "
         f"total_steps={TOTAL_STEPS:,}  gamma={GAMMA}  "
         f"start_jitter_m=track.length\n")

    cfg = PPOConfig(total_steps=TOTAL_STEPS, n_envs=N_ENVS,
                    rollout_steps=ROLLOUT_STEPS, gamma=GAMMA, seed=SEED,
                    eval_every=EVAL_EVERY, eval_episodes=EVAL_EPISODES)

    def on_update(rec):
        ev = f"  eval_return={rec['eval_return']:8.2f}" if "eval_return" in rec else ""
        print(f"  update {rec['update']:4d}  steps={rec['steps']:>11,}  "
             f"wall={rec['wall_s']:7.1f}s  "
             f"episodes_finished={rec['episodes_finished']:6d}  "
             f"return_mean={rec['return_mean']:8.2f}  "
             f"distance_mean={rec['distance_mean']:8.1f}  "
             f"off_track_rate={rec['off_track_rate']:.2f}  "
             f"explained_var={rec['explained_variance']:+.2f}  "
             f"approx_kl={rec['approx_kl']:.4f}{ev}", flush=True)

    t0 = time.time()
    res = train(make_batched_env=make_batched_env, cfg=cfg, on_update=on_update,
               make_eval_env=make_eval_env)
    wall_s = time.time() - t0
    history = res["history"]
    final = history[-1] if history else {}

    print(f"\n  training done: {len(history)} updates, {wall_s:.1f}s wall-clock "
         f"({cfg.total_steps/wall_s:,.0f} steps/s)")
    print(f"  final (this stage's own accounting -- distance is ABSOLUTE s, "
         f"not corrected for jittered starts, see per-section eval below): "
         f"off_track_rate={final.get('off_track_rate')}  "
         f"distance_mean={final.get('distance_mean')}")
    if "best_update" in res:
        print(f"  SELECTED checkpoint: update {res['best_update']} "
             f"(eval_return={res['best_eval']['eval_return']:.2f}) -- "
             f"the returned model holds these weights, not the final ones. "
             f"Final-weights eval_return for comparison: see history.")

    print("\n  per-section survival (deployed policy, one rollout per "
         f"section, {N_SECTIONS} sections around the lap):")
    sections = evaluate_per_section(res["model"])
    for row in sections:
        print(f"    start_s={row['start_s']:7.1f}  "
             f"distance_travelled={row['distance_travelled']:8.1f}  "
             f"off_track={row['off_track']}  steps={row['steps']}")
    distances = np.array([r["distance_travelled"] for r in sections])
    off_rate = np.mean([r["off_track"] for r in sections])
    print(f"\n  section distance: mean={distances.mean():.1f}  "
         f"std={distances.std():.1f}  min={distances.min():.1f}  "
         f"max={distances.max():.1f}")
    print(f"  section off_track_rate={off_rate:.2f}")
    print(f"  uniformity check: std/mean={distances.std()/max(distances.mean(),1e-9):.2f} "
         "(lower = more uniform survival across the lap)")

    torch.save(res["model"].state_dict(), OUT / "stage1_policy.pt")
    (OUT / "stage1_history.json").write_text(json.dumps(history, indent=2) + "\n")
    (OUT / "stage1_config.json").write_text(json.dumps(res["config"], indent=2) + "\n")
    (OUT / "stage1_sections.json").write_text(json.dumps(sections, indent=2) + "\n")
    (OUT / "stage1_summary.json").write_text(json.dumps({
        "n_envs": N_ENVS, "rollout_steps": ROLLOUT_STEPS,
        "total_steps": TOTAL_STEPS, "gamma": GAMMA,
        "wall_s": wall_s, "n_updates": len(history),
        "steps_per_s_full_loop": cfg.total_steps / wall_s,
        "final_training_stats": final,
        "best_update": res.get("best_update"),
        "best_eval": res.get("best_eval"),
        "section_distance_mean": float(distances.mean()),
        "section_distance_std": float(distances.std()),
        "section_off_track_rate": float(off_rate),
    }, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/stage1_{{policy.pt,history.json,"
         f"config.json,sections.json,summary.json}}")


if __name__ == "__main__":
    main()
