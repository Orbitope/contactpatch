# Power review — every result from Episode 6 onward, re-examined

*Written 2026-07-30. Status: **plan, not yet executed.** Follows the TRACKS.md
precedent: a root-level working document for a cross-episode effort. Findings
land in FINDINGS.md as they are established; this file holds the plan and its
decisions.*

---

## 1. Why this review exists

Season 2's design sweeps returned "no measurable effect" for weight distribution
(F44) and polar moment (F49), and those nulls have been treated as findings.
They are more likely **artefacts of an instrument with no resolution on the axis
being measured.** Three compounding reasons, each independently sufficient to
suspect the result:

1. **The car is below saturation almost everywhere.** F43 measured this
   directly, for the one design axis it was ever checked on: at 2.5 kN drive
   cap no tire on either car exceeds 63% of capability and the FWD-vs-RWD
   difference **vanishes**; at 10 kN it is 0.46 s. The default 4.5 kN sits near
   the bottom of that curve. Design differences express through tire
   saturation; an unsaturated car hides them. **Episodes 7 and 8 ran only at
   4.5 kN.** The F43 amplification experiment was never repeated for balance or
   layout — the two axes that returned nulls.

2. **The metric is diluted by construction.** `long_exit` is 393 m of which
   260 m is a power-limited straight where no handling property can matter.
   Full-lap time — the only time Episodes 6–8 report — is therefore ~two-thirds
   a measurement of the engine model. Episode 13 added `section_time` for
   exactly this reason and it mattered (+0.69% section vs +0.51% lap).
   Episodes 6–8 have no section metric.

3. **Braking is cap-limited, not grip-limited.** `BRAKE_MAX` is 12 kN
   (driver/RL) and 15 kN (OC) against a ~1,980 kg car whose tires support
   ~1.05 g ≈ 20 kN. Every configuration brakes at the same sub-grip cap, so
   the braking phase — where load transfer and balance differences should be
   loudest — is design-blind by construction. `[MEASURED]` check pending
   (Phase 0); if confirmed it joins the other two.

A fourth problem is a contradiction in our own error bar. F43 quotes a
**0.02 s** convergence floor in one paragraph and calls the largest plausible
convergence bias **0.08 s** four paragraphs later. If the floor is 0.08 s, then
F49's entire rear-drive spread (0.03 s) and most of F44's differences sit
*inside* the noise, and both findings' honest statement is "we cannot tell" —
which is a different claim from "there is no effect," and only the latter is
currently written down.

**The reframing this review adopts.** The question the series keeps asking is
*"is this design faster?"* What Episodes 6–8 actually measured is *"does this
design change minimum time on one gentle corner plus a long straight, at a
power level where the tires are loafing?"* The answer to the second question
being "no" says almost nothing about the first. A slow car driven mostly
straight looks the same in every configuration; that is not a finding about
cars, it is a property of the test.

## 2. What is at risk, episode by episode

| Ep | Result as published | Power exposure | Risk to conclusion |
|---|---|---|---|
| 6 | RWD faster by ~0.10 s; penalty ∝ power (F34/F43/F45) | **Already swept** 2.5–10 kN | **Low** — F43 is the model for this review. Only the headline *magnitude* is power-pinned; conditional already stated |
| 7 | Balance: K swings 1.06 deg/g, lap time flat (F44) | Single point, 4.5 kN | **High** — the null may be the instrument. K-vs-balance is safe (kinematic); the lap-time claim is not |
| 8 | Polar moment: rise time moves, lap time flat (F49) | Single point, 4.5 kN | **High** — same as Ep 7. The "solver cannot be surprised" mechanism may also be doing work, and the two are confounded |
| 9 | RL learns; reward-hacking story (F51–F56, F61) | `DRIVE_MAX = 4500` baked into env | **Low** — the episode is about training pathologies, not car design. Re-caveat, don't re-run |
| 10 | Design-conditioned policy; line deforms with balance | Same env constant | **Medium** — the *line-shape* claim is qualitative; the RL-vs-OC trend cross-check should be re-verified at the new power |
| 11 | Fastest design most fragile, p=0.0005 (F98) | Same env constant | **Medium** — ordering was established at 4.5 kN. Fragility mechanism (rear-limited divergence) should *strengthen* with power, but that is a prediction, not a measurement |
| 12 | Diff binds mid-corner; push-wide (F76/F77) | Closed-loop at 4.5 kN | **Medium** — diff torque bias scales directly with drive force. Direction safe, magnitudes not |
| 13 | TV worth +5.18% limit / +0.51% lap; allocator ~40% (F82, F97) | Closed-loop at 4.5 kN | **High for Ep 15's purposes** — TV acts on saturated tires; at low power there is less saturation to act on. The published magnitudes are floor estimates of what TV does at real sports-car power |
| 14 | H≈E in-corner; both drive clean (F93–F95) | RL, same env constant | **Medium** — re-train is expensive; defer until the power decision is fixed and Ep 15's design needs it |
| 15 | Not built | — | **Blocked on this review** — running "TV flattens design sensitivity" on an instrument that cannot see design sensitivity would produce a null that means nothing |
| 16 | Not built | — | Chrono cross-check inherits whatever power configuration we settle here; do not build before this lands |

