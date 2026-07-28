"""Episode 10 figures — one driver, many cars, and a cross-check.

``morph_figure``
    The pictorial hero: the same policy's line through the corner for each car it
    was asked about, on one road, with the cars drawn at their true balance.
``crosscheck_figure``
    The point of the episode: the learned driver's lap time against balance
    beside the optimal-control solver's, each normalised to its own scale,
    because the absolute times are not comparable and never will be.
``conditioned_card``
    Training curves plus the per-design table with error bars.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V
from physics.track import CORNER_ARC as T_ARC, ENTRY_STRAIGHT as T_ENTRY


def dkey(ff) -> str:
    """The one way a design point is named. See experiments/ep10/run.py."""
    return f"{float(ff):.2f}"

RAMP = (V.TEAL, V.GRN, V.AMB, V.COR, V.VIO)


def _stamp(y: float, results, extra: str = "") -> str:
    lo, hi = results["design_range"]
    # This read "slip envelope NOT enforced" on every Episode 10 figure, copied
    # from Episode 9. Episode 10's one substantive protocol change is that it IS
    # enforced, so the provenance stamp asserted the opposite of the episode it
    # was stamping. Read it from the results rather than restating it. F68.
    pen = results.get("envelope_penalty")
    env = ("slip envelope NOT enforced" if not pen
           else f"slip envelope penalised at {pen} per step of excess")
    bits = [
        f"[MEASURED] PPO on the double-track model, "
        f"{results['total_steps']:,} steps, ONE policy",
        f"front mass fraction resampled {lo:.2f}-{hi:.2f} per episode",
        f"{results['n_eval']} rollouts per design",
        f"[ASSUMED] reward = progress; {env}",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  -  ".join(bits), V.MUT, 9.5)


def morph_figure(results, traces) -> str:
    """One policy's line through the corner, for five different cars."""
    from .line_figures import track_backdrop
    from physics.track import long_exit

    track = long_exit()
    fracs = results["eval_fractions"]
    W, H = 1480, 1060
    s = V.head(
        W, H,
        "One driver, asked about five different cars",
        "A single policy, trained once with the car's weight distribution in its "
        "observation. Nothing is retrained between these lines — the same "
        "network is simply told it is driving a different car, and drives "
        "differently.",
    )

    back, to_px, scale = track_backdrop(track, T_ENTRY - 34.0,
                                        T_ENTRY + T_ARC + 60.0,
                                        90, 720, 180, 800)
    s += back
    win_lo, win_hi = T_ENTRY - 34.0, T_ENTRY + T_ARC + 60.0
    for i, ff in enumerate(fracs):
        tag = "f" + dkey(ff).replace(".", "")
        sa = traces[f"{tag}_s"]
        n = traces[f"{tag}_n"]
        m = (sa >= win_lo) & (sa <= win_hi)
        if not m.any():
            continue
        x, y = track.to_xy(sa[m], n[m])
        px, py = to_px(x, y)
        s += (f'<path d="{V.path(list(zip(px, py)))}" fill="none" '
              f'stroke="{RAMP[i % len(RAMP)]}" stroke-width="2.6" '
              f'opacity="0.95"/>')

    ly = 210
    s += D.text(770, ly - 26, "the five cars", V.FG, 15, weight="600")
    for i, ff in enumerate(fracs):
        # Deployed, matching the traces the lines are drawn from (F61, F68).
        row = results["across_designs"][dkey(ff)]["greedy"]
        colour = RAMP[i % len(RAMP)]
        y = ly + i * 118
        s += (f'<line x1="770" y1="{y - 4}" x2="812" y2="{y - 4}" '
              f'stroke="{colour}" stroke-width="3.4"/>')
        s += D.text(824, y, f"{100*ff:.0f}% front", colour, 14, weight="600")
        # the car itself, mass dot where it actually sits
        cx = 1120
        s += D.car_plan(cx, y + 24, length=86, width=38, wheel_len=20,
                        wheel_w=9, loads=(ff, ff, 1 - ff, 1 - ff), body=V.MUT)
        com_y = y + 24 + 86 * 0.30 * (1.0 - 2.0 * ff)
        s += f'<circle cx="{cx}" cy="{com_y:.1f}" r="6" fill="{V.AMB}"/>'
        lap = row["lap_time_mean"]
        s += D.text(1200, y + 6,
                    f"{lap:.2f} +/- {row['lap_time_std']:.2f} s"
                    if np.isfinite(lap) else "no finishes",
                    V.MUT, 12.5, mono=True)
        fr = row["finish_rate"]
        s += D.text(1200, y + 26, f"finished {fr:.0%}"
                    + ("" if fr else "  — left the road"),
                    V.COR if not fr else V.MUT, 11)
        s += D.text(1200, y + 44,
                    f"worst slip {row['worst_slip_deg']:.1f} deg", V.MUT, 11)

    s += D.rule(90, 850, 1400, V.GRID)
    for i, line in enumerate([
        "Episode 9's driver could drive one car, and comparing designs with a "
        "driver that has to be retrained for each one measures the retraining "
        "as much as the car —",
        "every run lands somewhere different. Season 2's comparisons were only "
        "fair because it was the same solver every time.",
        "",
        "This policy sees the car it is in. Train once, ask about anything in "
        "the range, and the comparison is between the cars rather than between "
        "training runs.",
    ]):
        s += D.text(90, 882 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Cropped to the corner. One DEPLOYED rollout per car, same seed, mean "
        "action. Contact-patch size is static load; the dot is the "
        "centre of gravity at its true position along the wheelbase.",
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


def crosscheck_figure(results) -> str:
    """Learned driver against solved driver. Shapes, never absolute times."""
    fracs = np.array(results["eval_fractions"])
    ref = results.get("ep07_optimal_control")
    W, H = 1480, 940
    s = V.head(
        W, H,
        "Two methods that share nothing but the physics",
        "A policy that learned to drive by crashing several hundred thousand "
        "times, and a solver that computed the answer in one shot. Asked the "
        "same question about the same cars.",
    )
    s += D.text(40, 92,
                "Each curve is normalised to its own mean and spread. The "
                "absolute times are NOT comparable — different entry speed, and "
                "only one of them enforces the slip envelope. Only designs "
                "where BOTH methods gave a trustworthy answer are compared.",
                V.MUT, 11.5)

    # Plot EXACTLY the designs the correlation is computed from, with the same
    # metric. This figure used to draw the SAMPLED policy's progress rate across
    # all five designs while the reported correlation came from the DEPLOYED
    # policy's lap time across the gated three — so its own red line bottomed at
    # 40% front while the caption beside it read "fastest 54% front". Three
    # populations in one figure, none of them labelled. See FINDINGS F68.
    used = [float(f) for f in results.get("crosscheck_fractions", [])]
    excluded = results.get("crosscheck_excluded", {})
    rl = np.array([results["across_designs"][dkey(f)]["greedy"]["lap_time_mean"]
                   if float(f) in used else np.nan for f in fracs], dtype=float)
    rl_sd = np.array([results["across_designs"][dkey(f)]["greedy"]
                      .get("lap_time_std", 0.0) or 0.0 for f in fracs],
                     dtype=float)
    ok = np.isfinite(rl)

    ax = _Ax(140, 760, 170, 620, fracs.min() - 0.01, fracs.max() + 0.01,
             -2.6, 2.6)
    s += D.panel_title(140, 150, "Normalised lap time against balance")
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 4, 4)
    xt = [(f"{100*v:.0f}", float(ax.x(v))) for v in fracs]
    yt = [(f"{v:+.0f}", float(ax.y(v))) for v in (-2, -1, 0, 1, 2)]
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "front mass fraction (%)",
               "standard deviations from that method's own mean", xt, yt)
    s += (f'<line x1="{ax.L}" y1="{float(ax.y(0)):.1f}" x2="{ax.R}" '
          f'y2="{float(ax.y(0)):.1f}" stroke="{V.MUT}" stroke-width="1" '
          f'stroke-dasharray="3 5"/>')

    def _norm(v):
        v = np.asarray(v, dtype=float)
        return (v - np.nanmean(v)) / (np.nanstd(v) or 1.0)

    if ok.sum() >= 2:
        rn = _norm(rl[ok])
        s += (f'<path d="{V.path(ax.pts(fracs[ok], rn))}" fill="none" '
              f'stroke="{V.COR}" stroke-width="2.8"/>')
        # error bars, scaled into the same normalised units
        scale = 1.0 / (np.nanstd(rl[ok]) or 1.0)
        for xv, yv, e in zip(fracs[ok], rn, rl_sd[ok] * scale):
            X = float(ax.x(xv))
            s += (f'<line x1="{X:.1f}" y1="{float(ax.y(yv - e)):.1f}" '
                  f'x2="{X:.1f}" y2="{float(ax.y(yv + e)):.1f}" '
                  f'stroke="{V.COR}" stroke-width="1.6" opacity="0.8"/>')
            s += (f'<circle cx="{X:.1f}" cy="{float(ax.y(yv)):.1f}" r="4" '
                  f'fill="{V.COR}"/>')
    if ref:
        # Restricted to `used` as well, and normalised over the same subset —
        # otherwise the two curves are standardised against different populations
        # and their vertical positions are not comparable even though the panel
        # invites exactly that comparison.
        oc = np.array([ref[dkey(f)]["time_s"]
                       if (dkey(f) in ref and float(f) in used) else np.nan
                       for f in fracs], dtype=float)
        m = np.isfinite(oc)
        on = _norm(oc[m])
        s += (f'<path d="{V.path(ax.pts(fracs[m], on))}" fill="none" '
              f'stroke="{V.TEAL}" stroke-width="2.8" stroke-dasharray="8 6"/>')
        for xv, yv, f in zip(fracs[m], on, fracs[m]):
            conv = ref[dkey(f)].get("converged", True)
            X, Y = float(ax.x(xv)), float(ax.y(yv))
            s += (f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="4" '
                  f'fill="{V.TEAL if conv else V.BG}" stroke="{V.TEAL}" '
                  f'stroke-width="1.6"/>')

    # The gate, drawn. An excluded design that simply vanishes from the panel
    # reads as a design that was never tested.
    for f in fracs:
        why = excluded.get(dkey(f))
        if not why:
            continue
        X = float(ax.x(f))
        s += (f'<rect x="{X-26:.1f}" y="{ax.T}" width="52" '
              f'height="{ax.B-ax.T}" fill="{V.MUT}" opacity="0.07"/>')
        for dx, dy in ((-1, -1), (-1, 1)):
            s += (f'<line x1="{X + dx*8:.1f}" y1="{float(ax.y(0)) + dy*8:.1f}" '
                  f'x2="{X - dx*8:.1f}" y2="{float(ax.y(0)) - dy*8:.1f}" '
                  f'stroke="{V.MUT}" stroke-width="2.4"/>')
        s += D.text(X, ax.T - 8, "excluded", V.MUT, 10, "middle", weight="600")
        short = ("policy cannot drive it" if "does not drive" in why
                 else "solve did not converge")
        s += D.text(X, ax.B + 34, short, V.MUT, 9.5, "middle")

    s += (f'<line x1="810" y1="196" x2="852" y2="196" stroke="{V.COR}" '
          f'stroke-width="3"/>')
    s += D.text(864, 201, "the learned driver", V.COR, 13.5, weight="600")
    s += D.text(864, 221, f"PPO, {results['total_steps']:,} steps, "
                f"{results['n_eval']} rollouts per car", V.MUT, 11)
    s += D.text(864, 237, "deployed lap time; bars are one s.d. over "
                "jittered rollouts", V.MUT, 11)
    s += (f'<line x1="810" y1="276" x2="852" y2="276" stroke="{V.TEAL}" '
          f'stroke-width="3" stroke-dasharray="8 6"/>')
    s += D.text(864, 281, "the solver", V.TEAL, 13.5, weight="600")
    s += D.text(864, 301, "Episode 7, minimum-time collocation", V.MUT, 11)
    s += D.text(864, 317, "unconverged solves are excluded, not drawn hollow",
                V.MUT, 11)

    corr = results.get("shape_correlation")
    y = 370
    if corr is not None:
        s += D.text(810, y, f"shape correlation {corr:+.2f}", V.FG, 20,
                    weight="600", mono=True)
        s += D.text(810, y + 24,
                    "between the two normalised curves", V.MUT, 11.5)
        s += D.text(810, y + 56,
                    f"spread across balance:", V.MUT, 11.5)
        s += D.text(810, y + 76,
                    f"learned  {results['rl_spread_s']:.3f} s", V.COR, 12,
                    mono=True)
        s += D.text(810, y + 94,
                    f"solved   {results['oc_spread_s']:.3f} s", V.TEAL, 12,
                    mono=True)
        s += D.text(810, y + 124,
                    f"fastest balance:", V.MUT, 11.5)
        s += D.text(810, y + 144,
                    f"learned  {100*results['rl_best_fraction']:.0f}% front",
                    V.COR, 12, mono=True)
        s += D.text(810, y + 162,
                    f"solved   {100*results['oc_best_fraction']:.0f}% front",
                    V.TEAL, 12, mono=True)

    s += D.rule(140, 668, 1400, V.GRID)
    for i, line in enumerate([
        "This is the strongest check available in this project, and it is worth "
        "being precise about what it does and does not show.",
        "",
        "What is shared: the tire file, the four-wheel model, the corner. What is "
        "not: everything else. One method searches a continuous optimisation "
        "problem with exact",
        "gradients and perfect foresight; the other stumbles into a policy by "
        "trial and error and cannot see past the next two seconds of road.",
        "",
        "If both say the same thing about how balance affects lap time, that is "
        "hard to explain by a shared bug, because there is almost no shared code "
        "to hold one.",
        "If they disagree, one of them is wrong and the disagreement says where "
        "to look. Either outcome is worth more than another run of the same "
        "method.",
    ]):
        s += D.text(140, 700 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results, "absolute times NOT comparable — rule 6")
    return s + V.foot(
        W, H,
        "Normalisation is to each method's own mean and standard deviation "
        "across the COMPARED designs, so only the shape is being compared. Raw times "
        "are in results.json for both.",
    )


