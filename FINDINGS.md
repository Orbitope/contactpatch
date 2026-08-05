# Findings

**What this is.** The running record of what the build has actually established
— every finding, every decision, and why. It accretes; nothing is deleted, only
superseded (with a pointer to what superseded it).

**Why it exists separately from everything else.** The project has four other
places writing could go, and none of them is this:

| Where | What belongs there |
|---|---|
| `docs/` | The plans. Written before the work; reference, not journal. |
| `HANDOFF.md` | Where the build *is* and what to do next. Should stay short. |
| `docs/learning-scaffold.md` | Concept explanations, useful as reference. Its predict-then-check workflow is not in use — see the bottom of this file. |
| `episodes/` | Article drafts. The deliverable. |
| **`FINDINGS.md`** | **What is true, how we know, and what we decided.** Feeds all of the above. |

Each finding is numbered and dated so an episode draft can cite it and a later
result can contradict it on the record.

**Every number carries a provenance tag** (CLAUDE.md rule 3), so a reader can
always tell a measurement from an assumption:

| Tag | Meaning |
|---|---|
| `[MEASURED]` | Produced by our code, with the artefact and configuration named |
| `[SOURCED]` | Published data or a published correlation, with the source named |
| `[DERIVED]` | Computed from sourced values by a stated formula |
| `[ASSUMED]` | Chosen by us |

Unless a finding says otherwise, its `[MEASURED]` numbers come from
`Sedan_Pac02Tire.tir`, MF 2002 pure slip, **offsets removed, unscaled**
(`LMUY = LKY = 1`, `LFZO = 0.81`, `Fz0′ = 3,929 N`) — i.e. `tire.default_tire()`.

---

# How to read the figures

D1 writes four figures. The first two are pictorial and assume nothing; the third
is the validation ledger; the fourth is the technical card, which is denser on
purpose and is the reference artefact.

| File | What it is | For |
|---|---|---|
| `D1_slip_angle.svg` | Five actual wheels at five angles, with force arrows | Ep 1 hero |
| `D1_load_split.svg` | Two wheels squashing by different amounts, plus a car in a corner | Ep 2 hero |
| `D1_reality_check.svg` | Our numbers against published ranges | validation |
| `D1_tire_card.svg` | Three analytical charts and the reference table | reference |
| `D2_load_transfer.svg` | Three cars — braking, steady, accelerating — with contact patches sized by load | pictorial |
| `D2_invariants_card.svg` | Axle load vs acceleration, transfer vs CoG height, yaw response vs inertia | technical |
| `D3_understeer_explained.svg` | The same car cruising and at the limit, with slip angles drawn | Ep 3 hero |
| `D3_steady_state_card.svg` | Understeer curve, slip angles, gradient vs weight distribution | technical |
| `D4_response_explained.svg` | Two cars turning in frame by frame, differing only in polar moment | Ep 8 hero |
| `D4_transient_card.svg` | Step response vs the linear model, the inertia sweep, the Izz uncertainty | technical |
| `ep04/01-the-fastest-line.svg` | The corner with both solved lines and their apexes | Ep 4 hero |
| `ep04/02-line-card.svg` | Speed, road position and longitudinal force along each line | technical |
| `ep05/01-four-wheels.svg` | The same corner with four wheels, contact patches sized by load | Ep 5 hero |
| `ep05/02-load-transfer-card.svg` | Per-wheel load, the anti-roll-bar sweep vs the bicycle model's flat line, wheel-lift margin | technical |

**House rule for every figure from here on: the pictorial version comes first,
the line chart second.** A force-versus-angle plot only means something once the
reader already knows what a slip angle is, and the wheels are what teach that.
Both get made; neither replaces the other.

## The pictorial pair

**`D1_slip_angle.svg`** — five copies of the same tire carrying the same weight.
A grey dashed arrow through each shows the direction of travel, identical in
every one. The tire is rotated off it by the slip angle, drawn true to scale, with
a long centreline so a 2° angle is actually visible. The red arrow is the grip
produced, to one length scale across all five. Underneath: the angle, the force,
and what it means. The strip along the bottom plots those same five points as the
conventional curve, so the reader can see the two representations are the same
thing.

**`D1_load_split.svg`** — three rows, each two tires sharing 6 kN. The lighter
band across each tire is its contact patch, and it grows with load, because a
harder-pressed tire really does squash into a longer patch. Arrows are each
tire's peak grip; the right column totals them. Below, a plan view of a car in a
left turn shows where the uneven split comes from in the first place.

## The technical card

`diagnostics/out/D1_tire_card.svg`. Three charts and a table. Every one of them
answers a question you could ask without knowing any vehicle dynamics.

### Vocabulary, once

| Term | Symbol | Plain meaning |
|---|---|---|
| Vertical load | `Fz` | How much weight is on that tire, in newtons. Our front tire carries ~3,600 N parked, more mid-corner. |
| Slip angle | `α` | The angle between where the wheel points and where it is actually travelling. **Not skidding** — a cornering tire runs a few degrees of it constantly. It is *how* a tire makes side force: rubber in the contact patch bends sideways, and bent rubber pushes back. |
| Grip coefficient | `μ` | Side force ÷ vertical load. μ = 1.0 means the tire can push sideways as hard as the car presses down — roughly 1 g of cornering. |
| Cornering stiffness | `Cα` | How fast force builds when you first turn the wheel, in newtons per degree. Steering response. |

### Panel A — "Lateral force vs slip angle"

**The question:** point a loaded tire slightly away from where it's rolling. How
much sideways force do you get?

- **Across the bottom:** how far off you're pointed, 0 to 20 degrees.
- **Up the side:** how much sideways force that produces, in newtons.
- **Seven curves:** the same tire with seven different weights pressing it down,
  1 kN at the bottom to 9 kN at the top.

Read any single curve left to right and you get the whole story of a tire. At
zero it makes nothing. Force climbs steeply — *that initial steepness is your
steering response*. It bends over, reaches a peak (the dot), and then **falls**.

The falloff is the part that surprises people: past the dot you are asking for
more and receiving less. There is no threshold you cross, no moment where grip
"runs out." There is a hill, and you want to sit near the top of it.

The **dashed vertical line at 12°** is a boundary we imposed on ourselves: past
it we don't trust the model, because the tire was probably never tested that far.
Notice the 7 kN and 9 kN dots sit beyond it — see finding F8.

*This is the Episode 1 figure.*

### Panel B — "Peak μ falls as load rises"

**The question:** press a tire down twice as hard. Do you get twice the grip?

Take just the seven dots from panel A. For each, divide the peak force by the
weight that was on the tire. That ratio is μ, and plotting it against load gives
this line.

If tires were simple, the line would be **flat** — twice the load, twice the
grip, same ratio. It isn't flat. It slopes down, and hard: 1.18 at 1 kN, 0.82 at
9 kN. Nine times the load buys about six times the force.

The two teal dashed lines mark where our actual car's front and rear tires sit at
rest, so you can see which part of this line the car lives on.

*This one chart is the reason most of the rest of the series exists.* See F1.

### Panel C — "Two tires sharing 6 kN"

**The question:** panel B says overloading a tire is wasteful. What does that
cost, concretely?

Two tires, 6 kN of weight between them. Slide load from one onto the other and
add up what the pair can produce.

- **Across the bottom:** how much load you moved across, 0 to 2,500 N.
- **Up the side:** the two tires' peak forces added together.
- **The three dots:** an even 3+3 split, then 4+2, then 5+1.

Even wins. 4+2 costs 1.4% of the pair's grip; 5+1 costs 5.6%. The tire you
overloaded never repays what the unloaded one gave up.

The curve's shape is not arbitrary. Because μ falls almost perfectly linearly
with load (panel B), the pair's total force works out to depend on the *sum of
the squares* of the two loads — and for a fixed total, a sum of squares is
smallest when the two are equal. That is why the penalty is a parabola: gentle
at first, then accelerating.

And this is not an abstract exercise. Cornering **is** moving rightward along
this curve — that's what weight transfer does to your outside and inside tires.

*This is the Episode 2 figure, and Episode 2 is the keystone of the series.*

### The table

Not physics — validation. The orange numbers are what our code computes; the grey
numbers beside each are what an earlier, independent script computed from the same
file. Agreement means we are turning the formula's knobs correctly. It says
nothing about whether the tire is any good; the charts say that.

---

# Findings

## Session 1 — tire model · 2026-07-25

Evidence for all of these: `diagnostics/out/D1_report.json`, 60/60 checks.

### F1 · Grip gets worse the harder you press. **Keystone.**
At 1 kN this tire produces 1.18 g of side force; at 9 kN, 0.82 g. `dμ/dFz` =
−0.0459 per kN, and for the offset-free tire that is exactly `PDY2/Fz0'` — a
single fitted coefficient.

**Why it matters:** this is the root of nearly every interesting claim the series
will make. Weight transfer costs grip *because of this*. Low centres of gravity
are good *because of this*. Anti-roll bars change handling balance *because of
this*. Spreading tire workload is the right control objective *because of this*.
Remove load sensitivity and most of the subject matter evaporates.

**Source:** `[MEASURED]` — D1 `load_sensitivity_negative_and_sane`, project tire.
`PDY2 = -0.18033` is a fitted coefficient of the .tir file `[SOURCED]`.

**Lands in:** Ep 2 (keystone), and structurally in Ep 3, 5, 7, 12, 13.

### F2 · Sharing load evenly between two tires maximises their combined grip, and the penalty for unevenness is quadratic.
6 kN split evenly gives 6,549 N of combined peak lateral force. Split 4+2 gives
6,457 N (−1.4%); 5+1 gives 6,182 N (−5.6%).

**Why it matters:** it converts F1 from a curve into a cost. It also explains
*why* the penalty accelerates — total grip depends on the sum of squared loads,
minimised at an even split — which is a cleaner mechanism than "grip falls off."

**Source:** `[MEASURED]` — D1 `even_split_makes_most_grip`. The 6 kN total and
the three splits are round numbers chosen for the figure `[ASSUMED]`.

**Lands in:** Ep 2.

### F3 · A tire makes its best grip while already sliding, and the angle grows with load.
Peak at 10.3° of slip at typical load; 9.7° at 1 kN rising to 14.3° at 9 kN.

**Why it matters:** the Ep 1 payoff line. It also means "grip" and "not sliding"
are different things, which is the intuition the whole series has to install
before anything else lands.

**Source:** `[MEASURED]` — D1 `slip_at_peak_increases_with_load`, project tire.

**Lands in:** Ep 1.

### F4 · The MF 2002 implementation is correct.
Reproduces an independently computed reference table across seven loads: peak μ
to 0.1%, peak force to 0.02%, cornering stiffness to 0.22%.

**Source:** `[MEASURED]` vs `[SOURCED]` — D1 section 1, 35 checks, comparing
`as_shipped_tire()` against the table in `docs/vehicle-reference-parameters.md`
§3.2. Note this row uses the **as-shipped** tire, not the project default.

**Why it matters:** it is the only reason to believe anything else in this file.
The reference was computed by a different script at a different time from the
same coefficients, so agreement is a genuine cross-check rather than a tautology.

### F5 · The reference table's "slip at peak" column omitted one formula term.
Standard MF 2002 puts the peak up to 1.0° below the reference (14.10° vs 15.1° at
9 kN). Cause: the `(1 − PEY3·sgn αy)` curvature factor. That term moves *where*
the peak sits and never *how high* — which is precisely why only that one column
disagreed while the other three matched to the digit. Dropping it reproduces the
reference to 0.04°.

**Why it matters:** a disagreement with a documented reference is either a bug or
an explanation, and leaving it as "close enough" would have been neither.
`MF02Tire(ey_camber_asymmetry=False)` exists so the explanation is a *test*.

**Caution carried forward:** this file's `PEY3 = −9.99` and `PEY4 = −760` are
degenerate camber-curvature coefficients, almost certainly fitted to data with no
camber sweep. **Do not model camber with them.**

### F6 · The tire as shipped pulls to one side. Removed — see D1.
Peak μ 1.012 cornering one way vs 1.086 the other, a 7.4% split, plus 37 N of
lateral force at zero slip angle. Cause: conicity (the tire is slightly conical,
so it rolls toward the apex like a paper cup) and ply steer (the belt plies are
laid at a bias angle, so the tread band shears sideways through the contact
patch). Both are per-sample manufacturing artefacts. The file declares
`TYRESIDE = LEFT` — it describes a tire mounted on one side of a car.

**Why it matters:** 7.4% is wider than the entire 0.95–1.10 g plausibility band
for this car's max lateral acceleration. Left unaddressed it would have corrupted
Ep 3's limit-grip number and every left/right comparison from Ep 5 onward.

### F7 · As shipped, the tire produces thrust at zero slip ratio.
`Fx(κ=0) = +108 N`, from the `PHX1` horizontal shift — 0.032 g of free
acceleration over four tires. Removed along with the other offsets (D1), but the
**modelling rule survives for any rescaled or re-sourced tire**: coasting must be
modelled by solving for the κ that delivers the demanded `Fx`, never by setting
`κ = 0`.

### F8 · At high load, the tire's best grip lies outside the region we trust.
At 7 kN and 9 kN the lateral peak occurs at 12.3° and 14.3° of slip — beyond our
self-imposed ±12° bound. Peak grip at those loads is therefore not reachable
inside honest territory.

**Why it matters:** RV-1's most loaded corner reaches ~6 kN, where the peak is
still inside — so this is not a problem today. It becomes one if a stiff,
high-transfer setup in the Season 2 sweeps pushes a corner past 7 kN. **Any sweep
that does needs its envelope occupancy checked before its lap time is believed.**

### F9 · `docs/vehicle-reference-parameters.md` §5 contradicts its own §3.2.
§5 states the D1 assertion as "slip at peak 5–10°". Its own §3.2 table lists
13.1° at 7 kN and 15.1° at 9 kN. The table is right; the assertion text is not.
D1 asserts 5–16°. The doc is left unedited (it is reference material) — this
entry is the correction of record.

## Session 2 — bicycle model · 2026-07-25

Evidence: `diagnostics/out/D2_report.json` (21/21) and `D3_report.json` (14/14).
`[MEASURED]` numbers are the bicycle model on the project tire unless stated.

### F10 · Braking moves 1.2 kN onto the front axle, and the formula is exact.
At 0.5 g of braking the front axle goes from 7.20 to 8.42 kN and the rear from
6.14 to 4.92 kN — 17% more on the front, and the two always sum to the car's
13.34 kN. Transfer is `m·a_x·h/L` with no fitting parameter, so it is exactly
linear in both acceleration and centre-of-gravity height.

**Source:** `[MEASURED]` — D2 `braking_transfers_load_forward`,
`transfer_proportional_to_com_height`. Formula `[DERIVED]`, standard.

**Why it matters:** combined with F1 (grip falls with load) this is the whole
mechanism by which weight transfer costs grip. It is also the quantitative case
for a low car: double the centre-of-gravity height, double the transfer.

**Lands in:** Ep 3, and structurally in Ep 5, 7, 8.

### F11 · The bicycle model is nearly neutral, and that is the one real model limitation. **Corrected — see F17.**
Understeer gradient **K = 0.187 deg/g** (R² =
0.9971 over the ±0.5 g fit window), against 1.8–5.5 for a real
sports car. Front axle needs 3.16 deg of slip per g, rear needs 3.01; understeer
is the difference between two nearly equal numbers — measured
0.19 against 0.15 analytic from
`W_f/C_f − W_r/C_r`.

**Cause.** A bicycle model has no track width, so no lateral load transfer, so
none of the grip loss that gives a real car most of its understeer. It also has
no compliance steer, no aligning torque, no roll camber and no roll steer; the
Bundorf decomposition attributes roughly 3 of a real car's 4.1 deg/g to exactly
those. **This is the model being honest, not wrong**, and D3 records it as an
accepted exception rather than widening a tolerance.

**Source:** `[MEASURED]` — D3 `understeer_gradient_below_a_real_car`,
`measured_K_matches_the_textbook_formula`. Bands `[SOURCED]` §4.

**Everything else about the curve is right.** Steering demand rises monotonically
to 99% of the grip limit, and steepens to
about 13x the linear-range slope — the "distinct upturn" the reference expects. Front slip exceeds rear throughout.
Sideslip crosses zero at 0.71 g. **An earlier version of this finding claimed the
upturn was missing and that the car showed terminal oversteer, and blamed both on
the missing lateral load transfer. Both were artefacts of my test protocol, not
the model — see F17.** Only the magnitude of K is a real limitation.

**How precise is that?** Across the input uncertainty the reference sheet itself
documents — front mass fraction 0.53–0.56, driver mass ±20 kg, CoM height 457–463
mm — K spans **0.14 to 0.27 deg/g**. So it is a one-decimal number. Almost all of
that spread is the weight-distribution range; driver mass and CoM height together
move it by less than 0.02. Quoting three decimals implies a confidence the inputs
do not support, however many digits the solver returns.

**Lands in:** Ep 3 (the measurement), Ep 5 (the crack — how much of the K gap does
the double-track model close?).

### F12 · Cornering slows a car down with no brakes and no drag.
At 0.76 g on the skidpad the car decelerates at 0.40 m/s² (0.040 g). The front
tire's grip acts along the steered wheel, so part of it points backwards.

**Source:** `[MEASURED]` — D2 `a_steered_front_tire_slows_the_car`.

**Why it matters:** it is why a real skidpad needs throttle to hold speed, it is
why integrating forward from a steady-state trim drifts (the drift is physics,
not solver error), and via load transfer it is the direct cause of F11's
symptom 3.

### F13 · Maximum lateral acceleration 1.073 g, reached inside the trusted envelope.
The hardest sustainable corner runs 9.4° of front slip against our imposed 12°
bound, so the limit is a real grip limit rather than the model being
extrapolated past where the tire was fitted.

**Source:** `[MEASURED]` — D3 `max_lateral_acceleration_in_band`,
`limit_reached_inside_the_slip_envelope`. **Caution:** the 0.95–1.10 g band it
is checked against was itself derived from this tire file, so this is a
consistency check and not outside validation.

### F14 · A load-transfer sign bug, found by D3 and fixed.
`derivatives()` was computing longitudinal acceleration as `dv_x/dt` — which
includes the centripetal term `v_y·r` — and feeding that to load transfer. Load
transfer is caused by the centre of mass's acceleration along the body axis,
which is `Fx/m`; the two differ by a kinematic term that is not a force.

**Effect while wrong:** a hard corner appeared to decelerate about three times
harder than it does, shifting enough load forward to invert the terminal
balance. Maximum lateral acceleration read 1.04 g instead of 1.073, and the
understeer curve turned over at 0.86 g with a *decreasing* steer angle that
looked like a solver branch failure.

**How it surfaced:** D3's `steer_increases_monotonically` check failed. It would
not have been visible in any single number — only in the shape of a swept curve.

**Source:** `[MEASURED]` — the fix is asserted by D2
`trim_and_integrator_agree_on_longitudinal_acceleration`. The same correction
applies to `a_y`, which is now the accelerometer reading `Fy/m` rather than
`dv_y/dt`.

**Carry forward:** the double-track model's *lateral* load transfer has exactly
the same trap — it must use `Fy/m`, not `dv_y/dt`.

### F15 · The car is neutral at 50.4% front weight, and the sweep is resolvable.
K rises monotonically from −0.369 deg/g at 42% front to +0.507 at 62%: a 0.88
deg/g spread against the 0.2 deg/g real-world measurement noise floor. Neutral
lands at 50.4% front — essentially 50:50, which is what identical tires at both
ends gives you.

**Source:** `[MEASURED]` — D3 `K_monotone_in_weight_distribution`. Noise floor
`[SOURCED]` §4.

**Why it matters:** real cars are *not* neutral at 50:50, and the gap between
that and this result is the same missing mechanism as F11. It also means the
Season 2 weight-distribution sweep will produce resolvable trends even though
the absolute values are not road-car-like — trend direction is the product
(CLAUDE.md rule 6).

### F16 · Doubling yaw inertia doubles the response time, and leaves steady state untouched.
90% yaw-rate rise time goes from 197 ms to 397 ms; the steady-state trim is
bit-identical. Rise time at nominal inertia sits inside the 0.08–0.30 s band.

**Source:** `[MEASURED]` — D2 `higher_izz_responds_more_slowly`,
`steady_state_independent_of_izz`. Band `[SOURCED]` §4.

**Lands in:** Ep 8, where yaw inertia is the axis independent of weight
distribution.


### F17 · The skidpad protocol changes the measured balance by more than the effect being measured. **Correction to F11.**
Same car, same tires, same model — only the throttle differs:

| | K (deg/g) | max lateral | steer peaks at | limit upturn |
|---|---|---|---|---|
| **Holding speed** (SAE J266, now the default) | **0.187** | 1.032 g | 98% of limit | steep upturn |
| Coasting (what I originally built) | 0.159 | 1.073 g | 86% of limit | none |

**Mechanism.** A steered front tire's grip points partly rearward (F12), so a
coasting car decelerates at ~0.04 g. That shifts load forward, pushing the
front/rear load ratio above the 1.174 the yaw balance demands, so the rear runs
proportionally nearer its peak and gives up first. A real constant-radius test
holds speed, the net longitudinal force is zero, and none of this happens.

**What it cost.** The coasting protocol produced two false findings — "no limit
upturn" and "terminal oversteer" — which I attributed to the bicycle model's
missing lateral load transfer. Both vanished when the protocol was corrected. **A
33% swing in the headline number came from a modelling choice I made in passing
and did not flag as a choice.**

**How it surfaced.** Not from a failing check — the coasting results passed a
diagnostic I had written around them. It surfaced from being asked whether the
findings should be fixed rather than accepted, and testing the attribution
instead of assuming it.

**Source:** `[MEASURED]` — D3 `protocol_sensitivity_is_recorded`, D2
`the_skidpad_protocol_changes_the_answer`. Protocol `[SOURCED]` SAE J266,
constant speed.

**Carried forward:** `trim_skidpad(hold_speed=True)` is the default and D3
reports both. The grip cost of the balancing drive force is **not** modelled
(combined slip, O2); `SkidpadPoint.drive_force_fraction` reports how much is being
got away with — 6.1% of lateral force at worst here. **Any test protocol is a
modelling choice and gets recorded as one.**


### F18 · The load transfer the bicycle model omits is about ten times the one it models, and its grip cost is now estimated.
Front-to-rear transfer in a corner is small — around 60 N at the limit. Side-to-side
transfer, which needs a track width and so cannot exist in this model, is
**2,316 N on the front axle** at 1.05 g.
That would split the front axle 5,917 N outside /
1,285 N inside instead of 3,601 N
each, and cost it an estimated **6.4%** of its
peak lateral force. The rear loses **5.4%**.

**Source:** `[DERIVED]` — computed in D3 from `m·a_y·h/t` and the tire's own load
sensitivity. **Not simulated**: the bicycle model cannot produce these numbers.
Assumes the roll-stiffness split follows the weight distribution, which is the
assumption `double_track.py` exists to replace.

**Why it matters.** It is Episode 2's arithmetic applied to a real corner, and it
sizes the Episode 5 effect before we build it. The two percentages differ, so the
balance moves — and that difference is most of the understeer F11 is not
producing. It also answers the obvious question about the current model directly:
we know the front/rear split at every point on the skidpad, and we do **not** know
the left/right split, because there is no left and right.

**Prediction for Ep 5:** the double-track model should raise K materially and
should not need any new tire physics to do it — just a track width and the load
sensitivity we already have.

### F19 · An ISO-to-screen sign error drew two figures with the wheels turned the wrong way.
`physics.schema` is ISO 8855: positive steer is **left**. SVG's positive
`rotate()` is **clockwise**, which on a nose-up car is **right**. Passing a
physics angle straight into a drawing call renders a plausible, wrong picture and
raises nothing.

**Source:** caught by review, not by a test. Fixed with named converters
`viz.diagram.screen_deg` / `screen_dx` that every figure now goes through.

**Why it is worth recording:** the numbers were right the whole time — D2's
mirror-symmetry check passed at 0.2% throughout. Only the picture was wrong, and
the picture is the deliverable. A figure is an output like any other and can be
wrong while every assertion passes.


### F20 · Audit of D1-D3 against closed-form theory. **The model's linear structure is exactly right.**
The linear bicycle model has exact solutions that appear nowhere in this
codebase, so agreeing with them is not the tautology an internal consistency
check is. Measured against them:

| Quantity | Result |
|---|---|
| Yaw-rate gain `r/δ` vs `V/(L + K·V²)` | matches to **< 0.01%** at 6–20 m/s |
| Sideslip `β` vs `b/R − (m_r/C_r)·V²/R` | matches to **< 0.002 mrad** |
| Understeer gradient as the fit window shrinks | 0.175 → 0.154 → 0.152 → 0.151 → **0.151** against 0.1505 analytic |
| Neutral-steer front mass fraction | 0.4999, where analytic K = −0.0002 deg/g |

**Source:** `[MEASURED]` vs `[DERIVED]` — now permanent D3 checks
(`yaw_rate_gain_matches_linear_theory`, `sideslip_matches_linear_theory`,
`measured_K_converges_to_the_textbook_formula`), not a one-off script.

**What it replaced.** D3 previously compared measured K against the analytic
formula at a 0.15 deg/g tolerance and passed with a 40% gap. That check
tolerated almost anything. Convergence has teeth: the error must fall
monotonically to under 1% as the window shrinks.

### F21 · Three real defects the audit found, none of which any existing check would have caught.

