"""Pictorial SVG primitives — actual wheels, arrows, angles.

The house style for this project is that **a reader who has never heard of a slip
angle should be able to look at the figure and see what is happening.** Line
charts are the second figure in a piece, never the first. This module draws the
first one: tires seen from above, the direction they are travelling, the angle
between the two, and force arrows whose length means something.

Geometry convention used throughout, chosen for legibility rather than to match
:mod:`physics.schema`'s ISO frame:

* **Up the page is the direction of travel.** Every figure keeps this fixed.
* A tire rotated **clockwise** on screen is pointed to the *right* of where it is
  going, and therefore pushes the car to the right — which is what happens when
  you steer right.
* Force arrow **length is proportional to force**, always, with the scale stated
  in the figure.

All coordinates are SVG pixels, y down.
"""

from __future__ import annotations

import math

from .lib import AMB, COR, FG, GRID, GRN, MUT, SLATE, TEAL, VIO, path  # noqa: F401


# ---------------------------------------------------------------------------
# ISO 8855 -> screen
# ---------------------------------------------------------------------------
# These two functions exist because the mismatch they fix is silent and it has
# already bitten once.
#
# ``physics.schema`` uses ISO 8855: **y points left**, and a **positive steer
# angle turns the wheels left**. SVG's y points **down**, so a positive
# ``rotate()`` is **clockwise**, which on a nose-up car points the wheels
# **right**. The two conventions are exactly opposite.
#
# Passing a physics angle straight into a drawing call therefore renders a
# perfectly plausible, perfectly wrong picture of a car turning the other way —
# no exception, no warning, and it looks fine unless you check it against the
# force arrows. Every figure that draws a steered wheel or a lateral force goes
# through these.


def screen_deg(iso_deg: float) -> float:
    """ISO angle (positive = left) -> SVG rotation (positive = clockwise/right)."""
    return -iso_deg


def screen_dx(iso_y: float) -> float:
    """ISO lateral quantity (positive = left) -> screen x offset (positive = right)."""
    return -iso_y


def screen_heading_deg(track_heading_deg: float) -> float:
    """Track heading -> the ``car_plan`` rotation that points the nose along it.

    A third convention, and the one that bit hardest. The other two convert a
    single angle; this one composes two frames, which is why ``screen_deg`` was
    not enough on its own.

    A plan-view figure maps track ``+x`` to screen right and track ``+y`` (left
    of travel) to screen **up**. ``car_plan`` with rotation 0 draws the nose at
    local ``-y``, i.e. screen up. SVG ``rotate(a)`` sends ``(0, -1)`` to
    ``(sin a, -cos a)``, and a car on heading ``θ`` travels screen
    ``(cos θ, -sin θ)``. Equating them gives ``a = 90° - θ``.

    The earlier ``screen_deg(θ) - 90`` gives ``-θ - 90``, which is out by 180°
    for every heading: nose down the page while the car travels up it. It
    survived review because a car body outline is very nearly symmetric — the
    only tell is the small nose mark, and the force arrows, which is how it was
    finally caught. See FINDINGS F36.
    """
    return 90.0 - track_heading_deg


def arrow(x1, y1, x2, y2, colour=FG, width=2.6, head=10.0, dash=None, opacity=1.0):
    """A line with a solid triangular head at ``(x2, y2)``."""
    ang = math.atan2(y2 - y1, x2 - x1)
    # stop the shaft short so it does not poke through the head
    bx, by = x2 - head * 0.85 * math.cos(ang), y2 - head * 0.85 * math.sin(ang)
    p = [
        (x2, y2),
        (x2 - head * math.cos(ang) + head * 0.42 * math.sin(ang),
         y2 - head * math.sin(ang) - head * 0.42 * math.cos(ang)),
        (x2 - head * math.cos(ang) - head * 0.42 * math.sin(ang),
         y2 - head * math.sin(ang) + head * 0.42 * math.cos(ang)),
    ]
    d = f' stroke-dasharray="{dash}"' if dash else ""
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in p)
    return (
        f'<g opacity="{opacity}">'
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
        f'stroke="{colour}" stroke-width="{width}"{d} stroke-linecap="round"/>'
        f'<polygon points="{pts}" fill="{colour}"/></g>'
    )


