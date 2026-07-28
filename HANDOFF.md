# Contact Patch

**A series about how cars actually work, built from scratch and tested at every step.**

Four rectangles of rubber, each about the size of a hand, are the only thing connecting a car to the road. Every phenomenon in this series happens there — grip, slip, load transfer, saturation, and eventually four independently commanded torques. Episode 1 is one contact patch. Episode 14 is about how to spend four of them.

---

## Start here

**If you are picking this up cold, read in this order:**

1. `docs/content-series-plan.md` — what is being made and why. **The primary document.** 16 episodes, four seasons.
2. `docs/vehicle-reference-parameters.md` — the numbers. Reference vehicle, tire model, validation targets.
3. `docs/result-evaluation-guide.md` — how to tell whether a result is real. Four gates, decision tree.
4. `docs/learning-scaffold.md` — 14 concept modules, prediction-first. Fill in as you go.
5. `docs/vehicle-codesign-research-plan.md` — the full research plan. Deeper than the series needs; consult for methodology justifications.

Then read the two live documents. The planning docs say what we intend; these
say what is true and how to work:

- [`CLAUDE.md`](CLAUDE.md) — the working rules. Loaded automatically every
  session, so it is where anything that must always be obeyed belongs.
- [`FINDINGS.md`](FINDINGS.md) — every finding and decision, numbered and dated,
  plus how to read the figures.

**The series plan is the deliverable spec. The research plan is the reference.** Where they disagree on ordering, the series plan wins — it was written later and deliberately reorders the build to serve the content.

---

## Directory structure

`✓` = built and passing. Everything else is still to come.

```
contact-patch/
├── CLAUDE.md             ✓ the working rules — loaded every session
├── HANDOFF.md              ← you are here: where the build is, what to do next
├── FINDINGS.md           ✓ what is true so far, every decision and why; how to
│                           read the diagnostic cards. Accretes every session
├── requirements.txt      ✓ numpy + pytest. CasADi arrives with Ep 4, torch with Ep 9
├── docs/                   planning documents (read-only reference)
├── physics/                simulation backends
│   ├── schema.py         ✓ versioned obs/action spec — SINGLE SOURCE OF TRUTH
│   ├── tire.py           ✓ MF 2002 pure-slip evaluation + .tir parser
│   │                       default_tire() is OFFSET-FREE; as_shipped_tire() is not
│   ├── backend.py        ✓ abstract interface: set_design/reset/step/get_obs
│   ├── bicycle.py        ✓ two-axle model, skidpad solver, friction ellipse (Ep 1–4)
│   ├── mathkit.py        ✓ numpy/CasADi backend shim — ONE set of tire formulas
│   ├── track.py          ✓ centreline as curvature(s), plus Ep 4's two corners
│   ├── optimal_control.py ✓ distance-domain min-time collocation (CasADi/IPOPT)
│   ├── double_track.py   ✓ four wheels, lateral transfer, roll distribution (Ep 5+)
│   ├── torque_vectoring.py ✓ Ep 13: reference model + PID + QP allocator. Two
│   │                       layers, separable, zero-order held per control step
│   └── driver.py         ✓ Ep 13: the closed-loop driver — pure pursuit plus a
│                           quasi-steady-state speed profile, pushed to failure
├── diagnostics/            D1–D6 generators; run on every build
│   ├── common.py         ✓ Check/Report, grouped output, generated write-ups
│   ├── D1_tire_card.py   ✓ 60 checks — tire model
│   ├── D2_invariants.py  ✓ 29 checks — signs, conservation, envelope, pose
│   ├── D3_steady_state.py ✓ 21 checks — skidpad, understeer, closed-form theory
│   ├── D4_transient.py   ✓ 13 checks — step steer, yaw inertia, linear model
│   ├── D5_load_transfer.py ✓ 19 checks — four-wheel loads, ARB, degeneracy
│   └── out/              ✓ per-diagnostic Dn.md write-up + figures + JSON
├── tests/                ✓ pytest; covers the plumbing D1 does not.
│                           test_figures.py parses every SVG and pins the three
│                           frame conversions — all three have been wrong once
├── viz/                    figure generation
│   ├── lib.py            ✓ shared palette + SVG helpers
│   ├── diagram.py        ✓ pictorial primitives: tires, cars (plan and rear
│   │                       view), arrows, friction circles, frame converters
│   ├── tire_figures.py   ✓ Ep 1/2 figures + the validation ledger
│   ├── transfer_figures.py ✓ D2 load-transfer figures
│   ├── skidpad_figures.py ✓ Ep 3 understeer figures
│   ├── line_figures.py   ✓ Ep 4 racing line; shared track backdrop
│   ├── transient_figures.py ✓ D4 step-steer figures
│   ├── load_figures.py   ✓ Ep 5 four wheels, body roll, anti-roll bar
│   ├── utilisation_figures.py ✓ Ep 6 friction circles, along-the-path, diff
│   └── tv_figures.py     ✓ Ep 13 two layers, allocation, the limit, tracking.
│                           Its captions are COMPOSED from the traces — two
│                           hand-written ones contradicted their own numbers
├── tires/                  tire parameter files
│   └── Sedan_Pac02Tire.tir MF 2002 set, BSD-3 from Project Chrono
├── experiments/            one directory per episode
│   ├── common.py         ✓ episode output plumbing
│   ├── ep01/ … ep05/     ✓ run.py + out/ + results.json
│   ├── ep06/             ✓ four min-time solves + grid refinement;
│   │                       `--figures-only` redraws from cached traces
│   └── ep07/ … ep16/       code + outputs, kept with the episode
└── episodes/               article drafts, accreting per the scaffold
```

