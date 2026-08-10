"""F134's baseline-vs-TV thread, drawn — one lap per checkpoint, three figures
each, same builders and colour scale as `speedref_lap_figure.py` so every
variant is directly comparable.

**Why this exists rather than another one-off script.** F134 found the
run's own D16 evaluator silently defaulted `tv_mode="none"`, which is exactly
the class of defect rule 1/13 exist to catch early: a number with no figure
behind it is easy to get away with printing wrong. This script always builds
the env with the SAME `tv_mode` the checkpoint was trained under (the fix
from F134), so the figure and the corrected D16 number can never diverge the
way the log line and the truth did.

Run once per checkpoint as it lands, or with no args to sweep every
checkpoint currently on disk for this thread (baseline/TV x seeds 0-2, only
the ones that exist).

    python -m experiments.tracks_pilot.tv_lap_figure [tag]
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

WEIGHT, CROSS_TRACK = 3.0, 0.0
ENVELOPE_PENALTY, ENVELOPE_EXPONENT = 3.0, 2.0

#: F120's capped baseline -- the pre-speed_ref reference every one of these
#: figures is captioned against, same as speedref_lap_figure.py.
CAPPED_BASELINE_UTIL = 0.090

#: (tv_mode, tag_stem) for every leg this thread runs. seed 0 has no `_s{n}`
#: suffix (speed_ref.py's own tag convention -- V2.SEED).
VARIANTS = [("none", "tvbaseline"), ("end_to_end", "tv_e2e")]
SEEDS = (0, 1, 2)


def _policy_path(tag_stem: str, seed: int) -> Path:
    suffix = "" if seed == 0 else f"_s{seed}"
    return OUT / f"speedref_w3_ct0{suffix}_{tag_stem}_policy.pt"


def drive_one_lap(track, env_kwargs, policy_path, seed: int):
    cfg = EnvConfig(track=track, start_jitter_m=0.0, **env_kwargs)
    env = DrivingEnv(cfg)
    # Scalar log_std (see policy_eval.py / speed_ref.py's identical fix):
    # this is a LOAD path, load_state_dict overwrites the VALUE, only the
    # SHAPE (from env.act_dim, which varies with tv_mode) has to be right.
    model = ActorCritic(env.obs_dim, env.act_dim, 64, -1.5)
    model.load_state_dict(torch.load(policy_path))
    policy = greedy_policy(model)

    env.reset(seed)
    env.s = 0.0
    env.backend.reset(env._spawn_speed())
    obs = env.observe()
    while not env.done:
        obs, _, _, info = env.step(policy(obs))
    return env.history(), bool(info["off_track"])


def make_figures(tv_mode: str, tag_stem: str, seed: int, track_name: str = "Spa"):
    policy_path = _policy_path(tag_stem, seed)
    if not policy_path.exists():
        return None

    track = load_real_track(track_name)
    env_kwargs = SR._env_kwargs(WEIGHT, SR.A_LAT_MAX, CROSS_TRACK,
                                ENVELOPE_PENALTY, ENVELOPE_EXPONENT, tv_mode)

    out_tag = f"{tag_stem}{'' if seed == 0 else f'_s{seed}'}"
    label = "TV (end_to_end)" if tv_mode == "end_to_end" else "baseline (tv_mode=none)"

    # F127's pattern: 96% finish, not 100% -- try a few start seeds for a
    # clean lap rather than assume the first lands on one.
    for drive_seed in range(6):
        h, off = drive_one_lap(track, env_kwargs, policy_path, drive_seed)
        if not off:
            break
    else:
        print(f"  [{out_tag}] *** all {drive_seed+1} seeds from s=0 left the "
              f"road -- drawing seed 0's anyway, incomplete")

    s = np.asarray(h["s"]); n = np.asarray(h["n"])
    v = np.asarray(h["speed"]); slip = np.asarray(h["alpha_max_deg"])
    util = np.asarray(h["utilisation_max"])
    ay = np.abs(np.asarray(h["a_y"])) / G
    dist = s - s[0]
    x, y = track.to_xy(s, n)
    frac = dist[-1] / track.length

    v_lo, v_hi = float(np.percentile(v, 1)), float(np.percentile(v, 99))
    at_limit = float((util > 0.9).mean())
    stamp = (f"[MEASURED] {policy_path.name}, deployed (mean-action) policy, "
            f"speed_ref_penalty={WEIGHT:g}, cross_track_penalty={CROSS_TRACK:g}, "
            f"envelope_penalty={ENVELOPE_PENALTY:g}/exponent={ENVELOPE_EXPONENT:g}, "
            f"tv_mode={tv_mode!r}, seed {seed} (drive seed {drive_seed}), "
            f"{track_name} via tracks_data.load_real_track, offset-free tire. "
            f"Rung 2 of the fidelity ladder (double-track): per-wheel loads "
            f"and load transfer, no roll camber, roll steer or compliance.")

    note_a = (f"The {label} car drove {dist[-1]:,.0f} m of {track_name} "
              f"({100*frac:.0f}% of the lap), "
              f"{'without leaving the road' if not off else 'before leaving the road'}. "
              f"Speed spans {v_lo:.1f}-{v_hi:.1f} m/s.")
    svg_a = lap_trace(track, x, y, v, title=f"F134: {label}, seed {seed} -- the lap",
                      subtitle=f"One lap, deployed policy, coloured by speed "
                               f"({v_lo:.1f}-{v_hi:.1f} m/s)",
                      note=note_a, stamp=stamp, v_lo=v_lo, v_hi=v_hi,
                      width=760, height=1180,
                      marks=[(float(x[0]), float(y[0]), "start")])
    (OUT / f"tv_{out_tag}_lap.svg").write_text(svg_a)

    note_c = (f"The same lap, coloured by tyre utilisation. Mean utilisation "
              f"is {util.mean():.3f} against F120's capped baseline "
              f"{CAPPED_BASELINE_UTIL:.3f} ({util.mean()/CAPPED_BASELINE_UTIL:.1f}x), "
              f"and {100*at_limit:.1f}% of the lap sits above 0.9.")
    svg_c = lap_trace(track, x, y, util, title=f"F134: {label}, seed {seed} -- tyre use",
                      subtitle="The same lap, coloured by tyre utilisation "
                               "(1.0 = the friction limit)",
                      note=note_c, stamp=stamp, v_lo=0.0, v_hi=1.0,
                      colour_label="tyre utilisation", unit="", fmt="{:.1f}",
                      width=760, height=1180,
                      marks=[(float(x[0]), float(y[0]), "start")])
    (OUT / f"tv_{out_tag}_lap_utilisation.svg").write_text(svg_c)

    note_b = (f"Worst slip peaks at {slip.max():.1f} deg "
              f"({'inside' if slip.max() <= 12.0 else 'OUTSIDE'} the 12 deg "
              f"tyre fit -- rule 4 {'valid' if slip.max() <= 12.0 else 'INVALID'}).")
    svg_b = lap_profile(
        dist,
        [(v, "speed (m/s)", TEAL, max(float(v.max()) * 1.15, 1.0), None, ""),
         (slip, "worst slip (deg)", AMB, max(float(slip.max()) * 1.3, 13.2),
          12.0, "12 deg -- edge of the tyre fit (rule 4)"),
         (util, "tyre utilisation", COR, 1.15, 1.0, "1.0 -- the friction limit")],
        title=f"F134: {label}, seed {seed} -- technical profile",
        subtitle="Speed, worst-wheel slip and tyre utilisation against distance",
        note=note_b, stamp=stamp)
    (OUT / f"tv_{out_tag}_profile.svg").write_text(svg_b)

    summary = {
        "policy": policy_path.name, "tv_mode": tv_mode, "seed": seed,
        "drive_seed": drive_seed,
        "distance_m": float(dist[-1]), "fraction_of_lap": float(frac),
        "off_track": off, "worst_slip_deg": float(slip.max()),
        "inside_tyre_fit": bool(slip.max() <= 12.0),
        "speed_min": float(v.min()), "speed_max": float(v.max()),
        "speed_mean": float(v.mean()), "speed_p1": v_lo, "speed_p99": v_hi,
        "a_y_max_g": float(ay.max()), "utilisation_mean": float(util.mean()),
        "utilisation_max": float(util.max()),
        "fraction_of_lap_above_0p9_utilisation": at_limit,
    }
    (OUT / f"tv_{out_tag}_lap_figure.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(f"  [{out_tag}] {dist[-1]:,.1f} m ({100*frac:.1f}% of lap), "
         f"off-track {off}, worst slip {slip.max():.2f} deg, "
         f"util mean {util.mean():.3f}")
    print(f"  wrote tv_{out_tag}_lap.svg, tv_{out_tag}_lap_utilisation.svg, "
         f"tv_{out_tag}_profile.svg")
    return summary


def main():
    made = []
    for tv_mode, tag_stem in VARIANTS:
        for seed in SEEDS:
            r = make_figures(tv_mode, tag_stem, seed)
            if r is not None:
                made.append((tag_stem, seed))
    if not made:
        print("  no checkpoints found on disk for this thread yet")
    else:
        print(f"\n  figures made for: {made}")


if __name__ == "__main__":
    main()