def tire(cx, cy, angle_deg=0.0, length=76.0, width=30.0, load_frac=1.0,
         colour="#3a3a3f", edge=MUT, patch=None, heading=0.0):
    """A tire seen from above, pointed ``angle_deg`` clockwise from straight up.

    ``load_frac`` (0-1) scales the **contact patch**, drawn as the lighter band
    across the middle. That is not decoration: a more heavily loaded tire really
    does squash into a longer, wider contact patch, and making the reader see one
    tire flattened harder than its neighbour is the entire point of the
    load-split figure.

    ``heading``, if non-zero, extends a thin centreline that far beyond the tire
    in both directions. Real slip angles are small — 5 degrees is barely
    perceptible on a 76-pixel rectangle — so the long baseline is what makes the
    angle legible without exaggerating it.
    """
    half_l, half_w = length / 2, width / 2
    lf = max(0.0, min(1.0, load_frac))
    patch_len = half_l * (0.22 + 0.62 * lf)
    patch_w = (width - 4) * (0.55 + 0.40 * lf)
    g = f'<g transform="rotate({angle_deg:.2f} {cx:.1f} {cy:.1f})">'
    if heading:
        g += (f'<line x1="{cx:.1f}" y1="{cy-heading:.1f}" x2="{cx:.1f}" '
              f'y2="{cy+heading:.1f}" stroke="{edge}" stroke-width="1.1" '
              f'opacity="0.75"/>')
    g += (f'<rect x="{cx-half_w:.1f}" y="{cy-half_l:.1f}" width="{width}" '
          f'height="{length}" rx="{half_w*0.55:.1f}" fill="{colour}" '
          f'stroke="{edge}" stroke-width="1.2"/>')
    if patch:
        g += (f'<rect x="{cx-patch_w/2:.1f}" y="{cy-patch_len:.1f}" '
              f'width="{patch_w:.1f}" height="{2*patch_len:.1f}" '
              f'rx="{patch_w*0.42:.1f}" fill="{patch}" opacity="0.9"/>')
    for k in (-0.55, 0.0, 0.55):  # tread grooves
        gx = cx + k * (half_w - 4)
        g += (f'<line x1="{gx:.1f}" y1="{cy-half_l+5:.1f}" x2="{gx:.1f}" '
              f'y2="{cy+half_l-5:.1f}" stroke="{edge}" stroke-width="0.8" '
              f'opacity="0.5"/>')
    return g + "</g>"


def car_plan(cx, cy, length=180.0, width=80.0, steer_deg=0.0, heading_deg=0.0,
             wheel_len=38.0, wheel_w=15.0, loads=(0.6, 0.6, 0.6, 0.6),
             body=MUT, patch=SLATE, heading=0.0, patches=None):
    """A car seen from above: body outline plus four wheels.

    ``heading_deg`` rotates the whole car (its **heading** — where the nose
    points). ``steer_deg`` additionally rotates the two front wheels. Keeping
    those separate is the entire subject of the understeer figure: the direction
    a car points, the direction it travels, and the direction its wheels point
    are three different things.

    ``loads`` is front-left, front-right, rear-left, rear-right as fractions,
    driving each wheel's contact-patch size.

    ``patches``, if given, is four colours in the same order, overriding
    ``patch`` per wheel. Used to colour each contact patch by how much of that
    tire is being used, so a car drawn along its path carries its own result.
    """
    hl, hw = length / 2, width / 2
    ax_f, ax_r = -length * 0.30, length * 0.30
    g = f'<g transform="rotate({heading_deg:.3f} {cx:.1f} {cy:.1f})">'
    g += (f'<rect x="{cx-hw:.1f}" y="{cy-hl:.1f}" width="{width}" height="{length}" '
          f'rx="{hw*0.5:.1f}" fill="none" stroke="{body}" stroke-width="1.8"/>')
    # a nose mark, so which way it points is never ambiguous
    g += (f'<path d="M {cx-9:.1f},{cy-hl+16:.1f} L {cx:.1f},{cy-hl+4:.1f} '
          f'L {cx+9:.1f},{cy-hl+16:.1f}" fill="none" stroke="{body}" '
          f'stroke-width="1.6"/>')
    pc = tuple(patches) if patches is not None else (patch,) * 4
    for (dx, dy), lf, steered, pcol in (
        ((-1, ax_f), loads[0], True, pc[0]), ((1, ax_f), loads[1], True, pc[1]),
        ((-1, ax_r), loads[2], False, pc[2]), ((1, ax_r), loads[3], False, pc[3]),
    ):
        wx = cx + dx * (hw + wheel_w * 0.35)
        wy = cy + dy
        g += tire(wx, wy, steer_deg if steered else 0.0, length=wheel_len,
                  width=wheel_w, load_frac=lf, patch=pcol,
                  heading=heading if steered else 0.0)
    return g + "</g>"


