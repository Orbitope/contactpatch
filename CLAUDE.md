# Contact Patch — working rules

A 16-episode series about how cars actually work, built from scratch and tested
at every step. Bicycle model → double-track → optimal control → RL → torque
vectoring. **The series is the deliverable; the research serves it.**

Read `HANDOFF.md` for where the build is and what to do next, and `FINDINGS.md`
for what has been established and why. `docs/` holds the plans and is **reference
only — do not edit it.** Corrections to a doc go in `FINDINGS.md` as an entry of
record.

**`Dn` and `Episode n` are unrelated numberings.** D4 is the fourth diagnostic
and feeds Episode 8; Episode 4 is about the racing line and needs the
optimal-control solver. See the mapping table in `HANDOFF.md` before writing
either number next to the other.

## Commands

```bash
python -m pytest tests/ -q && python -m diagnostics.D1_tire_card
```

`.venv/` at the project root; `pip install -r requirements.txt`. Diagnostics take
`-v` for every assertion and every technical note, and always write the full
detail to `diagnostics/out/*_report.json` regardless.

## Where writing goes

| File | Contents |
|---|---|
| `CLAUDE.md` | These rules. How to work here. |
| `HANDOFF.md` | Build state, next steps, episode status. Keep it short. |
| `FINDINGS.md` | **Every finding and every decision, numbered and dated, with why.** Append to it whenever something is established or chosen — that is what makes it useful three months later. |
| `docs/` | Plans. Read-only. |
| `episodes/` | Article drafts. |
| `experiments/epNN/` | Per-episode code and outputs, kept re-runnable. Ep 15 re-runs Ep 6 and 7's sweeps with TV on; that should be an afternoon, not a rebuild. |

## The working loop

**Work in episode order, one episode at a time.** For each: build only what that
episode needs, run the experiment, write the article with its figures, then move
on. Do not build diagnostics or physics ahead of the episode that needs them —
D4 was built early and feeds Episode 8, which was wasted sequencing.

An episode is done when all four exist:

1. `experiments/epNN/run.py` — the experiment, re-runnable
2. `experiments/epNN/out/` — its figures and `results.json`
3. `episodes/epNN-*.md` — the article, with the figures embedded
4. `FINDINGS.md` entries for anything it established

The article is the deliverable. Diagnostics gate the physics it rests on; they
are not the product.

## Rules that carry through every episode

These are the difference between results about cars and results about a curve fit.

1. **Two figures for every result: pictorial first, technical second.** Wheels,
   cars and force arrows before axes. A force-versus-angle plot only means
   something to a reader who already knows what a slip angle is. The technical
   charts stay — they are the reference and they carry more for an informed
   reader — but they are never the only version. `viz/diagram.py` has the
   primitives (tires from above, arrows, angle arcs) so a pictorial figure is a
   short function, not a project. Every figure ends with a plain sentence saying
   what the reader just saw.

2. **Validate against ranges from outside the project.** Never against our own
   derived numbers. `D1_reality_check.svg` is the pattern: published band, our
   value, and the source named on every row. **Watch for circularity** — the
   0.95–1.10 g band in `result-evaluation-guide.md` Gate 2 was itself derived
   from our tire file and is deliberately excluded. Mark any band that still
   needs a real citation as such, on the figure, rather than implying one.

3. **Label every number.** Any metric quoted anywhere — a finding, a figure, a
   console line, an episode draft — carries a provenance tag, or sits next to
   something that does. `docs/vehicle-reference-parameters.md` established three
   tiers; this is the fourth:

   | Tag | Meaning |
   |---|---|
   | `[MEASURED]` | Produced by our code. Name the artefact that produced it and the tire/model configuration. |
   | `[SOURCED]` | Published data or a published correlation. Name the source. |
   | `[DERIVED]` | Computed from sourced values by a stated formula. State the formula. |
   | `[ASSUMED]` | Chosen by us. Say so, and revisit if a diagnostic fails. |

   Generated figures carry a provenance stamp automatically — see
   `viz.tire_figures._stamp`. Findings in `FINDINGS.md` carry a **Source** line.
   An untagged number in prose is a bug: the reader cannot tell a measurement
   from an assumption, and six months from now neither can you.

4. **Envelope instrumentation is core-loop, not polish.** Every rollout logs
   per-wheel slip angle, slip ratio and vertical load. `Fz` 225–10,125 N is the
   file's own bound and is enforced. Slip ±12° and slip ratio ±0.20 are **ours**
   and are documented as ours. Lap times from outside the envelope are
   **discarded**, not celebrated.

