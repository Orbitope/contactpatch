"""Episode 5 — Where the simple model breaks.

Season 1 payoff. Runs the same skidpad through the two-wheel and four-wheel
models side by side, then sweeps the anti-roll bar through both — which is the
comparison that matters, because one of them cannot see the bar at all.

Run::

    python -m experiments.ep05.run
"""

from __future__ import annotations

import json
import math
from dataclasses import replace

import numpy as np

from experiments.common import episode_dir, write
from physics import schema
from physics.bicycle import BicycleBackend
from physics.bicycle import understeer_gradient as ug_bicycle
from physics.double_track import DoubleTrackBackend
from physics.double_track import understeer_gradient as ug_dt
from viz import load_figures

RADIUS = 30.0
SPEEDS = np.arange(5.0, 19.0, 0.25)
ROLL_SHARES = (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70)


def main() -> int:
    p = schema.RV_1
    out = episode_dir(5)
    dt, bi = DoubleTrackBackend(), BicycleBackend()
    print("Episode 5 — Where the simple model breaks")

    pts = [q for q in dt.skidpad_sweep(RADIUS, SPEEDS) if q.converged]
    k_dt, r2 = ug_dt(pts)
    k_bi, _ = ug_bicycle(bi.skidpad_sweep(RADIUS, SPEEDS))
    g_dt, g_bi = dt.max_lateral_g(RADIUS), bi.max_lateral_g(RADIUS)

    arb, arb_bi = {}, {}
    for e in ROLL_SHARES:
        arb[e], _ = ug_dt(DoubleTrackBackend(
            replace(p, roll_stiffness_front_share=e)).skidpad_sweep(RADIUS, SPEEDS))
        arb_bi[e], _ = ug_bicycle(BicycleBackend(
            replace(p, roll_stiffness_front_share=e)).skidpad_sweep(RADIUS, SPEEDS))

    # The article is the deliverable, so every pictorial the diagnostic makes
    # belongs here too. D5 was producing five figures while the episode embedded
    # two, which left the three most explanatory ones -- the ones that show a car
    # rather than an axis -- sitting in diagnostics/out where no reader goes.
    write(out / "01-four-wheels.svg", load_figures.four_wheel_figure(dt, pts))
    write(out / "02-body-roll.svg", load_figures.body_roll_figure(dt, pts))
    write(out / "03-anti-roll-bar.svg",
          load_figures.anti_roll_bar_figure(dt, arb, arb_bi))
    write(out / "04-low-and-wide.svg", load_figures.low_and_wide_figure(dt))
    write(out / "05-load-transfer-card.svg",
          load_figures.load_transfer_card(dt, pts, arb, arb_bi, k_dt, k_bi,
                                          g_dt, g_bi, dt.wheel_lift_a_y()))

    hard = max(pts, key=lambda q: q.a_y_g)
    cruise = min(pts, key=lambda q: abs(q.a_y_g - 0.20))
    results = {
        "radius_m": RADIUS,
        "K_bicycle": k_bi, "K_double_track": k_dt, "fit_r_squared": r2,
        "max_g_bicycle": g_bi, "max_g_double_track": g_dt,
        "grip_loss_pct": 100 * (g_bi - g_dt) / g_bi,
        "K_vs_roll_share_double_track": arb,
        "K_vs_roll_share_bicycle": arb_bi,
        "arb_authority_deg_per_g": max(arb.values()) - min(arb.values()),
        "arb_authority_bicycle_deg_per_g": (max(arb_bi.values())
                                            - min(arb_bi.values())),
        "wheel_lift_g": dt.wheel_lift_a_y(),
        "static_stability_factor": p.static_stability_factor,
        "at_the_limit": {
            "a_y_g": hard.a_y_g, "loads_N": hard.loads,
            "outside_over_inside": ((hard.loads["fr"] + hard.loads["rr"])
                                    / (hard.loads["fl"] + hard.loads["rl"])),
            "lateral_transfer_front_N": hard.lateral_transfer_front,
            "lateral_transfer_rear_N": hard.lateral_transfer_rear,
            "min_load_N": hard.min_load,
        },
        "cruising": {"a_y_g": cruise.a_y_g, "loads_N": cruise.loads},
        # Two protocols for "change the bar", and they are different experiments.
        # The sweep above redistributes a fixed total roll stiffness; this records
        # what bolting a bar ON does to the roll ANGLE instead. See FINDINGS F37.
        "roll_gradient_deg_per_g": p.roll_gradient_deg_per_g,
        "spring_only_roll_share": p.spring_only_roll_share,
        "roll_gradient_with_added_bar_deg_per_g": {
            str(e): p.roll_gradient_deg_per_g_with_bar(e) for e in ROLL_SHARES},
        "bar_rate_needed_Nm_per_rad": {
            str(e): p.bar_rate_for_share(e)[0] for e in ROLL_SHARES},
        "tire": dt.tire.provenance,
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"  {(out / 'results.json').name}")

    print(f"\n  K: bicycle {k_bi:+.2f} -> double-track {k_dt:+.2f} deg/g")
    print(f"  max lateral: {g_bi:.2f} -> {g_dt:.2f} g "
          f"({100*(g_bi-g_dt)/g_bi:.0f}% lost to lateral transfer)")
    print(f"  anti-roll bar authority: four wheels "
          f"{max(arb.values())-min(arb.values()):.2f} deg/g, two wheels "
          f"{max(arb_bi.values())-min(arb_bi.values()):.0e}")
    print(f"  at {hard.a_y_g:.2f} g the outside pair carries "
          f"{results['at_the_limit']['outside_over_inside']:.1f}x the inside pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
