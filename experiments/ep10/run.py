"""Episode 10 — One policy, a thousand cars.

Episode 9's driver could drive one car. This one is trained across the whole
weight-distribution range with the car's balance in its observation, so a single
policy can be asked about any of them — which is the only way an RL comparison
between designs means anything. Retraining per design measures the retraining.

Then the cross-check the series has been building toward: **sweep balance with the
learned driver and compare the trend against Episode 7's optimal-control sweep.**
Two methods with nothing in common but the physics.

**Absolute times are not comparable between the two and are never presented as
such** (CLAUDE.md rule 6). The RL environment starts at 15 m/s and does not
enforce the slip envelope; the solver starts at 32 m/s and does. What can be
compared is the *shape*: does lap time vary with balance the same way, and does
each method put its optimum in the same place?

Run::

    python -m experiments.ep10.run
    python -m experiments.ep10.run --figures-only
    python -m experiments.ep10.run --quick
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import torch

from diagnostics.common import Report
from diagnostics import D6_training_health as D6
from experiments.common import ROOT, episode_dir, write
from physics import schema
from physics import track as T
from physics.ppo import ActorCritic, PPOConfig, greedy_policy, train
from physics.rl_env import DrivingEnv, EnvConfig, rollout
from viz import conditioned_figures

TOTAL_STEPS = 5_000_000
SEED = 0
DESIGN_KEYS = ("front_mass_fraction",)

#: Train over exactly the range that gets evaluated. The documented design sweep
#: is 0.35-0.65, but Episode 7 only asks about 0.40-0.65, and the cars below 0.40
#: are the hardest in the range — at 0.35 front the understeer gradient is well
#: past -0.5 deg/g and the car is genuinely difficult. A first run over the full
#: range at 2M steps did not learn to drive at all: it collapsed into sliding at
#: 112 degrees of slip, finished 0% of laps, and spent 29.7% of its time outside
#: the tire model. See FINDINGS F60.
DESIGN_RANGES = {"front_mass_fraction": (0.40, 0.65)}

#: Cost per step for leaving the slip envelope. **Episode 10 constrains where
#: Episode 9 did not**, and that is a deliberate protocol change, not a bug fix
#: (F62, F63). Unconstrained, the reward's optimum is to slide: 21.0 m/s outside
#: the tire fit against 20.2 m/s inside it. A policy that answers "which weight
#: distribution is quicker?" by sliding at 121 degrees is answering a question
#: about our curve fit.
ENVELOPE_PENALTY = 0.5

#: Where to interrogate the trained policy. These are Episode 7's sweep points,
#: so the two methods are asked about exactly the same cars.
EVAL_FRACTIONS = (0.40, 0.47, 0.54, 0.61, 0.65)

#: Rollouts per design point. Enough to put an error bar on every number, which
#: Episode 9 could not do and was the biggest hole in it (CLAUDE.md rule 5).
N_EVAL = 12

#: Start-position jitter during evaluation, metres. Must be non-zero or a
#: deterministic policy produces identical rollouts and a meaningless zero spread.
EVAL_JITTER_M = 8.0


def _sampled(model):
    def act(obs):
        with torch.no_grad():
            d = model.distribution(torch.as_tensor(obs, dtype=torch.float32))
            return d.sample().numpy()
    return act


def evaluate_across_designs(model, fractions, n=N_EVAL) -> dict:
    """Ask the one policy about each car, several times, both ways."""
    out = {}
    for ff in fractions:
        row = {}
        for name, make in (("stochastic", _sampled), ("greedy", greedy_policy)):
            runs = []
            for s in range(n):
                # Jitter the start. Without it the deployed policy is
                # deterministic and the environment is deterministic, so all n
                # rollouts are byte-identical and the reported spread is exactly
                # zero — twelve copies of one run presented as twelve samples.
                # An earlier version did that and printed "+/- 0.000 s over 12
                # rollouts", which reads as precision and is the absence of
                # replication. See FINDINGS F66.
                env = DrivingEnv(EnvConfig(design_keys=DESIGN_KEYS,
                                           design_ranges=DESIGN_RANGES,
                                           envelope_penalty=ENVELOPE_PENALTY,
                                           start_jitter_m=EVAL_JITTER_M), seed=s)
                env.set_design(front_mass_fraction=ff)
                runs.append(rollout(env, make(model), seed=s))
            fin = [r for r in runs if r["finished"]]
            # Progress rate: distance covered per second, over EVERY rollout
            # including the ones that crashed. Mean lap time is computed only
            # over finishers, so when the finish rate varies by design — and it
            # does — a car that finishes 30% of laps is scored on its luckiest
            # runs while one that finishes 95% is scored on typical ones. That
            # is survivorship bias, biased in an unknown direction, and it was
            # the metric an earlier version compared designs on. Progress rate
            # has no such hole because nothing is dropped. See FINDINGS F58.
            rate = [r["distance_m"] / max(r["lap_time_s"], 1e-9) for r in runs]
            row[name] = {
                "distance_mean": float(np.mean([r["distance_m"] for r in runs])),
                "distance_std": float(np.std([r["distance_m"] for r in runs])),
                "finish_rate": float(np.mean([r["finished"] for r in runs])),
                "progress_rate_mean": float(np.mean(rate)),
                "progress_rate_std": float(np.std(rate)),
                "lap_time_mean": float(np.mean([r["lap_time_s"] for r in fin]))
                if fin else float("nan"),
                "lap_time_std": float(np.std([r["lap_time_s"] for r in fin]))
                if fin else float("nan"),
                "n_finished": len(fin),
                "worst_slip_deg": float(np.max([r["worst_slip_deg"] for r in runs])),
                "slip_over_bound": float(np.mean(
                    [r["slip_over_12deg_fraction"] for r in runs])),
            }
        out[dkey(ff)] = row
    return out


#: One canonical way to name a design point. JSON has no float keys, so a dict
#: keyed by 0.40 comes back keyed by the string "0.4" — not even "0.40" — and
#: every lookup silently misses. That is exactly what happened: the cross-check
#: figure rendered axes, grid, labels and no data at all, and nothing raised.
#: Everything that indexes a design goes through this. See FINDINGS F59.
def dkey(ff) -> str:
    return f"{float(ff):.2f}"


def _ep07_reference() -> dict | None:
    """Episode 7's optimal-control sweep, if it has been run."""
    p = ROOT / "experiments" / "ep07" / "out" / "results.json"
    if not p.exists():
        return None
    r = json.loads(p.read_text())
    return {dkey(ff): r["rows"][f"rwd_{float(ff):.2f}"]
            for ff in r["front_fractions"]}


