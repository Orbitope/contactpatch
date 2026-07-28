"""Episode 1 — Why does a tire make grip at all?

The experiment: take one tire, hold the load constant, and sweep the angle
between where it points and where it is going. Measure the sideways force.

That is the whole thing. No car, no suspension, no driver. Everything in the
next fifteen episodes is built on the shape of the curve this produces.

Run::

    python -m experiments.ep01.run
"""

from __future__ import annotations

import json
import math

import numpy as np

from experiments.common import episode_dir, write
from physics import schema
from physics.tire import default_tire
from viz import tire_figures

#: One front corner of RV-1 at rest. Every curve in this episode is at this
#: load, so that the only thing changing is the angle. [DERIVED] from the
#: [SOURCED] mass and weight distribution.
LOAD = schema.RV_1.static_fz_front


def main() -> int:
    tire = default_tire()
    out = episode_dir(1)
    print("Episode 1 — Why does a tire make grip at all?")

    write(out / "01-what-a-slip-angle-is.svg",
          tire_figures.slip_angle_figure(tire, LOAD))

    peak = tire.peak_lateral(LOAD)
    alphas = np.radians(np.linspace(0.0, 20.0, 401))
    forces = np.abs(tire.fy0(alphas, LOAD))

    def at(deg):
        return float(abs(tire.fy0(math.radians(deg), LOAD)))

    results = {
        "load_N": LOAD,
        "peak_force_N": peak.fy_peak,
        "peak_mu": peak.mu_peak,
        "peak_slip_deg": peak.alpha_peak_deg,
        "force_at_0_deg_N": at(0.0),
        "fraction_of_peak_at_2_deg": at(2.0) / peak.fy_peak,
        "fraction_of_peak_at_5_deg": at(5.0) / peak.fy_peak,
        "fraction_of_peak_at_16_deg": at(16.0) / peak.fy_peak,
        "cornering_stiffness_N_per_deg": peak.cornering_stiffness_per_deg,
        "peak_slip_deg_at_1kN": tire.peak_lateral(1000.0).alpha_peak_deg,
        "peak_slip_deg_at_9kN": tire.peak_lateral(9000.0).alpha_peak_deg,
        "imposed_slip_bound_deg": math.degrees(tire.envelope.imposed_alpha_max),
        "tire": tire.provenance,
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"  {(out / 'results.json').name}")

    print(f"\n  peak {peak.fy_peak:,.0f} N (mu {peak.mu_peak:.2f}) at "
          f"{peak.alpha_peak_deg:.1f} deg")
    print(f"  {100*results['fraction_of_peak_at_5_deg']:.0f}% of it is already "
          f"there by 5 deg; at 16 deg you are back down to "
          f"{100*results['fraction_of_peak_at_16_deg']:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
