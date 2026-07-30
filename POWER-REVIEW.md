# Power review — every result from Episode 6 onward, re-examined

*Written 2026-07-30. Status: **plan, not yet executed.** Follows the TRACKS.md
precedent: a root-level working document for a cross-episode effort. Findings
land in FINDINGS.md as they are established; this file holds the plan and its
decisions.*

---

## 1. Why this review exists

**Status update, 2026-07-30, mid-Phase-0: half the premise below turned out to
be wrong in a more interesting way than expected.** This review opened by
treating F44 (balance) and F49 (layout) as symmetric nulls, both suspected
instrument artefacts. Re-solving to check that (Phase 0 item 1) surfaced
**F99**: both entries predate the F72/F73/F79/F80 yaw-moment correction —
exactly the failure mode F90 already caught once, for a different number in
the same episode — and were never updated after the episode *articles*
already were. Corrected:

- **F44 (balance) was never a null.** The corrected data (all ten solves now
  converge; three used to be excluded) spans **0.205 s rear-drive, 0.121 s
  front-drive** across the 40–65% range — not "indistinguishable," a real and
  fully-converged ~1.7% effect. The published article already says this
  ("rear drive's sensitivity has doubled"); FINDINGS.md's F44 entry did not.
- **F49 (layout) is a genuinely flatter null than published**, not an
  artefact discovered — the corrected ranking removes the one candidate
  outlier (front-engine-FWD moves from last to second) and the span shrinks
  to a uniform 0.056 s.

**What this does to the rest of this section.** The saturation argument
(point 1 below) and the dilution argument (point 2) were built to explain
*two* apparent nulls. They still fully apply to **F49**, and to **F44's
lap-time* magnitude* question — does an already-real 1.7% effect grow with
power the way F43's drivetrain effect did? — but they no longer need to
argue F44 into existing at all. Read what follows with that adjustment; the
episode-risk table in §2 is corrected to match, and F99 is the finding this
plan now treats as read.

Three compounding reasons remain, independently sufficient to keep
questioning any *magnitude* claim at the default power level:

1. **The car is below saturation almost everywhere.** F43 measured this
   directly, for the one design axis it was ever checked on: at 2.5 kN drive
   cap no tire on either car exceeds 63% of capability and the FWD-vs-RWD
   difference **vanishes**; at 10 kN it is 0.46 s. The default 4.5 kN sits near
   the bottom of that curve. Design differences express through tire
   saturation; an unsaturated car hides them. **Episodes 7 and 8 ran only at
   4.5 kN.** The F43 amplification experiment was never repeated for balance or
   layout.

2. **The metric is diluted by construction — but less simply than "cut the
   straight."** `long_exit` is 393 m of which 260 m is a power-limited
   straight. The naive fix (a fixed corner-only time window) was tried against
   the balance sweep's own traces during Phase 0 and **understates the effect**:
   the speed deficit between the 40% and 65% front cars peaks at corner exit
   (~3.8%) and decays only slowly, **never fully re-converging within the
   392.8 m track** (still 0.9% apart at the finish). So the "irrelevant"
   straight is not fully irrelevant — it is where a real corner-caused
   deficit keeps bleeding off. Episode 13's `section_time` (a fixed window on
   its own, shorter, closed-loop lap) is not a direct template here; D-C
   below is revised accordingly. Episodes 6–8 still have no section metric of
   any kind, which remains true and remains worth having.

3. **Braking is cap-limited for the closed-loop driver, but NOT for the OC
   solver — measured directly, and the original guess (`~1,980 kg`, an earlier
   draft's error) had the wrong mass; RV-1 is 1,360 kg.** Checked both paths:
   - **OC (Episodes 6–8):** peak commanded braking force across every solve
     in Episode 6's traces reaches at most **87.6% of the 15 kN cap**
     (13,140 N ≈ 0.985 g) — **zero nodes sit at the cap.** The solver, free to
     ask for anything up to 15 kN, never asks for that much, because trail
     braking shares the tire's capacity with lateral force (the friction
     ellipse) and the optimiser is already trading the two optimally. **The
     OC brake cap does not bind and is not the problem.**
   - **Closed-loop driver (Episodes 11, 13, and everything Season 5 plans to
     build on it):** the speed plan's braking target is
     `min(BRAKE_MAX/mass, grip_use·g)` = `min(0.899 g, 1.0 g)` = **0.899 g at
     `grip_use=1`** — the 12 kN cap, not the tire, sets the plan, and the
     realised force gets to **98.9%** of that cap. Since the OC solver's own
     unconstrained result shows the tire can deliver **~0.985 g** under the
     same combined-slip demands, **the closed-loop driver brakes at a target
     that is below the tire's own demonstrated capability, and that target is
     a fixed scalar independent of `front_mass_fraction`, `i_zz` or
     drivetrain.** The braking *phase* is design-blind by construction for
     the closed-loop path specifically — confirmed, not merely suspected —
     while the OC path needs no fix here. **Not a D-A-style sensitivity
     question** — braking capacity is a tire/mass property, not an engine-power
     one, so it has no business riding the 1×/1.5×/2× power curve at all.
     `BRAKE_MAX` (closed-loop only) simply needs raising to at least the
     ~0.985 g the tire has already demonstrated it can deliver, once, not
     re-derived per power level.

