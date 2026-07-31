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

### Session 15 — Episode 14 infrastructure and pilot ✓ DONE

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

### Session 16 — Episode 14 production run, figures, and article ✓ DONE — **EPISODE 14 COMPLETE**

**Production training:** 3 seeds × 2 variants, 5,000,000 steps each, run as 6
parallel OS processes (`--variant={H,E} --seed={0,1,2}`), then
`--aggregate`. Wall-clock: H averaged 3.9 h/seed (13,552–14,501 s), E averaged
1.98 h/seed (7,097–7,167 s) — both close to the pilot's linear extrapolation
(F91).

**Result (F92): neither variant passes D6 cleanly.** H's pass rate is 0/3,
E's is 1/3 — but the two fail differently. H's three seeds stay near the
tire's own ±12° fit (9.4–14.8° worst slip) and its D6 failures are the mild
kind (critic quality, greedy/stochastic disagreement); two of three finish
the corner. E's three split sharply: one seed (seed 2) trains cleanly and
passes every check, the other two run substantially outside the tire's fit
(13.5° and 16.8°, up to 24.7% of the run past the bound) and neither
finishes — **the same tire-model exploit Episode 9 first found (F53/F56)**,
reappearing under the identical envelope penalty (0.5) Episode 10 and this
episode both use.

**The representative-seed rule (F71: median by finish distance, never
best-of-N) mattered concretely here.** E's finish distances are 131 m, 353 m,
393 m; the median (seed 1, 353 m) is one of the exploit seeds, not the one
clean pass (seed 2, 393 m, which any best-of-N rule would have surfaced
instead). Every "representative" E number and figure in the episode is
seed 1's.

