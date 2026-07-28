"""Review figures — every path, drawn in full, for inspection rather than for print.

These exist to be *looked at*. Season 3 produced several results that were correct
in a table and wrong on the road, and several more that were wrong in a table and
only caught by rendering the picture. This module draws one panel per rollout with
everything encoded at once:

* the **line** the car took, coloured by speed
* the **car** at intervals, drawn at the heading it is actually pointing
* an **arrow** at each car showing the direction it is actually travelling
* the car's colour is **slip angle** — the gap between pointing and going

On a car that is driving, body and arrow agree and the colour stays cool. Every
failure mode in Season 3 shows up as a visible disagreement between those two
marks, which is not true of any number in any table.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V
from physics.track import CORNER_ARC as T_ARC, ENTRY_STRAIGHT as T_ENTRY

#: Slip angle at which the colour ramp saturates. Our fit ends at 12°, so the
#: ramp is scaled to make an excursion past the bound unmistakable rather than
#: subtle.
SLIP_FULL_SCALE = 36.0


def _slip_colour(deg: float) -> str:
    r, g, b = V.ramp(min(float(deg) / SLIP_FULL_SCALE, 1.0))
    return f"#{r:02x}{g:02x}{b:02x}"


def _speed_colour(u: float) -> str:
    r, g, b = V.ramp(float(np.clip(u, 0.0, 1.0)))
    return f"#{r:02x}{g:02x}{b:02x}"


def path_review(cases, title: str, subtitle: str, stamp: str,
                cols: int = 3, panel: tuple[int, int] = (430, 470)) -> str:
    """One top-down panel per rollout, laid out in a grid.

    ``cases``: list of dicts with ``label``, ``sub``, ``trace`` (a rollout dict
    carrying s / n / xi / speed / alpha_max_deg), and ``ok`` (bool, drives the
    panel's accent colour).
    """
    from .line_figures import track_backdrop, path_heading
    from physics.track import long_exit

    track = long_exit()
    pw, ph = panel
    rows = (len(cases) + cols - 1) // cols
    W = 120 + cols * pw
    H = 250 + rows * ph + 230
    s = V.head(W, H, title, subtitle)
    s += D.text(40, 92,
                "Body = where the car points.  Arrow = where it is going.  "
                "Colour = how far apart those are (slip angle).  Line colour = "
                "speed.", V.MUT, 11.5)

    # a shared speed scale so panels are comparable
    v_all = np.concatenate([c["trace"]["speed"] for c in cases])
    v_lo, v_hi = float(v_all.min()), float(v_all.max())

    for ci, case in enumerate(cases):
        col, row = ci % cols, ci // cols
        L = 70 + col * pw
        R = L + pw - 70
        T = 200 + row * ph
        B = T + ph - 150
        tr = case["trace"]
        sa, n, xi = tr["s"], tr["n"], tr["xi"]
        slip, spd = tr["alpha_max_deg"], tr["speed"]

        # Crop TIGHT on the corner. The exit straight is 260 m of the 393 m
        # total and almost nothing happens on it — the car is pointed straight
        # and accelerating. What is worth looking at is turn-in, the arc, and the
        # first few car-lengths after the exit where any correction happens.
        #
        # Two earlier crops were both wrong in the same direction: the full track
        # (two thirds empty tarmac, corner reduced to a squiggle) and then
        # corner-plus-70 m, which still gave a third of the frame to straight.
        # 25 m before turn-in to 30 m past the exit is about 118 m, of which 63
        # is the arc itself.
        # The window is FIXED on the corner. Extending it to the end of the
        # trajectory — which an earlier version did via max() — silently gave
        # every successful run the full 393 m while framing only the failures
        # tightly, so the panels that worked were the ones you could not read.
        # A run is only allowed to widen the frame if it died beyond it.
        s_lo = max(T_ENTRY - 25.0, 0.0)
        s_hi = T_ENTRY + T_ARC + 30.0
        _fin = float(sa[-1]) >= track.length - 1.0
        if not _fin and float(sa[-1]) + 12.0 > s_hi:
            s_hi = min(float(sa[-1]) + 12.0, track.length)
        back, to_px, scale = track_backdrop(track, s_lo, s_hi, L, R, T, B)
        win = (sa >= s_lo) & (sa <= s_hi)
        accent = V.TEAL if case["ok"] else V.COR
        s += D.panel_title(L, T - 32, case["label"], case["sub"])
        s += back

        x, y = track.to_xy(sa, n)
        px, py = to_px(x, y)
        # the line, coloured by speed, segment by segment
        for k in range(len(sa) - 1):
            if not (win[k] and win[k + 1]):
                continue
            u = (0.5 * (spd[k] + spd[k + 1]) - v_lo) / max(v_hi - v_lo, 1e-9)
            s += (f'<line x1="{px[k]:.1f}" y1="{py[k]:.1f}" '
                  f'x2="{px[k+1]:.1f}" y2="{py[k+1]:.1f}" '
                  f'stroke="{_speed_colour(u)}" stroke-width="2.4" '
                  f'stroke-linecap="round"/>')

        head = path_heading(track, sa, xi)
        idx = np.where(win)[0]
        marks = list(idx[:: max(len(idx) // 13, 1)]) if len(idx) else []
        if len(idx) and marks[-1] != idx[-1]:
            marks.append(int(idx[-1]))
        for k in marks:
            hd = D.screen_heading_deg(math.degrees(float(head[k])))
            col_k = _slip_colour(slip[k])
            s += D.car_plan(float(px[k]), float(py[k]), length=40, width=20,
                            wheel_len=12, wheel_w=6, heading_deg=hd,
                            loads=(0.5,) * 4, body=col_k)
            if k + 1 < len(sa):
                vx, vy = float(px[k + 1] - px[k]), float(py[k + 1] - py[k])
                m = math.hypot(vx, vy)
                if m > 1e-6:
                    s += D.arrow(float(px[k]), float(py[k]),
                                 float(px[k]) + 30 * vx / m,
                                 float(py[k]) + 30 * vy / m, col_k, 2.0, 7.0)
        # Where it ended, and make a failure unmissable. The Episode 9 deployed
        # policy runs out of road 4 m before the corner exit, which on a plot
        # reads as "nearly finished" unless the moment is marked.
        fin = float(sa[-1]) >= track.length - 1.0
        off = abs(float(n[-1])) > track.half_width - 1e-6
        if win[-1]:
            ex, ey = float(px[-1]), float(py[-1])
            if off:
                for dx, dy in ((-1, -1), (-1, 1)):
                    s += (f'<line x1="{ex + dx*11:.1f}" y1="{ey + dy*11:.1f}" '
                          f'x2="{ex - dx*11:.1f}" y2="{ey - dy*11:.1f}" '
                          f'stroke="{V.COR}" stroke-width="3.4"/>')
                s += D.text(ex + 16, ey + 4, "OFF", V.COR, 12, weight="600")
            else:
                s += (f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="10" fill="none" '
                      f'stroke="{accent}" stroke-width="2.4"/>')

        s += D.text(L, B + 30,
                    "completed the lap" if fin
                    else f"LEFT THE ROAD at {sa[-1]:.0f} m of {track.length:.0f}",
                    accent, 12.5, weight="600")
        if fin:
            s += D.text(L, B + 48,
                        f"(cropped at {s_hi:.0f} m — the rest of the exit "
                        f"straight is beyond the frame)",
                        V.MUT, 10.5, style="italic")
        s += D.text(L, B + 66,
                    f"worst slip {float(np.max(slip)):.1f}°   ·   "
                    f"{100*float(np.mean(slip > 12.0)):.0f}% of steps past 12°",
                    V.MUT, 11.5, mono=True)
        s += D.text(L, B + 84,
                    f"speed {float(spd.min()):.1f}–{float(spd.max()):.1f} m/s"
                    + (f"   ·   {len(sa)*0.02:.2f} s" if fin else ""),
                    V.MUT, 11.5, mono=True)

    # legends
    ly = 200 + rows * ph + 10
    s += D.text(70, ly, "slip angle — the gap between pointing and going:",
                V.MUT, 11.5)
    for i, (deg, lab) in enumerate(((0, "0°"), (6, "6°"), (12, "12° — edge of "
                                    "our tire data"), (24, "24°"), (36, "36°+"))):
        bx = 430 + i * 150
        s += (f'<rect x="{bx}" y="{ly-11}" width="70" height="13" rx="3" '
              f'fill="{_slip_colour(deg)}"/>')
        s += D.text(bx, ly + 19, lab, V.MUT, 10)
    s += D.text(70, ly + 44, "line colour — speed:", V.MUT, 11.5)
    for i in range(5):
        u = i / 4.0
        bx = 430 + i * 150
        s += (f'<rect x="{bx}" y="{ly+33}" width="70" height="13" rx="3" '
              f'fill="{_speed_colour(u)}"/>')
        s += D.text(bx, ly + 63, f"{v_lo + u*(v_hi-v_lo):.0f} m/s", V.MUT, 10)

    s += D.text(40, H - 40, stamp, V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "Cars drawn oversized for legibility; positions, headings and the "
        "direction arrows are to scale. Cropped to where each rollout ended.",
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


__all__ = ["path_review", "line_compare", "SLIP_FULL_SCALE"]


def line_compare(cases, title: str, subtitle: str, stamp: str,
                 note_lines=(), channel: str = "drive",
                 channel_label: str = "throttle command  (−1 = full brake)") -> str:
    """Overlaid lines with no cars, plus unrolled offset, speed and one control.

    The companion to :func:`path_review`. Cars-along-the-path is right for judging
    whether *one* rollout is physically sensible; overlaid lines are right for
    asking *why two rollouts differ*. The curved track hides the answer — offsets
    of a metre are a few pixels on a 40 m radius — so the unrolled panels carry
    the actual comparison and the road view carries the intuition.

    The control panel is what makes a mechanism visible rather than inferred: two
    policies can look similar on the road and be doing completely different things
    with the throttle.
    """
    from .line_figures import track_backdrop
    from physics.track import long_exit

    track = long_exit()
    W, H = 1520, 1180
    s = V.head(W, H, title, subtitle)

    s_lo, s_hi = T_ENTRY - 25.0, T_ENTRY + T_ARC + 30.0
    back, to_px, scale = track_backdrop(track, s_lo, s_hi, 70, 560, 190, 760)
    s += D.panel_title(70, 168, "A · The corner from above")
    s += back
    for case in cases:
        tr = case["trace"]
        m = (tr["s"] >= s_lo) & (tr["s"] <= s_hi)
        x, y = track.to_xy(tr["s"][m], tr["n"][m])
        px, py = to_px(x, y)
        s += (f'<path d="{V.path(list(zip(px, py)))}" fill="none" '
              f'stroke="{case["colour"]}" stroke-width="3"'
              + (' stroke-dasharray="9 6"' if case.get("dashed") else "") + '/>')
        if not tr["finished"] and m.any():
            ex, ey = float(px[-1]), float(py[-1])
            for dx, dy in ((-1, -1), (-1, 1)):
                s += (f'<line x1="{ex + dx*10:.1f}" y1="{ey + dy*10:.1f}" '
                      f'x2="{ex - dx*10:.1f}" y2="{ey - dy*10:.1f}" '
                      f'stroke="{case["colour"]}" stroke-width="3.2"/>')
            s += D.text(ex + 15, ey + 4, "OFF", case["colour"], 11,
                        weight="600")

    hw = track.half_width
    panels = [
        ("B · Where on the road", "offset from centreline (m)", "n",
         (-hw - 0.3, hw + 0.3), 190, 430, [-hw, hw]),
        ("C · Speed", "speed (m/s)", "speed", None, 500, 740, []),
        (f"D · {channel_label}", "action", channel, (-1.05, 1.05), 810, 1050,
         [0.0]),
    ]
    for pt, ylab, key, ylim, T, B, guides in panels:
        # Autoscale over the PLOTTED WINDOW, never the whole track. The exit
        # straight reaches 39 m/s, which squashed a 17-23 m/s comparison into
        # the bottom fifth of the panel and read as "nothing happens here".
        vals = np.concatenate([
            c["trace"][key][(c["trace"]["s"] >= s_lo) & (c["trace"]["s"] <= s_hi)]
            for c in cases])
        lo, hi = ylim if ylim else (float(vals.min()) - 0.5,
                                    float(vals.max()) + 0.5)
        ax = _Ax(690, 1440, T, B, s_lo, s_hi, lo, hi)
        s += D.panel_title(690, T - 22, pt)
        s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 5, 4)
        xt = [(f"{v:.0f}", float(ax.x(v))) for v in (50, 70, 100, 133, 160)]
        yt = [(f"{v:+.1f}" if key == channel else f"{v:.0f}", float(ax.y(v)))
              for v in np.linspace(lo, hi, 4)]
        s = V.axes(s, ax.L, ax.R, ax.T, ax.B,
                   "distance along the track (m)", ylab, xt, yt)
        s += (f'<rect x="{float(ax.x(T_ENTRY)):.1f}" y="{ax.T}" '
              f'width="{float(ax.x(T_ENTRY+T_ARC)-ax.x(T_ENTRY)):.1f}" '
              f'height="{ax.B-ax.T}" fill="{V.AMB}" opacity="0.08"/>')
        for g in guides:
            s += (f'<line x1="{ax.L}" y1="{float(ax.y(g)):.1f}" x2="{ax.R}" '
                  f'y2="{float(ax.y(g)):.1f}" stroke="{V.MUT}" '
                  f'stroke-width="1.2" stroke-dasharray="4 5"/>')
        if key == "n":
            s += D.text(float(ax.x(T_ENTRY + 0.5*T_ARC)), ax.T + 16,
                        "the corner", V.AMB, 10, "middle")
            s += D.text(ax.R - 4, float(ax.y(hw)) - 6, "road edge", V.COR, 10,
                        "end")
        for case in reversed(cases):   # cases[0] drawn last, so it sits on top
            tr = case["trace"]
            m = (tr["s"] >= s_lo) & (tr["s"] <= s_hi)
            s += (f'<path d="{V.path(ax.pts(tr["s"][m], tr[key][m]))}" '
                  f'fill="none" stroke="{case["colour"]}" stroke-width="2.2"'
                  + (' stroke-dasharray="8 5"' if case.get("dashed") else "")
                  + '/>')

    ly = 800
    for i, case in enumerate(cases):
        tr = case["trace"]
        inc = (tr["s"] >= T_ENTRY) & (tr["s"] <= T_ENTRY + T_ARC)
        y = ly + i * 46
        s += (f'<line x1="70" y1="{y-4}" x2="112" y2="{y-4}" '
              f'stroke="{case["colour"]}" stroke-width="3.4"'
              + (' stroke-dasharray="8 5"' if case.get("dashed") else "") + '/>')
        s += D.text(124, y, case["label"], case["colour"], 13, weight="600")
        s += D.text(124, y + 18, case["sub"], V.MUT, 11)
        s += D.text(400, y,
                    "completed" if tr["finished"]
                    else f"OFF at {float(tr['s'][-1]):.0f} m",
                    V.TEAL if tr["finished"] else V.COR, 12, mono=True)
        s += D.text(400, y + 18,
                    f"slowest in corner {float(tr['speed'][inc].min()):.2f} m/s",
                    V.MUT, 11, mono=True)

    if note_lines:
        s += D.rule(70, ly + 46 * len(cases) + 14, 620, V.GRID)
        for i, line in enumerate(note_lines):
            s += D.text(70, ly + 46 * len(cases) + 42 + 20 * i, line, V.MUT, 12)

    s += D.text(40, H - 40, stamp, V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "No cars drawn: the comparison is between lines, and outlines on nearly "
        "the same arc obscure it. Panel A is intuition; B, C and D carry the "
        "measurement.",
    )
