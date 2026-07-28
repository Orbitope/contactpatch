# The fastest setup is the one that crashes

*Contact Patch, Episode 11. Season 3: The driver.*

---

## The question

Why don't racers just run the fastest setup?

Everyone who has tuned a car in a game knows the answer in their hands before they
can say it. You soften the rear, the car rotates, the lap time drops — and then on
lap four you get a bump mid-corner and you are facing the wrong way. The fast setup
and the setup you can actually drive are not the same setup.

**This is the first question in the series that optimal control structurally could
not answer.** Every result in Seasons 1 and 2 came from a solver that was handed
the whole road and exact knowledge of the car. Ask it what happens when the grip is
lower than expected and it does not crash — it returns a new plan for the new grip.
It cannot be surprised, and fragility is a property of something that can be.

Season 3 finally has a driver that can be surprised. So: perturb it.

## The experiment

Episode 10's design-conditioned policy, loaded and deployed. **Nothing is
retrained.** That matters more than it sounds: the driver is held identical across
every car and every disturbance, so a difference in outcome cannot be a difference
in training luck. It is also the only honest way to run this with one training
seed, which is still all Season 3 has.

Two disturbances, applied separately and then together so each one's contribution
is attributable:

**Steering noise.** Gaussian noise added to the commanded steering, every step.
This is the hands and the linkage — and unlike Episode 9's exploration noise, it is
still there when you deploy the policy. Episode 9's whole failure was noise that
vanished on the car you would ship. This does not vanish.

**Grip variation.** Peak lateral friction scaled per lap, through the tire file's
`LMUY` scaling coefficient and never by touching a fitted `P*` coefficient. One
surface per lap rather than per step, because that is what a damp patch or a cold
track actually is.

And **fragility defined before measuring it**, because it is a metric choice:
failure rate is the headline, lap-time scatter among the laps that survive is the
second number. A car can be reliable and still unpredictable, and a driver feels
the second one.

![What a fragile car looks like](../experiments/ep11/out/01-what-fragile-looks-like.svg)

## What happened, after I got it wrong once

I want to tell this in the order it happened, because the mistake is more useful
than the result.

I calibrated the disturbance levels on **10 rollouts per cell** and got this: zero
failures anywhere, worst slip 8.7–9.8° at steering σ 0.15, comfortably inside our
±12° tire fit. Push harder and failures appeared, but so did 13–17° of slip, where
the tire model is extrapolating and a crash is a statement about our curve fit
rather than about the car.

So I wrote the episode up as a null result: *the driver is too far inside the
envelope to be fragile, and the Pareto front does not exist at any disturbance I
can defend.* It was a tidy story and it even had a mechanism — Episode 10's
envelope penalty left the policy cornering at 6–7° with 12° available, five degrees
of margin it never spends.

Then I ran it properly at 40 rollouts, and it crashes plenty.

**Two errors, and the second is the one worth keeping.**

**A failure rate needs far more samples than a mean does.** At n = 10, a true 7%
rate shows up as zero events about half the time. I had not measured "no
failures"; I had measured nothing and read it as absence.

**Worst-slip is an extreme-value statistic and I used it as a bound.** The maximum
over a sample grows with sample size. "Worst slip 9.8° over ten laps" says nothing
about the worst over forty — and at forty the same condition reaches 11.7–15.3°.
Any max-over-n quantity — peak load, largest excursion, worst slip — is a property
of the sample, not the system. Medians hold still as n grows. Maxima do not. I had
built a conclusion on a number that was never a limit.

## Discarding laps, not conditions

Fixing that exposed a third error in how I was applying our own rule.

This project's rule 4 says laps from outside the slip envelope are discarded, not
celebrated. I had implemented that per *condition*: if the worst lap in a condition
exceeded 12°, the condition was disqualified. At forty rollouts that is absurd —
one excursion reached 35° while the **median** lap in the same cell sat at about 8°,
so a single bad lap threw away thirty-nine defensible ones.

Rule 4 is a per-lap rule. A lap that left the road at 20° of slip tells us about
our extrapolation. A lap that left the road having never exceeded 12° is real
evidence, and so is a lap that finished inside. So: keep those, drop the rest, and
report the failure rate over what is left.

One honest consequence, stated where it belongs rather than in a footnote. A lap
that **both** failed and left the fit gets discarded, and some of those were real
crashes. Every in-fit failure rate below is therefore a **lower bound**, not an
estimate. The ordering survives that; the magnitudes are floors.

## The tradeoff is real

Four designs, 120 deployed laps each, both disturbances applied, counting only
laps that never left the tire's fitted region:

