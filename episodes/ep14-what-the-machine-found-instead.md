# What the machine found instead

*Contact Patch, Episode 14. Season 4: Torque vectoring.*

---

## The question

Episode 13 built the classical answer to torque vectoring and it worked. It is
also, provably, a **choice**: a reference model tells the controller what the
car should be doing, and every newton-metre it produces serves that
instruction. Change one coefficient — ask for a pointier car — and the answer
changes.

So: give a learner the same four wheels, the same physics, the same stopwatch,
and **no reference model at all**. Don't tell it what the car should be doing.

**Does it agree with us?**

## Three ways to decide

| | Who decides *how much* to rotate | Who decides *which wheels pay* |
|---|---|---|
| **C** (Episode 13) | reference model + PID → a yaw moment `Mz` | QP allocator |
| **H** (hybrid) | **an RL policy** outputs `Mz` | **the same QP allocator** |
| **E** (end-to-end) | **an RL policy** — no `Mz` exists | **nobody** |

H is the smallest possible change from C: swap the hand-built upper layer for a
learned one and keep the lower layer bit-for-bit identical. Any difference is
attributable to the upper layer alone.

E deletes the allocator. Four learned numbers per step, scaled by each wheel's
own grip-based capacity, and nothing arbitrates between them but training.

Three seeds each, 5,000,000 steps, `envelope_penalty=0.5` — the same soft cost
for leaving the ±12° tire fit that Episode 10's protocol uses. Every number
below is the **deployed** policy: the mean action, not a sampled one.

## The answer: yes, and it costs you something specific

**All six policies drive the corner.** Full 393 m, 100% finish rate, every one
of them inside the ±12° region the tire model was actually fitted over — worst
case 11.5°.

![The same wheels, three different decision-makers](../experiments/ep14/out/01-same-wheels-different-drivers.svg)

So the headline is not "RL fails" and not "RL wins." Both formulations learn to
drive the corner at the limit without ever being told what a yaw moment is for.
The interesting result is *where they differ*, and it is sharper than expected.

### Same grip, twice the tire

| | H (allocator kept) | E (allocator deleted) | separation |
|---|---|---|---|
| Peak lateral acceleration | 0.915 ± 0.059 g | 0.976 ± 0.028 g | 1.3× seed sd — **not a finding** |
| Mean tire utilisation | **0.357 ± 0.087** | **0.701 ± 0.130** | 3.1× seed sd — **reportable** |

All `[MEASURED]`, 3 seeds each, deployed policy. This project's own rule is that
a trend smaller than twice the seed standard deviation is not a finding
(CLAUDE.md rule 5), and these two land on opposite sides of it.

**The two variants reach the same grip.** The 0.06 g between them is inside seed
noise and is reported as "no measurable difference," not as a small one.

**They pay very differently for it.** E spends roughly **twice** the
friction-ellipse utilisation — how much of each tire's available grip is being
used at once — to achieve the same lateral acceleration. The three H seeds
(0.27, 0.35, 0.45) and the three E seeds (0.55, 0.77, 0.78) do not overlap.

That is the QP allocator's objective, visible in the result. Its whole job is to
meet the demanded force and moment *while minimising tire workload* — spreading
the load so no tire is asked for a much larger share of what it has left than
its neighbours. H inherits that for free, because its lower layer is that
optimiser. E had to discover it, and didn't.

**So the learned upper layer is fine, and the hand-designed lower layer is not
free.** A policy can work out how much to rotate the car without a reference
model. Working out which wheels should pay for it — the convex problem with a
unique answer — is the part end-to-end learning did not rediscover in five
million steps.

### The learners are far more aggressive than the engineers

![Yaw moment along the road](../experiments/ep14/out/02-yaw-moment-along-the-road.svg)

Realized yaw moment, computed identically for all three from each trajectory's
own logged per-wheel forces:

| | median | 90th percentile | peak |
|---|---|---|---|
| **C** classical (delivered) | 11 N·m | 376 N·m | 995 N·m |
| **H** hybrid | 11 N·m | 1,477 N·m | 4,355 N·m |
| **E** end-to-end | 48 N·m | 1,393 N·m | 3,219 N·m |

All `[MEASURED]`, representative seed per variant.

Most of the time all three do almost nothing — the medians are tiny. But **when
the learners act, they act about four times harder than the classical
controller does.** The reference-model-plus-PID architecture is conservative by
construction: it asks for the moment that would make a real, saturating car
behave like a linear equation, and that demand is small. Neither learner was
told to want that, and neither chose it.

This is the "difference map between control surfaces" the research plan asked
for, and it points the same direction published work is said to report: the
best behaviour involves *deviating* from neutral yaw-rate tracking, which a
linear reference model structurally cannot express. Our version of that claim is
a comparison of two control surfaces on one corner, not a lap-time optimisation,
so it is corroboration in direction only.

### Did it stay on the map?

![Did it stay on the map?](../experiments/ep14/out/03-did-it-stay-on-the-map.svg)

Every seed's friction circles at the exact step it reached its own worst slip
angle. All six deployed policies are inside the ring.

![Seed by seed](../experiments/ep14/out/04-seed-by-seed.svg)

D6 — the training-health battery — passes 2 of 3 H seeds and 1 of 3 E seeds.
The three remaining failures are **training-process** checks, not driving ones:
one weak critic, two runs whose exploration entropy rose instead of falling. No
seed fails an envelope check or a deployment check.

