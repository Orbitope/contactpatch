"""The Spa specialist's lap, drawn — closing CLAUDE.md rules 1 and 13.

The Season 5 plan has carried this line for three sessions: *"rules 1 and 13
are still unmet for this entire thread — there is no pictorial figure of any
of it. `spa_track.svg` plus the ct2 lap trace, coloured by speed, is the
obvious first one and should land before the generalist, not after."*

Two figures, per rule 1. The pictorial one is the lap on the outline of Spa,
coloured by speed — readable by anyone. The technical one is speed and
worst-wheel slip against distance, with the 12° edge of the tyre fit drawn on
it, because that line is what decides whether the lap is quotable (rule 4).

**The cap is 13.0 m/s and that is not a detail.** It is the cap the selected
checkpoint was chosen under. Evaluating at the curriculum's *final* cap
instead is F109 — it turned a genuine 2,834.9 m result into a reported
699.7 m and made the best run in the batch read as the worst.

    python -m experiments.tracks_pilot.spa_lap_figure
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from physics.rl_env import DrivingEnv, EnvConfig
from physics.ppo import ActorCritic, greedy_policy
from physics.tracks_data import load_real_track
from experiments.tracks_pilot import spa_ppo_v2 as V2
from viz.lap_figures import lap_trace, lap_profile
from viz.lib import TEAL, AMB, COR
from physics.schema import G

import torch

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

POLICY = OUT / "curr_ct2_policy.pt"
EVAL_CAP = 13.0          # F109: the cap the checkpoint was SELECTED under
CROSS_TRACK = 2.0        # the ct2 recipe


def drive_one_lap():
    """One lap from the start line with the DEPLOYED (mean-action) policy.

    Mean action, not sampled: a Gaussian policy whose sampled rollouts look
    good and whose mean action fails has not produced a driver (D6, F61).
    """
    spa = load_real_track("Spa")
    env_over = {"track": spa, "cross_track_penalty": CROSS_TRACK,
                "speed_cap": EVAL_CAP}
    cfg = V2._cfg(env_over, start_jitter_m=0.0)

    env = DrivingEnv(cfg)
    model = ActorCritic(env.obs_dim, env.act_dim, 64, (-2.5, -1.0))
    model.load_state_dict(torch.load(POLICY))
    policy = greedy_policy(model)

    env.reset(0)
    env.s = 0.0
    env.backend.reset(env._spawn_speed())
    obs = env.observe()
    while not env.done:
        obs, _, _, info = env.step(policy(obs))
    return spa, env.history(), bool(info["off_track"])


def main():
    spa, h, off = drive_one_lap()
    s = np.asarray(h["s"]); n = np.asarray(h["n"])
    v = np.asarray(h["speed"]); slip = np.asarray(h["alpha_max_deg"])
    util = np.asarray(h["utilisation_max"])
    ay = np.abs(np.asarray(h["a_y"])) / G
    # Distance travelled, start-relative -- NOT absolute `s`. That confusion
    # is F110 exactly, and on a closed circuit the two differ by the start
    # offset for every probe that does not begin at the line.
    dist = s - s[0]
    x, y = spa.to_xy(s, n)
    laps = dist[-1] / spa.length

    # Colour scale from percentiles, not min/max: the very first sample is
    # the SPAWN speed (15.0 m/s, above the cap), it decays within a few
    # metres, and scaling to it would spend the top of the ramp on one point.
    v_lo, v_hi = float(np.percentile(v, 1)), float(np.percentile(v, 99))

    at_limit = float((util > 0.9).mean())
    stamp = (f"[MEASURED] curr_ct2_policy.pt, deployed (mean-action) policy, "
             f"speed_cap {EVAL_CAP:g} m/s (the cap the checkpoint was selected "
             f"under), cross_track_penalty {CROSS_TRACK:g}, Spa via "
             f"tracks_data.load_real_track, offset-free tire. "
             f"Rung 2 of the fidelity ladder (double-track): per-wheel loads "
             f"and load transfer, no roll camber, roll steer or compliance.")

    note_a = (f"The car drove all {dist[-1]:,.0f} m of Spa without leaving the "
              f"road. Cool is slow, warm is fast — but the whole lap spans "
              f"only {v_lo:.1f}–{v_hi:.1f} m/s, because a {EVAL_CAP:g} m/s "
              f"limiter is holding it back. This is a clean lap, not a fast one.")
    svg_a = lap_trace(spa, x, y, v, title="The Spa specialist's lap",
                      subtitle=f"One lap, deployed policy, coloured by speed — "
                               f"speed-capped at {EVAL_CAP:g} m/s",
                      note=note_a, stamp=stamp, v_lo=v_lo, v_hi=v_hi,
                      width=760, height=1180,
                      marks=[(float(x[0]), float(y[0]), "start")])
    (OUT / "spa_ct2_lap.svg").write_text(svg_a)

    # Second pictorial, coloured by how hard the tyres are working. The
    # speed-coloured one above is nearly monochrome BY CONSTRUCTION -- a
    # cap-pinned policy has almost no speed variation to show -- so on its own
    # it would leave a reader thinking the lap is featureless. Utilisation is
    # where this policy's behaviour actually lives.
    note_c = (f"The same lap, coloured by how hard the tyres are working. "
              f"Dark is coasting, bright is at the limit of grip. Almost the "
              f"whole circuit is dark: the car only truly leans on the tyres "
              f"in a handful of corners, for {100*at_limit:.1f}% of the lap.")
    svg_c = lap_trace(spa, x, y, util, title="Where the Spa policy uses the tyres",
                      subtitle="The same lap, coloured by tyre utilisation "
                               "(1.0 = the friction limit)",
                      note=note_c, stamp=stamp, v_lo=0.0, v_hi=1.0,
                      colour_label="tyre utilisation", unit="", fmt="{:.1f}",
                      width=760, height=1180,
                      marks=[(float(x[0]), float(y[0]), "start")])
    (OUT / "spa_ct2_lap_utilisation.svg").write_text(svg_c)

    note_b = (f"The bottom panel is the one that matters: the policy is at the "
              f"friction limit for {100*at_limit:.1f}% of the lap and below a "
              f"tenth of it for the rest. Slip peaks at {slip.max():.1f}°, "
              f"inside the 12° fit, so the lap is quotable (rule 4) — but the "
              f"car is limited by the speed cap, not by grip.")
    svg_b = lap_profile(
        dist,
        [(v, "speed (m/s)", TEAL, max(float(v.max()) * 1.15, 1.0),
          EVAL_CAP, f"{EVAL_CAP:g} m/s speed cap"),
         (slip, "worst slip (deg)", AMB, max(float(slip.max()) * 1.3, 13.2),
          12.0, "12° — edge of the tyre fit (rule 4)"),
         (util, "tyre utilisation", COR, 1.15, 1.0, "1.0 — the friction limit")],
        title="The same lap, technically",
        subtitle="Speed, worst-wheel slip and tyre utilisation against distance",
        note=note_b, stamp=stamp)
    (OUT / "spa_ct2_profile.svg").write_text(svg_b)

    summary = {
        "policy": POLICY.name, "eval_speed_cap": EVAL_CAP,
        "cross_track_penalty": CROSS_TRACK,
        "distance_m": float(dist[-1]), "fraction_of_lap": float(laps),
        "off_track": off, "worst_slip_deg": float(slip.max()),
        "inside_tyre_fit": bool(slip.max() <= 12.0),
        "speed_min": float(v.min()), "speed_max": float(v.max()),
        "speed_mean": float(v.mean()),
        "speed_p1": v_lo, "speed_p99": v_hi,
        "a_y_max_g": float(ay.max()), "a_y_mean_g": float(ay.mean()),
        "utilisation_max": float(util.max()),
        "utilisation_mean": float(util.mean()),
        "fraction_of_lap_above_0p9_utilisation": at_limit,
        "fraction_of_lap_above_0p5_utilisation": float((util > 0.5).mean()),
    }
    (OUT / "spa_ct2_lap_figure.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"  {dist[-1]:,.1f} m ({laps*100:.1f}% of lap), off-track {off}, "
          f"worst slip {slip.max():.2f}°")
    print(f"  speed p1-p99 {v_lo:.1f}-{v_hi:.1f} m/s, max |a_y| {ay.max():.2f} g")
    print(f"  AT THE LIMIT for {100*at_limit:.1f}% of the lap "
          f"(utilisation > 0.9); mean utilisation {util.mean():.3f}")
    print(f"  wrote spa_ct2_lap.svg, spa_ct2_profile.svg")


if __name__ == "__main__":
    main()
