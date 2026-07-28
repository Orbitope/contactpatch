"""D6 — is this training run evidence, or does it just look like evidence?

Every other diagnostic in this project checks physics. This one checks a *process*,
and it exists because building Season 3's first policy produced six separate
failures that all looked like success from the outside: training ran, losses
moved, curves went up and to the right, nothing crashed, and the result was
worthless.

The checks below are not hypothetical. Each one is a failure that actually
happened here, in order of discovery:

1. **The policy never updated.** Value loss started near 1600 (progress reward
   gives returns of order 40) so its gradient was 150x the policy's. A single
   ``clip_grad_norm_`` across both then scaled everything by 0.0067. Approximate
   KL sat at 0.0000 for 250k steps. → ``policy_is_actually_updating``
2. **The entropy bonus beat the policy gradient.** Entropy rose from 1.84 to 1.88
   over the same run: the policy was getting *more* random, not less.
   → ``exploration_is_not_growing``
3. **Exploration was 16x the useful action scale.** Holding the corner needs a
   normalised steering action of 0.037; the conventional initial standard
   deviation is 0.61. → ``exploration_matches_the_action_scale``
4. **The task was physically impossible.** The corner caps at 19.5 m/s and the
   environment started the car at 32. → ``the_task_is_completable``
5. **The critic stopped predicting.** Explained variance collapsed to zero
   mid-run while returns still looked healthy. → ``the_critic_predicts_returns``
6. **The deployed policy was a different driver from the trained one.** The
   stochastic policy completed every lap; its mean action crashed at a third
   distance. → ``greedy_and_stochastic_agree``

And the check the series plan asked for from the start, which is about physics
rather than optimisation:

7. **Where in tire state space did it spend its time?** A policy rewarded only
   for progress will happily operate where the tire model was never fitted, and
   the resulting lap time is a statement about our curve fit.
   → ``the_policy_stayed_inside_the_tire_model``

Run::

    python -m diagnostics.D6_training_health
"""

from __future__ import annotations

import math
import sys

import numpy as np

from diagnostics.common import Report
from physics import schema
from physics import track as T
from physics.rl_env import DrivingEnv, EnvConfig, STEER_RATE_MAX, rollout

#: A deployed policy below this finish rate has not learned the task, whatever
#: its training curves or its sampled performance say.
#:
#: This gate exists because Episode 9 was written up around a policy that
#: finished 88% of laps when its actions were sampled and 0% when they were not,
#: and the 88% was reported as the headline. It is not the headline. The
#: mean-action policy is the artefact a reader would use, and if that does not
#: work then nothing was learned — the sampled figure was measuring a quirk of
#: the exploration noise. See FINDINGS F61.
DEPLOY_FINISH_RATE = 0.8

#: A policy whose approximate KL is below this is not learning, whatever else the
#: curves say. PPO's own target is usually ~0.01; an order of magnitude under that
#: is a stalled update, not a careful one.
KL_FLOOR = 1e-4

#: Greedy and stochastic evaluation may differ, but not by this much. Beyond it
#: the policy depends on its own exploration noise and the thing you would deploy
#: is not the thing you trained.
GREEDY_GAP_FRACTION = 0.25

#: Our imposed slip bound, the same one every minimum-time solve enforces.
SLIP_BOUND_DEG = 12.0


def evaluate(model, cfg: EnvConfig, n: int = 8) -> dict:
    """Roll the policy out both ways: mean action, and sampled as trained."""
    import torch
    from physics.ppo import greedy_policy

    def sampled(obs):
        with torch.no_grad():
            d = model.distribution(torch.as_tensor(obs, dtype=torch.float32))
            return d.sample().numpy()

    out = {}
    for name, pol in (("greedy", greedy_policy(model)), ("stochastic", sampled)):
        runs = [rollout(DrivingEnv(cfg), pol, seed=s) for s in range(n)]
        out[name] = {
            "distance_m": float(np.mean([r["distance_m"] for r in runs])),
            "distance_std": float(np.std([r["distance_m"] for r in runs])),
            "finish_rate": float(np.mean([r["finished"] for r in runs])),
            "worst_slip_deg": float(np.max([r["worst_slip_deg"] for r in runs])),
            "slip_over_bound": float(np.mean(
                [r["slip_over_12deg_fraction"] for r in runs])),
            "envelope_occupancy": float(np.mean(
                [r["envelope_occupancy"] for r in runs])),
            "lap_time_s": float(np.mean([r["lap_time_s"] for r in runs
                                         if r["finished"]] or [float("nan")])),
        }
        out[name]["runs"] = runs
    return out