**The convergence-floor contradiction is resolved, not just re-audited.** F43
quoted both 0.02 s and 0.08 s as the convergence bias bound. That question is
now moot for F44/F49 specifically — every solve behind both corrected tables
converges (`Solve_Succeeded`, no iteration-limit exclusions), and re-running
them was verified bit-identical to the already-committed artefact, so there is
no unconverged-solve uncertainty to bound for these two findings. The 0.02 vs
0.08 s question may still matter for *other* unconverged solves elsewhere in
the project; it no longer determines whether F44 or F49 are real.

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
| 7 | Balance: K swings 1.06 deg/g; lap time spans **0.205 s RWD / 0.121 s FWD**, monotonic, all converged — **corrected by F99**, was published in FINDINGS as flat/null | Single point, 4.5 kN | **Medium, inverted** — not "is there an effect" (there is) but "how does an already-real ~1.7% effect move with power" — the F43 shape, not the F44/F49 null-audit shape |
| 8 | Polar moment: rise time moves, lap time flat and *more* uniform than published (0.056 s span, no outlier — **corrected by F99**) | Single point, 4.5 kN | **High, as before** — the null is real at 1×; the "solver cannot be surprised" mechanism may still be masking a power-dependent effect, and the two are confounded |
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

### D-A · How power is represented — resolved as a sensitivity axis, not a
replacement

The current `drive_max` force cap is wrong in a speed-dependent way — F43's own
caveat: "a real engine's force falls with speed rather than staying capped."
A constant force cap over-delivers at low speed and under-delivers at high
speed, which distorts exactly the corner-exit phase where drivetrain and
balance differences live.

**The obvious next move — pick the power-limited model and re-baseline
everything onto it — was checked before being adopted, and the check changed
the decision.** At RV-1's own 174 kW, `F = min(F_cap, P/v)` drops below
today's 4.5 kN cap once the car exceeds 38.7 m/s — **30% of Episode 6's own
exit straight, at the power every published episode already used.** Adopting
it as *the* model would silently move lap times in Episodes 1–14, including
the numbers F99 just finished correcting. That is a materially bigger
decision than "add a more realistic power model," and not one this plan gets
to make unilaterally.

**Resolution: run both, report both, let disagreement be the finding where
there is one.** This is rule 9 applied to itself — the same treatment track
width already gets (`[LIKELY]`, re-run at ±3%, the conclusion has to survive
it) — rather than silently swapping one assumption for another:

- **Flat cap (`F_cap`, unchanged)** — what every existing episode was measured
  with. Nothing already published is touched. Scaling it directly (F43's own
  method) is how the drivetrain power sweep already works, and Phase 1 keeps
  using it for continuity with F43, F44, F49.
- **Power-limited (`F = min(F_cap, P/v)`)** — run *alongside* the flat cap in
  Phase 1, not instead of it, at the same power levels. Where the two agree in
  trend and rank ordering, that is a stronger result than either alone —
  robust to a modelling choice this project was carrying unexamined. Where
  they disagree, the disagreement is reported as its own finding (most likely
  candidate: high-power, high-speed configurations — the exit straight above
  ~39 m/s — since that is exactly where the two models diverge at 1× already).
- **Neither replaces the other in any already-published article.** Episodes
  1–14 stand as measured. The comparison is new information Phase 1 produces,
  not a retroactive correction — unless the comparison itself surfaces a
  further F99-style staleness, in which case that gets its own finding, same
  as everything else in this project.

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

