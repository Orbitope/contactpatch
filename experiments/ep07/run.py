"""Episode 7 — Where you put the weight.

Sweep the front mass fraction and re-solve the corner at each point. Mass, tires,
wheelbase, track and yaw inertia are all held fixed; the only thing that moves is
where the mass sits along the wheelbase.

**Yaw inertia is deliberately held constant.** Physically you cannot move an engine
without changing both balance and polar moment, and separating them is the whole
point of the split between this episode and Episode 8. Holding ``i_zz`` fixed here
means the result isolates balance, and is *not* a prediction about a real car whose
engine has moved.

Both drivetrains are swept, which the series plan does not ask for. It is here
because Episode 6 found front-wheel drive slower at fixed 54% front weight and
explicitly deferred the obvious objection: a real front-drive car puts its engine
over the driven wheels. This is that experiment.

Run::

    python -m experiments.ep07.run
    python -m experiments.ep07.run --figures-only
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import replace

import numpy as np

from experiments.common import episode_dir, write
from physics import schema
from physics import track as T
from physics.bicycle import BicycleBackend
from physics.double_track import DoubleTrackBackend
from physics.double_track import understeer_gradient as ug_dt
from physics.optimal_control import solve_min_time
from viz import balance_figures

ENTRY_SPEED = 32.0
NODES = 100                     # the grid where Ep 6's solves converge (F39)
MAX_ITER = 8000                 # rear drive needs far more than the 2000 default
CORNERS = ("fl", "fr", "rl", "rr")

#: Front mass fraction sweep. The series plan asks for 0.35-0.65; five points
#: spans it without spending an hour of solver time on a smooth curve.
#: **All of these except 0.54 are [ASSUMED] design variations, not RV-1.** The
#: reference sheet's own range is 0.53-0.56, so the ends of this sweep describe
#: hypothetical cars — which is the point of a design sweep.
FRONT_FRACTIONS = (0.40, 0.47, 0.54, 0.61, 0.65)
NOMINAL = 0.54

#: Skidpad settings for the understeer gradient, matching D3/D5 so the K values
#: here are comparable with Episodes 3 and 5 rather than a new measurement.
SKIDPAD_RADIUS = 30.0
SKIDPAD_SPEEDS = np.arange(5.0, 19.0, 0.25)


def _brake_release_s(sol) -> float:
    """Distance at which the car finally stops braking before the corner.

    'Brake point' in the plan's sense. Taken as the last node in the approach
    where longitudinal force is still meaningfully negative, so trailing the
    brakes into the corner shows up as a number larger than the corner start.

        Interpolated between nodes, not snapped to one. Taken as the last node it
    reported values on a 3.97 m grid, so the five designs came out at nodes 16, 17,
    17, 18, 19 and the whole 11.9 m spread was exactly three grid steps — a
    quantised number masquerading as a measurement. That is F47's apex defect in a
    different variable, and the fix is the same: interpolate onto the crossing.
    """
    fx = np.asarray(sol.controls["drive_force"], dtype=float)
    approach = sol.s < (T.ENTRY_STRAIGHT + 0.5 * T.CORNER_ARC)
    braking = np.where(approach & (fx < -100.0))[0]
    if not braking.size:
        return float("nan")
    i = int(braking[-1])
    if i + 1 >= fx.size:
        return float(sol.s[i])
    f0, f1 = fx[i], fx[i + 1]
    if f1 <= f0:                      # not a crossing; fall back to the node
        return float(sol.s[i])
    frac = (-100.0 - f0) / (f1 - f0)
    frac = min(max(frac, 0.0), 1.0)
    return float(sol.s[i] + frac * (sol.s[i + 1] - sol.s[i]))


def _summary(sol, k_deg_per_g) -> dict:
    pw = sol.per_wheel
    corner = sol.corner_mask
    exitm = sol.s > (T.ENTRY_STRAIGHT + T.CORNER_ARC)
    return {
        "time_s": sol.time,
        "understeer_gradient_deg_per_g": k_deg_per_g,
        "apex_fraction_through_corner": sol.apex_fraction_through_corner,
        "brake_release_s": _brake_release_s(sol),
        "min_speed_ms": float(sol.speed.min()),
        "exit_speed_ms": float(sol.speed[-1]),
        "mean_utilisation_in_corner": {
            c: float(pw["utilisation"][c][corner].mean()) for c in CORNERS},
        "mean_utilisation_on_exit": {
            c: float(pw["utilisation"][c][exitm].mean()) for c in CORNERS},
        "worst_slip_deg": math.degrees(float(max(
            np.abs(pw["alpha"][c]).max() for c in CORNERS))),
        "envelope_occupancy": sol.envelope_occupancy(),
        "solver_status": sol.solver_status,
        "converged": sol.success,
    }


def figures(out) -> None:
    """Rebuild every figure from what is on disk. No solving."""
    results = json.loads((out / "results.json").read_text())
    meta = json.loads((out / "meta.json").read_text())
    tr = dict(np.load(out / "traces.npz"))
    track = T.long_exit()
    write(out / "01-where-the-mass-sits.svg",
          balance_figures.balance_figure(results, meta))
    write(out / "02-the-line-moves.svg",
          balance_figures.line_shift_figure(results, meta, tr, track))
    write(out / "03-balance-card.svg",
          balance_figures.balance_card(results, meta))


def main() -> int:
    out = episode_dir(7)
    if "--figures-only" in sys.argv:
        figures(out)
        return 0
    p = schema.RV_1
    track = T.long_exit()
    print("Episode 7 — Where you put the weight")
    print(f"  front mass fraction {FRONT_FRACTIONS[0]:.2f} to "
          f"{FRONT_FRACTIONS[-1]:.2f}, {NODES} nodes, both drivetrains\n")

    # Understeer gradient first: cheap, and it is the number Episode 3 introduced.
    print("  understeer gradient (30 m skidpad, four-wheel model):")
    k_of = {}
    for ff in FRONT_FRACTIONS:
        b = DoubleTrackBackend(replace(p, front_mass_fraction=ff))
        k_of[ff], _ = ug_dt(b.skidpad_sweep(SKIDPAD_RADIUS, SKIDPAD_SPEEDS))
        print(f"    {ff:.2f} front -> K {k_of[ff]:+.2f} deg/g")

    # Minimum-time solves. Warm-start each point from its neighbour along the
    # sweep, which is what the series plan means by "fast": a converged answer at
    # 0.47 front is a far better seed for 0.54 than any cold guess.
    # Solve the NOMINAL first, then walk outward in both directions, each point
    # seeded from its already-solved neighbour. Chaining from one end of the sweep
    # instead meant that when rear drive lost convergence at 0.47 it never
    # recovered -- every later point inherited a poor seed. Continuation from a
    # known-good centre keeps each step small in both directions.
    order = ([NOMINAL]
             + sorted((f for f in FRONT_FRACTIONS if f < NOMINAL), reverse=True)
             + sorted(f for f in FRONT_FRACTIONS if f > NOMINAL))
    sols, rows = {}, {}
    # FRONT DRIVE FIRST, and the ordering is not cosmetic. The front-drive
    # four-wheel problem converges in ~10 s where rear drive needs 250-350 s,
    # consistently, across Episodes 6, 7 and 8. Solving it first gives every
    # rear-drive solve a converged four-wheel answer for the SAME balance to
    # start from, which is a far better seed than a bicycle solve or than a
    # rear-drive answer at a different balance.
    #
    # An earlier version solved rear drive first from a bicycle seed and left
    # three of five points on the iteration limit. Their times were excluded
    # from every claim, but that also left Episode 7's monotonic trend and
    # Episode 10's cross-check resting on two usable points. See FINDINGS F57.
    for drive in ("fwd", "rwd"):
        print(f"\n  {drive.upper()} minimum-time solves (outward from "
              f"{NOMINAL:.2f}):")
        seed = solve_min_time(track, n_nodes=NODES, entry_speed=ENTRY_SPEED)
        for ff in order:
            done = [g for g in sols if g[0] == drive and sols[g].success]
            near = min((g[1] for g in done), key=lambda g: abs(g - ff),
                       default=None)
            start = (sols[("fwd", ff)] if drive == "rwd"
                     and ("fwd", ff) in sols and sols[("fwd", ff)].success
                     else sols[(drive, near)] if near is not None else seed)
            t0 = time.time()
            q = solve_min_time(
                track, params=replace(p, front_mass_fraction=ff, drive=drive),
                n_nodes=NODES, entry_speed=ENTRY_SPEED, four_wheel=True,
                diff="ideal", warm_start=start, max_iter=MAX_ITER)
            if not q.success:
                # One retry at double the budget from the nominal answer, which
                # is what finally converged the last stubborn layout in Ep 8.
                alt = sols.get((drive, NOMINAL))
                q2 = solve_min_time(
                    track,
                    params=replace(p, front_mass_fraction=ff, drive=drive),
                    n_nodes=NODES, entry_speed=ENTRY_SPEED, four_wheel=True,
                    diff="ideal",
                    warm_start=alt if alt is not None and alt.success else start,
                    max_iter=2 * MAX_ITER)
                if q2.success:
                    print(f"      (retried {drive} {ff:.2f} at "
                          f"{2*MAX_ITER} iterations — converged)")
                    q = q2
            sols[(drive, ff)] = q
            rows[f"{drive}_{ff:.2f}"] = _summary(q, k_of[ff])
            print(f"    {ff:.2f} front  {q.solver_status:28s} {q.time:7.3f} s  "
                  f"apex {100*q.apex_fraction_through_corner:5.1f}%  "
                  f"brake to {_brake_release_s(q):5.1f} m  ({time.time()-t0:.0f}s)")

    unconverged = [f"{d.upper()} {ff:.2f}" for (d, ff), q in sols.items()
                   if not q.success]
    if unconverged:
        print("\n  WARNING: these solves hit the iteration limit, so their times "
              "are not evidence (FINDINGS F39):")
        print("    " + ", ".join(unconverged))

    results = {
        "entry_speed_ms": ENTRY_SPEED, "n_nodes": NODES,
        "track": track.name, "track_length_m": track.length,
        "front_fractions": list(FRONT_FRACTIONS), "nominal": NOMINAL,
        "tire": sols[("rwd", NOMINAL)].meta["tire"],
        "held_fixed": ("mass, wheelbase, track, yaw inertia, CoM height, tires "
                       "and roll stiffness distribution. ONLY the fore-aft "
                       "position of the mass moves. Yaw inertia is held fixed "
                       "deliberately -- separating balance from polar moment is "
                       "the split between this episode and Episode 8, and a real "
                       "engine move would change both."),
        "sourced_range": [0.53, 0.56],
        "rows": rows,
        "K_deg_per_g": {f"{ff:.2f}": k_of[ff] for ff in FRONT_FRACTIONS},
    }
    # the headline: is there an optimum, and is it at 50:50?
    for drive in ("rwd", "fwd"):
        ok = [(ff, sols[(drive, ff)].time) for ff in FRONT_FRACTIONS
              if sols[(drive, ff)].success]
        pool = ok or [(ff, sols[(drive, ff)].time) for ff in FRONT_FRACTIONS]
        best = min(pool, key=lambda z: z[1])
        results[f"best_front_fraction_{drive}"] = best[0]
        results[f"best_time_{drive}"] = best[1]
        results[f"best_is_from_converged_solves_only_{drive}"] = bool(ok)
        times = [sols[(drive, ff)].time for ff in FRONT_FRACTIONS]
        results[f"time_span_{drive}"] = max(times) - min(times)
    results["fwd_minus_rwd_at_each_fraction"] = {
        f"{ff:.2f}": sols[("fwd", ff)].time - sols[("rwd", ff)].time
        for ff in FRONT_FRACTIONS}
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (out / "meta.json").write_text(
        json.dumps(sols[("rwd", NOMINAL)].meta, indent=2) + "\n")

    arrays = {"s": sols[("rwd", NOMINAL)].s}
    for (drive, ff), q in sols.items():
        tag = f"{drive}_{ff:.2f}".replace(".", "")
        arrays[f"{tag}_n"] = q.states["n"]
        arrays[f"{tag}_xi"] = q.states["xi"]
        arrays[f"{tag}_delta"] = q.states["delta"]
        arrays[f"{tag}_speed"] = q.speed
        # dt/ds at every node -- exact (verified: trapz(dt_ds, s) reproduces
        # sol.time to 0.0000%), unlike (1-n*kappa)/speed which drops v_y*sin(xi)
        # and is wrong by ~0.07s here because xi reaches 24 deg at turn-in. This
        # is what a section-time metric (POWER-REVIEW Phase 0) must integrate.
        arrays[f"{tag}_dt_ds"] = q.dt_ds
        for c in CORNERS:
            arrays[f"{tag}_utilisation_{c}"] = q.per_wheel["utilisation"][c]
            arrays[f"{tag}_load_{c}"] = q.per_wheel["load"][c]
    np.savez(out / "traces.npz", **arrays)
    print("\n  traces.npz")

    figures(out)
    print()
    for drive in ("rwd", "fwd"):
        print(f"  {drive.upper()}: fastest at {results[f'best_front_fraction_{drive}']:.2f} "
              f"front ({results[f'best_time_{drive}']:.3f} s), spread "
              f"{results[f'time_span_{drive}']:.3f} s across the sweep")
    print("  FWD minus RWD at each fraction: " + "  ".join(
        f"{k} {v:+.3f}" for k, v in
        results["fwd_minus_rwd_at_each_fraction"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