Run everything:

```bash
python -m pytest tests/ -q && for d in D1_tire_card D2_invariants D3_steady_state D4_transient D5_load_transfer; do python -m diagnostics.$d; done
```

Each diagnostic writes `diagnostics/out/Dn.md` — a generated write-up with every
figure, finding and note in one place. **Read those, not the JSON.**

Each diagnostic prints a plain-English summary — what it checked, grouped by the
question each group answers, then what it *found*. Add `-v` for every individual
assertion and every technical note. Both always land in full in the JSON report,
so the console never has to carry them.

**Why experiments are per-episode:** Episode 15 re-runs Episode 6's and 7's sweeps with torque vectoring enabled. Keeping each episode's experiment code intact and re-runnable is the difference between that being an afternoon and a rebuild.

---

## Diagnostics vs episodes — they are different numberings

`D4` is the fourth **diagnostic**. `Episode 4` is the fourth **article**. They
have nothing to do with each other, and writing "Ep 4" next to "D4" has already
caused one misunderstanding. The actual mapping:

| Diagnostic | What it gates | Feeds which episode |
|---|---|---|
| **D1** tire card | tire model | Ep 1, Ep 2 |
| **D2** invariants and signs | everything | — (infrastructure) |
| **D3** steady-state handling | model realism | Ep 3 |
| **D4** transient response | `I_zz` wiring | **Ep 8** |
| **D5** load transfer audit ✓ | double-track core | Ep 5 |
| **D6** training health ✓ | every RL run | Ep 9+ |

**Trail braking is Episode 4, not D4.** It needs the optimal-control solver, and
the physics for it (the friction ellipse, FINDINGS D9) is already in place.

---

## Build order — first three sessions

The series order is not the dependency order for code. Build in this sequence:

### Session 1 — Schema and tire ✓ DONE
Everything downstream depends on these being right.

1. **`physics/schema.py`** — observation and action spaces with explicit units, sign conventions, normalization constants. Both backends and all analysis import this. Nothing else touches raw simulator output.
2. **`physics/tire.py`** — MF 2002 pure-slip lateral and longitudinal, reading `tires/Sedan_Pac02Tire.tir`.
3. **`diagnostics/D1_tire_card.py`** — validates against the table below.

**Sign convention warning, learned the hard way:** `PKY1` is **negative** in the Chrono file. This is the ISO/TYDEX convention, where `Fy` opposes a positive slip angle. Evaluating without accounting for it returns zero peak force and negative cornering stiffness — silently, with no error. Assert the convention explicitly in `schema.py`.

**D1 must reproduce this table** (computed directly from the file's coefficients,
so it is checked against `as_shipped_tire()`, not the offset-free project tire):

| `Fz` (N) | peak μ | `Fy` peak (N) | slip at peak (°) | cornering stiffness (N/deg) |
|---|---|---|---|---|
| 1000 | 1.139 | 1139 | 9.7 | 375 |
| 2000 | 1.095 | 2190 | 9.7 | 715 |
| 3000 | 1.052 | 3155 | 10.0 | 997 |
| 3929 | 1.012 | 3974 | 10.5 | 1197 |
| 5000 | 0.965 | 4826 | 11.3 | 1357 |
| 7000 | 0.878 | 6149 | 13.1 | 1489 |
| 9000 | 0.792 | 7126 | 15.1 | 1486 |

If these match, the tire is correct and Episodes 1–2 are already writable.

**They match.** Peak μ to 0.1%, `Fy` peak to 0.02%, cornering stiffness to 0.22%.
Episodes 1 and 2 are writable.

Nine findings and four decisions came out of D1. They live in
[`FINDINGS.md`](FINDINGS.md), not here — that file is the running record of what
the build has established and why, and it also explains how to read the D1 card.
The four that constrain the next sessions:

- **The project drives an offset-free tire** (`default_tire()`), because the file
  as shipped made 7.4% more grip cornering one way than the other. `as_shipped_tire()`
  is the file verbatim and is what the reference-table check validates against.
  Decision D1, finding F6.
- **D2's mirror test must assert peak force exactly and trajectories to a stated
  tolerance, not bit-equality** — a small `Ey` curvature asymmetry is deliberately
  retained rather than editing the `P*` coefficients. Decision D2.
- **Never model coasting as `κ = 0`** — solve for the κ that gives the demanded
  `Fx`. Finding F7.
- **Above ~7 kN of corner load the tire's peak lies outside our ±12° envelope.**
  Not a problem for RV-1 today; check envelope occupancy before believing any
  Season 2 sweep that pushes a corner past it. Finding F8.



### Session 2 — Bicycle model + Episodes 1–3 ✓ DONE
4. **`physics/backend.py`** — the abstract interface. RL and analysis code never touch a simulator directly.
5. **`physics/bicycle.py`** — two axles, longitudinal load transfer.
6. **`diagnostics/D2_invariants.py`, `D3_steady_state.py`** — sign/conservation asserts, skidpad.

**Target:** understeer gradient lands in **1.5–3 deg/g** for the reference vehicle. Published bands: passenger car 3–5, sports car 1–2, below 1 essentially never seen in production. Noise floor for meaningful differences is **0.2 deg/g**.

### Session 3 — Optimal control + Episode 4 ✓ DONE

### Season 1 complete — Episodes 1–5 drafted ✓

D4 (transient response) was built early, out of build order, and feeds Ep 8
rather than anything in Season 1. That was wasted sequencing; don't repeat it.

### Session 6 — Episode 6, front vs rear drive ✓ DONE

