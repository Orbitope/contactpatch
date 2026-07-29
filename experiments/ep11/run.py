"""Episode 11 — the fastest setup is the one that crashes, and I could not prove it.

The first question in this series that optimal control **structurally cannot
answer.** A minimum-time solver is handed the whole road and perfect knowledge of
the car, so it is never surprised; asking it "what happens when the grip is not
what you expected?" just gets you a new plan for the new grip. Fragility is a
property of a driver who has to react, and Season 3 finally has one.

The experiment is deliberately cheap: **nothing is retrained.** Episode 10's one
design-conditioned policy is loaded and asked to drive each car under
perturbation. That keeps the driver fixed — the only thing changing between
columns of the result is the car and the disturbance, so a difference in outcome
cannot be a difference in training luck. It is also the only honest way to do it
with one training seed, which is still all Season 3 has.

Two perturbations, applied separately and then together so each one's contribution
is attributable:

``steer_noise``
    Gaussian noise on the commanded steering, every step, present at deployment.
    The hands and the linkage, not the policy's own exploration — Episode 9's
    noise vanished when you deployed the policy, and this does not.
``grip_spread``
    Peak lateral friction scaled per lap, through the tire file's ``LMUY`` and
    never by touching a ``P*`` coefficient. One surface per lap, which is what a
    damp patch or a cold track looks like.

**What "fragile" means here, stated before anything is measured**, because it is a
metric choice and rule 9 says choose it in the open:

1. **Failure rate** — the fraction of laps that leave the road. The headline.
2. **Lap-time spread** among the laps that finish. A car can be reliable and still
   unpredictable, and a driver feels the second one.

Absolute lap times are not comparable with Seasons 1-2 (rule 6) and are not quoted
as though they were. Every reported time is the DEPLOYED policy's (F61).

    python -m experiments.ep11.run
    python -m experiments.ep11.run --figures-only
    python -m experiments.ep11.run --quick
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import torch

from diagnostics.common import Report
from experiments.common import episode_dir, write
from physics.ppo import ActorCritic, PPOConfig, greedy_policy
from physics.rl_env import DrivingEnv, EnvConfig, rollout
from viz import fragility_figures

#: Episode 10's policy, reused verbatim. This episode trains nothing.
POLICY = "experiments/ep10/out/policy.pt"

DESIGN_KEYS = ("front_mass_fraction",)
DESIGN_RANGES = {"front_mass_fraction": (0.40, 0.65)}
ENVELOPE_PENALTY = 0.5
FRACTIONS = (0.40, 0.47, 0.54, 0.61, 0.65)

#: Rollouts per (design, condition). A failure RATE needs many more samples than
#: a mean does: at 30 rollouts one crash is 3.3% and the binomial 95% interval on
#: a true 10% rate is roughly 2-27%, which is stated with every number rather
#: than hidden. 40 is what fits the time budget with five conditions; every rate
#: is reported with its interval so the reader can see what 40 does and does not
#: support.
N_TRIALS = 40

#: Start jitter, carried over from Episode 10's evaluation so a "nominal" row here
#: is the same measurement Episode 10 reported (F66 — without jitter a
#: deterministic policy in a deterministic environment returns N copies of one
#: run and a spread of exactly zero).
JITTER_M = 8.0

#: [ASSUMED], and calibrated. **The calibration was initially run at 10 rollouts
#: per cell and that was not enough to calibrate on.** It reported 0% failures and
#: a worst slip of 8.7-9.8 deg at steering sigma 0.15; at 40 rollouts the same
#: condition loses laps and reaches 11.7-15.3 deg. Worst-slip is an extreme-value
#: statistic — it grows with sample count, so a max over 10 samples is not a bound
#: on anything. A whole conclusion was built on it and had to be retracted. See
#: FINDINGS F70.
#:
#: **0.15 was itself retracted, by F96.** It was chosen as "the strongest
#: disturbance the median lap survives" and described as the driver's hands and
#: linkage; measured against a 13.5:1 steering ratio it is 23 deg RMS at the
#: steering wheel — a continuous quarter-turn saw, not an imperfect driver.
#: `STEER_ATTENTIVE`/`STEER_DISTRACTED` are F96's own calibration (road-wheel RMS
#: converted through the same ratio): 1.6 deg and 4.7 deg at the wheel,
#: bracketing the reversal-rate literature's cognitive-load / visual-secondary-task
#: bands. `STEER_RETRACTED` keeps the original 0.15 in the grid, unquotable, so the
#: correction is a comparison in the data rather than a claim about it.
STEER_ATTENTIVE = 0.01
STEER_DISTRACTED = 0.03
STEER_RETRACTED = 0.15
GRIP_SPREAD = 0.20
STEER_BEYOND = 0.25
GRIP_BEYOND = 0.30

CONDITIONS = (
    ("nominal", 0.0, 0.0, "no perturbation — Episode 10's measurement"),
    ("steer", STEER_ATTENTIVE, 0.0,
     f"steering noise, attentive driver, sigma = {STEER_ATTENTIVE} (1.6 deg at the wheel)"),
    ("grip", 0.0, GRIP_SPREAD,
     f"grip varied +/-{GRIP_SPREAD:.0%} per lap"),
    ("both", STEER_ATTENTIVE, GRIP_SPREAD,
     "both together, attentive driver"),
    ("distracted", STEER_DISTRACTED, GRIP_SPREAD,
     f"both together, distracted driver, sigma = {STEER_DISTRACTED} (4.7 deg at the wheel)"),
    ("retracted_015", STEER_RETRACTED, GRIP_SPREAD,
     "the ORIGINAL noise level (F96) — 23 deg at the wheel, not a driver; kept "
     "only so the correction is visible in the data"),
    ("beyond", STEER_BEYOND, GRIP_BEYOND,
     "both, harder still — most laps leave the fit; direction only"),
)

#: The conditions any claim may rest on. ``retracted_015`` and ``beyond`` are
#: deliberately excluded — the first is F96's retracted value, kept only for
#: comparison; the second was never claimed to be realistic.
#:
#: Condition names avoid "." on purpose: they are joined with "_" into trace keys,
#: so a dotted name ("retracted_0.15") makes those keys awkward to parse back.
QUOTABLE = ("nominal", "steer", "grip", "both", "distracted")


def dkey(ff) -> str:
    """The one way a design point is named. Shared with the figures (F59)."""
    return f"{float(ff):.2f}"


def load_policy():
    """Episode 10's design-conditioned policy, deployed (mean action)."""
    probe = DrivingEnv(EnvConfig(design_keys=DESIGN_KEYS,
                                 design_ranges=DESIGN_RANGES,
                                 envelope_penalty=ENVELOPE_PENALTY))
    cfg = PPOConfig()
    model = ActorCritic(probe.obs_dim, probe.act_dim, cfg.hidden,
                        cfg.init_log_std)
    model.load_state_dict(torch.load(POLICY))
    model.eval()
    return model, probe.obs_dim


