"""Generated circuits must be closed, drivable, and corner-dense.

Each of these encodes a failure the generator actually produced during
development, so none of them is decoration (CLAUDE.md rule 11).
"""

import numpy as np
import pytest

from physics.track_gen import generate_track, generate_set, track_stats


def test_generated_tracks_close_exactly():
    """Closure is structural (periodic radial perturbation), so this should
    hold to floating point, not to a tolerance that hides a real gap."""
    for seed in (1, 7, 23):
        t = generate_track(seed)
        _, x, y, _ = t.centreline(2000)
        gap = float(np.hypot(x[0] - x[-1], y[0] - y[-1]))
        assert gap < 15.0, f"seed {seed} leaves a {gap:.1f} m gap"


def test_minimum_radius_is_drivable():
    """The first generator produced 0.4-1.3 m minimum radii -- the car needs
    ~8 m at 0.97 g. Caused by a 1/h harmonic envelope, where curvature
    (~ amplitude x frequency^2) is dominated by the HIGHEST harmonic."""
    for t in generate_set(6, seed0=100):
        st = track_stats(t)
        assert st["min_radius_m"] >= 8.0, (
            f"{t.name} has a {st['min_radius_m']:.1f} m corner -- undrivable")


def test_tracks_are_corner_dense():
    """**The threshold moved deliberately and the reason matters.** It was
    0.55, set when circuits were 3.2 km at base_radius=320 and necessarily
    twisty. Those circuits then failed to transfer to a real one, because
    their median achievable speed was 20.6 m/s against Spa's 37.2 -- scale,
    not curvature, set the policy's state distribution (F113).

    Scaling up to match Spa's speed necessarily trades corner density for
    speed. Real Spa is 35.2% cornering TIME, so demanding 55% at that scale
    is incoherent; the filter now asks 0.28 and delivers ~35%."""
    fracs = [track_stats(t)["corner_time_fraction"] for t in generate_set(6, seed0=200)]
    assert np.mean(fracs) > 0.28, f"mean corner time only {np.mean(fracs):.1%}"


def test_the_filter_actually_rejects_things():
    """A filter that accepts everything is not a filter. The raw generator at
    a high lobe count produces sub-8 m radii, so demanding them must fail."""
    with pytest.raises(RuntimeError, match="passed the filter"):
        generate_set(3, seed0=300, n_lobes=18, amplitude=0.40,
                     min_radius_m=8.0)


def test_generation_is_deterministic():
    a, b = generate_track(42), generate_track(42)
    s = np.linspace(0.0, min(a.length, b.length), 500, endpoint=False)
    assert np.allclose(a.curvature(s), b.curvature(s))
    assert not np.allclose(a.curvature(s), generate_track(43).curvature(s))


def test_self_intersection_detector_catches_a_figure_of_eight():
    """A guard that never fires is not a guard. A figure-of-eight is the
    canonical self-intersecting loop, so the detector must find its crossing."""
    from physics.track import SampledTrack
    from physics.track_gen import self_intersections
    t = np.linspace(0.0, 2.0 * np.pi, 600, endpoint=False)
    # Lemniscate: crosses itself exactly once, at the origin.
    x, y = 300.0 * np.cos(t), 300.0 * np.sin(t) * np.cos(t)
    fig8 = SampledTrack("fig8", x, y, half_width=5.0, closed=True,
                        smoothing=5.0, n_resample=900)
    assert self_intersections(fig8) >= 1, "detector missed a figure-of-eight"


def test_generated_tracks_do_not_self_intersect():
    from physics.track_gen import self_intersections
    for t in generate_set(5, seed0=40000):
        assert self_intersections(t) == 0, f"{t.name} crosses itself"


def test_every_generator_tags_its_style():
    """Four generator families with genuinely different geometry. A result on
    arcade circuits must never be reportable as a result on realistic ones,
    so the family travels with the track."""
    from physics.track_gen import (generate_track_with_straights,
                                   generate_track_arcade, STYLE_HARMONIC,
                                   STYLE_FILLETS, STYLE_ARCADE)
    for make, style in ((lambda: generate_track(1), STYLE_HARMONIC),
                        (lambda: generate_track_with_straights(1), STYLE_FILLETS),
                        (lambda: generate_track_arcade(1), STYLE_ARCADE)):
        t = make()
        assert style in t.description, f"{t.name} not tagged {style}"


def test_arcade_circuits_are_corner_dense_and_drivable():
    """The point of the arcade family: flowing curves, few straights. Real
    circuits average 40.7% cornering TIME; these should be at least that."""
    from physics.track_gen import generate_arcade_set
    ts = generate_arcade_set(8, seed0=0)
    assert len(ts) == 8
    # The SET function must guarantee drivability -- an earlier version did
    # not filter on radius at all and returned circuits with 1.3 m corners.
    for t in ts:
        assert track_stats(t)["min_radius_m"] >= 9.0, (
            f"{t.name} has a {track_stats(t)['min_radius_m']:.1f} m corner")
    cf = np.mean([track_stats(t)["corner_time_fraction"] for t in ts])
    assert cf > 0.30, f"arcade cornering only {cf:.1%}"
