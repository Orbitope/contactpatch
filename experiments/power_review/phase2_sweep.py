"""POWER-REVIEW Phase 2 — Episode 13's five-configuration torque-vectoring
study, re-measured across a {1x, 1.5x, 2x} power curve and both drive models
(D-A), plus the brake-cap fix Phase 0 confirmed (BRAKE_MAX raised to the
tire's own demonstrated ~0.985 g, applied once, not swept -- braking
capacity is a tire/mass property, not an engine one).

Lives outside experiments/epNN/ for the same reason phase1_sweep.py does:
this is cross-episode infrastructure, and Episode 13's own run.py stays the
untouched record of what was published. `ep13.lap()` builds its
`SpeedProfile` from the MODULE-LEVEL `DRIVE_MAX`/`BRAKE_MAX` constants
directly rather than from any `Driver` field (confirmed the hard way —
overriding the Driver's clip alone did nothing, because the plan still
targeted the old cap) — so this script builds `SpeedProfile` and `Driver`
together from the same power-derived values, exactly what D-A requires.

    python -m experiments.power_review.phase2_sweep --pilot
        1x only, flat model, all 5 configurations. Minutes.
    python -m experiments.power_review.phase2_sweep
        The full {1x,1.5x,2x} x {flat,power-limited} grid.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

from experiments.common import ROOT
from experiments.ep13.run import (CONDITIONS, SHORT, Car, best_valid,
                                  measure, section_time)
from physics import schema
from physics.driver import Driver, SpeedProfile, TrackLocator, drive_lap
from physics.track import long_exit

#: Same anchor as Phase 1: 1x is RV-1's real power / the flat cap's existing
#: DRIVE_MAX, so the two models' 1x points are each continuous with
#: everything already published, per D-A's resolution.
P_1X_WATTS = 174_000.0
DRIVE_MAX_1X_N = 4500.0
#: Phase 0's brake-cap fix: BRAKE_MAX (12,000 N -> 0.899 g) sits below the
#: tire's own demonstrated ~0.985 g under the same combined-slip demands.
#: Raised once, independent of power level -- not a sweep axis.
BRAKE_MAX_FIXED_N = 0.985 * schema.G * schema.RV_1.mass
POWER_MULTIPLIERS = (1.0, 1.5, 2.0)
POWER_LABELS = ("1x", "1.5x", "2x")
DRIVE_MODELS = ("flat", "power_limited")

#: GU_LO was originally 0.70 (a reasonable floor for Episode 13's own five
#: configurations at 1x power). At higher power the open differential's real
#: limit can sit well below that -- checked directly: at 2x/flat it goes
#: "off track" at gu=0.70 AND 0.50 but finishes clean at 0.30 -- so a search
#: that gives up when its own floor is invalid was reporting nan for
#: configurations that have a perfectly real, lower limit. Lowered to 0.05,
#: comfortably below anything observed to fail.
GU_LO, GU_HI, GU_TOL = 0.05, 1.60, 0.002
SECTION = (55.0, 165.0)

_NON_BINDING_DRIVE_MAX_N = 100_000.0


def driver_kw_for(mult: float, model: str) -> dict:
    """Returns (plan_drive_n, clip_kwargs).

    ``plan_drive_n`` feeds ONLY the SpeedProfile's feedforward reference
    (``a_drive``) -- Driver.control()'s own docstring is explicit that the
    plan only has to be a reasonable starting point the PI loop corrects
    toward, not a physically exact prediction. ``clip_kwargs`` is what
    actually constrains the realised force each step.

    **Why these are different for power_limited, and a bug this was found
    fixing.** An earlier version fed the CLIP's own drive_max (100,000 N,
    deliberately non-binding so drive_power alone governs) into the PLAN's
    a_drive too -- a nonsensical 7.5 g planning target. The plan's forward
    pass then demanded near-instant acceleration back to cornering speed,
    the PI loop's error term saturated chasing an unreachable target, and
    the open differential -- with no torque management -- span at 49.9 deg
    of slip on a lap the flat model drove cleanly at the same aggression.
    Confirmed directly: the SAME power-limited clip with a SANE plan
    (``DRIVE_MAX_1X_N`` scaled, matching the flat model's own planning
    value) drives the identical lap clean, 3.1 deg of slip. The plan always
    uses the flat-cap-scaled value regardless of drive model; only the clip
    varies.
    """
    plan_drive_n = DRIVE_MAX_1X_N * mult
    if model == "flat":
        return plan_drive_n, {"drive_max": plan_drive_n, "brake_max": BRAKE_MAX_FIXED_N}
    if model == "power_limited":
        return plan_drive_n, {"drive_max": _NON_BINDING_DRIVE_MAX_N,
                              "brake_max": BRAKE_MAX_FIXED_N,
                              "drive_power": P_1X_WATTS * mult}
    raise ValueError(model)


def power_lap(car: Car, track, ref: dict, gu: float, plan_drive_n: float,
              clip_kw: dict, max_steps: int = 4000):
    """Mirrors ep13.lap(), except a_brake/a_drive are built from the SAME
    values the Driver's clip uses (for the flat model) or a sane reference
    (for power-limited -- see driver_kw_for's docstring), rather than from
    the module constants ep13.lap() reads directly."""
    mass = car.backend.params.mass
    brake_max = clip_kw.get("brake_max", 12000.0)
    prof = SpeedProfile(track, a_lat=gu * ref["a_lat"],
                        a_brake=min(brake_max / mass, gu * schema.G),
                        a_drive=plan_drive_n / mass)
    d = Driver(car.backend.params, prof, TrackLocator(track), **clip_kw)
    return drive_lap(car.backend, track, d, tv=car.tv, grip_use=gu,
                     max_steps=max_steps)


def power_limit_of(car: Car, track, ref: dict, plan_drive_n: float, clip_kw: dict,
                   lo=GU_LO, hi=GU_HI, tol=GU_TOL) -> float:
    if not power_lap(car, track, ref, lo, plan_drive_n, clip_kw).valid:
        return float("nan")
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if power_lap(car, track, ref, mid, plan_drive_n, clip_kw).valid:
            lo = mid
        else:
            hi = mid
    return lo


def run_one(track, ref: dict, mult: float, power_label: str, model: str,
           log) -> dict:
    plan_drive_n, clip_kw = driver_kw_for(mult, model)
    cars = {c: Car(c, schema.RV_1, ref) for c in CONDITIONS}
    limits, bests, rows = {}, {}, {}
    for c in CONDITIONS:
        t0 = time.time()
        limits[c] = power_limit_of(cars[c], track, ref, plan_drive_n, clip_kw)
        lp = power_lap(cars[c], track, ref, limits[c], plan_drive_n, clip_kw) \
            if np.isfinite(limits[c]) else None
        rows[c] = {
            "limit_grip_use": limits[c],
            "lap_time": lp.lap_time if lp else float("nan"),
            "section_time": section_time(lp) if lp else float("nan"),
            "wall_s": time.time() - t0,
        }
        log(f"    {power_label}/{model} {SHORT[c]:16s} limit={limits[c]:.3f}  "
            f"lap={rows[c]['lap_time']:.3f}s  ({rows[c]['wall_s']:.0f}s)")
    open_, tv4 = rows["open"], rows["tv4"]
    lap_gain = (100.0 * (open_["lap_time"] - tv4["lap_time"]) / open_["lap_time"]
               if np.isfinite(open_["lap_time"]) and np.isfinite(tv4["lap_time"])
               else float("nan"))
    sec_gain = (100.0 * (open_["section_time"] - tv4["section_time"])
               / open_["section_time"]
               if np.isfinite(open_["section_time"]) and np.isfinite(tv4["section_time"])
               else float("nan"))
    limit_gain = (100.0 * (tv4["limit_grip_use"] - open_["limit_grip_use"])
                 / open_["limit_grip_use"])
    return {"rows": rows, "lap_gain_pct": lap_gain, "section_gain_pct": sec_gain,
           "limit_gain_pct": limit_gain,
           "plan_drive_n": plan_drive_n, "clip_kw_summary": dict(clip_kw)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    args = ap.parse_args()

    out = ROOT / "experiments" / "power_review" / "out"
    out.mkdir(parents=True, exist_ok=True)

    track = long_exit()
    ref = measure(schema.RV_1)
    print(f"reference: K={ref['k_us']:.4f} a_lat={ref['a_lat']/schema.G:.3f}g "
          f"(brake_max fixed at {BRAKE_MAX_FIXED_N:.0f} N = "
          f"{BRAKE_MAX_FIXED_N/schema.RV_1.mass/schema.G:.3f} g, all configs)")

    powers = [(1.0, "1x")] if args.pilot else list(zip(POWER_MULTIPLIERS, POWER_LABELS))
    models = ["flat"] if args.pilot else list(DRIVE_MODELS)

    results = {"config": {"powers": [p[1] for p in powers], "models": models,
                          "p_1x_watts": P_1X_WATTS, "drive_max_1x_n": DRIVE_MAX_1X_N,
                          "brake_max_fixed_n": BRAKE_MAX_FIXED_N},
              "cells": {}}
    t0 = time.time()
    for mult, power_label in powers:
        for model in models:
            print(f"\n  {power_label}/{model}:")
            results["cells"][f"{power_label}|{model}"] = run_one(
                track, ref, mult, power_label, model, print)
    results["wall_clock_s"] = time.time() - t0

    suffix = "_pilot" if args.pilot else ""
    path = out / f"phase2_results{suffix}.json"
    path.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\n  wrote {path}  ({results['wall_clock_s']:.0f}s wall)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
