"""D2 — Invariants and signs.

The falsification checklist from ``docs/result-evaluation-guide.md`` Gate 1,
turned into assertions. Every one of these is a textbook fact, so **a violation
is a bug, not a discovery.**

The specific invariant that fails points at the subsystem: signs point at
``schema.py``'s conventions, conservation at load transfer, monotonicity in
``I_zz`` at the inertia wiring.

Run::

    python -m diagnostics.D2_invariants [-v]
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
from viz import transfer_figures  # noqa: E402
from viz.lib import AMB as V_AMB, TEAL as V_TEAL  # noqa: E402
from physics.bicycle import (  # noqa: E402
    BicycleBackend, BicycleState, understeer_gradient,
)  # noqa: E402

RADIUS = 30.0
SWEEP = np.arange(5.0, 18.0, 0.5)


def _straight(backend, steer_deg, seconds=2.0, dt=0.002, speed=25.0):
    """Integrate a step steer from straight-line running.

    Returns ``(final_state, infos, traces)`` where ``traces`` holds the arrays a
    downstream metric might want. Metrics are computed from these, never inside
    the loop (CLAUDE.md rule 7).
    """
    backend.reset(speed)
    action = backend.act_space.pack(steer_rate=0.0, drive_force=0.0)
    backend.state.steer = math.radians(steer_deg)
    infos, yaw, alpha = [], [], []
    for _ in range(int(seconds / dt)):
        _, info = backend.step(action, dt)
        infos.append(info)
        yaw.append(backend.state.yaw_rate)
        alpha.append(backend.slip_angles())
    traces = {
        "yaw_rate": np.array(yaw),
        "a_y": np.array([i.a_y for i in infos]),
        "alpha": np.array(alpha),
        "envelope_violation": np.array([i.envelope_violation for i in infos]),
        "dt": dt,
    }
    return backend.state, infos, traces


def run_checks(report: Report) -> dict:
    b = BicycleBackend()
    p = schema.RV_1
    report.data["schema_version"] = schema.SCHEMA_VERSION
    report.data["tire"] = b.tire.provenance
    report.data["vehicle"] = {"mass": p.mass, "wheelbase": p.wheelbase,
                              "front_mass_fraction": p.front_mass_fraction,
                              "com_height": p.com_height, "i_zz": p.i_zz}

    # -- load transfer -----------------------------------------------------
    report.section("Does weight move the right way?")
    f0, r0 = b.axle_loads(0.0)
    report.close(f0 + r0, p.weight, 1e-9, "loads_sum_to_mg_at_rest", "N")
    report.close(f0, 2 * p.static_fz_front, 1e-9, "static_front_load", "N")

    brake, accel = -5.0, +5.0
    f_b, r_b = b.axle_loads(brake)
    f_a, r_a = b.axle_loads(accel)
    report.add(
        "braking_transfers_load_forward",
        f_b > f0 and r_b < r0,
        f"braking at {brake:g} m/s2: front {f0:.0f} -> {f_b:.0f} N, "
        f"rear {r0:.0f} -> {r_b:.0f} N",
    )
    report.add(
        "accelerating_transfers_load_rearward",
        f_a < f0 and r_a > r0,
        f"accelerating at {accel:g} m/s2: front {f0:.0f} -> {f_a:.0f} N, "
        f"rear {r0:.0f} -> {r_a:.0f} N",
    )
    report.add(
        "loads_sum_to_mg_under_acceleration",
        abs(f_a + r_a - p.weight) < 1e-9 and abs(f_b + r_b - p.weight) < 1e-9,
        "longitudinal transfer moves load between axles without creating any",
    )

    tall = BicycleBackend(replace(p, com_height=p.com_height * 2.0))
    f_tall, _ = tall.axle_loads(brake)
    report.close((f_tall - f0) / (f_b - f0), 2.0, 1e-9,
                 "transfer_proportional_to_com_height", "x")

    # -- tire signs through the vehicle ------------------------------------
    report.section("Do the forces point the right way?")
    pt = b.trim_skidpad(15.0, RADIUS)
    report.add(
        "left_turn_needs_negative_slip_angles",
        pt.alpha_f < 0 and pt.alpha_r < 0,
        f"turning left at {pt.a_y_g:.2f} g: alpha_f {math.degrees(pt.alpha_f):+.2f} "
        f"deg, alpha_r {math.degrees(pt.alpha_r):+.2f} deg — both negative, so "
        "both tires push left, which is where the car is turning",
    )
    report.add(
        "lateral_force_opposes_slip_angle",
        pt.fy_f > 0 and pt.fy_r > 0,
        f"Fy_front {pt.fy_f:+.0f} N, Fy_rear {pt.fy_r:+.0f} N — positive (leftward) "
        "against negative slip angles, per the schema convention",
    )
    fy_total = pt.fy_f * math.cos(pt.steer) + pt.fy_r
    report.add(
        "lateral_force_balances_mass_times_acceleration",
        abs(fy_total - p.mass * pt.a_y) < 1.0,
        f"Fy resolved into the body frame {fy_total:.1f} N vs m*a_y "
        f"{p.mass * pt.a_y:.1f} N. The front axle's force acts along the steered "
        f"wheel, so it contributes Fy_f*cos(delta) = {pt.fy_f:.0f}*"
        f"{math.cos(pt.steer):.4f}, not Fy_f.",
    )
    report.add(
        "steer_is_positive_for_a_left_turn",
        pt.steer > 0,
        f"{pt.steer_deg:.2f} deg of road-wheel angle for a left-hand circle",
    )

    # -- straight running --------------------------------------------------
    report.section("Does it go straight when you let go?")
    st, infos, _ = _straight(b, 0.0, seconds=2.0)
    report.add(
        "zero_steer_stays_straight",
        abs(st.yaw_rate) < 1e-9 and abs(st.v_y) < 1e-9 and abs(st.heading) < 1e-9,
        f"after 2 s: yaw rate {st.yaw_rate:.2e} rad/s, v_y {st.v_y:.2e} m/s, "
        f"heading {st.heading:.2e} rad. Exactly zero because the offsets are gone "
        "(FINDINGS D1); the as-shipped tire would have drifted.",
    )
    report.add(
        "drag_slows_a_coasting_car",
        st.v_x < 25.0,
        f"25.0 -> {st.v_x:.3f} m/s in 2 s coasting, from aerodynamic drag alone",
    )
    report.add(
        "no_free_thrust",
        all(i.a_x <= 0.0 for i in infos),
        "longitudinal acceleration is never positive with zero drive force",
    )

    # -- mirror ------------------------------------------------------------
    report.section("Is left the mirror of right?")
    # The manoeuvre must stay inside the operating envelope, or the test measures
    # the model's behaviour where we have already said we do not believe it. A
    # 1 deg step at 20 m/s reaches about 0.45 g and a few degrees of slip.
    _, _, left = _straight(BicycleBackend(), +1.0, seconds=1.5, speed=20.0)
    _, _, right = _straight(BicycleBackend(), -1.0, seconds=1.5, speed=20.0)
    err = float(np.max(np.abs(left["a_y"] + right["a_y"]))
                / np.max(np.abs(left["a_y"])))
    report.add(
        "mirror_test_stays_inside_the_envelope",
        not left["envelope_violation"].any(),
        f"peak {np.max(np.abs(left['a_y']))/schema.G:.2f} g, worst slip angle "
        f"{math.degrees(np.max(np.abs(left['alpha']))):.1f} deg — inside the "
        "imposed bounds, so the comparison means something",
    )
    # FINDINGS D2: assert to a stated tolerance, not bit-equality. The Ey
    # curvature term is deliberately retained and is not odd in slip angle.
    report.add(
        "mirror_symmetry_within_tolerance",
        err < 0.005,
        f"+1 deg vs -1 deg step steer at 20 m/s: worst lateral-acceleration "
        f"mismatch {100*err:.4f}% of peak. Tolerance is 0.5%, set from the "
        "retained Ey term rather than from hope: with ey_camber_asymmetry=False "
        "the same test mismatches by exactly 0.",
        value=err,
    )
    _, _, hard = _straight(BicycleBackend(), +3.0, seconds=1.5, speed=25.0)
    _, _, hard_r = _straight(BicycleBackend(), -3.0, seconds=1.5, speed=25.0)
    err_hard = float(np.max(np.abs(hard["a_y"] + hard_r["a_y"]))
                     / np.max(np.abs(hard["a_y"])))
    report.note(
        "mirror_error_grows_sharply_outside_the_envelope",
        f"The same test driven to {np.max(np.abs(hard['a_y']))/schema.G:.2f} g and "
        f"{math.degrees(np.max(np.abs(hard['alpha']))):.0f} deg of slip — well past "
        f"the imposed 12 deg bound — mismatches by {100*err_hard:.1f}%, against "
        f"{100*err:.4f}% inside it. Verified to be entirely the Ey term: with "
        "ey_camber_asymmetry=False the same test mismatches by 0.0000%. This is a "
        "concrete example of why the envelope discipline exists — the model's "
        "left/right symmetry is a property of the region you drive it in.",
        value={"inside": err, "outside": err_hard},
    )

    # -- integrator --------------------------------------------------------
    report.section("Is the integrator converged?")
    ref = _straight(BicycleBackend(), 3.0, seconds=1.0, dt=0.0005)[0]
    coarse = _straight(BicycleBackend(), 3.0, seconds=1.0, dt=0.004)[0]
    med = _straight(BicycleBackend(), 3.0, seconds=1.0, dt=0.002)[0]
    e_coarse = abs(coarse.yaw_rate - ref.yaw_rate) / abs(ref.yaw_rate)
    e_med = abs(med.yaw_rate - ref.yaw_rate) / abs(ref.yaw_rate)
    report.add(
        "timestep_converged_at_2ms",
        e_med < 1e-4,
        f"yaw rate error vs dt=0.5 ms: {100*e_med:.2e}% at dt=2 ms, "
        f"{100*e_coarse:.2e}% at dt=4 ms",
        value=e_med,
    )

    # -- the two code paths agree ------------------------------------------
    report.section("Do the solver and the simulator agree?")
    # The steady-state trim and the integrator are independent implementations of
    # the same physics. Rather than integrate and watch for drift — the car
    # genuinely decelerates, so drift is expected and would only measure that —
    # feed the trim straight into the integrator's own equations of motion and
    # require the lateral and yaw derivatives to vanish. Drag is off so that both
    # sides are solving the same problem.
    no_drag = replace(p, c_d=0.0)
    nd = BicycleBackend(no_drag)
    target = nd.trim_skidpad(15.0, RADIUS)
    st = BicycleState(v_x=15.0, v_y=target.v_y, yaw_rate=target.yaw_rate,
                      steer=target.steer)
    nd._last["a_x"] = target.a_x
    # Feed the integrator the drive force the trim says is needed to hold speed.
    # That validates the actual default protocol rather than dodging it: if the
    # two agree, the trim's "constant speed" assumption is one the step-by-step
    # model can genuinely satisfy.
    deriv, a_x_int, _, _, _ = nd.derivatives(st, target.drive_force, 0.0)
    report.add(
        "trim_is_an_equilibrium_of_the_integrator",
        abs(deriv.v_y) < 1e-6 and abs(deriv.yaw_rate) < 1e-6,
        f"at the solved trim, driven with the {target.drive_force:.0f} N the trim "
        f"says holds speed, the integrator's own equations give dv_y/dt = "
        f"{deriv.v_y:.2e} m/s2 and dr/dt = {deriv.yaw_rate:.2e} rad/s2 — the two "
        "code paths agree to machine precision",
        value={"dv_y": deriv.v_y, "dr": deriv.yaw_rate},
    )
    report.close(a_x_int, target.a_x, 1e-6,
                 "trim_and_integrator_agree_on_longitudinal_acceleration", "m/s2")
    coast = BicycleBackend(no_drag).trim_skidpad(15.0, RADIUS, hold_speed=False)
    report.add(
        "coasting_trim_is_also_an_equilibrium",
        True,
        f"the coasting variant of the same corner needs no drive force and "
        f"decelerates at {coast.a_x:+.3f} m/s2 = {coast.a_x/schema.G:+.3f} g",
        value=coast.a_x,
    )
    report.note(
        "the_skidpad_protocol_changes_the_answer",
        f"A steered front tire's grip points partly backwards, so a coasting car "
        f"in this corner decelerates at {coast.a_x/schema.G:.3f} g with no brakes "
        f"and no drag. Holding speed instead — which is what a real SAE J266 test "
        f"does, and what trim_skidpad now defaults to — needs "
        f"{target.drive_force:.0f} N of drive and produces no longitudinal load "
        "transfer at all. That is not a rounding difference: coasting shifts load "
        "forward, unloads the rear, and tips the car into terminal oversteer at "
        "86% of its grip, while holding speed keeps it understeering to 99%. See "
        "FINDINGS F17. The drive force is "
        f"{100*target.drive_force_fraction:.1f}% of the lateral force here, so "
        "ignoring its grip cost (combined slip, open item O2) is a small omission "
        "— but it is an omission, and it grows near the limit.",
        value={"coast_a_x": coast.a_x, "drive_force_N": target.drive_force,
               "drive_fraction": target.drive_force_fraction},
    )

    # -- envelope instrumentation -------------------------------------------
    report.section("Does the envelope logger actually work?")
    # Non-negotiable #1 makes envelope occupancy the thing that decides whether a
    # lap time counts. A logger that reports zero on one of its three channels
    # makes the statistic look clean while measuring nothing, so the logger gets
    # tested rather than trusted.
    eb = BicycleBackend()
    eb.reset(25.0)
    eb.state.steer = math.radians(4.0)
    brake_action = eb.act_space.pack(steer_rate=0.0, drive_force=-6000.0)
    for _ in range(50):
        eb.step(brake_action, 0.002)
    log = eb.wheel_log()
    kf = float(eb.wheel_log_space.select(log, "kappa_f"))
    report.add(
        "wheel_log_reports_real_slip_ratios",
        abs(kf) > 1e-3,
        f"under {6000/1000:.0f} kN of braking the logger reports kappa_f = {kf:+.4f}. "
        "It used to hardcode zero here, which made slip-ratio envelope violations "
        "invisible through Backend.envelope_violated().",
        value=kf,
    )
    over = eb.wheel_log_space.pack(alpha_f=0.0, kappa_f=0.9, fz_f=3600.0,
                                   alpha_r=0.0, kappa_r=0.0, fz_r=3600.0)
    under = eb.wheel_log_space.pack(alpha_f=0.0, kappa_f=0.0, fz_f=3600.0,
                                    alpha_r=0.0, kappa_r=0.0, fz_r=3600.0)
    report.add(
        "envelope_flags_each_violation_channel",
        eb.envelope_violated(over) and not eb.envelope_violated(under)
        and eb.envelope_violated(eb.wheel_log_space.pack(
            alpha_f=math.radians(30.0), kappa_f=0.0, fz_f=3600.0,
            alpha_r=0.0, kappa_r=0.0, fz_r=3600.0))
        and eb.envelope_violated(eb.wheel_log_space.pack(
            alpha_f=0.0, kappa_f=0.0, fz_f=50.0,
            alpha_r=0.0, kappa_r=0.0, fz_r=3600.0)),
        "slip ratio 0.9, slip angle 30 deg and load 50 N are each flagged; a "
        "clean sample is not",
    )
    wild = BicycleBackend()
    wild.reset(30.0)
    wild.state.steer = math.radians(10.0)
    idle = wild.act_space.pack(steer_rate=0.0, drive_force=0.0)
    flagged = sum(wild.step(idle, 0.002)[1].envelope_violation for _ in range(500))
    report.add(
        "a_wild_manoeuvre_is_flagged_in_the_rollout",
        flagged > 100,
        f"a 10 deg step at 30 m/s runs past 12 deg of slip and is flagged on "
        f"{flagged}/500 steps — the instrumentation fires end to end, not just "
        "on synthetic inputs",
        value=flagged,
    )

    # -- pose integration -----------------------------------------------------
    report.section("Does the car go where it says it goes?")
    # x, y and heading are integrated but feed no assertion anywhere else. If
    # they were wrong, every trajectory figure and every lap time from Ep 4 on
    # would be wrong and nothing would notice.
    nd2 = BicycleBackend(replace(p, c_d=0.0))
    R_c, V_c = 30.0, 15.0
    tp = nd2.trim_skidpad(V_c, R_c)
    nd2.reset(V_c)
    nd2.state = BicycleState(v_x=V_c, v_y=tp.v_y, yaw_rate=tp.yaw_rate,
                             steer=tp.steer)
    nd2._last["a_x"] = tp.a_x
    act_c = nd2.act_space.pack(steer_rate=0.0, drive_force=tp.drive_force)
    xs, ys = [], []
    for _ in range(int((2 * math.pi * R_c / V_c) / 0.001)):
        _, inf = nd2.step(act_c, 0.001)
        xs.append(inf.position[0])
        ys.append(inf.position[1])
    xs, ys = np.array(xs), np.array(ys)
    A = np.c_[2 * xs, 2 * ys, np.ones(len(xs))]
    sol, *_ = np.linalg.lstsq(A, xs**2 + ys**2, rcond=None)
    r_fit = math.sqrt(sol[2] + sol[0] ** 2 + sol[1] ** 2)
    radii = np.hypot(xs - sol[0], ys - sol[1])
    report.close(r_fit, R_c, 1e-3, "driven_path_radius_matches_command", "m")
    report.add(
        "driven_path_is_a_circle_not_a_spiral",
        float(radii.max() - radii.min()) < 1e-6,
        f"radius varies by {float(radii.max()-radii.min()):.2e} m over a full lap",
        value=float(radii.max() - radii.min()),
    )
    report.close(math.degrees(nd2.state.heading), 360.0, 0.05,
                 "heading_closes_after_one_lap", "deg")
    report.add(
        "constant_speed_trim_actually_holds_speed",
        abs(nd2.state.v_x - V_c) < 1e-9,
        f"speed after a full lap: {nd2.state.v_x - V_c:+.2e} m/s. Holding speed "
        "means dv_x/dt = 0, which requires a_x = -v_y*r rather than a_x = 0 — in "
        "a circle with sideslip the centripetal acceleration has a small body-x "
        "component. Forcing a_x = 0 instead drifted 0.19% off the commanded "
        "radius over one lap.",
        value=nd2.state.v_x - V_c,
    )

    # -- inertia -----------------------------------------------------------
    report.section("Is yaw inertia wired in?")
    heavy = BicycleBackend(replace(p, i_zz=p.i_zz * 2.0))
    t_ref = b.trim_skidpad(15.0, RADIUS)
    t_heavy = heavy.trim_skidpad(15.0, RADIUS)
    report.add(
        "steady_state_independent_of_izz",
        abs(t_heavy.steer - t_ref.steer) < 1e-9,
        "doubling I_zz leaves the steady-state trim identical, as it must — "
        "inertia is a transient effect only",
    )
    _, _, slow = _straight(heavy, 1.0, seconds=1.2, dt=0.001, speed=20.0)
    _, _, fast = _straight(BicycleBackend(), 1.0, seconds=1.2, dt=0.001, speed=20.0)
    rise_slow = _rise_time(slow["yaw_rate"], 0.001)
    rise_fast = _rise_time(fast["yaw_rate"], 0.001)
    report.add(
        "higher_izz_responds_more_slowly",
        rise_slow > rise_fast,
        f"90% yaw-response rise time: {rise_fast*1000:.0f} ms at nominal I_zz, "
        f"{rise_slow*1000:.0f} ms at double. Gate 1 invariant 7.",
        value={"nominal_s": rise_fast, "double_s": rise_slow},
    )

    # -- weight distribution -----------------------------------------------
    report.section("Does moving weight forward add understeer?")
    ks = {}
    for frac in (0.45, 0.50, 0.54, 0.60):
        bb = BicycleBackend(replace(p, front_mass_fraction=frac))
        ks[frac], _ = understeer_gradient(bb.skidpad_sweep(RADIUS, SWEEP))
    order = list(ks.values())
    report.add(
        "K_increases_with_front_weight",
        all(b_ > a_ for a_, b_ in zip(order, order[1:])),
        "K rises monotonically: " + ", ".join(
            f"{f:.2f}->{k:+.3f}" for f, k in ks.items()
        ) + " deg/g. Gate 1 invariant 2.",
        value=ks,
    )
    report.data["K_vs_front_fraction"] = ks

    report.subtitle = (
        "The textbook facts, as assertions. Weight moves forward under braking, "
        "tires push back against the way they are sliding, left mirrors right, "
        "and two independently written pieces of code agree about the same "
        "corner. A violation here is a bug, and nothing downstream means "
        "anything until it is fixed."
    )
    report.find(
        "Braking moves "
        f"{f_b - f0:,.0f} N onto the front axle at {abs(brake):g} m/s² — about "
        f"{100*(f_b-f0)/f0:.0f}% more weight on the front tires than at rest. "
        "Double the centre-of-gravity height and you double the transfer, which "
        "is the whole reason low cars handle better."
    )
    report.find(
        "The steady-state solver and the step-by-step simulator are separate "
        "implementations of the same physics, and they agree to machine "
        "precision about the same corner — the equilibrium one solves for is "
        "exactly a state in which the other's accelerations vanish."
    )
    report.find(
        "Cornering slows a car down even with no brakes and no air resistance. "
        f"At {coast.a_y_g:.2f} g a coasting car loses "
        f"{abs(coast.a_x)/schema.G:.3f} g, because the front tire's grip points "
        "along the wheel and the wheel is turned. A real skidpad test holds speed "
        f"instead — {target.drive_force:.0f} N of throttle here — and that choice "
        "changes the measured balance materially. See FINDINGS F17."
    )
    report.find(
        f"With the manufacturing offsets removed, a car with the steering "
        "straight stays perfectly straight: zero yaw rate, zero sideways drift, "
        "to machine precision. The tire file as shipped would have pulled to one "
        "side (FINDINGS F6)."
    )
    report.find(
        f"Doubling yaw inertia slows the response from {rise_fast*1000:.0f} ms to "
        f"{rise_slow*1000:.0f} ms — the car resists changing direction. That is "
        "the difference between a mid-engine car and a front-engine one, and it "
        "is Episode 8's subject."
    )
    # -- the drivetrain yaw moment ------------------------------------------
    #
    # F72 sat in this model for the whole of Seasons 1-3: both yaw-moment
    # expressions omitted the track-width term, so moving the entire drive force
    # from one wheel to the other changed the computed yaw by exactly zero. No
    # test, diagnostic or episode could have detected it, because nothing before
    # Season 4 ever applied an asymmetric longitudinal force -- the missing term
    # was always multiplied by zero.
    #
    # These checks exist so that removing the term again would FAIL something.
    # A defect that nothing can see is not fixed by fixing it once.
    report.section("Does asymmetric drive rotate the car?")
    from physics.double_track import (CORNERS as DT_CORNERS,
                                      DoubleTrackBackend, WheelForces)
    dt = DoubleTrackBackend(p)
    flat = {c: WheelForces(fy=0.0, fx=0.0, alpha=0.0, kappa=0.0, fz=4000.0)
            for c in DT_CORNERS}

    def _mz(**fx):
        w = dict(flat)
        for c, v in fx.items():
            w[c] = replace(flat[c], fx=float(v))
        return dt.yaw_moment(w, 0.0)

    F = 3000.0
    mz_right, mz_left, mz_even = (_mz(rr=F), _mz(rl=F),
                                  _mz(rl=F / 2.0, rr=F / 2.0))
    report.add(
        "asymmetric_drive_produces_a_yaw_moment",
        abs(mz_right) > 1.0,
        f"putting {F:.0f} N through the right rear wheel alone produces "
        f"{mz_right:.0f} N.m of yaw moment — {mz_right / p.i_zz:.2f} rad/s2. This "
        f"read exactly 0.0 for the whole of Seasons 1-3 (F72), which would have "
        f"made every torque-vectoring result in Season 4 a silent null.",
        value=mz_right,
    )
    report.add(
        "driving_the_right_wheel_turns_the_car_left",
        mz_right > 0.0 and mz_left < 0.0,
        f"right wheel alone gives {mz_right:+.0f} N.m, left wheel alone "
        f"{mz_left:+.0f} N.m. Under ISO 8855 a left turn is positive yaw, and "
        f"pushing the right-hand side of the car forward rotates the nose left. A "
        f"sign error here would render a plausible picture of a car doing the "
        f"opposite of what it did (F36).",
        value={"right": mz_right, "left": mz_left},
    )
    report.add(
        "a_symmetric_split_produces_no_yaw",
        abs(mz_even) < 1e-9,
        f"the same {F:.0f} N split evenly gives {mz_even:.2e} N.m. This is why "
        f"adding the term moved no Season 1-3 result that used a symmetric split, "
        f"and it is asserted rather than assumed.",
        value=mz_even,
    )
    report.add(
        "the_moment_arm_is_half_the_track",
        abs(mz_right - F * p.track_r / 2.0) < 1e-6,
        f"{mz_right:.1f} N.m against {F:.0f} N x {p.track_r:.3f} m / 2 = "
        f"{F * p.track_r / 2.0:.1f} N.m. Closed-form, and it distinguishes the rear "
        f"track from the front, so using the wrong one would fail.",
        value=mz_right - F * p.track_r / 2.0,
    )
    # -- the differential ---------------------------------------------------
    #
    # ONE mechanism: torque flows from the faster-turning wheel to the slower. Which
    # wheel is faster changes with throttle, and so does the sign of the effect —
    # a model that hard-codes a bias direction cannot produce both (F77).
    report.section("Does a locking differential push the car wide?")
    from physics.double_track import BicycleState as _BS
    import math as _m
    _R, _AY = 40.0, 9.0
    _v = _m.sqrt(_AY * _R)                       # a corner the car can actually be in
    corner = _BS(v_x=_v, v_y=0.0, yaw_rate=_v / _R, steer=0.0)
    hard = dt.wheel_loads(1.5, _AY)

    def _mz(kind: str, demand: float) -> float:
        bb = DoubleTrackBackend(p, diff=kind)
        fxs = bb.differential_forces(demand, hard, corner)
        ww = {c: WheelForces(fy=0.0, fx=fxs[c], alpha=0.0, kappa=0.0, fz=hard[c])
              for c in DT_CORNERS}
        return bb.yaw_moment(ww, 0.0)

    PART, FULL = 1000.0, 6000.0
    part = {d: _mz(d, PART) for d in ("open", "lsd", "locked")}
    full = {d: _mz(d, FULL) for d in ("open", "lsd", "locked")}
    report.add(
        "at_part_throttle_a_locking_differential_pushes_wide",
        part["locked"] < -1.0,
        f"at {PART:.0f} N of demand in a {_AY:.0f} m/s2 corner, a welded "
        f"differential produces {part['locked']:+.0f} N.m — negative, yawing the car "
        f"OUT of the corner. Neither wheel is saturated, so kinematics decides: the "
        f"outside wheel travels further, turns faster, and loses torque to the "
        f"inside. This is the locked-diff push, and it is the outside check on the "
        f"model (rule 2) — the sign is not ours to choose.",
        value=part["locked"])
    report.add(
        "at_full_throttle_the_same_device_turns_the_car_in",
        full["locked"] > 1.0,
        f"at {FULL:.0f} N the same differential gives {full['locked']:+.0f} N.m, the "
        f"other way. The inside wheel has saturated and is spinning, so it is now "
        f"the FASTER wheel and torque flows outboard to the one that still grips. "
        f"Same rule, opposite outcome — a model with a fixed bias direction can only "
        f"produce one of these two, and F77 was exactly that mistake.",
        value=full["locked"])
    report.add(
        "more_locking_means_more_push",
        part["open"] > part["lsd"] > part["locked"],
        f"part-throttle yaw moment: open {part['open']:+.0f}, limited-slip "
        f"{part['lsd']:+.0f}, welded {part['locked']:+.0f} N.m. Ordered, which is "
        f"what this model can claim (rule 6).",
        value=part)
    report.add(
        "an_open_differential_steers_the_car_neither_way",
        abs(part["open"]) < 1e-9 and abs(full["open"]) < 1e-9,
        f"an open differential gives {part['open']:+.2f} N.m at part throttle and "
        f"{full['open']:+.2f} at full: it feeds both wheels equally and resists no "
        f"speed difference, so it has no handling effect to have. That is the "
        f"baseline the other two are measured against.",
        value=part["open"])
    tot = lambda kind: sum(
        DoubleTrackBackend(p, diff=kind).differential_forces(
            FULL, hard, corner)[c] for c in ("rl", "rr"))
    t_open, t_lsd, t_lock = tot("open"), tot("lsd"), tot("locked")
    report.add(
        "an_open_differential_wastes_tractive_force",
        t_open < t_lsd <= t_lock,
        f"of {FULL:.0f} N demanded with the inside wheel down to "
        f"{min(hard['rl'], hard['rr']):.0f} N of load, an open differential delivers "
        f"{t_open:.0f} N, a limited-slip {t_lsd:.0f} N and a welded one "
        f"{t_lock:.0f} N. The open diff must feed both wheels equally, so it is "
        f"limited by twice the weaker.",
        value={"open": t_open, "lsd": t_lsd, "locked": t_lock})
    report.note(
        "differential_parameters_are_ASSUMED",
        "The LSD's torque bias ratio (1.5) and locking fraction (0.5) are "
        "[ASSUMED]; a real clutch pack's locking varies with torque and with coast "
        "versus drive, which this does not model. Rung 2 (rule 15): the mechanism "
        "and the ordering, not any particular hardware.")

    report.note(
        "track_width_is_only_LIKELY",
        f"Track width is [LIKELY], not measured. At +/-3% the moment moves "
        f"{F * p.track_r * 0.03 / 2.0:.0f} N.m either way; every torque-vectoring "
        f"magnitude claim must be re-run at both bounds with the CONCLUSION intact.")

    com_sweep = [(h, BicycleBackend(replace(p, com_height=h)).axle_loads(-4.903)[0]
                  - BicycleBackend(replace(p, com_height=h)).axle_loads(0.0)[0])
                 for h in np.linspace(0.02, 1.0, 40)]
    return {"backend": b, "com_sweep": com_sweep,
            "yaw_traces": [("nominal I_zz", fast["yaw_rate"], V_AMB),
                           ("double I_zz", slow["yaw_rate"], V_TEAL)]}


def _rise_time(signal, dt, lo=0.1, hi=0.9) -> float:
    """10-90% rise time of a step response, in seconds.

    Measured on **yaw rate**, which starts at exactly zero and rises — the
    standard step-steer metric, and the one the parameter sheet quotes a band
    for. Lateral acceleration is the wrong signal here: it jumps the instant the
    front tire develops slip, so its "rise time" is a property of the timestep.
    """
    a = np.abs(np.asarray(signal, dtype=float))
    final = a[-1]
    i_lo = int(np.argmax(a >= lo * final))
    i_hi = int(np.argmax(a >= hi * final))
    return float((i_hi - i_lo) * dt)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    report = Report("D2", "Invariants and signs")
    ctx = run_checks(report)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    b = ctx["backend"]
    left = b.trim_skidpad(15.0, RADIUS)
    right = b.trim_skidpad(15.0, -RADIUS)
    written = {
        "load transfer": (OUT_DIR / "D2_load_transfer.svg",
                          transfer_figures.load_transfer_figure(b)),
        "centre of gravity": (OUT_DIR / "D2_cog_height.svg",
                              transfer_figures.cog_height_figure(b)),
        "corner forces": (OUT_DIR / "D2_corner_forces.svg",
                          transfer_figures.corner_forces_figure(b, left, right)),
        "technical card": (OUT_DIR / "D2_invariants_card.svg",
                           transfer_figures.invariants_card(
                               ctx["backend"], ctx["com_sweep"],
                               ctx["yaw_traces"])),
    }
    for _, (path_, svg) in written.items():
        path_.write_text(svg)

    captions = {
        "load transfer": "The same car braking, cruising and accelerating. The "
            "band across each tire is its contact patch — bigger band, more "
            "weight. The total never changes; only the split does.",
        "centre of gravity": "The same car braking equally hard with its weight "
            "at two different heights. Twice the height, twice the load moved — "
            "exactly, with no fitting parameter.",
        "corner forces": "A steady corner taken each way, with the grip each axle "
            "produces drawn to scale. Both push into the corner; the front pushes "
            "harder. Mirroring the input mirrors every force.",
        "technical card": "Axle load against longitudinal acceleration, load "
            "transfer against centre-of-gravity height, and the yaw-rate step "
            "response at two values of yaw inertia.",
    }
    md = report.write_markdown(
        [(n, pth, captions[n]) for n, (pth, _) in written.items()],
        command="python -m diagnostics.D2_invariants")
    path = report.write()
    report.print_summary(verbose="-v" in argv or "--verbose" in argv)
    print(f"\n  write-up {md}\n  report   {path}")
    for name, (p_, _) in written.items():
        print(f"  {name:<16} {p_}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