def wilson(k: int, n: int) -> tuple[float, float]:
    """95% Wilson interval on a proportion.

    Used instead of k/n +/- 1.96*sqrt(p(1-p)/n) because the normal approximation
    is worst exactly where this episode lives — near 0% and near 100% — where it
    happily returns negative lower bounds and claims impossible precision.
    """
    if n == 0:
        return (float("nan"), float("nan"))
    z, p = 1.959964, k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, (c - h) / d), min(1.0, (c + h) / d))


def trial(model, ff: float, steer_noise: float, grip_spread: float,
          n: int) -> dict:
    """One (design, condition) cell: n deployed rollouts, everything logged."""
    pol = greedy_policy(model)
    runs = []
    for k in range(n):
        env = DrivingEnv(EnvConfig(design_keys=DESIGN_KEYS,
                                   design_ranges=DESIGN_RANGES,
                                   envelope_penalty=ENVELOPE_PENALTY,
                                   start_jitter_m=JITTER_M,
                                   steer_noise=steer_noise,
                                   grip_spread=grip_spread), seed=k)
        env.set_design(front_mass_fraction=ff)
        r = rollout(env, pol, seed=k)
        r["grip"] = env.grip
        runs.append(r)

    fin = [r for r in runs if r["finished"]]
    laps = np.array([r["lap_time_s"] for r in fin], dtype=float)
    # Envelope occupancy over EVERY rollout, not just finishers: a car that
    # leaves the road at 20 degrees of slip is exactly the case rule 4 exists for.
    slip = np.array([float(np.max(np.abs(r["alpha_max_deg"]))) for r in runs])
    ok = np.array([bool(r["finished"]) for r in runs])
    lo, hi = wilson(len(fin), len(runs))

    # --- rule 4, applied per LAP, which is the only level it means anything at.
    #
    # An earlier version gated on the WORST slip in the whole condition. At 40
    # rollouts that is an extreme-value statistic: it reached 35 deg while the
    # median lap sat at 8 deg, so one excursion disqualified 39 defensible laps.
    # The rule is that laps from outside the envelope are discarded — laps, not
    # conditions. See FINDINGS F70.
    #
    # A lap that left the road at 20 deg of slip tells us about our extrapolation.
    # A lap that left the road having never exceeded 12 deg is real evidence, and
    # so is a lap that finished inside. Keep those, drop the rest.
    inside = slip <= 12.0
    n_in = int(inside.sum())
    fail_in = int((~ok & inside).sum())
    ilo, ihi = wilson(n_in - fail_in, n_in) if n_in else (float("nan"),) * 2
    # How many of the DISCARDED laps were failures. This is the honest health
    # warning on the number above: every discarded failure is a real crash we
    # cannot attribute, so the in-fit failure rate is a LOWER BOUND.
    discarded_failures = int((~ok & ~inside).sum())
    return {
        "n_inside_fit": n_in,
        "inside_fit_fraction": float(inside.mean()),
        "failures_inside_fit": fail_in,
        # The quotable fragility number: failure rate over laps that never left
        # the region the tire file was fitted over.
        "failure_rate_inside_fit": (fail_in / n_in) if n_in else float("nan"),
        "failure_rate_inside_fit_ci95": [1.0 - ihi, 1.0 - ilo],
        "discarded_laps": int((~inside).sum()),
        "discarded_failures": discarded_failures,
        "failure_rate_is_lower_bound": discarded_failures > 0,
        # Per-lap pairs, so any future metric can be recomputed without re-running
        # (rule 7: metrics are computed downstream from logged arrays).
        "per_lap_finished": [bool(v) for v in ok],
        "per_lap_worst_slip_deg": [round(float(v), 3) for v in slip],
        "n": len(runs),
        "n_finished": len(fin),
        "finish_rate": len(fin) / len(runs),
        "finish_rate_ci95": [lo, hi],
        "failure_rate": 1.0 - len(fin) / len(runs),
        "lap_time_mean": float(laps.mean()) if len(fin) else float("nan"),
        "lap_time_std": float(laps.std()) if len(fin) > 1 else float("nan"),
        # Progress rate over every rollout, so a design scored on its luckiest
        # laps cannot look good by dropping its failures (F58).
        "progress_rate_mean": float(np.mean(
            [r["distance_m"] / max(r["lap_time_s"], 1e-9) for r in runs])),
        "distance_mean": float(np.mean([r["distance_m"] for r in runs])),
        "worst_slip_deg": float(slip.max()),
        "median_worst_slip_deg": float(np.median(slip)),
        "envelope_exceeded_fraction": float(np.mean(slip > 12.0)),
    }


