# RL test plan — getting a policy to the limit

Prioritised, pre-registered, with success criteria fixed **before** each run.
Written after four research passes (FINDINGS F105, plus the engineering and
limit-driving surveys) and five failed or partial runs (F104, F106–F111).

Read `CURRICULUM.md` for how the training itself works. This file is only
about **what gets tested, in what order, and how we decide it worked.**

---

## The numbers that matter

**Primary: lap time.** No denominator, no definitional ambiguity, and it is
what racing actually is. Only defined for a rule-4-valid completed lap.

**Secondary: cornering grip fraction, corners only.**

```
frac = mean over { s : v_limit(s) < 40 m/s } of  v_actual(s) / v_limit(s)
v_limit(s) = sqrt(a_lat_max / |kappa(s)|)
```

**The corners-only restriction is load-bearing and was a plan defect caught in
audit pass 1.** Three defensible definitions give **19.5% / 34.1% / 50.6% on
the identical lap**, because 67% of Spa has a cornering limit above what this
car can reach, so the naive whole-lap average is mostly a ratio to a speed
that is physically unattainable. Straights say nothing about how hard a car is
being driven.

**Current baseline (`curr_ct2_policy`, one seed, rule-4 valid):**

| | |
|---|---|
| lap time | **537 s** (13.1 m/s mean) |
| cornering grip fraction | **50.6%** |
| mean slip | 0.3° (tyres peak 8–12°) |
| completion | 48/48 probes |

**No published system reports the grip-fraction metric**, so there is no
external target for it — `[MEASURED]`, no implied comparison. Lap time has an
internal reference (Phase 0) but no external one either: rule 6 forbids
comparing our seconds to anyone else's.

## Is "at the limit" even compatible with rule 4? — yes, measured

The tyre peaks and the bound nearly coincide, so this had to be checked
before the plan could be trusted (audit pass 2, defect D).

| Fz (N) | peak \|Fy\| at | Fy at 12° as % of peak |
|---|---|---|
| 2000 | 9.7° | 99.5% |
| 4000 | **10.3°** | 99.7% |
| 6000 | 11.7° | 100.0% |

**Rule 4's 12° bound sits ~1.7° above the peak-force slip angle at typical
load.** A policy can therefore reach maximum cornering force and remain
inside the bound — "drive at the limit" and "stay rule-4 valid" are
compatible, and Phase 4's targets are not self-contradictory.

