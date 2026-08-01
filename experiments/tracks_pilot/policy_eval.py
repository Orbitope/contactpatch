"""THE evaluation for a driving policy. One implementation, used everywhere.

**Why this file exists.** Every policy in the Spa thread was scored by a
fresh inline script, each subtly different from the last. That is how a bug
in `finished` survived roughly twenty training runs and put a wrong claim
into FINDINGS.md (F109's "completed a full lap"): the harness that would
have caught it was rewritten each time, so no single version was ever
audited. Rule 7 says metrics are computed downstream from logged arrays;
this is that, made canonical. **Do not write another per-run eval. Import
this.**

What it reports, always, in the same shape:

* distance covered **from each probe's own start**, never absolute ``s``
* termination reason for every probe, as a breakdown that must sum to 1
* rule 4 envelope compliance, and a **validity verdict derived from it**
* lateral discipline -- is the car driving the road or hugging the edge
* monotonicity -- did ``s`` ever go backwards (progress-farming check)

The verdict is the point. `EvalResult.valid` is False whenever any probe
leaves the tyre model's fitted range, and `headline()` refuses to quote a
distance for an invalid result. CLAUDE.md rule 4: laps from outside the
envelope are discarded, not celebrated -- so the reporting path should make
celebrating one awkward, not merely discouraged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import torch

from physics.ppo import ActorCritic, greedy_policy
from physics.rl_env import DrivingEnv, EnvConfig, ENVELOPE_SLIP_MAX

#: The slip bound every minimum-time solve in Seasons 1-2 enforces and the
#: edge of the region the tyre file was fitted over. Ours, not the file's.
SLIP_BOUND_DEG = float(np.degrees(ENVELOPE_SLIP_MAX))

#: Probes around the lap. Evenly spaced so the result is not an artefact of
#: where one particular start happens to sit.
N_SECTIONS = 24


@dataclass
class EvalResult:
    track: str
    track_length_m: float
    n_sections: int
    speed_cap: float | None

    distance_mean: float
    distance_median: float
    distance_min: float
    distance_max: float
    distance_std: float
    fraction_of_lap: float

    finish_rate: float
    off_track_rate: float
    stall_rate: float
    timeout_rate: float

    worst_slip_deg: float
    sections_over_bound: int
    envelope_occupancy: float

    lateral_use_mean: float
    lateral_frac_beyond_80pct: float
    s_monotonic: bool
    speed_mean: float
    speed_max: float

    sections: list[dict] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """Rule 4. A result with any probe outside the tyre fit is not a
        measurement of driving, it is a measurement of the model failing."""
        return self.sections_over_bound == 0 and self.envelope_occupancy == 0.0

    def headline(self) -> str:
        pct = 100.0 * self.fraction_of_lap
        if not self.valid:
            return (f"NOT QUOTABLE (rule 4): {self.sections_over_bound}/"
                   f"{self.n_sections} sections outside the {SLIP_BOUND_DEG:.0f} deg "
                   f"tyre fit, worst {self.worst_slip_deg:.1f} deg, occupancy "
                   f"{self.envelope_occupancy:.4f}. Distance ({self.distance_mean:.1f} m, "
                   f"{pct:.1f}%) measures how freely it was allowed to slide.")
        return (f"{self.distance_mean:.1f} m ({pct:.1f}% of lap), "
               f"finished {self.finish_rate:.0%}, off-track {self.off_track_rate:.0%}, "
               f"worst slip {self.worst_slip_deg:.1f} deg, 0/{self.n_sections} "
               f"outside the fit -- rule 4 valid.")

    def report(self) -> str:
        L = [self.headline(), ""]
        L.append(f"  track {self.track} ({self.track_length_m:.0f} m), "
                f"{self.n_sections} probes, speed_cap {self.speed_cap}")
        L.append(f"  distance   mean {self.distance_mean:8.1f}  median "
                f"{self.distance_median:8.1f}  min {self.distance_min:7.1f}  "
                f"max {self.distance_max:7.1f}  sd {self.distance_std:.1f}")
        L.append(f"  ended by   finished {self.finish_rate:.2f}  off_track "
                f"{self.off_track_rate:.2f}  stalled {self.stall_rate:.2f}  "
                f"timeout {self.timeout_rate:.2f}")
        L.append(f"  envelope   worst slip {self.worst_slip_deg:5.1f} deg  "
                f"over bound {self.sections_over_bound}/{self.n_sections}  "
                f"occupancy {self.envelope_occupancy:.4f}")
        L.append(f"  driving    |n|/halfwidth {self.lateral_use_mean:.2f}  "
                f"beyond 80% {self.lateral_frac_beyond_80pct:.1%}  "
                f"s monotonic {self.s_monotonic}")
        L.append(f"  speed      mean {self.speed_mean:.1f}  max {self.speed_max:.1f} m/s")
        return "\n".join(L)

    def to_json(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")


def evaluate(model, track, speed_cap=None, n_sections=N_SECTIONS,
             env_kwargs=None, max_steps=30_000) -> EvalResult:
    """Drop the DEPLOYED (greedy/mean-action) policy at ``n_sections`` evenly
    spaced points and roll each to termination.

    ``model`` may be an ``ActorCritic`` or a path to a state dict.
    ``speed_cap`` MUST be the cap the checkpoint was selected under -- passing
    the curriculum's final cap instead is the F109 reporting bug.
    """
    base = dict(track=track, max_steps=max_steps, start_jitter_m=0.0)
    base.update(env_kwargs or {})
    if speed_cap is not None:
        base["speed_cap"] = speed_cap
    cfg = EnvConfig(**base)

    probe = DrivingEnv(cfg)
    if not isinstance(model, ActorCritic):
        m = ActorCritic(probe.obs_dim, probe.act_dim, 64, (-2.5, -1.0))
        m.load_state_dict(torch.load(model))
        model = m
    policy = greedy_policy(model)

    rows, lat, lat80, mono, spd, spd_max = [], [], [], True, [], 0.0
    for s0 in np.linspace(0.0, track.length, n_sections, endpoint=False):
        env = DrivingEnv(cfg)
        env.reset(0)
        env.s = float(s0)
        env.backend.reset(env._spawn_speed())
        obs = env.observe()
        while not env.done:
            obs, _, _, info = env.step(policy(obs))
        h = env.history()
        s_arr = np.asarray(h["s"])
        n_arr = np.asarray(h["n"])
        hw = np.asarray(track.half_width_at(s_arr))
        use = np.abs(n_arr) / np.maximum(hw, 1e-9)
        v = np.asarray(h["speed"])

        # `_dist_since_reset` is the env's own counter and is start-relative.
        # Recomputing as `s[-1] - s0` gives the same answer here only because
        # this harness never wraps; the counter is correct by construction.
        rows.append({
            "start_s": float(s0),
            "distance_travelled": float(env._dist_since_reset),
            "off_track": bool(info["off_track"]),
            "stalled": bool(info["stalled"]),
            "finished": bool(info["finished"]),
            "timeout": bool(info["timeout"]),
            "worst_slip_deg": float(np.max(h["alpha_max_deg"])),
            "envelope_occupancy": float(np.mean(h["envelope_violation"])),
            "lateral_use_mean": float(use.mean()),
            "speed_mean": float(v.mean()),
            "steps": int(env.steps),
        })
        lat.append(use.mean())
        lat80.append(float(np.mean(use > 0.8)))
        mono = mono and bool(np.all(np.diff(s_arr) >= -1e-9))
        spd.append(v.mean())
        spd_max = max(spd_max, float(v.max()))

    d = np.array([r["distance_travelled"] for r in rows])
    slip = np.array([r["worst_slip_deg"] for r in rows])
    occ = np.array([r["envelope_occupancy"] for r in rows])
    return EvalResult(
        track=getattr(track, "name", "?"), track_length_m=float(track.length),
        n_sections=n_sections, speed_cap=speed_cap,
        distance_mean=float(d.mean()), distance_median=float(np.median(d)),
        distance_min=float(d.min()), distance_max=float(d.max()),
        distance_std=float(d.std()),
        fraction_of_lap=float(d.mean() / track.length),
        finish_rate=float(np.mean([r["finished"] for r in rows])),
        off_track_rate=float(np.mean([r["off_track"] for r in rows])),
        stall_rate=float(np.mean([r["stalled"] for r in rows])),
        timeout_rate=float(np.mean([r["timeout"] for r in rows])),
        worst_slip_deg=float(slip.max()),
        sections_over_bound=int((slip > SLIP_BOUND_DEG).sum()),
        envelope_occupancy=float(occ.mean()),
        lateral_use_mean=float(np.mean(lat)),
        lateral_frac_beyond_80pct=float(np.mean(lat80)),
        s_monotonic=mono, speed_mean=float(np.mean(spd)), speed_max=spd_max,
        sections=rows)