**Four production figures built** (pictorial/technical pairs, rule 1):
`01-same-wheels-different-drivers.svg` (hero: C/H/E force arrows at peak
lateral g), `02-yaw-moment-along-the-road.svg` (realized Mz vs distance, all
three, plus per-variant D6 scorecard), `03-did-it-stay-on-the-map.svg` (all
six seeds' friction circles at their own worst-slip instant),
`04-seed-by-seed.svg` (worst slip angle and envelope occupancy, all six
seeds, bars against the ±12° bound). All four generated by
`experiments/ep14/run.py::build_final_figures`, re-runnable from cached
per-seed traces (`full_trace_*.npz`) without retraining.

**One methodological bug caught before publishing, not after:** the
friction-circle figure originally snapshotted each seed's peak-*utilisation*
instant, which need not be the same step as that seed's worst *slip angle* —
and briefly showed a smaller angle than `worst_slip_deg` already reported
elsewhere for the same seed. Fixed by picking `argmax(alpha_max_deg)`
instead, the same step the reported number comes from. See F92.

**Episode written:** `episodes/ep14-what-the-machine-found-instead.md`. The
honest headline: neither RL variant reliably converges to a policy that
agrees with the classical controller at this budget, and the two fail in
informative, different ways — H's mistakes stay close to the physics, E's
mostly reproduce a documented tire-model exploit. Not "RL cannot do torque
vectoring" (one E seed converges cleanly) and not a lap-time race (rule 6).

**533 tests passing**, full suite.

**Open for a future session, not blocking:** more E seeds either side of the
1-clean/2-exploit split to see if it holds at n=5 (rule 5's preference); a
stronger envelope penalty or longer training as a follow-up sweep; Episode 15
(Season 4 sweeps re-run with TV on) is next per the episode-status table.

### Session 17 — Episode 14 re-run, and three defects in how RL results were measured ✓ DONE — **EPISODE 14 COMPLETE**

**Session 16's Episode 14 was published and was wrong.** It reported that
neither RL variant converges. It was measuring the optimiser's stopping point,
not the policy. Corrected, re-run, rewritten.

**The result, after the fix:** all 6 seeds drive the full 393 m, finish, and
stay inside the ±12° tire fit (worst 11.5°). D6 passes 2/3 H and 1/3 E; the
three remaining failures are training-process checks (one weak critic, two
rising-entropy), none a driving or envelope failure.

**The actual episode finding — H vs E, which is the controlled comparison:**

| | H (allocator kept) | E (allocator deleted) | rule 5 |
|---|---|---|---|
| Peak lateral g | 0.915 ± 0.059 | 0.976 ± 0.028 | 1.3× sd — **no difference** |
| Mean tire utilisation | 0.357 ± 0.087 | 0.701 ± 0.130 | 3.1× sd — **reportable** |

Same grip, roughly twice the tire spent getting it. The QP allocator's
minimise-workload objective is visible in the policy that inherits it, and is
the piece end-to-end learning did not rediscover in 5M steps. Both learners run
~4× the classical controller's yaw moment at p90.

**Three defects, all in measurement rather than in RL** (F93, F94, D12):

1. **Last checkpoint, not best** (F93). `train()` returned final weights.
   Every one of the six seeds had already driven a clean lap and been trained
   past it; best checkpoints sat at 15/44/46/61/77/100% of training. Fixed:
   `PPOConfig.eval_every` scores the deployed policy on held-out seeds and
   keeps the best. Default off — Season 3 reproduces bit-for-bit.
2. **D6 was not reproducible** (F94). Its stochastic rollouts drew from
   torch's global unseeded RNG; identical weights gave worst slip 11.27 /
   12.12 / 11.74°, straddling the 12° gate. **This is F88 recurring inside the
   diagnostic** — F88 was fixed in `experiments/ep09/run.py` in the previous
   session and nobody checked the gate for the same pattern.
3. **The envelope check contradicted its own comment** (F94/D12). It took
   `max(deployed, sampled)`; the comment and CLAUDE.md both say deployed is the
   gate. Corrected; sampled now printed alongside every time.

**⚠️ Season 3 (Episodes 9–11) is affected by 1 and 2 and has not been
re-measured.** Same last-checkpoint path, same unreproducible D6, same
sampled-policy envelope verdicts. Its results are likely understated. This is
the single biggest outstanding correctness item in the project.

**Also:** `tests/test_ppo.py` now exists — 12 tests for the module every RL
result comes from, which previously had **none**. That absence is why these
defects survived.

**Next, agreed:** vectorize the environment (blocker for real tracks), then
research real circuit geometry. Measured today: 1,184 steps/s for H, 2,491 for
E, 3,492 baseline — pure Python per-step scalar math. `physics/tire.py`
**already vectorizes** (verified: `fy0`/`fx0`/`peak_fy`/`peak_fx`/`fy_combined`
all batch and match the scalar loop), because it was written against the
`mathkit` namespace. What remains is `double_track.py`, the track locator,
auto-reset masking in `rl_env.py`, and the QP allocator — which is H's 3×
per-step cost and the hardest piece to batch. Gate it on a differential test
against the scalar implementation plus a batch-independence test.

Training budget is ~2× oversized: median seed peaked at ~45% of 5M steps.

### Session 18 — the batched env, real-track groundwork, and three more corrections ✓ DONE

Four things happened, in this order. The first two were the agreed next steps
from Session 17; the last two are corrections that came out of questioning
Episode 14's own numbers.

**1. The environment is vectorized.** `physics/batched_env.py` exists and is
wired into PPO: **112× env throughput, 29× training**, gated on a differential
test against the scalar implementation plus a batch-independence test, as
planned. This was the blocker for real tracks.

**2. Real-circuit source survey is done — see `TRACKS.md`.** Recommendation:
**TUM `racetrack-database`** (LGPL-3.0, 25 circuits including Spa, Monza,
Silverstone, Suzuka; CSV, uniform 5 m sampling, asymmetric widths, **no
curvature/banking/elevation**). Do **not** vendor the CSVs — the licence chain
is LGPL over ODbL-derived OSM data; ship a downloader plus our converter.
**The curvature trap is measured, not guessed, and confirmed twice:** naive
finite-differencing of 5 m centreline points gives a 10.4 m minimum radius at
Spa where La Source is really ~25 m. Use a periodic cubic-spline fit +
arclength reparameterisation + analytic κ, and validate recovered corner radii
against **published** figures (rule 2). Staging is in `TRACKS.md` §4; step 1 is
`SampledTrack` + the round-trip test against our own synthetic tracks.

**Two things scoped but not built** (read-only investigation this session):

- **`SampledTrack` design question — resolved in Session 25.** Built on
  `scipy` (`>=1.11`, now a real dependency, verified via `pip show scipy` not
  guessed), **not** CasADi-safe, by design: RL training (`rl_env.py`,
  `batched_env.py`) is pure NumPy and is what the project is prioritising
  (D13); the optimal-control solver needs an analytic `Track` and was never
  going to get real-circuit geometry through this class regardless. Also:
  **"the track locator" does not exist yet** —
  `rl_env.py` carries `(s, n, xi)` as integrated state in the curvilinear frame
  and never inverts from Cartesian. That inverse is only needed once real
  (x, y) circuits arrive.
- **O9's scripted-policy sanity check belongs in `tests/test_rl_env.py`, not a
  new diagnostic.** It needs no trained model, unlike D6. Note
  `test_reward_is_progress_and_nothing_else` already exists there but is
  **self-referential** (asserts reward sum ≈ the env's own `s`), which is why it
  did not catch F95; the fix is a hand-derived expected return, and the
  `workload_penalty > 0` path is the one that would have made the flat
  direction visible.

**3. F95 — Episode 14's "half the tire" H-vs-E finding is retracted.** The
whole effect lived on the **exit straight**, not in the corner; where the tires
are actually cornering there is no measurable difference (1.8× sd). And on that
straight the reward is `s_dot * dt` and nothing else — summed lateral force
ranges **83 N to 3,199 N at identical reward**. The objective has a flat
direction and each seed settles somewhere different along it. **Underdetermination,
not a training failure.** The generalisable lesson, after four corrections in
two sessions: *an aggregate was reported before it was decomposed.* Rule 7 says
compute metrics downstream from logged arrays — but "downstream" is not
"understood".

**4. F96/F97/F98 — `STEER_NOISE = 0.15` was 23° RMS at the steering wheel, and
Episodes 11 and 13 have now both been re-measured.** F96 found it: the env
commands the **road wheel**, a driver holds the **steering wheel**, and nothing
converted between them across the ~13.5:1 ratio. 0.15 is a continuous
quarter-turn saw, an order of magnitude past the steering-reversal-rate
literature's own bands. Calibrated replacements: **0.01** (attentive, 1.6° at
the wheel) and **0.03** (distracted, 4.7°).

**The two re-measurements went opposite ways, and that is the point:**

| | at the retracted 0.15 | re-measured (0.01 / 0.03) | verdict |
|---|---|---|---|
| **Ep 13** — TV helps an imperfect driver | open diff 31/40 laps vs TV 40/40 | open diff **40/40 at both** levels | **RETRACTED (F97)** |
| **Ep 11** — fastest design is most fragile | 47% front 8.7% in-fit failures, others 0% | 47% front **9.3%**, others 0%, **p = 0.0005** Holm-corrected at both levels | **SURVIVES (F98)** |
| **Ep 14** — envelope guarantee under disturbance | 20–100% completion, 18–27° slip | **6/6 seeds 100%**, worst slip 5.8–11.8° | corrected in F96 |

**Ep 11's survival came with a second finding, though.** Its attentive and
distracted cells are **identical cell-for-cell**, and the `steer`-only condition
fails 0% at every drivable design. **All of Episode 11's fragility signal is the
±20% grip variation**; steering noise contributed nothing measurable and the
article's "two disturbances, each attributable" framing has been corrected.
Also retracted from Ep 11: the **population-level recovery table** (81/33/6/7%),
because at realistic noise the non-fastest designs leave the fit only 1, 4 and 1
times out of 120 — F70's small-n trap again. The *mechanism* (front-limited
pushes wide and self-corrects; rear-limited rotates and diverges) is a property
of the balance, not the disturbance, and stands.

**O10 is closed. O9 is not**, and is now the oldest outstanding correctness item.

### Session 19 — the power review supersedes the track work as next

**Season 2's nulls are suspected artefacts, and Episode 15 is blocked on
resolving that.** See **`POWER-REVIEW.md`** — the full plan. The short form:
F44 (balance: lap time flat) and F49 (layout: lap time flat) were measured only
at the 4.5 kN drive cap, which F43 proved is near the bottom of the power curve
where design effects vanish (no tire above 63% utilisation); the full-lap
metric is ~2/3 power-limited straight (Ep 13's `section_time` exists because of
this and Eps 6–8 lack it); and the brake caps (12–15 kN) appear to be *below*
tire grip (~20 kN), which would make the braking phase design-blind everywhere
— unaudited, Phase 0 checks it. Also unresolved: F43 internally quotes both
0.02 s and 0.08 s as the convergence floor, and F49's whole spread (0.03 s)
sits between them.

Plan: Phase 0 recomputes section metrics from the **existing** traces.npz
(rule 7 — no re-runs) and settles the floor + brake audit; Phase 1 re-measures
Eps 7/8 on a {1×, 1.5×, 2×} power curve × 3 corner radii, convergence-gated;
Phase 2 re-measures Eps 12/13 (TV's worth grows with saturation, and Ep 15
needs that number); Phase 3 conditionally retrains Ep 10/11 on the batched env;
Phase 4 is Episode 15 itself. Decisions D-A–D-D (power model, RV-1P level,
section definition, track set) are in the plan with recommendations, **not yet
ratified — start there.**

`TRACKS.md` staging and O9's scripted-policy test are unchanged but now queue
behind this; O9 is small enough to do alongside Phase 0.

**Also planned this session: `SEASON5.md`** — a six-episode extension (Eps
17–22, "The automated race engineer"): BO tunes setup, RL drives, and the
bridge is Ep 10's conditioning trick scaled to (setup ⊕ car ⊕ track) with the
frozen policy as an amortised evaluator, validated by specialist retrains (the
"amortisation gap" is itself a reported result). Not ratified; its dependency
graph runs through the power review, TRACKS staging, O3/O8/O9, and —
deliberately — Ep 16's Chrono check *before* the season starts.

### Session 20 — Phase 0 executed, and F99: half the premise above was stale

**Phase 0 items 1 and 2 are done, and did not go as scoped.** Recomputing
section times from the *existing* traces.npz turned out to be impossible —
Episodes 6/7 saved `n`/`ξ`/`speed` but never the per-node time (`dt_ds`) a
section split needs, and the naive `(1−n·κ)/speed` substitute is wrong by
~0.07 s exactly where `ξ` is large (24° at turn-in). Fixed properly: `dt_ds`
was already computed by the solver and discarded before saving; added it to
Episodes 6/7's trace output (two-line diff each, verified to reproduce
`Solution.time` to 0.0000% before use), re-ran both, and verified the re-run
**bit-identical** to the already-committed `results.json` and `traces.npz`
before trusting anything downstream.

