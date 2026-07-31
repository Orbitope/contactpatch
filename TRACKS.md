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

---

## 5. What this unlocks, and what it does not

**Does:** recognisable results, a much richer test of a controller (many corner
types, direction changes, braking zones of different severity), and a lap time
that a reader can compare against something they have seen.

**Does not:** make the model more accurate. It is still rung 2 — no elevation,
no banking, no camber, no aero balance, roughly 5% of a real car's understeer.
A flat, unbanked Spa run on this model is a statement about this model on that
geometry, and the article has to say so in those words.
