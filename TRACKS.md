# Real tracks — plan

**Goal.** Replace the single made-up 40 m corner with recognisable circuits, so
the series can say "Spa" rather than "a 90 degree left-hander". Readers know
real tracks; a synthetic corner is a diagram, a real one is a place.

**Why now.** The batched environment (`physics/batched_env.py`) made training
~29x faster end-to-end. A real circuit is 10-20x longer than the current 393 m
lap, so it was not affordable before and is now.

---

## 1. What the code actually needs

The physics reads **three things** off a track, and nothing else:

| | used by |
|---|---|
| `curvature(s) -> kappa` | the curvilinear kinematics in `rl_env.step`, the optimal-control solver, the driver's preview |
| `length` | episode termination |
| `half_width` | on-track/off-track test, observation normalisation |

`centreline()` and `to_xy()` exist only for drawing.

**So a real circuit drops in behind the existing interface.** It does not need a
new physics path — it needs a `Track`-shaped object whose `curvature(s)` comes
from sampled data instead of `Segment` arithmetic. Sketch:

```python
class SampledTrack:            # same surface as physics.track.Track
    def __init__(self, name, s, kappa, half_width, closed=True): ...
    def curvature(self, s):    # interpolate the sampled kappa
    @property
    def length(self): ...
```

**Three things the current `Track` cannot express and a real circuit needs:**

1. **Closed loops.** Every existing track is an open strip with a start and an
   end; `finished = s >= length` terminates the episode. A circuit is a lap, so
   `s` has to wrap and "finished" becomes "completed a lap".
2. **Variable width.** `half_width` is a scalar. Real circuits vary from ~5 m to
   ~12 m half-width, and the narrow parts are where the interesting driving is.
   This has to become `half_width(s)`.
3. **Elevation and banking.** Not modelled at all, and not in scope — but they
   are real, and a lap time from a flat model of Spa should say so out loud
   (rule 15). Eau Rouge without elevation is a different corner.

---

## 2. The measured risk: curvature is a second derivative

**This is the part that will go wrong if it is not designed for.** Most track
datasets publish centreline **coordinates**, not curvature. Getting kappa from
x, y means differentiating twice, and that amplifies noise brutally.

Measured, by round-tripping our own `long_exit()` track through the conversion
(so the right answer is known exactly):

| centreline data | max curvature error | against a corner kappa of 0.025 |
|---|---|---|
| clean | **1.16e-05** | 0.05% — the conversion itself is correct |
| + 2 cm noise, finite differences | 9.73 | **390x the signal** |
| + 2 cm noise, boxcar-smoothed heading | 0.45 | 18x the signal |
| + 2 cm noise, tuned smoothing spline | 0.013 | 53% |
| + 10 cm noise, tuned smoothing spline | 0.027 | 107% |

`[MEASURED]` — the noise model is deliberately pessimistic (independent noise on
4,000 points spaced ~0.1 m; real survey data is sparser and often already
fitted), so treat the numbers as an upper bound on the difficulty rather than a
prediction. The **ordering** is the point and it is not sensitive to the model.

**Consequences for source selection, in priority order:**

1. **Strongly prefer a dataset that publishes curvature directly**, or one that
   publishes a *fitted* centreline rather than raw GPS. Racing-line optimisation
   datasets usually do, because they need curvature for the same reason we do.
2. If only coordinates are available, fit properly (smoothing spline or
   piecewise arc fit) and **validate the recovered curvature against an
   independent number** — published corner radii for that circuit — rather than
   against our own fit. That is rule 2, and this is exactly the situation it
   exists for.
3. Whatever is used, the round-trip test above becomes a permanent test: take a
   track, sample its centreline, recover kappa, compare. It caught the noise
   problem before any real data was touched and it will catch a bad import.

---

## 3. Candidate sources — surveyed

### Recommended: `TUMFTM/racetrack-database`

<https://github.com/TUMFTM/racetrack-database> — **LGPL-3.0**, **25 circuits**
including **Spa, Monza, Silverstone, Suzuka**, Zandvoort, Sakhir, Catalunya,
Nürburgring.

| | |
|---|---|
| format | CSV, header `# x_m,y_m,w_tr_right_m,w_tr_left_m`, **metres** |
| sampling | uniform **5.00 m**, closed loop, endpoint not repeated |
| verified | Spa 1401 pts / 7000.1 m; Monza 1159 / 5790.2 m; Silverstone 1178 / 5886.8 m; Suzuka 1161 / 5802.9 m — all within ~0.2% of published lap lengths |
| widths | **asymmetric** left/right about the centreline. Spa total 9.77 m mean (7.87–16.42) |
| missing | **no curvature, no banking, no elevation** |

Everything else in this space is downstream of it, unlicensed, or unsuitable:

- **`f1tenth/f1tenth_racetracks`** (GPL-3.0) is an explicit 1:10 downscale of
  TUM with the real widths replaced by a constant 2.20 m. Its racing-line files
  *do* ship `kappa_radpm` pre-computed — but for the racing line, at 1:10, with
  a fictional width. Stronger copyleft, worse data: go upstream.
- **`TUMRT/sampling_based_3D_local_planning`** (GPL-3.0) ships κ(s) **and
  banking** already in our target form — but only Las Vegas Motor Speedway and
  Mount Panorama. Worth remembering if banking is ever wanted; not
  reader-recognisable in the Spa/Monza sense.
- **RACECAR / Indy Autonomous** is CC BY-NC sensor data, not track geometry.
- **AWS DeepRacer**, **CPS-TUWien/f1tenth_maps**, **nkapania/Wolverine** — no
  licence file at all. Unusable regardless of content.
- **OpenStreetMap directly** — ODbL, and a live Overpass query over Spa returns
  35 `highway=raceway` ways with named corners but **zero width tags**. That is
  the raw material TUM already processed; only worth it for a circuit TUM lacks.

### The curvature trap, confirmed twice

Independently of the round-trip measurement in section 2, the survey measured
naive finite-difference curvature on TUM's raw 5 m Spa points: **max |κ| =
0.0963 1/m, i.e. a 10.4 m minimum radius, where La Source is really ~25 m.**
Monza came out at 10.8 m. A 9-point moving average only reaches 19.4 m and
22.9 m respectively — still wrong.

So: **a periodic cubic-spline fit, arclength reparameterisation, then analytic
κ.** TUM publish exactly this as
<https://github.com/TUMFTM/trajectory_planning_helpers> (LGPL-3.0, pip
installable): `calc_splines.py`, `calc_head_curv_an.py`, `interp_track.py`.
Either use it or reimplement it, but do not `np.gradient` the coordinates.

**Validation gate (rule 2):** recovered corner radii checked against published
figures for that circuit — La Source ~25 m, Monza's Parabolica, etc. Our own
fit does not get to certify itself.

### Licensing, and how to stay clean

1. **Chain mismatch.** TUM ships LGPL-3.0 (a *software* licence) over data
   derived from **OpenStreetMap**, which is **ODbL** with share-alike.
   **Recommendation: do not vendor the CSVs.** Ship a small downloader plus our
   converter, keep only our own code in the repo, and attribute both TUM and
   OSM. That sidesteps the whole question.
2. **Circuit silhouettes are registered trademarks** — confirmed on the
   Nürburgring's own licensing page (EU figurative marks, EUIPO and DPMA).
   Naming a circuit and drawing its layout to illustrate an engineering result
   is ordinary identifying use; using an outline as a logo, cover art or
   merchandise is not.
3. **Operators assert IP over geometry data** in commercial licences (the
   IMS/Motorsport Games agreement covers topographical maps, CAD and LiDAR).
   The primary documents returned HTTP 403 and this is search-snippet evidence,
   not verified quotation — but the practical line is clear: laser-scan-grade
   geometry is licensed commercially; OSM-traced approximations are a different
   thing and are what TUM publishes.
4. **Sim-racing mod data (Assetto Corsa, rFactor, iRacing) is not a source.**
   iRacing's are laser-scanned under commercial licence; community mods have no
   clear provenance. No authoritative statement of mod redistribution terms was
   found, so this is "assume not redistributable" rather than a verified finding.

None of this is legal advice.

### Two things to record in FINDINGS when adopted

- Widths are `[SOURCED]` from **satellite image processing**, and TUM's own
  README warns their quality "varies greatly depending on the location". Spa's
  9.8 m mean total width looks low against the real circuit — low confidence.
- TUM state the smoothed centreline "does not lie perfectly in the middle of the
  track anymore", which is why left and right widths differ. Collapsing them to
  one symmetric `half_width` is a modelling choice and has to be said out loud.

---

## 4. Staging

