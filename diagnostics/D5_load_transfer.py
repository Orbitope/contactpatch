"""D5 — Load transfer audit.

Gates the double-track model. Everything the four-wheel model adds over the
bicycle model is load moving between wheels, so this diagnostic is almost
entirely about whether that bookkeeping is right.

The strongest check here is a **degeneracy test**: lower the centre of gravity
toward the road and lateral load transfer must vanish, at which point the
four-wheel model has to reproduce the two-wheel model's answer exactly. Two
independently written models agreeing in a limit where they should is a check
neither was written around.

Run::

    python -m diagnostics.D5_load_transfer [-v]
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diagnostics.common import OUT_DIR, Report  # noqa: E402
from physics import schema  # noqa: E402
from physics.bicycle import BicycleBackend  # noqa: E402
from physics.bicycle import understeer_gradient as ug_bicycle  # noqa: E402
from physics.double_track import DoubleTrackBackend  # noqa: E402
from physics.double_track import understeer_gradient as ug_dt  # noqa: E402
from viz import load_figures  # noqa: E402

RADIUS = 30.0
SPEEDS = np.arange(5.0, 19.0, 0.5)
ROLL_SHARES = (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70)


def run_checks(report: Report) -> dict:
    dt = DoubleTrackBackend()
    bi = BicycleBackend()
    p = schema.RV_1
    report.data["schema_version"] = schema.SCHEMA_VERSION
    report.data["tire"] = dt.tire.provenance
    report.data["roll_stiffness_front_share"] = p.roll_stiffness_front_share

    report.section("Is the load bookkeeping exact?")
    worst = 0.0
    for a_x in (-6.0, 0.0, 6.0):
        for a_y in (-9.0, 0.0, 9.0):
            worst = max(worst, abs(sum(dt.wheel_loads(a_x, a_y).values())
                                   - p.weight))
    report.add(
        "four_loads_always_sum_to_mg",
        worst < 1e-9,
        f"worst deviation {worst:.2e} N across nine combinations of longitudinal "
        "and lateral acceleration. Transfer moves load; it never creates any.",
        value=worst,
    )
    at_rest = dt.wheel_loads()
    report.close(at_rest["fl"], at_rest["fr"], 1e-9, "static_loads_symmetric", "N")
    report.close(at_rest["fl"] + at_rest["fr"], 2 * p.static_fz_front, 1e-9,
                 "static_front_axle_matches_weight_distribution", "N")

    report.section("Does load move the right way?")
    left = dt.wheel_loads(0.0, 8.0)
    report.add(
        "left_turn_loads_the_right_hand_wheels",
        left["fr"] > left["fl"] and left["rr"] > left["rl"],
        f"turning left at {8.0/schema.G:.2f} g: front {left['fl']:.0f} left / "
        f"{left['fr']:.0f} right, rear {left['rl']:.0f} / {left['rr']:.0f}. "
        "Gate 1 invariant 5.",
    )
    brake = dt.wheel_loads(-5.0, 0.0)
    report.add(
        "braking_still_loads_the_front",
        brake["fl"] + brake["fr"] > at_rest["fl"] + at_rest["fr"],
        f"front axle {at_rest['fl']+at_rest['fr']:.0f} -> "
        f"{brake['fl']+brake['fr']:.0f} N under braking — the bicycle model's "
        "behaviour is unchanged by adding a second track",
    )

    report.section("Is the transfer proportional to what it should be?")
    base = dt.wheel_loads(0.0, 6.0)
    d_base = 0.5 * (base["fr"] - base["fl"])
    tall = DoubleTrackBackend(replace(p, com_height=2 * p.com_height))
    tl = tall.wheel_loads(0.0, 6.0)
    report.close(0.5 * (tl["fr"] - tl["fl"]) / d_base, 2.0, 1e-9,
                 "lateral_transfer_proportional_to_com_height", "x")
    dg = dt.wheel_loads(0.0, 12.0)
    report.close(0.5 * (dg["fr"] - dg["fl"]) / d_base, 2.0, 1e-9,
                 "lateral_transfer_proportional_to_lateral_g", "x")
    wide = DoubleTrackBackend(replace(p, track_f=2 * p.track_f))
    wl = wide.wheel_loads(0.0, 6.0)
    report.close(0.5 * (wl["fr"] - wl["fl"]) / d_base, 0.5, 1e-9,
                 "lateral_transfer_inversely_proportional_to_track", "x")
    eps = p.roll_stiffness_front_share
    # d_base is already half the left-right difference, i.e. the transfer itself.
    report.close(d_base * p.track_f / (p.mass * 6.0 * p.com_height), eps,
                 1e-9, "roll_share_divides_the_transfer_moment", "")

    report.section("Does it lift a wheel when it should?")
    lift = dt.wheel_lift_a_y()
    ssf = p.static_stability_factor
    report.add(
        "wheel_lift_below_the_static_stability_factor",
        lift < ssf,
        f"first inside wheel lifts at {lift:.3f} g against an SSF of {ssf:.3f}. "
        "SSF is the rigid-body rollover threshold; no elastic roll distribution "
        "can beat it, so lifting above it would be a bug.",
        value={"lift_g": lift, "ssf": ssf},
    )
    report.add(
        "wheel_lift_is_not_reached_in_normal_cornering",
        lift > 1.3,
        f"{lift:.2f} g is well beyond the {dt.max_lateral_g(RADIUS):.2f} g this "
        "car can actually generate, so no result in this series involves a "
        "lifted wheel — the case is handled, not exercised",
    )

    report.section("Does it become the bicycle model when it should?")
    flat = replace(p, com_height=1e-6)
    dt_flat, bi_flat = DoubleTrackBackend(flat), BicycleBackend(flat)
    k_dt, _ = ug_dt(dt_flat.skidpad_sweep(RADIUS, SPEEDS))
    k_bi, _ = ug_bicycle(bi_flat.skidpad_sweep(RADIUS, SPEEDS))
    report.close(k_dt, k_bi, 0.02, "flat_car_reproduces_the_bicycle_gradient",
                 "deg/g", rel=True)
    g_dt, g_bi = dt_flat.max_lateral_g(RADIUS), bi_flat.max_lateral_g(RADIUS)
    report.close(g_dt, g_bi, 0.01, "flat_car_reproduces_the_bicycle_grip_limit",
                 "g", rel=True)
    report.note(
        "degeneracy_test_is_the_strongest_check_here",
        "With the centre of gravity on the road there is no lateral load "
        "transfer, so the four-wheel model has nothing the two-wheel model "
        f"lacks. It reproduces the understeer gradient to "
        f"{100*abs(k_dt-k_bi)/abs(k_bi):.2f}% and the grip limit to "
        f"{100*abs(g_dt-g_bi)/g_bi:.2f}%. Residual is the per-wheel slip-angle "
        "difference from yaw rate across the track, which the bicycle model "
        "averages away and which does not vanish with height.",
        value={"k_double_track": k_dt, "k_bicycle": k_bi},
    )

    report.section("What does lateral load transfer cost?")
    pts = [q for q in dt.skidpad_sweep(RADIUS, SPEEDS) if q.converged]
    k_full, r2 = ug_dt(pts)
    g_full = dt.max_lateral_g(RADIUS)
    g_bicycle = bi.max_lateral_g(RADIUS)
    k_bicycle, _ = ug_bicycle(bi.skidpad_sweep(RADIUS, SPEEDS))
    grip_loss = (g_bicycle - g_full) / g_bicycle
    report.data.update({
        "K_double_track": k_full, "K_bicycle": k_bicycle,
        "max_g_double_track": g_full, "max_g_bicycle": g_bicycle,
        "grip_loss_fraction": grip_loss, "fit_r_squared": r2,
    })
    report.add(
        "lateral_transfer_costs_grip",
        0.02 < grip_loss < 0.12,
        f"maximum lateral acceleration drops {g_bicycle:.3f} -> {g_full:.3f} g, "
        f"a {100*grip_loss:.1f}% loss, purely from sharing each axle's load "
        "unevenly. Episode 2's arithmetic, on a real car.",
        value=grip_loss,
    )
    hard = max(pts, key=lambda q: q.a_y_g)
    predicted = (p.roll_stiffness_front_share * p.mass * hard.a_y
                 * p.com_height / p.track_f)
    report.close(hard.lateral_transfer_front, predicted, 0.02,
                 "measured_transfer_matches_the_closed_form", "N", rel=True)
    report.note(
        "F18_predicted_this_before_the_model_existed",
        "FINDINGS F18 estimated, from static geometry and the tire's load "
        "sensitivity alone, that lateral transfer would cost the front axle "
        "about 6% of its grip and the rear about 5%. Measured whole-car loss: "
        f"{100*grip_loss:.1f}%. The prediction was made in Episode 3 with a model "
        "that could not simulate the effect, and it landed.",
        value={"predicted_front_pct": 6.4,
               "measured_whole_car_pct": 100 * grip_loss},
    )

    report.section("Can it respond to an anti-roll bar?")
    arb, arb_bicycle = {}, {}
    for e in ROLL_SHARES:
        d2 = DoubleTrackBackend(replace(p, roll_stiffness_front_share=e))
        arb[e], _ = ug_dt(d2.skidpad_sweep(RADIUS, SPEEDS))
        b2 = BicycleBackend(replace(p, roll_stiffness_front_share=e))
        arb_bicycle[e], _ = ug_bicycle(b2.skidpad_sweep(RADIUS, SPEEDS))
    report.data["K_vs_roll_share"] = arb
    report.data["K_vs_roll_share_bicycle"] = arb_bicycle
    vals = list(arb.values())
    report.add(
        "stiffer_front_bar_adds_understeer",
        all(y > x for x, y in zip(vals, vals[1:])),
        "K rises monotonically with front roll stiffness: "
        + ", ".join(f"{e:.2f}->{v:+.2f}" for e, v in arb.items())
        + " deg/g. Gate 1 invariant 3.",
        value=arb,
    )
    spread = vals[-1] - vals[0]
    floor = schema.VALIDATION_BANDS["understeer_gradient_noise_floor_deg_per_g"]
    report.add(
        "the_bar_is_worth_more_than_the_noise_floor",
        spread > floor,
        f"the documented 0.40-0.70 roll-share range moves K by {spread:.2f} deg/g "
        f"against a {floor} deg/g real-world measurement noise floor — resolvable, "
        f"but only by a factor of {spread/floor:.1f}. See the note.",
        value=spread,
    )
    report.note(
        "our_anti_roll_bar_authority_is_weaker_than_a_real_car_s",
        f"The full documented roll-share range buys {spread:.2f} deg/g, only "
        f"{spread/floor:.1f}x the 0.2 deg/g floor at which a professional test "
        "program can distinguish two builds. A single realistic bar change — say "
        "0.05 of roll share — moves K by about 0.05 deg/g, which is BELOW that "
        "floor and would not be reportable. Real chassis engineers get much more "
        "than this out of a bar. Two reasons ours is weak, and the second is the "
        "interesting one: we model all lateral transfer as elastic, which if "
        "anything OVERSTATES bar authority; and a real bar acts partly through "
        "roll camber and roll steer, which change the tires' effective slip "
        "angles rather than just their loads, and we model neither. Same missing "
        "terms as the understeer gap. **Treat the Season 2 roll-stiffness sweeps "
        "as directionally right and quantitatively weak until those terms exist.**",
        value={"spread_deg_per_g": spread, "noise_floor": floor,
               "ratio": spread / floor},
    )
    bic_spread = max(arb_bicycle.values()) - min(arb_bicycle.values())
    report.add(
        "the_bicycle_model_cannot_see_the_bar_at_all",
        bic_spread < 1e-9,
        f"the same sweep through the bicycle model moves K by {bic_spread:.2e} "
        "deg/g — exactly zero. It has no left and right, so roll stiffness "
        "distribution is not merely approximated, it is invisible. **This is the "
        "Episode 5 result.**",
        value=bic_spread,
    )

    report.section("What does a bar do to how far the car leans?")
    # The sweep above holds TOTAL roll stiffness fixed and moves only its
    # distribution, so the roll angle cannot change under it. That is one valid
    # protocol; bolting a bar on is the other, and it is the one a reader means
    # when they ask whether a stiffer bar reduces body roll. The figures quote
    # numbers from it, so it gets gated here. See FINDINGS F37.
    grad = p.roll_gradient_deg_per_g
    lo, hi = 3.0, 7.0
    report.add(
        "roll_gradient_lands_in_the_published_road_car_range",
        lo < grad < hi,
        f"body roll works out at {grad:.1f} deg/g from the documented spring "
        f"rates, inside the {lo:.0f}-{hi:.0f} deg/g band quoted for road cars on "
        "springs. An outside-the-project comparison, not one of our own numbers.",
        value=grad,
    )
    report.add(
        "the_spring_only_share_corroborates_the_assumed_share",
        0.0 < p.roll_stiffness_front_share - p.spring_only_roll_share < 0.05,
        f"the springs alone give a front roll-stiffness share of "
        f"{p.spring_only_roll_share:.3f}; we assume "
        f"{p.roll_stiffness_front_share:.2f}. The gap is what a modest front bar "
        f"({p.bar_rate_for_share(p.roll_stiffness_front_share)[0]/1000:.1f} "
        "kN.m/rad) would supply — two numbers from different routes agreeing.",
        value={"spring_only": p.spring_only_roll_share,
               "assumed": p.roll_stiffness_front_share},
    )
    with_bar = {e: p.roll_gradient_deg_per_g_with_bar(e) for e in ROLL_SHARES}
    report.data["roll_gradient_with_added_bar"] = with_bar
    report.add(
        "adding_any_bar_reduces_roll_whichever_end_it_goes_on",
        all(v <= grad + 1e-9 for v in with_bar.values()),
        "a bar is a spring, so fitting one raises total roll stiffness and the "
        "car leans less no matter which axle it goes on: "
        + ", ".join(f"{e:.2f}->{v:.1f}" for e, v in with_bar.items())
        + f" deg/g against {grad:.1f} on springs alone.",
        value=with_bar,
    )
    report.note(
        "roll_angle_is_largest_with_no_bar_at_all",
        f"The roll angle is **not monotonic** in front roll-stiffness share. It "
        f"peaks at {grad:.1f} deg/g at the spring-only share of "
        f"{p.spring_only_roll_share:.3f} and falls either side — "
        f"{with_bar[min(ROLL_SHARES)]:.1f} deg/g at "
        f"{min(ROLL_SHARES):.2f} (which needs a REAR bar) and "
        f"{with_bar[max(ROLL_SHARES)]:.1f} deg/g at {max(ROLL_SHARES):.2f}. "
        "Not what anyone expects from a knob labelled 'front stiffness', and the "
        "reason is simply that any bar is extra stiffness. **A bar does two "
        "separate things — it reduces lean AND it redistributes load — and only "
        "the redistribution changes the handling balance.** An earlier version of "
        "the anti-roll-bar figure asserted a bar cannot change how far a car "
        "leans, which was true of our parameterisation and false of cars.",
        value={"spring_only_gradient": grad, "with_bar": with_bar},
    )

    report.section("Does it reach a real car yet?")
    road_lo = schema.VALIDATION_BANDS["understeer_gradient_test_band_deg_per_g"][0]
    report.add(
        "still_below_the_road_car_band",
        max(vals) < road_lo,
        f"the most understeering setup in the documented range gives K = "
        f"{max(vals):.2f} deg/g, still below the {road_lo} deg/g floor for a real "
        "car. Lateral load transfer was not the whole story — see the note.",
        value=max(vals),
    )
    report.note(
        "lateral_load_transfer_is_not_where_the_understeer_gap_came_from",
        f"Episode 3 measured K = {k_bicycle:.2f} deg/g and attributed the gap to "
        "the road-car band to missing lateral load transfer plus missing "
        f"suspension effects. Adding lateral load transfer gives {k_full:.2f} "
        "deg/g at the nominal roll split — **essentially unchanged, and slightly "
        "lower**. Front and rear both lose grip to transfer, and at a 0.55 front "
        "roll share on a 54%-front car the two losses very nearly cancel, the "
        "same way the cornering compliances did. What the term DOES buy is "
        f"authority: K spans {min(vals):+.2f} to {max(vals):+.2f} across the "
        "documented bar range, a knob that does not exist in the bicycle model at "
        "all. So the correct attribution is: the remaining gap to a real car is "
        "compliance steer, roll camber, roll steer and aligning torque — the "
        "Bundorf terms — not lateral load transfer. FINDINGS F11's emphasis was "
        "wrong and F29 records the correction.",
        value={"K_bicycle": k_bicycle, "K_double_track": k_full,
               "K_range_over_bar_sweep": [min(vals), max(vals)]},
    )

    report.subtitle = (
        "Gates the four-wheel model. Everything it adds over the two-wheel one is "
        "load moving between wheels, so this is mostly about whether that "
        "bookkeeping is exact — and about one thing the two-wheel model could not "
        "do at all."
    )
    report.find(
        f"The four wheel loads always sum to the car's weight, to {worst:.0e} N. "
        "Cornering moves load onto the outside wheels, braking moves it forward, "
        "and doubling the height of the centre of gravity exactly doubles the "
        "sideways transfer. No fitting parameters anywhere."
    )
    report.find(
        f"**Lateral load transfer costs {100*grip_loss:.0f}% of the car's peak "
        f"cornering grip** — {g_bicycle:.2f} g becomes {g_full:.2f} g, purely from "
        "each axle sharing its load unevenly. Episode 3 predicted about 6% from "
        "static geometry alone, before a model existed that could simulate it."
    )
    report.find(
        "**An anti-roll bar now works, and in the two-wheel model it did nothing "
        f"whatsoever.** Sweeping front roll stiffness from 40% to 70% moves the "
        f"understeer gradient from {min(vals):+.2f} to {max(vals):+.2f} deg/g. The "
        f"identical sweep through the bicycle model moves it by {bic_spread:.0e} — "
        "exactly zero, because the model has no left and right for the bar to act "
        "between."
    )
    report.find(
        "**But it did not close the understeer gap, and that is a correction.** At "
        f"the nominal setup K goes {k_bicycle:.2f} -> {k_full:.2f} deg/g — "
        "essentially unchanged. Both axles lose grip to transfer and the losses "
        "nearly cancel. Episode 3 blamed the missing understeer partly on this "
        "term; that was wrong. What remains is suspension compliance, roll camber "
        "and roll steer."
    )
    report.find(
        "With the centre of gravity lowered to the road the four-wheel model "
        f"reproduces the two-wheel model's gradient to "
        f"{100*abs(k_dt-k_bi)/abs(k_bi):.2f}% and its grip limit to "
        f"{100*abs(g_dt-g_bi)/g_bi:.2f}%. Two independently written models agreeing "
        "in the limit where they must is the strongest check in this diagnostic."
    )

    return {"dt": dt, "bi": bi, "points": pts, "arb": arb,
            "arb_bicycle": arb_bicycle, "k_full": k_full,
            "k_bicycle": k_bicycle, "g_full": g_full, "g_bicycle": g_bicycle,
            "lift": lift}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    report = Report("D5", "Load transfer audit")
    ctx = run_checks(report)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = {
        "Ep 5 - four wheels": (
            OUT_DIR / "D5_four_wheels.svg",
            load_figures.four_wheel_figure(ctx["dt"], ctx["points"]),
        ),
        "Ep 5 - body roll": (
            OUT_DIR / "D5_body_roll.svg",
            load_figures.body_roll_figure(ctx["dt"], ctx["points"]),
        ),
        "Ep 5 - the anti-roll bar": (
            OUT_DIR / "D5_anti_roll_bar.svg",
            load_figures.anti_roll_bar_figure(
                ctx["dt"], ctx["arb"], ctx["arb_bicycle"]),
        ),
        "Ep 5 - low and wide": (
            OUT_DIR / "D5_low_and_wide.svg",
            load_figures.low_and_wide_figure(ctx["dt"]),
        ),
        "technical card": (
            OUT_DIR / "D5_load_transfer_card.svg",
            load_figures.load_transfer_card(
                ctx["dt"], ctx["points"], ctx["arb"], ctx["arb_bicycle"],
                ctx["k_full"], ctx["k_bicycle"], ctx["g_full"], ctx["g_bicycle"],
                ctx["lift"]),
        ),
    }
    for _, (path_, svg) in written.items():
        path_.write_text(svg)
    captions = {
        "Ep 5 - four wheels": "The same corner with four wheels instead of two. "
            "Contact patches sized by load: the outside pair carries several times "
            "what the inside pair does.",
        "Ep 5 - body roll": "The car seen from behind at four cornering forces, "
            "then again with an anti-roll bar fitted. Roll angle is derived from "
            "the spring and bar rates, not drawn for effect. The mechanism a plan "
            "view cannot show — and the second row shows a bar reducing lean "
            "while INCREASING the load it moves across the axle it is fitted to.",
        "Ep 5 - the anti-roll bar": "Two cars in the same corner with different "
            "front bar stiffness, at fixed TOTAL roll stiffness — so both lean "
            "the same amount here and the bar only chooses which axle absorbs "
            "it, and therefore which end gives up. Bolting a bar on instead "
            "raises the total and reduces lean as well; see the body-roll figure.",
        "Ep 5 - low and wide": "The same car cornering with only its height or "
            "its width changed. The two geometric levers that reduce load "
            "transfer rather than merely redistributing it.",
        "technical card": "Per-wheel load against cornering force, the "
            "anti-roll-bar sweep with the bicycle model's flat line for "
            "comparison, and where the wheel-lift threshold sits.",
    }
    md = report.write_markdown(
        [(n, pth, captions[n]) for n, (pth, _) in written.items()],
        command="python -m diagnostics.D5_load_transfer")
    path = report.write()
    report.print_summary(verbose="-v" in argv or "--verbose" in argv)
    print(f"\n  write-up {md}\n  report   {path}")
    for name, (p_, _) in written.items():
        print(f"  {name:<22} {p_}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
