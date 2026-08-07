"""Season 5 stage 1 — does the Spa recipe transfer, or is it a Spa constant?

The staging plan asks: *"If `cross_track_penalty=2.0` does not also solve a
fast and a tight circuit, it is a Spa constant, not a finding, and the sweep
has to be redone per band before anything else proceeds."* Monza is the fast
circuit, MexicoCity the tight one; Spa sits between them.

**Four runs, not two — the control arm is the point (F118).** The plan as
written trains each circuit at `cross_track_penalty=2.0` only, and that
design cannot answer its own question. The term was measured making cornering
worse on a policy that could already hold a line (9.6-10.5 deg of slip
against 5.7-6.0), so it is remedial rather than universal: it rescues a
policy that cannot hold a line and taxes one that can. Run single-armed, a
circuit where 2.0 *hurts* produces a poor result that reads as "this circuit
is hard", and the stage concludes the exact opposite of the truth. The 0.0 arm
costs 1.5 h and is the cheapest place in the season to buy that distinction.

**What each cell reports, and why utilisation is in the table.** Completing a
circuit is the first gate, not the last. F120 measured the solved Spa lap at
mean tyre utilisation 0.090, with 0.7% of its length above 0.9 -- a clean lap
driven at a twelfth of the available grip. Torque vectoring reallocates grip
between wheels and can do nothing for a car that is not using any, so a
specialist that laps cleanly under a speed cap has cleared the completion
gate while still being useless as a TV baseline. Both numbers go in the
table, every time, so that distinction cannot be lost again.

**Scoring is `policy_eval` (D16), not the curriculum's own per-section pass.**
`spa_curriculum` scores with `spa_ppo_v2.evaluate_per_section`; this stage
re-scores every checkpoint through the one committed evaluator so the four
cells are comparable to each other and to every other result in the project.
The evaluation cap is read from each run's own summary -- passing the
curriculum's *final* cap instead is F109, which turned a 2,834.9 m result
into a reported 699.7 m.

**One seed.** Rule 5 wants three before any of this is a trend. This stage
answers a yes/no question -- does the recipe transfer at all -- and the seeds
belong on whatever survives it.

    python -m experiments.tracks_pilot.stage1_transfer [steps]
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.tracks_data import load_real_track
from experiments.tracks_pilot import policy_eval as PE
from experiments.tracks_pilot import spa_curriculum as SC
from experiments.tracks_pilot import spa_ppo_v2 as V2

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

#: Fast and tight, from the plan's stratification by fraction of lap below
#: 15 m/s: Monza 1.8% (fast), MexicoCity 5.6% (tight). Spa is 1.5% and is
#: already done, so it is the reference row rather than a fifth run.
TRACKS = ("Monza", "MexicoCity")
#: Peak lateral acceleration this car actually reaches, [MEASURED] F120 --
#: `max |a_y|` over a full Spa lap. Used only to size the curriculum's
#: starting cap, never quoted as a grip figure.
A_LAT_MAX_G = 0.97
CROSS_TRACKS = (2.0, 0.0)
STEPS = 40_000_000
N_SECTIONS = 24


def _tightest(track) -> tuple[float, float]:
    """(minimum radius, the speed that corner allows) for one circuit."""
    s = np.linspace(0.0, track.length, 8000, endpoint=False)
    k = float(np.max(np.abs(np.asarray(track.curvature(s)))))
    r = 1.0 / max(k, 1e-9)
    return r, float(np.sqrt(A_LAT_MAX_G * 9.81 * r))


def _cap_start(track) -> float:
    """Starting speed cap, below the TIGHTEST corner's own limit on THIS
    circuit.

    `spa_curriculum.CAP_START` is 9.0 m/s, derived from Spa's 11.4 m minimum
    radius (~10.4 m/s at 0.97 g) with margin. Both stage-1 circuits are
    tighter -- Monza 8.2 m and MexicoCity 7.4 m, allowing 8.84 and 8.40 m/s --
    so the Spa constant starts the curriculum ABOVE the speed its tightest
    corner permits, and that corner is unsurvivable from the first step. That
    is the exact failure D6's `the_task_is_completable` exists to catch, and
    it would have been read as "the recipe does not transfer to tight
    circuits" when the real cause was a hard-coded number.

    Derived, not guessed: 0.85x the tightest corner's limit, matching the
    0.87x margin Spa's own value carries, rounded down to 0.5 m/s.
    """
    _, v_lim = _tightest(track)
    return float(np.floor(0.85 * v_lim * 2.0) / 2.0)


def _cell(track: str, ct: float, steps: int) -> dict:
    tag = f"{track.lower()}_ct{ct:g}"
    print(f"\n{'='*72}\n  {track}, cross_track_penalty={ct:g}, {steps:,} steps\n{'='*72}")
    SC.CROSS_TRACK = ct
    trk = load_real_track(track)
    SC.CAP_START = _cap_start(trk)
    r_min, v_lim = _tightest(trk)
    print(f"  cap starts at {SC.CAP_START:g} m/s — tightest corner {r_min:.1f} m "
          f"allows {v_lim:.2f} m/s (Spa's hard-coded 9.0 would be too fast here)")
    t0 = time.time()
    SC.main(track, steps, tag)
    wall = time.time() - t0

    summary = json.loads((OUT / f"curr_{tag}_summary.json").read_text())
    eval_cap = summary["eval_cap_used"]

    env_kw = dict(V2.V2_ENV)
    env_kw["cross_track_penalty"] = ct
    r = PE.evaluate(OUT / f"curr_{tag}_policy.pt", load_real_track(track),
                    speed_cap=eval_cap, n_sections=N_SECTIONS,
                    env_kwargs=env_kw)
    print(f"\n  [D16 re-score] {r.headline()}")
    print(f"    utilisation mean {r.utilisation_mean:.3f}, "
          f"at-limit {100*r.frac_at_limit:.1f}% of the lap")
    return {
        "track": track, "cross_track_penalty": ct, "tag": tag,
        "cap_start": SC.CAP_START,
        "steps": steps, "wall_s": wall, "eval_cap_used": eval_cap,
        "headline": r.headline(), "valid": r.valid,
        "fraction_of_lap": r.fraction_of_lap, "finish_rate": r.finish_rate,
        "off_track_rate": r.off_track_rate,
        "worst_slip_deg": r.worst_slip_deg,
        "sections_over_bound": r.sections_over_bound,
        "utilisation_mean": r.utilisation_mean,
        "frac_at_limit": r.frac_at_limit,
        "speed_mean": r.speed_mean,
        "explained_variance_tail": summary.get("explained_variance_tail"),
        "passes_d6_ev_gate": summary.get("passes_d6_ev_gate"),
    }


def main(steps: int = STEPS):
    OUT.mkdir(parents=True, exist_ok=True)
    cells = [_cell(t, ct, steps) for t in TRACKS for ct in CROSS_TRACKS]

    print(f"\n\n{'='*84}\n  STAGE 1 — does the Spa recipe transfer?\n{'='*84}")
    print(f"  {'circuit':<14}{'ct':>5}{'lap':>8}{'finish':>8}{'slip':>7}"
          f"{'util':>7}{'@limit':>8}  valid")
    for c in cells:
        print(f"  {c['track']:<14}{c['cross_track_penalty']:>5g}"
              f"{100*c['fraction_of_lap']:>7.1f}%{100*c['finish_rate']:>7.0f}%"
              f"{c['worst_slip_deg']:>7.1f}{c['utilisation_mean']:>7.3f}"
              f"{100*c['frac_at_limit']:>7.1f}%  {c['valid']}")

    # --- the question the stage exists to answer -----------------------
    print(f"\n  Is cross_track_penalty=2.0 a finding or a Spa constant?")
    verdicts = []
    for t in TRACKS:
        a = next(c for c in cells if c["track"] == t
                 and c["cross_track_penalty"] == 2.0)
        b = next(c for c in cells if c["track"] == t
                 and c["cross_track_penalty"] == 0.0)
        # Only compare laps the project is allowed to quote (rule 4).
        if not (a["valid"] and b["valid"]):
            v = "INCONCLUSIVE — a cell is outside the tyre fit, rule 4"
        else:
            d = a["fraction_of_lap"] - b["fraction_of_lap"]
            if abs(d) < 0.05:
                v = f"no measurable difference ({100*d:+.1f} pp)"
            elif d > 0:
                v = f"2.0 HELPS here ({100*d:+.1f} pp of lap)"
            else:
                v = f"2.0 HURTS here ({100*d:+.1f} pp of lap) — remedial, as F118 predicts"
        verdicts.append({"track": t, "verdict": v})
        print(f"    {t:<14}{v}")

    print(f"\n  Usable as a torque-vectoring baseline? (F120: Spa is 0.7% at the limit)")
    for c in cells:
        note = ("yes" if c["frac_at_limit"] > 0.05 else
                "NO — completes the lap without working the tyres")
        print(f"    {c['track']:<14}ct={c['cross_track_penalty']:g}  "
              f"{100*c['frac_at_limit']:.1f}% at the limit  {note}")

    (OUT / "stage1_transfer_results.json").write_text(json.dumps(
        {"steps": steps, "n_sections": N_SECTIONS, "cells": cells,
         "verdicts": verdicts}, indent=2) + "\n")
    print(f"\n  wrote stage1_transfer_results.json")


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else STEPS)