1. ✅ **DONE** — `SampledTrack` (`physics/track.py`) + the round-trip test
   (`tests/test_sampled_track.py`, 6 tests, all passing) validated against
   `long_exit()` where the curvature answer is known exactly. Two real bugs
   caught by the round-trip test itself before any external data was
   touched, exactly per §2's stated purpose:
   - `per=True` was hardcoded (correct for a real circuit, a closed loop)
     but silently doubled the fitted length when validated against the
     deliberately-open `long_exit`. Fixed with a `closed: bool` parameter,
     `True` by default for real circuits, `False` for open test tracks.
   - An untuned `smoothing` constant (0.05) recovered curvature *worse*
     than the naive finite-difference trap it exists to beat (err 42 vs.
     8.7 against the corner's 0.025 signal). scipy's own unweighted-data
     convention, `s ~= m` (the point count), matched this doc's own
     measured "tuned smoothing spline" row almost exactly (err 0.015 vs.
     0.013) — smoothing must scale with point count, not be a fixed
     constant. Recorded in the class docstring so real-data import starts
     from `s = len(x)`, not another guess.

   No external data yet — that is step 3.
2. ✅ **DONE** — closed-loop support: `s` wrapping, lap counting,
   `half_width_at(s)`. Two more real bugs caught by tests before anything
   drives a real circuit:
   - `rl_env`'s and `batched_env`'s curvature-ahead preview clamped the
     lookahead to `track.length`, flattening it to a single repeated point
     right where a closed track's driver most needs to see the next corner
     coming (the same clamp `driver.TrackLocator.preview` already had a
     documented, deliberate reason for on an OPEN track — closing the loop
     makes that reason not apply). Both now skip the clamp for
     `track.closed` and let the track's own `s % length` wraparound
     (`SampledTrack._u_of_s`) supply the right answer.
   - A synthetic closed-circle regression test for `driver.drive_lap`
     (`tests/test_driver.py`) found that `s` from `TrackLocator.locate` is
     bounded to `[0, length)` on a closed track — "where on the road", not
     a cumulative distance — so a naive `s >= length * n_laps` finish check
     can never fire, and a naive "big backward jump = one lap" wrap counter
     misreads the one genuinely ambiguous point on a loop (the start line,
     where `s=0` and `s=length` are the same physical point, so the very
     first fix can land on either). Fixed with a running sum of each step's
     *shortest signed circular delta* from the previous `s`, which resolves
     the start-line ambiguity to ~0 distance however the tie breaks, rather
     than reading it as an instant finish.
   - `half_width` also gained a `SampledTrack` implementation that
     interpolates a per-point `width` array along arclength (with its own
     wraparound at the seam), not just the constant fallback — validated by
     a round-trip test against a known width function, the same
     known-ground-truth pattern step 1 used for curvature.

   `Track` and `SampledTrack` both went from a plain `.half_width` scalar
   attribute to a `.half_width_at(s)` method; every caller in `rl_env.py`,
   `batched_env.py`, and `driver.py` was migrated, `Track`'s own returning
   the old scalar broadcast unchanged. `EnvConfig.n_laps` and
   `drive_lap`'s `n_laps` argument both default to 1, reproducing every
   existing open-track call exactly. **Not done**: `SpeedProfile`'s
   backward/forward passes still plan one lap only (`s` in `[0, length]`);
   multi-lap corner-braking continuity across the seam is deferred to
   whenever a real circuit's speed plan is actually needed (step 3+), same
   for `drive_lap`'s implicit assumption that the car starts at the world
   origin with heading 0 — true of every synthetic `Track` here by
   construction, but not automatic for a real circuit's raw coordinates.
3. ✅ **DONE** — Spa-Francorchamps, via `physics/tracks_data.py`
   (`download_track_csv` + `load_real_track`, not vendored — see
   `.gitignore` — fetched from TUM's `racetrack-database` on first use,
   cached in `physics/tracks_cache/`).

   **Validated against `[SOURCED]` figures, not our own fit (rule 2):**
   recovered `length` 6999.5 m against the Grand Prix layout's published
   7.004 km / 19-20 corners (consistent across multiple independent race
   reports) — **0.064% error**. No independently-published per-corner
   radius was found for La Source during this work despite several
   searches — general descriptions call it "tight" and "first gear" but
   give no number, and this doc's own prior "~25 m" has no citation either,
   so it is **not** used here as if it were external. The recovered minimum
   radius (11.4 m) is reported `[MEASURED]` only, checked for physical
   plausibility against a modern FIA circuit's typical tightest-corner range
   rather than a hard published number — that gap is stated, not papered
   over. Bounding box (1270 m × 2040 m) is also consistent with the real
   circuit's footprint, a cheap independent sanity check.

   **A real bug, found by measuring rather than reusing step 1's own
   convention:** `smoothing=0.0` (exact interpolation) looked like the
   right default going in — TUM's centreline is a processed racing surface,
   not raw noisy GPS — but measured directly, it fit a 5.8 m minimum
   radius, tighter than anything on the real circuit, because 5 m point
   spacing still carries enough residual irregularity for an
   exact-interpolating spline to read as a spurious sharp corner. A sweep
   (`smoothing` 0 to 1401) found `length` within 0.05-0.25% of published
   throughout and minimum radius stabilising to a plausible 9-11.5 m for
   `10 <= smoothing <= 300`; step 1's own `s ~= m` convention (1401 here)
   turned out to be **too much** smoothing for this dataset — different
   point spacing and noise character than the synthetic test it was
   measured on — worse length match and a washed-out corner. `20.0`
   (`DEFAULT_SMOOTHING` in `physics/tracks_data.py`) sits inside the
   plausible plateau. The lesson generalises the same way step 1's did:
   don't reuse a smoothing value measured on different data, measure again.

   5 tests (`tests/test_tracks_data.py`), skipped cleanly rather than
   failed when TUM's GitHub is unreachable — an external dependency this
   project does not control should not hard-fail CI/offline runs.
4. ✅ **INVESTIGATED — no code defect, the real work turned out to belong to
   step 5.** Checked `batched_env.py`'s buffers, `TrackLocator`'s window
   search, `EnvConfig.max_steps`/`drive_lap`'s `max_steps`, and PPO's
   reward/log accumulation for anything hardcoded to a ~1,000-2,000-step
   episode. Nothing is: `max_steps` is already a config value, no buffer is
   shaped off it, `TrackLocator`'s `window` is in metres (track-length
   independent), reward has no episode-length normalisation to break.

   What "the episode budget needs revisiting" (this step's own words)
   actually means, found by looking rather than assumed: three **training
   hyperparameters**, not infrastructure —
   - `physics/ppo.py`'s `rollout_steps=512` is smaller than even the OLD
     `max_steps=2000` cap; against a ~10,000-step Spa lap almost no episode
     would complete inside a rollout window, so `finished_returns`-derived
     stats (`return_mean`, `off_track_rate` — exactly what D6/rule 4 read)
     would sit `nan` for most of training.
   - `total_steps` (300k/1.2M/5M across `ppo.py`/ep09/ep10) buys an order of
     magnitude fewer COMPLETED laps on a track 5-18x longer, at unchanged
     step budget.
   - `gamma=0.995` (4 s effective horizon) was already short against the old
     26 s lap; against Spa's 10+ second straights it cannot connect
     corner-exit speed to its payoff at all.
   - **Bigger, adjacent finding**: no experiment script (`ep09`-`ep11`)
     actually routes through `batched_env.py` yet — every one constructs
     plain single-instance `DrivingEnv`s. `BatchedDrivingEnv` exists,
     is tested, and is exactly what a 10,000-step-lap training budget would
     need for throughput, but nothing wires it into a training run.

   None of these are guessable without a real training run to calibrate
   against (rule 9 — a modelling choice measured, not assumed), and every
   one is inseparable from actually retraining on a real circuit. They are
   step 5's work, not a separate step 4 — recorded here rather than
   invented a number for now.
5. **Retrain — scoped below, not yet run.** A real circuit changes what "a
   lap" costs, so every step-count and wall-clock number in Season 3 and 4
   is re-derived, not inherited. This is Episode 19's own subject
   (SEASON5.md §4), not a detour — this section is that episode's technical
   prerequisite, written before any run so the choices are on the record
   and checkable, per rule 9.

### Step 5 scoping (measured, nothing launched)

**1. `BatchedDrivingEnv` already works on Spa, checked directly.** Built
one with `EnvConfig(track=load_real_track("Spa"), max_steps=12000)`,
stepped it: no crash, no NaN in the observation, `closed`-track wraparound
(step 2) behaves as expected. No plumbing gap here — the gap is that no
experiment script passes `make_batched_env` to `ppo.train()` yet, even
though `train()` has accepted it as an optional argument all along.

**2. The batched speedup is real, measured on this machine, and bigger
than assumed going in — but not for the reason first assumed.** A first
pass compared batched aggregate throughput divided by `n_envs` against
single-instance throughput and found batching apparently *losing* by
~10x — alarming enough to stop and re-derive rather than write it down.
The error was the comparison, not the code: running `n_envs` single-instance
`DrivingEnv`s **sequentially** (`ppo.py`'s current unbatched path, one
Python `.step()` per env per rollout tick) does not parallelise on one
core — measured directly, `n_envs=8` sequential gives **2,648
instance-steps/s aggregate**, statistically the same as ONE instance alone
(2,699 steps/s). Aggregate sequential throughput is flat regardless of
`n_envs` — it has to be, it's the same core doing proportionally more
work in proportionally more wall-time. That is the correct baseline to
compare against, not "aggregate ÷ n_envs".

Against that baseline, measured on Spa specifically (not the old track):

| `n_envs` | instance-steps/s | speedup vs. 2,700 sequential |
|---|---|---|
| 8 (batched) | 4,831 | 1.8x |
| 256 | 78,559 | 29.1x — matches this doc's prior "29x" estimate |
| 1,024 | 127,143 | 47.1x |
| 4,096 | 157,709 | 58.4x (strongly diminishing) |

`n_envs=1024` is the reasonable working point: past it, throughput keeps
rising but the PPO rollout buffer (`[rollout_steps, n_envs, obs_dim]`)
grows just as fast for shrinking return.

**3. What this means for wall-clock, concretely.** Matching Episode 10's
own experience budget (`total_steps=5,000,000` at ~1,300 steps/lap ≈ 3,846
completed laps across training) on a ~10,000-step Spa lap needs ~7.7x more
total steps to buy the same number of completed laps: **~38.5M steps.**
Env-stepping cost alone (excludes the PPO gradient update, not yet
measured for this setup):
- **Unbatched (today's path): 38.5M / 2,700 ≈ 4.0 hours**, and that is
  BEFORE the ≥3 seeds × 2-3 tracks SEASON5.md §7 already calls for — this
  is where "multi-overnight" comes from if nothing changes.
- **Batched, `n_envs=1024`: 38.5M / 127,143 ≈ 5 minutes.**

Wiring `make_batched_env` into a Spa training script is not an
optimisation, it is the difference between a run that fits in an
afternoon and one that does not fit in a week once seeds and tracks
multiply. This is the one item from step 4's list that is unambiguous
without a pilot.

**4. Hyperparameters that ARE guesses until a pilot confirms them (rule
9 — proposed starting points, not final answers):**
- `gamma`: `0.995` (4 s effective horizon, already short against the old
  26 s lap) cannot connect corner-exit speed to its payoff across Spa's
  10+ second straights. Proposed starting point: `0.999` (≈1,000-step /
  20 s horizon). Needs a pilot to check learning stability at the higher
  variance this trades for.
- `rollout_steps=512` is under 1/19th of a Spa lap — most episodes will
  not finish inside a rollout window, so `finished_returns`-derived stats
  go `nan` for long stretches. Two candidate fixes, not yet chosen between:
  raise `rollout_steps` toward a multiple of the lap length (e.g. 12,288 ≈
  1.2 laps), which changes PPO's update cadence and sample efficiency; or
  add partial-episode return/off-track reporting so short rollouts stay
  informative without changing the update cadence at all. A pilot is what
  distinguishes these, not a guess now.
- `total_steps`: ~38.5M is the "same experience budget as Ep 10" starting
  point above, not a validated target — the pilot's job is to check
  whether that budget is anywhere near enough for a track 7.7x longer and
  more complex than a single corner, not just proportionally rescaled.

**5. ✅ Pilot run — `experiments/tracks_pilot/spa_ppo_pilot.py`.** Small on
purpose (not a scaled-down production run): `n_envs=256`,
`rollout_steps=1024`, `total_steps=5,000,000` (19 updates), `gamma=0.999`,
Spa, `envelope_penalty=0.5` (Ep 10's value, kept rather than reinvented).
Wall-clock 106.4 s. Artefacts in `experiments/tracks_pilot/out/`.

**What it answered:**
- **The batched path works end to end on Spa** — no crash, no NaN, across
  19 updates and ~19,600 completed episodes.
- **Measured full-loop throughput: 46,999 steps/s** (env-stepping AND the
  PPO gradient update, not the env-stepping-only 78,559 measured earlier).
  Revises the production estimate: 38.5M steps / 46,999 ≈ **14 minutes**,
  not the ~5 minutes an env-stepping-only number implied — still
  dramatically faster than the ~4-hour unbatched path, just a more honest
  number now that the whole loop has actually been measured once.
- **`gamma=0.999` shows no instability over this run** — `approx_kl` stays
  small (0.0003-0.0018) throughout, `explained_variance` climbs steadily
  from 0.00 to 0.34 rather than diverging or collapsing. Not proof it is
  the right value, but nothing here argues against it either.

**What it did NOT answer, and why — reported honestly rather than
stretched to look conclusive:**
- **The rollout_steps question is not yet testable.** `off_track_rate`
  stayed at 0.94-1.00 for all 19 updates — episodes are ending after ~200
  steps on average (1,295 completions in the *first* 262,144-step update
  alone), nowhere near the ~10,000-step scale a full lap would need. The
  policy is still in "learn not to leave the road within the first few
  hundred metres" territory; it has not yet reached the training stage
  where "does a near-complete lap fit inside one rollout window" would
  even apply. `return_mean` staying informative from update 0 onward
  (never `nan`) is real, but for the wrong reason — episodes are so short
  right now that many fit inside 1,024 steps regardless. The concern
  TRACKS.md raised (long episodes vs. a short rollout window) only becomes
  checkable once a policy exists that reliably survives past the first
  corner or two, which this pilot's budget does not reach.
- **5M steps is not remotely enough to see lap-driving behaviour on a
  ~20-corner, 7 km circuit**, and that is not a surprise stated after the
  fact: Episode 9's single 393 m corner needed hundreds of thousands to
  over a million steps to learn from scratch, and Spa is a different
  problem in kind, not just a longer version of the same one. The "match
  Episode 10's experience budget, scaled by lap-length ratio" heuristic
  behind the 38.5M figure was always flagged as unvalidated (§4 above);
  this pilot did not validate it either, because 5M steps stays entirely
  inside the "surviving the first corner" regime `return_mean` (noisily
  climbing 0 → ~15 across the run) and `explained_variance` (climbing
  0→0.34) both suggest the policy IS learning something — just not
  anything measurable yet against "how much of a lap does it complete."

**Honest bottom line:** infrastructure is proven and one real hyperparameter
(`gamma`) shows no red flags at this scale. Whether `rollout_steps=1024` (or
any other value) is adequate, and whether ~38.5M steps is anywhere near the
right budget for a full circuit rather than one corner, are both still open
— the next informative experiment is a LONGER pilot (order of the full
38.5M, or a defensible fraction of it) with off-track-rate and
episodes-per-update tracked as the health signal to watch for the shift
from "surviving the road" to "surviving whole laps," not a short smoke
test like this one.

**6. Speedup levers, checked directly rather than guessed, before the long
run:**
- ✅ **`n_envs=1024` instead of 256**: measured ~11% faster full-loop
  throughput (52,003 vs 46,999 steps/s in a short comparison). Free, no
  tradeoff. Adopted for the long run below.
- ❌ **Larger `rollout_steps`** (tried 4,096): no throughput benefit —
  measured slightly *worse* (43,569 vs 52,003 steps/s). That knob should
  be chosen for training-statistics reasons, not speed.
- ❌ **Cutting `FIXED_POINT_ITERS` below 6** (`batched_env.py`, the single
  biggest cost inside `env.step()`): investigated and rejected. The
  reference implementation shares the identical 6-iteration cap and, under
  realistic aggressive-driving states, does not actually converge to its
  own 1e-9 tolerance within 6 iterations either (measured: max
  `|Δa_y| ≈ 1.7e-4` even at iteration 6) — cutting further would silently
  diverge from the reference exactly at the grip-limit states that matter
  most for a racing policy.
- ❌ **MPS (Apple GPU) offload** for the PPO gradient update: measured ~2x
  *slower* than CPU (752k vs 1.43M samples/s) — the network (hidden=64) is
  too small for GPU dispatch/transfer overhead to pay off.
- **Real, unexplored tradeoff, not adopted**: `epochs=10` drives
  gradient-update cost roughly proportionally; cutting it would trade
  wall-clock for fewer gradient passes per batch of experience, a genuine
  sample-efficiency cost that would need its own validation before use.

**7. ✅ The long run — `experiments/tracks_pilot/spa_ppo_long.py`.** Full
scoped production budget: `n_envs=1024`, `rollout_steps=1024`,
`total_steps=38,500,000`, `gamma=0.999`, Spa. **632.1 s wall-clock
(10.5 min) — 60,910 steps/s**, faster than either short benchmark, and the
number to use going forward. 36 updates, 93,249 completed episodes.
Artefacts in `experiments/tracks_pilot/out/long_*`.

**This is a real, meaningful training curve, not another flat smoke test:**

| update | steps | `distance_mean` (m) | `off_track_rate` | `return_mean` | `explained_var` |
|---|---|---|---|---|---|
| 0 | 1.0M | 200 | 1.00 | -1.4 | 0.00 |
| 9 | 10.5M | 233 | 1.00 | 16.3 | 0.27 |
| 19 | 21.0M | 254 | 0.52 | 83.2 | 0.52 |
| 27 | 29.4M | 346 | 0.32 | 190.7 | 0.82 |
| 35 (final) | 37.7M | 365 | 0.54 | 173.7 | 0.75 |

`distance_mean` grew from ~200 m to ~365 m (roughly 80%), `off_track_rate`
fell from ~1.00 to a noisy 0.22-0.54 band in the back third of the run
(genuinely improving, not stuck), `explained_variance` climbed to a healthy
0.6-0.83, and `approx_kl` (0.0002-0.0019 throughout) shows no instability
at `gamma=0.999` across the full run. The policy is measurably learning to
survive longer and leave the road less often.

**And this is exactly the evidence that settles §4's open question, in the
direction the numbers actually point:** 365 m final `distance_mean` against
Spa's ~7,000 m length is **~5% of one lap**, after the full "same
experience budget as Episode 10, scaled by lap-length ratio" allowance.
The heuristic behind 38.5M was flagged as unvalidated when it was written
(§4) and this run is the validation — it is a real underestimate for a
20-corner circuit, not a defensible production number. Naively
extrapolating the observed distance-per-step rate to a full lap implies a
budget an order of magnitude or more past 38.5M, which is not a number to
trust from a short linear extrapolation of a noisy, likely-nonlinear
learning curve — but it is enough to say the right next move is not simply
"run 38.5M again," it is either substantially more steps, or a curriculum
change (Episode 9's own "start below the corner speed" trick made an
unlearnable single-corner task learnable — a 20-corner circuit may need
its own version of that idea, e.g. per-section curriculum or reward
shaping, rather than throwing raw steps at the whole lap from a standing
start every episode).

**8. Proposed training schedule (designed, not yet run).** The long run's
diagnosis is a curriculum problem, not (only) a budget problem: every
episode starts in the same first 300 m, so the policy has spent 38.5M
steps learning Spa's opening sector and has never seen the other ~95% of
the circuit except by surviving into it. The fix TRACKS.md's own
observation design already supports: the curvature preview is **local**
(next 55 m), so driving skill learned anywhere on the lap transfers
everywhere — spread the starts.

The load-bearing fact, verified in code rather than assumed:
`BatchedDrivingEnv._reset_mask` already draws `s0` per instance from
`uniform(0, start_jitter_m)`, so `start_jitter_m = track.length` gives
uniform starts around the whole circuit with **zero new environment
code**. On a closed track the existing termination (`s >= length *
n_laps`) then means "drive the remainder of the lap to the start line" —
episode difficulty varies naturally from a few metres to a full lap,
which IS the curriculum gradient, the same shape as Episode 9's
entry-speed trick (make the easy version of the task exist, let the
reward push toward the hard one).

Wall-clock arithmetic uses the long run's measured 60,910 steps/s.

| Stage | What | Budget | Wall-clock | Gate to advance |
|---|---|---|---|---|
| 0 | Warm-start support in `ppo.train()` (accept an initial `state_dict`, D-A pattern: additive, default-off, bit-identical unset) + a smoke test of full-lap jitter semantics on the closed track | code only | ~an hour of work | existing PPO tests still pass; smoke run shows varied start positions and sane terminations |
| 1 | **Learn the road everywhere.** `start_jitter_m = length`, otherwise the long run's exact config | ~40M steps | ~11 min/seed | `off_track_rate` clearly below the long run's 0.22–0.54 band; per-start-section survival roughly uniform (computed downstream from logged `s`, rule 7 — no section left unlearned) |
| 2 | **Stretch to laps.** Warm-start from Stage 1; same uniform starts (starts near `s=0` are full-lap tasks); `eval_every` ON with a from-the-start-line eval env, selection on deployed return (F93) | ~100–150M steps | ~30–40 min/seed | DEPLOYED (mean-action) policy from the start line covers a full lap — D12: the sampled curve counts for nothing here |
| 3 | **Consolidate and measure.** Keep the Stage 2 champion; deployed-policy evaluation from clean standing starts, ≥6 eval seeds (Episode 9's lesson: one harness is not a measurement), D6 gates, envelope occupancy | ~40M steps + eval | ~15 min/seed | D6 passes; envelope rule 4 respected; numbers quotable |

Per training seed: ~200–230M steps ≈ **~1 hour**. Rule 5 demands ≥3
seeds: **~3 hours, an afternoon** — 5 seeds fits an evening. This is why
the batched-path work mattered: the same schedule through the unbatched
path would be ~2 weeks per seed.

Pre-registered contingency (rule 9), so a stall is a decision point and
not an improvisation: if Stage 2 plateaus below lap scale, the forks are
(a) `gamma` 0.999 → 0.9995 (horizon 20 s → 40 s), (b) an entry-speed
curriculum stacked on the start-position one (Episode 9's actual trick),
(c) more raw steps — in that order, one at a time, never blended in a
single run. If Stage 1 itself fails its gate, stop and rethink the
observation (the preview may be too short for 90 m/s straights: 55 m is
0.6 s of lookahead at top speed) rather than pushing budget at it.

Known reporting caveats to carry into the runs, stated now rather than
discovered mid-analysis: `info["episode_distance"]` reports absolute `s`
at termination, not distance covered — with jittered starts those differ,
so Stage 1+ analysis must subtract start positions (downstream from logs,
rule 7); and a car whose draw lands within metres of the line "finishes"
trivially, a rare and harmless dilution of `episodes_finished` worth
remembering when reading that counter.

**9. Stage 1, run once without selection, and a real defect it surfaced —
fixed before trusting the checkpoint.** First run: `n_envs=1024`,
`rollout_steps=1024`, `total_steps=40,000,000`, `gamma=0.999`,
`start_jitter_m=track.length`, no `eval_every`. 990.5 s wall-clock, 38
updates, 86,490 completed episodes. Artefacts kept as
`experiments/tracks_pilot/out/stage1_noselect_*` — evidence, not deleted,
same reason F93 stays in `FINDINGS.md` rather than being quietly fixed and
forgotten.

**The training curve itself caught the problem, read carefully rather than
skimmed for a final number:** `return_mean` climbed to a clear peak of
**834 at update 25** (`off_track_rate` 0.92), then **genuinely declined** —
not noise, a sustained ~12-update regression — to `return_mean` 317-360 and
`off_track_rate` 0.96-1.00 by the final update 37. This is **exactly the
pattern F93 was written about** (Episode 14: "six healthy policies were
reported as non-convergent because only the final weights were saved").
Stage 1's own first run made the identical mistake — `eval_every` was
scoped for stage 2 only (§4 item 8's table), and stage 1 saved unselected
final weights despite the tooling to prevent this already existing and
already being tested (`tests/test_ppo.py`). **Caught by reading the
history, not by the run reporting failure** — `train()` returned
successfully, nothing errored, the checkpoint just was not the best one
produced.

Fixed in `experiments/tracks_pilot/spa_ppo_stage1.py`: `eval_every=2`,
`eval_episodes=8`, `make_eval_env` returning a `DrivingEnv` with
`start_jitter_m = track.length` — matching TRAINING's own distribution
(evaluating from-the-line, stage 2's task, would be selecting on the wrong
question here). Selection wiring smoke-tested against a tiny config before
re-running at full budget (rule: confirm before trusting compute).

**10. The corrected run — selection worked exactly as designed, and the
underlying result is real but modest, not the breakthrough the schedule
hoped for.** 1,149.2 s wall-clock, 38 updates, 86,490 completed episodes.
The training curve shows the **same rise-then-decline shape as the first
run** — `eval_return` climbed to 583.34 at update 32, then the final
updates' `return_mean`/`off_track_rate` show the same late decline the
first run had. **This time it did not matter**: selection correctly held
onto update 32's weights rather than the declined final ones —
`res["model"]` returns the genuine peak, demonstrated concretely rather
than assumed. Checked why the curve is non-monotonic at all before calling
it a new mystery: `log_std` barely moves across the whole run
(steer -2.49→-2.39, drive -0.99→-1.02) — `entropy_anneal=False` (this
project's own documented default: "with a constant bonus the log standard
deviation sits where it was initialised for the whole run, measured,
Episodes 10 and 14 alike") means exploration noise never tightens, so a
noisy, non-monotonic curve is the expected shape here, not a new defect.
Selection is the correct, standard answer to that noise — not eliminating
it, just not shipping from inside a dip.

**Per-section survival of the SELECTED checkpoint**: mean 536.6 m
(std 330.1, range 50.5-1,259.9 m), `off_track_rate=1.00` — every one of
the 24 fixed evaluation points still eventually leaves the road.
**Honestly, this does not cleanly clear the gate as written.** The gate
compared against the long run's 0.22-0.54 `off_track_rate`, but that
number came from the long run's own training-time bookkeeping — mostly
easy, near-start episodes late in an unjittered run — while this is the
DEPLOYED policy dropped at 24 fixed, often-harder points spanning the
WHOLE lap. Those are different populations; the gate as I wrote it did
not anticipate that mismatch, and "clearly below the band" is not a valid
comparison between them. What IS a fair comparison: mean per-section
distance (536.6 m) against the long run's own final `distance_mean`
(365 m) — **~47% more**, a real, direction-confirming improvement, but
still only ~7.7% of Spa's ~7,000 m lap. Stage 1 shows training everywhere
helps generally, not that anything close to lap-scale driving exists yet.

**Where this leaves the schedule**: the pre-registered contingency for a
stage-1 shortfall was "stop and rethink the observation... rather than
push budget at it" — but this is a real fork, not a clear failure calling
for that fallback specifically. The improvement is real and in the right
direction; it is just far smaller than the ~40M-step budget's authors
(this doc, in §4) hoped for, echoing the long run's own lesson that the
"scale Episode 10's budget by lap-length ratio" heuristic underestimates
what a 20-corner circuit needs.

**11. Reward re-tuned by explicit user decision (protocol change, rule
9), grounded in a real decomposition rather than intuition.** Reviewed
the reward structure with the user: progress (`ds·dt`, uncapped, the only
speed incentive there is), `off_track_penalty` (flat, once, default 50),
`envelope_penalty` (proportional to slip beyond 12°, `0.5`, Episode 10's
value). Decomposed 30 rollouts of the corrected stage-1 checkpoint:
`distance - total_reward` averaged **49.90** (std 0.73) — essentially the
entire non-progress cost is the flat off-track penalty, and the envelope
term barely fired (the policy was not yet pushing near the boundary).
**50 points is only ~10% of a typical episode's reward (497.3 mean), and
that fraction shrinks as the policy improves** — a flat penalty against a
growing progress total, weakening exactly as training succeeds. A
structural, not cosmetic, reason a fixed penalty under-deters improving
policies, and a plausible contributor to both stage-1 runs' rise-then-
decline shape.

**Decision**: `off_track_penalty: 50 -> 500` (a much larger, still flat,
fraction of banked reward) **and** `gamma: 0.999 -> 0.9995` (~2,000-step /
40 s horizon) together — the second changes the IMPLICIT deterrent (lost
future reward) to scale with how much of the lap remains, rather than
staying a fixed number that dilutes as episodes lengthen; the two are
meant to reinforce each other, not substitute. `envelope_penalty`
unchanged — it was not the active constraint in either run, no evidence
yet that it needs to be. User's stated priority order for this design:
**staying on track first, viable slip state second, speed third — but
deliberately still pushing the grip limit, since that is the only regime
where torque vectoring has anything to show.** Smoke-tested (tiny config,
no crash, sane negative returns from an untrained policy under the larger
penalty) before the full run. Stage 1 re-run from scratch (not
warm-started) under the new reward, so the comparison against both prior
runs is clean rather than confounded by an old-reward-tuned initial
policy. Previous stage-1 artefacts kept as `stage1_oldreward_*`.

Options going forward once this run reports, not resolved here: (a) more
stage-1 budget if the new reward's own gate still falls short, (b)
proceed to stage 2's warm start and let its own full-lap gate be the real
test, (c) `entropy_anneal=True` as a further contingency if the
rise-then-decline shape persists even under the new reward. Checked with
the user before choosing, since more large compute is the shared cost of
every option.

**12. A second reward defect (`stall_penalty`/`progress_scale` added),
`progress_scale` swept, and a two-phase warm-started confirmation run —
full detail already in HANDOFF.md's Session 25 entries. The headline,
stated plainly because it is easy to miss under "distance keeps
improving": across every reward configuration that actually drives (not
the stalling exploit), per-section off-track rate has stayed in a
**0.94-1.00 band, unmoved by any of this session's reward tuning.****

| configuration | section distance mean | section off-track rate |
|---|---|---|
| `off_track_penalty=50`, `gamma=0.999` | 536.6 m | 1.00 |
| `off_track_penalty=500` alone | 73.4 m | **0.00** — stalling exploit, not real driving |
| `+stall_penalty=150`, `progress_scale=3.0` | 595.2 m | 1.00 |
| `+stall_penalty=150`, `progress_scale=1.5` (two-phase warm start) | **653.5 m** | 0.96 |

The only configuration that ever moved off-track rate did so by teaching
the policy to give up (§4 item 11's stalling exploit) — every
configuration that produces genuine driving has landed in the same
narrow crash-rate band regardless of the specific `progress_scale`. One
genuinely positive detail, not noise: the single per-section probe whose
remaining distance to the lap end was short enough to actually reach it
(started at `s=6707.8`, ~292 m from `s=length`) did so cleanly — 19.8 m/s,
no crash, no stall, `finished=True`. The policy CAN drive safely over
distances close to what it has already learned to sustain; the open
question is whether more budget lets that safe range grow to cover a
whole lap, or whether the reward shape itself caps out here regardless
of steps.

**What this suggests, stated as a hypothesis rather than a conclusion**:
every run so far shows a late, sudden climb in return (and in
off-track-while-climbing) that has not yet visibly plateaued by 40M
steps — consistent with training still being mid-exploration of an
aggressive driving style rather than having converged to a stable one.
More budget might let that settle into safer driving on its own; or the
tension between "reward pushing the limit" and "penalty for crashing"
might have a floor this reward shape cannot get under no matter how long
it trains, in which case the fix is not a coefficient but a different
mechanism (a hard safety constraint, or a curriculum that only asks for
longer distances once shorter ones are reliably safe). Not resolved here
— flagged so the next round of tuning does not repeat a fourth or fifth
coefficient guess without first ruling out "just needs more steps."

**Sweep methodology note for next time (user's own proposal, recorded
before it is forgotten)**: future reward sweeps should share one common,
past-the-basics baseline checkpoint across branches (warm-started, not
each from scratch) rather than reproducing the "learn to survive at all"
cost per point — this sweep's own 5 points spent their entire 15M-step
budget still in deeply negative return territory, mostly paying that
shared cost rather than differentiating by reward. Two things to get
right when doing this, not just the warm start itself: (a) a higher
starting `lr` for the abbreviated branch, since the existing anneal
schedule already restarts cleanly on warm start (Stage 0) but assumes a
full-length run's usual pace, and a short branch needs to move faster
within its reduced budget; (b) state explicitly that sharing one baseline
changes the comparison from "what would each reward produce from
scratch" to "how does each reward reshape this one policy" — cheaper, and
often the more relevant question (it is exactly what stage 2 already
does), but it can bias every branch toward whichever behavioural basin
the baseline already committed to, which matters more here than usual
given training has already been observed to lurch between qualitatively
different regimes (stall-forever vs. crash-constantly).

**13. Step-back review of the whole training arc — three findings and a
revised plan.** Requested by the user after item 12; each finding is
checked against the runs' own logged histories, not reasoned from memory.

**Finding 1 — the critic has been dead since the reward change, our own
diagnostic would have caught it, and we never ran the diagnostic.**
`explained_variance`, median over the last fifth of training, per run:

| run | gamma | penalties | EV tail median | D6's own gate (>0.3) |
|---|---|---|---|---|
| long run | 0.999 | otp=50 | **+0.72** | pass |
| stage1 old-reward | 0.999 | otp=50 | **+0.33** | pass |
| stall-exploit | 0.9995 | otp=500 | +0.01 | **fail** |
| aggressive-crash | 0.9995 | otp=500, ps=3.0 | +0.00 | **fail** |
| current (ps=1.5, phase B) | 0.9995 | otp=500, ps=1.5 | +0.00 | **fail** |

`D6_training_health` has a check named `the_critic_predicts_returns`
whose own failure text is exactly this situation: "at zero the critic is
no better than predicting the mean, which makes every advantage estimate
noise and the policy gradient a random walk." **D6 was never run on any
of these pilots** — every Season 3/4 episode ran it; the tracks pilots
skipped it, and three consecutive runs trained with a dead critic while
we tuned reward coefficients on top. Worse than the usual dead-critic
case: `rollout_steps=1024` is far shorter than late-training episodes
(5,000-10,000 steps), so GAE bootstraps almost everything through V —
a dead critic does not just add noise, it dominates the advantage signal.

Two candidate causes, which were changed TOGETHER (violating item 8's own
pre-registered "one at a time, never blended" rule — recorded as a
process failure, not excused): (a) `gamma` 0.999→0.9995 gives a ~40 s
effective horizon while the observation's curvature preview reaches 55 m
(~3-5 s at speed) — the return simply is not predictable from the
observation at that horizon; (b) penalty magnitude ×10 makes value
targets spike-dominated (rare ±500s among ±0.1-scale steps), and the
value head's separate 0.5 grad-norm clip (F51) throttles how fast it can
learn targets of that scale.

**Finding 2 — my own "off-track rate is stuck at 0.94-1.00" headline
(item 12) has a censoring artifact and needs correcting.** An episode can
only end four ways; with `finished` requiring reaching `s=length` (a
multi-km drive from most spawn points) and the timeout at 300 s, any
policy that cannot yet drive several km ends by crash **almost by
construction**. The binary "did it eventually crash" is uninformative at
this stage; the real safety metric is the **hazard** — mean distance
driven before crashing — which DID improve: 536.6 → 595.2 → 653.5 m
(+22% over the arc). Off-track-eventually will stay ~1.0 until the
policy can survive lap-scale distances, and treating it as the headline
overstated the failure. (The priority-order concern stands — the crash
hazard is still far too high — but the instrument was measuring episode
topology as much as safety.)

**Finding 3 — there is still no existence proof that the task as posed is
completable, and the classical driver would provide one cheaply.**
`drive_lap` + `SpeedProfile` (Episode 13's closed-loop driver) has never
been run on Spa — blocked only by the start-pose gap already flagged at
step 2 ("drive_lap assumes the car starts at the world origin with
heading 0"), which is a few lines to fix. A classical lap would (a) prove
a full Spa lap is drivable inside our own physics and envelope, (b) give
a reference lap time and a reference reward total to calibrate penalty
scales against actual earnings of a competent lap, (c) exercise the
step-2/3 plumbing at racing speeds — an external check the RL loop was
not written around (rule 11). Related quantifiable check, not yet done:
the fraction of uniform spawn points that are doomed at birth (dropped at
15 m/s, steer=0, inside or just before the few corners whose limit speed
is below 15 m/s) — computable directly from `track.curvature`, and worth
knowing before interpreting per-section failures near those corners.

### Revised plan (proposed, in order — each step cheap and diagnostic
before any further 40M-step spend)

- **A. Make D6 the standing gate for every training run in this thread**
  starting now — it exists, it is generated not hand-written, and it
  would have failed three runs we instead interpreted by eye. Add
  `explained_variance` to the per-run summary JSON.
- **B. Classical baseline on Spa** (~minutes): fix the start pose (set
  the initial `BicycleState` from the centreline's own s=0 pose), run
  `drive_lap` at 2-3 `grip_use` values, record lap time, validity,
  envelope occupancy, and the reward a clean lap would earn under the
  current coefficients. If the classical driver cannot lap Spa, the task
  definition has a problem RL cannot fix and everything pauses there.
- **C. Single-variable critic test** (~13 min): revert `gamma` to 0.999,
  keep everything else exactly as the current run (otp=500, sp=150,
  ps=1.5). If EV recovers → the horizon was the poison and 0.999 stays;
  if EV stays ~0 → penalty magnitude is implicated, and the next single
  change is scaling penalties down (or normalising value targets), not
  another coefficient guess. Either outcome is informative; this honours
  the "one at a time" rule the last change broke.
- **D. Contingent, after C, at most one at a time**: dense edge-proximity
  shaping (a per-step cost near the track edge — predictable from the
  current observation, so it fixes credit assignment for safety directly;
  tradeoff to state up front: it mildly fights racing-line width usage,
  so threshold high, e.g. only beyond 80% of half-width, and revisit
  before stage 3); `entropy_anneal=True` (pre-registered, still untried);
  spawn-speed adaptation (`v0 = min(15, 0.8·v_limit(s0))` from local
  curvature, D-A default-off) to eliminate doomed spawns.
- **E. Gate redefinition for stage 1**: hazard-based, not
  binary-terminal — mean per-section distance-before-crash ≥ one lap
  length (7,000 m) with envelope occupancy ~0, plus D6 passing
  (including `the_critic_predicts_returns`). The per-section probe gains
  worst-slip and termination-cause columns (rule 4).
- **F. Sweeps**, when next needed, use the shared-baseline warm-start
  method (item 12), with the from-a-shared-point caveat stated.

**14. Plan item A done — `experiments/tracks_pilot/d6_spa.py`, run
against all five saved checkpoints — and it found a second real defect
beyond the dead critic.** Reuses D6's own KL/entropy/deployed-vs-sampled/
tire-envelope checks unmodified; adapts the two checks hardcoded to the
single synthetic corner (`the_task_is_completable`,
`exploration_matches_the_action_scale`) to use Spa's own tightest corner
(max recovered curvature, r=11.4 m) instead — same intent, right
reference. `off_track_penalty`/`stall_penalty`/`progress_scale` must be
passed explicitly per run rather than read from the saved config: those
are `EnvConfig` fields and `PPOConfig`'s serialized JSON has no record of
them at all — a `.get(..., 500.0)`-style default would have silently
reconstructed the WRONG reward for both `gamma=0.999` runs (which used
`off_track_penalty=50`), caught by checking the actual saved keys before
writing the fallback rather than after.

**`the_critic_predicts_returns` gate confirms item 13 exactly**: pass for
both `gamma=0.999` runs (EV +0.72, +0.33), fail for all three
`gamma=0.9995` runs (EV +0.01, +0.00, +0.00).

**A second, previously-unflagged defect, found by running the adapted
`the_task_is_completable` check rather than assumed**: it **fails for
all five runs**. Spa's tightest corner (r=11.4 m) has a limit speed of
10.1 m/s; every episode spawns at `entry_speed=15.0 m/s`, inherited
unchanged from the single-corner synthetic track. This is the exact
failure D6's check exists to catch (Episode 9: entry speed above the
corner's own limit), recurring on a new track because entry speed was
never revisited when the track changed. Every uniform spawn point within
braking distance of Spa's tightest corner (or any of its other corners
whose limit sits below 15 m/s) starts the episode already unsurvivable
without immediate hard braking — a likely PRIMARY contributor to the
short, heterogeneous per-section survival times already measured (item
10's 48.8-1259.9 m range), not merely the reward shape. This elevates
"spawn-speed adaptation" from item D's contingent list to something to
fix before the next training run, not after: `v0 = min(15, 0.8 *
v_limit(s0))` from local curvature at the drawn start, D-A default-off
so every existing episode is unaffected.

**`exploration_is_not_growing` fails for all five runs** (entropy rising
in every one, e.g. current run -0.56 -> -0.52) — expected given
`entropy_anneal=False` is the default and already documented elsewhere
in this codebase to behave exactly this way, but now formally gated
rather than merely known. Supports trying `entropy_anneal=True` (plan
item D) rather than leaving it as a vague "still untried" note.

`exploration_matches_the_action_scale` passes for all five (ratio 0.6x,
inside the adapted Spa-corner window). `greedy_and_stochastic_agree`
fails only for `stage1_stallexploit` (26% gap) — plausibly the stall
boundary itself being a more decision-sensitive knife-edge than genuine
driving, consistent with that run's already-known degenerate behaviour.

Reports written to `experiments/tracks_pilot/out/D6-Spa-<run>_report.json`
for all five runs.

**15. Plan item B — start-pose gap fixed, classical baseline attempted,
honest negative result.** `physics/driver.py`'s `drive_lap` always placed
the car at the world origin (`BicycleState`'s `x=y=heading=0` defaults) —
harmless for every synthetic `Track` (its `centreline` integrates FROM
the origin by construction, so this always coincided) but wrong for a
real circuit's raw coordinates, which is why `drive_lap` had never been
run on Spa at all. Fixed: the car now starts at the track's own s=0
centreline pose. Bit-identical for every existing caller (all 15
pre-existing `test_driver.py` tests pass unchanged); a new test
(`test_drive_lap_starts_at_the_tracks_own_pose_not_the_world_origin`)
checks it against a circle deliberately NOT centred on the origin, the
exact case that was silently wrong before.

**The classical baseline itself: does not complete a Spa lap, at any
grip level tried (`experiments/tracks_pilot/classical_baseline_spa.py`,
`grip_use` 0.3-0.85).** Every attempt spins or leaves the road in the
same ~900-1020 m window — checked directly, not assumed to be a speed
problem: dropping `grip_use` from 0.85 to 0.3 (much lower target speed
throughout) moved neither the failure location nor its severity (worst
slip 44-54° regardless). That rules out "too aggressive" as the cause
and points at the steering controller — pure-pursuit gains tuned only
against a single, constant-radius synthetic corner — not at speed. This
is a THIRD distinct problem location, different from both Spa's tightest
corner (item 14, s=403 m) and the reward-tuning arc's own crash
clustering; the pure-pursuit driver's fixed lookahead most likely cannot
track a corner whose curvature changes as fast as this section's does.

**Item B's actual goal (calibrate reward scales against a competent
lap's earnings) is therefore not yet available** — a real, useful
negative result, not a failure to hide. Driver-gain retuning for
real-circuit curvature is its own task, matching Episode 13's own
precedent that a hand-tuned driver's gains are exactly the kind of
unstated protocol choice CLAUDE.md rule 9 exists for (Episode 13 swept
them for the single synthetic corner; nothing has swept them for Spa).
Not attempted further here without checking scope with the user first.

**16. Plan item C — the confound is resolved. Gamma was not the
poison; penalty magnitude is.** `experiments/tracks_pilot/critic_gamma_test.py`:
`gamma` reverted to 0.999, everything else held exactly as the current
run (`off_track_penalty=500`, `stall_penalty=150`, `progress_scale=1.5`).
20M-step budget, 19 updates, 381.8 s. `explained_variance` sat at
**-0.001 to +0.000 for all 19 updates** — no recovery at all, in sharp
contrast to the reference `gamma=0.999`/`off_track_penalty=50` run, which
climbed from 0.0 to past D6's 0.3 gate by update 12-15 and reached 0.72
by the end. Reverting the horizon changed nothing; the critic stayed
exactly as dead as under `gamma=0.9995`.

This cleanly isolates the cause the step-back review (item 13) left
confounded: **the ~10x penalty-magnitude jump (50→500 flat, plus the new
150 stall penalty) is what broke the critic, not the longer horizon.**
Consistent with the mechanism already named in item 13: value targets
now spike between roughly the ordinary per-step scale (~0.1-1 with
`progress_scale=1.5`) and ±500-650 on a terminal step, a much harder
regression problem than the original reward's, and the value head's own
separate 0.5 grad-norm clip (F51) — already isolated FROM the policy's
clip, but still a fixed cap — may simply not let the critic's weights
move far enough per update to track targets that much larger in scale.

Per-section result at this checkpoint (worth recording, not the point of
this run): distance mean 281.5 m, off-track rate 1.00 — worse than the
`gamma=0.9995` runs, consistent with a genuinely noise-driven policy
gradient under a dead critic, exactly as item 13 warned it would look.

**Per the plan's own pre-registered next step, penalty magnitude is now
the implicated single variable — not gamma, and not a fresh guess.**
Two candidate fixes, not yet chosen between: (a) scale
`off_track_penalty`/`stall_penalty` down toward a magnitude the value
function can actually track, accepting this partially undoes item 11's
original fix for the weak-deterrent problem unless `gamma=0.9995`'s
implicit (lost-future-reward) deterrent is reinstated to carry more of
that weight, which was always its OTHER stated purpose (item 11: "the two
are meant to reinforce each other, not substitute" — this run suggests
they were instead compounding into a value-learning problem); (b) leave
the reward scale alone and address the value network's own ability to
track it — raise or remove the value head's grad-norm clip specifically,
or normalise returns/value targets before regression, so the SAME reward
shape becomes learnable without renegotiating the safety-vs-speed balance
again. Checked with the user before choosing, consistent with every
reward-design decision this arc has made.

**17. Fix (b) tried first, and it is also a clean negative result.**
`physics/ppo.py` gained `value_max_grad_norm` (D-A pattern, `None`
default reuses `max_grad_norm`, tested for default-safety and for
actually being wired in). `experiments/tracks_pilot/critic_value_clip_test.py`:
reward held exactly as the current stage-1 run (`gamma=0.9995`,
`off_track_penalty=500`, `stall_penalty=150`, `progress_scale=1.5`),
`value_max_grad_norm` set to an effectively unbounded 1e6 — does removing
the throttle recover the critic at all, before tuning a finite value.
20M steps, 19 updates.

**`explained_variance` stayed at -0.001 to +0.000 for all 19 updates —
statistically indistinguishable from item 16's gamma-revert result.**
Unclipping the value head entirely made no measurable difference. This
rules out the grad-norm clip as the bottleneck (or at least as the sole
one): F51's own mechanism — a fixed clip throttling the critic once
return magnitude grows — does not reproduce here even with the clip
effectively removed, so the critic's difficulty tracking these targets is
not (only) a step-size problem, it looks more like a genuine scale/
representation problem the network cannot regress against directly
regardless of how far each gradient step is allowed to move.

**Both `fix (b)` candidates tried; both negative. Moving to `fix (a)` —
reducing the reward's own scale — per the user's explicit direction**,
having now ruled out gamma and the clip as one-line fixes. `off_track_penalty`
to be brought down from 500 toward a magnitude closer to what the
critic demonstrably could track (the original `off_track_penalty=50`
config had EV 0.33-0.72) while keeping `gamma=0.9995` to carry more of
the deterrent implicitly, as item 11 originally intended the two to do
together — this time genuinely testing that intention rather than
stacking two large explicit-and-implicit deterrents at once.

**18. `fix (a)` is also a clean negative — and the real cause, found by
measuring the critic's OUTPUT rather than its error.**
`experiments/tracks_pilot/critic_penalty_test.py` (`off_track_penalty`
500 → 200, everything else held): `explained_variance` −0.002 across 19
updates. **Three candidate fixes, three clean negatives** — gamma,
grad-norm clip, penalty magnitude.

Two measurements then found the actual mechanism, neither of which is a
coefficient:

**(i) The observation cannot see far enough — real, but NOT the main
cause.** Lining every run up against `start_jitter_m` (a controlled
comparison already sitting in the existing data):

| jitter | reward | gamma | EV tail |
|---|---|---|---|
| 300 m | otp=50 | 0.999 | **+0.72** |
| 7,000 m | otp=50, *identical otherwise* | 0.999 | **+0.33** |
| 7,000 m | otp ≥ 200 | either | ~0.00 |

Rows 1-2 differ ONLY in spawn spread, and it halved EV. Mechanism: the
observation carries 6 curvature-preview samples reaching **55 m**
(`PREVIEW_DISTANCES`) and **no absolute track position**, so on a 7 km
circuit the critic cannot distinguish a kilometre of clear straight from
60 m before a hairpin when local curvature happens to match. A k-NN
estimate of the EV *achievable from the observation alone* (200 episodes,
initial observation → actual discounted return) gives a ceiling of
**+0.25 (old reward) and +0.28 (current reward)** — low, and nearly
IDENTICAL for both. So the observation ceiling explains 0.72 → 0.33 under
full-lap jitter, but **not** 0.33 → 0.00: the current reward's critic sits
far BELOW a ceiling it could reach.

**(ii) The critic never leaves its initialisation — this is the cause.**
Measured V(s) against actual discounted returns over 40 episodes per
config:

| config | critic V(s) | actual return G | V spans |
|---|---|---|---|
| old reward (EV 0.33) | mean 19.7, sd 2.8, range [−13, 21] | mean 177, sd 133, range [−51, 454] | **2.1%** of G's spread |
| current reward (EV 0.00) | mean −14.7, sd 1.4, range [−15, 6.7] | mean 133, sd 365, range [−500, 1052] | **0.39%** of G's spread |

The critic is not mis-predicting; it has barely moved. Its output is
stuck in a ±20 band while returns span ±1000. The arithmetic matches:
Adam at `lr=3e-4`, ~40 gradient steps per update (10 epochs × 4
minibatches) × 19-38 updates ⇒ ~760-1520 steps ⇒ **total** possible
travel per parameter ≈ `lr × steps` ≈ 0.2-0.5, so a 64-unit final layer
can reach ~±30 at absolute best against a required ±1000. It cannot get
there within the budget regardless of clip, horizon, or penalty size —
which is exactly why all three fixes did nothing: **none of them changed
the required output magnitude.**

This also reframes the "healthy" runs: the old reward's critic spanned
only 2.1% of its return spread too, and its EV=0.33 is partly GAE's own
bootstrapping correlation (`ret = adv + V`) rather than genuine
prediction. **The critic has been weak in every tracks-pilot run**; the
larger penalties merely made it unambiguously zero. That the policy still
improves throughout is consistent — with a near-constant baseline, GAE
degrades toward high-variance Monte-Carlo returns, which still carries a
valid (if noisy) policy gradient.

**The fix is the one remaining candidate from item 16, now identified by
measurement rather than chosen by elimination: normalise the value
targets / returns** (PopArt — van Hasselt et al. 2016, "Learning values
across many orders of magnitude" — or the running-return normalisation
shipped in most production PPO implementations). **Superseded by item 19
— the literature says the reward STRUCTURE is the thing to change, and
normalisation is at best a secondary tool.** It attacks the actual
problem: it puts the regression target in a range the network can
represent from its initialisation, instead of asking a freshly-initialised
head to travel three orders of magnitude. To be validated against the
racing-RL literature review (item 19) before implementing, since the user
asked what the field actually does here.

**19. The literature review (two independent agents, corroborating).
Verdict: our reward is structurally unlike anything published, and the
STRUCTURE — not the coefficients, not normalisation — is what to change.**

**19a. The single most important number.** Across every system surveyed,
the ratio of the largest safety penalty to one step's progress reward:

| system | penalty : per-step progress | delivery |
|---|---|---|
| GT Sophy (Maggiore, 200 km/h) | ~7 : 1 | dense, every 0.1 s while off course |
| GT Sophy (Sarthe, 300 km/h) | ~18 : 1 (36:1 in chicanes) | dense |
| GT7 (Sony, 2025) | ~20 : 1 | dense |
| Czechmanowski F1TENTH (MF6.1 tyres, PPO) | ~3-4 : 1 | per-violation, **not terminal** |
| Evans F1TENTH (all variants) | 5 : 1 | terminal, penalty = −1 |
| Swift (drone, Nature 2023) | small | terminal, penalty = 5.0 |
| TC-Driver / Chisari (ETH) | **0.1 : 1** | per-violation, not terminal |
| **ours** | **500-5000 : 1** | **single sample, terminal** |

We are one to three orders of magnitude outside the entire field, and we
deliver it as one terminal sample rather than spread across the offence.

**19b. Two flagship systems never terminate on crashing at all.** GT
Sophy's rollout worker is literally `dones = [False]` — a *continuing*
task with fixed 150 s episodes; off-course, wall contact and collisions
are all penalise-and-continue. Fuchs et al. (ETH GTS) likewise use fixed
100 s rollouts with no terminal condition defined. Where termination does
exist, its penalty is **small**: −1 (Evans ×3, Czechmanowski, Unity),
5.0 (Swift), −25 to −50 (Trumpp, Learn-to-Race). **No surveyed system
both terminates and applies a large penalty.**

**19c. Fuchs et al. documents OUR EXACT BIFURCATION, verbatim** — this is
the most valuable single sentence in the review:

> "Without this additional wall contact penalty, we found the learned
> policies did not brake and simply grinded along the track's walls in
> sharp curves. When using **fixed valued wall contact penalties**, we
> found the agent **either did not react to the penalty or ended up in a
> strategy of full braking and standing still to not risk any wall
> contact**, depending on the strength of the penalty."

That is item 11's under-deterrence (`otp=50`, ignored) and item 12's
stalling exploit (`otp=500`, coast to a stop) — the same two failure
modes, in the same order, from the same cause. **Their fix was not to
tune the constant: it was to make the penalty proportional to kinetic
energy**, `−c_w‖v‖²` with `c_w = 5×10⁻⁴`, justified physically as "the
energy-dependent loss in acceleration that takes place when hitting a
wall." A fixed-value penalty is the thing they explicitly report as
unfixable by tuning. We spent five runs discovering this independently.

**19d. Universal conventions we violate.**
- **Progress weight is pinned at exactly 1.0** in every major system, with
  safety tuned relative to it. Our `progress_scale` sweep (item 12) was
  tuning the one coefficient the field holds fixed by convention.
- **Discount horizon.** GT Sophy γ=0.9896 @10 Hz = **9.6 s**; Fuchs
  γ=0.98; Czechmanowski γ=0.99 @20 Hz = 5 s; Hildisch γ=0.96; Steiner
  γ=0.95. **Ours: γ=0.9995 @50 Hz = 40 s** — 4-8× longer than anyone,
  and directly responsible for the ±1000 value targets item 18 measured.
- **Spawn at speed.** Near-universal random-position spawning, and Fuchs
  spawns rolling at **100 km/h** "which we found can accelerate
  training." Jaritz et al. proved fixed-start spawning generalises worse.
  We do spawn randomly — but at a fixed 15 m/s that D6 (item 14) already
  flagged as *above* Spa's tightest corner's 10.1 m/s limit.
- **n-step returns:** GT Sophy 7-step, Fuchs 5-step, Hildisch 3-step.

**19e. On normalisation — the review partly contradicts item 18's
proposed fix, and that is worth stating plainly.** *No* surveyed racing
system normalises value targets or returns; only Trumpp (TUM) normalises
rewards at all ("a running statistics calculation"). GT Sophy hit the
identical large-loss instability and fixed it with **critic-only gradient
clipping at global norm 10** — note that is *looser* than our default 0.5
and far tighter than the 1e6 item 17 tried, so neither of our two
settings resembles theirs. Andrychowicz et al. (ICLR 2021) find value
normalisation "influences the performance very strongly" but *helps on
some environments and significantly hurts on others* — check, don't
assume. Andy Jones' debugging guide gives the operational target
directly: **hand-tune the reward scale so value targets land in roughly
[−10, +10]**, and names our exact symptom ("if residual variance drops to
zero, some scenarios are generating vastly larger returns than others").
So: normalisation is a legitimate secondary tool, but the field's answer
to our problem is to not create the huge targets in the first place.

**19f. A finding that independently validates rule 4.** Evans et al.
(RA-L 2023) report that a dense `v·cosψ − d_c` reward taught their agent
to **drift at over 30° slip on a single-track model valid to ~8°** —
"thus exploiting the simulation model." GT Sophy carries a dedicated tyre
term, `R_ts = −Σ min(|κ_i|,1)⁴·|α_i|` at **weight 0.25**, the only reward
term in the literature that addresses the contact patch directly. Our
`envelope_penalty` is the same idea and should be **kept and probably
strengthened**, not dropped — and this is direct external evidence that
dense progress shaping *without* it would produce exactly the
model-exploiting slip behaviour rule 4 exists to catch.

**19g. Closest analogue to this project, worth copying almost verbatim.**
Czechmanowski et al. (arXiv:2504.02420): single-track dynamic model with
**MF6.1 Magic Formula tyres identified from real data**, PPO, first RL
policy to beat expert humans in RC racing and to beat MPC. Their entire
reward:

```
r_t = −1                    if the track boundary is exceeded
    = s_t − s_{t−1}         otherwise        (centreline progress, Frenet)
```

No wall shaping, no smoothness terms, no stall penalty. Boundary
violation is **not terminal** — "it is reset to a random position on the
track to ensure full track exploration." γ=0.99, 400 parallel envs,
1024-step rollouts, 120M steps, 20 Hz. Observations normalised by
dividing by max; **no reward or value normalisation.** Their penalty is
~3-4× one step's progress.

**19h. Proposed redesign — following the field rather than continuing to
guess.** Each item is a structural change, not a coefficient:

1. **`progress_scale = 1.0`** — pin progress at 1, tune safety relative
   (universal convention; stop sweeping this).
2. **Replace the terminal `off_track_penalty` with a dense, speed-scaled
   boundary cost** — Fuchs' `−c_w‖v‖²` form, which is the documented cure
   for exactly our bifurcation. Charge it per step while off/near the
   edge rather than once at death.
3. **Penalise-and-continue, or reset-to-random-position** (GT Sophy,
   Fuchs, Czechmanowski) instead of terminate-with-a-cliff. This also
   removes the ±500 spike that item 18 measured as unreachable.
4. **`gamma` → ~0.99** (2 s at 50 Hz) or at most ~0.998 (GT Sophy's 9.6 s
   equivalent at our rate). This alone shrinks value targets by ~10-20×.
5. **Keep `envelope_penalty`** (19f), and consider GT Sophy's
   slip-ratio×slip-angle form at weight ~0.25 relative to progress.
6. **Spawn at a speed the local corner allows** — fixes D6's
   `the_task_is_completable` failure (item 14) and matches Fuchs' rolling
   start.
7. **Then re-check value-target magnitude against [−10, +10]** and only
   add return normalisation if it is still out of range — as a measured
   decision, not a default.
8. **Timeout-vs-terminal bootstrap: a real defect, but currently
   INERT — checked rather than assumed.** `rl_env.step` folds `timeout`
   into `done` and `_gae` cuts the bootstrap on `done` (`mask = 1.0 -
   dones[t]`), so a truncated episode is taught its future value is zero.
   Remonda et al. name this exact bug in a racing context and call the
   fix "essential". **But it is not firing here**: measured episode
   lengths are 371-2,672 steps against `max_steps=15,000`, so `timeout`
   never triggers. Worth fixing before it *becomes* live — which it will,
   the moment a policy survives long enough to matter, i.e. exactly when
   the project starts succeeding. Not a contributor to the current dead
   critic.

**20. The redesign ran — the critic is fixed, and the fix exposed that
every distance number in this arc was measuring tyre-model exploitation.**
`experiments/tracks_pilot/spa_ppo_v2.py`, 152 updates, 970.7 s.

**`explained_variance` = +0.881**, climbing 0.007 → 0.89 across the run
and passing D6's >0.3 gate **for the first time in this entire thread**,
after nine consecutive runs pinned at ~0.000. Item 18's diagnosis — the
value head could not travel far enough to represent the targets — is
confirmed: shrink the targets (penalties 500→5, γ 0.9995→0.995) and
quadruple the gradient-step budget (`n_envs` 1024→256), and the critic
learns normally. Nothing about the network or the algorithm needed to
change.

**The retraction.** Item 12 reported 653.5 m as "the best yet" and item
15/18 repeated it. Measured properly, with the envelope instrumentation
rule 4 mandates:

| policy | distance | worst slip | sections >12° | envelope occupancy |
|---|---|---|---|---|
| stage1 two-phase (EV 0.00) | 653.5 m | **30.1°** | **24 / 24** | 0.0352 |
| v2 redesign (EV 0.88) | 519.7 m | 17.8° | 16 / 24 | 0.0124 |

**That 653.5 m was driven entirely outside the tire model's fit** — every
one of the 24 sections over the 12° bound, peak 30.1°, 3.5% occupancy. By
rule 4 it was never a quotable number, and the whole reward-tuning arc's
"distance keeps improving" narrative (536.6 → 595.2 → 653.5) was tracking
how freely each policy was allowed to slide, not how well it drove. **The
comparison that matters reverses the conclusion**: v2 gives up 20% of the
distance and cuts peak slip by 41%, sections-over-bound by a third, and
envelope occupancy by 65%. Cleaner driving, correctly scored as better.

This is rule 4 doing exactly its job, and it is the second independent
confirmation of Evans et al.'s finding (item 19f) — a dense progress
reward will buy distance by sliding on a model that cannot support it,
and only envelope instrumentation catches it. Worth noting the earlier
runs' slip was never checked because the per-section probe did not log it;
v2's does now (`worst_slip_deg`, `envelope_occupancy` per section).

**What is still wrong.** 16/24 sections remain over the bound and
occupancy is 0.0124 against rule 4's ~0; off-track rate is still 1.00.
And `eval_return` peaks at updates 24-40 (363-437, a genuine broad
optimum, not a noise spike — checked) then declines to ~175-320 as EV
rises. The most plausible reading: **an accurate critic lets PPO optimise
the reward properly for the first time, and this reward still pays for
sliding more than it charges** — `envelope_penalty` is the one term item
19h deliberately left untouched, and at 0.5 (≈0.24/step at 17.8° against
~0.6/step of progress) it is now the binding weakness rather than a
safe default.

**Next, and it is a single-variable change:** raise `envelope_penalty`
(GT Sophy carries its tyre term at 0.25 relative to progress 1.0 and
switches it off only where the surface allows it). Then the ablation the
user asked for — subtract the seven v2 changes one at a time to find
which carried the critic fix, now that there is a working configuration
to ablate *from*.

**21. `envelope_penalty` swept — the first rule-4-valid configuration in
this thread, and a second sighting of item 18's magnitude failure.**
Single variable over the v2 baseline, 20M steps each
(`experiments/tracks_pilot/v2_variants.py --job envelope`):

| `envelope_penalty` | EV | D6 gate | distance | worst slip | >12° | occupancy |
|---|---|---|---|---|---|---|
| 0.5 (v2) | +0.479 | pass | 534.0 m | 18.4° | 17/24 | 0.0074 |
| 2.0 | +0.709 | pass | 477.0 m | 14.5° | 6/24 | 0.0038 |
| **6.0** | **+0.703** | **pass** | **468.0 m** | **11.0°** | **0/24** | **0.0000** |
| 15.0 | +0.073 | **FAIL** | 412.1 m | 12.7° | 2/24 | 0.0001 |

**6.0 puts every one of the 24 sections inside the tire model's own 12°
fit, at exactly zero envelope occupancy** — rule 4 satisfied for the first
time in this thread, costing 12% of the distance. Item 20 established that
every earlier distance figure was measuring how freely a policy could
slide; this is the first one that is not.

**15.0 is worse, not safer, and the way it fails matters**: EV collapses
to +0.073 and fails D6's gate, and its slip is *worse* than 6.0's (12.7°,
2/24). That is item 18's mechanism recurring in a different term — a
reward component large enough to dominate the value targets kills the
critic, and a dead critic then drives worse. **The relationship is an
inverted U, not "more penalty is more safety"**, which is precisely the
shape Fuchs et al. describe for fixed-value penalties (item 19c) and a
third independent confirmation of it inside this project.

`envelope_penalty = 6.0` is promoted to the v2 baseline. Off-track rate
is still 1.00 at every level — the car does not yet complete sections —
so this fixes validity, not competence. But the numbers are now quotable.

**27. A learned policy completed a lap of Spa** — and the run that did it
was nearly written off by an evaluation bug of mine.

`experiments/tracks_pilot/spa_curriculum.py`, 120M steps, 457 updates,
74.8 min, progressive speed cap 9.0 → 28.0 m/s over 19 raises,
`entropy_anneal=True`. EV tail **+0.977**.

**The corrected result** (selected checkpoint = update 80, trained at
cap 11.0):

| metric | at cap 28 (as first reported — WRONG) | at cap 11 (its own — correct) |
|---|---|---|
| per-section distance | 699.7 m (10.0%) | **2,834.9 m (40.5%)** |
| best single section | 1,836.7 m | **6,122.8 m (87%)** |
| worst slip | 36.0° | **9.8°** |
| sections > 12° | 15/24 | **0/24** |
| envelope occupancy | 0.0287 | **0.0000** |
| **completed a full lap** | 0/24 | **1/24** |

**`off_track_rate` is finally off 1.00** — the gate that had not moved
across roughly twenty training runs — and the result is rule-4 valid:
zero sections outside the tyre model's fit. Independently verified on the
`cap14` policy that the driving is genuine rather than gamed: `|n|` sits
at 0.51 of half-width (mid-road, 0.2% of time beyond 80%), `s` is strictly
monotonic (min Δs +0.196 m/step, never reverses), speed steady at the cap.
It drives the road.

**Defect 1 — the evaluation bug, mine.** The per-section probe ran the
selected checkpoint at `state["cap"]`, the cap the curriculum had reached
by the END (28.0), not the cap that checkpoint was trained under (11.0).
A policy trained for 11 m/s driven at 28 m/s slides — hence 36° slip and
15/24 outside the envelope. **It made the best result in this thread read
as a failure.** Fixed: the cap in force at each evaluation is recorded,
and the selected checkpoint is scored at its own.

**Defect 2 — the curriculum climbs past competence.** `eval_return`
peaked at **3,521.7 at update 80 (cap 11)** and never recovered as the cap
kept rising: 181.7 at cap 14, ~780 at caps 24-27, 741.8 at the end. The
plateau arm raises the cap whenever distance stalls, which is exactly what
a policy at the edge of its competence looks like — so it kept promoting a
policy that was getting worse. **This risk was identified while designing
the curriculum and deliberately skipped "to keep it simpler"; that was the
wrong call and it cost a 75-minute run.** Fixed with a freeze: stop
raising once the deployed policy sits below half its best eval for three
consecutive evaluations.

**What this establishes.** The task is learnable: a policy trained purely
by PPO, with no reference trajectory and no imitation, drives 40% of Spa
on average and a full lap from one start, entirely inside the tyre model.
The binding constraint was never the reward coefficients, the observation
horizon, or the track import — it was that nothing stopped the policy from
driving faster than it could control, and item 26's cap is what removed
that. The remaining work is raising the cap *without* losing competence,
which is now a well-posed problem with a working baseline and a diagnosed
failure mode rather than an open-ended search.

**28. Spa is solved: 100% of the lap from every start, rule-4 valid — and
the bug that hid it changed how results get scored here.**

`cross_track_penalty=2.0`, 40M steps, progressive cap, checkpoint scored at
its own cap (13.0 m/s). Verified at two probe densities:

| | 24 probes | 48 probes |
|---|---|---|
| fraction of lap | **100.0%** | **100.0%** |
| finished | **24/24** | **48/48** |
| off-track | 0% | 0% |
| worst slip | 10.4° | 10.4° |
| outside the 12° fit | **0/24** | **0/48** |
| `|n|` / half-width | 0.17 | 0.17 |
| lap time | — | 537.8 s (13.0 m/s) |

**The missing ingredient was the centreline term.** Item 27's failure
analysis showed the policy drifting off on *straights* (radius 3,934 m,
1.4° slip, 0/24 exits in a corner tighter than 40 m) — it could not hold a
line, and `edge_penalty` only fires past 75% of half-width, so below that
there was no restoring force at all. `cross_track_penalty` is the term
every dense reward in the item 19 survey carries and ours lacked. It took
Spa from 40.7% to 100%. **Not monotone:** 2.0 is valid; 5.0 travels further
before crashing (3753 m) but puts 24/24 sections outside the fit and is not
quotable — the same inverted U as item 21.

**The `finished` bug (FINDINGS F110).** `finished` was
`self.s >= track.length` — absolute position — while every training env
(`start_jitter_m = length`) and every probe (`env.reset(); env.s = s0`)
starts at non-zero `s`. An episode starting at `s0` needed only
`length − s0`. It corrupted **training** (episodes truncated early and
flagged as successes) as well as reporting, and put a false claim into
F109, now withdrawn: that policy finishes 0/24, not 1/24.

**It survived ~20 runs because every result was scored by a throwaway
script.** `experiments/tracks_pilot/policy_eval.py` is now the single
evaluator (D16): fixed metric set, termination reasons that must sum to 1,
a rule-4 verdict that refuses to quote a distance for an invalid result.
Audited in four passes — and pass 3 is the keeper: one test passed
*vacuously*, its only assertion inside an `if len(...)` guard, and had to be
strengthened until it failed against the old code too.

**19i. Cost of the detour, stated plainly.** Items 11-18 spent five
40M-step runs and four 20M-step diagnostics tuning coefficients inside a
reward structure the field abandoned — and the specific failure we spent
the most compute on is documented in a 2021 paper as the known
consequence of fixed-value penalties. **Reviewing the literature before
designing the reward would have cost an hour and saved all of it.** That
is the lesson worth carrying into Season 5, which plans considerably more
RL than this.

**Does:** recognisable results, a much richer test of a controller (many corner
types, direction changes, braking zones of different severity), and a lap time
that a reader can compare against something they have seen.

**Does not:** make the model more accurate. It is still rung 2 — no elevation,
no banking, no camber, no aero balance, roughly 5% of a real car's understeer.
A flat, unbanked Spa run on this model is a statement about this model on that
geometry, and the article has to say so in those words.
