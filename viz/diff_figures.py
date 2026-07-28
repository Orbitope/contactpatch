"""Episode 12 figures — what a differential actually does.

``mechanism_figure``
    The pictorial hero. Two cars seen from above in the same left-hand corner, one
    at part throttle and one at full, with an arrow on each driven wheel sized by
    the force it is carrying. At part throttle the outside arrow points BACKWARDS.
    You do not need to know what a slip ratio is to see that one wheel is being
    dragged while the other pushes, or which way that twists the car.
``decomposition_figure``
    The technical version: yaw moment against throttle for all three devices, with
    the crossover where each one changes its mind.
"""

from __future__ import annotations

import numpy as np

from . import diagram as D
from . import lib as V

COLOUR = {"open": V.TEAL, "lsd": V.AMB, "locked": V.COR}


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


def _stamp(y: float, r) -> str:
    return D.text(40, y, "  -  ".join([
        f"[MEASURED] double-track model, steady left corner R={r['corner_radius_m']:.0f} m, "
        f"a_y={r['a_y']:.1f} m/s2, v={r['exit_speed_ms']:.1f} m/s",
        "[ASSUMED] LSD torque bias 1.5:1, locking 0.5",
        "[LIKELY] track width",
        "RUNG 2 — mechanism and ordering only, not a real car (rule 15)",
    ]), V.MUT, 9.5)


