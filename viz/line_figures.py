"""Episode 4 figures — the racing line, drawn as a track seen from above.

``line_figure``
    The corner, the two solved lines overlaid, the apexes marked. The Ep 4 hero,
    and it needs no axes at all: it is a picture of a road.
``line_card``
    The technical panels — speed, lateral offset, and what the tires were doing
    along each line.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V
from physics.track import CORNER_ARC as T_ARC, ENTRY_STRAIGHT as T_ENTRY


def _stamp(y: float, sol, extra: str = "") -> str:
    m = sol.meta
    v, t = m["vehicle"], m["tire"]
    bits = [
        f"[MEASURED] bicycle model + optimal control + {t['file']}",
        "offsets removed" if t["offsets_removed"] else "as shipped",
        f"m {v['mass']:.0f} kg · {v['front_mass_fraction']:.0%} front",
        f"{m['n_nodes']} nodes, {m['ds']:.2f} m apart",
        "[SOURCED] RV-1 parameters §1",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  ·  ".join(bits), V.MUT, 9.5)


def _fit(xs, ys, L, R, T, B):
    """Uniform scale mapping so the track is not distorted."""
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    sc = min((R - L) / max(x1 - x0, 1e-9), (B - T) / max(y1 - y0, 1e-9))
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)

    def to_px(x, y):
        return (0.5 * (L + R) + (np.asarray(x) - cx) * sc,
                0.5 * (T + B) - (np.asarray(y) - cy) * sc)

    return to_px, sc


def track_backdrop(track, s0, s1, L, R, T, B, n=1600):
    """Draw a stretch of road seen from above, and return how to plot on it.

    Returns ``(svg, to_px, scale)`` where ``to_px(x, y)`` maps track metres to
    pixels and ``scale`` is pixels per metre. Both the Episode 4 line figure and
    the Episode 6 along-the-path figure draw on the same road; sharing this means
    a car plotted by one cannot land off the tarmac drawn by the other.
    """
    _, x_c, y_c, head = track.centreline(n)
    s_axis = np.linspace(0.0, track.length, n)
    win = (s_axis >= s0) & (s_axis <= s1)
    hw = track.half_width
    xl, yl = x_c - hw * np.sin(head), y_c + hw * np.cos(head)
    xr, yr = x_c + hw * np.sin(head), y_c - hw * np.cos(head)
    to_px, scale = _fit(np.concatenate([xl[win], xr[win]]),
                        np.concatenate([yl[win], yr[win]]), L, R, T, B)

    px_l, py_l = to_px(xl[win], yl[win])
    px_r, py_r = to_px(xr[win], yr[win])
    poly = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px_l, py_l))
    poly += " " + " ".join(f"{a:.1f},{b:.1f}"
                           for a, b in zip(px_r[::-1], py_r[::-1]))
    s = f'<polygon points="{poly}" fill="#26262a"/>'
    for xs_, ys_ in ((xl[win], yl[win]), (xr[win], yr[win])):
        a, b = to_px(xs_, ys_)
        s += (f'<path d="{V.path(list(zip(a, b)))}" fill="none" '
              f'stroke="{V.MUT}" stroke-width="1.6"/>')
    a, b = to_px(x_c[win], y_c[win])
    s += (f'<path d="{V.path(list(zip(a, b)))}" fill="none" stroke="{V.GRID}" '
          f'stroke-width="1" stroke-dasharray="9 9"/>')
    return s, to_px, scale


def path_heading(track, s, xi, n=2000):
    """Heading of the car's body in track x-y, radians.

    The centreline tangent plus the path-deviation angle. Drawing a car along a
    curve without this gives every instance the same orientation, which reads as
    a bug even when the positions are right.
    """
    s_ref = np.linspace(0.0, track.length, n)
    _, _, _, hd = track.centreline(n)
    return np.interp(s, s_ref, hd) + xi


def line_figure(solutions, labels, colours=None) -> str:
    """The corner with each solved line drawn on it."""
    colours = colours or (V.TEAL, V.COR)
    W, H = 1480, 1030
    ref = solutions[0]
    s = V.head(
        W, H,
        "The fastest way round a corner is not the obvious one",
        "The same 90° corner, driven twice. Identical car, identical entry "
        "speed, identical tires. The only thing that changes is how much "
        "straight road comes after it — and the fast line through the corner "
        "changes with it.",
    )

    # Crop to the corner. Drawn to the full length of the long-exit track, the
    # 260 m straight sets the scale and the corner -- the entire subject --
    # becomes a squiggle in one corner of the frame.
    ref_track = solutions[0].track
    s0 = max(T_ENTRY - 35.0, 0.0)
    # Clip to the SHORTEST track. Drawing tarmac from one track while letting a
    # line run to another's length puts the red line off the road.
    s1 = min(T_ENTRY + T_ARC + 45.0, min(q.track.length for q in solutions))
    _, x_c, y_c, head = ref_track.centreline(1600)
    s_axis = np.linspace(0.0, ref_track.length, 1600)
    win = (s_axis >= s0) & (s_axis <= s1)
    hw = ref_track.half_width
    xl, yl = x_c - hw * np.sin(head), y_c + hw * np.cos(head)
    xr, yr = x_c + hw * np.sin(head), y_c - hw * np.cos(head)
    to_px, scale = _fit(np.concatenate([xl[win], xr[win]]),
                        np.concatenate([yl[win], yr[win]]),
                        90, 880, 170, 800)

    # tarmac
    px_l, py_l = to_px(xl[win], yl[win])
    px_r, py_r = to_px(xr[win], yr[win])
    poly = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px_l, py_l))
    poly += " " + " ".join(f"{a:.1f},{b:.1f}"
                           for a, b in zip(px_r[::-1], py_r[::-1]))
    s += f'<polygon points="{poly}" fill="#26262a"/>'
    for xs_, ys_ in ((xl[win], yl[win]), (xr[win], yr[win])):
        a, b = to_px(xs_, ys_)
        s += (f'<path d="{V.path(list(zip(a, b)))}" fill="none" '
              f'stroke="{V.MUT}" stroke-width="1.6"/>')
    a, b = to_px(x_c[win], y_c[win])
    s += (f'<path d="{V.path(list(zip(a, b)))}" fill="none" stroke="{V.GRID}" '
          f'stroke-width="1" stroke-dasharray="9 9"/>')
    s += D.text(float(a[0]) + 8, float(b[0]) - 26, "centreline", V.MUT, 10.5)

    # which way the car goes
    ax0, ay0 = to_px(x_c[win][0], y_c[win][0])
    ax1, ay1 = to_px(x_c[win][8], y_c[win][8])
    s += D.arrow(float(ax0), float(ay0) + 40, float(ax1) + 60, float(ay1) + 40,
                 V.MUT, 2.0, 10)
    s += D.text(float(ax0) + 72, float(ay0) + 44, "direction of travel", V.MUT, 10.5)

    # the lines
    for sol, label, colour in zip(solutions, labels, colours):
        m = (sol.s >= s0) & (sol.s <= s1)
        x, y = sol.track.to_xy(sol.s[m], sol.states["n"][m])
        px, py = to_px(x, y)
        s += (f'<path d="{V.path(list(zip(px, py)))}" fill="none" '
              f'stroke="{colour}" stroke-width="3.4"/>')

    # apexes, and a car on each line so the reader sees a vehicle not a curve
    for j, (sol, colour) in enumerate(zip(solutions, colours)):
        i = sol.apex_index
        ax, ay = sol.track.to_xy(np.array([sol.s[i]]),
                                 np.array([sol.states["n"][i]]))
        apx, apy = to_px(ax, ay)
        heading = float(path_heading(sol.track, sol.s[i], sol.states["xi"][i]))
        s += D.car_plan(float(apx[0]), float(apy[0]), length=74, width=34,
                        wheel_len=18, wheel_w=8,
                        steer_deg=D.screen_deg(math.degrees(sol.states["delta"][i])),
                        heading_deg=D.screen_heading_deg(math.degrees(heading)),
                        loads=(0.55,) * 4, body=colour)
        s += (f'<circle cx="{apx[0]:.1f}" cy="{apy[0]:.1f}" r="10" fill="none" '
              f'stroke="{colour}" stroke-width="2.5"/>')
        s += D.text(apx[0] + (26 if j == 0 else -26), apy[0] + 42 * (1 if j == 0 else -1),
                    "apex", colour, 13, "start" if j == 0 else "end", weight="600")

    # legend and numbers
    ly = 200
    for sol, label, colour in zip(solutions, labels, colours):
        s += (f'<line x1="960" y1="{ly-5}" x2="1000" y2="{ly-5}" '
              f'stroke="{colour}" stroke-width="3"/>')
        s += D.text(1012, ly, label, V.FG, 14, weight="600")
        s += D.text(1012, ly + 22,
                    f"apex {100*sol.apex_fraction_through_corner:.0f}% through "
                    f"the corner", colour, 12.5)
        s += D.text(1012, ly + 42,
                    f"slowest {sol.speed.min():.1f} m/s "
                    f"({3.6*sol.speed.min():.0f} km/h)", V.MUT, 12)
        s += D.text(1012, ly + 60,
                    f"exit {sol.speed[-1]:.1f} m/s ({3.6*sol.speed[-1]:.0f} km/h)",
                    V.MUT, 12)
        ly += 110

    shift = 100 * (solutions[1].apex_fraction_through_corner
                   - solutions[0].apex_fraction_through_corner)
    s += D.rule(960, ly - 20, 1420, V.GRID)
    for i, line in enumerate([
        "Nobody told the optimiser what a",
        "racing line is. It was given the tires,",
        "the width of the road, and a stopwatch.",
        "",
        f"With a long straight ahead, the apex",
        f"moves {shift:.0f} percentage points later —",
        "sacrificing corner speed to get the car",
        "pointed straight sooner, so it can start",
        "accelerating earlier.",
    ]):
        s += D.text(960, ly + 12 + 21 * i, line, V.MUT, 12.5)

    s += D.text(90, 880,
                f"Cropped to the corner: {s0:.0f} m to {s1:.0f} m along the track. "
                f"Corner radius {1/abs(ref_track.curvature(T_ENTRY + 0.5*T_ARC)):.0f} m, "
                f"road {2*hw:.0f} m wide, entry speed "
                f"{ref.meta['entry_speed']:.0f} m/s in both cases. Scale "
                f"{10.0*scale:.0f} px per 10 m.", V.MUT, 11)
    s += _stamp(H - 40, ref,
                "corner geometry [ASSUMED] — a made-up corner chosen to be readable")
    return s + V.foot(
        W, H,
        "Minimum-time solve, distance-domain collocation. Slip angles are "
        "constrained to ±12° so the answer stays inside the region where the "
        "tire model was fitted.",
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


def line_card(solutions, labels, colours=None) -> str:
    colours = colours or (V.TEAL, V.COR)
    W, H = 1520, 640
    ref = solutions[0]
    s = V.head(
        W, H,
        "Episode 4 — minimum-time solve",
        "Two solves of the same corner, differing only in the length of the "
        "straight that follows. Distance along the track runs left to right in "
        "every panel; the shaded band is the corner.",
    )
    s_max = max(q.track.length for q in solutions)
    k = ref.track.curvature(np.linspace(0, ref.track.length, 400))
    corner = np.linspace(0, ref.track.length, 400)[np.abs(k) > 0.5 * np.abs(k).max()]
    c0, c1 = corner.min(), corner.max()

    panels = [
        ("A · Speed", "speed (m/s)", lambda q: q.speed, (10, 45), 100, 480),
        ("B · Where on the road", "offset from centreline (m)",
         lambda q: q.states["n"], (-4.5, 4.5), 620, 1000),
        ("C · Braking and driving", "longitudinal force (kN)",
         lambda q: q.controls["drive_force"] / 1000.0, (-16, 6), 1140, 1420),
    ]
    for title, ylab, get, (lo, hi), L, R in panels:
        ax = _Ax(L, R, 140, 460, 0, s_max, lo, hi)
        s += D.panel_title(L, 122, title)
        s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 4, 4)
        xt, yt = _ticks(ax, [0, 100, 200, 300],
                        np.linspace(lo, hi, 4), fx="{:.0f}", fy="{:.1f}")
        s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "distance along the track (m)",
                   ylab, xt, yt)
        s += (f'<rect x="{ax.x(c0):.1f}" y="{ax.T}" '
              f'width="{ax.x(c1)-ax.x(c0):.1f}" height="{ax.B-ax.T}" '
              f'fill="{V.AMB}" opacity="0.09"/>')
        s += D.text(float(ax.x(0.5 * (c0 + c1))), ax.T + 16, "corner", V.AMB, 10,
                    "middle")
        if lo < 0 < hi:
            s += (f'<line x1="{ax.L}" y1="{ax.y(0):.1f}" x2="{ax.R}" '
                  f'y2="{ax.y(0):.1f}" stroke="{V.MUT}" stroke-width="1" '
                  f'stroke-dasharray="3 5"/>')
        for sol, colour in zip(solutions, colours):
            s += (f'<path d="{V.path(ax.pts(sol.s, get(sol)))}" fill="none" '
                  f'stroke="{colour}" stroke-width="2.2"/>')
            i = sol.apex_index
            s += (f'<circle cx="{float(ax.x(sol.s[i])):.1f}" '
                  f'cy="{float(ax.y(get(sol)[i])):.1f}" r="4" fill="{colour}"/>')

    ly = 508
    for sol, label, colour in zip(solutions, labels, colours):
        s += D.text(100, ly, f"{label}:", colour, 12.5, weight="600")
        s += D.text(230, ly,
                    f"{sol.time:.2f} s over {sol.track.length:.0f} m  ·  apex "
                    f"{100*sol.apex_fraction_through_corner:.0f}% through the "
                    f"corner  ·  slowest {sol.speed.min():.1f} m/s  ·  exit "
                    f"{sol.speed[-1]:.1f} m/s  ·  worst slip "
                    f"{math.degrees(max(abs(sol.alpha_f).max(), abs(sol.alpha_r).max())):.1f}°"
                    f"  ·  envelope violations {100*sol.envelope_occupancy():.1f}%"
                    f"  ·  {sol.solver_status}", V.MUT, 11.5)
        ly += 22
    s += D.text(100, ly + 12,
                "Absolute times are not comparable between the two — they cover "
                "different distances. The comparable quantity is where the apex "
                "sits, and the shape of the speed trace through the corner.",
                V.MUT, 11.5)
    s += _stamp(H - 40, ref)
    return s + V.foot(
        W, H,
        "Slip angles constrained to ±12°, our imposed bound; the solver sits on "
        "that constraint through the corner, which is what a minimum-time answer "
        "should do.",
    )


__all__ = ["line_figure", "line_card"]
