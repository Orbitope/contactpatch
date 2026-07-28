"""Episode 8 — Front, mid, or rear engine. Season 2 payoff.

Weight distribution says *where* the mass is. Polar moment says *how far from the
middle* it is. Those are different questions, and Episode 7 deliberately froze the
second one. This is where it moves.

Three parts:

1. **Two cars, identical balance, different yaw inertia.** The controlled
   comparison Episode 7 could not make, because there balance and inertia were
   confounded by construction.
2. **The surface** over balance x inertia, with the five layout archetypes marked
   on it. This is the figure that shows the two axes are not the same axis.
3. **A minimum-time corner at each archetype**, to ask whether any of this shows
   up in a lap time when the driver already knows what is going to happen.

The transient work uses the bicycle model, matching D4 — which validated its step
response against an exactly integrated linear model to 3%. Yaw inertia is a
rigid-body property and lateral load transfer does not change it, so the four-wheel
model buys nothing here and D4's validation carries over. The minimum-time solves
use the four-wheel model, as Episodes 6 and 7 do.

Run::

    python -m experiments.ep08.run
    python -m experiments.ep08.run --figures-only
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import replace

import numpy as np

from diagnostics.D4_transient import step_response
from experiments.common import episode_dir, write
from physics import schema
from physics import track as T
from physics.bicycle import BicycleBackend
from physics.double_track import DoubleTrackBackend
from physics.double_track import understeer_gradient as ug_dt
from physics.optimal_control import solve_min_time
from viz import inertia_figures

ENTRY_SPEED = 32.0
NODES = 100
MAX_ITER = 8000
CORNERS = ("fl", "fr", "rl", "rr")

#: The controlled pair: same balance, inertia at the ends of the documented
#: range. 0.43 front is the mid-engine archetype's balance, chosen so the pair
#: brackets a layout that actually exists.
PAIR_FRONT = 0.43
PAIR_MULTS = (0.80, 1.22)

#: Surface grid. Both ranges are the documented design-sweep bounds from
#: ``docs/vehicle-reference-parameters.md`` §2, so nothing here is invented.
SURFACE_FRONT = (0.38, 0.43, 0.48, 0.53, 0.58, 0.62)
SURFACE_IZZ = (0.75, 0.90, 1.05, 1.20, 1.40)

SKIDPAD_RADIUS = 30.0
SKIDPAD_SPEEDS = np.arange(5.0, 19.0, 0.25)


def _resp(params) -> dict:
    """Step-steer metrics for one car.

    Drag is switched off exactly as D4 does it: over the response window it
    bleeds speed, and a car that settles later then sits at a different average
    speed, which moves the steady-state yaw rate by more than the effect being
    measured.
    """
    r = step_response(BicycleBackend(replace(params, c_d=0.0)))
    return {k: float(r[k]) for k in
            ("rise_time", "peak_time", "overshoot", "settling_time", "final")}


def figures(out) -> None:
    results = json.loads((out / "results.json").read_text())
    meta = json.loads((out / "meta.json").read_text())
    traces = dict(np.load(out / "traces.npz"))
    write(out / "01-two-cars-same-balance.svg",
          inertia_figures.pair_figure(results, meta, traces))
    write(out / "02-the-two-axes.svg",
          inertia_figures.surface_figure(results, meta))
    write(out / "03-inertia-card.svg",
          inertia_figures.inertia_card(results, meta, traces))


def main() -> int:
    out = episode_dir(8)
    if "--figures-only" in sys.argv:
        figures(out)
        return 0
    p = schema.RV_1
    track = T.long_exit()
    print("Episode 8 — Front, mid, or rear engine")

    # --- part 1: identical balance, different inertia ----------------------
    print(f"\n  Two cars at {PAIR_FRONT:.2f} front, inertia "
          f"{PAIR_MULTS[0]:.2f}x vs {PAIR_MULTS[1]:.2f}x:")
    pair, pair_traces = {}, {}
    for mult in PAIR_MULTS:
        v = replace(p, front_mass_fraction=PAIR_FRONT, i_zz=p.i_zz * mult)
        full = step_response(BicycleBackend(replace(v, c_d=0.0)))
        pair[f"{mult:.2f}"] = {**_resp(v), "i_zz": v.i_zz,
                               "i_zz_multiplier": mult}
        pair_traces[f"pair_{mult:.2f}".replace(".", "")] = full["yaw_rate"]
        pair_traces["pair_t"] = full["t"]
        print(f"    {mult:.2f}x  rise {1000*pair[f'{mult:.2f}']['rise_time']:5.0f} ms  "
              f"overshoot {100*pair[f'{mult:.2f}']['overshoot']:5.2f}%  "
              f"settles {1000*pair[f'{mult:.2f}']['settling_time']:5.0f} ms")
    k_pair, _ = ug_dt(DoubleTrackBackend(
        replace(p, front_mass_fraction=PAIR_FRONT)
    ).skidpad_sweep(SKIDPAD_RADIUS, SKIDPAD_SPEEDS))
    print(f"    both have the same understeer gradient: {k_pair:+.2f} deg/g")

    # --- part 2: the surface ------------------------------------------------
    print("\n  Response surface over balance x inertia "
          f"({len(SURFACE_FRONT)}x{len(SURFACE_IZZ)} step-steer runs):")
    surface = {}
    for ff in SURFACE_FRONT:
        for mult in SURFACE_IZZ:
            v = replace(p, front_mass_fraction=ff, i_zz=p.i_zz * mult)
            surface[f"{ff:.2f}_{mult:.2f}"] = _resp(v)
    k_of = {}
    for ff in SURFACE_FRONT:
        k_of[f"{ff:.2f}"], _ = ug_dt(DoubleTrackBackend(
            replace(p, front_mass_fraction=ff)
        ).skidpad_sweep(SKIDPAD_RADIUS, SKIDPAD_SPEEDS))
    rises = [surface[k]["rise_time"] for k in surface]
    print(f"    rise time spans {1000*min(rises):.0f}-{1000*max(rises):.0f} ms "
          f"across the grid")

    # --- part 3: the archetypes --------------------------------------------
    print("\n  The five layouts:")
    arch = {}
    seed = solve_min_time(track, n_nodes=NODES, entry_speed=ENTRY_SPEED)
    # Solve the layout closest to the reference car FIRST, then seed every other
    # layout from that converged answer. Chaining down the dict in declaration
    # order instead meant a failure early on was inherited by everything after
    # it — the same mistake Episode 7's first pass made, and the reason three of
    # five archetypes stopped on the iteration limit.
    # Solve the EASIEST layout first and seed everything from it. The front-drive
    # four-wheel problem converges in ~13 s where the rear-drive ones take
    # 250-350 s, consistently, across Episodes 6 and 8 — so it is the natural
    # continuation base. Ordering by "closest to the reference car" instead put
    # front_mid_rwd first on a cold bicycle seed and it failed, having converged
    # in the previous run when it inherited a four-wheel answer.
    order = (["front_fwd"]
             + [k for k in schema.LAYOUT_ARCHETYPES if k != "front_fwd"])
    base = None
    for name in order:
        v = schema.LAYOUT_ARCHETYPES[name]
        t0 = time.time()
        q = solve_min_time(track, params=v, n_nodes=NODES,
                           entry_speed=ENTRY_SPEED, four_wheel=True,
                           diff="ideal", warm_start=base or seed,
                           max_iter=MAX_ITER)
        if not q.success and base is not None:
            # one retry from the base answer rather than accepting a number that
            # cannot be quoted; a failed solve costs nothing but time
            q2 = solve_min_time(track, params=v, n_nodes=NODES,
                                entry_speed=ENTRY_SPEED, four_wheel=True,
                                diff="ideal", warm_start=base,
                                max_iter=2 * MAX_ITER)
            if q2.success:
                q = q2
                print(f"      (retried {name} at {2*MAX_ITER} iterations — "
                      f"converged)")
        if base is None and q.success:
            base = q
        k, _ = ug_dt(DoubleTrackBackend(v).skidpad_sweep(SKIDPAD_RADIUS,
                                                         SKIDPAD_SPEEDS))
        arch[name] = {
            **_resp(v),
            "front_mass_fraction": v.front_mass_fraction,
            "i_zz_multiplier": v.i_zz / p.i_zz,
            "drive": v.drive,
            "understeer_gradient_deg_per_g": k,
            "time_s": q.time, "solver_status": q.solver_status,
            "converged": q.success,
            "envelope_occupancy": q.envelope_occupancy(),
        }
        print(f"    {name:15s} {v.front_mass_fraction:.2f} front, "
              f"{v.i_zz/p.i_zz:.2f}x inertia, {v.drive}  "
              f"rise {1000*arch[name]['rise_time']:4.0f} ms  "
              f"K {k:+.2f}  {q.time:7.3f} s {'' if q.success else '(not conv)'}"
              f"  ({time.time()-t0:.0f}s)")

    results = {
        "entry_speed_ms": ENTRY_SPEED, "n_nodes": NODES,
        "track": track.name,
        "pair_front_mass_fraction": PAIR_FRONT,
        "pair_multipliers": list(PAIR_MULTS),
        "pair": pair,
        "pair_understeer_gradient_deg_per_g": k_pair,
        "surface_front": list(SURFACE_FRONT),
        "surface_izz": list(SURFACE_IZZ),
        "surface": surface,
        "K_deg_per_g": k_of,
        "archetypes": arch,
        "held_fixed": ("mass, wheelbase, track, CoM height, tires, roll "
                       "stiffness distribution. Balance and yaw inertia are the "
                       "two axes and they move independently, which is the "
                       "point -- a real layout change moves both at once."),
        "note": ("Transient metrics use the bicycle model, matching D4, which "
                 "validated its step response against an exactly integrated "
                 "linear model to 3%. Yaw inertia is a rigid-body property and "
                 "lateral load transfer does not change it. Lap times use the "
                 "four-wheel model as Episodes 6 and 7 do."),
    }
    conv = {k: a for k, a in arch.items() if a["converged"]}
    results["archetypes_converged"] = sorted(conv)
    results["archetypes_not_converged"] = sorted(set(arch) - set(conv))
    times = [a["time_s"] for a in (conv or arch).values()]
    results["archetype_time_span_s"] = max(times) - min(times)
    results["archetype_time_span_is_converged_only"] = bool(conv)
    results["archetype_rise_span_ms"] = 1000.0 * (
        max(a["rise_time"] for a in arch.values())
        - min(a["rise_time"] for a in arch.values()))
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (out / "meta.json").write_text(json.dumps(seed.meta, indent=2) + "\n")
    np.savez(out / "traces.npz", **pair_traces)
    print("\n  traces.npz")

    figures(out)
    print()
    print(f"  lap time spans {results['archetype_time_span_s']:.3f} s across "
          f"{len(results['archetypes_converged'])} converged layouts, while rise "
          f"time spans {results['archetype_rise_span_ms']:.0f} ms across all five")
    if results["archetypes_not_converged"]:
        print("  WARNING: not converged, times excluded from the span (F39): "
              + ", ".join(results["archetypes_not_converged"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
