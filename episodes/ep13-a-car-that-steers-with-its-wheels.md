# How engineers built a car that steers with its wheels

*Contact Patch, Episode 13. Season 4: Torque vectoring.*

---

## The question

Episode 12 ended with a device that cannot think. A differential feels the two
driven wheels turning at different speeds, applies one fixed rule to that
difference — torque flows from the faster wheel to the slower — and whatever
happens to the car's rotation happens as a side effect. It pushes you wide at part
throttle and turns you in when the inside wheel spins, and it has no idea which of
those you wanted.

But the side effect is real. Push harder on the right-hand wheels than the left and
the car rotates left. That is not subtle: on our car, moving 3000 N from one rear
wheel to the other is worth about 2240 N·m of yaw moment `[MEASURED]`, which is
more than a rad/s² of yaw acceleration on this car's 1950 kg·m² of polar moment.
(That is F72, and until this season the model did not have that term at all.) It is
a genuine steering input that has nothing to do with the steering wheel.

So: **if pushing one wheel harder rotates the car, why not just do that?**

Deliberately, on purpose, whenever the car is not rotating the way the driver
asked.

## Two layers

The classical answer has the same shape wherever it appears, and has for about
twenty years. It is worth stating before any of the physics, because the shape *is*
the engineering:

> **One layer decides how much you want to rotate. Another decides which wheels
> pay for it.**

The upper layer takes the steering angle and the speed, works out what the car
*should* be doing, compares that with what it *is* doing, and emits a single
number: a desired yaw moment, in newton-metres. It knows nothing about wheels.

The lower layer takes that one number, plus the total longitudinal force the
driver asked for, and turns it into four per-wheel forces — subject to no tire
being asked for more than it has left. It knows nothing about yaw rate, reference
models or drivers.

![Two layers](../experiments/ep13/out/01-two-layers.svg)

That split is the reason the architecture has lasted. The upper layer is where
vehicle-dynamics judgement lives, and it is two-dimensional — yaw rate in, moment
out — so it can be tuned, plotted, and argued about over a table. The lower layer
is a convex optimisation with a unique answer. Neither half needs to know how the
other one works, which means two people can build them.

### The upper layer: what *should* the car be doing?

The reference model is the textbook relation Episode 3 built:

```
r_ref = v · δ / (L + K · v²)
```

Steering angle `δ`, speed `v`, wheelbase `L`, and `K` — the understeer gradient,
the same number Episode 3 introduced in deg/g and Episode 5 measured on four
wheels. Our car's is **0.204 deg/g** `[MEASURED]`, which is tiny; a real car is
near 4.1, and roughly 3 of those come from suspension terms this model does not
have (F29, F73). More on that below.

Feed it the driver's steering angle and it says what yaw rate that angle *ought*
to produce. A PID closes the gap. Its output is the moment demand.

**The saturation matters more than the gains.** The reference model is linear, and
a linear model does not know that tires run out. Ask it what 25 degrees of steering
should do at 20 m/s and it answers **3.21 rad/s** — which implies **6.5 g** on a car
that makes 0.95 `[MEASURED]`. The PID would then see an error that can never be
closed, the allocator would saturate against it, and the driver aid would drag the
car into a spin trying to satisfy a number no tire can produce.

So the reference is capped at what the tires can actually sustain,
`r_max = a_y_max / v`, with `a_y_max` **0.951 g** `[MEASURED]` on this car — 0.466
rad/s at that speed, a factor of seven below what the linear model asked for. That
is not a detail. It is the difference between a stability controller and a hazard.

### The lower layer: who pays?

Four wheels, two demands. Deliver the total longitudinal force the driver wanted,
and deliver the moment the upper layer asked for. That is two equations and four
unknowns, so there are two degrees of freedom left over — and the classical answer
is to spend them minimising **tire workload**, so that no tire is asked for a much
larger share of what it has left than its neighbours.

Written out, it is a quadratic program:

```
minimise   s_fx · (Fx_total − Fx_demand)²
         + s_mz · (Mz − Mz_demand)² / (track/2)²
         + ε · Σ (Fx_i / cap_i)²

subject to  −cap_i ≤ Fx_i ≤ cap_i
```

`cap_i` is what that tire has left longitudinally given what it is already doing
laterally — the friction ellipse this project has used since FINDINGS D9, evaluated
per wheel on the previous instant's forces, because that is what a real controller's
sensors could know.

The two demands enter as weighted terms rather than hard constraints, and that is
not a shortcut. **At the limit they routinely cannot both be met.** A hard
formulation has to answer "which one do I give up?" with a branch; this answers it
with a ratio, `s_fx` against `s_mz`, which is one number that can be swept. It is
swept below.

**One thing worth noticing before any results.** If you only have a
torque-vectoring differential — one axle, a left/right split — then you have two
demands and *two* effectors, and there is nothing left to optimise. The allocation
is determined; the second layer collapses to a division. The QP only earns its
place when there are more effectors than demands, which on a car means a motor or
a brake at every corner. We ran both.

## The experiment

A controller can only be judged in closed loop, so this episode needed something
Seasons 1 and 2 did not have: **a driver who reacts.**

Not the minimum-time solver. Hand a solver four independent wheel forces and it
will use them optimally, which answers "what is torque vectoring worth to a driver
who knows the future?" — and Episode 8 already answered that class of question with
"almost nothing" (F49), because a solver that cannot be surprised simply plans
around whatever the car does. Not the learned policy either: that would confound
the controller with the training run.

What is left is the thing chassis engineers actually use — a repeatable,
unintelligent driver model, run with the aid on and with the aid off.

Ours steers by pure pursuit at a point about half a second ahead, and tracks a
quasi-steady-state speed profile: cornering limit everywhere, a backward pass for
how early to brake, a forward pass for how hard it can accelerate. It knows nothing
about racing lines and cannot trade entry for exit. **Every configuration therefore
drives the same geometric path**, which is what makes this a comparison — a lap
time difference cannot be a different line, because there is only one line.

The profile is built for `grip_use` times the car's measured grip. That is the
knob. Turn it up and the driver asks for more than the tires have.

### The metric, chosen before anything was measured

Because every configuration drives the same plan, at any given `grip_use` they are
all attempting an *identical* lap and take an almost identical time. **What differs
is whether the car can do it.** So the result is:

1. **the highest `grip_use` that still produces a valid lap** — on the road, and
   inside the ±12° region the tire file was actually fitted over;
2. **the quickest valid lap**, which is a monotone consequence of the first, and is
   reported only because a lap time is something a reader can hold on to.

Those two are not independent evidence. They are one measurement stated twice.

Five configurations, one driver:

| | what it is |
|---|---|
| **open differential** | what Episodes 9–11 drove |
| **limited-slip** | Episode 12's passive device, 1.5:1 and 0.5 locking |
| **allocator only** | the four-wheel allocator with its yaw demand forced to **zero** |
| **TV, four wheels** | the full two-layer controller |
| **TV, rear axle** | a torque-vectoring differential — one degree of freedom |

The third one is the important one, and it is the reason this episode can say
anything at all. Both it and the full controller replace the differential, so both
get grip-proportional braking and traction distribution for free. **Only one of
them also asks for yaw.** Without that control condition, "torque vectoring is
worth X" would be a claim about two things at once.

## The result

![The limit](../experiments/ep13/out/03-the-limit.svg)

| | cornering limit | best valid lap | corner section |
|---|---|---|---|
| open differential | 1.041 | 14.508 s | 5.483 s |
| limited-slip | **0.969** | **14.719 s** | 5.635 s |
| allocator only | 1.063 | 14.516 s | 5.515 s |
| **TV, four wheels** | **1.095** | **14.434 s** | **5.445 s** |
| TV, rear axle | 1.073 | 14.562 s | 5.531 s |

All `[MEASURED]`, one closed-loop driver, `long_exit`, tire offsets removed.