def car_rear_view(cx, cy, track, defl=(0.0, 0.0), body_w=150.0, body_h=78.0,
                  wheel_w=26.0, wheel_h=54.0, loads=(0.5, 0.5),
                  body=MUT, patch=SLATE, ride=46.0):
    """The car seen from behind, leaning.

    Every other figure in this project is a plan view, which is right for slip
    angles and racing lines and wrong for load transfer: a plan view can show
    that the outside tire carries more, but not *why*. This can.

    ``defl`` is how far each spring is compressed, in pixels, as
    ``(left, right)``. **The body angle is computed from those two deflections
    rather than passed in.** That is deliberate: given a roll angle and separate
    spring lengths, the two can disagree, and an earlier version of this figure
    leaned the body away from the compressed spring — a picture of a car doing
    something impossible, rendered without complaint. Deriving the angle from the
    springs makes that unrepresentable.

    The caller computes deflection from load, so a more heavily loaded corner is
    necessarily the compressed one.
    """
    half_t = track / 2.0
    dl, dr = defl
    g = ""
    g += (f'<line x1="{cx - half_t - wheel_w:.1f}" y1="{cy:.1f}" '
          f'x2="{cx + half_t + wheel_w:.1f}" y2="{cy:.1f}" stroke="{MUT}" '
          f'stroke-width="1.6"/>')
    for side, lf in zip((-1, 1), loads):
        wx = cx + side * half_t
        g += (f'<rect x="{wx - wheel_w/2:.1f}" y="{cy - wheel_h:.1f}" '
              f'width="{wheel_w:.1f}" height="{wheel_h:.1f}" '
              f'rx="{wheel_w*0.28:.1f}" fill="#3a3a3f" stroke="{MUT}" '
              f'stroke-width="1.2"/>')
        pw = wheel_w * (0.30 + 0.62 * max(0.0, min(1.0, lf)))
        g += (f'<rect x="{wx - pw/2:.1f}" y="{cy - 5:.1f}" width="{pw:.1f}" '
              f'height="5" rx="2" fill="{patch}" opacity="0.95"/>')
    # spring tops: compressed side sits lower (larger y)
    top_l = cy - wheel_h - ride + dl
    top_r = cy - wheel_h - ride + dr
    for wx, top in ((cx - half_t, top_l), (cx + half_t, top_r)):
        n = 6
        pts = [(wx, cy - wheel_h)]
        for j in range(1, n + 1):
            fy = (cy - wheel_h) + (top - (cy - wheel_h)) * j / n
            pts.append((wx + (8 if j % 2 else -8), fy))
        pts.append((wx, top))
        g += (f'<path d="{path(pts)}" fill="none" stroke="{MUT}" '
              f'stroke-width="1.5" opacity="0.85"/>')
    # body angle falls out of the two spring lengths
    roll_deg = math.degrees(math.atan2(top_r - top_l, track))
    by = 0.5 * (top_l + top_r) - body_h / 2
    g += (f'<g transform="rotate({roll_deg:.2f} {cx:.1f} {by:.1f})">'
          f'<rect x="{cx - body_w/2:.1f}" y="{by - body_h/2:.1f}" '
          f'width="{body_w:.1f}" height="{body_h:.1f}" rx="14" fill="none" '
          f'stroke="{body}" stroke-width="2"/>'
          f'<circle cx="{cx:.1f}" cy="{by:.1f}" r="4" fill="{body}"/></g>')
    return g