def run_checks(report: Report, history: list[dict], model, cfg: EnvConfig,
               train_cfg: dict) -> dict:
    p = cfg.params
    ev = evaluate(model, cfg)
    report.data["evaluation"] = {
        k: {kk: vv for kk, vv in v.items() if kk != "runs"}
        for k, v in ev.items()}
    report.data["train_config"] = train_cfg

    # -- did the optimiser do anything at all? ------------------------------
    report.section("Did the policy actually change?")
    kls = [h["approx_kl"] for h in history]
    median_kl = float(np.median(kls))
    report.add(
        "policy_is_actually_updating",
        median_kl > KL_FLOOR,
        f"median approximate KL per update is {median_kl:.5f} against a "
        f"{KL_FLOOR:g} floor. Below the floor the weights are barely moving and "
        "the run is a very expensive way to keep a random policy — which is what "
        "happened when the value gradient was 150x the policy's and one shared "
        "gradient clip scaled both by 0.0067.",
        value=median_kl,
    )
    ents = [h["entropy"] for h in history]
    grew = ents[-1] - ents[0]
    report.add(
        "exploration_is_not_growing",
        grew <= 0.0,
        f"policy entropy went {ents[0]:+.2f} -> {ents[-1]:+.2f} "
        f"({grew:+.2f}). A policy that is learning gets more decisive; rising "
        "entropy means the entropy bonus is beating the policy gradient, which "
        "on a Gaussian policy it will do indefinitely because entropy is "
        "unbounded above.",
        value=grew,
    )

    # -- is the search at the right scale? ----------------------------------
    report.section("Is the search at the scale of the problem?")
    std = np.exp(np.asarray(train_cfg["init_log_std"], dtype=float)
                 if not np.isscalar(train_cfg["init_log_std"])
                 else np.full(2, train_cfg["init_log_std"]))
    useful_steer = (p.wheelbase / T.CORNER_RADIUS) / 0.5 / STEER_RATE_MAX
    ratio = float(std[0] / useful_steer)
    report.add(
        "exploration_matches_the_action_scale",
        0.3 < ratio < 6.0,
        f"holding the {T.CORNER_RADIUS:.0f} m corner needs a normalised steering "
        f"action of about {useful_steer:.3f}; the policy searches with a standard "
        f"deviation of {std[0]:.3f}, a ratio of {ratio:.1f}x. Far above and the "
        "car saws the wheel off the road before it learns anything; far below "
        "and it never finds the behaviour at all.",
        value=ratio,
    )
    report.note(
        "the_two_action_dimensions_need_different_exploration",
        f"Steering rate and throttle have useful scales an order of magnitude "
        f"apart — {useful_steer:.3f} of authority against the whole [-1, 1] "
        f"interval — so a single exploration standard deviation cannot serve "
        f"both. With one value small enough for the steering, the policy never "
        f"sampled braking at all and sat at full throttle for half a million "
        f"steps. This run uses {np.round(std, 3).tolist()}.",
        value=std.tolist(),
    )

    # -- is the task winnable? ----------------------------------------------
    report.section("Is the task possible, and did it get solved?")
    from physics.double_track import DoubleTrackBackend
    v_corner = math.sqrt(DoubleTrackBackend(p).max_lateral_g(T.CORNER_RADIUS)
                         * schema.G * T.CORNER_RADIUS)
    report.add(
        "the_task_is_completable",
        cfg.entry_speed <= v_corner,
        f"the car makes {v_corner:.1f} m/s round this corner at the limit and "
        f"starts the episode at {cfg.entry_speed:.1f} m/s. Starting above the "
        "corner speed means the first thing the policy must discover is hard "
        "braking, seconds before any consequence, against an immediate reward "
        "for going faster — configured that way it never completed a single lap "
        "in 250k steps.",
        value={"corner_limit_ms": v_corner, "entry_ms": cfg.entry_speed},
    )
    offs = [h["off_track_rate"] for h in history]
    report.add(
        "the_off_track_rate_came_down",
        offs[-1] < 0.5 * max(offs[0], 1e-9) or offs[-1] < 0.1,
        f"episodes ending off the road went {offs[0]:.2f} -> {offs[-1]:.2f}. A "
        "rate stuck at 1.00 means every episode is a crash and the policy has "
        "never seen the behaviour it is supposed to be reinforcing.",
        value=offs[-1],
    )

    # -- is the critic doing its job? ---------------------------------------
    report.section("Is the critic predicting anything?")
    evs = [h["explained_variance"] for h in history]
    tail = float(np.median(evs[-max(len(evs) // 5, 1):]))
    report.add(
        "the_critic_predicts_returns",
        tail > 0.3,
        f"explained variance over the last fifth of training has a median of "
        f"{tail:+.2f}. At zero the critic is no better than predicting the mean, "
        "which makes every advantage estimate noise and the policy gradient a "
        "random walk.",
        value=tail,
    )

    # -- THE result: does the deployed policy work? -------------------------
    report.section("Does the policy you would actually deploy work?")
    g, st = ev["greedy"], ev["stochastic"]
    report.add(
        "the_deployed_policy_completes_the_task",
        g["finish_rate"] >= DEPLOY_FINISH_RATE,
        f"the mean-action policy — the one you would ship — finishes "
        f"{g['finish_rate']:.0%} of laps and covers {g['distance_m']:.0f} m. "
        f"Sampling its actions instead gives {st['finish_rate']:.0%} and "
        f"{st['distance_m']:.0f} m. **The deployed number is the result.** A run "
        f"whose sampled policy performs well and whose mean action does not has "
        f"not produced a driver; it has produced a policy whose competence lives "
        f"in its own exploration noise, and the sampled figure describes "
        f"something you cannot ship.",
        value={"greedy_finish": g["finish_rate"],
               "stochastic_finish": st["finish_rate"]},
    )
    best = max(g["distance_m"], st["distance_m"], 1e-9)
    gap = abs(g["distance_m"] - st["distance_m"]) / best
    report.add(
        "greedy_and_stochastic_agree",
        gap < GREEDY_GAP_FRACTION,
        f"mean-action rollouts reach {g['distance_m']:.0f} m and sampled "
        f"rollouts reach {st['distance_m']:.0f} m, a {100*gap:.0f}% gap. A large "
        "gap means the behaviour depends on the exploration noise itself, so the "
        "deterministic policy you would ship is a different driver from the one "
        "the training curves describe.",
        value=gap,
    )
    if gap >= GREEDY_GAP_FRACTION:
        report.note(
            "why_the_noise_matters_here",
            "The action-to-force map has a kink at zero — braking authority is "
            "12 kN against 4.5 kN of drive, because brakes really are stronger "
            "than engines. A Gaussian policy straddling that kink does not "
            "deliver the force of its mean action: E[f(a)] != f(E[a]), and the "
            "difference is always toward braking. At a mean throttle of zero the "
            "sampled policy delivers about 1.2 kN of net braking that the mean "
            "action does not have. **The policy did not learn to brake. It "
            "learned a mean action that brakes only when its own noise is added "
            "to it.**",
        )

    # -- and the physics question the series plan asked --------------------
    report.section("Did it stay inside the tire model?")
    # Judge the deployed policy here as well, for the same reason: the sampled
    # policy's envelope behaviour is not the behaviour you would ship. Both are
    # reported; the deployed one is what the check turns on.
    worst = max(g["worst_slip_deg"], st["worst_slip_deg"])
    frac = max(g["slip_over_bound"], st["slip_over_bound"])
    report.add(
        "the_policy_stayed_inside_the_tire_model",
        worst <= SLIP_BOUND_DEG,
        f"worst slip angle reached {worst:.1f} deg against our {SLIP_BOUND_DEG:.0f} "
        f"deg bound, with {100*frac:.1f}% of steps beyond it. Every minimum-time "
        "solve in Seasons 1 and 2 constrains this; the environment deliberately "
        "does not, so the policy is free to operate where the Magic Formula is "
        "extrapolating and the forces are arithmetic rather than measurement.",
        value={"worst_deg": worst, "fraction_beyond": frac},
    )
    report.add(
        "the_tire_file_s_own_load_range_was_respected",
        st["envelope_occupancy"] < 0.02,
        f"{100*st['envelope_occupancy']:.1f}% of steps left the tire file's own "
        "declared operating range. That bound is the file's, not ours, and "
        "outside it the model is not extrapolating from a fit — it has no fit.",
        value=st["envelope_occupancy"],
    )

    return {"evaluation": ev, "history": history}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    print("D6 is a diagnostic over a training run, so it needs one.\n"
          "Run it through experiments/ep09/run.py, which trains a policy and\n"
          "then calls D6 on the result:\n\n"
          "    python -m experiments.ep09.run\n")
    return 0


__all__ = ["run_checks", "evaluate", "KL_FLOOR", "GREEDY_GAP_FRACTION",
           "SLIP_BOUND_DEG", "DEPLOY_FINISH_RATE"]


if __name__ == "__main__":
    raise SystemExit(main())
