"""D2 figures — where the weight goes, drawn as a car.

``load_transfer_figure``
    Braking, cruising and accelerating, as three cars whose contact patches
    change size. The pictorial companion to D2's load-transfer checks, and the
    bridge between Episode 2 (two tires sharing a load) and Episode 3 (a whole
    car doing it).
``invariants_card``
    The technical panels: axle load against longitudinal acceleration, the
    centre-of-gravity height sweep, and the yaw-response comparison that shows
    inertia is actually wired in.
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
        f"m {v.mass:.0f} kg · L {v.wheelbase:.3f} m · h {v.com_height:.3f} m "
        f"· {v.front_mass_fraction:.0%} front",
        "[SOURCED] RV-1 parameters, vehicle-reference-parameters.md §1",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  ·  ".join(bits), V.MUT, 9.5)


def load_transfer_figure(backend) -> str:
    """Three cars: braking, steady, accelerating. Contact patches tell the story."""
    v = backend.params
    cases = [
        (-5.0, "Braking hard", V.COR),
        (0.0, "Steady", V.MUT),
        (+5.0, "Accelerating hard", V.TEAL),
    ]
    loads = [(a, *backend.axle_loads(a)) for a, _, _ in cases]
    lo = min(min(f, r) for _, f, r in loads)
    hi = max(max(f, r) for _, f, r in loads)

    W, H = 1480, 940
    s = V.head(
        W, H,
        "Where the weight goes when you brake",
        f"The car weighs {v.mass:,.0f} kg no matter what it is doing — "
        f"{v.weight/1000:.1f} kN pressing on the road, always. What changes is "
        f"how that weight is shared between the front and rear tires.",
    )
    s += D.text(40, 92,
                "The shaded band across each tire is its contact patch. Bigger "
                "band, more weight on that tire. Nothing is added or removed — it "
                "only moves.", V.MUT, 11.5)

    for i, ((a_x, title, colour), (_, fz_f, fz_r)) in enumerate(zip(cases, loads)):
        cx = 300 + i * 440
        cy = 380
        frac_f = (fz_f / 2 - lo / 2) / ((hi - lo) / 2) if hi > lo else 0.5
        frac_r = (fz_r / 2 - lo / 2) / ((hi - lo) / 2) if hi > lo else 0.5
        s += D.panel_title(cx - 170, 150, title,
                           f"{a_x:+.0f} m/s² ({a_x/9.80665:+.2f} g)"
                           if a_x else "no braking, no throttle")
        s += D.car_plan(cx, cy, length=210, width=92, wheel_len=46, wheel_w=18,
                        loads=(frac_f, frac_f, frac_r, frac_r))
        if a_x:
            # The car is drawn nose-up, so "forward" is UP the page. The arrow
            # runs along the car's own axis and points at the axle that GAINS
            # load — braking loads the front, accelerating loads the rear.
            ax_x = cx + 128
            y0, y1 = (cy + 78, cy - 78) if a_x < 0 else (cy - 78, cy + 78)
            s += D.arrow(ax_x, y0, ax_x, y1, colour, 3.0, 12)
            s += D.text(ax_x + 14, (y0 + y1) / 2 - 6,
                        "weight shifts", colour, 11.5)
            s += D.text(ax_x + 14, (y0 + y1) / 2 + 10,
                        "onto the front" if a_x < 0 else "onto the rear",
                        colour, 11.5, weight="600")
        s += D.text(cx - 150, cy - 66, "front", V.MUT, 11, "end")
        s += D.text(cx - 150, cy - 48, f"{fz_f/1000:.2f} kN", colour, 13.5, "end",
                    weight="600", mono=True)
        s += D.text(cx - 150, cy + 78, "rear", V.MUT, 11, "end")
        s += D.text(cx - 150, cy + 96, f"{fz_r/1000:.2f} kN", colour, 13.5, "end",
                    weight="600", mono=True)
        s += D.text(cx - 150, cy + 150, f"total {(fz_f+fz_r)/1000:.2f} kN",
                    V.FG, 12, "end", mono=True)
        if a_x:
            base_f = loads[1][1]
            s += D.text(cx - 150, cy + 168,
                        f"{100*(fz_f-base_f)/base_f:+.0f}% on the front",
                        colour, 11, "end")

    s += D.rule(60, 660, 1420, V.GRID)
    s += D.panel_title(60, 700, "Why this matters, and it is Episode 2 again",
                       None)
    for i, line in enumerate([
        "Braking at 0.5 g puts about 17% more weight on the front tires and takes "
        "the same off the rear. The total never changes.",
        "",
        "But grip does not follow weight one-for-one — a tire pressed harder gives "
        "back less than proportionally (Episode 2). So the",
        "front tires gain less grip than the rear ones lose, and the car has less "
        "total grip while braking than while cruising.",
        "",
        "Double the height of the centre of gravity and you double the transfer. "
        "That is the entire reason sports cars are low, and it is why",
        "the GR86's 460 mm figure is the number Toyota's engineers put in the "
        "press kit.",
    ]):
        s += D.text(60, 734 + 22 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, backend,
                "acceleration values [ASSUMED] round numbers for illustration")
    return s + V.foot(
        W, H,
        "Longitudinal load transfer is m·a_x·h/L, exactly — no tuning, no fudge "
        "factor. D2 asserts the signs, the conservation, and the proportionality "
        "to centre-of-gravity height.",
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


def invariants_card(backend, com_sweep, yaw_traces) -> str:
    """Technical panels behind D2's assertions."""
    v = backend.params
    W, H = 1520, 560
    s = V.head(
        W, H,
        "D2 — Invariants and signs",
        "The three measurements behind the assertions: load transfer against "
        "longitudinal acceleration, its proportionality to centre-of-gravity "
        "height, and yaw response against inertia.",
    )

    # A: axle load vs a_x
    a = _Ax(100, 560, 130, 420, -8, 8, 4.0, 9.5)
    s += D.panel_title(100, 112, "A · Axle load against acceleration")
    s = V.grid(s, a.L, a.R, a.T, a.B, 4, 5)
    xt, yt = _ticks(a, [-8, -4, 0, 4, 8], [4, 5, 6, 7, 8, 9],
                    fx="{:+.0f}", fy="{:.0f}")
    s = V.axes(s, a.L, a.R, a.T, a.B, "longitudinal acceleration (m/s²)",
               "axle load (kN)", xt, yt)
    axs = np.linspace(-8, 8, 60)
    for idx, (colour, label) in enumerate(((V.AMB, "front"), (V.TEAL, "rear"))):
        vals = [backend.axle_loads(x)[idx] / 1000 for x in axs]
        s += (f'<path d="{V.path(a.pts(axs, vals))}" fill="none" stroke="{colour}" '
              f'stroke-width="2.5"/>')
        s += D.text(a.R - 6, a.y(vals[-1]) - 8, label, colour, 11.5, "end")
    s += (f'<line x1="{a.x(0):.1f}" y1="{a.T}" x2="{a.x(0):.1f}" y2="{a.B}" '
          f'stroke="{V.MUT}" stroke-width="1" stroke-dasharray="3 5"/>')
    s += D.text(a.x(0) - 8, a.T + 14, "braking", V.MUT, 10, "end")
    s += D.text(a.x(0) + 8, a.T + 14, "accelerating", V.MUT, 10)
    s += D.text(a.L + 12, a.B - 14,
                f"the two always sum to {v.weight/1000:.2f} kN", V.MUT, 10.5)

    # B: transfer vs CoM height
    b = _Ax(650, 1000, 130, 420, 0, 1.0, 0, 3.0)
    s += D.panel_title(650, 112, "B · Transfer against centre-of-gravity height")
    s = V.grid(s, b.L, b.R, b.T, b.B, 4, 3)
    xt, yt = _ticks(b, [0, 0.25, 0.5, 0.75, 1.0], [0, 1, 2, 3],
                    fx="{:.2f}", fy="{:.0f}")
    s = V.axes(s, b.L, b.R, b.T, b.B, "centre-of-gravity height (m)",
               "load moved at 0.5 g (kN)", xt, yt)
    hs, ts = zip(*com_sweep)
    s += (f'<path d="{V.path(b.pts(hs, [t/1000 for t in ts]))}" fill="none" '
          f'stroke="{V.VIO}" stroke-width="2.5"/>')
    s += (f'<circle cx="{b.x(v.com_height):.1f}" '
          f'cy="{b.y(np.interp(v.com_height, hs, ts)/1000):.1f}" r="6" '
          f'fill="none" stroke="{V.AMB}" stroke-width="2"/>')
    s += D.text(b.x(v.com_height) + 11, b.y(np.interp(v.com_height, hs, ts)/1000) + 4,
                f"RV-1, {v.com_height*1000:.0f} mm", V.AMB, 11)
    s += D.text(b.L + 12, b.B - 14, "a straight line through the origin",
                V.MUT, 10.5)

    # C: yaw response
    c = _Ax(1090, 1420, 130, 420, 0, 0.8, 0, 1.15)
    s += D.panel_title(1090, 112, "C · Yaw response against inertia")
    s = V.grid(s, c.L, c.R, c.T, c.B, 4, 4)
    xt, yt = _ticks(c, [0, 0.25, 0.5, 0.75], [0, 0.5, 1.0], fx="{:.2f}", fy="{:.1f}")
    s = V.axes(s, c.L, c.R, c.T, c.B, "time since the steering input (s)",
               "yaw rate ÷ final", xt, yt)
    for (label, trace, colour) in yaw_traces:
        t = np.arange(len(trace)) * 0.001
        norm = np.abs(trace) / abs(trace[-1])
        keep = t <= 0.8
        s += (f'<path d="{V.path(c.pts(t[keep], norm[keep]))}" fill="none" '
              f'stroke="{colour}" stroke-width="2.5"/>')
        s += D.text(c.R - 6, c.y(norm[keep][-1]) + 14, label, colour, 11, "end")
    s += (f'<line x1="{c.L}" y1="{c.y(0.9):.1f}" x2="{c.R}" y2="{c.y(0.9):.1f}" '
          f'stroke="{V.MUT}" stroke-width="1" stroke-dasharray="3 4"/>')
    s += D.text(c.L + 10, c.y(0.9) - 7, "90%", V.MUT, 10)
    s += D.text(c.L + 12, c.B - 14, "heavier in yaw, slower to respond",
                V.MUT, 10.5)

    s += D.text(100, 470,
                "Panels A and B are arithmetic: transfer is m·a_x·h/L, so it is "
                "linear in both acceleration and centre-of-gravity height, and the "
                "two axle loads always sum to the car's weight. Panel C is the check "
                "that yaw inertia is actually in the loop rather than merely stored "
                "— doubling it doubles the time to respond, and leaves the "
                "steady-state cornering answer untouched.", V.MUT, 11.5)
    s += _stamp(H - 40, backend)
    return s + V.foot(
        W, H,
        "Every curve here is a Gate 1 falsification check from "
        "result-evaluation-guide.md. A violation would be a bug, not a discovery.",
    )


