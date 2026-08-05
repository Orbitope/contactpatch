"""Episode 10's `morph_figure`, in motion — two cars through the same corner,
at the same simulated time, side by side.

CLAUDE.md rule 10: "an animation is a loop over the same function rather than
a rebuild." `frame()` below is that function — one static SVG frame, exactly
`morph_figure`'s pictorial vocabulary (`track_backdrop`, `path_heading`,
`car_plan`) reused rather than reinvented, parameterised by frame index. The
driver script (`experiments/tools/render_morph_animation.py`) is the loop.

**Why two cars, synchronised by simulation step rather than by distance.**
Every trace in `traces.npz` is logged at fixed `dt=0.02` (`physics.rl_env.DT`),
so index ``i`` is the same elapsed simulated time for every car, however far
each has actually travelled. Synchronising on TIME rather than on arc length
is what lets a viewer see one car still braking while another has already
turned in — synchronising on distance would hide exactly that.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V
from .line_figures import track_backdrop, path_heading
from physics.track import CORNER_ARC as T_ARC, ENTRY_STRAIGHT as T_ENTRY

W, H = 1280, 760
S_LO, S_HI = T_ENTRY - 34.0, T_ENTRY + T_ARC + 60.0


def frame(track, traces, tags, labels, colours, i: int, dt: float,
          trail_s: float = 20.0) -> str:
    """One frame: both cars at simulation step ``i``, or parked at the road
    edge with a fault marker once a car's own trace has ended.

    ``trail_s`` is how much of each car's own recent path to draw behind it,
    in track metres — a bare dot reads as a car floating, not driving.
    """
    L, R, T, B = 160, W - 40, 90, H - 130
    back, to_px, scale = track_backdrop(track, S_LO, S_HI, L, R, T, B)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="Inter, system-ui, sans-serif">',
           f'<rect width="{W}" height="{H}" fill="{V.BG}"/>']
    out.append(D.text(40, 40, "One driver, two cars, the same corner",
                      V.FG, 19, weight="600"))
    out.append(D.text(40, 62,
        "Same policy, same seed, same instant of simulated time — only the "
        "car's own weight distribution differs.", V.MUT, 12.5))
    out.append(back)

    t = i * dt
    out.append(D.text(40, H - 96, f"t = {t:5.2f} s", V.FG, 15, mono=True))

    for tag, label, colour in zip(tags, labels, colours):
        sa, n = traces[f"{tag}_s"], traces[f"{tag}_n"]
        xi = traces[f"{tag}_xi"]
        finished = bool(traces[f"{tag}_finished"])
        n_steps = len(sa)
        alive = i < n_steps

        k = min(i, n_steps - 1)
        head = path_heading(track, sa[max(0, k - 1):k + 1],
                            xi[max(0, k - 1):k + 1])
        hd = D.screen_heading_deg(math.degrees(float(head[-1])))
        x, y = track.to_xy(np.array([sa[k]]), np.array([n[k]]))
        px, py = to_px(x, y)
        px, py = float(px[0]), float(py[0])

        # Trail: the last `trail_s` metres of THIS car's own path, so motion
        # reads even from a single static export and a viewer can see the
        # line each car is actually taking, not just its current point.
        lo = max(0, np.searchsorted(sa[:k + 1], sa[k] - trail_s))
        tx, ty = track.to_xy(sa[lo:k + 1], n[lo:k + 1])
        tpx, tpy = to_px(tx, ty)
        if len(tpx) > 1:
            pts = " L ".join(f"{a:.1f},{b:.1f}" for a, b in zip(tpx, tpy))
            out.append(f'<path d="M {pts}" fill="none" stroke="{colour}" '
                       f'stroke-width="2.2" opacity="0.55"/>')

        if alive:
            out.append(D.car_plan(px, py, length=46, width=22, wheel_len=13,
                                  wheel_w=6, heading_deg=hd,
                                  loads=(0.5,) * 4, body=colour))
        else:
            # The car's own trace ends before this frame — it left the road
            # or finished before this instant. Marked, not silently absent:
            # a car that vanishes with no explanation reads as a rendering
            # bug (F36's family), not as "this design failed here".
            reason = "left the road" if not finished else "off top of window"
            out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="none" '
                       f'stroke="{colour}" stroke-width="2.4" '
                       f'stroke-dasharray="3 3"/>')
            out.append(D.text(px + 14, py + 4, reason, colour, 11))

        ly = T + (0 if tag == tags[0] else 26)
        out.append(f'<line x1="{L}" y1="{ly-4}" x2="{L+30}" y2="{ly-4}" '
                   f'stroke="{colour}" stroke-width="3"/>')
        out.append(D.text(L + 38, ly, label, colour, 13, weight="600"))

    out.append(D.text(40, H - 40,
        "Same road, same policy, same instant — the paths diverge because "
        "the cars do.", V.FG, 12.5))
    out.append(V.foot(W, H,
        "[MEASURED] Episode 10 policy, DEPLOYED (mean-action), one seed. "
        "Slip envelope penalised; not enforced as a hard bound."))
    # `foot()` closes </svg> itself — appending another was the malformed-XML
    # bug the first render caught (qlmanage: "Extra content at the end of the
    # document"). One place to close the root, not two.
    return "".join(out)


def n_frames(traces, tags) -> int:
    return max(len(traces[f"{t}_s"]) for t in tags)