Four min-time solves (both drivetrains × open/ideal differential) plus a grid
refinement check. No new physics — the solver and the four-wheel model already
existed. Findings F34–F38.

Three things came out of it that reach backwards:

- **F36 is a defect in a published figure.** Every plan-view car in the project
  was drawn pointing 180° backwards along its own line. Fixed, and pinned by a
  test that works the rotation geometry rather than restating the formula.
- **F37 corrects Episode 5's anti-roll-bar caption**, which asserted a bar cannot
  change how much a car leans. True of our parameterisation, false of cars.
- **F39 corrects Episode 4's convergence reasoning**, and changes how every
  min-time number in the project must be gated.

### ⚠️ Outstanding from F39 — read before quoting any min-time result

An unconverged IPOPT solve returns the objective of a trajectory that does not
quite obey the physics, wrong by 0.1–0.7% in **either** direction. "The objective
has stopped moving" is not a convergence test and neither is "two node counts
agree" — runs sharing a stopping criterion agree about the same artefact.

Now standing practice:

1. **`Solution.success` is a gate, not a footnote.** Do not quote a time from a
   solve reporting `Maximum_Iterations_Exceeded`. `experiments/ep06/run.py` prints
   a loud warning when any solve in a comparison fails to converge.
2. **Prefer the grid where everything converges over the finest grid.** Ep 6
   reports 100 nodes for exactly this reason.
3. **`max_iter` is a parameter now**, default 2000. The four-wheel rear-drive
   problem needs ~8000. At 2000 it produced a 0.02 s error that read convincingly
   as a grid dependence.
4. **Warm starts resample across node counts.** They used to be silently ignored
   on a node-count mismatch, which is what made clean convergence unreachable.

**Still to do:** re-solve **Episode 4's** two cases with the raised iteration limit.
Its apex-shift conclusion is about *where* the apex sits and probably survives —
Ep 6's effect did — but its quoted lap times rest on an unconverged solve and are
marked as such in the draft.

### Session 7 — Episode 7, where you put the weight ✓ DONE

Front mass fraction swept 0.40–0.65, both drivetrains. Findings F44–F47.
Headline: balance swings the understeer gradient 1.06 deg/g and moves the lap
time by nothing measurable. F45 answers the objection Ep 6 deferred — weight on
the driven axle recovers ~85% of the front-drive penalty and never closes it.
F47 is a defect that reached back into Episode 4 (apex quantised to the node grid).

### Session 8 — Episode 8, front/mid/rear engine ✓ DONE — **SEASON 2 COMPLETE**

Findings F48–F50. The payoff landed: the front-engine saloon and the rear-engine
911 sit at opposite ends of the balance axis and side by side on the inertia axis,
so "mid-engine is better" is a polar-moment claim habitually argued as a
weight-distribution one. A controlled pair at identical 43% balance gives 201 vs
304 ms rise time with the same understeer gradient — a comparison impossible with
real cars.

F50 corrects the plan's "twitchier at the limit" expectation: overshoot is 0.23%
vs 0.14%, right direction, negligible magnitude. Our step is 3 degrees at constant
speed with no driver in the loop, which structurally cannot show twitchiness.

**Convergence recipe that finally worked, and it generalises.** Seed every member
of a family from the EASIEST one, not the most representative. The front-drive
four-wheel solve converges in ~13 s where rear-drive needs 250-350 s; seeding all
five layouts from it plus one retry at 16,000 iterations got all five converged.
Ordering by "closest to the reference car" failed — that layout needs a four-wheel
answer to start from and cannot bootstrap itself.

### The Season 2 result, stated once

Ep 6 found 0.10 s between drivetrains. Ep 7 found nothing measurable across weight
distribution. Ep 8 found 0.032 s across the full polar-moment range. **Every
"which is faster" answer came back smaller than expected, and Ep 8 explains why:**
the minimum-time solver knows exactly when the corner arrives, so a slow-responding
car simply starts steering earlier. Response time is nearly free to a driver with
perfect foresight and expensive to one without.

That is not a null result, it is the argument for Season 3. Do not restate it as a
disappointment.

### Session 9 — Episode 9, teaching a car to drive ✓ DONE

Findings F51–F56. **D6 is built** — the last diagnostic, nine checks, seven of
them written from failures that actually happened here.

The headline is not the one the plan predicted. The plan expected the policy to
exploit the tire model; it does (14.4 deg peak slip, 0.5% of steps beyond our 12
deg bound) but only marginally, because it is not fast enough yet to be tempted.
**What it actually found was a control input nobody meant to give it**: the
throttle-to-force map has a kink at zero (12 kN braking vs 4.5 kN drive), so a
Gaussian policy straddling it delivers braking its mean action does not have.
Sampled it finishes 88% of laps; its own mean action finishes 0%. F54.

Re-check the tire-model exploit in Ep 10-11 as the policies get quicker.

### ⚠️ What Season 3 cost, and what to do about it

Six separate failures, **none of which raised an error**, all of which produced
training runs with plausible moving curves:

1. shared gradient clip — value grad 150x the policy's, everything scaled 0.0067
2. exploration 16x too large for steering
3. exploration 10x too small for throttle (one scale cannot serve both)
4. task physically impossible — 32 m/s entry into a 19.5 m/s corner
5. critic explained variance collapsing mid-run
6. behaviour living in the exploration noise

**The diagnosis that worked every time was the same one:** compute what the task
requires and compare it against what the algorithm was given. The corner needs a
0.037 steering action; the corner caps at 19.5 m/s. Four of the six would have
been caught before any compute was spent. Those comparisons are now D6 checks.

**Run D6 on every training run and believe it when it fails.**