| Design | Lap, undisturbed | Laps lost | 95% interval |
|---|---|---|---|
| **47% front** — the quickest | 19.13 s | **9 of 104 · 8.7%** | 4.6–15.6% |
| 54% front | 19.42 s | 0 of 114 · 0% | 0–3.3% |
| 61% front | 19.80 s | 0 of 102 · 0% | 0–3.6% |
| 65% front | 20.04 s | 0 of 105 · 0% | 0–3.5% |

**Undisturbed, this driver is flawless on all four: 120 of 120 laps, none of them
outside the tire fit.** Everything above is caused by the disturbance, not by a
driver that was already struggling.

**And it survives correction for multiple comparisons.** Six pairwise Fisher exact
tests, Holm-Bonferroni at family-wise 0.05: the 47% car differs from the 54% car at
**p = 0.0011**, from the 65% at **p = 0.0016**, from the 61% at **p = 0.0033**. The
other three are indistinguishable from each other (p = 1.000). At 40 rollouts the
same effect sat at p = 0.045 uncorrected and established nothing.

**It is a cliff, not a slope.** One design loses laps and three do not. That is more
useful than a gradient would have been: it means there is a threshold to stay
behind rather than a dial to trade off.

The direction is what anyone who has tuned a car would predict, and it holds
across both disturbances applied separately as well as together. The more
rear-biased car is quicker and less forgiving. Weight over the driven axle helps it
put power down — Season 2's mechanism — and takes away the margin that absorbs a
surprise.

![The fastest setup is the one that crashes](../experiments/ep11/out/02-speed-vs-fragility.svg)

**This is the first chart in the series optimal control could not have produced.**
Ask a minimum-time solver about lower grip and it hands back a new plan, not a
crash. It has perfect foresight and exact knowledge of the car, so there is no such
thing as a surprise for it to mishandle. Fragility is a property of a driver that
can be caught out, and Season 3 finally has one.

![Which disturbance did the damage](../experiments/ep11/out/04-perturbation-card.svg)

## It isn't margin. It's whether you get it back.

The obvious explanation is that the fast car runs closer to the edge, so it needs
less provocation to go over. I believed that, wrote it down, and it is wrong.

Count how often each car actually went past the tire's fitted limit, and how many
of those laps ended off the road:

| Design | Laps that left the fit | Of those, crashed |
|---|---|---|
| 47% front | 16 | **13 — 81%** |
| 54% front | 6 | 2 — 33% |
| 61% front | 18 | **1 — 6%** |
| 65% front | 15 | 1 — 7% |

**The 61% car left the limit more often than the 47% car — eighteen laps against
sixteen — and crashed once against thirteen.** Exposure is roughly equal. What
differs is the return trip.

![When it lets go, does it come back?](../experiments/ep11/out/03-when-it-lets-go.svg)

The two laps in that figure are real, not drawn. The 61%-front car reached **13.4°**
of slip — further past the fit than the 47% car's **12.0°** — and completed the lap
anyway.

The mechanism is the one Season 2 spent two episodes on, showing up as a robustness
property instead of a lap-time one. **A car that runs out of front grip pushes wide,
and pushing wide scrubs speed, which restores grip.** That is a negative feedback
loop; it corrects itself whether or not the driver does anything clever. **A car that
runs out of rear grip rotates, and rotating points the tires further from where they
need to be, which rotates it more.** That is a positive feedback loop, and catching
it requires a correction in the right direction at the right moment.

So "fragile" does not mean "operating with less margin." It means **the failure mode
is divergent rather than self-limiting** — and that is a property you can read off
a car's balance before you ever drive it.

## While I was wrong about margin, I was also wrong about the numbers

Worth recording because I nearly published it. I described this policy as
conservative, cornering at 5.8–7.4° of slip against a 12° bound, banking margin it
never spends.

The Magic Formula is flat near its peak. Measured on our own tire, at 4 kN it peaks
at **10.35°** of slip — and at 5.8–7.3° the policy is already extracting **94–98% of
peak lateral force.** The ±12° envelope sits *at* peak grip, not comfortably beyond
it. There is no large untapped slip region, and "five degrees of margin" was a
misreading of a flat curve.

## A word I got wrong

Episode 10 ended by calling the 40%-front car "fragile." That was wrong, and this
experiment is what made it obvious.

Fragile means it fails when something goes wrong. The 40% car fails when **nothing**
goes wrong — 0% deployed finish rate with no disturbance at all. It is not a
knife-edge car, it is a car this driver cannot drive. Those are different problems
with different fixes, and collapsing them into one word cost the distinction. The
figures put it off the chart with the reason stated rather than plotting it at a lap
time it never set.

