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

## 3. Candidate sources

*(Being researched — see the findings section appended below once the source
survey completes. Requirements: open licence permitting redistribution,
several recognisable circuits, centreline plus width, and ideally curvature.)*

**Licensing trap to check explicitly:** sim-racing mod data (Assetto Corsa,
rFactor and similar) is generally **not** redistributable and much of it is
itself derived from copyrighted laser scans. Circuit *layouts* as geometric fact
are not copyrightable, but a specific survey dataset is. Anything imported needs
its licence recorded next to it, the same way `tires/Sedan_Pac02Tire.tir` records
its BSD-3 origin from Project Chrono.

---

## 4. Staging

1. **`SampledTrack` + the round-trip test**, validated against our own synthetic
   tracks where the answer is known. No external data yet.
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