**That verification step is what surfaced F99, which matters more than the
section metric it was chasing.** F44 (balance) and F49 (layout) — the two
"null" findings this whole review was built to explain — **predate the
F72/F73/F79/F80 yaw-moment correction**, exactly the failure mode F90 already
caught once, for a different number, in the same episode. Both episode
*articles* already carry the corrected numbers; only their FINDINGS.md entries
were never updated to match. Corrected:

- **F44 was never a null.** All ten solves now converge (three used to be
  excluded); the corrected spread is **0.205 s rear-drive, 0.121 s
  front-drive** across 40–65% front — a real, ~1.7% effect, not
  "indistinguishable." The article already says so ("sensitivity has
  doubled"); FINDINGS did not, until now.
- **F49 got tighter, not reversed.** The corrected ranking removes the one
  candidate outlier (front-engine-FWD: last place → second) and the span
  shrinks to a uniform **0.056 s**. Still a null — a more robust one.

**This changes Phase 1's shape.** Balance is no longer "is there an effect
hiding below the instrument's floor" — there is one, confirmed, at 1× power.
The question becomes the F43 shape: does an already-real effect grow with
power. Layout keeps the original null-audit framing, now against a tighter
baseline. `POWER-REVIEW.md` §1, §2, D-C, and the Phase 0/1 sections are all
updated to reflect this — D-C in particular, since the corrected traces let a
real check run: on `long_exit`, the balance-induced speed gap between the
40%/65% cars **never re-converges within the 392.8 m track** (3.8% at corner
exit, still 0.9% apart at the finish), so the original section-metric proposal
(end where speed traces re-converge) doesn't fire on this track and had to be
revised to report the speed-gap curve directly instead of assuming a
convergence point exists.

**Left open, deliberately not fixed in the same pass:** `episodes/ep07-*.md`'s
own numbers (0.21 s / 0.12 s) sit under a section still headed "it barely
changes how fast it is" — the prose was never re-read against the table it
sits above, once the table was corrected. An editorial call, queued as Phase 0
item 4, not folded into F99 itself. Episode 8's archetype sweep has **no
per-node trace saved at all** (only the scalar `time_s`); queued for whenever
Ep 8 is re-measured in Phase 1.

**571 tests pass.** Every number in F99 and the POWER-REVIEW.md updates
verified mechanically against the regenerated JSON before being written down —
the same discipline Ep11's correction needed after the fact, applied from the
start this time.

**Next:** Phase 0 items 3 (brake-cap audit) and 4 (Ep 7 article wording), then
Phase 1's power curve for Eps 6–8.

### Session 21 — Phase 0 finished (items 3–4), D-A resolved and built, Phase 1
run, and F100

**Phase 0 closed out.** The brake-cap hypothesis was half wrong: the OC
solver's 15 kN cap never binds (87.6% peak usage, zero nodes at cap —
tire-limited, as it should be); the closed-loop driver's 12 kN cap does bind,
identically regardless of design, confirmed rather than assumed. Episode 7's
own wording ("barely changes how fast it is") was inconsistent with its own
corrected numbers (0.21 s / 0.12 s, doubled) — reworded to distinguish a real
1.7%-of-lap quantitative effect from the understeer swing's qualitative one.

**D-A didn't get ratified as "adopt the power-limited model" — it got
resolved as "measure both, neither replaces the other."** Recommending the
power-limited model as a straight swap turned out to be a bigger commitment
than it looked: it drops below today's flat cap at 38.7 m/s, 30% of Episode
6's own exit straight, at the power every published episode already used.
Adopting it as *the* model would have silently moved Episodes 1–14's numbers,
including the ones F99 just corrected. The user's own reaction to seeing the
three options ("I like all of those framings") pointed at the right answer
directly: track width already gets this treatment (rule 9, ±3%, re-run and
see if the conclusion survives); the drive model gets it now too.

Implemented both D-A (power-limited drive, additive/opt-in on
`Limits.drive_power`, verified bit-identical to every existing solve when
unset) and D-D (hairpin R=15m, fast_sweep R=90m, radius the only thing that
varies from `long_exit`). New `experiments/power_review/phase1_sweep.py`
runs the {1×,1.5×,2×} × {3 tracks} × {2 drive models} grid for both axes.

**The sweep caught three of its own defects before anything got written up,
each by refusing to trust a surprising number:**
1. The pilot's numbers didn't match F99's already-verified baseline — a
   leftover `entry_speed=20.0` from an earlier scratch check instead of the
   established 32.0 m/s. Fixed by testing 32.0 against all three tracks
   directly rather than guessing a per-track value.
2. `power_limited` gave bit-identical results at 1.5x and 2x power on every
   track — `drive_max` was never actually raised for that mode (a stale
   comment claimed it matched a "15 kN default" that belongs to `brake_max`,
   not `drive_max`), so the leftover 4.5 kN flat cap silently governed at
   every power level except 1x. Fixed; re-ran the affected half only (a new
   `--models` merge flag), verified the fix directly before trusting the
   66-minute run it was replacing.
3. One cell in the corrected full grid reported `Solve_Succeeded` at a value
   1.1 s worse than its neighbours and worse than the *same design at lower
   power* — a genuine local-optimum trap passing IPOPT's own convergence
   test. Caught because it broke the spread's monotonicity, not because
   anything reported failure. A systematic scan of the other 268 cells found
   nothing else; one more cell (different track/power, same fraction and
   drivetrain — noted, not investigated further) needed more iterations and
   landed within 0.001 s of its own unconverged value.

**The result, F100: both axes grow monotonically with power, on every track,
under both drive models.** Balance took the outcome F99 predicted (×2.3–8.1
growth 1×→2×, F43-shaped). Layout's null did **not** survive — same order of
magnitude (×2.5–4.9) — the second correction to F49 in one day, for a
different reason than the first (F99 was drift; this is scope: a corrected
1× number can still be an incomplete measurement). Episode 15 now has the one
thing this whole review exists to give it: a design-sensitivity baseline, on
both axes, that measurably varies with power.

**Also fixed, unrelated to the physics: FINDINGS.md's own structure.** F99
had landed after `# Decisions` instead of at the end of `# Findings` — an
editing mistake from the session that wrote it. Moved verbatim; verified as a
pure relocation (108 insertions / 107 deletions, word count +7).

**Next:** Phase 2 (Episodes 12/13 at the power curve, both drive models — TV's
worth as a function of power, which Episode 15 also needs) and Phase 3
(conditional RL retrain). `SEASON5.md` is still waiting on all of this.

### Session 22 — Phase 2 done: TV's worth goes from +4.6% to +125.5% cornering limit across the power curve

**F101.** Same session, same discipline, continuing straight from Phase 1.
Gave `physics/driver.py` D-A support first (`Driver.drive_max`/`brake_max`/
`drive_power`, additive and opt-in, mirroring `optimal_control.Limits`;
verified bit-identical to Episode 13's committed best-lap result before
trusting it) — needed because `ep13.lap()`'s own `SpeedProfile` reads the
module-level constants directly, not any per-instance override.

