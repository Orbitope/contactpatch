"""Procedurally generated closed circuits, biased toward corners.

**Why generate rather than use the 24 real ones.** Measured across every
circuit in TUM's database, **59.3% of driving time is spent going straight**
(time-weighted, at the cornering limit, corner = radius < 200 m). Monza is
77% straight. A policy training on real circuits spends most of its steps
learning nothing about braking or grip, and our step budget is the binding
constraint on everything.

A corner-dense generated circuit delivers **~2.5x the learning signal per
step at identical compute**. That is the argument for this module — sample
efficiency first, generalisation second.

**Realism is explicitly not a goal.** Two independent groups (Remonda's
Formula RL; Evans's F1TENTH survey) report the same asymmetry: a policy
trained on a *complex* circuit transfers to simple ones, while a policy
trained on a simple circuit "did not finish the unseen tracks." Training on
harder-than-real geometry and evaluating on real circuits is therefore the
favourable direction, and the generated tracks do not need to look like
anything in particular. What they DO need is to span the range of corner
radii a real circuit contains, because that is what the policy must
generalise over.

**Closure is structural, not fitted.** The centreline is a periodic radial
perturbation of a circle, so it closes exactly by construction rather than by
a constraint the generator has to satisfy. `SampledTrack(closed=True)` then
handles arc-length reparameterisation and curvature.
"""

from __future__ import annotations

import numpy as np

from physics.track import SampledTrack

#: Every generator tags what it produced. Results are reported per family --
#: they have genuinely different geometry, and mixing them without a label
#: makes any "generated circuits do X" claim unreadable.
STYLE_HARMONIC = "harmonic"        # perturbed circle, star-shaped
STYLE_FILLETS = "fillets"          # straights + circular fillets, star-shaped
STYLE_CURVATURE = "curvature"      # curvature-space corner sequence, may fold
STYLE_ARCADE = "arcade"            # bounded-turn-rate pursuit, game style

#: Radius below which a point counts as "in a corner" for the density
#: statistics. Matches the threshold used to measure the 59.3% figure above.
CORNER_RADIUS_M = 200.0


def generate_track(seed: int, *, base_radius: float = 1200.0,
                   n_lobes: int = 8, amplitude: float = 0.20,
                   n_harmonics: int = 3, half_width: float = 5.0,
                   n_points: int = 1200, smoothing: float = 20.0,
                   name: str | None = None) -> SampledTrack:
    """One closed circuit.

    **`base_radius` is set by the achievable-SPEED distribution, not by
    curvature statistics.** This is the correction that mattered most. At
    base_radius=320 the forward-backward speed profile gives a median
    achievable speed of **20.6 m/s against real Spa's 37.2** — so a policy
    trained there spent **78.7% of its time on Spa above the 95th percentile
    of any speed it had ever seen**, and Spa's MEDIAN speed exceeded the
    generated circuits' MAXIMUM. That is a pure out-of-distribution failure
    and no reward term touches it. Four attempts at fixing Spa transfer by
    adjusting curvature statistics and reward shape all failed, because the
    quantity that sets the policy's state distribution is speed, and speed
    depends on circuit SCALE as much as on local geometry.

    **Defaults are measured, not guessed.** A sweep over lobes x amplitude
    (see the table in TRACKS.md) found 8 lobes / 0.20 amplitude /
    3 harmonics gives 72.7% corner time, minimum radius 8.7 m and 35
    curvature sign changes on a ~3.2 km lap. Raising lobes or amplitude
    beyond that trades corner density for undrivably tight radii: at 18
    lobes / 0.40 the minimum radius is 0.5 m and corner time falls to 41.8%,
    because the geometry becomes high-frequency noise rather than corners.

    ``n_lobes`` sets roughly how many major direction changes the lap has;
    ``amplitude`` how far the radius swings, which is what actually produces
    tight corners. Higher harmonics add the shorter-wavelength content that
    becomes the sub-50 m radii — a pure single-frequency lobe pattern gives a
    smooth kidney shape with no genuinely slow corners.
    """
    rng = np.random.default_rng(seed)
    theta = np.linspace(0.0, 2.0 * np.pi, n_points, endpoint=False)

    # Radial perturbation: a sum of harmonics of the lobe frequency, each with
    # its own random phase. Every term is periodic in theta, so r(0) == r(2pi)
    # and the loop closes exactly.
    r = np.ones_like(theta)
    for h in range(1, n_harmonics + 1):
        # 1/h^2, NOT 1/h. To first order in the perturbation,
        # kappa(theta) ~ (1/R)(1 + sum_h a_h (h^2 n^2 - 1) cos(...)), so with
        # amp = A/h^p the per-harmonic CURVATURE contribution scales as
        # h^(2-p). Therefore:
        #   1/h  -> h^1: the highest harmonic DOMINATES (measured 12.6 /
        #                25.5 / 38.3), giving 0.4-1.3 m minimum radii where
        #                the car needs >= 8 m, and 52-84 curvature sign
        #                changes against a real circuit's ~20 -- sharp noise
        #                rather than corners.
        #   1/h^2 -> h^0: every harmonic contributes EQUALLY (12.6 / 12.8 /
        #                12.8). This is the one we want, and it is what an
        #                earlier version of this comment wrongly attributed
        #                to 1/h.
        amp = amplitude / (h * h)
        phase = rng.uniform(0.0, 2.0 * np.pi)
        r += amp * np.sin(n_lobes * h * theta + phase)

    # Keep the loop from folding through its own centre. Without this a large
    # amplitude drives r negative and the "circuit" turns inside out.
    r = np.clip(r, 0.35, None)
    r *= base_radius

    x, y = r * np.cos(theta), r * np.sin(theta)
    return SampledTrack(
        name or f"gen{seed:04d}", x, y, half_width=half_width, closed=True,
        smoothing=smoothing, n_resample=2000,
        description=f"[{STYLE_HARMONIC}] Procedurally generated (seed {seed}, {n_lobes} lobes, "
                    f"amplitude {amplitude}, {n_harmonics} harmonics). "
                    f"Deliberately corner-dense; not a model of any real "
                    f"circuit.")


