"""Episode 3 — Building the simplest car that can understeer.

Constant-radius skidpad: drive a 30 m circle at every speed the car can hold,
and measure how much steering each extra g of cornering costs. Then move the
weight around and do it again.

Run::

    python -m experiments.ep03.run
"""

from __future__ import annotations

import json
import math
from dataclasses import replace

import numpy as np

from experiments.common import episode_dir, write
from physics import schema
from physics.bicycle import BicycleBackend, understeer_gradient
from viz import skidpad_figures, transfer_figures

RADIUS = 30.0                       # m [ASSUMED]
SPEEDS = np.arange(5.0, 19.0, 0.25)
FRACTIONS = (0.42, 0.46, 0.50, 0.54, 0.58, 0.62)


def main() -> int:
    b = BicycleBackend()
    p = schema.RV_1
    out = episode_dir(3)
    print("Episode 3 — Building the simplest car that can understeer")

    points = [pt for pt in b.skidpad_sweep(RADIUS, SPEEDS) if pt.converged]
    k, r2 = understeer_gradient(points)
    max_g = b.max_lateral_g(RADIUS)

    k_by_frac = {}
    for f in FRACTIONS:
        bb = BicycleBackend(replace(p, front_mass_fraction=f))
        k_by_frac[f], _ = understeer_gradient(bb.skidpad_sweep(RADIUS, SPEEDS))

    write(out / "01-what-understeer-is.svg",
          skidpad_figures.understeer_figure(b, points, k, RADIUS))
    write(out / "02-where-the-weight-goes.svg",
          transfer_figures.load_transfer_figure(b))
    write(out / "03-steady-state-card.svg",
          skidpad_figures.steady_state_card(
              b, points, k, max_g, k_by_frac,
              (2 * p.static_fz_front
               / (2 * abs(float(b.tire.cornering_stiffness(p.static_fz_front)))
                  * math.pi / 180),
               2 * p.static_fz_rear
               / (2 * abs(float(b.tire.cornering_stiffness(p.static_fz_rear)))
                  * math.pi / 180)),
              RADIUS))

    # uncertainty the reference sheet itself documents
    k_span = []
    for f in (0.53, 0.56):
        bb = BicycleBackend(replace(p, front_mass_fraction=f))
        k_span.append(understeer_gradient(bb.skidpad_sweep(RADIUS, SPEEDS))[0])

    slow = min(points, key=lambda q: abs(q.a_y_g - 0.20))
    fast = max(points, key=lambda q: q.a_y_g)
    results = {
        "radius_m": RADIUS,
        "understeer_gradient_deg_per_g": k,
        "understeer_gradient_range_from_input_uncertainty": [min(k_span), max(k_span)],
        "fit_r_squared": r2,
        "max_lateral_g": max_g,
        "K_by_front_fraction": k_by_frac,
        "neutral_front_fraction": float(np.interp(
            0.0, list(k_by_frac.values()), list(k_by_frac))),
        "cruising": {"a_y_g": slow.a_y_g, "steer_deg": slow.steer_deg,
                     "alpha_f_deg": math.degrees(slow.alpha_f),
                     "alpha_r_deg": math.degrees(slow.alpha_r),
                     "sideslip_deg": slow.sideslip_deg},
        "at_the_limit": {"a_y_g": fast.a_y_g, "steer_deg": fast.steer_deg,
                         "alpha_f_deg": math.degrees(fast.alpha_f),
                         "alpha_r_deg": math.degrees(fast.alpha_r),
                         "sideslip_deg": fast.sideslip_deg},
        "ackermann_deg": math.degrees(points[0].ackermann),
        "braking_load_transfer_N": (b.axle_loads(-0.5 * schema.G)[0]
                                    - b.axle_loads(0.0)[0]),
        "tire": b.tire.provenance,
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"  {(out / 'results.json').name}")

    print(f"\n  K = {k:.2f} deg/g  (range {min(k_span):.2f}-{max(k_span):.2f} "
          f"across the documented weight-distribution uncertainty)")
    print(f"  max lateral {max_g:.2f} g,  Ackermann {results['ackermann_deg']:.2f} deg")
    print("  K by front fraction: " + ", ".join(
        f"{f:.2f}->{v:+.2f}" for f, v in k_by_frac.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