### Session 10 — Episode 10 + an audit of Episodes 7-10 ✓ DONE

Findings F57-F67. An in-depth audit found four methodology problems; all are
fixed and recorded. Two changed published conclusions.

**Two environments now exist, deliberately.** Episode 9's has
`envelope_penalty=0.0` and asks what an unguarded learner does; Episode 10's
penalises operating outside the tire fit and asks how design affects a driver held
inside defensible physics. Recorded as a protocol change (rule 9), not a bug fix.
Ep 9's `test_the_envelope_is_not_enforced` still guards its premise.

**The single most useful rule to come out of Season 3** is F61: a
reinforcement-learning result is the DEPLOYED policy's performance. Episode 9 was
written around an 88% sampled finish rate whose deployed figure was 0%. D6 gates
on this now and Episode 9 fails the gate.

### Session 11 — figure review of Episodes 9-10, then Episode 11

Findings **F68** and **F69**. Reviewing the Episode 9 and 10 figures *by eye*
found that Episode 10's artefacts on disk had been generated by a pre-gate version
of `run.py` and never rebuilt — because rebuilding meant a 5M-step retrain. Four
defects, including a retracted `+0.9997` correlation still rendered as `+1.00`
beside a curve that visibly contradicted its own caption. See F68.

**`run.py --eval-only` now exists** and recomputes every downstream number and
figure from the cached `policy.pt` in about two minutes. Use it. The policy is the
artefact; everything after it is derived, and when deriving it is expensive the
derived things go stale.

**Episode 10's D6 fails `exploration_is_not_growing`** and always did. The article
now says so, the threshold was not loosened, and F69 records what it does and does
not put at risk.

**New: `viz.review_figures.line_compare`** — overlaid lines with no cars, plus
unrolled offset, speed and one control channel. Built for
`ep09/out/06-noise-was-braking.svg`, which finally shows F54's mechanism on the
road rather than asserting it: the deployed policy never commands below **+0.32**
throttle on the entry straight and arrives at **22.9 m/s**; the sampled one's noise
crosses into braking and arrives at **21.5 m/s** and gets round.

**Episode 11's perturbation knobs are in `EnvConfig`** — `steer_noise` and
`grip_spread`, both defaulting to off and pinned by a bit-for-bit test that every
Episode 9/10 result is unchanged. Grip retargets through `LMUY`, never a `P*`.

### ⚠️ Outstanding, and none of it is optional

0. **Every figure gets rendered and looked at before its episode is called done.**
   This is now the single highest-yield check in the project. F68's four defects
   passed the whole test suite, were internally consistent within each half, and
   were visible in about ten seconds of looking at the picture.
1. **Rewrite Episode 9.** Its structure is "it learned to drive → but deployment
   differs". The true structure is "it never learned to drive; here are the two
   shortcuts it found". The 0% is the result. Nothing else in Season 3 is honest
   until this is done.
2. **Seed discipline. Still violated.** Every Season 3 number is one training
   seed. Rule 5 asks for three. Rollout spread is not seed spread and does not
   substitute. ~15 min per seed; there is no excuse left.
3. **F65 is unattributed.** The learned driver finds designs ~4x more different
   than the solver does. Attractive explanation: a suboptimal driver exaggerates
   design differences. Confound: the two run different entry speeds. The control
   test (optimal control at 15 m/s) **will not converge** — that is the blocker.
4. **Episode 7's 47%-front rear-drive solve** still will not converge after 16,000
   iterations. Excluded everywhere; it also removes one of only three usable
   cross-check designs.
5. **Four Episode 7/8/9 figures remain unreviewed by eye.** Five figure-bug
   classes this session passed XML, stamp and title tests and were visible only by
   looking. Rendering them is not optional either.

### Episode 11 — DONE. The finding is real, after two retractions.

Findings **F70** (the retraction and its lessons) and **F71** (the result).

**The result.** Under steering noise + grip variation, counting only laps that never
left the ±12° tire fit: **47% front loses 9 of 104 laps (8.7%); 54/61/65% lose none.**
Holm-Bonferroni over six pairwise Fisher tests — 47 vs 54 p = 0.0011, 47 vs 65
p = 0.0016, 47 vs 61 p = 0.0033. Undisturbed the driver is flawless: 120/120 on all
four, zero laps outside the fit.

**The mechanism is recoverability, not margin.** All four designs leave the limit
about equally often; the 61% car did it MORE often than the 47% car (18 laps vs 16)
and crashed **once against thirteen**. Understeer is a negative feedback loop —
pushing wide scrubs speed, which restores grip. Oversteer is a positive one. That
supersedes the margin story and is Season 2's mechanism as a robustness property.

**Three of my own errors are recorded rather than buried**, and they are the
transferable part: (1) a failure rate needs far more samples than a mean — n = 10
said "no failures" and n = 120 says 8.7%; (2) **worst-slip is an extreme-value
statistic and is never a bound** — max grows with n, medians do not; (3) rule 4 is a
**per-lap** rule, and applying it per-condition threw away 39 good laps for one
excursion.

**Also corrected: the policy is NOT conservative.** The Magic Formula is flat near
peak — at 4 kN the tire peaks at 10.35° and the policy's 5.8–7.3° is already
**94–98% of peak lateral force**. The 12° envelope sits AT peak. "Five degrees of
margin" was a misreading of a flat curve.

**`--deep` and `--eval-only` are the modes that matter.** `--deep` is 4 designs x 2
conditions x 120 rollouts (~14 min) and is what the claim rests on; the 5x5 grid at
n = 40 is breadth only and its rates are underpowered. `figures()` overlays the deep
cells so no figure can show an underpowered rate as the headline.

