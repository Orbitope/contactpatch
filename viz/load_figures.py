"""Episode 5 figures — four wheels, and what the second track buys.

``four_wheel_figure``
    The same corner drawn with four wheels, contact patches sized by load. The
    Ep 5 hero: the outside pair is visibly carrying the car.
``load_transfer_card``
    Per-wheel load against cornering force, the anti-roll-bar sweep with the
    bicycle model's flat line beside it, and the wheel-lift threshold.
"""

from __future__ import annotations

import math
from dataclasses import replace as _replace

import numpy as np

from . import diagram as D
from . import lib as V
from physics.schema import G


def _stamp(y: float, backend, extra: str = "") -> str:
    p, v = backend.tire.provenance, backend.params
    bits = [
        f"[MEASURED] double-track model + {p['file']}",
        "offsets removed" if p["offsets_removed"] else "as shipped",
        f"m {v.mass:.0f} kg - track {v.track_f:.3f}/{v.track_r:.3f} m - "
        f"h {v.com_height:.3f} m - roll front {v.roll_stiffness_front_share:.0%}",
        "[SOURCED] RV-1 params §1, track width [LIKELY]",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  -  ".join(bits), V.MUT, 9.5)


def four_wheel_figure(backend, points) -> str:
    """Two cars: cruising and at the limit, with per-wheel loads drawn."""
    slow = min(points, key=lambda q: abs(q.a_y_g - 0.20))
    fast = max(points, key=lambda q: q.a_y_g)
    lo = min(min(q.loads.values()) for q in (slow, fast))
    hi = max(max(q.loads.values()) for q in (slow, fast))

    W, H = 1480, 1010
    s = V.head(
        W, H,
        "What the second track buys you",
        "The same car on the same circle as Episode 3 — but now it has a left and "
        "a right. Cornering leans on the outside wheels, and because grip falls "
        "as load rises, that costs the car grip nothing spent.",
    )
    s += D.text(40, 92,
                "Contact-patch size is load. Watch the inside pair shrink.",
                V.MUT, 11.5)

    for i, (pt, title) in enumerate(((slow, "Cruising"), (fast, "At the limit"))):
        cx, cy = 360 + i * 700, 400
        s += D.panel_title(cx - 250, 150, f"{title} - {pt.a_y_g:.2f} g",
                           f"{pt.speed:.1f} m/s, turning left")
        s += D.arrow(cx, cy + 250, cx, cy - 250, V.MUT, 1.8, 10, dash="5 5")
        s += D.text(cx, cy - 262, "direction of travel", V.MUT, 10.5, "middle")
        fr = {c: (pt.loads[c] - lo) / max(hi - lo, 1.0) for c in pt.loads}
        s += D.car_plan(cx, cy, length=240, width=104, wheel_len=54, wheel_w=22,
                        steer_deg=D.screen_deg(pt.steer_deg),
                        heading_deg=D.screen_deg(-pt.sideslip_deg),
                        loads=(fr["fl"], fr["fr"], fr["rl"], fr["rr"]))
        for corner, dx, dy in (("fl", -1, -1), ("fr", 1, -1),
                               ("rl", -1, 1), ("rr", 1, 1)):
            lx = cx + dx * 150
            ly = cy + dy * 76 + (0 if dy < 0 else 18)
            s += D.text(lx, ly, f"{pt.loads[corner]/1000:.2f} kN",
                        V.COR if pt.loads[corner] > 3000 else V.TEAL,
                        13, "end" if dx < 0 else "start", weight="600", mono=True)
        s += D.text(cx, cy + 300,
                    f"outside pair carries "
                    f"{(pt.loads['fr']+pt.loads['rr'])/(pt.loads['fl']+pt.loads['rl']):.1f}x "
                    f"the inside pair", V.FG, 13, "middle", weight="600")
        s += D.text(cx, cy + 322,
                    f"total {sum(pt.loads.values())/1000:.2f} kN - unchanged",
                    V.MUT, 11.5, "middle")

    s += D.rule(60, 760, 1420, V.GRID)
    for i, line in enumerate([
        "At the limit the outside wheels carry roughly four times what the inside "
        "wheels do. The total never changes -- it is the same",
        "car -- but Episode 2 already told us what that costs: two tires sharing a "
        "load unevenly make less grip than two sharing it evenly.",
        "",
        "That is the whole upgrade. The two-wheeled model could not represent this, "
        "and so it could not represent an anti-roll bar either,",
        "because a bar is a device for choosing WHICH axle suffers the uneven "
        "split.",
    ]):
        s += D.text(60, 800 + 22 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, backend,
                "30 m skidpad [ASSUMED], constant speed (SAE J266)")
    return s + V.foot(
        W, H,
        "Load transfer is m*a_y*h as a moment, divided between the axles by roll "
        "stiffness and converted to force by each axle's track width. No fitting "
        "parameters. D5 asserts the four loads always sum to the car's weight.",
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


def load_transfer_card(backend, points, arb, arb_bicycle, k_full, k_bicycle,
                       g_full, g_bicycle, lift) -> str:
    W, H = 1520, 640
    s = V.head(
        W, H,
        "D5 - Load transfer audit",
        f"Four-wheel model. Understeer gradient {k_full:.2f} deg/g against the "
        f"bicycle model's {k_bicycle:.2f}; peak lateral {g_full:.2f} g against "
        f"{g_bicycle:.2f}. Lateral transfer costs "
        f"{100*(g_bicycle-g_full)/g_bicycle:.0f}% of the grip.",
    )
    ay = np.array([q.a_y_g for q in points])

    a = _Ax(100, 560, 140, 450, 0, 1.05, 0, 6.5)
    s += D.panel_title(100, 122, "A - Per-wheel load against cornering force")
    s = V.grid(s, a.L, a.R, a.T, a.B, 5, 4)
    xt, yt = _ticks(a, [0, 0.25, 0.5, 0.75, 1.0], [0, 2, 4, 6],
                    fx="{:.2f}", fy="{:.0f}")
    s = V.axes(s, a.L, a.R, a.T, a.B, "lateral acceleration (g)",
               "wheel load (kN)", xt, yt)
    for corner, colour, label in (("fr", V.COR, "outside front"),
                                  ("rr", V.AMB, "outside rear"),
                                  ("fl", V.TEAL, "inside front"),
                                  ("rl", V.VIO, "inside rear")):
        vals = np.array([q.loads[corner] / 1000 for q in points])
        s += (f'<path d="{V.path(a.pts(ay, vals))}" fill="none" '
              f'stroke="{colour}" stroke-width="2.2"/>')
        s += D.text(a.R - 6, float(a.y(vals[-1])) + 4, label, colour, 10.5, "end")
    s += D.text(a.L + 12, a.B - 14,
                "the four always sum to the car's weight", V.MUT, 10.5)

    b = _Ax(660, 1010, 140, 450, 0.38, 0.72, -0.1, 0.45)
    s += D.panel_title(660, 122, "B - The anti-roll bar")
    s = V.grid(s, b.L, b.R, b.T, b.B, 4, 4)
    xt, yt = _ticks(b, [0.4, 0.5, 0.6, 0.7], [0.0, 0.2, 0.4],
                    fx="{:.1f}", fy="{:+.1f}")
    s = V.axes(s, b.L, b.R, b.T, b.B, "front share of roll stiffness",
               "K (deg/g)", xt, yt)
    ks = list(arb)
    s += (f'<path d="{V.path(b.pts(ks, [arb[e] for e in ks]))}" fill="none" '
          f'stroke="{V.COR}" stroke-width="2.6"/>')
    for e in ks:
        s += (f'<circle cx="{float(b.x(e)):.1f}" cy="{float(b.y(arb[e])):.1f}" '
              f'r="3.5" fill="{V.COR}"/>')
    s += (f'<path d="{V.path(b.pts(ks, [arb_bicycle[e] for e in ks]))}" '
          f'fill="none" stroke="{V.SLATE}" stroke-width="2.2" '
          f'stroke-dasharray="7 5"/>')
    s += D.text(b.R - 6, float(b.y(arb[ks[-1]])) - 10, "four wheels", V.COR,
                11, "end", weight="600")
    s += D.text(b.R - 6, float(b.y(arb_bicycle[ks[-1]])) + 18,
                "two wheels - flat", V.SLATE, 11, "end")
    s += D.text(b.L + 10, b.B - 14,
                "the bicycle model cannot see the bar at all", V.MUT, 10.5)

    c = _Ax(1100, 1420, 140, 450, 0, 1.8, 0, 4.0)
    s += D.panel_title(1100, 122, "C - How close to lifting a wheel")
    s = V.grid(s, c.L, c.R, c.T, c.B, 3, 4)
    xt, yt = _ticks(c, [0, 0.6, 1.2, 1.8], [0, 1, 2, 3, 4],
                    fx="{:.1f}", fy="{:.0f}")
    s = V.axes(s, c.L, c.R, c.T, c.B, "lateral acceleration (g)",
               "least-loaded wheel (kN)", xt, yt)
    mins = np.array([q.min_load / 1000 for q in points])
    s += (f'<path d="{V.path(c.pts(ay, mins))}" fill="none" stroke="{V.TEAL}" '
          f'stroke-width="2.6"/>')
    for x_, colour, label in ((g_full, V.AMB, "grip limit"),
                              (lift, V.COR, "wheel lifts"),
                              (backend.params.static_stability_factor, V.VIO,
                               "SSF")):
        s += (f'<line x1="{float(c.x(x_)):.1f}" y1="{c.T}" '
              f'x2="{float(c.x(x_)):.1f}" y2="{c.B}" stroke="{colour}" '
              f'stroke-width="1.4" stroke-dasharray="4 4"/>')
        s += D.text(float(c.x(x_)) - 5, c.T + 16, label, colour, 10, "end")
    s += D.text(c.L + 10, c.B - 14,
                "the car runs out of grip long before it lifts", V.MUT, 10.5)

    s += D.text(100, 500,
                f"Panel B is the Episode 5 result. Sweeping the front share of "
                f"roll stiffness across the documented 0.40-0.70 range moves the "
                f"understeer gradient from {min(arb.values()):+.2f} to "
                f"{max(arb.values()):+.2f} deg/g in the four-wheel model, and by "
                f"{max(arb_bicycle.values())-min(arb_bicycle.values()):.0e} deg/g "
                f"in the two-wheel one. Not approximated -- invisible.", V.MUT, 11.5)
    s += D.text(100, 522,
                f"But note what did NOT happen: at the nominal setup K went "
                f"{k_bicycle:.2f} -> {k_full:.2f} deg/g, essentially unchanged. "
                f"Both axles lose grip to transfer and the losses nearly cancel. "
                f"The remaining gap to a real car's 1.8-5.5 deg/g is suspension "
                f"compliance, roll camber and roll steer -- not this term.",
                V.MUT, 11.5)
    s += _stamp(H - 40, backend,
                "roll-share range [ASSUMED] §2, K noise floor 0.2 deg/g [SOURCED]")
    return s + V.foot(
        W, H,
        "Every curve here is a Gate 1 falsification check. The four loads summing "
        "to mg, the transfer scaling with height and inverse track, and wheel lift "
        "sitting below the static stability factor are all asserted exactly.",
    )


# ---------------------------------------------------------------------------


def anti_roll_bar_figure(backend, arb, arb_bicycle, soft=0.40, stiff=0.70) -> str:
    """The anti-roll bar, drawn. Two cars in the same corner, different bars.

    This is the Episode 5 result and it deserves better than a line on a graph:
    the whole point is that a bar chooses WHICH axle suffers the uneven load
    split, and that is a picture of four contact patches, not a slope.
    """
    from dataclasses import replace as _replace

    p = backend.params
    cases = []
    for share, name, note in ((soft, f"Soft front bar - {soft:.0%} of roll stiffness",
                               "the front axle shares its load more evenly"),
                              (stiff, f"Stiff front bar - {stiff:.0%}",
                               "the front axle takes more of the lean")):
        b = type(backend)(_replace(p, roll_stiffness_front_share=share))
        pts = [q for q in b.skidpad_sweep(30.0, np.arange(12.0, 17.5, 0.5))
               if q.converged]
        cases.append((share, name, note, max(pts, key=lambda q: q.a_y_g), arb[share]))
    lo = min(min(c[3].loads.values()) for c in cases)
    hi = max(max(c[3].loads.values()) for c in cases)

    W, H = 1480, 1020
    s = V.head(
        W, H,
        "What an anti-roll bar actually does",
        "Both cars are the same car in the same corner at the same speed. What a "
        "bar changes here is which end of the car absorbs the lean -- this sweep "
        "moves the front/rear split and holds the total roll stiffness fixed, "
        "which is what you get by stiffening one bar and softening the other.",
    )

    for i, (share, name, note, pt, k) in enumerate(cases):
        cx, cy = 360 + i * 700, 400
        s += D.panel_title(cx - 250, 152, name, note)
        s += D.arrow(cx, cy + 240, cx, cy - 240, V.MUT, 1.8, 10, dash="5 5")
        s += D.text(cx, cy - 252, "direction of travel", V.MUT, 10.5, "middle")
        fr = {c: (pt.loads[c] - lo) / max(hi - lo, 1.0) for c in pt.loads}
        s += D.car_plan(cx, cy, length=230, width=100, wheel_len=52, wheel_w=21,
                        steer_deg=D.screen_deg(pt.steer_deg),
                        heading_deg=D.screen_deg(-pt.sideslip_deg),
                        loads=(fr["fl"], fr["fr"], fr["rl"], fr["rr"]))
        colour = V.TEAL if i == 0 else V.COR
        s += D.text(cx - 148, cy - 74, "front", V.MUT, 10.5, "end")
        s += D.text(cx - 148, cy - 56,
                    f"{pt.lateral_transfer_front/1000:.2f} kN moved", colour,
                    13, "end", weight="600", mono=True)
        s += D.text(cx - 148, cy + 74, "rear", V.MUT, 10.5, "end")
        s += D.text(cx - 148, cy + 92,
                    f"{pt.lateral_transfer_rear/1000:.2f} kN moved", colour,
                    13, "end", weight="600", mono=True)
        s += D.text(cx + 148, cy - 56,
                    f"inside front {pt.loads['fl']/1000:.2f} kN", V.MUT, 11.5)
        s += D.text(cx + 148, cy + 92,
                    f"inside rear {pt.loads['rl']/1000:.2f} kN", V.MUT, 11.5)
        s += D.text(cx, cy + 290,
                    f"total moved: "
                    f"{(pt.lateral_transfer_front+pt.lateral_transfer_rear)/1000:.2f} kN",
                    V.FG, 12.5, "middle")
        s += D.text(cx, cy + 314, f"understeer gradient {k:+.2f} deg/g",
                    colour, 16, "middle", weight="600", mono=True)

    s += D.rule(60, 760, 1420, V.GRID)
    for i, line in enumerate([
        "The two cars move almost the same total load sideways. What differs is "
        "the split: the stiff-front car pushes more of it across the",
        "front axle and less across the rear.",
        "",
        "And an axle that shares its load unevenly makes less grip (Episode 2). "
        "So a stiff front bar deliberately weakens the front axle,",
        "which makes the car understeer more. That is the entire mechanism, and "
        "it is why a bar is the first thing anyone changes.",
        "",
        f"Measured: {arb[soft]:+.2f} deg/g with the soft front bar, "
        f"{arb[stiff]:+.2f} with the stiff one. The two-wheeled model of Episodes "
        f"1-4 returns {arb_bicycle[soft]:+.2f} for both --",
        "it has no left and right for a bar to act between, so the knob does not "
        "exist for it.",
        "",
        f"On the protocol: this sweep redistributes a fixed total roll stiffness, "
        f"so both cars here lean by the same "
        f"{p.roll_gradient_deg_per_g * cases[0][3].a_y_g:.1f}°. Bolting a bar ON "
        f"instead raises the total and the car",
        f"leans less as well -- down to "
        f"{p.roll_gradient_deg_per_g_with_bar(stiff) * cases[0][3].a_y_g:.1f}° at "
        f"{stiff:.0%} front share. Both protocols are real and they are not the "
        f"same experiment; see the body-roll figure.",
    ]):
        s += D.text(60, 800 + 22 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, backend,
                "roll-share range [ASSUMED] §2 - see FINDINGS F31: our bar "
                "authority is weak, trust the direction not the size")
    return s + V.foot(
        W, H,
        "Redistributing a fixed total roll stiffness changes which axle gives up "
        "first without changing how far the car leans. Adding stiffness does both "
        "-- and only the redistribution changes the balance.",
    )


def low_and_wide_figure(backend) -> str:
    """Why cornering cars are low and wide, drawn as four cars."""
    from dataclasses import replace as _replace

    p = backend.params
    variants = [
        (_replace(p), "RV-1 as it is", f"{p.com_height*1000:.0f} mm high, "
         f"{p.track_f*1000:.0f} mm wide", V.AMB),
        (_replace(p, com_height=p.com_height * 1.5), "Half again as tall",
         f"{p.com_height*1500:.0f} mm high", V.COR),
        (_replace(p, track_f=p.track_f * 1.25, track_r=p.track_r * 1.25),
         "A quarter wider", f"{p.track_f*1250:.0f} mm wide", V.TEAL),
    ]
    a_y = 8.0
    results = []
    for v, name, sub, colour in variants:
        b = type(backend)(v)
        loads = b.wheel_loads(0.0, a_y)
        results.append((name, sub, colour, loads,
                        0.5 * (loads["fr"] - loads["fl"]), b.wheel_lift_a_y()))
    lo = min(min(r[3].values()) for r in results)
    hi = max(max(r[3].values()) for r in results)

    W, H = 1480, 880
    s = V.head(
        W, H,
        "Why a cornering car wants to be low and wide",
        f"The same car cornering at {a_y/9.80665:.2f} g, with only its height or "
        f"its width changed. Contact-patch size is load. Nothing else differs -- "
        f"same mass, same tires, same corner.",
    )

    for i, (name, sub, colour, loads, transfer, lift) in enumerate(results):
        cx, cy = 300 + i * 440, 380
        s += D.panel_title(cx - 170, 152, name, sub)
        fr = {c: (loads[c] - lo) / max(hi - lo, 1.0) for c in loads}
        s += D.car_plan(cx, cy, length=200, width=88, wheel_len=46, wheel_w=18,
                        loads=(fr["fl"], fr["fr"], fr["rl"], fr["rr"]))
        s += D.text(cx, cy + 150, f"{transfer/1000:.2f} kN moved sideways",
                    colour, 14, "middle", weight="600", mono=True)
        s += D.text(cx, cy + 172,
                    f"inside front down to {loads['fl']/1000:.2f} kN",
                    V.MUT, 11.5, "middle")
        s += D.text(cx, cy + 196, f"lifts a wheel at {lift:.2f} g",
                    V.MUT, 11.5, "middle")
        base = results[0][4]
        if i:
            s += D.text(cx, cy + 224,
                        f"{100*(transfer-base)/base:+.0f}% vs the real car",
                        colour, 12.5, "middle", weight="600")

    s += D.rule(60, 660, 1420, V.GRID)
    for i, line in enumerate([
        "Transfer is mass x cornering force x height, divided by track width. Two "
        "levers, both geometric, neither costing anything at",
        "the tires: make the car lower, or make it wider. Half again as tall moves "
        "half again as much load; a quarter wider moves a fifth",
        "less.",
        "",
        "And every kilonewton moved sideways is grip thrown away, because the "
        "overloaded tire never repays what the unloaded one gave up.",
        "That is why the reference car's 460 mm centre of gravity is the number "
        "its engineers put in the press release, and why race cars are",
        "as low and as wide as the rules allow.",
    ]):
        s += D.text(60, 700 + 22 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, backend, f"evaluated at {a_y/9.80665:.2f} g [ASSUMED]")
    return s + V.foot(
        W, H,
        "Lowering the centre of gravity and widening the track are the only two "
        "ways to reduce load transfer without changing the tires or the corner. "
        "Everything else -- bars, springs -- only redistributes it.",
    )


# ---------------------------------------------------------------------------


def body_roll_figure(backend, points) -> str:
    """The car seen from behind, leaning. What a plan view cannot show.

    Every other figure in Season 1 is a plan view. Those are right for slip
    angles and racing lines and wrong for load transfer: a plan view can show
    that the outside tire carries more, but not why. This shows the mechanism —
    the body leans, the outside spring compresses, and load follows.
    """
    p = backend.params
    picks = [
        ("Standing still", 0.0),
        ("Gentle corner", 0.35),
        ("Hard corner", 0.75),
        ("At the limit", max(q.a_y_g for q in points)),
    ]
    lo = min(min(q.loads.values()) for q in points)
    hi = max(max(q.loads.values()) for q in points)
    static = backend.wheel_loads(0.0, 0.0)
    lo = min(lo, min(static.values()))
    hi = max(hi, max(static.values()))
    # ONE pixels-per-newton scale for the whole figure, set so the limit case
    # draws the derived roll gradient. Computing it per case (as an earlier
    # version did) normalises away the effect the figure exists to show: every
    # panel then leans by the same amount regardless of cornering force.
    limit = max(points, key=lambda z: z.a_y_g)
    static_corner = 0.5 * (static["fl"] + static["fr"])
    # Half the LATERAL split, not the gap to the static load. The front axle's
    # total is not its static total -- the constant-speed skidpad runs at
    # a_x = -v_y*r, which moves load fore and aft as well -- so measuring the
    # span against static made the drawn limit roll read 5.5 deg where the
    # derived gradient says 5.4. Small, but the figure quotes both numbers.
    span = max(0.5 * (limit.loads["fr"] - limit.loads["fl"]), 1.0)
    px_per_N = (170.0 * math.tan(math.radians(
        p.roll_gradient_deg_per_g * limit.a_y_g)) / (2.0 * span))

    W, H = 1480, 1400
    s = V.head(
        W, H,
        "Why the outside tires end up carrying the car",
        f"The same car seen from behind, turning left, at four cornering forces. "
        f"Roll angle is real, not drawn for effect: "
        f"{p.roll_gradient_deg_per_g:.1f} deg per g, computed from the spring "
        f"rates. Contact-patch width is load.",
    )
    s += D.text(40, 92,
                "The body leans, the outside spring compresses, the inside one "
                "extends -- and load follows the lean.", V.MUT, 11.5)

    for i, (label, a_y_g) in enumerate(picks):
        cx, cy = 240 + i * 336, 470
        if a_y_g == 0.0:
            loads = static
        else:
            q = min(points, key=lambda z: abs(z.a_y_g - a_y_g))
            loads = q.loads
            a_y_g = q.a_y_g
        # Spring deflection straight from load: a corner carrying more than its
        # static share compresses.
        defl = ((loads["fl"] - static_corner) * px_per_N,
                (loads["fr"] - static_corner) * px_per_N)
        fr = ((loads["fl"] - lo) / max(hi - lo, 1.0),
              (loads["fr"] - lo) / max(hi - lo, 1.0))
        s += D.panel_title(cx - 120, 160, label, f"{a_y_g:.2f} g")
        s += D.car_rear_view(cx, cy, track=170, defl=defl, loads=fr)
        roll = math.degrees(math.atan2(defl[1] - defl[0], 170.0))
        if a_y_g > 0.01:
            s += D.arrow(cx + 40, cy - 190, cx + 150, cy - 190, V.VIO, 2.6, 10)
            s += D.text(cx + 40, cy - 200,
                        "inertia pushes this way", V.VIO, 10.5)
        s += D.text(cx, cy + 34, f"roll {abs(roll):.1f}°", V.FG, 12.5, "middle",
                    mono=True)
        s += D.text(cx - 96, cy + 62, f"{loads['fl']/1000:.2f} kN", V.TEAL, 13,
                    "middle", weight="600", mono=True)
        s += D.text(cx + 96, cy + 62, f"{loads['fr']/1000:.2f} kN", V.COR, 13,
                    "middle", weight="600", mono=True)
        s += D.text(cx - 96, cy + 80, "inside", V.MUT, 10.5, "middle")
        s += D.text(cx + 96, cy + 80, "outside", V.MUT, 10.5, "middle")

    # ---- second row: what bolting a bar on does to the lean ---------------
    s += D.rule(60, 600, 1420, V.GRID)
    s += D.panel_title(60, 636,
                       "And now add an anti-roll bar",
                       f"All three at the same {limit.a_y_g:.2f} g. A bar is a "
                       f"spring, so adding one makes the car lean LESS as well as "
                       f"changing which axle takes the load. Front axle shown.")
    a_y = limit.a_y_g * G
    bars = [(0.40, "Rear bar added", "front share 40%"),
            (p.spring_only_roll_share, "Springs only",
             f"front share {p.spring_only_roll_share:.0%} - no bar at all"),
            (0.70, "Front bar added", "front share 70%")]
    bar_rolls = {}
    for share, label, sub in bars:
        i = [b[0] for b in bars].index(share)
        cx, cy = 300 + i * 440, 940
        bb = type(backend)(_replace(p, roll_stiffness_front_share=share))
        bl = bb.wheel_loads(0.0, a_y)
        roll = p.roll_gradient_deg_per_g_with_bar(share) * limit.a_y_g
        bar_rolls[share] = roll
        rate, end = p.bar_rate_for_share(share)
        # Deflection is set from the ROLL ANGLE here, not from load. With a bar
        # fitted the two genuinely decouple: the bar carries load across the axle
        # without the spring having to compress as far. The *direction* still
        # cannot disagree -- the outside spring compresses and the outside tire is
        # the loaded one -- but the magnitudes are no longer proportional, and
        # that decoupling is the whole point of the row.
        d = 0.5 * 170.0 * math.tan(math.radians(roll))
        fr = ((bl["fl"] - lo) / max(hi - lo, 1.0),
              (bl["fr"] - lo) / max(hi - lo, 1.0))
        s += D.panel_title(cx - 150, 700, label, sub)
        s += D.car_rear_view(cx, cy, track=170, defl=(-d, d), loads=fr)
        s += D.text(cx, cy + 34, f"roll {roll:.1f}°", V.FG, 14, "middle",
                    weight="600", mono=True)
        s += D.text(cx, cy + 58,
                    "no bar" if rate < 1.0
                    else f"{end} bar {rate/1000:.0f} kN.m/rad", V.MUT, 11,
                    "middle", mono=True)
        s += D.text(cx - 96, cy + 86, f"{bl['fl']/1000:.2f} kN", V.TEAL, 13,
                    "middle", weight="600", mono=True)
        s += D.text(cx + 96, cy + 86, f"{bl['fr']/1000:.2f} kN", V.COR, 13,
                    "middle", weight="600", mono=True)
        s += D.text(cx, cy + 108,
                    f"front axle moves "
                    f"{0.5*(bl['fr']-bl['fl'])/1000:.2f} kN across",
                    V.MUT, 11.5, "middle")

    s += D.rule(60, 1064, 1420, V.GRID)
    soft_r = bar_rolls[0.40]
    none_r = bar_rolls[p.spring_only_roll_share]
    stiff_r = bar_rolls[0.70]
    for i, line in enumerate([
        "Nothing is added to the car in the top row. The body leans because the "
        "cornering force acts at the tires and the weight acts through a",
        "centre of gravity 460 mm higher up, and that offset is a moment the "
        "springs have to resist. Resisting it means compressing on one side",
        "and extending on the other, which is the same thing as moving load across.",
        "",
        f"The bottom row adds a bar, and it does two separate things. The car "
        f"leans less: {none_r:.1f}° on springs alone, {stiff_r:.1f}° with a front "
        f"bar stiff enough to take 70% of the roll",
        f"stiffness, {soft_r:.1f}° with a rear bar taking the front down to 40%. "
        f"Any bar is extra stiffness, so the lean falls whichever end it goes on "
        f"-- the roll angle is",
        "LARGEST with no bar at all and drops either side of that, which is not "
        "what anyone expects from a knob labelled \"front stiffness\".",
        "",
        "And it moves more load across the axle it is fitted to. Those are two "
        "different effects and only the second changes the handling",
        "balance: less lean is a comfort and suspension-geometry gain, while the "
        "balance change is what a chassis engineer is actually buying.",
    ]):
        s += D.text(60, 1100 + 22 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, backend,
                f"roll angle [DERIVED] from spring rates "
                f"{p.spring_rate_front/1000:.0f}/{p.spring_rate_rear/1000:.0f} N/mm "
                "[SOURCED anchor / ASSUMED] plus the bar rate needed to reach each "
                "share; rigid-axle, no roll-centre geometry")
    return s + V.foot(
        W, H,
        "Roll angle is drawn from the spring and bar rates and is not a state of "
        "the model -- load transfer is computed from moment balance directly. The "
        "angle is here because it is the mechanism a plan view hides.",
    )


__all__ = ["four_wheel_figure", "body_roll_figure", "anti_roll_bar_figure",
           "low_and_wide_figure", "load_transfer_card"]