5. **Seed discipline.** ≥3 seeds per configuration, 5 preferred. Any trend
   smaller than 2× the seed standard deviation is not a finding — report "no
   measurable effect," never "a small effect."

6. **Absolute values are never comparable across models or methods.** Compare
   rank ordering, trend direction, normalised shape. Chrono will be slower in
   seconds and that means nothing.

7. **Metrics are computed downstream from logged arrays, never inside the sim
   loop.** You will redefine "apex" three times and must not re-run anything to
   do it.

8. **Every diagnostic emits a consolidated write-up.** `Report.write_markdown`
   produces `diagnostics/out/Dn.md`: the plain-English summary, every figure it
   made with a caption, the check groups, the technical notes and the headline
   numbers. **Generated, never hand-written**, so it cannot drift from the code.
   That file is the raw material an episode draft is written from — start there,
   not from the JSON.

9. **A test protocol is a modelling choice. Record it, and measure its
   sensitivity.** F17 cost a 33% error in the headline number and two false
   findings because "the skidpad coasts" was decided in passing and never
   flagged. Whenever a manoeuvre could reasonably be run more than one way —
   throttle held or not, entry speed, control input shape — state which and
   report the alternative alongside.

10. **Figures are SVG and generated from parameterised builders, never
   hand-placed or exported as bitmaps.** Vector output scales to any video
   resolution and every element stays editable downstream; parameterised
   builders mean any frame can be re-rendered at any value, so an animation is a
   loop over the same function rather than a rebuild. Do not hardcode a number
   into a figure that the model can supply.

11. **Prefer checks the code was not written around.** Closed-form theory, an
   independently computed reference, a property nobody coded toward. Internal
   consistency is cheap: a diagnostic written after the model, by the person who
   wrote the model, passes almost regardless. Every real defect found in Season 1
   so far was caught by an external comparison or by review — none by a
   self-consistency check. When adding a diagnostic, ask what it would take to
   fail it, and if the answer is "nothing plausible", it is decoration.

12. **Report to the precision the inputs support, not the precision the solver
   returns.** Propagate the documented parameter uncertainty and quote to that.
   K comes back as 0.1884; the reference sheet's own 0.53–0.56 weight-distribution
   range moves it to 0.14–0.27, so it is a one-decimal number. Tolerances inside
   assertions stay tight — they exist to catch regressions, not to claim accuracy
   — but anything a reader sees gets rounded honestly, with the spread stated.

13. **Write up and visualise every checkpoint, as you reach it.** Not at the end.
   A passing diagnostic with no figure and no `FINDINGS.md` entry is not done.
   Numbers that only ever existed in a terminal are lost work.

14. **Diagnostics speak plain English.** Group checks under the question each
   answers; state findings in sentences; put assertion-level detail behind `-v`
   and in the JSON. `result-evaluation-guide.md` promises that "is the physics
   right?" is checkable without vehicle-dynamics expertise — honour that.

15. **Label the model's fidelity, and treat "illustrative" as an honourable
   label.** A simplified model is a legitimate way to teach a concept. Presenting
   its output as though it described a real car is not. Every episode states which
   rung of the ladder it stands on and what that rung leaves out:

   | Rung | Model | What it is good for | What it cannot say |
   |---|---|---|---|
   | 1 | Bicycle (Ep 1–4) | slip angles, grip, the friction ellipse, balance as a concept | anything per-wheel; anything involving load transfer or roll |
   | 2 | Double-track (Ep 5–8, 12+) | load transfer, per-wheel loads, roll-stiffness distribution, differentials, torque vectoring | roll camber, roll steer, compliance steer, aligning torque, tire relaxation, suspension geometry, aero balance |
   | 3 | Chrono cross-check (Ep 16) | whether rung 2 got the trends right | still not a real car |

   **The number that fixes the scale: our understeer gradient is ~0.2 deg/g where a
   real car is ~4.1 (F29, F73). We reproduce roughly 5% of a real car's understeer**
   — because roughly 3 of those 4.1 deg/g are the Bundorf suspension terms rung 2
   does not model. Say that, in those terms, anywhere understeer is discussed.
   Rank ordering, trend direction and normalised shape are what this project can
   claim (rule 6); "this is how a GR86 behaves" is not, and never will be.

   This is not a hedge to sprinkle on a conclusion. It is the difference between
   "here is the mechanism, on a model built to show it" — which is the series'
   actual promise — and an implied claim about a car nobody validated against.