def track_stats(track: SampledTrack, n: int = 3000) -> dict:
    """Geometry summary, used to accept or reject a generated circuit.

    Time-weighted corner fraction, not distance-weighted: a car spends far
    longer per metre in a corner than on a straight, so distance-weighting
    understates how much of TRAINING is spent cornering — which is the whole
    quantity this module exists to raise.
    """
    s = np.linspace(0.0, track.length, n, endpoint=False)
    kappa = np.abs(np.asarray(track.curvature(s)))
    ds = float(s[1] - s[0])
    v_lim = np.minimum(np.sqrt(9.5 / np.maximum(kappa, 1e-9)), 45.0)
    dt = ds / v_lim
    corner = kappa > 1.0 / CORNER_RADIUS_M
    r_min = 1.0 / max(kappa.max(), 1e-9)
    # Longest stretch where the geometry allows a genuinely high speed --
    # the quantity the first generator silently destroyed.
    fast = v_lim > 30.0
    edges = np.diff(np.r_[0, fast.astype(int), 0])
    runs = np.diff(np.flatnonzero(edges))[::2]
    longest_fast = float(runs.max() * ds) if len(runs) else 0.0
    return {
        "length_m": float(track.length),
        "longest_fast_m": longest_fast,
        "min_radius_m": float(r_min),
        "corner_time_fraction": float(dt[corner].sum() / dt.sum()),
        "frac_below_50m": float(np.mean(kappa > 1.0 / 50.0)),
        "sign_changes": int(np.sum(np.sign(np.asarray(track.curvature(s)))[1:]
                                   != np.sign(np.asarray(track.curvature(s)))[:-1])),
    }


