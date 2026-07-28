"""Episode 9 — Teaching a car to drive, and watching it cheat.

Train a policy with nothing but a stopwatch, then ask D6 whether the result is
evidence. The interesting part of this episode turned out not to be the answer
but the number of ways the question can be silently mis-asked.

Run::

    python -m experiments.ep09.run
    python -m experiments.ep09.run --figures-only
    python -m experiments.ep09.run --quick        # a short run, for wiring checks
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import torch

from diagnostics.common import Report
from diagnostics import D6_training_health as D6
from experiments.common import episode_dir, write
from physics import schema
from physics import track as T
from physics.ppo import ActorCritic, PPOConfig, greedy_policy, train
from physics.rl_env import DrivingEnv, EnvConfig, rollout
from viz import learning_figures

TOTAL_STEPS = 1_200_000
SEED = 0


def _policy_from(path, cfg: EnvConfig):
    probe = DrivingEnv(cfg)
    train_cfg = json.loads((path.parent / "train_config.json").read_text())
    model = ActorCritic(probe.obs_dim, probe.act_dim, train_cfg["hidden"],
                        train_cfg["init_log_std"])
    model.load_state_dict(torch.load(path))
    return model, train_cfg


def figures(out) -> None:
    results = json.loads((out / "results.json").read_text())
    history = json.loads((out / "history.json").read_text())
    traces = dict(np.load(out / "traces.npz"))
    write(out / "01-what-it-learned.svg",
          learning_figures.learning_figure(results, history, traces))
    write(out / "02-the-noise-was-driving.svg",
          learning_figures.noise_figure(results, traces))
    write(out / "03-training-card.svg",
          learning_figures.training_card(results, history))


def main() -> int:
    out = episode_dir(9)
    if "--figures-only" in sys.argv:
        figures(out)
        return 0

    quick = "--quick" in sys.argv
    steps = 40_000 if quick else TOTAL_STEPS
    cfg = EnvConfig()
    ppo_cfg = PPOConfig(total_steps=steps, n_envs=8, rollout_steps=512,
                        epochs=10, seed=SEED)

    print("Episode 9 — Teaching a car to drive, and watching it cheat")
    print(f"  {steps:,} steps, entry {cfg.entry_speed:g} m/s, "
          f"reward = progress only, slip envelope NOT enforced\n")
    t0 = time.time()
    res = train(lambda i: DrivingEnv(EnvConfig(start_jitter_m=10.0), seed=i),
                ppo_cfg)
    print(f"  trained in {time.time()-t0:.0f}s "
          f"({len(res['history'])} updates)")
    torch.save(res["model"].state_dict(), out / "policy.pt")
    (out / "train_config.json").write_text(
        json.dumps(res["config"], indent=2) + "\n")
    (out / "history.json").write_text(json.dumps(res["history"], indent=2) + "\n")

    # --- D6: is this a result, or does it just look like one? --------------
    report = Report(
        "D6", "Training health",
        "Whether a reinforcement-learning run is evidence or an expensive way "
        "to keep a random policy. Every check here is a failure that happened "
        "while building this episode.")
    payload = D6.run_checks(report, res["history"], res["model"], cfg,
                            res["config"])
    ev = payload["evaluation"]

    g, st = ev["greedy"], ev["stochastic"]
    length = T.long_exit().length
    # State what happened, not what was hoped for. An earlier version of this
    # opened with "the policy learned to drive the corner" unconditionally, and
    # printed it above a run that had crashed on every single episode.
    if st["finish_rate"] >= 0.8:
        report.find(
            f"Trained on progress alone, the policy learned to drive the corner: "
            f"sampled rollouts cover {st['distance_m']:.0f} m of a "
            f"{length:.0f} m track and finish {st['finish_rate']:.0%} of laps.")
    else:
        report.find(
            f"**The policy has not learned the task.** Sampled rollouts reach "
            f"{st['distance_m']:.0f} m of a {length:.0f} m track and finish "
            f"{st['finish_rate']:.0%} of laps. Nothing below is a finding about "
            f"driving; it is a description of an unfinished training run.")

    gap = abs(g["distance_m"] - st["distance_m"]) / max(st["distance_m"], 1e-9)
    if gap >= D6.GREEDY_GAP_FRACTION:
        report.find(
            f"**The policy you would deploy is not the policy that was trained.** "
            f"Sampling its actions gives {st['distance_m']:.0f} m and a "
            f"{st['finish_rate']:.0%} finish rate; taking its mean action gives "
            f"{g['distance_m']:.0f} m and {g['finish_rate']:.0%}. The behaviour "
            f"depends on the exploration noise itself.")
    else:
        report.find(
            f"Sampled and mean-action rollouts agree to {100*gap:.0f}%, so the "
            f"policy does not depend on its own exploration noise to work.")

    # Read the CHECK's verdict rather than recomputing the question. An earlier
    # version tested `slip_over_bound > 0.005` here while the check tested
    # `worst_slip_deg <= 12`, and the two disagreed at the boundary: the summary
    # announced "it stayed inside the tire model" directly above a failing check
    # named the_policy_stayed_inside_the_tire_model. One source of truth.
    inside = next(c.passed for c in report.checks
                  if c.name == "the_policy_stayed_inside_the_tire_model")
    if not inside:
        report.find(
            f"**It went outside the tire model.** Worst slip angle "
            f"{st['worst_slip_deg']:.1f} deg against our "
            f"{D6.SLIP_BOUND_DEG:.0f} deg bound, with "
            f"{100*st['slip_over_bound']:.1f}% of steps beyond it. Nothing in the "
            f"environment stopped it — that constraint exists only inside the "
            f"optimal-control solver — so the forces out there are arithmetic "
            f"rather than measurement, and no lap time from this run is "
            f"comparable with Seasons 1 and 2.")
    else:
        report.find(
            f"It stayed inside the tire model unprompted: worst slip "
            f"{st['worst_slip_deg']:.1f} deg against our "
            f"{D6.SLIP_BOUND_DEG:.0f} deg bound, {100*st['slip_over_bound']:.1f}% "
            f"of steps beyond it, with nothing in the environment enforcing it.")

    results = {
        "total_steps": steps,
        "seed": SEED,
        "entry_speed_ms": cfg.entry_speed,
        "track_length_m": T.long_exit().length,
        "corner_limit_ms": float(np.sqrt(
            __import__("physics.double_track", fromlist=["x"])
            .DoubleTrackBackend(cfg.params).max_lateral_g(T.CORNER_RADIUS)
            * schema.G * T.CORNER_RADIUS)),
        "train_config": res["config"],
        "evaluation": {k: {kk: vv for kk, vv in v.items() if kk != "runs"}
                       for k, v in ev.items()},
        "d6_passed": report.ok,
        "d6_failures": [c.name for c in report.failures],
        "note": ("The slip envelope is deliberately NOT enforced in this "
                 "environment (see physics/rl_env.py). Lap times from outside "
                 "it are not comparable with Seasons 1-2 and are not quoted as "
                 "such."),
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    # traces for the figures: one rollout each way, plus the force-map curve
    tr = {}
    for name, pol in (("greedy", greedy_policy(res["model"])),
                      ("stochastic", _sampled(res["model"]))):
        r = rollout(DrivingEnv(cfg), pol, seed=0)
        for k in ("s", "n", "speed", "alpha_max_deg", "drive", "reward"):
            tr[f"{name}_{k}"] = r[k]
    np.savez(out / "traces.npz", **tr)

    md = report.write_markdown(command="python -m experiments.ep09.run")
    path = report.write()
    report.print_summary(verbose="-v" in sys.argv)
    print(f"\n  write-up {md}\n  report   {path}")
    figures(out)
    return 0 if report.ok else 1


def _sampled(model):
    def act(obs):
        with torch.no_grad():
            d = model.distribution(torch.as_tensor(obs, dtype=torch.float32))
            return d.sample().numpy()
    return act


if __name__ == "__main__":
    raise SystemExit(main())
