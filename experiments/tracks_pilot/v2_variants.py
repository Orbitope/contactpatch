"""TRACKS.md items 21-22 — one runner for both jobs that follow the v2
redesign, so neither becomes another near-copy of ``spa_ppo_v2.py``.

**Job 1, `--job envelope`** (item 21): v2 fixed the critic (EV 0.881) but
left 16/24 sections over the 12° slip bound at 0.0124 envelope occupancy,
against rule 4's requirement of ~0 for a quotable lap. `envelope_penalty` is
the one term item 19h deliberately did not touch, and item 20's evidence says
it is now the binding weakness: with an accurate critic PPO optimises this
reward properly for the first time, and the reward still pays for sliding
more than it charges. Sweeps it as a **single variable** over the v2
baseline.

**Job 2, `--job ablation`** (item 22): the user's "then we can subtract
some". v2 changed seven things at once, deliberately, because one-at-a-time
inside a broken structure had already failed for eight runs. Now that a
working configuration exists, each change is reverted **individually** back
to its pre-v2 value (including item 21's `envelope_penalty`, now part of the
baseline) to find which ones carried the critic fix. This is the
right order — ablate *from* something that works — and it is the part the
previous arc never reached.

Both jobs report the same row so they can be read side by side, and both
carry the rule 4 columns (`worst_slip_deg`, `envelope_occupancy`) that item
20 showed were the difference between a real result and a measurement of
tyre-model exploitation.

Budget: 20M steps per variant (76 updates, ~3,040 value-head gradient steps
— above the ~1,520 that starved the critic, below v2's full 6,080). v2's own
EV crossed D6's 0.3 gate by update ~30 and its eval peaked at 24-40, so 76
updates is enough to see both the critic's health and the peak. Stated as a
budget choice, not assumed sufficient: a variant that would only separate
itself after update 76 is not distinguished here, and the summary says so.

    python -m experiments.tracks_pilot.v2_variants --job envelope
    python -m experiments.tracks_pilot.v2_variants --job ablation
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.ppo import PPOConfig, train
from experiments.tracks_pilot import spa_ppo_v2 as V2

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

TOTAL_STEPS = 20_000_000
N_SECTIONS = 24

#: Single-variable sweep of the term v2 left alone. 0.5 is v2's own value
#: (the control); the rest escalate toward "sliding costs more than the
#: progress it buys". At 17.8 deg slip the penalty is
#: envelope_penalty * 5.8/12 per step against ~0.6/step of progress, so 0.5
#: charges ~0.24 and 6.0 charges ~2.9 -- crossing from "cheaper than sliding"
#: to "dearer than sliding" somewhere in this range, which is what the sweep
#: is for.
ENVELOPE_LEVELS = (0.5, 2.0, 6.0, 15.0)

#: Item 23. The default preview reaches 55 m == 1.29 s of lookahead at the
#: 42.7 m/s the trained policy actually reaches, while braking from there to a
#: 10 m/s hairpin needs ~89 m. Above ~32 m/s the car is structurally blind to
#: what it must brake for -- which no reward coefficient can fix, and which is
#: consistent with five runs of coefficient tuning failing to move the 100%
#: crash rate. These extend the horizon past the braking distance at the
#: speeds actually reached. The control is `env6` (default 55 m), already run
#: at this exact budget and config in item 21.
PREVIEW_SETS = {
    "prev120": (5.0, 15.0, 30.0, 50.0, 75.0, 120.0),          # same 6 points
    "prev250": (10.0, 25.0, 45.0, 70.0, 100.0, 140.0, 190.0, 250.0),
}

#: Each entry reverts ONE v2 change to its pre-v2 value. `ppo` keys go to
#: PPOConfig, everything else to EnvConfig.
ABLATIONS = {
    "v2_baseline":        {},
    "minus_progress_scale": {"env": {"progress_scale": 1.5}},
    "minus_small_offtrack": {"env": {"off_track_penalty": 500.0}},
    "minus_small_stall":    {"env": {"stall_penalty": 150.0}},
    "minus_edge_penalty":   {"env": {"edge_penalty": 0.0}},
    "minus_strong_envelope": {"env": {"envelope_penalty": 0.5}},
    "minus_spawn_speed":    {"env": {"spawn_speed_from_curvature": False}},
    "minus_short_gamma":    {"ppo": {"gamma": 0.9995}},
    "minus_more_updates":   {"ppo": {"n_envs": 1024}},
}


def run_variant(label: str, env_over: dict, ppo_over: dict,
               total_steps: int = TOTAL_STEPS) -> dict:
    n_envs = ppo_over.get("n_envs", V2.N_ENVS)
    ppo_kw = dict(total_steps=total_steps, n_envs=n_envs,
                  rollout_steps=V2.ROLLOUT_STEPS,
                  gamma=V2.GAMMA, seed=V2.SEED,
                  eval_every=V2.EVAL_EVERY, eval_episodes=V2.EVAL_EPISODES)
    ppo_kw.update(ppo_over)          # any PPOConfig field, not just gamma/n_envs
    cfg = PPOConfig(**ppo_kw)
    n_upd = total_steps // (n_envs * V2.ROLLOUT_STEPS)
    print(f"\n=== {label} ===  env={env_over or '{}'} ppo={ppo_over or '{}'}  "
         f"({n_upd} updates, {n_upd * cfg.epochs * cfg.minibatches:,} grad steps)",
         flush=True)

    t0 = time.time()
    res = train(make_batched_env=lambda n: V2.make_batched_env(n, env_over=env_over),
               cfg=cfg, make_eval_env=lambda: V2.make_eval_env(env_over))
    wall = time.time() - t0
    h = res["history"]
    n = len(h)
    ev_tail = float(np.median([r["explained_variance"]
                              for r in h[-max(n // 5, 1):]]))

    sec = V2.evaluate_per_section(res["model"], n_sections=N_SECTIONS,
                                 env_over=env_over)
    d = np.array([r["distance_travelled"] for r in sec])
    slip = np.array([r["worst_slip_deg"] for r in sec])
    occ = np.array([r["envelope_occupancy"] for r in sec])

    row = {
        "label": label, "env_over": env_over, "ppo_over": ppo_over,
        "total_steps": total_steps, "n_updates": n, "wall_s": wall,
        "explained_variance_tail": ev_tail,
        "passes_d6_ev_gate": bool(ev_tail > 0.3),
        "best_update": res.get("best_update"),
        "best_eval_return": (res.get("best_eval") or {}).get("eval_return"),
        "section_distance_mean": float(d.mean()),
        "section_distance_std": float(d.std()),
        "section_off_track_rate": float(np.mean([r["off_track"] for r in sec])),
        "section_stall_rate": float(np.mean([r["stalled"] for r in sec])),
        "section_finish_rate": float(np.mean([r["finished"] for r in sec])),
        "section_worst_slip_deg": float(slip.max()),
        "sections_over_12deg": int((slip > 12.0).sum()),
        "section_envelope_occupancy": float(occ.mean()),
    }
    print(f"  EV={ev_tail:+.3f} {'PASS' if ev_tail > 0.3 else 'FAIL'}  "
         f"dist={d.mean():6.1f}  slip_max={slip.max():5.1f}  "
         f"over12={int((slip > 12.0).sum())}/{N_SECTIONS}  "
         f"occ={occ.mean():.4f}  wall={wall:.0f}s", flush=True)
    torch.save(res["model"].state_dict(), OUT / f"{label}_policy.pt")
    (OUT / f"{label}_sections.json").write_text(json.dumps(sec, indent=2) + "\n")
    (OUT / f"{label}_history.json").write_text(json.dumps(h, indent=2) + "\n")
    return row


def _table(rows):
    print(f"\n{'variant':24s} {'EV':>7} {'gate':>5} {'dist':>7} {'slip':>6} "
         f"{'>12deg':>7} {'occ':>8} {'off':>5}")
    for r in rows:
        print(f"{r['label']:24s} {r['explained_variance_tail']:>+7.3f} "
             f"{'PASS' if r['passes_d6_ev_gate'] else 'FAIL':>5} "
             f"{r['section_distance_mean']:>7.1f} "
             f"{r['section_worst_slip_deg']:>6.1f} "
             f"{r['sections_over_12deg']:>4d}/{N_SECTIONS} "
             f"{r['section_envelope_occupancy']:>8.4f} "
             f"{r['section_off_track_rate']:>5.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=("envelope", "ablation", "preview",
                                      "entropy"), required=True)
    ap.add_argument("--steps", type=int, default=TOTAL_STEPS)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []

    if a.job == "envelope":
        print("Item 21 -- envelope_penalty sweep (single variable over v2)")
        print("  rule 4 wants envelope_occupancy ~0; v2 sits at 0.0124, "
             "16/24 sections over the 12 deg bound.")
        for lv in ENVELOPE_LEVELS:
            rows.append(run_variant(f"env{lv:g}", {"envelope_penalty": lv}, {},
                                    a.steps))
    elif a.job == "entropy":
        print("Item 24 -- exploration schedule (single variable over the best config)")
        print("  D6's exploration_is_not_growing FAILS on every run: entropy")
        print("  rises -0.661 -> -0.514 in env6 while eval_return falls 315 ->")
        print("  137. F51's documented failure -- the entropy bonus beating the")
        print("  policy gradient, so the mean action never sharpens. entropy_anneal")
        print("  is 19h.D's pre-registered contingency and has never been tried.")
        rows.append(run_variant("ent_anneal", {}, {"entropy_anneal": True}, a.steps))
        rows.append(run_variant("ent_zero", {}, {"entropy_coef": 0.0}, a.steps))
    elif a.job == "preview":
        print("Item 23 -- preview horizon (single variable over v2+envelope 6.0)")
        print("  55 m is 1.29 s of lookahead at the 42.7 m/s reached; braking "
             "to a 10 m/s hairpin from there needs ~89 m.")
        print("  Control is env6 (default 55 m), already run at this budget.")
        for label, pv in PREVIEW_SETS.items():
            rows.append(run_variant(label, {"preview_distances": pv}, {},
                                    a.steps))
    else:
        print("Item 22 -- ablation: revert each v2 change individually")
        print("  v2 changed 7 things at once (deliberately). This finds which "
             "carried the critic fix, now that there is a working config.")
        for label, over in ABLATIONS.items():
            rows.append(run_variant(label, over.get("env", {}),
                                    over.get("ppo", {}), a.steps))

    _table(rows)
    out = OUT / f"v2_{a.job}_results.json"
    out.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"\n  wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
