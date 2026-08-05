"""Episode 6, in motion — front-wheel drive vs rear-wheel drive, one corner.

Same vocabulary as `morph_animation.py` (`track_backdrop`, `path_heading`,
`car_plan`), and the same synchronisation principle — same instant, not same
arc length — but a different SOURCE of time. Episode 10's RL traces are
logged at a fixed `dt`, so trace index IS elapsed time. Episode 6's traces are
an optimal-control solution sampled at 100 fixed ARC-LENGTH nodes, with
``dt_ds`` (exact — `run.py` verifies `trapz(dt_ds, s)` reproduces the
solver's own reported time to 1e-13 relative error) at each one. Time has to
be built by integrating that, then each car's own state interpolated back
onto a common, evenly-spaced time grid — which is what ``build_time_grid``
and ``frame`` do.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V
from .line_figures import track_backdrop, path_heading


def build_time_grid(s: np.ndarray, dt_ds: np.ndarray) -> np.ndarray:
    """Cumulative time at each ``s`` node, by the trapezoid rule.

    Matches `run.py`'s own integration exactly (same rule, same nodes) so a
    time quoted from this is the solver's own time, not a re-derived one.
    """
    return np.concatenate([[0.0], np.cumsum(
        0.5 * (dt_ds[1:] + dt_ds[:-1]) * np.diff(s))])


def frame(track, s, t_nodes, n, xi, tags, labels, colours, t: float,
          window: tuple[float, float], trail_s: float = 20.0,
          w: int = 1280, h: int = 760) -> str:
    """One frame at simulated time ``t``. ``t_nodes``, ``n``, ``xi`` are dicts
    keyed by tag, each holding that car's own arrays over the SHARED ``s``
    grid (n_nodes points) — the per-car time grid is what makes "same instant"
    meaningful despite a shared arc-length parameterisation.
    """
    S_LO, S_HI = window
    L, R, T, B = 160, w - 40, 90, h - 130
    back, to_px, scale = track_backdrop(track, S_LO, S_HI, L, R, T, B)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}" font-family="Inter, system-ui, sans-serif">',
           f'<rect width="{w}" height="{h}" fill="{V.BG}"/>']
    out.append(D.text(40, 40, "Front-wheel drive vs rear-wheel drive, the same corner",
                      V.FG, 19, weight="600"))
    out.append(D.text(40, 62,
        "Optimal-control solutions, both with an ideal (LSD) differential — "
        "the same instant of simulated time for each.", V.MUT, 12.5))
    out.append(back)
    out.append(D.text(40, h - 96, f"t = {t:5.2f} s", V.FG, 15, mono=True))

    for tag, label, colour in zip(tags, labels, colours):
        tn = t_nodes[tag]
        s_now = float(np.interp(t, tn, s))
        n_now = float(np.interp(t, tn, n[tag]))
        xi_now = float(np.interp(t, tn, xi[tag]))
        hd = D.screen_heading_deg(math.degrees(
            float(path_heading(track, np.array([s_now]), np.array([xi_now]))[0])))
        x, y = track.to_xy(np.array([s_now]), np.array([n_now]))
        px, py = float(to_px(x, y)[0][0]), float(to_px(x, y)[1][0])

        lo_s = max(0.0, s_now - trail_s)
        trail_mask = (s >= lo_s) & (s <= s_now)
        if trail_mask.sum() > 1:
            tx, ty = track.to_xy(s[trail_mask], np.interp(s[trail_mask], s, n[tag]))
            tpx, tpy = to_px(tx, ty)
            pts = " L ".join(f"{a:.1f},{b:.1f}" for a, b in zip(tpx, tpy))
            out.append(f'<path d="M {pts}" fill="none" stroke="{colour}" '
                       f'stroke-width="2.2" opacity="0.55"/>')

        out.append(D.car_plan(px, py, length=46, width=22, wheel_len=13,
                              wheel_w=6, heading_deg=hd, loads=(0.5,) * 4,
                              body=colour))

        ly = T + (0 if tag == tags[0] else 26)
        out.append(f'<line x1="{L}" y1="{ly-4}" x2="{L+30}" y2="{ly-4}" '
                   f'stroke="{colour}" stroke-width="3"/>')
        out.append(D.text(L + 38, ly, label, colour, 13, weight="600"))

    out.append(D.text(40, h - 40,
        "Same corner, same solver, same instant — the driven wheels are the "
        "only difference.", V.FG, 12.5))
    out.append(V.foot(w, h,
        "[MEASURED] min-time optimal control, ideal (LSD) differential, "
        "100 nodes. FWD 0.033 s faster over the whole 12.05 s solve — a "
        "0.27% margin, not a large effect (FINDINGS Episode 6)."))
    # foot() closes </svg> itself -- same bug as the first morph_animation
    # render (double-close), caught the same way: cairosvg refused to parse
    # rather than silently degrading.
    return "".join(out)
