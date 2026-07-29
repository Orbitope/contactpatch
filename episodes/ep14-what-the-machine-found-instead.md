# What the machine found instead

*Contact Patch, Episode 14. Season 4: Torque vectoring.*

---

> ## ⚠️ THIS DRAFT IS RETRACTED AND IS BEING REWRITTEN
>
> Everything below rests on a result that was wrong. The six training runs it
> reports were never checkpoint-selected: `train()` returned whatever weights
> the policy held after its final update, and that is what was evaluated and
> published. Re-reading the training histories, **all six seeds had already
> driven the full 393 m inside the tire's own ±12° fit with a ~0% off-track
> rate** — and those policies were thrown away.
>
> So the conclusion this draft draws — "neither variant reliably converges",
> "removing the allocator removed the thing keeping the policy honest" — is a
> statement about model selection, not about reinforcement learning or torque
> vectoring.
>
> The fix (deployed-policy evaluation, best-checkpoint retention, entropy
> annealing) is in, and the six seeds are being re-run. See **FINDINGS F93**
> for the defect and the correction of record.

---

## The question

Episode 13 ended with a question, not a conclusion. We built the classical
answer to torque vectoring — a reference model and a PID decide how much
rotation the car should be making, a QP allocator decides which wheels pay for
it — and it worked. It is also, provably, a **choice**: we told the controller
what the car should be doing, and every newton-metre it produced was in
service of that instruction. Ask for a slightly pointier car and the answer
changes, weakly. Published work on this is said to say it changes more
strongly than that.

So: give a learner the same four wheels, the same physics, the same
stopwatch. Do not hand it a reference model. Do not tell it what the car
should be doing. Let it find out.

**Does it agree with us?**

This episode is the series' flagship for a specific reason: it is the one
place the payoff depends on a result we do not have yet. Either answer —
"it reinvented the allocator" or "it found something different" — is a real
result, and the discipline this episode has to hold to is not scripting which
one we wanted.

## Two variants, one physics

The research plan (`docs/vehicle-codesign-research-plan.md`, Phase 4b) draws
the comparison precisely:

| Variant | Upper layer | Lower layer |
|---|---|---|
| **C** (Episode 13) | Reference model + PID → `Mz` | QP allocator |
| **H** (hybrid) | RL policy outputs an `Mz` DEMAND | the SAME QP allocator |
| **E** (end-to-end) | RL policy outputs four wheel-force fractions | none |

**H is deliberately the smallest possible change from C.** Swap the reference
model and PID for a learned scalar; keep everything downstream — the same
`physics.torque_vectoring.Allocator`, the same friction-ellipse capacities —
bit for bit identical. If H disagrees with C, the disagreement belongs to the
upper layer alone, because the lower layer is literally the same code.

**E removes the allocator entirely.** Four raw numbers per step, scaled by
each wheel's own grip-based capacity, and nothing decides how they trade off
against each other except training. E asks whether four learned numbers
reinvent the allocator, beat it, or do neither.

Both route through the same hook Episode 13 built —
`DoubleTrackBackend.attach_torque_vectoring` — so plugging them in required no
changes to the backend at all, and `tv_mode="none"` reproduces every Season 3
result bit for bit. The environment now also logs lateral acceleration and
per-wheel friction-ellipse utilisation, a gap `HANDOFF.md` had flagged since
Episode 11: without it there was no way to check whether a torque-vectoring
result was measuring anything a saturated tire actually did.

## The experiment

Three seeds per variant, five million steps each — this project's own seed
discipline (rule 5) applied to a training run for the first time this season,
and it earned its keep immediately: the three seeds do not agree with each
other, which is itself information, not noise to average away.

`envelope_penalty=0.5`, the same value Episode 10's protocol uses — a soft
cost for operating outside the ±12° region the tire file was actually fitted
over, not a hard constraint. An unconstrained policy's optimum is to slide
(F62); this penalty is what stands between the training run and that
optimum, and part of what this episode checks is whether it is enough.

Every run gates on **D6**, this project's training-health battery, plus one
new check this episode's larger action space needed: that the policy explores
the new `Mz` or wheel-force dimensions at all, rather than collapsing to zero
or blowing past a sane range. And every number reported below is the
**deployed** policy — the mean action, not a sampled one (F61). Episode 9 was
once written around an 88% sampled finish rate whose deployed figure was 0%;
this episode does not repeat that.

## The result

![The same wheels, three different decision-makers](../experiments/ep14/out/01-same-wheels-different-drivers.svg)

**Neither variant passes cleanly.** H's D6 pass rate across its three seeds
is 0 out of 3. E's is 1 out of 3.

| Variant | Seed | D6 | Finished | Peak lateral g | Worst slip |
|---|---|---|---|---|---|
| H | 0 | FAILED — critic, tire model | Yes | 1.00 | 14.8° |
| H | 1 | FAILED — greedy/stochastic agree, tire model | Yes | 0.96 | 10.5° |
| H | 2 | FAILED — deployed policy, greedy/stochastic agree | No | 0.98 | 9.4° |
| E | 0 | FAILED — 6 checks | No | 1.01 | 13.5° |
| E | 1 | FAILED — 5 checks | No | 1.01 | 16.8° |
| E | 2 | **PASSED** | Yes | 0.98 | 8.8° |

All `[MEASURED]`, 5,000,000 steps/seed.

But the two variants fail in different ways, and the difference is the
finding.

![Yaw moment along the road](../experiments/ep14/out/02-yaw-moment-along-the-road.svg)

