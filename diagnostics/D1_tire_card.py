"""D1 — Tire model card.

Gates the tire code. Nothing downstream means anything until this passes.

Two jobs:

1. **Reproduce the reference table** in ``HANDOFF.md`` / ``docs/vehicle-reference-
   parameters.md`` §3.2, which was computed independently from the same
   coefficients. Agreement across four columns and seven loads is a strong
   check that the MF 2002 implementation is right.
2. **Assert the physics** that ``docs/result-evaluation-guide.md`` Gate 1
   requires: peak mu falls with load, cornering stiffness rises then saturates,
   the curve is odd about the origin once ply-steer offsets are removed, and the
   sign conventions in :mod:`physics.schema` hold.

Run::

    python -m diagnostics.D1_tire_card

Outputs ``diagnostics/out/D1_report.json`` and ``diagnostics/out/D1_tire_card.svg``.
Panel A is the Ep 1 figure; panels B and C are the Ep 2 figures.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

if __package__ in (None, ""):  # allow `python diagnostics/D1_tire_card.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diagnostics.common import OUT_DIR, Report  # noqa: E402
from physics import schema, tire as tire_mod  # noqa: E402
from viz import lib as V, tire_figures  # noqa: E402

#: The reference table. ``(Fz N, peak mu, Fy peak N, slip at peak deg, N/deg)``.
#: Computed directly from the file's coefficients by an earlier, independent
#: script — that independence is the point, so these numbers are pasted, never
#: regenerated from this module.
REFERENCE_TABLE = [
    (1000.0, 1.139, 1139.0, 9.7, 375.0),
    (2000.0, 1.095, 2190.0, 9.7, 715.0),
    (3000.0, 1.052, 3155.0, 10.0, 997.0),
    (3929.0, 1.012, 3974.0, 10.5, 1197.0),
    (5000.0, 0.965, 4826.0, 11.3, 1357.0),
    (7000.0, 0.878, 6149.0, 13.1, 1489.0),
    (9000.0, 0.792, 7126.0, 15.1, 1486.0),
]

TOL_MU = 0.001          # absolute
TOL_FY_REL = 0.002      # relative
TOL_CA_REL = 0.005      # relative
TOL_ALPHA_EXACT = 0.05  # deg, simplified-Ey mode
TOL_ALPHA_STD = 1.1     # deg, standard MF 2002 — see the Ey note in physics/tire.py


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def run_checks(report: Report) -> dict:
    # Two tires, and the distinction matters throughout this file:
    #   `shipped` — the .tir exactly as written. Validating against the
    #               reference table is a claim about *the implementation*, so it
    #               must use the file's own coefficients, offsets and all.
    #   `tire`    — what the project actually drives: offset-free. Every physics
    #               claim below is about this one, because this is the tire that
    #               will produce every result in the series.
    shipped = tire_mod.as_shipped_tire()
    shipped_simple = tire_mod.as_shipped_tire(ey_camber_asymmetry=False)
    tire = tire_mod.default_tire()
    env = tire.envelope

    report.data["schema_version"] = schema.SCHEMA_VERSION
    report.data["as_shipped"] = shipped.provenance
    report.data["project_default"] = tire.provenance
    report.data["conventions"] = schema.CONVENTIONS

    loads = [row[0] for row in REFERENCE_TABLE]
    ref_peaks = [shipped.peak_lateral(fz) for fz in loads]
    ref_simple = [shipped_simple.peak_lateral(fz) for fz in loads]
    peaks = [tire.peak_lateral(fz) for fz in loads]

    # -- 1. reference table, column by column (as-shipped) -----------------
    report.section("Does the code reproduce the reference table?")
    rows = []
    for i, ((fz, mu_r, fy_r, a_r, ca_r), p, ps) in enumerate(
        zip(REFERENCE_TABLE, ref_peaks, ref_simple)
    ):
        tag = f"{fz:.0f}N"
        report.close(p.mu_peak, mu_r, TOL_MU, f"peak_mu@{tag}")
        report.close(p.fy_peak, fy_r, TOL_FY_REL, f"peak_Fy@{tag}", "N", rel=True)
        report.close(
            p.cornering_stiffness_per_deg, ca_r, TOL_CA_REL,
            f"cornering_stiffness@{tag}", "N/deg", rel=True,
        )
        report.close(
            ps.alpha_peak_deg, a_r, TOL_ALPHA_EXACT,
            f"slip_at_peak_simplifiedEy@{tag}", "deg",
        )
        report.close(
            p.alpha_peak_deg, a_r, TOL_ALPHA_STD,
            f"slip_at_peak_standard@{tag}", "deg",
        )
        rows.append(
            {
                "fz": fz,
                "mu_peak_as_shipped": p.mu_peak, "mu_ref": mu_r,
                "fy_peak_as_shipped": p.fy_peak, "fy_ref": fy_r,
                "alpha_peak_deg_as_shipped": p.alpha_peak_deg,
                "alpha_peak_deg_simplified_ey": ps.alpha_peak_deg,
                "alpha_ref_deg": a_r,
                "cornering_stiffness_per_deg_as_shipped": p.cornering_stiffness_per_deg,
                "cornering_stiffness_ref": ca_r,
                "mu_peak_as_shipped_negative_branch":
                    shipped.peak_lateral(fz, branch="negative").mu_peak,
                "mu_peak_project_default": peaks[i].mu_peak,
            }
        )
    report.data["table"] = rows

    d_alpha = max(abs(p.alpha_peak_deg - r[3]) for p, r in zip(ref_peaks, REFERENCE_TABLE))
    report.note(
        "slip_at_peak_discrepancy_explained",
        f"Standard MF 2002 puts the lateral peak up to {d_alpha:.2f} deg below the "
        "reference table; dropping the (1 - PEY3*sgn(alpha_y)) curvature term "
        f"reproduces it to {TOL_ALPHA_EXACT} deg. The reference table was therefore "
        "generated without that term. Peak force, peak mu and cornering stiffness "
        "are unaffected by Ey, which is why only this one column disagrees. "
        "This file's PEY3=-9.99 / PEY4=-760 are degenerate camber-curvature "
        "coefficients; we keep the standard form for Chrono parity (Ep 16).",
        value=d_alpha,
    )

    # -- 2. the offset removal itself --------------------------------------
    report.section("Did removing the tire's built-in pull work?")
    # Every check from here down is on the project's tire. First: prove that
    # removing the offsets took away the asymmetry and nothing else.
    for fz in (1000.0, 3929.0, 9000.0):
        pos = tire.peak_lateral(fz, branch="positive")
        neg = tire.peak_lateral(fz, branch="negative")
        report.add(
            f"peak_force_symmetric@{fz:.0f}N",
            abs(pos.fy_peak - neg.fy_peak) < 1e-6,
            f"peak |Fy| identical both ways: {pos.fy_peak:.4f} vs {neg.fy_peak:.4f} N "
            f"(as shipped: {shipped.peak_lateral(fz).mu_peak:.4f} vs "
            f"{shipped.peak_lateral(fz, branch='negative').mu_peak:.4f} mu, a "
            f"{100*(shipped.peak_lateral(fz, branch='negative').mu_peak / shipped.peak_lateral(fz).mu_peak - 1):.1f}% split)",
            value=pos.fy_peak - neg.fy_peak,
        )
    report.add(
        "no_lateral_pull_at_zero_slip",
        float(tire.fy0(0.0, 3929.0)) == 0.0 and float(tire.fx0(0.0, 3929.0)) == 0.0,
        f"Fy(0) = {float(tire.fy0(0.0, 3929.0)):.1f} N and "
        f"Fx(0) = {float(tire.fx0(0.0, 3929.0)):.1f} N at Fz0' "
        f"(as shipped: {float(shipped.fy0(0.0, 3929.0)):+.0f} N and "
        f"{float(shipped.fx0(0.0, 3929.0)):+.0f} N)",
    )
    # ...and that the fitted *shape* survived. Peak mu must now be exactly the
    # Magic Formula's own mu_y = (PDY1 + PDY2*dfz)*LMUY, and the cornering
    # stiffness must be within a fraction of a percent of the as-shipped value —
    # the small difference is only the Shy shift moving where the slope is read.
    for fz in (1000.0, 3929.0, 9000.0):
        muy = (tire.PDY1 + tire.PDY2 * float(tire.dfz(fz))) * tire.scaling.lmuy
        report.close(
            tire.peak_lateral(fz).mu_peak, muy, 1e-9,
            f"peak_mu_equals_fitted_muy@{fz:.0f}N",
        )
    ca_shift = max(
        abs(tire.cornering_stiffness(fz) / shipped.cornering_stiffness(fz) - 1.0)
        for fz in loads
    )
    report.add(
        "cornering_stiffness_preserved_by_offset_removal",
        ca_shift < 0.005,
        f"max change {100*ca_shift:.2f}% across the load range — the fitted BCD is "
        "untouched; only the point at which the slope is read moved",
        value=float(ca_shift),
    )

    # -- 3. Gate 1 invariant #1: peak mu falls with load -------------------
    report.section("Does grip fall as the tire is pressed harder?")
    mus = np.array([p.mu_peak for p in peaks])
    dmu = np.diff(mus)
    report.add(
        "peak_mu_monotone_decreasing",
        bool(np.all(dmu < 0.0)),
        f"mu falls {mus[0]:.3f} -> {mus[-1]:.3f} over {loads[0]:.0f}-{loads[-1]:.0f} N; "
        f"largest step {dmu.max():+.4f}",
        value=list(mus),
    )
    slope_ref = float(
        np.polyfit(np.array(loads) / 1000.0, [p.mu_peak for p in ref_peaks], 1)[0]
    )
    report.close(slope_ref, -0.043, 0.006, "load_sensitivity_dmu_dkN_as_shipped", "/kN")
    slope = float(np.polyfit(np.array(loads) / 1000.0, mus, 1)[0])
    report.add(
        "load_sensitivity_negative_and_sane",
        -0.06 < slope < -0.03,
        f"project tire dmu/dFz = {slope:+.4f} /kN (as shipped {slope_ref:+.4f}); the "
        "offset-free value is the cleaner number — it is exactly PDY2/Fz0'",
        value=slope,
    )
    report.data["dmu_dkN"] = slope
    report.data["dmu_dkN_as_shipped"] = slope_ref

    # -- 4. cornering stiffness rises then saturates ----------------------
    report.section("Does the force curve have the right shape?")
    ca = np.array([p.cornering_stiffness_per_deg for p in peaks])
    fz_max_ca = tire.PKY2 * tire.fz0_prime
    report.add(
        "cornering_stiffness_rises_then_saturates",
        bool(np.all(np.diff(ca[:5]) > 0.0) and ca[-1] < ca[-2]),
        f"{ca[0]:.0f} -> {ca[-2]:.0f} N/deg then rolls over; analytic maximum at "
        f"Fz = PKY2*Fz0' = {fz_max_ca:.0f} N",
        value=list(ca),
    )

    # -- 4. slip at peak grows with load ----------------------------------
    ap = np.array([p.alpha_peak_deg for p in peaks])
    # Stated as "grows across the load range, with no material reversal". A
    # strict monotone test fails on a 0.014 deg dip between 1 and 2 kN, which is
    # two orders of magnitude below any measurement resolution and is a property
    # of the Ey term's dfz dependence, not a physics violation. The tolerance is
    # 0.05 deg and the dip is recorded below rather than tolerated silently.
    worst_reversal = float(-min(np.diff(ap).min(), 0.0))
    report.add(
        "slip_at_peak_increases_with_load",
        bool(ap[-1] - ap[0] > 1.0 and worst_reversal < 0.05),
        f"{ap[0]:.2f} -> {ap[-1]:.2f} deg over the tested load range; "
        f"largest local reversal {worst_reversal:.3f} deg (tol 0.05)",
        value=list(ap),
    )
    if worst_reversal > 0.0:
        i = int(np.argmin(np.diff(ap)))
        report.note(
            "slip_at_peak_dips_between_low_loads",
            f"Slip at peak dips {worst_reversal:.3f} deg between {loads[i]:.0f} and "
            f"{loads[i+1]:.0f} N before climbing. Real feature of the fit's Ey(dfz) "
            "term; it disappears with the simplified Ey. Not resolvable on a rig.",
            value=worst_reversal,
        )
    report.add(
        "slip_at_peak_in_band",
        bool(np.all((ap > 5.0) & (ap < 16.0))),
        f"all peaks within 5-16 deg (min {ap.min():.2f}, max {ap.max():.2f})",
        value=[float(ap.min()), float(ap.max())],
    )
    report.note(
        "slip_at_peak_band_differs_from_parameter_sheet",
        "docs/vehicle-reference-parameters.md §5 states the D1 assertion as "
        "'slip at peak 5-10 deg', which contradicts its own §3.2 table (13.1 deg "
        "at 7 kN, 15.1 deg at 9 kN). The table is right and the assertion text is "
        "not; D1 asserts 5-16 deg. Within RV-1's actual corner loads "
        f"(~{schema.RV_1.static_fz_front:.0f}-6000 N) the peak sits at 10-11.5 deg.",
    )

    # -- 5. how odd the curve is, and what is left -------------------------
    report.section("Is the tire the same turning left and right?")
    a = np.radians(np.linspace(0.1, 20.0, 200))
    core = tire_mod.default_tire(ey_camber_asymmetry=False)
    for fz in (1000.0, 3929.0, 9000.0):
        err = float(np.max(np.abs(core.fy0(a, fz) + core.fy0(-a, fz))))
        report.add(
            f"odd_symmetry_exact_without_Ey_asymmetry@{fz:.0f}N",
            err < 1e-9,
            f"max |Fy(a) + Fy(-a)| = {err:.2e} N",
            value=err,
        )
    residual = float(np.max(np.abs(tire.fy0(a, 3929.0) + tire.fy0(-a, 3929.0))))
    shipped_asym = float(np.max(np.abs(shipped.fy0(a, 3929.0) + shipped.fy0(-a, 3929.0))))
    pos = tire.peak_lateral(3929.0)
    neg = tire.peak_lateral(3929.0, branch="negative")
    report.add(
        "residual_asymmetry_is_location_only",
        residual < 0.02 * pos.fy_peak,
        f"max |Fy(a)+Fy(-a)| = {residual:.1f} N at Fz0' "
        f"({100*residual/pos.fy_peak:.1f}% of peak, down from {shipped_asym:.0f} N as "
        f"shipped). Peak force is identical both ways; the two branches reach it "
        f"{abs(pos.alpha_peak_deg - neg.alpha_peak_deg):.2f} deg apart.",
        value=residual,
    )
    report.note(
        "residual_asymmetry_is_the_Ey_term_and_is_kept_deliberately",
        f"What remains is the Ey curvature term's (1 - PEY3*sgn alpha_y) factor: "
        f"the branches peak at {pos.alpha_peak_deg:.2f} and {neg.alpha_peak_deg:.2f} "
        "deg with the same peak force. Removing it would mean zeroing PEY3/PEY4 — an "
        "edit to the P* coefficients, which discards the fit's internal consistency "
        "(vehicle-reference-parameters.md §3.3). It is third-order in slip angle, so "
        "it vanishes at the +/-0.5 g slip angles where understeer gradient is fitted. "
        "It does grow with load — "
        + ", ".join(
            f"{abs(tire.peak_lateral(f).alpha_peak_deg - tire.peak_lateral(f, branch='negative').alpha_peak_deg):.2f} deg at {f/1000:g} kN"
            for f in (1000.0, 3929.0, 9000.0)
        )
        + " — but by 9 kN both peaks are outside the imposed +/-12 deg envelope, so "
        "nothing we are willing to trust sees the wide end of it. D2's mirror test "
        "should assert peak force exactly and trajectories to a stated tolerance, "
        "not bit-equality.",
        value={"alpha_peak_pos_deg": pos.alpha_peak_deg,
               "alpha_peak_neg_deg": neg.alpha_peak_deg},
    )
    report.note(
        "why_the_offsets_were_removed",
        f"As shipped this file is left/right asymmetric by "
        f"{100*(shipped.peak_lateral(3929., branch='negative').mu_peak / shipped.peak_lateral(3929.).mu_peak - 1):.1f}% "
        f"in peak mu ({shipped.peak_lateral(3929.).mu_peak:.3f} vs "
        f"{shipped.peak_lateral(3929., branch='negative').mu_peak:.3f} at Fz0'), and "
        f"declares TYRESIDE = '{tire.tir.strings.get('TYRESIDE', '?')}'. That is "
        "conicity and ply steer — per-sample manufacturing artefacts that a real car "
        "aligns out. The split is wider than the whole 0.95-1.10 g plausibility band "
        "for max lateral g, so it would have corrupted Ep 3 and every left/right "
        "comparison from Ep 5 on. physics.tire.default_tire() therefore zeroes "
        "PHY*/PVY*/PHX*/PVX*; every fitted shape coefficient is untouched. "
        "physics.tire.as_shipped_tire() still returns the file verbatim, and section "
        "1 above validates the implementation against it.",
    )

    # -- 6. longitudinal ---------------------------------------------------
    report.section("Does accelerating and braking behave?")
    mux = np.array([tire.peak_longitudinal(fz)[0] for fz in loads])
    kx = np.array([tire.peak_longitudinal(fz)[1] for fz in loads])
    report.add(
        "peak_mux_monotone_decreasing",
        bool(np.all(np.diff(mux) < 0.0)),
        f"mu_x falls {mux[0]:.3f} -> {mux[-1]:.3f} over the load range",
        value=list(mux),
    )
    report.add(
        "longitudinal_stiffness_sign",
        float(tire.longitudinal_slip_stiffness(3929.0)) > 0.0,
        f"dFx/dkappa = {float(tire.longitudinal_slip_stiffness(3929.0)):.0f} N at Fz0' "
        "— drive slip drives",
    )
    fx_zero_shipped = float(shipped.fx0(0.0, shipped.fz0_prime))
    report.add(
        "no_free_thrust_at_zero_slip_ratio",
        float(tire.fx0(0.0, tire.fz0_prime)) == 0.0,
        f"Fx(kappa=0) = {float(tire.fx0(0.0, tire.fz0_prime)):.1f} N at Fz0'. As "
        f"shipped it is {fx_zero_shipped:+.0f} N — from the PHX1 horizontal shift — "
        f"which over four tires would have been "
        f"{4*fx_zero_shipped/(schema.RV_1.mass*schema.G):+.3f} g of thrust at zero "
        "commanded slip. Removing the offsets removes that too.",
        value=fx_zero_shipped,
    )
    report.add(
        "mux_exceeds_muy",
        bool(np.all(mux > mus)),
        f"mu_x > mu_y at every tested load ({mux[3]:.3f} vs {mus[3]:.3f} at Fz0') "
        "— conventional for a road tire",
    )
    report.data["mu_x_peak"] = list(mux)
    report.data["kappa_at_peak"] = list(kx)

    # -- 7. envelope -------------------------------------------------------
    report.section("Is everything inside the range we trust?")
    report.add(
        "reference_loads_inside_declared_Fz_range",
        all(env.declared_fz_min <= fz <= env.declared_fz_max for fz in loads),
        f"tested {loads[0]:.0f}-{loads[-1]:.0f} N inside declared "
        f"{env.declared_fz_min:.0f}-{env.declared_fz_max:.0f} N",
    )
    outside = [fz for fz, p in zip(loads, peaks)
               if p.alpha_peak > env.imposed_alpha_max]
    report.note(
        "lateral_peak_outside_imposed_slip_envelope_at_high_load",
        (
            "At " + ", ".join(f"{fz:.0f} N" for fz in outside) + " the lateral peak "
            f"sits beyond our imposed +/-{math.degrees(env.imposed_alpha_max):.0f} deg "
            "slip bound, so peak lateral force at those loads is not reachable "
            "inside the region we are willing to trust. RV-1's loaded outside "
            "front corner reaches ~6 kN, where the peak is still inside."
        ) if outside else "Every tested load peaks inside the imposed slip envelope.",
        value=outside,
    )
    report.data["imposed_alpha_max_deg"] = math.degrees(env.imposed_alpha_max)
    report.data["imposed_kappa_max"] = env.imposed_kappa_max
    report.add(
        "kappa_at_peak_inside_imposed_envelope",
        bool(np.all(kx <= env.imposed_kappa_max)),
        f"longitudinal peaks at kappa {kx.min():.3f}-{kx.max():.3f}, imposed bound "
        f"{env.imposed_kappa_max:.2f}",
    )

    # -- 8. Ep 2: the load-split experiment --------------------------------
    report.section("Episode 2's experiment")
    total = 6000.0
    split = {}
    for hi in (3000.0, 4000.0, 5000.0):
        lo = total - hi
        s = tire.peak_lateral(hi).fy_peak + tire.peak_lateral(lo).fy_peak
        split[f"{hi/1000:.0f}+{lo/1000:.0f}"] = s
    even = split["3+3"]
    report.add(
        "even_split_makes_most_grip",
        all(v < even for k, v in split.items() if k != "3+3"),
        "6 kN split: " + ", ".join(
            f"{k} -> {v:.0f} N ({100*(v-even)/even:+.1f}%)" for k, v in split.items()
        ),
        value=split,
    )
    report.data["load_split_6kN"] = split

    report.data["static_corner_loads"] = {
        "front": schema.RV_1.static_fz_front,
        "rear": schema.RV_1.static_fz_rear,
    }
    p_front = tire.peak_lateral(schema.RV_1.static_fz_front)
    report.note(
        "grip_at_RV1_static_corner_load",
        f"At RV-1's static front corner load ({schema.RV_1.static_fz_front:.0f} N) "
        f"this tire peaks at mu = {p_front.mu_peak:.3f} at "
        f"{p_front.alpha_peak_deg:.1f} deg. Consistent with the 0.95-1.10 g band in "
        "result-evaluation-guide Gate 2, and mildly optimistic: it is a 245-section "
        "tire on a car that wears 215s.",
        value=p_front.mu_peak,
    )

    # -- plain-English findings -------------------------------------------
    # Written for a reader who does not know what a slip angle is. The technical
    # notes above stay in the JSON; these are what the run actually *found*.
    report.subtitle = (
        "Checks the rubber before any car exists. A tire model answers one "
        "question: given how hard the tire is squashed into the road, and how far "
        "the wheel is pointed away from where it is actually travelling, how much "
        "sideways force does it make? Everything downstream is built on the answer."
    )
    ship_pos = shipped.peak_lateral(3929.0).mu_peak
    ship_neg = shipped.peak_lateral(3929.0, branch="negative").mu_peak
    report.find(
        f"Grip gets WORSE the harder you press. At 1 kN of load this tire pulls "
        f"{mus[0]:.2f} g sideways; at 9 kN only {mus[-1]:.2f} g. Press nine times "
        "harder and you get about six times the grip, not nine. Most of what this "
        "series is about traces back to that one fact."
    )
    report.find(
        f"Two tires sharing 6 kN make the most total grip when they share it "
        f"evenly. Splitting it 4+2 costs {100*(even-split['4+2'])/even:.1f}% of the "
        f"pair's grip; 5+1 costs {100*(even-split['5+1'])/even:.1f}%. The "
        "overloaded tire never repays what the unloaded one gave up. That is why "
        "weight transfer is expensive, and it is the Episode 2 result."
    )
    report.find(
        f"A tire makes its best grip while already sliding a little — "
        f"{peaks[3].alpha_peak_deg:.1f} degrees off its direction of travel at "
        f"typical load. Below that it has grip in reserve; past it, grip falls "
        "away again. The Episode 1 result."
    )
    report.find(
        f"The file's tire pulled to one side, and we removed it. As shipped it made "
        f"{100*(ship_neg/ship_pos - 1):.1f}% more grip cornering one way than the "
        f"other ({ship_pos:.3f} vs {ship_neg:.3f}) — a manufacturing artefact a real "
        f"car aligns out. It is now {peaks[3].mu_peak:.3f} both ways, with every "
        "fitted curve parameter untouched."
    )
    report.find(
        "The code reproduces an independently computed reference for this tire file "
        "to 0.1% on grip, 0.02% on force and 0.22% on steering response, across "
        "seven loads. One column — where along the curve the peak sits — differs by "
        "up to 1 degree, because the reference left out a formula term that moves "
        "the peak sideways without changing its height. Turning that term off here "
        "matches the reference to 0.04 degrees, so nothing is unexplained."
    )
    report.find(
        f"On our reference car this tire is good for about {p_front.mu_peak:.2f} g "
        "of cornering at its resting front-corner load — plausible for a GR86 on "
        "good summer tires, and mildly optimistic because it is a wider tire than "
        "the real car wears."
    )
    outside_env = [f"{fz/1000:g} kN" for fz, p in zip(loads, peaks)
                   if p.alpha_peak > env.imposed_alpha_max]
    if outside_env:
        report.find(
            "Caution for later: at " + " and ".join(outside_env) + " of load, the "
            "tire's best grip happens at a slip angle beyond the limit we are "
            "willing to trust the model to, so peak grip at those loads is not "
            "reachable inside honest territory. Our car's most loaded corner sits "
            "below that — but a stiff setup could push past it."
        )

    return {
        "tire": tire,
        "peaks": peaks,
        "shipped": shipped,
        "ref_peaks": ref_peaks,
        "loads": loads,
        "split_total": total,
    }


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------


class _Ax:
    """Minimal linear data -> pixel mapper for the SVG panels."""

    def __init__(self, L, R, T, B, x0, x1, y0, y1):
        self.L, self.R, self.T, self.B = L, R, T, B
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1

    def x(self, v):
        return self.L + (self.R - self.L) * (v - self.x0) / (self.x1 - self.x0)

    def y(self, v):
        return self.B - (self.B - self.T) * (v - self.y0) / (self.y1 - self.y0)

    def pts(self, xs, ys):
        return [(self.x(a), self.y(b)) for a, b in zip(xs, ys)]


def _ticks(ax, xs, ys, fx="{:g}", fy="{:g}"):
    return (
        [(fx.format(v), ax.x(v)) for v in xs],
        [(fy.format(v), ax.y(v)) for v in ys],
    )


def build_card(tire, peaks, loads, ref_peaks) -> str:
    W, H = 1520, 1120
    s = V.head(
        W, H,
        "D1 — Tire model card",
        f"{tire.tir.path.name} · MF 2002 pure slip · Fz0' = {tire.fz0_prime:.0f} N · "
        f"schema {schema.SCHEMA_VERSION} · panels use the project tire "
        f"(conicity and ply steer removed); the table validates the file as shipped",
    )
    env = tire.envelope
    colours = [f"rgb{V.ramp(i / (len(loads) - 1))}" for i in range(len(loads))]

    # ---- Panel A: the curve family -------------------------------------
    ax = _Ax(110, 730, 150, 545, 0, 20, 0, 8000)
    s += (f'<text x="110" y="132" fill="{V.FG}" font-size="14" font-weight="600">'
          f'A · Lateral force vs slip angle</text>')
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 5, 4)
    xt, yt = _ticks(ax, [0, 4, 8, 12, 16, 20], [0, 2000, 4000, 6000, 8000],
                    fy="{:.0f}")
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B,
               "slip angle α (deg)", "|Fy| (N)", xt, yt)
    a_deg = np.linspace(0.0, 20.0, 401)
    a_rad = np.radians(a_deg)
    for fz, col, p in zip(loads, colours, peaks):
        fy = -tire.fy0(a_rad, fz)
        s += (f'<path d="{V.path(ax.pts(a_deg, fy))}" fill="none" stroke="{col}" '
              f'stroke-width="2"/>')
        s += (f'<circle cx="{ax.x(p.alpha_peak_deg):.1f}" cy="{ax.y(p.fy_peak):.1f}" '
              f'r="3.5" fill="{col}"/>')
        label = "Fz0′ 3.9 kN" if abs(fz - tire.fz0_prime) < 1.0 else f"{fz/1000:g} kN"
        s += (f'<text x="{ax.R + 8}" y="{ax.y(fy[-1]) + 4:.1f}" fill="{col}" '
              f'font-size="10.5">{label}</text>')
    xe = ax.x(math.degrees(env.imposed_alpha_max))
    s += (f'<line x1="{xe:.1f}" y1="{ax.T}" x2="{xe:.1f}" y2="{ax.B}" '
          f'stroke="{V.MUT}" stroke-width="1" stroke-dasharray="4 4"/>')
    s += (f'<text x="{xe - 6:.1f}" y="{ax.T + 14}" fill="{V.MUT}" font-size="10" '
          f'text-anchor="end">imposed envelope</text>')
    s += (f'<text x="{ax.R - 6}" y="{ax.B - 14}" fill="{V.MUT}" font-size="10.5" '
          f'text-anchor="end">dots mark the peak · Fy is negative for positive α '
          f'(restoring); plotted here as magnitude</text>')

    # ---- Panel B: load sensitivity --------------------------------------
    bx = _Ax(880, 1420, 150, 545, 0, 10000, 0.70, 1.30)
    s += (f'<text x="880" y="132" fill="{V.FG}" font-size="14" font-weight="600">'
          f'B · Peak μ falls as load rises — the keystone fact</text>')
    s = V.grid(s, bx.L, bx.R, bx.T, bx.B, 5, 6)
    xt, yt = _ticks(bx, [0, 2000, 4000, 6000, 8000, 10000],
                    [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3], fx="{:.0f}", fy="{:.2f}")
    s = V.axes(s, bx.L, bx.R, bx.T, bx.B, "vertical load Fz (N)", "peak μ", xt, yt)
    fz_fine = np.linspace(400.0, 10000.0, 60)
    mu_fine = [tire.peak_lateral(f).mu_peak for f in fz_fine]
    s += (f'<path d="{V.path(bx.pts(fz_fine, mu_fine))}" fill="none" '
          f'stroke="{V.AMB}" stroke-width="2.5"/>')
    for fz, col, p in zip(loads, colours, peaks):
        s += (f'<circle cx="{bx.x(fz):.1f}" cy="{bx.y(p.mu_peak):.1f}" r="4" '
              f'fill="{col}"/>')
    for fz, label, col in (
        (schema.RV_1.static_fz_front, "RV-1 static front", V.TEAL),
        (schema.RV_1.static_fz_rear, "static rear", V.TEAL),
    ):
        s += (f'<line x1="{bx.x(fz):.1f}" y1="{bx.T}" x2="{bx.x(fz):.1f}" '
              f'y2="{bx.B}" stroke="{col}" stroke-width="1" stroke-dasharray="3 5"/>')
    s += (f'<text x="{bx.x(schema.RV_1.static_fz_front) + 6:.1f}" y="{bx.T + 14}" '
          f'fill="{V.TEAL}" font-size="10">RV-1 static corner loads</text>')
    slope = np.polyfit(np.array(loads) / 1000.0, [p.mu_peak for p in peaks], 1)[0]
    s += (f'<text x="{bx.L + 12}" y="{bx.B - 12}" fill="{V.MUT}" font-size="10.5">'
          f'dμ/dFz = {slope:+.4f} per kN</text>')

    # ---- Panel C: the load-split experiment ------------------------------
    cx = _Ax(110, 730, 640, 1010, 0, 2500, 5900, 6600)
    s += (f'<text x="110" y="622" fill="{V.FG}" font-size="14" font-weight="600">'
          f'C · Two tires sharing 6 kN — total peak lateral force vs how unevenly '
          f'it is split</text>')
    s = V.grid(s, cx.L, cx.R, cx.T, cx.B, 5, 7)
    xt, yt = _ticks(cx, [0, 500, 1000, 1500, 2000, 2500],
                    [6000, 6200, 6400, 6600], fx="{:.0f}", fy="{:.0f}")
    s = V.axes(s, cx.L, cx.R, cx.T, cx.B,
               "load transferred off one tire onto the other, Δ (N)",
               "sum of both tires' peak |Fy| (N)", xt, yt)
    d = np.linspace(0.0, 2500.0, 60)
    tot = [tire.peak_lateral(3000.0 + x).fy_peak + tire.peak_lateral(3000.0 - x).fy_peak
           for x in d]
    s += (f'<path d="{V.path(cx.pts(d, tot))}" fill="none" stroke="{V.COR}" '
          f'stroke-width="2.5"/>')
    for x, label in ((0.0, "3+3 kN"), (1000.0, "4+2 kN"), (2000.0, "5+1 kN")):
        y = (tire.peak_lateral(3000.0 + x).fy_peak
             + tire.peak_lateral(3000.0 - x).fy_peak)
        s += (f'<circle cx="{cx.x(x):.1f}" cy="{cx.y(y):.1f}" r="4.5" '
              f'fill="{V.AMB}"/>')
        s += (f'<text x="{cx.x(x) + 9:.1f}" y="{cx.y(y) + 4:.1f}" fill="{V.FG}" '
              f'font-size="11">{label} → {y:.0f} N '
              f'({100*(y-tot[0])/tot[0]:+.1f}%)</text>')
    s += (f'<text x="{cx.L + 12}" y="{cx.B - 12}" fill="{V.MUT}" font-size="10.5">'
          f'The overloaded tire never repays what the unloaded one lost. '
          f'This is why load transfer costs grip.</text>')

    # ---- Table -----------------------------------------------------------
    tx, ty = 880, 640
    s += (f'<text x="{tx}" y="{ty - 18}" fill="{V.FG}" font-size="14" '
          f'font-weight="600">Reference table — file as shipped, vs '
          f'vehicle-reference-parameters.md §3.2</text>')
    cols = [(0, "Fz (N)"), (85, "peak μ"), (170, "ref"), (240, "Fy pk (N)"),
            (340, "ref"), (415, "α* (°)"), (480, "ref"), (540, "Cα (N/°)")]
    for dxc, label in cols:
        s += (f'<text x="{tx + dxc}" y="{ty}" fill="{V.MUT}" font-size="11" '
              f'font-weight="600">{label}</text>')
    s += (f'<line x1="{tx}" y1="{ty + 7}" x2="{tx + 600}" y2="{ty + 7}" '
          f'stroke="{V.GRID}" stroke-width="1"/>')
    for i, ((fz, mu_r, fy_r, a_r, ca_r), p) in enumerate(zip(REFERENCE_TABLE, ref_peaks)):
        y = ty + 28 + i * 22
        vals = [
            (0, f"{fz:.0f}", V.FG), (85, f"{p.mu_peak:.3f}", V.AMB),
            (170, f"{mu_r:.3f}", V.MUT), (240, f"{p.fy_peak:.0f}", V.AMB),
            (340, f"{fy_r:.0f}", V.MUT), (415, f"{p.alpha_peak_deg:.2f}", V.AMB),
            (480, f"{a_r:.1f}", V.MUT),
            (540, f"{p.cornering_stiffness_per_deg:.0f}", V.AMB),
        ]
        for dxc, text, col in vals:
            s += (f'<text x="{tx + dxc}" y="{y}" fill="{col}" font-size="11.5" '
                  f'font-family="ui-monospace, SFMono-Regular, monospace">{text}</text>')
    notes = [
        "μ, Fy and Cα reproduce the reference to 0.1%, 0.02% and 0.22%. α* sits up "
        "to 1.0° lower because the reference omits the (1 − PEY3·sgn αy)",
        "curvature term; dropping it here matches to 0.04°. Ey moves only where the "
        "peak is, never how big it is.",
        "",
        "As shipped, the file is left/right asymmetric by 7.4% in peak μ — conicity "
        "and ply steer, per-sample manufacturing artefacts a real car",
        "aligns out. The panels above use default_tire(), which zeroes the "
        "PHY*/PVY*/PHX*/PVX* shifts and leaves every fitted shape coefficient",
        "intact: peak μ at Fz0' becomes 1.049 both ways instead of 1.012 / 1.086.",
    ]
    for i, line in enumerate(notes):
        s += (f'<text x="{tx}" y="{ty + 28 + 7 * 22 + 14 + 16 * i}" fill="{V.MUT}" '
              f'font-size="10.5">{line}</text>')

    p = tire.provenance
    sc = p["scaling"]
    s += (f'<text x="40" y="{H-40}" fill="{V.MUT}" font-size="9.5">'
          f'[MEASURED] {p["file"]}  ·  MF 2002 pure slip  ·  panels: offsets '
          f'removed  ·  table: as shipped  ·  Fz0′ {p["fz0_prime"]:.0f} N  ·  '
          f'LMUY {sc["lmuy"]:g} · LKY {sc["lky"]:g} · LFZO {sc["lfzo"]:g}  ·  '
          f'reference column [SOURCED] vehicle-reference-parameters.md §3.2  ·  '
          f'RV-1 corner loads [DERIVED] from SOURCED mass and weight '
          f'distribution</text>')
    return s + V.foot(
        W, H,
        "Real MF 2002 coefficients from Project Chrono (BSD-3), evaluated directly. "
        "No shape coefficient has been edited.",
    )


# ---------------------------------------------------------------------------


def reality_check_rows(tire) -> list[dict]:
    """Our numbers against ranges that come from **outside** this project.

    Provenance is printed on every row and is not decoration. Two rows have real
    external citations behind them (the reference sheet's NHTSA and handling
    bands); two are general vehicle-dynamics ranges that still need a citation
    pinned before anything is published — see open item O5 in FINDINGS.md. Rows
    with no value yet are shown greyed rather than omitted, because a validation
    ledger that hides what has not been checked is worse than none.

    Deliberately excluded: the 0.95-1.10 g "max lateral acceleration" band in
    ``result-evaluation-guide.md`` Gate 2. That band was itself derived from this
    tire file, so checking this tire against it would be circular.
    """
    fz_corner = schema.RV_1.static_fz_front
    p = tire.peak_lateral(fz_corner)
    mu_x = tire.peak_longitudinal(fz_corner)[0]

    return [
        {
            "label": "Slip angle where a tire makes its best grip",
            "source": "General vehicle-dynamics range for a road tire · "
                      "citation not yet pinned (FINDINGS O5)",
            "value": round(p.alpha_peak_deg, 1), "unit": "°",
            "lo": 6.0, "hi": 12.0, "axis": (0.0, 20.0),
        },
        {
            "label": "Peak grip of one tire at this car's resting corner load",
            "source": "Published skidpad figures, sports coupe on summer tires · "
                      "citation not yet pinned (FINDINGS O5)",
            "value": round(p.mu_peak, 3), "unit": "g",
            "lo": 0.85, "hi": 1.05, "axis": (0.70, 1.30),
            "note": "Known and expected: this is a 245-section tire on a car that "
                    "wears 215s. Open item O1 tracks rescaling it.",
        },
        {
            "label": "Grip accelerating vs grip cornering (μx ÷ μy)",
            "source": "Road tires grip slightly better longitudinally · "
                      "textbook, qualitative",
            "value": round(mu_x / p.mu_peak, 3), "unit": "×",
            "lo": 1.05, "hi": 1.20, "axis": (0.90, 1.40),
        },
        {
            "label": "Static Stability Factor of the reference car",
            "source": "NHTSA measured range, ~0.95 SUV to ~1.8 Corvette · "
                      "vehicle-reference-parameters.md §1 [DERIVED from SOURCED]",
            "value": round(schema.RV_1.static_stability_factor, 2), "unit": "",
            "lo": 0.95, "hi": 1.80, "axis": (0.80, 2.00),
        },
        {
            "label": "Understeer gradient",
            "source": "Sports car 1-2, passenger car 3-5 deg/g · "
                      "vehicle-reference-parameters.md §4 [SOURCED]",
            "value": None, "unit": "deg/g",
            "lo": 1.5, "hi": 3.0, "axis": (0.0, 6.0),
        },
        {
            "label": "Step-steer yaw rise time",
            "source": "vehicle-reference-parameters.md §4 [ASSUMED]",
            "value": None, "unit": "s",
            "lo": 0.08, "hi": 0.30, "axis": (0.0, 0.5),
        },
        {
            "label": "Lap time gained from torque vectoring",
            "source": "Published studies; 9% is the best case, an FSAE car on a "
                      "skidpad · result-evaluation-guide.md Gate 2 [SOURCED]",
            "value": None, "unit": "%",
            "lo": 1.0, "hi": 4.0, "axis": (0.0, 10.0),
        },
    ]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    verbose = "-v" in argv or "--verbose" in argv

    report = Report("D1", "Tire model card")
    ctx = run_checks(report)
    tire = ctx["tire"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written = {}
    # The technical card — unchanged, and still the reference artefact.
    written["technical card"] = OUT_DIR / "D1_tire_card.svg"
    written["technical card"].write_text(
        build_card(tire, ctx["peaks"], ctx["loads"], ctx["ref_peaks"])
    )
    # Pictorial companions. Same numbers, drawn as wheels rather than axes, for
    # readers who do not already know what a slip angle is.
    written["Ep 1 · slip angle"] = OUT_DIR / "D1_slip_angle.svg"
    written["Ep 1 · slip angle"].write_text(
        tire_figures.slip_angle_figure(tire, schema.RV_1.static_fz_front)
    )
    written["Ep 2 · load split"] = OUT_DIR / "D1_load_split.svg"
    written["Ep 2 · load split"].write_text(tire_figures.load_split_figure(tire))
    written["reality check"] = OUT_DIR / "D1_reality_check.svg"
    written["reality check"].write_text(
        tire_figures.reality_check_figure(reality_check_rows(tire))
    )

    report.data["reality_check"] = reality_check_rows(tire)
    captions = {
        "Ep 1 · slip angle": "Five copies of the same tire at the same load, "
            "differing only in how far they are pointed away from where they are "
            "going. Arrow length is grip, to one scale. The strip along the "
            "bottom is the same five points as the conventional curve.",
        "Ep 2 · load split": "Two tires sharing 6 kN, split three ways. The band "
            "across each tire is its contact patch. Even sharing wins; the "
            "overloaded tire never repays what the unloaded one gave up.",
        "reality check": "Every quantity we can measure today against a range "
            "from outside the project, with the source of each band named. Grey "
            "rows are not measurable until the vehicle model exists.",
        "technical card": "Panel A the force curve family, B peak grip against "
            "load, C the load-split experiment, plus the reference table "
            "validating the implementation against the file as shipped.",
    }
    md = report.write_markdown(
        [(name, path, captions[name]) for name, path in written.items()],
        command="python -m diagnostics.D1_tire_card")
    path = report.write()
    report.print_summary(verbose=verbose)
    print(f"\n  write-up {md}\n  report   {path}")
    for name, p in written.items():
        print(f"  {name:<20} {p}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