def self_intersections(track, n: int = 900) -> int:
    """Count crossings of the centreline with itself.

    A generated loop that crosses itself is not a circuit — the car would
    meet the same tarmac twice at different headings, and every curvilinear
    quantity (`n`, `xi`, half-width) becomes ambiguous there. **No generator
    here guaranteed this; it happened to hold at the parameters in use.**
    That is luck, not a property, and it fails as soon as jitter or amplitude
    rises — so it is checked rather than assumed.

    Vectorised segment-segment intersection: O(n^2) but on ~900 points it is
    milliseconds, and it runs once per candidate track, not per step.
    """
    _, x, y, _ = track.centreline(n)
    P = np.stack([x, y], axis=1)
    A = P
    B = np.roll(P, -1, axis=0)
    d = B - A
    # Pairwise: does segment i cross segment j?
    ax, ay = A[:, 0][:, None], A[:, 1][:, None]
    dx, dy = d[:, 0][:, None], d[:, 1][:, None]
    cx, cy = A[:, 0][None, :], A[:, 1][None, :]
    ex, ey = d[:, 0][None, :], d[:, 1][None, :]
    den = dx * ey - dy * ex
    ok = np.abs(den) > 1e-12
    den = np.where(ok, den, 1.0)
    t1 = ((cx - ax) * ey - (cy - ay) * ex) / den
    t2 = ((cx - ax) * dy - (cy - ay) * dx) / den
    hit = ok & (t1 > 1e-9) & (t1 < 1 - 1e-9) & (t2 > 1e-9) & (t2 < 1 - 1e-9)
    # Ignore self and immediate neighbours, which share endpoints by
    # construction and would otherwise register as crossings.
    idx = np.arange(n)
    sep = np.abs(idx[:, None] - idx[None, :])
    sep = np.minimum(sep, n - sep)
    hit &= sep > 1
    return int(hit.sum() // 2)


def generate_set(n_tracks: int, seed0: int = 0, *, min_radius_m: float = 8.0,
                 max_min_radius_m: float = 90.0,
                 #: Real Spa is 35.2% cornering time. The old 0.55 was set
                 #: when circuits were 3.2 km at base_radius=320 and
                 #: necessarily twisty; at the Spa-matched scale
                 #: (base_radius 1200, ~12 km laps) it is unachievable and
                 #: rejected every candidate. Scaling a circuit up trades
                 #: corner density for speed, and speed is the axis that
                 #: actually set the policy's state distribution.
                 min_corner_fraction: float = 0.28,
                 **kwargs) -> list[SampledTrack]:
    """``n_tracks`` circuits passing the acceptance filter.

    **The filter is the point of this function.** A raw generator produces
    some loops that are nearly circular (no braking to learn) and some with a
    2 m hairpin the car physically cannot take. Both waste training. Accepted
    circuits must be corner-dense AND have a tightest corner the car can
    actually negotiate.

    ``min_radius_m`` floor: at ~0.97 g a 8 m radius allows ~8.7 m/s, which is
    tight but drivable. Below that the corner is a wall.
    """
    out, seed, tries = [], seed0, 0
    while len(out) < n_tracks and tries < n_tracks * 200:
        tries += 1
        seed += 1
        t = generate_track(seed, **kwargs)
        st = track_stats(t)
        if (st["min_radius_m"] >= min_radius_m
                and st["min_radius_m"] <= max_min_radius_m
                and st["corner_time_fraction"] >= min_corner_fraction
                and self_intersections(t) == 0):
            out.append(t)
    if len(out) < n_tracks:
        raise RuntimeError(
            f"only {len(out)}/{n_tracks} circuits passed the filter in "
            f"{tries} attempts — loosen it rather than silently training on "
            f"a biased subset")
    return out


def generate_track_with_straights(
        seed: int, *, n_corners: int = 22, base_radius: float = 1100.0,
        jitter: float = 0.30, corner_radius_m: tuple = (12.0, 250.0),
        half_width: float = 5.0, smoothing: float = 8.0,
        cluster_frac: float = 0.80, long_gap: float = 6.0,
        name: str | None = None) -> SampledTrack:
    """Closed circuit built from **straights joined by circular fillets**.

    **Why this exists and the harmonic generator was not enough.** A radial
    perturbation in polar coordinates cannot produce a straight: blending the
    radius toward a constant gives a circular ARC, not a line. Measured, the
    harmonic generator's longest stretch allowing >30 m/s was 115-139 m
    regardless of parameters, against **1,501 m on Spa** — and a policy
    trained on it reached only ~19 m/s, had never seen a 40 m/s corner entry,
    and spun at **85.8 deg** the first time it met one on a real circuit.

    Straights are not wasted training time. They are what generates the
    high-speed states that make braking necessary, and a circuit without them
    does not contain the problem we are trying to teach.

    Here the geometry is explicit: vertices on a jittered circle, joined by
    straight lines, with each vertex rounded by an arc of a drawn radius. That
    gives **direct control of both** the straight length and the corner radius,
    which the harmonic form never had.

    **`corner_radius_m` upper bound is load-bearing and was wrong.** At
    (12, 70) the fastest corner this generator can construct is
    `sqrt(9.5 x 70) = 25.8 m/s`, so it produced circuits where only 18.5% of
    corner arclength was takeable above 30 m/s against **36.4% on real
    circuits** — i.e. adding straights to fix a high-speed gap made the gap
    WORSE, because the car brakes all the way down again for every corner.
    At (15, 200) it is 33.7%, matching real. The harmonic generator was
    already at 36.7% on this axis and never had the problem.
    """
    rng = np.random.default_rng(seed)
    # Vertices are CLUSTERED, not uniform. Uniform spacing gives either
    # corner density or straights but never both: measured, uniform vertices
    # produced 18-26% cornering with 710-1056 m straights, against the
    # harmonic generator's 72.8% cornering with 124 m straights. Neither is
    # the target.
    #
    # Real circuits are corner COMPLEXES separated by straights, so the gaps
    # between vertices are drawn bimodally: a short gap continues a complex,
    # a long one opens a straight.
    gaps = np.where(rng.random(n_corners) < cluster_frac, 1.0, long_gap)
    gaps *= rng.uniform(0.75, 1.25, n_corners)
    ang = np.cumsum(gaps) / gaps.sum() * 2.0 * np.pi
    rad = base_radius * (1.0 + rng.uniform(-jitter, jitter, n_corners))
    V = np.stack([rad * np.cos(ang), rad * np.sin(ang)], axis=1)

    # Pass 1: solve every fillet first. The straights are then drawn from one
    # fillet's EXIT to the next fillet's ENTRY -- the first version ran them
    # to the next vertex instead, which left gaps and fed splprep a
    # discontinuous path.
    fil = []
    for i in range(n_corners):
        A, B, C = V[i - 1], V[i], V[(i + 1) % n_corners]
        u, v = A - B, C - B
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        if lu < 1e-6 or lv < 1e-6:
            continue
        u, v = u / lu, v / lv
        half = np.arccos(float(np.clip(u @ v, -1.0, 1.0))) / 2.0
        if half < 0.10 or half > np.pi / 2 - 0.03:
            continue
        R = float(rng.uniform(*corner_radius_m))
        t = min(R / np.tan(half), 0.45 * lu, 0.45 * lv)
        R = t * np.tan(half)
        bis = u + v
        nb = np.linalg.norm(bis)
        if nb < 1e-9 or R < 1.0:
            continue
        centre = B + (bis / nb) * (R / np.sin(half))
        P0, P1 = B + u * t, B + v * t
        a0 = float(np.arctan2(*(P0 - centre)[::-1]))
        a1 = float(np.arctan2(*(P1 - centre)[::-1]))
        d = (a1 - a0 + np.pi) % (2 * np.pi) - np.pi
        fil.append((P0, P1, centre, R, a0, d))
    if len(fil) < 3:
        raise RuntimeError(f"seed {seed}: only {len(fil)} usable corners")

    # Pass 2: arc, then straight to the NEXT fillet's entry point.
    pts = []
    for k, (P0, P1, centre, R, a0, d) in enumerate(fil):
        arc = a0 + d * np.linspace(0.0, 1.0, max(int(abs(d) * R / 2.5), 8))
        pts.append(np.stack([centre[0] + R * np.cos(arc),
                             centre[1] + R * np.sin(arc)], axis=1))
        nxt = fil[(k + 1) % len(fil)][0]          # next fillet's entry
        seg = float(np.linalg.norm(nxt - P1))
        if seg > 2.0:
            m = max(int(seg / 10.0), 2)
            # Exclude both endpoints: they are the arc points already emitted.
            frac = np.linspace(0.0, 1.0, m + 2)[1:-1]
            pts.append(P1[None, :] + (nxt - P1)[None, :] * frac[:, None])
    P = np.concatenate(pts, axis=0)
    # splprep rejects duplicated consecutive points.
    keep = np.r_[True, np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-6]
    P = P[keep]
    return SampledTrack(
        name or f"str{seed:04d}", P[:, 0], P[:, 1], half_width=half_width,
        closed=True, smoothing=smoothing, n_resample=2500,
        description=f"[{STYLE_FILLETS}] Straights + fillets (seed {seed}, "
                    f"{n_corners} corners, radii {corner_radius_m[0]:.0f}-"
                    f"{corner_radius_m[1]:.0f} m). Corner-dense WITH real "
                    f"straights; not a model of any circuit.")


def generate_mixed_set(n_tracks: int, seed0: int = 0, *,
                       straight_share: float = 0.5,
                       min_radius_m: float = 9.0) -> list:
    """A training set drawn from BOTH generators.

    Measured, neither alone covers the task:

    | generator | cornering time | longest >30 m/s stretch |
    |---|---|---|
    | harmonic | **72.8%** | 124 m |
    | straights + fillets | 44.4% | **634 m** |
    | real Spa | 40.7% | 1,501 m |

    Training on the harmonic set alone produced a policy that completed 100%
    of laps on held-out generated circuits and then **spun at 85.8 deg on
    real Spa** — it had reached only ~19 m/s and had never experienced a
    40 m/s corner entry, because those circuits contain no straight long
    enough to build one.

    Mixing them is cheaper than compromising: corner-dense circuits teach
    cornering density, straight-bearing ones supply the high-speed states
    that make braking necessary. ``straight_share`` sets the split.
    """
    n_str = int(round(n_tracks * straight_share))
    out, seed = [], seed0
    while len(out) < n_str:
        seed += 1
        try:
            t = generate_track_with_straights(seed)
        except RuntimeError:
            continue
        if (track_stats(t)["min_radius_m"] >= min_radius_m
                and self_intersections(t) == 0):
            out.append(t)
    out += generate_set(n_tracks - n_str, seed0=seed0 + 500_000,
                        min_radius_m=min_radius_m)
    return out


# ---------------------------------------------------------------------------
# Curvature-space generation
# ---------------------------------------------------------------------------
#
# The two generators above are **star-shaped**: a single-valued radial
# function r(theta) > 0. That is provably a Jordan curve, which is why neither
# ever self-intersects -- and it is the same reason neither can produce a
# hairpin folding back onto a straight, a crossover, or anything like Eau
# Rouge. Measured: **1 of 25 real circuits is star-shaped** (IMS, an oval);
# the median real circuit spends 27% of its lap backtracking in polar angle.
# So that whole family excludes 24 of the 25 circuits we validate against.
# "Guaranteed simple" and "cannot double back" are the same constraint.
#
# Working directly in curvature space removes it. Specify kappa(s), integrate
# to heading and then to position:
#
#     theta(s) = integral_0^s kappa      x(s) = integral_0^s cos(theta)
#                                        y(s) = integral_0^s sin(theta)
#
# Closure needs three things, and the first is free: with
# kappa = 2*pi/L + (a zero-mean Fourier perturbation), the turning integral is
# exactly 2*pi by construction, so only x(L) = 0 and y(L) = 0 remain. Two
# constraints, two free coefficients, Newton.
#
# The trade is explicit and is the OPPOSITE of the polar form's: arbitrary
# shape and exact curvature control, at the cost of losing the simplicity
# guarantee -- roughly a third of solved curves cross themselves and must be
# rejected. That is why `self_intersections()` is a real filter here and a
# no-op for `generate_track`.


def _integrate_curvature(kappa: np.ndarray, ds: float):
    """kappa(s) -> (x, y, heading), by cumulative trapezoid."""
    theta = np.concatenate([[0.0], np.cumsum(0.5 * (kappa[1:] + kappa[:-1])) * ds])
    x = np.concatenate([[0.0], np.cumsum(0.5 * (np.cos(theta[1:])
                                                + np.cos(theta[:-1]))) * ds])
    y = np.concatenate([[0.0], np.cumsum(0.5 * (np.sin(theta[1:])
                                                + np.sin(theta[:-1]))) * ds])
    return x, y, theta


def _closure_residual(coef, base, harm, s, ds):
    """(x(L), y(L)) for a curvature profile with two coefficients varied."""
    k = base + coef[0] * np.cos(harm * s) + coef[1] * np.sin(harm * s)
    x, y, _ = _integrate_curvature(k, ds)
    return np.array([x[-1], y[-1]]), k


def generate_track_curvature_space(
        seed: int, *, length_m: float = 9000.0, n_harmonics: int = 9,
        target_min_radius_m: float = 18.0, n_points: int = 3000,
        half_width: float = 5.0, smoothing: float = 12.0,
        max_newton: int = 40, name: str | None = None) -> SampledTrack:
    """A closed circuit specified by its curvature profile.

    ``target_min_radius_m`` sets the perturbation scale, and doing it this
    way rather than "relative to the base curvature" is the correction that
    made this generator work at all. The base is ``2*pi/L`` = 7e-4 for a 9 km
    lap, while a 15 m corner is ``kappa`` = 0.067 -- a factor of ~100. A
    perturbation scaled as a small multiple of the base produces a near
    perfect circle: measured, minimum radius 704 m and **0.0% cornering
    time**.

    The exact bound ``max|kappa| <= 2*pi/L + sum_h sqrt(a_h^2 + b_h^2)`` is
    what makes this controllable -- the harmonic amplitudes are set so that
    sum equals the target curvature, so minimum radius needs no search.

    Raises ``RuntimeError`` if Newton fails to close the loop, or if the
    solved curve self-intersects. Both are expected outcomes for a fraction
    of seeds -- the caller retries with another.
    """
    rng = np.random.default_rng(seed)
    L = float(length_m)
    s = np.linspace(0.0, L, n_points)
    ds = float(s[1] - s[0])
    k0 = 2.0 * np.pi / L

    # Zero-mean perturbation => the turning integral stays exactly 2*pi, so
    # tangent closure never enters the Newton solve.
    # Budget the total harmonic amplitude against the exact bound above, so
    # the tightest corner lands near the target instead of being discovered.
    k_target = 1.0 / float(target_min_radius_m)
    budget = max(k_target - k0, 1e-6)
    w = rng.uniform(0.4, 1.0, n_harmonics) / np.arange(2, n_harmonics + 2) ** 0.55
    w = w / w.sum() * budget
    base = np.full(n_points, k0)
    for i, h in enumerate(range(2, n_harmonics + 2)):
        ph = rng.uniform(0.0, 2.0 * np.pi)
        base = base + w[i] * np.cos(2.0 * np.pi * h * s / L + ph)

    # Two free coefficients on the first harmonic, solved for position closure.
    harm = 2.0 * np.pi / L
    coef = np.zeros(2)
    res, k = _closure_residual(coef, base, harm, s, ds)
    for _ in range(max_newton):
        if np.linalg.norm(res) < 1e-3 * L:
            break
        J = np.zeros((2, 2))
        for j in range(2):
            d = np.zeros(2)
            d[j] = 1e-6 * k0
            rp, _ = _closure_residual(coef + d, base, harm, s, ds)
            J[:, j] = (rp - res) / d[j]
        try:
            step = np.linalg.solve(J, -res)
        except np.linalg.LinAlgError:
            raise RuntimeError(f"seed {seed}: singular Jacobian")
        # Damped: the residual is strongly nonlinear in the coefficients and
        # a full Newton step routinely overshoots into a wildly different loop.
        coef = coef + 0.5 * step
        res, k = _closure_residual(coef, base, harm, s, ds)
    if np.linalg.norm(res) >= 1e-3 * L:
        raise RuntimeError(f"seed {seed}: closure failed, "
                           f"residual {np.linalg.norm(res):.1f} m")

    x, y, _ = _integrate_curvature(k, ds)
    t = SampledTrack(name or f"cs{seed:04d}", x[:-1], y[:-1],
                     half_width=half_width, closed=True, smoothing=smoothing,
                     n_resample=2500,
                     description=f"Curvature-space generated (seed {seed}, "
                                 f"L={L:.0f} m, {n_harmonics} harmonics, "
                                 f"target min r {target_min_radius_m:.0f} m). Not star-shaped: "
                                 f"may double back, unlike the polar forms.")
    if self_intersections(t) > 0:
        raise RuntimeError(f"seed {seed}: self-intersecting")
    return t


def generate_curvature_set(n_tracks: int, seed0: int = 0, *,
                           min_radius_m: float = 9.0,
                           max_attempts_per: int = 60, **kwargs) -> list:
    """``n_tracks`` curvature-space circuits, retrying rejected seeds."""
    out, seed, tries = [], seed0, 0
    while len(out) < n_tracks and tries < n_tracks * max_attempts_per:
        tries += 1
        seed += 1
        try:
            t = generate_track_curvature_space(seed, **kwargs)
        except RuntimeError:
            continue
        if track_stats(t)["min_radius_m"] >= min_radius_m:
            out.append(t)
    if len(out) < n_tracks:
        raise RuntimeError(f"only {len(out)}/{n_tracks} in {tries} attempts")
    return out


def generate_track_corner_sequence(
        seed: int, *, length_m: float = 7500.0, n_corners: int = 14,
        min_radius_m: float = 14.0, max_radius_m: float = 220.0,
        counter_frac: float = 0.30,
        n_points: int = 3000, half_width: float = 5.0, smoothing: float = 10.0,
        max_newton: int = 60, name: str | None = None) -> SampledTrack:
    """Curvature-space, but built as **localised corners joined by straights**.

    The pure-Fourier version of curvature-space generation
    (`generate_track_curvature_space`) fails for a structural reason worth
    recording: a Fourier profile puts curvature *everywhere along the lap*,
    so the curve folds over itself. Measured at a 18 m target minimum radius,
    **73 of 80 seeds self-intersected**; backing the amplitude off far enough
    to stop that gives a near-circle (704 m minimum radius, 0.0% cornering).
    There is no amplitude that gives both.

    Real circuits are not like that. They are **kappa = 0 for most of their
    length**, with curvature concentrated into short corners -- which is
    exactly why Spa fits an 11.4 m hairpin into 7 km without crossing itself.

    So: kappa(s) is a sum of raised-cosine bumps at random positions, zero
    between them. Turning closure (integral kappa ds = 2*pi) is imposed by
    scaling all the bump amplitudes together, which is exact and needs no
    solve. Position closure is two constraints, solved by damped Newton on
    two bump amplitudes.
    """
    rng = np.random.default_rng(seed)
    L = float(length_m)
    s = np.linspace(0.0, L, n_points)
    ds = float(s[1] - s[0])

    centres = np.sort(rng.uniform(0.0, L, n_corners))
    radii = rng.uniform(min_radius_m, max_radius_m, n_corners)
    # A loop with net turning 2*pi made of same-sign corners is convex and
    # cannot cross itself; every opposite-sign ("counter") corner is what
    # buys an interesting shape AND what risks folding. Measured at 50/50
    # signs, 83% of solved curves self-intersected. `counter_frac` is that
    # dial, exposed rather than buried at 0.5.
    signs = np.where(rng.random(n_corners) < counter_frac, -1.0, 1.0)
    # Corner arc length: enough to turn a plausible angle at that radius.
    widths = radii * rng.uniform(0.5, 1.6, n_corners)

    def profile(scale, amps):
        k = np.zeros(n_points)
        for c, r, sg, w, a in zip(centres, radii, signs, widths, amps):
            d = np.abs((s - c + L / 2) % L - L / 2)
            m = d < w
            # Raised cosine: smooth entry and exit, so curvature RATE stays
            # bounded -- the property clothoids exist to guarantee.
            k[m] += sg * a * (1.0 / r) * 0.5 * (1.0 + np.cos(np.pi * d[m] / w))
        # Exact turning closure by construction.
        tot = np.trapezoid(k, dx=ds)
        if abs(tot) < 1e-12:
            raise RuntimeError(f"seed {seed}: degenerate profile")
        return k * (2.0 * np.pi / tot) * scale

    # Closure rides on a SMOOTH low-harmonic correction, not on the bump
    # amplitudes. Solving it with two bump amplitudes was badly conditioned --
    # a bump barely moves the endpoint without destroying the corner it
    # belongs to, and it accepted 1 seed in 100 (60 closure failures). A
    # first-harmonic correction moves the endpoint strongly while leaving
    # every corner essentially intact, because it is spread over the whole
    # lap at low amplitude.
    base_k = profile(1.0, np.ones(n_corners))
    c1, c2 = np.cos(2.0 * np.pi * s / L), np.sin(2.0 * np.pi * s / L)

    def resid(ab):
        k = base_k + ab[0] * c1 + ab[1] * c2
        k = k * (2.0 * np.pi / np.trapezoid(k, dx=ds))   # keep turning exact
        x, y, _ = _integrate_curvature(k, ds)
        return np.array([x[-1], y[-1]]), k

    ab = np.zeros(2)
    r0, k = resid(ab)
    scale = 2.0 * np.pi / L
    for _ in range(max_newton):
        if np.linalg.norm(r0) < 2e-3 * L:
            break
        J = np.zeros((2, 2))
        for j in range(2):
            d = ab.copy()
            d[j] += 1e-3 * scale
            rp, _ = resid(d)
            J[:, j] = (rp - r0) / (1e-3 * scale)
        try:
            step = np.linalg.solve(J, -r0)
        except np.linalg.LinAlgError:
            raise RuntimeError(f"seed {seed}: singular Jacobian")
        ab = ab + 0.6 * step
        r0, k = resid(ab)
    if np.linalg.norm(r0) >= 2e-3 * L:
        raise RuntimeError(f"seed {seed}: closure residual "
                           f"{np.linalg.norm(r0):.0f} m")

    x, y, _ = _integrate_curvature(k, ds)
    t = SampledTrack(name or f"cq{seed:04d}", x[:-1], y[:-1],
                     half_width=half_width, closed=True, smoothing=smoothing,
                     n_resample=2500,
                     description=f"[{STYLE_CURVATURE}] Corner-sequence (seed "
                                 f"{seed}, {n_corners} corners, radii "
                                 f"{min_radius_m:.0f}-{max_radius_m:.0f} m). "
                                 f"Not star-shaped: may double back.")
    if self_intersections(t) > 0:
        raise RuntimeError(f"seed {seed}: self-intersecting")
    return t




def generate_track_arcade(
        seed: int, *, n_checkpoints: int = 18, base_radius: float = 500.0,
        radius_jitter: float = 0.45, step_m: float = 6.0,
        min_radius_m: float = 30.0, half_width: float = 5.0,
        smoothing: float = 25.0, max_steps: int = 20000,
        name: str | None = None) -> SampledTrack:
    """**Arcade style** — flowing arcs, few long straights. Not realistic, and
    deliberately so.

    This is OpenAI Gym `CarRacing-v0`'s construction, scaled to a full-size
    car. A point marches forward at a fixed `step_m` while its heading turns
    toward the current checkpoint **by at most a bounded rate**; when it gets
    close, it targets the next one. The turn-rate bound is what produces
    continuously flowing curves rather than corner-straight-corner, and it
    sets the minimum radius exactly:

        min_radius = step_m / max_turn_per_step

    CarRacing uses 3.5 units per step and 0.31 rad, giving 11.29 m against a
    6.67 m half-width. Here the bound is derived from `min_radius_m` instead,
    so the geometry is drivable by *our* car rather than by a magic constant.

    **`min_radius_m` is the pursuit's bound, not the delivered radius.** The
    spline fit tightens corners past it: asking for 15 m delivers 6-7 m. The
    default asks for 30 and delivers ~17. Measured, not assumed -- and a
    reason to check `track_stats` rather than trust the parameter.

    Defaults chosen by sweep: 18 checkpoints on a 500 m base gives **40.4%
    cornering time against real Spa's 35.2%**, minimum radius 17.3 m, on a
    4.6 km lap. Median achievable speed is 28 m/s against Spa's 37 -- lower
    because the style is twistier, which is the point of it, not a defect.

    **Known property, not a defect:** curvature is piecewise-constant with
    step discontinuities at checkpoint hand-over, so there are no clothoid
    transitions. Spline smoothing rounds them. Tagged `STYLE_ARCADE` so a
    result on these is never quietly reported as a result on realistic
    geometry.
    """
    rng = np.random.default_rng(seed)
    turn_max = step_m / float(min_radius_m)

    ang = np.sort(rng.uniform(0.0, 2.0 * np.pi, n_checkpoints))
    rad = base_radius * (1.0 + rng.uniform(-radius_jitter, radius_jitter,
                                           n_checkpoints))
    cps = np.stack([rad * np.cos(ang), rad * np.sin(ang)], axis=1)

    p = cps[0].copy()
    heading = float(np.arctan2(*(cps[1] - cps[0])[::-1]))
    pts = [p.copy()]
    target = 1
    laps = 0
    for _ in range(max_steps):
        tgt = cps[target % n_checkpoints]
        want = float(np.arctan2(*(tgt - p)[::-1]))
        d = (want - heading + np.pi) % (2.0 * np.pi) - np.pi
        heading += float(np.clip(d, -turn_max, turn_max))
        p = p + step_m * np.array([np.cos(heading), np.sin(heading)])
        pts.append(p.copy())
        if np.linalg.norm(tgt - p) < step_m * 4.0:
            target += 1
            if target > n_checkpoints:
                laps = 1
                break
    if not laps:
        raise RuntimeError(f"seed {seed}: pursuit never closed the loop")

    P = np.array(pts)
    # The pursuit ends near the start but not on it; drop the tail so the
    # spline's periodic fit is not asked to bridge a visible gap.
    gap = np.linalg.norm(P[-1] - P[0])
    if gap > step_m * 8.0:
        raise RuntimeError(f"seed {seed}: closure gap {gap:.0f} m")
    keep = np.r_[True, np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-6]
    P = P[keep]
    t = SampledTrack(name or f"ar{seed:04d}", P[:, 0], P[:, 1],
                     half_width=half_width, closed=True, smoothing=smoothing,
                     n_resample=2500,
                     description=f"[{STYLE_ARCADE}] Bounded-turn-rate pursuit "
                                 f"(seed {seed}, {n_checkpoints} checkpoints, "
                                 f"step {step_m:.0f} m, min radius "
                                 f"{min_radius_m:.0f} m). CarRacing-v0's "
                                 f"construction scaled to a full-size car. "
                                 f"Flowing arcs, few long straights; NOT a "
                                 f"model of a real circuit.")
    t.style = STYLE_ARCADE
    if self_intersections(t) > 0:
        raise RuntimeError(f"seed {seed}: self-intersecting")
    return t


def generate_arcade_set(n_tracks: int, seed0: int = 0, *,
                        min_radius_m: float = 9.0,
                        min_corner_fraction: float = 0.30,
                        **kwargs) -> list:
    """``n_tracks`` arcade circuits that the car can actually drive.

    **The minimum-radius filter is not optional here.** The pursuit bound is
    a bound on the MARCHING path, not on the fitted spline: at a 30 m bound
    the delivered minimum radius ranges 1.3-16.5 m across seeds, because the
    spline tightens corners at checkpoint hand-over. An unfiltered set
    returned 3 drivable circuits out of 8 and the other 5 had corners the car
    physically cannot take.
    """
    out, seed, tries = [], seed0, 0
    while len(out) < n_tracks and tries < n_tracks * 200:
        tries += 1
        seed += 1
        try:
            t = generate_track_arcade(seed, **kwargs)
        except RuntimeError:
            continue
        st = track_stats(t)
        if (st["min_radius_m"] >= min_radius_m
                and st["corner_time_fraction"] >= min_corner_fraction):
            out.append(t)
    if len(out) < n_tracks:
        raise RuntimeError(f"only {len(out)}/{n_tracks} in {tries} attempts")
    return out