**Revised during Phase 0: the re-convergence assumption below does not hold on
`long_exit`, checked directly rather than assumed.** The original proposal
(end the section where speed traces re-converge within tolerance) presumes
convergence happens before the track runs out. Tested on Episode 7's own
traces, RWD 40% vs 65% front: the speed gap peaks at **3.8%** right at corner
exit and decays to **0.9%** by the finish, 260 m later — **it never reaches
the 0.5% proposed tolerance.** A fixed geometric corner window (turn-in to
corner-arc end) is worse, not better: it recovers only **~19%** of the full-lap
time span (0.039 s of 0.205 s for RWD), because it cuts off before the
corner-exit deficit has even started bleeding off, and because heading angle
`ξ` reaches **24° at turn-in** — nowhere near small enough to treat the
lateral-velocity correction to `dt/ds` as negligible, which is *why* a naive
arclength/speed integration silently disagreed with the solver's own exact
`dt_ds` by ~0.07 s when checked (see FINDINGS F99's provenance; `dt_ds` is now
logged directly in Episodes 6/7's traces rather than approximated).

**Practical consequence: for a corner this short relative to its exit
straight, "the section" and "the full lap" are not usefully different
metrics** — the corner-caused deficit is still resolving when the straight
ends, so nearly all of the full-lap number *is* the section number, just
diluted by however much of the remaining gap has already bled off by the
finish line. This reframes what a section metric is *for* here: not
separating signal from an irrelevant straight (there mostly isn't one, on
this specific track), but **decomposing where along the lap a design
difference is created**, which full-lap time collapses into one scalar and
throws away. Kept for that purpose:

- **Start:** the latest common braking point across the configurations being
  compared (first `s` where any config's longitudinal demand goes negative,
  minimum over configs).
- **End:** full track length by default (not a re-convergence point, absent
  evidence one exists within the track) — report the **speed-gap curve**
  itself (gap vs `s`, from corner entry to finish) as a figure alongside any
  scalar, since the curve is where "does it converge, and how fast" actually
  lives, and a single number hides exactly the thing D-C exists to reveal.
  A re-convergence point is used only where it is *checked* to occur before
  the track ends (e.g. a longer or slower configuration) — never assumed.
- Both endpoints, and the whole curve, computed **downstream from logged
  arrays** (rule 7) via each solve's own `dt_ds` — exact, not approximated
  from `(1 − n·κ)/speed`, which is wrong exactly where `ξ` is large (turn-in,
  corner exit) — never inside the sim loop, so redefining anything re-slices
  old runs for free, provided `dt_ds` was logged (Phase 0 added this to
  Episodes 6/7; Episode 8's archetype sweep has **no per-node trace saved at
  all** yet, only a scalar `time_s` — a gap of its own, noted in Phase 0).
- The exit-speed difference at the section end is reported *alongside* section
  time regardless, because carrying +1 km/h onto a straight is real lap time
  on a real circuit even though our 260 m straight exaggerates its weight.
- **Longer or slower tracks (D-D) may behave differently** — a hairpin's much
  lower exit speed could plausibly re-converge with the following straight
  well before it ends, where `long_exit`'s fast, power-limited exit does not.
  Check per track; do not import this section's conclusion onto a track it
  was not measured on.

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

### Phase 0 — status: items 1–3 done, none of them the way they were planned; item 4 open

1. **DONE, but not as scoped.** "Recompute section times from the existing
   `traces.npz`" turned out to be impossible as literally written — Episodes
   6/7's saved arrays have `n`, `ξ`, `speed` but never the per-node time
   (`dt_ds`) needed to integrate a true section time, and the naive
   `(1−n·κ)/speed` substitute is wrong by ~0.07 s exactly where `ξ` is large
   (turn-in). Fixed with a minimal, reviewed, additive change: `dt_ds` was
   already computed by the solver and discarded before saving — added it to
   Episodes 6 and 7's trace output (two-line diff each), re-ran both, verified
   the re-run **bit-identical** to the already-committed `results.json` before
   trusting anything downstream. **That re-run surfaced F99** (below) —
   larger news than the section metric itself. Episode 8's archetype sweep
   still has no per-node trace saved at all (only a scalar `time_s`); adding
   it is now queued for whenever Ep 8 is re-measured (Phase 1).
2. **DONE, superseded by a bigger finding.** The 0.02-vs-0.08 s floor question
   is moot for F44/F49 specifically: both corrected tables rest on fully
   converged solves (verified), so there is no unconverged-solve bias to
   bound for them. What the re-audit actually found is **F99**: F44 and F49's
   FINDINGS.md entries predate the F72/F73/F79/F80 yaw-moment correction that
   their own episode *articles* already carry — the same staleness F90 found
   once before, in a different number, in the same episode. F44 was not a
   null (corrected spread 0.205 s RWD / 0.121 s FWD); F49 remains a null, and
   a tighter one than published (0.056 s, no outlier). See F99 and §1's
   status update for the full account, and the corrected D-C for what the
   re-run's speed-trace check found about re-convergence (it doesn't, on this
   track).
