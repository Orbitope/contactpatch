"""Episode 8 figures — how a car answers the wheel.

``response_figure``
    Two cars given the same flick of steering, drawn as a strip of snapshots.
    Same weight distribution, different polar moment. The Ep 8 hero.
``transient_card``
    Yaw-rate traces against closed-form theory, the inertia sweep, and the
    uncertainty band that says how much of the answer we actually know.
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
        f"m {v.mass:.0f} kg · Izz {v.i_zz:.0f} kg·m² · {v.front_mass_fraction:.0%} front",
        "[SOURCED] RV-1 parameters, vehicle-reference-parameters.md §1",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  ·  ".join(bits), V.MUT, 9.5)


def response_figure(backend, resp, sweep, izz_mult) -> str:
    """A strip of snapshots: two cars turning in, frame by frame."""
    lo, hi = izz_mult[0], izz_mult[-1]
    traces = {m: sweep[m]["trace"] for m in (lo, hi)}
    dt = resp["dt"]
    frames = [0.0, 0.1, 0.2, 0.35, 0.5, 0.8]

    W, H = 1480, 1010
    s = V.head(
        W, H,
        "How a car answers the wheel",
        f"Two cars, identical in every way except how far their weight sits from "
        f"the middle. Both are given the same {resp['steer_deg']:g}° flick of "
        f"steering at {resp['speed']:g} m/s, at the same instant. Each frame is "
        f"the heading each car has turned to by that moment.",
    )

    rows = [
        (lo, f"Weight near the middle  ·  {lo:.2f}× polar moment", V.TEAL,
         "mid-engine end of the range"),
        (hi, f"Weight spread out  ·  {hi:.2f}× polar moment", V.COR,
         "front- or rear-engine end"),
    ]
    x0, dx = 250, 205
    for r, (mult, title, colour, sub) in enumerate(rows):
        cy = 300 + r * 250
        s += D.panel_title(60, cy - 96, title, sub)
        yaw = traces[mult]
        for i, t in enumerate(frames):
            cx = x0 + i * dx
            k = min(int(t / dt), len(yaw) - 1)
            heading = float(np.trapezoid(yaw[:k + 1], dx=dt)) if k else 0.0
            s += D.car_plan(cx, cy, length=112, width=50, wheel_len=26,
                            wheel_w=11, steer_deg=D.screen_deg(resp["steer_deg"]),
                            heading_deg=D.screen_deg(math.degrees(heading)),
                            loads=(0.55,) * 4, body=colour)
            if r == 0:
                s += D.text(cx, cy - 128, f"{t:.2f} s", V.MUT, 11.5, "middle")
            s += D.text(cx, cy + 84, f"{math.degrees(heading):.1f}°", colour,
                        12.5, "middle", mono=True)
        s += D.text(60, cy + 20,
                    f"turned {math.degrees(float(np.trapezoid(yaw[:int(frames[-1]/dt)], dx=dt))):.1f}° "
                    f"by {frames[-1]:g} s", colour, 12.5, weight="600")
        s += D.text(60, cy + 40,
                    f"{1000*sweep[mult]['rise_time']:.0f} ms to respond, "
                    f"{100*sweep[mult]['overshoot']:.2f}% overshoot", V.MUT, 11.5)

    s += D.rule(60, 720, 1420, V.GRID)
    d_rise = 1000 * (sweep[hi]["rise_time"] - sweep[lo]["rise_time"])
    for i, line in enumerate([
        "Both cars weigh the same and carry the same share of it over the front "
        "wheels. The only difference is whether that weight sits near the",
        "middle or out at the ends — and it is worth "
        f"{d_rise:.0f} ms of delay before the car starts doing what you asked.",
        "",
        "The one with its weight spread out is slower to start turning, and "
        "slightly steadier once it gets there — it overshoots a little less.",
        "Both effects are small on this car, because a bicycle model is almost "
        "critically damped: it has none of the tire and suspension lag that",
        "makes a real car swing past by 5-40%. Trust the direction here, not the "
        "size.",
        "",
        "Both end up in exactly the same corner. Polar moment changes the "
        "journey, never the destination.",
    ]):
        s += D.text(60, 764 + 22 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, backend,
                f"step steer {resp['steer_deg']:g}° at {resp['speed']:g} m/s "
                "[ASSUMED]  ·  inertia multipliers 0.75-1.40 [SOURCED range, §2]")
    return s + V.foot(
        W, H,
        "Heading is the integral of yaw rate, drawn to scale. This is the axis "
        "Episode 8 is about, and it is independent of weight distribution: two "
        "cars can be balanced identically and still answer completely differently.",
    )


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


def transient_card(backend, resp, theory, sweep, izz_mult, izz_band) -> str:
    W, H = 1520, 600
    s = V.head(
        W, H,
        "D4 — Transient response",
        f"Step steer {resp['steer_deg']:g}° at {resp['speed']:g} m/s. Rise time "
        f"{1000*resp['rise_time']:.0f} ms, overshoot "
        f"{100*resp['overshoot']:.0f}%, damping ratio {theory['zeta']:.2f}.",
    )
    t, yaw = resp["t"], np.abs(resp["yaw_rate"]) / resp["final"]

    # A: the response vs theory
    a = _Ax(100, 560, 130, 430, 0, 1.2, 0, 1.35)
    s += D.panel_title(100, 112, "A · Yaw rate against closed-form theory")
    s = V.grid(s, a.L, a.R, a.T, a.B, 6, 3)
    xt, yt = _ticks(a, [0, 0.4, 0.8, 1.2], [0, 0.5, 1.0], fx="{:.1f}", fy="{:.1f}")
    s = V.axes(s, a.L, a.R, a.T, a.B, "time since the steering input (s)",
               "yaw rate ÷ final", xt, yt)
    keep = t <= 1.2
    s += (f'<path d="{V.path(a.pts(t[keep], yaw[keep]))}" fill="none" '
          f'stroke="{V.AMB}" stroke-width="2.5"/>')
    wn, z = theory["wn"], theory["zeta"]
    wd = wn * math.sqrt(max(1 - z * z, 1e-9))
    th = 1 - np.exp(-z * wn * t[keep]) * (
        np.cos(wd * t[keep]) + z / math.sqrt(max(1 - z * z, 1e-9))
        * np.sin(wd * t[keep]))
    s += (f'<path d="{V.path(a.pts(t[keep], th))}" fill="none" stroke="{V.VIO}" '
          f'stroke-width="1.8" stroke-dasharray="6 4"/>')
    s += (f'<line x1="{a.L}" y1="{a.y(1.0):.1f}" x2="{a.R}" y2="{a.y(1.0):.1f}" '
          f'stroke="{V.MUT}" stroke-width="1" stroke-dasharray="3 5"/>')
    s += D.text(a.L + 12, a.T + 20, "measured", V.AMB, 11.5, weight="600")
    s += D.text(a.L + 12, a.T + 38, "second-order theory", V.VIO, 11.5)
    s += D.text(a.R - 8, a.B - 12,
                f"ωn {wn:.1f} rad/s · ζ {z:.2f}", V.MUT, 10.5, "end")

    # B: inertia sweep
    b = _Ax(660, 1010, 130, 430, 0, 1.2, 0, 1.35)
    s += D.panel_title(660, 112, "B · The same input at three inertias")
    s = V.grid(s, b.L, b.R, b.T, b.B, 6, 3)
    xt, yt = _ticks(b, [0, 0.4, 0.8, 1.2], [0, 0.5, 1.0], fx="{:.1f}", fy="{:.1f}")
    s = V.axes(s, b.L, b.R, b.T, b.B, "time (s)", "yaw rate ÷ final", xt, yt)
    for mult, colour in zip(izz_mult, (V.TEAL, V.AMB, V.COR)):
        tr = np.abs(sweep[mult]["trace"]) / sweep[mult]["final"]
        s += (f'<path d="{V.path(b.pts(t[keep], tr[keep]))}" fill="none" '
              f'stroke="{colour}" stroke-width="2.2"/>')
        s += D.text(b.R - 6, b.y(tr[keep][-1]) + (14 if mult > 1 else -8),
                    f"{mult:.2f}×", colour, 11, "end")
    s += D.text(b.L + 12, b.B - 14,
                "more inertia: slower AND more overshoot", V.MUT, 10.5)

    # C: uncertainty
    c = _Ax(1100, 1420, 130, 430, 1650, 2400, 0.10, 0.22)
    s += D.panel_title(1100, 112, "C · What we do not know about Izz")
    s = V.grid(s, c.L, c.R, c.T, c.B, 3, 3)
    xt, yt = _ticks(c, [1750, 2050, 2350], [0.12, 0.16, 0.20],
                    fx="{:.0f}", fy="{:.2f}")
    s = V.axes(s, c.L, c.R, c.T, c.B, "yaw inertia (kg·m²)", "rise time (s)",
               xt, yt)
    xs = [v["i_zz"] for v in izz_band.values()]
    ys = [v["rise_time"] for v in izz_band.values()]
    s += (f'<path d="{V.path(c.pts(xs, ys))}" fill="none" stroke="{V.VIO}" '
          f'stroke-width="2.5"/>')
    for x_, y_, lab in zip(xs, ys, ("radius of\ngyration", "ours",
                                    "SAE mass\nregression")):
        s += f'<circle cx="{c.x(x_):.1f}" cy="{c.y(y_):.1f}" r="4.5" fill="{V.VIO}"/>'
        for j, ln in enumerate(lab.split("\n")):
            s += D.text(c.x(x_), c.y(y_) - 26 + 13 * j, ln, V.MUT, 9.5, "middle")
    s += D.text(c.L + 10, c.B - 14,
                "three published correlations, one car", V.MUT, 10.5)

    s += D.text(100, 480,
                "Panel A is the check that matters: the measured response and the "
                "closed-form second-order solution are the same curve, and none of "
                "that theory appears in our code. Panel C is the caveat — the three "
                "published ways to estimate yaw inertia disagree by 36%, which is "
                f"{1000*(max(ys)-min(ys)):.0f} ms of rise time. Report the direction "
                "of the inertia effect confidently and its magnitude loosely.",
                V.MUT, 11.5)
    s += _stamp(H - 40, backend,
                "Izz correlations [SOURCED] vehicle-reference-parameters.md §1")
    return s + V.foot(
        W, H,
        "Rise time is 10-90% of final yaw rate; overshoot is peak over final. "
        "Final value is the mean of the last 10% of the trace, so a decaying tail "
        "does not distort every metric.",
    )


__all__ = ["response_figure", "transient_card"]
