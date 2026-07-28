"""Episode 3 figures — understeer, drawn as a car rather than as a slope.

``understeer_figure``
    What understeer *is*, using actual wheels: the front axle sliding at a bigger
    angle than the rear, and what that costs you in steering. The Ep 3 hero.
``steady_state_card``
    The three analytical panels — understeer angle against lateral g, slip angles
    against lateral g, and the gradient against weight distribution.

Both carry a provenance stamp (CLAUDE.md rule 3).
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V


def _stamp(y: float, backend, extra: str = "") -> str:
    p = backend.tire.provenance
    v = backend.params
    bits = [
        f"[MEASURED] bicycle model + {p['file']}",
        "offsets removed" if p["offsets_removed"] else "as shipped",
        f"m {v.mass:.0f} kg · L {v.wheelbase:.3f} m · {v.front_mass_fraction:.0%} front"
        f" · h {v.com_height:.3f} m",
        "[SOURCED] RV-1 parameters, vehicle-reference-parameters.md §1",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  ·  ".join(bits), V.MUT, 9.5)


def _pick(points, target_g):
    return min(points, key=lambda p: abs(p.a_y_g - target_g))


# ---------------------------------------------------------------------------


def understeer_figure(backend, points, k, radius) -> str:
    """Two cars on the same circle, one cruising and one at the limit."""
    slow = _pick(points, 0.20)
    fast = max(points, key=lambda p: p.a_y_g)

    W, H = 1480, 1000
    s = V.head(
        W, H,
        "What understeer actually is",
        f"The same car on the same {radius:.0f} m circle, driven gently and then "
        f"as hard as it will go. Nothing about the car changes — only how fast it "
        f"is going round.",
    )

    for i, (pt, title) in enumerate(((slow, "Cruising"), (fast, "At the limit"))):
        cx = 330 + i * 700
        cy = 372
        # The car's heading is not the direction it travels: body sideslip is the
        # difference, and it is what makes the nose point into the corner at speed.
        s += D.panel_title(cx - 250, 150, f"{title} — {pt.a_y_g:.2f} g",
                           f"{pt.speed:.1f} m/s ({pt.speed*3.6:.0f} km/h)")

        # direction of travel, fixed and vertical in both panels
        s += D.arrow(cx, cy + 226, cx, cy - 226, V.MUT, 1.8, 10, dash="5 5")
        s += D.text(cx, cy - 238, "direction the car is travelling", V.MUT, 10.5,
                    "middle")

        # ISO -> screen: a left turn is a POSITIVE steer angle in the physics
        # and must draw anticlockwise. See viz.diagram.screen_deg.
        s += D.car_plan(cx, cy, steer_deg=D.screen_deg(pt.steer_deg),
                        heading_deg=D.screen_deg(-pt.sideslip_deg), heading=150,
                        loads=(0.55,) * 4)

        # Slip angle at each axle, drawn as a bar as well as written, because
        # the difference between them IS the understeer and at 0.2 g it is
        # 0.03 deg — invisible as a wheel angle, obvious as a bar.
        span = max(abs(math.degrees(fast.alpha_f)), abs(math.degrees(fast.alpha_r)))
        for label, alpha, ay, colour in (("front", pt.alpha_f, cy - 62, V.AMB),
                                         ("rear", pt.alpha_r, cy + 62, V.TEAL)):
            deg = abs(math.degrees(alpha))
            w = 150 * deg / span
            s += D.text(cx + 150, ay - 14, f"{label} tires sliding", V.MUT, 11)
            s += (f'<rect x="{cx+150}" y="{ay-6}" width="{max(w,1):.1f}" '
                  f'height="13" rx="3" fill="{colour}" opacity="0.85"/>')
            s += D.text(cx + 156 + max(w, 1), ay + 5, f"{deg:.2f}°", colour, 12.5,
                        weight="600", mono=True)

        # Sideslip: NEGATIVE beta means the nose points into the corner. Saying
        # "points into the corner by -2.03 deg" is the kind of label that reads
        # fine to the author and backwards to everyone else.
        into = -pt.sideslip_deg
        s += D.text(cx - 250, cy + 300, "steering angle", V.MUT, 11)
        s += D.text(cx - 250, cy + 322, f"{pt.steer_deg:.1f}°", V.FG, 17,
                    weight="600", mono=True)
        gap = abs(math.degrees(pt.alpha_f)) - abs(math.degrees(pt.alpha_r))
        s += D.text(cx - 70, cy + 300, "front slides more than rear by", V.MUT, 11)
        s += D.text(cx - 70, cy + 322, f"{gap:.2f}°", V.AMB, 17,
                    weight="600", mono=True)
        s += D.text(cx + 120, cy + 300,
                    "nose points " + ("into" if into > 0 else "out of")
                    + " the corner by", V.MUT, 11)
        s += D.text(cx + 120, cy + 322, f"{abs(into):.1f}°", V.VIO, 17,
                    weight="600", mono=True)

    s += D.rule(60, 720, 1420, V.GRID)

    s += D.panel_title(60, 762, "Understeer is the gap between those two numbers",
                       None)
    lines = [
        "A cornering tire only makes grip by sliding slightly — that is Episode 1. "
        "So every axle runs at some slip angle.",
        "**Understeer means the front axle has to slide more than the rear** to hold "
        "the same corner. You feel it as needing",
        "more steering than the corner geometrically requires, and as the car running "
        "wide when you ask for more.",
        "",
        f"Measured on this car: about {k:.1f}° of extra steering per extra g "
        "(0.1-0.3 across the uncertainty in the car's own numbers). A real road",
        "car is 1.8-5.5. Ours is nearly neutral, and that is the model telling "
        "the truth about itself — a two-wheeled car cannot lean on its",
        "outside tires, and that is where most of a real car's understeer comes "
        "from.",
    ]
    for i, line in enumerate(lines):
        bold = line.startswith("**")
        s += D.text(60, 796 + 23 * i, line.replace("**", ""),
                    V.FG if bold else V.MUT, 12.5,
                    weight="600" if bold else "normal")

    s += _stamp(H - 40, backend,
                f"skidpad radius {radius:.0f} m [ASSUMED]  ·  understeer gradient "
                f"fitted over |a_y| ≤ 0.5 g [SOURCED definition, §4]")
    return s + V.foot(
        W, H,
        "A car that understeers is not broken. It is a car whose front tires give "
        "up first — which is what almost every manufacturer deliberately builds, "
        "because running wide is recoverable and spinning is not.",
    )


# ---------------------------------------------------------------------------


class _Ax:
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
    return ([(fx.format(v), ax.x(v)) for v in xs],
            [(fy.format(v), ax.y(v)) for v in ys])


def steady_state_card(backend, points, k, max_g, k_vs_front, analytic,
                      radius) -> str:
    W, H = 1520, 620
    s = V.head(
        W, H,
        "D3 — Steady-state handling",
        f"Constant-radius skidpad, {radius:.0f} m. Understeer gradient "
        f"K = {k:.3f} deg/g, maximum lateral acceleration {max_g:.3f} g.",
    )
    ay = np.array([p.a_y_g for p in points])
    und = np.array([p.understeer_angle_deg for p in points])

    # -- A: the understeer curve -------------------------------------------
    a = _Ax(100, 570, 130, 470, 0, 1.1, 0, 2.0)
    s += D.panel_title(100, 112, "A · Extra steering vs cornering force")
    s = V.grid(s, a.L, a.R, a.T, a.B, 5, 4)
    xt, yt = _ticks(a, [0, 0.25, 0.5, 0.75, 1.0], [0, 0.5, 1.0, 1.5, 2.0],
                    fx="{:.2f}", fy="{:.1f}")
    s = V.axes(s, a.L, a.R, a.T, a.B, "lateral acceleration (g)",
               "steer − Ackermann (deg)", xt, yt)
    s += (f'<path d="{V.path(a.pts(ay, und))}" fill="none" stroke="{V.COR}" '
          f'stroke-width="2.5"/>')
    fit_x = np.array([0.0, 0.5])
    s += (f'<path d="{V.path(a.pts(fit_x, k * fit_x))}" fill="none" '
          f'stroke="{V.AMB}" stroke-width="1.8" stroke-dasharray="6 4"/>')
    s += (f'<line x1="{a.x(0.5):.1f}" y1="{a.T}" x2="{a.x(0.5):.1f}" y2="{a.B}" '
          f'stroke="{V.MUT}" stroke-width="1" stroke-dasharray="3 5"/>')
    s += D.text(a.x(0.5) + 6, a.T + 14, "fit window ends", V.MUT, 10)
    s += D.text(a.L + 14, a.T + 22, f"K = {k:.3f} deg/g", V.AMB, 13, weight="600")
    s += D.text(a.L + 14, a.T + 40, "slope of the dashed line", V.MUT, 10.5)
    s += D.text(a.R - 8, a.B - 12, "steepens sharply at the limit", V.MUT, 10.5,
                "end")

    # -- B: slip angles -----------------------------------------------------
    b = _Ax(660, 1000, 130, 470, 0, 1.1, 0, 9)
    s += D.panel_title(660, 112, "B · Which axle is working harder")
    s = V.grid(s, b.L, b.R, b.T, b.B, 5, 3)
    xt, yt = _ticks(b, [0, 0.5, 1.0], [0, 3, 6, 9], fx="{:.1f}", fy="{:.0f}")
    s = V.axes(s, b.L, b.R, b.T, b.B, "lateral acceleration (g)",
               "slip angle (deg)", xt, yt)
    for arr, colour, label in (
        (np.abs(np.degrees([p.alpha_f for p in points])), V.AMB, "front"),
        (np.abs(np.degrees([p.alpha_r for p in points])), V.TEAL, "rear"),
    ):
        s += (f'<path d="{V.path(b.pts(ay, arr))}" fill="none" stroke="{colour}" '
              f'stroke-width="2.5"/>')
        s += D.text(b.R - 6, b.y(arr[-1]) - 8, label, colour, 11.5, "end")
    s += D.text(b.L + 12, b.B - 14,
                "the gap between them is the understeer", V.MUT, 10.5)

    # -- C: K vs weight distribution ----------------------------------------
    c = _Ax(1090, 1420, 130, 470, 0.40, 0.64, -1.0, 2.0)
    s += D.panel_title(1090, 112, "C · Where the weight sits")
    s = V.grid(s, c.L, c.R, c.T, c.B, 4, 3)
    xt, yt = _ticks(c, [0.42, 0.50, 0.58], [-1, 0, 1, 2],
                    fx="{:.2f}", fy="{:+.0f}")
    s = V.axes(s, c.L, c.R, c.T, c.B, "fraction of weight on the front",
               "K (deg/g)", xt, yt)
    s += (f'<rect x="{c.L}" y="{c.y(2.0):.1f}" width="{c.R-c.L}" '
          f'height="{c.y(1.8)-c.y(2.0):.1f}" fill="{V.GRN}" opacity="0.18"/>')
    s += D.text(c.L + 10, c.y(1.9) + 4, "real road cars start here", V.GRN, 10)
    s += (f'<line x1="{c.L}" y1="{c.y(0):.1f}" x2="{c.R}" y2="{c.y(0):.1f}" '
          f'stroke="{V.MUT}" stroke-width="1" stroke-dasharray="3 4"/>')
    s += D.text(c.R - 6, c.y(0) - 8, "neutral", V.MUT, 10, "end")
    fr = list(k_vs_front)
    kv = [k_vs_front[f] for f in fr]
    s += (f'<path d="{V.path(c.pts(fr, kv))}" fill="none" stroke="{V.VIO}" '
          f'stroke-width="2.5"/>')
    for f, v in zip(fr, kv):
        s += f'<circle cx="{c.x(f):.1f}" cy="{c.y(v):.1f}" r="3.5" fill="{V.VIO}"/>'
    s += (f'<circle cx="{c.x(backend.params.front_mass_fraction):.1f}" '
          f'cy="{c.y(k):.1f}" r="6" fill="none" stroke="{V.AMB}" '
          f'stroke-width="2"/>')
    s += D.text(c.x(backend.params.front_mass_fraction) + 10, c.y(k) + 4,
                "RV-1", V.AMB, 11)
    s += D.text(c.L + 10, c.B - 14,
                "the whole sweep stays below the road-car band", V.MUT, 10.5)

    front_c, rear_c = analytic
    s += D.text(100, 520,
                f"Cornering compliance: front {front_c:.2f} deg/g, rear "
                f"{rear_c:.2f} deg/g. K is the difference — {front_c - rear_c:+.2f} "
                f"analytically against {k:+.3f} measured. With identical tires at "
                f"both ends those two numbers nearly cancel, which is why a "
                f"bicycle model is nearly neutral.", V.MUT, 11.5)
    s += D.text(100, 542,
                "A real car gets most of its understeer from lateral load transfer, "
                "compliance steer, roll camber and roll steer — none of which a "
                "two-wheeled model has. Episode 5 measures how much of that gap the "
                "double-track model closes.", V.MUT, 11.5)

    s += _stamp(H - 40, backend,
                f"radius {radius:.0f} m [ASSUMED]  ·  K fitted over |a_y| ≤ 0.5 g "
                f"[SOURCED definition]  ·  road-car band [SOURCED] §4")
    return s + V.foot(
        W, H,
        "Steady-state equilibria solved directly, not simulated. D2 checks that "
        "the solver and the step-by-step integrator agree to machine precision.",
    )


__all__ = ["understeer_figure", "steady_state_card"]