**H's three seeds cluster near the tire's own boundary.** Every one keeps its
worst slip angle under 15°, two of the three finish the whole corner, and the
D6 failures are the mild kind — an optimistic critic, or the greedy and
sampled policies disagreeing slightly with each other — not a policy that has
run off and done something the physics doesn't support. Constraining the
lower layer to the same allocator C uses appears to constrain the upper
layer's mistakes along with it.

**E's three seeds split sharply.** One (seed 2) trains cleanly, passes every
D6 check, and finishes the corner at 8.8° worst slip. The other two find a
way to operate substantially outside the tire's own fit — 13.5° and 16.8°, up
to a quarter of the whole run spent past the ±12° bound — and neither
finishes. This is **the same tire-model exploit Episode 9 first found**
(F53/F56), reappearing under the identical envelope penalty this episode and
Episode 10 both use. Removing the allocator did not just remove a piece of
hand-engineering; on two seeds out of three, it removed the thing that had
been keeping the policy honest.

## Did it stay on the map?

![Did it stay on the map?](../experiments/ep14/out/03-did-it-stay-on-the-map.svg)

Six seeds, six friction-circle snapshots, each taken at the exact step that
produced that seed's own worst slip angle — not a different, cherry-picked
moment. H's circles are all comfortably inside their rings. Two of E's three
arrows reach or pass theirs.

![Seed by seed](../experiments/ep14/out/04-seed-by-seed.svg)

Stated as bars rather than a pass rate: H's worst slip angles run 9.4–14.8°,
none by much. E's run 8.8°, 13.5°, 16.8° — one seed comfortably inside, two
substantially outside, and no seed in between. Three seeds is this project's
own minimum (rule 5); five would be preferred, and a fourth or fifth E seed
landing on either side of that split is the obvious next check.

## The seed that would have been picked, and wasn't

This episode's own rule about representative seeds (F71: pick the median by
finish distance, never the best of N) earns its keep here concretely. E's
three finish distances are 131 m, 353 m and 393 m. The median is 353 m — seed
1, one of the two exploit seeds. The one clean pass, seed 2, finishes the
full 393 m and would be the seed any best-of-three selection would show
instead. Every E number and figure in this episode marked "representative" is
seed 1's, not seed 2's, on purpose. A different selection rule would have told
a flatly more flattering, and less honest, story.

## What this can't tell you

**Fidelity: rung 2** (CLAUDE.md rule 15). Same double-track model, same
understeer gap, same missing roll-camber and roll-steer terms as every other
episode this season. Nothing here is a claim about a real car's RL torque
vectoring — it is a claim about what this training budget, this reward, and
this envelope penalty produced on this model.

**Not a lap-time race.** No absolute lap time was compared across C, H and E
— rule 6 forbids it, and no lap-time race was run in the first place. This
episode compares *control-surface behaviour*: realized yaw moment against
distance, and whether the policy stayed inside the tire it was trained on.

**Not "RL cannot do torque vectoring."** One E seed in three converges
cleanly and passes every check. The finding is that the exploit is more
common without an allocator constraining the action space, at this budget —
not that it is inevitable.

**Training budget, reward, and envelope penalty are all still open.** Longer
training, more seeds, or a stronger envelope penalty could all move these
numbers; none of the three was swept here.

## What this is

This is not "RL beat the engineers" or "RL reinvented the engineers' answer."
It is the more useful, less quotable result: at this budget, **neither
variant converges reliably**, and the two fail in informative, different
ways. H — the variant with the allocator still standing between the policy
and the wheels — keeps its mistakes small and physical. E — the variant with
nothing standing between them — mostly finds a way to ask the tire model for
something it was never fitted to give, the same failure mode this project
documented three seasons ago, now recurring in a harder, four-dimensional
action space under the same guardrail that was supposed to prevent it.

Twenty years of engineering consensus put an allocator between the
decision and the wheels. On this evidence, in this training regime, removing
it did not make the learner smarter about the tires. It made the tires the
first thing it found a way to cheat.

---

## Reproducing this

```bash
python -m experiments.ep14.run --pilot                      # ~5 minutes, validates the pipeline
python -m experiments.ep14.run --variant=H --seed=0         # ~3.8 hours; repeat for seed=1,2 and variant=E
python -m experiments.ep14.run --aggregate                  # collects the 6 runs, builds the figures
python -m experiments.ep14.run --figures-only                # redraws from cached results, no retraining
```

Production is one (variant, seed) per process so the six seeds run in
parallel across cores rather than serially — sequentially this would cost the
better part of two days. Wall-clock, this machine: H averaged 3.9 hours/seed,
E averaged 1.98 hours/seed, both close to the pilot's linear extrapolation
(F91).

**New code this episode.** `EnvConfig.tv_mode` in `physics/rl_env.py` —
`"none"` (every Season 3 result, byte-for-bit unchanged), `"hybrid"` (variant
H), `"end_to_end"` (variant E) — plus one new D6 check
(`exploration_covers_the_torque_vectoring_action`) and per-step logging of
lateral acceleration and per-corner force. All additive: 18 pre-existing
`test_rl_env.py` tests pass unchanged, plus a new seal test and adapter tests
that check the hybrid and end-to-end action paths against a fresh, independent
`Allocator.allocate` call rather than the training code's own idea of what it
did (rule 11).

**On the friction-circle figure.** The instant it snapshots is
`argmax(alpha_max_deg)` — the exact step `worst_slip_deg` is computed from,
not the step of peak friction-ellipse utilisation, which need not be the same
moment. An earlier draft used the wrong one and briefly showed a smaller
angle on the figure than the number quoted beside it. Caught before
publishing; see FINDINGS F92.
