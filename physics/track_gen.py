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

#: Radius below which a point counts as "in a corner" for the density
#: statistics. Matches the threshold used to measure the 59.3% figure above.
CORNER_RADIUS_M = 200.0


def generate_track(seed: int, *, base_radius: float = 320.0,
                   n_lobes: int = 8, amplitude: float = 0.20,
                   n_harmonics: int = 3, half_width: float = 5.0,
                   n_points: int = 1200, smoothing: float = 20.0,
                   name: str | None = None) -> SampledTrack:
    """One closed circuit.

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
        description=f"Procedurally generated (seed {seed}, {n_lobes} lobes, "
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
                 max_min_radius_m: float = 60.0,
                 min_corner_fraction: float = 0.55,
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
        seed: int, *, n_corners: int = 22, base_radius: float = 600.0,
        jitter: float = 0.30, corner_radius_m: tuple = (15.0, 200.0),
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
        description=f"Generated from straights + fillets (seed {seed}, "
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
