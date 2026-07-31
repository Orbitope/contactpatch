"""TRACKS.md staging step 3: one real circuit, imported and validated.

Validated against a **published, independently-sourced** figure (rule 2),
not against our own fit: Spa-Francorchamps's Grand Prix layout is widely and
consistently documented at 7.004 km / 19-20 corners (multiple independent
race reports agree; not derived from anything in this repository).

No independently published PER-CORNER radius was found for La Source during
this work (general descriptions call it "tight", "first gear", but no source
gave a number) — TRACKS.md's own "~25 m" figure has no citation either, so it
is deliberately NOT used here as if it were external. The minimum radius
recovered below is reported as `[MEASURED]` only, checked for physical
plausibility (a modern FIA circuit's tightest corners run ~8-15 m) rather
than against a hard published number, and that gap is stated rather than
papered over with an unsourced figure from our own docs.

Requires network access to TUM's racetrack-database (github.com); skipped
cleanly rather than failed if that is not available, since CI/offline
environments should not hard-fail on an external dependency this project
does not control.
"""

from __future__ import annotations

import urllib.error
import urllib.request

import numpy as np
import pytest

from physics.tracks_data import DEFAULT_SMOOTHING, download_track_csv, load_real_track

SPA_URL = "https://raw.githubusercontent.com/TUMFTM/racetrack-database/master/tracks/Spa.csv"


def _network_available() -> bool:
    try:
        urllib.request.urlopen(SPA_URL, timeout=5.0)
        return True
    except (urllib.error.URLError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _network_available(),
    reason="TUM racetrack-database (github.com) not reachable")


def test_download_caches_and_does_not_refetch(tmp_path):
    path = download_track_csv("Spa", cache_dir=tmp_path)
    assert path.exists()
    mtime = path.stat().st_mtime
    path2 = download_track_csv("Spa", cache_dir=tmp_path)
    assert path2 == path
    assert path.stat().st_mtime == mtime  # not re-downloaded


def test_spa_length_matches_the_published_lap_length(tmp_path):
    """7.004 km, 19-20 corners: consistently reported across independent
    race sources (multiple seasons' Belgian GP results), not derived from
    anything this project produced."""
    track = load_real_track("Spa", cache_dir=tmp_path)
    published_m = 7004.0
    err_pct = 100.0 * abs(track.length - published_m) / published_m
    assert err_pct < 0.5, (
        f"recovered length {track.length:.1f} m is {err_pct:.2f}% off the "
        f"published {published_m} m -- TRACKS.md's own prior survey measured "
        f"~0.2% here, so anything much worse than that is a regression")


def test_spa_curvature_is_physically_plausible_not_a_fit_artefact():
    """No published per-corner radius to check against (see module
    docstring) -- this instead guards the failure mode that WAS measured
    directly: exact interpolation (smoothing=0) fits residual point-spacing
    noise as a spurious 5.8 m 'corner', tighter than anything on a real FIA
    circuit. DEFAULT_SMOOTHING must stay in the plateau that avoids it."""
    track = load_real_track("Spa")
    s = np.linspace(0.0, track.length, 5000, endpoint=False)
    kappa = np.abs(track.curvature(s))
    min_radius = 1.0 / np.max(kappa)
    # Measured plateau (see DEFAULT_SMOOTHING's comment): 9-11.5 m for
    # 10 <= smoothing <= 300. A generous band around that, not the exact
    # figure -- the point is "not an artefact", not a pinned float.
    assert 7.0 < min_radius < 20.0, (
        f"minimum radius {min_radius:.1f} m is outside the plausible band "
        f"for a modern FIA circuit's tightest corner -- check DEFAULT_SMOOTHING")


def test_exact_interpolation_would_have_been_an_artefact():
    """Documents the actual measurement DEFAULT_SMOOTHING is based on, as a
    regression check: smoothing=0 on this real dataset must stay obviously
    too tight, or the story in the module docstring is no longer true."""
    exact = load_real_track("Spa", smoothing=0.0)
    smoothed = load_real_track("Spa", smoothing=DEFAULT_SMOOTHING)
    s = np.linspace(0.0, exact.length, 5000, endpoint=False)
    r_exact = 1.0 / np.max(np.abs(exact.curvature(s)))
    r_smoothed = 1.0 / np.max(np.abs(smoothed.curvature(s)))
    assert r_exact < 7.0, (
        "smoothing=0 no longer produces an implausibly tight radius on this "
        "dataset -- re-measure whether DEFAULT_SMOOTHING is still justified")
    assert r_smoothed > r_exact


def test_half_width_varies_along_spa_not_constant():
    """TRACKS.md §1: a real circuit's width varies (~5-12 m); this is the
    property SampledTrack.half_width_at exists to carry (staging step 2)."""
    track = load_real_track("Spa")
    s = np.linspace(0.0, track.length, 200, endpoint=False)
    widths = track.half_width_at(s)
    assert np.max(widths) - np.min(widths) > 1.0, \
        "expected real variation in half-width along the lap, found none"
    assert np.all(widths > 1.0), "half-width should never collapse to ~0"