## 3. Decisions this review must make first

Each is a modelling choice (rule 9): record it, and measure its sensitivity.

### D-A · How power is represented

The current `drive_max` force cap is wrong in a speed-dependent way — F43's own
caveat: "a real engine's force falls with speed rather than staying capped."
A constant force cap over-delivers at low speed and under-delivers at high
speed, which distorts exactly the corner-exit phase where drivetrain and
balance differences live.

**Options:**
1. Keep the force cap, sweep it. Cheapest; keeps continuity with F43. The cap
   stays `[ASSUMED]` and the speed distortion stays unmodelled.
2. **Power-limited drive: `F = min(F_cap, P/v)`** — two parameters, the
   standard first-order model. `[SOURCED]`-able against any real car's
   power/torque curve. Changes the OC constraint (still smooth, CasADi-safe)
   and one line in the driver and env.
3. Full torque curve + gearing. Fidelity theatre at rung 2; rejected.

**Recommendation: 2**, with the F = P/v knee stated on every figure. It makes
"horsepower" mean horsepower, which the series narrative needs, and it removes
a known distortion from the phase of the corner we care most about.

### D-B · What power level(s) the series stands on

RV-1 is a GR86: 174 kW / 228 hp `[SOURCED]`. The 4.5 kN cap ≈ 135 kW at 30 m/s,
mildly *under* the real car. The instinct "raise the power so effects show" is
right as measurement practice but wrong as a spec change: RV-1's validation
targets (D1 reality-check rows, understeer band, SSF) are anchored to the GR86,
and silently re-powering it breaks rule 2's chain.

**Recommendation: keep RV-1 as the anchor; measure on a three-point power
curve, not a pair.** A pair can only say "different"; a curve can say
*monotone*, which is what made F43 credible — its four points growing in order
is why the trend is trusted even where individual solves didn't converge.

- **RV-1 (1×)** — GR86 power, P = 174 kW / 228 hp `[SOURCED]`. The validation
  anchor. Every diagnostic keeps passing against it.
- **1.5×** — P ≈ 260 kW / ~350 hp. The ordinary sports-car tier (Supra,
  Cayman S class). Arguably the most *relevant* point: if effects express here,
  they matter for cars people actually drive, not just for the top of the range.
- **RV-1P (2×)** — P ≈ 350 kW / ~470 hp `[ASSUMED]`. The amplification end,
  where F43 showed design effects at 4–5× their 1× size.

Every design question from here is answered as the **curve**, with the shape
reported: an effect that grows smoothly through 1.5× is a different (and more
useful) claim than one that only exists at 2×. Headline number at the level
where the effect expresses, conditional stated in the finding, F43-style.
"Rear drive is faster *at a given power*" was the most useful sentence in
Season 2; this makes that structure the default.

### D-C · The section metric — "ignore the straights once it's evened out"

Full-lap time stays (it is what a stopwatch measures) but stops being the
headline. The headline becomes **section time over the window where designs can
differ**, defined mechanically, not by eye:

- **Start:** the latest common braking point across the configurations being
  compared (first `s` where any config's longitudinal demand goes negative,
  minimum over configs).
- **End:** the `s` past corner exit where the compared speed traces have
  re-converged to within a stated tolerance (proposal: |Δv| < 0.5% of v,
  sustained for 10 m). Beyond that point the cars differ only by the constant
  speed offset they carry onto the straight — integrating further just dilutes.
- Both endpoints computed **downstream from logged arrays** (rule 7), never
  inside the sim loop, so redefining the tolerance re-slices old runs for free.
- The exit-speed difference at the section end is reported *alongside* section
  time, because carrying +1 km/h onto a straight is real lap time on a real
  circuit even though our 260 m straight exaggerates its weight.

### D-D · The track set

One 40 m corner cannot support "is it faster" claims — different corner speeds
stress different budgets (slow = traction-limited exit, fast = lateral-limited).
Add two synthetic corners via the existing `Segment` machinery (no TUM import
needed):

- `hairpin`: R = 15 m (second-gear corner, traction-dominated)
- `long_exit`: R = 40 m (the incumbent, continuity with everything published)
- `fast_sweep`: R = 90 m (lateral-dominated, near-flat at RV-1 power — and NOT
  at RV-1P power, which is itself a finding worth having)

Full grid {3 tracks × 2 powers} only for the episodes being actively
re-measured (7, 8); single-track spot checks elsewhere.

## 4. Phases

### Phase 0 — costs an afternoon, spends no solver time

1. **Recompute section times from the existing `traces.npz`** of Episodes 6–8
   under the D-C definition. If the balance/layout nulls stay null *on the
   section metric at 4.5 kN*, the dilution explanation weakens and saturation
   is the live one; if section times already separate, F44/F49 are corrected
   before any re-run.
2. **Resolve the 0.02 vs 0.08 s floor contradiction** (F43 internal): re-derive
   the convergence bias bound from the converged/unconverged pairs already on
   disk; write the answer down once, as a finding, and re-audit F44/F49's
   claims against it.
