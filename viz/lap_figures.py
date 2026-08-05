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


def _wrap(s: str, n: int) -> list[str]:
    """Greedy word wrap. Captions are prose (rule 1: every figure ends with a
    plain sentence), and prose long enough to say something useful is long
    enough to run off a 1000 px canvas."""
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def _axis_max(v: float, n_ticks: int = 4) -> float:
    """Smallest round axis maximum at or above ``v``, so mid-ticks are clean.

    Rounding the maximum itself to a 1/2/2.5/5 decade is too coarse -- 13.2
    becomes 20 and a third of the panel is empty. Rounding the *step* and
    taking the next multiple gives 15, and every tick still reads as a round
    number."""
    import math
    if v <= 0:
        return 1.0
    raw = v / max(n_ticks, 1)
    k = math.floor(math.log10(raw))
    base = 10.0 ** k
    step = next((m * base for m in (1.0, 2.0, 2.5, 5.0)
                 if raw <= m * base * 1.0000001), 10.0 * base)
    return math.ceil(v / step - 1e-9) * step


def _caption(out, x, y_top, note, stamp, n_note=112, n_stamp=142):
    """Stack the plain-English note and the provenance stamp from ``y_top``.

    Laid out sequentially rather than at two fixed offsets: a note that wraps
    to three lines used to overprint the stamp, and a provenance line nobody
    can read is the same as no provenance line (rule 3)."""
    y = y_top
    for ln in _wrap(note, n_note):
        out.append(f'<text x="{x}" y="{y:.1f}" fill="{FG}" '
                   f'font-size="12.5">{esc(ln)}</text>')
        y += 17.0
    y += 9.0
    for ln in _wrap(stamp, n_stamp):
        out.append(f'<text x="{x}" y="{y:.1f}" fill="{MUT}" '
                   f'font-size="10.5" font-style="italic">{esc(ln)}</text>')
        y += 13.0
    return y


def _fit(xs, ys, w, h, pad, top=0.0, bottom=0.0):
    """World (metres) -> screen, preserving aspect. Y flips: SVG grows down.

    ``top``/``bottom`` reserve bands the drawing may not enter -- the title
    block and the caption. Without them the circuit is centred on the whole
    canvas and the caption prints straight over the track, which is not a
    cosmetic problem: text across the racing line hides the part of the figure
    the caption is describing."""
    x0, x1 = float(np.min(xs)), float(np.max(xs))
    y0, y1 = float(np.min(ys)), float(np.max(ys))
    usable = h - top - bottom
    sx = (w - 2 * pad) / max(x1 - x0, 1e-9)
    sy = (usable - 2 * pad) / max(y1 - y0, 1e-9)
    s = min(sx, sy)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    mid = top + usable / 2
    def to_screen(X, Y):
        return (w / 2 + (np.asarray(X) - cx) * s,
                mid - (np.asarray(Y) - cy) * s)   # flip
    return to_screen, s


def lap_trace(track, x, y, speed, *, title, subtitle, note, stamp,
              width=1000, height=820, pad=70, edges=True,
              marks=None, v_lo=None, v_hi=None,
              colour_label="speed along the lap", unit="m/s", fmt="{:.1f}",
              cap_reserve=132.0):
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
    to_screen, _ = _fit(allx, ally, width, height, pad,
                        top=88.0, bottom=cap_reserve)

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
    out.append(f'<path d="{band}" fill="#2b2b30" stroke="none"/>')

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
    lx, ly, lw = width - 214, 106, 170
    out.append(f'<text x="{lx}" y="{ly-12}" fill="{MUT}" font-size="11.5">'
               f'{esc(colour_label)}</text>')
    for i in range(60):
        r, g, b = ramp(i / 59)
        out.append(f'<rect x="{lx + lw*i/60:.1f}" y="{ly}" '
                   f'width="{lw/60+0.8:.1f}" height="11" fill="rgb({r},{g},{b})"/>')
    out.append(f'<text x="{lx}" y="{ly+26}" fill="{MUT}" font-size="11">'
               f'{fmt.format(v_lo)} {esc(unit)}</text>')
    out.append(f'<text x="{lx+lw}" y="{ly+26}" fill="{MUT}" font-size="11" '
               f'text-anchor="end">{fmt.format(v_hi)} {esc(unit)}</text>')

    _caption(out, 40, height - 122, note, stamp)
    out.append('</svg>')
    return "".join(out)