## What this can't tell you

**The claim is scoped to 47-65% front, and to this driver.** The 40%-front car is
absent because the policy cannot drive it *unperturbed* — 0% deployed finish rate
with nothing going wrong. That is not fragility, it is a car outside this driver's
competence, and Episode 10 called it "fragile," which was the wrong word.

**"Fragile for this driver" is the honest form.** I checked whether the policy is
simply *better* at nose-heavy cars, which would fake this whole result: relative to
what the solver achieves on the same car, it actually gets **further** from the limit
as the car gets nose-heavy. So the confound points the other way — it is relatively
better at the rear-biased cars, and those are the ones that fail. But that test is
indirect, because lap-time ratio measures pace, not disturbance rejection. A car can
be quick in a policy's hands and still be one it cannot catch.

**Every failure rate is a lower bound.** Laps that both failed and left the tire
fit are discarded, and some were genuine crashes. The ranking is robust to that;
the numbers are floors, and the report counts how many laps each cell had to drop.

**The ±12° bound is ours, not physics.** It is where the tire file's fit ends. A
sharper answer needs tire data past that, which we do not have, and no amount of
solver or policy work substitutes for it.

**One disturbance shape each.** Gaussian per-step steering noise and a per-lap
uniform grip scale are two guesses at what "a bad day" means. A gust, a kerb, a
damp patch part-way through a corner, or a driver with a slow reaction time are all
different disturbances and could rank designs differently.

**Still one training seed.** Episode 11 inherits Episode 10's policy and therefore
Episode 10's single seed, and Episode 10's D6 failure (`exploration_is_not_growing`)
applies here unchanged. Nothing in this episode is a claim about what PPO does in
general.

**Forty rollouts per cell.** Every rate carries a 95% Wilson interval, and at
n = 40 an observed 0% is consistent with a true rate up to about 9%. "No failures"
means "no failures in forty laps", which is not the same as "cannot fail".

## The crack

Season 3 set out to build a driver and ask it a question a solver could not answer.
It built one, the question got an answer, and the answer is the one every racer
already knows in their hands: the quick setup is the one that bites.

What is new is not the conclusion. It is that the conclusion now falls out of a
tire model, a four-wheel car and a driver that learned to drive by crashing — with
no human intuition anywhere in the chain. That is worth more than being told it.

And it points somewhere specific. Every driver in this series so far — solver and
policy alike — has been handed a fixed car and asked to make the best of it. None
of them could change the car while driving it. A fragile car is one that needs a
correction the driver cannot make in time; the alternative is a car that makes the
correction itself.

That is what a differential does, badly, and what torque vectoring does on purpose.
Season 4 starts there.

---

**Fidelity: rung 2, one learned driver, one training seed.** Everything here is 'fragile **for this driver**' — a different policy, or a better one, could rank these cars differently. The double-track model's missing suspension terms are also the terms that would most change how a real car behaves at the limit.

## Reproducing this

```bash
python -m experiments.ep11.run
```

Trains nothing. Loads `experiments/ep10/out/policy.pt`, runs five designs across
five disturbance conditions at 40 deployed rollouts each — about fifteen minutes on
a laptop CPU — and writes the figures. `--quick` runs a three-design wiring check.
`--figures-only` redraws from `results.json`.

**Numbers quoted above** are `[MEASURED]` from Episode 10's policy driving
`physics/rl_env.py` on the four-wheel model with the Project Chrono tire, offsets
removed, deployed (mean action, no exploration noise — F61).

**Both disturbance magnitudes are `[ASSUMED]`.** Steering noise is in normalised
action units; grip is a multiplier on peak lateral friction applied through
`[SCALING_COEFFICIENTS]`, never by editing a fitted `P*` coefficient. They were
calibrated at 40 rollouts per cell after a 10-rollout calibration produced a
retracted conclusion — see F70.

**Rule 4 is applied per lap.** `trial()` records `(finished, worst_slip)` for every
rollout, and `failure_rate_inside_fit` counts only laps that never exceeded 12° of
slip. `results.json` keeps the per-lap pairs so any other metric can be recomputed
without re-running.

**Two standing checks guard the claim.**
`a_speed_fragility_tradeoff_is_measurable_inside_the_fit` would fail if the effect
vanished, and `the_faster_car_is_the_more_fragile_one` asserts the *ordering* rather
than merely the existence of failures — a scrambled ranking would be a tradeoff you
could not act on.

Full provenance: `FINDINGS.md` F70, plus F63 on the envelope penalty that caused
this, F61 on why every number is the deployed policy's, and F69 on the inherited
D6 failure.