# ---------------------------------------------------------------------------


def cog_height_figure(backend, a_x: float = -4.903) -> str:
    """Two cars braking equally hard. One is low, one is tall."""
    from dataclasses import replace as _replace

    v = backend.params
    tall_h = v.com_height * 2
    cars = [
        (v.com_height, "RV-1, 460 mm", V.TEAL),
        (tall_h, f"the same car, {tall_h*1000:.0f} mm", V.COR),
    ]
    W, H = 1480, 800
    s = V.head(
        W, H,
        "Why sports cars are low",
        f"Two identical cars braking equally hard at {abs(a_x)/9.80665:.1f} g. The "
        f"only difference is how high the weight sits. Nothing else changes — same "
        f"mass, same wheelbase, same tires.",
    )
    base_f, base_r = backend.axle_loads(0.0)
    results = []
    for h, _, _ in cars:
        bb = type(backend)(_replace(v, com_height=h))
        results.append(bb.axle_loads(a_x))
    lo = min(min(r) for r in results)
    hi = max(max(r) for r in results)

    for i, ((h, title, colour), (fz_f, fz_r)) in enumerate(zip(cars, results)):
        cx = 380 + i * 620
        cy = 380
        s += D.panel_title(cx - 210, 160, title,
                           f"centre of gravity {h*1000:.0f} mm above the road")
        s += D.car_plan(cx, cy, length=210, width=92, wheel_len=46, wheel_w=18,
                        loads=((fz_f / 2 - lo / 2) / ((hi - lo) / 2),) * 2
                        + ((fz_r / 2 - lo / 2) / ((hi - lo) / 2),) * 2)
        s += D.arrow(cx + 128, cy + 78, cx + 128, cy - 78, colour, 3.0, 12)
        s += D.text(cx + 142, cy - 4, f"{(fz_f-base_f)/1000:+.2f} kN", colour,
                    13.5, weight="600", mono=True)
        s += D.text(cx + 142, cy + 14, "moved forward", V.MUT, 11)
        s += D.text(cx - 150, cy - 66, "front", V.MUT, 11, "end")
        s += D.text(cx - 150, cy - 48, f"{fz_f/1000:.2f} kN", colour, 13.5, "end",
                    weight="600", mono=True)
        s += D.text(cx - 150, cy + 78, "rear", V.MUT, 11, "end")
        s += D.text(cx - 150, cy + 96, f"{fz_r/1000:.2f} kN", colour, 13.5, "end",
                    weight="600", mono=True)

    s += D.rule(60, 610, 1420, V.GRID)
    lines = [
        f"Twice the height, twice the transfer — {(results[0][0]-base_f)/1000:.2f} kN "
        f"becomes {(results[1][0]-base_f)/1000:.2f} kN. It is exactly proportional, "
        "with no fudge factor: the",
        "transfer is m·a_x·h/L, and h is the only thing that changed.",
        "",
        "And transfer costs grip, because a tire pressed harder gives back less than "
        "proportionally (Episode 2). So the tall car has",
        "less total grip while braking than the low one — same tires, same weight, "
        "worse car. That is why Toyota put the GR86's",
        "460 mm centre of gravity in the press release.",
    ]
    for i, line in enumerate(lines):
        s += D.text(60, 654 + 22 * i, line, V.MUT, 12.5)
    s += _stamp(H - 40, backend,
                f"braking at {a_x:.2f} m/s2 [ASSUMED]  ·  tall variant is RV-1 with "
                "com_height doubled, nothing else changed")
    return s + V.foot(
        W, H,
        "D2 asserts this proportionality exactly: doubling centre-of-gravity "
        "height doubles the transfer, to machine precision.",
    )