3. **DONE, and the original guess was half wrong.** Measured directly (§1,
   point 3, corrected mass 1,360 kg not the earlier draft's 1,980 kg): the
   **OC solver's 15 kN cap never binds** (peak commanded braking reaches
   87.6% of it, zero nodes at cap — braking is tire/combined-slip-limited,
   as it should be). The **closed-loop driver's 12 kN cap does bind** — its
   speed plan targets 0.899 g against a tire that (per the OC solver's own
   revealed capability under the same demands) can deliver ~0.985 g, and that
   0.899 g target is a fixed scalar independent of any design parameter.
   Braking is confirmed design-blind by construction, but **only for the
   closed-loop path** (Episodes 11, 13, and anything Season 5 builds on it) —
   not for Episodes 6–8's OC solves, which need no fix here. Not a power-curve
   question — braking capacity is a tire/mass property, not an engine one —
   `BRAKE_MAX` (closed-loop only) just needs raising to the ~0.985 g already
   demonstrated, once, independent of the 1×/1.5×/2× sweep.
4. **Fix the live inconsistency F99 flagged** in `episodes/ep07-*.md`: its own
   corrected numbers (0.21 s / 0.12 s, doubled) sit under a section still
   headed "it barely changes how fast it is." An editorial call, not a
   measurement — make it deliberately, not by drift.
5. Write D-A, D-B, D-D into FINDINGS as decisions once ratified (D-C already
   updated in place above, from what Phase 0 actually found rather than what
   it assumed).

### Phase 1 — DONE. Both axes grow monotonically with power, on every track,
under both drive models. See F100.

Balance took the outcome it predicted (F43-style, already real at 1× per
F99): ×2.3–8.1 growth 1×→2×, all 12 rows monotonic. Layout's null did **not**
survive: same range order as balance (×2.5–4.9), all 6 rows monotonic —
reversing F49 a second time in one day, for a different reason than F99's
correction (that was drift; this is scope — a corrected 1× number can still
be an incomplete measurement). Two defects found and fixed in the process,
both by refusing to trust a surprising number rather than by assuming the
grid was clean: a single cell landed in a genuine local-optimum trap
(`Solve_Succeeded` at a value 1.1 s off from both neighbours and worse than
the same design at *lower* power — physically impossible for a real
power increase, caught because it broke the spread's monotonicity, not
because the solve reported failure) and one cell hit the iteration limit
(re-solved, landed within 0.001 s of the unconverged run's own value — F39's
gentle case). A systematic scan of the other 268 cells found nothing else.

Episode 15 now has what this whole review exists to give it: **a
design-sensitivity baseline, on both axes, that measurably varies with
power.** What follows is the original plan, kept for the record of what was
intended before it ran; F100 above is what actually happened.

OC solves only; hours, not days. For each of Ep 7's balance grid and Ep 8's
layout grid: {1×, 1.5×, 2×} × {hairpin, long_exit, fast_sweep} × **{flat cap,
power-limited}** (D-A — both drive models, not one), section metric headline,
**every solve required to converge** (F39 gate — raise `max_iter`, prefer the
grid where everything converges; at 2× power expect to need it). The 1.5× row
doubles as the convergence hedge: if 2× solves fight the iteration limit, the
1×→1.5× leg still establishes the trend direction on fully converged solves
rather than losing the phase to F39. Envelope occupancy must stay 0 (higher
power pushes slip ratio toward the ±0.20 bound; if solves start riding it,
that is reported, not clipped away). Ep 6 needs only a confirmation pass: F43
already contains its power sweep on the flat-cap model; re-express it on the
section metric and add the power-limited comparison alongside it.

