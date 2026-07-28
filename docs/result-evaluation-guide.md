# Result Evaluation Guide

**Purpose.** This document exists so that "is this result real?" and "are these parameters right?" become checkable procedures rather than judgement calls requiring vehicle-dynamics expertise. Every check below is either a published benchmark, a textbook invariant, or an arithmetic rule.

**How to use it.** Work top to bottom. Part A is one-time (parameter verification). Part B runs on every result before you believe it. Part C is what to do when something fails.

---

# Part A — The three uncertain parameters, resolved

These were flagged as `[ASSUMED]` and as the ones that would bias results. All three now have primary or near-primary sources.

## A1. Weight distribution — **RESOLVED, 53:47**

Toyota's own GT86 press kit states an intentional **53:47 front:rear** distribution, describing it as the result of setting powertrain and driving position as low and as far toward the centre as possible, and stating that engineers established 53:47 as producing the ideal response during spirited driving. That is a manufacturer primary source and a design intent, not an estimate.

**Conflict to be aware of.** An enthusiast suspension-calculation spreadsheet uses **56:44**. Both can be true: manufacturer figures are typically quoted at curb weight with no occupants, while a corner-weighted car with a driver aboard sits further forward. Since our simulated mass includes an 80 kg driver, the truth for our purposes is probably between the two.

**Decision:** use **0.54** front fraction as nominal (splitting the difference, driver-inclusive), and **document the 53–56 range as a known uncertainty**. The design sweep spans 0.35–0.65 anyway, so the nominal only matters as the "stock car" reference point on plots.

## A2. CoM height — **RESOLVED, 460 mm**

Toyota's press kit states an **ultra-low centre of gravity of 460 mm**, tied to a driver hip-point of 400 mm and the low-mounted boxer engine. Independent cross-check: the enthusiast spreadsheet uses 18 inches = **457 mm**. Two independent sources within 3 mm is as good as this gets without a tilt table.

**Decision:** use **0.460 m**. High confidence. Note this is a genuinely low value — it is the platform's headline engineering claim — so do not "correct" it upward toward generic sedan figures.

## A3. Track width — **RESOLVED with lower confidence, 1505 / 1495 mm**

Front **1505 mm**, rear **1495 mm**, sourced from a dimensional listing that cites SAE J1100-compliant surveys. The source is a lower-quality content site, so treat as `[LIKELY]` rather than `[SOURCED]`.

**Why this one matters most.** Track width is the **moment arm for torque vectoring**. Yaw moment from a left-right torque split scales linearly with it, so a 5% error in track width is a 5% error in every TV result. It is the single most leverage-bearing uncertain number in the project.

**Sanity checks that make 1505/1495 credible:**
- Overall width is 1775 mm `[SOURCED]`. Track is typically 82–88% of overall width for a coupe; 1505/1775 = 84.8%. In range.
- Front track slightly wider than rear is the conventional arrangement for a front-engine RWD car.
- Consistent with the platform's 5×100 bolt pattern and +48 offset 7.5" factory wheels, which are described as conservative.

**Decision:** use 1.505 / 1.495 m, and add a **TV-result sensitivity note**: before publishing any TV magnitude claim, re-run the headline case with track width at ±3% and confirm the *conclusion* (not the number) is unchanged. If a finding flips on a 3% track-width change, it was never a finding.

## A4. Summary of the reference vehicle after verification

| Parameter | Value | Confidence |
|---|---|---|
| Curb mass | 1280 kg | High |
| Simulated mass (+ driver) | 1360 kg | High |
| Wheelbase | 2.575 m | High |
| Track front / rear | 1.505 / 1.495 m | **Medium — sensitivity-check TV results** |
| Front mass fraction | 0.54 (range 0.53–0.56) | High |
| CoM height | 0.460 m | High |
| Yaw inertia | 1,950 kg·m² | Medium (correlations disagree; see parameter sheet) |

---

# Part B — Deciding whether a result is real

Four gates, in order. A result must pass all four. Later gates are meaningless if an earlier one fails.

## Gate 1 — Falsification checklist (does the model obey physics?)

These are textbook facts. **Any violation is a bug, not a discovery.** No expertise needed: if the model disagrees with these, the model is wrong.