**It works.** The controlled car survives **5.2% more cornering demand** than the
passive one, and the direct evidence that both layers are doing their jobs is
better than the lap time: the allocator delivers the moment the PID asks for to
within 60 N·m of a 996 N·m peak, and RMS yaw-rate error through the corner falls
from **0.1662 rad/s to 0.0197 — 88% lower** `[MEASURED]`, both cars driving the
same plan at the hardest aggression the passive one completes.

**And it is worth 0.51% of lap time.** Half a percent. The corner section — brake
point to full exit — improves by 0.69%. Both are an order of magnitude below the
"1–4%" the series plan expected, and the reason is not subtle: 260 of this lap's
393 m are a straight, and on it the car is power-limited, not grip-limited. A yaw
controller has nothing to do there. The lap-time number is diluted by construction,
which is why the cornering limit is the one that describes what actually changed.

Which is also why the skidpad matters.

## The skidpad, and the number from outside

The best published figure for a torque-vectoring gain is about **9%**, for an FSAE
car on a skidpad. **That number is `[SOURCED — citation outstanding]`**: it comes
from this project's own planning document, which states it without a reference, and
I have not been back to the paper. It is marked as needing one rather than dressed
up as verified — which is what this project's own rule about validation bands says
to do when the band has not been traced.

A skidpad is the most favourable manoeuvre there is — constant radius, steady
state, nothing but cornering — so that 9% is a **ceiling**, not a target. Beating it would be evidence of a bug, not of a good
controller. That is rule 2 of this project doing its job: the comparison band comes
from outside, and our own model does not get to set it.

Same driver, constant-radius circle, aggression turned up until it fell off:

| | sustained lateral acceleration |
|---|---|
| open differential | 0.939 g |
| limited-slip | 0.893 g |
| allocator only | **0.932 g** |
| torque vectoring, four wheels | **0.951 g** |
| torque-vectoring differential | 0.949 g |

All `[MEASURED]`, 40 m radius, same driver, aggression bisected to 0.002.
**+1.30%**, comfortably under the ceiling.

![What it is worth](../experiments/ep13/out/05-what-it-is-worth.svg)

## What the controller actually does with its time

![Yaw tracking](../experiments/ep13/out/04-yaw-tracking.svg)

The demand **changes sign inside the corner**. It peaks at +996 N·m at 77 m —
adding rotation, because the front tires are saturating and the car is no longer
turning as much as a linear model says it should — and reaches −526 N·m at 131 m,
taking rotation away as the steering unwinds faster than the car's rotation decays.

Between those two it settles to a small steady value. In the middle of a steady
corner the car already turns roughly the way the linear model says it should — that
is what the reference model was built from — so the error is nearly zero and the few
hundred newton-metres still being commanded are the PID's integral term holding it
there.

**A yaw controller is mostly a transient device.** It earns its keep where the car
is changing what it is doing, which is exactly where a passive differential is
applying one fixed rule with no idea which transient it is in.

![Which wheels pay](../experiments/ep13/out/02-which-wheels-pay.svg)

## Most of it is not torque vectoring

Here is the finding I did not expect, and it exists only because of the control
condition.

The allocator **with its yaw demand forced to zero** — four wheels sharing brake and
drive force in proportion to what each has left, no yaw control whatsoever — gets
**40%** of the whole cornering-limit improvement on the lap.

That share is the least stable number in this episode. It moved from 77% to 40% when
the allocator went from being re-solved inside the integrator to holding its command
for the control interval, as a real ECU does, and across the six sensitivity runs it
spans 38–56%. So this is a "roughly half" claim and it is stated as one. **The
ordering is what survives**: open differential worse than allocator-only,
allocator-only worse than the full controller, in every run.

And on the skidpad the split **inverts**. Look at the table above: the allocator
alone is 0.932 g against the passive car's 0.939. On a steady circle there is no
braking to distribute and almost no drive force to spread, so the lower layer has
nothing to be clever with and lands slightly *below* the passive car — and the whole
skidpad gain is yaw control. The same two layers split the credit in opposite
proportions in the two manoeuvres.