**Ep 12 turned out not to have a power axis at all.** Checked before
building anything: it's a steady-state, fixed-corner mechanism study that
sweeps *demanded* force directly (0–6,500 N), no engine cap, no lap. Its
existing sweep already covers 1×/most-of-1.5× but not 2×; extended it
directly and confirmed F76/F77's mechanism holds unchanged through
12,000 N, no re-publish needed. Original plan had assumed Ep 12 needed the
same {1×,1.5×,2×} treatment as Ep 13 without checking.

**Ep 13's result: TV's cornering-limit gain over the open differential goes
+4.6% (1×, matching F82) → +48.3% (1.5×) → +125.5% (2×), monotonic under
both drive models.** Not because TV improves with power — because
everything else collapses and TV doesn't: the open differential's own
limit nearly halves (−54%), the LSD becomes completely undrivable by 2×
(checked at 0.002 resolution — no valid `grip_use` anywhere from stalled to
spun), the single-axis TV-differential degrades substantially too, and only
the full four-wheel allocator holds its limit flat across the whole range.

**Two more real defects, same pattern as Phase 1 — caught by not accepting
a surprising number:**
1. A plan/clip mismatch produced a textbook-shaped false result: feeding the
   power-limited clip's deliberately non-binding drive_max (100,000 N) into
   the *plan's* acceleration target too (7.5 g, no physical meaning) made
   the tracking driver's error term saturate chasing an unreachable speed,
   and the open differential spun at 49.9° — reading exactly like "more
   power breaks an open diff" before it was checked. Confirmed by
   construction: the same clip with a sane plan drives the identical lap at
   3.1°. Fixed by separating what the plan assumes from what the clip
   enforces.
2. `GU_LO=0.70` was silently reporting "no valid lap" for cars whose real
   limit sat below it once defect 1 was fixed — checked directly (2×/flat
   open diff: off track at 0.70 and 0.50, clean at 0.30) rather than
   accepted. Lowered to 0.05, and the new floor was itself verified valid
   before trusting anything built on it.

**Closes Phase 2.** Episode 15 has both prerequisites now: a
design-sensitivity baseline that varies with power (F100) and TV's own
worth as a function of the same curve, with a mechanistic account of why
(F101). 583 tests pass throughout; every number in F101 checked against the
regenerated JSON before being written down.

**Next:** Phase 3 (conditional RL retrain, Episodes 9–11) — lower priority
per the original plan (needs the power decision fixed and Episode 15's
design to actually need it first) — then Episode 15 itself, now unblocked
on both of its prerequisites. `SEASON5.md` still waits behind all of Season
4's own episodes landing.

### Session 23 — Episode 15's experiment: F102, TV flattens layout up to 47×, and a genuine exception

**Went straight to Episode 15 instead of Phase 3**, since it was the actual
payoff both prior phases existed for and Phase 3 was explicitly the lower
priority. New `experiments/ep15/run.py`: Episode 7's balance sweep and
Episode 8's five layout archetypes, TV off (open diff) vs TV on (`tv4`), at
1× and 2× power, D11's cornering-limit protocol — reusing Phase 2's driver
infrastructure directly.

**Result: layout sensitivity is nearly erased by TV, and increasingly so
with power** — 16× flatter at 1×, **47× flatter at 2×** (spread 0.271→0.017
at 1×, 0.713→0.015 at 2×). The series plan's payoff line stands: "the thing
that made a 911 a 911" is something this controller has already made
irrelevant to whether the car holds a line, on this model. **Balance
flattens for the RWD car (10.3× at 2×) and does not for the FWD one** — and
that split is a real, checked mechanism, not a gap: the FWD archetype's
drive force fully saturates whichever power cap it's given, yet its
cornering limit sits at a bit-identical 1.100 regardless — its limit is a
front-tire slip-angle ceiling (11.9°, one tenth of a degree from the ±12°
envelope), not a traction-management one, so there is nothing for an
allocator to fix.

**The one pattern that needed a direct check** — `front_fwd`'s
power-invariant limit — is the same "identical across power" shape that was
a real bug twice already this session (Phase 1's `drive_max` bug, Phase 2's
plan/clip bug). Checked rather than assumed: confirmed the drive-force clip
genuinely reaches and saturates the raised cap at both power levels; the
limit doesn't move because something else binds first. Different mechanism,
same discipline.

**A recurring, unexplained wall-clock oddity, noted rather than chased
further:** 4 of 60 configurations across the quick and full runs took
~900–1000s against every other config's 7–8s. Direct re-tests of the exact
same parameters ran in under a second each time, and the reported results
are physically consistent with their neighbours, so this reads as a
transient system-level slowdown rather than a code defect — but it is
recorded here in case the pattern recurs on a future run.