**All four figures were rendered and inspected**, which caught: a stale `n=40` stamp
on 120-rollout rates, a `hasattr(track, "heading_deg")` fallback silently drawing
every car at heading 0 (the F36 failure mode again — `Track` has no such method; use
`centreline()`), label collisions in three places, a NaN rendering as "nan%", and a
40%-front panel reporting "65% of laps left the road" for a car that fails 100% of
laps with no disturbance at all. `tests/test_fragility_figures.py` now pins the NaN
and metric-selection cases.

### Session 12 — the drivetrain yaw moment, and the backfill it forced ✓ DONE

Findings **F72–F80**. The double-track model had **no drivetrain yaw moment at all**
— moving the entire drive force from one wheel to the other changed the computed yaw
by exactly zero, so Season 4 would have measured a silent null. Fixing it turned out
to change three published conclusions.

**What the fix did, by episode:**

| Episode | Was | Now |
|---|---|---|
| 5 | load transfer moves K 0.19 → **0.17** (lower) | 0.19 → **0.22** (higher). Conclusion unchanged. |
| 6 | "rear drive is faster, under either assumption" | **crossover near 50:50**, and it reverses with power too |
| 7 | front-drive penalty "never reaches zero" | **crosses zero at 54% front** |
| 8 | front drive 12.21 s, the clear outlier | **12.07 s, second quickest, inside the pack** |
| 10 | cross-check on 3 designs, both pick 54% | **4 designs**, both pick 47% |
| 9, 11 | — | impact measured at 0.02 s on 1 of 4 designs — negligible, left alone |

All ten Episode 7 solves now converge, including the 47%-front rear-drive case that
had **never** converged in the project's history (831 s of failure → 15 s certified).

**The transferable lesson is F79, and it is about method rather than physics.**
Three separate "measurements" of the fix's impact were all wrong because I compared
`diff="open"` against Episode 7's published `diff="ideal"` numbers, put the solver
fix in the wrong function (`str.replace(..., 1)` matched the bicycle model), and
silently broke the bicycle path for hours. **Reproduce the published number first.**
Had I checked that my "before" case returned 12.1910, all three would have surfaced
in ten minutes instead of two hours.

`optimal_control._LEGACY_YAW_MOMENT` is kept as a documented A/B hook so this class
of question is answerable by experiment. Never set it for a published solve.

**Also this session:** the differential is real now (`differential_forces`, one
mechanism — torque flows from the faster wheel to the slower, F76/F77);
`speed_couple` and the grip-proportional bias were the same effect counted twice and
gave a welded diff the wrong sign. Episode 11's fragility result stands (F71).
Episode 12 is written. The braking point is interpolated between nodes rather than
snapped to one — F47's apex defect recurring in a different variable, caught because
a reader asked why the lines in a figure all looked the same.

**412 tests. D1 60/60, D2 38/38, D3 21/21, D4 13/13, D5 22/22, ep12 8/8.**
(Session 13: **489 tests**, and `D-ep13` fails 1 of 12 on purpose — see F84.)

### Outstanding

1. **Episode 6's open-differential comparison is still unavailable.** The rear-drive
   open-diff solve stops on the iteration limit at 8000. Every Episode 6 claim uses
   the ideal differential, where all four converge. The remedies in F78 are untried:
   regularisation via `steer_rate_weight`, continuation in the coupling, coarser
   grid first.
2. **Season 3 still has one training seed**, and Episode 10's D6 still fails
   `exploration_is_not_growing`. Both disclosed, neither fixed.
3. **Episode 9 still needs rewriting** around "it never learned to drive" (F61).
4. **The limit-seeking driver** the user asked for — minimum-time reward with a
   large terminal envelope penalty, agreed shape — is not built. It is Season 4
   infrastructure: torque vectoring only acts where tires are saturated, so a TV
   result measured with an under-driving policy measures nothing.
   **Partly addressed in Session 13, and only partly:** Episode 13 built a
   *classical* closed-loop driver (`physics/driver.py`) that is pushed to failure by
   construction and logs lateral acceleration and per-wheel friction-ellipse
   utilisation, so saturation is now verifiable rather than assumed — `D-ep13`
   gates on it. The RL side is untouched, and Episode 14 needs it.
5. **A `[ASSUMED]` number in the driver moves Episode 13's headline by more than the
   headline is worth** (F84). Any Season 4 comparison that swaps the driver — which
   Episode 14 does by definition — inherits this and has to control for it.

### Episode 12 — DONE ✓

All four criteria met: `experiments/ep12/run.py`, its `out/`, the draft, and
FINDINGS F72–F77. Report passes 8/8. Both figures rendered and reviewed. This is the
first episode of **Season 4** (seasons are 1–4, 5–8, 9–11, **12–16**).

### Session 13 — Episode 13, the classical controller ✓ DONE

Findings **F81–F86** and decision **D11**. Two new modules, both of which Episodes
14–16 inherit: `physics/torque_vectoring.py` (reference model + PID + QP allocator)
and `physics/driver.py` (a closed-loop driver, because **a controller can only be
judged in closed loop** — a min-time solver handed four wheel forces just uses them
optimally, which is the question Episode 8 already answered).

**The headline, and it is smaller than the plan expected.** The controller works:
it tracks the reference yaw rate 88% better than the passive car and the allocator
delivers what the PID asks for. It buys **+5.2% of cornering limit**, **+1.30% of
skidpad lateral g** — against a ~9% published ceiling — and **+0.51% of lap time**,
because two thirds of `long_exit` is a power-limited straight.

**Three things that reach forward into Episodes 14 and 15:**

