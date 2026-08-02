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
        # 1/h^2, NOT 1/h. Curvature of a radial perturbation scales roughly
        # with amplitude x frequency^2, so a 1/h envelope leaves every
        # harmonic contributing EQUALLY to curvature and the highest one
        # dominates. Measured with 1/h: minimum radius 0.4-1.3 m (the car
        # needs >= 8 m) and 52-84 curvature sign changes against a real
        # circuit's ~20 -- sharp noise, not corners.
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
    return {
        "length_m": float(track.length),
        "min_radius_m": float(r_min),
        "corner_time_fraction": float(dt[corner].sum() / dt.sum()),
        "frac_below_50m": float(np.mean(kappa > 1.0 / 50.0)),
        "sign_changes": int(np.sum(np.sign(np.asarray(track.curvature(s)))[1:]
                                   != np.sign(np.asarray(track.curvature(s)))[:-1])),
    }


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
                and st["corner_time_fraction"] >= min_corner_fraction):
            out.append(t)
    if len(out) < n_tracks:
        raise RuntimeError(
            f"only {len(out)}/{n_tracks} circuits passed the filter in "
            f"{tries} attempts — loosen it rather than silently training on "
            f"a biased subset")
    return out
