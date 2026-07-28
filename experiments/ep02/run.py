"""Episode 2 — The most important graph in vehicle dynamics.

Two experiments, both on the tire model alone:

1. Sweep the load and measure peak grip. Does it scale?
2. Give two tires a fixed total load and slide it from one to the other. Does
   the pair make the same total force however it is shared?

Run::

    python -m experiments.ep02.run
"""

from __future__ import annotations

import json

import numpy as np

from experiments.common import episode_dir, write
from physics import schema
from physics.tire import default_tire
from viz import tire_figures

#: Two tires sharing this much. A round number near the reference car's front
#: axle load, chosen so the splits are easy to read. [ASSUMED]
TOTAL = 6000.0


def main() -> int:
    tire = default_tire()
    out = episode_dir(2)
    print("Episode 2 — The most important graph in vehicle dynamics")

    write(out / "01-why-weight-transfer-costs-grip.svg",
          tire_figures.load_split_figure(tire, TOTAL))

    loads = np.array([1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000],
                     dtype=float)
    peaks = [tire.peak_lateral(f) for f in loads]

    splits = {}
    for hi in (3000.0, 3500.0, 4000.0, 4500.0, 5000.0):
        lo = TOTAL - hi
        total = (tire.peak_lateral(hi).fy_peak + tire.peak_lateral(lo).fy_peak)
        splits[f"{hi/1000:g}+{lo/1000:g}"] = total
    even = splits["3+3"]

    slope = float(np.polyfit(loads / 1000.0, [p.mu_peak for p in peaks], 1)[0])
    results = {
        "peak_mu_by_load": {int(f): p.mu_peak for f, p in zip(loads, peaks)},
        "peak_force_by_load_N": {int(f): p.fy_peak for f, p in zip(loads, peaks)},
        "dmu_dkN": slope,
        "force_ratio_9kN_over_1kN": peaks[-1].fy_peak / peaks[0].fy_peak,
        "load_ratio_9kN_over_1kN": 9.0,
        "split_totals_N": splits,
        "split_loss_pct": {k: 100 * (even - v) / even for k, v in splits.items()},
        "static_corner_loads_N": {
            "front": schema.RV_1.static_fz_front,
            "rear": schema.RV_1.static_fz_rear,
        },
        "tire": tire.provenance,
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"  {(out / 'results.json').name}")

    print(f"\n  peak mu {peaks[0].mu_peak:.2f} at 1 kN -> {peaks[-1].mu_peak:.2f} "
          f"at 9 kN  (dmu/dFz {slope:+.3f} per kN)")
    print(f"  9x the load buys "
          f"{results['force_ratio_9kN_over_1kN']:.1f}x the force, not 9x")
    for k, v in splits.items():
        print(f"  {k} kN -> {v:,.0f} N  ({100*(v-even)/even:+.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