## Code invariants

- **`physics/schema.py` is the single source of truth** for units, sign
  conventions and normalisation. Nothing else interprets raw simulator output.
  SI and radians internally; degrees only at output boundaries, suffixed `_deg`.
- **`tire.default_tire()` is offset-free** and is what everything drives.
  `as_shipped_tire()` is the file verbatim and is only for validating the
  implementation against the reference table. See FINDINGS D1.
- **Never hand-edit the `P*` tire coefficients.** Retarget through the
  `[SCALING_COEFFICIENTS]` block (`LMUY`, `LKY`, `LFZO`) and record the factors.
- **The tire formulas exist once.** `physics/mathkit.py` supplies a numpy or
  CasADi namespace and `physics/tire.py` is written against it, so the optimiser
  and the simulator evaluate the same equations. Never write a second tire model
  for a new solver — `tests/test_casadi_tire.py` is what keeps that honest.
- **A reinforcement-learning result is the DEPLOYED policy's performance.** For a
  Gaussian policy that means the mean action, not sampled actions. Report the
  deployed number as the headline and the sampled number as diagnostic detail
  explaining it. A run whose sampled policy scores well and whose mean action
  fails has not produced a driver — its competence lives in the exploration
  noise. D6 gates on this (`the_deployed_policy_completes_the_task`). Episode 9
  was written around an 88% sampled finish rate whose deployed figure was 0%.
  See FINDINGS F61.
- **Evaluate over several seeds AND several evaluation harnesses.** Episode 9's
  88% came from one harness; six clean-start seeds gave 0%. A number that moves
  that far when you ask it twice is not a measurement.
- **Never quote a time from a solve that did not converge.** `Solution.success`
  is a gate. `Maximum_Iterations_Exceeded` means the returned objective belongs to
  a trajectory that does not quite obey the physics — wrong by 0.1–0.7% in
  **either** direction, which is the size of most findings in this project. Two
  things that are *not* convergence evidence and both read like it: "the objective
  stopped moving to 1 part in 10⁵", and "two node counts agree" (runs sharing a
  stopping criterion agree about the same artefact). Prefer the grid where every
  solve in the comparison converges over the finest grid; raise `max_iter` before
  accepting a coarser answer. See FINDINGS F39.
- **Every minimum-time solve constrains the slip envelope.** A min-time solver
  will drive at 30° of slip where the tire model is extrapolating and return a
  time that is a statement about our curve fit. `Solution.envelope_occupancy()`
  must be 0.
- **Season 2 roll-stiffness magnitudes are not quotable.** The double-track
  model's anti-roll-bar authority is only ~1.5× the 0.2 deg/g measurement noise
  floor across its whole documented range, because roll camber and roll steer are
  not modelled (F31). Rank ordering and trend direction are usable; magnitudes
  are not. Same missing terms as the understeer gap (F29).
- **Never model coasting as `κ = 0`.** Solve for the κ that gives the demanded
  `Fx`. See FINDINGS F7.
- **Frame conversions are named functions in `viz/diagram.py`, never inline
  arithmetic**, and every one is pinned by a test that works the geometry rather
  than restating the formula. `screen_deg`, `screen_dx`, `screen_heading_deg`.
  All three have been wrong at least once and **all three failed silently** — a
  wrong sign renders a plausible picture of a car doing something it never did.
  F36 got a 180°-wrong car heading into a published figure because a car outline
  is nearly symmetric. If you find yourself composing two conventions inline,
  that is the bug.
- Track width is the moment arm for torque vectoring and is only `[LIKELY]`.
  Re-run every TV magnitude claim at ±3% track and confirm the *conclusion*
  holds. If a finding flips on that, it was never a finding.

## On the global RL-environment guidance

`~/.claude/CLAUDE.md` routes custom-RL-environment work to the `rl-env-*`
skills. Season 3 (Ep 9–11) builds a PPO environment and will partially match
those trigger signals, so: **this project does not use `simulacrum`.** It has its
own D1–D6 battery and its own layout, both fixed by `docs/`. Do not scaffold a
`spec.md`/`reference.py`/`fast.py` package here. The skills are still worth
consulting as *technique* references — `rl-env-vectorize` for masking and
broadcasting bugs, `rl-env-debug-triage` before touching hyperparameters — and
the differential-testing idea already exists here as the Ep 16 Chrono
cross-check. Raise it with the user if this reading looks wrong when Season 3
starts.
