"""RL_PLAN Phase 0 — what is a good lap, and does one exist at all?

The plan puts this first and it had never been run: *"We do not know what a
good lap time IS on this car and circuit. The classical driver laps cleanly at
`v_max=12` and spins at 45; its fastest CLEAN lap has never been measured.
Bisect `v_max` (and `grip_use`) to find it."*

**Why it is first.** Every phase below it is tuning an RL policy toward a
number nobody has measured. And the plan states its own stop condition: *"if
no `v_max` yields a valid clean lap, then rule 4 and this vehicle model may be
incompatible at speed, and every phase below is chasing a target that does not
exist. That would be the single most important thing to find out, and it costs
minutes."*

**Why the existing sweep did not answer it.** `classical_baseline_spa.py`
sweeps `grip_use` at a **fixed `v_max=45`** and spins or leaves the road at
every level, covering 12-15% of a lap. That is not evidence that no clean lap
exists — it is one point on the wrong axis. This bisects the axis the plan
named.

**What this number is and is not.** It is **not** an external validation
(rule 2): it is our own code, driving with a global speed plan the RL policy
never gets, so it is an upper reference rather than a ground truth. State it
that way wherever it is quoted. It is the honest denominator for "how good is
this policy", which currently has none.

    python -m experiments.tracks_pilot.phase0_target
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from physics import schema
from physics.double_track import DoubleTrackBackend
from physics.driver import Driver, SpeedProfile, TrackLocator, drive_lap
from physics.tracks_data import load_real_track

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

TRACK = "Spa"
#: Swept, not fixed at 45 the way the existing baseline did. 12 is the value
#: the plan records as lapping cleanly, so the answer is bracketed already.
#:
#: **19-23 and grip 0.70 are here because F125's headline came from a finer
#: sweep that this grid did not contain (F139/F140).** Re-running the script
#: wrote an artefact whose best row was 362.1 s at v_max 20, while the finding
#: quoted 347.6 s at v_max 21 — a number the file had no way to produce. The
#: result was right and reproduced exactly on a re-run; it simply was not
#: *persisted*, so an audit against the named artefact could not confirm it.
#: The grid a finding is quoted from has to be the grid the script actually
#: runs, or the artefact silently stops being evidence for the finding.
V_MAX = (12.0, 14.0, 16.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0,
         28.0, 34.0, 45.0)
#: The lateral budget the PLAN is built for, as a fraction of the tyre's
#: measured 0.97 g peak. Three levels: conservative, mid, and at the limit --
#: 0.70 is the one F125's fastest-valid row (330.8 s) came from.
GRIP = (0.60, 0.70, 0.85)
SLIP_BOUND_DEG = 12.0


def attempt(v_max: float, grip_use: float) -> dict:
    trk = load_real_track(TRACK)
    prof = SpeedProfile(trk, a_lat=grip_use * 9.3, a_brake=8.0, a_drive=3.3,
                        v_max=v_max, wrap=True)
    driver = Driver(schema.RV_1, prof, TrackLocator(trk, window=40.0))
    backend = DoubleTrackBackend(schema.RV_1, diff="open")
    lap = drive_lap(backend, trk, driver, grip_use=grip_use, max_steps=60_000)
    dist = float(lap.log["s_total"][-1]) if len(lap.log["s_total"]) else 0.0
    slip = float(lap.worst_slip_deg)
    return {
        "v_max": v_max, "grip_use": grip_use,
        "completed": bool(lap.valid), "reason": lap.reason,
        "lap_time_s": lap.lap_time, "distance_m": dist,
        "fraction_of_lap": dist / trk.length,
        "worst_slip_deg": slip,
        # Rule 4 is a separate gate from "did it finish": a lap driven at 30
        # degrees of slip is a statement about our curve fit, not a lap time.
        "inside_tyre_fit": bool(slip <= SLIP_BOUND_DEG),
        "rule4_valid": bool(lap.valid and slip <= SLIP_BOUND_DEG),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    trk = load_real_track(TRACK)
    print(f"RL_PLAN Phase 0 — the classical driver's fastest CLEAN lap of "
          f"{TRACK} ({trk.length:.0f} m)\n")
    print(f"  {'v_max':>7}{'grip':>7}{'done':>7}{'lap s':>9}{'% lap':>8}"
          f"{'slip':>8}  rule 4")
    rows = []
    for g in GRIP:
        for v in V_MAX:
            r = attempt(v, g)
            rows.append(r)
            print(f"  {v:>7.1f}{g:>7.2f}{str(r['completed']):>7}"
                  f"{(r['lap_time_s'] or 0):>9.1f}"
                  f"{100*r['fraction_of_lap']:>7.1f}%{r['worst_slip_deg']:>7.1f}°"
                  f"  {'VALID' if r['rule4_valid'] else ''}")

    valid = [r for r in rows if r["rule4_valid"]]
    print()
    if not valid:
        print("  *** NO v_max PRODUCES A RULE-4-VALID CLEAN LAP.")
        print("      This is RL_PLAN Phase 0's stop-and-rethink condition. The")
        print("      RL phases below it are chasing a target that does not")
        print("      exist, and rule 4 and this vehicle model may simply be")
        print("      incompatible at speed on this circuit.")
        best = None
    else:
        best = min(valid, key=lambda r: r["lap_time_s"])
        print(f"  TARGET: {best['lap_time_s']:.1f} s at v_max="
              f"{best['v_max']:.0f} m/s, grip_use={best['grip_use']:.2f}, "
              f"worst slip {best['worst_slip_deg']:.1f}°")
        print(f"  [MEASURED] our own classical driver, which gets a global "
              f"speed plan the RL policy does not. An upper reference, NOT an "
              f"external validation (rule 2).")

    # `target` is the FASTEST rule-4-valid lap. That is NOT automatically the
    # quotable one: F125 quotes 347.6 s rather than this 330.8 s because the
    # fastest sits 0.4 deg from the 12 deg bound, and rule 12 says report to
    # the precision the inputs support. That is a judgement, not a threshold --
    # so rather than bake in a margin nobody has justified, every valid row is
    # written out with its own margin, and the judgement stays reconstructible
    # from the artefact. F139 mistook this gap for a wrong measurement; the
    # rows were simply not in the file (F140).
    for r in rows:
        r["margin_to_bound_deg"] = SLIP_BOUND_DEG - r["worst_slip_deg"]
    (OUT / "phase0_target.json").write_text(json.dumps(
        {"track": TRACK, "track_length_m": float(trk.length),
         "slip_bound_deg": SLIP_BOUND_DEG, "attempts": rows,
         "target_fastest_valid": best,
         "valid_by_lap_time": sorted(
             ({k: r[k] for k in ("v_max", "grip_use", "lap_time_s",
                                 "worst_slip_deg", "margin_to_bound_deg")}
              for r in rows if r["rule4_valid"]),
             key=lambda r: r["lap_time_s"]),
         "note": ("`target_fastest_valid` is the quickest rule-4-valid lap. "
                  "The QUOTED target may differ: rule 12 discounts laps with "
                  "little margin to the 12 deg bound. See `valid_by_lap_time` "
                  "and FINDINGS F125/F140."),
         "target": best}, indent=2) + "\n")
    print(f"\n  wrote phase0_target.json")


if __name__ == "__main__":
    main()