**1. The envelope logger reported zero slip ratio.** `wheel_log()` hardcoded
`kappa = 0`, and `Backend.envelope_violated()` defaults to that accessor — so
slip-ratio violations were invisible through the documented API. Envelope
occupancy is what decides whether a lap time counts at all (non-negotiable #1),
so this would have made the statistic look clean while measuring two channels out
of three. It would have surfaced first in Season 3's D6, as suspiciously good
honesty numbers.

**2. The constant-speed trim did not hold speed.** "Holding speed" means
`dv_x/dt = 0`, and `dv_x/dt = Fx/m + v_y·r`. I had forced `Fx/m = 0`, which
leaves `dv_x/dt = v_y·r`. In a circle with sideslip the centripetal acceleration
has a small component along the body x-axis, so the correct condition is
`a_x = −v_y·r`, not zero. **Consequence:** the "steady state" drifted — 0.19% off
the commanded radius and 2.7° of heading over a single lap. Now exact: radius
error 0.001%, radius spread 3×10⁻¹¹ m, zero speed drift.

**3. Nothing tested the pose integration at all.** `x`, `y` and `heading` were
integrated and fed no assertion anywhere. If they had been wrong, every
trajectory figure and every lap time from Episode 4 on would have been wrong
silently. D2 now drives a full lap and fits a circle to the path.

**The pattern worth naming.** Every one of these passed the existing checks
because the checks were written around what the code does. What caught them was
comparing against something written independently — closed-form theory, or a
property the code was never built to satisfy. **Internal consistency is cheap and
proves little.** D2 and D3 now carry 4 closed-form and 7 instrumentation checks
that no amount of self-consistent wrongness would pass.


## Session 3 — transient response · 2026-07-25

Evidence: `diagnostics/out/D4_report.json` (13/13).

### F22 · The car answers the wheel in about 194 ms, and the linear model predicts it exactly.
A 1° step at 20 m/s: yaw
rate reaches 90% of final in 194 ms and settles in
0.3 s. The linear bicycle model, integrated exactly, gives
198 ms — a
2% match, with
ωn = 10.0 rad/s and ζ = 0.98. Rise time is inside the
published 80–300 ms band.

**Source:** `[MEASURED]` vs `[DERIVED]` — D4 `rise_time_matches_the_linear_model`.
Band `[ASSUMED]` §4.

**A trap worth recording.** The first version compared against the *textbook*
second-order step-response formulas and disagreed by 65%, which looked like a
model bug. The yaw-rate transfer function has a **numerator zero** at
`s = −Cr·L/(a·m·V)` that those formulas assume away; it speeds the rise up. The
fix was to integrate the linear state space instead of using a closed-form
approximation to it. **An external reference is only external if it is the right
reference.**

### F23 · Our car barely overshoots, and that is another named gap.
Overshoot is **0.8%** against a published 5–40% expectation.
Damping ratio 0.98 — practically critically damped. The linear model
agrees, so it is not a solver artefact.

**Missing:** tire relaxation length (a tire needs roughly half a wheel revolution
to build side force; we model it as instantaneous), suspension compliance and
damping, and steering-system dynamics. All add phase lag, and phase lag is what
produces overshoot.

**Source:** `[MEASURED]` — D4 `overshoot_is_far_below_the_published_band`,
recorded as an accepted exception with a reason rather than a widened band.

**Same family as F11.** The model is more idealised than the car in a nameable
way. **Do not quote our overshoot as a property of a GR86.** Episode 8 should
rest on the direction and relative size of the inertia effect, not its absolute
value.

### F24 · Polar moment changes the journey, never the destination.
Across the documented 0.75–1.40× inertia range, rise time goes
149 → 279 ms
while the final yaw rate is constant to a few parts in ten thousand. Overshoot
falls slightly with inertia — the direction the reference sheet states.

**Source:** `[MEASURED]` — D4, four checks.

**Why it matters:** it is what makes yaw inertia an axis genuinely independent of
weight distribution, so Episode 8 can hold one fixed and sweep the other.

**Precision:** yaw inertia is the least certain number in the car — the three
published correlations bracket 1719–2346 kg·m², moving rise time over
172–234 ms.
Report to the nearest 10 ms.

### F25 · I almost published a wrong correction to the reference sheet.
Working from the incomplete second-order theory above, I wrote a D4 note stating
that §5 had the overshoot-vs-inertia direction backwards, and a plain-English
finding to match. Both were wrong: with the correct reference the measured
direction agrees with the sheet.

**What caught it:** running the comparison before trusting the derivation. The
wrong note would have passed every check, because the check was the derivation.

**Carried forward:** a correction to a source is a claim like any other and needs
the same standard of evidence as a finding — arguably more, since it invites the
reader to distrust the reference.


## Session 4 — optimal control · 2026-07-26

Evidence: `experiments/ep04/out/results.json`, `tests/test_optimal_control.py`
(16 checks), `tests/test_casadi_tire.py` (6 checks).

### F26 · The optimal apex moves later when there is more straight to come. **The Episode 4 result.**
Same 40 m corner, same 32 m/s entry, same car. With 30 m of exit the
minimum-time apex sits **49%**
through the corner; with 260 m of exit, **55%**
— a shift of about **6 percentage points**, roughly 4 m along a 63 m arc.

It pays for the later apex with corner speed: minimum speed drops
24.6 → 24.3 m/s.
In exchange, speed at the finish goes 27.5 →
46.5 m/s.

**Source:** `[MEASURED]` — distance-domain collocation, CasADi/IPOPT. Corner
geometry and entry speed `[ASSUMED]`.

**Robustness:** grid refinement at 140 / 200 / 280 nodes gives
+5.5 / +6.2 /
+5.9 points. The shift is not a
discretisation artefact. Report it as "about 6 points", not 6.2.

**Caveat on record:** the long-exit solve converged cleanly; the short-exit solve
hit the 2000-iteration limit with its objective stable to 1 part in 10⁵ and
constraint violation 2e-4 m. Converged in practice, not a clean exit.

**Why it matters:** the geometric racing line is optimal for a corner with
nothing after it, and real corners always have something after them. The fast
line is not a shape.

### F27 · The solver discovered trail braking without being told about it.
Braking continues past turn-in in both solves — brake release at
83 m and
73 m, with the corner beginning at 70 m.
The long-exit line releases 10 m earlier, trading turn-in help for getting on the
power sooner.

**Source:** `[MEASURED]` — `brake_release_s_m` in the Ep 4 results.

**Mechanism:** braking transfers load forward (F10), more front load is more
front grip (F1), so carrying the brakes into the corner buys front-end bite. The
friction ellipse (D9) charges for it, and the solver weighs the trade.

**Why it matters more than a demonstration would.** The original plan was to
script three braking strategies and report which won. A solver given no technique
that rediscovers one is stronger evidence than a comparison designed to have a
winner. **This is also the first result that turns on the ellipse's assumed
shape** — that a tire trades braking for cornering is certain; that it trades
along an ellipse is a stand-in for coefficients this file lacks (O2 was closed
pragmatically, not solved).

### F28 · One set of tire formulas, two evaluation backends.
`physics/mathkit.py` supplies a numpy or CasADi namespace; `physics/tire.py` is
written against it. `tests/test_casadi_tire.py` asserts the two agree to 1e-6 N
across ±15° of slip, ±0.3 slip ratio and 300–9500 N of load.

**Source:** `[MEASURED]` — the differential test.

**Why:** the alternative was a second tire model written in CasADi. An optimiser
finds and exploits any difference between two implementations, and the result
looks like a finding rather than a bug. Given how many defects this project has
already traced to two things drifting apart, a duplicated tire model was not a
risk worth taking.

**Two deliberate differences, both bounded by the test.** CasADi's `sign()`
returns 0 at exactly 0, which kills the Ey curvature term instead of picking a
branch and leaves the solver on a discontinuity — replaced by a steep `tanh`.
And the friction ellipse's `sqrt(1 - used²)` has an infinite derivative at
saturation, which is a NaN in the Jacobian the first time an optimiser asks a
fully-braked tire to corner — the radicand is now floored at 1e-6, capping
lateral force at 0.1% of pure slip there rather than 0.


## Session 5 — the double-track model · 2026-07-26

Evidence: `diagnostics/out/D5_report.json` (19/19),
`experiments/ep05/out/results.json`.

### F29 · Lateral load transfer is NOT where the understeer gap came from. **Correction to F11.**
Adding lateral load transfer moves the understeer gradient
**0.19 → 0.22 deg/g** — essentially
unchanged, and slightly higher.

*(Originally recorded as 0.19 → 0.17, unchanged and slightly **lower**. The sign of
that 0.03 deg/g wobble was an artefact of the yaw-moment defect corrected in F73;
re-measured after the fix it goes the other way. **This finding's conclusion is
untouched** — load transfer is still not where the understeer gap came from, and
0.22 against a real car's 4.1 is still about 5% of it.)* Both axles lose grip to transfer, and at a 55%
front roll share on a 54%-front car the two losses nearly cancel, the same
cancellation that made the cornering compliances nearly equal in F11.

**F11 attributed the gap to the road-car band to missing lateral load transfer
plus missing suspension effects. The first half was wrong.** The remaining gap is
compliance steer, roll camber, roll steer and aligning torque — the Bundorf terms,
which a published decomposition puts at roughly 3 of a real car's 4.1 deg/g.

**Source:** `[MEASURED]` — D5
`lateral_load_transfer_is_not_where_the_understeer_gap_came_from`.

**Why it matters:** it retires the assumption that Episode 5 would close the gap,
and names what actually would. Any future claim that this model understeers like a
real car needs those terms, not a wider track.

### F30 · The bicycle model is blind to an anti-roll bar, not merely approximate.
Sweeping the front share of roll stiffness across the documented 0.40–0.70 range
moves K from **+0.02 to
+0.32 deg/g** in the four-wheel
model. The identical sweep through the two-wheel model moves it by
**0e+00 deg/g — exactly zero.**

**Source:** `[MEASURED]` — D5 `the_bicycle_model_cannot_see_the_bar_at_all`,
`stiffer_front_bar_adds_understeer`.

**Why it matters, and it is the Episode 5 result.** An approximate answer can
carry error bars. A blind one returns a confident number that cannot move, and
nothing in the output says the input was ignored. Run Season 2's setup sweeps on
the bicycle model and you get a clean flat line reading "roll stiffness
distribution has no effect on handling balance" — a statement about the model
indistinguishable in form from a statement about cars.

### F31 · Our anti-roll bar authority is weak, and that is a real limitation.
The full roll-share range buys only
0.31 deg/g, about **1.5× the 0.2 deg/g floor** at
which a professional test programme can distinguish two builds. A single realistic
bar change of 0.05 roll share moves K by ~0.05 deg/g — **below that floor, and
not reportable.**

**Source:** `[MEASURED]` — D5 `our_anti_roll_bar_authority_is_weaker_than_a_real_car_s`.
Noise floor `[SOURCED]` §4.

**Two reasons, and the second is the interesting one.** We model all lateral
transfer as elastic, which if anything *overstates* bar authority — there is a
geometric component acting through the roll centres that does not follow roll
stiffness. And a real bar acts partly through roll camber and roll steer, changing
the tires' effective slip angles rather than only their loads, and we model
neither. Same missing terms as F29.

**Carried forward: treat Season 2's roll-stiffness sweeps as directionally right
and quantitatively weak.** Rank ordering is usable; magnitudes are not.

### F32 · The four-wheel model reduces to the two-wheel model in the limit where it must.
With the centre of gravity lowered to the road, lateral transfer vanishes and the
four-wheel model reproduces the two-wheel model's understeer gradient to **0.6%**
and its grip limit to **0.00%**.

**Source:** `[MEASURED]` — D5 `flat_car_reproduces_the_bicycle_gradient`,
`flat_car_reproduces_the_bicycle_grip_limit`.

**Why it counts.** Two independently written models agreeing in a limit neither
was written to satisfy — the class of check CLAUDE.md rule 11 asks for. The 0.6%
residual is the per-wheel slip-angle difference from yaw rate across the track,
which the bicycle model averages away and which does not vanish with height.

### F33 · F18's prediction landed.
Episode 3 estimated, from static geometry and the tire's load sensitivity alone —
with a model that could not simulate the effect — that lateral load transfer would
cost the front axle ~6% of its grip. Measured whole-car loss:
**6%** (1.03 → 0.97 g).

At the limit the outside pair carries **3.8×**
the inside pair, and the least-loaded wheel is down to
1.37 kN. Wheel lift would occur at
1.61 g against a static stability factor of
1.63 — correctly just below, since SSF is the
rigid-body threshold no elastic distribution can beat.

**Source:** `[MEASURED]` — D5 `lateral_transfer_costs_grip`,
`measured_transfer_matches_the_closed_form`, `F18_predicted_this_before_the_model_existed`.

---

## Session 6 — front-wheel drive vs rear-wheel drive · 2026-07-26

Evidence: `experiments/ep06/out/results.json`, `traces.npz`. Four minimum-time
solves — both drivetrains × both differential bounds — on the long-exit corner,
160 nodes, entry 32 m/s, four-wheel model.

### F34 · Rear-wheel drive is faster out of a corner, and the differential decides by how much.

| | Open diff | Ideal diff | a perfect diff is worth |
|---|---|---|---|
| Rear-wheel drive | 12.15 s | 12.09 s | 0.07 s |
| Front-wheel drive | 12.31 s | 12.19 s | **0.13 s** |
| **front drive costs** | **+0.16 s** | **+0.10 s** | |

**The conclusion holds under both bounds; the magnitude does not.**

**Read the bounds the right way round.** An earlier version of this entry treated
the ideal-diff +0.100 s as the answer and the open-diff +0.163 s as an inflated
alternative. That is backwards: an *ideal* differential is the most generous
assumption available to front drive, so **+0.100 s is a lower bound on the penalty,
not a best estimate.** A real limited-slip differential sits between the bounds, so
the honest statement is **"front drive costs at least 0.10 s here, and up to
0.16 s with no LSD at all."** Both numbers are front drive's *best* and *worst*
case, and the reference car's factory LSD puts the truth in between.

**A perfect differential is worth roughly twice as much to front drive as to rear
drive** (0.13 s vs 0.07 s). The front-drive car's driven wheels are also its
steering wheels and are closer to saturation, so recovered traction is worth more
to the axle with less to spare. This is Episode 12's opening.

Both cars pick the **same line** — apex 53.33% through the corner in both
ideal-diff solves, paths never more than 12 cm apart. The difference is entirely in
what the tires are asked to do, not where the car goes. See F42.

**Source:** `[MEASURED]` — `experiments/ep06/run.py`, `time_delta_s_open`,
`time_delta_s_ideal`, `diff_worth_s_rwd`, `diff_worth_s_fwd`.

**Precision:** quoted to 0.01 s. The differential assumption alone moves the
answer by 0.06 s, which is larger than any digit beyond that, and the friction
ellipse is a placeholder (D9). Treat the rank ordering as the result.

### F35 · An open differential binds mid-corner, not on the exit straight. **Corrects a figure caption.**
The point at which an open differential costs the driven axle the most total
drive force is **19 m into the corner** for rear drive and **49 m in** for front
drive — a peak shortfall of **1.4 kN** and **1.6 kN** of axle force
respectively. Averaged over the exit straight the shortfall is **0.00 kN**: out
there the car is level, both driven wheels can take plenty, and the *engine* is
the binding constraint instead.

This is obvious once stated — the inside wheel is unloaded by cornering, so that
is where equal-torque splitting hurts — and it was not what the figure originally
said. The first version of `differential_figure` sampled the station where drive
force peaks on the exit straight, so both panels read 4.50 kN and the picture
silently contradicted its own caption.

Mean shortfall through the corner is **0.38 kN** (rear drive) and **0.76 kN**
(front drive) — twice as much, which is the mechanism behind F34's asymmetry.

**Source:** `[MEASURED]` — `traces.npz`, ideal-minus-open axle force.

### F36 · Every plan-view car in the project was drawn pointing backwards. **Defect.**
The track-heading-to-screen conversion was `screen_deg(θ) - 90`, i.e. `-θ - 90`.
The correct rotation is `90 - θ`. The two differ by **exactly 180° at every
heading**, so every car drawn along a path — including the apex cars in Episode
4's published hero figure — had its nose pointing back down its own line.

**It survived review because a car body outline is nearly symmetric.** The only
tells are the small nose mark and the force arrows, and Episode 4's cars carried
no arrows. It was caught when the Episode 6 along-the-path figure put force
arrows on the wheels and the cornering forces pointed *outward*.

Fixed by adding `viz.diagram.screen_heading_deg` — a third named converter
alongside `screen_deg` and `screen_dx` — and pinning it with
`test_car_heading_rotation_points_the_nose_along_travel`, which works the
rotation geometry rather than restating the formula.

**Why it matters:** this is the third silent frame-convention defect in the
project and the first to survive into a published figure. All three were
compositions of conventions, not single-angle conversions. Rule 11's point again:
it was found by an external cross-check (do the arrows point where physics says?),
never by self-consistency.

**Source:** `[MEASURED]` — `tests/test_figures.py`, frame-conversion group.

### F37 · An anti-roll bar reduces body roll, and our sweep protocol hid that. **Corrects Episode 5.**
Episode 5's anti-roll-bar figure stated that both cars "lean by the same total
amount — that is set by mass, height and cornering force, and a bar cannot change
it." **That is true of our parameterisation and false of cars.**

The sweep varies `roll_stiffness_front_share`, which redistributes a *fixed*
total roll stiffness — the **trade** protocol, what you get by stiffening one bar
and softening the other. Bolting a bar *on* is the other protocol and the more
common one: a bar is a spring, so it raises the total and the car leans less as
well as redistributing.

Computed for RV-1 (roll gradient 5.8 deg/g on springs alone):

| Front share of roll stiffness | Bar needed | Roll gradient |
|---|---|---|
| 0.40 | 18.5 kN·m/rad, rear | 4.4 deg/g |
| 0.52 (springs only) | none | **5.8 deg/g** |
| 0.55 (nominal) | 3.8 kN·m/rad, front | 5.4 deg/g |
| 0.70 | 36.1 kN·m/rad, front | 3.6 deg/g |

**The roll angle is largest with no bar at all and falls either side**, because
any bar is extra stiffness whichever end it goes on. Non-monotonic in a knob
labelled "front stiffness", which is why the figure now says so explicitly.

The two effects are separate and **only the redistribution changes the handling
balance.** Less lean is a comfort and suspension-geometry gain.

**Source:** `[DERIVED]` — `VehicleParams.bar_rate_for_share`,
`roll_gradient_deg_per_g_with_bar`; `m·g·h/K_φ` with
`K_φ = 0.5·k·t²` per axle plus the bar. Rigid-axle, no roll-centre geometry.
Spring rates `[SOURCED anchor / ASSUMED]`.

**Why it matters:** a statement about our parameterisation was published as a
statement about cars. Rule 9's failure mode exactly — the trade-versus-add choice
was made implicitly by writing the sweep, never recorded as a protocol, and then
generalised in prose.

### F38 · The spring-only roll share corroborates the assumed one.
The documented spring rates alone give a front roll-stiffness share of
**0.522**; we assume **0.55**. The gap is exactly what a modest front bar
(3.8 kN·m/rad, 6% of total) would supply. Two numbers reached by different routes
agreeing is cheap reassurance that the assumed share is not arbitrary.

**Source:** `[DERIVED]` — `spring_only_roll_share` vs
`roll_stiffness_front_share`; `tests/test_schema_and_tire.py`.

### F39 · An unconverged min-time solve returns an objective that cannot be trusted at the 0.1–0.7% level, in either direction. **Corrects Episode 4.**

Episode 4 said of its unconverged solve: *"its objective was stable to 1 part in
10⁵ and its constraint violation was 2×10⁻⁴ m, so it is converged in every
practical sense."* **That reasoning is wrong** — "the objective has stopped
moving" measures whether the iterate stalled, not whether it reached the feasible
optimum, and the two differ by far more than 1 part in 10⁵.

**Correction to an earlier version of this entry.** It claimed unconverged solves
report a time *below* the true optimum — a systematic optimistic bias. That was
generalised from a single case and is **wrong**. Later evidence (below) shows
deviations of either sign: on the Episode 6 problem the unconverged rear-drive
times land 3 ms above and 4 ms below the cleanly converged value. The reliable
statement is that the objective is *untrustworthy*, not that it is *optimistic*.

Demonstrated on the short-exit corner, same problem three ways:

| | Time | Status |
|---|---|---|
| cold start, 110 nodes | 5.873 s | `Maximum_Iterations_Exceeded` |
| cold start, 80 nodes | 5.875 s | `Maximum_Iterations_Exceeded` |
| **warm start resampled from the 80-node answer** | **5.912 s** | **`Solve_Succeeded`** |

The cleanly converged answer is **0.65% slower**. Two independent cold runs at
different node counts agreeing with each other (5.873, 5.875) looked like
convergence evidence and was not — they were agreeing about the same bias.

**Mechanism.** IPOPT drives feasibility and optimality together. Stopping early
leaves a constraint violation, so the returned iterate is slightly infeasible and
its objective is not the optimum of the problem we posed — it is the objective of
a trajectory that does not quite obey the physics. Which side of the optimum it
lands on depends on which constraints are still violated, and is not predictable.
The magnitude is problem-dependent: 0.65% on the Episode 4 short-exit corner,
0.03% on the Episode 6 long-exit one.

Also worth recording: the code comment claimed the returned iterate's constraint
violation was bounded by `acceptable_constr_viol_tol`. **It is not.** The
rear-drive problem never reaches IPOPT's *acceptable* level at all, so that bound
never applies to it — `Maximum_Iterations_Exceeded` is not
`Solved_To_Acceptable_Level`.

**Consequence for Episode 6: none, once checked properly.** Both rear-drive solves
had hit the iteration limit while both front-drive solves converged, which is
exactly the asymmetry that could manufacture the result — so it had to be checked
rather than assumed either way. Re-solved with staged warm starts and a raised
iteration limit:

| Nodes | RWD | FWD | front drive costs | both converged |
|---|---|---|---|---|
| 100 | 12.091 s | 12.191 s | **+0.100 s** | **yes** |
| 140 | 12.094 s | 12.187 s | +0.093 s | no |
| 180 | 12.087 s | 12.185 s | +0.098 s | no |

**The penalty survives.** Spread 0.007 s across three grids against a ~0.096 s
effect, and the fully converged pair at 100 nodes gives +0.100 s. Decisively, the
unconverged rear-drive times *straddle* the converged one (+3 ms, −4 ms) instead
of sitting below it, so no one-sided bias is operating. Episode 6 now reports the
100-node grid as primary, because it is the grid on which every solve in the
comparison converges.

Episode 6's draft also contained a wrong reassurance — *"the unclean solves are
the ones that came out faster, so if anything the true rear-drive advantage is
slightly larger"* — which assumed a bias direction that does not exist. Removed.

**Fix in hand:** `solve_min_time` now resamples a warm start onto the requested
grid instead of silently ignoring one whose node count differs, which is what
makes clean convergence reachable — solve coarse, then resample up. The silent
ignore was the enabling defect. `max_iter` is now a parameter too; the rear-drive
problem never even reaches IPOPT's *acceptable* level at 2000 iterations, so the
returned iterate's constraint violation is not bounded by
`acceptable_constr_viol_tol` as the code comment implied.

**On the intermediate scare.** A first re-solve at 160 nodes with the *default*
2000-iteration limit returned rear drive at 12.110 s, making the gap look like
0.075 s and suggesting a grid dependence. Raising the limit to 8000 moved that
same solve to ~12.09 s, in line with every other grid. **The 0.075 s was an
artefact of the iteration limit, not of the mesh** — which is itself the finding
restated: an unconverged objective is not evidence about anything.

**Why it matters:** convergence status is now a gate rather than a footnote, and
`Maximum_Iterations_Exceeded` on any solve whose number is quoted means the number
does not ship until it is either converged or bracketed. Note also the shape of
the near-miss: two cold runs at 80 and 110 nodes agreeing to 2 ms *looked* like
convergence evidence and was two runs agreeing about the same artefact.

**Source:** `[MEASURED]` — `tests/test_optimal_control.py`
`test_a_warm_start_from_a_different_node_count_is_resampled_not_ignored`;
direct probe on `T.short_exit()`.

**Why it matters:** the third finding in a row (with F36, F37) where a *stated
justification* was the failure rather than the code. The code did what it said;
the sentence explaining why that was acceptable was false. Convergence status is
now a gate, not a footnote.

### F43 · The front-drive penalty is proportional to engine power, and at low power it vanishes.
The whole Episode 6 mechanism is front tires running out of grip because they are
steering *and* accelerating. So the penalty should scale with how much
acceleration there is to place — and the drive-force cap was `[ASSUMED]` at
4.5 kN, never tested. Swept:

| Drive cap | ≈ power at 30 m/s | RWD | FWD | **FWD costs** | converged |
|---|---|---|---|---|---|
| 2.5 kN | 75 kW / 101 hp | 13.279 s | 13.276 s | **no measurable difference** | no |
| **4.5 kN** | **135 kW / 181 hp** | **12.092 s** | **12.193 s** | **+0.101 s** | **yes** |
| 7.0 kN | 210 kW / 282 hp | 11.306 s | 11.493 s | **+0.187 s** | no |
| 10.0 kN | 300 kW / 402 hp | 11.002 s | 11.465 s | **+0.463 s** | no |

**Monotonic across a 4× power range, spanning 0.46 s** — four and a half times the
effect at our own assumed power level. At ~100 hp it **vanishes**: −0.003 s, far
below the 0.02 s floor the convergence uncertainty imposes. Which is what the
mechanism predicts, and the figure shows why — at 2.5 kN **no tire on either car
exceeds 63%** of its capability, so there is spare grip everywhere and it cannot
matter which pair is driven.

**Correction to an earlier version of this entry**, which reported −0.041 s at
2.5 kN and called it a sign reversal with front drive "marginally faster". That came
from a solve warm-started off a bicycle seed; restarted from the converged 100-node
answer the same case gives −0.003 s. **There is no measurable reversal — the penalty
goes to zero, it does not go negative.** Reporting a −0.04 s "gain" was also a
rule-5 violation: below the floor it is no measurable effect, never a small one.

**Convergence, per F39.** Only the 4.5 kN row has both solves converged, and it
reproduces the headline (+0.101 vs +0.100 s). The other three have an unconverged
rear-drive solve, so **individual values are not quotable.** The *trend* is: the
0.46 s span is ~6× the largest plausible convergence bias (0.08 s), it is monotonic
across four points, and it is the direction the mechanism requires. Direction and
rough magnitude are usable; the numbers are not.

**Why it matters — this is the episode's most useful result.** "Rear drive is
faster" is not a fact about drivetrains, it is a fact about drivetrains *at a given
power level*, and the conditional is doing most of the work. It also lines up with
something anyone can observe without a model: economy hatchbacks are front-drive and
nobody objects, while high-powered cars are overwhelmingly rear- or all-wheel-drive.
The model reproduces that split from the friction circle alone, with no styling,
packaging or cost argument anywhere in it — a check against the outside world of
exactly the kind CLAUDE.md rule 2 asks for, and one the code was not written toward.

**Source:** `[MEASURED]` — `experiments/ep06/run.py` power sweep, 100 nodes, ideal
differential, staged warm start, `max_iter` 8000. Drive cap is `[ASSUMED]`; the
power equivalents are `[DERIVED]` as force × 30 m/s and are indicative only, since
a real engine's force falls with speed rather than staying capped.

### F42 · The drivetrain does not change where the car goes. It changes which tires pay for it.
The strongest thing in Episode 6 is a *non*-difference. Measured between the two
ideal-differential solves:

| | Rear drive | Front drive |
|---|---|---|
| Apex position | 53.33% through the corner | **53.33%** |
| Path separation | — | max **12 cm**, mean 5 cm, on an **800 cm** road |
| Peak speed difference | — | 0.70 m/s |
| **Front tires used, exit straight** | **10%** | **61%** |
| **Rear tires used, exit straight** | **59%** | **8%** |

**The two racing lines are the same line to within the width of a hand**, and the
apexes agree to 0.01%. Meanwhile the tire workload is almost exactly inverted.

**Why, and it is not a coincidence.** Through the corner the car is grip-limited
and neither drivetrain helps it turn — both solve an identical cornering problem
and find an identical optimum. The drivetrain only starts to matter once there is
longitudinal force to place, and by then the path is already committed. So the
difference cannot show up as a different line; it can only show up as a different
*distribution of work*.

This is also why the effect is worth so little per corner (0.8% of the segment) and
so much per lap: 0.10 s compounds across every corner, and across a dozen corners
it is more than a second.

**Source:** `[MEASURED]` — `experiments/ep06/out/traces.npz`, `fwd_n − rwd_n` and
per-wheel utilisation over `s > 132.8 m`.

**Why it matters:** it is the answer to "these two figures look identical — is that
real?" It is real, it is the point, and the figures should lead with it rather than
apologise for it. It also means the overlay figure is the right hero: two lines a
reader cannot tell apart, with wheels that are obviously doing different things.

### F40 · The approach "straight" is a hard manoeuvre at the grip limit, and the busy steering there is real. **This entry replaces an earlier one that called it a defect. The earlier one was wrong.**

**What I originally claimed:** that minimising time alone leaves the steering
degenerate on the approach straight, that the observed ±10° swings were the
optimiser wandering in a flat direction, that two figures were therefore drawing
meaningless steer angles, and that the fix was a steering-rate penalty.

**Every part of that was wrong**, and two independent checks killed it.

**Check 1 — what the car is actually doing on the "straight":**

| s (m) | n (m) | steer | slip, front left | lateral accel |
|---|---|---|---|---|
| 4.0 | −0.02 | −8.6° | +8.3° | **−0.60 g** |
| 15.9 | −0.64 | +0.6° | +3.8° | **−0.86 g** |
| 23.8 | −1.58 | +13.5° | −6.7° | +0.26 g |
| 47.6 | −3.98 | +2.8° | **−12.0°** | **+0.96 g** |
| 63.5 | −2.80 | +5.8° | **−12.0°** | **1.00 g** |

It is not cruising. It pulls up to **0.86 g in the direction away from the corner**
to reach the outside edge, reverses, and is **pinned to the ±12° slip envelope from
s = 48 m — twenty-two metres before the corner nominally begins.** A manoeuvre that
reverses lateral acceleration through 1.5 g of range while at the limit requires
large steering inputs in both directions. That is what was in the trace.

**Check 2 — the failed fix, which is the cleaner argument.** Swept over
1e-4 / 1e-3 / 1e-2, a steer-rate penalty:

| Weight | Time | Convergence | Worst jump | Reversals |
|---|---|---|---|---|
| 0 | 12.0909 s | **Solve_Succeeded** | 10.9° | 4 |
| 1e-4 | 12.0917 s | iteration limit | 8.3° | 4 |
| 1e-3 | 12.0945 s | iteration limit | 7.1° | 4 |
| 1e-2 | 12.0989 s | iteration limit | 4.8° | 4 |

**Damping the steering costs time, monotonically.** If the motion were a
degenerate flat direction, damping it would have been free — that is what
degenerate means. It was not free, so the steering is doing work. It also removed
none of the four reversals (they are the real manoeuvre) and broke a solve that
converged cleanly without it.

A third hypothesis, that the car was riding the road-edge constraint, is also dead:
only 5 of 100 nodes sit on the edge and **none** of the nine large steering changes
occurs at one. The path `n` is perfectly smooth throughout —
0, −0.02, −0.12, −0.32, −0.64, −1.08, −1.58 — which should have told me
immediately that a smooth path cannot be produced by meaningless steering.

**Consequences.**
1. **The figures were correct.** Cars drawn with turned wheels on the approach are
   showing a real manoeuvre. I was about to "fix" an accurate figure, which would
   have replaced a true picture with a false one.
2. `steer_rate_weight` stays in `solve_min_time` but **defaults to 0.0** — it is
   an opt-in lever, not a fix.
3. **There is a genuine finding here, and it is not a defect:** the optimum begins
   cornering well before the corner and deliberately swerves the *wrong way* first
   to use the full width of the road. Nobody told it to.

**Source:** `[MEASURED]` — `traces.npz` per-node `delta`, `alpha`, summed `fy`;
steer-weight sweep on the Episode 6 problem at 100 nodes.

**Why it matters — and this is the part worth keeping.** I found "chatter" by
diffing an array, built a story that explained it, wrote it up as a defect, and
proposed a fix. The story was plausible and false. What killed it was **checking
the physical state at those nodes** (0.86 g and a saturated tire is not a car
cruising) and **the fix's own failure to be free**. A defect that goes away when
you look at what the car is doing was never a defect. Compare F36, where the
figure really was wrong: there the force arrows pointed somewhere physics forbade.
The discipline is the same in both directions — check against the physics, not
against how the numbers look.

| Steering change per node | In the corner | Entry straight |
|---|---|---|
| Typical | 0.5° | 2.4° (RWD), 3.8° (FWD) |
| Worst | 1.0° | **10.9° (RWD), 12.4° (FWD)** |
| Direction reversals in the first 70 m | — | **4 (RWD), 6 (FWD)** |

**Cause.** The car genuinely must move ~4 m across the road before the
left-hander, and it does — `n` runs from 0 to the −4.00 m road edge, which is the
correct wide entry. But thousands of ways to travel 4 m sideways on a straight
take *the same time*, so the time-only objective does not distinguish them and the
solver settles on an arbitrary one. Arbitrary looks like sawing at the wheel.

**Consequences.**
1. **Two figures draw a car on the entry straight, and its steer angle there is
   noise** — the Episode 6 along-the-path figure's first station and Episode 4's
   line figure both sit in the chatter zone.
2. The two drivetrains chatter *differently* (4 vs 6 reversals). Weaving adds
   distance, so some unknown part of any time difference is arbitrary rather than
   physical.
3. **Likely the reason the rear-drive open-differential case would not converge**
   even at 8000 iterations — a flat, chattering direction is badly conditioned.

**Fix.** A small penalty on steering rate, `w · Σ(steer_rate/steer_rate_max)²`,
normalised so `w` is dimensionless. Standard practice in minimum-time formulations
and it should have been there from Episode 4. **The weight must not buy smoothness
with lap time**, so it is chosen by measuring both, and the invariance is asserted
in the tests rather than assumed.

**Source:** `[MEASURED]` — `traces.npz`, per-node `delta` differences split by
track section.

**Why it matters:** found by asking whether 4 m node spacing was too coarse for a
40 m corner. It wasn't — the geometric error is 4.9 cm on an 8 m road. But
checking *the shape* led to checking *the controls*, which is where the real defect
was. The question that finds a bug is often not about the thing that is broken.

### F41 · Episode 6's differential numbers are not all on equal footing.
With the 100-node primary grid, three of the four solves converge cleanly and one
does not:

| | Open diff | Ideal diff |
|---|---|---|
| Rear-wheel drive | 12.158 s ⚠️ **iteration limit** | 12.091 s ✓ |
| Front-wheel drive | 12.322 s ✓ | 12.191 s ✓ |

So under F39's rule:

- **The headline (+0.100 s with an ideal diff) is established** — both solves
  converged, and it holds to 0.008 s across 100/140/180 nodes.
- **"A perfect differential is worth 0.131 s to front drive" is established** —
  both front-drive solves converged.
- **"…worth 0.067 s to rear drive" is NOT**, and neither is the open-diff gap of
  +0.163 s. Both subtract an unconverged number.

The qualitative claim that the differential matters roughly twice as much to front
drive survives, since the front-drive side is clean and the rear-drive gain would
have to be more than double its current value to overturn the ordering. But the
open-diff figures do not ship until that solve converges — F40's regularisation is
the most likely route.

**Source:** `[MEASURED]` — `experiments/ep06/out/results.json`, `solver_status`
per solve; the run script now prints a warning when any solve in a comparison
fails to converge.

---

## Session 7 — where you put the weight · 2026-07-26

Evidence: `experiments/ep07/out/results.json`, `traces.npz`. Front mass fraction
swept 0.40–0.65, both drivetrains, 100 nodes, ideal differential, continuation
warm starts outward from the nominal 0.54.

### F44 · Balance transforms how the car behaves and barely changes how fast it is.
| Front mass | K (deg/g) | Rear drive | Front drive |
|---|---|---|---|
| 40% | **−0.43** | 12.103 s ✓ | 12.305 s ✓ |
| 47% | −0.13 | 12.078 s ⚠ | 12.221 s ✓ |
| 54% (nominal) | +0.17 | 12.091 s ✓ | 12.191 s ✓ |
| 61% | +0.47 | 12.136 s ⚠ | 12.199 s ✓ |
| 65% | **+0.63** | 12.189 s ⚠ | 12.221 s ✓ |

**The understeer gradient swings 1.06 deg/g**, from clear oversteer to clear
understeer, against a 0.2 deg/g real-world measurement floor. That is the largest
and cleanest effect in the sweep, and it is the number Episode 3 introduced now
doing real work.

**The lap time does almost nothing.** Within the 0.02 s floor these solves
support (F39), rear drive's two converged points — 40% and 54% — are
**indistinguishable** (0.012 s apart), and front drive ties across 54–61%
(0.008 s apart). Only one point is clearly worse: front drive at 40% front, which
loses **0.114 s** because a front-drive car with 60% of its mass over the
undriven axle cannot put power down.

**So "50:50 is a marketing number" is true, but not for the expected reason.** The
series plan anticipated an optimum somewhere other than 50:50. What the sweep
actually shows is that **across most of the range there is no measurable optimum
at all.** Balance dominates how the car *feels* and is nearly irrelevant to how
fast it is — over this corner, at this power, with yaw inertia held fixed.

**Source:** `[MEASURED]` — `experiments/ep07/run.py`. Three rear-drive solves hit
the iteration limit and are excluded from every optimum claim.

### F45 · Weight over the driven wheels recovers most of the front-drive penalty, but never all of it. **Completes Episode 6.**
Episode 6 found front drive 0.10 s slower at a fixed 54% front and explicitly
deferred the obvious objection: a real front-drive car puts its engine over its
driven wheels. Measured:

| Front mass | 40% | 47% | 54% | 61% | 65% |
|---|---|---|---|---|---|
| **front drive costs** | +0.202 s | *+0.119 s* | +0.100 s | +0.063 s | **+0.032 s** |

**Monotonic across every converged point, and it never crosses zero.** Loading the
driven axle buys back roughly 85% of the deficit between 40% and 65% front — but
at 65% front, more nose-heavy than most real front-drive cars, front drive is
still slower.

The objection is therefore answered and the Episode 6 conclusion survives it: at
equal power, the axle that steers should not also be the axle that drives, and
piling weight onto it narrows the gap without closing it.

**Re-solved, and the monotonic claim now has support it previously lacked.** An
earlier version of this entry called the trend monotonic while **three of five
rear-drive solves had stopped on the iteration limit**, each carrying up to
~0.08 s of F39 error — larger than every adjacent gap in the sequence (0.03–0.06 s).
The *span* claim survived that; the point-by-point claim did not, and both were
stated as though equally supported.

Re-solving with Episode 8's recipe — front drive first, each rear-drive point
seeded from the converged front-drive answer at the **same balance**, plus a retry
at 16,000 iterations — converged 9 of 10. The four converged gaps are
**+0.202, +0.100, +0.063, +0.032 s: monotonic, spanning 0.170 s**, with no
unconverged number among them.

**0.47 front is still excluded** (italicised above). It failed at 16,000
iterations after 1,008 s and is the one point in this sweep that will not solve.
Its value sits between its neighbours, which is consistent, but consistency is not
evidence.

### F46 · Balance moves the braking point, not the apex. **Corrects an expectation in the series plan.**
The plan predicted that "the apex migrates continuously as weight moves
rearward". It does not:

| | across the whole 40–65% sweep |
|---|---|
| Apex position, rear drive | moves **0.9** percentage points |
| Apex position, front drive | moves **1.5** points |
| **Brake release point** | moves **15.9 m** (both drivetrains) |

Apex movement of about a point is not resolvable here and is not a finding. The
brake point moves 15.9 m — four node spacings, unambiguous — and monotonically:
more front weight, later braking, because there is more front grip to brake
against. At 61–65% front the car is still braking well past turn-in.

Worth comparing with Episode 4, where changing what came *after* the corner moved
the apex about 6 points. **The apex is set by the corner's context, not by the
car's balance.** That is a sharper statement than the one the plan expected, and
it came out of the data rather than being looked for.

**Source:** `[MEASURED]` — apex from interpolated position (F47), brake release
from the last node with longitudinal force below −100 N before mid-corner.

### F47 · Apex position was quantised to the node grid. **Defect, and it silently affected Episode 4.**
`apex_index` is an `argmax` over nodes, so apex position could only ever land *on*
a node. At 100 nodes this track's corner gets ~16 of them, quantising apex to
**6.7% of the corner** — coarser than the effect Episode 7 set out to measure. It
showed up as five different cars all reporting *exactly* 53.3%: not a physical
result, one shared node index.

Fixed with three-point parabolic interpolation about the peak, computed downstream
from the logged arrays (rule 7). Pinned by a test that recovers a vertex whose
position is known in closed form, rather than checking against solver output.

**This reaches back into Episode 4**, whose grid-refinement table reported apex
shifts of 5.5 / 6.2 / 5.9 points at 140 / 200 / 280 nodes. At those grids one node
is 3.1–6.3% of the corner, so that spread was substantially quantisation rather
than physics. The conclusion (a later apex with a long straight to follow)
survives — 6 points is larger than the quantisation — but the digits did not mean
what they appeared to.

**Source:** `[MEASURED]` — `Solution.apex_offset_nodes`;
`tests/test_optimal_control.py` apex group.

**Why it matters:** a metric can be precise, reproducible, stable under
refinement, and still be reporting the grid rather than the car. Five identical
readings looked like a clean null result and were an artefact.


---

## Session 8 — front, mid or rear engine · 2026-07-26

Evidence: `experiments/ep08/out/results.json`. Step-steer transients on the
bicycle model (matching D4, validated against an exactly integrated linear model
to 3%); lap times from four-wheel minimum-time solves at 100 nodes.

### F48 · Balance and polar moment are independent axes, and the layouts people argue about are separated on the second one.
Two cars at **identical** 43% front balance, polar moment at the ends of the
documented range:

| | 0.80× polar moment | 1.22× |
|---|---|---|
| Rise time | **201 ms** | **304 ms** |
| Settling time | 386 ms | 560 ms |
| Understeer gradient | −0.30 deg/g | **−0.30 deg/g** |

**Same steady-state behaviour, 51% difference in how long it takes to get
there.** That comparison cannot be made with real cars, because moving an engine
changes both properties at once.

The five layout archetypes, placed on the two axes:

| Layout | Front mass | Polar moment | Rise time | K |
|---|---|---|---|---|
| Front engine, FWD | 62% | 1.25× | 234 ms | +0.49 |
| Front engine, RWD | **55%** | **1.20×** | 236 ms | +0.21 |
| Front-mid, RWD | 53% | 1.00× | 201 ms | +0.13 |
| Mid engine, RWD | 43% | **0.80×** | 201 ms | −0.30 |
| Rear engine, RWD | **38%** | **1.22×** | 356 ms | −0.51 |

**The front-engine saloon and the rear-engine 911 sit at opposite ends of the
balance axis — 55% against 38%, about as far apart as production cars get — and
at essentially the same height on the inertia axis (1.20× against 1.22×).**

And the mid-engine car is not the balance outlier: at 43% front it is *less*
rearward than the 911. What separates it is 0.80× polar moment, the lowest of the
five. **"Mid-engine is better" is a polar-moment claim that is habitually argued
as a weight-distribution claim**, and the two get conflated because a real engine
move changes both.

Note also that front-mid (53% front, 1.00×) and mid (43% front, 0.80×) reach the
*same* 201 ms rise time by different routes — nose-heavier but higher inertia
versus more rearward but lower inertia. Two axes trading off, in one pair of
numbers.

**Source:** `[MEASURED]` — `experiments/ep08/run.py`. Archetype balance and
inertia values are `[ASSUMED]`, from the reference sheet §2.

### F49 · Polar moment barely shows up in a lap time, because the solver cannot be surprised.
**All five layouts converged cleanly**, so this comparison rests on no excluded
solves:

| Layout | Polar moment | Rise time | Lap time |
|---|---|---|---|
| Front-mid, RWD | 1.00× | 201 ms | 12.09 s |
| Mid engine, RWD | 0.80× | 201 ms | 12.09 s |
| Front engine, RWD | 1.20× | 236 ms | 12.09 s |
| Rear engine, RWD | **1.22×** | **356 ms** | 12.12 s |
| Front engine, FWD | 1.25× | 234 ms | 12.21 s |

**Quoted to 0.01 s (rule 12).** These solves resolve to about 0.02 s, so the
millisecond digits an earlier version of this entry printed were solver output,
not accuracy. At honest precision **three of the four rear-drive layouts share one
lap time** across a 0.80×–1.20× range of polar moment.

Across all four rear-drive cars, rise time spans 155 ms and lap time spans
**0.03 s — barely above the floor.** Only the mid-engine and rear-engine pair are
far enough apart to separate at all, and even that gap is 1.5× the floor. Read the
lap-time column as "no measurable effect", not as a small one.

The only layout clearly off the pace is the front-drive one, 0.113 s behind the
quickest — and Episode 6 already accounted for that on entirely different grounds
(the friction circle, not the inertia). **Polar moment, the property this episode
is about, is worth almost nothing here.**

**This is not a null result, it is the setup for Season 3.** The minimum-time
solver plans the entire corner before turning the wheel. It knows exactly when the
corner arrives, so it can simply begin steering earlier to compensate for a car
that responds slowly. Response time costs a clairvoyant driver almost nothing.

A real driver reacts to what has already happened. For them a 155 ms delay is 155
ms of the car not doing what they asked, at a moment when they are correcting.
**The gap between those two situations is the entire justification for Episodes
9–11**, and it is why "which layout is faster" has been the wrong question for
three episodes running.

**Source:** `[MEASURED]` — all five archetypes `Solve_Succeeded`, envelope
occupancy zero throughout. Reaching that took seeding every layout from the
front-drive solve, which converges in ~13 s where the rear-drive ones need
250–350 s, plus one retry at 16,000 iterations. Continuation from the *easiest*
member of a family, not the most representative one, is the lesson — the
reference-closest layout failed on a cold start and converged when it inherited a
four-wheel answer.

### F50 · Our model shows no "twitchiness", and the plan expected some. **Corrects an expectation.**
The series plan predicted low polar moment would be "twitchier at the limit".
Measured overshoot in the controlled pair: **0.23%** at 0.80× against **0.14%** at
1.22×.

The *direction* is right and matches D4 and the linear model — lower inertia
overshoots more. The *magnitude* is nil. Neither car meaningfully overshoots, so
nothing here supports calling one nervous.

**Why our setup cannot show it.** The step is 3° at constant speed, which is a
gentle, essentially linear input, and there is no driver in the loop. "Nervous at
the limit" is a claim about large inputs near saturation with a human correcting —
three things this experiment deliberately does not have. Reporting a 0.09
percentage-point difference as twitchiness would have been the rule-5 error again.

**Source:** `[MEASURED]` — `experiments/ep08/run.py` pair overshoot; consistent
with D4's `overshoot_decreases_with_yaw_inertia`.


---

## Session 9 — teaching a car to drive · 2026-07-26

Evidence: `experiments/ep09/out/results.json`, `history.json`,
`diagnostics/out/D6_report.json`. PPO on the four-wheel model, progress-only
reward, slip envelope deliberately unenforced.

### F51 · PPO's conventional shared gradient clip silently disabled policy learning. **Defect.**
Measured directly on this problem:

| | loss | gradient norm |
|---|---|---|
| policy | 0.14 | **1.0** |
| value | 1606 | **149.5** |
| combined, clipped to 0.5 | | **scaled by 0.0067** |

A progress reward gives returns of order 40 m, so the value loss starts near 1600
and its gradient is 150× the policy's. One `clip_grad_norm_` across both — the
default in most PPO implementations — then scales *everything* by 0.0067, giving
the policy an effective learning rate of 2×10⁻⁶.

**Training ran for 250,000 steps. Losses moved. Nothing crashed. Approximate KL
sat at 0.0000 and the policy never updated.** The two networks share no
parameters, so clipping them separately costs nothing and removes the coupling.

**Source:** `[MEASURED]` — direct gradient-norm comparison; `physics/ppo.py`.

### F52 · Three hyperparameters were wrong because they came from convention rather than from the task.
Each was diagnosed by computing what the *problem* needs and comparing:

| | conventional | what this task needs | ratio |
|---|---|---|---|
| Steering exploration | std 0.61 | **0.037** of authority | **16×** too large |
| Throttle exploration | same as steering | the whole [−1, +1] | **10×** too small |
| Entropy coefficient | 0.01 | 0.0005 | 20× too large |

Holding the 40 m corner needs about 3.7° of steer reached over half a second —
7.4 deg/s against 200 deg/s of authority, a normalised action of 0.037. Searching
that with a standard deviation of 0.61 means sawing the wheel off an 8 m road
within a second, every episode, so the policy never saw a trajectory worth
reinforcing.

**And one exploration scale cannot serve both action dimensions.** With a value
small enough for steering, the policy converged to full throttle and never
sampled braking at all, sitting in that local optimum for half a million steps.
`init_log_std` is now per-dimension: `(-2.5, -1.0)`.

**Why it matters:** none of these produced an error. All three produced training
runs with moving curves and no learning. The diagnosis in every case was to
compute the scale of a useful action and compare it against the scale being
searched — which is now a D6 check.

### F53 · The task was physically impossible as configured. **Defect.**
The corner is 40 m radius and the car makes 0.97 g, so **19.5 m/s is the fastest
it can be taken. The environment started the car at 32 m/s**, copied from the
optimal-control episodes.

A solver that sees the whole road plans that braking in one shot. A learner must
discover 1.3 s of hard braking beginning two seconds before any consequence,
against an immediate reward for going faster. Configured that way the policy
never completed a single lap in 250k steps — it drove off the road at 65 m, every
time.

Starting at 15 m/s makes the task learnable **with no reward shaping**: the policy
learns to steer first, and the progress reward pushes it faster until braking
becomes necessary on its own terms. The curriculum is in the task, not the reward.

**Why it matters:** the same number describing a different problem. Nothing
flagged it, because 32 m/s is a perfectly reasonable speed — for a driver that can
plan.

### F54 · The policy's behaviour lives in its exploration noise. The trained driver and the deployed driver are different drivers.
**This is Episode 9's result.**

| | distance | laps finished |
|---|---|---|
| Sampled, as trained | **362 m** | **88%** |
| Its own mean action | **129 m** | **0%** |

A 64% gap on the same weights, same road, same seed. The mean-action policy
arrives at the corner at 22.9 m/s where 19.5 is the limit, runs wide, and leaves
the road.

**Mechanism, and it is exact.** Braking authority is 12 kN against 4.5 kN of
drive — real physics, brakes are stronger than engines — so the map from throttle
action to force has a kink at zero. A Gaussian policy straddling that kink does
not deliver the force of its mean action:

| mean throttle | force(mean action) | E[force(sampled)] | difference |
|---|---|---|---|
| +0.30 | +1350 N | +939 N | −411 N |
| **0.00** | **0 N** | **−1183 N** | **−1183 N** |
| −0.10 | −1200 N | −2035 N | −835 N |

`E[f(a)] ≠ f(E[a])`, and the gap is always toward braking. **The policy never
learned to brake. It learned a mean action that brakes only once its own noise is
added to it.** Switch the noise off to deploy it and the braking disappears with
it.

**Why it matters:** every training curve in the run describes the sampled policy.
Nothing in them hints that the deterministic policy — the one you would actually
ship — cannot get round the corner. Reporting either number alone is a true
statement about a driver that is not the other one.

### F55 · The policy gradient raises exploration noise on its own, with no entropy bonus at all.
Two arms, 400k steps each, identical seed:

| entropy coefficient | throttle `log_std` | steering `log_std` |
|---|---|---|
| **0.0 — none** | −1.00 → **−0.96** | −2.50 → **−2.41** |
| 0.0005 | −1.00 → −0.97 | −2.50 → −2.43 |

**Removing the entropy bonus entirely does not stop the noise growing.** The rise
is the policy gradient's doing, not the regulariser's. A converging policy
normally becomes more decisive; this one becomes slightly less so.

That is consistent with F54 — if the noise is doing useful work, the gradient
should protect it — but **the effect is modest** (~4% over 400k steps, ~6% over
1.2M) and this is corroboration, not proof. The direct evidence for noise-as-control
is the 64% greedy gap and the arithmetic above.

Worth recording as a caution: "entropy is rising, lower the entropy coefficient"
is the obvious reading and it is wrong here. The coefficient was already almost
zero.

**Source:** `[MEASURED]` — two-arm experiment, `physics/ppo.py` history
`log_std`.

### F56 · The policy went outside the tire model, but far less than the series plan predicted.
Worst slip angle **14.4°** against our 12° bound, with **0.5%** of steps beyond
it — with nothing in the environment enforcing the bound.

The plan expected this to be the episode: *"It didn't learn to drive. It learned
that my tire model was optimistic at 25 degrees of slip, and drove there."* At
14.4° peak and half a percent of steps it is real and it is a D6 failure, but it
is a footnote next to F54, not the headline.

**Why the prediction missed:** the policy is not fast enough yet to be tempted.
It finishes 88% of laps at a modest pace; the tire-model exploit is available to a
policy operating at the limit everywhere, and this one is not. Expect this finding
to grow in Episodes 10–11 as the policies get quicker, and re-check it there.

**Source:** `[MEASURED]` — D6 `the_policy_stayed_inside_the_tire_model`.


---

## Session 10 — audit corrections · 2026-07-26

An in-depth audit of Episodes 7–10 found four methodology problems and several
documentation lapses. These are the entries of record.

### F57 · Continuation should start from the EASIEST member of a family, not the most representative.
Episode 7 originally left three of five rear-drive solves on the iteration limit
by seeding each balance from its neighbour starting at one end of the sweep.
Excluding them was correct, but it left the monotonic trend and Episode 10's
cross-check resting on two usable points.

**The recipe that works, established in Episode 8 and now applied to 7:** solve
the *fastest-converging* member first and seed everything from it, plus one retry
at double the iteration budget. Front-drive four-wheel solves converge in ~10 s
where rear-drive ones need 250–350 s, so the front-drive answer at the same
balance is the best available seed for its rear-drive twin.

Result: **7 of 10 converged → 9 of 10.** One point, 47% front rear drive, still
fails after 16,000 iterations and 1,008 s and is excluded everywhere.

**It changed a published conclusion.** With four converged rear-drive points
instead of two, structure appeared where Episode 7 had reported none: rear drive
is tied fastest at 40% and 54% front and **measurably slower** at 61% (+0.05 s)
and 65% (+0.10 s), while front drive is tied at 54% and 61%. Each drivetrain
prefers the end of the range that loads the wheels it drives. The earlier
statement — "no measurable optimum at all across most of the range" — was a
description of having two data points, not of cars.

**Source:** `[MEASURED]` — `experiments/ep07/run.py`.

### F58 · Averaging lap time over finishers only is survivorship bias when the finish rate varies.
Episode 10 compared designs on mean lap time computed across finishing rollouts.
Finish rate varies by design, so a car finishing 30% of laps was scored on its
luckiest runs and one finishing 95% on typical ones — biased in an unknown
direction.

Replaced with **progress rate** (distance per second, over every rollout
including crashes), which drops nothing and is finite even when the finish rate
is zero.

**Source:** `[MEASURED]` — `experiments/ep10/run.py`.

### F59 · JSON has no float keys, and the failure is silent. **Defect.**
Episode 10's cross-check figure rendered axes, gridlines, labels and **no data at
all.** Both curves missing, no error, and it passed every figure test — valid
XML, provenance stamp present, title present.

`_ep07_reference()` built a dict keyed by floats. Written to JSON and read back,
`0.40` becomes the string `"0.4"` — not even `"0.40"`. Every lookup missed. The
RL curve was separately absent because the policy finished no laps, so two
independent faults produced one empty figure.

Fixed with a single `dkey()` used by both the experiment and the figures.

**Why it matters:** the audit only found this because the figure was rendered and
looked at. Four distinct figure-bug classes this session passed XML, stamp and
title checks and were visible only by eye.

### F60 · Train over the range you evaluate.
Episode 10 sampled front mass fraction from the documented sweep (0.35–0.65)
while only ever evaluating 0.40–0.65 — spending a quarter of its samples on the
hardest cars in the range, which nobody asks about. Narrowed to the evaluated
range. Recorded as a **training** decision in `EnvConfig`, not a change to what
`DESIGN_SWEEP` means.

### F61 · A reinforcement-learning result is the DEPLOYED policy's performance. **Corrects Episode 9's framing.**

Episode 9 was written around a policy that finishes **88% of laps when its actions
are sampled and 0% when they are not.** The 88% was the headline; the 0% was
presented as an interesting caveat.

**That is backwards.** The mean-action policy is the artefact a reader would use.
If it does not work, nothing was learned — and the sampled figure was measuring a
quirk of the exploration noise rather than driving skill. F54 established the
mechanism precisely: the policy's braking comes from Gaussian noise passing
through a kinked actuator map, so removing the noise removes the braking.

**Both readings describe real drivers; neither describes a competent one.** The
sampled policy limps round on a noise-generated crutch; the mean policy is the
same policy with the crutch removed.

**And the 88% does not survive being asked twice.** It came from D6's evaluation
harness with `start_jitter_m=0` and its own seed sequence. Six clean-start seeds
give **0%**. A number that moves that far under a change of harness is not a
measurement.

**Consequences, applied:**
- D6 gains `the_deployed_policy_completes_the_task`, gating on an 80% mean-action
  finish rate. **Episode 9 now fails it**, which is the honest verdict.
- The tire-model check judges the deployed policy too.
- Two CLAUDE.md invariants: the deployed policy is the result; evaluate over
  several seeds *and* several harnesses.

**This also kills the Episode 9 vs Episode 10 contrast** drawn earlier — "Ep 9
behaved, Ep 10 exploited". Neither learned to drive. They found different
shortcuts: Episode 9 one in the *optimiser* (noise through a kinked force map),
Episode 10 one in the *physics* (forces from an unfitted region of the tire
model). See F62.

### F62 · Sliding outside the tire model pays, measurably. The environment is under-specified.
Measured directly on Episode 10's policy, 6 rollouts, per-step progress split by
whether the step was inside our ±12° slip bound:

| | share of steps | progress |
|---|---|---|
| Inside the envelope | 67.3% | 20.23 m/s |
| **Outside** (to 121°) | **32.7%** | **21.01 m/s** |

**It goes 4% faster where the tire model has no fit.** The exploit is real and the
reward pays for it, so more training finds it *faster* — a 4M-step run launched to
"fix" the collapse was killed on this evidence.

The environment as specified — progress reward, no envelope penalty — does not
have driving as its optimum. Two independent runs found two different shortcuts,
which is the signature of an under-determined task rather than of bad luck.

**Consequence:** Episode 10 cannot deliver its design comparison or the
RL-versus-optimal-control cross-check as posed. A policy sliding at 121° says
nothing about weight distribution. Resolving the exploit is properly Episode 11's
subject, arriving two episodes early.

**Source:** `[MEASURED]` — per-step progress from `traces`, split on
`alpha_max_deg > 12`.


### F63 · Penalising the physics exploit also closed the optimiser exploit. Prediction wrong.
Episode 10's environment gains a per-step cost for operating outside the ±12°
slip fit, scaled by how far outside. **A protocol change, recorded as one** (rule
9): the unconstrained environment was not broken, it was answering a different
question. Episode 9 keeps `envelope_penalty = 0.0` and its premise intact.

| | unconstrained | constrained |
|---|---|---|
| Worst slip | **148°** | 18.5° (10.9° on cars it drives) |
| Steps beyond 12° | **36.5%** | 3.2% |
| Deployed vs sampled distance | 129 m vs 362 m | **322 m vs 320 m** |

**I predicted the noise crutch (F54) would survive this, and it did not.** The
prediction was that the envelope penalty addresses the physics shortcut only,
leaving the Gaussian-through-a-kink braking mechanism untouched.

The mechanism I missed: **noise now costs.** Random actions push slip past the
bound and get penalised, so the policy stopped relying on them — and the
deployed/sampled gap closed on its own, to the point where the mean action is
*better* than sampling at 61% front. Constraining the physics fixed the optimiser
exploit as a side effect, because both shortcuts were being paid for out of the
same currency.

Worth keeping as a caution in the other direction: two shortcuts that looked
independent shared a cause, and I reasoned about them as if they were separate.

**Source:** `[MEASURED]` — `experiments/ep10/run.py`, `envelope_penalty=0.5`.

### F64 · A design-conditioned policy has a competence band, and the aggregate hides it.
The constrained policy, deployed (mean action), across the five designs:

| Front mass | Finishes | Distance | Worst slip |
|---|---|---|---|
| 40% | **0%** | 110 m | 21.6° |
| 47% | **100%** | 393 m | 10.9° |
| 54% | **100%** | 393 m | 7.0° |
| 61% | **100%** | 393 m | 4.5° |
| 65% | **0%** | 94 m | 4.2° |

**It drives the middle of the range perfectly and entirely inside the tire model,
and fails both extremes.** D6 reported this as "75% of laps" — an average across
a bimodal distribution, which is the kind of number that conceals a result rather
than stating one.

The two failures are different in kind. At 40% front, the most oversteering car,
it slides at 21.6° and crashes. At 65% it never exceeds 4.2°, so it is not
sliding at all — it understeers wide and runs out of road. One end needs less
aggression, the other needs more.

**Consequence for the cross-check, which is the episode's purpose.** An earlier
version computed a shape correlation of **+0.75** across all five designs, with an
RL spread of **6.15 s** against the solver's **0.098 s**. That number was
worthless: it correlated *which cars the policy can drive* against *which cars are
quicker*, and was driven entirely by the two total failures.

The cross-check is now gated on designs where **both** methods produced a
trustworthy answer — the optimal-control solve converged *and* the deployed policy
drives the car — and **refuses to report a correlation below three usable
designs** rather than producing one. On this run that leaves two, so it refuses.

**Source:** `[MEASURED]` — `experiments/ep10/run.py`; `crosscheck_n_usable`.


### F65 · The learned driver says balance matters ~4x more than the solver does. Observed, and NOT explained.
Over the three designs where both methods have a trustworthy answer (54%, 61%,
65% front):

| | relative spread of lap time |
|---|---|
| Learned driver, deployed | **3.1%** (19.43 → 20.04 s) |
| Optimal control | **0.81%** (12.091 → 12.189 s) |

Both put lap time **increasing with front mass** — same ordering, independent
methods sharing only the tire file, the four-wheel model and the corner. That
agreement is the episode's cross-check and it holds.

**The magnitudes disagree by about 4x, and I cannot currently say why.**

The attractive explanation is driver quality: the solver re-optimises its entire
line for each car and absorbs the design change, while one conditioned policy
cannot fully re-plan per car, so the same change costs it more. If true it is a
caution for every RL-based design comparison — *a suboptimal driver exaggerates
how different designs are.*

**But the two methods are running different tasks, not just different methods.**
The RL environment starts at 15 m/s; the solver starts at 32. The control test is
to re-solve the optimal-control problem at 15 m/s entry and see whether its
sensitivity grows to match.

**That test was run and returned nothing usable: all three solves failed to
converge at 15 m/s**, even with the front-drive seeding and a 16,000-iteration
retry. Their values (13.119 / 13.145 / 13.183 s) imply a 0.49% spread — *lower*
than at 32 m/s, which would point away from entry speed being the explanation —
but unconverged objectives are not evidence (F39) and this is not quoted as any.

**Status: the gap is measured; the mechanism is unattributed.** Recorded this way
rather than assigned to the appealing explanation. What would settle it: getting
the 15 m/s optimal-control solves to converge, or training an RL policy at 32 m/s
entry so both methods share one task.

**Source:** `[MEASURED]` — `experiments/ep10/out/results.json`,
`rl_over_oc_sensitivity`; control test unconverged.

### F66 · Twelve identical rollouts reported as twelve samples. **Defect.**
Episode 10's evaluation reported `19.68 +/- 0.000 s` over 12 rollouts per design.
That reads as extraordinary precision and is the **complete absence of
replication**: the deployed policy is deterministic, the environment is
deterministic, and every rollout started at the same place, so all twelve were
byte-identical. One run, printed twelve times, with a zero standard deviation
attached.

Fixed by jittering the start position during evaluation. With genuine variation:

| Front mass | deployed lap |
|---|---|
| 47% | 19.13 ± 0.142 s |
| 54% | 19.43 ± 0.132 s |
| 61% | 19.80 ± 0.123 s |
| 65% | 20.04 ± 0.122 s |

**The trend survives:** 0.615 s spread across designs against a 0.132 s
within-design standard deviation — 4.7x, clear of rule 5's 2x bar.

**Note what this spread is and is not.** It is *rollout* variation from a jittered
start. It is **not** training-seed variation, which rule 5 actually asks for and
which no Season 3 result yet has.

**Why it matters:** a zero error bar is not a small error bar. It is a signal that
nothing was being averaged, and it looked like the most precise number in the
episode.

### F67 · On a correlation of three monotone points.
Episode 10's cross-check initially reported a shape correlation of **+0.9997**,
which is very nearly meaningless. Tested directly: **two random monotone 3-point
series exceed r = 0.99 about 25% of the time.** With both series monotone and
n = 3 the statistic is close to determined by the ordering alone.

The figure and the results file now report the two things three points can
support — whether the methods agree on **ordering**, and how far apart they are on
**magnitude** — with the correlation demoted and carrying its own caveat.

Kept as a general caution: a correlation computed over a handful of monotone
points will look spectacular and is not evidence. Check what the same statistic
does on random data of the same shape before quoting it.

### F68 · Episode 10's figures were generated by an earlier version of the code and were never regenerated. **Defect, four parts.** · 2026-07-27

**Source:** `experiments/ep10/out/02-two-methods-one-answer.svg` and
`results.json`, reviewed by eye against `experiments/ep10/run.py`.

The cross-check gate from F64 landed in `run.py` and the on-disk artefacts were
never rebuilt, because the only way to rebuild them was a 5-million-step retrain.
Four separate defects, all of which a reader would have taken at face value.

**1. The figure plotted a different population, a different policy and a
different metric from the arithmetic printed beside it.** The panel drew the
**sampled** policy's *progress rate* across **all five** designs; the correlation,
spread and "fastest balance" text beside it came from the **deployed** policy's
*lap time* across the **gated three**. The visible result was a red curve whose
minimum sat at 40% front next to a caption reading `fastest balance: learned 54%
front` — the figure contradicting its own legend. The figure now plots exactly the
designs the arithmetic uses, on the same metric, normalised over the same subset.

**2. The retracted correlation was still on disk as the current value.** The
figure showed `shape correlation +1.00` from a stored `+0.9997` — the number F67
retracted. Recomputed on the correct three designs and metric it is **+0.9851**,
and it still carries F67's caveat.

**3. Both exclusions were recorded under one key named for the wrong reason.**
`crosscheck_excluded_unconverged` listed `0.40` and `0.47` together, asserting the
solver failed on the 40% car. The solver is fine there — **the policy cannot drive
it**, which is this episode's actual finding, filed as a solver problem. Now
`crosscheck_excluded` records the reason per design and the figure draws each
exclusion in place with that reason, so a gated design cannot read as an untested
one.

**4. The provenance stamp on every Episode 10 figure asserted the opposite of
Episode 10.** `_stamp` carried the literal string "slip envelope NOT enforced",
copied from Episode 9, onto the episode whose one substantive protocol change is
that it *is* enforced (F63). Rule 3 exists to stop exactly this; a hardcoded
provenance string defeats it. The stamp now reads `envelope_penalty` from the
results.

**The enabling condition was the absence of a cheap rebuild.** `run.py` gained
`--eval-only`, which reloads `policy.pt` and recomputes every downstream number
and figure in about two minutes. The policy is the artefact; everything after it
is derived (rule 7). When regenerating a figure costs an hour, figures go stale —
that is a property of the workflow, not of anyone's diligence.

**Also corrected while here:** the console printed the **sampled** per-design
table as the headline result. That is the reporting habit behind Episode 9's 88%
(F61). It now prints deployed first and labels sampled as diagnostic.

### F69 · Episode 10's D6 fails one of ten checks, and the article did not say so. · 2026-07-27

**Source:** `diagnostics/out/D6.md`, `experiments/ep10/out/results.json`
(`d6_passed: false`).

`exploration_is_not_growing` **fails**: policy entropy rose from −0.66 to −0.48
(**+0.18**) over 5M steps, meaning the entropy bonus is outrunning the policy
gradient. This was failing before the F68 rebuild — it is not new, and it was
absent from the episode draft, which mentioned D6 only as something the run
performs.

The threshold is **not** being loosened. A check that gets relaxed when it fires
is decoration (rule 11), and this one is in the battery because it caught a real
Episode 9 failure.

**What it does and does not put at risk.** The five deployed-policy and
envelope checks pass: the policy drives 4 of 5 cars deployed, at a worst slip of
7.4° against a 12° bound. So the episode's *comparative* claim — the ordering of
designs by lap time — does not rest on the failing check. What the failure does
say is that this policy was **still drifting toward randomness when training
stopped**, so it is not a converged artefact and its absolute times have no claim
to being the best this method can do. The episode states this, and it compounds
the single-seed gap (rule 5) rather than being independent of it.

Recorded rather than fixed: raising `entropy_coef`'s decay or annealing it to zero
is the likely remedy and is a retrain, which belongs with the seed-discipline work
that Season 3 owes anyway.

### F70 · Calibrating a failure rate on 10 rollouts produced a retracted conclusion. The speed-fragility tradeoff is real; its magnitude is only partly quotable. · 2026-07-27

**Source:** `experiments/ep11/run.py`, Episode 10's policy deployed, 5 designs x 5
disturbance conditions x 40 rollouts. Supersedes the first version of this entry
entirely.

**The retraction first, because it is the transferable part.** Perturbation levels
were calibrated at **10 rollouts per cell**, which reported 0% failures and a worst
slip of 8.7-9.8 deg at steering sigma 0.15. At **40 rollouts the same condition
loses laps and reaches 11.7-15.3 deg.** On that basis this entry originally
concluded "there is no perturbation level at which this driver fails while staying
inside the tire fit" and the episode was drafted around *I could not make it
crash.* Both were wrong.

**Two distinct errors, and the second is the one worth remembering:**

1. **A failure rate needs far more samples than a mean.** At n = 10 a true 7% rate
   shows up as zero events about half the time. Nothing was measured; absence of
   evidence was read as evidence of absence.
2. **Worst-slip is an extreme-value statistic and was used as if it were a bound.**
   The maximum over a sample grows with sample size, so "worst slip 9.8 deg over 10
   laps" says nothing about the worst over 40. Any max-over-n quantity — worst slip,
   peak load, largest excursion — is a property of the sample, not of the system,
   and must never be quoted as a limit. **Medians and quantiles are stable under n;
   maxima are not.**

**What the 40-rollout data actually shows.** Under both disturbances together, on
the four cars the policy can drive, in-fit failure rate falls monotonically as the
cars get slower — the fastest is several times more likely to end up off the road
than the slowest. The tradeoff the episode set out to find is there and has the
shape vehicle-dynamics intuition predicts for a more rear-biased car.

**Rule 4 is a per-LAP rule, and applying it per-condition was a third error.** The
first envelope check gated on the worst slip in an entire condition. At n = 40 that
reached 35 deg while the **median** lap sat at ~8 deg, so a single excursion
disqualified 39 defensible laps. Laps from outside the envelope are discarded —
laps, not conditions. `trial()` now records per-lap `(finished, worst_slip)` pairs
and reports `failure_rate_inside_fit` over the laps that never exceeded 12 deg.

**The remaining honest limit.** A lap that BOTH failed and left the fit is
discarded, and some of those were real crashes. So every in-fit failure rate here is
a **lower bound**, and cells for which that applies are flagged
(`failure_rate_is_lower_bound`) and counted in the report by the
`discarded_failures_are_declared` check. The ordering is robust; the magnitudes are
floors, not estimates.

**The 40%-front car is not a fragility result and Episode 10 mis-worded it.** It
fails **unperturbed**, at 0% deployed finish rate. That is a car this driver cannot
drive, not a knife-edge car. Episode 10's "that is a car that is fragile" is
corrected in its draft; the two conditions have different causes and different
fixes.

**A fourth error, corrected: "5 degrees of margin it never spends" was wrong.**
This entry and the Episode 11 draft both described the policy as conservative
because it corners at 5.8-7.4 deg of slip against a 12 deg bound. **The Magic
Formula is flat near its peak, so that is not margin.** Measured on our own tire:

| Fz (N) | slip at peak Fy | Fy at 12 deg, as % of peak |
|---|---|---|
| 1500 | 9.65 deg | 99.5% |
| 4000 | 10.35 deg | 99.7% |
| 7000 | 12.50 deg | 100.0% |

At 4 kN the tire peaks at **10.35 deg**, and the policy's 5.8-7.3 deg is already
**94-98% of peak lateral force**. The +/-12 deg envelope sits *at* peak grip, not
below it — past 12 deg is the tire giving up, not the tire working harder. So there
is no large untapped slip region, and "conservative driver banking margin" was a
misreading of a flat curve. What remains unmeasured is whether the policy leaves
**lap time** on the table, which needs instrumentation the environment does not yet
have (see F71).

### F71 · The fastest design is measurably the fragile one, and the mechanism is recoverability, not margin. · 2026-07-27

**Source:** `experiments/ep11/run.py --deep`, `experiments/ep11/out/results_deep.json`.
Episode 10's policy deployed, 4 designs x 2 conditions x **120** rollouts, rule 4
applied per lap.

**Unperturbed, this driver is flawless on all four designs it can drive:** 120/120
laps completed, **zero** laps outside the tire fit, on every one of 47/54/61/65%
front. That baseline matters — it means everything below is disturbance-induced
rather than residual incompetence.

**Under steering noise and grip variation together, only the fastest design loses
laps:**

| Design | nominal lap | in-fit failures | rate | 95% Wilson |
|---|---|---|---|---|
| **47% front** | 19.16 s | **9 / 104** | **8.7%** | 4.6-15.6% |
| 54% front | 19.45 s | 0 / 114 | 0% | 0-3.3% |
| 61% front | 19.82 s | 0 / 102 | 0% | 0-3.6% |
| 65% front | 20.06 s | 0 / 105 | 0% | 0-3.5% |

**Significant after correction.** Six pairwise Fisher exact tests, Holm-Bonferroni
at family-wise 0.05: 47 vs 54 **p = 0.0011**, 47 vs 65 **p = 0.0016**, 47 vs 61
**p = 0.0033**, all below their Holm thresholds. The other three designs are
indistinguishable from each other (p = 1.000). At n = 40 the same effect sat at
p = 0.045 uncorrected and established nothing — the depth was necessary.

**It is a cliff, not a gradient.** One design is fragile and three are not, rather
than fragility rising smoothly with pace. That is a more useful shape than a
gradient: it means there is a threshold to stay behind, not a dial to trade off.

**The mechanism is recoverability, and it is visible in the discarded laps.** All
four designs leave the +/-12 deg fit about equally often. What differs is whether
they come back:

| Design | laps that left the fit | of which crashed |
|---|---|---|
| 47% front | 16 | **13 (81%)** |
| 54% front | 6 | 2 (33%) |
| 61% front | 18 | **1 (6%)** |
| 65% front | 15 | 1 (7%) |

The 61% car exceeded the limit **more often** than the 47% car and crashed once.
So this is not about how much margin a design has — it is about **what happens when
the margin is gone.** A nose-heavy car that runs out of front grip pushes wide and
slows, which is self-correcting; a rear-biased car that runs out of rear grip
rotates, which is not. That is Season 2's understeer mechanism reappearing as a
robustness property, and it supersedes the "margin" explanation in F70.

**Scope, and it is narrow.** One training seed; Episode 10's D6 failure
(`exploration_is_not_growing`, F69) applies unchanged; one evaluation harness where
rule 5 asks for several; the 40%-front car is excluded because the policy cannot
drive it unperturbed at all (that is not fragility); and every rate is a **lower
bound**, since laps that both failed and left the fit are discarded. The claim is
"fragile **for this driver**", not "fragile". Which is the honest form of it, and is
Episode 10's crack arriving on schedule: how different a design is depends on who
is driving it.

**Not established: whether this driver leaves lap time on the table.** It uses
94-98% of peak lateral force (F70), so it is near the *grip* limit — but the
environment logs no lateral acceleration and no per-wheel friction-ellipse
utilisation, so "at the limit" cannot currently be stated as a measurement. That
instrumentation is a prerequisite for Season 4: torque vectoring only acts where
tires are saturated and there is longitudinal force to redistribute, so a TV result
measured with an under-driving policy would be measuring nothing.

**Kept as a standing check.** `a_speed_fragility_tradeoff_is_measurable_inside_the_fit`
and `the_faster_car_is_the_more_fragile_one` are in the Episode 11 report so this
cannot silently revert to a null result, and so the ordering — not just the existence
of failures — is what gets asserted.



### F72 · The double-track model has no drivetrain yaw moment. Torque vectoring would produce exactly zero yaw response. **Blocker for Season 4.** · 2026-07-27

**Source:** `physics/double_track.py` lines 326 and 428 — both yaw-moment
computations — plus a direct experiment.

Both `m_z` expressions in the simulator are:

```python
m_z = p.a * (fy_f * cos(steer) + fx_f * sin(steer)) - p.b * fy_r
```

Longitudinal moment arms only. **There is no `(fx_right - fx_left) * track / 2`
term anywhere in the model.** Track width is used for load transfer, for the
rollover threshold, and for per-wheel velocities in the slip-angle calculation —
but never as a moment arm.

**Verified by experiment rather than by reading.** Driving the rear axle with the
same total force split three ways:

| Split | `m_z` the model computes | drivetrain term it discards |
|---|---|---|
| 1500 N / 1500 N | 0.0000 N.m | 0 (zero by symmetry) |
| 0 N / 3000 N | **0.0000 N.m** | **+2242 N.m** |
| 3000 N / 0 N | **0.0000 N.m** | **−2242 N.m** |

The model returns an identical yaw moment when the entire drive force is moved from
one wheel to the other. On RV-1's 1.495 m rear track that discards 2242 N.m, which
against `i_zz` = 1950 kg.m² is **1.15 rad/s² of yaw acceleration**.

**Why this matters more than a missing term usually would.** Torque vectoring *is*
this term. Season 4 — Episodes 12 through 16, described in the series plan as "the
core; everything above was setup" — is entirely about generating yaw by asymmetric
longitudinal force. Run today, a TV controller would produce **precisely zero** yaw
response, and nothing would error. Episode 12's differential comparison has the same
problem: an open, a limited-slip and a welded differential differ mainly in how much
left/right asymmetry they permit, and the model is blind to all of it.

**A second, smaller gap in the same place.** Drive force is split 50/50 between the
driven wheels unconditionally (`fx[c] = drive_force / 2.0`). That is not a
differential model — it is a fixed split that happens to coincide with a locked
diff in force terms. An open differential's defining constraint is that the pair is
limited by twice the weaker wheel; `optimal_control.py` models that correctly (see
its `diff="open"` handling) and the simulator does not. **The optimiser and the
simulator therefore disagree about the drivetrain**, which is the class of
divergence `tests/test_casadi_tire.py` exists to prevent for the tire.

**How this survived.** Nothing references it. Seasons 1-3 never applied an
asymmetric longitudinal force, so the missing term was always multiplied by zero and
no diagnostic, test or episode could have detected it. D2 checks signs and
conservation but has no asymmetric-drive case. CLAUDE.md already carries the line
"track width is the moment arm for torque vectoring and is only `[LIKELY]`" — the
rule anticipated the term that was never written.

**Required before Episode 12, in order:**

1. Add the drivetrain yaw moment to both `m_z` computations, with a sign convention
   asserted in `schema.py` (positive `m_z` is a left turn under ISO 8855, so more
   force on the RIGHT wheel yaws left).
2. Add a real differential model — open, limited-slip and locked — replacing the
   unconditional 50/50 split, matching `optimal_control.py`'s open-diff constraint
   so the two agree.
3. Add a D2 check with an asymmetric-drive case that **fails** without the moment
   term. This finding was invisible because no check could see it; the fix is not
   done until a check would catch its removal.
4. Re-derive nothing else: the term is additive and zero under symmetric drive, so
   every Season 1-3 result is unaffected. That is worth asserting with a test rather
   than assuming.

### F73 · The yaw-moment equation was inconsistent with the force equations. Fixing it moves the understeer gradient 0.172 → 0.220 deg/g. **Correction of record.** · 2026-07-27

**Source:** `[MEASURED]` — `physics/double_track.py`, before/after on
`skidpad_sweep(30 m, 5–18.75 m/s)` with `understeer_gradient`. Follows from F72.

Fixing F72's missing drivetrain term meant rewriting `m_z` as a per-wheel sum,
`M_z = Σ (x_w · Fy_body − y_w · Fx_body)`. That turned out to add **two** terms, not
one, and the second changes published Season 1–3 numbers. I claimed in F72 that
every earlier result was unaffected. **That was wrong, and this is the correction.**

**The two added terms:**

1. **Drivetrain** — `(track/2)·(fx_right − fx_left)` per axle. Zero under a
   symmetric split, which is why Seasons 1–3 never saw it. This is F72, and it is
   what torque vectoring is.
2. **Steering drag** — `(track_f/2)·sin(steer)·(fy_fl − fy_fr)`. A steered front
   tire's lateral force has a rearward component in the body frame, and the more
   heavily loaded **outside** tire is dragged back harder than the inside one, which
   yaws the car **out** of the corner. Not zero in any steady corner.

**Why this is a fix and not an addition.** The model's force equations already
resolved the front wheels fully into the body frame:

```python
fx_body = fx_f * cos(steer) - fy_f * sin(steer) + fx_r - drag
fy_body = fy_f * cos(steer) + fx_f * sin(steer) + fy_r
```

The old moment expression used only the *lateral* projection and discarded the
longitudinal one entirely. **The same model was resolving forces one way and moments
another, about the same four wheels.** That is an internal inconsistency, not a
modelling choice, and it is the strongest argument for the change: nothing new was
assumed.

**The cost, stated plainly.** The understeer gradient on the reference car moves:

| | K, deg/g |
|---|---|
| bicycle model (F29) | 0.19 |
| double-track, superseded moment | **0.172** |
| double-track, consistent moment | **0.220** |

That is **+28% relative**, on a number Episode 3 published. It is inside the
0.14–0.27 band that the weight-distribution uncertainty already implies (rule 12),
so **no published headline changes at its stated precision** — K remains a
one-decimal number and 0.2 deg/g covers both. But the underlying value moved and
saying otherwise would be false.

**Weak external support for the direction.** F29 puts a real car near 4.1 deg/g with
about 3 of that from Bundorf suspension terms this model does not have. Our value
rising 0.172 → 0.220 closes ~0.05 of a ~3.9 deg/g gap — the right direction, and far
too small to be evidence on its own. Recorded as direction, not validation.

**No double counting.** Steering drag is a tire-force projection, not a suspension
kinematic. It is disjoint from the compliance-steer/roll-camber/roll-steer terms F29
names as the remaining gap.

**Pinned.** `tests/test_drivetrain_yaw.py` decomposes the new moment into the
superseded expression plus these two named terms, so any future change to either is
attributable rather than mysterious, and asserts `body_forces` matches the
projection the acceleration equations use.

**Still to check** (not done, and it belongs with Episode 12): whether
`optimal_control.py`'s four-wheel yaw moment carries the same two terms. If it does
not, the solver and the simulator now disagree about yaw the way F72 found they
disagree about the drivetrain — and `tests/test_casadi_tire.py` exists precisely
because that class of divergence is what makes cross-checks meaningless.

### F74 · ~~Season 2's four-wheel solves must be re-run...~~ **RETRACTED — the measurement compared two different differential models. See F79.** · 2026-07-27

**Source:** `[MEASURED]` — `solve_min_time(long_exit, RV_1 fwd, n_nodes=100,
four_wheel=True, diff="open", entry_speed=32)`, matched to Episode 7's exact
configuration, before and after F73's fix.

| | fwd, 54% front |
|---|---|
| Episode 7 as published | 12.1910 s |
| corrected yaw moment, same 100 nodes, same entry speed | **12.3218 s** |
| shift | **+0.1308 s (+1.07%)** |

**Episode 7's entire rear-drive spread across five weight distributions was
0.098 s.** The correction is **1.3x the size of the finding it sits under**, so the
four-wheel results of Episodes 6, 7 and 8 — and Episode 10's cross-check against
them — are not quotable until re-solved.

**What probably survives, and it must be shown rather than assumed.** The correction
is systematic: every design gains the same missing steering-drag moment, so rank
ordering and trend direction plausibly hold while absolute times all move. That is
exactly the distinction rule 6 draws, and it is the claim Season 2 actually made. But
"plausibly holds" is not a result. The re-solve has to demonstrate the ordering
survives, and if it does not, Season 2's conclusions change.

**Not affected:** anything from the bicycle model (Episodes 1-4), because a two-axle
model has no left/right asymmetry for either new term to act on. Episodes 9-11's RL
results use the simulator, which is now consistent, and their *fragility* conclusion
is an ordering of finish rates rather than a lap time — but Episode 10's OC
cross-check numbers come from Episode 7 and inherit this.

**Re-solve order when it happens:** Episode 6's four solves first (fewest, and they
establish whether the shift is uniform), then Episode 7's ten, then Episode 8's
surface. Seed from the easiest member and retry at 2x iterations (the F57 recipe),
and quote nothing from a solve that did not converge (F39).

### D10 · Model fidelity is labelled on every episode, and "illustrative" is an honourable label. · 2026-07-27

**Decision.** A simplified model is a legitimate way to teach a mechanism; implying
it describes a real car is not. CLAUDE.md rule 15 now carries the three-rung ladder
(bicycle / double-track / Chrono cross-check) with what each rung cannot say, and
every episode states which rung it stands on.

**Rationale.** Requested directly by the user: re-running and re-reporting prior
results is fine, and a simpler model is fine, *provided it is flagged as a simpler
model that is illustrative of the concept rather than realistic.* This is the
model-fidelity counterpart to the existing per-number provenance tags
(`[MEASURED]`/`[SOURCED]`/`[DERIVED]`/`[ASSUMED]`), which label where a number came
from but say nothing about whether the model that produced it resembles a car.

**The anchoring number.** Our understeer gradient is ~0.2 deg/g against a real car's
~4.1 (F29, F73) — roughly **5%** of a real car's understeer, because about 3 of
those 4.1 deg/g are Bundorf suspension terms the double-track model does not have.
That single comparison sets the scale for how much of this project is illustrative,
and it is to be stated in those terms wherever understeer is discussed.

### F75 · The differential's traction model is right and its yaw model has the wrong sign. A force-only model cannot see a locked diff's defining behaviour. · 2026-07-27

**Source:** `[MEASURED]` — `DoubleTrackBackend.split_drive` + `yaw_moment`, left
turn at 9 m/s² lateral, 6000 N demanded on the rear axle.

**What is right, and it is verified.** Parameterising the three differentials on a
single torque bias ratio — open 1.0, LSD 1.5 `[ASSUMED]`, welded ∞ — reproduces the
tractive-force story exactly as textbooks describe it:

| a_y | open | lsd (1.5:1) | locked |
|---|---|---|---|
| 0 m/s² | 6000 N | 6000 N | 6000 N |
| 6 m/s² | 5191 N | 6000 N | 6000 N |
| 9 m/s² | **3880 N** | 4850 N | **6000 N** |

The open differential loses 35% of the demanded force once the inside wheel goes
light, the LSD recovers until it hits its bias limit, and the welded one recovers
all of it. That is Episode 12's traction half and it is sound.

**What is wrong.** The yaw moments that follow are:

| | rl | rr | m_z | reads as |
|---|---|---|---|---|
| open | 1940 | 1940 | 0 N.m | neutral |
| lsd | 1940 | 2910 | **+725 N.m** | turns IN |
| locked | 1940 | 4060 | **+1585 N.m** | turns IN |

**The series plan predicts a locked differential pushes WIDE on power, and this
model says the opposite.** The plan is right and the model is wrong.

**Why, precisely.** I modelled torque distribution as proportional to grip capacity,
which gives more force to the loaded **outside** wheel and therefore a moment into
the corner. That captures the traction benefit and misses the mechanism that
actually dominates a locked diff's handling: **the speed constraint.** A welded
differential forces both wheels to one rotational speed while the outside wheel must
travel further round the corner, so the inside wheel is over-driven and pushes while
the outside is under-driven and drags. That couple yaws the car **out** of the
corner, and it is the classic locked-diff complaint.

Both effects are real and they oppose each other. **A model with no wheel speeds
cannot represent the second one at all**, and `double_track.py` takes `fx` as an
input and never solves for wheel rotation.

**The fix, and it is not a tweak.** The kinematic term is
``Δκ ≈ yaw_rate · track / v``, giving a force couple of roughly
``±½ · K_κ · Δκ`` — inside positive, outside negative — scaled by how much the device
actually locks (0 for open, partial for an LSD, full for welded). That needs
`split_drive` to receive yaw rate and speed, which it currently does not, and needs
the tire's longitudinal slip stiffness. It is a real addition, not a sign flip.

**RESOLVED the same day — see F76.** The couple is implemented as
`speed_couple`, kept as a separate method from `split_drive` because conflating the
two mechanisms is what produced this defect. The traction numbers below stand
unchanged.

**Until it existed, no yaw claim from this differential model was usable.** The
traction numbers above were. Episode 12's payoff line — "a differential is a machine
for deciding which wheel gets to be in charge" — survives on traction alone; its
"locked diff pushes wide" result does not, and must not be written up from this
model as it stands.

**Consequence for Season 4.** Torque vectoring is genuinely torque-commanded rather
than speed-constrained, so a TV actuator's yaw authority does **not** depend on the
missing term — F72's moment arm is what TV needs and that is now correct. But any
Season 4 comparison against a *passive* differential baseline inherits this gap, and
Episode 12 is that baseline.

### F76 · A differential has two mechanisms, and only one of them steers the car. · 2026-07-27

**Source:** `[MEASURED]` — `DoubleTrackBackend.split_drive` and `speed_couple`,
left-hand corner exit at 25 m/s, 0.55 rad/s yaw, 9 m/s² lateral, 6000 N demanded.
Resolves F75.

Modelling a differential as a torque-sharing device alone gets its handling
**backwards**. The two mechanisms are separate, and they are separate methods:

| | what it does | what it decides |
|---|---|---|
| `split_drive` | shares out the demanded force, limited by grip and by the torque bias ratio | **traction** — how much force reaches the road |
| `speed_couple` | resists the left/right speed difference a corner forces | **handling** — which way the car is steered |

**The couple.** In a corner the outside wheel must travel further, so free-rolling it
turns faster. A device that resists that drags the outside wheel below its rolling
speed and pushes the inside above it — opposite slip ratios, opposite forces:

    d_kappa ~ yaw_rate * track / v ,   dF ~ 0.5 * K_kappa * d_kappa * locking

inside pushed forward, outside dragged back. `K_kappa` is
`tire.longitudinal_slip_stiffness`, read from the file, not assumed. Each side is
capped by its own grip so the couple cannot invent force.

**The result, and the sign is now right:**

| device | couple (inside/outside) | net yaw moment | reads as |
|---|---|---|---|
| open | 0 / 0 | **+0 N.m** | neither way |
| lsd (1.5:1, locking 0.5) | +605 / −605 N | **−180 N.m** | pushes wide |
| welded (locking 1.0) | +1211 / −1211 N | **−225 N.m** | pushes wide |

Negative is out of the corner. **The welded diff now pushes wide, as the series plan
and every driver who has used one says it should.** Before the couple it produced
+1585 N.m and turned *into* the corner (F75).

Note the two mechanisms genuinely oppose each other: the grip-bias term alone yaws
in, the couple yaws out, and the couple wins. That is why getting one of them right
was not enough, and why they are reported separately rather than as one number.

**Traction is unchanged and still correct:** of 6000 N demanded with the inside wheel
light, open delivers 3880 N, the LSD 4850 N and welded 6000 N.

**`locking` is the least defensible number here.** 0.5 for the LSD is `[ASSUMED]`; a
real clutch pack's locking varies with torque and with direction (coast versus
drive), which this does not model. Every LSD claim is to be re-run at 0.25 and 0.75
with the conclusion required to hold. Rung 2 (rule 15): this shows the mechanism, not
any particular hardware.