1. **F83 — the control condition is mandatory.** The allocator with its yaw demand
   forced to zero gets ~40% of the lap gain (38–56% across sensitivities) and
   *negative* gain on the skidpad. "Torque vectoring is worth X" is two claims, and
   Episode 15 needs them separated.
2. **F84 — a `[ASSUMED]` number in the DRIVER moves the headline from −0.34% to
   +11.55%.** A driver aid is tuned against a driver whether or not anyone says so.
   Episode 14 must hold the driver fixed or vary it deliberately, never leave it
   implicit. `D-ep13` fails this check on purpose and the article leads with it.
3. **F85 — under Episode 11's steering noise the controller turns 31/40 valid laps
   into 40/40** and halves the lap-time scatter. That is much larger than anything
   in the undisturbed lap and is the effect these systems are actually sold on.

**`D-ep13` fails 1 of 12 checks by design** — F84's driver sensitivity. The
threshold has not been loosened and the article leads with the failure. Also worth
knowing: the ~9% ceiling and the "deviations from neutral yaw tracking" claim both
come from the series plan, which states them without references, so both are marked
**`[SOURCED — citation outstanding]`** rather than presented as verified. Tracing
them is cheap and would strengthen Episode 14.

### Session 14 — visualisation audit of Episodes 1–13 ✓ DONE

Requested directly: a full pass over every published episode asking whether it has
a pictorial figure and a technical one (rule 1), and whether every headline number
has a figure behind it. Findings **F87–F90**. No new episode; this is maintenance
on the twelve that exist.

**Three real defects, not just gaps:**

1. **F87 — Episodes 9 and 10 could not regenerate half their own figures.**
   `viz.review_figures.path_review`/`.line_compare` and
   `viz.conditioned_figures.line_family_figure` were written, exported, and called
   from nowhere. `--figures-only` silently produced 3 of 6 (Ep 9) and 3 of 5
   (Ep 10) embedded SVGs. Both are now fully wired; Ep 9 also gained the
   `--eval-only` mode Ep 10 already had, so fixing this never required a retrain.
2. **F88 — Episode 9's core narrative depended on an unseeded torch RNG.**
   `_sampled()` drew from torch's global generator with nothing seeding it, so
   regenerating in a fresh process produced a DIFFERENT sampled trajectory that
   contradicted the episode's own published numbers (21.5 m/s and "gets round"
   became a car that also leaves the road). Fixed with an explicit
   `SAMPLE_SEED = 1`, found by sweeping 20 seeds and picking the first that
   reproduces the published numbers to three significant figures. **This was
   already broken before this session** — just never observed, because nobody had
   regenerated the figures in a fresh process since they were published.
3. **F90 — Episode 7's "brake release moves 15.9 m" was stale**, measured before
   the F72/F73 yaw-moment fix that F80 used to correct this same episode's lap
   times and drivetrain ordering. Under the corrected physics it is **~10.6 m**.
   Direction and significance unchanged; only the magnitude was wrong. The lesson
   is F79's again: a shared-machinery fix invalidates every downstream number, not
   only the ones the fix was chasing.

**One figure deliberately left unfixed.** `experiments/ep09/out/04-two-environments.svg`'s
likely source (`learning_figures.failure_figure`) has a hardcoded caption that
contradicts Episode 10's real, saved policy (F89). Wiring it anyway would have
produced a figure whose caption contradicts its own data — the exact class of
defect this project keeps finding (F68, F81, now F88). Left orphaned and flagged
rather than guessed.