**Figures and article done in the same session.** New `viz/chassis_figures.py`
— a pictorial (five archetypes, one corner, one shared aggression, TV off vs
on, reusing Ep11's `track_backdrop` pattern) and a technical spread card. The
pictorial needed data the main sweep didn't produce — every point there was
measured at its own limit, which can't show one car diverging from another
on one road — so a small shared-`grip_use` comparison (0.65, 2× power) was
added and computed standalone rather than re-running the 70-minute sweep:
4 of 5 archetypes leave the road with an open differential, 0 of 5 do with
the allocator, at the identical demand. `episodes/ep15-*.md` is written,
both figures embedded, every number checked against the JSON. **Episode 15
is DRAFTED — all four pieces exist.**

**Season 4 (Episodes 12–15) is now complete.** Episode 16 (the Chrono
cross-check) is the only piece of the original 16-episode plan left.

### Session 24 — Episode 16 deprioritized; RL multi-track training is next

**User decision (D13).** Not pursuing Chrono for now — explicitly a
publication-grade validation step the user doesn't currently need, and
they're more interested in the RL multi-track direction. Revisit-able, not
closed. This means every finding in the project stays a rung-2 claim,
unverified against an independent simulator, for as long as this holds —
recorded as an accepted risk in D13, not quietly dropped.

**What replaces it: `TRACKS.md`'s own staging order**, already written,
now prioritized ahead of Phase 3 of the power review:

1. `SampledTrack` + the round-trip curvature test, against `long_exit` where
   the answer is already known (TRACKS.md §2 — clean data: 1.16e-05 error;
   the naive finite-difference trap is 390× the signal on noisy data, so
   this has to be a periodic spline fit with analytic κ, not `np.gradient`).
2. Closed-loop support (`s` wrapping, lap counting, `half_width(s)`).
3. One real circuit imported (TUM `racetrack-database`, TRACKS.md's own
   recommendation) and validated against **published** corner radii — rule 2,
   not our own fit certifying itself.
4. Batched-env support for the step count a real circuit implies (~10,000
   steps/lap against today's ~1,000 on `long_exit` — `max_steps` and the
   episode budget both need rederiving).
5. Only then retrain.

**Next action (superseded by Session 25):** start on step 1, `SampledTrack`.

### Session 25 — `SampledTrack` (TRACKS.md staging step 1) done

Step 1 of the staging order above is complete: `SampledTrack` in
`physics/track.py`, validated by `tests/test_sampled_track.py` (6 tests,
round-tripped against `long_exit()` where the curvature answer is known
exactly), full suite green (599 passed). `scipy>=1.11` added to
`requirements.txt` (checked via `pip show scipy` that it was not already an
indirect dependency, per rule 3 — don't claim a provenance you haven't
verified).

The round-trip test did its job and caught two real bugs before any external
circuit data was touched, exactly TRACKS.md §2's stated reason for writing it
first:

1. **Periodic vs. open fit.** The constructor hardcoded `per=True`
   (periodic spline — correct for a real circuit, which is a closed loop).
   Validated against `long_exit()`, which is deliberately open (entry
   straight → corner → exit straight, start far from end), it silently fit a
   loop roughly double the intended length (`length` came out ~785 m against
   a known 393 m) — forcing periodicity on an open curve does not error, it
   just closes a gap that was never there. Fixed with a `closed: bool = True`
   parameter threaded through both the `splprep(per=...)` call and the
   chord-length arclength sum; real circuits keep the default, `long_exit`
   and other open synthetic tracks pass `closed=False`.
2. **Untuned smoothing constant.** An arbitrary `smoothing=0.05` recovered
   curvature *worse* than the naive finite-difference trap it exists to beat
   (err 42 vs. the trap's own 8.7, against a 0.025 corner signal) — smoothing
   has to scale with point count, not be a fixed guess. scipy's own
   unweighted-data convention, `s ~= m` (the point count), matched TRACKS.md's
   own measured "tuned smoothing spline" row almost exactly (err 0.015 vs.
   0.013 there). Recorded in the class docstring so real-data import starts
   from `s = len(x)`, not another guess.

TRACKS.md §4 updated to mark step 1 done with this detail. Both bugs were
caught by running the test and reading the failure, not assumed away or
argued around — same discipline as the rest of this session.

**Next action (done later this session):** TRACKS.md staging step 2 —
closed-loop support (`s` wrapping, lap counting, `half_width(s)`); touches
`rl_env.py`'s termination condition and the driver's track preview.

### Session 25 continued — TRACKS.md staging step 2 done

Full detail in `TRACKS.md` §4 step 2. Summary: `Track`/`SampledTrack` gained
`half_width_at(s)` (replacing the plain `.half_width` scalar attribute
everywhere it was consumed as a boundary check — `rl_env.py`,
`batched_env.py`, `driver.py`), `EnvConfig.n_laps` and `drive_lap`'s
`n_laps` argument (both default 1, every existing call reproduced exactly),
and `SampledTrack` can now take a per-point `width` array for real varying
half-width. Full suite: 606 passed (599 + 7 new tests), zero regressions.

Two more real bugs, caught by tests rather than assumed away:

1. The curvature-ahead preview in both `rl_env.py` and `batched_env.py`
   clamped to `track.length`, which is correct for an open track but
   flattens a closed track's lookahead to a repeated point right at the
   spot a driver most needs to see the next corner. Fixed by skipping the
   clamp when `track.closed`.
2. `driver.drive_lap`'s new `n_laps` support first used a "big backward
   jump in `s` = one lap" wrap counter, and a synthetic closed-circle test
   caught it misreading the one genuinely ambiguous point on any loop: the
   start line, where `s=0` and `s=length` are the same physical point, so
   the very first position fix can land on either — the naive counter read
   that as an instant final-lap finish (`lap_time=0.04s`). Fixed with a
   running sum of each step's shortest signed circular delta from the
   previous `s`, which resolves the ambiguity to ~0 distance travelled
   however the tie breaks.

**Deliberately not done** (recorded so it isn't rediscovered as a surprise
later): `SpeedProfile`'s backward/forward passes still plan a single lap
(`s` in `[0, length]`) — a real circuit's corner-braking continuity across
the seam needs its own pass, deferred to whenever a real circuit's speed
plan is actually driven. `drive_lap` also still assumes the car starts at
the world origin with heading 0, true of every synthetic `Track` here by
construction but not automatic for a real circuit's raw coordinates — a
real circuit will need its start pose derived from the track itself.

**Next action (done later this session, user approved the download first —
step 3 fetches external files):** TRACKS.md staging step 3 — import one
real circuit (TUM `racetrack-database`) and validate against published
figures (rule 2).

### Session 25 continued — TRACKS.md staging step 3 done

Full detail in `TRACKS.md` §4 step 3. Summary: `physics/tracks_data.py`
(`download_track_csv` + `load_real_track`) fetches Spa-Francorchamps from
TUM's `racetrack-database` (LGPL-3.0/OpenStreetMap) on first use and caches
it in `physics/tracks_cache/`, which is git-ignored — the CSV is never
vendored, per TRACKS.md §3's own licensing recommendation. 5 new tests in
`tests/test_tracks_data.py`, skipped (not failed) when TUM's GitHub is
unreachable.

**Validated against published figures, not our own fit:** recovered
`length` 6999.5 m against the Grand Prix layout's published 7.004 km —
0.064% error. Could not find an independently-published per-corner radius
for La Source (several searches, general descriptions only) — this doc's
own prior "~25 m" has no citation either, so it was **not** reused as if it
were external; the recovered 11.4 m minimum radius is reported measured-only,
checked for physical plausibility rather than against a hard number. Stated
as a real gap rather than smoothed over with an unsourced figure.

**A real bug, found by measuring rather than reusing step 1's own
convention:** exact interpolation (`smoothing=0.0`) looked right going in —
TUM's centreline is a processed surface, not raw noisy GPS — but measured
directly it fit a 5.8 m minimum radius, tighter than any real corner on the
circuit, because 5 m point spacing still carries enough residual
irregularity for exact interpolation to read as a spurious sharp corner. A
sweep found `length` within 0.05-0.25% of published throughout and minimum
radius stabilising to a plausible 9-11.5 m for `10 <= smoothing <= 300`.
Step 1's own `s ~= m` convention (1401 for Spa's point count) turned out to
be **too much** here — different point spacing and noise character than the
synthetic data it was measured on, worse length match, washed-out corner.
`DEFAULT_SMOOTHING = 20.0` sits inside the plausible plateau. Same lesson
as step 1, generalised correctly this time: measure smoothing on the data
in front of you, don't carry a number over from different data.

**Next action (done later this session — turned out to be an
investigation, not a code change):** TRACKS.md staging step 4.

### Session 25 continued — TRACKS.md staging step 4: investigated, no defect

Checked `batched_env.py`'s buffers, `TrackLocator`'s window search,
`EnvConfig.max_steps`/`drive_lap`'s `max_steps`, and PPO's reward/log
accumulation for anything hardcoded to a ~1,000-2,000-step episode.
**Nothing is** — `max_steps` is already a config value, no buffer is sized
off it, `TrackLocator`'s `window` is in metres not track-fraction, reward
has no episode-length normalisation. Full detail and the four things that
DO need attention in `TRACKS.md` §4 step 4:

- `ppo.py`'s `rollout_steps=512` is smaller than the OLD `max_steps=2000`
  cap; against a ~10,000-step Spa lap almost no episode finishes inside a
  rollout window, so `return_mean`/`off_track_rate` (what D6/rule 4 read)
  would go `nan` for most of training.
- `total_steps` (300k/1.2M/5M) buys an order of magnitude fewer completed
  laps at unchanged budget, on a track 5-18x longer.
- `gamma=0.995` (4 s horizon) was already short against the old 26 s lap;
  cannot connect corner-exit speed to payoff across Spa's 10+ second
  straights at all.
- No experiment script routes through `BatchedDrivingEnv` yet — `ep09`-`11`
  all build single-instance `DrivingEnv`s. The batched env is tested and
  exists specifically for this throughput problem, but nothing wires it in.

None of these are guessable without an actual training run to calibrate
against (rule 9) — they're step 5's work, not a separable step 4, so
recorded here rather than invented as numbers now.

**Next action (done later this session, user chose "scope it out first,
don't run yet"):** step 5 scoping.

### Session 25 continued — TRACKS.md staging step 5 scoped, not run

Full detail in `TRACKS.md` §4 step 5. User explicitly chose to scope this
before running anything (step 5 is Episode 19's own subject). Measured
rather than estimated:

- `BatchedDrivingEnv` already works on Spa — built and stepped one
  directly, no crash, no NaN. The gap is that no experiment script passes
  `make_batched_env` to `ppo.train()` yet.
- **First pass at the batched-vs-unbatched comparison was wrong and got
  caught before it went in the doc**: dividing batched aggregate
  throughput by `n_envs` and comparing to single-instance made batching
  look ~10x SLOWER. The real baseline — `n_envs=8` run sequentially, which
  is today's actual unbatched path — measures at 2,648 instance-steps/s,
  statistically identical to one instance alone (2,699), because
  sequential single-core work can't parallelise regardless of how many
  "envs" are configured. Against that corrected baseline, batched
  throughput on Spa specifically: 29.1x at `n_envs=256` (matches this
  doc's prior "29x" estimate), 47.1x at `n_envs=1024`.
- Concretely: matching Episode 10's experience budget (5M steps at
  ~1,300-step laps ≈ 3,846 completed laps) on ~10,000-step Spa laps needs
  ~38.5M steps. Env-stepping alone: **~4.0 hours unbatched** (today's
  path, before ≥3 seeds × 2-3 tracks multiply it further — this is where
  "multi-overnight" comes from) vs **~5 minutes batched** at
  `n_envs=1024`. Wiring the batched path in is not an optimisation, it's
  the difference between an afternoon and a week.
- `gamma=0.995`, `rollout_steps=512`, and `total_steps` all need
  retuning — proposed starting points recorded in TRACKS.md (gamma→0.999,
  rollout_steps toward a lap-length multiple or a partial-episode-stats
  fix instead, total_steps~38.5M), explicitly flagged as guesses a pilot
  run needs to confirm, not final answers (rule 9).

**Next action (done later this session, user said "Run the pilot"):** the
pilot itself.

### Session 25 continued — TRACKS.md staging step 5: pilot run

Full detail and the honest "what it did and did not answer" breakdown in
`TRACKS.md` §4 step 5. `experiments/tracks_pilot/spa_ppo_pilot.py`: PPO on
Spa through `BatchedDrivingEnv`, `n_envs=256`, `rollout_steps=1024`,
`total_steps=5,000,000`, `gamma=0.999`. Ran clean, 106.4 s wall-clock,
~19,600 completed episodes. Artefacts in `experiments/tracks_pilot/out/`.

**Answered:** batched training on a real circuit works end to end (no
crash, no NaN). Measured full-loop throughput (env-stepping AND the PPO
gradient update, not measured before): **46,999 steps/s** — revises the
production estimate from ~5 minutes (env-stepping only) to **~14 minutes**
for 38.5M steps, still a dramatic win over the ~4-hour unbatched path.
`gamma=0.999` shows no instability (`approx_kl` small throughout,
`explained_variance` climbing steadily 0→0.34).

**Did NOT answer, stated honestly rather than stretched:** the
rollout_steps question isn't testable yet — `off_track_rate` stayed
0.94-1.00 across all 19 updates, episodes averaging ~200 steps (crashing
within the first corner or two), nowhere near lap-length. The pilot never
reached the training stage where "does a near-full lap fit in one rollout
window" applies. Nor does 5M steps say anything about whether ~38.5M is
the right production budget for a 20-corner circuit versus Episode 9's
one corner (which alone took hundreds of thousands to over a million
steps to learn) — that heuristic was flagged as unvalidated when written
and stays unvalidated.

**Next action (done later this session, user said "Run the pilot" then
"WHY DO YOU STOP KEEPING RUNNING IT" — kept going without stopping to ask
again):** speedup check, then the full long run.

### Session 25 continued — speedup levers checked, then the long run

**Speedup levers, measured not guessed** (full detail TRACKS.md §4 step 5
item 6): `n_envs=1024` is a free ~11% full-loop win over 256, adopted.
Larger `rollout_steps` (4,096) does not help throughput, if anything
slightly hurts. Cutting `FIXED_POINT_ITERS` below 6 was investigated and
rejected — the reference implementation shares the identical 6-iteration
cap and does not converge to its own 1e-9 tolerance within 6 iterations
under realistic aggressive-driving states either (measured directly), so
cutting further would silently diverge from the reference exactly at the
grip-limit states that matter most. MPS (Apple GPU) measured ~2x slower
than CPU for this small a network — not worth pursuing.

**The long run** — `experiments/tracks_pilot/spa_ppo_long.py`, full scoped
budget (`n_envs=1024`, `rollout_steps=1024`, `total_steps=38,500,000`,
`gamma=0.999`, Spa). 632.1 s wall-clock (10.5 min, 60,910 steps/s — the
number to use going forward), 93,249 completed episodes. Artefacts in
`experiments/tracks_pilot/out/long_*`.

**A real training curve this time, not another flat smoke test:**
`distance_mean` grew from ~200 m to ~365 m over the run, `off_track_rate`
fell from ~1.00 to a noisy 0.22-0.54 band in the back third,
`explained_variance` climbed to a healthy 0.6-0.83, `approx_kl` stayed
small throughout (no instability at `gamma=0.999`). The policy is
measurably learning.

**And the number that matters: 365 m final `distance_mean` against Spa's
~7,000 m is ~5% of one lap**, after the FULL "same experience budget as
Episode 10, scaled by lap-length ratio" allowance (38.5M steps). That
heuristic was flagged unvalidated when written (step 4) and this run is
the validation — it is a real underestimate for a 20-corner circuit. Not
a case for "just run 38.5M again": either substantially more steps, or a
curriculum change (Episode 9's "start below the corner speed" trick made
an unlearnable single-corner task learnable — a full circuit may need its
own version, e.g. per-section curriculum, rather than raw steps from a
standing start every episode).

**Next action (done later this session, user asked for a feasible
training schedule):** the schedule below.

### Session 25 continued — training schedule designed (TRACKS.md §4 item 8)

Full table and pre-registered contingencies in `TRACKS.md`. The
diagnosis: the long run was a curriculum problem, not (only) a budget
problem — every episode started in Spa's first 300 m, so 38.5M steps
went into the opening sector and the policy never saw ~95% of the
circuit. The fix is already supported in code, verified not assumed:
`BatchedDrivingEnv._reset_mask` draws `s0` per instance, so
`start_jitter_m = track.length` gives uniform starts around the whole
lap with zero new environment code, and the local (55 m) curvature
preview means skill learned anywhere transfers everywhere.

Four stages: (0) warm-start support in `ppo.train()` (D-A pattern,
additive, bit-identical when unset) + jitter smoke test; (1) ~40M steps
uniform-start survival, gate on per-section survival uniformity; (2)
~100–150M steps warm-started, `eval_every` on with from-the-line eval,
gate on the DEPLOYED policy completing a full lap (D12/F93); (3)
consolidate + measure, ≥6 eval seeds, D6 gates. ~1 h/seed at the
measured 60,910 steps/s; ≥3 seeds (rule 5) ≈ an afternoon.
Pre-registered stall contingencies in order: gamma 0.9995, entry-speed
curriculum, more steps — one at a time, never blended.

**Next action (done later this session, user said "DO all the
training"):** Stage 0, then Stage 1 (twice — see below).

### Session 25 continued — Stage 0 done, Stage 1 caught its own F93 recurrence

**Stage 0**: `ppo.train()` gained `init_state_dict` (D-A pattern, additive,
`None` default reproduces every existing call bit-for-bit). 2 new tests;
full suite 613 passed. Also verified directly: `BatchedDrivingEnv`'s
existing `start_jitter_m` mechanism already gives sane, varied starts
across the whole lap with zero new environment code.

**Stage 1, run once without checkpoint selection first — and it recurred
F93.** 40M steps, uniform starts, no `eval_every`. Trained cleanly by
every surface signal (no crash, no NaN) but its own history showed
`return_mean` peaking at update 25 (834) then genuinely declining over
the next 12 updates to 317-360, `off_track_rate` worsening from 0.92 back
to 0.96-1.00 alongside it. Exactly the pattern F93 was written about
(Episode 14: only the final, worse weights get saved) — `eval_every` had
been scoped for stage 2 only, and stage 1 made the identical mistake
despite the selection tooling already existing and already tested.
**Caught by reading the training curve, not by any run-reported
failure.** Fixed and re-run with `eval_every=2`, `eval_episodes=8`, and an
eval env matching TRAINING's own jittered distribution (not stage 2's
from-the-line task — selecting against the wrong distribution would
answer the wrong question for this stage). First run's artefacts kept as
`stage1_noselect_*`, evidence rather than deleted.

**The corrected run: selection worked, and the underlying result is real
but modest.** 1,149.2 s wall-clock, 38 updates. Same rise-then-decline
shape recurred (peak `eval_return` 583.34 at update 32, decline after) —
checked why rather than treating it as a new mystery: `log_std` barely
moves the whole run (`entropy_anneal=False`, this project's own
documented default — exploration noise never tightens). Selection
correctly held onto update 32's weights rather than the declined final
ones. Per-section survival of the SELECTED checkpoint: mean 536.6 m
(range 50.5-1,259.9 m), every section still eventually off-track. Real,
if modest, improvement over the unjittered long run's 365 m (~47% more)
— but honestly, nowhere near the gate as originally written, which
turned out to compare two different populations (easy near-start
training-time episodes vs. hard fixed points spanning the whole lap) —
a mismatch this session's own gate design didn't anticipate.

**Track visualized** for the user during this run:
`experiments/tracks_pilot/out/spa_track.svg` — Spa's true shape with
recovered varying half-width (3.9-8.2 m), reusing `viz/lib.py`'s existing
primitives rather than a new tool.

**Next action (done later this session, user reviewed the reward
structure and said "do both", then "Sweep them", then "keep going" with
warm-started reuse):** the rest of the reward-tuning arc below.

### Session 25 continued — reward-tuning arc: stall exploit, sweep, warm-started confirmation

Full detail in `TRACKS.md` §4 items 11-12. Summary of the whole arc,
since it is easy to lose the thread across five runs:

1. **`off_track_penalty=500` alone taught the policy to give up.** Checked
   directly: it braked steadily from 15 m/s to a dead stop every episode
   (`stalled=True`, never `off_track`) — stalling was free, so once
   crashing got expensive enough, coasting to a stop became strictly
   safer than driving. Per-section distance collapsed to 73.4 m.
2. **Fixed with two new `EnvConfig` fields** (`physics/rl_env.py`,
   `physics/batched_env.py`, D-A pattern, differential-tested,
   10 new tests): `stall_penalty` (closes the loophole directly) and
   `progress_scale` (grows the reward for covering ground, by explicit
   user decision after reviewing the tradeoff between the two).
3. **`progress_scale=3.0` swung too far the other way** — `return_mean`
   peaked at 2985 specifically BY crashing more often
   (`off_track_rate` 0.88-1.00 during the climb); per-section off-track
   rate came back 100%, same as the very first run.
4. **Swept `progress_scale` instead of guessing a fourth combination**
   (`experiments/tracks_pilot/reward_sweep.py`, 5 points x 15M steps):
   2.5 and 3.0 already trending crash-heavy that early; 2.0 surprisingly
   the MOST stall-prone (not a monotonic relationship); 1.0 and 1.5 the
   only two still a genuine mix of both failure modes.
5. **`progress_scale=1.5` run via two-phase warm start** — phase A
   reproduced the sweep's own 15M-step run exactly (recovering the
   checkpoint the sweep script never saved, a real gap in it), phase B
   warm-started the remaining 25M steps to reach the full 40M budget.
   789.2 s total wall-clock. Per-section result: **653.5 m mean distance,
   the best yet — but off_track_rate=0.96**, plus one genuinely positive
   detail: the one probe close enough to the lap end to actually reach it
   (started 292 m out) did so cleanly, no crash, no stall.

**The headline, stated plainly**: across every configuration that
actually drives, per-section off-track rate has stayed in a 0.94-1.00
band. Distance has steadily improved (536.6 -> 595.2 -> 653.5 m) but
"stay on track" — the user's own stated #1 priority — has not moved
under any variant tried. Every run shows a late, sudden return climb
that has not visibly plateaued by 40M steps, consistent with training
still mid-exploration rather than converged — more budget might resolve
it on its own, or the reward shape might have a floor coefficients alone
cannot get under.

**Sweep methodology for next time**, the user's own proposal, recorded
before it is lost: share one past-the-basics baseline checkpoint across
future sweep branches (warm-started) rather than paying the "learn to
survive" cost per point; use a higher starting `lr` for the abbreviated
branch; and state explicitly that this changes the comparison from
"what would each reward produce from scratch" to "how does each reward
reshape this one policy" — cheaper, but can bias every branch toward
whichever regime the baseline already committed to.

**Next action (done later this session, user asked for a step-back
review):** the review below.

### Session 25 continued — step-back review: the critic has been dead since the reward change

Full analysis and revised plan in `TRACKS.md` §4 item 13. The three
findings, each verified against the runs' own logged histories:

1. **`explained_variance` collapsed from 0.33-0.72 (gamma=0.999 runs) to
   ~0.00 in every run since the gamma/penalty change** — the critic
   predicts nothing, so with `rollout_steps` far shorter than episodes
   (GAE bootstraps almost everything through V) the advantage signal has
   been mostly noise for three consecutive 40M-step runs. `D6`'s own
   `the_critic_predicts_returns` check (gate: EV > 0.3) describes exactly
   this failure — **and D6 was never run on any tracks pilot**, despite
   being the project's standing training-health diagnostic. Also a
   process failure worth owning: gamma and penalty scale were changed
   together, violating the schedule's own pre-registered "one at a time,
   never blended" rule, so the two candidate causes (40 s horizon vs a
   3-5 s observation preview; ±500 value-target spikes vs the value
   head's 0.5 grad-norm clip, F51) are currently confounded.
2. **The "off-track rate stuck at 0.94-1.00" headline had a censoring
   artifact** — with finish requiring a multi-km drive to `s=length` and
   a 300 s timeout, eventual-crash is near-guaranteed by construction
   until the policy can survive lap-scale distances. The honest safety
   metric is hazard (mean distance before crash), which did improve
   536.6 → 595.2 → 653.5 m. Corrected in the record, not just noted.
3. **No existence proof the task is completable**: the classical driver
   has never lapped Spa (blocked only by the small start-pose gap flagged
   at step 2). A classical baseline lap would prove completability,
   calibrate reward scales against a competent lap's actual earnings, and
   be an external check the RL loop wasn't written around (rule 11).

**Revised plan (TRACKS.md item 13, in order)**: (A) D6 becomes the
standing gate for every training run; (B) classical baseline on Spa
first; (C) single-variable gamma-revert run to un-confound the critic
collapse; (D) contingent single changes only (dense edge shaping /
entropy anneal / spawn-speed adaptation); (E) stage-1 gate redefined as
hazard-based (≥ one lap length before crash) + D6 passing; (F) future
sweeps use the shared-baseline warm-start method.

**Next action (done later this session, user said "Sure" to A+B):** item
A below; item B (classical baseline) next.

### Session 25 continued — D6-Spa (item A), and a second real defect found

Full detail in `TRACKS.md` §4 item 14. `experiments/tracks_pilot/d6_spa.py`
reuses D6's own KL/entropy/deployed-vs-sampled/tire-envelope checks
unmodified, adapting only the two hardcoded to the single synthetic
corner (`the_task_is_completable`, `exploration_matches_the_action_scale`)
to use Spa's own tightest corner (r=11.4 m) instead. Caught a real bug
before it shipped: `off_track_penalty`/`stall_penalty`/`progress_scale`
are `EnvConfig` fields with no record in the saved `PPOConfig` JSON, so a
`.get(..., default)` read would have silently reconstructed the WRONG
reward for both `gamma=0.999` runs — fixed by requiring them passed
explicitly per run (`RUN_REWARDS` table, checked against each script's
actual constants, not guessed).

Run against all five saved checkpoints:

- **`the_critic_predicts_returns` confirms item 13 exactly**: pass for
  both `gamma=0.999` runs (EV +0.72, +0.33), fail for all three
  `gamma=0.9995` runs (EV +0.01, +0.00, +0.00).
- **A second, previously-unflagged defect**: `the_task_is_completable`
  **fails for all five runs**. Spa's tightest corner (r=11.4 m) caps at
  10.1 m/s; every episode spawns at `entry_speed=15.0 m/s`, inherited
  unchanged from the single-corner synthetic track. Exactly the failure
  D6 exists to catch (Episode 9's entry speed above corner limit),
  recurring because entry speed was never revisited when the track
  changed. Every spawn near that corner (or Spa's other sub-15-m/s
  corners) starts already unsurvivable without immediate hard braking —
  a likely PRIMARY contributor to the short, heterogeneous per-section
  survival already measured, not only the reward shape. Elevates
  "spawn-speed adaptation" from a contingent later item to something to
  fix before the next training run.
- `exploration_is_not_growing` fails for all five (entropy rising in
  every run) — expected given `entropy_anneal=False`'s already-documented
  behaviour, now formally gated rather than just known.
- `exploration_matches_the_action_scale` passes for all five.
  `greedy_and_stochastic_agree` fails only for `stage1_stallexploit`
  (26% gap), plausibly the stall boundary being a more knife-edge
  decision than genuine driving.

**Next action (done later this session):** item B below.

### Session 25 continued — item B: start-pose fixed, classical baseline is an honest negative result

Full detail in `TRACKS.md` §4 item 15. `physics/driver.py`'s `drive_lap`
always placed the car at the world origin — harmless for every synthetic
`Track` (its `centreline` integrates FROM the origin, so this always
coincided) but wrong for a real circuit's raw coordinates, which is why
`drive_lap` had never run on Spa at all. Fixed: the car now starts at the
track's own s=0 pose. Bit-identical for every existing caller (all 15
pre-existing `test_driver.py` tests unchanged); new test added checking
it against a circle deliberately not centred on the origin — the exact
case that was silently wrong before.

**The classical baseline itself does not complete a Spa lap at any grip
level tried** (`experiments/tracks_pilot/classical_baseline_spa.py`,
0.3-0.85). Every attempt spins or leaves the road in the same ~900-1020 m
window regardless of aggression — checked directly: dropping `grip_use`
from 0.85 to 0.3 moved neither the failure location nor its severity
(worst slip 44-54° either way), ruling out "too aggressive" and pointing
at the steering controller (pure-pursuit gains tuned only against the
single synthetic corner) rather than speed. A third distinct problem
location, different from Spa's tightest corner (item 14, s=403 m).

Item B's actual goal — calibrate reward scales against a competent lap's
earnings — isn't available yet as a result. An honest negative result,
not a failure to hide: driver-gain retuning for real-circuit curvature
is its own task (Episode 13's own precedent: a hand-tuned driver's gains
are exactly the protocol choice CLAUDE.md rule 9 exists for). Not
attempted further without checking scope with the user first.

**Next action:** check with the user — driver-gain retuning for Spa
(new work, unscoped), or item C (the single-variable gamma-revert
training run) instead, since B's finding doesn't block C.

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
| 11 | The fastest setup is the one that crashes | 3 | perturbation eval ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep11/` (re-measured after F96; ordering survives, F98) |
| 12 | What a differential actually does | 4 | diff modes ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep12/` |
| 13 | How engineers built a car that steers with its wheels | 4 | classical TV ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep13/` (noise result retracted by F97) |
| 14 | What the machine found instead | 4 | RL TV variants ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep14/` (rewritten after F93/F94; H-vs-E retracted by F95) |
| 15 | Is chassis tuning about to be automated away? | 4 | TV × Season 2 sweeps ✓ | ✅ **DRAFTED** — `episodes/`, `experiments/ep15/`, F102 |
| 16 | Did any of this survive real physics? | 4 | Chrono backend | ⏸️ **ON HOLD** — deprioritized (D13); revisit-able, not closed |

**Seasons 1–2 (Ep 1–8) carry no training risk.** Tire model, double-track, optimal control only. If the RL work proves harder than expected, half the series still ships.

---

## Attribution

`tires/Sedan_Pac02Tire.tir` is from [Project Chrono](https://github.com/projectchrono/chrono), BSD-3-Clause. Header reads "Magic Formula Tire from ADAMS/Car TIR file." 245/40 R18, `FNOMIN` 4850 N.

It is sized for a heavier car than RV-1 (nominal load implies ~1980 kg). Rescale using the Magic Formula's own `[SCALING_COEFFICIENTS]` block — `LFZO`, `LMUY`, `LKY` — and document the factors used. **Do not hand-edit the `P*` coefficients**; that discards the fit's internal consistency.

Vehicle dimensions from Toyota press material and published specifications. See `docs/vehicle-reference-parameters.md` for per-value sourcing and confidence tiers.
