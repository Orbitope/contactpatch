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
2. **Closed-loop support** — `s` wrapping, lap counting, `half_width(s)`.
   Touches `rl_env` termination and the driver's preview.
3. **One real circuit, imported and validated** against published corner radii
   and total length. One is enough to prove the pipeline; a second is cheap.
4. **Batched env support for long tracks** — the current curvature lookup is
   called per step on an array, which is fine, but a 5 km circuit at 50 Hz is
   ~10,000 steps per lap against today's ~1,000, so `max_steps` and the episode
   budget both need revisiting.
5. **Only then** retrain. A real circuit changes what "a lap" costs, so every
   step-count and wall-clock number in Season 3 and 4 is re-derived, not
   inherited.

---

## 5. What this unlocks, and what it does not

**Does:** recognisable results, a much richer test of a controller (many corner
types, direction changes, braking zones of different severity), and a lap time
that a reader can compare against something they have seen.

**Does not:** make the model more accurate. It is still rung 2 — no elevation,
no banking, no camber, no aero balance, roughly 5% of a real car's understeer.
A flat, unbanked Spa run on this model is a statement about this model on that
geometry, and the article has to say so in those words.