**Pinned, and the pin is verified.** Nine tests in `tests/test_drivetrain_yaw.py`
cover the sign, mirroring left against right, vanishing in a straight line, growing
with yaw rate, shrinking with speed, and ordering the three devices. Four D2 checks
under "Does a welded differential push the car wide?" — and removing `speed_couple`
makes two of them fail with exactly F75's +1585 N.m, so the defect cannot return
unnoticed.

### F77 · A differential's torque bias and its speed resistance are the SAME mechanism. Modelling them as two counted it twice and got the direction backwards. · 2026-07-27

**Source:** `[MEASURED]` — Episode 12's first run. Three of seven checks failed and
all three were right. Supersedes the two-mechanism structure of F76.

**What the checks caught:**

1. `all_three_devices_agree_when_the_wheels_are_equally_loaded` — **the sweep was
   unphysical.** It varied lateral acceleration while holding yaw rate fixed, but a
   steady corner ties them: `a_y = v²/R`. At 25 m/s on a 40 m radius the implied
   lateral acceleration is **1.59 g** on a car that makes about 0.97 g, and at the
   bottom of the sweep the car was yawing at 0.625 rad/s with *zero* lateral
   acceleration. A scenario that cannot happen.
2. `more_locking_means_more_push` — **not monotone**: open +0, LSD −352, welded
   −318 N.m. The welded diff pushed *less* than the LSD.
