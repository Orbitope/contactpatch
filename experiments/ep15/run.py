"""Episode 15 — is chassis tuning about to be automated away?

Season 2 measured the unflattened baseline: balance swings the understeer
gradient by over a degree per g and barely moves lap time (F44 — corrected,
see F99); polar moment barely shows up in a lap time at all (F49 — also
corrected). Season 4 built a controller that changes what the car does
mid-corner. This episode asks the question that answer *lets* you ask: if
the car can compensate for its own layout in real time, does the layout
still matter?

**The prerequisite this episode needed and did not have until now.**
POWER-REVIEW Phase 1 (F100) found both design axes are real but small at 1x
power (228 hp) and grow monotonically 2.3-8x by 2x power (~470 hp) — a
sensitivity baseline that actually varies, which a flat 1x measurement
alone could not show. Phase 2 (F101) found torque vectoring's own worth
grows the same way, from a few percent to more than doubling the cornering
limit, for the same reason: a passive differential is overwhelmed by real
power where an active one is not. This episode is the two put together:
does TV flatten design sensitivity, and does the answer depend on power the
same way both of its ingredients did?

**Protocol.** Every design point driven by the SAME closed-loop driver
(``physics/driver.py``) at the SAME track (``long_exit``), TV off (open
differential) and TV on (the four-wheel allocator, Episode 13's ``tv4``),
at RV-1's own power (1x, "your actual GR86") and at 2x (where F101 found
TV's worth balloons). The metric is D11's: the highest ``grip_use`` that
still produces a valid lap, swept per design point, bisected to 0.002. The
spread of that limit across a design sweep is what "sensitivity" means
here; whether TV flattens it is whether that spread shrinks with TV on.

Two axes, both inherited unchanged from where they were measured:

* **Balance** — Episode 7's five front-mass fractions, both drivetrains.
* **Layout** — Episode 8's five engine-position archetypes.

**Fidelity: rung 2** (rule 15). This is still a double-track model with no
roll camber, roll steer or compliance steer — the terms that make up most
of a real car's understeer (F29, F73) — driven by a tracker that never
brakes in a corner or trades line for exit. Whatever this episode finds
about "flattening" is a trend on a model that reproduces roughly 5% of a
real car's understeer gradient, not a claim about a real 911.

    python -m experiments.ep15.run
    python -m experiments.ep15.run --figures-only
    python -m experiments.ep15.run --quick
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import replace

import numpy as np

from diagnostics.common import Report
from experiments.common import episode_dir, write
from experiments.ep13.run import Car, measure, section_time
from experiments.power_review.phase2_sweep import driver_kw_for, power_lap, power_limit_of
from physics import schema
from physics.track import long_exit

FRONT_FRACTIONS = (0.40, 0.47, 0.54, 0.61, 0.65)
POWER_LEVELS = ((1.0, "1x"), (2.0, "2x"))
TV_CONDITIONS = ("open", "tv4")   # off, on
TV_LABEL = {"open": "TV off (open diff)", "tv4": "TV on (allocator)"}


def balance_point(ff: float, drive: str) -> schema.VehicleParams:
    return replace(schema.RV_1, front_mass_fraction=ff, drive=drive)


def limit_for(params: schema.VehicleParams, tv_name: str, track, mult: float,
             model: str = "flat") -> tuple[float, float, float]:
    """(grip_use limit, lap_time at it, section_time at it)."""
    ref = measure(params)
    car = Car(tv_name, params, ref)
    plan_n, clip = driver_kw_for(mult, model)
    limit = power_limit_of(car, track, ref, plan_n, clip)
    if not np.isfinite(limit):
        return limit, float("nan"), float("nan")
    lp = power_lap(car, track, ref, limit, plan_n, clip)
    return limit, lp.lap_time, section_time(lp)


def sweep_axis(design_points: dict, track, mult: float, log) -> dict:
    """design_points: name -> VehicleParams (drivetrain already baked in)."""
    out = {}
    for tv in TV_CONDITIONS:
        for name, params in design_points.items():
            t0 = time.time()
            limit, lap_t, sec_t = limit_for(params, tv, track, mult)
            out[f"{tv}|{name}"] = {"limit_grip_use": limit, "lap_time": lap_t,
                                   "section_time": sec_t,
                                   "wall_s": time.time() - t0}
            log(f"    {tv:6s} {name:10s} limit={limit:.3f}  lap={lap_t:.3f}s  "
                f"({time.time()-t0:.0f}s)")
    return out


def spread(rows: dict, tv: str, names) -> float:
    vals = [rows[f"{tv}|{n}"]["limit_grip_use"] for n in names]
    vals = [v for v in vals if np.isfinite(v)]
    return max(vals) - min(vals) if len(vals) > 1 else float("nan")


def main() -> int:
    out = episode_dir(15)
    if "--figures-only" in sys.argv:
        figures(out)
        return 0
    quick = "--quick" in sys.argv
    track = long_exit()
    fracs = (0.40, 0.54, 0.65) if quick else FRONT_FRACTIONS
    archetypes = (["front_mid_rwd", "mid_rwd"] if quick
                 else list(schema.LAYOUT_ARCHETYPES))

    print("Episode 15 — Is chassis tuning about to be automated away?")
    print(f"  balance: {len(fracs)} fractions x 2 drivetrains x "
          f"{len(TV_CONDITIONS)} TV states x {len(POWER_LEVELS)} power levels")
    print(f"  layout: {len(archetypes)} archetypes x {len(TV_CONDITIONS)} "
          f"TV states x {len(POWER_LEVELS)} power levels\n")

    t_start = time.time()
    results = {"config": {"fractions": list(fracs), "archetypes": archetypes,
                          "powers": [p[1] for p in POWER_LEVELS]},
              "balance": {}, "layout": {}}

    for mult, power_label in POWER_LEVELS:
        print(f"  == {power_label} power ==")
        print("  balance (rwd):")
        rwd_points = {f"{ff:.2f}": balance_point(ff, "rwd") for ff in fracs}
        rwd_rows = sweep_axis(rwd_points, track, mult, print)
        print("  balance (fwd):")
        fwd_points = {f"{ff:.2f}": balance_point(ff, "fwd") for ff in fracs}
        fwd_rows = sweep_axis(fwd_points, track, mult, print)
        results["balance"][power_label] = {"rwd": rwd_rows, "fwd": fwd_rows}

        print("  layout:")
        layout_points = {a: schema.LAYOUT_ARCHETYPES[a] for a in archetypes}
        layout_rows = sweep_axis(layout_points, track, mult, print)
        results["layout"][power_label] = layout_rows
        print()

    # -- does TV flatten sensitivity? -----------------------------------
    names_frac = [f"{ff:.2f}" for ff in fracs]
    print("  Sensitivity spread (grip_use limit, max-min across the sweep):")
    flatten = {"balance": {}, "layout": {}}
    for _, power_label in POWER_LEVELS:
        for drive in ("rwd", "fwd"):
            rows = results["balance"][power_label][drive]
            off = spread(rows, "open", names_frac)
            on = spread(rows, "tv4", names_frac)
            flatten["balance"][f"{power_label}|{drive}"] = {"off": off, "on": on}
            print(f"    balance {power_label}/{drive}: TV-off={off:.3f}  "
                  f"TV-on={on:.3f}  ({'flattens' if on < off else 'does not flatten'})")
        rows = results["layout"][power_label]
        off = spread(rows, "open", archetypes)
        on = spread(rows, "tv4", archetypes)
        flatten["layout"][power_label] = {"off": off, "on": on}
        print(f"    layout  {power_label}: TV-off={off:.3f}  TV-on={on:.3f}  "
              f"({'flattens' if on < off else 'does not flatten'})")
    results["flattening"] = flatten
    results["wall_clock_s"] = time.time() - t_start

    # -- checks -----------------------------------------------------------
    report = Report(
        "D-ep15", "Is chassis tuning about to be automated away?",
        "Season 2 measured design sensitivity without a controller in the "
        "loop; this asks whether an active one flattens it, and whether the "
        "answer depends on power the way both of its ingredients (F100, "
        "F101) did.",
    )
    report.section("Did the sweeps produce usable data?")
    n_finite = sum(1 for axis in ("balance", "layout")
                   for _, power_label in POWER_LEVELS
                   for k, v in (results[axis][power_label].items()
                               if axis == "layout" else
                               {**results[axis][power_label]["rwd"],
                                **results[axis][power_label]["fwd"]}.items())
                   if np.isfinite(v["limit_grip_use"]))
    n_total = sum(1 for axis in ("balance", "layout")
                  for _, power_label in POWER_LEVELS
                  for k, v in (results[axis][power_label].items()
                              if axis == "layout" else
                              {**results[axis][power_label]["rwd"],
                               **results[axis][power_label]["fwd"]}.items()))
    report.add("most_design_points_produced_a_valid_limit", n_finite >= 0.7 * n_total,
              f"{n_finite}/{n_total} design points (both axes, both TV states, "
              f"both power levels) found a finite grip_use limit.",
              value=n_finite / n_total if n_total else 0.0)

    report.section("Does TV flatten design sensitivity, and does that depend on power?")
    for axis in ("balance", "layout"):
        for key, v in flatten[axis].items():
            report.add(f"{axis}_{key}_flattens_or_is_explained",
                      True,
                      f"{axis} {key}: TV-off spread {v['off']:.3f}, "
                      f"TV-on spread {v['on']:.3f} — "
                      f"{'flattens' if v['on'] < v['off'] else 'does not flatten'}. "
                      "This check always passes; it exists to put the direction "
                      "in the report rather than only in prose.",
                      value=v["on"] - v["off"])

    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    md = report.write_markdown(command="python -m experiments.ep15.run")
    report.write()
    report.print_summary(verbose="-v" in sys.argv)
    print(f"\n  write-up {md}")
    print(f"  {(out / 'results.json').name}")
    print(f"\n  {results['wall_clock_s']:.0f}s wall total")
    return 0 if report.ok else 1


def figures(out) -> None:
    pass


if __name__ == "__main__":
    sys.exit(main())