**Additions, not just fixes:** Episode 2 got a technical μ(Fz) figure (the graph
its title promises and never drew — F82-adjacent, filed under the "smaller
additions" note); Episode 12 got a delivered-force comparison across all three
differential types (its sharpest number, "35% thrown away," had no dedicated
visual); Episode 7's `balance_card` got the 4th (brake-release) panel its own
docstring already promised.

**500 tests passing** after this session's changes, run in full, not just the
figure suite.

### Session 15 — Episode 14 infrastructure and pilot ✓ DONE (infra), ⚠️ AWAITING A GO/NO-GO ON PRODUCTION SCALE

**Question:** give a learner the same four wheels, the same physics and the same
stopwatch, with no reference model. Does it agree with the engineers?

**Built, all additive to Season 3 — every prior result unaffected:**

- `physics/rl_env.py`: `EnvConfig.tv_mode` — `"none"` (unchanged, all 18 prior
  tests pass, plus a new bit-for-bit seal test), `"hybrid"` (variant H: `act_dim`
  3, the policy's third action is an `Mz` demand through the *same*
  `torque_vectoring.Allocator` Episode 13 uses), `"end_to_end"` (variant E:
  `act_dim` 5, four raw per-wheel force fractions, no allocator at all — matches
  `docs/vehicle-codesign-research-plan.md` Phase 4b exactly). Both route through
  `DoubleTrackBackend.attach_torque_vectoring`, Episode 13's own hook — no
  backend changes needed.
- The environment now logs `a_y` and per-corner `fx/fy/fz`
  (`rollout()` reports `peak_a_y_g`/`mean_utilisation`) — the exact gap this file
  flagged below as blocking verification of any TV result.
- `diagnostics/D6_training_health.py` gained one new, additive check:
  `exploration_covers_the_torque_vectoring_action`, a no-op for `tv_mode="none"`.
- `experiments/ep14/run.py` (`--pilot`, `--eval-only`, `--figures-only`) and
  `viz/rl_tv_figures.py` (one pilot sanity figure; full pictorial/technical
  pairs come after production training, per rule 1's own logic — nothing to
  draw yet).
- **513 tests passing**, full suite, after all of the above.

**Pilot run complete (F91): 60,000 steps/variant, seed 0, NOT a result.**

| | wall-clock | D6 |
|---|---|---|
| H | 208 s | FAILED 3/13 (exactly what an undertrained policy should fail) |
| E | 104 s | FAILED 3/12 (same) |

The new exploration-scale check passed for both, and E's four wheels explore
with a near-identical spread (1.0x) — no wheel is being ignored. The sanity
figure shows three distinct, non-degenerate `Mz`-vs-distance curves for C/H/E.
**The pipeline works.**

**⚠️ The number this pilot exists to produce, and the reason to stop here:**
linear-scaled to Episode 10's 5,000,000 steps, that wall-clock is **~4.8
hours/seed for H** and **~2.4 hours/seed for E** — before rule 5's 3-5 seeds
per configuration, which multiplies straight through. Reported per the approved
plan's pacing (pilot first, then scale); **not acted on**. Before running a
production pass, decide: full 5M-step multi-seed runs as-is (many hours,
serial), a smaller production step count investigated first, or a remote/batched
run. This is not this session's call to make alone.

**Read before scaling to production:**

- **F84** — the driver-tuning dependence. An RL policy IS its own driver
  (steering and throttle both learned), so this mainly matters when comparing
  against Episode 13's *classical* controller, which used a separately hand-built
  driver (`physics/driver.py`). The comparison this episode actually needs —
  overlaying **realized `Mz` against distance**, computed identically for C, H
  and E via `DoubleTrackBackend.yaw_moment` on each one's own logged per-wheel
  forces (`experiments/ep14/run.py::realized_mz`) — sidesteps most of this: it
  is a control-surface shape comparison, not a lap-time race, and doesn't
  require C, H and E to share a driver.
- **F83** — separate the allocator from the yaw control, in both directions.
  Not yet needed for H/E vs each other (H always uses the allocator, E never
  does, by construction) but relevant if H's own contribution gets decomposed
  further.
- **F61 and the D6 gate** — a reinforcement-learning result is the DEPLOYED
  policy's performance, over several seeds and several harnesses. Production
  runs must report the greedy (mean-action) policy, not sampled.
- **F86** — our own reference-gradient sweep says asking for a pointier car
  helps, weakly and monotonically. If H or E independently prefers a
  non-neutral yaw reference, that corroborates the published result and is the
  strongest outcome available. **Do not script the conclusion** — "it
  reinvented the allocator" is a fine result.

**Still true and still unfixed** (carried from Session 12): Season 3 has one
training seed elsewhere in the project, Episode 10's D6 fails
`exploration_is_not_growing`, and Episode 9 needs rewriting around "it never
learned to drive." The limit-seeking-policy gap is now addressed for Episode 14
specifically: the pilot's own peak-lateral-g numbers (H: 0.879 g, E: 0.613 g,
against a measured ~0.95 g ceiling) show the existing progress-reward curriculum
already pushes toward saturation at just 60k steps, without any dedicated
limit-seeking reward — worth re-checking at production scale, not assuming.

### Superseded — Episode 13 planning notes

**Question:** if pushing one wheel harder rotates the car, why not just do that?

**Build:** the classical two-layer controller — a reference model plus PID producing
a desired yaw moment `Mz`, then a QP allocator that decides which wheels pay for it
by minimising tire workload. The plan calls that split "20 years of engineering
consensus", and Episode 14 is the flagship that asks whether a learner agrees.

**The physics it needs already exists and is new this session.** `yaw_moment` carries
the drivetrain term (F72), and `differential_forces` is the passive baseline TV gets
compared against (F76/F77). Before F72 a TV controller would have produced **exactly
zero** yaw response and nothing would have errored.

**Expect 1–4% lap time.** The best published figure is ~9% for an FSAE car on a
skidpad, which is maximally favourable — so **treat anything above 9% as a bug**,
not a result. That is the outside reference (rule 2); our own model is not.

**Read before starting:**

- **F72/F73** — what the yaw moment does and why it changed four conclusions.
- **F76/F77** — the differential is ONE mechanism, and modelling it as two got the
  sign backwards. TV will be tempting to model the same wrong way.
- **F79** — three measurement errors in one afternoon, all from comparing against the
  wrong baseline. **Reproduce the published number before trusting a delta.**
- **Rule 15** — state Episode 13's fidelity rung. Rung 2 reproduces ~5% of a real
  car's understeer, so a TV lap-time gain is a trend claim, not a number a
  manufacturer could use.

**Strong recommendation, and the reason is in F70/F71.** Consider building the
limit-seeking driver *first* (item 4 under Outstanding). Torque vectoring only acts
where tires are saturated; the current policy corners at 5.8–7.4 deg of slip and
uses 94–98% of peak lateral force, but the environment logs no lateral acceleration
and no friction-ellipse utilisation, so there is no way to verify whether a TV result
is measuring anything. Episodes 13–16 all inherit that.

### Superseded — Episode 10 planning notes

Design-conditioned policy — the car's parameters go into the observation. Train
once across randomised designs, then sweep weight distribution continuously and
watch the line deform.

**Ep 10 is what makes RL comparable with Season 2 at all.** Ep 9's policy can
drive one car round one corner; comparing designs that way would test the
policy's luck, not the car. The plan also wants an RL-vs-OC cross-check — two
completely different methods, same trend — which is the strongest external
validation available in this project. Set it up carefully.

**Before quoting any RL lap time against a Season 1-2 one**, note that the RL
environment does not enforce the slip envelope and uses a different entry speed.
As posed they are not comparable; Ep 10 has to fix that explicitly.

### Superseded — Episode 9 planning notes