def corner_forces_figure(backend, left, right) -> str:
    """Which way the tires actually push, and that left mirrors right.

    Both panels take their numbers from a real trim — the right-hand one from a
    negative-radius solve, not from mirroring the left one by hand — so the
    figure would show an asymmetry if the model had one.

    Every angle and every lateral offset goes through :func:`D.screen_deg` /
    :func:`D.screen_dx`. Skipping that conversion is what drew this figure with
    the wheels turned the wrong way the first time: ISO's positive steer is
    left, SVG's positive rotation is clockwise, and nothing complains.
    """
    W, H = 1480, 820
    s = V.head(
        W, H,
        "Which way the tires push, and why left mirrors right",
        "A car holding a steady circle. The wheels are pointed slightly away from "
        "where they are travelling, and the grip that produces is what bends the "
        "car's path. Two of D2's sign checks, drawn.",
    )
    scale = 100.0 / max(abs(left.fy_f), abs(left.fy_r))
    for i, (pt, title) in enumerate(((left, "Turning left"),
                                     (right, "Turning right"))):
        cx = 380 + i * 640
        cy = 350
        s += D.panel_title(cx - 230, 150, title, f"{abs(pt.a_y_g):.2f} g")
        s += D.arrow(cx, cy + 230, cx, cy - 230, V.MUT, 1.8, 10, dash="5 5")
        s += D.text(cx, cy - 242, "direction of travel", V.MUT, 10.5, "middle")
        s += D.car_plan(
            cx, cy, length=200, width=88, wheel_len=44, wheel_w=17,
            steer_deg=D.screen_deg(pt.steer_deg),
            # the body sits at -beta from its velocity in ISO, so +beta on screen
            heading_deg=D.screen_deg(-pt.sideslip_deg),
            heading=120, loads=(0.55,) * 4)
        for label, fy, ay, colour in (
            ("front", pt.fy_f, cy - 62, V.AMB),
            ("rear", pt.fy_r, cy + 62, V.TEAL),
        ):
            x0 = cx + D.screen_dx(math.copysign(60.0, fy))
            x1 = cx + D.screen_dx(math.copysign(60.0 + abs(fy) * scale, fy))
            s += D.arrow(x0, ay, x1, ay, colour, 3.2, 12)
            s += D.text(x1 + (12 if x1 > cx else -12), ay - 8,
                        f"{label} {abs(fy)/1000:.1f} kN", colour, 11.5,
                        "start" if x1 > cx else "end")
        s += D.text(cx, cy + 268,
                    f"steer {pt.steer_deg:+.2f}°  ·  grip points "
                    f"{'left' if pt.fy_f > 0 else 'right'}, into the corner",
                    V.MUT, 11.5, "middle")

    s += D.rule(60, 660, 1420, V.GRID)
    for i, line in enumerate([
        "Both tires push toward the inside of the corner, and the front pushes "
        "harder — it has more weight on it and a longer lever to the centre of mass.",
        "Mirror the steering input and every force mirrors with it, to within 0.2% "
        "(D2 asserts 0.5%). The residual is one deliberately retained term in the",
        "tire formula, not an asymmetry in the car — see FINDINGS D2.",
    ]):
        s += D.text(60, 700 + 22 * i, line, V.MUT, 12.5)
    s += _stamp(H - 40, backend, "arrow length is force, to one scale in both panels")
    return s + V.foot(
        W, H,
        "A tire makes force by being pointed slightly away from where it is going. "
        "Everything a car does in a corner comes from those two arrows.",
    )


__all__ = ["load_transfer_figure", "cog_height_figure",
           "corner_forces_figure", "invariants_card"]