3. **Brake-cap audit**: compute peak achievable deceleration vs the cap for
   RV-1; check whether any Season 2 solve ever brakes below the cap. If none
   does, braking has been design-blind everywhere and the section metric must
   start before the braking zone to have any chance of seeing balance effects
   under braking — and `brake_max` needs the same D-A/D-B treatment as drive.
4. Write D-A through D-D into FINDINGS as decisions with their sensitivity
   plans, once confirmed.

### Phase 1 — Season 2 re-measured (Episodes 6, 7, 8)

OC solves only; hours, not days. For each of Ep 7's balance grid and Ep 8's
layout grid: {1×, 1.5×, 2×} × {hairpin, long_exit, fast_sweep}, section metric
headline, **every solve required to converge** (F39 gate — raise `max_iter`,
prefer the grid where everything converges; at 2× power expect to need it).
The 1.5× row doubles as the convergence hedge: if 2× solves fight the
iteration limit, the 1×→1.5× leg still establishes the trend direction on
fully converged solves rather than losing the phase to F39.
Envelope occupancy must stay 0 (higher power pushes slip ratio toward the
±0.20 bound; if solves start riding it, that is reported, not clipped away).
Ep 6 needs only a confirmation pass: F43 already contains its power sweep;
re-express it on the section metric and under D-A's power model.

**Pre-registered outcomes (rule 9), stated before running:**
- *If* balance/layout spreads stay within the (re-derived) floor at all three
  powers on the section metric: the nulls are real, and they get **stronger** —
  currently they are one-power-point claims; they become power-robust claims
  across a 2× range. F44/F49 stand with upgraded evidence.
- *If* spreads emerge and grow monotonically along 1× → 1.5× → 2×: F44 and
  F49's lap-time claims are corrected F43-style ("balance barely matters *at
  228 hp*"), with the curve shape saying whether the effect is already alive at
  ordinary sports-car power or only at the top; Episode 7 and 8's articles gain
  the power conditional, and Episode 15 inherits a design-sensitivity baseline
  that actually varies — which it needs to exist.
- *If* spreads appear but **non-monotonically**, that is a flag on the
  instrument (convergence, envelope riding), not a finding — investigate before
  quoting anything. Monotonicity is the same credibility test F43 passed.
- Any of the three is publishable; this is not a fishing trip.

### Phase 2 — Season 4 classical (Episodes 12, 13)

Closed-loop; ~15 min per configuration set, so the full curve is affordable
here too. Re-run Ep 12's diff comparison and Ep 13's five-configuration study
at {1×, 1.5×, 2×} (D-A model, section metric). The specific number Episode 15
needs from this phase: **TV's worth as a function of power** — per F43's
mechanism the corner-section gain should grow with saturation, and the curve
shape tells Episode 15 which power its comparison lives at. Ep 13's
driver-preview sensitivity check (F84) is re-run at 2× — if the preview
dependence grows with power, Episode 15's protocol must fix the driver before
it compares anything.

### Phase 3 — Season 3 RL (Episodes 9–11) — conditional, cheapest last

No retraining until Phases 0–2 land. Then:
- Ep 9: re-caveat only (training-pathology story is power-independent).
- Ep 10/11: retrain the design-conditioned policy with the batched env (29×
  throughput makes this an overnight job, not a week). RL training is the one
  place the full curve is not affordable — retrain at **2× only**, and lean on
  Phase 1/2's curves for shape. Re-verify: (a) the RL-vs-OC trend cross-check
  at the new power, (b) F98's fragility ordering.
  Pre-registered: the fragility gap should widen with power (more rear-axle
  demand on corner exit); if it instead closes, F98 gains a power conditional.

### Phase 4 — Episode 15, unblocked

Only now does "does TV flatten design sensitivity?" have both of its
prerequisites: a design-sensitivity baseline that measurably varies (Phase 1)
and a TV magnitude measured where tires saturate (Phase 2). The episode's
comparison runs at RV-1P on the section metric, with the RV-1 numbers alongside
as the "your actual GR86" row. Scope per the series plan: Ep 6 + 7 + 8 axes
(drivetrain, balance, layout — layout is what the 911 payoff line rests on).

## 5. Gates that apply to every phase

- `Solution.success` on every quoted solve; grids where everything converges
  beat finer grids that don't (F39).
- Envelope occupancy 0 for OC; deployed-policy envelope per D12 for RL.
- ≥3 seeds where stochastic (rule 5); rank/trend claims only across models
  (rule 6).
- Every re-measured number replaces its predecessor in the article **with the
  correction visible** — the F96→F97/F98 pattern: state what was claimed, what
  it is now, and why the direction of change was not predictable in advance.
- Fidelity rung stated everywhere (rule 15): all of this is still rung 2; RV-1P
  makes the *simulated car* faster, not the model realer.

## 6. What this review does not do

- No real-circuit import (TRACKS.md is separate infrastructure; the synthetic
  three-corner set is deliberately sufficient here).
- No tire rescale (O1 stays open; same tire throughout keeps comparisons
  internally valid).
- No Chrono (Episode 16 waits for the power configuration to stabilize, or it
  would validate numbers we are about to change).
