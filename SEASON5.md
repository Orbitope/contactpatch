# Season 5 — The automated race engineer

*Written 2026-07-30. Status: **plan, not yet ratified.** Root-level planning doc
per the TRACKS.md / POWER-REVIEW.md precedent. This is an extension beyond the
16-episode series plan in `docs/content-series-plan.md` (which is read-only
reference); adopting it is a deliberate scope decision, recorded here and in
FINDINGS when made.*

---

## 1. The question

Given a car's primary characteristics — power, weight, engine layout,
drivetrain — **what does it take to automate maximising its racing output, and
where does each gain actually come from?** Hardware tuning (setup), software
control (torque vectoring and friends), a learned driver, or the combination.
On one track, and across many.

Seasons 1–4 built every ingredient: the physics (S1–2), a learner and the
discipline to measure it honestly (S3), active control and a classical
benchmark for it (S4). Season 5 is the first season that uses them *together*,
and it is the "so what" of the series: everyone who has tuned a car in a game
has run this loop by hand. The season asks what happens when the loop runs
itself — and which parts of the racer's craft turn out to be search problems,
which turn out to be control problems, and which don't automate at all.

## 2. The architecture — who tunes what

Three different kinds of decision, three different tools. Confusing them is the
category error the season exists to untangle, so the plan states the division
up front:

| Decision | Timescale | Tool | Why |
|---|---|---|---|
| **Setup** (ballast, roll share, brake bias, diff character, TV targets) | once, in the garage | **Bayesian optimisation** | one-shot choice, no sequential structure, expensive noisy evaluations, and BO's posterior uncertainty is itself reportable ("the tuner knows what it doesn't know") |
| **Driving + active effectors** (steer, throttle, TV moment, active bias) | every 20 ms | **RL policy** (vs the classical controller as benchmark) | sequential decisions under uncertainty — the thing RL is actually for |
| **The pairing** (setup and controller co-adapt) | per experiment | **protocol, not algorithm** | F84's lesson generalised — see §5, trap 1 |

**The bridge between them — the season's central technique.** Episode 10
trained one policy conditioned on design parameters and then swept the
parameter through the *trained* policy. Scaled up: train **one policy
conditioned on (setup ⊕ car ⊕ track features)**, freeze it, and it becomes an
**amortised evaluator** — any setup vector can be lapped cheaply. BO then
searches over the conditioning inputs using the frozen policy as its objective.
Train once; tune everything.

**And the known hole in the bridge, stated before use.** A conditioned policy's
competence is not uniform over its conditioning space — Ep 10's own policy
could not drive the 40%-front car at all, and F98 scoped every fragility claim
"for this driver." An argmax through the amortised evaluator therefore measures
*setup × this policy's ability to drive it*, not setup alone. The season treats
this as a first-class measurement problem, not a footnote:

- every BO champion found through the amortised evaluator is **validated by a
  specialist retrain** at that setup (the gold standard the oracle is
  approximating);
- the gap between oracle-predicted and specialist-retrained lap time — **the
  amortisation gap** — is measured, mapped over the setup space, and reported
  as its own result. If the gap correlates with distance from the training
  distribution, that is the honest boundary of the technique and one of the
  most useful findings the season can produce.

## 3. What is actually tunable, at rung 2

