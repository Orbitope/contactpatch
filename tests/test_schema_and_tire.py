"""Unit tests for the parts of the schema and tire code that D1 does not exercise.

D1 is the physics gate — it owns every claim about what the tire *does*. These
tests own the plumbing underneath it: the .tir parser, the channel spec, the
envelope arithmetic, and the vehicle geometry. A failure here means a number is
being carried incorrectly, which is exactly the class of bug that never shows up
as an obviously wrong plot.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from physics import schema, tire as tire_mod


# ---------------------------------------------------------------------------
# .tir parsing
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tir():
    return tire_mod.load_tir(tire_mod.DEFAULT_TIR)


@pytest.fixture(scope="module")
def tire(tir):
    return tire_mod.MF02Tire(tir)


def test_parses_numbers_strings_and_sections(tir):
    assert tir.get("FNOMIN") == 4850.0
    assert tir.get("PKY1") == pytest.approx(-21.92)
    assert tir.text("PROPERTY_FILE_FORMAT") == "PAC2002"
    assert tir.text("TYRESIDE") == "LEFT"
    assert "PCY1" in tir.sections["LATERAL_COEFFICIENTS"]
    # [SHAPE] is a free-format table; it must not poison the flat namespace.
    assert not any(k.startswith("1.0") for k in tir.numbers)


def test_trailing_comments_are_stripped(tir):
    # "VXLOW = 1  $Tyre use switch" — the value must be 1, not "1 $Tyre...".
    assert tir.get("VXLOW") == 1.0
    assert tir.get("PEX4") == pytest.approx(-3.7604e-5)


def test_missing_coefficient_raises_unless_defaulted(tir):
    with pytest.raises(KeyError):
        tir.get("PKY4")  # MF 6.1 term, genuinely absent from a 5.2 file
    assert tir.get("PKY4", 2.0) == 2.0


# ---------------------------------------------------------------------------
# Sign conventions
# ---------------------------------------------------------------------------


def test_lateral_force_opposes_slip_angle(tire):
    assert float(tire.fy0(math.radians(4.0), 3929.0)) < 0.0
    assert float(tire.fy0(math.radians(-4.0), 3929.0)) > 0.0


def test_longitudinal_force_follows_slip_ratio(tire):
    assert float(tire.fx0(0.05, 3929.0)) > 0.0
    assert float(tire.fx0(-0.05, 3929.0)) < 0.0


def test_sign_assert_rejects_the_wrong_convention():
    with pytest.raises(AssertionError, match="non-negative"):
        schema.assert_lateral_sign_convention(+68000.0)
    with pytest.raises(AssertionError, match="non-positive"):
        schema.assert_longitudinal_sign_convention(-87000.0)


def test_analytic_cornering_stiffness_matches_finite_difference(tire):
    h = 1e-6
    for fz in (1000.0, 3929.0, 9000.0):
        fd = float(tire.fy0(h, fz) - tire.fy0(-h, fz)) / (2 * h)
        assert float(tire.cornering_stiffness(fz)) == pytest.approx(fd, rel=1e-6)


def test_analytic_slip_stiffness_matches_finite_difference(tire):
    h = 1e-8
    for fz in (1000.0, 3929.0, 9000.0):
        fd = float(tire.fx0(h, fz) - tire.fx0(-h, fz)) / (2 * h)
        assert float(tire.longitudinal_slip_stiffness(fz)) == pytest.approx(fd, rel=1e-4)


# ---------------------------------------------------------------------------
# Broadcasting and scaling
# ---------------------------------------------------------------------------


def test_fy0_broadcasts_over_alpha_and_load(tire):
    alpha = np.radians(np.linspace(-10, 10, 7))
    fz = np.full_like(alpha, 3000.0)
    assert tire.fy0(alpha, fz).shape == (7,)
    assert tire.fy0(alpha[:, None], np.array([1000.0, 5000.0])).shape == (7, 2)


def test_lmuy_scales_peak_force_proportionally(tire):
    base = tire.peak_lateral(3929.0)
    scaled = tire.rescaled(lmuy=0.90).peak_lateral(3929.0)
    assert scaled.fy_peak == pytest.approx(0.90 * base.fy_peak, rel=1e-3)


def test_lky_scales_cornering_stiffness_proportionally(tire):
    base = float(tire.cornering_stiffness(3929.0))
    scaled = float(tire.rescaled(lky=0.85).cornering_stiffness(3929.0))
    assert scaled == pytest.approx(0.85 * base, rel=2e-3)


def test_lfzo_moves_the_nominal_load(tir):
    t = tire_mod.MF02Tire(tir, tire_mod.Scaling.from_tir(tir))
    assert t.fz0_prime == pytest.approx(4850.0 * 0.81)
    assert t.rescaled(lfzo=1.0).fz0_prime == pytest.approx(4850.0)


def test_without_offsets_zeroes_the_force_at_zero_slip(tire):
    core = tire.without_offsets()
    assert float(core.fy0(0.0, 3929.0)) == 0.0
    assert float(core.fx0(0.0, 3929.0)) == 0.0
    assert float(tire.fy0(0.0, 3929.0)) != 0.0  # original is untouched
    assert core.offsets_removed and not tire.offsets_removed


def test_project_default_is_offset_free_and_as_shipped_is_not():
    assert tire_mod.default_tire().offsets_removed is True
    assert tire_mod.as_shipped_tire().offsets_removed is False
    assert float(tire_mod.default_tire().fy0(0.0, 3929.0)) == 0.0
    assert float(tire_mod.as_shipped_tire().fy0(0.0, 3929.0)) != 0.0


def test_default_tire_is_symmetric_in_peak_force():
    t = tire_mod.default_tire()
    for fz in (1000.0, 3929.0, 9000.0):
        pos = t.peak_lateral(fz, branch="positive")
        neg = t.peak_lateral(fz, branch="negative")
        assert pos.fy_peak == pytest.approx(neg.fy_peak, abs=1e-6)
        # ...but not in *where* the peak is: that residual is the Ey term, kept
        # on purpose rather than edited out of the P* coefficients. It grows with
        # load: 0.27 deg at 1 kN, 0.79 at Fz0', 2.38 at 9 kN — where both peaks
        # are outside the imposed +/-12 deg envelope anyway.
        assert 0.1 < abs(pos.alpha_peak_deg - neg.alpha_peak_deg) < 3.0


def test_offset_removal_preserves_the_fitted_shape(tire):
    """Peak mu must collapse to the Magic Formula's own mu_y, and Ca must barely move."""
    core = tire.without_offsets()
    for fz in (1000.0, 3929.0, 9000.0):
        muy = (core.PDY1 + core.PDY2 * float(core.dfz(fz))) * core.scaling.lmuy
        assert core.peak_lateral(fz).mu_peak == pytest.approx(muy, abs=1e-9)
        assert float(core.cornering_stiffness(fz)) == pytest.approx(
            float(tire.cornering_stiffness(fz)), rel=0.005
        )