#: --deep: the narrow, deep re-run. At n = 40 the in-fit failure rates were
#: 12% / 0% / 0% / 0% and NOTHING survived a multiple-comparison correction
#: (Fisher exact p = 0.045 for the closest pair, against a Bonferroni threshold of
#: 0.008 over six comparisons). The 5 x 5 grid spent its samples on breadth when
#: the question needed depth: distinguishing 12% from 0% takes n ~ 120, and only
#: two conditions and four designs actually carry the claim.
N_DEEP = 120
FRACTIONS_DEEP = (0.47, 0.54, 0.61, 0.65)      # the designs the policy can drive
#: ``both`` (attentive driver) is the corrected headline; ``distracted`` re-asks
#: the same question at F96's harsher realistic level, since the correction
#: could plausibly have gone either way.
CONDITIONS_DEEP = ("nominal", "both", "distracted")
#: Conditions the multiple-comparison test is actually run on — everything in
#: CONDITIONS_DEEP except the uncontested baseline.
PERTURBED_DEEP = tuple(c for c in CONDITIONS_DEEP if c != "nominal")


def fisher_exact_two_sided(x1: int, n1: int, x2: int, n2: int) -> float:
    """Two-sided Fisher exact p for two proportions.

    Not a chi-square and not a normal approximation: the counts here are single
    digits, where both of those are simply wrong.
    """
    from math import comb
    tot, k = n1 + n2, x1 + x2
    if k == 0 or k == tot:
        return 1.0
    obs = comb(n1, x1) * comb(n2, k - x1)
    lo, hi = max(0, k - n2), min(n1, k)
    num = sum(comb(n1, i) * comb(n2, k - i) for i in range(lo, hi + 1)
              if comb(n1, i) * comb(n2, k - i) <= obs * (1.0 + 1e-9))
    return min(1.0, num / comb(tot, k))