## The part where this episode was wrong, and how

The first version of this article said the opposite. It reported that neither
variant reliably converges, that three seeds could not complete the corner, and
that deleting the allocator invited a tire-model exploit. It was published, and
it was wrong.

**Three measurement defects, none of them about reinforcement learning:**

1. **We kept the last checkpoint instead of the best one.** Training returned
   whatever weights the policy held after its final update. Re-reading the six
   training histories, every single seed had already driven the full corner
   inside the tire fit and been trained past it — one of them was clean for 463
   consecutive updates. The best checkpoints turned out to sit at 15%, 44%, 46%,
   61%, 77% and 100% of training. There is no late point where these runs are
   reliably good, which is exactly why keeping the end produced a false
   negative. (FINDINGS F93)

2. **The gate was not reproducible.** D6 sampled its stochastic rollouts from an
   unseeded global RNG. The same weights evaluated three times gave worst slip
   angles of 11.27°, 12.12° and 11.74° — straddling the 12° bound, so a policy
   passed or failed on the draw. (FINDINGS F94)

3. **The gate contradicted its own rule.** The envelope check took the worse of
   the deployed and sampled policies, while the comment directly above it — and
   this project's own stated invariant — said the deployed number was what it
   turned on. Because the exploration scale never anneals, those differ by
   several degrees on identical weights. (FINDINGS F94, decision D12)

Fixing the first turned "3 of 6 could not finish" into "6 of 6 finish." Fixing
the third turned "3 of 6 stayed inside the tire fit" into "6 of 6." **That
second change moves a headline in the flattering direction, which is why it is
recorded as an explicit protocol decision rather than a bug fix**, and why the
sampled figure is now printed alongside the deployed one on every line.

The uncomfortable part is that the wrong version was *coherent*. It had six
seeds, real numbers, a consistent story about end-to-end action spaces being
riskier, and a mechanism that sounded right. Nothing about reading it would tell
you it was measuring the optimiser's stopping point rather than the policy.

## What this can't tell you

**Fidelity: rung 2** (CLAUDE.md rule 15). Double-track model, no roll camber, no
roll steer, no compliance steer. We reproduce roughly 5% of a real car's
understeer gradient. Trends and orderings, never magnitudes.

**Four independently commanded wheel forces is a four-motor electric car**, not
RV-1's rear-drive combustion driveline.

**H and E are their own drivers; C is not.** The classical car is driven by the
hand-built closed-loop driver from Episode 13, whose preview time moves Episode
13's own headline by more than the controller is worth (F84). The realized-`Mz`
comparison sidesteps the worst of this — it is a control-surface comparison
computed identically for all three, not a lap-time race — but the three
trajectories are not identical and the utilisation comparison between H and E is
the cleaner one, because those two share everything except the allocator.

**One corner, three seeds.** Rule 5's minimum, not its preference of five. The
utilisation gap clears the bar by 3.1×; the grip difference does not clear it at
all and is reported as no difference.

**Training budget was roughly 2× oversized** — the median seed peaked at ~45% of
5,000,000 steps. That is only knowable because we now checkpoint.

## What it means

The engineers split the problem in two: one layer decides how much to rotate,
another decides which wheels pay. Twenty years of practice says that split is
the right one.

A learner given no reference model reproduces the first half readily — both
variants learned how much rotation to ask for, and both ask for far more of it
than the classical controller ever does. Given the second half for free, it
uses it. Denied it, it still drives the corner just as fast, and spends twice
the tire doing it.

Which is a more specific answer than "does it agree with us." It agrees about
the goal and disagrees about the aggression, and the piece of the classical
architecture it could not replace from scratch is the one that was never a
judgement call in the first place — the convex problem with a unique answer.

---

## Reproducing this

```bash
python -m experiments.ep14.run --pilot                 # ~5 min, validates the pipeline
python -m experiments.ep14.run --variant=H --seed=0    # repeat for seed=1,2 and variant=E
python -m experiments.ep14.run --aggregate             # collects the 6 runs, builds figures
python -m experiments.ep14.run --figures-only          # redraw from cached results
```

One `(variant, seed)` per process so the six run in parallel. Measured cost on
an 11-core machine: **H ≈ 4.3 CPU-hours per seed, E ≈ 2.5** — of which only
~1.2 h is physics; the rest is the PPO update loop. The environment runs at
1,184 steps/s for H and 2,491 for E, and H is slower despite a *smaller* action
space because it solves the QP allocator every step.

**New this episode.** `PPOConfig.eval_every` scores the deployed policy on
held-out seeds during training and keeps the best checkpoint;
`PPOConfig.entropy_anneal` decays the entropy bonus. Both default off, so every
Season 3 result is reproduced bit-for-bit by the path that produced it, and
`tests/test_ppo.py` — twelve tests for a module that previously had none — pins
that, including that switching evaluation on does not perturb the run it
watches.

**Still open.** Two seeds fail `exploration_is_not_growing`: annealing the
entropy coefficient to zero helped only marginally, so the policy gradient
itself is not sharpening the exploration scale. And Season 3 (Episodes 9–11) was
gated by the same unreproducible D6 and kept the same last checkpoints, so
**those results are likely understated too.** Recorded, not yet re-run.
