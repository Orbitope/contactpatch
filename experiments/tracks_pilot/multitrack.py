"""Train one policy across many generated circuits, with the literature settings.

Combines three things this project measured or read its way to:

**1. Corner-dense generated circuits** (`physics/track_gen.py`). Real circuits
spend 59.3% of driving time going straight, where nothing about braking or
grip is learned. Generated ones here run 72.8% cornering — **1.79x the
learning signal per step at identical compute**. Realism is not a goal:
Remonda and Evans independently report complex-to-simple transfer works and
simple-to-complex does not, so training harder than the evaluation is the
right direction.

**2. A track bank** (`physics/track_bank.py`) so each of the 256 instances
drives its own circuit, redrawn every reset. Measured at 1.7 us/step against
79.9 us for the single shared spline — multi-track is *cheaper* than what we
were doing.

**3. The settings the survey said we had wrong** (RL_PLAN Phases 1 and 4):

| | ours was | now | why |
|---|---|---|---|
| `minibatches` | 4 (batch 65,536) | 32 (8,192) | Sophy 1,024, Fuchs 4,096, TRI 256. 8x the gradient steps on identical data. |
| `gae_lambda` | 0.95 (0.37 s) | 0.98 (0.80 s) | Sophy's n-step ablation is flat n=5–9, cliffs at n=1. |
| penalties | fixed magnitude | **speed-scaled** | No published limit-driving agent uses a dense fixed-weight penalty. Fixed ones are minimised by driving slowly. |
| `envelope_penalty` | 6 | 0.25 | Sophy's tyre-slip weight is 0.25 against progress 1 — ours was 24x that, and Sophy drops it entirely on its fastest track. |
| `cross_track_penalty` | 2 | 0.2 | Sophy has none at all; Evans uses 0.004 against a velocity weight of 0.04. Ours was the term pinning the policy mid-road at 50% of the cornering limit. |

**What this run is and is not.** It is the first multi-circuit training in the
project and the first with the corrected reward form. It is **one seed**, so
under rule 5 nothing here is a trend until it is three. Evaluation is on
**held-out generated circuits and on real Spa**, neither of which appear in
training.

    python -m experiments.tracks_pilot.multitrack [n_tracks] [steps]
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.batched_env import BatchedDrivingEnv
from physics.ppo import PPOConfig, train
from physics.rl_env import DrivingEnv, EnvConfig
from physics.track_bank import TrackBank, BankTrackView
from physics.track_gen import generate_set, track_stats
from physics.tracks_data import load_real_track
from experiments.tracks_pilot import policy_eval as PE

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

N_TRACKS = 64
N_HELDOUT = 8
TOTAL_STEPS = 60_000_000
N_ENVS, ROLLOUT = 256, 1024

#: Reward, at the magnitudes the survey supports rather than the ones this
#: project tuned its way to. See the table in the module docstring.
ENV = dict(
    max_steps=30_000,
    progress_scale=1.0,
    off_track_penalty=5.0,
    stall_penalty=2.0,
    envelope_penalty=0.25,
    cross_track_penalty=0.2,
    edge_penalty=0.15,
    speed_scaled_penalties=True,
    penalty_speed_ref=25.0,
    spawn_speed_from_curvature=True,
    speed_cap=None,          # no limiter: F111 showed raising one teaches nothing
)


def _cfg(track, **over):
    base = dict(track=track, start_jitter_m=float(track.length), **ENV)
    base.update(over)
    return EnvConfig(**base)


def main(n_tracks: int = N_TRACKS, total_steps: int = TOTAL_STEPS):
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Multi-track training — {n_tracks} generated circuits, "
         f"{total_steps:,} steps")

    tracks = generate_set(n_tracks + N_HELDOUT, seed0=10_000)
    train_tracks, heldout = tracks[:n_tracks], tracks[n_tracks:]
    bank = TrackBank(train_tracks)
    cf = np.mean([track_stats(t)["corner_time_fraction"] for t in train_tracks])
    print(f"  {bank}")
    print(f"  mean cornering time {100*cf:.1f}% (real circuits: 40.7%)")
    print(f"  held out: {len(heldout)} generated circuits + real Spa\n")

    cfg = PPOConfig(total_steps=total_steps, n_envs=N_ENVS,
                    rollout_steps=ROLLOUT, gamma=0.995, gae_lambda=0.98,
                    minibatches=32, epochs=10, seed=0, entropy_anneal=True,
                    eval_every=8, eval_episodes=4)
    n_upd = total_steps // (N_ENVS * ROLLOUT)
    print(f"  {n_upd} updates x {cfg.epochs} epochs x {cfg.minibatches} "
         f"minibatches = {n_upd*cfg.epochs*cfg.minibatches:,} gradient steps "
         f"(was {n_upd*10*4:,} at the old settings)\n")

    def make_batched(n):
        return BatchedDrivingEnv(_cfg(train_tracks[0]), n=n, seed=0, bank=bank)

    def make_eval():
        # A held-out circuit, so checkpoint selection is not made on the
        # training distribution.
        return DrivingEnv(_cfg(heldout[0], start_jitter_m=0.0))

    def on_update(rec):
        if rec["update"] % 8 == 0:
            ev = f" eval={rec['eval_return']:8.1f}" if "eval_return" in rec else ""
            print(f"  upd {rec['update']:4d} steps={rec['steps']:>11,} "
                 f"v={rec.get('speed_mean', float('nan')):5.1f} "
                 f"slip={rec.get('worst_slip_mean_deg', 0.0):5.1f} "
                 f"off={rec['off_track_rate']:.2f} "
                 f"EV={rec['explained_variance']:+.3f}{ev}", flush=True)

    t0 = time.time()
    res = train(make_batched_env=make_batched, cfg=cfg, on_update=on_update,
               make_eval_env=make_eval)
    wall = time.time() - t0
    h = res["history"]
    ev_tail = float(np.median([r["explained_variance"]
                              for r in h[-max(len(h)//5, 1):]]))
    print(f"\n  done: {len(h)} updates, {wall/60:.1f} min, EV tail {ev_tail:+.3f}")

    # --- evaluation: held-out generated circuits, then real Spa ------------
    rows = {}
    for i, t in enumerate(heldout[:4]):
        r = PE.evaluate(res["model"], t, n_sections=12, env_kwargs=ENV)
        rows[t.name] = {"headline": r.headline(), "lap_frac": r.fraction_of_lap,
                        "finish": r.finish_rate, "valid": r.valid,
                        "slip": r.worst_slip_deg}
        print(f"\n  [held-out {t.name}] {r.headline()}")
    spa = load_real_track("Spa")
    r_spa = PE.evaluate(res["model"], spa, n_sections=24, env_kwargs=ENV)
    rows["Spa"] = {"headline": r_spa.headline(),
                   "lap_frac": r_spa.fraction_of_lap,
                   "finish": r_spa.finish_rate, "valid": r_spa.valid,
                   "slip": r_spa.worst_slip_deg}
    print(f"\n  [REAL Spa, never trained on] {r_spa.headline()}")

    torch.save(res["model"].state_dict(), OUT / "multitrack_policy.pt")
    (OUT / "multitrack_history.json").write_text(json.dumps(h, indent=2) + "\n")
    r_spa.to_json(OUT / "multitrack_spa_eval.json")
    (OUT / "multitrack_summary.json").write_text(json.dumps({
        "n_train_tracks": n_tracks, "n_heldout": len(heldout),
        "total_steps": total_steps, "wall_s": wall,
        "mean_corner_time_fraction": float(cf),
        "explained_variance_tail": ev_tail, "env": {k: v for k, v in ENV.items()},
        "gradient_steps": n_upd * cfg.epochs * cfg.minibatches,
        "results": rows,
    }, indent=2) + "\n")
    print(f"\n  wrote multitrack_*")


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else N_TRACKS,
         int(sys.argv[2]) if len(sys.argv) > 2 else TOTAL_STEPS)