| # | Must be true | If violated |
|---|---|---|
| 1 | Peak tire μ **decreases** as vertical load increases | Tire code or load-transfer sign error |
| 2 | Moving weight forward **increases** understeer gradient K | Weight-distribution wiring or axle indexing |
| 3 | Stiffer **front** anti-roll bar → **more** understeer | Roll-stiffness distribution sign flipped |
| 4 | Braking transfers load **forward**; accelerating transfers **rearward** | Longitudinal load transfer sign |
| 5 | In a left turn, **right-side** wheels gain load | Lateral load transfer sign |
| 6 | Higher CoM → **more** load transfer, proportionally | Geometry error |
| 7 | Higher yaw inertia → **slower** yaw response, **less** overshoot | `I_zz` not actually in the loop |
| 8 | Σ of four normal loads = `mg` when vertical acceleration is zero | Double-counted load transfer |
| 9 | Sum of all four tire forces cannot exceed μ·`mg` | Friction limit not enforced |
| 10 | A FWD car cannot accelerate out of a corner as hard as RWD at the same grip | Drivetrain torque routing |
| 11 | Locking a diff **increases** understeer on power (RWD) | Diff model sign |
| 12 | Terminal behaviour should be understeer for a road-car setup | Consistent with SAE J266 observation that most road vehicles show limit understeer |

Gate 1 is checked by diagnostics D1–D5. **If any of these fail, stop. Nothing downstream means anything.**

## Gate 2 — Plausibility bands (are the magnitudes sane?)

Published reference values. Being outside a band is not automatically wrong, but it demands an explanation before publication.

### Handling metrics

| Quantity | Expected range | Source basis |
|---|---|---|
| Understeer gradient K, passenger car | 3 – 5 deg/g | Widely cited |
| K, sports car | 1 – 2 deg/g | " |
| K, our GR86-class car | expect **1.5 – 3 deg/g** | Interpolating; it is a sports car with mild understeer bias |
| K below 1 deg/g | essentially never seen in production | Practitioner report: virtually no production vehicles below 1 deg/g |
| **K noise floor** | **0.2 deg/g** | Difference observed between two submissions of the *same* tire in professional testing |
| K drift during vehicle development | up to 0.5 deg/g | " |
| Max lateral acceleration, our car | 0.95 – 1.10 g | Follows from the Chrono tire's peak μ ≈ 1.04 at our corner load |
| Static Stability Factor | 1.66 | Ours; NHTSA range runs ~0.95 (SUV) to ~1.8 (Corvette) |

**The 0.2 deg/g figure is the most important number here.** It is the real-world resolution limit of understeer-gradient measurement. Any K difference our design sweep produces that is smaller than 0.2 deg/g is finer than a professional test program can distinguish between two batches of the same tire. **Do not report it as a finding.**

### Torque vectoring benefit

| Claim | Published value | Notes |
|---|---|---|
| TV lap-time saving, FSAE car, skid-pad trajectory | **up to ≈9%** | Best-case: a small light car on a constant-radius circle, i.e. maximally favourable to yaw authority |
| TV benefit, road-track lap | consistently positive but smaller | Multiple studies report improved yaw response and lap times via better tire-force exploitation, generally without the 9% headline |
| TV energy saving (not lap time) | ~10% in typical driving | Different objective; do not conflate with lap time |

**Interpretation band for our project.** A GR86-class car on a mixed circuit is much less favourable than an FSAE car on a skidpad. Expect **1–4%** lap time from TV. Treat results this way:

- **< 0.5%** — suspiciously small. Likely the controller is undertrained, the moment arm is wrong, or actuator limits are binding.
- **1 – 4%** — plausible. Report it.
- **4 – 9%** — high but not impossible if the track is corner-dense. Requires explanation.
- **> 9%** — exceeds the best published figure on a maximally favourable case. **Assume a bug or tire-model exploitation until proven otherwise.**

### A published result that doubles as a validation signal

One study comparing TV controllers on a modelled race car found that **best lap times were not produced by perfectly neutral yaw-rate tracking, but by allowing certain deviations from the target yaw rate.**

This is a strong, falsifiable prediction for our P4b experiment. If our learned upper-layer policy (variant H) converges on commanding yaw moments that deliberately deviate from a neutral-steer reference — and goes faster doing so — **that is independent corroboration**, not an anomaly. It is also exactly the kind of behaviour a classical reference-model controller cannot express, which is the "why RL?" argument made concrete.

Conversely: if our learned policy converges to *exactly* neutral-yaw tracking and shows no gain over the classical baseline, that is a hint the policy is undertrained or the reward is not actually lap-time-driven.

## Gate 3 — Statistical rules (is it bigger than noise?)

No expertise required; these are arithmetic.

| Rule | Threshold |
|---|---|
| Minimum seeds per configuration | 3 (5 preferred in the fast environment) |
| Effect size to call a trend real | change across the sweep range > **2× seed standard deviation** |
| Understeer gradient differences | must exceed **0.2 deg/g** (Part B Gate 2) |
| Lap-time differences | must exceed 2× seed std **and** be visible in the cumulative delta-time trace as a localised gain, not diffuse noise |
| Rank-order claims | Spearman correlation across ≥ 5 design points; with 3 points, report effect size only and say so |
| Paired comparisons (multi-track) | same fixed evaluation track set for every design; never resample |

