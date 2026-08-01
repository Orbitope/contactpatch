# The two-stage driving curriculum

How a policy is trained to drive a circuit here, why each stage exists, and
what to change when applying it to a new track. Written so the other 23
circuits do not require re-deriving any of it.

`docs/` is reference-only per CLAUDE.md; this lives at the root because it is
a working document that will change as the recipe is applied elsewhere.

---

## The problem this solves

Plain PPO with a progress reward does not learn to drive a real circuit. It
drives faster than it can control, crashes at 100% of start positions, and no
amount of reward-coefficient tuning fixes it (nine variants tried; see
FINDINGS F104-F108). The two failures underneath are:

1. **It cannot hold a line.** Without a centreline term, lateral position is a
   random walk with an absorbing barrier at the track edge. The policy drifts
   off on *straights* — measured at 3,934 m radius, 1.4° slip (F108).
2. **It drives past its own competence.** The progress reward pays immediately
   for speed; braking pays later, and only if the corner is then taken
   correctly. It learns the first half and never the compound second half.

## Stage 1 — learn to hold a line

`experiments/tracks_pilot/spa_curriculum.py`

**Speed cap as a limiter on the action**, not a reward term: above the cap the
policy may coast or brake but not accelerate. A limiter cannot be traded away
against progress, which is the point — every reward-shaped attempt at this was
traded away.

Start the cap **below the tightest corner's own limit** so no corner is
unsurvivable from step one: `v = sqrt(a_lat_max / kappa_max)`. For Spa
(r = 11.4 m, ~0.97 g) that is ~10.4 m/s, so `CAP_START = 9.0`.

**`cross_track_penalty` is the term that makes this work at all.** Every dense
reward in the racing-RL literature has one and this project's did not:
Jaritz `v(cos a − d)`; Evans CTH `(v/v_max)cos psi − d_c`; TC-Driver
`progress − |n|`. Swept: **2.0 is right**; 5.0 travels further before crashing
but puts 24/24 sections outside the tyre fit and is not quotable. Not
monotone — do not assume higher is safer (same shape as F107).

Raise the cap on **mastery or plateau**, freeze on **degradation** or when
already at the tyre limit. The plateau arm is load-bearing: a pure mastery
gate never fires, because a "section" is a whole lap and crash-free is rare
early on.

**Stage 1 output for Spa:** 100% lap completion from all 48 probes, 0 sections
outside the fit, 537 s.

## Stage 2 — learn where the limit is

`experiments/tracks_pilot/spa_pushlimit.py`

**Stage 1's output is not a driver.** Measured against what the car can do:

| | stage 1 policy |
|---|---|
| fraction of grip-limited speed used | 28.9% mean, 21.7% median |
| above 90% of the limit | 1.2% of the lap |
| mean slip angle | 0.3° (tyres peak 8–12°) |
| speed standard deviation | 0.29 m/s — no modulation |
| lap time | 537 s vs ~135 s at the limit |

It follows the road with the throttle pinned and lets the limiter do the rest.
It knows nothing about braking points, the friction limit or the racing line —
and **torque vectoring is meaningless at 29% of the limit**, which makes stage
1 alone useless for Seasons 4–5.

**Warm-start from stage 1** (holding a line is worth keeping) and raise the cap
until **grip binds instead of the limiter**.

**The gate is the difference.** Stage 1 raises on mastery-or-plateau, which
stalls at a cap the policy is merely pinned against. Stage 2 measures *which
constraint is active*:

* mean speed within `CAP_BINDING_RATIO` (0.90) of the cap → **the limiter is
  what is holding it back** → raise
* below that for `CAP_RELEASE_PATIENCE` (4) updates → **the policy is choosing
  its own speed** → grip binds, freeze the cap, done

This is a direct measurement rather than a proxy, and it is self-terminating:
the curriculum stops when it has achieved its purpose rather than at a
hand-set ceiling.

The slip guard sits at the **real 12° bound**, not stage 1's conservative 10°:
driving at the limit *means* slip in the 8–12° range, and a guard below that
stops the curriculum before the regime it exists to reach. `envelope_penalty`
does the work of keeping it inside.

---

## Applying this to a new circuit

1. **`CAP_START`** — recompute from that circuit's own tightest corner, do not
   reuse Spa's. `sqrt(7.6 / kappa_max)` is the working formula.
2. **`cross_track_penalty`** — 2.0 is measured on Spa only. Confirm on one fast
   and one tight circuit before trusting it everywhere; if it does not
   transfer it is a Spa constant, not a finding, and needs sweeping per band.
3. **`max_steps`** — must exceed `track.length / cap / dt`, with margin. At 9
   m/s a 7 km lap is ~39,000 steps.
4. **Everything else** carries over: `envelope_penalty=6.0`, `off_track=5.0`,
   `stall=2.0`, `progress_scale=1.0`, `edge_penalty=0.15`, γ=0.995,
   `n_envs=256`, `entropy_anneal=True`.

## Rules that are not negotiable

* **Score with `policy_eval.py`.** Never write a per-run evaluator (D16). A
  `finished` bug survived ~20 runs precisely because every result had its own
  throwaway harness.
* **Evaluate a checkpoint at the configuration it was selected under** — not
  at whatever the curriculum reached by the end (F109).
* **A result with any probe outside the 12° fit is not quotable** (rule 4).
  `EvalResult.headline()` enforces this; do not work around it.
* **≥3 seeds before any of it is a trend** (rule 5). Everything measured so far
  is one seed.

---

## Why the gates get tested by replay, not by smoke test

Four bugs in this curriculum's gate logic reached a full training run before
anyone noticed:

1. the selected checkpoint scored at the curriculum's **final** cap, not the
   one it was trained under (F109)
2. the cap **raised past the policy's competence** and destroyed it —
   `eval_return` peaked at 3521 and ended at 741
3. the release **latched** at update 49, mid-adaptation, freezing the cap for
   the remaining 195 updates
4. the gate read `speed_mean`, which PPO **did not record** — it would have
   read NaN forever and never fired

Every one of them was smoke-tested first, and every smoke test passed. That is
the lesson: **a smoke test proves the code runs; it cannot exercise a feedback
loop whose failure appears at update 49.** Running one and calling the gate
validated is the mistake, not the smoke test itself.

`tests/test_curriculum_gate.py` drives the gate with synthetic update records
describing behaviours we know matter — a policy slowly learning to use new
headroom (the measured 85%→97%-over-60-updates shape), one genuinely at the
grip limit, one already outside the tyre fit — and asserts what the cap does.
It reproduces the 75-minute failure in 1.6 seconds, and both of the relevant
tests were confirmed to **fail against the old gate** before being trusted.

**Any new curriculum gate gets a replay test before it gets a training run.**
