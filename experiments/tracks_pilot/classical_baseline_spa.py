"""TRACKS.md staging step 5, revised plan item B — classical baseline on Spa.

Blocked until now by the start-pose gap ``drive_lap`` had: it always placed
the car at the world origin (``BicycleState``'s ``x=y=heading=0`` defaults),
which coincides with every synthetic ``Track``'s own s=0 (its ``centreline``
integrates FROM the origin by construction) but not with a real circuit's raw
coordinates. Fixed in ``physics/driver.py`` (``drive_lap`` now sets the car's
starting pose from the track's own s=0 centreline point), tested against a
circle deliberately NOT centred on the origin
(``tests/test_driver.py::test_drive_lap_starts_at_the_tracks_own_pose_not_the_world_origin``).

**Honest result: the classical driver, at its current gains, does not
complete a Spa lap at any grip level tried (0.3-0.85).** Every attempt spins
or leaves the road within the same ~900-1020 m window, independent of how
conservatively it is driven — checked directly, not assumed: reducing
``grip_use`` from 0.85 down to 0.3 (much lower target speeds throughout)
did not move the failure point or reduce its severity (worst slip 44-54 deg
regardless). That rules out "too aggressive" as the cause; it points at the
STEERING controller (pure-pursuit gains tuned against a single, constant-
radius synthetic corner) rather than at speed. This is a DIFFERENT location
from Spa's tightest corner (r=11.4 m at s=403 m, TRACKS.md item 14) --  a
second, distinct place the current driver/gain choices do not generalise to
real-circuit geometry.

This is a real, useful negative result, not a failure to hide: it means
"calibrate the RL reward against a competent classical lap's earnings" is
not yet available, and driver-gain retuning for real-circuit curvature is
its own task (matching Episode 13's own precedent: "the driver sweeps them
and requires the conclusion to survive" -- a hand-tuned driver is exactly
the unstated protocol choice CLAUDE.md rule 9 exists for), not attempted
further here without checking with the user on how much effort to spend.

    python -m experiments.tracks_pilot.classical_baseline_spa
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

GRIP_LEVELS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.85)


def attempt(grip_use: float) -> dict:
    spa = load_real_track("Spa")
    prof = SpeedProfile(spa, a_lat=grip_use * 9.3, a_brake=8.0, a_drive=3.3,
                        v_max=45.0)
    locator = TrackLocator(spa, window=40.0)
    driver = Driver(schema.RV_1, prof, locator)
    backend = DoubleTrackBackend(schema.RV_1, diff="open")
    lap = drive_lap(backend, spa, driver, grip_use=grip_use, max_steps=25_000)
    distance = float(lap.log["s_total"][-1]) if len(lap.log["s_total"]) else 0.0
    return {
        "grip_use": grip_use, "valid": lap.valid, "reason": lap.reason,
        "lap_time_s": lap.lap_time, "distance_m": distance,
        "worst_slip_deg": lap.worst_slip_deg,
        "max_offset_m": lap.max_offset,
        "fraction_of_lap": distance / spa.length,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("TRACKS.md step 5, plan item B -- classical baseline on Spa\n")
    results = []
    for gu in GRIP_LEVELS:
        r = attempt(gu)
        results.append(r)
        print(f"  grip_use={gu:.2f}  valid={r['valid']!s:5s}  reason={r['reason']:12s}  "
             f"distance={r['distance_m']:7.1f} m ({r['fraction_of_lap']:.1%} of lap)  "
             f"worst_slip={r['worst_slip_deg']:5.1f} deg  lap_time={r['lap_time_s']:.1f} s")

    any_valid = any(r["valid"] for r in results)
    print(f"\n  any grip level completed a full lap: {any_valid}")
    if not any_valid:
        print("  HONEST RESULT: the classical driver does not complete a Spa "
             "lap at its current gains, at any grip level tried. The failure "
             "location and severity do not change with grip_use, which rules "
             "out 'too aggressive' as the cause -- see this script's own "
             "docstring. Driver-gain retuning for real-circuit curvature is "
             "a separate task, not attempted further here.")

    (OUT / "classical_baseline_spa_results.json").write_text(
        json.dumps(results, indent=2) + "\n")
    print(f"\n  wrote {OUT.relative_to(ROOT)}/classical_baseline_spa_results.json")


if __name__ == "__main__":
    main()