**When a trend is smaller than 2× seed spread, the correct report is "no measurable effect," not "a small effect."**

## Gate 4 — Honesty checks (is the result about cars or about the model?)

| Check | Pass condition | Where |
|---|---|---|
| Envelope occupancy | < 2% of samples outside the imposed operating envelope (±12° slip, ±0.20 slip ratio, `Fz` within 225–10,125 N) | D6 panel B |
| Gap to OC ceiling | RL within ~1% of the optimal-control lap time for the same design | D6 panel C |
| Design-space coverage | no cold spots in the conditioned policy's visit histogram | D6 panel D |
| Action saturation | no channel pinned at its limit > 50% of the time | D6 panel E |
| Termination mix | > 90% laps completed; spins < 2% | D6 panel F |
| Clairvoyant bound (P4) | learned TV lap time sits **between** passive optimum and open-loop OC-with-per-wheel-torques | P4 methodological guard |

**Read D6 panel B before panel A.** A beautifully converged reward curve on an exploited tire model is worse than no result at all, because it looks like success.

---

# Part C — What to do when a check fails

A decision tree, so a failure produces an action rather than a stall.

**Gate 1 failure (physics invariant violated)**
→ Stop all downstream work. This is a code bug. The specific invariant that failed points at the subsystem: signs → schema conventions; conservation → load transfer; monotonicity in `I_zz` → inertia wiring. Fix, re-run D1–D5, then resume.

**Gate 2 failure (magnitude outside band)**
→ Not automatically a bug. Work through in this order:
1. Is a Gate 1 invariant *also* failing? If so, that's the real problem.
2. Is the design point genuinely unusual (e.g. 0.38 front fraction legitimately produces K below the road-car band)? If so, record it as an **explicit accepted exception in the test**, with the reason. Do not silently widen the tolerance.
3. Otherwise, suspect parameters: track width and CoM height are the highest-leverage uncertain values.

**Gate 3 failure (effect smaller than noise)**
→ Either run more seeds (cheap in the fast environment) or report "no measurable effect." Both are legitimate outcomes. What is not legitimate is reporting the trend anyway with a hedge.

**Gate 4 failure (envelope or convergence)**
→ Envelope violation: discard the lap time entirely; it measures model error, not car behaviour. Then either tighten the boundary penalty or restrict the design range.
→ OC gap > 1%: the policy is undertrained. More steps, or reward shaping. Do not interpret any finding from an undertrained policy.

**Two or more gates failing at once**
→ Almost always a single upstream cause, usually in P0. Return to the diagnostics rather than debugging the finding.

---

# Part D — A worked example of the whole procedure

Hypothetical result: *"Moving weight rearward from 0.54 to 0.44 front fraction improves lap time by 0.35 s and moves the apex 6% later."*

1. **Gate 1** — Does K decrease as weight moves rearward? Yes (invariant 2 satisfied, correct direction). Do loads still sum to `mg`? Yes. → Pass.
2. **Gate 2** — K went from 2.4 to 1.7 deg/g. Both inside the 1.5–3 expected band for this car class; the 0.7 deg/g change comfortably exceeds the 0.2 noise floor. Lap-time change is 0.4% — modest, plausible. → Pass.
3. **Gate 3** — Seed std is 0.09 s across 5 seeds. 0.35 s > 2 × 0.09 = 0.18 s. → Pass. Apex shift: 6% vs seed std of 1.8% → 6 > 3.6. → Pass.
4. **Gate 4** — Envelope occupancy 0.4%; OC gap 0.8%; no cold spots. → Pass.

**Verdict: report it.** And state the seed spread alongside the effect, always.

Now the same result with seed std of 0.25 s: 0.35 < 2 × 0.25 = 0.50. **Gate 3 fails.** Correct action: run more seeds. If the spread persists, the honest report is "lap-time effect not resolvable; apex shift is resolvable and is the finding."

---

# Part E — Things this guide cannot do for you

Stated plainly so the boundaries are visible:

- It cannot tell you whether a **novel** behaviour is real. If the learned TV policy does something not covered by Gates 1–2 — some unexpected corner-entry strategy — no checklist settles it. The recourse is: does it survive at multiple design points, does it survive in Chrono, and does it disappear when you remove the mechanism you think causes it? That last one — an **ablation** — is the general-purpose tool and is worth reaching for by default.
- It cannot validate **absolute** lap times. The tire is generic and oversized-then-rescaled; the model omits suspension compliance, aligning torque, and tire temperature. Comparative claims are the product; absolute claims are not.
- It cannot substitute for the **Chrono cross-check** (P6). Gates 1–4 confirm internal consistency. Only a different model tests whether findings depend on our particular simplifications.