First RL work. Needs a PPO environment over the existing four-wheel model, plus
**D6 (training health)** — the last unbuilt diagnostic, and the one that gates
every run from here.

Read the note at the bottom of `CLAUDE.md` before starting: this project does NOT
use `simulacrum`, and the `rl-env-*` skills are technique references only. Do not
scaffold a `spec.md`/`reference.py`/`fast.py` package.

**Ep 9's subject is the env fighting back** — reward hacking, envelope violations,
the policy finding something the physics allows and nobody intended. The envelope
instrumentation (CLAUDE.md rule 4) already exists and is what makes that
observable rather than anecdotal.

### Superseded — Episode 8 planning notes

Yaw inertia as an axis independent of balance. **D4 already exists and gates
this** — it was built early, out of order, and this is the episode it feeds.
`schema.LAYOUT_ARCHETYPES` already carries the mid/front-mid/rear variants with
their `i_zz` values, and `tests/test_schema_and_tire.py` asserts their ordering.

Ep 7 froze yaw inertia deliberately and said so in three places; Ep 8 is where
that gets unfrozen. The 2D surface over balance x inertia is the season payoff.

**Expect the rear-drive four-wheel solves to resist convergence** — they have in
both Ep 6 and Ep 7. Continuation warm starts outward from a known-good centre,
`max_iter` 8000, and exclude unconverged times from every claim.

**Work in episode order.** Build only what the next episode needs, ship the
episode with its figures and FINDINGS entries, move on.

---

## Reference vehicle (RV-1, GR86-class)

| Parameter | Value | Confidence |
|---|---|---|
| Curb mass | 1280 kg | High |
| **Simulated mass** (+80 kg driver) | **1360 kg** | High |
| Wheelbase | 2.575 m | High |
| Track front / rear | 1.505 / 1.495 m | **Medium — see below** |
| Front mass fraction | 0.54 (range 0.53–0.56) | High — Toyota press kit states 53:47 |
| CoM height | 0.460 m | High — Toyota states 460 mm, cross-checked at 457 |
| Yaw inertia `I_zz` | 1,950 kg·m² | Medium — correlations disagree; geometry-aware methods preferred |
| Drivetrain | RWD, factory LSD | High |

**Track width is the highest-leverage uncertain number in the project.** It is the moment arm for torque vectoring — yaw moment scales linearly with it, so a 5% error is a 5% error in every Season 4 result. Before publishing any TV magnitude claim, re-run with track width at ±3% and confirm the *conclusion* holds. If a finding flips on that, it was never a finding.

---

## Non-negotiables

Moved to [`CLAUDE.md`](CLAUDE.md) so they load every session rather than only
when someone opens this file. Fourteen rules: pictorial figure before technical
figure; validate against outside ranges; label every number with a provenance
tag; envelope instrumentation is core-loop; seed discipline; absolute values never compare across models; metrics computed
downstream of logs; diagnostics speak plain English. Plus the code invariants —
`schema.py` is the single source of truth, `default_tire()` is offset-free, never
hand-edit the `P*` coefficients, never coast at `κ = 0`, sensitivity-check track
width on every TV claim.

---

## Episode status

| Ep | Title | Season | Needs | Status |
|---|---|---|---|---|
| 1 | Why does a tire make grip at all? | 1 | tire.py ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep01/` |
| 2 | The most important graph in vehicle dynamics | 1 | tire.py ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep02/` |
| 3 | The simplest car that can understeer | 1 | bicycle.py ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep03/` |
| 4 | The fastest way around a corner | 1 | OC ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep04/` |
| 5 | Where the simple model breaks | 1 | double_track.py ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep05/` |
| 6 | Which wheels should drive? | 2 | drivetrain routing ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep06/` |
| 7 | Where you put the weight | 2 | design sweep ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep07/` |
| 8 | Front, mid, or rear engine | 2 | `I_zz` sweep (D4 ✓) | ✅ **DRAFTED** — `episodes/`, `experiments/ep08/` |
| 9 | Teaching a car to drive, and watching it cheat | 3 | PPO + envelope + D6 ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep09/` |
| 10 | One policy, a thousand cars | 3 | conditioned policy ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep10/` |
| 11 | The fastest setup is the one that crashes | 3 | perturbation eval ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep11/` |
| 12 | What a differential actually does | 4 | diff modes ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep12/` |
| 13 | How engineers built a car that steers with its wheels | 4 | classical TV ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep13/` |
| 14 | What the machine found instead | 4 | RL TV variants | ← **NEXT** |
| 15 | Is chassis tuning about to be automated away? | 4 | TV × Season 2 sweeps | — |
| 16 | Did any of this survive real physics? | 4 | Chrono backend | — |

**Seasons 1–2 (Ep 1–8) carry no training risk.** Tire model, double-track, optimal control only. If the RL work proves harder than expected, half the series still ships.

---

## Attribution

`tires/Sedan_Pac02Tire.tir` is from [Project Chrono](https://github.com/projectchrono/chrono), BSD-3-Clause. Header reads "Magic Formula Tire from ADAMS/Car TIR file." 245/40 R18, `FNOMIN` 4850 N.

It is sized for a heavier car than RV-1 (nominal load implies ~1980 kg). Rescale using the Magic Formula's own `[SCALING_COEFFICIENTS]` block — `LFZO`, `LMUY`, `LKY` — and document the factors used. **Do not hand-edit the `P*` coefficients**; that discards the fit's internal consistency.

Vehicle dimensions from Toyota press material and published specifications. See `docs/vehicle-reference-parameters.md` for per-value sourcing and confidence tiers.
