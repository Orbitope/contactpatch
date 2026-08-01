"""Lap traces on a real circuit — the pictorial half of every RL track result.

CLAUDE.md rule 1: pictorial first, technical second. A speed-versus-distance
plot only means something to a reader who already knows the circuit; a lap
drawn on the actual outline of Spa, coloured by speed, means something to
anyone. Rule 10: parameterised builder, SVG, so any policy or any frame can
be re-rendered by calling this again with different arrays.

Everything here is driven by data passed in. Nothing about a particular
circuit or a particular policy is baked in.
"""

from __future__ import annotations

import numpy as np

from viz.lib import esc, BG, FG, MUT, GRID, AMB, COR, TEAL, ramp


def _fit(xs, ys, w, h, pad):
    """World (metres) -> screen, preserving aspect. Y flips: SVG grows down."""
    x0, x1 = float(np.min(xs)), float(np.max(xs))
    y0, y1 = float(np.min(ys)), float(np.max(ys))
    sx = (w - 2 * pad) / max(x1 - x0, 1e-9)
    sy = (h - 2 * pad) / max(y1 - y0, 1e-9)
    s = min(sx, sy)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    def to_screen(X, Y):
        return (w / 2 + (np.asarray(X) - cx) * s,
                h / 2 - (np.asarray(Y) - cy) * s)   # flip
    return to_screen, s


def lap_trace(track, x, y, speed, *, title, subtitle, note, stamp,
              width=1000, height=760, pad=70, edges=True,
              marks=None, v_lo=None, v_hi=None):
    """One lap drawn on its circuit, coloured by speed.

    ``track`` supplies the outline; ``x``/``y``/``speed`` are the driven
    trajectory in world coordinates. ``marks`` is an optional list of
    ``(x, y, label)`` annotations — start line, a named corner, wherever a
    policy failed.
    """
    sc, sub_c = float(np.min(speed)), float(np.max(speed))
    v_lo = sc if v_lo is None else v_lo
    v_hi = sub_c if v_hi is None else v_hi

    s_c, xc, yc, _ = track.centreline(2000)
    hw = np.asarray(track.half_width_at(s_c))
    # Track edges from the centreline normal, so the drawn width is the width
    # the simulator actually enforced rather than a decorative constant.
    dx = np.gradient(xc); dy = np.gradient(yc)
    L = np.hypot(dx, dy); L[L == 0] = 1e-9
    nx, ny = -dy / L, dx / L
    xl, yl = xc + nx * hw, yc + ny * hw
    xr, yr = xc - nx * hw, yc - ny * hw

    allx = np.concatenate([xl, xr, np.asarray(x)])
    ally = np.concatenate([yl, yr, np.asarray(y)])
    to_screen, _ = _fit(allx, ally, width, height, pad)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
           f'height="{height}" viewBox="0 0 {width} {height}" '
           f'font-family="Inter, system-ui, sans-serif">'
           f'<rect width="{width}" height="{height}" fill="{BG}"/>']
    out.append(f'<text x="40" y="46" fill="{FG}" font-size="21" '
               f'font-weight="600">{esc(title)}</text>')
    out.append(f'<text x="40" y="70" fill="{MUT}" font-size="13">'
               f'{esc(subtitle)}</text>')

    # --- the road ---
    for X, Y in ((xl, yl), (xr, yr)):
        px, py = to_screen(X, Y)
        d = "M " + " L ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px, py)) + " Z"
        out.append(f'<path d="{d}" fill="none" stroke="{GRID}" stroke-width="1.6"/>')
    pxl, pyl = to_screen(xl, yl)
    pxr, pyr = to_screen(xr, yr)
    band = ("M " + " L ".join(f"{a:.1f},{b:.1f}" for a, b in zip(pxl, pyl))
            + " L " + " L ".join(f"{a:.1f},{b:.1f}"
                                 for a, b in zip(pxr[::-1], pyr[::-1])) + " Z")
    out.append(f'<path d="{band}" fill="#232326" stroke="none"/>')

    # --- the driven line, coloured by speed ---
    px, py = to_screen(x, y)
    v = np.asarray(speed, dtype=float)
    step = max(1, len(px) // 1400)          # cap segment count, keep the file small
    for i in range(0, len(px) - step, step):
        u = (v[i] - v_lo) / max(v_hi - v_lo, 1e-9)
        r, g, b = ramp(float(np.clip(u, 0, 1)))
        out.append(f'<line x1="{px[i]:.1f}" y1="{py[i]:.1f}" '
                   f'x2="{px[i+step]:.1f}" y2="{py[i+step]:.1f}" '
                   f'stroke="rgb({r},{g},{b})" stroke-width="2.6" '
                   f'stroke-linecap="round"/>')

    for mx, my, lab in (marks or []):
        sx_, sy_ = to_screen([mx], [my])
        out.append(f'<circle cx="{sx_[0]:.1f}" cy="{sy_[0]:.1f}" r="5" '
                   f'fill="none" stroke="{AMB}" stroke-width="2"/>')
        out.append(f'<text x="{sx_[0]+10:.1f}" y="{sy_[0]-8:.1f}" fill="{AMB}" '
                   f'font-size="12">{esc(lab)}</text>')

    # --- speed legend ---
    lx, ly, lw = width - 250, 110, 190
    out.append(f'<text x="{lx}" y="{ly-12}" fill="{MUT}" font-size="11.5">'
               f'speed along the lap</text>')
    for i in range(60):
        r, g, b = ramp(i / 59)
        out.append(f'<rect x="{lx + lw*i/60:.1f}" y="{ly}" '
                   f'width="{lw/60+0.8:.1f}" height="11" fill="rgb({r},{g},{b})"/>')
    out.append(f'<text x="{lx}" y="{ly+26}" fill="{MUT}" font-size="11">'
               f'{v_lo:.1f} m/s</text>')
    out.append(f'<text x="{lx+lw}" y="{ly+26}" fill="{MUT}" font-size="11" '
               f'text-anchor="end">{v_hi:.1f} m/s</text>')

    out.append(f'<text x="40" y="{height-40}" fill="{FG}" font-size="12.5">'
               f'{esc(note)}</text>')
    out.append(f'<text x="40" y="{height-18}" fill="{MUT}" font-size="10.5" '
               f'font-style="italic">{esc(stamp)}</text>')
    out.append('</svg>')
    return "".join(out)
