"""The round-trip test TRACKS.md's staging step 1 requires before any real
circuit data touches SampledTrack.

Take a track whose curvature is known exactly (``long_exit``, built from
analytic Segments), sample its centreline the way a real circuit's would
arrive (a list of (x, y) points, possibly noisy), recover curvature with
SampledTrack, and compare against the ground truth. This is the check
TRACKS.md's own survey ran once by hand (§2: clean data recovers to 1.16e-05,
390x-the-signal if you skip the spline and finite-difference the raw
coordinates instead) — made a permanent, automated regression here rather
than a one-off measurement.
"""

from __future__ import annotations

import numpy as np
import pytest

from physics.track import ENTRY_STRAIGHT, CORNER_ARC, SampledTrack, long_exit


def _clean_sample(track, n=4000):
    s, x, y, _ = track.centreline(n)
    return s, x, y


def test_recovers_curvature_on_clean_data():
    """No noise: the spline should interpolate essentially exactly."""
    truth = long_exit()
    s, x, y = _clean_sample(truth)
    sampled = SampledTrack("long_exit_roundtrip", x, y, truth.half_width,
                           smoothing=0.0, closed=False)

    kappa_true = truth.curvature(s)
    kappa_recovered = sampled.curvature(s)
    err = np.max(np.abs(kappa_true - kappa_recovered))
    # TRACKS.md's own measurement on this exact round-trip: 1.16e-05. A
    # generous margin (1e-3) rather than pinning the exact figure -- the
    # point of this test is "the pipeline works", not reproducing a specific
    # float, and n/spline-library details can shift it slightly.
    assert err < 1e-3, f"clean-data curvature error {err:.2e} exceeds 1e-3"


def test_length_matches_within_spline_discretisation():
    truth = long_exit()
    s, x, y = _clean_sample(truth)
    sampled = SampledTrack("long_exit_roundtrip", x, y, truth.half_width,
                           smoothing=0.0, closed=False)
    assert sampled.length == pytest.approx(truth.length, rel=1e-3)


def test_straight_sections_recover_zero_curvature():
    truth = long_exit()
    s, x, y = _clean_sample(truth)
    sampled = SampledTrack("long_exit_roundtrip", x, y, truth.half_width,
                           smoothing=0.0, closed=False)
    # well inside the entry straight, away from the corner-join blend zone
    assert sampled.curvature(np.array([10.0]))[0] == pytest.approx(0.0, abs=1e-3)
    # well inside the exit straight
    assert sampled.curvature(np.array([truth.length - 20.0]))[0] == \
        pytest.approx(0.0, abs=1e-3)


def test_corner_curvature_sign_and_magnitude():
    """long_exit's corner is a left-hander (positive curvature, 1/40 m)."""
    truth = long_exit()
    s, x, y = _clean_sample(truth)
    sampled = SampledTrack("long_exit_roundtrip", x, y, truth.half_width,
                           smoothing=0.0, closed=False)
    mid_s = ENTRY_STRAIGHT + 0.5 * CORNER_ARC
    got = sampled.curvature(np.array([mid_s]))[0]
    assert got == pytest.approx(1.0 / 40.0, rel=0.02)


def test_noisy_data_stays_far_below_the_naive_finite_difference_trap():
    """TRACKS.md's headline number: naive finite-differencing of 2cm-noisy
    points is 390x the corner's own curvature signal. A smoothed spline fit
    must not be anywhere close to that, even if it is not as tight as the
    clean case."""
    rng = np.random.default_rng(0)
    truth = long_exit()
    # TRACKS.md's own measurement (Sec. 2) used 4,000 points spaced ~0.1 m --
    # match it, since the naive trap's severity scales with point density
    # (noise amplification through a second difference grows as ~1/dx^2) and
    # a sparser sample understates it.
    s, x, y = _clean_sample(truth, n=4000)
    noise = 0.02  # 2 cm, TRACKS.md's own pessimistic noise level
    xn = x + rng.normal(0.0, noise, size=x.shape)
    yn = y + rng.normal(0.0, noise, size=y.shape)

    # the naive trap: finite-difference heading from noisy points directly
    dxn, dyn = np.gradient(xn), np.gradient(yn)
    ddxn, ddyn = np.gradient(dxn), np.gradient(dyn)
    denom = np.power(dxn**2 + dyn**2, 1.5)
    naive_kappa = (dxn * ddyn - dyn * ddxn) / denom
    naive_err = np.max(np.abs(naive_kappa[50:-50] - truth.curvature(s)[50:-50]))

    # "Tuned" here means scipy's own convention for splprep with unweighted
    # points: s ~= m (the point count) is the documented default smoothing
    # target. Verified directly against this exact noisy dataset: s=0.05 (an
    # untuned guess) gave err=42 -- worse than the naive trap it's supposed to
    # beat -- while s=m gave err=0.015, matching TRACKS.md's own measured
    # "tuned smoothing spline" row (0.013). The lesson generalises: smoothing
    # must scale with point count, not be a fixed constant.
    sampled = SampledTrack("long_exit_noisy", xn, yn, truth.half_width,
                           smoothing=len(xn), closed=False)
    got_err = np.max(np.abs(sampled.curvature(s) - truth.curvature(s)))

    corner_kappa = 1.0 / 40.0
    assert naive_err > 50 * corner_kappa, (
        "sanity check on the trap itself failed -- naive finite-differencing "
        "should be wildly wrong on noisy data")
    assert got_err < 2 * corner_kappa, (
        f"smoothed-spline recovery ({got_err:.4f}) should stay within a "
        f"couple of corner-curvatures ({corner_kappa:.4f}) of the truth, "
        f"nowhere near the naive trap ({naive_err:.4f})")