def test_rescaled_preserves_offset_removal():
    t = tire_mod.default_tire().rescaled(lmuy=0.9)
    assert t.offsets_removed is True
    assert float(t.fy0(0.0, 3929.0)) == 0.0
    assert tire_mod.as_shipped_tire().rescaled(lmuy=0.9).offsets_removed is False


def test_provenance_records_what_produced_a_result():
    p = tire_mod.default_tire().provenance
    assert p["offsets_removed"] is True
    assert p["ey_camber_asymmetry"] is True
    assert p["file"] == "Sedan_Pac02Tire.tir"
    assert p["scaling"]["lfzo"] == pytest.approx(0.81)


def test_peak_branches_differ_and_mean_sits_between(tire):
    pos = tire.peak_lateral(3929.0, branch="positive")
    neg = tire.peak_lateral(3929.0, branch="negative")
    mid = tire.peak_lateral(3929.0, branch="mean")
    assert neg.fy_peak > pos.fy_peak  # ply steer / conicity
    assert pos.fy_peak < mid.fy_peak < neg.fy_peak
    assert mid.fy_peak == pytest.approx(0.5 * (pos.fy_peak + neg.fy_peak))


def test_peak_location_is_a_true_maximum(tire):
    for fz in (1000.0, 5000.0, 9000.0):
        p = tire.peak_lateral(fz)
        for d in (-1e-3, 1e-3):
            assert abs(float(tire.fy0(p.alpha_peak + d, fz))) <= p.fy_peak + 1e-9


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


