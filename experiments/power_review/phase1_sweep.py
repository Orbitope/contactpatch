"""POWER-REVIEW Phase 1 — Episode 7's balance sweep and Episode 8's layout
sweep, re-measured across a {1x, 1.5x, 2x} power curve, three corner radii
(D-D), and both drive models side by side (D-A: flat cap and power-limited,
neither replacing the other).

This is cross-episode infrastructure, not itself an episode — it lives
outside experiments/epNN/ for the same reason POWER-REVIEW.md lives at the
repo root rather than inside one episode's directory. Episodes 7 and 8's own
run.py are untouched and remain the record of what was published (rule:
"Episodes 1-14 stand as measured").

Every solve is warm-started from the nearest already-converged neighbour
along whichever axis changed least (design point, then power, then drive
model; track changes always cold-start, since a different corner radius is
the biggest jump in the grid). Every solve is convergence-gated (F39): only
Solve_Succeeded results are quotable, and this script tags every row with
its own convergence status rather than silently dropping failures.

    python -m experiments.power_review.phase1_sweep --pilot
        One track (long_exit), one power (1x), both drive models, balance
        sweep only. Minutes, not hours -- validates the pipeline before the
        full grid is asked to run.

    python -m experiments.power_review.phase1_sweep --axis balance
    python -m experiments.power_review.phase1_sweep --axis layout
    python -m experiments.power_review.phase1_sweep --axis both
        The full {1x,1.5x,2x} x {hairpin,long_exit,fast_sweep} x
        {flat,power-limited} grid for the chosen axis (axes). Hours.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace

import numpy as np

from experiments.common import ROOT
from physics import schema
from physics import track as T
from physics.double_track import DoubleTrackBackend
from physics.double_track import understeer_gradient as ug_dt
from physics.optimal_control import Limits, Solution, solve_min_time

# ---------------------------------------------------------------------------
# Grid definition
# ---------------------------------------------------------------------------

#: The SAME entry speed on every track (32 m/s -- Episodes 6/7/8's own
#: established value), deliberately, not a per-track guess: verified all
#: three converge cleanly at it with zero envelope occupancy before
#: adopting it, and using one entry speed means track geometry is the only
#: thing that varies between tracks rather than track geometry AND an
#: arbitrary per-track entry speed both varying at once.
ENTRY_SPEED = {"hairpin": 32.0, "long_exit": 32.0, "fast_sweep": 32.0}
NODES = 100
MAX_ITER = 3000

#: 1x anchored to RV-1's real power (D-B, [SOURCED]); the flat cap's own 1x is
#: the existing DRIVE_MAX (4500 N, continuity with F43/F44/F49 -- D-A's whole
#: point is that these are two DIFFERENT conventions and neither silently
#: overwrites the other).
P_1X_WATTS = 174_000.0
DRIVE_MAX_1X_N = 4500.0
POWER_MULTIPLIERS = (1.0, 1.5, 2.0)
POWER_LABELS = ("1x", "1.5x", "2x")

TRACKS = {"hairpin": T.hairpin, "long_exit": T.long_exit,
          "fast_sweep": T.fast_sweep}
DRIVE_MODELS = ("flat", "power_limited")

FRONT_FRACTIONS = (0.40, 0.47, 0.54, 0.61, 0.65)
NOMINAL_FRACTION = 0.54

SKIDPAD_RADIUS = 30.0
SKIDPAD_SPEEDS = np.arange(5.0, 19.0, 0.25)


#: A drive_max large enough to never bind for "power_limited" mode, so
#: drive_power alone governs. This was originally left at Limits' own
#: default (4500 N) on the mistaken belief that it matched the 15 kN OC
#: default -- it does not (that is brake_max's default, not drive_max's) --
#: and the result was 4500 N silently acting as the real constraint at every
#: power level, since P/v never dropped that low at any speed these tracks
#: reach. Caught by checking WHY 1.5x and 2x produced bit-identical results
#: rather than assuming the sweep had nothing left to show at high power.
#: Set comfortably above the worst case: 2x power (348 kW) at v_min (8 m/s)
#: is 43,500 N; 100,000 N leaves no room for ambiguity.
_NON_BINDING_DRIVE_MAX_N = 100_000.0


def limits_for(mult: float, model: str) -> Limits:
    if model == "flat":
        return Limits(drive_max=DRIVE_MAX_1X_N * mult)
    if model == "power_limited":
        return Limits(drive_max=_NON_BINDING_DRIVE_MAX_N,
                      drive_power=P_1X_WATTS * mult)
    raise ValueError(model)


def understeer_gradient(params: schema.VehicleParams) -> float:
    b = DoubleTrackBackend(params)
    k, _ = ug_dt(b.skidpad_sweep(SKIDPAD_RADIUS, SKIDPAD_SPEEDS))
    return k


def solve_one(track, params: schema.VehicleParams, lim: Limits,
              entry_speed: float, warm_start: Solution | None) -> Solution:
    q = solve_min_time(track, params, n_nodes=NODES, entry_speed=entry_speed,
                       four_wheel=True, diff="ideal", limits=lim,
                       warm_start=warm_start, max_iter=MAX_ITER)
    if not q.success and warm_start is not None:
        # One retry, cold, at double the budget -- the same fallback ep07/08
        # use, since a bad warm start can trap the solver worse than none.
        q2 = solve_min_time(track, params, n_nodes=NODES,
                            entry_speed=entry_speed, four_wheel=True,
                            diff="ideal", limits=lim, warm_start=None,
                            max_iter=2 * MAX_ITER)
        if q2.success:
            q = q2
    return q


# ---------------------------------------------------------------------------
# Balance axis (Episode 7's grid)
# ---------------------------------------------------------------------------

def sweep_balance(track_name: str, power_label: str, mult: float,
                  drive_model: str, entry_speed: float, log) -> dict:
    p = schema.RV_1
    track = TRACKS[track_name]()
    lim = limits_for(mult, drive_model)
    order = ([NOMINAL_FRACTION]
             + sorted((f for f in FRONT_FRACTIONS if f < NOMINAL_FRACTION),
                     reverse=True)
             + sorted(f for f in FRONT_FRACTIONS if f > NOMINAL_FRACTION))
    sols, rows = {}, {}
    for drive in ("fwd", "rwd"):
        seed = None
        for ff in order:
            near = min((g[1] for g in sols if g[0] == drive and sols[g].success),
                      key=lambda g: abs(g - ff), default=None)
            start = (sols[("fwd", ff)] if drive == "rwd"
                    and ("fwd", ff) in sols and sols[("fwd", ff)].success
                    else sols[(drive, near)] if near is not None else seed)
            params = replace(p, front_mass_fraction=ff, drive=drive)
            t0 = time.time()
            q = solve_one(track, params, lim, entry_speed, start)
            sols[(drive, ff)] = q
            k = understeer_gradient(params)
            tag = f"{drive}_{ff:.2f}"
            rows[tag] = {
                "time_s": q.time, "converged": q.success,
                "solver_status": q.solver_status,
                "envelope_occupancy": q.envelope_occupancy(),
                "understeer_gradient_deg_per_g": k,
                "dt_ds": q.dt_ds.tolist(), "s": q.s.tolist(),
                "wall_s": time.time() - t0,
            }
            log(f"    {track_name}/{power_label}/{drive_model} {tag}: "
                f"{'ok' if q.success else 'FAILED'} {q.time:.3f}s "
                f"({rows[tag]['wall_s']:.0f}s wall)")
            if seed is None and q.success:
                seed = q
    return rows


# ---------------------------------------------------------------------------
# Layout axis (Episode 8's grid)
# ---------------------------------------------------------------------------

def sweep_layout(track_name: str, power_label: str, mult: float,
                 drive_model: str, entry_speed: float, log) -> dict:
    track = TRACKS[track_name]()
    lim = limits_for(mult, drive_model)
    names = ["front_mid_rwd"] + [k for k in schema.LAYOUT_ARCHETYPES
                                 if k != "front_mid_rwd"]
    rows, seed = {}, None
    for name in names:
        params = schema.LAYOUT_ARCHETYPES[name]
        t0 = time.time()
        q = solve_one(track, params, lim, entry_speed, seed)
        k = understeer_gradient(params)
        rows[name] = {
            "time_s": q.time, "converged": q.success,
            "solver_status": q.solver_status,
            "envelope_occupancy": q.envelope_occupancy(),
            "understeer_gradient_deg_per_g": k,
            "dt_ds": q.dt_ds.tolist(), "s": q.s.tolist(),
            "wall_s": time.time() - t0,
        }
        log(f"    {track_name}/{power_label}/{drive_model} {name}: "
            f"{'ok' if q.success else 'FAILED'} {q.time:.3f}s "
            f"({rows[name]['wall_s']:.0f}s wall)")
        if seed is None and q.success:
            seed = q
    return rows


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true",
                    help="long_exit, 1x only, both drive models, balance only")
    ap.add_argument("--axis", choices=("balance", "layout", "both"),
                    default="both")
    ap.add_argument("--models", choices=("flat", "power_limited", "both"),
                    default="both",
                    help="re-run only one drive model and MERGE into the "
                         "existing phase1_results.json, leaving the other "
                         "model's already-verified results untouched")
    args = ap.parse_args()

    # Not experiments/epNN/out/ -- this is cross-episode infrastructure, same
    # reason POWER-REVIEW.md lives at the repo root rather than in one
    # episode's directory.
    out = ROOT / "experiments" / "power_review" / "out"
    out.mkdir(parents=True, exist_ok=True)

    models = list(DRIVE_MODELS) if args.models == "both" else [args.models]

    if args.pilot:
        tracks, powers = ["long_exit"], [(1.0, "1x")]
        axes = ["balance"]
    else:
        tracks = list(TRACKS)
        powers = list(zip(POWER_MULTIPLIERS, POWER_LABELS))
        axes = ["balance", "layout"] if args.axis == "both" else [args.axis]

    suffix = "_pilot" if args.pilot else ""
    path = out / f"phase1_results{suffix}.json"
    # Merge mode: start from what is already on disk (a prior full run) so a
    # single-model re-run doesn't discard the other model's already-verified
    # results -- the flat-cap half of this grid was unaffected by the
    # drive_max bug and re-running it would just burn ~30 minutes reproducing
    # numbers already on disk.
    if args.models != "both" and path.exists():
        results = json.loads(path.read_text())
        print(f"  merging into existing {path}")
    else:
        results = {"config": {}, "balance": {}, "layout": {}}
    results["config"].update({
        "tracks": tracks, "powers": [p[1] for p in powers],
        "drive_models": list(DRIVE_MODELS), "axes": axes,
        "nodes": NODES, "max_iter": MAX_ITER,
        "p_1x_watts": P_1X_WATTS, "drive_max_1x_n": DRIVE_MAX_1X_N,
    })

    print(f"Phase 1 sweep — tracks={tracks} powers={[p[1] for p in powers]} "
          f"models={models} axes={axes}")
    t_start = time.time()

    for track_name in tracks:
        entry_speed = ENTRY_SPEED[track_name]
        for mult, power_label in powers:
            for drive_model in models:
                key = f"{track_name}|{power_label}|{drive_model}"
                if "balance" in axes:
                    print(f"\n  balance: {key}")
                    results["balance"][key] = sweep_balance(
                        track_name, power_label, mult, drive_model,
                        entry_speed, print)
                if "layout" in axes:
                    print(f"\n  layout: {key}")
                    results["layout"][key] = sweep_layout(
                        track_name, power_label, mult, drive_model,
                        entry_speed, print)

    results["wall_clock_s"] = results.get("wall_clock_s", 0.0) + (time.time() - t_start)
    path.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\n  wrote {path}  ({time.time()-t_start:.0f}s wall this run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
