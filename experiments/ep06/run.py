"""Episode 6 — Front-wheel drive vs rear-wheel drive.

Same corner, same car, same tires, same entry speed. The only change is which
axle receives drive torque. Then look at what each tire was being asked to do
along the way.

Run::

    python -m experiments.ep06.run
    python -m experiments.ep06.run --figures-only   # redraw from cached traces

``--figures-only`` reloads ``out/traces.npz``, ``out/results.json`` and
``out/meta.json`` and rebuilds every figure without re-solving. Four four-wheel
minimum-time solves take minutes; iterating on a figure should not.
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
from physics.optimal_control import Limits, solve_min_time
from viz import utilisation_figures

ENTRY_SPEED = 32.0

#: Primary grid. **100 nodes, not the finest available**, and the reason is the
#: whole of FINDINGS F39: this is the only grid on which *every* solve in the
#: comparison converges cleanly. On finer grids the rear-drive problem stops on
#: the iteration limit, and an unconverged objective is not evidence. Choosing
#: the grid where the numerics are trustworthy beats choosing the finest one.
NODES = 100
#: Grid refinement. Rear drive does not converge at these, so they bracket rather
#: than confirm — which is still worth having, and is reported as such.
REFINE_NODES = (140, 180)
#: The rear-drive four-wheel problem needs far more than IPOPT's 2000 default. At
#: 2000 it returned a time 0.02 s off, which looked like a grid dependence.
MAX_ITER = 8000
#: Drive-force caps for the power sensitivity, kN. 4.5 is the nominal and the
#: only one where both solves converge; the rest establish the trend (F43).
POWER_SWEEP_KN = (2.5, 4.5, 7.0, 10.0)
#: Where on the exit to sample per-wheel state for the power figure: 20 m past
#: the corner, where the front-drive car is still finishing the turn AND putting
#: power down, which is the whole point.
PWR_STATION = T.ENTRY_STRAIGHT + T.CORNER_ARC + 20.0
CORNERS = ("fl", "fr", "rl", "rr")


def _summary(sol) -> dict:
    pw = sol.per_wheel
    corner = sol.corner_mask
    exitm = sol.s > (T.ENTRY_STRAIGHT + T.CORNER_ARC)
    return {
        "drive": sol.meta["drive"],
        "time_s": sol.time,
        "apex_fraction_through_corner": sol.apex_fraction_through_corner,
        "min_speed_ms": float(sol.speed.min()),
        "exit_speed_ms": float(sol.speed[-1]),
        "peak_utilisation": {c: float(pw["utilisation"][c].max()) for c in CORNERS},
        "mean_utilisation_in_corner": {
            c: float(pw["utilisation"][c][corner].mean()) for c in CORNERS},
        "mean_utilisation_on_exit": {
            c: float(pw["utilisation"][c][exitm].mean()) for c in CORNERS},
        "first_wheel_saturated": _first_saturated(sol),
        "peak_drive_kN": float(sol.controls["drive_force"].max() / 1000.0),
        "load_range_N": {c: [float(pw["load"][c].min()), float(pw["load"][c].max())]
                         for c in CORNERS},
        "worst_slip_deg": math.degrees(float(max(
            np.abs(pw["alpha"][c]).max() for c in CORNERS))),
        "envelope_occupancy": sol.envelope_occupancy(),
        "solver_status": sol.solver_status,
        "converged": sol.success,
    }


def _first_saturated(sol) -> dict:
    """Which wheel reaches 99% of its friction circle first, and where."""
    best = None
    for c in CORNERS:
        u = sol.per_wheel["utilisation"][c]
        hit = np.where(u > 0.99)[0]
        if hit.size:
            s_at = float(sol.s[hit[0]])
            if best is None or s_at < best[1]:
                best = (c, s_at)
    return {"corner": best[0], "s_m": best[1]} if best else {}


def figures(out) -> None:
    """Rebuild every figure from what is on disk. No solving."""
    tr = dict(np.load(out / "traces.npz"))
    results = json.loads((out / "results.json").read_text())
    meta = json.loads((out / "meta.json").read_text())
    track = T.long_exit()
    c0, c1 = T.ENTRY_STRAIGHT, T.ENTRY_STRAIGHT + T.CORNER_ARC
    marks = [("turn-in", c0 + 6.0), ("apex", c0 + 0.55 * T.CORNER_ARC),
             ("25 m past the corner", c1 + 25.0)]
    write(out / "01-two-things-at-once.svg",
          utilisation_figures.utilisation_figure(tr, results, meta, marks))
    write(out / "02-the-whole-run.svg",
          utilisation_figures.whole_track_figure(tr, results, meta, track))
    write(out / "03-both-cars-one-road.svg",
          utilisation_figures.overlay_figure(tr, results, meta, track))
    write(out / "04-along-the-corner.svg",
          utilisation_figures.along_the_corner_figure(tr, results, meta, track))
    write(out / "05-what-the-differential-does.svg",
          utilisation_figures.differential_figure(tr, results, meta))
    if "power_sweep" in results:
        write(out / "06-power-changes-the-answer.svg",
              utilisation_figures.power_figure(results, meta))
    write(out / "07-utilisation-card.svg",
          utilisation_figures.utilisation_card(tr, results, meta, (c0, c1)))


def main() -> int:
    out = episode_dir(6)
    if "--figures-only" in sys.argv:
        figures(out)
        return 0
    p = schema.RV_1
    print("Episode 6 — Front-wheel drive vs rear-wheel drive")
    print(f"  {NODES} nodes, entry {ENTRY_SPEED:g} m/s, same corner both ways\n")

    track = T.long_exit()          # a straight to accelerate down, so drive matters
    sols = {}
    seed = solve_min_time(track, n_nodes=NODES, entry_speed=ENTRY_SPEED)
    # Four solves: both drivetrains, both differentials. The differential is a
    # modelling choice that changes the answer, so it gets measured rather than
    # assumed (CLAUDE.md rule 9).
    for diff in ("open", "ideal"):
        for drive in ("rwd", "fwd"):
            t0 = time.time()
            sols[(drive, diff)] = solve_min_time(
                track, params=replace(p, drive=drive), n_nodes=NODES,
                entry_speed=ENTRY_SPEED, four_wheel=True, diff=diff,
                warm_start=seed, max_iter=MAX_ITER)
            q = sols[(drive, diff)]
            print(f"  {drive.upper():4s} {diff:6s} {q.solver_status:28s} "
                  f"{q.time:7.3f} s exit {q.speed[-1]:5.1f} m/s  "
                  f"({time.time()-t0:.0f}s)")
    if not all(q.success for q in sols.values()):
        # Loud, because it is the difference between a result and an artefact.
        print("\n  WARNING: not every solve converged cleanly. Any time quoted "
              "from this run is not evidence — see FINDINGS F39.")
        for (drive, diff), q in sols.items():
            if not q.success:
                print(f"    {drive.upper()} {diff}: {q.solver_status}")

    results = {
        "entry_speed_ms": ENTRY_SPEED, "n_nodes": NODES,
        "track": track.name, "track_length_m": track.length,
        "tire": sols[("rwd", "open")].meta["tire"],
        "note": ("Every wheel's longitudinal force is capped at its own "
                 "capability. With an OPEN differential the 50/50 torque split "
                 "then limits the driven pair to twice the weaker (inside) "
                 "wheel; with an IDEAL one the split floats, which is the best "
                 "an LSD could do. The reference car has a factory LSD, so the "
                 "truth is between. Episode 12 is about that gap."),
    }
    for diff in ("open", "ideal"):
        for drive in ("rwd", "fwd"):
            results[f"{drive}_{diff}"] = _summary(sols[(drive, diff)])
        results[f"time_delta_s_{diff}"] = (sols[("fwd", diff)].time
                                          - sols[("rwd", diff)].time)
        results[f"exit_delta_ms_{diff}"] = (sols[("fwd", diff)].speed[-1]
                                           - sols[("rwd", diff)].speed[-1])
    for drive in ("rwd", "fwd"):
        results[f"diff_worth_s_{drive}"] = (sols[(drive, "open")].time
                                           - sols[(drive, "ideal")].time)
    # the primary comparison the article leads with
    results["rwd"] = results["rwd_ideal"]
    results["fwd"] = results["fwd_ideal"]
    results["time_delta_s"] = results["time_delta_s_ideal"]
    results["exit_speed_delta_ms"] = results["exit_delta_ms_ideal"]
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"  {(out / 'results.json').name}")

    arrays = {}
    for (drive, diff), q in sols.items():
        tag = drive if diff == "ideal" else f"{drive}_open"
        for k in ("utilisation", "load", "alpha", "fy", "fx"):
            for c in CORNERS:
                arrays[f"{tag}_{k}_{c}"] = q.per_wheel[k][c]
        arrays[f"{tag}_speed"] = q.speed
        arrays[f"{tag}_n"] = q.states["n"]
        # xi (heading relative to the road) and delta (steer) are what let a
        # figure draw the car pointing where it actually points, rather than
        # tangent to the road at every station.
        arrays[f"{tag}_xi"] = q.states["xi"]
        arrays[f"{tag}_delta"] = q.states["delta"]
        arrays[f"{tag}_drive"] = q.controls["drive_force"]
    np.savez(out / "traces.npz", s=sols[("rwd", "ideal")].s, **arrays)
    print("  traces.npz")
    (out / "meta.json").write_text(
        json.dumps(sols[("rwd", "ideal")].meta, indent=2) + "\n")

    # Grid refinement. The headline is a 0.1 s difference on a 12 s solve, and
    # the whole thing is an artefact of chopping the road into slices, so it must
    # not depend on how many slices. There is no seed discipline to apply here --
    # the solver is deterministic -- and this is its analogue (CLAUDE.md rule 5).
    print("\n  grid refinement (ideal diff):")
    refine = {}
    for nodes in REFINE_NODES:
        row = {}
        for drive in ("rwd", "fwd"):
            # Seed from the converged primary solve, resampled onto this grid. A
            # fresh bicycle solve is a much poorer start: started that way at 220
            # nodes the rear-drive problem stopped on an envelope-violating
            # trajectory. Resampling a warm start across node counts is what makes
            # this possible at all -- it used to be silently ignored (F39).
            q = solve_min_time(track, params=replace(p, drive=drive),
                               n_nodes=nodes, entry_speed=ENTRY_SPEED,
                               four_wheel=True, diff="ideal",
                               warm_start=sols[(drive, "ideal")],
                               max_iter=MAX_ITER)
            occ = q.envelope_occupancy()
            # A trajectory outside the slip envelope is not a slower answer, it is
            # not an answer: the tire model is extrapolating there. CLAUDE.md rule
            # 4 -- discarded, not celebrated. Excluded from the spread, and the
            # exclusion is recorded rather than quietly dropped.
            row[drive] = {"time_s": q.time, "status": q.solver_status,
                          "envelope_occupancy": occ, "admissible": occ == 0.0,
                          "converged": q.success}
        row["delta_s"] = row["fwd"]["time_s"] - row["rwd"]["time_s"]
        row["admissible"] = all(row[d]["admissible"] for d in ("rwd", "fwd"))
        row["both_converged"] = all(row[d]["converged"] for d in ("rwd", "fwd"))
        refine[str(nodes)] = row
        print(f"    {nodes:4d} nodes: FWD is {row['delta_s']:+.3f} s"
              + ("   both converged" if row["both_converged"] else
                 "   (rear drive on the iteration limit — brackets, "
                 "does not confirm)")
              + ("" if row["admissible"] else "   DISCARDED — outside the "
                 "slip envelope, see results.json"))
    refine[str(NODES)] = {
        "delta_s": results["time_delta_s_ideal"], "admissible": True,
        "both_converged": (sols[("rwd", "ideal")].success
                           and sols[("fwd", "ideal")].success),
        "rwd": {"time_s": results["rwd_ideal"]["time_s"], "admissible": True,
                "converged": sols[("rwd", "ideal")].success,
                "envelope_occupancy": results["rwd_ideal"]["envelope_occupancy"]},
        "fwd": {"time_s": results["fwd_ideal"]["time_s"], "admissible": True,
                "converged": sols[("fwd", "ideal")].success,
                "envelope_occupancy": results["fwd_ideal"]["envelope_occupancy"]}}
    results["grid_refinement"] = refine
    ok = {k: v for k, v in refine.items() if v["admissible"]}
    results["grid_refinement_node_counts_used"] = sorted(ok, key=int)
    results["grid_refinement_node_counts_discarded"] = sorted(
        (k for k in refine if k not in ok), key=int)
    deltas = [v["delta_s"] for v in ok.values()]
    results["delta_s_spread_over_node_counts"] = (max(deltas) - min(deltas)
                                                  if len(deltas) > 1 else None)
    dropped = results["grid_refinement_node_counts_discarded"]
    print(f"    admissible node counts: "
          f"{', '.join(results['grid_refinement_node_counts_used'])}"
          + (f"   discarded: {', '.join(dropped)}" if dropped else ""))
    if results["delta_s_spread_over_node_counts"] is not None:
        print(f"    spread across admissible node counts: "
              f"{results['delta_s_spread_over_node_counts']:.3f} s "
              f"against a {results['time_delta_s_ideal']:.3f} s effect")
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    # Power sensitivity. The whole mechanism is front tires running out of grip
    # while doing two jobs, so the penalty must scale with how much acceleration
    # there is to place -- and the drive cap is [ASSUMED]. An effect whose size is
    # set by an assumed parameter needs that parameter swept, or the conclusion is
    # about our guess (CLAUDE.md rule 9). See FINDINGS F43.
    print("\n  power sensitivity (ideal diff):")
    power = {}
    for kn in POWER_SWEEP_KN:
        row = {}
        for drive in ("rwd", "fwd"):
            q = solve_min_time(track, params=replace(p, drive=drive),
                               n_nodes=NODES, entry_speed=ENTRY_SPEED,
                               four_wheel=True, diff="ideal",
                               warm_start=sols[(drive, "ideal")],
                               max_iter=MAX_ITER,
                               limits=replace(Limits(), drive_max=kn * 1000.0))
            exitm = q.s > (T.ENTRY_STRAIGHT + T.CORNER_ARC)
            pw = q.per_wheel
            # Enough per-wheel state to DRAW this, not just tabulate it. A sweep
            # with no figure is a table, and the whole argument here is about what
            # the tires are doing -- so the tires have to be visible (rule 1).
            k = int(np.argmin(np.abs(q.s - PWR_STATION)))
            row[drive] = {
                "time_s": q.time, "status": q.solver_status,
                "converged": q.success,
                "envelope_occupancy": q.envelope_occupancy(),
                "mean_utilisation_on_exit": {
                    c: float(pw["utilisation"][c][exitm].mean()) for c in CORNERS},
                "at_station": {
                    "s_m": float(q.s[k]),
                    "speed_ms": float(q.speed[k]),
                    "load_N": {c: float(pw["load"][c][k]) for c in CORNERS},
                    "fx_N": {c: float(pw["fx"][c][k]) for c in CORNERS},
                    "fy_N": {c: float(pw["fy"][c][k]) for c in CORNERS},
                    "utilisation": {c: float(pw["utilisation"][c][k])
                                    for c in CORNERS},
                },
            }
        row["delta_s"] = row["fwd"]["time_s"] - row["rwd"]["time_s"]
        row["both_converged"] = all(row[d]["converged"] for d in ("rwd", "fwd"))
        # indicative only: a real engine's force falls with speed
        row["approx_kW_at_30ms"] = kn * 30.0
        power[f"{kn:g}"] = row
        print(f"    {kn:5.1f} kN (~{kn*30*1.341:.0f} hp): FWD is "
              f"{row['delta_s']:+.3f} s"
              + ("   both converged" if row["both_converged"]
                 else "   (not all converged — trend only)"))
    results["power_sweep"] = power
    ok = [v["delta_s"] for v in power.values() if v["both_converged"]]
    results["power_sweep_quotable_kN"] = [k for k, v in power.items()
                                          if v["both_converged"]]
    deltas = [v["delta_s"] for v in power.values()]
    results["power_sweep_delta_span_s"] = max(deltas) - min(deltas)
    print(f"    penalty spans {results['power_sweep_delta_span_s']:.3f} s across "
          f"the sweep; quotable at {results['power_sweep_quotable_kN']} kN only")
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    figures(out)
    print()
    for diff in ("open", "ideal"):
        print(f"  {diff:6s} diff: FWD is {results[f'time_delta_s_{diff}']:+.3f} s, "
              f"exit {results[f'exit_delta_ms_{diff}']:+.2f} m/s")
    for drive in ("rwd", "fwd"):
        print(f"  a perfect diff is worth {results[f'diff_worth_s_{drive}']:+.3f} s "
              f"to {drive.upper()}")
    for d in ("rwd", "fwd"):
        u = results[d]["mean_utilisation_on_exit"]
        print(f"  {d.upper()} (ideal diff) mean utilisation on exit: "
              + "  ".join(f"{c} {u[c]:.2f}" for c in CORNERS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
