"""TRACKS.md staging step 5, item 19h — the reward redesign, all at once.

Items 11-18 spent five 40M-step runs and four 20M-step diagnostics tuning
coefficients inside a reward structure the racing-RL literature abandoned
(item 19). This applies the field's structure instead. Every change below is
sourced, not guessed; the numbers in brackets are what the cited system uses.

| change | from | to | source |
|---|---|---|---|
| `progress_scale` | 1.5 | **1.0** | progress weight is pinned at 1.0 in GT Sophy, Fuchs, GT7, Czechmanowski — universally |
| `off_track_penalty` | 500 | **5.0** | terminal penalties in the field are −1 (Evans, Czechmanowski) to 5.0 (Swift) to −50 (Trumpp); never large |
| `stall_penalty` | 150 | **2.0** | same reasoning; kept below `off_track_penalty` so crashing-while-trying still reads as worse than giving up |
| `edge_penalty` | — | **0.15** | NEW. Dense, speed-scaled, `−c·dt·v²·ramp`. Fuchs' `−c_w‖v‖²` and GT Sophy's `−(time off course)·speed²`. ~4.5:1 vs per-step progress at 30 m/s; field band is 3-20:1 |
| `gamma` | 0.9995 | **0.995** | ours was 40 s at 50 Hz, 4-8x longer than any published system (GT Sophy 9.6 s, Fuchs γ=0.98, Czechmanowski 5 s). 0.995 = 4 s |
| `spawn_speed_from_curvature` | — | **True** | D6's `the_task_is_completable` fails on all five prior runs — Spa's tightest corner caps at 10.1 m/s and every episode spawned at 15.0. Fuchs spawns rolling at 100 km/h |
| `n_envs` | 1024 | **256** | NOT a reward change — see below |
| `envelope_penalty` | 0.5 | **0.5** | unchanged, and deliberately so (see below) |

**Why `n_envs` drops.** Item 18 measured the actual cause of the dead critic:
the value head never leaves its initialisation, because Adam at `lr=3e-4`
over the available gradient steps can only travel ~0.2-0.5 per parameter.
The gradient-step budget is `total_steps / (n_envs · rollout_steps) ·
epochs · minibatches` — so `n_envs=1024` bought throughput by *dividing the
number of updates by four*. At 256 the same 40M steps give ~152 updates
(~6,080 gradient steps) instead of 38 (~1,520). Measured throughput cost:
~78.6k vs ~127k steps/s, so ~1.6x slower wall-clock for 4x the critic's
learning budget. Worth it, and it is the one lever that attacks item 18's
mechanism directly rather than shrinking the target.

**Why `envelope_penalty` stays.** Evans et al. (RA-L 2023) report that a
dense progress-shaped reward taught their agent to drift at over 30° slip on
a single-track model valid to ~8° — "exploiting the simulation model". GT
Sophy carries a dedicated `min(|κ|,1)⁴·|α|` tyre term at weight 0.25. This
project's `envelope_penalty` is the same instrument and rule 4 is the same
concern; adding dense progress shaping without it is precisely the
documented way to get a policy that games the tyre fit. Kept, and worth
raising later if the envelope occupancy climbs.

**This is deliberately a multi-variable change** (user's call: "add a bunch
and see if it works, then we can subtract some"). One-at-a-time would be
eight more runs, and items 11-18 already demonstrate that one-at-a-time
inside the wrong structure converges on nothing. The ablation comes after
something works, which is the opposite order from the last arc and is the
point. Nothing here is claimed as *the* cause of an improvement until that
ablation runs.

    python -m experiments.tracks_pilot.spa_ppo_v2
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

N_ENVS = 256
ROLLOUT_STEPS = 1024
TOTAL_STEPS = 40_000_000
GAMMA = 0.995
PROGRESS_SCALE = 1.0
OFF_TRACK_PENALTY = 5.0
STALL_PENALTY = 2.0
EDGE_PENALTY = 0.15
EDGE_THRESHOLD = 0.75
ENVELOPE_PENALTY = 0.5
SEED = 0
#: Raised from 15,000. A Spa lap at ~30 m/s is ~11,650 steps, uncomfortably
#: close to the old cap -- and `timeout` is folded into `done` while `_gae`
#: cuts the bootstrap on `done`, so a truncated episode is taught its future
#: value is zero (item 19h.8). That bug is currently INERT (episodes end at
#: 371-2,672 steps, verified) and this keeps it inert as episodes lengthen,
#: rather than letting it quietly activate at the exact moment the policy
#: starts succeeding. The proper truncation-vs-termination fix needs
#: final-observation plumbing through the batched env; deferred, not forgotten.
MAX_STEPS = 30_000
EVAL_EVERY = 4
EVAL_EPISODES = 8
N_SECTIONS = 24


def _cfg(**over):
    spa = load_real_track("Spa")
    base = dict(track=spa, max_steps=MAX_STEPS,
                envelope_penalty=ENVELOPE_PENALTY,
                off_track_penalty=OFF_TRACK_PENALTY,
                stall_penalty=STALL_PENALTY,
                progress_scale=PROGRESS_SCALE,
                edge_penalty=EDGE_PENALTY,
                edge_threshold=EDGE_THRESHOLD,
                spawn_speed_from_curvature=True,
                start_jitter_m=spa.length)
    base.update(over)
    return EnvConfig(**base)


def make_batched_env(n_envs, seed=SEED):
    return BatchedDrivingEnv(_cfg(), n=n_envs, seed=seed)


def make_eval_env():
    return DrivingEnv(_cfg())


def evaluate_per_section(model, n_sections=N_SECTIONS):
    spa = load_real_track("Spa")
    starts = np.linspace(0.0, spa.length, n_sections, endpoint=False)
    policy = greedy_policy(model)
    rows = []
    for s0 in starts:
        env = DrivingEnv(_cfg(start_jitter_m=0.0))
        env.reset(0)
        env.s = float(s0)
        env.backend.reset(env._spawn_speed())
        obs = env.observe()
        while not env.done:
            obs, r, done, info = env.step(policy(obs))
        h = env.history()
        rows.append({
            "start_s": float(s0),
            "distance_travelled": float(h["s"][-1]) - float(s0),
            "off_track": bool(info["off_track"]),
            "stalled": bool(info["stalled"]),
            "finished": bool(info["finished"]),
            "worst_slip_deg": float(np.max(h["alpha_max_deg"])),
            "envelope_occupancy": float(np.mean(h["envelope_violation"])),
            "steps": int(env.steps),
        })
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("TRACKS.md item 19h -- reward redesign following the racing-RL literature")
    print(f"  n_envs={N_ENVS} (was 1024: 4x more gradient steps, item 18)  "
         f"gamma={GAMMA} (was 0.9995)")
    print(f"  progress_scale={PROGRESS_SCALE}  off_track={OFF_TRACK_PENALTY} "
         f"(was 500)  stall={STALL_PENALTY} (was 150)  "
         f"edge={EDGE_PENALTY} (dense, speed-scaled, NEW)")
    print(f"  spawn_speed_from_curvature=True  envelope={ENVELOPE_PENALTY}  "
         f"total_steps={TOTAL_STEPS:,}\n")

    cfg = PPOConfig(total_steps=TOTAL_STEPS, n_envs=N_ENVS,
                    rollout_steps=ROLLOUT_STEPS, gamma=GAMMA, seed=SEED,
                    eval_every=EVAL_EVERY, eval_episodes=EVAL_EPISODES)
    n_updates = TOTAL_STEPS // (N_ENVS * ROLLOUT_STEPS)
    print(f"  {n_updates} updates x {cfg.epochs * cfg.minibatches} grad steps "
         f"= {n_updates * cfg.epochs * cfg.minibatches:,} value-head gradient "
         f"steps (was ~1,520)\n")

    def on_update(rec):
        ev = f"  eval_return={rec['eval_return']:8.2f}" if "eval_return" in rec else ""
        print(f"  update {rec['update']:4d}  steps={rec['steps']:>11,}  "
             f"return_mean={rec['return_mean']:8.2f}  "
             f"dist_mean={rec['distance_mean']:7.1f}  "
             f"off_track={rec['off_track_rate']:.2f}  "
             f"EV={rec['explained_variance']:+.3f}  "
             f"kl={rec['approx_kl']:.4f}{ev}", flush=True)

    t0 = time.time()
    res = train(make_batched_env=make_batched_env, cfg=cfg, on_update=on_update,
               make_eval_env=make_eval_env)
    wall_s = time.time() - t0
    history = res["history"]
    n = len(history)
    ev_tail = float(np.median([h["explained_variance"]
                              for h in history[-max(n // 5, 1):]]))

    print(f"\n  done: {n} updates, {wall_s:.1f}s ({TOTAL_STEPS/wall_s:,.0f} steps/s)")
    print(f"  explained_variance tail median: {ev_tail:+.3f} "
         f"({'PASSES' if ev_tail > 0.3 else 'FAILS'} D6's >0.3 gate)")
    if "best_update" in res:
        print(f"  SELECTED checkpoint: update {res['best_update']} "
             f"(eval_return={res['best_eval']['eval_return']:.2f})")

    sections = evaluate_per_section(res["model"])
    d = np.array([r["distance_travelled"] for r in sections])
    off = np.mean([r["off_track"] for r in sections])
    stall = np.mean([r["stalled"] for r in sections])
    fin = np.mean([r["finished"] for r in sections])
    slip = np.max([r["worst_slip_deg"] for r in sections])
    occ = np.mean([r["envelope_occupancy"] for r in sections])
    print(f"\n  per-section ({N_SECTIONS} points): distance mean={d.mean():.1f} "
         f"std={d.std():.1f} max={d.max():.1f}")
    print(f"    off_track={off:.2f}  stalled={stall:.2f}  finished={fin:.2f}")
    print(f"    worst_slip={slip:.1f} deg  envelope_occupancy={occ:.3f} "
         f"(rule 4: must be ~0 for a quotable lap)")

    torch.save(res["model"].state_dict(), OUT / "v2_policy.pt")
    (OUT / "v2_history.json").write_text(json.dumps(history, indent=2) + "\n")
    (OUT / "v2_config.json").write_text(json.dumps(res["config"], indent=2) + "\n")
    (OUT / "v2_sections.json").write_text(json.dumps(sections, indent=2) + "\n")
    (OUT / "v2_summary.json").write_text(json.dumps({
        "n_envs": N_ENVS, "rollout_steps": ROLLOUT_STEPS,
        "total_steps": TOTAL_STEPS, "gamma": GAMMA,
        "progress_scale": PROGRESS_SCALE,
        "off_track_penalty": OFF_TRACK_PENALTY,
        "stall_penalty": STALL_PENALTY, "edge_penalty": EDGE_PENALTY,
        "edge_threshold": EDGE_THRESHOLD, "envelope_penalty": ENVELOPE_PENALTY,
        "spawn_speed_from_curvature": True,
        "wall_s": wall_s, "n_updates": n,
        "explained_variance_tail_median": ev_tail,
        "passes_d6_ev_gate": bool(ev_tail > 0.3),
        "section_distance_mean": float(d.mean()),
        "section_distance_std": float(d.std()),
        "section_off_track_rate": float(off),
        "section_stall_rate": float(stall),
        "section_finish_rate": float(fin),
        "section_worst_slip_deg": float(slip),
        "section_envelope_occupancy": float(occ),
        "best_update": res.get("best_update"),
        "best_eval": res.get("best_eval"),
    }, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/v2_*")


if __name__ == "__main__":
    main()