def friction_circle(cx, cy, r, fx_frac, fy_frac, colour=COR, ring=MUT,
                    label=None, size=9.5):
    """A tire's friction circle with the force it is actually making inside it.

    ``fx_frac`` and ``fy_frac`` are the longitudinal and lateral forces as
    fractions of what this tire could produce at its current load. The ring is
    everything the tire has; the arrow is what is being spent. When the arrow
    touches the ring the tire has nothing left, and *which* direction it is
    pointing says what it ran out doing.

    This is the figure that makes "asked to do two things at once" visible: a
    front tire on a front-wheel-drive car exiting a corner has an arrow pointing
    diagonally, and diagonal arrows reach the ring sooner than straight ones.
    """
    used = min(math.hypot(fx_frac, fy_frac), 1.0)
    g = (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" '
         f'stroke="{ring}" stroke-width="1.2" opacity="0.75"/>')
    g += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{colour}" '
          f'opacity="{0.06 + 0.30 * used:.3f}"/>')
    # screen: +x right, +y down. ISO +y is left, so lateral flips; forward is up.
    tx = cx - fy_frac * r
    ty = cy - fx_frac * r
    if used > 0.02:
        g += arrow(cx, cy, tx, ty, colour, 2.2, 7.0)
    if label:
        g += text(cx, cy + r + 14, label, MUT, size, "middle")
    return g


def angle_arc(cx, cy, r, angle_deg, colour=TEAL, width=1.6):
    """Arc from straight-up to ``angle_deg`` clockwise, centred on ``(cx, cy)``."""
    a = math.radians(angle_deg)
    x0, y0 = cx, cy - r
    x1, y1 = cx + r * math.sin(a), cy - r * math.cos(a)
    sweep = 1 if angle_deg > 0 else 0
    return (f'<path d="M {x0:.1f},{y0:.1f} A {r:.1f},{r:.1f} 0 0 {sweep} '
            f'{x1:.1f},{y1:.1f}" fill="none" stroke="{colour}" '
            f'stroke-width="{width}"/>')


def esc(s) -> str:
    """XML-escape text destined for an SVG ``<text>`` element.

    A bare ``<`` in a caption — "fitted over |a_y| <= 0.5 g" — produces a file
    that renders as an XML parse error instead of a figure, and nothing in the
    pipeline complains: the SVG is written, the diagnostic passes, and the
    breakage only appears when someone opens it. ``tests/test_figures.py`` parses
    every generated figure for exactly this reason.
    """
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, s, fill=FG, size=12, anchor="start", weight="normal",
         style="normal", mono=False):
    fam = (' font-family="ui-monospace, SFMono-Regular, Menlo, monospace"'
           if mono else "")
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}" '
            f'font-style="{style}"{fam}>{esc(s)}</text>')


def panel_title(x, y, s, sub=None):
    out = text(x, y, s, FG, 15, weight="600")
    if sub:
        out += text(x, y + 19, sub, MUT, 11.5)
    return out


def rule(x1, y, x2, colour=GRID, width=1.0):
    return (f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
            f'stroke="{colour}" stroke-width="{width}"/>')


def band(x, y, w, h, lo_frac, hi_frac, colour, opacity=0.28, radius=3):
    """A shaded horizontal band inside a track — used for "expected range"."""
    bx = x + w * lo_frac
    bw = max(w * (hi_frac - lo_frac), 2.0)
    return (f'<rect x="{bx:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h}" '
            f'rx="{radius}" fill="{colour}" opacity="{opacity}"/>')


__all__ = ["arrow", "tire", "car_plan", "car_rear_view",
           "friction_circle", "angle_arc",
           "text", "panel_title",
           "rule", "band", "esc", "screen_deg", "screen_dx",
           "screen_heading_deg"]