3. `the_push_wide_conclusion_holds_across_the_assumed_locking_range` — the sign
   flipped at locking 0.25 (+166 N.m), so the conclusion depended on the assumption.

**The root cause is one modelling error, and it is conceptual rather than
arithmetic.** `split_drive` biased torque toward the wheel with more **grip** — the
loaded **outside** wheel. A locking differential does not do that. A clutch pack, or
a weld, resists *relative rotation*: **torque flows from the faster-turning wheel to
the slower one.** In a corner the outside wheel travels further and therefore turns
faster, so a locking device sends torque **inboard**. My model sent it outboard.

Worse, that transfer **is** the yaw couple. `split_drive`'s bias and
`speed_couple`'s couple are not two mechanisms that happen to interact — they are one
physical effect described twice, with opposite signs, which is why the net ordering
came out scrambled.

**The unifying rule, and it explains both behaviours a differential is known for:**

- **No wheelspin** — kinematics dominates. Outside turns faster, torque flows
  inboard, the car is yawed **out** of the corner. That is the locked-diff push.
- **Inside wheel spinning** — the light inside wheel turns faster than kinematics
  alone would have it, so torque flows **outboard**, to the wheel that still grips.
  That is the traction benefit an LSD is bought for.

Same rule, opposite outcomes, selected by which wheel is actually turning faster.
A model that hard-codes a bias direction cannot produce both.

**What this invalidates.** F76's traction table (open 3880 N / LSD 4850 N / welded
6000 N) came from the grip-proportional bias and is **not quotable**. Its yaw-couple
half — the mechanism, the sign, the scaling with yaw rate and speed — stands, because
that part was never the grip bias. Episode 12 is not written and nothing published
depends on this.

**The fix:** one method taking demand, loads and state; equal split first, then a
locking transfer from faster wheel to slower sized by
`½·K_κ·(Δv/v)·locking`, then per-wheel grip caps, then an anti-spin transfer of
whatever the saturated wheel cannot hold — up to the device's bias limit. Open
differential = no transfer at either stage, which correctly leaves it limited by
twice the weaker wheel.

**The lesson, which is the transferable part.** I built the traction model first,
verified it against a textbook table, and it looked right. Then I built the handling
model separately, verified its sign, and that looked right too. **Both were checked
in isolation and the pair was incoherent.** Checking each mechanism against what it
alone should do never asks whether they are the same mechanism. Only running them
together, against an ordering check, did.

### F78 · ~~The rear-drive four-wheel solve cannot be re-solved...~~ **RETRACTED — rear drive converges in 10 s with the correct configuration. See F79.** · 2026-07-27

**Source:** `[MEASURED]` — four solves of `long_exit`, RV-1 rear drive, 100 nodes,
32 m/s entry, four-wheel, open differential. Plan Phase B, time box reached.

| attempt | iterations | wall clock | objective | IPOPT status |
|---|---|---|---|---|
| cold | 8 000 | 497 s | 12.1579 | not converged |
| warm-started from the FWD solution | 8 000 | 605 s | 12.1579 | not converged |
| warm-started from the FWD solution | 20 000 | 1 466 s | 12.1579 | not converged |
| cold, short | 400 | 33 s | 12.1582 | `Maximum_Iterations_Exceeded` |

**Front drive converges in 9 s. Rear drive does not converge in 24 minutes**, and
warm-starting from the geometrically identical front-drive solution does not help at
all — the same value to four decimals every time.

**It is not wandering; it is stuck.** The objective is stable from **400** iterations
to **20 000** — 12.1582 against 12.1579, one part in 4 x 10⁴. It reaches a point in
under a minute and then spends 24 more failing to certify it.

**And that is precisely the trap F39 documents**, which is why the number is not
quotable despite looking settled: *"the objective stopped moving to 1 part in 10⁵"*
is explicitly **not** convergence evidence. An uncertified iterate belongs to a
trajectory that does not quite obey the physics, wrong by 0.1-0.7% in either
direction — and 0.1% here is 0.012 s against an Episode 7 finding whose whole spread
was 0.098 s.

**Invoking plan step B4.** Front-drive results re-solve cleanly and will be
re-reported. **Rear-drive results from Episodes 6, 7 and 8 become unsupported rather
than revised.** That is a worse outcome to publish than a corrected number and it is
the honest one: there is no rear-drive figure I can stand behind until the solve
converges.

**What this costs.** Episode 7's headline comparison was rear drive across five
weight distributions. Episode 6's rear-drive case, and Episode 8's surface, are
affected the same way. Episode 10's cross-check already excluded the 47% rear-drive
car for non-convergence (F64); it now loses the rest.

**Remedies not yet tried**, in the order worth trying next:

1. **Regularisation.** The objective is documented as degenerate wherever the car has
   spare road, which is what `steer_rate_weight` exists for. A problem that reaches a
   point and cannot certify it is what a degenerate objective looks like — a flat
   direction leaves the KKT conditions unsatisfiable to tolerance. Raising the weight
   is the cheapest next move and was outside this phase's time box.
2. **Continuation in the coupling.** Scale the new drivetrain yaw term from 0 to 1
   across a sequence of solves, warm-starting each from the last.
3. **A coarser grid solved first**, then interpolated up — the F57 recipe applied to
   node count rather than to design.

**Never** loosen `ipopt.tol` to make this pass. The whole point of the gate is that
it is not ours to move.

### F79 · Retraction of F74 and F78. Three of my own errors, none of them physics. · 2026-07-27

**Source:** `[MEASURED]` — Episode 7's exact configuration (`diff="ideal"`, bicycle
seed, rear drive warm-started from the solved front-drive car of the same balance),
with the yaw-moment fix toggled by `optimal_control._LEGACY_YAW_MOMENT`.

**The legacy setting reproduces the published numbers exactly**, which is what makes
everything below trustworthy:

| | fwd 0.54 | rwd 0.54 |
|---|---|---|
| published | 12.1910 | 12.0909 |
| legacy yaw moment, re-run | **12.1910** ✓ | **12.0909** ✓ |
| corrected yaw moment | **12.0537** | **12.0864** |
| delta | **−0.1373 s** | **−0.0045 s** |

**Rear drive converges in 10 seconds** — ten times *faster* than the legacy solve's
99 s. There was never a convergence regression.

**Three errors, and not one of them was in the physics:**

1. **I solved `diff="open"` and compared it against Episode 7's published
   `diff="ideal"` numbers.** A different and far more constrained problem. Every
   "regression" measurement in F74 and F78 was that mismatch.
2. **The solver fix went into the wrong function.** A `str.replace(..., 1)` matched
   the *first* occurrence of the force/moment block, which is the **bicycle** model;
   `dynamics_4w` was never changed. So F74's "+0.13 s from the yaw fix" measured
   nothing but the differential mode — the four-wheel yaw moment was still the old
   one throughout.
3. **That misplaced edit silently broke the bicycle path**, deleting its `a_x`/`a_y`
   definitions. Nothing exercised it until the correct recipe needed a bicycle seed,
   at which point it raised `NameError`. It had been broken for hours.

**What actually diagnosed it**, since two plausible leads did not: the literature
points at IPOPT's `mu_init` for minimum-lap-time problems, and the `fmax(fz, 1.0)`
floor is a known non-smoothness. **Both were dead ends here** — `lg(mu)` reached
−10.8, so the barrier was fully driven down, and the lightest wheel load was ~900 N,
nowhere near the 1 N floor. What found it was **reading IPOPT's iteration log**
(constraint violation oscillating at 2.5e-2 with step norms of 108 — cycling, not
slow convergence) and then **diffing my call signature against Episode 7's**.

**The transferable lesson.** F73's process rule was "measure before claiming". That
was necessary and not sufficient: I *did* measure, three times, and every
measurement was against the wrong baseline. **A measurement is only as good as the
claim that the two sides differ in exactly one thing.** The cheap guard is to
reproduce the published number first — had I checked that my "before" case returned
12.1910, all three errors would have surfaced in the first ten minutes instead of
after two hours of solver time.

**`_LEGACY_YAW_MOMENT` is kept** in `optimal_control.py` as a documented diagnostic
hook, precisely so this class of question is answerable by A/B rather than by
argument. It must never be set for a published solve.

### F80 · The corrected yaw moment reverses the front-drive/rear-drive ordering. **Escalated.** · 2026-07-27

**Source:** `[MEASURED]` — as F79, RV-1 nominal 54% front, `long_exit`, 100 nodes,
32 m/s entry, `diff="ideal"`, both solves converged, envelope occupancy 0.

| | fwd | rwd | verdict |
|---|---|---|---|
| published (legacy moment) | 12.1910 | 12.0909 | **rear drive faster by 0.100 s** |
| corrected moment | 12.0537 | 12.0864 | **front drive faster by 0.033 s** |

**The fix moves front drive 30× more than rear drive** (−0.137 s against −0.005 s),
and that asymmetry is physically coherent rather than suspicious: on a front-drive
car the driven wheels are *also* the steered ones, so both new terms — the drivetrain
moment and the steering-drag moment — act on the same axle. On rear drive only the
drivetrain term does, and the steered front axle carries no drive force.

**Episode 6's conclusion is that "front drive costs at least 0.10 s here."** With the
corrected moment that is wrong in sign, not merely in magnitude. Episode 6 line 162
already records an earlier draft in which "the sign flipped and front drive came out
marginally ahead" — which is what the corrected physics now says.

**The full sweep, both ways.** The legacy setting reproduces **all ten** published
numbers to four decimals — including the 47% rear-drive case, still uncertified
after 831 s exactly as published. That is what makes the corrected column evidence.

| Front mass | published (legacy) | corrected | |
|---|---|---|---|
| 40% | RWD by 0.202 s | RWD by 0.116 s | |
| 47% | RWD by 0.119 s | RWD by 0.037 s | |
| 54% | RWD by 0.100 s | **FWD by 0.033 s** | flips |
| 61% | RWD by 0.063 s | **FWD by 0.110 s** | flips |
| 65% | RWD by 0.032 s | **FWD by 0.167 s** | flips |

**The correction is uniform for front drive (−0.130 to −0.137 s, spread 0.007) and
wildly non-uniform for rear drive (−0.055 to +0.063, spread 0.118).** Seventeen
times more scatter, which is why the ordering moves at all.

**Three further consequences.**

1. **Rear drive's optimum moves from 54% to 47% front**, and its sensitivity to
   balance doubles: 0.21 s across the range against the 0.10 s previously reported.
   Front drive's optimum stays at 54%.
2. **Every solve now converges.** The 47% rear-drive case had never converged in the
   project's history — 831 s of failure on the legacy moment, 15 s and certified
   with the fix. It was a standing exclusion in Episode 7 *and* in Episode 10's
   cross-check.
3. **Episode 6's open-differential comparison is still unavailable.** The rear-drive
   open-diff solve stops on the iteration limit at 8000 iterations. Every Episode 6
   claim now uses the ideal differential, where all four solves converge.

**Both episodes have been rewritten around the corrected numbers**, including
explicit retraction paragraphs — Episode 6's "rear-wheel drive is faster, under
either assumption" and Episode 7's "it never reaches zero". In both cases the
previous draft had the trend right and the intercept wrong, because the missing term
penalised the steered-and-driven axle specifically and so held front drive back at
every point of the sweep.

**The better story is the one the correction produced**, not the one it destroyed:
whichever end of the car carries the weight is the end that should drive it, and the
crossover sits near 50:50 — which is also why a real front-drive hatchback is
nose-heavy. Episode 6's power sweep says the same thing from the other direction:
at 101 hp front drive is 0.026 s quicker, at 402 hp it is 0.287 s slower.

## Session 13 — the classical torque-vectoring controller · 2026-07-27

### F81 · `Track.centreline` depended on how many points you asked it for, and two callers disagreed about where the road was by 0.098 m. **Defect, drawing and driving only.** · 2026-07-27

**Source:** `[MEASURED]` — `Track.to_xy` (which samples the centreline at 2,000
points) round-tripped through `driver.TrackLocator.locate` (4,000 points), on
`long_exit`.

The centreline was integrated with left-endpoint Riemann sums:

```python
heading = cumsum(ds * k[:-1])
x       = cumsum(ds * cos(heading[:-1]))
```

Both are first-order, so the path drifts by O(ds) and **the geometry therefore
depended on `n_points`**. Place a point 2.00 m to the right of the centreline with
`to_xy`, ask the locator where it is, and the answer came back **2.098 m** — a 3.3%
error in a lateral offset, produced by two pieces of code that each believed they
were describing the same road.

| where | disagreement, 2,000 against 4,000 points |
|---|---|
| opening straight | 0.000 m |
| corner entry, 75 m | 0.012 m |
| mid-corner, 100 m | 0.067 m |
| corner exit onward | **0.098 m**, and it stays there |

The error accumulates through the corner and then persists for the rest of the
track, which is the signature of a heading error rather than a position one.

**Fixed** by integrating heading with the trapezoid rule and position with the
midpoint heading. Both are second order, and the two grids now agree to under a
millimetre. `tests/test_driver.py::test_the_locator_inverts_the_drawing_map` pins
it by round-tripping the two maps against each other rather than by restating
either formula.

**Scope, stated precisely.** Nothing physical reads `centreline`: the optimal
control and the RL environment both integrate `curvature(s)` directly, and no
published number in Seasons 1–3 moves. It is the **drawing** map, and from this
episode on the **driver's** map. Season 1–3 figures drawn through it are displaced
by up to 0.098 m on a 393 m track, which is invisible at figure scale, and have
**not** been regenerated — a deliberate call, recorded here rather than left
implicit.

**Why it is worth an entry anyway.** This is the F36 family again: a geometry
function that is quietly wrong renders a completely plausible picture and nothing
errors. It had been in the repository since Episode 4, and it was found in ten
minutes by checking one map against its own inverse — the cheapest external check
there is (rule 11).

### F82 · The classical two-layer controller works, and on a lap it is worth half a percent. · 2026-07-27

**Source:** `[MEASURED]` — `experiments/ep13/run.py`, `long_exit`, closed-loop
driver (`physics/driver.py`), `grip_use` swept to failure and bisected to 0.002.
Reference model built from the car: K = 0.204 deg/g, grip ceiling 0.951 g, both
`[MEASURED]`.