def deep(out) -> int:
    """Four designs, two conditions, enough rollouts to settle it."""
    model, _ = load_policy()
    print("Episode 11 — deep re-run")
    print(f"  {len(FRACTIONS_DEEP)} designs x {len(CONDITIONS_DEEP)} conditions "
          f"x {N_DEEP} deployed rollouts")
    print("  (n=40 left the effect at p=0.045 uncorrected, which settles nothing)\n")

    look = {c[0]: c for c in CONDITIONS}
    cells, t0 = {}, time.time()
    for name in CONDITIONS_DEEP:
        _, sn, gs, _d = look[name]
        print(f"  {name}:")
        for ff in FRACTIONS_DEEP:
            c = trial(model, ff, sn, gs, N_DEEP)
            cells[f"{name}|{dkey(ff)}"] = c
            lo, hi = c["failure_rate_inside_fit_ci95"]
            print(f"    {dkey(ff)} front  in-fit {c['failures_inside_fit']:3d}/"
                  f"{c['n_inside_fit']:3d} = {c['failure_rate_inside_fit']:5.1%} "
                  f"[{lo:5.1%}-{hi:5.1%}]   discarded {c['discarded_laps']:3d} "
                  f"({c['discarded_failures']} of them crashes)")
    print(f"\n  {time.time()-t0:.0f}s\n")

    # --- does the effect survive a correction for multiple comparisons? -------
    # Run once per perturbed condition: the correction at the attentive level
    # (F96's realistic value) is the headline, and at the distracted level is
    # the check that it is not an artefact of picking the gentler one.
    ks = [dkey(f) for f in FRACTIONS_DEEP]
    by_condition = {}
    for cond in PERTURBED_DEEP:
        pairs = []
        for i, a in enumerate(ks):
            for b in ks[i + 1:]:
                ca, cb = cells[f"{cond}|{a}"], cells[f"{cond}|{b}"]
                pv = fisher_exact_two_sided(
                    ca["failures_inside_fit"], ca["n_inside_fit"],
                    cb["failures_inside_fit"], cb["n_inside_fit"])
                pairs.append({"a": a, "b": b, "p": pv})
        # Holm-Bonferroni: same family-wise guarantee as Bonferroni, uniformly
        # more powerful, so it is the honest choice rather than the harshest one.
        order = sorted(pairs, key=lambda d: d["p"])
        m = len(order)
        for i, d in enumerate(order):
            thresh = 0.05 / (m - i)
            d["holm_threshold"] = thresh
            d["significant"] = bool(d["p"] <= thresh)
            if not d["significant"]:
                for later in order[i:]:
                    later["significant"] = False
                    later.setdefault("holm_threshold", 0.05 / (m - i))
                break
        sig = [d for d in order if d.get("significant")]
        print(f"  {cond}: pairwise, Holm-Bonferroni corrected at family-wise 0.05:")
        for d in order:
            print(f"    {d['a']} vs {d['b']}   p = {d['p']:.4f}  vs threshold "
                  f"{d['holm_threshold']:.4f}   "
                  f"{'SIGNIFICANT' if d.get('significant') else 'not significant'}")
        verdict = (
            "the fastest design is measurably more fragile than at least one "
            "other, after correction" if sig else
            "no pair of designs is distinguishable after correction; the "
            "effect is directional only")
        print(f"  VERDICT ({cond}): {verdict}\n")
        by_condition[cond] = {"pairwise": order, "n_significant_pairs": len(sig),
                              "verdict": verdict}

    res = {
        "policy": POLICY, "n_trials": N_DEEP,
        "fractions": list(FRACTIONS_DEEP),
        "conditions": list(CONDITIONS_DEEP),
        "steer_noise": {name: look[name][1] for name in CONDITIONS_DEEP},
        "grip_spread": GRIP_SPREAD,
        "cells": cells, "by_condition": by_condition,
        # Back-compat top-level fields, from the attentive ("both") condition —
        # the headline the article quotes.
        "pairwise": by_condition["both"]["pairwise"],
        "n_significant_pairs": by_condition["both"]["n_significant_pairs"],
        "verdict": by_condition["both"]["verdict"],
        "correction": "Holm-Bonferroni, family-wise alpha 0.05, "
                      f"{len(by_condition['both']['pairwise'])} pairwise Fisher "
                      "exact tests, per condition",
        "why_this_run_exists": (
            "The 5x5 grid at n=40 gave in-fit rates of 12/0/0/0 with the closest "
            "pair at p=0.045 uncorrected -- nothing after correction. Breadth was "
            "spent where depth was needed."),
    }
    (out / "results_deep.json").write_text(json.dumps(res, indent=2) + "\n")
    print(f"\n  wrote {out / 'results_deep.json'}")
    return 0


