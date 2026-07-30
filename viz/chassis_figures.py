"""Episode 15 figures — does an active controller flatten chassis design?

``flattening_paths``
    The pictorial hero. Five layout archetypes, the same corner, the same
    aggression — TV off on the left, TV on on the right. Nobody needs to know
    what a cornering limit is to read "four cars leave the road, then none do."
``flattening_card``
    The technical version: the cornering-limit spread across each design
    sweep, TV off against TV on, at both power levels — the numbers behind
    the picture.
"""

from __future__ import annotations

import numpy as np

from . import diagram as D
from . import lib as V
from .line_figures import track_backdrop
from physics.track import CORNER_ARC, ENTRY_STRAIGHT, long_exit

ARCH_LABEL = {
    "front_fwd": "front engine, FWD",
    "front_rwd": "front engine, RWD",
    "front_mid_rwd": "front-mid, RWD",
    "mid_rwd": "mid engine, RWD",
    "rear_rwd": "rear engine, RWD",
}
ARCHETYPES = ("front_fwd", "front_rwd", "front_mid_rwd", "mid_rwd", "rear_rwd")
#: Distinct per-archetype colours for the "still on the road" lines. COR (red)
#: is reserved for "left the road", so it is deliberately not in this ramp.
RAMP = (V.TEAL, V.GRN, V.AMB, V.VIO, V.SLATE)
S_LO, S_HI = ENTRY_STRAIGHT - 20.0, ENTRY_STRAIGHT + CORNER_ARC + 40.0


def _stamp(y: float, gu: float) -> str:
    return D.text(40, y, "  -  ".join([
        "[MEASURED] double-track model, closed-loop driver, long_exit, "
        f"grip_use held fixed at {gu:.2f}, 2x power",
        "RUNG 2 — ordering and direction only, not a real car (rule 15)",
    ]), V.MUT, 9.5)


def flattening_paths(results, traces) -> str:
    """TV off vs TV on, five archetypes, one shared aggression."""
    track = long_exit()
    gu = results.get("shared_gu_figure", 0.65)
    W, H = 1400, 900
    s = V.head(
        W, H,
        "Five cars, one corner — with the controller off, then on",
        "Same driver, same corner, same aggression (grip_use held fixed, not "
        "each car's own limit). Left: an open differential. Right: torque "
        "vectoring. Nothing else changes.",
    )

    panW = (W - 80) / 2
    for col, tv in enumerate(("open", "tv4")):
        L = 40 + col * panW
        label = "TV off — open differential" if tv == "open" else "TV on — four-wheel allocator"
        s += D.text(L + 14, 110, label, V.FG, 16, weight="600")
        back, to_px, _ = track_backdrop(track, S_LO, S_HI, L + 14, L + panW - 26,
                                        140, H - 90)
        s += back
        n_fail = 0
        for i, name in enumerate(ARCHETYPES):
            tag = f"{tv}_{name}"
            if f"{tag}_s" not in traces:
                continue
            sa, nn = traces[f"{tag}_s"], traces[f"{tag}_n"]
            fin = bool(traces[f"{tag}_finished"][0])
            if not fin:
                n_fail += 1
            m = (sa >= S_LO) & (sa <= S_HI)
            if not m.any():
                continue
            x, y = track.to_xy(sa[m], nn[m])
            px, py = to_px(x, y)
            colour = RAMP[i % len(RAMP)] if fin else V.COR
            pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px, py))
            s += (f'<polyline points="{pts}" fill="none" stroke="{colour}" '
                  f'stroke-width="{2.6 if fin else 3.2}" '
                  f'opacity="{0.85 if fin else 1.0}"/>')
            if not fin:
                s += (f'<circle cx="{px[-1]:.1f}" cy="{py[-1]:.1f}" r="6" '
                      f'fill="{V.COR}"/>')
        s += D.text(L + 14, H - 55,
                    f"{5-n_fail}/5 cars still on the road" if n_fail else
                    "5/5 cars still on the road",
                    V.TEAL if n_fail == 0 else V.COR, 14, weight="600")

    s += _stamp(H - 30, gu)
    return s + V.foot(
        W, H,
        "Every path is simulation output, not drawn. A line that stops and "
        "ends in a red dot is a car that left the road.",
    )


def flattening_card(results) -> str:
    """The spread numbers: TV off vs TV on, both axes, both power levels."""
    fl = results["flattening"]
    W, H = 1200, 620
    s = V.head(
        W, H,
        "Does the controller flatten design sensitivity?",
        "Spread in cornering-limit grip_use across each design sweep — "
        "smaller is flatter. Bars share one scale.",
    )

    rows = [
        ("Layout, 1x power", fl["layout"]["1x"]),
        ("Layout, 2x power", fl["layout"]["2x"]),
        ("Balance (RWD), 1x power", fl["balance"]["1x|rwd"]),
        ("Balance (RWD), 2x power", fl["balance"]["2x|rwd"]),
        ("Balance (FWD), 1x power", fl["balance"]["1x|fwd"]),
        ("Balance (FWD), 2x power", fl["balance"]["2x|fwd"]),
    ]
    max_spread = max(v["off"] for _, v in rows)
    x0, bar_max_w, y0, rowh = 260, 780, 130, 78
    for i, (label, v) in enumerate(rows):
        y = y0 + i * rowh
        s += D.text(40, y - 8, label, V.FG, 13.5, weight="600")
        off_w = bar_max_w * v["off"] / max_spread
        on_w = bar_max_w * v["on"] / max_spread
        s += (f'<rect x="{x0}" y="{y}" width="{off_w:.1f}" height="16" '
              f'fill="{V.COR}" opacity="0.85"/>')
        s += D.text(x0 + off_w + 8, y + 13, f"TV off: {v['off']:.3f}", V.MUT, 11.5)
        s += (f'<rect x="{x0}" y="{y+22}" width="{on_w:.1f}" height="16" '
              f'fill="{V.TEAL}" opacity="0.85"/>')
        s += D.text(x0 + on_w + 8, y + 35, f"TV on: {v['on']:.3f}", V.MUT, 11.5)
        factor = v["off"] / v["on"] if v["on"] > 1e-6 else float("inf")
        flattens = v["on"] < v["off"] * 0.9
        note = (f"{factor:.1f}x flatter" if flattens and np.isfinite(factor)
               else "no measurable flattening")
        s += D.text(40, y + 34, note,
                    V.TEAL if flattens else V.AMB, 12, style="italic")

    s += D.rule(40, y0 + len(rows) * rowh + 6, W - 80, V.GRID)
    s += D.text(40, y0 + len(rows) * rowh + 32,
                "The front-driven balance sweep is not a gap in the result — "
                "its limit is a front-tire slip-angle ceiling, not a traction "
                "problem, so there is nothing for an allocator to redistribute.",
                V.MUT, 12.5)
    s += _stamp(H - 20, results.get("shared_gu_figure", 0.65))
    return s + V.foot(
        W, H,
        "Rung 2 (rule 15) — a trend on a model with no roll camber, roll "
        "steer or compliance steer, not a claim about a real car.",
    )