def conditioned_card(results, history) -> str:
    steps = np.array([h["steps"] for h in history])
    fracs = results["eval_fractions"]
    W, H = 1520, 760
    s = V.head(
        W, H,
        "Episode 10 - one policy across the design range",
        "Training curves for the conditioned policy, and what it does on each "
        "car it was asked about.",
    )
    for key, ylab, title, L, R, floor in (
            ("distance_mean", "distance (m)", "A - Learning", 100, 400, None),
            ("approx_kl", "approximate KL", "B - Policy updating", 540, 840, 1e-4),
            ("explained_variance", "explained variance", "C - Critic",
             980, 1280, 0.3)):
        vals = np.array([h[key] for h in history])
        lo, hi = float(np.min(vals)), float(np.max(vals))
        if floor is not None:
            lo, hi = min(lo, floor * 0.5), max(hi, floor * 1.5)
        pad = 0.08 * (hi - lo or 1.0)
        ax = _Ax(L, R, 150, 440, 0, float(steps[-1]), lo - pad, hi + pad)
        s += D.panel_title(L, 132, title)
        s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 4, 4)
        xt = [(f"{v/1e6:.1f}M", float(ax.x(v)))
              for v in np.linspace(0, steps[-1], 4)]
        yt = [(f"{v:.3g}", float(ax.y(v)))
              for v in np.linspace(lo - pad, hi + pad, 4)]
        s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "environment steps", ylab, xt, yt)
        s += (f'<path d="{V.path(ax.pts(steps, vals))}" fill="none" '
              f'stroke="{V.TEAL}" stroke-width="2"/>')
        if floor is not None:
            s += (f'<line x1="{ax.L}" y1="{float(ax.y(floor)):.1f}" x2="{ax.R}" '
                  f'y2="{float(ax.y(floor)):.1f}" stroke="{V.COR}" '
                  f'stroke-width="1.6" stroke-dasharray="6 5"/>')
            s += D.text(ax.L + 8, float(ax.y(floor)) - 7,
                        f"D6 floor {floor:g}", V.COR, 10)

    ly = 500
    rows = [("front mass", "lap time", "finished", "distance", "worst slip")]
    for ff in fracs:
        r = results["across_designs"][dkey(ff)]["stochastic"]
        lap = (f"{r['lap_time_mean']:.2f} +/- {r['lap_time_std']:.2f} s"
               if np.isfinite(r["lap_time_mean"]) else "—")
        rows.append((f"{100*ff:.0f}%", lap, f"{r['finish_rate']:.0%}",
                     f"{r['distance_mean']:.0f} +/- {r['distance_std']:.0f} m",
                     f"{r['worst_slip_deg']:.1f} deg"))
    for ri, row in enumerate(rows):
        for ci, cell in enumerate(row):
            s += D.text(100 + ci * 250, ly + ri * 22, cell,
                        V.FG if ri == 0 or ci == 0 else V.MUT, 12,
                        weight="600" if ri == 0 else "normal",
                        mono=(ri > 0 and ci > 0))
    s += D.text(100, ly + 22 * len(rows) + 18,
                f"D6: {'PASSED' if results['d6_passed'] else 'FAILED'}"
                + ("" if results["d6_passed"] else
                   " — " + ", ".join(results["d6_failures"])),
                V.GRN if results["d6_passed"] else V.COR, 12.5, weight="600")
    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Every figure is one seed of training, evaluated over "
        f"{results['n_eval']} rollouts per design. The spread quoted is across "
        "rollouts, not across training seeds.",
    )


