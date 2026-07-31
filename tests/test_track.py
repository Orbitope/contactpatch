"""Tests for track geometry (physics/track.py).

POWER-REVIEW D-D added ``hairpin`` and ``fast_sweep`` alongside the existing
``short_exit``/``long_exit`` — same 90 deg turn and entry/exit straight
lengths, radius the only thing that varies. These tests are the check that
the two new tracks are geometrically sane and actually drivable before any
sweep is built on top of them.
"""

from __future__ import annotations

import numpy as np
import pytest

from physics import schema
from physics.optimal_control import Limits, solve_min_time
from physics.track import (ENTRY_STRAIGHT, FAST_SWEEP_RADIUS, HAIRPIN_RADIUS,
                            fast_sweep, hairpin, long_exit)

NEW_TRACKS = (
    (hairpin, HAIRPIN_RADIUS, 12.0),
    (fast_sweep, FAST_SWEEP_RADIUS, 25.0),
)


@pytest.mark.parametrize("track_fn,radius,_entry", NEW_TRACKS)
def test_length_matches_entry_plus_arc_plus_exit(track_fn, radius, _entry):
    trk = track_fn()
    arc = 0.5 * np.pi * radius
    assert trk.length == pytest.approx(ENTRY_STRAIGHT + arc + 260.0)


@pytest.mark.parametrize("track_fn,radius,_entry", NEW_TRACKS)
def test_curvature_zero_on_the_straights(track_fn, radius, _entry):
    trk = track_fn()
    assert trk.curvature(np.array([10.0]))[0] == pytest.approx(0.0, abs=1e-9)
    assert trk.curvature(np.array([trk.length - 5.0]))[0] == \
        pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("track_fn,radius,_entry", NEW_TRACKS)
def test_curvature_matches_1_over_r_at_corner_midpoint(track_fn, radius, _entry):
    # rel=1e-3, not the default 1e-6: tanh approaches its plateau
    # asymptotically, never exactly, so a residual tail remains even many
    # blend-widths from the join. The hairpin's short arc (23.6 m against a
    # 4 m blend) makes that residual large enough to matter at pytest's
    # default tolerance, though physically negligible.
    trk = track_fn()
    arc_len = trk.segments[1].length
    mid_s = ENTRY_STRAIGHT + 0.5 * arc_len
    assert trk.curvature(np.array([mid_s]))[0] == \
        pytest.approx(1.0 / radius, rel=1e-3)


@pytest.mark.parametrize("track_fn,radius,entry_speed", NEW_TRACKS)
def test_solves_cleanly_inside_the_envelope(track_fn, radius, entry_speed):
    """Each new track must actually be drivable before any sweep uses it."""
    trk = track_fn()
    sol = solve_min_time(trk, schema.RV_1, n_nodes=80, entry_speed=entry_speed,
                         limits=Limits(), diff="ideal", four_wheel=True,
                         print_level=0)
    assert sol.success, sol.solver_status
    assert sol.envelope_occupancy() == 0.0


def test_radius_is_the_only_thing_that_differs_from_long_exit():
    """D-D's whole point: isolate radius, not the turn angle or straight
    lengths, as the varied quantity between tracks."""
    le = long_exit()
    for track_fn, radius, _entry in NEW_TRACKS:
        trk = track_fn()
        assert trk.segments[0].length == le.segments[0].length
        assert trk.segments[2].length == le.segments[2].length
        assert trk.half_width == le.half_width
        # arc SWEEP ANGLE (arc length / radius) matches, only radius differs
        le_angle = le.segments[1].length / le.segments[1].radius
        new_angle = trk.segments[1].length / radius
        assert new_angle == pytest.approx(le_angle)


def test_half_width_at_matches_the_scalar_constant():
    """TRACKS.md staging step 2 introduces half_width_at(s) as the interface
    every caller should use (SampledTrack's may vary with s); Track's own
    every synthetic track is one width throughout, so this must exactly
    reproduce the scalar for any s, in and out of segment bounds."""
    trk = long_exit()
    probe = np.array([-10.0, 0.0, 50.0, trk.length, trk.length + 10.0])
    got = trk.half_width_at(probe)
    assert np.all(got == trk.half_width)
    assert got.shape == probe.shape