def figures(out) -> None:
    results = json.loads((out / "results.json").read_text())
    traces = dict(np.load(out / "traces.npz"))

    # The n=40 grid is the breadth run; the n=120 deep run is what the claim rests
    # on. Overlay the deep cells so no figure ever shows an underpowered rate as
    # though it were the result. The grid's own cells survive for the 40%-front car
    # and for the conditions the deep run does not cover.
    deep_path = out / "results_deep.json"
    if deep_path.exists():
        d = json.loads(deep_path.read_text())
        results["deep"] = d
        for key, cell in d["cells"].items():
            results["cells"][key] = cell
        for k in (dkey(f) for f in d["fractions"]):
            results["failure_rate_inside_fit_both"][k] = \
                d["cells"][f"both|{k}"]["failure_rate_inside_fit"]
            nom = d["cells"][f"nominal|{k}"]
            if nom["n_finished"]:
                results["speed_nominal_s"][k] = nom["lap_time_mean"]
                results["lap_spread_perturbed_s"][k] = \
                    d["cells"][f"both|{k}"]["lap_time_std"]
        results["n_trials_headline"] = d["n_trials"]

    write(out / "01-what-fragile-looks-like.svg",
          fragility_figures.fragility_paths(results, traces))
    write(out / "02-speed-vs-fragility.svg",
          fragility_figures.pareto_figure(results))
    write(out / "03-when-it-lets-go.svg",
          fragility_figures.recovery_figure(results, traces))
    write(out / "04-perturbation-card.svg",
          fragility_figures.condition_card(results))


