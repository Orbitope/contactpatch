"""Does our SAC learn a task PPO is known to solve? A sanity check on the
implementation, not on the task.

Multi-track SAC reached eval ~4 against PPO's 655 on the same environment.
That is not slow learning, it is a suspect implementation -- so before
debugging on the hard problem, run it on `long_exit`, the single synthetic
corner Episodes 9-11 already solve with PPO. If SAC cannot learn that, the
bug is in `physics/sac.py`; if it can, the multi-track task is the problem.

Runs both algorithms on identical environment and reward so the comparison
is the algorithm.
"""

from __future__ import annotations

import numpy as np
import torch

from physics.batched_env import BatchedDrivingEnv
from physics.rl_env import DrivingEnv, EnvConfig
from physics.track import long_exit
from physics import ppo as PPO
from physics import sac as SAC

ENV = dict(max_steps=1200, envelope_penalty=6.0, off_track_penalty=5.0,
           stall_penalty=2.0, progress_scale=1.0)
STEPS = 1_500_000


def _cfg(**over):
    base = dict(track=long_exit(), **ENV)
    base.update(over)
    return EnvConfig(**base)


def main():
    print(f"SAC vs PPO on long_exit (the task Episodes 9-11 solve), "
         f"{STEPS:,} steps each\n")

    print("--- PPO ---")
    pc = PPO.PPOConfig(total_steps=STEPS, n_envs=64, rollout_steps=512,
                       gamma=0.99, minibatches=8, epochs=10, seed=0,
                       eval_every=10, eval_episodes=3)
    pres = PPO.train(make_batched_env=lambda n: BatchedDrivingEnv(_cfg(), n=n, seed=0),
                     cfg=pc, make_eval_env=lambda: DrivingEnv(_cfg()),
                     on_update=lambda r: None)
    pev = [r["eval_return"] for r in pres["history"] if "eval_return" in r]
    print(f"  final eval {pev[-1]:8.1f}   best {max(pev):8.1f}   "
         f"EV {pres['history'][-1]['explained_variance']:+.3f}")

    print("\n--- SAC ---")
    sc = SAC.SACConfig(total_steps=STEPS, n_envs=64, batch_size=512,
                       replay_size=500_000, hidden=256, gamma=0.99,
                       updates_per_step=0.25, warmup_steps=50_000, seed=0,
                       n_step=5, auto_alpha=True, eval_every=40,
                       eval_episodes=3)
    sres = SAC.train(make_batched_env=lambda n: BatchedDrivingEnv(_cfg(), n=n, seed=0),
                     cfg=sc, make_eval_env=lambda: DrivingEnv(_cfg()),
                     on_update=lambda r: None)
    sev = [r["eval_return"] for r in sres["history"] if "eval_return" in r]
    print(f"  final eval {sev[-1]:8.1f}   best {max(sev):8.1f}   "
         f"entropy {sres['history'][-1]['entropy']:+.2f}  "
         f"alpha {sres['history'][-1]['alpha']:.4f}")

    print(f"\n  VERDICT: SAC/PPO best-eval ratio {max(sev)/max(max(pev),1e-9):.2f}")
    print(f"  Below ~0.5 means physics/sac.py is the problem, not the task.")


if __name__ == "__main__":
    main()