def figures(out) -> None:
    results = json.loads((out / "results.json").read_text())
    history = json.loads((out / "history.json").read_text())
    traces = dict(np.load(out / "traces.npz"))
    write(out / "01-one-driver-many-cars.svg",
          conditioned_figures.morph_figure(results, traces))
    write(out / "02-two-methods-one-answer.svg",
          conditioned_figures.crosscheck_figure(results))
    write(out / "03-conditioned-card.svg",
          conditioned_figures.conditioned_card(results, history))


def main() -> int:
    out = episode_dir(10)
    if "--figures-only" in sys.argv:
        figures(out)
        return 0

    quick = "--quick" in sys.argv
    eval_only = "--eval-only" in sys.argv
    steps = 60_000 if quick else TOTAL_STEPS
    fracs = EVAL_FRACTIONS if not quick else (0.47, 0.54, 0.61)
    n_eval = N_EVAL if not quick else 3

    print("Episode 10 — One policy, a thousand cars")
    lo, hi = DESIGN_RANGES["front_mass_fraction"]
    print(f"  {steps:,} steps, front mass fraction resampled from "
          f"{lo:.2f}-{hi:.2f} every episode and fed to the policy\n")

    cfg = PPOConfig(total_steps=steps, n_envs=8, rollout_steps=512, epochs=10,
                    seed=SEED)
    if eval_only:
        # The policy is the artefact; every number downstream of it is derived
        # (rule 7). Without this path the only way to redraw a figure was a
        # 5M-step retrain, so results.json and the figures went stale relative
        # to the cross-check gate and a retracted +1.00 correlation stayed on
        # disk labelled as current. See FINDINGS F68.
        probe = DrivingEnv(EnvConfig(design_keys=DESIGN_KEYS,
                                     design_ranges=DESIGN_RANGES,
                                     envelope_penalty=ENVELOPE_PENALTY))
        model = ActorCritic(probe.obs_dim, probe.act_dim, cfg.hidden,
                            cfg.init_log_std)
        model.load_state_dict(torch.load(out / "policy.pt"))
        res = {"model": model,
               "history": json.loads((out / "history.json").read_text()),
               "config": json.loads((out / "train_config.json").read_text())}
        print(f"  reusing the cached policy in {out / 'policy.pt'} — no training")
    else:
        t0 = time.time()
        res = train(lambda i: DrivingEnv(
            EnvConfig(start_jitter_m=10.0, design_keys=DESIGN_KEYS,
                      design_ranges=DESIGN_RANGES,
                                  envelope_penalty=ENVELOPE_PENALTY), seed=i),
            cfg)
        print(f"  trained in {time.time()-t0:.0f}s ({len(res['history'])} updates)")
        torch.save(res["model"].state_dict(), out / "policy.pt")
        (out / "train_config.json").write_text(
            json.dumps(res["config"], indent=2) + "\n")
        (out / "history.json").write_text(
            json.dumps(res["history"], indent=2) + "\n")

    print(f"\n  asking the one policy about {len(fracs)} cars, "
          f"{n_eval} rollouts each:")
    across = evaluate_across_designs(res["model"], fracs, n_eval)
    # DEPLOYED first, sampled second and marked as diagnostic. This printed the
    # sampled table alone, which is the reporting habit that let Episode 9 be
    # written around an 88% finish rate whose deployed figure was 0%. The
    # invariant is that the result is the deployed policy. See FINDINGS F61.
    for ff, row in across.items():
        g, st = row["greedy"], row["stochastic"]
        print(f"    {ff} front:  DEPLOYED finished {g['finish_rate']:4.0%}"
              + (f"  lap {g['lap_time_mean']:5.2f} +/- {g['lap_time_std']:.2f} s"
                 if g["n_finished"] else f"  reached {g['distance_mean']:5.1f} m"))
        print(f"                 (sampled  finished {st['finish_rate']:4.0%}"
              + (f"  lap {st['lap_time_mean']:5.2f} +/- {st['lap_time_std']:.2f} s)"
                 if st["n_finished"] else f"  reached {st['distance_mean']:5.1f} m)"))

    # --- D6 on the nominal car ---------------------------------------------
    report = Report("D6", "Training health — design-conditioned policy",
                    "The same nine checks Episode 9 introduced, run on a policy "
                    "that has to drive every car in the range rather than one.")
    nominal = EnvConfig(design_keys=DESIGN_KEYS, design_ranges=DESIGN_RANGES,
                              envelope_penalty=ENVELOPE_PENALTY)
    D6.run_checks(report, res["history"], res["model"], nominal, res["config"])

    ref = _ep07_reference()
    results = {
        "total_steps": steps, "seed": SEED, "n_eval": n_eval,
        "design_keys": list(DESIGN_KEYS),
        "design_range": list(DESIGN_RANGES["front_mass_fraction"]),
        "design_range_documented": list(schema.DESIGN_SWEEP["front_mass_fraction"]),
        # Recorded so the figure stamps can state the protocol rather than
        # restate a constant copied from Episode 9. See FINDINGS F68.
        "envelope_penalty": ENVELOPE_PENALTY,
        "eval_fractions": list(fracs),
        "train_config": res["config"],
        "across_designs": across,
        "ep07_optimal_control": ref,
        "d6_passed": report.ok,
        "d6_failures": [c.name for c in report.failures],
        "comparability": (
            "Absolute lap times are NOT comparable with Episode 7. The RL "
            "environment starts at 15 m/s and does not enforce the slip "
            "envelope; the optimal-control solver starts at 32 m/s and does. "
            "Only the SHAPE of each curve against balance is compared "
            "(CLAUDE.md rule 6)."),
    }

    # the cross-check, stated as a correlation of shapes rather than of values
    if ref:
        # Only compare against optimal-control points that CONVERGED. Three of
        # Episode 7's five rear-drive solves originally stopped on the iteration
        # limit, carrying up to ~0.08 s of error (F39) against a total spread of
        # 0.11 s — so a correlation using them compares the learned shape against
        # a baseline that is potentially half noise. The figure drew them hollow;
        # the arithmetic did not exclude them. See FINDINGS F57.
        # A design is usable for the cross-check only if BOTH methods produced a
        # trustworthy answer for it: the optimal-control solve converged, AND the
        # deployed policy actually drives the car.
        #
        # The second condition is not fussiness. Without it the correlation is
        # computed across designs the policy cannot drive at all, so it measures
        # "which cars can this policy handle?" against "which cars are quicker?"
        # — different questions with a spurious relationship between them. That
        # produced a shape correlation of +0.75 with an RL spread of 6.15 s
        # against the solver's 0.098 s: the number was entirely driven by two
        # total failures. See FINDINGS F64.
        drivable = {dkey(f) for f in fracs
                    if across[dkey(f)]["greedy"]["finish_rate"]
                    >= D6.DEPLOY_FINISH_RATE}
        common = [f for f in fracs
                  if dkey(f) in ref and ref[dkey(f)].get("converged", True)
                  and dkey(f) in drivable]
        results_dropped = sorted(
            {dkey(f) for f in fracs if dkey(f) in ref} - set(map(dkey, common)))
        if results_dropped:
            print(f"    excluded (solver did not converge, or the policy cannot "
                  f"drive that car): {', '.join(results_dropped)}")
        # RL side uses progress rate, not finisher-only lap time (F58). Higher
        # is faster, so it is negated to keep "lower is better" on both curves.
        # Every design in `common` is drivable by construction, so lap time is
        # available for all of them and is directly what the solver reports.
        # Progress rate was the right metric when failures had to be included.
        rl = np.array([across[dkey(f)]["greedy"]["lap_time_mean"]
                       for f in common])
        oc = np.array([ref[dkey(f)]["time_s"] for f in common])
        ok = np.isfinite(rl)
        results["crosscheck_n_usable"] = int(ok.sum())
        if ok.sum() >= 3:
            rl_n = (rl[ok] - rl[ok].mean()) / (rl[ok].std() or 1.0)
            oc_n = (oc[ok] - oc[ok].mean()) / (oc[ok].std() or 1.0)
            # A correlation on three monotone points is very nearly determined:
            # two RANDOM monotone 3-point series exceed r = 0.99 about 25% of the
            # time. Report it, but never as the headline, and report alongside it
            # the two things three points can actually support — whether the
            # methods agree on DIRECTION, and how far apart they are on
            # MAGNITUDE. See FINDINGS F65.
            results["shape_correlation"] = float(np.corrcoef(rl_n, oc_n)[0, 1])
            results["shape_correlation_caveat"] = (
                f"computed on {int(ok.sum())} designs; with both series monotone "
                "this statistic is nearly determined and is not evidence on its "
                "own — read the direction and magnitude rows instead")
            rl_o = np.argsort(np.argsort(rl[ok]))
            oc_o = np.argsort(np.argsort(oc[ok]))
            results["same_ordering"] = bool(np.array_equal(rl_o, oc_o))
            rl_rel = float((rl[ok].max() - rl[ok].min()) / abs(np.mean(rl[ok])))
            oc_rel = float((oc[ok].max() - oc[ok].min()) / abs(np.mean(oc[ok])))
            results["rl_relative_spread"] = rl_rel
            results["oc_relative_spread"] = oc_rel
            results["rl_over_oc_sensitivity"] = rl_rel / max(oc_rel, 1e-9)
            results["crosscheck_fractions"] = [float(f) for f in common]
            # Two different exclusion reasons, recorded separately. Collapsing
            # them into one "unconverged" key said the solver failed on the 40%
            # car when in fact the solver is fine there and the POLICY cannot
            # drive it — which is this episode's actual finding, mislabelled as
            # a solver problem.
            results["crosscheck_excluded"] = {
                dkey(f): ("the deployed policy does not drive this car"
                          if dkey(f) not in drivable
                          else "the optimal-control solve did not converge")
                for f in fracs if dkey(f) in ref and dkey(f) not in set(map(dkey, common))}
            # Was "negated progress rate (m/s)" and is now deployed lap time.
            # The label did not follow the metric.
            results["crosscheck_rl_metric"] = (
                "deployed lap time (s), mean over jittered rollouts")
            results["rl_spread_s"] = float(rl[ok].max() - rl[ok].min())
            results["oc_spread_s"] = float(oc[ok].max() - oc[ok].min())
            results["rl_best_fraction"] = float(
                np.array(common)[ok][int(np.argmin(rl[ok]))])
            results["oc_best_fraction"] = float(
                np.array(common)[ok][int(np.argmin(oc[ok]))])
            print(f"\n  cross-check vs Episode 7 (shape only):")
            print(f"    RL  spread across balance {results['rl_spread_s']:.3f} s, "
                  f"fastest at {results['rl_best_fraction']:.2f} front")
            print(f"    OC  spread across balance {results['oc_spread_s']:.3f} s, "
                  f"fastest at {results['oc_best_fraction']:.2f} front")
            print(f"    same ordering of designs: {results['same_ordering']}")
            print(f"    relative spread: RL {100*results['rl_relative_spread']:.1f}% "
                  f"vs OC {100*results['oc_relative_spread']:.1f}% "
                  f"-> RL is {results['rl_over_oc_sensitivity']:.1f}x more "
                  f"sensitive to balance")
            print(f"    (shape correlation {results['shape_correlation']:+.4f}, "
                  f"but on {int(ok.sum())} monotone points that is nearly "
                  f"determined — not evidence on its own)")
        else:
            results["crosscheck_refused"] = (
                f"only {int(ok.sum())} design(s) have both a converged "
                f"optimal-control solve and a policy that drives them; three is "
                f"the minimum for a shape comparison to mean anything")
            print(f"\n  CROSS-CHECK REFUSED: {results['crosscheck_refused']}")
    else:
        print("\n  cross-check skipped: experiments/ep07/out/results.json missing")

    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    tr = {}
    for ff in fracs:
        # Same jitter and same seed as the evaluation, so the drawn line IS one
        # of the rollouts the numbers beside it come from. Without the jitter the
        # 40% car completes the corner from a standing start at s = 0 while all
        # twelve jittered evaluation rollouts leave the road — so the figure drew
        # a completed lap next to the words "finished 0%". A figure whose line is
        # not drawn from the reported population will contradict its own caption
        # sooner or later. F68.
        env = DrivingEnv(EnvConfig(design_keys=DESIGN_KEYS, design_ranges=DESIGN_RANGES,
                              envelope_penalty=ENVELOPE_PENALTY,
                              start_jitter_m=EVAL_JITTER_M), seed=0)
        env.set_design(front_mass_fraction=ff)
        # DEPLOYED, not sampled. These traces are what the line figures draw, and
        # drawing sampled lines beside a table of deployed lap times put two
        # different drivers in one figure — including a 40% car whose sampled line
        # completes the corner and whose deployed line leaves the road. The
        # deployed policy is the result (F61), so it is what gets drawn. F68.
        r = rollout(env, greedy_policy(res["model"]), seed=0)
        tag = dkey(ff).replace(".", "")
        for k in ("s", "n", "speed", "alpha_max_deg"):
            tr[f"f{tag}_{k}"] = r[k]
    np.savez(out / "traces.npz", **tr)

    md = report.write_markdown(command="python -m experiments.ep10.run")
    report.write()
    report.print_summary(verbose="-v" in sys.argv)
    print(f"\n  write-up {md}")
    figures(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
