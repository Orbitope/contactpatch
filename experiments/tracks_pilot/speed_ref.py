"""Getting the policy TO the limit — replace the scalar cap with a plan.

**The measured problem (F120, F121).** The solved Spa policy sits on the
speed cap for 99.6% of the lap and on the tyres for 0.7%. The curriculum did
not stop early; it stopped correctly, freezing the cap once slip reached
9.69° in the tightest corner — which then sets the speed for the entire
circuit. A single scalar cannot say "fast here, slow there", and Spa needs a
factor of four between the two. Against a curvature-aware reference the flat
13 m/s cap is too slow over 99.3% of the lap and too fast over the 0.7% that
is corners; the split is unchanged at every `v_max` from 20 to 60 m/s.

**The instrument this run swaps in.** `speed_ref_penalty` charges only the
*excess* over `driver.SpeedProfile`'s target — cornering limit, backward pass
to brake for what is coming, forward pass for power. One-sided by design:
being too slow is already paid for in lost progress. So the policy is free to
use the straights and is charged for arriving at a corner too fast, which is
the shape the flat cap could not express.

**What this costs, stated up front rather than in a footnote.** The reference
is the classical controller's own answer. Training against it shifts the
claim from *"the policy discovered braking"* to *"the policy learned to match
a reference"*, and every result from this file must say so. That trade is
worth making here and would not have been in Episode 9: Season 5's question
is whether torque vectoring moves a car **at the limit**, and TV has nothing
to reallocate while mean tyre utilisation is 0.090. A driver that learned
braking on its own but never uses its tyres cannot answer it.

**Success is not lap distance.** The capped policy already completes 100% of
Spa. This run has to complete the lap *and* work the tyres:

| gate | capped baseline (F120) | needed |
|---|---|---|
| lap completed, rule-4 valid | 100%, 0/24 over 12° | unchanged |
| mean tyre utilisation | 0.090 | materially higher |
| fraction of lap above 0.9 | 0.7% | materially higher |

A run that raises utilisation by going off the road, or by sliding past the
12° fit, has failed both gates — those are the two ways this could produce an
exciting number that means nothing (F62: sliding covers ground *faster*,
21.0 m/s against 20.2, so the unguarded optimum really is to slide).

    python -m experiments.tracks_pilot.speed_ref [steps]
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from physics.ppo import PPOConfig, train
from physics.rl_env import DrivingEnv, EnvConfig
from physics.tracks_data import load_real_track
from physics.driver import SpeedProfile, BRAKE_MAX, DRIVE_MAX
from physics import schema
from experiments.tracks_pilot import policy_eval as PE
from experiments.tracks_pilot import spa_ppo_v2 as V2

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "tracks_pilot" / "out"

TRACK = "Spa"
STEPS = 40_000_000
N_SECTIONS = 24

#: Weight on the excess-over-reference term. Sized against the progress
#: reward rather than guessed: progress pays `v * dt` per step, so exceeding
#: the plan by `e` m/s gains `e * dt` and costs `w * e * dt`. Any `w > 1` makes
#: exceeding the plan net-negative; the sweep brackets that crossing rather
#: than assuming the scale is right, because a term that is too weak is
#: ignored and one that is too strong reproduces the cap's timidity by a
#: different route.
#: `w=1` was dropped after measurement, not on the sizing argument alone:
#: progress pays `v*dt` and exceeding the plan by `e` costs `w*e*dt`, so
#: only `w>1` makes overspeed net-negative -- and a launched w=1 run sat
#: at 100% off-track with 17.7 deg of slip by 13M steps, the curriculum
#: frozen at its 0.45 g start because the raise gate needs off<0.15.
WEIGHTS = (3.0, 10.0)

#: The reference's lateral budget. 0.97 g is the tyre's measured peak, so a
#: plan built at that value asks for the limit in every corner from the first
#: step -- the same mistake `CAP_START` exists to avoid, in a new form. The
#: run starts the plan conservative and raises it as the policy stays clean.
A_LAT_START = 0.45 * schema.G
A_LAT_MAX = 0.97 * schema.G
A_LAT_STEP = 0.08 * schema.G
#: Raise the plan only while the policy is BOTH keeping the car on the road
#: and inside the tyre fit. Either gate alone is insufficient: clean-but-
#: sliding is F62, and inside-the-fit-but-crashing is not a driver.
RAISE_OFF_BELOW = 0.15
RAISE_SLIP_BELOW_DEG = 9.0
RAISE_PATIENCE = 3


#: **A centreline term fights the racing line, and that is the whole problem
#: here.** The fast way through a corner is out-in-out: the car belongs at the
#: outside on entry, at the INSIDE EDGE at the apex, and back out on exit.
#: `cross_track_penalty` pays the policy to sit in the middle, so it is a tax
#: on exactly the manoeuvre this run exists to produce. F118 measured the cost
#: on a policy that could already hold a line -- 5.7-6.0 deg of slip became
#: 9.6-10.5 -- without having the mechanism; this is the mechanism.
#:
#: It is swept rather than simply removed, because F110 is also true: the term
#: took Spa from 40.7% to 100% lap completion when the policy could NOT hold a
#: line. The hypothesis this arm tests is that the speed plan now supplies
#: what the centreline term was crudely standing in for -- a curvature-aware
#: target tells the policy to slow for a corner, so it no longer needs to be
#: pinned to the middle of the road to survive one.
CROSS_TRACKS = (0.0, 2.0)


def _env_kwargs(weight: float, a_lat: float, cross_track: float = 0.0) -> dict:
    # **The researched reward, not `spa_ppo_v2.V2_ENV`.** V2_ENV predates the
    # RL survey (F105/F112) and differs on seven fields, three of which work
    # directly against this experiment:
    #
    #   `action_repeat` 1 (50 Hz) vs 5 (10 Hz) -- a Gaussian resampled at
    #     50 Hz produces near-zero net displacement over the ~1 s a brake
    #     application must persist, so the policy cannot SAMPLE a sustained
    #     brake. Teaching a car to brake for a corner is the entire point here.
    #   `speed_scaled_penalties` absent vs True -- a fixed-magnitude penalty is
    #     minimised by driving slowly. No published limit-driving agent uses
    #     one; Sophy scales by speed squared, Fuchs by kinetic energy, TRI by
    #     speed.
    #   `edge_penalty` fixed vs speed-scaled -- a fixed cost near the edge is a
    #     fixed cost at the apex, which is where a fast line belongs.
    #
    # Building a limit-seeking experiment on the pre-survey reward was the
    # error; `multitrack.ENV` is where the survey's conclusions actually live.
    from experiments.tracks_pilot import multitrack as MT
    kw = dict(MT.ENV)
    kw.update(
        cross_track_penalty=cross_track,
        speed_cap=None,              # THE point: no scalar limiter
        speed_ref_penalty=weight,
        speed_ref_a_lat=a_lat,
    )
    return kw


def _run(weight: float, steps: int, seed: int = None,
         cross_track: float = 0.0) -> dict:
    seed = V2.SEED if seed is None else seed
    tag = (f"speedref_w{weight:g}_ct{cross_track:g}"
           + (f"_s{seed}" if seed != V2.SEED else ""))
    trk = load_real_track(TRACK)
    print(f"\n{'='*72}\n  {TRACK}, speed_ref_penalty={weight:g}, "
          f"cross_track_penalty={cross_track:g}, {steps:,} steps\n{'='*72}")
    print(f"  plan starts at a_lat {A_LAT_START/schema.G:.2f} g, "
          f"raises by {A_LAT_STEP/schema.G:.2f} g toward "
          f"{A_LAT_MAX/schema.G:.2f} g while off<{RAISE_OFF_BELOW} "
          f"and slip<{RAISE_SLIP_BELOW_DEG}°")

    state = {"a_lat": A_LAT_START, "clean": 0, "raises": 0, "log": []}
    #: Live handles. Both envs build the speed plan ONCE and cache it, so the
    #: curriculum has to reach the objects, not the dict that made them --
    #: `make_batched` is called once at startup and never again. Assigning
    #: `state["a_lat"]` alone would leave the whole run training at 0.45 g
    #: while faithfully logging a rising number. `spa_curriculum` hit the
    #: matching version of this with the scalar cap; pinned by
    #: tests/test_speed_ref_curriculum.py.
    envs = {}

    def make_batched(n):
        e = V2.make_batched_env(
            n, env_over={"track": trk, **_env_kwargs(weight, state['a_lat'], cross_track)})
        envs["batched"] = e
        return e

    def make_eval():
        # FIXED at the final plan, and never raised with the curriculum. The
        # selection criterion has to be stationary or "best checkpoint" partly
        # means "checkpoint judged at the most generous curriculum stage": the
        # penalty is excess over the plan, so a faster plan charges less, and
        # a late checkpoint would score better for that reason alone. Judging
        # every checkpoint against the plan we ultimately want makes early
        # ones score badly, which is correct -- they are worse at the task the
        # run exists to solve.
        e = DrivingEnv(EnvConfig(
            track=trk, start_jitter_m=0.0,
            **_env_kwargs(weight, A_LAT_MAX, cross_track)))
        envs["eval"] = e
        return e

    def on_update(rec):
        off = rec.get("off_track_rate", 1.0)
        slip = rec.get("worst_slip_mean_deg", 99.0)
        if off < RAISE_OFF_BELOW and slip < RAISE_SLIP_BELOW_DEG:
            state["clean"] += 1
        else:
            state["clean"] = 0
        if (state["clean"] >= RAISE_PATIENCE
                and state["a_lat"] < A_LAT_MAX - 1e-9):
            state["a_lat"] = min(state["a_lat"] + A_LAT_STEP, A_LAT_MAX)
            # Mutate BOTH live envs. The eval env is a separate object and
            # would otherwise keep scoring against the old plan -- which is
            # how a checkpoint gets selected under one plan and reported
            # under another (F109, in its speed-cap form).
            # Training env only. The eval env's plan stays fixed -- see
            # `make_eval`.
            if envs.get("batched") is not None:
                envs["batched"].set_speed_ref_a_lat(state["a_lat"])
            state["clean"] = 0
            state["raises"] += 1
            state["log"].append({"update": rec["update"],
                                 "a_lat_g": state["a_lat"] / schema.G})
            print(f"    ^ plan raised to {state['a_lat']/schema.G:.2f} g "
                  f"at update {rec['update']}")
        if rec["update"] % 25 == 0:
            print(f"  upd {rec['update']:4d} steps={rec['steps']:>11,} "
                  f"v={rec.get('speed_mean', float('nan')):5.1f} "
                  f"slip={slip:5.1f} off={off:.2f} "
                  f"a_lat={state['a_lat']/schema.G:.2f}g "
                  f"EV={rec['explained_variance']:+.3f}", flush=True)

    # The survey's PPO settings too: 32 minibatches (Sophy 1,024, Fuchs
    # 4,096, TRI 256 -- ours was 4) and gae_lambda 0.98, whose n-step
    # equivalent Sophy's ablation shows flat over 5-9 and cliffing at 1.
    cfg = PPOConfig(total_steps=steps, n_envs=V2.N_ENVS,
                    rollout_steps=V2.ROLLOUT_STEPS, gamma=0.975,
                    gae_lambda=0.98, minibatches=32,
                    seed=seed, eval_every=8, eval_episodes=V2.EVAL_EPISODES,
                    entropy_anneal=True)
    t0 = time.time()
    res = train(make_batched_env=make_batched, cfg=cfg, on_update=on_update,
                make_eval_env=make_eval)
    wall = time.time() - t0

    # Scored through the one committed evaluator (D16). `res["model"]` holds
    # the SELECTED checkpoint, not the final weights.
    #
    # `a_lat` does not affect these numbers and that is worth stating, because
    # the F109 reflex says "score at the value the checkpoint was selected
    # under". Here the plan enters the REWARD only -- `observe()` carries
    # speed, offset, heading error, yaw rate, sideslip, steer, curvature
    # preview and design, and no reference speed -- so distance, slip and
    # utilisation are identical at any `a_lat`. F109's real content, that a
    # selection criterion must not drift, is handled in `make_eval`.
    r = PE.evaluate(res["model"], trk, n_sections=N_SECTIONS,
                    env_kwargs=_env_kwargs(weight, A_LAT_MAX, cross_track))
    print(f"\n  [D16] {r.headline()}")
    print(f"    utilisation mean {r.utilisation_mean:.3f} "
          f"(capped baseline 0.090), at-limit {100*r.frac_at_limit:.1f}% "
          f"(baseline 0.7%)")

    torch.save(res["model"].state_dict(), OUT / f"{tag}_policy.pt")
    (OUT / f"{tag}_history.json").write_text(
        json.dumps(res["history"], indent=2) + "\n")
    return {
        "weight": weight, "cross_track_penalty": cross_track,
        "seed": seed, "steps": steps, "wall_s": wall,
        "a_lat_final_g": state["a_lat"] / schema.G,
        "a_lat_raises": state["raises"], "a_lat_log": state["log"],
        "headline": r.headline(), "valid": r.valid,
        "fraction_of_lap": r.fraction_of_lap, "finish_rate": r.finish_rate,
        "off_track_rate": r.off_track_rate,
        "worst_slip_deg": r.worst_slip_deg,
        "sections_over_bound": r.sections_over_bound,
        "utilisation_mean": r.utilisation_mean,
        "frac_at_limit": r.frac_at_limit,
        "speed_mean": r.speed_mean, "speed_max": r.speed_max,
    }


def limit_ceiling(track, a_lat=A_LAT_MAX) -> float:
    """The most of a lap that tracking the plan can spend at the grip limit.

    Not 100%, and assuming otherwise would make a good result read as a
    failure. The plan works the tyres in two places:

    - **cornering-limited** stretches, where speed is set by `sqrt(a_lat/k)`;
    - **braking** zones, where it decelerates at `BRAKE_MAX` = 0.985 g, which
      is essentially the tyre's own limit.

    Power zones are not: `a_drive` is 0.337 g, well under. Measured per track,
    because it is a property of the circuit's curvature distribution:

    | | cornering | braking | at the limit |
    |---|---|---|---|
    | Spa | 12.1% | 19.1% | **30.2%** |
    | Monza | 4.7% | 15.4% | 19.4% |
    | MexicoCity | 6.4% | 18.9% | 24.5% |

    So Spa's target for `frac_at_limit` is ~30%, against the capped
    baseline's 0.7% (F120).

    **Slightly optimistic, deliberately.** `SpeedProfile`'s three passes do not
    enforce the friction ellipse, so where braking and cornering overlap the
    plan asks for more than the tyre can give. It is a ceiling, quoted as one.

    **Why not benchmark against the classical driver instead.** There is no
    working classical baseline on Spa: `classical_baseline_spa.py` spins or
    leaves the road at every grip level from 0.30 to 0.85, covering 12-15% of
    a lap. The plan is usable as a reference target even though the classical
    *controller* cannot follow it.
    """
    s = np.linspace(0.0, track.length, 8000, endpoint=False)
    ds = float(s[1] - s[0])
    k = np.abs(np.asarray(track.curvature(s)))
    a_brake = BRAKE_MAX / schema.RV_1.mass
    p = SpeedProfile(track, a_lat=a_lat, a_brake=a_brake,
                     a_drive=DRIVE_MAX / schema.RV_1.mass, v_max=60.0,
                     wrap=bool(getattr(track, "closed", False)))
    v = np.array([p.target(float(q)) for q in s])
    cornering = v >= np.sqrt(a_lat / np.maximum(k, 1e-9)) * 0.995
    braking = (v * np.gradient(v, ds)) < -0.9 * a_brake
    return float(np.mean(cornering | braking))


#: The capped baseline this run has to beat on utilisation without losing the
#: lap. [MEASURED] F120, `curr_ct2_policy.pt` re-scored through `policy_eval`.
BASELINE = {"fraction_of_lap": 1.000, "worst_slip_deg": 10.4,
            "utilisation_mean": 0.090, "frac_at_limit": 0.007,
            "speed_mean": 13.03, "valid": True}


def main(steps: int = STEPS, seeds: tuple[int, ...] = None, weights=None,
         cross_tracks=None):
    """``seeds`` runs every weight at each seed. One seed answers "does this
    work at all", which is what the sweep is for; rule 5 wants >=3 before any
    of it is a trend, and those belong on the weight that survives -- e.g.
    `main(seeds=(0, 1, 2), weights=(3.0,))`."""
    OUT.mkdir(parents=True, exist_ok=True)
    weights = WEIGHTS if weights is None else weights
    cts = CROSS_TRACKS if cross_tracks is None else cross_tracks
    rows = [_run(w, steps, sd, ct)
            for w in weights for ct in cts for sd in (seeds or [V2.SEED])]

    print(f"\n\n{'='*88}\n  SPEED REFERENCE vs THE SCALAR CAP — Spa\n{'='*88}")
    print(f"  {'run':<20}{'lap':>8}{'slip':>7}{'over12':>8}{'v_mean':>8}"
          f"{'util':>8}{'@limit':>9}  valid")
    print(f"  {'capped (F120)':<16}{100*BASELINE['fraction_of_lap']:>7.1f}%"
          f"{BASELINE['worst_slip_deg']:>7.1f}{0:>8}"
          f"{BASELINE['speed_mean']:>8.1f}{BASELINE['utilisation_mean']:>8.3f}"
          f"{100*BASELINE['frac_at_limit']:>8.1f}%  True")
    for c in rows:
        lbl = (f"w={c['weight']:g} ct={c['cross_track_penalty']:g}"
               + (f" s{c['seed']}" if seeds else ""))
        print(f"  {lbl:<20}"
              f"{100*c['fraction_of_lap']:>7.1f}%{c['worst_slip_deg']:>7.1f}"
              f"{c['sections_over_bound']:>8}{c['speed_mean']:>8.1f}"
              f"{c['utilisation_mean']:>8.3f}{100*c['frac_at_limit']:>8.1f}%"
              f"  {c['valid']}")

    ceiling = limit_ceiling(load_real_track(TRACK))
    print(f"\n  Did any run get the car to the limit WITHOUT losing the lap?")
    print(f"    ceiling: tracking the plan perfectly puts {100*ceiling:.1f}% of "
          f"Spa at the grip limit — the rest is braking, power or v_max limited.")
    print(f"    baseline: {100*BASELINE['frac_at_limit']:.1f}%. "
          f"Calling it a win at half the ceiling ({100*ceiling/2:.1f}%).")
    winners = [c for c in rows if c["valid"]
               and c["fraction_of_lap"] >= 0.95
               and c["frac_at_limit"] >= 0.5 * ceiling]
    if winners:
        b = max(winners, key=lambda c: c["frac_at_limit"])
        print(f"    YES — w={b['weight']:g}: {100*b['frac_at_limit']:.1f}% of the "
              f"lap at the limit against the baseline's 0.7%, "
              f"{100*b['fraction_of_lap']:.0f}% of the lap, rule-4 valid.")
        print(f"    Claim shifts from 'discovered braking' to 'matched a "
              f"reference' — say so wherever this is quoted.")
    else:
        print(f"    NO. Either the lap was lost or utilisation did not move.")
        for c in rows:
            why = ("outside the tyre fit" if not c["valid"] else
                   "lost the lap" if c["fraction_of_lap"] < 0.95 else
                   "utilisation did not move")
            print(f"      w={c['weight']:g}: {why}")

    (OUT / "speedref_results.json").write_text(json.dumps(
        {"track": TRACK, "steps": steps, "baseline": BASELINE,
         "limit_ceiling": ceiling,
         "weights": list(weights), "cross_tracks": list(cts),
         "seeds": list(seeds or [V2.SEED]),
         "runs": rows}, indent=2) + "\n")
    print(f"\n  wrote speedref_results.json")


if __name__ == "__main__":
    import sys
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    sd = None
    for a in sys.argv[1:]:
        if a.startswith("--seeds="):
            sd = tuple(int(x) for x in a.split("=", 1)[1].split(","))
    w = None
    ct = None
    for a in sys.argv[1:]:
        if a.startswith("--weights="):
            w = tuple(float(x) for x in a.split("=", 1)[1].split(","))
        if a.startswith("--cross-tracks="):
            ct = tuple(float(x) for x in a.split("=", 1)[1].split(","))
    main(int(argv[0]) if argv else STEPS, seeds=sd, weights=w, cross_tracks=ct)
