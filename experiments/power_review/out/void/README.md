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
