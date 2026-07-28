"""Episode 8 figures — balance and polar moment are two different axes.

``pair_figure``
    The pictorial hero. Two cars with identical weight distribution, drawn with
    their mass concentrated near the centre and spread toward the ends, and their
    yaw-rate responses to the same steering input side by side.
``surface_figure``
    The two-axis map: balance across, inertia up, response time as colour, with
    the five real layout archetypes marked on it. The figure that shows front-
    engine and rear-engine sit at opposite ends of one axis and together on the
    other.
``inertia_card``
    Technical panels: the response traces, rise time and overshoot against
    inertia, and the lap times.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V

#: Lap-time differences below this are not reportable (FINDINGS F39).
NOISE_FLOOR_S = 0.02

#: Nice names for the archetypes, in the order a reader would expect.
LAYOUTS = (
    ("front_fwd", "Front engine,\nfront drive", "hatchback"),
    ("front_rwd", "Front engine,\nrear drive", "saloon"),
    ("front_mid_rwd", "Front-mid,\nrear drive", "GR86, Corvette"),
    ("mid_rwd", "Mid engine,\nrear drive", "Cayman, 296"),
    ("rear_rwd", "Rear engine,\nrear drive", "911"),
)


def _stamp(y: float, meta, extra: str = "") -> str:
    v, t = meta["vehicle"], meta["tire"]
    bits = [
        f"[MEASURED] bicycle model (transient) + double-track (lap time) + "
        f"{t['file']}",
        f"m {v['mass']:.0f} kg held fixed",
        "[SOURCED] i_zz range 0.75-1.40x, RV-1 params §2",
        "layout archetype values [ASSUMED] §2",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  -  ".join(bits), V.MUT, 9.5)


def _mass_blobs(cx, cy, length, spread, colour, n=7):
    """Mass drawn as blobs along the car, gathered in or flung out.

    ``spread`` 0 puts every blob at the centre of gravity; 1 pushes them to the
    ends. Polar moment is mass times distance SQUARED, so this is the honest
    picture of what the number means — same total mass, same balance, different
    distance from the middle.
    """
    g = ""
    for i in range(n):
        u = (i - (n - 1) / 2.0) / max((n - 1) / 2.0, 1.0)   # -1 .. +1
        dy = u * spread * length * 0.42
        r = 5.0 + 3.0 * (1.0 - abs(u))
        g += (f'<circle cx="{cx:.1f}" cy="{cy + dy:.1f}" r="{r:.1f}" '
              f'fill="{colour}" opacity="0.55"/>')
    return g


def pair_figure(results, meta, traces) -> str:
    """Two cars, same balance, different polar moment. The Episode 8 hero."""
    mults = results["pair_multipliers"]
    ff = results["pair_front_mass_fraction"]
    W, H = 1480, 1070
    s = V.head(
        W, H,
        "Two cars with identical weight distribution, behaving differently",
        f"Both are {100*ff:.0f}% on the front axle. Both weigh the same. Both have "
        f"the same tires and the same understeer gradient. The only difference is "
        f"how far the mass sits from the middle of the car.",
    )
    s += D.text(40, 92,
                "Same steering input at the same speed. The one with its mass "
                "gathered near the centre answers the wheel sooner and settles "
                "sooner.", V.MUT, 11.5)

    colours = (V.TEAL, V.COR)
    labels = ("Mass gathered near the middle", "Mass spread toward the ends")
    subs = ("low polar moment — a mid-engine car",
            "high polar moment — engine over one axle, or hanging past it")
    for i, mult in enumerate(mults):
        r = results["pair"][f"{mult:.2f}"]
        cx, cy = 340 + i * 720, 330
        s += D.panel_title(cx - 250, 152, labels[i], subs[i])
        s += D.car_plan(cx, cy, length=210, width=92, wheel_len=46, wheel_w=19,
                        loads=(ff, ff, 1 - ff, 1 - ff), body=V.MUT)
        # the mass, drawn where it is
        com_y = cy + 210 * 0.30 * (1.0 - 2.0 * ff)
        s += _mass_blobs(cx, com_y, 210, 0.30 if i == 0 else 1.0, colours[i])
        s += D.text(cx, cy + 148, f"{r['i_zz']:.0f} kg·m²", colours[i], 15,
                    "middle", weight="600", mono=True)
        s += D.text(cx, cy + 166, f"polar moment, {mult:.2f}x the reference car",
                    V.MUT, 10.5, "middle")

    # the two responses, on one set of axes so they can be compared directly
    t = traces["pair_t"]
    L, R, TT, B = 240, 1240, 560, 800
    y_all = np.concatenate([np.abs(traces[f"pair_{m:.2f}".replace('.', '')])
                            for m in mults])
    ymax = float(y_all.max()) * 1.12
    s = V.grid(s, L, R, TT, B, 5, 4)
    xt = [(f"{v:.1f}", L + (R - L) * v / t[-1]) for v in
          np.linspace(0, t[-1], 5)]
    yt = [(f"{v:.2f}", B - (B - TT) * v / ymax) for v in
          np.linspace(0, ymax, 4)]
    s = V.axes(s, L, R, TT, B, "time after the steering input (s)",
               "yaw rate (rad/s)", xt, yt)
    for i, mult in enumerate(mults):
        y = np.abs(traces[f"pair_{mult:.2f}".replace('.', '')])
        pts = list(zip(L + (R - L) * t / t[-1], B - (B - TT) * y / ymax))
        s += (f'<path d="{V.path(pts)}" fill="none" stroke="{colours[i]}" '
              f'stroke-width="2.6"/>')
        r = results["pair"][f"{mult:.2f}"]
        s += D.text(R + 12, B - (B - TT) * y[-1] / ymax + 4 + (0 if i == 0 else 16),
                    f"{mult:.2f}x", colours[i], 12, weight="600")

    ly = 848
    rows = [("", "rise time", "overshoot", "settles after")]
    for i, mult in enumerate(mults):
        r = results["pair"][f"{mult:.2f}"]
        rows.append((f"{mult:.2f}x polar moment",
                     f"{1000*r['rise_time']:.0f} ms",
                     f"{100*r['overshoot']:.1f}%",
                     f"{1000*r['settling_time']:.0f} ms"))
    for ri, row in enumerate(rows):
        for ci, cell in enumerate(row):
            col = V.FG if ri == 0 else (colours[ri - 1] if ci == 0 else V.MUT)
            s += D.text(240 + ci * 250, ly + ri * 24, cell, col, 12.5,
                        weight="600" if ri == 0 or ci == 0 else "normal",
                        mono=(ri > 0 and ci > 0))

    k = results["pair_understeer_gradient_deg_per_g"]
    s += D.text(240, ly + 96,
                f"Both cars have an understeer gradient of {k:+.2f} deg/g — "
                f"identical, because that is set by balance and these two have "
                f"the same balance.", V.MUT, 12)
    s += D.text(240, ly + 118,
                "Steady-state behaviour is the same. Everything about how they "
                "GET there is different. That is the distinction this episode "
                "exists for.", V.MUT, 12)
    o_lo = results["pair"][f"{mults[0]:.2f}"]["overshoot"]
    o_hi = results["pair"][f"{mults[1]:.2f}"]["overshoot"]
    s += D.text(240, ly + 146,
                f"What this does NOT show is twitchiness. Overshoot is "
                f"{100*o_lo:.2f}% and {100*o_hi:.2f}% — the low-inertia car "
                f"overshoots more, which is the textbook direction, but both "
                f"numbers are so small that",
                V.MUT, 12)
    s += D.text(240, ly + 166,
                "neither car meaningfully overshoots at all. A 3 degree step at "
                "constant speed is a gentle input; \"nervous at the limit\" is a "
                "claim about large inputs and a driver in the loop, and this "
                "is neither.", V.MUT, 12)

    s += _stamp(H - 40, meta, "drag off during the step, as in D4")
    return s + V.foot(
        W, H,
        "Mass blobs are a schematic of distribution, not a mass model: polar "
        "moment goes as mass times distance squared, so the same total mass "
        "further out is a larger number. The yaw traces are measured.",
    )


def surface_figure(results, meta) -> str:
    """Balance across, polar moment up, response time as colour. Layouts marked."""
    fronts = results["surface_front"]
    izzs = results["surface_izz"]
    W, H = 1480, 1060
    s = V.head(
        W, H,
        "Weight distribution and polar moment are not the same axis",
        "Every square is a car. Left to right is where the mass sits along the "
        "car; bottom to top is how far it sits from the middle. Colour is how "
        "quickly the car answers the steering wheel.",
    )
    s += D.text(40, 92,
                "The five real layouts are marked. Note where the front-engine "
                "saloon and the rear-engine sports car land: opposite ends of "
                "one axis, side by side on the other.", V.MUT, 11.5)

    L, R, TT, B = 200, 900, 170, 720
    cw = (R - L) / len(fronts)
    ch = (B - TT) / len(izzs)
    rises = [results["surface"][f"{f:.2f}_{m:.2f}"]["rise_time"]
             for f in fronts for m in izzs]
    lo, hi = min(rises), max(rises)
    for i, f in enumerate(fronts):
        for j, m in enumerate(izzs):
            rt = results["surface"][f"{f:.2f}_{m:.2f}"]["rise_time"]
            u = (rt - lo) / max(hi - lo, 1e-9)
            r_, g_, b_ = V.ramp(u)
            x = L + i * cw
            y = B - (j + 1) * ch
            s += (f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw:.1f}" '
                  f'height="{ch:.1f}" fill="#{r_:02x}{g_:02x}{b_:02x}" '
                  f'opacity="0.88"/>')
            s += D.text(x + cw / 2, y + ch / 2 + 4, f"{1000*rt:.0f}",
                        "#15151a", 11, "middle", weight="600", mono=True)
    # axes
    for i, f in enumerate(fronts):
        s += D.text(L + (i + 0.5) * cw, B + 22, f"{100*f:.0f}%", V.MUT, 11,
                    "middle")
    for j, m in enumerate(izzs):
        s += D.text(L - 12, B - (j + 0.5) * ch + 4, f"{m:.2f}x", V.MUT, 11,
                    "end")
    s += D.text((L + R) / 2, B + 48, "front mass fraction  →  nose-heavy",
                V.FG, 12.5, "middle")
    s += (f'<text x="{L-78}" y="{(TT+B)/2}" fill="{V.FG}" font-size="12.5" '
          f'text-anchor="middle" transform="rotate(-90 {L-78} {(TT+B)/2})">'
          f'polar moment  →  mass further out</text>')
    s += D.text(L, TT - 14, "numbers are rise time in milliseconds — lower is "
                "a car that answers faster", V.MUT, 10.5)

    # The archetypes, at their true coordinates. Codes rather than bare dots:
    # matching five unlabelled markers back to a legend by eye is work the reader
    # should not have to do, and one of them was landing on top of a cell number.
    codes = {"front_fwd": "FF", "front_rwd": "FR", "front_mid_rwd": "FM",
             "mid_rwd": "M", "rear_rwd": "R"}
    arch = results["archetypes"]
    for key, name, example in LAYOUTS:
        a = arch[key]
        fx = (a["front_mass_fraction"] - fronts[0]) / (fronts[-1] - fronts[0])
        fy = (a["i_zz_multiplier"] - izzs[0]) / (izzs[-1] - izzs[0])
        px = L + cw / 2 + fx * (R - L - cw)
        py = B - ch / 2 - fy * (B - TT - ch)
        # The MARKER stays exactly where the car is. An earlier version nudged
        # it up to 30 px to clear the cell's own number, under a caption that
        # says the layouts are drawn at their true coordinates — moving the data
        # to make room for the annotation. The label moves instead.
        lab_dy = 26.0 if abs(py - (B - ch / 2 - round(fy * 4) * ch)) < 12 else 0.0
        s += (f'<circle cx="{px:.1f}" cy="{py:.1f}" r="10" fill="{V.BG}" '
              f'stroke="{V.FG}" stroke-width="2.2"/>')
        s += (f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.2" fill="{V.FG}"/>')
        s += (f'<rect x="{px+11:.1f}" y="{py-9+lab_dy:.1f}" width="26" '
              f'height="17" rx="4" fill="{V.BG}" opacity="0.82"/>')
        s += D.text(px + 24, py + 4 + lab_dy, codes[key], V.FG, 11, "middle",
                    weight="600", mono=True)

    ly = 180
    s += D.text(950, ly - 14, "The five layouts", V.FG, 15, weight="600")
    for i, (key, name, example) in enumerate(LAYOUTS):
        a = arch[key]
        y = ly + 22 + i * 84
        s += (f'<circle cx="962" cy="{y - 4}" r="9" fill="{V.BG}" '
              f'stroke="{V.FG}" stroke-width="2"/>')
        s += D.text(962, y, {"front_fwd": "FF", "front_rwd": "FR",
                             "front_mid_rwd": "FM", "mid_rwd": "M",
                             "rear_rwd": "R"}[key], V.FG, 9, "middle",
                    weight="600", mono=True)
        for j, line in enumerate(name.split("\n")):
            s += D.text(986, y + j * 15, line, V.FG, 12.5, weight="600")
        s += D.text(986, y + 32, example, V.MUT, 10.5, style="italic")
        s += D.text(1210, y, f"{100*a['front_mass_fraction']:.0f}% front", V.MUT,
                    11, mono=True)
        s += D.text(1210, y + 16, f"{a['i_zz_multiplier']:.2f}x inertia", V.MUT,
                    11, mono=True)
        s += D.text(1210, y + 32, f"rise {1000*a['rise_time']:.0f} ms", V.AMB,
                    11, mono=True)
        s += D.text(1210, y + 48, f"K {a['understeer_gradient_deg_per_g']:+.2f} deg/g",
                    V.VIO, 11, mono=True)

    s += D.rule(60, 780, 1420, V.GRID)
    fr = arch["front_rwd"]
    re = arch["rear_rwd"]
    mid = arch["mid_rwd"]
    for i, line in enumerate([
        f"Read the front-engine saloon and the rear-engine sports car off the "
        f"map. They sit at {100*fr['front_mass_fraction']:.0f}% and "
        f"{100*re['front_mass_fraction']:.0f}% front — opposite ends of the "
        f"balance axis, about as far apart as",
        f"two production cars get. And they sit at {fr['i_zz_multiplier']:.2f}x "
        f"and {re['i_zz_multiplier']:.2f}x polar moment: essentially the same "
        f"height on the other axis.",
        "",
        f"The mid-engine car is the outlier, and not on the axis people usually "
        f"name. Its balance ({100*mid['front_mass_fraction']:.0f}% front) is "
        f"unremarkable — the rear-engine car is further back. What makes it",
        f"different is that its mass is gathered in the middle: "
        f"{mid['i_zz_multiplier']:.2f}x, the lowest of the five, and it answers "
        f"the wheel in {1000*mid['rise_time']:.0f} ms against the saloon's "
        f"{1000*fr['rise_time']:.0f} ms.",
        "",
        "\"Mid-engine is better\" is usually argued as a weight-distribution "
        "claim. It is not. It is a polar-moment claim, and the two get confused "
        "because moving an",
        "engine changes both at once. Holding balance fixed and moving only the "
        "inertia — the top figure — is a comparison you cannot make with real "
        "cars.",
    ]):
        s += D.text(60, 812 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, meta)
    return s + V.foot(
        W, H,
        "Rise time is 10-90% of the steady yaw rate after a step steering input, "
        "measured on the bicycle model at constant speed with drag off — the "
        "same procedure D4 validated against an exactly integrated linear model.",
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


def inertia_card(results, meta, traces) -> str:
    izzs = np.array(results["surface_izz"])
    fronts = results["surface_front"]
    W, H = 1520, 700
    s = V.head(
        W, H,
        "Episode 8 - polar moment against balance",
        "How quickly the car answers the wheel, how much it overshoots, and what "
        "any of it is worth in a lap time. One line per weight distribution.",
    )

    for pi, (key, ylab, title, L, R, scale) in enumerate((
            ("rise_time", "rise time (ms)", "A - How fast it answers", 100, 420,
             1000.0),
            ("overshoot", "overshoot (%)", "B - How much it overshoots", 560,
             880, 100.0))):
        vals = [[results["surface"][f"{f:.2f}_{m:.2f}"][key] * scale
                 for m in izzs] for f in fronts]
        flat = [v for row in vals for v in row]
        pad = 0.06 * (max(flat) - min(flat) or 1.0)
        ax = _Ax(L, R, 150, 460, izzs.min(), izzs.max(),
                 min(flat) - pad, max(flat) + pad)
        s += D.panel_title(L, 132, title)
        s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 4, 4)
        xt = [(f"{v:.2f}", float(ax.x(v))) for v in izzs]
        yt = [(f"{v:.1f}", float(ax.y(v))) for v in
              np.linspace(min(flat) - pad, max(flat) + pad, 4)]
        s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "polar moment (x reference)",
                   ylab, xt, yt)
        for fi, f in enumerate(fronts):
            u = fi / max(len(fronts) - 1, 1)
            r_, g_, b_ = V.diverge(2.0 * u - 1.0)
            col = f"#{r_:02x}{g_:02x}{b_:02x}"
            s += (f'<path d="{V.path(ax.pts(izzs, vals[fi]))}" fill="none" '
                  f'stroke="{col}" stroke-width="2"/>')
            if pi == 1:
                s += D.text(ax.R + 8, float(ax.y(vals[fi][-1])) + 4,
                            f"{100*f:.0f}%", col, 10)

    # lap times at the archetypes
    arch = results["archetypes"]
    names = [k for k, _, _ in LAYOUTS]
    times = [arch[k]["time_s"] for k in names]
    ax = _Ax(1020, 1400, 150, 460, -0.5, len(names) - 0.5,
             min(times) - 0.05, max(times) + 0.05)
    s += D.panel_title(1020, 132, "C - Lap time by layout")
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, len(names), 4)
    yt = [(f"{v:.2f}", float(ax.y(v))) for v in
          np.linspace(min(times) - 0.05, max(times) + 0.05, 4)]
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "layout", "time (s)", [], yt)
    for i, (key, name, _ex) in enumerate(LAYOUTS):
        a = arch[key]
        x = float(ax.x(i))
        col = V.TEAL if a["converged"] else V.MUT
        s += (f'<circle cx="{x:.1f}" cy="{float(ax.y(a["time_s"])):.1f}" r="5" '
              f'fill="{col if a["converged"] else V.BG}" stroke="{col}" '
              f'stroke-width="1.8"/>')
        s += D.text(x, ax.B + 18, name.split("\n")[0].replace(" engine,", ""),
                    V.MUT, 9, "middle")
    s += D.text(1020, 500,
                f"Lap time spans only {results['archetype_time_span_s']:.3f} s "
                f"across all five layouts, while rise time spans "
                f"{results['archetype_rise_span_ms']:.0f} ms.", V.MUT, 11.5)

    s += D.text(100, 512,
                "Rise time falls with polar moment and rises with front weight; "
                "overshoot does the opposite. Both directions match the linear "
                "model D4 validated against.", V.MUT, 11.5)
    s += D.text(100, 534,
                "Hollow markers in panel C are solves that stopped on the "
                "iteration limit — their times are not evidence (FINDINGS F39).",
                V.MUT, 11.5)
    s += D.text(100, 556,
                "Steady-state yaw rate is independent of polar moment to one "
                "part in ten thousand (D4), so none of this moves the understeer "
                "gradient. Inertia is a transient effect only.", V.MUT, 11.5)
    s += _stamp(H - 40, meta)
    return s + V.foot(
        W, H,
        "Transient metrics from a step steer on the bicycle model; lap times "
        "from four-wheel minimum-time solves. Absolute times are specific to "
        "this invented corner.",
    )


__all__ = ["pair_figure", "surface_figure", "inertia_card"]
