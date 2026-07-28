"""Pictorial tire figures — the "look at it and see it" versions.

Three figures, each built to be understood before any axis is read:

``slip_angle_figure``
    What a slip angle *is*, drawn as actual wheels. The Ep 1 hero image.
``load_split_figure``
    Why moving weight onto one tire costs the pair grip, drawn as two wheels
    squashing by different amounts. The Ep 2 hero image.
``reality_check_figure``
    Where our numbers land against published bands, with the source of each band
    named. Answers "is this in line with what the industry says?" rather than
    "does the code match itself?".

Every one of them ends with a plain sentence stating what the reader just saw.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V


def _force_scale(max_force_n: float, max_px: float) -> float:
    return max_px / max_force_n


def _stamp(y: float, tire=None, extra: str = "", x: float = 40.0) -> str:
    """Provenance line. Every figure carries one — CLAUDE.md rule 3.

    A reader must be able to tell, from the figure alone, whether a number was
    measured by our code, published by someone else, or assumed — and which
    configuration produced it. Note in particular that the offsets-removed flag
    is on here: the same tire file with the offsets left in gives a peak mu 7.4%
    apart between left and right, and a figure that does not say which one it is
    is not reproducible.
    """
    bits = []
    if tire is not None:
        p = tire.provenance
        sc = p["scaling"]
        bits += [
            f"[MEASURED] {p['file']}",
            "MF 2002 pure slip",
            "offsets removed" if p["offsets_removed"] else "as shipped",
            f"Fz0′ {p['fz0_prime']:.0f} N",
            f"LMUY {sc['lmuy']:g} · LKY {sc['lky']:g} · LFZO {sc['lfzo']:g}",
        ]
    if extra:
        bits.append(extra)
    return D.text(x, y, "  ·  ".join(bits), V.MUT, 9.5)


# ---------------------------------------------------------------------------
# 1 · What a slip angle is
# ---------------------------------------------------------------------------


def slip_angle_figure(tire, fz: float, alphas_deg=(0.0, 2.0, 5.0, None, 16.0)) -> str:
    """Five identical tires at the same load, differing only in slip angle.

    ``None`` in ``alphas_deg`` is replaced by the peak of the curve, so the
    figure always marks the actual maximum rather than a guessed one.
    """
    peak = tire.peak_lateral(fz)
    alphas = [peak.alpha_peak_deg if a is None else a for a in alphas_deg]
    forces = [abs(float(tire.fy0(math.radians(a), fz))) for a in alphas]

    W, H = 1480, 830
    s = V.head(
        W, H,
        "What a slip angle is, and why grip has a top",
        f"The same tire with the same weight on it ({fz:,.0f} N — one front corner "
        f"of the car at rest). The only thing changing is the angle between where "
        f"the wheel points and where it is actually going.",
    )
    s += D.text(40, 92,
                "Angles are drawn true to scale — this is genuinely how small a "
                "slip angle is. Arrow length is force, to one scale across all five.",
                V.MUT, 11.5)

    x0, dx, cy = 160, 272, 306
    scale = _force_scale(max(forces), 140.0)
    trust_deg = math.degrees(tire.envelope.imposed_alpha_max)

    for i, (a, f) in enumerate(zip(alphas, forces)):
        cx = x0 + i * dx
        is_peak = abs(a - peak.alpha_peak_deg) < 1e-6

        # direction of travel — identical in every cell, which is the whole point
        s += D.arrow(cx, cy + 152, cx, cy - 152, V.MUT, 1.8, 9, dash="5 5")
        s += D.text(cx, cy - 166, "direction of travel", V.MUT, 10.5, "middle")

        # the long centreline is what makes a 2 deg angle visible honestly
        s += D.tire(cx, cy, a, load_frac=0.55, patch=V.SLATE, heading=145)

        if a > 0.01:
            r = 112
            s += D.angle_arc(cx, cy, r, a, V.TEAL, 1.8)
            # offset the label clear of the travel line — at 2 deg the arc end is
            # only 4 px off it, and the number would sit on top of the dashes
            lx = cx + max(34.0, r * math.sin(math.radians(a)) + 16)
            s += D.text(lx, cy - r * math.cos(math.radians(a)) + 4,
                        f"{a:.1f}°", V.TEAL, 13, "start", weight="600")

        if f > 1.0:
            colour = V.AMB if is_peak else V.COR
            s += D.arrow(cx, cy, cx + f * scale, cy, colour, 3.4, 12)

        s += D.text(cx, cy + 195, f"α = {a:.1f}°", V.FG, 13.5, "middle",
                    weight="600" if is_peak else "normal")
        s += D.text(cx, cy + 217, f"{f:,.0f} N", V.AMB if is_peak else V.MUT,
                    13, "middle", mono=True)
        caption = ""
        if a == 0.0:
            caption = "pointed exactly where it is\ngoing: no sideways force"
        elif is_peak:
            caption = "the most it can do"
        elif a > peak.alpha_peak_deg:
            caption = (f"{100*(1-f/max(forces)):.0f}% less than the peak —\n"
                       f"more angle, less grip")
        elif f / max(forces) > 0.85:
            caption = (f"already {100*f/max(forces):.0f}% of everything\n"
                       f"the tire will ever give")
        else:
            caption = f"{100*f/max(forces):.0f}% of the maximum"
        for j, line in enumerate(caption.split("\n")):
            s += D.text(cx, cy + 240 + 16 * j, line,
                        V.AMB if is_peak else V.MUT, 11, "middle")
        if a > trust_deg:
            s += D.text(cx, cy + 282,
                        f"past our {trust_deg:.0f}° trust limit", V.VIO, 10.5,
                        "middle", style="italic")

    # bridge to the conventional chart: these same five points on the curve
    bx0, bx1, by0, by1 = 160, 1330, 760, 640
    s += D.text(bx0, 600,
                "Those same five tires, drawn the way engineers usually draw them. "
                "Every point on this curve is one of the pictures above.",
                V.MUT, 12)
    s += D.rule(bx0, by0, bx1, V.MUT)
    a_fine = np.linspace(0.0, 20.0, 300)
    f_fine = np.abs(tire.fy0(np.radians(a_fine), fz))
    fmax = float(f_fine.max())
    pts = [(bx0 + (bx1 - bx0) * a / 20.0, by0 - (by0 - by1) * f / fmax)
           for a, f in zip(a_fine, f_fine)]
    s += (f'<path d="{V.path(pts)}" fill="none" stroke="{V.COR}" '
          f'stroke-width="2" opacity="0.8"/>')
    for a, f in zip(alphas, forces):
        px = bx0 + (bx1 - bx0) * a / 20.0
        py = by0 - (by0 - by1) * f / fmax
        s += (f'<line x1="{px:.1f}" y1="{by0}" x2="{px:.1f}" y2="{py:.1f}" '
              f'stroke="{V.GRID}" stroke-width="1"/>')
        s += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{V.AMB}"/>'
    for a in (0.0, 20.0):
        s += D.text(bx0 + (bx1 - bx0) * a / 20.0, by0 + 19, f"{a:.0f}°",
                    V.MUT, 11, "middle")
    s += D.text(bx1, by1 - 10, "sideways force", V.MUT, 11, "end")

    f5 = abs(float(tire.fy0(math.radians(5.0), fz)))
    s += _stamp(H - 40, tire,
                f"vertical load {fz:,.0f} N = RV-1 static front corner [DERIVED "
                f"from SOURCED mass and weight distribution]")
    return s + V.foot(
        W, H,
        "A tire is not a switch that grips until it lets go. Force builds steeply, "
        f"then flattens: by 5° it is already making {100*f5/max(forces):.0f}% of "
        "everything it will ever make, and the last few percent costs another 5°. "
        "Past the top, more angle buys nothing at all.",
    )


# ---------------------------------------------------------------------------
# 2 · Why weight transfer costs grip
# ---------------------------------------------------------------------------


def load_split_figure(tire, total_n: float = 6000.0) -> str:
    """Two tires sharing a fixed total load, split three ways."""
    splits = [(3000.0, 3000.0), (4000.0, 2000.0), (5000.0, 1000.0)]
    results = []
    for hi, lo in splits:
        ph, pl = tire.peak_lateral(hi), tire.peak_lateral(lo)
        results.append((hi, lo, ph.fy_peak, pl.fy_peak, ph.fy_peak + pl.fy_peak))
    baseline = results[0][4]

    W, H = 1480, 1200
    s = V.head(
        W, H,
        "Why weight transfer costs grip",
        f"Two tires, {total_n/1000:g} kN of weight between them — that never "
        f"changes. All that changes is how the weight is shared. The shaded band "
        f"across each tire is its contact patch: more weight, more squash.",
    )

    max_force = max(r[2] for r in results)
    scale = _force_scale(max_force, 175.0)
    y0, dy = 250, 200
    lx, rx = 430, 700

    for i, (hi, lo, fh, fl, tot) in enumerate(results):
        cy = y0 + i * dy
        pct = 100 * (tot - baseline) / baseline

        s += D.text(150, cy + 5, f"{hi/1000:g} kN + {lo/1000:g} kN", V.FG, 15,
                    weight="600")
        s += D.text(150, cy + 26,
                    "shared evenly" if hi == lo else
                    f"{(hi-lo)/1000:g} kN moved across", V.MUT, 11.5)

        for cx, load, force in ((lx, lo, fl), (rx, hi, fh)):
            s += D.tire(cx, cy, 0.0, length=64, width=26,
                        load_frac=load / 5000.0, patch=V.SLATE)
            s += D.text(cx, cy + 52, f"{load/1000:g} kN", V.MUT, 11, "middle",
                        mono=True)
            s += D.arrow(cx + 16, cy, cx + 16 + force * scale, cy, V.COR, 3.0, 11)
            s += D.text(cx + 22 + force * scale, cy - 9, f"{force:,.0f} N",
                        V.MUT, 11, mono=True)

        s += D.rule(1130, cy - 30, 1400, V.GRID)
        colour = V.GRN if i == 0 else V.COR
        s += D.text(1400, cy + 2, f"{tot:,.0f} N", colour, 17, "end",
                    weight="600", mono=True)
        s += D.text(1400, cy + 24,
                    "the most this pair can make" if i == 0 else f"{pct:+.1f}%",
                    colour, 12, "end")

    sep = y0 + 3 * dy - 50
    s += D.rule(150, sep, 1400, V.GRID)

    # what makes the loads unequal in the first place
    s += D.panel_title(150, sep + 52, "Where the uneven split comes from",
                       "A car in a left turn throws its weight onto the "
                       "right-hand wheels. That is the same picture as the "
                       "bottom row above, happening to a real car.")
    ccx, ctop = 340, sep + 108
    body_w, body_h = 100, 168
    s += (f'<rect x="{ccx-body_w/2:.0f}" y="{ctop:.0f}" width="{body_w}" '
          f'height="{body_h}" rx="28" fill="none" stroke="{V.MUT}" '
          f'stroke-width="1.6"/>')
    s += D.text(ccx, ctop + body_h / 2 + 4, "car", V.MUT, 11, "middle")
    for dxw, dyw, load_frac in ((-1, 0, 0.22), (1, 0, 0.95),
                                (-1, 1, 0.24), (1, 1, 0.92)):
        wx = ccx + dxw * (body_w / 2 + 17)
        wy = ctop + 36 + dyw * 96
        s += D.tire(wx, wy, 0.0, length=48, width=19,
                    load_frac=load_frac, patch=V.SLATE)
    s += D.text(ccx - body_w / 2 - 44, ctop + 40, "inside wheels", V.MUT, 11, "end")
    s += D.text(ccx - body_w / 2 - 44, ctop + 56, "unloaded", V.TEAL, 11, "end")
    s += D.text(ccx + body_w / 2 + 44, ctop + 40, "outside wheels", V.MUT, 11)
    s += D.text(ccx + body_w / 2 + 44, ctop + 56, "squashed", V.COR, 11)
    s += D.arrow(ccx - 34, ctop + body_h + 40, ccx + 46, ctop + body_h + 40,
                 V.VIO, 2.8, 11)
    s += D.text(ccx + 58, ctop + body_h + 44, "weight moves this way in a left turn",
                V.VIO, 11.5)

    ty = ctop + 6
    s += D.text(700, ty,
                "Cornering does not remove weight from the car. It moves it.",
                V.FG, 15, weight="600")
    for i, line in enumerate([
        "And moving it is expensive, because the tire you press harder gives back",
        "less than the tire you unload gives up. That is the whole cost, and it is",
        "why a lower car corners better, why anti-roll bars change the way a car",
        "handles, and why every racing engineer cares where the weight sits.",
        "",
        "Nothing here involves the driver, the engine, or the road surface. It is",
        "a property of rubber.",
    ]):
        s += D.text(700, ty + 30 + 22 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, tire,
                "loads are illustrative round numbers [ASSUMED]; forces are the "
                "model's peak lateral force at each load")
    return s + V.foot(
        W, H,
        f"Peak lateral force per tire, evaluated at each load. "
        f"Even split {baseline:,.0f} N; "
        + "; ".join(f"{r[0]/1000:g}+{r[1]/1000:g} {100*(r[4]-baseline)/baseline:+.1f}%"
                    for r in results[1:]) + ".",
    )


# ---------------------------------------------------------------------------
# 3 · Reality check against published values
# ---------------------------------------------------------------------------


def reality_check_figure(rows) -> str:
    """Where our numbers sit against published bands.

    ``rows`` is a list of dicts with keys ``label``, ``value``, ``lo``, ``hi``,
    ``axis`` (``(min, max)``), ``unit``, ``source``, ``status``. A row with
    ``value=None`` is drawn greyed as "not measurable yet" — that is deliberate,
    because an honest validation table shows what has *not* been checked.
    """
    W, H = 1480, 180 + 74 * len(rows)
    s = V.head(
        W, H,
        "Reality check — our numbers against published values",
        "Each bar is the range the literature or the reference sheet says to "
        "expect. The dot is what this model produces. Nothing here is checked "
        "against our own code; every band comes from outside the project.",
    )

    tx, bx0, bx1 = 60, 620, 1180
    y = 150
    for r in rows:
        lo, hi = r["lo"], r["hi"]
        amin, amax = r["axis"]
        span = amax - amin

        s += D.text(tx, y + 4, r["label"], V.FG, 13.5, weight="600")
        s += D.text(tx, y + 24, r["source"], V.MUT, 10.5, style="italic")

        s += (f'<rect x="{bx0}" y="{y-11}" width="{bx1-bx0}" height="22" rx="4" '
              f'fill="{V.GRID}" opacity="0.55"/>')
        s += D.band(bx0, y - 11, bx1 - bx0, 22,
                    (lo - amin) / span, (hi - amin) / span, V.TEAL, 0.45)
        s += D.text(bx0 + (bx1 - bx0) * (lo - amin) / span, y + 30,
                    f"{lo:g}", V.MUT, 10, "middle", mono=True)
        s += D.text(bx0 + (bx1 - bx0) * (hi - amin) / span, y + 30,
                    f"{hi:g}", V.MUT, 10, "middle", mono=True)

        if r["value"] is None:
            s += D.text(bx1 + 22, y + 5, "not measurable until the car exists",
                        V.MUT, 12, style="italic")
        else:
            px = bx0 + (bx1 - bx0) * (r["value"] - amin) / span
            inside = lo <= r["value"] <= hi
            colour = V.GRN if inside else V.COR
            s += (f'<circle cx="{px:.1f}" cy="{y:.1f}" r="7" fill="{colour}" '
                  f'stroke="{V.BG}" stroke-width="2"/>')
            s += D.text(bx1 + 22, y + 5,
                        f"{r['value']:g} {r['unit']}", colour, 13.5,
                        weight="600", mono=True)
            if inside:
                s += D.text(bx1 + 22, y + 24, "inside the published range",
                            V.MUT, 10.5)
            else:
                s += D.text(bx1 + 22, y + 24, "OUTSIDE the published range",
                            colour, 10.5, weight="600")
                s += D.text(bx1 + 22, y + 39,
                            r.get("note", "unexplained — do not publish until it is"),
                            V.MUT, 10)
        y += 74

    s += _stamp(H - 40, None,
                "[SOURCED] / [DERIVED] bands as labelled per row  ·  "
                "[MEASURED] values from Sedan_Pac02Tire.tir, offsets removed, "
                "unscaled  ·  see FINDINGS.md O5 for the two bands still "
                "awaiting a citation")
    return s + V.foot(
        W, H,
        "Bands are quoted ranges, not tolerances — sitting inside one is evidence, "
        "not proof. The real external test is Episode 16, where three design "
        "points get re-run in Project Chrono and we compare trend direction.",
    )


__all__ = ["slip_angle_figure", "load_split_figure", "reality_check_figure"]
