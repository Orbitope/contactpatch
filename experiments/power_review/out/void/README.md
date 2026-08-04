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