def main() -> int:
    out = episode_dir(11)
    if "--figures-only" in sys.argv:
        figures(out)
        return 0
    if "--deep" in sys.argv:
        return deep(out)

    quick = "--quick" in sys.argv
    n = 6 if quick else N_TRIALS
    fracs = (0.40, 0.54, 0.65) if quick else FRACTIONS

    print("Episode 11 — The fastest setup is the one that crashes")
    print(f"  Episode 10's policy, reused verbatim. Nothing is trained here.")
    print(f"  {len(fracs)} designs x {len(CONDITIONS)} conditions x {n} "
          f"deployed rollouts\n")

    model, _ = load_policy()
    t0 = time.time()
    cells: dict[str, dict] = {}
    for name, sn, gs, _desc in CONDITIONS:
        print(f"  {name}:")
        for ff in fracs:
            c = trial(model, ff, sn, gs, n)
            cells[f"{name}|{dkey(ff)}"] = c
            lo, hi = c["finish_rate_ci95"]
            lap = (f"lap {c['lap_time_mean']:5.2f} +/- {c['lap_time_std']:.2f} s"
                   if c["n_finished"] > 1 else "           --      ")
            print(f"    {dkey(ff)} front  finished {c['finish_rate']:4.0%} "
                  f"[{lo:.0%}-{hi:.0%}]  {lap}  worst slip "
                  f"{c['worst_slip_deg']:4.1f} deg")
    print(f"\n  {time.time()-t0:.0f}s")

    # --- the finding: does being fast cost robustness? ----------------------
    nominal = {dkey(f): cells[f"nominal|{dkey(f)}"] for f in fracs}
    both = {dkey(f): cells[f"both|{dkey(f)}"] for f in fracs}
    # Speed is measured UNPERTURBED (what a setup sheet would claim) and fragility
    # PERTURBED (what you actually get). Comparing a car's advertised pace against
    # its behaviour on a bad day is the whole point of the episode.
    beyond = {dkey(f): cells[f"beyond|{dkey(f)}"] for f in fracs}
    speed = {k: v["lap_time_mean"] for k, v in nominal.items()}
    frag = {k: v["failure_rate"] for k, v in both.items()}
    spread = {k: v["lap_time_std"] for k, v in both.items()}
    frag_beyond = {k: v["failure_rate"] for k, v in beyond.items()}
    # The quotable one: failures among laps that never left the fit.
    frag_in = {k: v["failure_rate_inside_fit"] for k, v in both.items()}
    frag_in_steer = {dkey(f): cells[f"steer|{dkey(f)}"]["failure_rate_inside_fit"]
                     for f in fracs}

    ranked = sorted((k for k in speed if np.isfinite(speed[k])),
                    key=lambda k: speed[k])
    print("  fastest-first, with what perturbation does to each:")
    print("    (in-fit = failures among laps that never exceeded 12 deg slip)")
    for k in ranked:
        b = both[k]
        print(f"    {k} front  nominal {speed[k]:5.2f} s  ->  all laps "
              f"{frag[k]:4.0%} fail | in-fit {frag_in[k]:4.0%} of "
              f"{b['n_inside_fit']:2d} laps"
              + ("  (lower bound)" if b["failure_rate_is_lower_bound"] else ""))

    report = Report(
        "D6-inherited — Episode 11 fragility sweep",
        "Episode 11 trains nothing, so it inherits Episode 10's training health "
        "verbatim, including its one failing check. These checks are about "
        "whether the FRAGILITY MEASUREMENT is sound, not whether the policy is.",
    )
    report.section("Is the perturbation actually perturbing anything?")
    # Measured only on the designs that survive UNPERTURBED. A design the policy
    # already cannot drive fails at 100% in every column, so including it pins
    # the worst-case at 100% everywhere and the check can never fire. The first
    # version did that and passed a level at which nothing whatsoever changed.
    baseline = [dkey(f) for f in fracs
                if cells[f"nominal|{dkey(f)}"]["failure_rate"] < 0.5]
    nom = float(np.mean([cells[f"nominal|{k}"]["failure_rate"] for k in baseline])) \
        if baseline else float("nan")
    pert = float(np.mean([cells[f"both|{k}"]["failure_rate"] for k in baseline])) \
        if baseline else float("nan")
    report.add(
        "perturbation_changes_the_outcome",
        bool(baseline) and pert > nom,
        f"across the {len(baseline)} designs that complete the lap unperturbed, "
        f"mean failure rate {nom:.0%} -> {pert:.0%} once perturbed. Measured on "
        f"those designs only: a car that already fails 100% of the time fails "
        f"100% under perturbation too, and averaging it in hides whether the "
        f"disturbance does anything at all.",
        value=pert - nom,
    )
    report.add(
        "perturbation_does_not_saturate",
        min(v["finish_rate"] for k, v in cells.items()
            if k.startswith("both")) < 1.0
        and max(v["finish_rate"] for k, v in cells.items()
                if k.startswith("both")) > 0.0,
        "at least one design survives and at least one does not. A level where "
        "everything fails ranks nothing, and neither does one where everything "
        "survives — both would produce a flat Pareto front that looks like a "
        "finding.",
    )
    report.section("Can the differences between designs be believed?")
    # Two designs are distinguishable only if their Wilson intervals are disjoint.
    pairs, disjoint = 0, 0
    ks = [dkey(f) for f in fracs]
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            pairs += 1
            la, ha = cells[f"both|{a}"]["finish_rate_ci95"]
            lb, hb = cells[f"both|{b}"]["finish_rate_ci95"]
            if ha < lb or hb < la:
                disjoint += 1
    report.add(
        "some_designs_are_statistically_distinguishable",
        disjoint > 0,
        f"{disjoint} of {pairs} design pairs have disjoint 95% Wilson intervals "
        f"on the perturbed finish rate at n = {n}. With overlapping intervals "
        f"everywhere the ranking would be decoration.",
        value=disjoint,
    )
    report.section("Is enough of the data inside the tire model to use?")
    # Per LAP. The first version tested the worst slip in each condition, which
    # at 40 rollouts is an extreme-value statistic: it failed at 35 deg while the
    # median lap sat at 8 deg, disqualifying 39 defensible laps for one excursion.
    q = {k: v for k, v in cells.items() if k.split("|")[0] in QUOTABLE}
    keep = min(v["inside_fit_fraction"] for v in q.values())
    med = max(v["median_worst_slip_deg"] for v in q.values())
    report.add(
        "most_laps_are_inside_the_fit",
        keep >= 0.5 and med <= 12.0,
        f"the leanest quotable cell keeps {keep:.0%} of its laps inside the "
        f"+/-12 deg fit, and the highest median worst-slip across them is "
        f"{med:.1f} deg. Laps that excurse are discarded individually rather than "
        f"disqualifying their whole condition (rule 4 is a per-lap rule).",
        value=keep,
    )
    lower_bound = [k for k, v in q.items() if v["failure_rate_is_lower_bound"]]
    report.add(
        "discarded_failures_are_declared",
        True,
        f"{len(lower_bound)} of {len(q)} quotable cells discarded at least one "
        f"lap that BOTH failed and left the fit. For those cells the in-fit "
        f"failure rate is a LOWER BOUND — the discarded crashes are real crashes "
        f"we cannot attribute to the car rather than to our extrapolation. This "
        f"check always passes; it exists to put the number in the report.",
        value=len(lower_bound),
    )
    b = [v for k, v in cells.items() if k.startswith("beyond")]
    b_worst = max(v["worst_slip_deg"] for v in b)
    report.add(
        "the_beyond_condition_really_is_beyond",
        b_worst > 12.0,
        f"the `beyond` condition reaches {b_worst:.1f} deg of slip. It is reported "
        f"and excluded from every claim. This check exists so the exclusion is "
        f"justified by measurement rather than by assertion — if `beyond` turned "
        f"out to stay inside the fit, it would be quotable and the episode's "
        f"conclusion would change.",
        value=b_worst,
    )
    report.section("Is there any disturbance that breaks it inside the fit?")
    # The episode's actual result, as a check so it cannot be quietly forgotten.
    # Measured on the in-fit laps only, and only on cars the policy can drive
    # unperturbed — a car that fails 100% with no disturbance has nothing to say
    # about disturbance.
    drivable = [dkey(f) for f in fracs
                if cells[f"nominal|{dkey(f)}"]["failure_rate"] < 0.5]
    inside_failures = max(
        (cells[f"{c}|{k}"]["failure_rate_inside_fit"]
         for c in QUOTABLE if c != "nominal" for k in drivable),
        default=0.0)
    report.add(
        "a_speed_fragility_tradeoff_is_measurable_inside_the_fit",
        inside_failures > 0.0,
        f"the worst in-fit failure rate on a drivable car is "
        f"{inside_failures:.0%}. At 0% there would be no fragility to rank and the "
        f"Pareto front this episode set out to measure would not exist at any "
        f"defensible disturbance. An earlier 10-rollout calibration said exactly "
        f"that and was wrong — see FINDINGS F70.",
        value=inside_failures,
    )
    # The ordering is the claim, so check the ordering, not just that failures
    # exist. Ranked fastest-first on unperturbed pace.
    by_speed = sorted(drivable,
                      key=lambda k: cells[f"nominal|{k}"]["lap_time_mean"])
    rates = [cells[f"both|{k}"]["failure_rate_inside_fit"] for k in by_speed]
    monotone = all(a >= b - 1e-12 for a, b in zip(rates, rates[1:]))
    report.add(
        "the_faster_car_is_the_more_fragile_one",
        monotone and rates[0] > rates[-1],
        "in-fit failure rate falls monotonically as the cars get slower: "
        + " -> ".join(f"{k} {r:.0%}" for k, r in zip(by_speed, rates))
        + ". This is the episode's claim; if the ordering were scrambled there "
          "would be a tradeoff in magnitude but not one you could act on.",
        value=rates[0] - rates[-1],
    )

    results = {
        "policy": POLICY,
        "trained_here": False,
        "n_trials": n,
        "jitter_m": JITTER_M,
        # The headline value — attentive driver, F96's calibration. The figures'
        # captions quote this one; distracted and retracted are in "conditions".
        "steer_noise": STEER_ATTENTIVE,
        "steer_noise_distracted": STEER_DISTRACTED,
        "steer_noise_retracted_F96": STEER_RETRACTED,
        "grip_spread": GRIP_SPREAD,
        "envelope_penalty": ENVELOPE_PENALTY,
        "fractions": list(fracs),
        "conditions": [{"name": c[0], "steer_noise": c[1], "grip_spread": c[2],
                        "description": c[3]} for c in CONDITIONS],
        "cells": cells,
        "speed_nominal_s": speed,
        "failure_rate_perturbed": frag,
        "failure_rate_inside_fit_both": frag_in,
        "failure_rate_inside_fit_steer": frag_in_steer,
        "failure_rate_beyond_envelope": frag_beyond,
        "quotable_conditions": list(QUOTABLE),
        "beyond_is_not_quotable": (
            "The `beyond` condition is the only one that produces failures, and it "
            "reaches 12-17 deg of slip where the tire file has no fit. Its failure "
            "rates are reported for direction only and support no claim (rule 4)."),
        "lap_spread_perturbed_s": spread,
        "ranked_fastest_first": ranked,
        "checks_passed": report.ok,
        "check_failures": [c.name for c in report.failures],
        "inherited_d6": {
            "from": "experiments/ep10/out/results.json",
            "note": "Episode 11 trains nothing; Episode 10's D6 applies and it "
                    "fails exploration_is_not_growing. See FINDINGS F69.",
        },
        "comparability": (
            "Absolute lap times are NOT comparable with Seasons 1-2 (rule 6): "
            "different entry speed, and only the RL environment is being asked "
            "about disturbance rejection at all. Speed is measured unperturbed "
            "and fragility perturbed, deliberately."),
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    # traces: the first 8 rollouts per design per condition for the path fan, PLUS
    # every lap that left the +/-12 deg fit in a quotable perturbed condition.
    #
    # The second part is not optional. The recovery figure needs a lap that went
    # past the fit and came back beside one that went past and did not, and at a
    # realistic disturbance (F96/F98) those laps are RARE — 12 in 120 for the
    # fastest design and 1-4 for the others. Saving only seeds 0-7 captured none of
    # them, so the figure silently drew two laps that never left the fit at all
    # while its caption said they had. Which seeds qualify is read from the cell's
    # own per-lap arrays, so this cannot disagree with the reported rates.
    def trace_rollout(tr, name, sn, gs, ff, k):
        tag = f"{name}_{dkey(ff).replace('.', '')}_{k}"
        if f"{tag}_s" in tr:
            return
        env = DrivingEnv(EnvConfig(
            design_keys=DESIGN_KEYS, design_ranges=DESIGN_RANGES,
            envelope_penalty=ENVELOPE_PENALTY, start_jitter_m=JITTER_M,
            steer_noise=sn, grip_spread=gs), seed=k)
        env.set_design(front_mass_fraction=ff)
        r = rollout(env, greedy_policy(model), seed=k)
        for key in ("s", "n", "speed", "alpha_max_deg"):
            tr[f"{tag}_{key}"] = r[key]
        tr[f"{tag}_finished"] = np.array([float(r["finished"])])

    tr = {}
    for name, sn, gs, _d in CONDITIONS:
        for ff in fracs:
            for k in range(min(8, n)):
                trace_rollout(tr, name, sn, gs, ff, k)
            if name == "nominal" or name not in QUOTABLE:
                continue
            slips = cells[f"{name}|{dkey(ff)}"]["per_lap_worst_slip_deg"]
            over = [k for k, v in enumerate(slips) if v > 12.0]
            for k in over:
                trace_rollout(tr, name, sn, gs, ff, k)
    np.savez(out / "traces.npz", **tr)

    md = report.write_markdown(command="python -m experiments.ep11.run")
    report.write()
    report.print_summary(verbose="-v" in sys.argv)
    print(f"\n  write-up {md}")
    figures(out)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
