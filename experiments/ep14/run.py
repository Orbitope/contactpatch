"""Episode 14 — what the machine found instead. Flagship.

Episode 13 built the classical answer to "if pushing one wheel harder rotates
the car, why not just do that?" — a reference model and a PID decide how much
rotation is wanted, a QP allocator decides which wheels pay for it. This
episode asks the sharper question the research plan poses
(``docs/vehicle-codesign-research-plan.md`` Phase 4b): **does learning beat
hand-designed allocation, and if so where** — not "can RL drive fast."

Three variants, one corner, one physics model:

======  ==================================  ======================
C       reference model + PID -> Mz          QP allocator (Ep 13, done)
H       RL policy OUTPUTS the Mz demand      the SAME QP allocator
E       RL policy outputs four wheel forces  none — no allocator at all
======  ==================================  ======================

H is deliberately the smallest possible change from C: swap the reference
model and PID for a learned scalar, keep everything downstream identical. If H
disagrees with C, the disagreement is attributable to the upper layer alone,
because the lower layer is bit-for-bit the same code
(:class:`physics.torque_vectoring.Allocator`). E removes the allocator
entirely and asks whether four learned numbers per step reinvent it, beat it,
or do neither.

**Do not script the conclusion.** "It reinvented the allocator" is a fine
result and arguably the more interesting one — a first-principles system
finding the same answer as twenty years of engineering consensus is
corroboration, not disappointment.

Pacing, per the approved plan: this file is the PILOT phase. ``--pilot`` runs
a short training pass per variant to validate the whole pipeline — the action
modes, the D6 gate, the comparison metric, one sanity figure — and reports
wall-clock time back before any production, multi-seed run is committed to.
Do not read pilot-run numbers as a result; a pilot exists to find out whether
the infrastructure works, not what the answer is.

Run::

    python -m experiments.ep14.run --pilot
    python -m experiments.ep14.run --pilot --figures-only

Production, one (variant, seed) per process so seeds run in parallel rather
than serially — rule 5 wants 3-5 seeds per configuration, and at ~4.8h/seed
for H and ~2.4h/seed for E (linear-scaled from the pilot, F91) serial would
cost the better part of a day::

    python -m experiments.ep14.run --variant=H --seed=0
    python -m experiments.ep14.run --variant=H --seed=1
    ...
    python -m experiments.ep14.run --aggregate     # after all seeds finish
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

from diagnostics.common import Report
from diagnostics import D6_training_health as D6
from experiments.common import episode_dir, write
from physics.double_track import CORNERS, DoubleTrackBackend, WheelForces
from physics.ppo import ActorCritic, PPOConfig, greedy_policy, train
from physics.rl_env import DrivingEnv, EnvConfig, rollout
from physics.track import long_exit

SEED = 0

#: Short enough to validate the pipeline in minutes, not a result. Roughly
#: Episode 9's own --quick scale; variant E's action space is larger so it may
#: need more even to look sane, which is itself pilot information.
PILOT_STEPS = 60_000

#: Placeholder for the production run this pilot exists to size correctly.
#: Episode 10 needed 5M steps for a 2-action policy; H (3 actions) and E
#: (5 actions) are not assumed to need the same, and this number is NOT to be
#: trusted until the pilot's wall-clock time comes back.
PRODUCTION_STEPS = 5_000_000

#: Matches Episode 10's protocol: penalise operating outside the tire fit,
#: because an unconstrained policy's optimum is to slide (F62), and a sliding
#: torque-vectoring policy is not measuring torque vectoring.
ENVELOPE_PENALTY = 0.5

#: Score the DEPLOYED policy every this many updates and keep the best.
#: 20 updates is ~82,000 training steps; at 1,220 updates that is 61
#: evaluations of 4 laps each, about 6% of wall-clock. See FINDINGS F93 — the
#: first production run had none of this, kept the final weights, and reported
#: six policies that had each already driven a clean lap as "RL does not
#: converge."
EVAL_EVERY = 20
EVAL_EPISODES = 4

VARIANTS = {
    "H": {"tv_mode": "hybrid", "init_log_std": (-2.5, -1.0, -1.5)},
    "E": {"tv_mode": "end_to_end",
          "init_log_std": (-2.5, -1.5, -1.5, -1.5, -1.5)},
}


def _tag(variant: str, seed: int, pilot: bool) -> str:
    """Filename fragment for one (variant, seed) run. Pilot artifacts keep the
    unsuffixed names they already have on disk (F91) rather than being
    silently overwritten by seed-suffixed production ones."""
    return variant if pilot else f"{variant}_seed{seed}"


def _env_config(variant: str) -> EnvConfig:
    return EnvConfig(tv_mode=VARIANTS[variant]["tv_mode"],
                     envelope_penalty=ENVELOPE_PENALTY)


def _policy_from(out: Path, tag: str, cfg: EnvConfig):
    probe = DrivingEnv(cfg)
    train_cfg = json.loads((out / f"train_config_{tag}.json").read_text())
    model = ActorCritic(probe.obs_dim, probe.act_dim, train_cfg["hidden"],
                        train_cfg["init_log_std"])
    model.load_state_dict(torch.load(out / f"policy_{tag}.pt"))
    return model, train_cfg


def train_variant(out: Path, variant: str, steps: int, seed: int,
                  tag: str) -> dict:
    cfg = _env_config(variant)
    ppo_cfg = PPOConfig(total_steps=steps, n_envs=8, rollout_steps=512,
                        epochs=10, init_log_std=VARIANTS[variant]["init_log_std"],
                        seed=seed, eval_every=EVAL_EVERY,
                        eval_episodes=EVAL_EPISODES, entropy_anneal=True)
    print(f"  variant {variant} seed {seed}: {steps:,} steps, act_dim="
          f"{DrivingEnv(cfg).act_dim}, envelope_penalty={ENVELOPE_PENALTY:g}, "
          f"eval every {EVAL_EVERY} updates")
    t0 = time.time()
    res = train(lambda i: DrivingEnv(
        EnvConfig(tv_mode=VARIANTS[variant]["tv_mode"], start_jitter_m=10.0,
                  envelope_penalty=ENVELOPE_PENALTY), seed=i), ppo_cfg,
        # Scored on the environment the result is REPORTED on: no start
        # jitter, same config D6 and evaluate_variant use. Selecting on the
        # training distribution would select for something else.
        make_eval_env=lambda: DrivingEnv(_env_config(variant)))
    wall_s = time.time() - t0
    print(f"    trained in {wall_s:.0f}s ({len(res['history'])} updates)")
    if "best_update" in res:
        ev = res["best_eval"]
        print(f"    best deployed checkpoint: update {res['best_update']}"
              f"/{res['n_updates']} — return {ev['eval_return']:.1f}, "
              f"distance {ev['eval_distance']:.0f} m, "
              f"finish {ev['eval_finish_rate']:.0%}")
        # The final weights are kept too, because "the last checkpoint is not
        # the best one" is this episode's own correction of record (F93) and
        # it has to stay checkable rather than asserted.
        torch.save(res["final_state"], out / f"policy_{tag}_final.pt")
    torch.save(res["model"].state_dict(), out / f"policy_{tag}.pt")
    (out / f"train_config_{tag}.json").write_text(
        json.dumps(res["config"], indent=2) + "\n")
    (out / f"history_{tag}.json").write_text(
        json.dumps(res["history"], indent=2) + "\n")
    return {**res, "wall_s": wall_s}


def evaluate_variant(out: Path, tag: str, model, cfg: EnvConfig,
                     history: list, train_cfg: dict) -> dict:
    report = Report(
        f"D6-ep14-{tag}", f"Episode 14 {tag} — training health",
        "The same ten Season 3 checks, plus the exploration-scale check this "
        "episode's larger action space adds.")
    payload = D6.run_checks(report, history, model, cfg, train_cfg)
    ev = payload["evaluation"]
    md = report.write_markdown(
        command=f"python -m experiments.ep14.run  # {tag}")
    report.write()
    print(f"    D6: {'PASSED' if report.ok else f'FAILED ({len(report.failures)})'}"
          f" — {md.name}")
    for c in report.failures:
        print(f"      FAIL {c.name}")

    # One rollout of the DEPLOYED (mean-action) policy, for the sanity trace.
    # F61: the deployed policy is the result. Not sampled.
    env = DrivingEnv(cfg)
    tr = rollout(env, greedy_policy(model), seed=0)
    return {"evaluation": {k: {kk: vv for kk, vv in v.items() if kk != "runs"}
                          for k, v in ev.items()},
            "d6_passed": report.ok,
            "d6_failures": [c.name for c in report.failures],
            "deployed_trace": tr}


def realized_mz(trace: dict, params) -> np.ndarray:
    """The yaw moment a trajectory ACTUALLY made, from its logged per-wheel
    forces — computed downstream (rule 7), never inside the training loop.

    Works identically for C, H and E, which is what makes it the honest
    "difference map between control surfaces" the plan asks for: C and H have
    an explicit Mz *demand* to compare delivery against, E has none at all,
    but all three produce four wheel forces and the physics computing what
    moment those forces make is the SAME function
    (:meth:`physics.double_track.DoubleTrackBackend.yaw_moment`) regardless of
    which controller chose them.
    """
    backend = DoubleTrackBackend(params)
    n = len(trace["s"])
    mz = np.zeros(n)
    for i in range(n):
        wheels = {c: WheelForces(fy=trace[f"fy_{c}"][i], fx=trace[f"fx_{c}"][i],
                                 alpha=0.0, kappa=0.0, fz=trace[f"fz_{c}"][i])
                  for c in CORNERS}
        mz[i] = backend.yaw_moment(wheels, float(trace["steer"][i]))
    return mz


def figures(out: Path, name: str = "results.json",
           fig_name: str = "01-pilot-sanity.svg") -> None:
    from viz import rl_tv_figures
    results = json.loads((out / name).read_text())
    write(out / fig_name, rl_tv_figures.pilot_sanity_figure(results))


def full_trace(out: Path, variant: str, seed: int) -> dict:
    """Re-roll the DEPLOYED policy for one (variant, seed) to recover the
    per-corner fx/fy/fz arrays the compact ``result_*.json`` doesn't keep
    (only their downstream summaries do). Same policy file, same env config,
    same seed=0 rollout ``evaluate_variant`` already used — this reproduces
    that run's own s/mz/peak_a_y_g bit for bit, it just keeps more of it.

    Cached to ``full_trace_{variant}_seed{n}.npz`` so the figure step doesn't
    re-roll a policy every time a caption wording changes.
    """
    tag = f"{variant}_seed{seed}"
    cache = out / f"full_trace_{tag}.npz"
    if cache.exists():
        return dict(np.load(cache))
    cfg = _env_config(variant)
    model, _ = _policy_from(out, tag, cfg)
    env = DrivingEnv(cfg)
    tr = rollout(env, greedy_policy(model), seed=0)
    keys = ("s", "a_y", "utilisation_max", "alpha_max_deg") + tuple(
        f"{f}_{c}" for f in ("fx", "fy", "fz") for c in CORNERS)
    data = {k: np.asarray(tr[k]) for k in keys}
    np.savez(cache, **data)
    return data


def production_report(out: Path) -> dict:
    """Per-seed friction-ellipse detail for the figures that ask 'did each
    seed's policy stay inside the tire it was fitted on' — the compact
    aggregate in ``results.json`` keeps only the representative seed's trace.

    Peak-g instant (for the control-surfaces comparison) and worst-SLIP
    instant (for the envelope-escape figure) are picked from the SAME logged
    arrays every other metric in this episode comes from (rule 7) — nothing
    here is computed inside a rollout loop. The worst-slip instant is
    ``argmax(alpha_max_deg)``, not ``argmax(utilisation_max)`` — the two need
    not coincide, and picking utilisation would let the friction-circle
    snapshot show a smaller angle than the ``worst_slip_deg`` already
    reported in ``result_*.json`` and the seed-scorecard figure, which is
    exactly the kind of disagreeing-numbers bug rule 3 exists to catch.
    """
    from physics import schema
    backend = DoubleTrackBackend(schema.RV_1)
    report = {"variants": {}}
    for variant in ("H", "E"):
        seeds = []
        for seed in range(3):
            rp = out / f"result_{variant}_seed{seed}.json"
            if not rp.exists():
                continue
            tr = full_trace(out, variant, seed)
            i_peak = int(np.argmax(np.abs(tr["a_y"])))
            i_slip = int(np.argmax(tr["alpha_max_deg"]))

            def _corners(i):
                out2 = {}
                for c in CORNERS:
                    fx, fy = float(tr[f"fx_{c}"][i]), float(tr[f"fy_{c}"][i])
                    fz = max(float(tr[f"fz_{c}"][i]), 1.0)
                    fx_p = float(backend.tire.peak_fx(fz))
                    fy_p = float(backend.tire.peak_fy(fz))
                    out2[c] = {"fx": fx, "fy": fy, "fz": fz,
                              "util": math.hypot(fx / fx_p, fy / fy_p)}
                return out2

            fracs = {}
            for c in CORNERS:
                fz = max(float(tr[f"fz_{c}"][i_slip]), 1.0)
                fx_p = float(backend.tire.peak_fx(fz))
                fy_p = float(backend.tire.peak_fy(fz))
                fracs[c] = {"fx_frac": float(tr[f"fx_{c}"][i_slip]) / fx_p,
                           "fy_frac": float(tr[f"fy_{c}"][i_slip]) / fy_p}
            seeds.append({
                "seed": seed,
                "peak_instant": {"s": float(tr["s"][i_peak]),
                                 "a_y_g": float(tr["a_y"][i_peak] / schema.G),
                                 "corners": _corners(i_peak)},
                "worst_slip_instant": {
                    "s": float(tr["s"][i_slip]),
                    "utilisation_max": float(tr["utilisation_max"][i_slip]),
                    "alpha_max_deg": float(tr["alpha_max_deg"][i_slip]),
                    "fracs": fracs,
                },
            })
        report["variants"][variant] = seeds
    (out / "production_report.json").write_text(
        json.dumps(report, indent=2) + "\n")
    return report


def _run_one(out: Path, variant: str, seed: int, steps: int, pilot: bool,
             eval_only: bool) -> dict:
    """Train (or load) and evaluate ONE (variant, seed) combination.

    Deliberately a single-variant, single-seed unit: rule 5's 3-5 seeds per
    configuration cost, linear-scaled from the pilot (F91), the better part of
    a day if run serially in one process. Each call to this function is meant
    to be one OS process, so seeds run in parallel across cores instead.
    """
    from physics import schema

    tag = _tag(variant, seed, pilot)
    cfg = _env_config(variant)
    if eval_only:
        model, train_cfg = _policy_from(out, tag, cfg)
        history = json.loads((out / f"history_{tag}.json").read_text())
        wall_s = None
        print(f"  reusing cached policy_{tag}.pt — no training")
    else:
        res = train_variant(out, variant, steps, seed, tag)
        model, history, train_cfg, wall_s = (
            res["model"], res["history"], res["config"], res["wall_s"])

    ev = evaluate_variant(out, tag, model, cfg, history, train_cfg)
    tr = ev.pop("deployed_trace")
    mz = realized_mz(tr, schema.RV_1)
    entry = {
        **ev,
        "variant": variant, "seed": seed, "wall_s": wall_s,
        "peak_a_y_g": float(np.max(np.abs(tr["a_y"])) / schema.G),
        "mean_utilisation": float(np.mean(tr["utilisation_max"])),
        "worst_slip_deg": float(np.max(tr["alpha_max_deg"])),
        "finished": bool(tr["finished"]),
        "distance_m": float(tr["distance_m"]),
        "s": tr["s"].tolist(),
        "mz": mz.tolist(),
    }
    (out / f"result_{tag}.json").write_text(json.dumps(entry, indent=2) + "\n")
    np.savez(out / f"trace_{tag}.npz",
            s=tr["s"], mz=mz, a_y=tr["a_y"],
            utilisation_max=tr["utilisation_max"],
            **{f"fx_{c}": tr[f"fx_{c}"] for c in CORNERS},
            **{f"fy_{c}": tr[f"fy_{c}"] for c in CORNERS})
    print(f"  {tag}: peak {entry['peak_a_y_g']:.3f} g, mean utilisation "
          f"{entry['mean_utilisation']:.2f}, finished={entry['finished']}\n")
    return entry


def _load_classical_c(results: dict) -> None:
    """Episode 13, reused — not retrained, not re-evaluated."""
    from physics import schema
    ep13 = episode_dir(13) / "results.json"
    if ep13.exists():
        c = json.loads(ep13.read_text())
        tv4 = c["traces"]["tv4"]
        i_peak = int(np.argmax(np.abs(tv4["a_y"])))
        results["classical_c"] = {
            "source": "experiments/ep13/out/results.json",
            "s": tv4["s"],
            "mz_demand": c["traces"]["tv4_control"]["mz_demand"],
            "mz_delivered": c["traces"]["tv4_control"]["mz_delivered"],
            "peak_instant": {
                "s": tv4["s"][i_peak],
                "a_y_g": tv4["a_y"][i_peak] / schema.G,
                "corners": {c2: {"fx": tv4[f"fx_{c2}"][i_peak],
                                "fz": tv4[f"fz_{c2}"][i_peak],
                                "util": tv4[f"util_{c2}"][i_peak]}
                           for c2 in CORNERS},
            },
        }
        print("  classical C loaded from experiments/ep13/out/results.json")
    else:
        print("  classical C not found — run experiments/ep13/run.py first "
              "for the three-way comparison")


def build_final_figures(out: Path, results: dict) -> None:
    """The four production figures (rule 1: pictorial+technical pairs),
    built from ``results.json`` and the per-seed friction-ellipse detail in
    ``production_report.json``. Re-runnable from cached traces alone — no
    retraining — so a caption or colour tweak costs seconds, not hours.
    """
    report = production_report(out)
    from viz import rl_tv_figures
    write(out / "01-same-wheels-different-drivers.svg",
         rl_tv_figures.control_surfaces_figure(results, report))
    write(out / "02-yaw-moment-along-the-road.svg",
         rl_tv_figures.yaw_moment_figure(results))
    write(out / "03-did-it-stay-on-the-map.svg",
         rl_tv_figures.envelope_escape_figure(results, report))
    write(out / "04-seed-by-seed.svg",
         rl_tv_figures.seed_scorecard_figure(results))
    print("  production_report.json")
    print("  01-same-wheels-different-drivers.svg")
    print("  02-yaw-moment-along-the-road.svg")
    print("  03-did-it-stay-on-the-map.svg")
    print("  04-seed-by-seed.svg")


def aggregate(out: Path, seeds: range) -> int:
    """Collect every ``result_{variant}_seed{n}.json`` this session produced
    into one results.json — the seed loop rule 5 asks for, read back rather
    than reported per-process. Every seed's D6 verdict is kept individually
    (not just an aggregate pass rate): a single failing seed is information,
    not noise to average away."""
    results = {"pilot": False, "seeds": list(seeds),
              "envelope_penalty": ENVELOPE_PENALTY, "variants": {}}
    for variant in ("H", "E"):
        per_seed = []
        for seed in seeds:
            p = out / f"result_{variant}_seed{seed}.json"
            if not p.exists():
                print(f"  missing {p.name} — skipping seed {seed} for {variant}")
                continue
            per_seed.append(json.loads(p.read_text()))
        if not per_seed:
            print(f"  no completed seeds for variant {variant}")
            continue
        d6_pass = [e["d6_passed"] for e in per_seed]
        # The deployed (F61) representative trace for the comparison figure:
        # the median seed by finish distance, not the best — the best-of-N is
        # an extreme-value statistic and never a bound (F71's lesson).
        by_distance = sorted(per_seed, key=lambda e: e["distance_m"])
        rep = by_distance[len(by_distance) // 2]
        results["variants"][variant] = {
            "n_seeds": len(per_seed),
            "d6_pass_rate": float(np.mean(d6_pass)),
            "d6_passed_seeds": [e["seed"] for e in per_seed if e["d6_passed"]],
            "d6_failed_seeds": [e["seed"] for e in per_seed if not e["d6_passed"]],
            "peak_a_y_g_by_seed": {e["seed"]: e["peak_a_y_g"] for e in per_seed},
            "mean_utilisation_by_seed":
                {e["seed"]: e["mean_utilisation"] for e in per_seed},
            "finished_by_seed": {e["seed"]: e["finished"] for e in per_seed},
            "worst_slip_deg_by_seed":
                {e["seed"]: e["worst_slip_deg"] for e in per_seed},
            "envelope_occupancy_by_seed":
                {e["seed"]: e["evaluation"]["greedy"]["envelope_occupancy"]
                 for e in per_seed},
            "d6_failures_by_seed":
                {e["seed"]: e["d6_failures"] for e in per_seed},
            "representative_seed": rep["seed"],
            "d6_passed": rep["d6_passed"],
            "d6_failures": rep["d6_failures"],
            "peak_a_y_g": rep["peak_a_y_g"],
            "mean_utilisation": rep["mean_utilisation"],
            "finished": rep["finished"],
            "distance_m": rep["distance_m"],
            "s": rep["s"], "mz": rep["mz"],
        }
        print(f"  {variant}: {len(per_seed)} seed(s), D6 pass rate "
              f"{100*np.mean(d6_pass):.0f}%, representative seed "
              f"{rep['seed']} (median finish distance)")

    _load_classical_c(results)
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"\n  {(out / 'results.json').name}")
    build_final_figures(out, results)

    ok = all(v.get("d6_pass_rate", 0.0) > 0.0 for v in results["variants"].values())
    return 0 if ok else 1


def main() -> int:
    out = episode_dir(14)
    argv = sys.argv[1:]

    def _arg(flag, default=None):
        for a in argv:
            if a.startswith(flag + "="):
                return a.split("=", 1)[1]
        return default

    if "--figures-only" in argv:
        results = json.loads((out / "results.json").read_text())
        if results.get("pilot", True):
            figures(out)
        else:
            build_final_figures(out, results)
        return 0

    if "--aggregate" in argv:
        lo, hi = (int(x) for x in _arg("--seeds", "0,3").split(","))
        return aggregate(out, range(lo, hi))

    pilot = "--pilot" in argv
    eval_only = "--eval-only" in argv
    steps = PILOT_STEPS if pilot else PRODUCTION_STEPS
    variant_arg = _arg("--variant")
    seed = int(_arg("--seed", "0"))
    variants = [variant_arg] if variant_arg else ["H", "E"]

    print("Episode 14 — what the machine found instead")
    print(f"  {'PILOT' if pilot else 'PRODUCTION'} run, {steps:,} steps, "
          f"variant(s) {variants}, seed {seed}\n")

    results = {"pilot": pilot, "steps": steps, "seed": seed,
              "envelope_penalty": ENVELOPE_PENALTY, "variants": {}}
    for variant in variants:
        print(f"Variant {variant} ({VARIANTS[variant]['tv_mode']})")
        results["variants"][variant] = _run_one(out, variant, seed, steps,
                                                pilot, eval_only)

    _load_classical_c(results)

    # Single-process convenience path (pilot, or an ad hoc --variant=H run):
    # write a results.json usable by figures() directly. The multi-process
    # production path uses --aggregate instead, once every seed has landed
    # its own result_{variant}_seed{n}.json.
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"\n  {(out / 'results.json').name}")
    figures(out)

    if pilot:
        print("\n  PILOT COMPLETE. Do not read these numbers as a result —")
        print("  report wall-clock time and D6 status back before scaling to")
        print("  a production, multi-seed run (CLAUDE.md rule 5).")
    return 0 if all(results["variants"][v]["d6_passed"]
                    for v in results["variants"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
