"""Episode 14 figures.

``pilot_sanity_figure``
    ONE figure for the pilot phase: realized yaw moment against distance for
    whichever of C (Episode 13, if present), H and E trained, plus each
    variant's D6 status. Enough to look at by eye before committing to a
    production run (rule: every figure gets looked at, F68's lesson) — not a
    pictorial/technical pair. Those come once there is a real result to draw,
    per the approved plan for this episode.
"""

from __future__ import annotations

import numpy as np

from . import diagram as D
from . import lib as V

COLOUR = {"C": V.SLATE, "H": V.TEAL, "E": V.COR}
LABEL = {"C": "classical (Ep 13)", "H": "variant H — RL Mz + allocator",
         "E": "variant E — end-to-end"}


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


def pilot_sanity_figure(results) -> str:
    W, H = 1480, 760
    pilot = results.get("pilot", True)
    s = V.head(
        W, H,
        f"Episode 14 pilot — is the pipeline producing anything sane?",
        "Realized yaw moment against distance, computed downstream from each "
        "trajectory's own logged per-wheel forces (rule 7) — the same physics "
        "regardless of which controller chose them. NOT a result: "
        + ("this is the pilot pass." if pilot else "this is a production run."),
    )

    series = {}
    if "classical_c" in results:
        c = results["classical_c"]
        series["C"] = (np.asarray(c["s"]), np.asarray(c["mz_demand"]))
    for v in ("H", "E"):
        info = results.get("variants", {}).get(v)
        if info and "s" in info:
            series[v] = (np.asarray(info["s"]), np.asarray(info["mz"]))

    ax_lo = 100.0
    all_y = []
    for arr in series.values():
        all_y.extend(arr[1].tolist())
    if not all_y:
        all_y = [0.0, 1.0]
    y0, y1 = min(all_y) - 200, max(all_y) + 200

    ax = _Ax(100, 1380, 160, 480, 0.0, 400.0, y0, y1)
    s += D.panel_title(100, 140, "Yaw moment along the road")
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 6, 4)
    xt = [(f"{v:.0f}", float(ax.x(v))) for v in range(0, 401, 50)]
    yt = [(f"{v:+.0f}", float(ax.y(v))) for v in np.linspace(y0, y1, 5)]
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "distance along the road (m)",
              "yaw moment (N.m)", xt, yt)
    s += (f'<line x1="{ax.L}" y1="{float(ax.y(0.0)):.1f}" x2="{ax.R}" '
          f'y2="{float(ax.y(0.0)):.1f}" stroke="{V.FG}" stroke-width="1" '
          f'stroke-dasharray="5 5" opacity="0.5"/>')

    ly = 540
    for i, (key, (sa, mz)) in enumerate(series.items()):
        s += (f'<path d="{V.path(ax.pts(sa, mz))}" fill="none" '
              f'stroke="{COLOUR[key]}" stroke-width="2.4"/>')
        y = ly + i * 22
        s += (f'<line x1="100" y1="{y-4}" x2="140" y2="{y-4}" '
              f'stroke="{COLOUR[key]}" stroke-width="3"/>')
        s += D.text(150, y, LABEL[key], COLOUR[key], 13)

    # Per-variant status block: D6, saturation, whether it finished at all.
    ty = 540
    tx = 780
    s += D.panel_title(tx, 522, "Did each variant learn anything at all?")
    for v in ("H", "E"):
        info = results.get("variants", {}).get(v)
        y = ty + (0 if v == "H" else 100)
        if info is None:
            s += D.text(tx, y, f"variant {v}: not yet run", V.MUT, 13)
            continue
        d6 = "PASSED" if info["d6_passed"] else f"FAILED ({len(info['d6_failures'])})"
        colour = V.TEAL if info["d6_passed"] else V.COR
        s += D.text(tx, y, f"variant {v} — D6 {d6}", colour, 14, weight="600")
        s += D.text(tx, y + 20,
                    f"finished={info['finished']}  distance={info['distance_m']:.0f} m  "
                    f"peak {info['peak_a_y_g']:.2f} g  util {info['mean_utilisation']:.2f}",
                    V.MUT, 12, mono=True)
        if info.get("wall_s"):
            s += D.text(tx, y + 40, f"trained in {info['wall_s']:.0f} s", V.MUT, 12)
        if not info["d6_passed"]:
            s += D.text(tx, y + 60,
                        ", ".join(info["d6_failures"]), V.COR, 11)

    s += D.rule(60, 590, W - 120, V.GRID)
    for i, line in enumerate(D_wrap(
            "Pilot run: this checks whether the infrastructure produces a "
            "sane trajectory and a D6 verdict for each variant, not whether "
            "either variant has learned something worth reporting. A pilot "
            "policy that has not converged is expected to fail D6 and to "
            "produce a noisy or flat Mz trace — that is what a short run "
            "looks like, not evidence about the research question.", 148)):
        s += D.text(60, 624 + 20 * i, line, V.MUT, 12)

    s += D.text(40, H - 24,
               "[MEASURED] realized Mz from logged per-wheel forces via "
               "DoubleTrackBackend.yaw_moment  ·  RUNG 2, PILOT — not a "
               "result (rule 15)", V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "Classical C's line (if present) is Episode 13's DEMANDED moment, not "
        "realized — H and E have no separate demand for E, so all three are "
        "shown as what the wheels actually did.",
    )


def D_wrap(text: str, width: int) -> list[str]:
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


__all__ = ["pilot_sanity_figure"]
