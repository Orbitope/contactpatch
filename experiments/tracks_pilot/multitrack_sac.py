"""Multi-track training with SAC — the off-policy attempt.

Same environment, same reward, same 1,000 generated circuits as
`multitrack.py`. **The only thing that changes is the learning algorithm**,
so this is a controlled test of the one remaining hypothesis from F113.

The case for it, from the runs rather than from theory: seven PPO runs all
converged within ~10 updates and then stopped moving. The last one held
`eval_return` in a 653-659 band for **280 updates and 73 million steps**
while `explained_variance` sat at 0.93 -- an accurate critic on a policy that
crashes every episode. That is a local optimum, not slow learning, and PPO's
exploration is a single state-independent `log_std` vector that offers no way
out of one.

Fuchs et al. name the mechanism: "PPO required much more training data and
suffered from premature convergences due to its state-independent
exploration." Every headline racing agent is off-policy -- GT Sophy (QR-SAC),
Fuchs (SAC), TC-Driver (SAC), Hildisch (SAC), Evans (TD3).

    python -m experiments.tracks_pilot.multitrack_sac [n_tracks] [steps]
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.batched_env import BatchedDrivingEnv
from physics.rl_env import DrivingEnv
from physics.sac import SACConfig, train
from physics.track_bank import TrackBank
from physics.track_gen import generate_mixed_set, track_stats
from physics.tracks_data import load_real_track
from experiments.tracks_pilot import policy_eval as PE
from experiments.tracks_pilot.multitrack import ENV, _cfg

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

N_TRACKS, N_HELDOUT = 1000, 8
TOTAL_STEPS = 30_000_000
#: Fewer than PPO's 256: off-policy reuses every transition many times from
#: replay, so throughput matters less than update count. 64 envs at
#: updates_per_step=0.5 gives ~32 gradient steps per environment step
#: collected, against PPO's 10 epochs over a rollout.
N_ENVS = 64


def main(n_tracks: int = N_TRACKS, total_steps: int = TOTAL_STEPS):
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"SAC multi-track — {n_tracks} circuits, {total_steps:,} steps")
    tracks = generate_mixed_set(n_tracks + N_HELDOUT, seed0=10_000)
    train_tracks, heldout = tracks[:n_tracks], tracks[n_tracks:]
    bank = TrackBank(train_tracks, store_geometry=False)
    st = [track_stats(t) for t in train_tracks[:64]]
    print(f"  {bank}")
    print(f"  cornering {100*np.mean([x['corner_time_fraction'] for x in st]):.1f}%  "
         f"longest straight {np.mean([x['longest_fast_m'] for x in st]):.0f} m")

    cfg = SACConfig(total_steps=total_steps, n_envs=N_ENVS, gamma=0.98,
                    alpha=0.01, tau=0.005, n_step=5, batch_size=1024,
                    replay_size=1_000_000, hidden=256, lr=3e-4,
                    updates_per_step=0.5, warmup_steps=200_000, seed=0,
                    eval_every=40, eval_episodes=4)
    print(f"  SAC: gamma {cfg.gamma}, alpha {cfg.alpha}, {cfg.n_step}-step, "
         f"{cfg.hidden}x2 hidden, replay {cfg.replay_size:,}\n")

    def make_batched(n):
        return BatchedDrivingEnv(_cfg(train_tracks[0]), n=n, seed=0, bank=bank)

    def make_eval():
        return DrivingEnv(_cfg(heldout[0], start_jitter_m=0.0))

    def on_update(rec):
        if rec["update"] % 40 == 0:
            ev = (f" eval={rec['eval_return']:8.1f}" if "eval_return" in rec
                  else "")
            print(f"  upd {rec['update']:5d} steps={rec['steps']:>11,} "
                 f"buf={rec['replay']:>9,} ret={rec['return_mean']:8.1f} "
                 f"off={rec['off_track_rate']:.2f} "
                 f"slip={rec['worst_slip_mean_deg']:5.1f} "
                 f"ent={rec['entropy']:+.2f}{ev}", flush=True)

    t0 = time.time()
    res = train(make_batched_env=make_batched, cfg=cfg, on_update=on_update,
               make_eval_env=make_eval)
    wall = time.time() - t0
    print(f"\n  done: {len(res['history'])} updates, {wall/60:.1f} min")
    print(f"  best eval {res['best_eval'].get('eval_return', float('nan')):.1f} "
         f"at update {res.get('best_update')}")

    rows = {}
    for t in heldout[:4]:
        r = PE.evaluate(res["model"], t, n_sections=12, env_kwargs=ENV)
        rows[t.name] = r.headline()
        print(f"\n  [held-out {t.name}] {r.headline()}")
    spa = load_real_track("Spa")
    r = PE.evaluate(res["model"], spa, n_sections=24, env_kwargs=ENV)
    rows["Spa"] = r.headline()
    print(f"\n  [REAL Spa, never trained on] {r.headline()}")

    torch.save(res["model"].state_dict(), OUT / "sac_policy.pt")
    (OUT / "sac_history.json").write_text(json.dumps(res["history"], indent=2) + "\n")
    (OUT / "sac_summary.json").write_text(json.dumps({
        "algo": "sac", "n_tracks": n_tracks, "total_steps": total_steps,
        "wall_s": wall, "best_eval": res["best_eval"], "results": rows,
    }, indent=2) + "\n")
    print("\n  wrote sac_*")


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else N_TRACKS,
         int(sys.argv[2]) if len(sys.argv) > 2 else TOTAL_STEPS)
