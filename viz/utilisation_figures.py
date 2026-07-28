"""Episode 6 figures — which tires are being asked to do two things at once.

``utilisation_figure``
    The centrepiece. Both drivetrains at three points through the corner, with
    every wheel's friction circle drawn and the force it is spending inside it.
``utilisation_card``
    Friction-circle usage against distance for all four wheels, both
    drivetrains, plus speed and the lines.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V
from physics.track import CORNER_ARC as T_ARC, ENTRY_STRAIGHT as T_ENTRY

CORNERS = ("fl", "fr", "rl", "rr")

#: Which differential these figures are drawn from. The traces are keyed
#: ``{drive}_*`` for the ideal-differential solve and ``{drive}_open_*`` for the
#: open one, and an earlier version of this module stamped "open differential"
#: on figures built from the ideal traces. One string, used by every stamp here,
#: so the label cannot disagree with the data again.
DIFF_STAMP = ("IDEAL differential [ASSUMED]: torque split floats freely, the "
              "best an LSD could manage. See figure 03 for the open-diff case")

#: Below this, a lap-time difference is not reportable. It is the size of the
#: convergence uncertainty an unconverged solve carries (F39: 0.1-0.7% of a 12 s
#: objective is 0.01-0.08 s), so anything under it is noise no matter how many
#: decimals the solver returns.
PWR_NOISE_FLOOR_S = 0.02


def _stamp(y: float, meta, extra: str = "") -> str:
    v, t = meta["vehicle"], meta["tire"]
    bits = [
        f"[MEASURED] double-track model + optimal control + {t['file']}",
        "offsets removed" if t["offsets_removed"] else "as shipped",
        f"m {v['mass']:.0f} kg - {v['front_mass_fraction']:.0%} front",
        f"{meta['n_nodes']} nodes",
        "[SOURCED] RV-1 params §1",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  -  ".join(bits), V.MUT, 9.5)


def utilisation_figure(traces, results, meta, marks) -> str:
    """Two drivetrains x three points through the corner, friction circles drawn."""
    s_axis = traces["s"]
    W, H = 1480, 1060
    s = V.head(
        W, H,
        "Which tires are being asked to do two things at once",
        "The same corner, the same car, the same tires. The only difference is "
        "which axle receives drive torque. Each circle is everything one tire "
        "can do at that instant; the arrow is what it is spending.",
    )
    s += D.text(40, 92,
                "Arrow up means accelerating, sideways means cornering, "
                "diagonal means both -- and diagonal reaches the edge sooner.",
                V.MUT, 11.5)

    rows = (("rwd", "Rear-wheel drive", V.TEAL),
            ("fwd", "Front-wheel drive", V.COR))
    col_x = (430, 780, 1130)
    for ri, (drive, title, colour) in enumerate(rows):
        cy = 300 + ri * 340
        s += D.panel_title(60, cy - 100, title,
                           f"{results[drive]['time_s']:.2f} s, exits at "
                           f"{results[drive]['exit_speed_ms']:.1f} m/s")
        for ci, (label, s_at) in enumerate(marks):
            k = int(np.argmin(np.abs(s_axis - s_at)))
            cx = col_x[ci]
            if ri == 0:
                s += D.text(cx, cy - 112, label, V.FG, 13, "middle", weight="600")
            # a small car, with a friction circle beside each wheel
            s += D.car_plan(cx, cy, length=118, width=54, wheel_len=26,
                            wheel_w=11, loads=(0.5,) * 4, body=V.MUT)
            for corner, dx, dy in (("fl", -1, -1), ("fr", 1, -1),
                                   ("rl", -1, 1), ("rr", 1, 1)):
                fz = traces[f"{drive}_load_{corner}"][k]
                fx = traces[f"{drive}_fx_{corner}"][k]
                fy = traces[f"{drive}_fy_{corner}"][k]
                # normalise by what this tire could do at this load
                cap_x = max(1.174 * fz, 1.0)
                cap_y = max(1.049 * fz, 1.0)
                u = traces[f"{drive}_utilisation_{corner}"][k]
                wx = cx + dx * 96
                wy = cy + dy * 46
                s += D.friction_circle(
                    wx, wy, 30, fx / cap_x, fy / cap_y,
                    colour=V.COR if u > 0.9 else (V.AMB if u > 0.5 else V.TEAL),
                    label=f"{100*u:.0f}%")
        u_ex = results[drive]["mean_utilisation_on_exit"]
        s += D.text(60, cy - 40, "averaged over the whole exit straight:",
                    V.MUT, 11)
        s += D.text(60, cy - 18,
                    f"front {0.5*(u_ex['fl']+u_ex['fr']):.0%}   "
                    f"rear {0.5*(u_ex['rl']+u_ex['rr']):.0%}",
                    colour, 15, weight="600", mono=True)
        u_c = results[drive]["mean_utilisation_in_corner"]
        s += D.text(60, cy + 16, "averaged through the corner:", V.MUT, 11)
        s += D.text(60, cy + 38,
                    f"front {0.5*(u_c['fl']+u_c['fr']):.0%}   "
                    f"rear {0.5*(u_c['rl']+u_c['rr']):.0%}",
                    V.MUT, 13, mono=True)

    s += D.rule(60, 800, 1420, V.GRID)
    dt = results["time_delta_s"]
    for i, line in enumerate([
        "Look at the exit column. The rear-wheel-drive car's front tires are "
        "nearly idle -- they are only steering, and the corner is",
        "almost over. Its rear tires are doing the accelerating. Two jobs, two "
        "axles.",
        "",
        "The front-wheel-drive car has to do both jobs with the same pair of "
        "tires, and on exit they are at the edge of what they can",
        "do. Not because they have less grip -- they are the same tires at a "
        "similar load -- but because the force they are being asked",
        "for points diagonally, and a diagonal reaches the edge of the circle "
        "sooner than either direction alone.",
        "",
        f"Over this corner and the straight after it, that is worth "
        f"{dt:+.2f} s and "
        f"{results['exit_speed_delta_ms']:+.1f} m/s of exit speed.",
    ]):
        s += D.text(60, 840 + 22 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, meta, DIFF_STAMP)
    return s + V.foot(
        W, H,
        "Friction-circle usage is sqrt((Fx/Fx_peak)^2 + (Fy/Fy_peak)^2) at each "
        "wheel's instantaneous load. The ellipse shape is the placeholder "
        "combined-slip model, not a fitted one -- see FINDINGS D9.",
    )


def _u_colour(u: float) -> str:
    """Teal (idle) through amber to coral (nothing left)."""
    r, g, b = V.ramp(float(u))
    return f"#{r:02x}{g:02x}{b:02x}"


def _wheel_overlay(cx, cy, heading_deg, length, width, wheel_w, forces,
                   colours, arrow_len=26.0):
    """Force arrows at each of a car's four wheels, drawn in the car's frame.

    ``forces`` is fl/fr/rl/rr as ``(fx, fy, used)`` with fx/fy in ISO body axes
    (x forward, y left) and ``used`` the fraction of that tire spent. **Arrow
    length is ``used``, direction is the force.** So length answers "how close to
    the edge is this tire?" and angle answers "what did it spend it on?" — which
    is the whole Episode 6 argument in one mark.

    Drawn inside the same ``rotate()`` as :func:`viz.diagram.car_plan`, with the
    same wheel offsets, so the arrows cannot drift off the wheels.
    """
    hl, hw = length / 2, width / 2
    ax_f, ax_r = -length * 0.30, length * 0.30
    g = f'<g transform="rotate({heading_deg:.3f} {cx:.1f} {cy:.1f})">'
    for corner, (sx, dy) in zip(CORNERS, ((-1, ax_f), (1, ax_f),
                                          (-1, ax_r), (1, ax_r))):
        fx, fy, used = forces[corner]
        mag = math.hypot(fx, fy)
        if mag < 1e-6 or used < 0.04:
            continue
        wx = cx + sx * (hw + wheel_w * 0.35)
        wy = cy + dy
        L = arrow_len * min(float(used), 1.0)
        # ISO -> screen: forward is up (-y), +y_iso (left) is -x
        tx = wx - (fy / mag) * L
        ty = wy - (fx / mag) * L
        g += D.arrow(wx, wy, tx, ty, colours[corner], 1.9, 6.0)
    return g + "</g>"


def along_the_corner_figure(traces, results, meta, track) -> str:
    """The car walked along its own solved line, carrying its result with it.

    The friction-circle figure shows three instants in isolation; this one puts
    them back on the road, because "the front tires run out on exit" is a claim
    about a *place* and the reader should be able to point at it.
    """
    from .line_figures import track_backdrop, path_heading

    s_axis = traces["s"]
    c0 = T_ENTRY
    c1 = T_ENTRY + T_ARC
    s0, s1 = c0 - 30.0, c1 + 58.0
    # Spread far enough apart that two cars never touch at this scale: the
    # braking zone, turn-in, the apex, the exit, and out on the straight.
    stations = [c0 - 22.0, c0 + 14.0, c0 + 0.54 * T_ARC, c1 + 2.0, c1 + 40.0]

    W, H = 1480, 1160
    s = V.head(
        W, H,
        "Where each tire runs out, drawn on the road it happens on",
        "The same corner driven twice, identical in every respect except which "
        "axle is driven. The car is drawn at five points along its own solved "
        "line; each contact patch is coloured by how much of that tire is left.",
    )
    s += D.text(40, 92,
                "Arrow length is how much of the tire is spent; arrow direction "
                "is what it was spent on. Long and diagonal is the expensive one.",
                V.MUT, 11.5)

    panels = (("rwd", "Rear-wheel drive", 70, 700),
              ("fwd", "Front-wheel drive", 770, 1400))
    for drive, title, L, R in panels:
        back, to_px, scale = track_backdrop(track, s0, s1, L, R, 210, 800)
        s += D.panel_title(L, 176, title,
                           f"{results[drive]['time_s']:.2f} s  ·  exits at "
                           f"{results[drive]['exit_speed_ms']:.1f} m/s")
        s += back

        n = traces[f"{drive}_n"]
        xi = traces[f"{drive}_xi"]
        delta = traces[f"{drive}_delta"]
        x, y = track.to_xy(s_axis, n)
        px, py = to_px(x, y)
        # Clip the line to the same window as the tarmac. Drawing the whole
        # 393 m solution on a crop of it sends the rest of the lap off the panel
        # as two stray lines that read as part of the road.
        win = (s_axis >= s0) & (s_axis <= s1)
        s += (f'<path d="{V.path(list(zip(px[win], py[win])))}" fill="none" '
              f'stroke="{V.FG}" stroke-width="2.2" opacity="0.55"/>')

        head = path_heading(track, s_axis, xi)
        for s_at in stations:
            k = int(np.argmin(np.abs(s_axis - s_at)))
            cxp, cyp = float(px[k]), float(py[k])
            u = {c: float(traces[f"{drive}_utilisation_{c}"][k]) for c in CORNERS}
            fz = {c: float(traces[f"{drive}_load_{c}"][k]) for c in CORNERS}
            fzmax = max(max(fz.values()), 1.0)
            cols = {c: _u_colour(u[c]) for c in CORNERS}
            hd = D.screen_heading_deg(math.degrees(float(head[k])))
            s += D.car_plan(cxp, cyp, length=48, width=23, wheel_len=13,
                            wheel_w=6.5, steer_deg=D.screen_deg(
                                math.degrees(float(delta[k]))),
                            heading_deg=hd,
                            loads=tuple(fz[c] / fzmax for c in CORNERS),
                            body=V.FG, patches=tuple(cols[c] for c in CORNERS))
            s += _wheel_overlay(
                cxp, cyp, hd, 48, 23, 6.5,
                {c: (float(traces[f"{drive}_fx_{c}"][k]),
                     float(traces[f"{drive}_fy_{c}"][k]), u[c]) for c in CORNERS},
                cols, arrow_len=30.0)
            front = 0.5 * (u["fl"] + u["fr"])
            s += D.text(cxp, cyp + 44, f"front {front:.0%}",
                        _u_colour(front), 11, "middle", mono=True)

    # legend: what the patch colours mean. Kept clear of the lowest station's
    # own label, which sits just under the panel edge.
    ly = 872
    s += D.text(70, ly, "fraction of the tire being used:", V.MUT, 11.5)
    for i, u in enumerate((0.1, 0.35, 0.6, 0.85, 1.0)):
        bx = 290 + i * 96
        s += (f'<rect x="{bx}" y="{ly-11}" width="70" height="13" rx="3" '
              f'fill="{_u_colour(u)}"/>')
        s += D.text(bx + 35, ly + 16, f"{u:.0%}", V.MUT, 10.5, "middle")
    s += D.text(830, ly, "nothing left to steer or brake with at 100%",
                V.MUT, 11.5)

    s += D.rule(70, 912, 1400, V.GRID)
    dt = results["time_delta_s"]
    for i, line in enumerate([
        "Follow the front wheels along each line. Through the corner both cars "
        "are the same: all four patches near the top of the scale, because both",
        "are cornering as hard as the tires allow and the lines are nearly "
        "identical.",
        "",
        "Past the corner exit they part company. The rear-drive car's front "
        "patches cool off — the corner is over, they are only steering. The",
        "front-drive car's stay hot, and its arrows stay long and diagonal, "
        "because the same two tires that are finishing the corner are also the",
        f"ones putting the power down. Over this corner and the straight after "
        f"it that costs {dt:+.2f} s.",
    ]):
        s += D.text(70, 942 + 22 * i, line, V.MUT, 12.5)

    s += D.text(70, H - 62,
                f"Cropped to {s0:.0f}–{s1:.0f} m along the track; scale "
                f"{10.0*scale:.0f} px per 10 m. The car is drawn about "
                f"{48.0/(4.5*scale):.1f}× its true size so the wheels are "
                f"legible — positions, headings and steer angles are to scale.",
                V.MUT, 11)
    s += _stamp(H - 40, meta, DIFF_STAMP)
    return s + V.foot(
        W, H,
        "Contact-patch size is vertical load, normalised per instant; patch "
        "colour and arrow length are friction-circle usage. Slip angle is "
        "constrained to ±12° and envelope occupancy is zero in both solves.",
    )


def power_figure(results, meta) -> str:
    """How much engine power the answer depends on — drawn, not tabulated.

    The front-drive penalty is proportional to power, and at low power it
    disappears. That was the episode's most useful result and it existed only as a
    table, which is a rule-1 failure: the whole claim is about tires filling up, so
    the tires have to be visible.

    Each column is one power level. Each column shows the two cars 20 m past the
    corner exit — still finishing the turn, already accelerating — with every
    wheel's friction circle drawn. Read left to right and watch the front-drive
    car's front circles fill.
    """
    sweep = results["power_sweep"]
    keys = sorted(sweep, key=float)
    W, H = 1480, 1120
    s = V.head(
        W, H,
        "How much of this answer is about the engine?",
        "The same corner, the same car, the same tires — with four different "
        "engines. Each pair is 20 m past the corner exit, where the car is still "
        "turning and already accelerating. Circles are what each tire can do; "
        "arrows are what it is spending.",
    )
    s += D.text(40, 92,
                "Watch the front-drive car's FRONT circles fill up as the engine "
                "gets stronger. That filling is the entire penalty.", V.MUT, 11.5)

    col_w = 1340 / len(keys)
    for ci, k in enumerate(keys):
        row = sweep[k]
        cx = 110 + col_w * (ci + 0.5)
        kn = float(k)
        s += D.text(cx, 150, f"{kn:g} kN", V.FG, 16, "middle", weight="600")
        s += D.text(cx, 170, f"≈{kn*30*1.341:.0f} hp", V.MUT, 11, "middle")
        for ri, (drive, label, colour) in enumerate(
                (("rwd", "rear drive", V.TEAL), ("fwd", "front drive", V.COR))):
            cy = 300 + ri * 300
            st = row[drive]["at_station"]
            if ci == 0:
                s += D.text(58, cy - 78, label, colour, 13, weight="600")
            s += D.car_plan(cx, cy, length=92, width=42, wheel_len=20, wheel_w=9,
                            loads=(0.5,) * 4, body=V.MUT)
            for corner, dx, dy in (("fl", -1, -1), ("fr", 1, -1),
                                   ("rl", -1, 1), ("rr", 1, 1)):
                fz = st["load_N"][corner]
                u = st["utilisation"][corner]
                s += D.friction_circle(
                    cx + dx * 74, cy + dy * 36, 24,
                    st["fx_N"][corner] / max(1.174 * fz, 1.0),
                    st["fy_N"][corner] / max(1.049 * fz, 1.0),
                    colour=_u_colour(u), label=f"{100*u:.0f}%", size=9)
        d = row["delta_s"]
        # CLAUDE.md rule 5: below the noise floor it is "no measurable effect",
        # never "a small effect". An earlier version printed "-0.00 s / front
        # drive GAINS" off a -0.003 s difference -- claiming a win from zero, and
        # from an unconverged solve at that.
        floor = PWR_NOISE_FLOOR_S
        if abs(d) < floor:
            s += D.text(cx, 790, "no measurable", V.MUT, 15, "middle",
                        weight="600")
            s += D.text(cx, 810, "difference", V.MUT, 15, "middle", weight="600")
            s += D.text(cx, 832, f"|{d:+.3f}| s, under the {floor:.2f} s floor",
                        V.MUT, 9.5, "middle", style="italic")
        else:
            # "front drive costs -0.03 s" is not a sentence. Since the corrected
            # yaw moment (F79) the sign genuinely goes both ways across this
            # sweep, so the label has to say which way rather than assume.
            s += D.text(cx, 790, f"{abs(d):.2f} s",
                        V.AMB if row["both_converged"] else V.MUT, 19, "middle",
                        weight="600", mono=True)
            s += D.text(cx, 812,
                        "front drive is SLOWER" if d > 0 else "front drive is FASTER",
                        V.COR if d > 0 else V.TEAL, 10.5, "middle", weight="600")
        if not row["both_converged"] and abs(d) >= PWR_NOISE_FLOOR_S:
            s += D.text(cx, 832, "trend only", V.MUT, 9.5, "middle",
                        style="italic")

    s += D.rule(60, 862, 1420, V.GRID)
    lo, hi = sweep[keys[0]], sweep[keys[-1]]
    for i, line in enumerate([
        "At the low-power end the corner exit is limited by the ENGINE, not by "
        "grip. No tire on either car is above 63%, so there is spare",
        "grip everywhere and it does not matter which pair is driven. The two "
        "cars are the same speed, to within the noise floor.",
        "",
        "At the high-power end the front-drive car's front tires are being asked "
        "to finish the corner and deliver all the acceleration at once,",
        "and they run out. The rear-drive car splits those two jobs across two "
        "axles and never has the problem.",
        "",
        f"So the answer REVERSES across the range: front drive "
        f"{abs(lo['delta_s']):.2f} s ahead at {keys[0]} kN, "
        f"{abs(hi['delta_s']):.2f} s behind at {keys[-1]} kN — a span of "
        f"{results['power_sweep_delta_span_s']:.2f} s across a 4x range of engine.",
        "\"Rear drive is faster\" is not a fact about drivetrains; it is a fact "
        "about drivetrains at a given power level. It is also why nobody minds "
        "that economy hatchbacks are",
        "front-wheel drive, and why almost nothing built to be fast is.",
    ]):
        s += D.text(60, 892 + 21 * i, line, V.MUT, 12.5)

    quotable = ", ".join(results.get("power_sweep_quotable_kN", []))
    s += _stamp(H - 40, meta,
                f"drive cap [ASSUMED]; power [DERIVED] as force x 30 m/s, "
                f"indicative; converged at {quotable} kN (F39)")
    return s + V.foot(
        W, H,
        "A real engine's force falls with speed rather than holding a cap, so "
        "these are levels of available acceleration rather than horsepower "
        "figures. The trend is the result; the individual times are indicative.",
    )


def whole_track_figure(traces, results, meta, track) -> str:
    """The entire track from above — straight, corner, straight — nothing cropped.

    Every other figure here crops to the corner, which is where the *result* is.
    This one exists to make the run **inspectable**: the whole road at true
    proportions, the line the car actually took, coloured by speed, with the car
    drawn at stations along all of it. Reading numbers off a trace tells you what
    you thought to ask; a top-down view of the road tells you when the car did
    something no driver would do.

    That is not hypothetical. The entry-straight steering chatter of F40 was
    invisible in every figure in this episode because they all begin 30 m before
    turn-in, so the setup phase was off-frame.
    """
    from .line_figures import track_backdrop, path_heading

    s_axis = traces["s"]
    c0, c1 = T_ENTRY, T_ENTRY + T_ARC
    W, H = 1480, 1180
    s = V.head(
        W, H,
        "The whole run from above — nothing cropped",
        "The complete 393 m: approach straight, the 90° corner, and the exit "
        "straight. The line is the path the car actually took, coloured by speed. "
        "Cars are drawn at stations along the whole run, not just the corner.",
    )

    for drive, title, L, R in (("rwd", "Rear-wheel drive", 60, 470),
                               ("fwd", "Front-wheel drive", 520, 930)):
        back, to_px, scale = track_backdrop(track, 0.0, track.length, L, R, 150, 1010)
        s += D.panel_title(L, 130, title,
                           f"{results[drive]['time_s']:.2f} s")
        s += back
        n = traces[f"{drive}_n"]
        x, y = track.to_xy(s_axis, n)
        px, py = to_px(x, y)
        v = traces[f"{drive}_speed"]
        vmin, vmax = float(v.min()), float(v.max())
        # coloured per segment: slow is teal, fast is coral
        for k in range(len(s_axis) - 1):
            u = (0.5 * (v[k] + v[k + 1]) - vmin) / max(vmax - vmin, 1e-9)
            s += (f'<line x1="{px[k]:.1f}" y1="{py[k]:.1f}" x2="{px[k+1]:.1f}" '
                  f'y2="{py[k+1]:.1f}" stroke="{_u_colour(u)}" '
                  f'stroke-width="2.6" stroke-linecap="round"/>')
        head = path_heading(track, s_axis, traces[f"{drive}_xi"])
        delta = traces[f"{drive}_delta"]
        for s_at in (14.0, 40.0, c0 - 4.0, c0 + 0.3 * T_ARC,
                     c0 + 0.7 * T_ARC, c1 + 18.0, c1 + 90.0, c1 + 200.0):
            k = int(np.argmin(np.abs(s_axis - s_at)))
            u = {c: float(traces[f"{drive}_utilisation_{c}"][k]) for c in CORNERS}
            fz = {c: float(traces[f"{drive}_load_{c}"][k]) for c in CORNERS}
            fzmax = max(max(fz.values()), 1.0)
            s += D.car_plan(
                float(px[k]), float(py[k]), length=30, width=15, wheel_len=9,
                wheel_w=4.5,
                steer_deg=D.screen_deg(math.degrees(float(delta[k]))),
                heading_deg=D.screen_heading_deg(math.degrees(float(head[k]))),
                loads=tuple(fz[c] / fzmax for c in CORNERS), body=V.FG,
                patches=tuple(_u_colour(u[c]) for c in CORNERS))
        # where the corner is, marked on the road
        for s_at, lab in ((c0, "corner starts"), (c1, "corner ends")):
            k = int(np.argmin(np.abs(s_axis - s_at)))
            s += D.text(float(px[k]) + 16, float(py[k]) + 4, lab, V.MUT, 10)

    # legend
    ly = 1058
    s += D.text(60, ly, "line colour is speed:", V.MUT, 11.5)
    ref = traces["rwd_speed"]
    for i, u in enumerate((0.0, 0.25, 0.5, 0.75, 1.0)):
        bx = 210 + i * 84
        s += (f'<rect x="{bx}" y="{ly-11}" width="60" height="12" rx="3" '
              f'fill="{_u_colour(u)}"/>')
        s += D.text(bx + 30, ly + 17,
                    f"{ref.min() + u * (ref.max() - ref.min()):.0f}", V.MUT, 10,
                    "middle")
    s += D.text(640, ly, "m/s.  Contact-patch colour is how much of that tire is "
                "used, as in the other figures.", V.MUT, 11.5)

    s += D.text(990, 200,
                "What to look for, and what a reader can check without", V.FG,
                13, weight="600")
    s += D.text(990, 220, "taking the numbers on trust:", V.FG, 13, weight="600")
    for i, line in enumerate([
        "",
        "· The line should hug the outside of the road on the",
        "  approach, cut to the inside at the apex, and run",
        "  wide again on exit. That is the racing line, and",
        "  nobody told the solver about it.",
        "",
        "· It should be coldest (slowest) around the apex and",
        "  warmest at the end of the exit straight.",
        "",
        "· The front wheels are turned on the approach, and",
        "  that is correct, not a glitch. The car pulls 0.86 g",
        "  the WRONG way first to reach the outside edge, then",
        "  is already at the slip limit 22 m before the corner",
        "  nominally starts. It corners before the corner.",
        "",
        "· Rear drive: front patches go cold on the exit,",
        "  rear patches stay warm. Front drive: the opposite,",
        "  and its front patches stay warm much longer.",
        "",
        "· Neither car should ever be off the tarmac.",
    ]):
        s += D.text(990, 244 + 19 * i, line, V.MUT, 11.5)

    s += _stamp(H - 40, meta, DIFF_STAMP)
    return s + V.foot(
        W, H,
        "True proportions: the corner is 40 m radius on an 8 m road, and the exit "
        "straight really is that long relative to it. Cars are drawn oversized to "
        "be legible; positions, headings and steer angles are to scale.",
    )


def overlay_figure(traces, results, meta, track) -> str:
    """Both drivetrains on ONE road, so the comparison is direct.

    Side-by-side panels are honest but they make the reader hold two pictures in
    their head and diff them. Overlaying is noisier and far more convincing,
    because the first thing it shows is that **the two lines are nearly the same
    line** — which is the real finding. Nothing about the path changes; what
    changes is what the tires are being asked to do along it.

    Two views: the whole 393 m on the left so the straights are in frame, and the
    corner enlarged on the right with the two cars drawn as a pair at each station,
    offset perpendicular to travel so both are visible.
    """
    from .line_figures import track_backdrop, path_heading

    s_axis = traces["s"]
    c0, c1 = T_ENTRY, T_ENTRY + T_ARC
    cars = (("rwd", "Rear-wheel drive", V.TEAL, -1),
            ("fwd", "Front-wheel drive", V.COR, +1))

    W, H = 1480, 1180
    s = V.head(
        W, H,
        "Both cars on the same road",
        "The same corner driven twice, overlaid rather than side by side. The two "
        "lines are almost indistinguishable — that is the point. What differs is "
        "not where the car goes but what its tires are being asked to do.",
    )

    def _draw(L, R, T, B, s0, s1, car_len, stations, stagger_m):
        out, to_px, scale = track_backdrop(track, s0, s1, L, R, T, B)
        win = (s_axis >= s0) & (s_axis <= s1)
        # The two lines sit almost on top of each other, so the second one drawn
        # would simply erase the first. Rear drive goes down thick and solid,
        # front drive dashed over it, and both stay readable.
        for (drive, _, colour, _side), (w, dash) in zip(
                cars, ((4.0, ""), (2.4, ' stroke-dasharray="9 7"'))):
            x, y = track.to_xy(s_axis, traces[f"{drive}_n"])
            px, py = to_px(x, y)
            out += (f'<path d="{V.path(list(zip(px[win], py[win])))}" fill="none" '
                    f'stroke="{colour}" stroke-width="{w}"{dash}/>')
        for i, (drive, _, colour, _side) in enumerate(cars):
            x, y = track.to_xy(s_axis, traces[f"{drive}_n"])
            px, py = to_px(x, y)
            head = path_heading(track, s_axis, traces[f"{drive}_xi"])
            delta = traces[f"{drive}_delta"]
            for s_at in stations:
                # Stagger the two cars ALONG the track rather than nudging them
                # sideways. A perpendicular nudge put cars visibly off the tarmac,
                # which reads as "the car left the road" -- a fiction, in a figure
                # whose entire job is letting a reader judge what is reasonable.
                # Staggered, each car is drawn at a genuine point on its own
                # solved path and both stay where they really were.
                k = int(np.argmin(np.abs(s_axis - (s_at + i * stagger_m))))
                hd = D.screen_heading_deg(math.degrees(float(head[k])))
                u = {c: float(traces[f"{drive}_utilisation_{c}"][k])
                     for c in CORNERS}
                fz = {c: float(traces[f"{drive}_load_{c}"][k]) for c in CORNERS}
                fzmax = max(max(fz.values()), 1.0)
                out += D.car_plan(
                    float(px[k]), float(py[k]),
                    length=car_len, width=car_len * 0.48,
                    wheel_len=car_len * 0.27, wheel_w=car_len * 0.13,
                    steer_deg=D.screen_deg(math.degrees(float(delta[k]))),
                    heading_deg=hd,
                    loads=tuple(fz[c] / fzmax for c in CORNERS), body=colour,
                    patches=tuple(_u_colour(u[c]) for c in CORNERS))
        return out, scale

    left, sc_l = _draw(60, 430, 150, 1010, 0.0, track.length, 26,
                       (24.0, c0 + 0.45 * T_ARC, c1 + 40.0, c1 + 185.0), 13.0)
    s += D.panel_title(60, 130, "The whole 393 m")
    s += left

    right, sc_r = _draw(520, 1010, 150, 700, c0 - 26.0, c1 + 46.0, 46,
                        (c0 - 16.0, c0 + 10.0, c0 + 0.50 * T_ARC, c1 - 6.0,
                         c1 + 26.0), 8.0)
    s += D.panel_title(520, 130, "The corner, enlarged",
                       "the two cars drawn as a pair at each point, nudged apart "
                       "so both are visible")
    s += right

    ly = 760
    for i, (drive, label, colour, _s) in enumerate(cars):
        dash = '' if i == 0 else ' stroke-dasharray="9 7"'
        s += (f'<line x1="520" y1="{ly + i*26 - 4}" x2="562" '
              f'y2="{ly + i*26 - 4}" stroke="{colour}" '
              f'stroke-width="{4.0 if i == 0 else 2.4}"{dash}/>')
        s += D.text(574, ly + i * 26, label, colour, 13, weight="600")
        s += D.text(760, ly + i * 26,
                    f"{results[drive]['time_s']:.3f} s   "
                    f"apex {100*results[drive]['apex_fraction_through_corner']:.1f}% "
                    f"through   slowest "
                    f"{results[drive]['min_speed_ms']:.1f} m/s   exit "
                    f"{results[drive]['exit_speed_ms']:.1f} m/s", V.MUT, 11.5)

    s += D.rule(520, ly + 62, 1420, V.GRID)
    for i, line in enumerate([
        "The car outline is coloured by drivetrain; each contact patch is "
        "coloured by how much of that tire is being used, on the",
        "same scale as the other figures — cool means spare grip, hot means "
        "nothing left.",
        "",
        "Both cars apex at the same point to within a tenth of a percent and "
        "their slowest speeds differ by 0.3 m/s. Through the",
        "corner every patch on both cars is hot. Follow the pair out of the "
        "corner and they separate: the rear-drive car's front",
        "patches cool while its rears stay hot, and the front-drive car's fronts "
        "stay hot long after the corner is over, because",
        "they are still doing the accelerating.",
        "",
        "On the approach both cars run to the outside edge — the correct wide entry, "
        "which nobody specified. They get there by pulling",
        "0.86 g in the opposite direction first, and they are already at the slip "
        "limit 22 m before the corner begins (F40).",
    ]):
        s += D.text(520, ly + 92 + 20 * i, line, V.MUT, 12)

    s += D.text(60, 1060,
                f"Left panel {10*sc_l:.0f} px per 10 m; right panel "
                f"{10*sc_r:.0f} px per 10 m. Cars drawn oversized for legibility "
                f"and staggered a few metres apart along the track so they do not "
                f"overlap; every car sits at a real point on its own solved path, "
                f"with heading and steer angle to scale.", V.MUT, 11)
    s += _stamp(H - 40, meta, DIFF_STAMP)
    return s + V.foot(
        W, H,
        "Overlaid rather than side by side because the strongest thing this "
        "comparison shows is how little the path changes. Both solves keep slip "
        "angle inside ±12° with zero envelope violations.",
    )


def differential_figure(traces, results, meta) -> str:
    """What the differential does, and why it matters more to front drive.

    The open/ideal split is a modelling choice that moves the headline number by
    60%, so it gets its own figure rather than a footnote (CLAUDE.md rule 9).
    """
    s_axis = traces["s"]
    # Sample where the differential actually BINDS -- the station at which the
    # open diff costs the axle the most total drive force. An earlier version
    # sampled where drive force peaks on the exit straight, which is where the
    # ENGINE is the limit: both diffs read 4.50 kN there and the two panels were
    # identical, quietly contradicting the caption. The binding point turns out
    # to be inside the corner, not on the way out of it.
    gap = ((traces["rwd_fx_rl"] + traces["rwd_fx_rr"])
           - (traces["rwd_open_fx_rl"] + traces["rwd_open_fx_rr"]))
    k = int(np.argmax(gap))

    W, H = 1480, 1060
    s = V.head(
        W, H,
        "What the differential does, and who needs it more",
        "The rear axle of the rear-drive car, at the point in the corner where "
        "the differential costs it the most. Both wheels are on the same axle at "
        "the same instant; the only difference is whether the differential may "
        "send them different torque.",
    )
    s += D.text(40, 92,
                "Arrow length is the driving force at that wheel. The inside "
                "wheel is unloaded by the cornering, so it can take less -- and "
                "an open differential makes that the whole axle's problem.",
                V.MUT, 11.5)

    cases = (("rwd_open", "Open differential", "equal torque, both wheels",
              V.COR, "The split is forced to 50/50, so the outside wheel is held "
              "down to whatever the light inside one can take."),
             ("rwd", "Ideal differential", "torque follows grip",
              V.TEAL, "Each wheel takes what its own load allows. This is the "
              "best an LSD could manage, so it is the optimistic bound."))
    for i, (tag, title, sub, colour, note) in enumerate(cases):
        cx, cy = 380 + i * 700, 400
        s += D.panel_title(cx - 260, 156, title, sub)
        s += D.arrow(cx, cy + 110, cx, cy - 200, V.MUT, 1.6, 9, dash="5 5")
        s += D.text(cx, cy - 212, "direction of travel", V.MUT, 10.5, "middle")
        fz = {c: float(traces[f"{tag}_load_{c}"][k]) for c in ("rl", "rr")}
        fx = {c: float(traces[f"{tag}_fx_{c}"][k]) for c in ("rl", "rr")}
        u = {c: float(traces[f"{tag}_utilisation_{c}"][k]) for c in ("rl", "rr")}
        fzmax = max(max(fz.values()), 1.0)
        for side, corner, name in ((-1, "rl", "inside"), (1, "rr", "outside")):
            wx = cx + side * 130
            s += D.tire(wx, cy, 0.0, length=96, width=38,
                        load_frac=fz[corner] / fzmax, patch=_u_colour(u[corner]))
            s += D.arrow(wx, cy - 56, wx, cy - 56 - 130.0 * fx[corner] / 4500.0,
                         colour, 3.0, 10)
            s += D.text(wx, cy + 78, name, V.MUT, 11, "middle")
            s += D.text(wx, cy + 100, f"{fz[corner]/1000:.2f} kN on it",
                        V.MUT, 11.5, "middle", mono=True)
            s += D.text(wx, cy + 122, f"{fx[corner]/1000:+.2f} kN driving",
                        colour, 13, "middle", weight="600", mono=True)
        total = fx["rl"] + fx["rr"]
        s += D.text(cx, cy + 168, f"axle total {total/1000:.2f} kN", V.FG, 14,
                    "middle", weight="600", mono=True)
        s += D.text(cx - 260, cy + 206, note, V.MUT, 11.5)

    s += D.rule(60, 660, 1420, V.GRID)
    rows = [
        ("", "Open diff", "Ideal diff", "a perfect diff is worth"),
        ("Rear-wheel drive", f"{results['rwd_open']['time_s']:.3f} s",
         f"{results['rwd_ideal']['time_s']:.3f} s",
         f"{results['diff_worth_s_rwd']:.3f} s"),
        ("Front-wheel drive", f"{results['fwd_open']['time_s']:.3f} s",
         f"{results['fwd_ideal']['time_s']:.3f} s",
         f"{results['diff_worth_s_fwd']:.3f} s"),
        ("front drive costs", f"{results['time_delta_s_open']:+.3f} s",
         f"{results['time_delta_s_ideal']:+.3f} s", ""),
    ]
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            bold = "600" if r == 0 or c == 0 else "normal"
            col = V.FG if r == 0 or c == 0 else V.MUT
            if r == 3 and c in (1, 2):
                col = V.AMB
            s += D.text(60 + c * 300, 700 + r * 26, cell, col, 12.5,
                        weight=bold, mono=(c > 0 and r > 0))

    for i, line in enumerate([
        f"This is happening at s = {s_axis[k]:.0f} m, which is {s_axis[k]-T_ENTRY:.0f} m "
        f"INTO the corner, not on the way out of it. That is where the inside "
        f"wheel is lightest, so that is where an",
        "open differential hurts. Out on the straight the car is level, both "
        "driven wheels can take plenty, and the engine is the limit instead — "
        "the differential makes no",
        "difference there at all.",
        "",
        f"Rear drive gains {results['diff_worth_s_rwd']:.3f} s from a perfect "
        f"differential. Front drive gains {results['diff_worth_s_fwd']:.3f} s — "
        f"roughly twice as much. That is not a coincidence: the front-drive car's "
        f"driven wheels are also its",
        "steering wheels, so they are closer to the edge already, and recovering "
        "traction is worth more to the axle with less to spare.",
        "",
        f"Rear drive is faster either way, so the conclusion holds. The size of it "
        f"does not: {results['time_delta_s_open']:+.3f} s with an open diff, "
        f"{results['time_delta_s_ideal']:+.3f} s with a perfect one. The reference "
        f"car has a factory",
        "limited-slip differential, so the truth is between — and quoting the "
        "open-diff number alone would have overstated the front-drive penalty by "
        "about 60%.",
    ]):
        s += D.text(60, 828 + 22 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, meta,
                f"both bounds [ASSUMED]; sampled at s = {s_axis[k]:.0f} m, where "
                "the open diff costs the axle the most")
    return s + V.foot(
        W, H,
        "Every wheel's longitudinal force is capped at its own capability in "
        "both cases. The open diff adds the 50/50 split constraint on top, which "
        "limits the driven pair to twice the weaker wheel.",
    )


class _Ax:
    def __init__(self, L, R, T, B, x0, x1, y0, y1):
        self.L, self.R, self.T, self.B = L, R, T, B
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1

    def x(self, v):
        return self.L + (self.R - self.L) * (np.asarray(v) - self.x0) / (self.x1 - self.x0)

    def y(self, v):
        return self.B - (self.B - self.T) * (np.asarray(v) - self.y0) / (self.y1 - self.y0)

    def pts(self, xs, ys):
        return list(zip(self.x(xs), self.y(ys)))


def _ticks(ax, xs, ys, fx="{:g}", fy="{:g}"):
    return ([(fx.format(v), float(ax.x(v))) for v in xs],
            [(fy.format(v), float(ax.y(v))) for v in ys])


def utilisation_card(traces, results, meta, corner_bounds) -> str:
    W, H = 1520, 700
    s_axis = traces["s"]
    s_max = float(s_axis.max())
    c0, c1 = corner_bounds
    s = V.head(
        W, H,
        "Episode 6 - friction-circle usage along the corner",
        f"Rear-wheel drive {results['rwd']['time_s']:.2f} s, front-wheel drive "
        f"{results['fwd']['time_s']:.2f} s over {s_max:.0f} m. Shaded band is the "
        f"corner; everything right of it is the exit straight.",
    )

    for i, (drive, title) in enumerate((("rwd", "A - Rear-wheel drive"),
                                        ("fwd", "B - Front-wheel drive"))):
        ax = _Ax(100 + i * 520, 520 + i * 520, 150, 440, 0, s_max, 0, 1.15)
        s += D.panel_title(100 + i * 520, 132, title)
        s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 4, 4)
        xt, yt = _ticks(ax, [0, 100, 200, 300], [0, 0.5, 1.0],
                        fx="{:.0f}", fy="{:.1f}")
        s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "distance along the track (m)",
                   "fraction of the tire used", xt, yt)
        s += (f'<rect x="{float(ax.x(c0)):.1f}" y="{ax.T}" '
              f'width="{float(ax.x(c1)-ax.x(c0)):.1f}" height="{ax.B-ax.T}" '
              f'fill="{V.AMB}" opacity="0.09"/>')
        s += (f'<line x1="{ax.L}" y1="{float(ax.y(1.0)):.1f}" x2="{ax.R}" '
              f'y2="{float(ax.y(1.0)):.1f}" stroke="{V.MUT}" stroke-width="1" '
              f'stroke-dasharray="3 5"/>')
        s += D.text(ax.L + 8, float(ax.y(1.0)) - 6, "nothing left", V.MUT, 10)
        for corner, colour, label in (("fr", V.COR, "outside front"),
                                      ("fl", V.AMB, "inside front"),
                                      ("rr", V.TEAL, "outside rear"),
                                      ("rl", V.VIO, "inside rear")):
            u = traces[f"{drive}_utilisation_{corner}"]
            s += (f'<path d="{V.path(ax.pts(s_axis, u))}" fill="none" '
                  f'stroke="{colour}" stroke-width="2"/>')
            if i == 1:
                s += D.text(ax.R + 10, ax.T + 20 + 20 * ("fr fl rr rl".split()
                                                         .index(corner)),
                            label, colour, 11)

    c = _Ax(1140, 1420, 150, 440, 0, s_max, 20, 50)
    s += D.panel_title(1140, 132, "C - Speed")
    s = V.grid(s, c.L, c.R, c.T, c.B, 4, 3)
    xt, yt = _ticks(c, [0, 150, 300], [20, 30, 40, 50], fx="{:.0f}", fy="{:.0f}")
    s = V.axes(s, c.L, c.R, c.T, c.B, "distance (m)", "speed (m/s)", xt, yt)
    s += (f'<rect x="{float(c.x(c0)):.1f}" y="{c.T}" '
          f'width="{float(c.x(c1)-c.x(c0)):.1f}" height="{c.B-c.T}" '
          f'fill="{V.AMB}" opacity="0.09"/>')
    for drive, colour, lab in (("rwd", V.TEAL, "RWD"), ("fwd", V.COR, "FWD")):
        s += (f'<path d="{V.path(c.pts(s_axis, traces[f"{drive}_speed"]))}" '
              f'fill="none" stroke="{colour}" stroke-width="2.2"/>')
        s += D.text(c.R - 6, float(c.y(traces[f"{drive}_speed"][-1]))
                    + (14 if drive == "fwd" else -8), lab, colour, 11, "end")
    s += D.text(c.L + 10, c.B - 14, "identical until the exit", V.MUT, 10.5)

    s += D.text(100, 500,
                f"Through the corner both cars are at the limit -- every wheel "
                f"near 1.0 -- and the lines are nearly identical. The difference "
                f"is entirely on the exit, where the front-wheel-drive car's front "
                f"tires must steer and accelerate at once and reach "
                f"{max(results['fwd']['mean_utilisation_on_exit']['fl'], results['fwd']['mean_utilisation_on_exit']['fr']):.0%} "
                f"average usage against the rear-drive car's "
                f"{max(results['rwd']['mean_utilisation_on_exit']['fl'], results['rwd']['mean_utilisation_on_exit']['fr']):.0%}.",
                V.MUT, 11.5)
    s += D.text(100, 522,
                f"Caveat on record: the rear-drive solve reported "
                f"'{results['rwd']['solver_status']}'. Its objective was stable "
                f"and its envelope occupancy zero, so it is converged in practice, "
                f"but it is not a clean exit and the {results['time_delta_s']:+.2f} s "
                f"gap should be read as approximate.", V.MUT, 11.5)
    s += _stamp(H - 40, meta, DIFF_STAMP)
    return s + V.foot(
        W, H,
        "Both solves constrain slip angle to +/-12 deg and every wheel's "
        "longitudinal force to its own capability. Envelope occupancy is zero in "
        "both, so neither answer relies on extrapolating the tire model.",
    )


__all__ = ["utilisation_figure", "power_figure", "whole_track_figure",
           "overlay_figure", "along_the_corner_figure", "differential_figure",
           "utilisation_card"]
