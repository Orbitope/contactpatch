"""Stage 2 — warm-start the lane-follower and raise the cap until GRIP binds.

**Why this exists.** `spa_curriculum.py` with `cross_track_penalty=2.0`
produced a policy that laps Spa 100% of the time, rule-4 valid. Measured
against what the car can actually do, it is not a driver:

    fraction of the grip-limited speed used   28.9% mean, 21.7% median
    above 90% of the limit                     1.2% of the lap
    mean slip angle                            0.3 deg  (tyres peak 8-12)
    speed standard deviation                   0.29 m/s -- no modulation
    lap time                                   537 s vs ~135 s at the limit

It learned to follow the road with the throttle pinned and let the limiter
do the rest. It has learned nothing about braking points, the friction
limit, or the racing line — and torque vectoring, which is the whole point
of Season 4-5, is meaningless at 29% of the limit.

**The fix is not to remove the cap, it is to make the cap stop being the
thing that binds.** Warm-start from that policy (it can hold a line; that is
worth keeping) and raise the cap until the policy *chooses* to go slower
than it is allowed to — at which point grip, not the limiter, is setting the
speed, and it is finally making the decisions the series is about.

**The gate is the difference from stage 1.** Stage 1 raised on
mastery-or-plateau and froze on degradation, which stalled at a cap the
policy was simply pinned against. This raises while the policy is *using*
the cap (mean speed close to it) and stops when it is not — a direct
measurement of which constraint is active, rather than a proxy.

`envelope_penalty` keeps slip inside the tyre fit; the slip guard here sits
at the real 12 deg bound rather than stage 1's conservative 10, because
driving at the limit *means* slip in the 8-12 range and a guard below that
stops the curriculum before the thing it exists to reach.

    python -m experiments.tracks_pilot.spa_pushlimit [track] [steps]
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.ppo import PPOConfig, train
from physics.rl_env import ENVELOPE_SLIP_MAX
from physics.tracks_data import load_real_track
from experiments.tracks_pilot import spa_ppo_v2 as V2
from experiments.tracks_pilot import policy_eval as PE

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

TOTAL_STEPS = 120_000_000
WARM_START = OUT / "curr_ct2_policy.pt"
CROSS_TRACK = 2.0
CAP_START = 13.0          # where the warm-started policy already lives
CAP_STEP = 1.5
CAP_MAX = 60.0            # above anything this car can use; never meant to bind

#: Raise while the policy is PINNED at the cap. If mean speed is within this
#: fraction of the cap, the limiter is what is holding it back, so lift it.
CAP_BINDING_RATIO = 0.90
#: ...and stop once it sits below that for this many consecutive updates:
#: the policy is now choosing its own speed, which is the goal.
CAP_RELEASE_PATIENCE = 4
CAP_MIN_UPDATES_BETWEEN = 3
#: Updates to let the policy ADAPT after a raise before its speed is allowed
#: to count as evidence that grip binds. Without this the curriculum stops
#: almost immediately: mean speed always dips right after a raise, because the
#: policy has not learnt to use the new headroom yet, and that dip is
#: indistinguishable from "the tyres will not allow more". Caught in the smoke
#: test, where the release fired 4 updates in.
CAP_ADAPT_UPDATES = 10

#: The real tyre-model bound (12 deg), not stage 1's conservative 10. Driving
#: at the limit means slip in the 8-12 range; a guard below that would stop
#: the curriculum before it reaches the regime it exists to find.
SLIP_BOUND_DEG = float(np.degrees(ENVELOPE_SLIP_MAX))


def main(track_name: str = "Spa", total_steps: int = TOTAL_STEPS,
        tag: str | None = None):
    tag = tag or f"push_{track_name.lower()}"
    OUT.mkdir(parents=True, exist_ok=True)
    track = load_real_track(track_name)
    env_over = {"speed_cap": CAP_START, "track": track,
                "cross_track_penalty": CROSS_TRACK}

    cfg = PPOConfig(total_steps=total_steps, n_envs=V2.N_ENVS,
                    rollout_steps=V2.ROLLOUT_STEPS, gamma=V2.GAMMA,
                    seed=V2.SEED, eval_every=8,
                    eval_episodes=V2.EVAL_EPISODES, entropy_anneal=True)
    n_upd = total_steps // (V2.N_ENVS * V2.ROLLOUT_STEPS)
    print(f"Stage 2 -- push the limit on {track_name}, {total_steps:,} steps")
    print(f"  warm start: {WARM_START.name}")
    print(f"  cap {CAP_START} -> {CAP_MAX} m/s, +{CAP_STEP} while mean speed is "
         f"within {CAP_BINDING_RATIO:.0%} of it")
    print(f"  stop raising once it sits below that for {CAP_RELEASE_PATIENCE} "
         f"updates == grip is binding, not the limiter")
    print(f"  {n_upd} updates\n")

    envs = {}
    def make_batched(n):
        envs["b"] = V2.make_batched_env(n, env_over=env_over)
        return envs["b"]
    def make_eval():
        envs["e"] = V2.make_eval_env(env_over)
        return envs["e"]

    st = {"cap": CAP_START, "hot": 0, "cold": 0, "last": -99,
          "raises": [], "released": False}

    def on_update(rec):
        v = rec.get("speed_mean", float("nan"))
        slip = rec.get("worst_slip_mean_deg", 0.0)
        ratio = v / st["cap"] if st["cap"] > 0 else 0.0
        binding = np.isfinite(ratio) and ratio >= CAP_BINDING_RATIO
        # Rule 4 still holds: never raise while already outside the tyre fit.
        over = np.isfinite(slip) and slip > SLIP_BOUND_DEG
        if binding:
            st["hot"] += 1; st["cold"] = 0
        elif rec["update"] - st["last"] >= CAP_ADAPT_UPDATES:
            # Only count as "not using the cap" once the policy has had time
            # to adapt to the last raise -- see CAP_ADAPT_UPDATES.
            st["cold"] += 1; st["hot"] = 0
        raised = False
        if (binding and not over and not st["released"]
                and st["cap"] < CAP_MAX
                and rec["update"] - st["last"] >= CAP_MIN_UPDATES_BETWEEN):
            st["cap"] = min(st["cap"] + CAP_STEP, CAP_MAX)
            st["last"] = rec["update"]
            raised = True
            st["raises"].append({"update": rec["update"], "cap": st["cap"],
                                 "speed_mean": float(v), "slip": float(slip)})
            for e in (envs.get("b"), envs.get("e")):
                if e is not None:
                    e.cfg.speed_cap = st["cap"]
            env_over["speed_cap"] = st["cap"]
        settled = rec["update"] - st["last"] >= CAP_ADAPT_UPDATES
        if (st["cold"] >= CAP_RELEASE_PATIENCE and settled
                and not st["released"]):
            st["released"] = True
            print(f"  >>> update {rec['update']}: mean speed {v:.1f} is "
                 f"{ratio:.0%} of cap {st['cap']:.1f} -- GRIP is now binding, "
                 f"cap frozen", flush=True)
        rec["speed_cap"] = st["cap"]
        if rec["update"] % 8 == 0 or raised:
            ev = f" eval={rec['eval_return']:8.1f}" if "eval_return" in rec else ""
            print(f"  upd {rec['update']:4d} cap={st['cap']:5.1f}"
                 f"{'^' if raised else ' '} v={v:5.1f} ({ratio:4.0%}) "
                 f"slip={slip:4.1f} off={rec['off_track_rate']:.2f} "
                 f"EV={rec['explained_variance']:+.3f}{ev}", flush=True)

    t0 = time.time()
    res = train(make_batched_env=make_batched, cfg=cfg, on_update=on_update,
               make_eval_env=make_eval,
               init_state_dict=torch.load(WARM_START))
    wall = time.time() - t0
    h = res["history"]
    ev_tail = float(np.median([r["explained_variance"]
                              for r in h[-max(len(h)//5, 1):]]))
    sel = res.get("best_update")
    cap_at_sel = CAP_START
    for r in st["raises"]:
        if r["update"] <= sel:
            cap_at_sel = r["cap"]

    print(f"\n  done: {len(h)} updates, {wall/60:.1f} min")
    print(f"  final cap {st['cap']:.1f} ({len(st['raises'])} raises), "
         f"grip-binding: {st['released']}")
    print(f"  EV tail {ev_tail:+.3f}")
    print(f"  scoring checkpoint from update {sel} at ITS cap {cap_at_sel:.1f}")

    env_kw = {k: v for k, v in V2.V2_ENV.items() if k != "max_steps"}
    env_kw["cross_track_penalty"] = CROSS_TRACK
    r = PE.evaluate(res["model"], track, speed_cap=cap_at_sel, env_kwargs=env_kw)
    print("\n" + r.report())
    r.to_json(OUT / f"{tag}_eval.json")
    torch.save(res["model"].state_dict(), OUT / f"{tag}_policy.pt")
    (OUT / f"{tag}_history.json").write_text(json.dumps(h, indent=2) + "\n")
    (OUT / f"{tag}_summary.json").write_text(json.dumps({
        "track": track_name, "total_steps": total_steps, "wall_s": wall,
        "warm_start": WARM_START.name, "cap_start": CAP_START,
        "cap_final": st["cap"], "cap_at_selection": cap_at_sel,
        "cap_raises": st["raises"], "grip_binding": st["released"],
        "explained_variance_tail": ev_tail, "best_update": sel,
    }, indent=2) + "\n")
    print(f"\n  wrote {tag}_*")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "Spa",
         int(sys.argv[2]) if len(sys.argv) > 2 else TOTAL_STEPS)