def test_envelope_reads_the_files_declared_ranges(tire):
    e = tire.envelope
    assert (e.declared_fz_min, e.declared_fz_max) == (225.0, 10125.0)
    assert e.declared_alpha_max == pytest.approx(1.5708)
    # The imposed bounds are ours, and must be far tighter than the declared ones.
    assert e.imposed_alpha_max == pytest.approx(math.radians(12.0))
    assert e.imposed_alpha_max < e.declared_alpha_max / 5


def test_envelope_flags_each_violation_kind(tire):
    e = tire.envelope
    alpha = np.radians([0.0, 20.0, 0.0, 0.0, 0.0])
    kappa = np.array([0.0, 0.0, 0.5, 0.0, 0.0])
    fz = np.array([3000.0, 3000.0, 3000.0, 100.0, 20000.0])
    assert list(e.violation_mask(alpha, kappa, fz)) == [False, True, True, True, True]
    assert e.occupancy(alpha, kappa, fz) == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Vehicle parameters
# ---------------------------------------------------------------------------


def test_rv1_geometry_is_self_consistent():
    v = schema.RV_1
    v.check()
    assert v.a + v.b == pytest.approx(v.wheelbase)
    # Front-biased mass puts the CoM closer to the front axle: a < b.
    assert v.a < v.b
    # ...and the lever arms must reproduce the static split: Fz_front = W*b/L.
    assert 2 * v.static_fz_front == pytest.approx(v.weight * v.b / v.wheelbase)
    assert 2 * v.static_fz_rear == pytest.approx(v.weight * v.a / v.wheelbase)
    assert 2 * (v.static_fz_front + v.static_fz_rear) == pytest.approx(v.weight)


def test_static_stability_factor_is_in_the_nhtsa_range():
    ssf = schema.RV_1.static_stability_factor
    assert 0.95 < ssf < 1.8
    assert ssf == pytest.approx(1.63, abs=0.01)


def test_track_sensitivity_variant_scales_both_tracks():
    v = schema.RV_1.scaled_track(1.03)
    assert v.track_f == pytest.approx(schema.RV_1.track_f * 1.03)
    assert v.track_r == pytest.approx(schema.RV_1.track_r * 1.03)
    assert v.mass == schema.RV_1.mass  # nothing else moved


def test_roll_gradient_lands_in_the_published_road_car_range():
    """3-7 deg/g for a road car on springs. An outside-the-project band."""
    assert 3.0 < schema.RV_1.roll_gradient_deg_per_g < 7.0


def test_bar_rate_reaches_the_share_it_was_asked_for():
    """Invert the answer: fit the bar, then recompute the share it produces.

    The forward direction is the definition, so solving it and checking the
    round trip is a check the algebra was not written around.
    """
    v = schema.RV_1
    for share in (0.40, 0.45, 0.50, 0.55, 0.60, 0.70):
        rate, end = v.bar_rate_for_share(share)
        assert rate >= 0.0, f"a bar cannot have negative stiffness ({share})"
        k_f = v.roll_stiffness_front + (rate if end == "front" else 0.0)
        k_r = v.roll_stiffness_rear + (rate if end == "rear" else 0.0)
        assert k_f / (k_f + k_r) == pytest.approx(share)
        assert end == ("front" if share >= v.spring_only_roll_share else "rear")


def test_adding_any_bar_reduces_roll_and_the_no_bar_case_is_the_maximum():
    """The non-obvious shape: roll angle is largest with NO bar.

    A bar is a spring, so it can only add roll stiffness, whichever end it goes
    on. That makes the roll angle non-monotonic in front share — peaked at the
    spring-only share — which is not what a knob labelled "front stiffness"
    suggests, and is why the figure says so explicitly.
    """
    v = schema.RV_1
    base = v.roll_gradient_deg_per_g
    # zero to within float noise on a 60,766 N.m/rad total
    assert v.bar_rate_for_share(v.spring_only_roll_share)[0] == pytest.approx(
        0.0, abs=1e-6)
    assert (v.roll_gradient_deg_per_g_with_bar(v.spring_only_roll_share)
            == pytest.approx(base))
    for share in (0.40, 0.45, 0.50, 0.55, 0.60, 0.70):
        assert v.roll_gradient_deg_per_g_with_bar(share) <= base + 1e-9
    # ...and monotone in bar rate on each side of the peak
    assert (v.roll_gradient_deg_per_g_with_bar(0.70)
            < v.roll_gradient_deg_per_g_with_bar(0.60)
            < v.roll_gradient_deg_per_g_with_bar(0.55))
    assert (v.roll_gradient_deg_per_g_with_bar(0.40)
            < v.roll_gradient_deg_per_g_with_bar(0.45)
            < v.roll_gradient_deg_per_g_with_bar(0.50))


