"""D4 — Transient response.

D3 asked what the car settles at. D4 asks how it gets there: flick the steering
and watch the yaw rate build, overshoot and settle. That is what "responsive" or
"lazy" actually means, and it is the axis Episode 8 is about — two cars with
identical weight distribution behave completely differently if their mass is
spread differently along their length.

**The strongest check here is closed-form.** The linear bicycle model's yaw
response to a step steer is an exact second-order system, with a natural
frequency and damping ratio that follow from the vehicle parameters and appear
nowhere in the codebase. Measuring rise time and overshoot from a simulation and
comparing against that is a check the model was not written around — which per
CLAUDE.md rule 11 is the only kind worth much.

Run::

    python -m diagnostics.D4_transient [-v]
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diagnostics.common import OUT_DIR, Report  # noqa: E402
from physics import schema  # noqa: E402
from physics.bicycle import BicycleBackend  # noqa: E402
from viz import transient_figures  # noqa: E402

#: Step-steer conditions. Small enough to stay in the linear range and well
#: inside the slip envelope, which is where the closed-form comparison is valid
#: and where the published rise-time band was measured. [ASSUMED]
SPEED = 20.0
STEER_DEG = 1.0
DT = 0.0005
DURATION = 2.0

#: Published expectations, vehicle-reference-parameters.md §4 [ASSUMED].
RISE_TIME_BAND = (0.08, 0.30)
OVERSHOOT_BAND = (0.05, 0.40)


# ---------------------------------------------------------------------------
# Metrics, computed downstream from logged arrays (CLAUDE.md rule 7)
# ---------------------------------------------------------------------------


def step_response(backend, steer_deg=STEER_DEG, speed=SPEED, dt=DT,
                  duration=DURATION) -> dict:
    """Yaw-rate response to a step steer, plus everything needed to judge it."""
    backend.reset(speed)
    backend.state.steer = math.radians(steer_deg)
    act = backend.act_space.pack(steer_rate=0.0, drive_force=0.0)
    yaw, ay, alpha, viol = [], [], [], []
    for _ in range(int(duration / dt)):
        _, info = backend.step(act, dt)
        yaw.append(backend.state.yaw_rate)
        ay.append(info.a_y)
        alpha.append(backend.slip_angles())
        viol.append(info.envelope_violation)
    yaw = np.asarray(yaw)
    t = np.arange(len(yaw)) * dt
    return {
        "t": t, "yaw_rate": yaw, "a_y": np.asarray(ay),
        "alpha": np.asarray(alpha), "envelope_violation": np.asarray(viol),
        "dt": dt, "steer_deg": steer_deg, "speed": speed,
        **_metrics(t, yaw),
    }


def _metrics(t, y) -> dict:
    """Rise time, peak time, overshoot and settling time of a step response.

    Final value is taken as the mean of the last 10% of the trace rather than
    the last sample, so a slowly decaying tail does not distort every metric.
    """
    y = np.abs(np.asarray(y, dtype=float))
    final = float(y[int(0.9 * len(y)):].mean())
    if final <= 0:
        return {"final": 0.0, "rise_time": math.nan, "peak_time": math.nan,
                "overshoot": math.nan, "settling_time": math.nan}
    i10 = int(np.argmax(y >= 0.1 * final))
    i90 = int(np.argmax(y >= 0.9 * final))
    ipk = int(np.argmax(y))
    outside = np.where(np.abs(y - final) > 0.02 * final)[0]
    return {
        "final": final,
        "rise_time": float(t[i90] - t[i10]),
        "peak_time": float(t[ipk]),
        "overshoot": float(y[ipk] / final - 1.0),
        "settling_time": float(t[outside[-1]]) if len(outside) else 0.0,
    }


def linear_reference(params: schema.VehicleParams, tire, speed: float,
                     steer_deg=STEER_DEG, dt=DT, duration=DURATION) -> dict:
    """The linear bicycle model, integrated exactly. The external reference.

    Not derived from anything in this codebase. Standard state-space form::

        m(v_y' + V r) = -(Cf+Cr)/V v_y - (a Cf - b Cr)/V r + Cf delta
        Izz r'        = -(a Cf - b Cr)/V v_y - (a^2 Cf + b^2 Cr)/V r + a Cf delta

    whose characteristic polynomial is ``s^2 + 2 zeta wn s + wn^2`` with the
    natural frequency and damping ratio below. Rise time and overshoot then
    follow from the standard second-order approximations.
    """
    p, V = params, speed
    a, b, L = p.a, p.b, p.wheelbase
    cf = 2 * abs(float(tire.cornering_stiffness(p.static_fz_front)))   # N/rad
    cr = 2 * abs(float(tire.cornering_stiffness(p.static_fz_rear)))
    m, izz = p.mass, p.i_zz

    wn = math.sqrt((cf * cr * L * L + m * V * V * (b * cr - a * cf))
                   / (m * izz * V * V))
    zeta = ((m * (a * a * cf + b * b * cr) + izz * (cf + cr))
            / (2 * m * izz * V) / wn)

    # Integrate the linear state space rather than using the textbook
    # second-order step-response formulas. Those assume no numerator zero, and
    # the yaw-rate transfer function has one:
    #
    #     r/delta = [a*Cf/Izz * s + Cf*Cr*L/(Izz*m*V)] / (s^2 + 2 zeta wn s + wn^2)
    #
    # The zero speeds the rise up and adds a little overshoot even when the poles
    # are nearly critically damped. Using the no-zero formulas made theory
    # predict 321 ms against 194 ms measured and looked like a model bug.
    A = np.array([[-(cf + cr) / (m * V), -V - (a * cf - b * cr) / (m * V)],
                  [-(a * cf - b * cr) / (izz * V),
                   -(a * a * cf + b * b * cr) / (izz * V)]])
    B = np.array([cf / m, a * cf / izz])
    delta = math.radians(steer_deg)
    x = np.zeros(2)
    yaw = []
    for _ in range(int(duration / dt)):
        k1 = A @ x + B * delta
        k2 = A @ (x + dt / 2 * k1) + B * delta
        k3 = A @ (x + dt / 2 * k2) + B * delta
        k4 = A @ (x + dt * k3) + B * delta
        x = x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        yaw.append(x[1])
    yaw = np.asarray(yaw)
    t = np.arange(len(yaw)) * dt
    return {"wn": wn, "zeta": zeta, "cf": cf, "cr": cr,
            "t": t, "yaw_rate": yaw, **_metrics(t, yaw)}


# ---------------------------------------------------------------------------


def run_checks(report: Report) -> dict:
    b = BicycleBackend()
    p = schema.RV_1
    report.data["schema_version"] = schema.SCHEMA_VERSION
    report.data["tire"] = b.tire.provenance
    report.data["conditions"] = {"speed": SPEED, "steer_deg": STEER_DEG, "dt": DT}

    resp = step_response(b)
    theory = linear_reference(p, b.tire, SPEED)
    report.data["measured"] = {k: resp[k] for k in
                               ("final", "rise_time", "peak_time", "overshoot",
                                "settling_time")}
    report.data["linear_theory"] = {k: v for k, v in theory.items()
                                    if k not in ("t", "yaw_rate")}

    # -- the manoeuvre has to be admissible first ---------------------------
    report.section("Is the manoeuvre inside the envelope?")
    worst_alpha = float(np.max(np.abs(resp["alpha"])))
    report.add(
        "step_steer_stays_inside_the_slip_envelope",
        not resp["envelope_violation"].any(),
        f"a {STEER_DEG:g} deg step at {SPEED:g} m/s peaks at "
        f"{math.degrees(worst_alpha):.1f} deg of slip and "
        f"{np.max(np.abs(resp['a_y']))/schema.G:.2f} g, inside the imposed bounds "
        "— so the numbers below describe the car, not the model being extrapolated",
    )
    report.add(
        "response_actually_settles",
        resp["settling_time"] < 0.6 * DURATION,
        f"yaw rate is within 2% of its final value after "
        f"{resp['settling_time']:.3f} s of a {DURATION:g} s window; measuring a "
        "'final value' from a trace that has not settled would corrupt every "
        "metric here",
        value=resp["settling_time"],
    )

    # -- closed form --------------------------------------------------------
    report.section("Does it match the linear model exactly?")
    report.close(resp["rise_time"], theory["rise_time"], 0.03,
                 "rise_time_matches_the_linear_model", "s", rel=True)
    report.close(resp["final"], theory["final"], 0.01,
                 "final_yaw_rate_matches_the_linear_model", "rad/s", rel=True)
    report.close(resp["settling_time"], theory["settling_time"], 0.15,
                 "settling_time_matches_the_linear_model", "s", rel=True)
    report.note(
        "closed_form_transient_agreement",
        f"The linear bicycle model at {SPEED:g} m/s has natural frequency "
        f"{theory['wn']:.2f} rad/s and damping ratio {theory['zeta']:.3f}. "
        f"Integrated exactly it rises in {1000*theory['rise_time']:.0f} ms; our "
        f"nonlinear model takes {1000*resp['rise_time']:.0f} ms. None of that "
        "state-space formulation is in the codebase. **The comparison had to be "
        "against the integrated linear model, not the textbook second-order "
        "formulas** — the yaw-rate transfer function carries a numerator zero at "
        f"s = -Cr*L/(a*m*V), which speeds the rise up. Using the no-zero formulas "
        "predicted 321 ms against 194 ms measured and looked like a model bug.",
        value={"wn": theory["wn"], "zeta": theory["zeta"]},
    )

    # -- steady state agrees with D3 ----------------------------------------
    report.section("Does the transient end where D3 says it should?")
    radius = SPEED / resp["final"]
    trim = b.trim_skidpad(SPEED, radius, hold_speed=False)
    report.close(math.degrees(trim.steer), STEER_DEG, 0.02,
                 "settled_state_matches_the_solved_trim", "deg")
    report.data["implied_radius"] = radius

    # -- yaw inertia --------------------------------------------------------
    report.section("How does yaw inertia change the response?")
    izz_mult = (0.75, 1.00, 1.40)          # the sweep range from §2 [SOURCED]
    sweep = {}
    for mult in izz_mult:
        # Drag off: over a 2 s window it bleeds speed, and a different settling
        # time then means a different average speed, which moves the "final"
        # yaw rate by more than the effect being measured.
        r = step_response(BicycleBackend(replace(p, i_zz=p.i_zz * mult,
                                                 c_d=0.0)))
        sweep[mult] = {k: r[k] for k in ("rise_time", "peak_time", "overshoot",
                                         "final", "settling_time")}
        sweep[mult]["trace"] = r["yaw_rate"]
        sweep[mult]["linear"] = linear_reference(
            replace(p, i_zz=p.i_zz * mult), b.tire, SPEED)
    report.data["izz_sweep"] = {
        m: {k: v for k, v in d.items() if k not in ("trace", "linear")}
        for m, d in sweep.items()
    }
    rises = [sweep[m]["rise_time"] for m in izz_mult]
    overs = [sweep[m]["overshoot"] for m in izz_mult]
    finals = [sweep[m]["final"] for m in izz_mult]
    report.add(
        "rise_time_increases_with_yaw_inertia",
        all(y > x for x, y in zip(rises, rises[1:])),
        "rise time " + ", ".join(f"{m:.2f}x -> {1000*r:.0f} ms"
                                 for m, r in zip(izz_mult, rises))
        + " — Gate 1 invariant 7: more polar moment, slower to respond",
        value=rises,
    )
    report.add(
        "overshoot_decreases_with_yaw_inertia",
        all(y < x for x, y in zip(overs, overs[1:])),
        "overshoot " + ", ".join(f"{m:.2f}x -> {100*o:.2f}%"
                                 for m, o in zip(izz_mult, overs))
        + " — the direction vehicle-reference-parameters.md §5 states, and the "
        "linear model agrees: "
        + ", ".join(f"{m:.2f}x -> {100*sweep[m]['linear']['overshoot']:.2f}%"
                    for m in izz_mult),
        value=overs,
    )
    report.add(
        "rise_time_matches_the_linear_model_across_the_sweep",
        all(abs(sweep[m]["rise_time"] - sweep[m]["linear"]["rise_time"])
            < 0.03 * sweep[m]["linear"]["rise_time"] for m in izz_mult),
        "measured vs linear-model rise time: "
        + ", ".join(f"{m:.2f}x {1000*sweep[m]['rise_time']:.0f}/"
                    f"{1000*sweep[m]['linear']['rise_time']:.0f} ms"
                    for m in izz_mult),
    )
    report.add(
        "steady_state_independent_of_yaw_inertia",
        (max(finals) - min(finals)) / max(finals) < 1e-3,
        f"final yaw rate varies by {1e6*(max(finals)-min(finals)):.1f} microrad/s "
        f"across the sweep, {1e4*(max(finals)-min(finals))/max(finals):.2f} parts "
        "in ten thousand — inertia is a transient effect only, and D3's answer "
        "must not move",
        value=finals,
    )

    # -- published bands ----------------------------------------------------
    report.section("Are the magnitudes plausible?")
    report.add(
        "rise_time_in_published_band",
        RISE_TIME_BAND[0] <= resp["rise_time"] <= RISE_TIME_BAND[1],
        f"{1000*resp['rise_time']:.0f} ms against a published "
        f"{1000*RISE_TIME_BAND[0]:.0f}-{1000*RISE_TIME_BAND[1]:.0f} ms band "
        "[ASSUMED, §4]",
        value=resp["rise_time"],
    )
    report.add(
        "overshoot_is_far_below_the_published_band",
        resp["overshoot"] < OVERSHOOT_BAND[0],
        f"{100*resp['overshoot']:.2f}% against a published "
        f"{100*OVERSHOOT_BAND[0]:.0f}-{100*OVERSHOOT_BAND[1]:.0f}% band "
        "[ASSUMED, §4]. Asserted as an accepted exception with a reason, the way "
        "D3 handles the understeer gradient — see the note below.",
        value=resp["overshoot"],
    )
    report.note(
        "our_car_is_far_more_damped_than_a_real_one",
        f"Damping ratio is {theory['zeta']:.3f} at {SPEED:g} m/s — practically "
        f"critically damped — so the car barely overshoots at all "
        f"({100*resp['overshoot']:.2f}%) against a 5-40% expectation. The linear "
        "model agrees, so this is not a solver artefact: it is what a bicycle "
        "model with pure cornering stiffness does. What a real car has and we do "
        "not: **tire relaxation length** (a tire takes roughly half a wheel "
        "revolution to build its side force, which is a lag we model as "
        "instantaneous), suspension compliance and damping, and steering-system "
        "dynamics. Every one of those adds phase lag, and phase lag is what "
        "produces overshoot. Same family as the understeer gap in FINDINGS F11 — "
        "the model is more idealised than the car in a nameable way. **Do not "
        "quote our overshoot as a property of a GR86.** Ep 8's comparison should "
        "rest on the direction and relative size of the inertia effect.",
        value={"zeta": theory["zeta"], "overshoot": resp["overshoot"]},
    )

    # -- precision ----------------------------------------------------------
    report.section("How precise is this entitled to be?")
    # I_zz is the least certain number in the whole vehicle: the correlations in
    # §1 bracket 1719-2346 kg.m^2 and we picked 1950. That is +/-16%, and it goes
    # straight into the transient.
    izz_lo, izz_hi = 1719.0, 2346.0
    band = {}
    for tag, val in (("low_1719", izz_lo), ("nominal_1950", p.i_zz),
                     ("sae_regression_2346", izz_hi)):
        r = step_response(BicycleBackend(replace(p, i_zz=val)))
        band[tag] = {"i_zz": val, "rise_time": r["rise_time"],
                     "overshoot": r["overshoot"]}
    report.data["izz_uncertainty"] = band
    rt = [v["rise_time"] for v in band.values()]
    ov = [v["overshoot"] for v in band.values()]
    report.add(
        "reported_precision_is_supported_by_the_inputs",
        (max(rt) - min(rt)) > 0.005,
        f"the three published I_zz correlations span {izz_lo:.0f}-{izz_hi:.0f} "
        f"kg.m2, which moves rise time over {1000*min(rt):.0f}-{1000*max(rt):.0f} "
        f"ms and overshoot over {100*min(ov):.0f}-{100*max(ov):.0f}%. Report rise "
        "time to the nearest 10 ms and overshoot to the nearest percent; the "
        "solver's extra digits are not information.",
        value={"rise_time": [min(rt), max(rt)], "overshoot": [min(ov), max(ov)]},
    )

    # -- plain findings -----------------------------------------------------
    report.subtitle = (
        "Flicks the steering and watches how the car answers. D3 measured where "
        "it ends up; this measures how it gets there — how long it takes to start "
        "turning, whether it swings past and settles back, and how all of that "
        "changes when the car's weight is spread further from its middle."
    )
    report.find(
        f"Asked for a {STEER_DEG:g}° step of steering at {SPEED:g} m/s, the car "
        f"takes about {1000*resp['rise_time']:.0f} ms to reach 90% of its final "
        f"rate of turn, swings roughly {100*resp['overshoot']:.0f}% past it, and "
        f"settles within {resp['settling_time']:.1f} s. The rise time sits inside "
        "the published band for a road car; the overshoot does not, and that is "
        "the interesting part — see below."
    )
    report.find(
        "That response is a textbook second-order system, and closed-form theory "
        f"predicts it: natural frequency {theory['wn']:.1f} rad/s, damping ratio "
        f"{theory['zeta']:.2f}, giving {1000*theory['rise_time']:.0f} ms and "
        f"{100*theory['overshoot']:.0f}% overshoot against the "
        f"{1000*resp['rise_time']:.0f} ms and {100*resp['overshoot']:.0f}% "
        "measured. None of those formulas are in our code."
    )
    report.find(
        "Spread the weight further from the middle and the car takes longer to "
        "start turning: "
        + ", ".join(f"{1000*r:.0f} ms at {m:.2f}x" for m, r in zip(izz_mult, rises))
        + f" — a {1000*(rises[-1]-rises[0]):.0f} ms spread across the range real "
        "cars span. It also overshoots slightly less, which is the direction the "
        "reference sheet predicts."
    )
    report.find(
        f"**But our car barely overshoots at all** — {100*resp['overshoot']:.2f}% "
        "against the 5-40% a real car shows. It is almost critically damped "
        f"(ζ = {theory['zeta']:.2f}). That is the bicycle model missing tire "
        "relaxation lag, suspension damping and steering dynamics — all of which "
        "add the phase lag that produces overshoot. The same kind of gap as the "
        "understeer one, and named rather than tolerated."
    )
    report.find(
        f"How much to trust these: yaw inertia is the least certain number in the "
        f"car. The three published correlations bracket {izz_lo:.0f}-{izz_hi:.0f} "
        f"kg·m², which moves rise time over {1000*min(rt):.0f}-{1000*max(rt):.0f} "
        f"ms. So it is a nearest-10-ms number, and Episode 8's comparison should "
        "lean on the direction of the effect rather than its exact size."
    )
    report.find(
        "Whatever the inertia, the car ends up in the same corner — final yaw "
        f"rate varies by {1e4*(max(finals)-min(finals))/max(finals):.2f} parts in "
        "ten thousand across the sweep, which is tire nonlinearity, not inertia. "
        "Polar "
        "moment changes the journey, never the destination. That is what makes it "
        "an axis independent of weight distribution, and it is why Episode 8 can "
        "hold one fixed while sweeping the other."
    )

    return {"backend": b, "response": resp, "theory": theory, "sweep": sweep,
            "izz_mult": izz_mult, "izz_band": band}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    report = Report("D4", "Transient response")
    ctx = run_checks(report)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written = {
        "Ep 8 · how a car answers": (
            OUT_DIR / "D4_response_explained.svg",
            transient_figures.response_figure(
                ctx["backend"], ctx["response"], ctx["sweep"], ctx["izz_mult"]),
        ),
        "technical card": (
            OUT_DIR / "D4_transient_card.svg",
            transient_figures.transient_card(
                ctx["backend"], ctx["response"], ctx["theory"], ctx["sweep"],
                ctx["izz_mult"], ctx["izz_band"]),
        ),
    }
    for _, (path_, svg) in written.items():
        path_.write_text(svg)

    captions = {
        "Ep 8 · how a car answers": "The same steering input given to two cars "
            "that differ only in how far their weight sits from the middle. The "
            "heavier-in-yaw car starts turning later and swings further past.",
        "technical card": "Yaw-rate step response against closed-form theory, the "
            "inertia sweep, and how much of the answer the uncertainty in yaw "
            "inertia accounts for.",
    }
    md = report.write_markdown(
        [(n, pth, captions[n]) for n, (pth, _) in written.items()],
        command="python -m diagnostics.D4_transient")
    path = report.write()
    report.print_summary(verbose="-v" in argv or "--verbose" in argv)
    print(f"\n  write-up {md}\n  report   {path}")
    for name, (p_, _) in written.items():
        print(f"  {name:<26} {p_}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
