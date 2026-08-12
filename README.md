# Contact Patch

**How a car actually handles — built from a measured tire file upward, and checked at every step.**

### → [Read the interactive article](https://orbitope.github.io/contactpatch/)

Front-wheel drive or rear? Is 50:50 weight distribution real engineering or a
marketing number? Is mid-engine actually better, and better at what?

Everything a car does happens on four patches of rubber the size of your hand.
This project builds one out of a real tire data file, points a minimum-time
solver at it, and asks. **Most of the famous answers come back smaller than the
arguments about them** — until you replace the perfect driver with one that can
be surprised, and the numbers move.

The article runs the tire model live in your browser. Every number in it is
exported from the experiments' own artefacts.

---

## The series

Fifteen written parts, in `episodes/`. Each is a draft article with its figures
embedded; each has a re-runnable experiment beside it in `experiments/epNN/`.

**Season 1 — one tire, then the simplest car that can misbehave**

| | | |
|---|---|---|
| 1 | [Why does a tire make grip at all?](episodes/ep01-why-a-tire-makes-grip.md) | slip angle, and why sliding *is* the mechanism |
| 2 | [The most important graph in vehicle dynamics](episodes/ep02-the-most-important-graph.md) | grip falls as load rises — the fact everything else is bookkeeping on |
| 3 | [The simplest car that can understeer](episodes/ep03-the-simplest-car-that-can-understeer.md) | two axles, a skidpad, the understeer gradient |
| 4 | [The fastest way round a corner isn't the obvious one](episodes/ep04-the-fastest-way-round-a-corner.md) | minimum-time optimal control, trail braking |
| 5 | [Where the simple model breaks](episodes/ep05-where-the-simple-model-breaks.md) | four wheels, load transfer, roll |

**Season 2 — the arguments everybody has**

| | | |
|---|---|---|
| 6 | [Which wheels should drive?](episodes/ep06-which-wheels-should-drive.md) | FWD vs RWD: same racing line, inverted tire workload |
| 7 | [Where you put the weight](episodes/ep07-where-you-put-the-weight.md) | balance changes the car far more than the lap time |
| 8 | [Front, mid, or rear engine](episodes/ep08-front-mid-or-rear-engine.md) | "mid-engine is better" is a polar-moment claim in disguise |

**Season 3 — give it a driver that can be surprised**

| | | |
|---|---|---|
| 9 | [Teaching a car to drive, and watching it cheat](episodes/ep09-teaching-a-car-to-drive.md) | PPO, and the two shortcuts it found instead |
| 10 | [One policy, a thousand cars](episodes/ep10-one-policy-a-thousand-cars.md) | one driver conditioned on the design it is driving |
| 11 | [The fastest setup is the one that crashes](episodes/ep11-the-fastest-setup-is-the-one-that-crashes.md) | fragility as a measurement, not a vibe |

**Season 4 — and then software gets involved**

| | | |
|---|---|---|
| 12 | [What a differential actually does](episodes/ep12-what-a-differential-actually-does.md) | one fixed rule: torque flows to the slower wheel |
| 13 | [How engineers built a car that steers with its wheels](episodes/ep13-a-car-that-steers-with-its-wheels.md) | classical torque vectoring — reference model, PID, allocator |
| 14 | [What the machine found instead](episodes/ep14-what-the-machine-found-instead.md) | hand the same four wheels to a learner |
| 15 | [Is chassis tuning about to be automated away?](episodes/ep15-is-chassis-tuning-about-to-be-automated-away.md) | what the controller makes irrelevant, and what it doesn't |

Episode 16 — a cross-check against an independent physics engine — is on hold,
not cancelled ([D13](FINDINGS.md)).

---

## What this model can and cannot say

Stated up front because it is the difference between a result about cars and a
result about a curve fit.

**Our understeer gradient is ~0.2 deg/g where a real car is ~4.1. We reproduce
roughly 5% of a real car's understeer**, because about 3 of those 4.1 deg/g come
from suspension terms — roll camber, roll steer, compliance steer — that a
double-track model does not have.

So: **rank ordering, trend direction and normalised shape are what this project
claims.** "This is how a GR86 behaves" is not, and never will be. Every episode
states which rung of the ladder it stands on and what that rung leaves out. A
simplified model is a legitimate way to teach a mechanism; presenting its output
as though it described a real car is not.

---

## How the work is kept honest

The interesting part of this repo is arguably the bookkeeping.

- **[`FINDINGS.md`](FINDINGS.md)** — 142 numbered, dated findings and decisions,
  including the retractions. When a result turns out to be wrong it gets an entry
  saying so, next to the original. Several headline numbers in this series have
  been retracted by later entries; they are still there to read.
- **Every number carries a provenance tag** — `[MEASURED]`, `[SOURCED]`,
  `[DERIVED]` or `[ASSUMED]`. An untagged number in prose is treated as a bug.
- **Validation is against published ranges from outside the project**, never
  against our own derived numbers, and bands that would be circular are
  deliberately excluded and marked as such.
- **Diagnostics D1–D6** gate the physics — the tire card, sign and conservation
  invariants, steady-state handling, transient response, load transfer, and
  training health. Each emits a generated write-up, never hand-written, so it
  cannot drift from the code.
- **Seed discipline**: ≥3 seeds per configuration. Any trend smaller than 2× the
  seed standard deviation is reported as "no measurable effect," never as "a
  small effect."
- **Nothing is quoted from a solve that did not converge**, and every
  minimum-time result is checked for whether it left the tire model's validated
  envelope.

An audit of the fifteen write-ups found ten carrying at least one number that had
drifted from its own artefact, after two shared-machinery corrections propagated
downstream. That audit is itself in `FINDINGS.md`, and the web article is built
so it can't happen there — its numbers are exported from the artefacts.

---

## Running it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

Then any diagnostic, which prints a plain-English summary and writes a full
write-up to `diagnostics/out/`:

```bash
python -m diagnostics.D1_tire_card
```

Add `-v` for every individual assertion. Each episode's experiment re-runs from
its own directory; most support `--figures-only` to redraw from cached traces
without recomputing.

---

## Layout

```
physics/       tire model, bicycle and double-track cars, optimal control,
               torque vectoring, the batched RL environment
diagnostics/   D1-D6 — the gates the physics has to pass
experiments/   one directory per episode: run.py + out/ + results.json
episodes/      the article drafts
viz/           parameterised SVG figure builders
docs/          the interactive article (GitHub Pages) + planning documents
tools/         exporters that turn artefacts into the article's data files
FINDINGS.md    every finding and decision, numbered and dated
CLAUDE.md      the working rules
```

---

## Licence and attribution

This project is [MIT licensed](LICENSE).

`tires/Sedan_Pac02Tire.tir` is from [Project Chrono](https://github.com/projectchrono/chrono),
BSD-3-Clause — a Magic Formula 2002 set, 245/40 R18. It is sized for a heavier
car than the reference vehicle and is rescaled through the Magic Formula's own
`[SCALING_COEFFICIENTS]` block, with the factors recorded. The `P*` coefficients
are never hand-edited.

Vehicle dimensions are from published specifications, with per-value sourcing and
confidence tiers in `docs/vehicle-reference-parameters.md`.