def test_spring_only_share_is_near_the_assumed_share():
    """The assumed 0.55 must stay explicable as "springs plus a modest bar"."""
    v = schema.RV_1
    assert v.spring_only_roll_share == pytest.approx(0.522, abs=0.005)
    assert v.spring_only_roll_share < v.roll_stiffness_front_share
    # a bar that gets from one to the other should be a small fraction of total
    rate, end = v.bar_rate_for_share(v.roll_stiffness_front_share)
    assert end == "front"
    assert rate / v.roll_stiffness_total < 0.10, "0.55 should not need a huge bar"


def test_layout_archetypes_are_ordered_as_the_parameter_sheet_claims():
    a = schema.LAYOUT_ARCHETYPES
    # Mid-engine: least mass forward and lowest polar moment of the RWD set.
    assert a["mid_rwd"].front_mass_fraction < a["front_mid_rwd"].front_mass_fraction
    assert a["mid_rwd"].i_zz == min(v.i_zz for v in a.values())
    # Rear-engine is rearward-biased *and* high inertia — the non-collinearity
    # that Ep 8 is about.
    assert a["rear_rwd"].front_mass_fraction < 0.5
    assert a["rear_rwd"].i_zz > a["front_mid_rwd"].i_zz


# ---------------------------------------------------------------------------
# Channel specs
# ---------------------------------------------------------------------------


def test_space_round_trips_named_values():
    v = schema.OBS_BICYCLE.pack(
        v_x=30.0, v_y=1.0, yaw_rate=0.4, beta=0.03, a_y=8.0,
        alpha_f=0.05, alpha_r=0.03, fz_f=3600.0, fz_r=3100.0, steer=0.1,
    )
    assert v.shape == (len(schema.OBS_BICYCLE),)
    assert schema.OBS_BICYCLE.unpack(v)["yaw_rate"] == pytest.approx(0.4)
    assert schema.OBS_BICYCLE.select(v, "fz_f") == pytest.approx(3600.0)


def test_space_normalisation_is_invertible():
    sp = schema.OBS_BICYCLE
    v = np.arange(len(sp), dtype=float) + 1.0
    assert np.allclose(sp.denormalise(sp.normalise(v)), v)


def test_space_rejects_missing_and_unknown_channels():
    with pytest.raises(AssertionError, match="missing channels"):
        schema.ACT_BICYCLE.pack(steer_rate=0.1)
    with pytest.raises(AssertionError, match="unknown channels"):
        schema.ACT_BICYCLE.pack(steer_rate=0.1, drive_force=100.0, boost=1.0)


def test_wheel_log_has_three_channels_per_wheel():
    log = schema.WHEEL_LOG_DOUBLE_TRACK
    assert len(log) == 3 * len(schema.CORNERS)
    assert log.names[:3] == ("alpha_fl", "kappa_fl", "fz_fl")
    assert schema.WHEEL_LOG_BICYCLE.names == (
        "alpha_f", "kappa_f", "fz_f", "alpha_r", "kappa_r", "fz_r",
    )


def test_index_error_names_the_available_channels():
    with pytest.raises(KeyError, match="yaw_rate"):
        schema.OBS_BICYCLE.index("yaw_rat")


# ---------------------------------------------------------------------------
# D1 is itself a test
# ---------------------------------------------------------------------------


def test_d1_passes():
    from diagnostics.common import Report
    from diagnostics.D1_tire_card import run_checks

    report = Report("D1", "Tire model card")
    run_checks(report)
    assert report.ok, "D1 gates failed: " + "; ".join(
        f"{c.name} ({c.detail})" for c in report.failures
    )
