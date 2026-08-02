"""A TrackBank must agree with the splines it was built from, and be fast.

The bank replaces spline evaluation with a table gather. If the tables drift
from the source geometry, every multi-track result is measuring a different
circuit than the one we think we trained on -- silently.
"""

import time

import numpy as np
import pytest

from physics.track_bank import TrackBank, BankTrackView
from physics.track_gen import generate_set
from physics.tracks_data import load_real_track


def test_bank_curvature_matches_the_source_spline():
    tracks = generate_set(4, seed0=500)
    bank = TrackBank(tracks)
    for i, t in enumerate(tracks):
        s = np.linspace(0.0, t.length, 700, endpoint=False)
        ref = np.asarray(t.curvature(s))
        got = bank.curvature(np.full(s.shape, i), s)
        # Absolute tolerance: near-zero curvature on a straight makes a
        # relative one meaningless. 6e-4 is the measured worst case at
        # n_grid=16000 (see the table in track_bank's docstring), with
        # headroom -- NOT a tolerance widened until the test passed.
        err = np.max(np.abs(ref - got))
        assert err < 6e-4, f"{t.name}: max curvature error {err:.2e}"
        # ...and the error must be where we think it is: tight corners.
        sig = np.abs(ref) > 0.005
        if sig.any():
            rel = np.max(np.abs(ref - got)[sig] / np.abs(ref)[sig])
            assert rel < 0.035, f"{t.name}: {rel:.1%} relative error"


def test_bank_half_width_matches_the_source():
    spa = load_real_track("Spa")
    bank = TrackBank([spa])
    s = np.linspace(0.0, spa.length, 700, endpoint=False)
    ref = np.asarray(spa.half_width_at(s))
    got = bank.half_width_at(np.zeros(s.shape, dtype=int), s)
    assert np.max(np.abs(ref - got)) < 0.05


def test_bank_wraps_past_one_lap():
    """Closed circuits: s beyond one lap is a second lap, not an error."""
    t = generate_set(1, seed0=600)[0]
    bank = TrackBank([t])
    s = np.array([10.0, 10.0 + t.length, 10.0 + 3 * t.length])
    k = bank.curvature(np.zeros(3, dtype=int), s)
    assert np.allclose(k, k[0], atol=1e-9)


def test_view_presents_the_scalar_track_interface():
    """The single-instance env and every eval path use scalars; a bank
    circuit must drop into those unchanged or the reference implementation
    stops being usable as the differential-test oracle."""
    tracks = generate_set(2, seed0=700)
    bank = TrackBank(tracks)
    v = BankTrackView(bank, 1)
    assert isinstance(v.curvature(123.0), float)
    assert isinstance(v.half_width_at(123.0), float)
    assert v.length == pytest.approx(tracks[1].length)
    arr = v.curvature(np.array([10.0, 20.0, 30.0]))
    assert arr.shape == (3,)


def test_bank_lookup_is_fast_enough_to_be_worth_it():
    """The whole justification for this class is speed. 256 instances on 256
    DIFFERENT circuits must cost less than one shared spline evaluation,
    otherwise use the spline and keep the code simpler."""
    tracks = generate_set(8, seed0=800)
    bank = TrackBank(tracks)
    n = 256
    tid = np.random.randint(0, len(tracks), n)
    s = np.random.uniform(0, 3000.0, n)
    bank.curvature(tid, s)                       # warm
    t0 = time.perf_counter()
    for _ in range(300):
        bank.curvature(tid, s)
    per = (time.perf_counter() - t0) / 300

    spa = load_real_track("Spa")
    s2 = np.random.uniform(0, spa.length, n)
    spa.curvature(s2)
    t1 = time.perf_counter()
    for _ in range(300):
        spa.curvature(s2)
    per_spline = (time.perf_counter() - t1) / 300

    assert per < per_spline, (
        f"bank {per*1e6:.1f} us vs shared spline {per_spline*1e6:.1f} us -- "
        f"the bank is supposed to be FASTER, not just possible")