**Setup dimensions (BO's search space), all existing or forced-open:**

| Knob | State | Caveat |
|---|---|---|
| `front_mass_fraction` (ballast) | exists | Season 2's axis; well understood |
| `roll_stiffness_front_share` | exists | **F31: authority ~1.5× noise floor** — either O8 gets resolved first or claims are rank/trend only, stated on every figure |
| `brake_bias` | exists (0.65) | dead knob until the brake caps are fixed — POWER-REVIEW Phase 0 audit gates this |
| Diff character (bias ratio → preload/ramp) | crude (1.0/1.5/∞) | forces **O3** open; a tuning season cannot tune a three-point knob |
| TV targets (`k_us`, `s_mz`, effectors) | exists | Ep 13's own sensitivity sweeps are the prior |
| Power level | via POWER-REVIEW D-A/D-B | a *given*, not a knob — it is part of "primary characteristics" |

**Explicitly not available, and the article says so every time:** camber, tire
pressures, aero balance (drag only, zero downforce), springs-as-grip, ride
height, gearing, elevation and kerbs. Real per-track tuning lives heavily in
aero and gearing, so at rung 2 **per-track setup differences arise from
corner-speed mix alone**. That is a real mechanism (hairpins are
traction-limited, sweepers lateral-limited) and it is the *only* mechanism we
model. Fidelity statement on every result.

**Track set:** 2–3 real circuits from the TUM database (TRACKS.md), chosen for
*distinct corner-speed distributions* — one fast-biased (Monza-like), one
tight-biased, one mixed (Spa-like) — plus the synthetic three-corner set from
POWER-REVIEW D-D as the controlled environment. The corner-speed histogram of
each circuit is a figure in its own right: it is the entire causal pathway by
which "track" enters this model, so the reader should see it.

## 4. The episode arc

Six episodes, ordered so the expensive and risky pieces come after the season
has already produced publishable results — the same risk structure the original
series used (Seasons 1–2 carried no training risk; here Eps 17–18 carry none).

### Ep 17 · What does tuning even buy? — BO meets the passive car
BO tunes the passive car's setup (ballast, roll share, brake bias, diff) on one
real circuit, driven by the **classical closed-loop driver** (Ep 13's, D11
protocol — no RL anywhere). Baselines: factory setup, and a hand-tuned
one-knob-at-a-time pass (the sim-racer's method) with matched evaluation
budget. Deliverables: what the optimum looks like, how big the basin is (BO's
posterior — is setup *touchy* or *forgiving*?), and how much of the gain each
knob carries (decomposed, F95's lesson). **This episode works even if
everything RL fails later.**

### Ep 18 · The compromise — one setup, many tracks
Per-circuit specialist setups vs one multi-track compromise setup (BO over the
sum/worst-case). The cost of compromise in seconds, *where* on each lap it is
paid (section metric), and which knob the tracks disagree about — the model's
version of "Monza wants less wing." Also the fragility question, re-using
Ep 11's machinery: is the specialist setup tuned closer to an edge (F98-style
failure-rate under grip variation) than the compromise? "The robust setup and
the fast setup are not the same setup" would be the season's first
transferable finding.

### Ep 19 · The learned driver meets real tracks
The RL infrastructure episode, and honest about being one (the method *is* the
story, which the series plan's own rule permits). Track-conditioned policy
(curvature preview already in the observation) trained across circuits;
specialist single-track policies as comparison. Generalisation gap, where it
lives (which corner types), and the training-budget rederivation a 10,000-step
lap forces. Gate: **O9's scripted-policy test and D6 pass on the new env
before any result is quoted.**

### Ep 20 · One policy, every garage — the amortised tuner
The bridge episode. Setup-conditioned policy; BO searches the conditioning
space through the frozen policy; champions validated by specialist retrains;
**the amortisation gap mapped and reported.** Head-to-head against Ep 17's
classical-driver BO on the same circuit: do the two tuners agree on where the
optimum is? (Two independent methods, same trend — the strongest internal
validation this project has, per Ep 10's RL-vs-OC precedent.)

### Ep 21 · Garage vs software — active and passive versions of the same effector
The cleanest question in the season. For each effector that exists in both
forms — brake bias (static vs policy-scheduled), differential (tuned passive
LSD vs active diff vs TV) — compare the **best passive-tuned** version against
the **active** version, each with setup co-tuned (§5 trap 1). What does
deciding in real time buy over deciding in the garage? Pre-registered
expectation from Ep 13/F82: less than the marketing implies on a clean lap,
more under disturbance — but that expectation was set at 4.5 kN and the
POWER-REVIEW curve may move it.

### Ep 22 · The automated race engineer — the season payoff
The full stack on a car the reader picks: primary characteristics fixed
(HP/weight/layout/drivetrain, a few archetypes), everything else automated —
BO setup, learned or classical driver, TV on/off. **Attribution decomposed**
(F95: no aggregate before decomposition): of the total gain from
factory-setup-passive to fully-automated, how much came from setup, from the
driver, from active control, and from their interactions? Then the honest
close, which the series has earned by now: the list of racer's-craft items
that did *not* automate — and the rung-2 list of what this model was never
allowed to see.

## 5. The traps, pre-registered (rule 9), with the findings that predict them

1. **Co-adaptation (F84 generalised).** The optimal setup depends on the
   driver; a setup tuned under the classical driver is not the RL driver's
   optimum. **Protocol: every controller comparison co-tunes** — max over
   setup for each controller separately, then compare champions. Comparing at
   a shared setup answers a different (and less interesting) question, and if
   used it is labelled as such.
2. **The optimiser exploits the model (F39/envelope, F95 for reward).** BO
   will find simulator artefacts exactly the way the min-time solver drove at
   30° slip and PPO found the reward's flat direction. **Every BO evaluation
   inherits the same gates as every other measurement**: envelope occupancy,
   `Fz` bounds, valid-lap criteria (D11), deployed-policy rule (D12). A
   champion that lives outside the envelope is discarded, not celebrated —
   rule 4 applies to optimisers too. O9's scripted-policy test must exist
   before Ep 19, since a reward hole found by BO is F95 at scale.
3. **The amortisation gap masquerading as a setup effect.** Handled
   structurally (§2): specialist-retrain validation, gap mapped and published.
4. **Noise burying the signal (rule 5, F66, F70).** BO's objective is a noisy
   lap under start jitter and seeds; per-evaluation budgets and the seed
   protocol are fixed *before* the search runs, and every claimed gain clears
   2× seed sd. Failure *rates* need the F70 sample sizes, not means'.
5. **Aggregates before decomposition (F95, the four-corrections lesson).**
   Multi-track objectives are sums over places the car is doing different
   things. Every multi-track result decomposes per-track and per-section
   before any average is quoted.
6. **Instrument resolution (POWER-REVIEW).** No Season 5 experiment runs until
   the power review lands: tuning gains measured below the instrument floor
   are the same artefact class the review exists to kill. Setup deltas are
   *smaller* than design deltas, so the floor matters *more* here, not less.

## 6. Dependency graph

```
POWER-REVIEW Phase 0–2  ──────────────┐   (instrument fixed; TV worth vs power known -- DONE)
TRACKS.md staging 1–4   ──────────────┤   (SampledTrack, round-trip test, closed loop,
                                      │    budget rederivation; CasADi Q resolved)
O3 diff formulation     ──────────────┤   (a tunable diff to tune)
O8 decision             ──────────────┤   (roll-share magnitudes: fix or trend-only)
O9 scripted-policy test ──────────────┤   (before any new RL result)
Ep 15 (uses Phase 1–2 outputs) ───────┤   (design-sensitivity baseline, TV-flattening -- DONE)
[Ep 16 Chrono cross-check] ───────────┤   (deprioritized, D13 -- see note below)
                                      ▼
        Ep 17 → Ep 18 (classical only, no training risk)
                  │
        Ep 19 → Ep 20 (RL on real tracks; amortised tuner)
                  │
        Ep 21 → Ep 22 (co-tuned comparisons; full stack)
```

**Revised, D13 (2026-07-30): Episode 16 is deprioritized, not required.**
This graph originally put it directly before Season 5 on the reasoning
below, unchanged as a statement of risk:

> A season quantifying 0.1–1% setup effects on an unvalidated model is the
> riskiest ordering available, and the Chrono check exists to buy exactly
> that trust.

That risk is now **accepted rather than mitigated**, by explicit user
decision — not pursuing publication-grade validation at this time, and RL
multi-track training (TRACKS.md's staging, above) is the actual priority.
Season 5 can proceed once its other prerequisites land, understanding that
every setup-delta claim it produces remains a rung-2 claim never checked
against an independent simulator. Revisit-able: if Ep 16 gets picked back
up later, this note — not the season's own findings — is what needs
revisiting first.

## 7. Cost, honestly

- **Eps 17–18: cheap.** Closed-loop laps at ~15 min per configuration set; BO
  at a few hundred evaluations per search is hours, not days. No training.
- **Ep 19: the big spend.** Real-circuit laps are ~10× more steps; even at the
  batched env's 29× training speedup, multi-track × ≥3 seeds is
  multi-overnight. Budget rederived from a pilot before the production run
  (Ep 14's pilot-first pattern, which caught three defects early).
- **Ep 20: one large conditioned training run + retrain validations** (each
  validation is an Ep-19-scale specialist, so the validation *budget* — how
  many champions get retrained — is a pre-registered choice, not improvised).
- **Eps 21–22: mostly re-evaluation** of trained artefacts plus BO searches;
  bounded by how many co-tuning cells §5-trap-1 demands. The cell count is the
  thing to watch — co-tuning is quadratic in carelessness.

## 8. What Season 5 cannot claim

Rung 2 throughout (rule 15): ~5% of a real car's understeer, no aero, no
camber, no thermal tire, flat tracks. Every "the automated engineer found X"
is a claim about **this model's** setup landscape; trend direction and rank
ordering are the exports (rule 6), and the Chrono check covers Season 2's
findings, not these. The season's honest thesis is not "here is your car's
optimal setup" — it is **"here is what kind of problem race engineering is:
which parts are search, which parts are control, and what it costs to know."**
That claim survives rung 2, and it is the one worth making.