This is the same construction TRI use deliberately (*thresholds "slightly
larger than the slip angles needed to achieve maximum cornering force"*),
arrived at independently here for tyre-model-validity reasons.

**Caveat:** at 6,000 N the peak moves to 11.7°, leaving 0.3°. Under heavy
load transfer the margin nearly vanishes, so rule-4 violations at high load
are expected to be the binding failure and should be reported per-wheel, not
just as a lap maximum.

## Gates every run must pass to be reported at all

1. **Rule 4** — `sections_over_bound == 0` and `envelope_occupancy == 0`.
   `policy_eval.headline()` refuses to quote a distance otherwise. A faster
   invalid policy is not a result (F106).
2. **D6 critic health** — `explained_variance > 0.3` (F104).
3. **Deployed, not sampled** — every number from `policy_eval.py`, greedy
   policy, ≥24 probes (F61, D16).
4. **Scored at the configuration it was selected under** (F109).

A run failing 1–2 is reported as a **negative result with its cause**, not
discarded and not retried with a tweak.

---

## Priority list

Ordered by (evidence strength × cheapness) ÷ risk. Each phase states what it
changes, why, what would count as success, and what result would make us
**stop and rethink rather than proceed**.

### Phase 0 — Establish the target · minutes, no training

We do not know what a good lap time *is* on this car and circuit. The
classical driver laps cleanly at `v_max=12` and spins at 45; its fastest
**clean** lap has never been measured. Bisect `v_max` (and `grip_use`) to find
it, scored by `policy_eval`'s own rule-4 gate.

That number is the RL policy's target and the honest denominator for every
"how good is this" claim. It is **not** an external validation (rule 2) — it
is our own code, and a driver with a global speed plan the RL does not get.
State it that way wherever it is quoted.

- **Success:** a rule-4-valid classical lap time exists, with the `v_max` that
  produced it.
- **Stop and rethink:** if no `v_max` yields a *valid* clean lap, then rule 4
  and this vehicle model may be incompatible at speed, and every phase below
  is chasing a target that does not exist. That would be the single most
  important thing to find out, and it costs minutes.

### Phase 1 — Optimisation hygiene · zero extra simulation

Three changes, all "match published defaults". None is a hypothesis about
driving; all three are about whether the optimiser can learn anything at all.
Bundled because they interact only through the optimiser and testing them
separately costs 3× for a question none of them individually answers.

| change | from | to | evidence |
|---|---|---|---|
| `minibatches` | 4 (batch 65,536) | 32 (batch 8,192) | Sophy 1,024, Fuchs 4,096, Czechmanowski 1,024, TRI 256. Ours is 64× the largest. 8× more gradient steps on identical data. |
| observation normalisation | none | fixed z-score from known ranges | 6 of 7 surveyed systems normalise. Sophy: *"we standardized the inputs on the basis of the knowledge of the range of each feature scalar."* We know every bound. |
| `gae_lambda` | 0.95 (0.37 s) | 0.98 (0.8 s) | Sophy's n-step ablation is flat from n=5–9 and cliffs at n=1; 0.8 s lands on the flat part. |

**Measured, not assumed:** our observation is *not* dominated by curvature —
we already scale it ×40, and its SD (0.39) is the largest of any input.
**Speed has the smallest SD (0.0057)**, because the cap pins it. Normalisation
is therefore about the speed channel, not the curvature one, and Phase 2 is
what actually fixes it.

- **Success:** EV ≥ 0.9 sustained, and lap time improves ≥ 5% at equal budget
  with rule 4 intact.
- **Neutral:** lap time within ±5%. Keep the changes — they are free and match
  the field — and proceed. They were never expected to teach braking.
- **Stop and rethink:** EV drops below 0.3, or lap completion falls below 50%.
  That would mean our optimiser was accidentally load-bearing at its old
  settings and something is being masked.

### Phase 2 — Make speed observable · the measured defect

`speed_cap` pins speed to a 0.245–0.300 band. **The policy never experiences
varied speed, so it cannot learn a (speed, curvature) → deceleration map** —
the mapping has no training signal along its most important axis. This is our
own measurement, not from a paper, and it is the most specific defect found.

- Spawn speed sampled uniformly in `[0.3, 1.0] ×` the local corner limit,
  rather than a fixed `entry_speed`.
- Fuchs does this and states the reason in our terms: *"initialize the
  position of agents equally distributed over the racing track with an initial
  speed of 100 km/h... allows the agents to faster approach the maximal
  feasible segment speeds."* GT Sophy randomises start speed too.
- Removes the spawn/cap inconsistency noted on the lap figure (spawn 15.0 m/s
  ignores a 13.0 cap).

- **Success:** speed SD in the observation rises ≥ 5×, **and** cornering grip
  fraction ≥ 60% (from 50.6%), rule 4 intact.
- **Stop and rethink:** completion collapses below 50% — meaning spawning at
  speed is beyond the policy and it needs Phase 3 first.

### Phase 3 — Control rate · the largest structural gap

50 Hz → **10 Hz decisions, physics unchanged at 50 Hz**, **with γ reduced
0.995 → 0.99 in the same change** — audit pass 1 caught that leaving γ alone
gives a 20 s horizon at 10 Hz, double the longest published (Sophy 9.6 s,
TRI 10 s). γ=0.99 at 10 Hz is 10 s. The rate change and the γ change are one
edit, not two, because the horizon is the thing being held fixed.

Implemented via first-order hold
(linear interpolation of steering between decisions, as GT Sophy-vision does,
rather than zero-order — a 5-step steering jump is a real transient a Pacejka
model will respond to).

Every published full-size-car system runs 10–20 Hz. Sophy swept 5–60 Hz and
found *"no substantial performance gains from acting more frequently than
10 Hz."* At 50 Hz our exploration noise is resampled 5× more often, and a
Gaussian resampled that fast produces near-zero net displacement over the ~1 s
a brake application must persist — **the policy cannot sample a sustained
brake.** This also multiplies every horizon by 5 at unchanged γ and λ.

- **Success:** cornering grip fraction ≥ 70%, sustained braking events
  appear, defined as **≥ 0.5 s of continuous negative drive command that
  produces ≥ 3 m/s of actual speed reduction**, occurring before ≥ 3 distinct
  corners. Both halves matter: audit pass 2 found that "0.4 s of negative
  drive" alone is 4 samples at 10 Hz and could be satisfied by noise, and a
  brake command that does not slow the car is not braking. Rule 4 intact.
- **Stop and rethink:** if braking still does not appear at 10 Hz, exploration
  is not the constraint and the reward is — go to Phase 4 before anything else.

### Phase 4 — Reward form · fixed-magnitude → speed-scaled

Our penalties are the outlier: dense, permanently active, fixed weight. No
published limit-driving system has one.

| term | Sophy | Evans | ours | proposed |
|---|---|---|---|---|
| progress | 1 | — | 1 | 1 |
| tyre slip | **0.25**, and **0** on its fastest track | — | **6** | 0.25 · v · α_excess |
| off-course | 0.01 · v² | — | 5 fixed | 0.01 · v² |
| cross-track | **none** | 0.004 (vs velocity 0.04) | **2** | 0 |

TRI's formulation is the model to copy — `R_slip = q₂·v·(α_f,excess +
α_r,excess)` with **thresholds set slightly above the slip angle giving peak
cornering force**, i.e. calibrated to *permit* operation at the friction peak
and punish only excursions past it. That is exactly our rule-4 problem stated
as a reward.

- **Success:** lap time within 25% of Phase 0's classical reference, cornering
  grip fraction ≥ 80%, rule 4 intact, completion ≥ 90%.
- **Stop and rethink:** rule 4 breaks (any section over 12°). Then the slip
  threshold is mis-calibrated, not the weight — re-derive it from the tyre's
  own peak-force slip angle rather than adjusting the coefficient.

### Phase 5 — Only if Phases 1–4 leave us short

Each is a bigger commitment and changes what the series can claim.

- **5a. Mistake learning** (Sophy): reset at states ~2 s before each off-track.
  Cheap, and the published mechanism for corner-specific braking.
- **5b. Asymmetric action-rate cost** (TRI): free to release throttle and brake
  hard, penalised to stab and release. TRI explicitly exempts braking from
  their rate penalty — a symmetric one teaches the agent not to brake.
- **5c. TAL speed reference** from our own `SpeedProfile`. **Reaches ~90%
  completion where progress rewards reach ~50% on the F1TENTH benchmark.**
  Held back deliberately: it hands the policy a classical controller's answer,
  which changes the episode's claim from "it discovered this" to "it learned
  to imitate this". Worth doing, but as a stated comparison, not a rescue.
- **5d. Off-policy (SAC/TD3).** Fuchs: *"PPO required much more training data
  and suffered from premature convergences due to its state-independent
  exploration."* Every headline system is off-policy. This is a large rewrite
  and contradicts `physics/ppo.py`'s stated pedagogical purpose — raise it
  with the user before starting.

---

## Comparisons — fixed now, so no phase can pick a flattering baseline

Audit pass 2 found the plan did not say what each phase is measured against,
which would let any result be framed as an improvement after the fact.

**Every phase reports two deltas, both mandatory:**

1. **vs the frozen original** — `curr_ct2_policy`, 537 s, 50.6% cornering grip.
   This never changes, so the whole sequence is comparable end to end.
2. **vs the immediately preceding phase**, which is the marginal value of the
   change actually being tested.

A phase that improves on (2) but not (1) has undone earlier progress and must
say so. **Phases 2 and 3 change the training distribution and the control
rate, so lap times before and after are not naively comparable** — both must
be re-scored with `policy_eval.py` under the *new* configuration, and the old
policy re-scored there too rather than quoting its old number.

## Reporting protocol — identical for every phase

1. Run, scored by `policy_eval.py` at the checkpoint's own configuration.
2. **Report the pre-registered criteria verbatim**, including which were met
   and which were not. No post-hoc redefinition of success.
3. Add the grip-fraction and braking-event metrics to `policy_eval.py` so
   every run reports them automatically — never a one-off script (D16).
4. `FINDINGS.md` entry, numbered, with **Source** line and the negative result
   if it failed. `TRACKS.md` item. Commit.
5. **Then** proceed to the next phase — never run two phases without reporting
   the first.

## Rules carried in from prior failures

- **Replay-test any curriculum gate before it gets a training run**
  (`tests/test_curriculum_gate.py`). Four gate bugs reached full runs; all
  four were smoke-tested first.
- **Re-run the gate replay tests after Phase 3.** `CAP_ADAPT_UPDATES` and
  `CAP_MIN_UPDATES_BETWEEN` are expressed in *updates*; at 10 Hz an update
  spans 5× more simulated time, so the same update count is a different
  physical adaptation window. The existing tests assert in updates and would
  not catch that mismatch (audit pass 2, defect B).
- **Verify a new test fails against the old behaviour** before trusting it.
  One passed vacuously behind an `if len(...)` guard.
- **≥3 seeds before any of this is a trend** (rule 5). Everything measured so
  far is one seed, including F110.
- **Preserve prior artefacts** under distinct names; never overwrite.

---

## Season 5 recalibration — what the multi-track and TV research changed

Added after the fourth research pass. These do not affect Phases 0–4, which
are about one circuit. They change what Episode 19 and 21 can claim.

### The 17/7 split has no precedent, and a large gap is the *expected* result

**Almost nobody trains on more than one circuit.** The largest real-circuit
training sets found are **3 tracks** (Jaritz, ICRA 2018) and **4** (Siegert,
ETH 2026). The standard protocol is train-on-one, test-on-others.

**GT Sophy is a specialist.** Wurman et al. trained a version *per car-track
combination*; the "mixed-scenario training" in the abstract is opponent counts
and start positions, not circuits. Sony still require explicit training per
new track. **The best racing agent in the world does not generalise across
tracks and does not try to** — that is the framing for Episode 19, and it is
a more interesting story than a gap number.

**Calibration from general RL:** Cobbe et al. (CoinRun, 256M steps) close the
generalisation gap only past ~10,000 training levels; Procgen says the same.
**17 circuits is three orders of magnitude below that.** So:

> **Pre-registered expectation: the generalist will be substantially worse on
> held-out circuits. That is what the field predicts, and "we measured a gap
> with 17 environments" is not a finding.** The finding is the *shape* — which
> corner types it fails on, and whether the gap closes with more circuits.

The nearest quantitative analogue is drone racing (Green et al. 2026, 40
unseen tracks): **generalist 14.52% slower than per-track specialists, but the
specialists score 0% off their own track.** Pre-register against that shape.

### The trap: an under-trained specialist flatters the generalist

Wang et al. (ICRA 2025) report a generalist **beating** the specialist on 2 of
6 tracks at equal success. That should not happen if the specialists were
converged. **Budget the specialists as carefully as the generalist and report
their seed variance** — otherwise the gap measures our training budget, not
generalisation. This compounds rule 5: three seeds on the specialists is not
optional here, it is the whole comparison.

### Training-set composition matters more than its size

Two independent groups, same conclusion: **complex circuits generalise, simple
ones do not.** Formula RL — trained on complex Aalborg transfers to both
simple and complex held-outs; trained on simple Michigan **"did not finish the
unseen tracks."** Evans's survey — the MCO map produces the best
generalisation, all agents 100% on all test maps.

**Action: over-weight tight, complex circuits in the 17-track training set.**
The current stratified split takes 6 tight / 6 mixed / 5 fast, which is
defensible, but the literature predicts a fast-biased training set fails on
tight held-outs — worth stating as a directional prediction we can check.

Also: Toromanoff (CARLA) went from **2.4% → 58.4%** on an unseen town moving
from 1 to 3 training towns. Most of the benefit may arrive early; a 3-track
generalist is worth running before the 17-track one.

### Torque vectoring — the destination, recalibrated

- **No RL torque-vectoring paper reports a lap time. Not one.** The literature
  is road-car stability and energy efficiency on ISO manoeuvres.
- **Classical TV is worth 4–9% of lap time** on small low-downforce cars
  (Antunes 2019: **7.6%**, real Formula Student car, real track, PI yaw-rate
  controller). That is the magnitude to expect and to design the experiment
  to resolve.
- **The 50–75% RL-beats-classical figures are baseline artefacts.** The same
  table shows −57.6% against LQR+SQP and **−5.2%** against SMC+SQP. Realistic:
  single-digit to low-double-digit percent against a competently tuned
  baseline.
- **No RL-TV paper reports seed variance.** Under rule 5 essentially every
  RL-vs-RL claim in that literature would be "no measurable effect."

**Prior art for our own POWER-REVIEW nulls:** Medina et al. (*Vehicles* 3(1),
2021) compared PID / SMC / LQR / MPC / LPV-MPC by lap time on a real circuit —
**all five within 0.13 s** — and state plainly that *"the error in the yaw
rate is not critical for lap times."* That is an independent, published
instance of exactly our Season 2 conclusion: lap time is a blunt instrument
for a chassis controller. Cite it.

**One paper does the joint thing we are building toward:** Bári & Palkovics
(arXiv:2506.06077, 2025) — PPO, 5 continuous actions (steering + four wheel
torques), TORCS, ~1.5×10⁹ steps. It **discovered torque vectoring from a bare
progress reward**: more torque to outer wheels, *negative* torque on the
inside rear against understeer. No lap time quoted, single track, and the
authors concede the powertrain difference confounds their comparison. It is a
proof that emergence is possible, not a magnitude.

### What this project is structurally set up to produce that does not exist

Recorded because it changes what is worth writing up, not just what to run:

1. A training-track-count sweep against held-out real circuits.
2. A specialist-vs-generalist lap-time gap on real circuits.
3. An observation-representation ablation for cross-track transfer.
4. A controlled comparison of TV action spaces (four torques vs `Mz` +
   allocator vs residual) with everything else fixed.
5. **Seed-variance reporting anywhere in RL torque vectoring.**
6. A joint-policy vs fixed-driver-plus-RL-TV ablation with vehicle, tyre model
   and reward held fixed.
