"""Episode 13 figures — the two-layer torque-vectoring controller.

``two_layers_figure``
    The pictorial hero, and it is the episode's argument in one picture: on the
    left a car that is not turning as much as its driver asked, in the middle the
    single number that describes the gap, on the right the four wheels paying for
    it. Two layers, drawn as two panels, with one number passing between them.
``allocation_figure``
    Three moments in the same corner, each a car from above with a force arrow on
    every wheel drawn to the same scale. Turn-in, mid-corner and exit ask for
    opposite things, and you can see which wheel is being asked.
``limit_figure``
    The technical headline: lap time against how hard the driver is trying, for
    every configuration, with the point where each one falls off marked.
``tracking_figure``
    Yaw rate against distance — what was asked for, what the passive car did, what
    the controlled car did — with the moment demand underneath it.
``worth_figure``
    What it is worth, against the published ceiling, decomposed into the layer
    that earned it, and put through every sensitivity the conclusion has to
    survive.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V

COLOUR = {"open": V.SLATE, "lsd": V.AMB, "alloc": V.VIO, "tv4": V.TEAL,
          "tvrear": V.GRN}
CORNERS = ("fl", "fr", "rl", "rr")


class _Ax:
    def __init__(self, L, R, T, B, x0, x1, y0, y1):
        self.L, self.R, self.T, self.B = L, R, T, B
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1

    def x(self, v):
        return self.L + (self.R - self.L) * (np.asarray(v, dtype=float)
                                             - self.x0) / (self.x1 - self.x0)

    def y(self, v):
        return self.B - (self.B - self.T) * (np.asarray(v, dtype=float)
                                             - self.y0) / (self.y1 - self.y0)

    def pts(self, xs, ys):
        return list(zip(np.atleast_1d(self.x(xs)), np.atleast_1d(self.y(ys))))


def _stamp(y: float, r) -> str:
    """Provenance, on two lines because one does not fit at 1540 px."""
    rm = r["reference_model"]
    return (D.text(40, y - 13, "  -  ".join([
        f"[MEASURED] double-track model, closed-loop driver, {r['track']['name']} "
        f"({r['track']['length_m']:.0f} m), grip_use swept to failure",
        f"[MEASURED] reference model K={rm['k_deg_per_g']:.2f} deg/g, grip ceiling "
        f"{rm['a_y_max_g']:.2f} g",
    ]), V.MUT, 9.5)
        + D.text(40, y, "  -  ".join([
            "[SOURCED — CITATION OUTSTANDING] ~9% skidpad ceiling, FSAE",
            "[LIKELY] track width — the moment arm; conclusion re-run at +/-3%",
            "RUNG 2 — ordering and direction only, not a real car (rule 15)",
        ]), V.MUT, 9.5))


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


def _paragraph(x, y, text, width=118, size=12.5, colour=V.MUT, dy=21):
    return "".join(D.text(x, y + dy * i, ln, colour, size)
                   for i, ln in enumerate(_wrap(text, width)))


def _corner_index(r, key="tv4_control"):
    """The instant in the corner where the controller is working hardest."""
    mz = np.abs(np.asarray(r["traces"][key]["mz_demand"]))
    s = np.asarray(r["traces"]["tv4"]["s"])
    m = (s > r["track"]["section"][0]) & (s < r["track"]["section"][1])
    idx = np.where(m)[0]
    return int(idx[np.argmax(mz[idx])])


def _rotation_fan(cx, cy, radius, rate_ref, rate_act, seconds=1.0):
    """Two arcs whose SPAN is how far the car turns in one second, and the gap.

    The first version of this drew two arcs of a fixed span at different radii,
    which encoded the *sign* of each yaw rate and nothing else — two numbers that
    differ by 9% rendered as two identical arcs, and a reader comparing them would
    have been comparing a decoration. Span proportional to rate is the honest
    version: the amber arc really is longer than the grey one by exactly the
    fraction the numbers differ by, and the wedge between their tips is the error
    the controller is being asked to close.
    """
    def tip(rate, rr):
        a = math.degrees(rate * seconds)
        return (cx + rr * math.sin(math.radians(a)),
                cy - rr * math.cos(math.radians(a)), a)

    # Straight-ahead reference, and a ray to each tip, so the arcs read as ANGLES
    # swept from the car rather than as two free-floating curves.
    out = (f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" '
           f'y2="{cy - radius - 40:.1f}" stroke="{V.GRID}" stroke-width="1.4" '
           f'stroke-dasharray="5 5"/>')
    for rate, rr, colour in ((rate_act, radius, V.SLATE),
                             (rate_ref, radius + 30, V.AMB)):
        xt, yt, _ = tip(rate, rr)
        out += (f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{xt:.1f}" y2="{yt:.1f}" '
                f'stroke="{colour}" stroke-width="1.2" opacity="0.5"/>')
    for rate, rr, colour in ((rate_act, radius, V.SLATE),
                             (rate_ref, radius + 30, V.AMB)):
        x1, y1, a = tip(rate, rr)
        sweep = 1 if a > 0 else 0
        out += (f'<path d="M {cx:.1f},{cy - rr:.1f} A {rr:.0f},{rr:.0f} 0 0 '
                f'{sweep} {x1:.1f},{y1:.1f}" fill="none" stroke="{colour}" '
                f'stroke-width="3.2"/>')
        tang = math.radians(a) + (math.pi / 2 if sweep == 1 else -math.pi / 2)
        out += D.arrow(x1 - 13 * math.cos(tang), y1 - 13 * math.sin(tang), x1, y1,
                       colour, 3.2, 13)
    # the shortfall, between the two tips, on the outer radius
    xr, yr, ar = tip(rate_ref, radius + 30)
    xa, ya, aa = tip(rate_act, radius + 30)
    sweep = 1 if ar > aa else 0
    out += (f'<path d="M {xa:.1f},{ya:.1f} A {radius+30:.0f},{radius+30:.0f} 0 0 '
            f'{sweep} {xr:.1f},{yr:.1f}" fill="none" stroke="{V.COR}" '
            f'stroke-width="8" opacity="0.55" stroke-linecap="round"/>')
    out += D.text(cx, cy - radius - 66,
                  f"where the nose points after {seconds:.0f} s", V.MUT, 11.5,
                  "middle")
    return out


def _yaw_arc(cx, cy, radius, magnitude, colour, label=None, span=52.0):
    """An arc around the car showing which way it is being twisted, and how hard."""
    import math as _m
    a0, a1 = -span, span
    sweep = 1 if magnitude < 0 else 0          # negative = nose right = clockwise
    p0 = (cx + radius * _m.sin(_m.radians(a0)),
          cy - radius * _m.cos(_m.radians(a0)))
    p1 = (cx + radius * _m.sin(_m.radians(a1)),
          cy - radius * _m.cos(_m.radians(a1)))
    (sx, sy), (ex, ey) = (p0, p1) if sweep == 1 else (p1, p0)
    out = (f'<path d="M {sx:.1f},{sy:.1f} A {radius:.0f},{radius:.0f} 0 0 '
           f'{sweep} {ex:.1f},{ey:.1f}" fill="none" stroke="{colour}" '
           f'stroke-width="3.2" opacity="0.9"/>')
    tip = a1 if sweep == 1 else a0
    tang = _m.radians(tip) + (_m.pi / 2 if sweep == 1 else -_m.pi / 2)
    out += D.arrow(ex - 14 * _m.cos(tang), ey - 14 * _m.sin(tang), ex, ey,
                   colour, 3.2, 14)
    if label:
        out += D.text(cx, cy - radius - 16, label, colour, 12.5, "middle",
                      weight="600")
    return out


def _wheel_forces(s, cx, cy, forces, caps, scale, car_len=250.0, car_w=118.0,
                  wheel_w=24.0, show_caps=True):
    """Longitudinal force arrows on all four wheels, to a stated scale.

    Screen: the car is drawn nose-up, so a forward force is an arrow pointing UP
    the page and a braking force points down. The car's left-hand wheels are drawn
    on the left, which is what you see looking down on a car pointing away from
    you — the same convention ``diagram.car_plan`` uses for its own wheels.
    """
    hw = car_w / 2.0
    ax_f, ax_r = -car_len * 0.30, car_len * 0.30
    for corner, (dx, dy) in zip(CORNERS, ((-1, ax_f), (1, ax_f),
                                          (-1, ax_r), (1, ax_r))):
        wx, wy = cx + dx * (hw + wheel_w * 0.35), cy + dy
        f = forces[corner]
        if show_caps and caps:
            cap = caps[corner] * scale
            s += (f'<line x1="{wx:.1f}" y1="{wy - cap:.1f}" x2="{wx:.1f}" '
                  f'y2="{wy + cap:.1f}" stroke="{V.GRID}" stroke-width="9" '
                  f'stroke-linecap="round" opacity="0.85"/>')
        length = f * scale
        colour = V.TEAL if f >= 0 else V.COR
        if abs(length) > 1.5:
            s += D.arrow(wx, wy, wx, wy - length, colour, 4.4, 12)
        s += D.text(wx + (16 if dx > 0 else -16), wy - length / 2 + 4,
                    f"{f:+.0f}", colour, 12, "start" if dx > 0 else "end",
                    weight="600", mono=True)
    return s


# ---------------------------------------------------------------------------
# 1. the hero
# ---------------------------------------------------------------------------

def two_layers_figure(r) -> str:
    W, H = 1560, 1000
    tr, ct = r["traces"]["tv4"], r["traces"]["tv4_control"]
    i = _corner_index(r)
    r_ref, r_act = ct["r_ref"][i], ct["r"][i]
    mz = ct["mz_demand"][i]
    forces = {c: tr[f"fx_{c}"][i] for c in CORNERS}
    tire_peak = {c: abs(tr[f"fx_{c}"][i]) for c in CORNERS}

    s = V.head(
        W, H,
        "Two layers: how much to rotate, and who pays for it",
        "One instant in one left-hand corner. The driver has asked for more "
        "rotation than the car is producing; a controller turns that gap into a "
        "single number, and an allocator turns that number into four forces.")

    # -- panel A: the gap ---------------------------------------------------
    ax, ay = 300, 430
    s += D.panel_title(70, 150, "1. How much do you want to rotate?",
                       "A reference model says what this steering angle at this "
                       "speed should produce.")
    s += D.car_plan(ax, ay, length=250, width=118, wheel_len=54, wheel_w=24,
                    steer_deg=D.screen_deg(math.degrees(tr["steer"][i])),
                    loads=(0.55, 0.8, 0.55, 0.8), body=V.MUT)
    s += _rotation_fan(ax, ay, 150, r_ref, r_act)
    s += D.text(70, ay + 190, f"asked for   {r_ref:+.3f} rad/s "
                f"({math.degrees(r_ref):+.1f} deg/s)", V.AMB, 14,
                weight="600", mono=True)
    s += D.text(70, ay + 214, f"getting     {r_act:+.3f} rad/s "
                f"({math.degrees(r_act):+.1f} deg/s)", V.SLATE, 14,
                weight="600", mono=True)
    s += D.text(70, ay + 244,
                f"short by {abs(r_ref - r_act):.3f} rad/s", V.COR, 13,
                weight="600", mono=True)
    s += _paragraph(70, ay + 278,
                    "The car is not turning as tightly as the linear model says "
                    "it should. Its front tires are near their peak and have "
                    "stopped repaying steering angle with cornering force.", 46)

    # -- panel B: one number ------------------------------------------------
    bx = 700
    s += D.panel_title(bx - 60, 150, "2. One number",
                       "The upper layer's entire output.")
    s += (f'<rect x="{bx - 80:.0f}" y="{ay - 90:.0f}" width="300" height="180" '
          f'rx="14" fill="none" stroke="{V.COR}" stroke-width="2" '
          f'opacity="0.8"/>')
    s += D.text(bx + 70, ay - 40, "desired yaw moment", V.MUT, 12.5, "middle")
    s += D.text(bx + 70, ay + 14, f"{mz:+.0f}", V.COR, 44, "middle",
                weight="700", mono=True)
    s += D.text(bx + 70, ay + 44, "N.m", V.COR, 15, "middle")
    s += D.text(bx + 70, ay + 74,
                "PID on the gap, one scalar", V.MUT, 11.5, "middle")
    s += D.arrow(bx - 110, ay, bx - 84, ay, V.MUT, 2.2, 10)
    s += D.arrow(bx + 224, ay, bx + 252, ay, V.MUT, 2.2, 10)
    s += _paragraph(bx - 80, ay + 140,
                    "The upper layer knows nothing about wheels. Everything it has "
                    "learned about the car is in this one number, which is what "
                    "makes the two halves separable at all.", 40)

    # -- panel C: who pays --------------------------------------------------
    cx, cy = 1180, 430
    s += D.panel_title(1010, 150, "3. Which wheels pay for it?",
                       "A QP spends the leftover freedom on tire workload.")
    s += D.car_plan(cx, cy, length=250, width=118, wheel_len=54, wheel_w=24,
                    steer_deg=D.screen_deg(math.degrees(tr["steer"][i])),
                    loads=(0.55, 0.8, 0.55, 0.8), body=V.MUT)
    scale = 100.0 / max(300.0, max(abs(v) for v in forces.values()))
    s = _wheel_forces(s, cx, cy, forces, tire_peak, scale, show_caps=False)
    s += _yaw_arc(cx, cy, 215, mz, V.COR,
                  "and the car rotates" if mz > 0 else "and the car is held back")
    total = sum(forces.values())
    s += D.text(1010, cy + 250,
                f"total drive     {total:+.0f} N", V.FG, 13.5, weight="600",
                mono=True)
    s += D.text(1010, cy + 274,
                f"left/right gap  "
                f"{(forces['fr'] + forces['rr']) - (forces['fl'] + forces['rl']):+.0f} N",
                V.COR, 13.5, weight="600", mono=True)
    s += _paragraph(1010, cy + 308,
                    "The driver's demand for total force is met exactly; the "
                    "difference between the right-hand wheels and the left-hand "
                    "ones is the moment. More force on the right turns the nose "
                    "left.", 46)

    s += D.rule(70, 830, W - 140, V.GRID)
    for i2, line in enumerate(_wrap(
            "That split — one layer deciding how much rotation you want, another "
            "deciding who pays — is the classical architecture, and the reason it "
            "has lasted is that the halves can be built, tuned and argued about "
            "separately. The upper layer is a vehicle-dynamics judgement with two "
            "numbers in it. The lower layer is a convex optimisation with a unique "
            "answer. Neither has to know how the other works.", 148)):
        s += D.text(70, 864 + 22 * i2, line, V.MUT, 13)

    s += _stamp(H - 40, r)
    return s + V.foot(
        W, H,
        "Arrow length is longitudinal force at the contact patch, to scale within "
        "the panel; teal pushes forward, red drags back. Both cars are drawn "
        "nose-up and are turning left. One instant, taken where the controller is "
        "working hardest.")


# ---------------------------------------------------------------------------
# 2. three moments
# ---------------------------------------------------------------------------

def _demand_sentence(mz: float, phase: str, r_ref: float, r_act: float) -> str:
    """The explanation, composed from the sign rather than written next to it.

    The first version of this figure carried three hand-written sentences, and one
    of them said the controller was working *against* the car's rotation directly
    beneath a number saying it was adding +809 N.m of it. That is F68's failure
    mode — a caption that contradicts its own curve, internally consistent within
    each half, visible in ten seconds of looking. Deriving the words from the
    number makes it unrepresentable.
    """
    gap = r_ref - r_act
    if abs(mz) < 60.0:
        return (f"{phase} The car is turning within {abs(gap):.3f} rad/s of what "
                f"was asked, so there is almost nothing for the controller to do "
                f"and the allocator is simply feeding the driven axle.")
    if abs(gap) < 0.005:
        # A standing moment with no visible error is the integral term holding the
        # car where the proportional term put it. Saying "0.000 rad/s less, so it
        # adds rotation" instead would read as a contradiction, which is how the
        # sentence came out the first time this was generated.
        return (f"{phase} The error has been driven to almost nothing "
                f"({abs(gap):.3f} rad/s), and the {abs(mz):.0f} N.m holding it "
                f"there is the PID's integral term: a standing moment, not a "
                f"correction.")
    if mz > 0.0:
        return (f"{phase} The car is turning {abs(gap):.3f} rad/s LESS than the "
                f"reference asks, so the controller adds rotation: more force to "
                f"the right-hand wheels than the left.")
    return (f"{phase} The car is turning {abs(gap):.3f} rad/s MORE than the "
            f"reference asks, so the controller takes rotation away: more force "
            f"to the left-hand wheels than the right.")


def allocation_figure(r) -> str:
    W, H = 1560, 980
    tr, ct = r["traces"]["tv4"], r["traces"]["tv4_control"]
    s_arr = np.asarray(tr["s"])
    picks = []
    for target, title, phase in (
            (78.0, "Turn-in", "Just past the brake point, still loading up the "
             "front tires."),
            (105.0, "Mid-corner", "Steady state, at the highest lateral "
             "acceleration of the lap."),
            (135.0, "Exit", "Power down, unwinding the steering.")):
        i = int(np.argmin(np.abs(s_arr - target)))
        picks.append((i, title,
                      _demand_sentence(ct["mz_demand"][i], phase,
                                       ct["r_ref"][i], ct["r"][i])))

    s = V.head(
        W, H,
        "The same controller asks for opposite things in one corner",
        "Three moments from a single lap of the same 40 m corner. Force arrows are "
        "to one scale across all three panels, and the grey bar behind each wheel "
        "is what that tire had left to give.")

    scale = 92.0 / 2600.0
    for k, (i, title, why) in enumerate(picks):
        L = 60 + k * 500
        cx, cy = L + 210, 420
        forces = {c: tr[f"fx_{c}"][i] for c in CORNERS}
        s += D.text(L, 152, title, V.FG, 18, weight="600")
        s += D.text(L, 176,
                    f"{s_arr[i]:.0f} m along the road   {tr['speed'][i]:.1f} m/s",
                    V.MUT, 12)
        loads = [tr[f"fz_{c}"][i] for c in CORNERS]
        lmax = max(loads) or 1.0
        s += D.car_plan(cx, cy, length=230, width=110, wheel_len=50, wheel_w=22,
                        steer_deg=D.screen_deg(math.degrees(tr["steer"][i])),
                        loads=tuple(l / lmax for l in loads), body=V.MUT)
        caps = {c: max(abs(tr[f"fx_{c}"][i]), 1.0) for c in CORNERS}
        s = _wheel_forces(s, cx, cy, forces, caps, scale, car_len=230,
                          car_w=110, wheel_w=22, show_caps=False)
        mz = ct["mz_demand"][i]
        s += _yaw_arc(cx, cy, 168, mz if abs(mz) > 1 else 1.0,
                      V.COR if abs(mz) > 50 else V.GRID)
        s += D.text(L, cy + 230, f"{mz:+.0f} N.m asked for",
                    V.COR if abs(mz) > 50 else V.MUT, 15, weight="600",
                    mono=True)
        gap = (forces["fr"] + forces["rr"]) - (forces["fl"] + forces["rl"])
        s += D.text(L, cy + 256, f"{gap:+.0f} N right minus left", V.MUT, 13,
                    mono=True)
        s += _paragraph(L, cy + 292, why, 46)

    s += D.rule(60, 820, W - 120, V.GRID)
    for i2, line in enumerate(_wrap(
            "A differential cannot do this. It has one behaviour, set by which "
            "wheel is turning faster, and Episode 12 showed that the same device "
            "therefore pushes the car wide at part throttle and turns it in when "
            "the inside wheel spins. A controller chooses, instant by instant, and "
            "the three panels above are the same hardware being asked for three "
            "different things inside one corner.", 148)):
        s += D.text(60, 856 + 22 * i2, line, V.MUT, 13)

    s += _stamp(H - 34, r)
    return s + V.foot(
        W, H,
        "One lap, at the highest aggression both the passive and the controlled "
        "car complete. Contact-patch shading is vertical load. Teal pushes the car "
        "forward, red drags it back; the car is nose-up and turning left.")


# ---------------------------------------------------------------------------
# 3. the limit
# ---------------------------------------------------------------------------

def limit_figure(r) -> str:
    W, H = 1540, 980
    s = V.head(
        W, H,
        "How hard can the driver try before the car cannot do it?",
        "Same driver, same line, same speed plan. The plan is built for a fraction "
        "of the car's measured grip; turn that fraction up and the lap gets "
        "quicker until the car runs out of road or slides past the tire fit.")

    rows = {c: r["sweeps"][c] for c in r["conditions"]}
    valid_t = [p["lap_time"] for c in rows for p in rows[c] if p["valid"]]
    gus = [p["grip_use"] for c in rows for p in rows[c]]
    ax = _Ax(150, 1010, 200, 660, min(gus) - 0.01, max(gus) + 0.01,
             min(valid_t) - 0.15, max(valid_t) + 0.15)
    s += D.panel_title(150, 178, "Lap time against how hard the driver tries")
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 6, 4)
    xt = [(f"{v:.2f}", float(ax.x(v)))
          for v in np.arange(0.85, 1.1501, 0.05)]
    yt = [(f"{v:.1f}", float(ax.y(v)))
          for v in np.arange(math.floor(min(valid_t) * 10) / 10,
                             max(valid_t) + 0.15, 0.2)]
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B,
               "grip_use  —  the fraction of measured grip the speed plan assumes",
               "lap time (s)", xt, yt)

    for c in r["conditions"]:
        pts = [(p["grip_use"], p["lap_time"]) for p in rows[c] if p["valid"]]
        if pts:
            s += (f'<path d="{V.path(ax.pts([p[0] for p in pts], [p[1] for p in pts]))}" '
                  f'fill="none" stroke="{COLOUR[c]}" stroke-width="2.8" '
                  f'opacity="0.95"/>')
        lim = r["limits"][c]
        x = float(ax.x(lim))
        s += (f'<line x1="{x:.1f}" y1="{ax.T}" x2="{x:.1f}" y2="{ax.B}" '
              f'stroke="{COLOUR[c]}" stroke-width="1.6" stroke-dasharray="5 5" '
              f'opacity="0.75"/>')
        b = r["best"][c]
        if b:
            s += (f'<circle cx="{float(ax.x(b["grip_use"])):.1f}" '
                  f'cy="{float(ax.y(b["lap_time"])):.1f}" r="6" fill="{V.BG}" '
                  f'stroke="{COLOUR[c]}" stroke-width="2.6"/>')

    s += D.text(ax.R - 6, ax.T - 10,
                "dashed line = the last aggression this car survives", V.MUT,
                11.5, "end")

    ly = 220
    s += D.text(1060, ly - 30, "the five configurations", V.FG, 15, weight="600")
    order = sorted(r["conditions"], key=lambda c: -r["limits"][c])
    for i, c in enumerate(order):
        y = ly + i * 88
        b = r["best"][c]
        s += (f'<line x1="1060" y1="{y-5}" x2="1102" y2="{y-5}" '
              f'stroke="{COLOUR[c]}" stroke-width="3.4"/>')
        s += D.text(1114, y, r["labels"][c], COLOUR[c], 13.5, weight="600")
        s += D.text(1060, y + 24, f"limit  {r['limits'][c]:.3f}", V.MUT, 12,
                    mono=True)
        s += D.text(1060, y + 42,
                    f"best   {b['lap_time']:.3f} s" if b else "no valid lap",
                    V.MUT, 12, mono=True)
        s += D.text(1060, y + 60,
                    f"peak   {b['peak_a_y_g']:.3f} g" if b else "", V.MUT, 12,
                    mono=True)

    s += D.rule(150, 736, W - 300, V.GRID)
    g = r["gains"]
    for i, line in enumerate(_wrap(
            f"Every configuration drives the same plan, so at any point on this "
            f"axis they are all attempting the same lap and take nearly the same "
            f"time. The whole result is how far right each line reaches: the "
            f"passive car gives up at {r['limits']['open']:.3f}, the controlled one "
            f"at {r['limits']['tv4']:.3f}, which is {g['limit_pct']:+.1f}% more "
            f"cornering grip demanded and survived — and only "
            f"{g['lap_pct']:+.2f}% of lap time, because two thirds of this lap is a "
            f"straight where the controller has nothing to do.", 148)):
        s += D.text(150, 770 + 22 * i, line, V.MUT, 13)

    s += _stamp(H - 40, r)
    return s + V.foot(
        W, H,
        "Circles mark each configuration's quickest valid lap. A lap counts as "
        "valid only if it stayed on the road AND inside the +/-12 degree tire fit; "
        "invalid laps are discarded, not plotted as fast times.")


# ---------------------------------------------------------------------------
# 4. tracking
# ---------------------------------------------------------------------------

def tracking_figure(r) -> str:
    W, H = 1540, 1060
    tv, op, ct = r["traces"]["tv4"], r["traces"]["open"], r["traces"]["tv4_control"]
    s0, s1 = r["track"]["section"]
    s = V.head(
        W, H,
        "What the controller is actually doing",
        "Yaw rate through the corner: what the reference model asked for, what the "
        "passive car did, and what the controlled car did. Underneath, the moment "
        "the upper layer demanded and the moment the wheels delivered.")

    sa_tv, sa_op = np.asarray(tv["s"]), np.asarray(op["s"])
    m_tv = (sa_tv >= s0) & (sa_tv <= s1)
    m_op = (sa_op >= s0) & (sa_op <= s1)
    r_ref = np.asarray(ct["r_ref"])[m_tv]
    r_tv = np.asarray(ct["r"])[m_tv]
    r_op = np.asarray(op["yaw_rate"])[m_op]
    ref_op = np.asarray(r["traces"]["open_r_ref"])[m_op]
    lo = float(min(r_ref.min(), r_tv.min(), r_op.min())) - 0.05
    hi = float(max(r_ref.max(), r_tv.max(), r_op.max())) + 0.05

    ax = _Ax(150, 1400, 200, 520, s0, s1, lo, hi)
    s += D.panel_title(150, 178, "Yaw rate through the corner")
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 6, 4)
    xt = [(f"{v:.0f}", float(ax.x(v))) for v in np.arange(s0, s1 + 1, 20)]
    yt = [(f"{v:+.1f}", float(ax.y(v))) for v in np.arange(-0.6, 0.81, 0.2)
          if lo <= v <= hi]
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "distance along the road (m)",
               "yaw rate (rad/s)", xt, yt)

    s += (f'<path d="{V.path(ax.pts(sa_tv[m_tv], r_ref))}" fill="none" '
          f'stroke="{V.AMB}" stroke-width="2.4" stroke-dasharray="7 5"/>')
    s += (f'<path d="{V.path(ax.pts(sa_op[m_op], r_op))}" fill="none" '
          f'stroke="{COLOUR["open"]}" stroke-width="2.6"/>')
    s += (f'<path d="{V.path(ax.pts(sa_tv[m_tv], r_tv))}" fill="none" '
          f'stroke="{COLOUR["tv4"]}" stroke-width="2.8"/>')
    # Legend in the empty lower-left of the panel: the curves all live in the top
    # half here, and a legend laid over the reference line is a legend that hides
    # the thing it is naming.
    for i, (lbl, col) in enumerate((("what was asked for (reference model)", V.AMB),
                                    ("passive car", COLOUR["open"]),
                                    ("controlled car", COLOUR["tv4"]))):
        y = ax.B - 76 + 22 * i
        s += (f'<line x1="{ax.L + 20}" y1="{y - 5}" x2="{ax.L + 62}" '
              f'y2="{y - 5}" stroke="{col}" stroke-width="3"/>')
        s += D.text(ax.L + 74, y, lbl, col, 12.5)
    t = r["tracking"]
    # Outside the plot box entirely, on the title line. Every corner INSIDE it is
    # crossed by one of the three curves at some point, and a number laid over the
    # curve it describes is a number the reader has to work around.
    s += D.text(ax.R - 8, ax.T - 38,
                f"RMS error against the same reference, through this corner",
                V.MUT, 12, "end")
    s += D.text(ax.R - 8, ax.T - 18,
                f"passive {t['yaw_rms_open']:.4f} rad/s   controlled "
                f"{t['yaw_rms_tv']:.4f} rad/s   "
                f"({100*(1-t['yaw_rms_tv']/t['yaw_rms_open']):.0f}% lower)",
                COLOUR["tv4"], 12.5, "end", mono=True)

    mz_d = np.asarray(ct["mz_demand"])[m_tv]
    mz_a = np.asarray(ct["mz_delivered"])[m_tv]
    mlo = float(min(mz_d.min(), mz_a.min())) - 200
    mhi = float(max(mz_d.max(), mz_a.max())) + 200
    ax2 = _Ax(150, 1400, 630, 860, s0, s1, mlo, mhi)
    s += D.panel_title(150, 608, "The one number passing between the layers")
    s = V.grid(s, ax2.L, ax2.R, ax2.T, ax2.B, 6, 4)
    yt2 = [(f"{v:+.0f}", float(ax2.y(v)))
           for v in np.arange(-1500.0, 1501.0, 500.0) if mlo <= v <= mhi]
    s = V.axes(s, ax2.L, ax2.R, ax2.T, ax2.B, "distance along the road (m)",
               "yaw moment (N.m)", xt, yt2)
    s += (f'<line x1="{ax2.L}" y1="{float(ax2.y(0.0)):.1f}" x2="{ax2.R}" '
          f'y2="{float(ax2.y(0.0)):.1f}" stroke="{V.FG}" stroke-width="1.2" '
          f'stroke-dasharray="6 5" opacity="0.5"/>')
    s += (f'<path d="{V.path(ax2.pts(sa_tv[m_tv], mz_d))}" fill="none" '
          f'stroke="{V.COR}" stroke-width="4.5" opacity="0.9"/>')
    # Wide dashes, on top: the two lines agree so closely that a thin dash
    # disappeared into the line underneath it, and a reader saw one curve where
    # the caption promised two.
    s += (f'<path d="{V.path(ax2.pts(sa_tv[m_tv], mz_a))}" fill="none" '
          f'stroke="{V.TEAL}" stroke-width="2.2" stroke-dasharray="10 8"/>')
    s += (f'<line x1="{ax2.L + 20}" y1="{ax2.T + 19}" x2="{ax2.L + 56}" '
          f'y2="{ax2.T + 19}" stroke="{V.COR}" stroke-width="4.5"/>')
    s += D.text(ax2.L + 66, ax2.T + 24, "demanded by the PID", V.COR, 12.5)
    s += (f'<line x1="{ax2.L + 20}" y1="{ax2.T + 39}" x2="{ax2.L + 56}" '
          f'y2="{ax2.T + 39}" stroke="{V.TEAL}" stroke-width="2.2" '
          f'stroke-dasharray="10 8"/>')
    s += D.text(ax2.L + 66, ax2.T + 44,
                f"delivered by the wheels — the dashes sit on the solid line "
                f"because it is never short by more than "
                f"{t['mz_delivery_error']:.0f} N.m", V.TEAL, 12.5)
    s += D.text(ax2.R - 8, ax2.T + 24, "positive = turn the nose IN", V.MUT,
                11.5, "end")
    s += D.text(ax2.R - 8, ax2.T + 44, "negative = hold the rotation BACK",
                V.MUT, 11.5, "end")

    # Composed from the trace, not written beside it. The hand-written version of
    # this sentence said the controller held the car back at turn-in and added
    # rotation on exit, which is precisely backwards for this lap — and it sat
    # directly under a curve saying so. Same defect as the one in the allocation
    # figure, same fix.
    s_corner = sa_tv[m_tv]
    i_hi, i_lo = int(np.argmax(mz_d)), int(np.argmin(mz_d))
    s += D.rule(150, 892, W - 300, V.GRID)
    for i, line in enumerate(_wrap(
            f"The demand changes sign inside the corner. It peaks at "
            f"{mz_d[i_hi]:+.0f} N.m at {s_corner[i_hi]:.0f} m — adding rotation, "
            f"because the front tires are saturating and the car is no longer "
            f"turning as much as a linear model says it should — and reaches "
            f"{mz_d[i_lo]:+.0f} N.m at {s_corner[i_lo]:.0f} m, taking rotation "
            f"away as the steering unwinds faster than the car's rotation decays. "
            f"Between the two it settles to a small steady value. A yaw controller "
            f"is mostly a transient device.", 148)):
        s += D.text(150, 926 + 22 * i, line, V.MUT, 13)

    s += _stamp(H - 34, r)
    return s + V.foot(
        W, H,
        f"Both laps at grip_use {t['grip_use']:.3f}, the hardest plan the passive "
        f"car completes. The reference curve on the passive lap is what the "
        f"controller WOULD have been asked to fix; nothing was controlling it.")


# ---------------------------------------------------------------------------
# 5. what it is worth
# ---------------------------------------------------------------------------

def _short_note(note: str) -> str:
    """Trim a sensitivity label to something that fits beside its number."""
    return (note.replace(" (CLAUDE.md)", "").replace("allocator prefers", "prefers")
            .replace("driver looks", "preview"))


def worth_figure(r) -> str:
    W, H = 1540, 1000
    g = r["gains"]
    s = V.head(
        W, H,
        "What it is worth, and how much of it is the thing you think",
        "Against the best published figure, decomposed into the layer that earned "
        "it, and put through every number the result rests on.")

    # -- panel 1: the four gains against the published ceiling --------------
    bars = [("cornering limit", g["limit_pct"]),
            ("skidpad lateral g", g["skidpad_pct"]),
            ("corner section time", g["section_pct"]),
            ("whole lap time", g["lap_pct"])]
    ax = _Ax(340, 900, 200, 400, 0.0, 10.0, 0, 1)
    s += D.panel_title(70, 178, "Torque vectoring against the passive car",
                       "percent improvement, four ways of asking")
    for i, (lbl, val) in enumerate(bars):
        y = 226 + i * 46
        s += D.text(330, y + 5, lbl, V.FG, 13, "end")
        s += (f'<rect x="{ax.L}" y="{y - 12}" width="{max(float(ax.x(max(val, 0.0)) - ax.L), 2.0):.1f}" '
              f'height="24" rx="4" fill="{V.TEAL if val > 0 else V.COR}" '
              f'opacity="0.85"/>')
        s += D.text(float(ax.x(max(val, 0.0))) + 12, y + 5, f"{val:+.2f}%",
                    V.FG, 13, weight="600", mono=True)
    x9 = float(ax.x(9.0))
    s += (f'<line x1="{x9:.1f}" y1="206" x2="{x9:.1f}" y2="452" '
          f'stroke="{V.AMB}" stroke-width="2" stroke-dasharray="6 5"/>')
    s += D.text(x9, 472, "~9%: best published figure (FSAE, skidpad)",
                V.AMB, 12, "middle", weight="600")
    s += D.text(x9, 490, "an outside ceiling — beating it would be a bug",
                V.MUT, 11.5, "middle")
    for v in (0, 2, 4, 6, 8, 10):
        s += D.text(float(ax.x(v)), 436, f"{v}%", V.MUT, 11, "middle")

    # -- panel 2: which layer earned it -------------------------------------
    s += D.panel_title(70, 486, "Which layer earned it?",
                       "cornering limit, three configurations")
    lo = min(r["limits"][c] for c in ("open", "alloc", "tv4")) - 0.01
    hi = max(r["limits"][c] for c in ("open", "alloc", "tv4")) + 0.01
    ax2 = _Ax(340, 900, 530, 660, lo, hi, 0, 1)
    for i, c in enumerate(("open", "alloc", "tv4")):
        y = 546 + i * 42
        s += D.text(330, y + 5, r["labels"][c], COLOUR[c], 13, "end",
                    weight="600")
        s += (f'<rect x="{ax2.L}" y="{y - 11}" '
              f'width="{max(float(ax2.x(r["limits"][c]) - ax2.L), 3.0):.1f}" '
              f'height="22" rx="4" fill="{COLOUR[c]}" opacity="0.85"/>')
        s += D.text(float(ax2.x(r["limits"][c])) + 12, y + 5,
                    f"{r['limits'][c]:.3f}", V.FG, 13, weight="600", mono=True)
    # The axis does NOT start at zero, and a truncated bar chart that does not say
    # so overstates its differences by whatever factor the reader fails to notice.
    s += (f'<line x1="{ax2.L}" y1="{528}" x2="{ax2.L}" y2="{670}" '
          f'stroke="{V.MUT}" stroke-width="1.2"/>')
    for v in np.arange(math.ceil(lo * 100) / 100, hi, 0.02):
        s += D.text(float(ax2.x(v)), 686, f"{v:.2f}", V.MUT, 10.5, "middle")
    s += D.text(340, 706, f"note the axis starts at {lo:.3f}, not zero — these "
                f"bars are a zoom on a {100*(hi-lo):.1f}-point range",
                V.MUT, 11, style="italic")
    s += _paragraph(340, 736,
                    f"The middle bar is the same allocator with its yaw demand "
                    f"forced to zero: four wheels sharing brake and drive force in "
                    f"proportion to what each has left, and no yaw control at all. "
                    f"It accounts for {100*g['allocator_share']:.0f}% of the "
                    f"improvement. Most of what this system buys on this lap is "
                    f"not torque vectoring.", 74)

    # -- panel 3: sensitivities ---------------------------------------------
    s += D.panel_title(980, 306, "Does the conclusion survive?",
                       "cornering-limit gain under every number it rests on")
    y = 354
    s += D.text(980, y, f"nominal   {g['limit_pct']:+6.2f}%", V.TEAL, 13.5,
                weight="600", mono=True)
    y += 30
    for key, row in r["sensitivity"].items():
        s += D.text(980, y, f"{row['gain_pct']:+6.2f}%",
                    V.TEAL if row["gain_pct"] > 0 else V.COR, 13, mono=True,
                    weight="600")
        s += D.text(1064, y, _short_note(row["note"]), V.MUT, 12)
        y += 24
    y += 8
    s += _paragraph(980, y, "The driver's preview time is the one that "
                    "matters: the same controller is worth nothing "
                    "measurable to a driver who looks close, and "
                    "11.6% to one who looks far.", 46,
                    size=11.5, dy=18)
    y += 96
    s += D.text(980, y, f"steering disturbance, {r['noise']['open']['n']} seeds",
                V.FG, 13.5, weight="600")
    s += D.text(980, y + 18, "valid laps = finished, on the road, inside the fit",
                V.MUT, 11)
    y += 18
    y += 26
    for c in r["conditions"]:
        n = r["noise"][c]
        s += D.text(980, y, f"{n['valid']:3d}/{n['n']}", COLOUR[c], 12.5,
                    mono=True, weight="600")
        s += D.text(1050, y, f"{r['short'][c]}", COLOUR[c], 12.5)
        lap_s = ("—" if not np.isfinite(n["mean_lap"])
                 else f"{n['mean_lap']:.2f} +/- "
                      f"{0.0 if not np.isfinite(n['sd_lap']) else n['sd_lap']:.2f} s")
        s += D.text(1380, y, lap_s, V.MUT, 12.5, "end", mono=True)
        y += 24

    s += D.rule(70, 810, W - 140, V.GRID)
    for i, line in enumerate(_wrap(
            f"The honest summary: the controller does what it says on the tin — it "
            f"tracks the reference yaw rate, the allocator delivers the moment "
            f"asked for, and the car survives {g['limit_pct']:+.1f}% more cornering "
            f"demand. But the lap-time number is {g['lap_pct']:+.2f}%, an order of "
            f"magnitude below the published skidpad figure, and most of what is "
            f"left is the allocator rather than the yaw control. On this car, on "
            f"this corner, with a driver who does not make mistakes, torque "
            f"vectoring is a small effect measured carefully. To a driver who DOES "
            f"make mistakes it is worth much more: under steering noise the passive "
            f"car loses {r['noise']['open']['n'] - r['noise']['open']['valid']} laps "
            f"of {r['noise']['open']['n']} and the controlled one loses none.",
            148)):
        s += D.text(70, 844 + 22 * i, line, V.MUT, 13)

    s += _stamp(H - 40, r)
    return s + V.foot(
        W, H,
        "Every percentage is against the open-differential car driven by the same "
        "driver on the same line. The 9% line is the most favourable published "
        "case, not a target.")
