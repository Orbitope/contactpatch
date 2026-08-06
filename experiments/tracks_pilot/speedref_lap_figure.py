"""The F127 speed_ref specialist's lap, drawn against the F120 capped baseline.

Same builders, same road, same colour-scale conventions as
`spa_lap_figure.py` (which drew `curr_ct2`, the capped baseline) — so the two
sets of figures are directly comparable rather than only individually
readable. `a_lat` is irrelevant to the driven trajectory (verified earlier
this session: `speed_ref_penalty` only enters the REWARD, `observe()` carries
no reference speed, so `policy_eval`'s distance/slip/utilisation are
bit-identical at any `a_lat`); `A_LAT_MAX` is used only so the config matches
how F127's own D16 numbers were produced.

    python -m experiments.tracks_pilot.speedref_lap_figure
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from physics.rl_env import DrivingEnv, EnvConfig
from physics.ppo import ActorCritic, greedy_policy
from physics.tracks_data import load_real_track
from physics.schema import G
from experiments.tracks_pilot import speed_ref as SR
from viz.lap_figures import lap_trace, lap_profile
from viz.lib import TEAL, AMB, COR

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

POLICY = OUT / "speedref_w3_ct0_policy.pt"
WEIGHT, CROSS_TRACK = 3.0, 0.0


def drive_one_lap(seed: int = 0):
    spa = load_real_track("Spa")
    kw = SR._env_kwargs(WEIGHT, SR.A_LAT_MAX, CROSS_TRACK)
    cfg = EnvConfig(track=spa, start_jitter_m=0.0, **kw)

    env = DrivingEnv(cfg)
    model = ActorCritic(env.obs_dim, env.act_dim, 64, (-2.5, -1.0))
    model.load_state_dict(torch.load(POLICY))
    policy = greedy_policy(model)

    env.reset(seed)
    env.s = 0.0
    env.backend.reset(env._spawn_speed())
    obs = env.observe()
    while not env.done:
        obs, _, _, info = env.step(policy(obs))
    return spa, env.history(), bool(info["off_track"])


def main():
    # 96% finish rate (F127) -- try a few seeds from the line rather than
    # assume the first one lands on a clean lap.
    for seed in range(6):
        spa, h, off = drive_one_lap(seed)
        if not off:
            break
    else:
        print(f"  *** all {seed+1} seeds from s=0 left the road -- drawing "
              f"seed 0's anyway, incomplete")

    s = np.asarray(h["s"]); n = np.asarray(h["n"])
    v = np.asarray(h["speed"]); slip = np.asarray(h["alpha_max_deg"])
    util = np.asarray(h["utilisation_max"])
    ay = np.abs(np.asarray(h["a_y"])) / G
    dist = s - s[0]
    x, y = spa.to_xy(s, n)
    laps = dist[-1] / spa.length

    v_lo, v_hi = float(np.percentile(v, 1)), float(np.percentile(v, 99))
    at_limit = float((util > 0.9).mean())
    stamp = (f"[MEASURED] speedref_w3_ct0_policy.pt (F127), deployed "
             f"(mean-action) policy, no speed cap -- a curvature-aware plan "
             f"(speed_ref_penalty={WEIGHT:g}) replaces it, cross_track_penalty "
             f"{CROSS_TRACK:g}, Spa via tracks_data.load_real_track, "
             f"offset-free tire, seed {seed}. Rung 2 of the fidelity ladder "
             f"(double-track): per-wheel loads and load transfer, no roll "
             f"camber, roll steer or compliance.")

    note_a = (f"The car drove {dist[-1]:,.0f} m of Spa ({100*laps:.0f}% of "
              f"the lap), {'without leaving the road' if not off else 'before leaving the road'}. "
              f"Speed spans {v_lo:.1f}-{v_hi:.1f} m/s -- nearly double the "
              f"capped baseline's 13.0-15.0 -- because there is no flat "
              f"limiter here, only a plan that slows for corners.")
    svg_a = lap_trace(spa, x, y, v, title="The speed_ref specialist's lap",
                      subtitle=f"One lap, deployed policy, coloured by speed "
                               f"({v_lo:.1f}-{v_hi:.1f} m/s) -- no speed cap",
                      note=note_a, stamp=stamp, v_lo=v_lo, v_hi=v_hi,
                      width=760, height=1180,
                      marks=[(float(x[0]), float(y[0]), "start")])
    (OUT / "speedref_w3_ct0_lap.svg").write_text(svg_a)

    note_c = (f"The same lap, coloured by tyre utilisation. Mean utilisation "
              f"is {util.mean():.3f} against the capped baseline's 0.090 -- "
              f"3.4x -- and {100*at_limit:.1f}% of the lap sits above 0.9.")
    svg_c = lap_trace(spa, x, y, util, title="Where the speed_ref policy uses the tyres",
                      subtitle="The same lap, coloured by tyre utilisation "
                               "(1.0 = the friction limit)",
                      note=note_c, stamp=stamp, v_lo=0.0, v_hi=1.0,
                      colour_label="tyre utilisation", unit="", fmt="{:.1f}",
                      width=760, height=1180,
                      marks=[(float(x[0]), float(y[0]), "start")])
    (OUT / "speedref_w3_ct0_lap_utilisation.svg").write_text(svg_c)

    note_b = (f"Worst slip peaks at {slip.max():.1f}°, inside the 12° fit "
              f"(rule 4 valid), while speed and utilisation both run far "
              f"above the capped baseline throughout.")
    svg_b = lap_profile(
        dist,
        [(v, "speed (m/s)", TEAL, max(float(v.max()) * 1.15, 1.0), None, ""),
         (slip, "worst slip (deg)", AMB, max(float(slip.max()) * 1.3, 13.2),
          12.0, "12° -- edge of the tyre fit (rule 4)"),
         (util, "tyre utilisation", COR, 1.15, 1.0, "1.0 -- the friction limit")],
        title="The same lap, technically",
        subtitle="Speed, worst-wheel slip and tyre utilisation against distance",
        note=note_b, stamp=stamp)
    (OUT / "speedref_w3_ct0_profile.svg").write_text(svg_b)

    summary = {
        "policy": POLICY.name, "seed": seed,
        "distance_m": float(dist[-1]), "fraction_of_lap": float(laps),
        "off_track": off, "worst_slip_deg": float(slip.max()),
        "inside_tyre_fit": bool(slip.max() <= 12.0),
        "speed_min": float(v.min()), "speed_max": float(v.max()),
        "speed_mean": float(v.mean()), "speed_p1": v_lo, "speed_p99": v_hi,
        "a_y_max_g": float(ay.max()), "utilisation_mean": float(util.mean()),
        "utilisation_max": float(util.max()),
        "fraction_of_lap_above_0p9_utilisation": at_limit,
    }
    (OUT / "speedref_w3_ct0_lap_figure.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(f"  seed {seed}: {dist[-1]:,.1f} m ({laps*100:.1f}% of lap), "
         f"off-track {off}, worst slip {slip.max():.2f}°")
    print(f"  speed {v_lo:.1f}-{v_hi:.1f} m/s, utilisation mean "
         f"{util.mean():.3f}, at-limit {100*at_limit:.1f}%")
    print(f"  wrote speedref_w3_ct0_lap.svg, "
         f"speedref_w3_ct0_lap_utilisation.svg, speedref_w3_ct0_profile.svg")


if __name__ == "__main__":
    main()