The lesson generalises past this car. When a system replaces a mechanical device
with a computer, some of what you measure is the *decision-making* and some is
simply that a computer can meter four things separately where a lump of gears could
only meter one. Those are different claims with different consequences for Episode
15, and only a control condition separates them.

## The number that depends on the driver, not the car

One of this episode's twelve checks fails. It is the one that asks whether the
result survives the driver being tuned differently, and it is the most useful thing
in the run.

The driver's preview time — how far ahead it aims — is `[ASSUMED]` at 0.55 s. Change
it by 30% in each direction, change nothing else, and:

| driver preview | passive limit | controlled limit | gain |
|---|---|---|---|
| 30% less | 1.057 | 1.054 | **−0.34%** |
| nominal | 1.041 | 1.095 | **+5.18%** |
| 30% more | 0.996 | 1.111 | **+11.55%** |

All `[MEASURED]`; the preview time itself is `[ASSUMED]`. A single assumed number **in the driver** — not in the car, not in the controller —
moves the headline from "nothing measurable" to "+11.6%". (The −0.34% is 0.0036 in
`grip_use` against a bisection resolution of 0.002, so read it as a wash rather than a
reversal. A wash is still not +5%.)

The mechanism is not mysterious. A shorter preview makes the driver steer later and
harder, which suits the passive car and hands the yaw controller a reference signal
full of the driver's own transients to chase. A longer preview makes the driver
smoother and slower to correct, which the passive car cannot recover from and the
controller can.

**A driver aid is developed against a driver, and the pair gets tuned together
whether or not anyone says so.** Any measurement of what such a system is worth has
a driver model inside it. The check stays failed and the threshold has not been
moved.

## What it is worth to a driver who makes mistakes

All of the above is a driver who does exactly the same thing every lap. Add
Episode 11's steering noise — the same magnitude, applied the same way — and run 40
seeded laps of each configuration at an aggression all of them can handle
undisturbed:

| | valid laps | lap time |
|---|---|---|
| open differential | **31/40** | 14.602 ± 0.015 s |
| limited-slip | **3/40** | 14.659 ± 0.039 s |
| allocator only | 40/40 | 14.608 ± 0.009 s |
| **torque vectoring, four wheels** | **40/40** | **14.580 ± 0.006 s** |
| torque-vectoring differential | 40/40 | 14.596 ± 0.015 s |

All `[MEASURED]`, 40 seeds each at `grip_use` 0.991; the noise magnitude is
`[ASSUMED]` and is Episode 11's.

A 78% completion rate becomes 100%, and the lap-time scatter is cut by more than
half. **That is a far larger effect than the half percent it is worth to a perfect
driver** — and it is what production stability systems are actually sold on. The
undisturbed lap could not have shown it.

(The limited-slip car's 3/40 wants care: at this aggression it is already past its
own limit of 0.969, so it is being asked to do something it cannot do cleanly even
undisturbed. It is evidence about that device at that demand, not a general claim
about limited-slip differentials.)

## The differential loses to no differential

Look again at the second row of that table. **The limited-slip differential is the
slowest configuration tested** — slower than an open differential by 0.211 s, and
0.072 lower in cornering limit (0.969 against 1.041).

That is Episode 12's push-wide appearing in a lap time for the first time. A locking
device drags the outside wheel and yaws the car out of the corner, and our driver,
which brakes in a straight line and turns in at a fixed point, pays for that at
entry with no way to recover it. A real driver would adapt. Ours cannot, and that is
a limitation of this experiment as much as a property of the device — but the
direction is the same one every driver of a welded car reports.

## What this can't tell you

**Fidelity: rung 2** (CLAUDE.md rule 15). Four independently commanded wheel forces
is a four-motor electric car, not RV-1's rear-drive combustion driveline. The
rear-axle version is the one RV-1 could actually have, and it is worth about 60% as
much: +3.07% of cornering limit against +5.18%. Underneath both is a double-track model with no roll camber, no roll steer and
no compliance steer — the terms that make up about three quarters of a real car's
understeer. **We reproduce roughly 5% of a real car's understeer gradient**, so a
percentage here is a trend, not a specification.