**The two drive models are reported side by side, not collapsed to one.**
Where they agree in trend and ordering, say so — that is a stronger result,
robust to a modelling choice this project was carrying unexamined until now.
Where they diverge, report where and by how much (§1 already predicts the
likely spot: high-speed, high-power configurations above ~39 m/s, where the
two models' constraints cross even at 1×). Neither model is presented as
having replaced the other.

**Pre-registered outcomes (rule 9), stated before running — split by finding,
since F99 means balance and layout no longer ask the same question:**

*Balance (Ep 7) — already real at 1×, per F99. The question is the curve:*
- *If* the 0.205 s / 0.121 s spread **grows monotonically** through
  1× → 1.5× → 2×: confirms the F43 mechanism (saturation) also drives balance,
  gives Episode 15 a design-sensitivity baseline that varies, and the curve
  shape says whether the effect is already large at ordinary sports-car power
  (1.5×) or only opens up at the top.
- *If* the spread **stays flat or shrinks** with power: a genuinely
  interesting reversal of the F43 pattern, worth its own explanation (e.g. if
  balance's effect is more about traction *authority* than *saturation
  margin*, it might not scale with power the way a pure friction-circle
  effect does) — investigate before quoting, not assumed away.
- *If* it moves **non-monotonically**: instrument flag (convergence, envelope
  riding), not a finding.

*Layout (Ep 8) — a corrected, tighter null at 1×. The question is whether it
stays null:*
- *If* the 0.056 s spread stays within the (now-moot-for-1× but still
  relevant-at-2×) convergence floor at all three powers: the null is real and
  gets **stronger** — a one-power-point null becomes a power-robust one.
- *If* a spread emerges and grows monotonically: F49 is corrected F43-style
  ("polar moment barely matters *at 228 hp*"), and layout joins balance as a
  real, power-conditional design axis.
- *If* non-monotonic: instrument flag, not a finding.

Any of these outcomes is publishable; this is not a fishing trip.

### Phase 2 — DONE. TV's cornering-limit gain over the open differential
grows from +4.6% at 1× to +125.5% at 2× power. See F101.

TV goes from a small, carefully-measured effect (matching F82's original
+5.18%) to more than doubling the achievable cornering limit — not because
TV gets better with power, but because everything else gets worse and TV
does not: the open differential's own limit nearly halves (1.044→0.480,
−54%), the passive LSD becomes completely undrivable by 2× (checked at fine
resolution — no valid `grip_use` anywhere from stalled to spun), and even
the single-axis TV-differential degrades substantially. Only the full
four-wheel allocator holds its limit essentially flat across the whole
range. Episode 12's own mechanism (F76/F77) was checked at the power-implied
demand levels directly (no re-publish needed — it already holds through
12,000 N) rather than swept through the same {1×,1.5×,2×} machinery, since
it turned out not to have a power axis at all (below).

Two more real defects, found the same way as Phase 1's — by not accepting a
surprising number — before anything got written up: a plan/clip mismatch
that produced a false "more power makes an open diff spin" result before
the plan and the clip were made to agree on what the car could actually do,
and a bisection floor (`GU_LO=0.70`) that was silently reporting "no valid
lap" for configurations whose real limit just sat below it.

Episode 15 now has both things it needed: a design-sensitivity baseline
that varies with power (F100) and TV's own worth as a function of the same
curve (F101), with a mechanistic account of why. What follows is the
original plan, kept for the record of what was intended.

**Revised on inspection: Episode 12 does not have a power level to sweep.**
The original plan above treated Ep 12 like Ep 13 — re-run at {1×,1.5×,2×} —
without checking that Ep 12 is a steady-state, fixed-corner mechanism study
(`A_Y=9.0`, exit speed and yaw rate both fixed) that sweeps the **demanded**
force directly (`DEMAND_SWEEP`, 0–6,500 N), not a lap with an engine cap.
There is no "power level" parameter for it to vary independently of what it
already sweeps. Checked before building anything: 6,500 N covers 1× (4,500 N)
and most of 1.5× (6,750 N) but not 2× (9,000 N).

**Ep 12's actual Phase 2 task, much smaller than originally planned:** extend
`DEMAND_SWEEP`'s upper bound to comfortably clear 9,000 N and confirm F76/F77's
mechanism conclusion (the speed-coupling handling term dominates the
traction term) still holds at the higher demand. No drive model question
applies here — `probe()` never touches `drive_max`/`drive_power` at all.

**Ep 13 is where the real Phase 2 compute lives**, and it needed
`physics/driver.py`'s D-A support (built and verified above) first, since
`ep13.lap()`'s own `SpeedProfile` construction reads the module-level
`DRIVE_MAX`/`BRAKE_MAX` constants directly rather than any per-instance
override — confirmed the hard way (raising the clip alone did nothing,
because the *plan* still targeted the old cap). Re-run Ep 13's
five-configuration study at {1×, 1.5×, 2×} — both drive models, section
metric, `SpeedProfile` and `Driver` built consistently from the same
power-derived values rather than reusing `ep13.lap()`'s hardcoded wrapper.
Also apply the brake-cap fix Phase 0 confirmed (`BRAKE_MAX` raised to the
tire's demonstrated ~0.985 g, not swept — a one-time correction, not a power
axis; see §1 point 3). The specific number Episode 15 needs from this phase:
**TV's worth as a function of power** — per F43's mechanism the
corner-section gain should grow with saturation, and the curve shape tells
Episode 15 which power its comparison lives at. Ep 13's driver-preview
sensitivity check (F84) is re-run at 2× — if the preview dependence grows
with power, Episode 15's protocol must fix the driver before it compares
anything.

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