def mechanism_figure(results) -> str:
    """Two cars, two throttle openings, opposite behaviour."""
    W, H = 1540, 960
    s = V.head(
        W, H,
        "Which wheel is in charge?",
        "The same welded differential, in the same left-hand corner, at two throttle "
        "openings. A differential resists the two driven wheels turning at different "
        "speeds — and which wheel is turning faster changes with the throttle.",
    )

    cases = (("part", results["part"], results["part_throttle_N"],
              "Part throttle", "The outside wheel travels further, so it turns "
              "faster. The device drags it back and pushes the inside wheel on.",
              "the car is twisted OUT of the corner"),
             ("full", results["full"], results["full_throttle_N"],
              "Full throttle", "The inside wheel has run out of grip and is "
              "spinning, so now IT is the faster one. Torque flows the other way, "
              "to the wheel that still grips.",
              "the car is twisted INTO the corner"))

    for i, (key, tag, demand, title, why, verdict) in enumerate(cases):
        L = 60 + i * 740
        r = tag["locked"]
        s += D.text(L, 152, title, V.FG, 18, weight="600")
        s += D.text(L, 176, f"{demand:.0f} N asked of the rear axle", V.MUT, 12)

        cx, cy = L + 250, 400
        # The car with its front wheels actually turned, so the panel shows a car in
        # a corner rather than a straight-ahead car with a caption claiming it is.
        s += D.car_plan(cx, cy, length=250, width=118, wheel_len=54, wheel_w=24,
                        steer_deg=14.0, loads=(0.55, 0.75, 0.55, 0.75),
                        body=V.MUT)
        s += D.arrow(cx, cy - 148, cx, cy - 186, V.MUT, 2.0, 9)
        s += D.text(cx, cy - 196, "travelling this way", V.MUT, 11, "middle")
        s += D.text(cx - 66, cy + 122, "inside", V.MUT, 11.5, "middle")
        s += D.text(cx + 66, cy + 122, "outside", V.MUT, 11.5, "middle")

        # Force arrows on the two driven wheels, scaled and signed.
        scale = 150.0 / 4100.0
        for lbl, force, dx in (("inside", r["inside_N"], -59),
                               ("outside", r["outside_N"], +59)):
            wx, wy = cx + dx, cy + 78
            length = force * scale
            colour = V.TEAL if force >= 0 else V.COR
            s += D.arrow(wx, wy, wx, wy - length, colour, 5.0, 14)
            s += D.text(wx + (18 if dx > 0 else -18), wy - length / 2,
                        f"{force:+.0f} N", colour, 13,
                        "start" if dx > 0 else "end", weight="600", mono=True)
            if force < 0:
                s += D.text(wx + (18 if dx > 0 else -18),
                            wy - length / 2 + 18, "dragged back", V.COR, 11,
                            "start" if dx > 0 else "end")

        # Which way the car is being twisted, DRAWN. A number and a sentence make
        # the reader do the work; an arc round the car does not.
        mz = r["mz"]
        import math as _m
        arc_r, colour = 168.0, (V.COR if mz < 0 else V.TEAL)
        a0, a1 = (-58.0, 58.0)
        if mz < 0:            # yawing right (out of a left corner): clockwise
            sweep, tip = 1, a1
        else:                 # yawing left: anticlockwise
            sweep, tip = 0, a0
        x0 = cx + arc_r * _m.sin(_m.radians(a0))
        y0 = cy - arc_r * _m.cos(_m.radians(a0))
        x1 = cx + arc_r * _m.sin(_m.radians(a1))
        y1 = cy - arc_r * _m.cos(_m.radians(a1))
        sx, sy = (x0, y0) if sweep == 1 else (x1, y1)
        ex, ey = (x1, y1) if sweep == 1 else (x0, y0)
        s += (f'<path d="M {sx:.1f},{sy:.1f} A {arc_r:.0f},{arc_r:.0f} 0 0 '
              f'{sweep} {ex:.1f},{ey:.1f}" fill="none" stroke="{colour}" '
              f'stroke-width="3.4" opacity="0.9"/>')
        tang = _m.radians(tip) + (_m.pi / 2 if sweep == 1 else -_m.pi / 2)
        s += D.arrow(ex - 14 * _m.cos(tang), ey - 14 * _m.sin(tang), ex, ey,
                     colour, 3.4, 15)
        s += D.text(cx, cy + arc_r + 34,
                    "twisted OUT of the corner" if mz < 0
                    else "twisted INTO the corner", colour, 12.5, "middle",
                    weight="600")

        yc = cy + 250
        s += D.text(L, yc, f"{mz:+.0f} N.m of yaw moment",
                    V.COR if mz < 0 else V.TEAL, 14, weight="600", mono=True)
        for li, line in enumerate(_wrap(why, 58)):
            s += D.text(L, yc + 28 + 20 * li, line, V.MUT, 12.5)

    s += D.rule(60, 790, W - 120, V.GRID)
    for i, line in enumerate([
        "This is one mechanism, not two. Torque flows from the faster-turning wheel "
        "to the slower one — that is all a limited-slip or welded differential does. "
        "Everything above follows",
        "from which wheel happens to be faster, and the throttle decides that. An "
        "earlier model of mine hard-coded the direction and could therefore only "
        "ever produce one of these two pictures.",
    ]):
        s += D.text(60, 824 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Arrow length is longitudinal force at the contact patch, to scale between "
        "the panels. Teal pushes the car forwards, red drags it back. Contact-patch "
        "shading is static load; the car is drawn nose-up and is turning left.",
    )


