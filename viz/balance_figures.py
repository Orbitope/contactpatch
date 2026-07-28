"""Episode 7 figures — where the mass sits, and what it costs.

``balance_figure``
    The pictorial hero. Five cars seen from above, the centre of mass drawn as a
    dot that actually moves along the wheelbase, contact patches sized by static
    load, with lap time and understeer gradient under each.
``line_shift_figure``
    The corner from above with the solved line at each balance overlaid, so the
    apex migration is a picture rather than a column of percentages.
``balance_card``
    The technical panels: lap time, understeer gradient, apex position and brake
    release against front mass fraction, both drivetrains.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V
from physics.track import CORNER_ARC as T_ARC, ENTRY_STRAIGHT as T_ENTRY

CORNERS = ("fl", "fr", "rl", "rr")

#: Below this, a lap-time difference is not reportable — the size of the
#: convergence uncertainty an unconverged solve carries (FINDINGS F39).
NOISE_FLOOR_S = 0.02


def _stamp(y: float, meta, extra: str = "") -> str:
    v, t = meta["vehicle"], meta["tire"]
    bits = [
        f"[MEASURED] double-track model + optimal control + {t['file']}",
        "offsets removed" if t["offsets_removed"] else "as shipped",
        f"m {v['mass']:.0f} kg held fixed",
        f"{meta['n_nodes']} nodes",
        "front mass fraction [ASSUMED] outside 0.53-0.56",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  -  ".join(bits), V.MUT, 9.5)


def _row(results, drive, ff):
    return results["rows"][f"{drive}_{ff:.2f}"]


def _fmt_delta(d: float) -> tuple[str, str]:
    """A signed time, or an honest 'no difference' when it is under the floor."""
    if abs(d) < NOISE_FLOOR_S:
        return "no measurable", "difference"
    return f"{d:+.2f} s", "front drive costs" if d > 0 else "front drive gains"


def balance_figure(results, meta) -> str:
    """Five cars, the centre of mass drawn where it actually is.

    The whole episode is about one dot moving along the wheelbase. A reader who
    has never heard of a weight distribution can see the dot move, see the front
    contact patches grow, and read the lap time underneath.
    """
    fracs = results["front_fractions"]
    lo, hi = results["sourced_range"]
    W, H = 1480, 1130
    s = V.head(
        W, H,
        "Where the mass sits, and what it costs",
        "The same car five times: same mass, same tires, same wheelbase, same "
        "corner. The only thing that moves is the centre of gravity along the "
        "wheelbase — the dot. Contact-patch size is the static load each tire "
        "carries.",
    )
    s += D.text(40, 92,
                f"Only {lo:.2f}-{hi:.2f} front describes the reference car. The "
                f"rest are hypothetical cars, which is the point of a sweep.",
                V.MUT, 11.5)

    col = 1340 / len(fracs)
    # "Fastest" only means something above the noise floor. Collect every balance
    # whose time is within the floor of the best CONVERGED time and call them all
    # tied -- an earlier version marked a single winner 0.012 s clear of the next
    # point and printed "+-0.013" next to a rival that was actually quicker but
    # unconverged. Rule 5: below the floor it is no measurable difference.
    tied = {}
    for drive in ("rwd", "fwd"):
        conv = [(ff, _row(results, drive, ff)["time_s"]) for ff in fracs
                if _row(results, drive, ff)["converged"]]
        pool = conv or [(ff, _row(results, drive, ff)["time_s"]) for ff in fracs]
        best_t = min(t for _, t in pool)
        tied[drive] = {ff for ff, t in pool if t - best_t < NOISE_FLOOR_S}
        results.setdefault("_best_time_converged", {})[drive] = best_t
    for i, ff in enumerate(fracs):
        cx = 110 + col * (i + 0.5)
        inside_src = lo <= ff <= hi
        s += D.text(cx, 148, f"{100*ff:.0f} : {100*(1-ff):.0f}", V.FG, 17,
                    "middle", weight="600")
        s += D.text(cx, 168,
                    "the reference car" if inside_src else "hypothetical",
                    V.AMB if inside_src else V.MUT, 10.5, "middle")

        # static load per tire is what sets the patch sizes here
        f_share, r_share = ff / 2.0, (1.0 - ff) / 2.0
        biggest = max(f_share, r_share)
        loads = tuple(x / biggest for x in
                      (f_share, f_share, r_share, r_share))
        s += D.car_plan(cx, 360, length=176, width=78, wheel_len=40, wheel_w=17,
                        loads=loads, body=V.MUT)
        # Axle reference lines. The centre of gravity moves 25% of the wheelbase
        # across this sweep, which is 644 mm on a real car and only 26 px here --
        # true to scale and genuinely hard to see. Drawing the axles it moves
        # between, and printing the distance, makes it legible without
        # exaggerating the movement (rule 10: no cheating the geometry).
        for ax_y, lab in ((360 - 176 * 0.30, "front axle"),
                          (360 + 176 * 0.30, "rear axle")):
            s += (f'<line x1="{cx-62:.1f}" y1="{ax_y:.1f}" x2="{cx+62:.1f}" '
                  f'y2="{ax_y:.1f}" stroke="{V.GRID}" stroke-width="1.2" '
                  f'stroke-dasharray="3 4"/>')
            if i == 0:
                s += D.text(cx - 108, ax_y + 4, lab, V.MUT, 9.5, "end")
        com_y = 360 + 176 * 0.30 * (1.0 - 2.0 * ff)
        s += (f'<circle cx="{cx:.1f}" cy="{com_y:.1f}" r="9" fill="{V.AMB}"/>')
        s += (f'<circle cx="{cx:.1f}" cy="{com_y:.1f}" r="15" fill="none" '
              f'stroke="{V.AMB}" stroke-width="1.4" opacity="0.6"/>')
        wb = meta["vehicle"]["wheelbase"]
        s += D.text(cx, 474, f"{1000 * wb * (1.0 - ff):.0f} mm", V.AMB, 11,
                    "middle", mono=True)
        s += D.text(cx, 488, "behind the front axle", V.MUT, 9, "middle")
        if i == 0:
            s += D.text(cx - 108, com_y + 4, "centre of", V.AMB, 10.5, "end")
            s += D.text(cx - 108, com_y + 17, "gravity", V.AMB, 10.5, "end")
        # static load per tire, since the patch sizes alone are a subtle cue
        w_kn = meta["vehicle"]["mass"] * 9.80665 / 1000.0
        s += D.text(cx - 62, 330, f"{0.5*ff*w_kn:.2f}", V.MUT, 10, "end",
                    mono=True)
        s += D.text(cx + 62, 330, f"{0.5*ff*w_kn:.2f}", V.MUT, 10, "start",
                    mono=True)
        s += D.text(cx - 62, 400, f"{0.5*(1-ff)*w_kn:.2f}", V.MUT, 10, "end",
                    mono=True)
        s += D.text(cx + 62, 400, f"{0.5*(1-ff)*w_kn:.2f}", V.MUT, 10, "start",
                    mono=True)
        if i == 0:
            s += D.text(cx - 108, 272, "kN per tire,", V.MUT, 9, "end")
            s += D.text(cx - 108, 284, "standing still", V.MUT, 9, "end")

        k = results["K_deg_per_g"][f"{ff:.2f}"]
        s += D.text(cx, 520, f"K {k:+.2f} deg/g", V.VIO, 13, "middle",
                    weight="600", mono=True)
        s += D.text(cx, 537, "understeer gradient", V.MUT, 9.5, "middle")

        for j, (drive, label, colour) in enumerate(
                (("rwd", "rear drive", V.TEAL),
                 ("fwd", "front drive", V.COR))):
            r = _row(results, drive, ff)
            y = 590 + j * 62
            if i == 0:
                s += D.text(58, y, label, colour, 12, weight="600")
            is_tied = ff in tied[drive]
            gap = r["time_s"] - results["_best_time_converged"][drive]
            s += D.text(cx, y, f"{r['time_s']:.3f} s",
                        colour if is_tied else V.MUT, 16 if is_tied else 14,
                        "middle", weight="600" if is_tied else "normal",
                        mono=True)
            if is_tied:
                note = "fastest" if len(tied[drive]) == 1 else "fastest (tied)"
            else:
                note = f"{gap:+.3f} s"
            s += D.text(cx, y + 17, note, colour if is_tied else V.MUT, 10,
                        "middle")
            if not r["converged"]:
                s += D.text(cx, y + 31, "not converged", V.MUT, 9, "middle",
                            style="italic")

    s += D.rule(60, 730, 1420, V.GRID)
    k0 = results["K_deg_per_g"][f"{fracs[0]:.2f}"]
    k1 = results["K_deg_per_g"][f"{fracs[-1]:.2f}"]
    tie_r = ", ".join(f"{100*f:.0f}%" for f in sorted(tied["rwd"]))
    tie_f = ", ".join(f"{100*f:.0f}%" for f in sorted(tied["fwd"]))
    for i, line in enumerate([
        f"The understeer gradient does exactly what Episode 3 says it should: "
        f"{k0:+.2f} deg/g with the mass at the back, {k1:+.2f} with it at the "
        f"front. Negative is",
        f"oversteer. That is a {k1-k0:.2f} deg/g swing, against a 0.2 deg/g "
        f"real-world measurement floor — the largest, cleanest effect in this "
        f"sweep by far.",
        "",
        f"The LAP TIME is a different story. Within the {NOISE_FLOOR_S:.2f} s "
        f"floor these solves support, front drive is tied fastest at {tie_f}, and "
        f"rear drive's converged points ({tie_r}) cannot be",
        "separated at all. Only the extremes are clearly slower, and only for "
        "front drive: at 40% front it loses 0.11 s, because a front-drive car "
        "with no weight on its",
        "driven wheels cannot put the power down.",
        "",
        "So 50:50 is a marketing number, but not for the reason you would expect. "
        "It is not that the optimum sits somewhere else — it is that across most",
        "of the range there is no measurable optimum at all. Balance changes how "
        "the car FEELS, dramatically. It barely changes how fast it is.",
        "",
        "Yaw inertia is held fixed across all five. That is not what happens when "
        "you move a real engine — that changes balance and polar moment together",
        "— and separating them is what Episode 8 is for. Read this as the effect "
        "of balance alone.",
    ]):
        s += D.text(60, 766 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, meta, "yaw inertia held FIXED — see Episode 8")
    return s + V.foot(
        W, H,
        "Static load sets the contact-patch sizes; the centre-of-gravity dot is "
        "drawn at its true position along the wheelbase. Lap times come from "
        "minimum-time solves on the Episode 4 corner with an ideal differential.",
    )


def line_shift_figure(results, meta, traces, track) -> str:
    """The line does NOT move. The braking point does — and that is the finding.

    This figure used to be titled "the fast line moves when the weight moves" and
    was cropped to the corner, which is the one place nothing happens: all five
    rear-drive lines fit inside 30 cm of each other on an 8 m road, and the apex
    shifts about one percentage point. A reader looking at it saw five identical
    curves and no number, and was right to.

    What actually moves is where each car gets off the brakes, by nearly 12 m, and
    that happens on the entry straight — outside the old crop entirely. So the
    window now includes the braking zone, the braking points are marked, and the
    separation is quoted rather than left to the eye.
    """
    from .line_figures import track_backdrop

    fracs = results["front_fractions"]
    s_axis = np.asarray(traces["s"])
    c0, c1 = T_ENTRY, T_ENTRY + T_ARC
    ramp = [V.TEAL, V.GRN, V.AMB, V.COR, V.VIO]
    W, H = 1520, 1210
    s = V.head(
        W, H,
        "The line doesn't move. The braking point does.",
        "The same corner, solved five times with the centre of gravity in five "
        "different places. I expected the racing line to migrate. It barely "
        "does — what changes is how early the car has to slow down.",
    )

    def tag(drive, ff):
        return f"{drive}_{f'{ff:.2f}'.replace('.', '')}"

    # window now REACHES BACK into the braking zone, because that is where the
    # difference lives. The old crop started 30 m before the corner and cut it off.
    win_lo, win_hi = 20.0, c1 + 40.0
    for drive, title, L, R in (("rwd", "Rear-wheel drive", 60, 700),
                               ("fwd", "Front-wheel drive", 800, 1440)):
        back, to_px, scale = track_backdrop(track, win_lo, win_hi, L, R, 200, 690)
        s += D.panel_title(L, 168, title)
        s += back
        m = (s_axis >= win_lo) & (s_axis <= win_hi)
        seps = []
        for i, ff in enumerate(fracs):
            g = tag(drive, ff)
            n = np.asarray(traces[f"{g}_n"])
            seps.append(n[m])
            x, y = track.to_xy(s_axis[m], n[m])
            px, py = to_px(x, y)
            s += (f'<path d="{V.path(list(zip(px, py)))}" fill="none" '
                  f'stroke="{ramp[i % len(ramp)]}" stroke-width="2.4" '
                  f'opacity="0.95"/>')
            # the braking point, which is the thing that actually differs
            br = _row(results, drive, ff).get("brake_release_s")
            if br is not None:
                j = int(np.argmin(np.abs(s_axis - br)))
                bx, by = track.to_xy(np.array([s_axis[j]]), np.array([n[j]]))
                bpx, bpy = to_px(bx, by)
                s += (f'<circle cx="{float(bpx[0]):.1f}" cy="{float(bpy[0]):.1f}" '
                      f'r="6.5" fill="{V.BG}" stroke="{ramp[i % len(ramp)]}" '
                      f'stroke-width="2.6"/>')
        spread = float(np.max(np.max(seps, axis=0) - np.min(seps, axis=0)))
        s += D.text(L, 720, f"all five lines fit inside {100*spread:.0f} cm",
                    V.FG, 13, weight="600")
        s += D.text(L, 740, f"of each other, on an {2*track.half_width:.0f} m road "
                    f"— {100*spread/(2*track.half_width):.0f}% of the width",
                    V.MUT, 11.5)
        brs = [(_row(results, drive, ff).get("brake_release_s"), ff)
               for ff in fracs]
        brs = [(b, f) for b, f in brs if b is not None]
        if brs:
            lo_b, hi_b = min(brs)[0], max(brs)[0]
            s += D.text(L, 768,
                        f"but the braking points span {hi_b - lo_b:.1f} m",
                        V.AMB, 13, weight="600")
            s += D.text(L, 788, "(circles) — interpolated between nodes, not "
                        "snapped to one", V.MUT, 11.5)

    # Legend along the top, clear of both roads. Placed at W-250 it sat on the
    # front-drive panel's road surface.
    for i, ff in enumerate(fracs):
        x = 60 + i * 150
        s += (f'<line x1="{x}" y1="{140}" x2="{x+30}" y2="{140}" '
              f'stroke="{ramp[i % len(ramp)]}" stroke-width="3.2"/>')
        s += D.text(x + 38, 144, f"{100*ff:.0f}% front", ramp[i % len(ramp)], 12,
                    weight="600")

    s += D.rule(60, 826, W - 120, V.GRID)
    br_r = [(_row(results, "rwd", ff).get("brake_release_s"), ff) for ff in fracs]
    br_r = sorted((b, f) for b, f in br_r if b is not None)
    for i, line in enumerate([
        "I expected the racing line to migrate as the balance changed, and drew "
        "this figure to show it. It does not: across the whole 40-65% sweep the "
        "five lines stay within a hand's width",
        "of each other, and the apex moves about one percentage point. Cropped to "
        "the corner — which is how this figure was first drawn — there is nothing "
        "to see, and nothing to see IS the result.",
        "",
        "What the solver changes instead is the braking point. Rear drive: "
        + ", ".join(f"{100*f:.0f}% at {b:.1f} m"
                    for b, f in sorted(br_r, key=lambda t: t[1]))
        + ". From 47% upward that",
        "climbs monotonically, about 3.3 m per design step — a nose-heavy car "
        "brakes later because its front tires have more load to brake against. The "
        "40% car breaks the pattern, braking later than 47%.",
        "",
        "These braking points are INTERPOLATED between nodes. Read straight off "
        "the 100-node grid they landed on nodes 16, 17, 17, 18 and 19 — quantised "
        "to 3.97 m, with the whole span exactly three",
        "grid steps, which is a grid artefact wearing a measurement's clothes. That "
        "is FINDINGS F47's apex defect in a different variable, and the fix is the "
        "same: interpolate onto the crossing rather than",
        "snapping to the nearest node. Interpolated, the five sit at 16.7, 17.4, "
        "17.9, 18.1 and 19.1 node-widths and the effect is no longer a staircase.",
        "",
        "Worth holding against Episode 10: the SOLVER moves its line by about "
        "30 cm across these five cars. The LEARNED driver, asked about the same "
        "five, moves its line by 452 cm.",
        "A perfect driver absorbs the design change and re-optimises around it; a "
        "real one shows you the car in the shape of its line. That gap is "
        "FINDINGS F65.",
    ]):
        s += D.text(60, 858 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, meta)
    return s + V.foot(
        W, H,
        "Window reaches back into the braking zone on purpose: the old crop began "
        "30 m before the corner and cut off the only thing that differs. Circles "
        "mark where each car releases the brakes.",
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


def balance_card(results, meta) -> str:
    fracs = np.array(results["front_fractions"])
    lo, hi = results["sourced_range"]
    W, H = 1520, 790
    s = V.head(
        W, H,
        "Episode 7 - front mass fraction sweep",
        "Lap time, understeer gradient, apex position and brake release against "
        "where the mass sits. The shaded band is the range the reference car's "
        "own parameter sheet supports; everything outside it is a hypothetical.",
    )

    panels = [
        ("A - Lap time", "time (s)",
         lambda d: [_row(results, d, ff)["time_s"] for ff in fracs], 100, 420),
        ("B - Understeer gradient", "K (deg/g)",
         None, 560, 880),
        ("C - Apex position", "% through the corner",
         lambda d: [100 * _row(results, d, ff)["apex_fraction_through_corner"]
                    for ff in fracs], 1020, 1340),
    ]
    for title, ylab, get, L, R in panels:
        if get is None:
            ks = [results["K_deg_per_g"][f"{ff:.2f}"] for ff in fracs]
            y0, y1 = min(ks) - 0.05, max(ks) + 0.05
        else:
            vals = get("rwd") + get("fwd")
            pad = 0.05 * (max(vals) - min(vals) or 1.0)
            y0, y1 = min(vals) - pad, max(vals) + pad
        ax = _Ax(L, R, 150, 460, fracs.min() - 0.01, fracs.max() + 0.01, y0, y1)
        s += D.panel_title(L, 132, title)
        s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 4, 4)
        xt = [(f"{100*v:.0f}", float(ax.x(v))) for v in fracs]
        yt = [(f"{v:.2f}", float(ax.y(v))) for v in np.linspace(y0, y1, 4)]
        s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "front mass fraction (%)", ylab,
                   xt, yt)
        s += (f'<rect x="{float(ax.x(lo)):.1f}" y="{ax.T}" '
              f'width="{float(ax.x(hi) - ax.x(lo)):.1f}" height="{ax.B-ax.T}" '
              f'fill="{V.AMB}" opacity="0.10"/>')
        if get is None:
            ks = [results["K_deg_per_g"][f"{ff:.2f}"] for ff in fracs]
            s += (f'<path d="{V.path(ax.pts(fracs, ks))}" fill="none" '
                  f'stroke="{V.VIO}" stroke-width="2.4"/>')
            for xv, yv in zip(fracs, ks):
                s += (f'<circle cx="{float(ax.x(xv)):.1f}" '
                      f'cy="{float(ax.y(yv)):.1f}" r="3.5" fill="{V.VIO}"/>')
        else:
            for drive, colour in (("rwd", V.TEAL), ("fwd", V.COR)):
                vals = get(drive)
                s += (f'<path d="{V.path(ax.pts(fracs, vals))}" fill="none" '
                      f'stroke="{colour}" stroke-width="2.2"/>')
                for xv, yv, ff in zip(fracs, vals, fracs):
                    conv = _row(results, drive, ff)["converged"]
                    s += (f'<circle cx="{float(ax.x(xv)):.1f}" '
                          f'cy="{float(ax.y(yv)):.1f}" r="3.5" '
                          f'fill="{colour if conv else V.BG}" '
                          f'stroke="{colour}" stroke-width="1.5"/>')

    # Report ties, not a single winner. argmin always names one point even when
    # the next is a millisecond behind, and after the re-solve both drivetrains
    # have two settings inside the floor of each other (rule 5).
    def _tied(drive):
        conv = [(f, _row(results, drive, f)["time_s"]) for f in fracs
                if _row(results, drive, f)["converged"]]
        best = min(t for _, t in conv)
        return [f for f, t in conv if t - best < NOISE_FLOOR_S]

    tr, tf = _tied("rwd"), _tied("fwd")
    fmt = lambda xs: " and ".join(f"{100*x:.0f}%" for x in sorted(xs))
    s += D.text(100, 556,
                "Hollow markers are solves that stopped on the iteration limit; "
                "their times are not evidence (FINDINGS F39). Filled markers "
                "converged cleanly.", V.MUT, 11.5)
    s += D.text(100, 578,
                f"Within the {NOISE_FLOOR_S:.2f} s these solves resolve, rear "
                f"drive is fastest at {fmt(tr)} front and front drive at "
                f"{fmt(tf)} — each wants the end of the range that loads the "
                f"wheels it drives.", V.MUT, 11.5)
    s += D.text(100, 600,
                f"Understeer gradient runs "
                f"{results['K_deg_per_g'][f'{fracs[0]:.2f}']:+.2f} to "
                f"{results['K_deg_per_g'][f'{fracs[-1]:.2f}']:+.2f} deg/g across the "
                f"same sweep, against a 0.2 deg/g measurement floor — five times "
                f"the resolution, where the lap times are barely one.",
                V.MUT, 11.5)
    s += D.text(100, 622,
                "Yaw inertia is held fixed, so this isolates balance. A real "
                "engine move would change polar moment too — Episode 8.",
                V.MUT, 11.5)
    s += _stamp(H - 40, meta)
    return s + V.foot(
        W, H,
        "Every solve constrains slip angle to +/-12 degrees. Absolute times are "
        "specific to this invented corner; the comparable quantities are the "
        "shape of each curve and where its optimum sits.",
    )


__all__ = ["balance_figure", "line_shift_figure", "balance_card"]