def lap_profile(dist, panels, *, title, subtitle, note, stamp,
                width=1000, height=640):
    """The technical companion to ``lap_trace``: any number of traces against
    distance, on a shared x-axis.

    ``panels`` is a list of ``(values, ylabel, colour, y_hi, limit_or_None,
    limit_label)``. Kept general rather than hard-coding speed-and-slip
    (rule 10) so a torque-vectoring run can add yaw moment, or a braking
    study a longitudinal trace, without touching this file.

    CLAUDE.md rule 1 keeps this as the *second* figure, never the only one.
    It carries what the pictorial cannot: how close the policy ran to the
    edge. A limit line is drawn where one exists, because a trace without it
    invites the reader to judge "is 10 degrees a lot?" from nothing.
    """
    d = np.asarray(dist, dtype=float)
    L, R = 84.0, width - 60.0
    top, bottom = 100.0, height - 132.0
    n_p = len(panels)
    gap = 30.0
    ph = (bottom - top - gap * (n_p - 1)) / n_p

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
           f'height="{height}" viewBox="0 0 {width} {height}" '
           f'font-family="Inter, system-ui, sans-serif">'
           f'<rect width="{width}" height="{height}" fill="{BG}"/>',
           f'<text x="40" y="40" fill="{FG}" font-size="19" '
           f'font-weight="600">{esc(title)}</text>',
           f'<text x="40" y="62" fill="{MUT}" font-size="12.5">'
           f'{esc(subtitle)}</text>']

    sx = lambda q: L + (R - L) * (q - d[0]) / max(d[-1] - d[0], 1e-9)
    for j, (ys, ylab, colour, y_hi, limit, lim_lab) in enumerate(panels):
        T = top + j * (ph + gap)
        B = T + ph
        ys = np.asarray(ys, dtype=float)
        y_hi = _axis_max(y_hi)
        sy = lambda q, T=T, B=B, y_hi=y_hi: B - (B - T) * q / max(y_hi, 1e-9)
        for f in (0.25, 0.5, 0.75):
            out.append(f'<line x1="{L}" y1="{T+ph*f:.1f}" x2="{R}" '
                       f'y2="{T+ph*f:.1f}" stroke="{GRID}" stroke-width="0.8"/>')
        if limit is not None:
            out.append(f'<line x1="{L}" y1="{sy(limit):.1f}" x2="{R}" '
                       f'y2="{sy(limit):.1f}" stroke="{COR}" stroke-width="1.4" '
                       f'stroke-dasharray="6 4"/>')
            out.append(f'<text x="{R-4}" y="{sy(limit)-7:.1f}" fill="{COR}" '
                       f'font-size="11" text-anchor="end">{esc(lim_lab)}</text>')
        step = max(1, len(d) // 2200)
        pts = " L ".join(f"{sx(dd):.1f},{sy(q):.1f}"
                         for dd, q in zip(d[::step], ys[::step]))
        out.append(f'<path d="M {pts}" fill="none" stroke="{colour}" '
                   f'stroke-width="1.7"/>')
        out.append(f'<line x1="{L}" y1="{B}" x2="{R}" y2="{B}" '
                   f'stroke="{GRID}" stroke-width="1.2"/>')
        out.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{B}" '
                   f'stroke="{GRID}" stroke-width="1.2"/>')
        for f in (0.0, 0.5, 1.0):
            q = f * y_hi
            lab = f"{q:.2f}".rstrip("0").rstrip(".") if y_hi < 10 else f"{q:.0f}"
            out.append(f'<text x="{L-8}" y="{sy(q)+4:.1f}" fill="{MUT}" '
                       f'font-size="10.5" text-anchor="end">{lab}</text>')
        # Label ABOVE the panel, left-aligned: anchored to the left of the
        # axis it ran off the canvas for any label longer than "deg".
        out.append(f'<text x="{L}" y="{T-9:.1f}" fill="{colour}" '
                   f'font-size="11.5" font-weight="600">{esc(ylab)}</text>')

    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        q = d[0] + f * (d[-1] - d[0])
        out.append(f'<text x="{sx(q):.1f}" y="{bottom+18:.1f}" fill="{MUT}" '
                   f'font-size="10.5" text-anchor="middle">{q:.0f}</text>')
    out.append(f'<text x="{(L+R)/2:.1f}" y="{bottom+36:.1f}" fill="{MUT}" '
               f'font-size="11" text-anchor="middle">'
               f'distance along the lap (m)</text>')
    _caption(out, 40, height - 126, note, stamp)
    out.append('</svg>')
    return "".join(out)