def _wrap(text: str, width: int) -> list[str]:
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def decomposition_figure(results) -> str:
    """Yaw moment against throttle, all three devices, with the crossover."""
    W, H = 1500, 940
    s = V.head(
        W, H,
        "The throttle decides which way it steers you",
        "Yaw moment against how much force the driver asks of the rear axle, in one "
        "steady corner. Below the crossing a locking differential pushes the car "
        "wide; above it, the same device turns the car in.",
    )

    dem = np.array(results["demand_sweep"])
    series = {d: np.array([p["mz"] for p in results["sweeps"][d]])
              for d in results["devices"]}
    lo = float(min(v.min() for v in series.values())) - 150
    hi = float(max(v.max() for v in series.values())) + 150

    ax = _Ax(150, 900, 190, 620, 0.0, float(dem.max()), lo, hi)
    s += D.panel_title(150, 168, "Yaw moment against throttle")
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 5, 4)
    xt = [(f"{v:.0f}", float(ax.x(v))) for v in (0, 1500, 3000, 4500, 6000)]
    yt = sorted({0.0, lo + 0.02 * (hi - lo), hi - 0.02 * (hi - lo),
                 0.5 * lo, 0.5 * hi})
    yt = [(f"{v:+.0f}", float(ax.y(v))) for v in yt]
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B,
               "force asked of the rear axle (N)",
               "yaw moment (N.m)   negative = pushed wide", xt, yt)
    # the zero line is the whole story
    s += (f'<line x1="{ax.L}" y1="{float(ax.y(0.0)):.1f}" x2="{ax.R}" '
          f'y2="{float(ax.y(0.0)):.1f}" stroke="{V.FG}" stroke-width="1.4" '
          f'stroke-dasharray="6 5" opacity="0.6"/>')
    s += D.text(ax.L + 8, float(ax.y(0.0)) - 10, "no effect either way", V.MUT, 11)
    s += D.text(ax.R - 8, ax.T + 18, "turns the car IN", V.TEAL, 11.5, "end",
                weight="600")
    s += D.text(ax.R - 8, ax.B - 12, "pushes the car WIDE", V.COR, 11.5, "end",
                weight="600")

    for d in results["devices"]:
        y = series[d]
        s += (f'<path d="{V.path(ax.pts(dem, y))}" fill="none" '
              f'stroke="{COLOUR[d]}" stroke-width="3"/>')
        # Mark where the device CHANGES ITS MIND: negative to positive. The first
        # sign change is at zero throttle, where it merely departs from doing
        # nothing, and marking that says nothing at all.
        cross = np.where((y[:-1] < 0.0) & (y[1:] >= 0.0))[0]
        for c in cross[:1]:
            # linear interpolation onto the crossing, so the dot sits on the line
            x0v, x1v, y0v, y1v = dem[c], dem[c + 1], y[c], y[c + 1]
            xv = float(x0v + (x1v - x0v) * (-y0v) / (y1v - y0v))
            s += (f'<circle cx="{float(ax.x(xv)):.1f}" '
                  f'cy="{float(ax.y(0.0)):.1f}" r="6" fill="{V.BG}" '
                  f'stroke="{COLOUR[d]}" stroke-width="2.5"/>')
            s += D.text(float(ax.x(xv)), float(ax.y(0.0)) - 16,
                        f"changes its mind at {xv:.0f} N", COLOUR[d], 11.5,
                        "middle", weight="600")

    ly = 210
    s += D.text(940, ly - 30, "the three devices", V.FG, 15, weight="600")
    for i, d in enumerate(results["devices"]):
        y = ly + i * 116
        p, f = results["part"][d], results["full"][d]
        s += (f'<line x1="940" y1="{y-5}" x2="982" y2="{y-5}" '
              f'stroke="{COLOUR[d]}" stroke-width="3.4"/>')
        s += D.text(994, y, results["labels"][d], COLOUR[d], 13.5, weight="600")
        s += D.text(940, y + 24,
                    f"part throttle  {p['mz']:+7.0f} N.m", V.MUT, 12, mono=True)
        s += D.text(940, y + 42,
                    f"full throttle  {f['mz']:+7.0f} N.m", V.MUT, 12, mono=True)
        s += D.text(940, y + 64,
                    f"delivers {f['delivered_N']:.0f} of "
                    f"{results['full_throttle_N']:.0f} N", V.MUT, 12, mono=True)

    s += D.rule(150, 672, W - 300, V.GRID)
    for i, line in enumerate([
        "An open differential is the flat line: it feeds both wheels equally and "
        "resists nothing, so it has no handling effect to have — and it pays for "
        "that by delivering only",
        f"{results['full']['open']['delivered_N']:.0f} N of the "
        f"{results['full_throttle_N']:.0f} N asked for, because it is limited by "
        "twice the weaker wheel. The other two recover that force, and the price is "
        "a car that steers itself.",
    ]):
        s += D.text(150, 706 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Circles mark where each device crosses from pushing wide to turning in. "
        "One steady corner and one car: rank ordering and the two signs are the "
        "result, the magnitudes are illustrative (rules 6 and 15).",
    )