| configuration | cornering limit | best valid lap | corner section |
|---|---|---|---|
| open differential | 1.041 | 14.508 s | 5.483 s |
| limited-slip (Ep 12's device) | 0.969 | 14.719 s | 5.635 s |
| allocator, yaw demand forced to zero | 1.063 | 14.516 s | 5.515 s |
| **torque vectoring, four wheels** | **1.095** | **14.434 s** | **5.445 s** |
| torque-vectoring differential (rear axle) | 1.073 | 14.562 s | 5.531 s |

**Both layers do what they claim.** The allocator delivers the moment the PID asks
for to within 60 N·m of a 996 N·m peak — 6% at the single worst instant of the lap
and near zero everywhere else, the shortfall coming from the allocation being
computed once per control interval on the previous instant's loads, as an ECU must.
RMS yaw-rate error against the same reference model, through the same corner at the
same aggression: **passive 0.1662 rad/s, controlled 0.0197 — 88% lower.** That is a
far more direct measurement of "it works" than any lap time.

**What it is worth, four ways of asking:**

| | gain |
|---|---|
| cornering limit | **+5.18%** |
| skidpad, sustained lateral acceleration | **+1.30%** (0.939 → 0.951 g) |
| corner section, brake point to full exit | +0.69% |
| whole lap | **+0.51%** |

The series plan expected 1–4% of lap time. **We measure an order of magnitude less,
and the reason is the track rather than the controller:** 260 of `long_exit`'s
393 m are a straight where the car is power-limited at 4500 N and a yaw controller
has nothing to do. The cornering-limit number is the one that describes what
changed.

**The outside check holds.** The best published figure is ~9% for an FSAE car on a
skidpad — the most favourable manoeuvre there is, and therefore a ceiling. Ours on
the same manoeuvre is 1.30%. A result above 9% would have been evidence of a bug
(rule 2). **`[SOURCED — citation outstanding]`**: that 9% is the series plan's
figure, stated there without a reference and not traced back to a paper here. Rule
2 says to mark such a band rather than imply a citation, and the figures carry the
same marking. Tracing it is cheap and should happen before Episode 14 leans on it.

**The tires were saturated, which is the precondition for any of this meaning
anything.** The quickest valid controlled lap peaks at 0.969 g against a measured
steady-state ceiling of 0.951 g and reaches 9.94° of slip, where the tire's peak at
this load is near 10.4° (F71). Torque vectoring only acts where there is spare
longitudinal capacity to move, so a TV result measured with an under-driving car
measures nothing.

**Fidelity: rung 2.** Four independently commanded wheel forces is a four-motor
electric car; the rear-axle version RV-1 could actually have is worth about 60% as
much (+3.07% of cornering limit against +5.18%). Track width is `[LIKELY]` and is
the moment arm: at ±3% the gain is +5.36% and +5.00%. **See F83 and F84 before
quoting any of this** — half of it is not yaw control, and the size of all of it
depends on how the driver was tuned.

### F83 · Roughly half of it is not torque vectoring at all, and the split moves. · 2026-07-27

**Source:** `[MEASURED]` — the `alloc` condition of `experiments/ep13/run.py`: the
same four-wheel allocator with its yaw demand forced to zero.

Both the allocator-only car and the fully controlled car replace the differential,
so both get brake and drive force spread across four wheels in proportion to what
each has left. **Only one of them also asks for yaw.** The control condition is the
only thing separating "a computer meters four wheels separately" from "a controller
vectors torque", and they are different claims with different consequences for
Episode 15.

On the lap, the allocator alone accounts for **40%** of the cornering-limit gain
(open 1.041, allocator 1.063, full controller 1.095).

**That share is the least stable number in the episode and is quoted as a range.**
It moved from 77% to 40% when the allocator went from being re-solved inside the
integrator to holding its command for the control interval — a modelling fix, not a
physics change. Across the six sensitivity runs it spans **38–56%**. What survives
every one of them is the ordering: open < allocator-only < full controller.

**On the skidpad the split inverts completely.** Sustained lateral acceleration:
open 0.939 g, allocator-only **0.932 g**, full controller 0.951 g. On a steady
circle there is no braking to distribute and almost no drive force to spread, so the
lower layer has nothing to be clever with and lands *below* the passive car — the
whole skidpad gain is yaw control. **The same two layers therefore split the credit
in opposite proportions in the two manoeuvres**, which is an argument for reporting
the decomposition per manoeuvre rather than once.

### F84 · The measured value of the controller depends on how the driver was tuned, by more than the controller is worth. **A check fails on this and it is not being loosened.** · 2026-07-27

**Source:** `[MEASURED]` — `experiments/ep13/run.py` sensitivity block, `t_look`
varied ±30% about its `[ASSUMED]` 0.55 s, everything else held.

| driver preview | passive limit | controlled limit | gain |
|---|---|---|---|
| 30% less (0.385 s) | 1.057 | 1.054 | **−0.34%** |
| nominal (0.55 s) | 1.041 | 1.095 | **+5.18%** |
| 30% more (0.715 s) | 0.996 | 1.111 | **+11.55%** |

A single `[ASSUMED]` number in the *driver* — not in the car, not in the controller
— moves the headline from "nothing measurable" to "+11.6%". The −0.34% is 0.0036 in
`grip_use` against a bisection resolution of 0.002, so it is a wash rather than a
reversal; but a wash is not +5%.

**The mechanism is not mysterious.** A shorter preview makes the pure-pursuit driver
steer later and harder, which suits the passive car and gives the yaw controller a
reference signal full of the driver's own transients to chase. A longer preview
makes the driver smoother and slower to correct, which the passive car cannot
recover from and the controller can.

**`D-ep13`'s `the_conclusion_survives_the_driver_being_tuned_differently` therefore
fails, the article says so, and the threshold has not been moved** (F69's rule). It
is the only one of the report's twelve checks that fails.

**The transferable part.** A driver aid is developed against a driver, and the pair
is tuned together whether or not anyone says so. Any measurement of what such a
system is worth carries the driver model inside it, and reporting one number for it
is reporting half the experiment. Episode 14 hands the same car to a learned driver;
this finding is why that comparison has to hold the driver fixed or vary it
deliberately, and never leave it implicit.

### F85 · Under a disturbed driver the controller is worth far more than it is worth to a perfect one. · 2026-07-27

**Source:** `[MEASURED]` — 40 seeded laps per configuration at `grip_use` 0.991,
`steer_noise` 0.15 (Episode 11's convention and value). A lap counts only if it
finished, stayed on the road and stayed inside the ±12° tire fit.

| configuration | valid laps | lap time |
|---|---|---|
| open differential | **31/40** | 14.602 ± 0.015 s |
| limited-slip | **3/40** | 14.659 ± 0.039 s |
| allocator only | 40/40 | 14.608 ± 0.009 s |
| torque vectoring, four wheels | **40/40** | **14.580 ± 0.006 s** |
| torque-vectoring differential | 40/40 | 14.596 ± 0.015 s |

The controller converts a 78% completion rate into 100% and cuts the lap-time
scatter by more than half. **That is a much larger effect than the half percent of
lap time it is worth to a driver who never makes a mistake** — and it is the
justification production stability systems are actually sold on, which our
undisturbed lap could not have shown.

It also puts Episode 11's finding in a new light: F71 measured how a *design*
survives disturbance; this measures how a *controller* does, with the design held
fixed. Both say the same thing about what "fast" means when the day is not perfect.

**The LSD's 3/40 is the strongest single number in the episode**, and it should be
read carefully: at this aggression the passive limited-slip car is already past its
own limit (0.969), so it is being asked to do something it cannot do cleanly even
undisturbed. It is evidence about that device at that demand, not a general claim
that limited-slip differentials fail nine laps in ten.

### F86 · The reference model is a choice, and asking for a pointier car than the car is helps slightly. · 2026-07-27

**Source:** `[MEASURED]` — `experiments/ep13/run.py` reference sweep, `k_us` varied
with everything else held.

| target understeer gradient | cornering limit |
|---|---|
| 0.204 deg/g (the car's own, `[MEASURED]`) | 1.095 |
| 0.100 deg/g | 1.097 |
| 0.000 deg/g (neutral) | 1.100 |
| −0.150 deg/g (pointier than neutral) | 1.102 |

Monotone, and small: 0.007 in `grip_use` across the whole range, against a
bisection resolution of 0.002. **Reported as a weak monotone trend, not as a
result** — three-and-a-half resolution units over four points is the sort of margin
this project has learned to state and not lean on (F70).

Its interest is what it implies rather than its size. The upper layer's entire
model of "what the car should be doing" is one coefficient, and moving it changes
the answer. The series plan reports that published work on optimising torque
vectoring for lap time finds the best times come from *allowing* deviations from
neutral yaw-rate tracking — that the reference model is itself a constraint.
**`[SOURCED — citation outstanding]`**: that is the plan's assertion, stated there
without a reference, and it has not been traced back to a paper. Our sweep is
consistent with it in direction and is far too small to be evidence for it. The same
applies to the ~9% skidpad ceiling F82 is checked against, and both are marked
rather than implied (rule 2).

**This is the hook for Episode 14, and it is a real one:** a learner given the same
four wheels and the same stopwatch is not handed a reference model at all.

## Session 14 — a visualisation audit of Episodes 1–13 · 2026-07-27

A full pass asking, of every published episode, whether it has a pictorial figure
and a technical one (rule 1), and whether every headline number has a figure
behind it rather than living only in a table. Findings F87–F89.

### F87 · Two episodes' figures could not be regenerated from their own `run.py`. **Defect, rule 10.** · 2026-07-27

**Source:** `[MEASURED]` — `experiments/ep09/run.py` and `experiments/ep10/run.py`,
`figures()` functions, cross-referenced against the SVGs their own articles embed.

Episode 9 embeds six figures; `figures()` wrote three. Episode 10 embeds five;
`figures()` wrote three. The missing five — `04-two-environments.svg`,
`05-path-review.svg`, `06-noise-was-braking.svg` (Ep 9) and `04-path-review.svg`,
`05-five-lines.svg` (Ep 10) — were sitting in `out/` with no code path that
produced them any more. `viz.review_figures.path_review` and `.line_compare`, and
`viz.conditioned_figures.line_family_figure`, were all defined, exported, and
called from nowhere. Running `python -m experiments.ep09.run --figures-only` today
would have silently regenerated half an episode's figures and left the other half
whatever was last on disk.

**Fixed for Episode 10** by wiring `line_family_figure` and `path_review` into its
`figures()`, adding the `xi` and `finished` fields their calls need to the
per-fraction trace loop, and regenerating via `--eval-only` (no retrain: the
policy is the artefact, F68's rule). Both now reproduce bit-for-bit.

**Fixed for Episode 9** the same way, for `path_review` and `line_compare`, after
finding and fixing a second, deeper bug — see F88. `04-two-environments.svg` is
deliberately **not** wired back in; see F89.

**Also added:** an `--eval-only` mode for Episode 9's `run.py`, matching Episode
10's — it did not have one, so the only way to add a field to a saved trace was a
1.2M-step retrain.

### F88 · The trace Episode 9's core narrative depends on was drawn from an unseeded RNG. **Defect — the figures were not reproducible even before this session.** · 2026-07-27

**Source:** `[MEASURED]` — `experiments/ep09/run.py`'s `_sampled()`, before and
after.

```python
def _sampled(model):
    def act(obs):
        d = model.distribution(torch.as_tensor(obs, dtype=torch.float32))
        return d.sample().numpy()          # torch's GLOBAL rng, never seeded
    return act
```

Regenerating Episode 9's figures in a fresh process (exactly what F87's fix makes
possible) drew a different sample than whatever produced the published ones: the
"sampled" trajectory went off the road at 139 m, flatly contradicting the article's
own numbers — "arrives at 21.5 m/s ... and it gets round". The deployed
(mean-action) trajectory is unaffected, because it never samples; it reproduced
the published 129 m exactly, which is what made the sampled mismatch legible as a
bug rather than noise.

**This was already broken, not newly broken.** `_sampled` never seeded torch, in
the version that produced the published figures either — it was reproducible only
by the accident of whatever global RNG state a given process happened to be in
when it reached that call. A rerun of the ORIGINAL `main()` (full retrain) would
have hit this too, just less visibly, since retraining itself consumes an
unpredictable number of draws from the same global generator.

**Fixed** by giving `_sampled` its own `torch.Generator`, seeded explicitly
(`SAMPLE_SEED = 1`). That value is not a free choice — a 20-seed sweep (`for
torch_seed in range(20)`) found 13 of 20 finish the corner (65%, consistent with
the D6-reported 75% aggregate finish rate over many more samples), and seed 1 is
the first that finishes and reproduces the published numbers to within rounding:

| | published | reproduced at `SAMPLE_SEED=1` |
|---|---|---|
| deployed speed at corner entry | 22.9 m/s | **22.90** |
| sampled speed at corner entry | 21.5 m/s | **21.51** |
| deployed minimum throttle, entry straight | "never below +0.32" | **+0.319** |

**The mechanism is real and now reproducible**; it was never in doubt — the D6
aggregate evaluation (which is unaffected, since it does not go through
`_sampled`) already reported the 61-percentage-point deployed/sampled gap this
session and every prior one. What was fragile was the ONE illustrative trajectory
the figures and the prose quote specific numbers from.

**The transferable lesson.** A figure whose caption survives is not evidence the
code that made it is correct — it is evidence nobody has re-run it in a fresh
process yet. This is F68 and F81's lesson again, in a third place: RNG state is
exactly as capable of quietly making a figure irreproducible as a stale cache or a
first-order integrator, and less likely to be suspected because "add a seed" reads
like tidiness rather than correctness.

### F89 · One figure's likely source could not be safely reconstructed, and was left orphaned rather than guessed. · 2026-07-27

**Source:** `viz.learning_figures.failure_figure`, cross-referenced against
`experiments/ep10/out/traces.npz`'s `f054_*` (Episode 10's real, saved, nominal
policy).

The obvious candidate for `experiments/ep09/out/04-two-environments.svg` — the
only unwired function that takes exactly two cases and is about comparing failure
modes — carries a hardcoded caption asserting its right-hand car "is travelling
sideways and backwards... asked for forces at over 120 degrees" and reaches
"21.0 m/s against 20.2 inside the envelope" by exploiting the tire model. Episode
10's actual saved policy does no such thing: its nominal (54% front) rollout
finishes with a worst slip of 6° and 0% of steps beyond the tire fit — the
opposite of what the caption describes.

**Not wired in.** Publishing `failure_figure` against Episode 10's real trace would
produce a figure whose caption contradicts its own data — F68's failure mode,
committed on purpose this time instead of by accident. The pre-existing
`04-two-environments.svg` on disk is left as is (the article's embed still
resolves to a real file); `--figures-only` now says explicitly that it is not
regenerating it and why.

**Open question, not resolved here:** what `failure_figure`'s caption describes —
a policy exploiting slip past 120° — sounds like an EARLIER, pre-fix iteration of
Episode 10's training (before whatever made the envelope penalty effective), not
the one that shipped. If that iteration's trace still exists somewhere, this
figure could be correctly rebuilt from it. If it does not, the honest fix is to
rewrite `failure_figure`'s caption to describe what the shipped comparison
actually shows, or retire the function. Neither is a visualisation-audit task; both
are follow-ups.

### Smaller additions from the same audit

- **Episode 2** had no technical (axes) figure at all — a table of four load/grip
  points was the only evidence for an episode titled after a graph. Added
  `viz.tire_figures.mu_vs_load_figure`: peak μ against load (the actual curve the
  table sampled) and what a fixed total costs a pair as it is shared less evenly —
  both computed fresh from the tire model, not restated from the table. `[MEASURED]`,
  fit slope −0.0459/kN matches the episode's own quoted −0.046.
- **Episode 12**'s sharpest number — "the open differential throws away 35% of the
  demanded force" — had no dedicated figure; `mechanism_figure` only ever drew the
  welded device. Added `viz.diff_figures.traction_figure`: three cars, one
  throttle opening, delivered-force bars for open/limited-slip/welded side by
  side. Data already in `results.json`, no new computation.
- **Episode 7**'s `balance_card` docstring promised four panels (lap time,
  understeer gradient, apex position, brake release) and built three. Added panel
  D. Doing so surfaced F90, below — the fourth panel's own number turned out to be
  stale.

### F90 · Episode 7's "brake release moves 15.9 m" predates the yaw-moment correction and is wrong under the corrected physics. **Defect, and the correction of record.** · 2026-07-27

**Source:** `[MEASURED]` — `experiments/ep07/out/results.json` (`brake_release_s`
per drivetrain per front-mass-fraction), from a full fresh re-solve of all ten
cases, all converged, envelope occupancy 0.

F46 reported brake release moving **15.9 m** across the 40–65% front sweep, "four
node spacings, unambiguous." That number was measured before F72/F73 added the
drivetrain and steering-drag yaw moment terms — the same fix that F79/F80 record
moving Episode 7's lap times and reversing its drivetrain ordering. The lap-time
table and the crossover narrative were corrected for it (F80). The brake-release
number was not, and it should have been: it is computed from the same corrected
solves and it moved.

| | rwd | fwd |
|---|---|---|
| 40% front | 71.1 m | 68.4 m |
| 47% front | 66.1 m | 65.2 m |
| 65% front | 75.9 m | 75.6 m |

Span across both drivetrains and the whole sweep is now **~10.6 m** — about 3 node
spacings at this solve's 100-node grid, not 4 — still comfortably above node
resolution and still monotonic (more front weight, later braking), so **the
finding's direction and its status as a real, resolvable effect are unchanged.**
Only the magnitude was stale. `episodes/ep07-where-you-put-the-weight.md`'s table
and prose are corrected to match; F46 is superseded by this entry for the
magnitude, not for the direction.

**How this survived a correction pass that touched everything else in the same
episode.** F80 re-solved and re-checked the lap-time table, the understeer
gradient, and the crossover fraction, because those were the numbers the
escalation was about. Brake release was not part of that headline and nobody asked
whether a number computed from the same corrected solves needed re-reading. The
lesson is the same shape as F79's: a fix to shared machinery invalidates every
number downstream of it, not only the ones the fix was motivated by, and the way
to catch the rest is to regenerate every figure and reread every table rather than
trust that "the important ones were checked."

## Session 15 — Episode 14 infrastructure and pilot · 2026-07-27

### F91 · The RL action space grows to variants H and E without disturbing Season 3, and a pilot run confirms the pipeline produces something sane. · 2026-07-27

**Source:** `[MEASURED]` — `physics/rl_env.py` (`EnvConfig.tv_mode`),
`diagnostics/D6_training_health.py`, `experiments/ep14/run.py --pilot`, 60,000
steps per variant, seed 0.

Episode 14 asks whether an RL policy, given the same four wheels and no
hand-built reference model, agrees with Episode 13's classical two-layer
controller. Per `docs/vehicle-codesign-research-plan.md` Phase 4b, two new
variants:

- **H (hybrid)** — the policy's action grows by one: an `Mz` DEMAND, fed
  through the *identical* `physics.torque_vectoring.Allocator` variant C
  uses. `act_dim` 3.
- **E (end-to-end)** — the policy's action REPLACES the net drive-force
  channel with four raw per-wheel force fractions, scaled by each wheel's own
  grip-based capacity (`Allocator.capacities()`), no allocator call at all.
  `act_dim` 5, no separate demand channel — matching the plan's "none" lower
  layer exactly.

Both route through `DoubleTrackBackend.attach_torque_vectoring`, the same hook
`physics/driver.py` built for Episode 13 — no backend changes were needed.
`schema.ACT_BICYCLE` is untouched; the extra action dimensions are consumed
inside `DrivingEnv.step()` before anything reaches the backend's own action
space.

**`tv_mode="none"` reproduces every Season 3 result bit-for-bit** — all 18
pre-existing `test_rl_env.py` tests pass unchanged, plus a new explicit seal
test comparing the bare default against `tv_mode="none"` on identical seeds
and actions.

**Also fixed, not deferred: the environment logged no lateral acceleration
and no per-wheel friction-ellipse utilisation**, flagged in `HANDOFF.md` as
the reason there was previously no way to verify a torque-vectoring result was
measuring anything a saturated tire actually did. `_record()` now logs `a_y`
and per-corner `fx/fy/fz`; `rollout()` reports `peak_a_y_g` and
`mean_utilisation`, mirroring `physics.driver.Lap`'s own properties so
Episode 13 and 14 figures can share plotting code.

**One new D6 check**, additive: `exploration_covers_the_torque_vectoring_action`
inspects the model's current (post-training) `log_std` on the new action
dimension(s) — collapsed-to-zero or blown-out-past-the-range are both failures,
and for variant E, a >10x spread across the four wheels' exploration scale is
too (a policy that never learned to use one wheel would look exactly like
that — F52's mismatched-exploration-scale failure, in a new action space).
A no-op for every `tv_mode="none"` run, so Episodes 9-11 are unaffected.

**The pilot** (60,000 steps/variant, far short of Episode 10's 5,000,000, and
read as pipeline validation, not a result — CLAUDE.md rule 5's seed discipline
does not even apply to a number this provisional):

| | wall-clock (60k steps) | D6 | peak lateral g | mean utilisation |
|---|---|---|---|---|
| H | 208 s | FAILED (3/13) | 0.879 | 0.45 |
| E | 104 s | FAILED (3/12) | 0.613 | 0.25 |

Both D6 failures are exactly what an undertrained policy should produce
(`the_deployed_policy_completes_the_task`, `the_off_track_rate_came_down`,
and one of `greedy_and_stochastic_agree` / `exploration_is_not_growing`) —
none of the three failures is the new exploration-scale check, which passed
for both, with a healthy, near-uniform spread across E's four wheels
(std 0.221-0.229, a 1.0x ratio). The realized-`Mz`-vs-distance sanity figure
(`experiments/ep14/out/01-pilot-sanity.svg`) shows three non-degenerate,
distinctly different curves for C, H and E — the pipeline is producing
something to compare, not noise or a flat line.

**What this pilot is for, extrapolated rather than assumed.** Linear scaling
from 60,000 to Episode 10's 5,000,000 steps gives **~4.8 hours per seed for H**
and **~2.4 hours per seed for E** — before rule 5's 3-5 seeds per
configuration, which multiplies straight through (roughly 14-24 hours for H
alone, 7-12 for E, run serially). This is the number the approved plan's pilot
phase exists to surface before any production run is committed to, and it is
reported rather than acted on — the decision to spend that much wall-clock,
or to look for a smaller production step count first, is not this session's
to make alone.

### F92 · ~~Production training (3 seeds × 2 variants, 5,000,000 steps): neither RL variant reliably agrees with the classical controller, and the seeds disagree with each other.~~ **RETRACTED by F93 — read that instead.** · 2026-07-28

> **This entry's conclusion is withdrawn.** Every per-seed number below is
> correctly measured, but all six describe the *last* checkpoint of a run that
> was never checkpoint-selected, and every one of the six seeds had already
> passed through a clean, in-envelope, full-distance window that was discarded.
> The D6 pass rates and the "end-to-end is more prone to the tire-model
> exploit" reading are therefore artefacts of model selection. Kept unedited
> as the record of what was published and why it was wrong. See **F93**.

**Source:** `[MEASURED]` — `experiments/ep14/run.py --variant={H,E} --seed={0,1,2}`,
5,000,000 steps each, `envelope_penalty=0.5`, aggregated via `--aggregate`.
Full detail in `experiments/ep14/out/results.json` and `production_report.json`;
per-seed D6 reports in `diagnostics/out/D6-ep14-{H,E}_seed{0,1,2}.md`.

| Variant | Seed | Wall-clock | D6 | Finished | Distance | Peak lat. g | Worst slip | Envelope occupancy |
|---|---|---|---|---|---|---|---|---|
| H | 0 | 13,552 s (3.76 h) | FAILED (critic, tire model) | True | 393 m (100%) | 1.00 | 14.8° | 4.0% |
| H | 1 | 14,501 s (4.03 h) | FAILED (greedy/stochastic agree, tire model) | True | 393 m (100%) | 0.96 | 10.5° | 0.0% |
| H | 2 | 13,880 s (3.86 h) | FAILED (deployed-policy, greedy/stochastic agree) | False | 136 m (35%) | 0.98 | 9.4° | 0.0% |
| E | 0 | 7,167 s (1.99 h) | FAILED (6 checks) | False | 131 m (33%) | 1.01 | 13.5° | 24.7% |
| E | 1 | 7,119 s (1.98 h) | FAILED (5 checks) | False | 353 m (90%) | 1.01 | 16.8° | 3.5% |
| E | 2 | 7,097 s (1.97 h) | **PASSED** | True | 393 m (100%) | 0.98 | 8.8° | 0.0% |

**H's D6 pass rate is 0/3; E's is 1/3.** Neither variant converges to a policy
this project's own training-health battery calls clean, at this budget, this
reward, this envelope penalty.

**The two variants fail differently, and the difference is informative.** H's
three seeds cluster near the tire's own ±12° fit (9.4–14.8°) and its failures
are the mild kind — an optimistic critic, the greedy and sampled policies
disagreeing with each other — not a policy that has run away from the physics.
Two of its three seeds finish the full corner. E's three seeds split sharply:
one (seed 2) trains cleanly, passes every D6 check, and finishes; the other two
find a way to operate substantially outside the tire's own fit (13.5° and
16.8°, up to 24.7% of the run spent past the bound) and neither finishes —
**the same tire-model exploit Episode 9 first found (F53/F56), reappearing
under the identical envelope penalty (0.5) Episode 10's protocol and this
episode both use.** An end-to-end action space with no allocator to constrain
it is, on this evidence, more prone to finding that exploit than a policy whose
lower layer is fixed to the classical allocator — itself a real result about
*where* an allocator helps, which is the sharper question this episode set out
to ask.

**The representative-seed rule (median by finish distance, not best-of-N —
F71) surfaces its own point here.** E's three finish distances are 131 m, 353 m
and 393 m; the median is seed 1 at 353 m — one of the two exploit seeds, NOT
the one clean pass (seed 2, which would be picked by any best-of-N rule and
would flatter the result). Every E figure and number in this episode that says
"representative" is seed 1's trace, not seed 2's, on purpose.

**Methodological correction made before publishing, not after:** the first
draft of the friction-circle figure (`envelope_escape_figure`) picked each
seed's peak-*utilisation* instant to snapshot, which need not be the same
step as that seed's worst *slip angle* — and briefly showed a smaller angle
on the figure than `worst_slip_deg` already reported elsewhere for the same
seed (rule 3: an internal disagreement between two numbers describing the
same thing). Fixed by picking `argmax(alpha_max_deg)` instead, the same step
`worst_slip_deg` is computed from, so the figure and the number it sits next
to now describe the identical instant. See `experiments/ep14/run.py::production_report`.

**What this is not.** Not a claim that RL cannot do torque vectoring, and not
a claim that the classical controller "won" — no lap-time race was run, and
CLAUDE.md rule 6 forbids comparing absolute lap times across methods anyway.
It is a report of what THIS training budget, THIS reward, and THIS envelope
penalty actually produced: a hybrid action space that stays close to the
physics but does not fully converge, and an end-to-end action space that
mostly finds the same tire-model exploit Season 3 already documented, with one
seed in three finding a clean answer instead. Longer training, a different
seed count, or a stronger envelope penalty are all still open.

---

### F93 · Episode 14's production run kept the last checkpoint instead of the best one, and its headline conclusion is retracted. **Defect, and the correction of record.** · 2026-07-28

**Source:** `[MEASURED]` — re-analysis of `experiments/ep14/out/history_{H,E}_seed{0,1,2}.json`,
the six 5,000,000-step production runs recorded in F92.

**The claim being retracted.** F92 and the first draft of Episode 14 reported
that neither RL variant reliably converges — H passing D6 in 0 of 3 seeds, E in
1 of 3 — and drew a conclusion about end-to-end action spaces being prone to a
tire-model exploit. **That conclusion was an artefact of model selection, not a
property of the variants.**

**What actually happened.** `physics/ppo.train` returned the weights it happened
to hold after the final update, and `experiments/ep14/run.py` saved those. No
checkpoint was ever scored during training. Re-reading the six training
histories, **every one of the six seeds passed through a sustained window in
which it drove the full 393 m with a worst slip angle inside the tire's own
±12° fit and a ~0% off-track rate** — and in five of six that window was
nowhere near the end of the run:

| Seed | Best clean window at | Distance | Worst slip | Off-track | Clean updates | FINAL weights reported instead |
|---|---|---|---|---|---|---|
| H seed 0 | update 429 (35%) | 393 m | 9.1° | 0.00 | 463 | 14.8°, D6 FAILED |
| H seed 1 | update 1009 (83%) | 381 m | 7.4° | 0.04 | 11 | 10.5°, D6 FAILED |
| H seed 2 | update 655 (54%) | 393 m | 12.0° | 0.00 | 65 | 9.4°, did not finish |
| E seed 0 | update 298 (24%) | 393 m | 9.2° | 0.00 | 127 | 13.5°, D6 FAILED |
| E seed 1 | update 612 (50%) | 393 m | 10.4° | 0.00 | 150 | 16.8°, D6 FAILED |
| E seed 2 | update 248 (20%) | 393 m | 8.4° | 0.00 | 227 | 8.8°, D6 PASSED |

"Clean" = a 20-update window averaging >370 m, <12° worst slip, <10% off-track.
H seed 0 was clean for **463 consecutive updates** and we reported the weights
from update 1219.

**PPO itself was healthy the whole time.** Median approximate KL 0.0041–0.0050
against a 0.01–0.02 norm, clip fraction 4–6%. The updates were not too
aggressive and the runs were not diverging — they were wandering, which is what
an unselected policy does, and nothing was watching.

**Two mechanisms, both fixed.**

1. *No model selection.* The project already had the rule that would have
   caught this — F61, "a reinforcement-learning result is the DEPLOYED policy's
   performance" — but applied it **once at the end** instead of throughout.
   `PPOConfig.eval_every` now scores the deployed policy on held-out seeds and
   keeps the best checkpoint, selecting on mean deployed **return** (the
   objective the reward already defines) and deliberately *not* on "did it stay
   inside the envelope", which is what D6 then checks independently.
2. *The exploration scale never annealed.* Final `log_std` sat within ~0.2 log
   units of its initialisation on all six seeds after 5,000,000 steps, so the
   mean-action policy that gets shipped stayed a different driver from the
   sampled one the training curves describe — which is precisely D6's
   `greedy_and_stochastic_agree` failure, seen on 4 of 6 seeds.
   `PPOConfig.entropy_anneal` decays the entropy bonus to zero.

Both default to **off**, and `tests/test_ppo.py` pins that the untouched path is
bit-for-bit what Seasons 3 produced, and that switching evaluation on does not
perturb the run it is watching.

**Why it survived to publication.** Two reasons worth recording, because
neither is about RL:

- **The pilot gated on the wrong thing.** It was built to answer "does the
  pipeline work", and "work" was defined as *produces a D6 verdict and a
  figure*. The right definition was *produces a policy we would keep*.
  Checkpointing is the first thing a multi-hour training run needs, and a pilot
  that does not exercise it has not de-risked the run.
- **`physics/ppo.py` had no tests at all** — the module every Season 3 and
  Season 4 result comes out of. `tests/test_ppo.py` now exists (12 tests).

**Stated as a limitation, because this is the failure mode being corrected:**
the clean windows above are measured on *training* rollouts — sampled actions,
jittered starts. D6 scores the *deployed* policy on clean starts. So the table
is strong evidence that good policies existed and were discarded, **not proof
that those checkpoints would pass D6.** The re-run with selection enabled is
what settles it, and its result is reported separately rather than assumed here.

**Carried implication for Season 3, not yet acted on.** Episodes 10 and 11 used
the same final-checkpoint-only path, and Episode 10's saved policy has the
identical frozen-`log_std` signature (final `[-2.24, -1.08]`) alongside a D6 that
fails `exploration_is_not_growing`. **Those results are likely understated by
the same mechanism.** Recorded here rather than fixed, so the scope of this
correction stays honest about what has and has not been re-measured.

---

### F94 · D6's own evaluation was not reproducible, and its envelope check contradicted its documented rule. **Defect, in the gate every RL result passes through.** · 2026-07-29

**Source:** `[MEASURED]` — `diagnostics/D6_training_health.py::evaluate`, probed
against Episode 14's six re-run policies.

Two defects, found while re-evaluating the Episode 14 re-run and both older
than Episode 14.

**1. The stochastic rollouts drew from torch's global, unseeded RNG.** The
environment seeds were fixed (`seed=s for s in range(n)`); the *action
sampling* was not. Three back-to-back `evaluate` calls on identical weights
(Episode 14, E seed 2):

| run | deployed worst slip | sampled worst slip | sampled distance |
|---|---|---|---|
| 0 | 9.33° | 11.27° | 359.1 m |
| 1 | 9.33° | 12.12° | 359.4 m |
| 2 | 9.33° | 11.74° | 393.2 m |

The deployed rollout is exactly reproducible. The sampled one is not, and it
**straddles the 12° bound the envelope check tests against** — so the same
policy passed or failed depending on the draw. This was mistaken for a real
change in the results before it was identified: two seeds appeared to flip
from PASS to FAIL after an unrelated edit that could not have touched them.

**This is F88 a second time.** F88 was the same defect in
`experiments/ep09/run.py`, found earlier in the same session and fixed there;
nobody checked whether the same pattern existed in the diagnostic. Fixed by
drawing from an explicit `torch.Generator` seeded with `SAMPLE_SEED = 0`,
re-seeded per policy so both rollouts start from the same draw. Verified
identical across repeated calls.

**2. The envelope check took `max(deployed, sampled)` while the comment
directly above it said the deployed number was the gate.** CLAUDE.md's own
invariant agrees with the comment: *"Report the deployed number as the headline
and the sampled number as diagnostic detail explaining it."* The code disagreed
with both.

This is not cosmetic, because the exploration scale never anneals (F93): a
Gaussian policy still sampling with std 0.2–0.38 visits slip angles its mean
action never does. On these six policies:

| | deployed | sampled |
|---|---|---|
| H 0 | 5.49° | 5.60° |
| H 1 | 11.14° | 13.00° |
| H 2 | 6.83° | 12.06° |
| E 0 | 6.47° | 9.20° |
| E 1 | 11.50° | 12.89° |
| E 2 | 9.33° | 11.11° |

**All six deployed policies are inside the fit; three sampled ones are not.**
Gating on the sampled figure judges a shipped controller by noise that is not
present when it is deployed.

**Decision (D12), taken explicitly rather than by leaving the bug in place:**
the check turns on the **deployed** policy, and the sampled figure is printed
on the same line every time, per rule 9. The sampled number is not discarded —
it says how much of *training* happened where the tire model was
extrapolating, which is a real caveat about the learning signal even when the
resulting policy is clean. Recorded because it is a protocol choice that moves
the headline from "3 of 6 stayed inside the tire fit" to "6 of 6", and a change
in that direction deserves to be visible rather than buried.

`the_tire_file_s_own_load_range_was_respected` had the same problem — it tested
the sampled rollout only — and now reports both with the deployed figure as the
gate.

**Carried implication.** Episodes 9, 10 and 11 were all gated by this
diagnostic. Their D6 verdicts were not reproducible, and their envelope verdicts
were taken on the sampled policy. Combined with F93's missing checkpoint
selection, **Season 3's results are doubly understated.** Not re-run here.

---

### F95 · Episode 14's "half the tire" comparison measured a free parameter of our own reward. **Retracts the H-vs-E utilisation finding.** · 2026-07-29

**Source:** `[MEASURED]` — `experiments/ep14/out/full_trace_{H,E}_seed{0,1,2}.npz`,
decomposed by position on the lap.

**What was claimed.** That E spends roughly twice the friction-ellipse
utilisation of H for the same lap time and peak grip (0.70 ± 0.13 against
0.357 ± 0.087, 3.1× the pooled seed standard deviation), and that this said
something about the QP allocator.

**What the number actually is.** Split by where on the lap it happens:

| | H | E | rule 5 |
|---|---|---|---|
| in the corner (60–150 m) | 0.70 ± 0.07 | 0.85 ± 0.10 | **1.8× — not a finding** |
| on the exit straight (>200 m) | 0.23 ± 0.13 | 0.63 ± 0.15 | 2.9× |
| whole lap | 0.36 ± 0.09 | 0.70 ± 0.13 | 3.1× |

**Where the tires are actually cornering there is no measurable difference.**
The whole effect lives on the straight, which is 260 of the lap's 393 m and
therefore dominates the average.

**And on the straight the metric is measuring nothing the objective constrains.**
The reward there is `s_dot * dt` and nothing else: the car is on the road, so no
off-track penalty, and worst slip angle across all six seeds is **0.02°–1.08°**
against a 12° envelope bound, so no envelope penalty either. Summed per-wheel
lateral force on that same straight ranges from **83 N to 3,199 N** — a factor
of 38 — at **identical reward**. Wheels fighting each other is free.

So the objective has a flat direction, and each seed settles somewhere different
along it. That explains every symptom at once: the 4× spread in H's own straight
utilisation (0.08, 0.25, 0.35), the absence of any correlation with net drive
force (H seed 2 makes 775 N of net drive on 0.08 utilisation while H seed 1
makes 543 N on 0.35), and the fact that both variants show it — because it is
the reward, not the action space. H's allocator does not prevent it: the
allocator faithfully delivers whatever `Mz` its policy asks for, and asking for
yaw on a straight costs nothing.

**This is underdetermination, not a training failure.** The seed variance is the
correct behaviour of a well-trained policy against an objective that does not
care. Reading it as "E is wasteful" or "the allocator is efficient" was reading
structure into noise.

**Retracted:** the H-vs-E utilisation comparison, and any claim built on it.
**Not retracted:** all six policies complete the lap inside the ±12° tire fit
(F93/F94's corrected result), and in the corner the two variants are
indistinguishable — which is itself the answer to "does the learned upper layer
work", just a quieter one.

**How it was found, and the gap that let it through.** Rung 4 of the
`rl-env-debug-triage` ladder — inspect reward scale and specification before
touching anything else. It was found only because the seed-to-seed instability
was questioned; nothing in the pipeline flagged it. **The env has no
scripted-policy sanity check** — a trivial policy with a hand-derived expected
return, which is the cheapest reward-specification test there is and would have
made the flat direction obvious. That is rung 2 of the same ladder and it is
missing. Recorded as open item O9.

**The generalisable lesson, because this is the fourth correction in one
session.** Every one had the same shape: an aggregate was reported before it was
decomposed. Rule 7 says compute metrics downstream from logged arrays, and that
was done — but "downstream" is not "understood". A lap-average is a sum over
places the car was doing different things, and it is worth nothing until you
have asked which of those places it came from.

---

### F96 · `STEER_NOISE = 0.15` is 23 degrees RMS at the steering wheel, not a driver. **Affects Episodes 11 and 13.** · 2026-07-29

**Source:** `[MEASURED]` — closed-loop RMS steer deviation of Episode 14's
H seed 0 policy against its own noise-free run, six draws per level.
`[SOURCED]` — steering-reversal-rate methodology for the noise/intent boundary.
`[ASSUMED]` — 13.5:1 steering ratio; `docs/vehicle-reference-parameters.md`
specifies the car but not the rack.

`EnvConfig.steer_noise` perturbs the steering **rate** command, as a fraction of
`STEER_RATE_MAX` (200 deg/s at the **road wheel**). Episode 11 set it to 0.15,
Episode 13 reused "Episode 11's value", and both describe it as the driver's
hands and the steering linkage. What it actually produces:

| `steer_noise` | road-wheel RMS | at the steering wheel (13.5:1) |
|---|---|---|
| 0.01 | 0.12° | **1.6°** |
| 0.02 | 0.23° | 3.1° |
| 0.03 | 0.35° | 4.7° |
| 0.05 | 0.58° | 7.8° |
| 0.10 | 1.16° | 15.6° |
| **0.15** | 1.73° | **23.4°** |

**23 degrees RMS at the wheel is not an imperfect driver.** It is a continuous
quarter-turn saw. Against the reversal-rate literature's own bands — reversals
under 1° characterise cognitive load, 2–6° characterise a *visual* secondary
task, i.e. eyes off the road — 0.15 is off the scale by an order of magnitude.

**The unit trap.** The environment commands the **road wheel**; a driver holds
the **steering wheel**. The ~13.5:1 ratio between them is exactly where a
number that sounds plausible stops being one, and nothing in the code converts
between the two.

**Recommended values:** `0.01` for an attentive driver (1.6° at the wheel, the
micro-correction boundary) and `0.03` for a distracted one (4.7°, the
visual-task band). Both `[DERIVED]` from the measurement above plus an
`[ASSUMED]` steering ratio, so they are a defensible approximation and not a
validated figure.

**What this does to Episode 14's robustness test.** Run at 0.15, the six
policies scattered from 100% down to 20% completion and reached 18–27° of slip,
and I reported that the envelope guarantee does not survive disturbance. **That
is retracted.** Re-run at 0.01: **all six complete 100% of laps** with lap
scatter of ±0.01–0.02 s and worst slip 5.8–11.8°, inside the fit. At 0.03, five
of six still complete 100% and the worst excursion is a marginal 13.0°.

**And the H-vs-E result the test was built to settle:** no measurable
difference in robustness — 0.8× the pooled seed standard deviation at 0.03,
identical at 0.01. Consistent with F95's finding that the two carry the same
utilisation in the corner, hence the same margin. The pre-registered hypothesis
(the allocator buys robustness) is **rejected**, now at a disturbance level that
means something.

**Carried implication, not yet acted on.** Episode 11's fragility conclusions
and Episode 13's noise study (78% → 100% completion, the largest effect Episode
13 reports) both rest on 0.15. Neither has been re-measured. Episode 13's
qualitative direction may well survive — its noise laps were run at an
aggression close to the passive car's limit, where any disturbance hurts — but
the magnitude is a statement about a 23° saw.

**The part that stings.** `STEER_NOISE = 0.15` sits three lines below a comment
citing **F70 — a retraction caused by a perturbation magnitude nobody
justified.** The lesson had already been learned, written down, and placed
directly above the constant that repeated it, because the value was chosen as
"the strongest disturbance the median lap survives" rather than by asking what
a driver does. A rule written next to a number does not check the number.

---

### F97 · Episode 13's steering-noise robustness result, re-measured at F96's realistic levels, is retracted. · 2026-07-29

**Source:** `[MEASURED]` — `experiments/ep13/out/results.json`, `noise` and
`noise_distracted` blocks, 40 seeds each, same `grip_use` (0.991) and lap as the
original run.

**What was claimed.** That steering noise (`sigma = 0.15`, described as "the
same magnitude" as Episode 11) is where torque vectoring earns its keep: the
open differential completed 31/40 laps against the four-wheel controller's
40/40, "a far larger effect than the half percent it is worth to a perfect
driver."

**Re-measured at F96's calibrated levels — attentive driver (`sigma = 0.01`,
1.6° at the wheel) and distracted driver (`sigma = 0.03`, 4.7° at the wheel),
40 seeds each:**

| | old (retracted, σ=0.15) | attentive (σ=0.01) | distracted (σ=0.03) |
|---|---|---|---|
| open differential | 31/40 · 14.602 ± 0.015 s | **40/40** · 14.589 ± 0.001 s | **40/40** · 14.590 ± 0.003 s |
| limited-slip | 3/40 · 14.659 ± 0.039 s | 0/40 · — | 0/40 · — |
| allocator only | 40/40 · 14.608 ± 0.009 s | 40/40 · 14.599 ± 0.000 s | 40/40 · 14.600 ± 0.002 s |
| TV, four wheels | 40/40 · 14.580 ± 0.006 s | 40/40 · 14.572 ± 0.001 s | 40/40 · 14.573 ± 0.001 s |
| TV, rear axle | 40/40 · 14.596 ± 0.015 s | 40/40 · 14.592 ± 0.001 s | 40/40 · 14.591 ± 0.003 s |

**At a disturbance level that means something, the open differential is not
measurably more fragile than any TV configuration.** All four of the
configurations that could drive this lap at all complete 100% of laps at both
realistic noise levels, and the lap-time scatter across seeds (0.001–0.003 s)
is far below the deterministic gap between configurations. The pre-registered
claim — that a driver who makes mistakes gets far more value from TV than a
perfect one does — is **rejected**, in exactly the shape F96 found for Episode
14: the effect was real, but only at a disturbance nobody's hands produce.

**The limited-slip car's 0/40 is not a new problem.** It was already past its
own aggression limit (0.969, against the 0.991 this study drives at) — the
original article's own caveat. At `sigma = 0.15` it occasionally survived by
being randomly nudged off a knife-edge it cannot hold deterministically; at the
much smaller realistic noise levels there is nothing to nudge it, so it fails
consistently. This is evidence about a device already asked to do something it
cannot do cleanly, not a new finding about noise.

**Not retracted.** Every result upstream of the noise study — the +5.18%
cornering-limit gain, the +1.30% skidpad gain, the 88% yaw-tracking-error
reduction, the allocator accounting for ~40% of the gain, and the
driver-preview-time sensitivity (D-ep13's one pre-existing, expected failure) —
does not involve `steer_noise` and is unaffected.

**Closes O10 for Episode 13.** Episode 11's half of O10 is tracked separately
(see F98) because it uses a different policy and a different disturbance
protocol (deployed RL policy against a designed-conditioned car, not a
closed-loop classical controller).

---

### F98 · Episode 11's fragility ordering survives F96's correction — but steering noise turns out to have contributed almost nothing to it. · 2026-07-29

**Source:** `[MEASURED]` — `experiments/ep11/out/results.json` (5 designs × 7
conditions × 40 deployed rollouts) and `results_deep.json` (4 designs × 3
conditions × 120 deployed rollouts, seeds identical to the original deep run).

**Re-measured at F96's calibrated levels — attentive driver (`sigma = 0.01`,
1.6° at the wheel) and distracted driver (`sigma = 0.03`, 4.7° at the wheel),
both combined with the unchanged ±20% grip variation:**

| design | old (retracted, σ=0.15+grip) | attentive (σ=0.01+grip) | distracted (σ=0.03+grip) |
|---|---|---|---|
| 47% front — the quickest | 9/104 · 8.7% [4.6–15.6%] | **10/108 · 9.3%** [5.1–16.2%] | **10/108 · 9.3%** [5.1–16.2%] |
| 54% front | 0/114 · 0% | 0/119 · 0% | 0/119 · 0% |
| 61% front | 0/102 · 0% | 0/116 · 0% | 0/116 · 0% |
| 65% front | 0/105 · 0% | 0/119 · 0% | 0/119 · 0% |

Holm-Bonferroni corrected (family-wise 0.05), 47% against each other design:
all three comparisons at **p = 0.0005** (below every threshold), both at the
attentive and the distracted level. **The episode's headline claim survives:
the fastest design is measurably more fragile than the others, at a
disturbance magnitude that means something.** This is the opposite outcome
from F95 and F97 — the same bug, but this time the correction does not
overturn the conclusion.

**Why it survives, and the part that does not survive unchanged.** In the deep
run the attentive and distracted cells come out **identical in every reported
integer** — same in-fit rate, same discarded-lap count, same discarded-failure
count, at all four designs.

**That identity is about outcomes, not trajectories, and the distinction
matters.** Directly measured (`sigma` 0.01 vs 0.03 on the same seeds): the paths
genuinely differ and peak slip moves by **0.2–0.7°**. What does not change is
whether any lap crosses the two thresholds the metric counts — 12° of slip, and
leaving the road. So the honest statement is *steering noise at a realistic
magnitude does not change any lap's verdict in this experiment*, *not* that it
does nothing measurable. This was checked because the identical counts are
equally consistent with the noise never reaching the simulator, which would have
been a defect rather than a finding; it is wired correctly.

**What this does retract is the attribution.** The article's framing — "two
disturbances, applied separately and then together so each one's contribution is
attributable" — implied steering noise carried part of the effect. It does not:
the `steer`-only condition (0.01, no grip) produces the same 0% failure rate as
`nominal` at every drivable design, and every bit of the fragility signal comes
from the ±20% grip variation, which F96 did not touch. **Episode 11 is a
grip-variation result and should be read as one.**

**What this means for the old 0.15 run, looking back.** It was not that
steering noise was doing the work and got corrected away (F97's pattern). It
was already, mostly, the grip-variation experiment wearing a steering-noise
label. The unrealistic magnitude inflated how often cars left the fit — the
three non-fastest designs discarded **6, 18 and 15** laps of 120 at the old
value against **1, 4 and 1** now — and inflated the severity when they did, with
worst slip reaching **35°** on the 65%-front car against 13–15° now. At 35° the
Magic Formula is pure extrapolation, so those were never laps about a car. What
the old magnitude did *not* do is manufacture the ranking.

**Retracted: the population-level recovery-mechanism table.** "It isn't
margin, it's whether you get it back" reported, per design, how many laps left
the fit and what fraction of those crashed (81%/33%/6%/7% for 47/54/61/65%
front, from 16/6/18/15 discarded laps). At the corrected noise level the
non-fastest designs leave the fit far less often — **1, 4, and 1 laps** out of
120 for 54/61/65% front. F70's own lesson applies directly: a percentage
computed from 1 or 4 samples is not a rate, and re-quoting 100%/0%/0% from
those counts would repeat exactly the mistake this project has already
retracted twice. **Not retracted:** the mechanism itself — a front-limited car
pushes wide and self-corrects, a rear-limited car rotates and diverges — is a
property of the vehicle, not of the disturbance magnitude.

**A third defect, found while regenerating the figure, and it is the worst of
the three.** `03-when-it-lets-go.svg` drew two named laps — "seed 2 of the 61%
car" and "seed 2 of the 47% car" — with their peak slip angles, 13.4° and 12.0°,
**written into the caption as literal strings.** At the corrected disturbance
those same two laps peak at **7.3° and 7.6°** and never approach the fit at all.
The figure therefore rendered two unremarkable laps beneath a caption asserting
that both had gone past the tire's fitted limit, and beneath a headline reading
"Same exposure. Opposite outcome." **Nothing failed.** The numbers were text, so
they could not disagree with the arrays beside them.

This is CLAUDE.md rule 10 — *do not hardcode a number into a figure that the
model can supply* — and the figure had violated it in three separate places
(both slip labels, and a summary sentence reading "18 laps against 16 — and
crashed once against thirteen"). All three are now computed. Two further changes
were needed to make the figure honest rather than merely current:

1. **It selects its own examples.** `_pick_recovery_pair` scans the traces for a
   lap that exceeded 12° and finished beside one that exceeded 12° and did not,
   from the same condition, preferring the pair with the closest peak slip —
   because "equally far over the edge, opposite outcome" is the claim. If no such
   pair exists the panel says so and draws nothing.
2. **It checks the mechanism before asserting it.** The captions ("the nose gives
   up first") are only true if the recovered lap is the more front-biased car. It
   now tests that and withholds the explanation if the selected pair inverts it.
3. **It only counts excursions it actually draws.** Slip is measured inside the
   panel's own `s` window. The first version of this fix measured the whole lap,
   which would have let a lap qualify on an excursion happening off-panel — the
   caption asserting an excursion the reader cannot see. That is the original
   defect reached through a different door, and it also made the subtitle and the
   on-car label report two different numbers for one lap.

**What the corrected figure shows.** A pair does exist at the attentive level:
the **65%-front car reached 12.9° and completed the lap; the 47%-front car
reached 13.6° and left the road** (seeds 25 and 31, both named on the figure).
The pairing is mechanism-consistent — most nose-heavy recovers, most tail-heavy
does not — and it makes the point more cleanly than the retracted version, since
the car that crashed went *further* over the limit rather than less far. The
undriveable 40%-front car is excluded because the figure draws from the deep
run's design list.

**And the trace-retention bug underneath.** Only seeds 0–7 of each cell were
saved, while the laps that leave the fit at a realistic disturbance are rare —
12 of 120 for the fastest design, 1–4 for the others — so **none of them were in
the file.** `run.py` now additionally saves every lap that exceeded the fit in a
quotable condition, choosing which by reading the cell's own
`per_lap_worst_slip_deg`, so the figure and the reported rates cannot disagree.

**The lesson, and it is the same one as F95's.** Every correction in this cluster
was a number that had stopped being checked against the thing it described — a
lap-average nobody decomposed (F95), a constant nobody converted to
driver-facing units (F96), and here a measurement nobody re-read after the run
that produced it changed. A figure generated from a parameterised builder is not
automatically a figure that cannot lie; it is only as honest as the fraction of
it that is actually computed.

**Closes O10.** Both halves of Episode 11 and Episode 13's noise studies are
now re-measured at a realistic disturbance level (F97, F98). The general
lesson from F96 — check a perturbation's real-world magnitude before trusting
what it seems to prove — held for one episode's headline (F97, retracted) and
not the other's (F98, survived), which is itself worth keeping: a corrected
bug does not have a predetermined direction of effect, and both outcomes were
real until measured.

---

### F99 · F44 and F49 predate the yaw-moment correction, exactly like F90's brake-release number — and this time the "no effect" conclusion itself was wrong for one of them. **Defect, and the correction of record.** · 2026-07-30

**Source:** `[MEASURED]` — fresh re-solves of `experiments/ep07/run.py` and
`experiments/ep08/run.py`, unchanged except for one additive trace field
(`dt_ds`, added for POWER-REVIEW Phase 0's section-time work). Verified
bit-identical to the already-committed `results.json` in every other field
before anything below was trusted — this is not new drift, it is drift that
was already sitting in the repository, discovered while auditing it for
POWER-REVIEW.

**F90 already named this failure mode once**, for Episode 7's brake-release
number: "a fix to shared machinery invalidates every number downstream of it,
not only the ones the fix was motivated by... regenerate every figure and
reread every table rather than trust that the important ones were checked."
F44 and F49 are two more instances of exactly that, discovered because Phase 0
asked "is this null real?" and re-solving to check it surfaced that the
tables being questioned were never the current ones.

**Both episode *articles* are already correct.** `episodes/ep07-*.md` and
`episodes/ep08-*.md` both carry explicit re-solved-after-F72/F73/F79/F80
notices and numbers that match a fresh re-solve exactly. **Only the FINDINGS.md
entries were never updated after the articles were.** No published, reader-
facing content is wrong; the project's own numbered record of what is true
was stale, in the file whose entire purpose is not being that.

**F44, corrected — and here the conclusion itself reverses, not just the
magnitude:**

| Front mass | K (deg/g) | Rear drive | Front drive |
|---|---|---|---|
| 40% | −0.37 | 12.059 s ✓ | 12.175 s ✓ |
| 47% | −0.07 | 12.047 s ✓ | 12.084 s ✓ |
| 54% (nominal) | +0.22 | 12.086 s ✓ | 12.054 s ✓ |
| 61% | +0.51 | 12.173 s ✓ | 12.063 s ✓ |
| 65% | +0.68 | 12.252 s ✓ | 12.085 s ✓ |

**All ten solves converge now** (F80: the fix that corrected the moment also
fixed the 47%-rear-drive case that had never converged in the project's
history). F44's own text excluded three rear-drive points as unconverged;
none are excluded now, so every claim below rests on the full grid.

**The lap time does not "do almost nothing."** Rear drive spans **0.205 s**
across the range (12.047 to 12.252) and front drive spans **0.121 s** (12.054
to 12.175) — both monotonic, both now fully converged, neither resting on an
excluded point. F44 called the 40%-and-54% rear-drive gap "indistinguishable
(0.012 s apart)" from two of the *previously converged* points; the
now-complete range is seventeen times that. **This is not a small correction
to a null result — it is a reversal of the headline**, and the article already
says so in different words ("rear drive's sensitivity has doubled... the
whole 40–65% range is worth 0.21 s"). F44 is the one place that sentence never
arrived.

**F49, corrected — here the story tightens rather than reverses:**

| Layout | Polar moment | Rise time | Lap time |
|---|---|---|---|
| Mid engine, RWD | 0.80× | 201 ms | 12.043 s |
| Front engine, FWD | 1.25× | 234 ms | 12.068 s |
| Front-mid, RWD | 1.00× | 201 ms | 12.078 s |
| Rear engine, RWD | **1.22×** | **356 ms** | 12.079 s |
| Front engine, RWD | 1.20× | 236 ms | 12.099 s |

**The ranking is not merely shifted, it is inverted at both ends.** F49's
table had front-engine-FWD dead last, 0.113 s off the pace, and rear-engine-RWD
mid-pack. The corrected data has front-engine-FWD in **second place** and
rear-engine-RWD tied for third — the one design F49 singled out as "clearly
off the pace" is now indistinguishable from the pack it was compared against.
The full span **shrinks** from F49's 0.03–0.113 s (with one outlier) to a
uniform **0.056 s** with no outlier at all. Where F44's null reversed into a
real effect, F49's null gets *more* uniformly null — a cleaner, more robust
version of the same conclusion, not a different one.

**What this changes about the power review's premise.** POWER-REVIEW.md
opened by treating F44 and F49 symmetrically — two nulls, both suspected of
being instrument artefacts of low power and a diluted lap metric. That premise
now only half-applies:

- **Balance (F44) is not a null to explain away.** It is already a real,
  fully-converged, ~1.7% effect at 1× power. Phase 1's balance question changes
  from "is there an effect hiding below the instrument's resolution?" to "how
  does an already-real effect move across the power curve?" — closer in shape
  to F43's original drivetrain sweep than to a null-result audit.
- **Layout (F49) is still the open question POWER-REVIEW framed it as** — if
  anything more so, since the corrected data removes the one candidate outlier
  and leaves a flatter result to interrogate.

**A live inconsistency this leaves in `episodes/ep07-*.md`, corrected in the
same session, after this entry was written.** The article's own numbers
(0.21 s / 0.12 s, doubled from the earlier draft) sat under a section headed
"Result two: it barely changes how fast it is" and a pull-quote saying the
same. The *numbers* were corrected when F80 landed; the *sentence describing
them* was not re-read against its own table — the same gap F90 found, one
level up, in prose instead of a figure. Reworded to "it moves the needle, but
far less than it moves the feel," distinguishing a real quantitative effect
(1.7% of a lap) from the understeer swing's qualitative one (oversteer to
understeer, not a percentage of anything).

**The lesson, restated because this is the second time it has been learned.**
F90: "the way to catch the rest is to regenerate every figure and reread every
table, rather than trust that the important ones were checked." That lesson
was written down and did not prevent this — because it was applied to the
*episode*, once, and never applied to *FINDINGS.md's own record of the
episode*, which drifted from it afterward and stayed drifted. A correction to
shared machinery invalidates every number that depends on it **including the
numbers already sitting in the file that exists to keep this from happening.**

---

### F100 · POWER-REVIEW Phase 1: balance's real effect and layout's null both grow monotonically with power, on every track, under both drive models — the layout null does not survive. · 2026-07-30

**Source:** `[MEASURED]` — `experiments/power_review/phase1_sweep.py`, the
full {1×, 1.5×, 2×} × {hairpin, long_exit, fast_sweep} × {flat cap,
power-limited} grid, both axes (Episode 7's balance sweep, Episode 8's
layout sweep). 270 solves. 269 converged on the first pass; the two that
didn't are accounted for below, not silently excluded.

**The result, stated once because it holds everywhere it was checked.**
Every one of 12 balance rows (3 tracks × 2 drivetrains) and 6 layout rows
(3 tracks) grows monotonically from 1× to 1.5× to 2× power, under **both**
drive models. Representative (`long_exit`, flat cap, `fwd_0.54` as the
comparison point across neighbouring designs):

| | 1× | 1.5× | 2× |
|---|---|---|---|
| Balance spread, RWD | 0.205 s | 0.319 s | 0.740 s |
| Balance spread, FWD | 0.120 s | 0.525 s | 0.836 s |
| Layout spread | 0.056 s | 0.116 s | 0.262 s |

Growth factor 1×→2×, across all 12 balance rows (3 tracks × 2 drivetrains ×
2 drive models): **×2.3–8.1**, widest for hairpin FWD under the flat cap
(×8.1) and narrowest for fast_sweep RWD under power-limited drive (×2.3).
Layout: ×2.5–4.9 across the three tracks and both models, a tighter range.
**The same order of magnitude as F43's original drivetrain sweep** (which
found 4–5× amplification from its own lowest to highest power point) —
balance's range brackets it, layout's sits inside it — on an axis (layout)
that F99 had just corrected to a *tighter* null at 1×.

**F49's null does not survive the power curve, and this is the second
correction to it in one day, for a different reason than the first.** F99
corrected F49's numbers at the power level it was measured at (drift, not a
design flaw in the finding). This measures the same finding across power and
finds the null itself was a low-power artefact — exactly what
POWER-REVIEW's original premise suspected, before F99 showed the premise had
been arguing from a stale table. **Both things are true at once**: F49's 1×
number was wrong (F99) and F49's 1×-only *scope* was also insufficient
(this entry) — a corrected measurement can still be an incomplete one.

**Balance (F44/F99) gets what it predicted.** F99 already established a real
1× effect and asked whether it would grow with power, F43-style. It does, on
every track, under both drive models, with no exceptions once the two
defects below were fixed. Season 2's balance finding is now power-robust
across a 2× range rather than a one-point claim.

**Two defects found while producing this, both caught by refusing to trust
a number before checking it, neither by assuming the grid was clean:**

1. **A single cell in a genuinely bad local optimum.**
   `long_exit|1.5x|flat|rwd_0.61` reported `Solve_Succeeded` at **12.672 s** —
   self-consistent enough to pass IPOPT's own convergence test, but a full
   1.1 s slower than both its neighbours (11.40 s at 0.54 front, 11.63 s at
   0.65 front) and slower than the *same design at 1× power* (12.17 s),
   which a genuine 1.5×-power solve cannot be. Found because the spread
   computed across the sweep broke monotonicity in exactly one place — not
   because the solve reported any failure. Warm-starting cleanly from the
   converged 0.54 neighbour (the intended staging) and, independently, a
   cold start both land at **11.525 s**, matching each other and restoring
   monotonicity. **A systematic scan of every other point in the 270-cell
   grid — checking each balance point against a linear interpolation of its
   neighbours, and each layout point against the other four — found zero
   further instances.** This one cell is corrected in place; nothing else in
   the dataset needed it.
2. **One cell hit the iteration limit** (`hairpin|1x|flat|rwd_0.61` —
   the same fraction, the same drivetrain, a different track and power;
   plausibly a genuinely harder region for this solver rather than
   coincidence, not investigated further here). Re-solved from the same
   converged 0.54 neighbour at double `max_iter`: **12.355 s**, against the
   unconverged run's own **12.356 s** — this one **was** nearly exact
   despite not converging, the F39 pattern in its gentler form (small error,
   not a large one, but still not quotable until checked).

**The flat-cap/power-limited divergence has a clean explanation, not a
mysterious one.** Because both models are defined as `4500 N × mult` and
`174,000 W × mult` respectively, their crossover speed —
`174,000/4,500 = 38.7 m/s` — **is invariant to the power multiplier**; only
how much of each lap is spent above or below it changes, and more power
means higher top speed on the same track, hence more of the lap above the
crossover. Consistent with the data: at 1× power, `hairpin` and `long_exit`
(lower average speed) show power-limited **faster** than flat cap (the P/v
constraint is looser than 4.5 kN below 38.7 m/s); by 2× power that gap has
shrunk and, on both tracks, flipped sign. `fast_sweep` (the high-speed
track) shows the opposite pattern throughout — power-limited slower than
flat at every power level, the gap *widening* with power. Neither model is
reported as having superseded the other (D-A); this divergence is itself
Phase 1's answer to the question D-A raised.

**Closes Phase 1 for both axes.** Pre-registered outcomes (rule 9): balance
was "grows monotonically → confirms F43's mechanism" (confirmed, on all
three tracks, both models); layout was "grows monotonically → F49 corrected
F43-style, joins balance as a real design axis" (also confirmed — not the
"stays flat, gets stronger" alternative). Episode 15 now has what it needed
and did not have before this entry: **a design-sensitivity baseline, on
both axes, that measurably varies with power** — the missing prerequisite
POWER-REVIEW named at the start.

---

### F101 · POWER-REVIEW Phase 2: torque vectoring is worth 25× more cornering limit at 2× power than at 1×, and a passive differential becomes undrivable long before that. · 2026-07-30

**Source:** `[MEASURED]` — `experiments/power_review/phase2_sweep.py`,
Episode 13's five configurations at {1×, 1.5×, 2×} power × {flat cap,
power-limited}, `long_exit`, bisected to `grip_use` tolerance 0.002, plus
Phase 0's brake-cap fix (`BRAKE_MAX` raised to the tire's demonstrated
~0.985 g, applied once, every configuration — not a swept axis; see §1
point 3 of POWER-REVIEW.md).

**The headline: TV's cornering-limit gain over the open differential.**

| Power | Flat cap | Power-limited |
|---|---|---|
| 1× | **+4.6%** | +8.8% |
| 1.5× | +48.3% | +66.2% |
| 2× | **+125.5%** | +123.0% |

Monotonic under both drive models, growing from a low-single-digit number —
matching F82's original 1× measurement (+5.18% there; +4.6% here, the small
remainder explained entirely by the brake-cap fix, not drift) — to **more
than doubling** the achievable cornering limit by 2×. Lap-time gain follows
the same shape: −0.95% (a wash, matching F82/F97) → +5.08% → **+14.06%**
(flat cap); corner-section gain **+24.55%** at 2×, against F82's original
−1.32%-to-modest range. **This is the number Episode 15 needed and did not
have**: at real sports-car power, torque vectoring is not a small effect
measured carefully — it is the difference between a car that corners and
one that does not.

