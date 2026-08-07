"""Season 5 stage 1 — does the `speed_ref` recipe transfer past Spa?

The staging plan's original question: *"If `cross_track_penalty=2.0` does
not also solve a fast and a tight circuit, it is a Spa constant, not a
finding."* Monza is the fast circuit, MexicoCity the tight one.

**This replaces `stage1_transfer_SUPERSEDED_by_speedref.py`, not extends
it.** That version trained `spa_curriculum`'s flat speed cap + cross-track
sweep. F121 showed the cap itself is the wrong instrument (bound to the road
99.6% of the lap on Spa, 0.7% at the tyre limit) and `speed_ref` replaced it
before stage 1 ever ran (HANDOFF: "Run order changed"). Running the old
stage 1 now would characterise a recipe already superseded on its own home
track — so this is a fresh build on `speed_ref._run`, not a patch.

**Still four runs, the control arm still not optional (F118).**
`cross_track_penalty` was measured making cornering worse on a policy that
could already hold a line (Spa: 9.6-10.5 deg of slip against 5.7-6.0 without
it). Single-armed, a circuit where the term hurts reads as "this circuit is
hard" and the stage concludes the opposite of the truth.

**One weight, not two.** `speed_ref.WEIGHTS` includes 10.0, which was never
validated on Spa either (F127 is `w=3` only) — testing an unvalidated weight
on TWO new circuits at once would confound "does the recipe transfer" with
"does w=10 work at all". `w=3` is the one proven result; that is what
transfers or does not.

**No per-track baseline to beat, and that is stated rather than faked.**
Spa has F120 (capped baseline) and F125 (classical lap-time target); neither
exists for Monza or MexicoCity. This stage reports each cell against
`limit_ceiling` (the plan's own per-track grip-limited fraction, already
measured for both circuits in `speed_ref.limit_ceiling`'s docstring) and
against rule 4, and compares the two `cross_track` arms to each other --
it does not manufacture a false "vs baseline" number where none exists.

    python -m experiments.tracks_pilot.stage1_speedref [steps]
"""

from __future__ import annotations

import json
from pathlib import Path

from physics.tracks_data import load_real_track
from experiments.tracks_pilot import speed_ref as SR

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

TRACKS = ("Monza", "MexicoCity")
WEIGHT = 3.0
CROSS_TRACKS = (0.0, 2.0)
STEPS = SR.STEPS  # 40M, matching the run that produced F127


def main(steps: int = STEPS):
    OUT.mkdir(parents=True, exist_ok=True)
    cells = []
    for track in TRACKS:
        for ct in CROSS_TRACKS:
            r = SR._run(WEIGHT, steps, cross_track=ct, track_name=track)
            r["track"] = track
            cells.append(r)

    print(f"\n\n{'='*88}\n  STAGE 1 (speed_ref) — does the recipe transfer past Spa?"
         f"\n{'='*88}")
    print(f"  {'circuit':<14}{'ct':>5}{'lap':>8}{'finish':>8}{'slip':>7}"
         f"{'util':>7}{'@limit':>8}  valid")
    for c in cells:
        print(f"  {c['track']:<14}{c['cross_track_penalty']:>5g}"
             f"{100*c['fraction_of_lap']:>7.1f}%{100*c['finish_rate']:>7.0f}%"
             f"{c['worst_slip_deg']:>7.1f}{c['utilisation_mean']:>7.3f}"
             f"{100*c['frac_at_limit']:>7.1f}%  {c['valid']}")

    print(f"\n  Per-track grip-limited ceiling (speed_ref.limit_ceiling):")
    ceilings = {}
    for track in TRACKS:
        c = SR.limit_ceiling(load_real_track(track))
        ceilings[track] = c
        print(f"    {track:<14}{100*c:.1f}%")

    print(f"\n  Is cross_track_penalty=2.0 a finding or a Spa constant here?")
    verdicts = []
    for track in TRACKS:
        a = next(c for c in cells if c["track"] == track
                and c["cross_track_penalty"] == 2.0)
        b = next(c for c in cells if c["track"] == track
                and c["cross_track_penalty"] == 0.0)
        if not (a["valid"] and b["valid"]):
            v = "INCONCLUSIVE -- a cell is outside the tyre fit, rule 4"
        else:
            d_util = a["utilisation_mean"] - b["utilisation_mean"]
            d_lap = a["fraction_of_lap"] - b["fraction_of_lap"]
            if d_lap < -0.05:
                v = f"2.0 COSTS the lap here ({100*d_lap:+.1f} pp of lap)"
            elif d_util < -0.03:
                v = (f"2.0 taxes utilisation ({d_util:+.3f}) -- matches F118's "
                    f"remedial-not-universal reading")
            elif d_lap > 0.05:
                v = f"2.0 HELPS complete the lap here ({100*d_lap:+.1f} pp)"
            else:
                v = f"no measurable difference (lap {100*d_lap:+.1f} pp, util {d_util:+.3f})"
        verdicts.append({"track": track, "verdict": v})
        print(f"    {track:<14}{v}")

    print(f"\n  Did any cell reach the limit without losing the lap?")
    for c in cells:
        ceiling = ceilings[c["track"]]
        win = (c["valid"] and c["fraction_of_lap"] >= 0.95
              and c["frac_at_limit"] >= 0.5 * ceiling)
        print(f"    {c['track']:<14}ct={c['cross_track_penalty']:g}  "
             f"{100*c['frac_at_limit']:.1f}% at limit vs {100*ceiling/2:.1f}% "
             f"win threshold  {'YES' if win else ''}")

    (OUT / "stage1_speedref_results.json").write_text(json.dumps(
        {"weight": WEIGHT, "cross_tracks": list(CROSS_TRACKS),
         "steps": steps, "ceilings": ceilings,
         "cells": cells, "verdicts": verdicts}, indent=2) + "\n")
    print(f"\n  wrote stage1_speedref_results.json")


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else STEPS)
