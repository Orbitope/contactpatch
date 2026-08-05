# Void run — POWER-REVIEW Phase 3, first attempt

Kept, not deleted, because the failure is instructive.

This 112-minute run trained on nothing. A `speed_mean` logging line added to
`physics/ppo.py`'s scalar path had captured the `e.reset(...)` call under
`if "speed" in info:` — true on **every** step — so the environment was reset
after every single step. Every episode was one step long, `done` never fired,
and `episodes_finished` stayed **0 across all 1,220 updates**.

Nothing in the loss curves looked wrong. EV sat at +0.097 and the D6 gate
caught *that*, but the gate only says "the critic did not learn" — it does not
say why, and the actual cause was that there was nothing to learn from.
`episodes_finished == 0` was the only signal, and it was in the history the
whole time.

`tests/test_rl_env.py::test_ppo_scalar_path_lets_episodes_run_to_termination`
now pins it, and was verified to fail against the broken code before being
trusted.

**Do not cite any number in these files.**

## Second void run — `phase3_VOID2_run.log`

Trained correctly (EV +0.791, passed D6) but its fragility table is not
usable, for the reasons in FINDINGS F117: the two "successful" designs ran at
12.1–16.7° of slip, outside the 12° tyre fit, and 0.61's 75% failure rate was
a steering bug — all 48 failures at s = 74–76 m (sd 0.5 m) at 1.6° slip, off
the road on the entry straight with the tyres idle.

Superseded by the `phase3_1x_*` / `phase3_2x_*` pair, which add
`cross_track_penalty` (the measured cause) and raise `envelope_penalty` to
F107's value, and which run **both** power levels under that same reward so
the comparison is power rather than power-plus-reward.

## Third void run — `phase3_1x_*`

Trained fine (EV +0.443, passed D6) and is still not usable, for two reasons
found only by comparing against Episode 10's own committed policy:

1. **The design set omitted 0.40**, which is where Ep11's 1× fragility
   actually lives (90–100% failure there, ~13% at 0.47, 0% elsewhere). The
   sweep measured four designs that are all fine at 1×.
2. **`cross_track_penalty=2.0` made the policy corner harder.** In an
   identical clean evaluation env it slides 9.6–10.5° where Ep10's original
   slides 5.7–6.0°. Denied the racing line it must hold a tighter effective
   radius. It was added to fix a 0.61 steering spike that does not exist in
   the original policy at all.

Superseded by a run using Episode 10's own reward and the full design set.

## ATTEMPT4_* — the 1x leg that trained without start jitter (2026-08-04)

Voided by the baseline gate, automatically, which is the first time that has
happened rather than being discovered afterwards.

**Symptom.** 0/60 failures at every design, where Episode 10's own policy
fails ~90% at 0.40 — and worst slip of **169.1°** at 0.40 against Episode
10's 7.1°. A car at 169° of slip is spinning, not driving. Every row was
outside the 12° fit, so the whole table was unquotable under rule 4 in any
case.

**Cause.** `_cfg()` did not set `start_jitter_m`; Episode 10 trains with
10.0 m. A field-by-field diff of the two `EnvConfig`s found it — reward,
design range, PPO budget and seed all matched, and only this and `drive_max`
(`None`, which resolves to the same 4500 N) differed. Without jitter every
episode starts at the same point, so a degenerate spinning solution survives:
it only ever has to work from one start.

**Why it matters beyond this run.** Three previous attempts were voided for
reasons found by hand, after the fact. This one was caught by the run itself,
before any of its numbers were interpreted. The gate is cheap and it works;
the lesson is that "I matched the reward" is not the same as "I matched the
configuration", and only a mechanical diff establishes the second.

## CRAWLER_* — the 2x leg that stopped driving (2026-08-05)

**Symptom.** 0/60 failures at every design, worst slip 0.4-0.8°, envelope
occupancy 0.0000 — and a **mean distance of ~20 m on a 393 m track.** The
policy collapsed over the last fifth of training (`return_mean` 393 -> 330 ->
46.6 -> 30.3 -> 20.7 -> 20.1) into something that barely moves. Its perfect
failure rate means "never got anywhere", and its low slip means "barely
turns".

**It passed the gate that had just been written to catch bad runs.** Check A
asked for slip inside the fit, zero envelope occupancy and a live critic. A
stationary car satisfies all three trivially: it has no slip, cannot leave the
envelope, and gives a critic a constant return to predict. Slip and occupancy
constrain *how* a policy drives and say nothing about *whether* it does.

**Fix.** Check A now requires the best design to cover >=90% of the track.
This is D6's `the_deployed_policy_completes_the_task`, which the gate should
have carried from the start — F61 is the same failure in Season 3, where
Episode 9 was written around an 88% sampled finish rate whose deployed figure
was 0%.

**Threshold detail worth keeping.** A first version used the *minimum* mean
distance across designs and rejected the valid 1x leg, whose 0.65 design
genuinely fails 20% of the time. "Can this policy drive at all" is a question
about its best design; "does it drive every design" is what the fragility
table measures. Using the max separates them.