**The reason, and it is not subtle once measured directly: the passive
differential runs out of road long before torque vectoring does.**

| Config | 1× limit | 2× limit | Change |
|---|---|---|---|
| Open differential | 1.044 | 0.480 | **−54%** |
| LSD (1.5:1) | 0.970 | **undrivable** | — |
| TV, rear axle only | 1.082 | 0.722 (flat) / 0.335 (power-limited) | −33% to −68% |
| **TV, four wheels** | 1.093 | 1.082 | **−1%, effectively flat** |

The open differential's own achievable limit **nearly halves** from 1× to
2× power — more torque, delivered without any per-wheel intelligence,
simply overwhelms it. The single-axis TV-differential degrades too, more
under the power-limited model (which delivers more torque at low speed —
D-A's own crossover mechanism, F100) than under the flat cap. **Only the
full four-wheel allocator holds its limit essentially constant across a 2×
power range.** This is the mechanistic answer to "why does TV's worth grow
with power": it is not that TV gets better with power, it is that
everything else gets worse and TV does not.

**LSD's "undrivable" is checked, not assumed.** Scanned at fine resolution
(`gu` in 0.002 steps from 0.02 to 0.058) at 2× power: the car transitions
directly from `stalled` (too slow to register as under way) to `spun`
(49.9–52.5° of slip) with **no valid grip_use in between** — not a search
that gave up early, a corner this configuration cannot complete at any
aggression from the gentlest tested upward. Consistent with the article's
own earlier finding that the LSD is *already* the slowest configuration
tested at 1× (F79) — this is that same weakness, worse at real power.

**Three defects found and fixed while building this, none accepted at face
value:**

1. **A plan/clip mismatch that produced a false physical result.** The
   power-limited drive model's clip deliberately sets a non-binding
   `drive_max` (100,000 N) so `drive_power` alone governs — but an early
   version fed that same 100,000 N into the `SpeedProfile`'s own planning
   input too, a 7.5 g acceleration target with no physical meaning. The
   plan's forward pass then demanded near-instant post-corner acceleration,
   the tracking driver's error term saturated chasing it, and the open
   differential spun at 49.9° on a lap the flat model drove clean at the
   same aggression — which read, before it was checked, as "more power
   makes an open diff worse," the right shape for a real finding and
   entirely wrong. Confirmed by construction: the same clip with a sane
   planning value (the flat model's own figure) drives the identical lap at
   3.1°. Fixed by separating what the plan assumes from what the clip
   enforces (`driver_kw_for` now returns both, independently).
2. **`GU_LO = 0.70` was too high a floor once the first defect was fixed.**
   The corrected run still showed most of the passive-differential cells as
   `nan` at 1.5×/2× power. Checked rather than reported: 2×/flat open diff
   goes off track at `gu = 0.70` *and* `0.50` but finishes clean at `0.30` —
   the search's own starting point sat above the car's real limit, so
   "no valid lap" was being reported for configurations that have a
   perfectly real, just much lower, one. Lowered to 0.05, and the new floor
   was itself checked before trusting the results built on it.
3. **Episode 12 does not have a power axis at all**, discovered by checking
   rather than assuming Episode 12 needed the same {1×,1.5×,2×} treatment
   as Episode 13. It is a steady-state, fixed-corner mechanism study that
   sweeps *demanded* force directly (0–6,500 N) — no engine cap, no
   `SpeedProfile`, no lap. Its sweep already covers 1× and most of 1.5× but
   not 2× (9,000 N); extending it directly (not through the Phase 2 sweep
   infrastructure) found the mechanism conclusion (F76/F77 — the
   speed-coupling term dominates at full throttle) holds unchanged through
   12,000 N, with the outside wheel's own grip saturating the asymmetry by
   9,000 N. No re-publish needed; recorded here as the check, not a finding
   of its own.

**Not retracted, not touched:** everything upstream of the power question —
the two-layer controller's mechanism (F82's "both layers do what they
claim"), the allocator's ~40% share of the gain, the driver-preview
sensitivity (F84) — none of it depended on power level and none of it
changed.

**Closes Phase 2.** Episode 15 now has the second thing it needed: not just
a design-sensitivity baseline that varies with power (F100), but TV's own
worth as a function of the same power curve, and a mechanistic account of
why. Both were missing when POWER-REVIEW opened; both exist now.

---

### F102 · Episode 15: torque vectoring flattens layout sensitivity by up to 47×, flattens balance for rear-driven cars — and does nothing for a front-driven one, for a reason worth keeping. · 2026-07-30

**Source:** `[MEASURED]` — `experiments/ep15/run.py`, Episode 7's balance
sweep (5 fractions × 2 drivetrains) and Episode 8's five layout archetypes,
each driven with TV off (open differential) and TV on (the four-wheel
allocator), at RV-1's own power (1×) and 2×, `long_exit`, D11's protocol
(cornering-limit `grip_use`, bisected to 0.002). Uses Phase 2's driver
infrastructure directly (`experiments/power_review/phase2_sweep.py`).

**Layout: TV nearly erases it, and increasingly so as power rises.**

| | TV off (spread) | TV on (spread) | Flattening factor |
|---|---|---|---|
| 1× power | 0.271 | 0.017 | **16×** |
| 2× power | 0.713 | 0.015 | **47×** |

The five archetypes span 0.83–1.10 in cornering limit with TV off at 1×
(F49/F99/F100's already-established sensitivity) and 0.39–1.10 at 2× — a
spread that **grows 2.6× with power, exactly as F100 found for the OC-solver
version of this same axis.** With TV on, every archetype sits in a tight
1.07–1.10 band at both power levels. **The thing that made a 911 a 911 —
where the engine sits — is something this controller has already made
irrelevant to whether the car can hold a line, on this model, at this
power.** The series-plan payoff line stands: this is the flattening it
asked whether would hold.

**Balance: flattens for the rear-driven car, and does not need to for the
front-driven one — a real mechanism, not a gap in the result.**

| | TV off, 1×→2× | TV on, 1×→2× | Flattens at 2×? |
|---|---|---|---|
| RWD | 0.086 → **0.371** | 0.047 → 0.036 | **Yes — 10.3× flatter** |
| FWD | 0.091 → 0.091 | 0.094 → 0.080 | **No measurable flattening** |

RWD's sensitivity grows with power exactly like layout's does, and TV
collapses it the same way. **FWD's sensitivity does not grow with power at
all — 0.091 both times, with or without TV — because power was never what
was binding it.** Checked directly on the archetype that shows this
starkest (`front_fwd`, 62% front mass, TV off): drive force **fully
saturates whichever cap it is given** (4,500 N at 1×, 9,000 N at 2× — the
power scaling reaches the wheels correctly) and the cornering limit is
**bit-identical, 1.100, at both power levels.** Worst slip angle is 11.9° at
both — one tenth of a degree from the ±12° envelope, on the axle that is
doing double duty as steering *and* driving. This car's limit is a lateral
slip-angle ceiling, not a traction-management one, so giving it more torque
neither helps nor needs fixing. TV even makes the FWD balance sweep
**marginally less uniform** (0.094 vs 0.091 at 1×) — plausible and not
alarming: an allocator built to redistribute traction has less to
redistribute on an axle that was never the bottleneck, and reallocating
force that was already fine is not guaranteed to be free.

**The reframing this forces, stated plainly:** "does TV flatten design
sensitivity" does not have one answer — it has the answer for *whichever
mechanism the design axis actually threatens the car through*. Where a
design's vulnerability is a passive differential being overwhelmed by
torque (RWD balance, every layout archetype — F101's mechanism), TV fixes
it, more so as power rises. Where a design's vulnerability is a tire's own
slip-angle ceiling (this FWD archetype), TV has nothing to allocate, because
nothing was being mismanaged.

**Checked, not assumed, twice over.** A systematic scan of every balance
point against a linear interpolation of its neighbours found nothing
suspicious (matching Phase 1's discipline exactly). The one pattern worth a
direct check — `front_fwd`'s power-invariant limit, the same "identical
across power levels" shape that was a real bug in Phase 1 (F100) and again
in this session's own Phase 2 script — was confirmed to be a *different*,
genuine mechanism this time: the drive-force clip is measurably reaching
and saturating the raised 2× cap; the limit does not move because
something else (front-tire slip angle) binds first regardless.

**Fidelity: rung 2** (rule 15), same as everything Season 2 through 4
stands on. This is a trend on a model that reproduces roughly 5% of a real
car's understeer gradient, driven by a tracker that never brakes in a
corner. Whether a real, road-legal 911's engine position stops mattering to
a driver is not a claim this project can make; whether it stops mattering
*to this rung-2 model's own cornering limit, under this controller* is
exactly what was measured, and it does.

**Closes the series plan's Episode 15 question.** Both of POWER-REVIEW's
outputs (F100, F101) were prerequisites for asking it at all; this is the
answer, and it came with an exception precise enough to explain rather than
a footnote to hide.

---

### F103 · A real circuit imports cleanly, but the smoothing constant must be measured on the data in front of you — carrying one over is worth a factor of two in recovered corner radius. · 2026-08-01

**Source:** `[MEASURED]` — `physics/tracks_data.py`, `physics/track.py`
(`SampledTrack`), `tests/test_sampled_track.py`, `tests/test_tracks_data.py`.
Spa-Francorchamps from TUM's `racetrack-database` (`[SOURCED]`, LGPL-3.0 over
OpenStreetMap), never vendored — downloader plus converter, per TRACKS.md §3's
licensing survey.

**The import validates against an external figure (rule 2):** recovered length
**6999.5 m** against the published Grand Prix layout's **7.004 km** — 0.064%.
Bounding box 1270 × 2040 m, consistent with the real circuit's footprint.

**No independently published per-corner radius was found for La Source**
despite repeated search; TRACKS.md's own prior "~25 m" has no citation either
and was *not* reused as though it were external. Recovered minimum radius
(11.4 m) is `[MEASURED]` only, checked for plausibility against a modern FIA
circuit's tightest-corner range rather than against a number.

**The transferable finding is about smoothing.** `scipy`'s `splprep` `s`
parameter has no good universal default and must scale with the data:

| smoothing | length error | min radius | verdict |
|---|---|---|---|
| 0.0 (exact interpolation) | −0.048% | **5.8 m** | fits residual 5 m point-spacing noise as a spurious corner |
| 20 | −0.064% | 11.4 m | in the stable plateau |
| 1401 (`s ≈ m`, step 1's own convention) | −0.242% | 9.9 m | over-smoothed; worst length match |

Step 1's synthetic round-trip (0.1 m spacing, i.i.d. noise) had established
`s ≈ m` as the rule. On Spa (5 m spacing, already-processed centreline) that
rule is **wrong in the other direction**. Both the too-low and too-high
failures are silent — they return a plausible track. The lesson generalises:
measure smoothing against the dataset, never inherit it.

---

### F104 · Every tracks-pilot training run had a dead critic, and the cause was that the value head could not physically reach the required output magnitude within its gradient budget. · 2026-08-01

**Source:** `[MEASURED]` — `experiments/tracks_pilot/`, nine runs on Spa;
`critic_gamma_test.py`, `critic_value_clip_test.py`, `critic_penalty_test.py`,
`d6_spa.py`.

`explained_variance` (D6's own `the_critic_predicts_returns`, gate > 0.3):

| runs | gamma | `off_track_penalty` | EV |
|---|---|---|---|
| long, stage1-oldreward | 0.999 | 50 | +0.72, +0.33 |
| all later stage-1 runs | 0.9995 | 500 | +0.01, +0.00, +0.00 |

**Three single-variable fixes, three clean negatives** — reverting gamma
(−0.001), unclipping the value head entirely at 1e6 (−0.001), reducing the
penalty 500 → 200 (−0.002). None moved EV at all.

**The cause, found by measuring the critic's OUTPUT rather than its error:**

| | critic V(s) | actual return G | V spans |
|---|---|---|---|
| old reward | mean 19.7, sd 2.8 | mean 177, sd 133 | **2.1%** of G's spread |
| current reward | mean −14.7, sd 1.4 | mean 133, sd 365 | **0.39%** |

The critic had barely left its initialisation. The arithmetic explains it:
Adam at `lr=3e-4` over the available gradient steps (`total_steps /
(n_envs · rollout_steps) · epochs · minibatches` ≈ 1,520) gives each parameter
a **total** possible travel of ~0.2-0.5, so a 64-unit output layer reaches
~±30 against a required ±1000. **None of the three fixes changed the required
output magnitude, which is exactly why none of them did anything.**

**This also retracts the healthy-looking baseline:** the old reward's critic
spanned only 2.1% of its spread too, and its EV = 0.33 was substantially GAE's
own bootstrapping correlation (`ret = adv + V`), not prediction.

**Two consequences for this project.** (a) `n_envs` is not a free throughput
knob — it *divides* the gradient-step budget, and choosing 1024 for speed
quartered the critic's ability to learn. (b) **D6 exists, has a check for
precisely this, and was never run on any tracks pilot.** Three consecutive
40M-step runs trained on advantage estimates that were mostly noise while
reward coefficients were tuned on top.

---

### F105 · This project's reward was structurally unlike anything in published racing RL — by one to three orders of magnitude — and the specific failure it produced is documented in a 2021 paper. · 2026-08-01

**Source:** `[SOURCED]` — literature review, two independent agents,
corroborating. GT Sophy (Wurman et al., *Nature* 602:223-228, 2022, Extended
Data Table 1); Fuchs et al. (RA-L 6(3):4257-4264, 2021); Sony GT7
(arXiv:2504.09021); Czechmanowski et al. (arXiv:2504.02420); Evans et al.
(RA-L 8(9), 2023); Hildisch et al. (RLC 2025, arXiv:2505.07321).

**Ratio of largest safety penalty to one step's progress reward:**

| system | ratio | delivery |
|---|---|---|
| GT Sophy (Maggiore) | ~7:1 | dense, every 0.1 s while off course |
| GT Sophy (Sarthe) | ~18:1 | dense |
| Czechmanowski (MF6.1 tyres, PPO) | ~3-4:1 | per-violation, **not terminal** |
| Evans F1TENTH | 5:1 | terminal, penalty = **−1** |
| **this project, before the redesign** | **500-5000:1** | **one terminal sample** |

**Two flagship systems never terminate on crashing at all** — GT Sophy's
rollout worker is literally `dones = [False]`, a continuing task with 150 s
episodes; Fuchs uses fixed 100 s rollouts. Where termination exists the
penalty is −1 to −50. **No surveyed system both terminates and applies a
large penalty.**

**Fuchs et al. documents this project's exact bifurcation, verbatim:**

> "Without this additional wall contact penalty, we found the learned policies
> did not brake and simply grinded along the track's walls... When using
> **fixed valued wall contact penalties**, we found the agent **either did not
> react to the penalty or ended up in a strategy of full braking and standing
> still**, depending on the strength of the penalty."

That is this project's under-deterrence at `off_track_penalty=50` and its
stalling exploit at 500 — same two failure modes, same order, same cause.
**Their fix was not tuning the constant: it was making the penalty
proportional to kinetic energy** (`−c_w‖v‖²`, `c_w = 5×10⁻⁴`). Five runs were
spent rediscovering a documented result.

**Other conventions violated:** progress weight is pinned at exactly 1.0
everywhere (this project swept it); γ=0.9995 at 50 Hz is a **40 s** horizon
against GT Sophy's 9.6 s, Fuchs' 0.98, Czechmanowski's 5 s.

**Process finding, recorded because Season 5 plans considerably more RL:**
reviewing the literature *before* designing the reward would have cost about
an hour and saved nine training runs.

---

### F106 · Distance-before-crash measured tyre-model exploitation, not driving — and rule 4's envelope instrumentation is the only reason it was caught. · 2026-08-01

**Source:** `[MEASURED]` — `experiments/tracks_pilot/v2_variants.py`,
per-section probes (24 fixed points around Spa) with `worst_slip_deg` and
`envelope_occupancy` logged.

The reward-tuning arc reported a rising sequence — 536.6 → 595.2 → **653.5 m**,
the last called "the best yet". Measured against the tyre model:

| policy | distance | worst slip | sections > 12° | occupancy |
|---|---|---|---|---|
| best-distance policy | **653.5 m** | **30.1°** | **24 / 24** | 0.0352 |
| redesigned policy | 519.7 m | 17.8° | 16 / 24 | 0.0124 |

**Every one of the 24 sections was outside the tyre file's own 12° fit.** By
rule 4 that number was never quotable, and the whole "distance keeps
improving" narrative was tracking how freely each policy was permitted to
slide. Correctly scored, the comparison **reverses**.

This independently reproduces Evans et al. (RA-L 2023), who report a dense
progress reward teaching an agent to drift at over 30° slip on a single-track
model valid to ~8° — "thus exploiting the simulation model" — and it is why
GT Sophy carries a dedicated `min(|κ|,1)⁴·|α|` tyre term at weight 0.25.

**The earlier runs' slip was never checked because the per-section probe did
not log it.** Rule 4's instrumentation is core-loop for exactly this reason:
the metric that looked like progress was measuring the model's failure.

---

### F107 · `envelope_penalty` has an inverted-U optimum: 6.0 puts every section inside the tyre model, 15.0 breaks the critic and drives worse. · 2026-08-01

**Source:** `[MEASURED]` — `v2_variants.py --job envelope`, single variable
over the redesigned reward, 20M steps each, 24 per-section probes.

| `envelope_penalty` | EV | D6 gate | distance | worst slip | > 12° | occupancy |
|---|---|---|---|---|---|---|
| 0.5 | +0.479 | pass | 534.0 m | 18.4° | 17/24 | 0.0074 |
| 2.0 | +0.709 | pass | 477.0 m | 14.5° | 6/24 | 0.0038 |
| **6.0** | **+0.703** | **pass** | 468.0 m | **11.0°** | **0/24** | **0.0000** |
| 15.0 | +0.073 | **FAIL** | 412.1 m | 12.7° | 2/24 | 0.0001 |

**6.0 is the first rule-4-valid configuration in the thread** — zero sections
outside the fit, at a cost of 12% distance.

**15.0 is worse, not safer, and the way it fails is the point:** EV collapses
to +0.073, failing D6's gate, and its slip is *worse* than 6.0's. That is
F104's magnitude mechanism recurring in a different term — **any reward
component large enough to dominate the value targets kills the critic, and a
dead critic then drives worse.** The relationship is an inverted U, which is
the same shape F105's Fuchs quote describes for fixed-value penalties. Third
independent sighting inside this project.

---

### F108 · The binding constraint on the learned driver was speed versus competence — not the reward, the observation horizon, or the track. · 2026-08-01

**Source:** `[MEASURED]` — `experiments/tracks_pilot/`, failure analysis over
24 per-section probes; `classical_baseline_spa.py`; `v2_variants.py`.

**Three candidate blockers were tested and rejected**, each recorded rather
than quietly dropped:

- **Reward coefficients** — nine variants (ablation + envelope sweep). Every
  revert was worse; none moved `off_track_rate` off 1.00.
- **Observation horizon** — extending preview 55 m → 120 m → 250 m did not
  move the crash rate and made envelope compliance *worse*, despite the
  braking arithmetic being real (42.7 m/s needs ~89 m to reach 10 m/s; the
  observation reaches 55 m = 1.29 s).
- **Track import quality** — more curvature smoothing reduced sign changes
  58 → 22 but made the *classical* driver do worse (1018 → 338 m).

**The existence proof that reframed it:** the classical driver
**completes a full lap of Spa** — 6999.5 m, 100%, 2.3° slip — at `v_max=12`,
and also at 8 and 6. It spins at 45. **The geometry is driveable and the task
is completable; the failure was purely speed.**

**The failure mode, measured at the moment each probe leaves the road:**

| | |
|---|---|
| speed | 27.9 m/s (peak 42.7) |
| speed the corner allows | 24.0 m/s |
| **above the corner's limit** | **15 / 24 probes, by 9.0 m/s** |
| **slip at exit** | **4.2°** — against a 12° bound |

**It is not out of grip.** At 4.2° the tyres are doing perhaps 40% of what
they can. It arrives too fast and then does not turn hard enough — it
under-brakes and under-steers. The progress reward pays immediately for speed;
braking pays later and only if the corner is *then* taken correctly, so the
policy learns the first half and never the compound second half. The classical
driver never has to discover it: `SpeedProfile` computes the braking point
analytically from the whole track.

**A `speed_cap` limiter on the action** (above the cap, no positive drive — a
limiter rather than a reward term, so it cannot be traded against progress)
took per-section distance from **468 m to 3448 m** in one 20M-step run.

**Also retracted here:** a "required deceleration to follow the limit curve"
metric, which scored `long_exit` (driven by every episode 4-13) *worse* than
Spa and therefore does not discriminate. Caught only by running the control.

---

### F109 · A learned policy drove a lap of Spa: 40.5% of the circuit on average, one full lap, entirely inside the tyre model. · 2026-08-01

**Source:** `[MEASURED]` — `experiments/tracks_pilot/spa_curriculum.py`,
120M steps, 457 updates, 74.8 min, `n_envs=256`, γ=0.995,
`entropy_anneal=True`, progressive speed cap 9.0 → 28.0 m/s over 19 raises.
Selected checkpoint update 80 (cap 11.0), scored at its own cap.

| metric | value |
|---|---|
| explained variance (tail) | **+0.977** |
| per-section distance | **2834.9 m — 40.5% of the lap** |
| best single section | **6122.8 m — 87%** |
| worst slip | **9.8°** (bound 12°) |
| sections > 12° | **0 / 24** |
| envelope occupancy | **0.0000** |
| ~~completed a full lap~~ | ~~1 / 24~~ → **0 / 24, see F110** |

**`off_track_rate` came off 1.00 for the first time in ~20 training runs**,
and the result is rule-4 valid. The driving is genuine, not gamed: `|n|` sits
at **0.51** of half-width (mid-road; 0.2% of time beyond 80%, 0.0% beyond
95%), `s` is strictly monotonic (min Δs +0.196 m/step — never reverses), speed
steady at the cap.

> **CORRECTION (F110, 2026-08-01).** The "completed a full lap · 1/24"
> line above is **withdrawn**. It came from `info["finished"]`, which was
> defined as `self.s >= track.length` — *absolute* position — so a probe
> started at `s0` needed to cover only `length − s0` to be flagged finished.
> Re-scored with the corrected, start-relative definition this policy
> finishes **0 of 24** and covers 2849.6 m (40.7%). The rest of the entry —
> distance, EV, envelope compliance, the lateral-discipline checks — is
> unaffected and stands. See F110 for the bug and for the result that
> genuinely does complete a lap.

**What this establishes:** the task is learnable by plain PPO with no
reference trajectory and no imitation, on a real circuit, within the tyre
model this project can defend. **This is a rung-2 result throughout (rule 15)**
— flat track, no elevation, ~5% of a real car's understeer — and the lap is
slow, capped at 11 m/s where the classical driver's own clean lap runs at 12.
It is a demonstration that the learning problem is solvable, **not** a lap time
and not a claim about a real car.

**Two defects found in the reporting of this very run, both recorded because
both nearly changed the conclusion:**

1. **Evaluation at the wrong configuration.** The per-section probe scored the
   selected checkpoint at the cap the curriculum had reached by the *end*
   (28 m/s) rather than the cap it was trained under (11 m/s). A policy trained
   for 11 m/s driven at 28 slides: it reported 699.7 m, 36.0° slip, 15/24
   outside the envelope — **making the best result in the thread read as a
   failure.** A checkpoint must be evaluated at the configuration it was
   selected under.
2. **A curriculum that advances on plateau will climb past competence.**
   `eval_return` peaked at 3521.7 (cap 11, update 80) and never recovered as
   the cap rose — 181.7 at cap 14, 741.8 at the end. "Distance stopped
   improving" is exactly what a policy at its competence edge looks like, so
   the gate kept promoting a policy that was getting worse. Fixed with a freeze
   once the deployed policy falls below half its best. **This risk was
   identified while designing the curriculum and skipped "to keep it simpler";
   that was the wrong call and it cost a 75-minute run.**


### F110 · A learned policy drives a complete lap of Spa from every start — and the bug that hid it was scoring "finished" against absolute track position. · 2026-08-01

**Source:** `[MEASURED]` — `experiments/tracks_pilot/spa_curriculum.py`
(`cross_track_penalty=2.0`, 40M steps, progressive speed cap, selected
checkpoint at its own cap 13.0 m/s), scored by
`experiments/tracks_pilot/policy_eval.py`.

| metric | 24 probes | 48 probes |
|---|---|---|
| distance | **6999.7 m** | **6999.6 m** |
| **fraction of lap** | **100.0%** | **100.0%** |
| **finished** | **24 / 24** | **48 / 48** |
| off-track | **0%** | **0%** |
| worst slip | 10.4° | 10.4° |
| sections outside the 12° fit | **0 / 24** | **0 / 48** |
| envelope occupancy | **0.0000** | **0.0000** |
| `|n|` / half-width | 0.17 | 0.17 |
| lap time | — | 537.8 s (13.0 m/s) |

**Rule-4 valid**, verified at two probe densities. The car drives mid-road
(`|n|` at 0.17 of half-width, 0.3% of time beyond 80%), `s` is strictly
monotonic, and every probe ends by completing the lap rather than by
crashing, stalling or timing out.

**The missing ingredient was the centreline term** (F108 diagnosed the
symptom: the policy drifted off on *straights*, at 1.4° slip, radius
3,934 m). Adding `cross_track_penalty` — the single most universal term in
the racing-RL literature and the one this project's reward lacked — took
Spa from 40.7% to 100%. **The coefficient matters and is not monotone:**
2.0 is valid at 100%; 5.0 drives *further before crashing* (3753 m) but
puts **24/24 sections outside the tyre fit** and is not quotable. Same
inverted-U as F107.

**The bug, which is the more transferable finding.** `finished` was
`self.s >= track.length * n_laps` — **absolute** position. Every training
env (`start_jitter_m = track.length`) and every per-section probe
(`env.reset(); env.s = s0`) starts at non-zero `s`, so an episode starting
at `s0` needed to cover only `length − s0` to be flagged finished. The bar
got easier the further round the lap the episode began.

It corrupted **both** halves of the loop:

- **Training** — episodes were truncated early and flagged as successes, so
  the finish signal and `episode_distance` partly measured start position
  rather than driving.
- **Reporting** — the tell was distances forming an exact arithmetic
  sequence (7000, 6708, 6416, … = `length − s0`). It also **put a false
  claim into F109** ("completed a full lap · 1/24"), now withdrawn: that
  policy finishes 0/24.

**Why it survived ~20 runs: every policy was scored by a fresh inline
script.** No single version was ever audited, so a wrong flag propagated
untouched. The fix is process, not arithmetic — see D16.

---


### F111 · Raising a uniform speed cap does not teach a policy to drive at the limit — it makes it arrive at corners faster and crash. Negative result. · 2026-08-01

**Source:** `[MEASURED]` — `experiments/tracks_pilot/spa_pushlimit.py`, 120M
steps warm-started from F110's policy, 98 min, cap raised 13.0 → 23.5 m/s
over 7 raises on a gate that lifts the cap while mean speed sits within 90%
of it.

| update | cap (m/s) | `eval_return` | `off_track_rate` |
|---|---|---|---|
| **0** | 14.5 | **6800.2** | 1.00 |
| 96 | 19.0 | 3421.3 | 1.00 |
| 192 | 22.0 | 896.7 | 1.00 |
| 456 | 23.5 | **790.9** | 1.00 |

**The best checkpoint was update 0.** 120M steps made the policy
monotonically worse — 8.6× by eval return — and the final policy is not
quotable: 24/24 sections outside the 12° fit, worst slip 25.6°, occupancy
0.0318. It did get faster (13.7 → 20.9 m/s mean) and the critic stayed
healthy throughout (EV +0.983), so this is not a training failure. **It is
the objective being wrong.**

**The mechanism, and it is the transferable part.** The gate lifted the cap
on *"is the policy pinned against it"* and never on *"can it still complete
a lap"*. `off_track_rate` was 1.00 from update 0 and never recovered, and
the cap rose seven times regardless. Stage 1's gate had a mastery condition;
replacing it with a pure speed-ratio gate silently dropped the only term
checking competence.

**Two further observations that a gate fix alone does not answer:**

1. **Training `off_track_rate` is a poor competence signal.** It is measured
   under sampled actions with exploration noise; the same policy showing 1.00
   there completes 48/48 probes when deployed. F61 already says a result is
   the deployed policy's performance, and `_evaluate_deployed` already
   returns `eval_finish_rate` every 8 updates — the gate should read that.
2. **A uniform cap only binds on straights.** In corners the policy must
   still choose to slow, and nothing in this curriculum teaches that.
   Raising a global ceiling lets the car arrive at corners faster without
   ever rewarding the decision to brake for one — which is exactly the
   observed behaviour.

**What this does not show:** whether a competence-gated cap would work, or
whether the uniform-cap instrument is wrong in principle. Both are open, and
the literature is being consulted before another 98 minutes is spent
guessing (D15).

---


### F112 · Multi-track training on generated circuits reaches 100% lap completion on unseen circuits and drives at the tyre's peak — but transfers to a real circuit only where the training geometry contained the same regime. · 2026-08-02

**Source:** `[MEASURED]` — `experiments/tracks_pilot/multitrack.py`, 64
procedurally generated circuits (`physics/track_gen.py`), 60M steps, 39.3 min,
228 updates, EV tail +0.647. Reward at the magnitudes the F105 survey
supports: `envelope_penalty` 0.25, `cross_track_penalty` 0.2, penalties
**speed-scaled**, no speed cap. `minibatches` 4 → 32, `gae_lambda` 0.95 →
0.98. Scored by `policy_eval.py` (D16) on circuits absent from training.

| evaluation circuit | distance | finished | worst slip | rule 4 |
|---|---|---|---|---|
| held-out `gen10121` | **100.0% of lap** | **100%** | 11.4° | **valid** |
| held-out `gen10123` | **100.0%** | **100%** | 11.4° | **valid** |
| held-out `gen10119` | 100.0% | — | 12.0° | 1/12 over |
| held-out `gen10122` | 100.0% | — | 12.8° | 12/12 over |
| **real Spa** (never seen) | **52.8%** | 0% | **85.8°** | badly invalid |

> **PROVENANCE CAVEAT, added 2026-08-03.** The artefacts for this run were
> **not committed** — `multitrack_summary.json`, the policy and the sections
> file were deleted by a `rm -f multitrack_*` after a smoke test and the names
> were then reused by later runs. 159 comparable artefacts from other runs in
> this directory *are* committed, so this is my error, not policy. The numbers
> below survive only in this entry.
>
> Reproducing it requires checking out commit `840b0f6` and re-running:
> `track_gen.py` and the reward have both changed since (`envelope_exponent`,
> the arcade family, the scale correction). The track set is recoverable
> exactly — `generate_set(72, seed0=10_000)` at that commit gives training
> `gen10002`…`gen10118` and held-out `gen10119, gen10121, gen10122, gen10123,
> gen10130, gen10131, gen10144, gen10148`, verified against the four circuit
> names reported below.

**Three results that hold.** Zero-shot completion of **entire laps on
circuits never trained on** — against 40.7% on a circuit the previous
best policy *had* trained on. Mean speed **18.8 m/s against 13.1** (+43%).
And slip at **11.4°, sitting on the tyre's peak-force angle of 10.3°**: the
first policy in this project that works the tyres rather than cruising
(F111's predecessor used 50.6% of the cornering limit at 0.3° mean slip).

**Rule 4 is marginally breached on two of four** (12.0° and 12.8° against the
12° bound, occupancy ≤ 0.0124). `envelope_penalty = 0.25` is GT Sophy's
tyre-slip weight and is slightly too weak here. That is a coefficient, not a
structure.

**The Spa failure is the finding, and the cause is the generator.** The
policy spins at 85.8°. Measured: the generated circuits' longest stretch
allowing >30 m/s is **115–139 m; Spa's is 1,501 m**. The policy reached
~19 m/s and had **never experienced a 40 m/s corner entry** in training, so
it arrives at Spa's fast corners in a state it has literally never seen.

**The generator was optimised on the wrong quantity, by me.** The
justification for generating at all was that 59.3% of real driving time is
spent on straights "where nothing is learned" — so the generator maximised
corner density (72.8% vs 40.7%) and eliminated straights entirely. That
reading was wrong: **straights are not wasted training time, they are what
produces the high-speed states that make braking necessary.** A circuit
without them does not contain the problem being taught.

**What this does not show:** whether a mixed training set fixes it. A
generator with both regimes now exists (`generate_mixed_set`: 57.9%
cornering, straights 97–963 m, bracketing Spa on both axes) and is being
tested. One seed throughout — nothing here is a trend until three (rule 5).

**Methodology caveat, recorded rather than implied:** the generator designs
are this project's own, not from the literature. Procedural track generation
was never surveyed before building it — D15's lesson was applied to reward
design and then not to this. Measured against the 24 real circuits, the
straights-and-fillets construction is close on every axis (p99 curvature
0.0534 vs 0.0573; curvature rate 5.6e-3 vs 4.8e-3; median corner length 43 m
vs 49 m; clothoid-like fraction 43.5% vs 40.2%), and the harmonic one is
deliberately harder (p90 curvature 2.4× real, 35 corners per lap vs 20). A
survey is outstanding.

---


### F113 · Zero-shot transfer from generated circuits to a real one is unsolved here after six attempts, and the field does not do it either. Negative result. · 2026-08-03

**Source:** `[MEASURED]` — six `experiments/tracks_pilot/multitrack.py` runs,
60M steps each, ~4 h compute total, all scored by `policy_eval.py` on real
Spa with the policy never having seen it.

| # | change from the previous run | Spa distance | Spa worst slip |
|---|---|---|---|
| 1 | harmonic circuits, `envelope_penalty` 0.25 linear | **52.8%** | 85.8° |
| 2 | + mixed generator (straights added) | 27.3% | 93.4° |
| 3 | + fast-corner band fixed, quartic penalty 3.0 | 10.3% | 28.6° |
| 4 | harmonic only, quartic 1.0 | 14.0% | 78.1° |
| 5 | + circuit scale matched to Spa's speed distribution | 13.7% | 22.2° |
| 6 | + 10 Hz control rate (was 50) | 14.7% | 27.5° |

**Nothing beat the first attempt.** Each change was justified by a measured
mechanism — a fast-corner gap, a linear-vs-quartic penalty shape, an
out-of-distribution speed histogram, a control rate every published system
sets differently — and each was individually defensible. The compound result
is that **six plausible fixes produced no improvement**, which is itself the
finding: the failure is not any of the things tested.

**What DOES work, and is not in question:**

* **F110** — a single-circuit policy completes 100% of Spa, rule-4 valid,
  48/48 probes, at 13 m/s.
* **F112** — a multi-circuit policy completes **100% of laps on generated
  circuits it has never seen**, rule-4 valid on 2 of 4, at 18.8 m/s and 11.4°
  slip (the tyre's peak-force angle is 10.3°).

So the policy generalises **within** the generated distribution and fails to
cross to a real circuit. That is a distribution-shift result, not a
competence one.

**The field agrees, and this is the part worth carrying into Episode 19.**
GT Sophy — the strongest racing agent published — **is a specialist**: a
version was trained per car–track combination, and Sony still require
explicit training for each new circuit. Its "mixed-scenario training" varies
opponents and start positions, not tracks. TC-Driver's zero-shot claim holds
on one of three unseen circuits, is marginal on the second and **fails on the
third at 94% crashes**. Learn-to-Race's RL baseline drops 31.1% → 11.8% seen
to unseen. Cobbe/Procgen close the generalisation gap only past ~10,000
training levels; we used 64.

**Recommended change of approach, on that evidence:** stop treating
cross-circuit zero-shot as the target. Train specialists, as the field does,
and report the generalisation gap as a measured phenomenon rather than a
problem to be engineered away. That is what SEASON5 Ep 19 asks for, and it is
a more honest episode than a transfer result nobody else achieves either.

**What this does NOT show:** that transfer is impossible. Untested here are
budget (60M against Czechmanowski's 120M), training-circuit count (64 against
Procgen's 10,000), fresh-sampling every episode rather than a fixed bank
(unanimous in the general-RL literature and not done here), and an off-policy
algorithm (every headline racing system uses one; Fuchs names PPO's
state-independent exploration as the reason it underperforms).

---


### F114 · SAC matches PPO on the task PPO solves, and holds its peak where PPO decays — so the multi-track failure is the task, not the learner. · 2026-08-03

**Source:** `[MEASURED]` — `experiments/tracks_pilot/sac_sanity.py`, both
algorithms on `long_exit` (the single corner Episodes 9-11 solve), identical
environment and reward, 1.5M steps each, one seed.

| | best eval | final eval | final / best |
|---|---|---|---|
| PPO | 393.1 | 122.5 | **31%** |
| SAC | **393.7** | **393.1** | **100%** |

**Why this run exists.** Multi-track SAC reached eval ~4 against PPO's 655
on the same environment. That is not slow learning, it is a suspect
implementation — so rather than debug on the hard problem, run it on a task
whose answer is already known. A ratio below ~0.5 would have meant
`physics/sac.py` was broken.

**It is 1.00. The implementation is sound**, and the multi-track transfer
failure (F113) is a property of the task, not of PPO's exploration. That
closes the last open hypothesis from F113's "what this does not show" list.

**The secondary result is the more useful one.** PPO ended at **31% of its
own best**; SAC ended at 100%. Eval decay after an early peak is a recurring
pattern in this project — F109's curriculum run peaked at update 80 and lost
79% of it by the end, which is what motivated the degradation freeze. SAC did
not do that here. Entropy settled at -1.87 against the -2 target with alpha
self-tuned to 0.0203, i.e. the temperature loop held exploration where it was
asked to.

**What this does not show:** that SAC is better on the multi-track problem —
it measurably is not (eval ~4 vs 655). One seed, one synthetic corner, and
rule 5 wants three before either the parity or the stability gap is a trend.
It shows only that the tool works, which is what it was run to establish.

---


### F115 · Raising the closed-loop brake cap moved every Episode 13 number — and removed a published claim that was reading signal out of noise. · 2026-08-03

**Source:** `[MEASURED]` — `experiments/ep13/run.py` re-run at
`driver.BRAKE_MAX = 0.985 g` (13,137 N), against the committed 0.899 g
(12,000 N) result. POWER-REVIEW Phase 0 item 3.

**Why it moved anything.** Episode 13 *bisects* `grip_use` to the cornering
limit, and the old cap binds at `grip_use ≥ 0.899`. The experiment therefore
spent its entire measurement in the regime where the cap — not the tyre, not
the design — set the braking demand.

| | before (0.899 g) | after (0.985 g) |
|---|---|---|
| TV4 vs open, cornering limit | **+5.18%** | **+4.64%** |
| rear-axle TV vs open | +3.11% | +3.61% |
| 30% less driver preview | −0.34% | **0.00%** |
| 30% more driver preview | +11.55% | **+13.18%** |

**The direction was not predictable in advance** (the F96→F97/F98 pattern):
more braking authority *lowered* the nominal TV gain, because the passive car
benefits from it too, while *widening* the spread across driver preview.

**The finding that matters is a retraction.** The article previously reported
the ±3% track-width check as +5.36% / +5.18% / +5.00% and concluded "the
magnitude moves with the arm, as it must." Re-measured it is
**+4.82% / +4.64% / +4.82% — not monotonic in track width at all.**

The spread across ±3% is now **0.01 percentage points against a bisection
resolution worth ~0.27**. The earlier ordering was three numbers spanning
0.36 pp, every pair within about one resolution step, that happened to fall
in the expected sequence. The moment-arm physics is real and the magnitude
surely does scale with it — **this experiment cannot resolve it**, and it was
quoted as though it had.

**CLAUDE.md's track-width rule is satisfied, and this is what satisfying it
looks like:** "re-run every TV magnitude claim at ±3% track and confirm the
*conclusion* holds." It does — TV is worth +4.6% to +4.8% across the whole
plausible range. The conclusion survives; an incidental observation attached
to it did not, and that distinction is the rule's entire point.

---


### F116 · O9 closed — the RL reward is now pinned to a hand-derived identity, and every Season 5 RL result so far was quoted with that gate open. · 2026-08-03

**Source:** `[MEASURED]` — `tests/test_scripted_policy.py`, 6 tests.

**The gate, and that it was missed.** O9 has sat in the open-questions
register since Season 3 blocking "any further RL result", HANDOFF calls it
"the oldest outstanding correctness item", and SEASON5 §4 makes it explicit
for Episode 19: *"O9's scripted-policy test and D6 pass on the new env before
any result is quoted."* **F110 through F114 were all quoted with it open.**
Nothing in them is known to be wrong — but they were produced against a
reward specification that had never been checked, which is precisely the
condition O9 exists to forbid.

**The identity, derived by hand rather than read off the implementation.**
With every penalty disabled:

    reward_t = ds_t · dt · progress_scale,   ds_t = s_dot_t
    => sum_t reward_t = progress_scale · (s_final − s_initial)

The summed return **is** the arc length advanced along the track. Measured:
49.197346 against 49.197346, difference 0.0e+00.

**Why the existing tests could not have caught this.** Everything in
`test_batched_env.py` checks that the two implementations *agree*; everything
in `test_rl_env.py` checks that a component *behaves*. Neither checks that
the reward means what the specification says. **Two implementations can agree
perfectly on the wrong quantity** — which is exactly how F95's flat reward
direction survived to publication, the failure O9 was raised to prevent.

**What the six tests pin:** the identity itself; exact linearity in
`progress_scale` (2.000000×); the same identity on a closed *generated*
circuit, which exercises wrapping and varying half-width; the same identity
in the batched env, so both implementations satisfy the spec rather than
merely each other; a stationary policy earning nothing, so a reward that pays
for existing fails; and every penalty verified to *subtract*, so a sign error
turning a penalty into a bonus fails.

**Verified to fail against a broken reward** before being trusted: halving
the progress term breaks 3 of the 6.

---


### F117 · POWER-REVIEW Phase 3: the 2× fragility result does not reproduce F98's structure, and is not quotable. Inconclusive, with the reason. · 2026-08-03

**Source:** `[MEASURED]` — `experiments/power_review/phase3_rl.py`, 5M steps,
70.4 min, design-conditioned policy retrained at `drive_max` 9,000 N (2×),
EV tail **+0.791** (passes D6's gate), 4 designs × 2 driver conditions ×
60 deployed rollouts. One seed.

| design | attentive | distracted | worst slip | rule 4 |
|---|---|---|---|---|
| 0.47 front | 0/60 · 0% | 0/60 · 0% | 15.6–16.7° | **over bound** |
| 0.54 | 0/60 · 0% | 0/60 · 0% | 12.1–12.3° | **over bound** |
| 0.61 | **48/60 · 80%** | **43/60 · 71.7%** | 8.0–8.1° | valid |
| 0.65 | 0/60 · 0% | 0/60 · 0% | 1.9–2.3° | valid |

**F98 at 1×:** 0.47 is the only design that ever fails (10/108, 9.3%);
0.54/0.61/0.65 are all 0/119.

**The pre-registered question was whether the gap widens with power.** It
appears to invert — 0.47 stops failing, 0.61 starts. **That reading is not
supported, for two independent reasons, and neither is a close call.**

**1. The designs that "succeed" do so outside the tyre model.** 0.47 runs at
15.6–16.7° of slip and 0.54 at 12.1–12.3°, against the 12° bound. Their 0%
failure rate is not a result under rule 4 — it measures how freely the policy
was allowed to slide, which is F106 exactly. The only rule-4-valid rows are
0.61 and 0.65.

**2. The failure pattern is not physical.** Slip falls monotonically with
front mass fraction — 16.7 → 12.3 → 8.1 → 2.3° — which is what a
weight-distribution sweep should do. Failure rate does not: **0% → 0% → 75% →
0%.** A single spike surrounded by zeros, with the *lower*-slip neighbour on
each side succeeding, is not a fragility ordering. It is far more consistent
with one design-conditioned policy having learned 0.61 badly than with any
property of the car at that mass fraction.

**CONFIRMED as a policy artefact, by direct measurement rather than
inference.** All 48 failures at 0.61 occur at **s = 74-76 m, standard
deviation 0.5 m** — the same point every time — at **1.6° of slip**. The
corner runs roughly 100-290 m, so the car is leaving the road **on the entry
straight, before the corner, with the tyres doing almost nothing.**

That is not a limit-handling property of a 61%-front car. It is F108's
failure mode exactly: a policy that cannot hold a line drifting off a
straight at ~1.5° slip, because nothing in the reward pulls it back to the
centreline. **Episode 10's environment has no `cross_track_penalty`** — the
term F110 showed takes a policy from 40.7% to 100% lap completion, and the
single most universal term in the racing-RL literature (F105).

**This is why the ≥3 seeds F117 originally called for were not run:** the
diagnosis is conclusive without them, and it would have cost ~3.5 hours to
confirm something a 60-rollout probe settled in two minutes. Seeds establish
whether an effect is real; they cannot tell you an effect is a steering bug.

**Supporting evidence:** training was visibly unstable over the last fifth — `return_mean` went 393 → 18.0 → 257.9 → 102.1
→ 273.0 across updates 1000–1200 with `off_track_rate` spiking to 0.50. The
checkpoint is a sample from an oscillating policy, not a converged one, which
is F114's PPO decay pattern in a different experiment.

**Status: Phase 3 is INCONCLUSIVE, not complete.** F98 does not gain a power
conditional on this evidence, and it does not keep one either — the
experiment cannot currently distinguish "fragility inverts with power" from
"this policy is bad at 0.61". What it would take: **≥3 seeds** (rule 5, and a
single non-monotonic spike is precisely the shape seed variance produces),
and an `envelope_penalty` strong enough that 0.47 and 0.54 stay inside the
tyre fit so their success rates mean something.

**Next step, now evidence-led rather than brute force:** re-run Phase 3 with
`cross_track_penalty` added, which addresses the measured cause, and with a
stronger `envelope_penalty` so 0.47 and 0.54 stay inside the tyre fit. Both
changes make the 2× environment differ from Episode 10's 1× one, so the 1×
baseline must be re-run under the same reward before any 1×-vs-2× comparison
is drawn — otherwise the comparison confounds power with reward.

> **SUPERSEDED by F118 (2026-08-04).** This prescription was carried out and
> is wrong on both counts: the environment without the term does not produce
> the failure, and adding the term made cornering measurably worse. The last
> sentence — re-run the 1× baseline under the same reward — survives and is
> the only part that did.

---

### F118 · A cross-track penalty rescues a policy that cannot hold a line, and penalises one that can · 2026-08-04

F117 diagnosed Phase 3's 0.61 failure spike as a steering artefact caused by
Episode 10's environment having no `cross_track_penalty`, and prescribed
re-running Phase 3 with the term added. **Both halves are wrong, and the check
that settles it is the one F117 never ran: score Episode 10's own committed
policy.**

**1. The environment without the term does not produce the failure.** Ep10's
committed policy, scored by `policy_eval` in a clean env, 30 rollouts per
design: **0/30 failures at 0.61, median worst slip 5.7°.** [MEASURED] The
spike does not exist in the policy that environment actually produced, so
"no cross-track term ⇒ cannot hold a line" is falsified directly. The spike
belongs to the Phase 3 retrain, not to the missing term.

**2. Adding the term made cornering worse.** Identical track, identical
evaluator, no steering noise:

| policy | median worst slip |
|---|---|
| Ep10 committed (`cross_track_penalty=0`) | **5.7–6.0°** |
| Phase 3 retrain (`cross_track_penalty=2.0`) | 9.6–10.5° |

70% more slip, in the direction that spends tyre for nothing. [MEASURED]

**The generalisable form, and why both F110 and this are true.** F110 stands
— the term took Spa from 40.7% to 100% lap completion. It is remedial, not
universal: it **rescues a policy that cannot hold a line and penalises one
that can**, because it pulls toward the centreline in exactly the corners
where the fast line is not the centre. A policy that already holds a line
pays the pull as a permanent tax on cornering.

F105 called it "the single most universal term in the racing-RL literature."
That reading was too strong, and the counter-example was in the same survey:
**GT Sophy uses no cross-track term at all.** A term the fastest published
agent omits is not universal.

**Method note — what made this findable.** Nothing in the Phase 3 output
distinguished a good run from a bad one; both produced tables that read as
results. The disproof came from scoring an *externally committed* artefact
(Ep10's policy) in the same harness — rule 11 — rather than from inspecting
the new run's own numbers. Two Phase 3 attempts were voided before that check
was run, one of which also omitted design 0.40 from `EVAL_FRACTIONS`
entirely, so it could not have reproduced the baseline it claimed to extend.

**Consequence for Season 5 staging.** Stage 1 asks whether
`cross_track_penalty=2.0` "is a Spa constant, not a finding" by training
Monza and MexicoCity specialists with it. On this evidence the answer is
likely *Spa constant*, and the stage as written cannot detect that — it has
no control arm. **Stage 1 must run each circuit at both 2.0 and 0.0.** Spa
needed the term because F110's policy could not hold a line; a circuit whose
policy can will be slower with it, and a single-arm test would record that
slowdown as the circuit being hard.

**Source:** `experiments/power_review/phase3_rl.py`,
`experiments/tracks_pilot/policy_eval.py`; void artefacts and their README in
`experiments/power_review/out/void/`.

**Re-verified 2026-08-04 under current code**, 30 rollouts per cell, both
policies scored in the same env at 1x power:

| design | Ep10 committed (ct=0) | retrain (ct=2.0) |
|---|---|---|
| 0.40 | 7.1°, **90% off** | 12.0° |
| 0.47 | 5.5°, **13% off** | 10.2° |
| 0.54 | 5.5°, 0% off | 9.3° |
| 0.61 | 5.7°, 0% off | 9.7° |
| 0.65 | 5.5°, 0% off | 10.0° |

Both halves hold: the retrain carries 4 more degrees of slip at every design,
and Ep10's own fragility structure (0.40 ~90%, 0.47 ~13%, the rest 0%) is
reproduced exactly -- which independently validates the bands hard-coded into
Phase 3's baseline gate, so that gate is checking against a measurement rather
than a remembered number.

**The re-verification cost an hour to an error worth recording.** The first
attempt scored Ep10's policy at **26-28° with 100% off-track**, and the
temptation was to read that as F118 being wrong. It was the harness:
`phase3_rl.POWER_MULT` defaulted to **2.0** at module level, so importing the
module and calling `_cfg()` silently built a double-power car. `main()` sets
it per leg, so no run was ever affected -- only code that imports it. Now
defaults to 1.0, the baseline, which is the D-A pattern the rest of the
project uses: **a default reproduces the control, never the treatment.**

---

### F119 · `SampledTrack` drew offset lines on the wrong side of the road · 2026-08-04

`SampledTrack.centreline` returned heading from `np.arctan2`, which is
**wrapped** to +/-pi. `SampledTrack.to_xy` then interpolated that array with
`np.interp`. A query landing between two samples that straddle the branch cut
got a heading swung through ~2pi, so the offset point was placed using a
heading wrong by up to pi.

**Measured on Spa** [MEASURED, `physics/track.py`, `load_real_track("Spa")`]:

| | |
|---|---|
| branch-cut crossings per lap | 5 |
| max placement error at 5 m offset | **10.0 m — exactly 2x the offset** |
| fraction of the lap wrong by >0.1 m | 0.25% |

2x the offset is the diagnostic signature: the point is mirrored to the
**far side of the track**. This is F36's failure mode in a different
function — a wrong frame conversion that renders a completely believable
picture of a car that was never there.

**Scope.** `Track` (the analytic corners: `short_exit`, `long_exite`,
`hairpin`, `fast_sweep`) is unaffected — it accumulates heading from
curvature and is continuous by construction, so every Season 1-4 figure built
on those is fine. Only `SampledTrack` — the **real circuits** — was wrong,
which is precisely what Season 5 is about. `TrackBank` already unwrapped, for
this exact reason; `SampledTrack` was simply missed when that lesson was
applied.

**Fix.** `heading = np.unwrap(np.arctan2(dy, dx))`, making `SampledTrack`
match `Track`'s contract. Safe by construction: `sin`/`cos` of the unwrapped
heading equal those of the wrapped one at every sample point, so nothing that
consumes heading pointwise changes value. Only interpolation between samples
changes — which is the defect.

**The test nearly became decoration, which is the more useful lesson.** The
first version asserted no step exceeds 10x the sample spacing and **passed
against the broken code by 0.02x** (9.92x measured). The branch-cut error is
spread across one sample interval rather than concentrated in one step, so a
threshold hunting for a big jump never sees it. The published threshold is 3x,
measured from both sides: legitimate geometry reaches 1.42x -- which is just
`1 + n*kappa` at Spa's 11.4 m minimum radius, the outside of a corner being
genuinely longer -- and the bug reaches 9.92x.

CLAUDE.md rule 11 says to ask what it would take to fail a check. Running the
test against the reverted code is that question made mechanical, and it is
the only reason this was caught.

**Source:** `physics/track.py:SampledTrack.centreline`;
`tests/test_sampled_track.py::test_offset_line_is_continuous_across_the_heading_branch_cut`
and `::test_sampled_track_heading_is_continuous_like_the_analytic_track`.

---

### F120 · The solved Spa lap is a clean lap, not a limit lap — 0.7% of it is at the friction limit · 2026-08-04

Drawing the Spa specialist (`curr_ct2`) for the first time — rules 1 and 13,
outstanding for this whole thread — produced the figures and also the number
that should govern how the result is used.

[MEASURED, `experiments/tracks_pilot/spa_lap_figure.py`, deployed mean-action
policy, `speed_cap` 13.0 m/s (the cap the checkpoint was selected under, F109)]

| | |
|---|---|
| lap completed | **6,999.3 m — 100%**, 0% off-track |
| worst-wheel slip | 9.69°, inside the 12° fit — rule 4 valid |
| max lateral acceleration | 0.97 g |
| **mean** lateral acceleration | **0.08 g** |
| lap above 0.9 tyre utilisation | **0.7%** |
| lap above 0.5 tyre utilisation | 2.7% |
| speed, p1-p99 | 13.0-14.7 m/s (cap 13.0) |

**The policy is pinned against the speed cap, not against the tyres.** Mean
speed is 13.03 m/s against a 13.0 cap; mean tyre utilisation is 0.090. It
touches the friction limit in a handful of corners and coasts at a twelfth of
it everywhere else.

**Why this matters more than the figure.** Season 5's destination is torque
vectoring, and TV only does anything to a car that is *using its tyres* —
reallocating grip between wheels is meaningless when 97% of the lap uses 9%
of it. The user identified this before the measurement existed: *"the speed
cap is working but it is not going to learn anything we want it to since it
won't be at the limit... otherwise TV isn't helpful."* That is now a number:
**0.7%.**

**What Spa is and is not.** It IS a solved control problem and a valid rule-4
lap — the recipe completes a real circuit cleanly and repeatably, which no
earlier attempt did (F110). It is NOT a limit-driving baseline, and any TV
delta measured against it would be measured on a car that is barely working
its tyres. Season 5 stage 1 should carry this: a specialist that completes a
circuit under a cap has cleared the *first* gate, not the one TV needs.

**Method note.** The first version of the lateral-acceleration number was
1.52 g, computed as `v^2 * kappa` from the **centreline** curvature. The car
drives its own line, so that is not its lateral acceleration -- and 1.52 g
is above what the tyres can deliver, which is what flagged it. The logged
`a_y` and `utilisation_max` arrays give 0.97 g. CLAUDE.md rule 7 says metrics
come from the logged arrays; this is why.

**Source:** `experiments/tracks_pilot/spa_lap_figure.py`,
`out/spa_ct2_lap.svg`, `out/spa_ct2_lap_utilisation.svg`,
`out/spa_ct2_profile.svg`, `out/spa_ct2_lap_figure.json`.

---

### F121 · A scalar speed cap is the wrong instrument: it binds 99.6% of the lap and is still too fast in the corners · 2026-08-04

F120 established that the solved Spa policy spends 0.7% of the lap at the
friction limit. This is why, and it is not a tuning problem.

**What is holding the policy back, measured point by point** [MEASURED,
`curr_ct2_policy.pt`, deployed policy, one lap, `speed_cap` 13.0 m/s]:

| the car is sitting on... | share of the lap |
|---|---|
| the **speed cap** | **99.6%** |
| the tyres | 0.7% |
| neither | 0.4% |

The curriculum did not stop early. It stopped *correctly*: `CAP_SLIP_HEADROOM_DEG`
freezes the cap once worst-wheel slip approaches 10°, and slip reaches 9.69°
in the tightest corner. So the cap froze at the value where **one corner** is
at the tyre limit, which leaves the other 99% of the circuit driving at a
speed set by that corner.

**The instrument is wrong, not its setting.** A single scalar cannot express
"fast here, slow there", and Spa needs a factor of four between the two. A
curvature-aware reference — `driver.SpeedProfile`, which already exists —
gives, against the flat 13.0 m/s cap:

| | |
|---|---|
| reference speed | 10.4 min, 40.0 mean, 60.0 max m/s |
| **above** the cap over | **99.3% of the lap** |
| **below** the cap over | **0.7%** — the corners |
| median headroom the flat cap discards | 26.6 m/s |

The flat cap is **simultaneously too slow almost everywhere and too fast
exactly where it matters**. The 99.3/0.7 split is the same 0.7% as the
at-the-limit measurement, from the opposite direction: the only places the
cap is not the binding constraint are the places it is already too permissive.

**Not sensitive to the assumption.** The reference's absolute speeds depend on
`v_max`, which is a choice. The conclusion does not: at `v_max` of 20, 25, 30,
45 and 60 m/s the split is 99.3% / 0.7% in every case. A finding that flipped
on `v_max` would not be a finding (rule 11 in the form CLAUDE.md's track-width
note uses).

**Consequence for Season 5.** Getting a policy *to the limit* is a different
problem from getting one *round a circuit*, and only the second is solved. The
fix is already built and has never been trained with: `speed_ref_penalty` and
`speed_ref_a_lat` on `EnvConfig`, backed by `SpeedProfile`, reward the policy
for tracking a curvature-aware target instead of obeying a flat limiter. That
is the next experiment, and it is the one the torque-vectoring episodes depend
on — TV reallocates grip between wheels and has nothing to reallocate while
mean utilisation is 0.090.

**Caveat on the lap time.** Integrating `ds/v` over the reference gives 197 s
against the driven 535 s. That is [DERIVED] from the plan, **not a simulated
lap** — it assumes the car achieves `a_lat` everywhere and ignores the tyre
model's actual envelope. It is quoted as an indication of the size of the gap,
not as a lap time, and no lap time may be quoted from it (rule 6, and the
convergence rule's ban on quoting times from runs that did not happen).

**Source:** `experiments/tracks_pilot/spa_lap_figure.py` for the driven lap;
`physics/driver.SpeedProfile`; `physics/rl_env.EnvConfig.speed_ref_penalty`.

---


# Decisions

### D1 · The project drives an offset-free tire. · 2026-07-25
`physics.tire.default_tire()` zeroes `PHY*`/`PVY*`/`PHX*`/`PVX*`.
`as_shipped_tire()` returns the file verbatim and is what the reference-table
check validates against.

**Rationale:** F6. Zeroing the shifts removes a manufacturing artefact that a
real car aligns out; it is not an idealisation of the tire's physics. Every
fitted shape coefficient survives — peak μ becomes exactly the Magic Formula's
own `μy`, and cornering stiffness moves by at most 0.22% (only the point at which
the slope is read shifted).

**Consequences:** peak μ at `Fz0'` is 1.049 both ways instead of 1.012 / 1.086.
`Fy(0) = Fx(0) = 0` exactly. Max lateral g at RV-1's static front corner rises
from 1.026 to 1.064 — still inside the 0.95–1.10 band.

**Would be revisited if:** we ever want to model a car that genuinely pulls, or
Ep 16 shows Chrono's offsets materially changing a conclusion.

### D2 · Keep the `Ey` curvature asymmetry. · 2026-07-25
**Rationale:** removing it means zeroing `PEY3`/`PEY4` — an edit to the `P*`
coefficients, which discards the fit's internal consistency
(`docs/vehicle-reference-parameters.md` §3.3). It contributes **zero**
peak-force asymmetry; it only moves where the peak sits (0.27° apart at 1 kN,
0.79° at `Fz0'`, 2.38° at 9 kN, where both peaks are outside our envelope
anyway). It is third-order in slip angle, so it vanishes entirely at the ±0.5 g
slip angles where understeer gradient is measured.

**Consequence for D2 (the diagnostic):** the mirror test must assert **peak force
exactly** and **trajectories to a stated tolerance** — not bit-equality.

### D3 · Implement standard MF 2002, not a simplified form. · 2026-07-25
**Rationale:** Chrono consumes this same file with these same equations, so Ep 16
compares two *vehicle* models rather than two tire models plus two vehicle
models. Confirms open item 7 in `vehicle-reference-parameters.md` §6.

### D4 · Diagnostics lead with plain English. · 2026-07-25
Console output groups checks under the question each answers and states findings
in sentences; `-v` and the JSON carry the assertion-level detail.

**Rationale:** `docs/result-evaluation-guide.md` opens by promising that "is the
physics right?" is checkable *without* vehicle-dynamics expertise. A wall of 60
assertions named `peak_mu@3929N` broke that promise.

### D5 · Each axle is two tires at half the axle load, not one tire at full load. · 2026-07-25
**Rationale:** with load sensitivity in play those are materially different —
one tire at 7,200 N makes far less than two at 3,600 N — and the real car has
two. Modelling the axle as a single tire would have systematically
under-predicted grip and corrupted every absolute number in Season 1.

### D8 · The skidpad holds speed, matching SAE J266. · 2026-07-25
`trim_skidpad(hold_speed=True)` is the default: net longitudinal force zero, no
longitudinal load transfer. **Rationale:** F17 — it is what the real test does,
and the alternative changes K by 33% and inverts the terminal balance. The grip
cost of the balancing drive force is not modelled (O2) and is reported per point
so the omission stays visible.

### D6 · The skidpad is solved, not simulated. · 2026-07-25
`trim_skidpad` runs a damped Newton solve on the two steady-state equations.
**Rationale:** at steady state the transients are gone by definition, so
integrating for ten seconds and hoping is strictly worse than solving to machine
precision in milliseconds. The two paths are cross-checked in D2 — the trim is
exactly a state in which the integrator's accelerations vanish. Sweeps use
continuation, warm-starting each solve from its neighbour, which is also what
keeps the solver on the grippy side of the tire curve near the limit.

### D7 · D3 accepts an understeer gradient below the road-car band. · 2026-07-25
**Rationale:** F11. The gate is stated as a bicycle-model band (0.05–1.5 deg/g)
with teeth at both ends, plus a separate assertion that K must land *below* the
road-car band — the parameter sheet's own structural check. The reason is
recorded in the report rather than the tolerance being widened, per
`result-evaluation-guide.md` Part C.


### D9 · Combined slip is a friction ellipse, on by default. · 2026-07-25
`MF02Tire.fy_combined` scales pure-slip lateral force by
`sqrt(1 - (Fx/Fx_peak)^2)`; `BicycleBackend(combined_slip=True)` is the default.
**Closes open item O2.**

**Rationale.** Brought forward from Episode 4 for two reasons. It closes a
dishonesty that was already live: D3's constant-speed skidpad applies a drive
force to hold speed, and without an ellipse that force was free. And everything
from Ep 4 onward — the racing line, FWD vs RWD tire utilisation, torque
vectoring — is a combined-slip story, so the alternative was building three
episodes on a model that says a tire can brake and corner at 100% of both.

**What it is and is not.** The one certain thing is modelled: a tire has a finite
force budget and longitudinal force spends part of it. The *shape* of the
trade-off is an assumption. MF 2002 ships its own fitted weighting functions
(`RBX*`/`RBY*`), and this `.tir` does not contain them, so the ellipse is a
stand-in. Any result that turns on the shape rather than on there merely being a
trade-off carries that caveat.

**Measured effect on existing results:** small. At 0.87 g the throttle holding
skidpad speed is 4.9% of the driven axle's longitudinal budget, which costs
0.1% of its lateral force. K and max lateral g are unchanged to three decimals.

**A small finding fell out.** On an RWD car the throttle costs the *rear* axle
grip, so combined slip makes the car need slightly **less** steering, not more —
power oversteer in miniature. Direction confirmed by test.

**Deferred deliberately: the trail-braking result.** That is Episode 4, and the
strong version is the optimal-control solver discovering trail braking on its own
rather than a hand-scripted comparison of three brake protocols. The physics to
support it now exists; the experiment waits for the solver.

### D11 · A controller is measured by how hard its car can be driven before it fails, not by one lap time. · 2026-07-27

**Decision.** Episode 13 drives every configuration with the same closed-loop
driver, on the same line, to the same speed plan, and sweeps one knob — `grip_use`,
the fraction of the car's measured grip the plan is built for — until the lap stops
being valid. The reported result is the **highest `grip_use` that still produces a
valid lap** (on the road, and inside the ±12° tire fit, applied per lap). Lap time
is reported alongside it and is a monotone consequence of it, not independent
evidence.

**Rationale.** At a fixed `grip_use` every configuration is attempting an identical
lap and takes an almost identical time, because the *plan* sets the speed and the
driver only tracks it. What differs between configurations is whether the car can
follow the plan at all. A single lap at a single aggression would therefore measure
the driver's tuning as much as the car's behaviour; sweeping to failure measures
where the failure is, which is a limit property of the car-plus-controller.

**What it costs.** The metric is only as good as the driver, and F84 measures
exactly how bad that can be: a ±30% change in the driver's preview time moves the
headline from "nothing measurable" to +11.6%. The sweep does not remove that
dependence — it makes it visible and cheap to re-measure, which is the most this
approach can honestly claim.

**Not applicable to the optimal-control episodes.** A minimum-time solver has no
aggression knob; it is already at the limit by construction. This is a
closed-loop-only protocol and Seasons 1–2 are unaffected.

### D12 · A reinforcement-learning policy is judged on the actions it would actually take, including where the tire model is concerned. · 2026-07-29

**Decision.** D6's envelope checks —
`the_policy_stayed_inside_the_tire_model` and
`the_tire_file_s_own_load_range_was_respected` — turn on the **deployed**
(mean-action) policy. The sampled policy's figure is reported on the same line
every time and is never dropped.

**Rationale.** This extends F61 ("a reinforcement-learning result is the
DEPLOYED policy's performance") to the physics checks, where the code had
silently done the opposite: it took `max(deployed, sampled)` while its own
comment claimed the deployed number was the gate. Because the exploration scale
does not anneal (F93), the two differ by several degrees of slip on the same
weights — H seed 2 reaches 6.8° deployed and 12.1° sampled. Gating on the
sampled number judges a controller by noise that is not present when it runs.

**What the sampled number still buys, and why it is kept.** It measures how much
of *training* happened where the Magic Formula was extrapolating. A policy can
be clean at deployment and still have learned from partly fictional rewards, and
that is worth seeing. It is diagnostic detail, not the gate.

**Recorded because it moves a headline.** Applying it to Episode 14 changes
"3 of 6 seeds stayed inside the tire fit" to "6 of 6". A protocol change in the
flattering direction has to be visible, stated, and attributable — see F94 for
the measurement that forced it.

---

### D13 · Episode 16 (the Chrono cross-check) is deprioritized. RL multi-track training is the priority. · 2026-07-30

**Decision.** `docs/content-series-plan.md` names Episode 16 the series'
"SERIES PAYOFF" — three design points re-run in Project Chrono, trend
direction compared, the only validation tier that tests findings against
assumptions this project did not make itself. User decision: not pursuing
it for now. Explicit reason given: this would matter for a result heading
toward formal publication; that is not the current goal, and RL training
across multiple (eventually real) tracks is the more interesting direction
right now. **Revisit-able, not closed** — the user's own words were "we can
revisit chrono later if I change my mind."

**What this changes.** `SEASON5.md`'s dependency graph listed Ep 16 as a
prerequisite *before* Season 5 starts, specifically to avoid building a
season of setup-delta claims on an unvalidated rung-2 model. With Chrono off
the table for now, that specific risk is accepted rather than mitigated —
worth restating plainly rather than quietly dropping: every finding in this
project remains a rung-2 claim (rule 15), unverified against an independent
simulator, and stays that way until Ep 16 is picked back up. This is a
knowingly accepted scope decision, not an oversight.

**What replaces it as the priority: RL multi-track training.** Concretely,
`TRACKS.md`'s own staging order — `SampledTrack` + the round-trip curvature
test, closed-loop support, one real circuit imported and validated against
published corner radii, batched-env support for a real circuit's step count,
*then* retrain. This was already the plan; it now has priority over Ep16
rather than sitting behind Phase 3 of the power review.

**Not touched:** `docs/content-series-plan.md` is read-only reference and is
not edited to reflect this — this entry is the correction of record per
CLAUDE.md's own rule for that situation. `HANDOFF.md`'s episode-status table
is updated to show Ep 16 as on hold rather than next.

---

# Open

| # | Question | Blocks |
|---|---|---|
| O1 | Rescale the tire to GR86 size via `LMUY`/`LKY`/`LFZO`, or accept a 245-section tire on a car that wears 215s? Currently unscaled and mildly optimistic. | Nothing yet; must be decided before any absolute-grip claim is published |
| ~~O2~~ | ~~Combined-slip formulation~~ **CLOSED by D9** — friction ellipse, on by default. Revisit only if a result turns on the shape of the trade-off rather than its existence. | |
| O3 | Differential model: concrete preload/ramp torque-bias formulation. | Ep 12 |
| O4 | Mirror-test tolerance for the D2 diagnostic, given D2 above. | `double_track.py` |
| ~~O6~~ | ~~How much of the understeer gap does the double-track model close?~~ **CLOSED by F29 — none of it.** The gap is the Bundorf suspension terms. |  |
| O8 | Add compliance steer / roll camber / roll steer, or accept a permanently low understeer gradient and compare only trends? Decides whether Season 2's magnitudes are ever quotable. | Season 2 |
| ~~O6-old~~ | ~~How much of the understeer gap (F11) does the double-track model close? F18 predicts the size of the effect; Ep 5 measures it. The single most important open question in Season 1. | Ep 5 |
| O7 | ~~Does terminal oversteer survive lateral load transfer?~~ **CLOSED by F17** — it was a protocol artefact, not a model property. |  |
| ~~O10~~ | ~~Episodes 11 and 13 have not been re-measured at a realistic steering-noise level~~ **CLOSED by F97/F98.** Episode 13's 78%->100% result is retracted (F97); Episode 11's fastest-is-most-fragile ordering survives (F98), though its recovery-mechanism percentage table does not (small-n). | |
| ~~O9~~ **CLOSED 2026-08-03** | The RL environment had **no scripted-policy sanity check**. Closed by `tests/test_scripted_policy.py`: with every penalty off, summed reward is *exactly* the arc length advanced — a hand-derived identity, not a number read off the code — plus exact linearity in `progress_scale`, the same identity on a closed generated circuit and in the batched env, a stationary policy earning nothing, and every penalty verified to subtract rather than add. Three of the six fail against a deliberately broken reward. | — (was: any further RL result) |
| O5 | Pin real citations for two bands in the reality-check figure: slip angle at peak (6-12°) and road-sports-car skidpad grip (0.85-1.05 g). Both are general knowledge today, marked as such on the figure. | Publishing any comparison against them |
| O6 | Pin a real citation for the **~9% FSAE skidpad torque-vectoring ceiling** and for the claim that the best lap times allow deviations from neutral yaw-rate tracking. Both come from `docs/content-series-plan.md`, which states them without references; both are marked `[SOURCED — citation outstanding]` in Episode 13's figures and text. | Episode 14 leaning on either |

---

# Validation status — where we stand against outside knowledge

`diagnostics/out/D1_reality_check.svg` is the live version of this table; it
regenerates on every run, so it cannot drift from the code.

The project's validation comes in four tiers, weakest to strongest. It is worth
being blunt that only the first two are done:

1. **Internal consistency.** 60 D1 checks: signs, monotonicity, conservation.
   Catches bugs, proves nothing about reality. **Done.**
2. **Reproducing an independent computation** of the same tire file. Proves the
   Magic Formula is implemented correctly. **Done.**
3. **Agreement with published ranges.** What the reality-check figure shows.
   **Partly done** — four quantities measurable now, three waiting on the
   vehicle model.
4. **A different simulator.** Episode 16 re-runs three design points in Project
   Chrono and compares trend direction. This is the only tier that tests whether
   our findings survive assumptions we did not make ourselves. **Not started, and
   it is the one that counts.**

| Quantity | Published range | Ours | |
|---|---|---|---|
| Slip angle at peak grip | 6–12° | 10.1° | inside |
| Peak grip, one tire at resting corner load | 0.85–1.05 g | 1.064 g | **outside, explained** |
| Grip accelerating ÷ grip cornering | 1.05–1.20× | 1.116× | inside |
| Static Stability Factor | 0.95–1.80 (NHTSA) | 1.63 | inside |
| Understeer gradient | 1.5–3.0 deg/g | — | needs `bicycle.py` |
| Step-steer yaw rise time | 0.08–0.30 s | — | needs `bicycle.py` |
| Lap time gained from torque vectoring | 1–4% (series plan) | **+0.51%** lap, **+1.30%** skidpad | **below the band, explained** (F82) |

**The one outside the band is expected and is not a defect.** Our tire is a
245-section fitted for a ~1,980 kg car; the real GR86 wears 215s. It grips more
than the real car would. Open item O1 tracks rescaling it via `LMUY`/`LKY`/`LFZO`.
Because the series' output is *comparative* — this design versus that one, with
one tire model throughout — an absolute-grip offset does not invalidate anything.
It does mean no absolute lap time or cornering-g figure gets published as a claim
about a real GR86.

**Two of the bands still need real citations** (O5), and Episode 13 added a third
and a fourth (O6: the ~9% torque-vectoring ceiling and the neutral-yaw-tracking
claim). The NHTSA range and the
handling bands are sourced in `docs/vehicle-reference-parameters.md`; the
slip-at-peak and skidpad ranges are general vehicle-dynamics knowledge, marked as
such on the figure, and must be pinned to a reference before publication.

**One band was deliberately excluded.** `result-evaluation-guide.md` Gate 2 gives
0.95–1.10 g for max lateral acceleration — but that band was itself derived from
this tire file. Checking this tire against it would be circular, so it is not on
the figure. Worth watching for the same trap elsewhere in the docs.
# On `docs/learning-scaffold.md`

Its predict-then-check structure is not being used, by decision. Validation
against published ranges and against Chrono (the table above) is the mechanism
we are relying on instead. The scaffold's concept explanations remain useful as
reference; its Prediction/Reality slots are not part of the workflow.

### D14 · Every training run in this project runs D6, and every checkpoint is evaluated at the configuration it was selected under. · 2026-08-01

**Why.** Two failures in the Spa RL thread were caused by skipping steps this
project already had:

- **D6 was never run on any tracks pilot.** Its own
  `the_critic_predicts_returns` check describes the dead critic exactly, and
  three consecutive 40M-step runs trained on noise-dominated advantages while
  reward coefficients were tuned on top (F104). Every Season 3/4 episode ran
  D6; the pilots quietly did not.
- **A checkpoint was scored at a configuration it was never trained for**,
  reporting the best result in the thread as a failure (F109).

**The rule.** A training run is not finished until D6 (or its track-adapted
form, `experiments/tracks_pilot/d6_spa.py`) has run against its history and
checkpoint, and the per-run summary carries `explained_variance` alongside the
performance numbers. Where a curriculum varies the environment during
training, the configuration in force at each evaluation is recorded, and the
selected checkpoint is scored at **its own** — never at whatever the schedule
happened to reach by the end.

**Scope.** `d6_spa.py` adapts exactly two of D6's seven checks — the two
hardcoded to `physics.track.CORNER_RADIUS`, meaningless on a 20-corner
circuit — to use the circuit's own tightest corner. Everything else is D6's
logic unmodified. Adaptation is not permission to loosen a gate.

---

### D15 · Reward design starts from the published literature, not from first principles. · 2026-08-01

**Why.** The Spa reward was designed from scratch and tuned over nine
training runs. The literature review that followed (F105) found the resulting
structure was one to three orders of magnitude outside anything published —
a 500-5000:1 terminal penalty against per-step progress, where the field uses
3-20:1 delivered densely — and that the exact failure mode it produced
(a policy that either ignores the penalty or freezes) is documented verbatim
in Fuchs et al. (2021), along with its cure.

**The rule.** Before designing or substantially re-weighting a reward, check
what comparable published systems use, and record the comparison. The specific
anchors this project now has: progress weight pinned at 1.0; safety penalties
3-20:1 against per-step progress and **speed-scaled rather than fixed**;
discount horizons of 5-10 s, not 40; random-position spawning at speed.

**What this is not.** Not an instruction to copy coefficients — Sony's own
follow-up finds no correlation between how closely a generated reward matches
their hand-tuned one and how well it performs. It is an instruction to know
the shape of the solution space before searching it. An hour of reading would
have saved nine runs.

### D16 · There is one policy evaluator, it lives in version control, and no run writes its own. · 2026-08-01

**Why.** The `finished` bug (F110) survived roughly twenty training runs and
reached FINDINGS.md because every result was scored by a throwaway script
written fresh for that run. Each was slightly different, none was ever
reviewed, and the harness that should have caught the bug was the thing
being rewritten each time. The arithmetic error was trivial; the process
that let it live for twenty runs was not.

**The rule.** `experiments/tracks_pilot/policy_eval.py` is the evaluator.
Import it. Do not write a per-run eval, not even "just to check something" —
that is exactly how this happened. It reports a fixed metric set every time,
so two runs are always comparable, and it carries:

- distance measured **from each probe's own start**, never absolute `s`
- a termination-reason breakdown that **must sum to 1** — a probe ending for
  an unnamed reason is a bug in the report, and is asserted in the tests
- a rule-4 validity verdict, with `headline()` **refusing to quote a
  distance** when any probe sits outside the tyre fit
- lateral-discipline and `s`-monotonicity checks, so "it drove far" cannot
  be confused with "it drove the road"

**Auditing a shared harness is worth doing in explicit passes.** This one was
done in four: (1) write tests for the bug; (2) **verify they fail against the
old code** — 3 of 4 did; (3) find that the 4th passed *vacuously*, its only
assertion wrapped in an `if len(...)` guard, and strengthen it until it also
failed; (4) re-score every affected claim. Pass 3 is the one worth
institutionalising: a test that cannot fail is indistinguishable from a test
that passes, and rule 11 already says so.

### D17 · Power is a sensitivity AXIS, not a re-baselining — and the series stands on three levels, reported as a curve. · 2026-08-03

**Why.** POWER-REVIEW D-A and D-B, ratified by Phases 1 and 2 and recorded
here per Phase 0 item 5. They have governed every measurement since F100 and
were never written into this file.

**D-A — how power is represented.** The `drive_max` force cap is wrong in a
speed-dependent way (F43's own caveat: a real engine's force falls with
speed). The obvious fix — adopt `F = min(F_cap, P/v)` and re-baseline
everything onto it — **was checked before being adopted, and the check
changed the decision**: at RV-1's own 174 kW that model drops below today's
4.5 kN cap once the car passes 38.7 m/s, which is 30% of Episode 6's own
trace. Re-baselining would therefore have silently changed published numbers
for a reason unrelated to the question being asked. Power is instead a
**sensitivity axis** run alongside the existing representation.

**D-B — the levels.**

| level | power | role |
|---|---|---|
| RV-1 (1×) | 174 kW / 228 hp `[SOURCED]` | the validation anchor; every diagnostic keeps passing here |
| 1.5× | ~260 kW / ~350 hp | the ordinary sports-car tier, and arguably the most *relevant*: effects that express here matter for cars people drive |
| RV-1P (2×) | ~350 kW / ~470 hp `[ASSUMED]` | the amplification end, where F43 showed design effects at 4-5× their 1× size |

**Every design question is answered as the curve, with its shape stated.** An
effect that grows smoothly through 1.5× is a different and more useful claim
than one that only appears at 2×. Headline at the level where the effect
expresses, conditional stated in the finding — the F43 structure. "Rear drive
is faster *at a given power*" was Season 2's most useful sentence; this makes
that form the default.

---

### D18 · Three synthetic corners, not one — and the third is chosen because it changes character with power. · 2026-08-03

**Why.** POWER-REVIEW D-D, recorded per Phase 0 item 5. One 40 m corner
cannot support "is it faster" claims: different corner speeds stress
different budgets, so a single radius silently selects which budget the
answer is about.

| track | radius | what it stresses |
|---|---|---|
| `hairpin` | 15 m | second-gear, traction-dominated exit |
| `long_exit` | 40 m | the incumbent — continuity with everything published |
| `fast_sweep` | 90 m | lateral-dominated, near-flat at RV-1 power **and not at RV-1P** |

That last row is the point of the set rather than a side effect: a corner
whose limiting budget *changes* between the two power levels is itself a
finding, and one a single-radius track cannot produce.

**Scope, deliberately bounded:** the full {3 tracks × 2 powers} grid runs only
for episodes being actively re-measured (7 and 8); everywhere else takes
single-track spot checks. And no TUM import — these are built from the
existing `Segment` machinery, because real-circuit geometry is `TRACKS.md`'s
problem and mixing the two would confound a power result with an import
result.

