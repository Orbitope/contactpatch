"""Episode 12 — what a differential actually does.

Your car has one. You have never seen it work. It sits between the driven wheels and
decides, moment to moment, which of them gets to be in charge.

**Two mechanisms, and they pull in opposite directions.** Getting this wrong is what
F75 was: a differential modelled as a torque-sharing device alone gets its handling
backwards.

``split_drive``  shares out the force the driver asked for, limited by each wheel's
                 grip and by how unequally the device is willing to share. That is
                 TRACTION: how much force reaches the road at all.
``speed_couple`` resists the wheels turning at different speeds — which in a corner
                 they must, because the outside wheel travels further. That is
                 HANDLING: which way the car gets steered as a side effect.

The traction mechanism favours the loaded outside wheel and turns the car IN. The
speed mechanism pushes the inside wheel and drags the outside, turning it OUT. **The
second one wins**, which is why a welded differential pushes wide on power and why
modelling only the first is worse than useless. See FINDINGS F76.

Three devices, distinguished by two numbers:

======  ==================  ================
device  torque bias ratio   locking fraction
======  ==================  ================
open    1.0 (equal always)  0.0 (resists nothing)
lsd     1.5 [ASSUMED]       0.5 [ASSUMED]
welded  inf (grip only)     1.0 (resists all)
======  ==================  ================

**Fidelity: rung 2** (CLAUDE.md rule 15). This shows the mechanism on a double-track
model. It does not model a clutch pack's ramp angles, its different behaviour on
coast versus drive, or the suspension terms that make up most of a real car's
understeer. Rank ordering and trend direction are what it can claim.

    python -m experiments.ep12.run
    python -m experiments.ep12.run --figures-only
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np

from diagnostics.common import Report
from experiments.common import episode_dir, write
from physics import schema
from physics.double_track import (CORNERS, BicycleState, DoubleTrackBackend,
                                  WheelForces)
from physics.track import CORNER_ARC, ENTRY_STRAIGHT

DEVICES = ("open", "lsd", "locked")
LABEL = {"open": "open", "lsd": "limited-slip (1.5:1)", "locked": "welded"}

#: The corner this episode is about. Self-consistent: a steady corner ties
#: ``a_y = v^2/R`` and ``yaw_rate = v/R``, so the three cannot be chosen freely. An
#: earlier version swept lateral acceleration at a fixed yaw rate and implied 1.59 g
#: on a car that makes 0.97 g — a corner no car can be in. See FINDINGS F77.
CORNER_RADIUS = 40.0
A_Y = 9.0                      # m/s^2, about 0.92 g — near this car's limit
EXIT_SPEED = math.sqrt(A_Y * CORNER_RADIUS)          # 19.0 m/s
YAW_RATE = EXIT_SPEED / CORNER_RADIUS                # 0.474 rad/s

#: Sweep the THROTTLE, not the corner. This is where the episode lives: the same
#: device does opposite things at the two ends, and a single operating point would
#: have shown only one of them.
DEMAND_SWEEP = np.linspace(0.0, 6500.0, 66)

#: The [ASSUMED] LSD numbers get swept, because F76/F77 flag them as the weakest part
#: of the model and CLAUDE.md requires the CONCLUSION to survive their range.
LOCKING_SWEEP = (0.25, 0.5, 0.75)

#: Where the two regimes are read off, for the checks and the article.
PART_THROTTLE, FULL_THROTTLE = 1000.0, 6000.0


def state_at(v: float, yaw: float) -> BicycleState:
    return BicycleState(v_x=v, v_y=0.0, yaw_rate=yaw, steer=0.0)


def probe(backend: DoubleTrackBackend, demand: float, loads: dict) -> dict:
    """One operating point: what the differential does and what it costs."""
    st = state_at(EXIT_SPEED, YAW_RATE)
    fx = backend.differential_forces(demand, loads, st)
    driven = backend.driven_corners()
    inside = [c for c in driven if c[1] == "l"][0]      # left turn
    outside = [c for c in driven if c[1] == "r"][0]
    w = {c: WheelForces(fy=0.0, fx=fx[c], alpha=0.0, kappa=0.0, fz=loads[c])
         for c in CORNERS}
    mz = backend.yaw_moment(w, 0.0)
    return {
        "demand_N": float(demand),
        "inside_N": float(fx[inside]),
        "outside_N": float(fx[outside]),
        "delivered_N": float(fx[inside] + fx[outside]),
        "shortfall_N": float(demand - fx[inside] - fx[outside]),
        "asymmetry_N": float(fx[outside] - fx[inside]),
        "mz": float(mz),
        "yaw_accel": float(mz / backend._params.i_zz),
    }


def sweep(diff: str, **kw) -> list[dict]:
    b = DoubleTrackBackend(schema.RV_1, diff=diff, **kw)
    loads = b.wheel_loads(1.5, A_Y)
    return [probe(b, d, loads) for d in DEMAND_SWEEP]


def at_demand(rows: list[dict], demand: float) -> dict:
    return min(rows, key=lambda r: abs(r["demand_N"] - demand))


def figures(out) -> None:
    from viz import diff_figures
    results = json.loads((out / "results.json").read_text())
    write(out / "01-which-wheel-is-in-charge.svg",
          diff_figures.mechanism_figure(results))
    write(out / "02-traction-and-handling.svg",
          diff_figures.decomposition_figure(results))
    write(out / "03-who-delivers-the-force.svg",
          diff_figures.traction_figure(results))


def main() -> int:
    out = episode_dir(12)
    if "--figures-only" in sys.argv:
        figures(out)
        return 0

    print("Episode 12 — What a differential actually does")
    print(f"  steady left corner: R={CORNER_RADIUS:.0f} m, a_y={A_Y:.1f} m/s2, "
          f"v={EXIT_SPEED:.1f} m/s, yaw={YAW_RATE:.3f} rad/s\n")

    sweeps = {d: sweep(d) for d in DEVICES}
    part = {d: at_demand(sweeps[d], PART_THROTTLE) for d in DEVICES}
    full = {d: at_demand(sweeps[d], FULL_THROTTLE) for d in DEVICES}

    for name, tag in ((f"PART throttle ({PART_THROTTLE:.0f} N)", part),
                      (f"FULL throttle ({FULL_THROTTLE:.0f} N)", full)):
        print(f"  {name}")
        print(f"    {'device':22s} {'inside':>8s} {'outside':>8s} "
              f"{'delivered':>10s} {'yaw moment':>12s}")
        for d in DEVICES:
            r = tag[d]
            arrow = ("pushes wide" if r["mz"] < -1 else
                     ("turns in" if r["mz"] > 1 else "neither"))
            print(f"    {LABEL[d]:22s} {r['inside_N']:7.0f}N {r['outside_N']:7.0f}N "
                  f"{r['delivered_N']:9.0f}N {r['mz']:+9.0f} N.m  {arrow}")
        print()

    locking_sens = {}
    for lk in LOCKING_SWEEP:
        rows = sweep("lsd", locking=lk)
        locking_sens[f"{lk:.2f}"] = {
            "part_mz": at_demand(rows, PART_THROTTLE)["mz"],
            "full_mz": at_demand(rows, FULL_THROTTLE)["mz"]}
    print("  LSD locking sensitivity (the weakest [ASSUMED] number, F77):")
    for k, v in locking_sens.items():
        print(f"    locking {k}: part {v['part_mz']:+7.0f}  full {v['full_mz']:+7.0f} N.m")

    report = Report(
        "D-ep12 — What a differential does",
        "One mechanism: torque flows from the faster-turning wheel to the slower. "
        "The checks ask whether both of its faces appear, whether they are ordered, "
        "and whether the conclusion survives the assumed numbers.")

    report.section("Does it do anything when there is nothing to decide?")
    straight = {d: DoubleTrackBackend(schema.RV_1, diff=d).differential_forces(
        4000.0, DoubleTrackBackend(schema.RV_1).wheel_loads(1.5, 0.0),
        state_at(EXIT_SPEED, 0.0)) for d in DEVICES}
    report.add(
        "no_device_does_anything_in_a_straight_line",
        all(abs(straight[d]["rl"] - straight[d]["rr"]) < 1e-9 for d in DEVICES)
        and len({round(straight[d]["rl"], 6) for d in DEVICES}) == 1,
        f"with no yaw rate every device feeds both wheels "
        f"{straight['open']['rl']:.0f} N. There is no speed difference to resist, so "
        f"a welded differential is invisible on a motorway and awful in a car park. "
        f"A model showing a difference here would be inventing one.",
        value=straight["open"]["rl"])

    report.section("Which way does it steer the car?")
    report.add(
        "at_part_throttle_a_locking_differential_pushes_wide",
        part["locked"]["mz"] < -1.0,
        f"at {PART_THROTTLE:.0f} N a welded differential gives "
        f"{part['locked']['mz']:+.0f} N.m — negative, yawing the car OUT of the "
        f"corner. Neither wheel is saturated, so kinematics decides: the outside "
        f"wheel travels further, turns faster, and loses torque to the inside. This "
        f"is the push every driver of a welded car complains about, and it is the "
        f"OUTSIDE check on this model (rule 2) — the sign is not ours to choose.",
        value=part["locked"]["mz"])
    report.add(
        "at_full_throttle_the_same_device_turns_the_car_in",
        full["locked"]["mz"] > 1.0,
        f"at {FULL_THROTTLE:.0f} N the same device gives {full['locked']['mz']:+.0f} "
        f"N.m, the other way. The inside wheel has saturated and is spinning, so it "
        f"is now the faster one and torque flows outboard to the wheel that still "
        f"grips. Same rule, opposite outcome. A model with a fixed bias direction "
        f"can only ever produce one of these, and that was F77's mistake.",
        value=full["locked"]["mz"])
    report.add(
        "more_locking_means_more_push",
        part["open"]["mz"] > part["lsd"]["mz"] > part["locked"]["mz"],
        f"part-throttle: open {part['open']['mz']:+.0f}, limited-slip "
        f"{part['lsd']['mz']:+.0f}, welded {part['locked']['mz']:+.0f} N.m. Ordered, "
        f"which is what this model can claim (rule 6).",
        value={d: part[d]["mz"] for d in DEVICES})
    report.add(
        "an_open_differential_steers_the_car_neither_way",
        all(abs(part[d]["mz"]) < 1e-9 for d in ("open",))
        and abs(full["open"]["mz"]) < 1e-9,
        f"an open differential gives {part['open']['mz']:+.2f} N.m at part throttle "
        f"and {full['open']['mz']:+.2f} at full. It feeds both wheels equally and "
        f"resists no speed difference, so it has no handling effect to have.",
        value=part["open"]["mz"])

    report.section("What does it cost in traction?")
    report.add(
        "an_open_differential_wastes_tractive_force",
        full["open"]["shortfall_N"] > 500.0,
        f"asked for {FULL_THROTTLE:.0f} N with the inside wheel light, an open "
        f"differential delivers {full['open']['delivered_N']:.0f} N and throws away "
        f"{full['open']['shortfall_N']:.0f} N. It must feed both wheels equally, so "
        f"it is limited by twice the weaker one. That sentence is the entire reason "
        f"the other two devices exist.",
        value=full["open"]["shortfall_N"])
    report.add(
        "locking_recovers_the_wasted_force",
        (full["open"]["delivered_N"] < full["lsd"]["delivered_N"]
         <= full["locked"]["delivered_N"]),
        f"delivered at full throttle: open {full['open']['delivered_N']:.0f} N, "
        f"limited-slip {full['lsd']['delivered_N']:.0f} N, welded "
        f"{full['locked']['delivered_N']:.0f} N.",
        value={d: full[d]["delivered_N"] for d in DEVICES})

    report.section("Does the conclusion survive the assumed numbers?")
    report.add(
        "the_push_wide_conclusion_holds_across_the_assumed_locking_range",
        all(v["part_mz"] < 0.0 for v in locking_sens.values()),
        f"the LSD's locking fraction is [ASSUMED] at 0.5 and is the weakest number "
        f"in this model. Across 0.25-0.75 the part-throttle moment stays negative "
        f"({', '.join(f'{k}: {v['part_mz']:+.0f}' for k, v in locking_sens.items())}"
        f" N.m), so the CONCLUSION does not depend on the assumption even though the "
        f"magnitude plainly does.",
        value=locking_sens)
    report.note(
        "magnitudes_are_not_quotable",
        "Rung 2 (rule 15). Track width is [LIKELY]; the LSD's two numbers are "
        "[ASSUMED]; a real clutch pack behaves differently on coast than on drive, "
        "which this does not model. The ordering and the two signs are the result. "
        "The N.m are illustrative.")

    results = {
        "corner_radius_m": CORNER_RADIUS, "a_y": A_Y,
        "exit_speed_ms": EXIT_SPEED, "yaw_rate": YAW_RATE,
        "part_throttle_N": PART_THROTTLE, "full_throttle_N": FULL_THROTTLE,
        "devices": list(DEVICES), "labels": LABEL,
        "demand_sweep": [float(v) for v in DEMAND_SWEEP],
        "sweeps": sweeps, "part": part, "full": full,
        "locking_sensitivity": locking_sens,
        "fidelity": ("Rung 2 — double-track. Shows the mechanism; does not model "
                     "clutch-pack ramp angles, coast-versus-drive asymmetry, or the "
                     "suspension terms that are most of a real car's understeer. "
                     "Ordering and trend direction only (rules 6 and 15)."),
        "checks_passed": report.ok,
        "check_failures": [c.name for c in report.failures],
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    md = report.write_markdown(command="python -m experiments.ep12.run")
    report.write()
    report.print_summary(verbose="-v" in sys.argv)
    print(f"\n  write-up {md}")
    figures(out)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