**Track width is `[LIKELY]`, and it is the moment arm.** Every yaw number scales
directly with it. At −3% the gain is +5.36% and at +3% it is +5.00%, against +5.18%
nominal: the magnitude moves with the arm, as it must, and the conclusion does not.

**The driver is a tracker, not a racing driver**, and its preview time changes the
answer by more than the controller is worth. See the section above; that is the
biggest caveat in this episode by a distance. It also cannot trade line for exit and
never brakes in a corner, so its absolute lap times are slower than the
optimal-control episodes' and are not comparable with them (rule 6).

**One corner, one car, one tire.** And the aggression knob scales cornering and
braking limits together, so `grip_use` is a plan the driver believes in, not a
property of the road.

**The two headline numbers are one measurement.** Stated above, repeated here,
because it is the sort of thing that gets quoted as two.

**One of twelve checks fails** and the run says so: the driver-tuning one above.
It is the only one, and it is the one that matters most.

## The crack

The controller works. It also did exactly what we told it to.

Look back at the upper layer: we handed it a linear reference model and said *this
is what the car should be doing*. Every moment it demanded was in service of making
a real, saturating, load-transferring car behave like a textbook equation.

That is a **choice**, and it is buried in one coefficient. Ask for a pointier car
than the car is, and the answer changes:

| target understeer gradient | cornering limit |
|---|---|
| 0.204 deg/g (the car's own) | 1.095 |
| 0.100 deg/g | 1.097 |
| 0.000 deg/g — neutral | 1.100 |
| −0.150 deg/g | 1.102 |

All `[MEASURED]`. Monotone, and small — 0.007 across the whole range against a
bisection resolution of 0.002 — so read it as a weak trend and not as a result.

Published work on optimising torque vectoring for lap time is said to report the
same direction more strongly: that the best times come from *allowing* deviations
from neutral yaw-rate tracking, which would make the reference model — the thing
twenty years of engineering consensus is built around — itself a constraint on how
fast the car can go. **That claim has the same outstanding citation as the 9%**: it
comes from this project's planning note and I have not traced it. Our own sweep
points the same way and is far too small to be evidence for it.

So the obvious question is the one this whole series has been walking toward.

Give something the same four wheels, the same physics, the same stopwatch, and **no
reference model at all**. Do not tell it what the car should be doing. Let it find
out.

Does it agree with us?

---

## Reproducing this

```bash
python -m experiments.ep13.run
```

About six minutes: roughly 700 closed-loop laps, no solver and no training.
`--figures-only` redraws from `results.json`; `--quick` runs a coarser sweep.

**New code this episode.** `physics/torque_vectoring.py` (reference model, PID,
allocator) and `physics/driver.py` (the closed-loop driver). The backend's
per-wheel longitudinal split is now a hook: with nothing attached it is exactly the
differential of Episode 12, which is pinned by a test, so every result in Episodes
1–12 is untouched.

**Checks.** The run generates its own write-up at `diagnostics/out/D-ep13.md` —
twelve checks, one of which fails on purpose. Alongside it, three of the thirty
tests in `tests/test_torque_vectoring.py` and `tests/test_driver.py` are external
rather than self-consistent, which is the kind this project has learned to value
(rule 11): the allocator's idea of the moment a force makes is checked against the
*simulator's* yaw-moment code, the QP's answer is checked against brute-force
sampling of the feasible box, and the driver's position fix is checked against the
drawing map's inverse. The third one is how F81 was found — a defect that had been
sitting in the track geometry since Episode 4.

**On the yaw moment all of this rests on.** Until this season the model had no
drivetrain yaw term at all: moving the entire drive force from one wheel to the
other changed the computed yaw by exactly zero. A torque-vectoring controller run
on that model would have produced a perfect null result and nothing would have
errored. That is F72, and it is why Season 4 needed a physics fix before it could
have an episode.
