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
"""

from __future__ import annotations

import json
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

VARIANTS = {
    "H": {"tv_mode": "hybrid", "init_log_std": (-2.5, -1.0, -1.5)},
    "E": {"tv_mode": "end_to_end",
          "init_log_std": (-2.5, -1.5, -1.5, -1.5, -1.5)},
}


def _env_config(variant: str) -> EnvConfig:
    return EnvConfig(tv_mode=VARIANTS[variant]["tv_mode"],
                     envelope_penalty=ENVELOPE_PENALTY)


def _policy_from(out: Path, variant: str, cfg: EnvConfig):
    probe = DrivingEnv(cfg)
    train_cfg = json.loads((out / f"train_config_{variant}.json").read_text())
    model = ActorCritic(probe.obs_dim, probe.act_dim, train_cfg["hidden"],
                        train_cfg["init_log_std"])
    model.load_state_dict(torch.load(out / f"policy_{variant}.pt"))
    return model, train_cfg


def train_variant(out: Path, variant: str, steps: int) -> dict:
    cfg = _env_config(variant)
    ppo_cfg = PPOConfig(total_steps=steps, n_envs=8, rollout_steps=512,
                        epochs=10, init_log_std=VARIANTS[variant]["init_log_std"],
                        seed=SEED)
    print(f"  variant {variant}: {steps:,} steps, act_dim="
          f"{DrivingEnv(cfg).act_dim}, envelope_penalty={ENVELOPE_PENALTY:g}")
    t0 = time.time()
    res = train(lambda i: DrivingEnv(
        EnvConfig(tv_mode=VARIANTS[variant]["tv_mode"], start_jitter_m=10.0,
                  envelope_penalty=ENVELOPE_PENALTY), seed=i), ppo_cfg)
    wall_s = time.time() - t0
    print(f"    trained in {wall_s:.0f}s ({len(res['history'])} updates)")
    torch.save(res["model"].state_dict(), out / f"policy_{variant}.pt")
    (out / f"train_config_{variant}.json").write_text(
        json.dumps(res["config"], indent=2) + "\n")
    (out / f"history_{variant}.json").write_text(
        json.dumps(res["history"], indent=2) + "\n")
    return {**res, "wall_s": wall_s}


def evaluate_variant(out: Path, variant: str, model, cfg: EnvConfig,
                     history: list, train_cfg: dict) -> dict:
    report = Report(
        f"D6-ep14-{variant}", f"Episode 14 variant {variant} — training health",
        "The same ten Season 3 checks, plus the exploration-scale check this "
        "episode's larger action space adds.")
    payload = D6.run_checks(report, history, model, cfg, train_cfg)
    ev = payload["evaluation"]
    md = report.write_markdown(
        command=f"python -m experiments.ep14.run  # variant {variant}")
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


def figures(out: Path) -> None:
    from viz import rl_tv_figures
    results = json.loads((out / "results.json").read_text())
    write(out / "01-pilot-sanity.svg", rl_tv_figures.pilot_sanity_figure(results))


def main() -> int:
    from physics import schema

    out = episode_dir(14)
    argv = sys.argv[1:]
    if "--figures-only" in argv:
        figures(out)
        return 0

    pilot = "--pilot" in argv
    eval_only = "--eval-only" in argv
    steps = PILOT_STEPS if pilot else PRODUCTION_STEPS

    print("Episode 14 — what the machine found instead")
    print(f"  {'PILOT' if pilot else 'PRODUCTION'} run, {steps:,} steps per "
          f"variant, seed {SEED}\n")

    results = {"pilot": pilot, "steps": steps, "seed": SEED,
              "envelope_penalty": ENVELOPE_PENALTY, "variants": {}}
    for variant in ("H", "E"):
        print(f"Variant {variant} ({VARIANTS[variant]['tv_mode']})")
        cfg = _env_config(variant)
        if eval_only:
            model, train_cfg = _policy_from(out, variant, cfg)
            history = json.loads((out / f"history_{variant}.json").read_text())
            wall_s = None
            print(f"  reusing cached policy_{variant}.pt — no training")
        else:
            res = train_variant(out, variant, steps)
            model, history, train_cfg, wall_s = (
                res["model"], res["history"], res["config"], res["wall_s"])

        ev = evaluate_variant(out, variant, model, cfg, history, train_cfg)
        tr = ev.pop("deployed_trace")
        mz = realized_mz(tr, schema.RV_1)
        results["variants"][variant] = {
            **ev,
            "wall_s": wall_s,
            "peak_a_y_g": float(np.max(np.abs(tr["a_y"])) / schema.G),
            "mean_utilisation": float(np.mean(tr["utilisation_max"])),
            "worst_slip_deg": float(np.max(tr["alpha_max_deg"])),
            "finished": bool(tr["finished"]),
            "distance_m": float(tr["distance_m"]),
            # Small enough (one pilot rollout, a few hundred steps) to store
            # inline rather than in a side-car npz, so the sanity figure reads
            # everything from one results.json like classical C already does.
            "s": tr["s"].tolist(),
            "mz": mz.tolist(),
        }
        np.savez(out / f"trace_{variant}.npz",
                s=tr["s"], mz=mz, a_y=tr["a_y"],
                utilisation_max=tr["utilisation_max"],
                **{f"fx_{c}": tr[f"fx_{c}"] for c in CORNERS},
                **{f"fy_{c}": tr[f"fy_{c}"] for c in CORNERS})
        print(f"  peak {results['variants'][variant]['peak_a_y_g']:.3f} g, "
              f"mean utilisation {results['variants'][variant]['mean_utilisation']:.2f}, "
              f"finished={results['variants'][variant]['finished']}\n")

    # Classical C, reused from Episode 13 — not retrained, not re-evaluated.
    # If it is missing, the pilot still reports on H and E alone; the
    # comparison figure just has two lines instead of three.
    ep13 = episode_dir(13) / "results.json"
    if ep13.exists():
        c = json.loads(ep13.read_text())
        results["classical_c"] = {
            "source": "experiments/ep13/out/results.json",
            "s": c["traces"]["tv4"]["s"],
            "mz_demand": c["traces"]["tv4_control"]["mz_demand"],
            "mz_delivered": c["traces"]["tv4_control"]["mz_delivered"],
        }
        print("  classical C loaded from experiments/ep13/out/results.json")
    else:
        print("  classical C not found — run experiments/ep13/run.py first "
              "for the three-way comparison")

    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"\n  {(out / 'results.json').name}")
    figures(out)

    if pilot:
        print("\n  PILOT COMPLETE. Do not read these numbers as a result —")
        print("  report wall-clock time and D6 status back before scaling to")
        print("  a production, multi-seed run (CLAUDE.md rule 5).")
    return 0 if all(results["variants"][v]["d6_passed"] for v in ("H", "E")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