def test_to_xy_round_trips_through_centreline():
    truth = long_exit()
    s, x, y = _clean_sample(truth)
    sampled = SampledTrack("long_exit_roundtrip", x, y, truth.half_width,
                           smoothing=0.0, closed=False)
    probe_s = np.array([50.0, 100.0, 200.0, 300.0])
    xs, ys = sampled.to_xy(probe_s, np.zeros_like(probe_s))
    # centreline (n=0) should land on the fitted centreline itself
    _, xref, yref, _ = sampled.centreline(2000)
    sref, _, _, _ = sampled.centreline(2000)
    for i, sv in enumerate(probe_s):
        j = np.argmin(np.abs(sref - sv))
        assert xs[i] == pytest.approx(xref[j], abs=0.5)
        assert ys[i] == pytest.approx(yref[j], abs=0.5)


def _circle(radius, n=400):
    theta = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    return theta, radius * np.cos(theta), radius * np.sin(theta)


def test_half_width_at_defaults_to_constant():
    """No `width=` given: half_width_at must reproduce the scalar constant
    everywhere, matching Track's interface exactly -- this is the backward
    compatibility every existing caller relies on."""
    truth = long_exit()
    s, x, y = _clean_sample(truth)
    sampled = SampledTrack("long_exit_roundtrip", x, y, truth.half_width,
                           smoothing=0.0, closed=False)
    probe = np.array([0.0, 50.0, 200.0, truth.length])
    got = sampled.half_width_at(probe)
    assert np.all(got == truth.half_width)


def test_half_width_at_recovers_variable_width_on_a_closed_track():
    """TRACKS.md staging step 2: a real circuit's half-width varies along s.
    Round-trip against a known width function on a closed synthetic track
    (a circle), the same known-ground-truth pattern the curvature test uses
    at step 1."""
    radius = 50.0
    theta, x, y = _circle(radius)
    width_true = 5.0 + 5.0 * (theta / (2 * np.pi))  # ramps 5 m -> 10 m
    track = SampledTrack("circle", x, y, half_width=7.5, closed=True,
                         width=width_true, smoothing=0.0)

    s_test = np.linspace(0.0, track.length, 50, endpoint=False)
    w_true = 5.0 + 5.0 * ((s_test / radius) / (2 * np.pi))
    w_got = track.half_width_at(s_test)
    err = np.max(np.abs(w_got - w_true))
    assert err < 0.01, f"variable-width recovery error {err:.4f} exceeds 0.01 m"


def test_half_width_at_wraps_at_the_seam_on_a_closed_track():
    """s=0 and s=length are the same physical point on a closed track;
    half_width_at must not silently flat-extrapolate past the raw points'
    own range at the seam (a real risk since periodic splprep does not
    require the last raw point to equal the first)."""
    radius = 50.0
    theta, x, y = _circle(radius)
    width_true = 7.0 + 0.5 * np.sin(theta)  # smooth, genuinely periodic
    track = SampledTrack("circle", x, y, half_width=7.5, closed=True,
                         width=width_true, smoothing=0.0)
    just_before_end = track.half_width_at(np.array([track.length - 1e-3]))[0]
    just_after_start = track.half_width_at(np.array([1e-3]))[0]
    assert just_before_end == pytest.approx(just_after_start, abs=0.05)
