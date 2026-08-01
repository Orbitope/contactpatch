"""TRACKS.md item 26 — progressive speed-limit curriculum, trained long.

**Why a speed curriculum.** Item 25 established the task is completable: the
classical driver laps Spa cleanly (2.3° slip) at ``v_max=12`` and spins at 45.
The failure analysis then showed the RL policy leaves the road at 27.9 m/s
into corners allowing 24.0 (15/24 probes over the limit by 9.0 m/s) at only
**4.2° slip** — it is not out of grip, it under-brakes and under-steers. The
progress reward pays immediately for speed; braking pays later and only if
the corner is then taken correctly, so the policy learns the first half and
never the second.

Capping the speed removes the ability to make that mistake. Measured, one
run: ``speed_cap=14`` took per-section distance from 468 m to **3448 m**, a
7.4x improvement and the largest single movement in this whole thread.

**Why progressive.** A fixed cap is a compromise: 14 m/s is still too fast
for Spa's tightest corner (r=11.4 m allows ~10.4 m/s at this car's ~0.97 g)
and far too slow everywhere else. Hildisch et al. (RLC 2025, arXiv:2505.07321
— item 19 §4b) raise the limit on a *performance* gate: "the action space for
the speed command is [0.5; α] with α ∈ [1;7] m/s. **α is increased by 0.5 m/s
as soon as the agent completes three consecutive laps without track-boundary
violation.**" This is that, adapted: start below the tightest corner's own
limit so every corner is takeable from the first step, and raise the cap only
once the policy is demonstrably keeping the car on the road.

The cap is a limiter on the ACTION (above it, no positive drive), not a
reward term, so the policy cannot trade it away against progress — which is
the whole point, given that trading safety for progress is the documented
failure this thread has hit at every previous turn.

**Budget.** 120M steps, matching Czechmanowski et al. (arXiv:2504.02420), the
closest published analogue — single-track dynamic model with MF6.1 Magic
Formula tyres, PPO, beats MPC and expert humans. Every run in this thread so
far has been 20-40M, so under-training has never been ruled out.

    python -m experiments.tracks_pilot.spa_curriculum
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.ppo import PPOConfig, train
from physics.rl_env import EnvConfig
from physics.tracks_data import load_real_track
from experiments.tracks_pilot import spa_ppo_v2 as V2

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

TOTAL_STEPS = 120_000_000
#: Below the tightest corner's own limit (r=11.4 m at ~0.97 g -> ~10.4 m/s),
#: so no corner on the circuit is unsurvivable from the very first step --
#: the failure D6's `the_task_is_completable` exists to catch.
CAP_START = 9.0
CAP_STEP = 1.0
CAP_MAX = 45.0
#: Raise the cap on MASTERY **or** PLATEAU. The mastery gate alone would have
#: stalled this run: measured on the cap=14 run, `off_track_rate` has median
#: 0.90 and sits below 0.55 in only 12% of updates, so "3 consecutive clean"
#: would essentially never fire and the whole 120M steps would train at
#: cap=9. Checked before spending the compute rather than after.
#:
#: Hildisch et al. can gate purely on mastery because a clean lap is
#: achievable in their setting; here a "section" is up to 7 km and the best
#: policy so far covers ~3.4 km, so crash-free is rare by construction. The
#: plateau arm is what keeps the curriculum moving: once distance stops
#: improving at the current cap, the policy has learned what that cap can
#: teach it.
CAP_CLEAN_BELOW = 0.60
CAP_PATIENCE = 3
#: Updates without a new best distance at the current cap before raising
#: anyway. 458 updates over 36 raises (9 -> 45 at +1.0) is ~12.7 apiece, so
#: this paces the curriculum to use roughly the whole budget even if the
#: mastery gate never fires.
CAP_PLATEAU_PATIENCE = 12
#: Stop raising the cap once the deployed policy drops below this fraction of
#: the best eval seen, for this many consecutive evaluations. Without it the
#: curriculum climbs past competence -- see the comment at the gate.
CAP_DEGRADE_FRAC = 0.5
CAP_DEGRADE_PATIENCE = 3
#: Do not raise the cap while the policy is already at the tyre model's own
#: limit. Measured: with the degradation freeze alone the cap reached 16 and
#: selection landed on a cap-13 checkpoint that exceeded 12 deg in 21 of 24
#: sections -- more distance than the cap-11 policy (41.4% vs 40.5%) but
#: rule-4 INVALID, where the slower one was clean (0/24) and completed a lap.
#: Raising the speed limit past what the tyres can hold buys distance the
#: project is not allowed to quote. Gated on the training history's own
#: `worst_slip_mean_deg`, so it costs nothing extra to evaluate.
CAP_SLIP_HEADROOM_DEG = 10.0
#: Centreline restoring term -- the omission that capped Spa at 40% of a lap
#: (see EnvConfig.cross_track_penalty). Swept before use.
CROSS_TRACK = 5.0
N_SECTIONS = 24


def main(track: str = "Spa", total_steps: int = TOTAL_STEPS,
        tag: str | None = None):
    global CROSS_TRACK
    """``track`` selects the circuit; SEASON5 Ep 19 wants specialists on
    circuits with distinct corner-speed distributions (fast / mixed / tight)
    before the multi-track generalist, so the generalisation gap has a
    denominator. Measured spread, % of lap below 15 m/s: Monza 1.8 (fast),
    Spa 1.5 (mixed, p10 23.9), MexicoCity 5.6 (tight)."""
    global TOTAL_STEPS
    TOTAL_STEPS = total_steps
    tag = tag or track.lower()
    OUT.mkdir(parents=True, exist_ok=True)
    env_over = {"speed_cap": CAP_START, "track": load_real_track(track),
                "cross_track_penalty": CROSS_TRACK}
    ppo_over = {"entropy_anneal": True}   # D6's exploration gate fails without it

    cfg = PPOConfig(total_steps=TOTAL_STEPS, n_envs=V2.N_ENVS,
                    rollout_steps=V2.ROLLOUT_STEPS, gamma=V2.GAMMA,
                    seed=V2.SEED, eval_every=8, eval_episodes=V2.EVAL_EPISODES,
                    **ppo_over)
    n_upd = TOTAL_STEPS // (V2.N_ENVS * V2.ROLLOUT_STEPS)
    print(f"Curriculum specialist -- {track}, {total_steps:,} steps")
    print(f"  cap {CAP_START} -> {CAP_MAX} m/s, +{CAP_STEP} when off_track_rate "
         f"< {CAP_CLEAN_BELOW} for {CAP_PATIENCE} consecutive updates")
    print(f"  {n_upd} updates x {cfg.epochs*cfg.minibatches} = "
         f"{n_upd*cfg.epochs*cfg.minibatches:,} value-head gradient steps\n")

    batched = {}
    def make_batched(n):
        e = V2.make_batched_env(n, env_over=env_over)
        batched["env"] = e
        return e
    evals = {}
    def make_eval():
        e = V2.make_eval_env(env_over)
        evals["env"] = e
        return e

    state = {"cap": CAP_START, "clean": 0, "raises": [], "best": -1.0,
             "stale": 0, "per_cap": [], "eval_caps": [], "best_eval_seen": -1e30,
             "degraded": 0}

    def on_update(rec):
        # --- the curriculum gate: mastery OR plateau ---
        off = rec["off_track_rate"]
        dist = rec["distance_mean"]
        if np.isfinite(off) and off < CAP_CLEAN_BELOW:
            state["clean"] += 1
        else:
            state["clean"] = 0
        if np.isfinite(dist) and dist > state["best"]:
            state["best"], state["stale"] = dist, 0
        else:
            state["stale"] += 1
        if "eval_return" in rec:
            if rec["eval_return"] > state["best_eval_seen"]:
                state["best_eval_seen"] = rec["eval_return"]
                state["degraded"] = 0
            elif rec["eval_return"] < CAP_DEGRADE_FRAC * state["best_eval_seen"]:
                state["degraded"] += 1
        mastered = state["clean"] >= CAP_PATIENCE
        plateaued = state["stale"] >= CAP_PLATEAU_PATIENCE
        # Freeze the curriculum once the deployed policy has clearly fallen
        # away from its own best. Measured on the first run: eval peaked at
        # 3521.7 (cap 11, update 80) and never recovered as the cap kept
        # climbing to 28 -- ending at 741.8. The plateau arm alone will happily
        # raise the cap past the policy's competence and destroy it. This risk
        # was identified while designing the curriculum and deliberately not
        # implemented "to keep it simpler"; that was the wrong call and it cost
        # a 75-minute run.
        frozen = state["degraded"] >= CAP_DEGRADE_PATIENCE
        # Rule 4: a faster cap that puts the car outside the tyre fit is not
        # an improvement, it is an unquotable number.
        slip = rec.get("worst_slip_mean_deg", 0.0)
        at_grip_limit = np.isfinite(slip) and slip > CAP_SLIP_HEADROOM_DEG
        raised = False
        if ((mastered or plateaued) and not frozen and not at_grip_limit
                and state["cap"] < CAP_MAX):
            state["per_cap"].append({"cap": state["cap"],
                                     "best_distance": float(state["best"]),
                                     "until_update": rec["update"]})
            state["cap"] = min(state["cap"] + CAP_STEP, CAP_MAX)
            state["clean"] = state["stale"] = 0
            state["best"] = -1.0
            raised = True
            state["raises"].append({"update": rec["update"],
                                    "steps": rec["steps"],
                                    "cap": state["cap"],
                                    "reason": "mastery" if mastered else "plateau",
                                    "worst_slip_mean_deg": float(slip),
                                    "off_track_rate": float(off)})
            # Mutate BOTH envs -- the eval env is a separate object and would
            # otherwise silently keep scoring at the old cap.
            for e in (batched.get("env"), evals.get("env")):
                if e is not None:
                    e.cfg.speed_cap = state["cap"]
            env_over["speed_cap"] = state["cap"]
        rec["speed_cap"] = state["cap"]
        if "eval_return" in rec:
            # Remember the cap AT SELECTION TIME. Evaluating the chosen
            # checkpoint at the FINAL cap instead is a real bug that already
            # bit once: the update-80 policy was trained at cap 11 and scored
            # at cap 28, reporting 699.7 m / 36 deg slip / 15-of-24 outside
            # the tyre model when its true numbers at its own cap are
            # 2834.9 m / 9.8 deg / 0-of-24. It made the best result of the
            # thread look like a failure.
            state["eval_caps"].append({"update": rec["update"],
                                       "cap": state["cap"],
                                       "eval_return": rec["eval_return"]})
        if rec["update"] % 8 == 0 or raised:
            ev = f" eval={rec['eval_return']:7.1f}" if "eval_return" in rec else ""
            print(f"  upd {rec['update']:4d} steps={rec['steps']:>11,} "
                 f"cap={state['cap']:4.1f}{'^' if raised else ' '} "
                 f"off={off:.2f} dist={rec['distance_mean']:7.1f} "
                 f"EV={rec['explained_variance']:+.3f}{ev}", flush=True)

    t0 = time.time()
    res = train(make_batched_env=make_batched, cfg=cfg, on_update=on_update,
               make_eval_env=make_eval)
    wall = time.time() - t0
    h = res["history"]
    n = len(h)
    ev_tail = float(np.median([r["explained_variance"] for r in h[-max(n//5,1):]]))

    print(f"\n  done: {n} updates, {wall/60:.1f} min "
         f"({TOTAL_STEPS/wall:,.0f} steps/s)")
    print(f"  final cap {state['cap']:.1f} m/s after {len(state['raises'])} raises")
    print(f"  EV tail {ev_tail:+.3f} ({'PASS' if ev_tail>0.3 else 'FAIL'})")

    # Evaluate the SELECTED checkpoint at the cap it was trained under, not
    # at whatever the curriculum happened to reach by the end.
    sel = res.get("best_update")
    eval_cap = state["cap"]
    for e in state["eval_caps"]:
        if e["update"] == sel:
            eval_cap = e["cap"]
            break
    print(f"  evaluating the selected checkpoint at ITS OWN cap "
         f"{eval_cap:.1f} m/s (final curriculum cap was {state['cap']:.1f})")
    sec = V2.evaluate_per_section(res["model"], n_sections=N_SECTIONS,
                                 env_over={"speed_cap": eval_cap})
    d = np.array([r["distance_travelled"] for r in sec])
    slip = np.array([r["worst_slip_deg"] for r in sec])
    occ = np.array([r["envelope_occupancy"] for r in sec])
    off = np.mean([r["off_track"] for r in sec])
    fin = np.mean([r["finished"] for r in sec])
    L = env_over["track"].length
    print(f"\n  per-section: dist mean={d.mean():.1f} ({100*d.mean()/L:.1f}% of lap) "
         f"max={d.max():.1f}")
    print(f"    off_track={off:.2f}  finished={fin:.2f}  "
         f"slip_max={slip.max():.1f}  over12={int((slip>12).sum())}/{N_SECTIONS}  "
         f"occ={occ.mean():.4f}")

    torch.save(res["model"].state_dict(), OUT / f"curr_{tag}_policy.pt")
    (OUT / f"curr_{tag}_history.json").write_text(json.dumps(h, indent=2)+"\n")
    (OUT / f"curr_{tag}_sections.json").write_text(json.dumps(sec, indent=2)+"\n")
    (OUT / f"curr_{tag}_summary.json").write_text(json.dumps({
        "total_steps": TOTAL_STEPS, "wall_s": wall, "n_updates": n,
        "cap_start": CAP_START, "cap_final": state["cap"],
        "eval_cap_used": eval_cap, "eval_caps": state["eval_caps"],
        "curriculum_frozen": bool(state["degraded"] >= CAP_DEGRADE_PATIENCE),
        "cap_slip_headroom_deg": CAP_SLIP_HEADROOM_DEG,
        "cap_raises": state["raises"], "per_cap_best": state["per_cap"],
        "entropy_anneal": True,
        "explained_variance_tail": ev_tail, "passes_d6_ev_gate": bool(ev_tail>0.3),
        "section_distance_mean": float(d.mean()),
        "section_fraction_of_lap": float(d.mean()/L),
        "section_off_track_rate": float(off), "section_finish_rate": float(fin),
        "section_worst_slip_deg": float(slip.max()),
        "sections_over_12deg": int((slip>12).sum()),
        "section_envelope_occupancy": float(occ.mean()),
        "best_update": res.get("best_update"),
        "best_eval": res.get("best_eval"),
    }, indent=2)+"\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/curr_{tag}_*")


if __name__ == "__main__":
    import sys
    tr = sys.argv[1] if len(sys.argv) > 1 else "Spa"
    st = int(sys.argv[2]) if len(sys.argv) > 2 else TOTAL_STEPS
    if len(sys.argv) > 3:
        CROSS_TRACK = float(sys.argv[3])
    tg = sys.argv[4] if len(sys.argv) > 4 else None
    main(tr, st, tg)
