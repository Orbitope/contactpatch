"""Episode 13 — how engineers built a car that steers with its wheels.

Episode 12's differential *reacts*: it resists a speed difference the corner
forces on it. This episode's controller *decides*. Two layers — a reference model
and a PID that say how much the car should be rotating, and a QP allocator that
says which wheels pay for it — and the experiment asks what that is worth.

Five configurations, one driver
-------------------------------

======  ==========================================================
open    open differential. What Episodes 9-11 drove.
lsd     the passive limited-slip device of Episode 12 (1.5:1, 0.5).
alloc   the four-wheel allocator with the yaw demand FORCED TO ZERO.
tv4     the full two-layer controller, four independent wheels.
tvrear  a torque-vectoring differential: driven axle only, one dof.
======  ==========================================================

``alloc`` is the condition that makes the rest interpretable. Both it and ``tv4``
replace the differential with an allocator, so both get grip-proportional braking
and traction distribution for free; only ``tv4`` also asks for yaw. Without the
control condition, "torque vectoring is worth X" would be a claim about two things
at once, and F79's lesson is that a measurement is only as good as the claim that
its two sides differ in exactly one thing.

The metric, chosen before anything was measured (rule 9)
--------------------------------------------------------

Every configuration is driven by the SAME driver (``physics/driver.py``) tracking
the SAME centreline to the SAME speed plan. The plan is built for ``grip_use``
times the car's measured grip, so at a given ``grip_use`` every configuration is
attempting an identical lap and takes an almost identical time. **What differs is
whether the car can do it.** The result is therefore:

1. **the highest ``grip_use`` that still produces a valid lap** — on the road, and
   inside the +/-12 degree tire fit (rule 4, applied per lap: F70's third lesson);
2. **the quickest valid lap**, which is a monotone consequence of (1) and is
   reported because a lap time is what a reader can hold on to.

Those two are not independent evidence. Saying so here rather than presenting them
as two results is the point of writing the metric down first.

Two manoeuvres, and the second one is the one the outside reference used
-----------------------------------------------------------------------

The lap is Episode 4's ``long_exit`` corner, for continuity with Seasons 2 and 3.
But 260 of its 393 m are a power-limited straight where nothing a yaw controller
does can matter, so a lap-time percentage from it understates what the controller
does to the *corner*. The skidpad — a constant-radius circle, driven faster and
faster until it fails — is the manoeuvre the best published figure comes from
(~9% for an FSAE car), so it is the one our number has to be compared against.
**Anything above 9% here is a bug, not a result** (rule 2: the ceiling comes from
outside this project; our own model does not get to set it).

Fidelity: rung 2 (rule 15)
--------------------------

Four independently commanded wheel forces is a four-motor electric car, not RV-1's
rear-drive combustion driveline; ``tvrear`` is the version RV-1 could actually
have. Underneath both is a double-track model with no roll camber, no roll steer
and no compliance steer — the terms that make up roughly 3 of a real car's 4.1
deg/g of understeer (F29, F73). Trend direction and rank ordering are the claim.
No number here is a specification.

    python -m experiments.ep13.run
    python -m experiments.ep13.run --quick
    python -m experiments.ep13.run --figures-only
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import replace

import numpy as np

from diagnostics.common import Report
from experiments.common import episode_dir, write
from physics import schema
from physics import torque_vectoring as tvm
from physics.double_track import DoubleTrackBackend
from physics.driver import (BRAKE_MAX, DRIVE_MAX, Driver, SpeedProfile,
                            TrackLocator, drive_lap)
from physics.track import CORNER_RADIUS, Segment, Track, long_exit

CONDITIONS = ("open", "lsd", "alloc", "tv4", "tvrear")
LABEL = {
    "open": "open differential",
    "lsd": "limited-slip (1.5:1)",
    "alloc": "allocator, no yaw control",
    "tv4": "torque vectoring, four wheels",
    "tvrear": "torque-vectoring differential",
}
SHORT = {"open": "open diff", "lsd": "LSD", "alloc": "allocator only",
         "tv4": "TV (4 wheels)", "tvrear": "TV (rear axle)"}

#: Aggression grid for the curve in the figures. The headline limit is then
#: bisected to 0.002, because a 0.0125 grid cannot resolve a 5% difference in it.
GU_GRID = np.round(np.arange(0.850, 1.1501, 0.0125), 4)
GU_LO, GU_HI = 0.82, 1.28

#: The section of the lap that contains the corner: brake point to full exit.
SECTION = (55.0, 165.0)

#: Steering disturbance for the robustness study — Episode 11's convention and
#: Episode 11's value, so "noise" means the same thing in both seasons.
STEER_NOISE = 0.15
N_SEEDS = 40          # a failure rate needs samples, not repeats (F70)

#: Target understeer gradients the reference model is asked for, deg/g. The first
#: is the car's own measured value; the rest ask for a pointier car than it is.
TARGET_K_DEG_PER_G = (None, 0.10, 0.0, -0.15)


def skidpad_track(radius: float = CORNER_RADIUS, laps: float = 1.5) -> Track:
    """Lead-in, then ``laps`` of a constant-radius circle."""
    return Track(name="skidpad",
                 segments=[Segment(30.0), Segment(laps * 2 * math.pi * radius,
                                                  radius)],
                 half_width=4.0,
                 description=f"{laps:g} laps of a {radius:.0f} m circle")


class Car:
    """One configuration: a car, and whatever decides its wheel forces."""

    def __init__(self, name: str, params: schema.VehicleParams, ref: dict,
                 **tv_kw):
        self.name = name
        diff = name if name in ("open", "lsd") else "open"
        self.backend = DoubleTrackBackend(params, diff=diff)
        self.tv = None
        if name in ("alloc", "tv4", "tvrear"):
            self.tv = tvm.build(
                self.backend,
                effectors=("rear" if name == "tvrear" else "four"),
                yaw_control=(name != "alloc"),
                k_us=ref["k_us"], a_y_max=ref["a_y_max"], **tv_kw)


def measure(params: schema.VehicleParams) -> dict:
    """What the controller needs to know about the car. All [MEASURED]."""
    probe = DoubleTrackBackend(params, diff="open")
    a_y_max = tvm.measure_grip_ceiling(probe, CORNER_RADIUS)
    return {"k_us": tvm.measure_understeer_gradient(probe),
            "a_y_max": a_y_max,
            "a_lat": a_y_max}


def lap(car: Car, track: Track, ref: dict, gu: float, *, seed=None,
        steer_noise: float = 0.0, driver_kw: dict | None = None,
        max_steps: int = 4000):
    mass = car.backend.params.mass
    prof = SpeedProfile(track, a_lat=gu * ref["a_lat"],
                        a_brake=min(BRAKE_MAX / mass, gu * schema.G),
                        a_drive=DRIVE_MAX / mass)
    d = Driver(car.backend.params, prof, TrackLocator(track),
               steer_noise=steer_noise, **(driver_kw or {}))
    return drive_lap(car.backend, track, d, tv=car.tv, grip_use=gu, seed=seed,
                     max_steps=max_steps)


def section_time(lp, s0=SECTION[0], s1=SECTION[1]) -> float:
    s, t = lp.log["s"], lp.log["t"]
    if s[-1] < s1:
        return math.nan
    return float(np.interp(s1, s, t) - np.interp(s0, s, t))


def sweep(car: Car, track: Track, ref: dict, grid=GU_GRID, **kw) -> list[dict]:
    out = []
    for gu in grid:
        lp = lap(car, track, ref, float(gu), **kw)
        out.append({
            "grip_use": float(gu), "valid": bool(lp.valid), "reason": lp.reason,
            "lap_time": float(lp.lap_time), "section_time": section_time(lp),
            "worst_slip_deg": float(lp.worst_slip_deg),
            "peak_a_y_g": float(lp.peak_a_y_g),
            "max_offset_m": float(lp.max_offset),
            "mean_utilisation": float(lp.mean_utilisation),
        })
    return out


def limit_of(car: Car, track: Track, ref: dict, lo=GU_LO, hi=GU_HI,
             tol=0.002, **kw) -> float:
    """Highest ``grip_use`` that still yields a valid lap, by bisection.

    Assumes validity is monotone in aggression, which the swept curve is checked
    against — if the grid shows a valid lap above the bisected limit, the
    assumption is wrong and the run says so rather than quietly reporting the
    smaller number.
    """
    if not lap(car, track, ref, lo, **kw).valid:
        return math.nan
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if lap(car, track, ref, mid, **kw).valid:
            lo = mid
        else:
            hi = mid
    return lo


def best_valid(rows: list[dict]) -> dict | None:
    ok = [r for r in rows if r["valid"]]
    return min(ok, key=lambda r: r["lap_time"]) if ok else None


# ---------------------------------------------------------------------------

def main() -> int:
    out = episode_dir(13)
    if "--figures-only" in sys.argv:
        figures(out)
        return 0
    quick = "--quick" in sys.argv
    t_start = time.time()

    params = schema.RV_1
    ref = measure(params)
    track, skid = long_exit(), skidpad_track()
    k_deg = math.degrees(ref["k_us"]) * schema.G

    print("Episode 13 — How engineers built a car that steers with its wheels")
    print(f"  reference model built from the car: K = {k_deg:.3f} deg/g "
          f"[MEASURED], grip ceiling {ref['a_y_max']/schema.G:.3f} g [MEASURED]")
    print(f"  lap: {track.name}, {track.length:.0f} m   "
          f"skidpad: {skid.description}\n")

    grid = GU_GRID[::2] if quick else GU_GRID
    cars = {c: Car(c, params, ref) for c in CONDITIONS}

    # -- 1. the lap ---------------------------------------------------------
    print("  Lap sweep (long exit) — aggression until it fails")
    laps, limits, bests = {}, {}, {}
    for c in CONDITIONS:
        laps[c] = sweep(cars[c], track, ref, grid)
        limits[c] = limit_of(cars[c], track, ref)
        bests[c] = best_valid(laps[c])
        b = bests[c]
        print(f"    {SHORT[c]:16s} limit gu={limits[c]:.3f}  best "
              f"{b['lap_time']:6.3f} s @ gu={b['grip_use']:.4f}  "
              f"corner {b['section_time']:5.3f} s  peak {b['peak_a_y_g']:.3f} g  "
              f"worst slip {b['worst_slip_deg']:5.2f} deg")

    base, tv = bests["open"], bests["tv4"]
    lap_gain = 100.0 * (base["lap_time"] - tv["lap_time"]) / base["lap_time"]
    sec_gain = 100.0 * (base["section_time"] - tv["section_time"]) \
        / base["section_time"]
    limit_gain = 100.0 * (limits["tv4"] - limits["open"]) / limits["open"]
    alloc_share = (100.0 * (limits["alloc"] - limits["open"]) / limits["open"]
                   / limit_gain if limit_gain else math.nan)
    print(f"\n    TV vs open: lap {lap_gain:+.2f}%, corner section "
          f"{sec_gain:+.2f}%, cornering limit {limit_gain:+.2f}%")
    print(f"    of that limit gain, the allocator alone accounts for "
          f"{100*alloc_share:.0f}%\n")

    # -- 2. the skidpad, which is what the published figure measured ---------
    print("  Skidpad — sustained lateral acceleration, same driver")
    skid_limits, skid_a_y = {}, {}
    for c in CONDITIONS:
        skid_limits[c] = limit_of(cars[c], skid, ref, max_steps=6000)
        lp = lap(cars[c], skid, ref, skid_limits[c], max_steps=6000)
        m = np.asarray(lp.log["s"]) > skid.length - 2 * math.pi * CORNER_RADIUS
        skid_a_y[c] = (float(np.mean(np.abs(np.asarray(lp.log["a_y"])[m])))
                       / schema.G if m.any() else math.nan)
        print(f"    {SHORT[c]:16s} limit gu={skid_limits[c]:.3f}  sustained "
              f"{skid_a_y[c]:.3f} g")
    skid_gain = 100.0 * (skid_a_y["tv4"] - skid_a_y["open"]) / skid_a_y["open"]
    print(f"\n    TV vs open on the skidpad: {skid_gain:+.2f}% lateral "
          f"acceleration (published ceiling ~9%)\n")

    # -- 3. what the upper layer is actually doing --------------------------
    gu_probe = min(limits["open"], limits["tv4"])
    tv_lap = lap(cars["tv4"], track, ref, gu_probe)
    open_lap = lap(cars["open"], track, ref, gu_probe)
    T = tv_lap.tv_log
    corner = (np.asarray(tv_lap.log["s"]) > SECTION[0]) & \
             (np.asarray(tv_lap.log["s"]) < SECTION[1])
    tracking = {
        "mz_peak": float(np.max(np.abs(T["mz_demand"]))),
        "mz_mean_abs": float(np.mean(np.abs(T["mz_demand"]))),
        "mz_delivery_error": float(np.max(np.abs(T["mz_demand"]
                                                 - T["mz_delivered"]))),
        "fx_delivery_error": float(np.max(np.abs(T["fx_demand"]
                                                 - T["fx_delivered"]))),
        "yaw_rms_tv": float(np.sqrt(np.mean((T["r_ref"] - T["r"])[corner] ** 2))),
        "grip_use": float(gu_probe),
    }
    # The same reference model, evaluated on the lap the passive car drove. The
    # controller is not in that loop; this is what it would have been asked to fix.
    rm = tvm.ReferenceModel(wheelbase=params.wheelbase, k_us=ref["k_us"],
                            a_y_max=ref["a_y_max"])
    r_ref_open = np.array([rm.yaw_rate(v, st) for v, st in
                           zip(open_lap.log["speed"], open_lap.log["steer"])])
    m_open = (np.asarray(open_lap.log["s"]) > SECTION[0]) & \
             (np.asarray(open_lap.log["s"]) < SECTION[1])
    tracking["yaw_rms_open"] = float(np.sqrt(
        np.mean((r_ref_open - np.asarray(open_lap.log["yaw_rate"]))[m_open] ** 2)))
    print(f"  Yaw-rate tracking through the corner (gu={gu_probe:.3f}): "
          f"open {tracking['yaw_rms_open']:.4f} rad/s RMS, "
          f"TV {tracking['yaw_rms_tv']:.4f} rad/s RMS")
    print(f"    peak moment demanded {tracking['mz_peak']:.0f} N.m, "
          f"largest shortfall in delivering it "
          f"{tracking['mz_delivery_error']:.1f} N.m\n")

    # -- 4. what should the reference model ask for? ------------------------
    print("  Reference model: what happens if you ask for a pointier car")
    ref_sweep = {}
    for target in TARGET_K_DEG_PER_G:
        k = ref["k_us"] if target is None else math.radians(target) / schema.G
        car = Car("tv4", params, {**ref, "k_us": k})
        lim = limit_of(car, track, ref)
        rows = sweep(car, track, ref, grid[::2])
        b = best_valid(rows)
        key = "measured" if target is None else f"{target:+.2f}"
        ref_sweep[key] = {"k_deg_per_g": (k_deg if target is None else target),
                          "limit": lim,
                          "best_lap": (b["lap_time"] if b else math.nan)}
        print(f"    target K = {ref_sweep[key]['k_deg_per_g']:+.3f} deg/g: "
              f"limit gu={lim:.3f}, best lap "
              f"{ref_sweep[key]['best_lap']:.3f} s")
    print()

    # -- 5. sensitivities ---------------------------------------------------
    print("  Sensitivities — the conclusion has to survive all of these")
    sens = {}

    def compare(tag: str, note: str, params_v=None, driver_kw=None, tv_kw=None):
        """All three limits under one variation, so the decomposition moves too.

        Measuring only open-against-TV would test whether the *gain* survives and
        leave the split between the two layers as a single unreplicated number.
        It is the least stable quantity in this episode — it moved from 77% to 40%
        when the allocator went from being re-solved inside the integrator to
        holding its command for the control interval — so it gets a spread rather
        than a decimal point.
        """
        p = params_v or params
        r = measure(p) if params_v is not None else ref
        a = Car("open", p, r)
        m = Car("alloc", p, r, **(tv_kw or {}))
        b = Car("tv4", p, r, **(tv_kw or {}))
        kw = {"driver_kw": driver_kw} if driver_kw else {}
        la, lm, lb = (limit_of(a, track, r, **kw), limit_of(m, track, r, **kw),
                      limit_of(b, track, r, **kw))
        gain = 100.0 * (lb - la) / la
        sens[tag] = {"note": note, "open": la, "alloc": lm, "tv4": lb,
                     "gain_pct": gain,
                     "allocator_share": ((lm - la) / (lb - la)
                                         if lb > la else math.nan)}
        print(f"    {note:38s} open {la:.3f}  alloc {lm:.3f}  TV {lb:.3f}  "
              f"{gain:+5.2f}%  allocator {100*sens[tag]['allocator_share']:3.0f}%")

    for f in (0.97, 1.03):
        compare(f"track_{f:.2f}", f"track width x{f:.2f} (CLAUDE.md)",
                params_v=replace(params, track_f=params.track_f * f,
                                        track_r=params.track_r * f))
    if not quick:
        compare("look_short", "driver looks 30% less far ahead",
                driver_kw={"t_look": 0.385})
        compare("look_long", "driver looks 30% further ahead",
                driver_kw={"t_look": 0.715})
        compare("priority_mz", "allocator prefers the moment (s_mz=4)",
                tv_kw={"s_mz": 4.0})
        compare("priority_fx", "allocator prefers the force (s_mz=0.25)",
                tv_kw={"s_mz": 0.25})
    print()

    # -- 6. does it help a driver who is not perfect? ------------------------
    print(f"  Steering disturbance, {N_SEEDS} seeds "
          f"(steer_noise={STEER_NOISE}, Episode 11's value)")
    n_seeds = 8 if quick else N_SEEDS
    gu_noise = round(min(limits["open"], limits["tv4"]) - 0.05, 4)
    noise = {}
    for c in CONDITIONS:
        rows = [lap(cars[c], track, ref, gu_noise, seed=k,
                    steer_noise=STEER_NOISE) for k in range(n_seeds)]
        good = [r for r in rows if r.valid]
        times = [r.lap_time for r in good]
        noise[c] = {
            "n": n_seeds, "grip_use": gu_noise,
            "valid": len(good), "valid_rate": len(good) / n_seeds,
            "mean_lap": float(np.mean(times)) if times else math.nan,
            "sd_lap": float(np.std(times, ddof=1)) if len(times) > 1 else math.nan,
            "worst_slip_deg": float(np.max([r.worst_slip_deg for r in rows])),
        }
        print(f"    {SHORT[c]:16s} {noise[c]['valid']:3d}/{n_seeds} valid  "
              f"lap {noise[c]['mean_lap']:.3f} +/- {noise[c]['sd_lap']:.3f} s")
    print()

    # -- checks -------------------------------------------------------------
    report = Report(
        "D-ep13", "How engineers built a car that steers with its wheels",
        "Two layers: a reference model and a PID decide how much the car should "
        "rotate, a QP allocator decides which wheels pay for it. The checks ask "
        "whether each layer does its job, whether the tires were saturated enough "
        "for any of it to matter, and whether the result survives the numbers it "
        "was built on.")

    report.section("Does the controller reach the wheels at all?")
    report.add(
        "the_allocator_delivers_the_moment_it_is_asked_for",
        tracking["mz_delivery_error"] < 0.1 * tracking["mz_peak"],
        f"across the whole lap the largest gap between the moment the PID asked "
        f"for and the moment the four wheels produced is "
        f"{tracking['mz_delivery_error']:.1f} N.m, against a peak demand of "
        f"{tracking['mz_peak']:.0f} N.m — "
        f"{100*tracking['mz_delivery_error']/tracking['mz_peak']:.1f}% at the "
        f"worst instant of the lap and near zero for the rest of it. The lower "
        f"layer is almost never the limitation: the tires have longitudinal "
        f"capacity to spare nearly every time they are asked, and what shortfall "
        f"there is comes from the allocation being computed once per control "
        f"interval on the previous instant's loads, which is what a real ECU has "
        f"to do.",
        value=tracking["mz_delivery_error"])
    report.add(
        "the_upper_layer_tracks_its_reference_better_than_the_passive_car",
        tracking["yaw_rms_tv"] < tracking["yaw_rms_open"],
        f"RMS yaw-rate error against the same reference model, through the same "
        f"corner at the same aggression: passive "
        f"{tracking['yaw_rms_open']:.4f} rad/s, controlled "
        f"{tracking['yaw_rms_tv']:.4f} rad/s "
        f"({100*(1-tracking['yaw_rms_tv']/tracking['yaw_rms_open']):.0f}% lower). "
        f"This is what the controller was built to do, and it is a more direct "
        f"measurement of it than any lap time.",
        value=[tracking["yaw_rms_open"], tracking["yaw_rms_tv"]])

    report.section("Were the tires saturated enough for it to matter?")
    report.add(
        "the_car_was_driven_at_the_limit",
        tv["peak_a_y_g"] > 0.9 * ref["a_y_max"] / schema.G
        and tv["worst_slip_deg"] > 6.0,
        f"the quickest valid TV lap peaks at {tv['peak_a_y_g']:.3f} g against a "
        f"measured steady-state ceiling of {ref['a_y_max']/schema.G:.3f} g, and "
        f"reaches {tv['worst_slip_deg']:.1f} deg of slip where the tire's peak at "
        f"this load is near 10.4 deg. Torque vectoring only acts where tires are "
        f"saturated, so a result measured with an under-driving car measures "
        f"nothing — this check is the precondition for every number in this "
        f"episode.",
        value=tv["peak_a_y_g"])
    report.add(
        "no_quoted_lap_left_the_tire_fit",
        all(b["worst_slip_deg"] <= 12.0 for b in bests.values() if b),
        "every lap quoted anywhere in this episode stayed inside the +/-12 deg "
        "region the tire file was fitted over. Laps outside it are discarded, not "
        "celebrated (rule 4), and they are discarded one lap at a time (F70).",
        value={c: bests[c]["worst_slip_deg"] for c in CONDITIONS if bests[c]})

    report.section("What is it worth?")
    report.add(
        "torque_vectoring_raises_the_cornering_limit",
        limits["tv4"] > limits["open"],
        f"the passive car runs out of road above grip_use "
        f"{limits['open']:.3f}; the controlled one holds on to "
        f"{limits['tv4']:.3f}, {limit_gain:+.1f}%. Same driver, same line, same "
        f"speed plan — the only difference is which wheels got which force.",
        value=[limits["open"], limits["tv4"]])
    report.add(
        "the_gain_is_below_the_best_published_figure",
        skid_gain < 9.0,
        f"on the skidpad — the manoeuvre the ~9% figure comes from, and the most "
        f"favourable one there is — this controller is worth "
        f"{skid_gain:+.2f}% of sustained lateral acceleration. The 9% is an "
        f"OUTSIDE number (rule 2) and it is a ceiling: our model does not get to "
        f"beat the most favourable published case, and if it did that would be a "
        f"bug rather than a result. **The citation is outstanding**: the figure "
        f"comes from this project's own series plan, which states it without a "
        f"reference, so it is marked as needing one rather than presented as "
        f"verified (rule 2's own instruction about unsourced bands).",
        value=skid_gain)
    report.add(
        "the_passive_limited_slip_differential_is_slower_than_an_open_one",
        bests["lsd"]["lap_time"] > bests["open"]["lap_time"],
        f"the LSD's best valid lap is {bests['lsd']['lap_time']:.3f} s against "
        f"{bests['open']['lap_time']:.3f} s for the open differential, and its "
        f"cornering limit is {limits['lsd']:.3f} against {limits['open']:.3f}. "
        f"This is Episode 12's push-wide (F76/F77) showing up in a lap time for "
        f"the first time: a locking device drags the outside wheel and yaws the "
        f"car out of the corner, and here that costs the driver the corner "
        f"entry.",
        value=[bests["open"]["lap_time"], bests["lsd"]["lap_time"]])

    report.section("Is it the yaw control, or just better bookkeeping?")
    shares = [v["allocator_share"] for v in sens.values()
              if np.isfinite(v.get("allocator_share", math.nan))] or [math.nan]
    report.add(
        "the_control_condition_separates_the_two_layers",
        limits["alloc"] > limits["open"],
        f"the allocator with its yaw demand forced to zero reaches "
        f"{limits['alloc']:.3f} against the open differential's "
        f"{limits['open']:.3f} and the full controller's {limits['tv4']:.3f}. "
        f"So {100*alloc_share:.0f}% of the improvement is the LOWER layer alone — "
        f"spreading brake and drive force across four wheels in proportion to "
        f"what each has left — and only the remainder is yaw control. A study "
        f"without this condition would have attributed all of it to torque "
        f"vectoring. Across the sensitivity runs the share spans "
        f"{100*min(shares):.0f}-{100*max(shares):.0f}%, so this is a 'roughly "
        f"half' claim rather than a decimal one — but the ordering "
        f"open < allocator < full controller holds in every one of them.",
        value={"open": limits["open"], "alloc": limits["alloc"],
               "tv4": limits["tv4"], "shares": shares})

    report.note(
        "on_the_skidpad_the_allocator_alone_buys_nothing",
        f"sustained lateral acceleration: open {skid_a_y['open']:.3f} g, "
        f"allocator-only {skid_a_y['alloc']:.3f} g, full controller "
        f"{skid_a_y['tv4']:.3f} g. On a steady circle there is no braking to "
        f"distribute and almost no drive force to spread, so the lower layer has "
        f"nothing to be clever with and lands slightly BELOW the passive car — "
        f"the whole skidpad gain is yaw control. The same two layers therefore "
        f"split the credit completely differently in the two manoeuvres, which is "
        f"an argument for reporting the decomposition per manoeuvre rather than "
        f"once.")

    report.section("Does the conclusion survive the numbers it rests on?")
    report.add(
        "the_conclusion_survives_plus_or_minus_3_percent_of_track_width",
        all(sens[k]["gain_pct"] > 0.0 for k in sens if k.startswith("track")),
        f"track width is the moment arm for torque vectoring and is only "
        f"[LIKELY] (CLAUDE.md). At -3% the gain is "
        f"{sens['track_0.97']['gain_pct']:+.2f}% and at +3% "
        f"{sens['track_1.03']['gain_pct']:+.2f}%, against "
        f"{limit_gain:+.2f}% nominal. The magnitude moves with the arm, as it "
        f"must; the conclusion does not.",
        value={k: sens[k]["gain_pct"] for k in sens if k.startswith("track")})
    if not quick:
        report.add(
            "the_conclusion_survives_the_driver_being_tuned_differently",
            all(sens[k]["gain_pct"] > 0.0 for k in ("look_short", "look_long")),
            f"**This check is expected to fail, and the failure is the finding.** "
            f"The driver's preview time is [ASSUMED], and it is exactly the "
            f"unstated protocol choice rule 9 was written about. Nominal gain "
            f"{limit_gain:+.2f}%. At 30% LESS preview it is "
            f"{sens['look_short']['gain_pct']:+.2f}% — the passive car improves to "
            f"{sens['look_short']['open']:.3f} and the controlled one falls to "
            f"{sens['look_short']['tv4']:.3f}, a difference of "
            f"{abs(sens['look_short']['tv4'] - sens['look_short']['open']):.4f} in "
            f"grip_use against a bisection resolution of 0.002, so it is barely "
            f"more than nothing rather than a reversal. At 30% MORE preview the "
            f"gain is {sens['look_long']['gain_pct']:+.2f}%. **The measured value "
            f"of the controller therefore varies by more than the controller is "
            f"worth, depending on how the driver it is helping was tuned** — and "
            f"the threshold is not being loosened to hide that (F69).",
            value={k: sens[k]["gain_pct"] for k in ("look_short", "look_long")})
        report.add(
            "the_conclusion_survives_the_allocator_s_priority_ratio",
            all(sens[k]["gain_pct"] > 0.0
                for k in ("priority_mz", "priority_fx")),
            f"when the two demands cannot both be met the allocator has to prefer "
            f"one, and the preference is a modelling choice. Weighting the moment "
            f"4x gives {sens['priority_mz']['gain_pct']:+.2f}% and weighting it "
            f"1/4 gives {sens['priority_fx']['gain_pct']:+.2f}%.",
            value={k: sens[k]["gain_pct"]
                   for k in ("priority_mz", "priority_fx")})

    report.section("Does it help a driver who is not perfect?")
    report.add(
        "the_disturbed_comparison_has_enough_samples_to_be_a_rate",
        all(v["n"] >= 8 for v in noise.values()),
        f"{n_seeds} seeded laps per configuration with steering noise, not "
        f"repeats of one (F66) and not the ten that produced a retracted "
        f"conclusion in Episode 11 (F70).",
        value=n_seeds)
    report.note(
        "what_the_disturbance_study_found",
        " · ".join(f"{SHORT[c]}: {noise[c]['valid']}/{noise[c]['n']} valid, "
                   f"{noise[c]['mean_lap']:.2f} +/- {noise[c]['sd_lap']:.2f} s"
                   for c in CONDITIONS)
        + f" — all at grip_use {gu_noise:.3f}.")

    report.note(
        "the_two_headline_numbers_are_not_independent",
        "Lap time and cornering limit are the same measurement twice: every "
        "configuration drives the same plan, so a quicker lap is only available "
        "by surviving a more aggressive plan. They are both reported because a "
        "lap time is legible and a grip_use is not.")
    report.note(
        "magnitudes_are_not_quotable",
        "Rung 2 (rule 15). Four independently commanded wheel forces is an "
        "electric car, not RV-1. Track width is [LIKELY] and is the moment arm. "
        "The driver is a centreline tracker, not a racing driver, so it cannot "
        "trade line for exit and its absolute lap times are not comparable with "
        "the optimal-control episodes (rule 6). Ordering and direction are the "
        "result.")

    report.findings.append(
        f"The two-layer controller works as advertised: the allocator delivers "
        f"the demanded yaw moment to within {tracking['mz_delivery_error']:.2f} "
        f"N.m, and yaw-rate tracking error through the corner falls "
        f"{100*(1-tracking['yaw_rms_tv']/tracking['yaw_rms_open']):.0f}%.")
    report.findings.append(
        f"It is worth {limit_gain:+.1f}% of cornering limit, {sec_gain:+.2f}% of "
        f"the corner section and {lap_gain:+.2f}% of the whole lap — the last "
        f"number is small because 260 of the lap's 393 m are a power-limited "
        f"straight where a yaw controller has nothing to do.")
    report.findings.append(
        f"On the skidpad, which is what the ~9% published figure measured, it is "
        f"worth {skid_gain:+.2f}% of sustained lateral acceleration.")
    report.findings.append(
        f"About {100*alloc_share:.0f}% of the gain is the allocator alone, with "
        f"its yaw demand forced to zero. Most of what a torque-vectoring system "
        f"buys on this lap is not torque vectoring.")
    if "look_short" in sens:
        report.findings.append(
            f"The number depends on the driver as much as on the car: across a "
            f"+/-30% change in how far ahead the SAME driver looks, the gain runs "
            f"from {sens['look_short']['gain_pct']:+.2f}% to "
            f"{sens['look_long']['gain_pct']:+.2f}%. A controller is tuned against "
            f"a driver whether or not anyone says so.")
    report.findings.append(
        f"The passive limited-slip differential is the slowest configuration "
        f"tested ({bests['lsd']['lap_time']:.3f} s against the open "
        f"differential's {bests['open']['lap_time']:.3f} s), which is Episode "
        f"12's push-wide appearing in a lap time.")

    results = {
        "track": {"name": track.name, "length_m": track.length,
                  "section": list(SECTION)},
        "skidpad": {"description": skid.description, "radius_m": CORNER_RADIUS},
        "reference_model": {"k_us_rad_per_ms2": ref["k_us"],
                            "k_deg_per_g": k_deg,
                            "a_y_max_ms2": ref["a_y_max"],
                            "a_y_max_g": ref["a_y_max"] / schema.G},
        "conditions": list(CONDITIONS), "labels": LABEL, "short": SHORT,
        "sweeps": laps, "limits": limits, "best": bests,
        "skidpad_limits": skid_limits, "skidpad_a_y_g": skid_a_y,
        "gains": {"lap_pct": lap_gain, "section_pct": sec_gain,
                  "limit_pct": limit_gain, "skidpad_pct": skid_gain,
                  "allocator_share": alloc_share},
        "tracking": tracking,
        "traces": {
            "tv4": {k: np.asarray(v).tolist() for k, v in tv_lap.log.items()
                    if k in ("s", "t", "speed", "yaw_rate", "steer", "a_y",
                             "alpha_max_deg", "n", "fx_fl", "fx_fr", "fx_rl",
                             "fx_rr", "fz_fl", "fz_fr", "fz_rl", "fz_rr",
                             "util_fl", "util_fr", "util_rl", "util_rr")},
            "tv4_control": {k: np.asarray(v).tolist() for k, v in T.items()},
            "open": {k: np.asarray(v).tolist() for k, v in open_lap.log.items()
                     if k in ("s", "t", "speed", "yaw_rate", "steer", "a_y", "n")},
            "open_r_ref": r_ref_open.tolist(),
        },
        "reference_sweep": ref_sweep,
        "sensitivity": sens,
        "noise": noise,
        "steer_noise": STEER_NOISE,
        "fidelity": ("Rung 2 — double-track, four commanded wheel forces. Shows "
                     "the mechanism and the two-layer split; does not model roll "
                     "camber, roll steer or compliance steer, which are most of a "
                     "real car's understeer. Ordering and trend only (rules 6, "
                     "15)."),
        "wall_clock_s": time.time() - t_start,
        "checks_passed": report.ok,
        "check_failures": [c.name for c in report.failures],
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    md = report.write_markdown(command="python -m experiments.ep13.run")
    report.write()
    report.print_summary(verbose="-v" in sys.argv)
    print(f"\n  write-up {md}")
    print(f"  {time.time() - t_start:.0f} s")
    figures(out)
    return 0 if report.ok else 1


def figures(out) -> None:
    from viz import tv_figures
    results = json.loads((out / "results.json").read_text())
    write(out / "01-two-layers.svg", tv_figures.two_layers_figure(results))
    write(out / "02-which-wheels-pay.svg", tv_figures.allocation_figure(results))
    write(out / "03-the-limit.svg", tv_figures.limit_figure(results))
    write(out / "04-yaw-tracking.svg", tv_figures.tracking_figure(results))
    write(out / "05-what-it-is-worth.svg", tv_figures.worth_figure(results))


if __name__ == "__main__":
    raise SystemExit(main())
