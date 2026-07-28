"""Episode 4 — The fastest way round a corner isn't the obvious one.

Two minimum-time solves of the same 90° corner at the same entry speed. The only
difference is how much straight road follows it. Nothing is told about racing
lines; the answer comes out of the tire model, the width of the road and a
stopwatch.

Also runs a grid-refinement check, because "the apex moved" is only a finding if
it survives changing the discretisation.

Run::

    python -m experiments.ep04.run
"""

from __future__ import annotations

import json
import math
import time

import numpy as np

from experiments.common import episode_dir, write
from physics import track as T
from physics.optimal_control import solve_min_time
from viz import line_figures

ENTRY_SPEED = 32.0        # m/s at the start line, both cases [ASSUMED]
NODES = 200
GRID_CHECK = (140, 200, 280)


def _summary(sol) -> dict:
    return {
        "track": sol.track.name,
        "track_length_m": sol.track.length,
        "time_s": sol.time,
        "apex_s_m": sol.apex_s,
        "apex_fraction_through_corner": sol.apex_fraction_through_corner,
        "apex_offset_m": float(sol.states["n"][sol.apex_index]),
        "min_speed_ms": float(sol.speed.min()),
        "exit_speed_ms": float(sol.speed[-1]),
        "max_speed_ms": float(sol.speed.max()),
        "worst_slip_deg": math.degrees(float(max(np.abs(sol.alpha_f).max(),
                                                 np.abs(sol.alpha_r).max()))),
        "envelope_occupancy": sol.envelope_occupancy(),
        "peak_brake_kN": float(sol.controls["drive_force"].min() / 1000.0),
        "peak_drive_kN": float(sol.controls["drive_force"].max() / 1000.0),
        "brake_release_s_m": _brake_release(sol),
        "solver_status": sol.solver_status,
        "converged": sol.success,
    }


def _brake_release(sol) -> float:
    """Distance at which braking stops. Where trail braking would show up."""
    braking = sol.controls["drive_force"] < -200.0
    if not braking.any():
        return float("nan")
    return float(sol.s[np.where(braking)[0][-1]])


def main() -> int:
    out = episode_dir(4)
    print("Episode 4 — The fastest way round a corner isn't the obvious one")
    print(f"  entry speed {ENTRY_SPEED:g} m/s, {NODES} nodes\n")

    # Long exit first: it converges cleanly, and the short-exit solve is then
    # warm-started from it. Continuation, the same trick the design sweeps will
    # need in Season 2.
    t0 = time.time()
    long_sol = solve_min_time(T.long_exit(), n_nodes=NODES,
                              entry_speed=ENTRY_SPEED)
    print(f"  long exit  {long_sol.solver_status:28s} {long_sol.time:7.3f} s "
          f"({time.time()-t0:.0f} s of solver)")
    t0 = time.time()
    short_sol = solve_min_time(T.short_exit(), n_nodes=NODES,
                              entry_speed=ENTRY_SPEED, warm_start=long_sol)
    print(f"  short exit {short_sol.solver_status:28s} {short_sol.time:7.3f} s "
          f"({time.time()-t0:.0f} s of solver)")

    solutions = [short_sol, long_sol]
    labels = ["30 m of straight after the corner",
              "260 m of straight after the corner"]
    write(out / "01-the-fastest-line.svg", line_figures.line_figure(solutions, labels))
    write(out / "02-line-card.svg", line_figures.line_card(solutions, labels))

    # Grid refinement: does the apex shift survive changing the discretisation?
    grid = {}
    for nn in GRID_CHECK:
        a = solve_min_time(T.short_exit(), n_nodes=nn, entry_speed=ENTRY_SPEED)
        b = solve_min_time(T.long_exit(), n_nodes=nn, entry_speed=ENTRY_SPEED)
        grid[nn] = {
            "short_apex_frac": a.apex_fraction_through_corner,
            "long_apex_frac": b.apex_fraction_through_corner,
            "shift_points": 100 * (b.apex_fraction_through_corner
                                   - a.apex_fraction_through_corner),
            "short_time_s": a.time, "long_time_s": b.time,
            "short_status": a.solver_status, "long_status": b.solver_status,
        }
        print(f"  grid {nn:3d}: apex shift "
              f"{grid[nn]['shift_points']:+5.1f} points")

    shift = 100 * (long_sol.apex_fraction_through_corner
                   - short_sol.apex_fraction_through_corner)
    results = {
        "entry_speed_ms": ENTRY_SPEED,
        "n_nodes": NODES,
        "corner": {"radius_m": T.CORNER_RADIUS, "arc_m": T.CORNER_ARC,
                   "half_width_m": T.HALF_WIDTH,
                   "entry_straight_m": T.ENTRY_STRAIGHT},
        "short_exit": _summary(short_sol),
        "long_exit": _summary(long_sol),
        "apex_shift_points": shift,
        "grid_refinement": grid,
        "limits": vars(short_sol.limits),
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"  {(out / 'results.json').name}")

    print(f"\n  apex moves {shift:+.0f} percentage points later with the long exit")
    print(f"  min speed {short_sol.speed.min():.1f} -> {long_sol.speed.min():.1f} m/s")
    print(f"  exit speed {short_sol.speed[-1]:.1f} -> {long_sol.speed[-1]:.1f} m/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