__all__ = ["morph_figure", "crosscheck_figure", "conditioned_card",
           "line_family_figure"]


def line_family_figure(runs, results) -> str:
    """Five lines, one road, no cars. The comparison Episode 10 is actually for.

    Drawing a car at intervals is right for judging whether ONE rollout is
    sensible — body versus travel direction, slip colour. It is wrong for
    comparing five rollouts, because fifteen car outlines on nearly the same arc
    obscure the thing being compared. Here the cars come off and the lines stay.

    Three views of the same five rollouts, because the curved track hides
    precision and the unrolled plot hides intuition:

    * **A** — the road from above, lines overlaid
    * **B** — lateral position against distance, which resolves centimetres
    * **C** — speed against distance

    ``runs``: dict of front-mass-fraction -> rollout dict.
    """
    from .line_figures import track_backdrop
    from physics.track import long_exit

    track = long_exit()
    fr = sorted(runs)
    W, H = 1520, 1120
    s = V.head(
        W, H,
        "One driver, five cars, five different lines",
        "The same policy driving five weight distributions. Nothing retrained — "
        "it is told which car it is in. The lines it chooses are up to 4.5 m "
        "apart on an 8 m road.",
    )

    # ---- A: the road, lines only -----------------------------------------
    s_lo, s_hi = T_ENTRY - 25.0, T_ENTRY + T_ARC + 30.0
    back, to_px, scale = track_backdrop(track, s_lo, s_hi, 70, 560, 190, 730)
    s += D.panel_title(70, 168, "A · The corner from above")
    s += back
    for i, ff in enumerate(fr):
        r = runs[ff]
        m = (r["s"] >= s_lo) & (r["s"] <= s_hi)
        x, y = track.to_xy(r["s"][m], r["n"][m])
        px, py = to_px(x, y)
        s += (f'<path d="{V.path(list(zip(px, py)))}" fill="none" '
              f'stroke="{RAMP[i % len(RAMP)]}" stroke-width="2.8"/>')
        if not r["finished"]:
            s += (f'<circle cx="{px[-1]:.1f}" cy="{py[-1]:.1f}" r="7" '
                  f'fill="none" stroke="{RAMP[i % len(RAMP)]}" '
                  f'stroke-width="2.4"/>')
            s += D.text(float(px[-1]) + 12, float(py[-1]) + 4, "off",
                        RAMP[i % len(RAMP)], 10.5, weight="600")

    # ---- B: unrolled lateral position ------------------------------------
    hw = track.half_width
    ax = _Ax(690, 1440, 190, 470, s_lo, s_hi, -hw - 0.3, hw + 0.3)
    s += D.panel_title(690, 168, "B · Where on the road",
                       "positive is toward the inside of the corner")
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 5, 4)
    xt = [(f"{v:.0f}", float(ax.x(v))) for v in (50, 70, 100, 133, 160)]
    yt = [(f"{v:+.0f}", float(ax.y(v))) for v in (-4, -2, 0, 2, 4)]
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "distance along the track (m)",
               "offset from centreline (m)", xt, yt)
    for edge in (-hw, hw):
        s += (f'<line x1="{ax.L}" y1="{float(ax.y(edge)):.1f}" x2="{ax.R}" '
              f'y2="{float(ax.y(edge)):.1f}" stroke="{V.COR}" '
              f'stroke-width="1.4" stroke-dasharray="6 5" opacity="0.7"/>')
    s += D.text(ax.R - 4, float(ax.y(hw)) - 6, "inside edge of the road",
                V.COR, 10, "end")
    s += (f'<rect x="{float(ax.x(T_ENTRY)):.1f}" y="{ax.T}" '
          f'width="{float(ax.x(T_ENTRY + T_ARC) - ax.x(T_ENTRY)):.1f}" '
          f'height="{ax.B - ax.T}" fill="{V.AMB}" opacity="0.08"/>')
    s += D.text(float(ax.x(T_ENTRY + 0.5 * T_ARC)), ax.T + 16, "the corner",
                V.AMB, 10, "middle")
    for i, ff in enumerate(fr):
        r = runs[ff]
        m = (r["s"] >= s_lo) & (r["s"] <= s_hi)
        s += (f'<path d="{V.path(ax.pts(r["s"][m], r["n"][m]))}" fill="none" '
              f'stroke="{RAMP[i % len(RAMP)]}" stroke-width="2.2"/>')

    # ---- C: speed --------------------------------------------------------
    v_all = np.concatenate([runs[f]["speed"] for f in fr])
    ax2 = _Ax(690, 1440, 560, 810, s_lo, s_hi,
              float(v_all.min()) - 0.5, float(v_all.max()) + 0.5)
    s += D.panel_title(690, 538, "C · Speed")
    s = V.grid(s, ax2.L, ax2.R, ax2.T, ax2.B, 5, 4)
    xt2 = [(f"{v:.0f}", float(ax2.x(v))) for v in (50, 70, 100, 133, 160)]
    yt2 = [(f"{v:.0f}", float(ax2.y(v))) for v in
           np.linspace(float(v_all.min()), float(v_all.max()), 4)]
    s = V.axes(s, ax2.L, ax2.R, ax2.T, ax2.B, "distance along the track (m)",
               "speed (m/s)", xt2, yt2)
    s += (f'<rect x="{float(ax2.x(T_ENTRY)):.1f}" y="{ax2.T}" '
          f'width="{float(ax2.x(T_ENTRY + T_ARC) - ax2.x(T_ENTRY)):.1f}" '
          f'height="{ax2.B - ax2.T}" fill="{V.AMB}" opacity="0.08"/>')
    for i, ff in enumerate(fr):
        r = runs[ff]
        m = (r["s"] >= s_lo) & (r["s"] <= s_hi)
        s += (f'<path d="{V.path(ax2.pts(r["s"][m], r["speed"][m]))}" '
              f'fill="none" stroke="{RAMP[i % len(RAMP)]}" stroke-width="2.2"/>')

    # ---- legend + the monotone table -------------------------------------
    ly = 790
    for i, ff in enumerate(fr):
        r = runs[ff]
        inc = (r["s"] >= T_ENTRY) & (r["s"] <= T_ENTRY + T_ARC)
        y = ly + i * 22
        s += (f'<line x1="70" y1="{y - 4}" x2="112" y2="{y - 4}" '
              f'stroke="{RAMP[i % len(RAMP)]}" stroke-width="3.4"/>')
        s += D.text(124, y, f"{100*ff:.0f}% front", RAMP[i % len(RAMP)], 12.5,
                    weight="600")
        s += D.text(250, y, f"apex {float(r['n'][inc].max()):+.2f} m", V.MUT,
                    12, mono=True)
        s += D.text(400, y, f"slowest {float(r['speed'][inc].min()):.2f} m/s",
                    V.MUT, 12, mono=True)
        s += D.text(580, y,
                    "completed" if r["finished"]
                    else f"off at {float(r['s'][-1]):.0f} m",
                    V.TEAL if r["finished"] else V.COR, 12, mono=True)

    s += D.rule(70, 908, 1440, V.GRID)
    n_apex = [float(runs[f]["n"][(runs[f]["s"] >= T_ENTRY)
              & (runs[f]["s"] <= T_ENTRY + T_ARC)].max()) for f in fr]
    for i, line in enumerate([
        f"Both columns above are monotone in weight distribution. Move mass "
        f"forward and the driver takes a TIGHTER line — apex "
        f"{n_apex[0]:+.2f} m at {100*fr[0]:.0f}% front against "
        f"{n_apex[-1]:+.2f} m at {100*fr[-1]:.0f}% — and carries LESS speed "
        f"through the corner.",
        "",
        "That is a bigger change than anything Season 2 found. The "
        "optimal-control solver's apex moved barely a percentage point across "
        "this same range of cars (Episode 7); this driver's line moves "
        f"{n_apex[-1]-n_apex[0]:.1f} m.",
        "",
        "The solver re-optimises everything for each car and lands on almost the "
        "same line every time. This driver has one set of learned reflexes and "
        "applies them to whatever car it is given,",
        "so the car's behaviour shows up in the LINE rather than being absorbed "
        "by the plan. Which of those is the real racing line depends entirely on "
        "who is driving.",
    ]):
        s += D.text(70, 940 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results, "deployed policy — mean action, no exploration "
                "noise; one rollout per car, same seed")
    return s + V.foot(
        W, H,
        "Cars are deliberately not drawn: fifteen outlines on nearly the same "
        "arc hide the comparison. Panel A is for intuition, panel B resolves "
        "the centimetres.",
    )
