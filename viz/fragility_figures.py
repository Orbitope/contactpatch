"""Episode 11 figures — speed against fragility.

``fragility_paths``
    The pictorial hero, and the one that carries the episode: one small road per
    design, with every perturbed lap drawn on it. A fragile car is not a number
    here, it is a fan of lines that stops going round the corner. Nobody needs to
    know what a slip angle is to read it.
``pareto_figure``
    The technical version: advertised pace against what a bad day costs.
``condition_card``
    Which perturbation did what, so each one's contribution is attributable.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V
from physics.track import CORNER_ARC as T_ARC, ENTRY_STRAIGHT as T_ENTRY


def dkey(ff) -> str:
    """The one way a design point is named. See experiments/ep11/run.py."""
    return f"{float(ff):.2f}"


RAMP = (V.TEAL, V.GRN, V.AMB, V.COR, V.VIO)
#: The window every panel uses. Fixed on the corner and the corrections just after
#: it, never widened to fit a lap that happened to finish — a crop that adapts to
#: the data frames failures tightly and successes loosely and makes the failures
#: look worse than they are.
S_LO, S_HI = T_ENTRY - 25.0, T_ENTRY + T_ARC + 30.0


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


def _wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap. SVG text does not wrap itself and long strings silently
    run off the canvas edge."""
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


def _stamp(y: float, results) -> str:
    return D.text(40, y, "  -  ".join([
        f"[MEASURED] Episode 10's policy ({results['policy']}), DEPLOYED, "
        f"nothing retrained",
        f"{results.get('n_trials_headline', results['n_trials'])} rollouts per "
        f"design (headline rates); {results['n_trials']} for the condition grid",
        f"[ASSUMED] steering noise sigma {results['steer_noise']}, "
        f"grip +/-{results['grip_spread']:.0%} per lap",
        f"slip envelope penalised at {results['envelope_penalty']}",
    ]), V.MUT, 9.5)


def fragility_paths(results, traces) -> str:
    """One road per design, every perturbed lap drawn on it."""
    from .line_figures import track_backdrop
    from physics.track import long_exit

    track = long_exit()
    fracs = results["fractions"]
    cond = "both"
    W, H = 1560, 1000
    s = V.head(
        W, H,
        "What a fragile car looks like",
        "The same driver, the same corner, the same disturbance — five cars that "
        "differ only in where their weight sits. Each panel shows eight laps with "
        "steering noise and a grip surface that changes lap to lap.",
    )

    cols, panW = len(fracs), 288
    for i, ff in enumerate(fracs):
        L = 40 + i * panW
        cell = results["cells"][f"{cond}|{dkey(ff)}"]
        back, to_px, _ = track_backdrop(track, S_LO, S_HI,
                                        L + 14, L + panW - 26, 210, 700)
        s += D.text(L + 14, 150, f"{100*ff:.0f}% front", RAMP[i % len(RAMP)],
                    16, weight="600")
        # An all-laps-discarded cell has no in-fit rate. Say that, rather than
        # letting a NaN format itself onto the page as "nan%".
        # A design the policy cannot drive UNDISTURBED has no fragility to report,
        # and quoting it a disturbed failure rate is worse than useless: the in-fit
        # filter discards most of its laps, so the 40%-front car came out at "65%
        # of laps left the road" -- which reads as BETTER than the 100% it fails
        # with no disturbance at all. Say what is actually wrong with it.
        nom = results["cells"][f"nominal|{dkey(ff)}"]["failure_rate"]
        fr = cell["failure_rate_inside_fit"]
        if nom >= 0.5:
            s += D.text(L + 14, 172, f"undriveable: fails {nom:.0%} of laps",
                        V.COR, 12, weight="600")
            s += D.text(L + 14, 190, "with no disturbance at all", V.MUT, 11)
        elif not np.isfinite(fr):
            s += D.text(L + 14, 172, "no lap stayed inside the tire fit",
                        V.MUT, 12, weight="600")
        else:
            s += D.text(L + 14, 172,
                        "every lap completed" if fr == 0
                        else f"{fr:.0%} of laps left the road",
                        V.TEAL if fr == 0 else V.COR, 12, weight="600")
        s += back
        for k in range(8):
            tag = f"{cond}_{dkey(ff).replace('.', '')}_{k}"
            if f"{tag}_s" not in traces:
                continue
            sa, nn = traces[f"{tag}_s"], traces[f"{tag}_n"]
            fin = bool(traces[f"{tag}_finished"][0])
            m = (sa >= S_LO) & (sa <= S_HI)
            if not m.any():
                continue
            x, y = track.to_xy(sa[m], nn[m])
            px, py = to_px(x, y)
            # A lap that went off is drawn in the alarm colour and ends in a
            # cross. Same-coloured lines with different endings are unreadable at
            # this size, and "it stopped early" is the entire finding.
            s += (f'<path d="{V.path(list(zip(px, py)))}" fill="none" '
                  f'stroke="{RAMP[i % len(RAMP)] if fin else V.COR}" '
                  f'stroke-width="{1.7 if fin else 2.4}" '
                  f'opacity="{0.75 if fin else 1.0}"/>')
            if not fin:
                ex, ey = float(px[-1]), float(py[-1])
                for dx, dy in ((-1, -1), (-1, 1)):
                    s += (f'<line x1="{ex+dx*7:.1f}" y1="{ey+dy*7:.1f}" '
                          f'x2="{ex-dx*7:.1f}" y2="{ey-dy*7:.1f}" '
                          f'stroke="{V.COR}" stroke-width="2.6"/>')

    # the read-off row: pace against consequence, in words
    s += D.rule(40, 748, W - 80, V.GRID)
    y0 = 782
    s += D.text(40, y0, "Read it left to right:", V.FG, 13.5, weight="600")
    for i, ff in enumerate(fracs):
        k = dkey(ff)
        L = 40 + i * panW
        lap = results["speed_nominal_s"].get(k, float("nan"))
        s += D.text(L + 14, y0 + 28,
                    f"{lap:.2f} s clean" if np.isfinite(lap)
                    else "no clean lap", V.MUT, 12, mono=True)
        fi = results["failure_rate_inside_fit_both"][k]
        nom = results["cells"][f"nominal|{k}"]["failure_rate"]
        s += D.text(L + 14, y0 + 48,
                    "n/a — undriveable" if nom >= 0.5
                    else (f"{fi:.0%} fail dirty" if np.isfinite(fi)
                          else "not measurable"),
                    V.MUT, 12, mono=True)
        sp = results["lap_spread_perturbed_s"].get(k, float("nan"))
        s += D.text(L + 14, y0 + 68,
                    f"+/-{sp:.2f} s when it does" if np.isfinite(sp) else "--",
                    V.MUT, 12, mono=True)

    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Cropped identically on every panel, to the corner and the corrections "
        "just after it. Coloured lines completed the lap; red lines left the road "
        "and the cross is where. The cars are not drawn because eight nearly "
        "coincident outlines hide the very thing being compared.",
    )


def pareto_figure(results) -> str:
    """Advertised pace against what a bad day costs."""
    fracs = results["fractions"]
    W, H = 1480, 940
    s = V.head(
        W, H,
        "The fastest setup is the one that crashes",
        "Horizontal: how quick the car is when nothing goes wrong — the number a "
        "setup sheet would quote. Vertical: how often it fails to get round once "
        "the driver's hands shake and the grip is not what was expected.",
    )

    laps = [results["speed_nominal_s"][dkey(f)] for f in fracs]
    fails = [results["failure_rate_perturbed"][dkey(f)] for f in fracs]
    fin = [np.isfinite(l) for l in laps]
    good = [l for l, f in zip(laps, fin) if f]
    lo = min(good) - 0.15 if good else 0.0
    hi = max(good) + 0.15 if good else 1.0

    s += D.text(40, 92, "Failure rate counts only laps that never left the tire "
                "model's fitted region — rule 4 applied per lap.", V.MUT, 11.5)
    ax = _Ax(150, 800, 216, 640, lo, hi, -0.05, 1.05)
    s += D.panel_title(150, 194, "Clean pace against dirty-day failure rate")
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 4, 4)
    xt = [(f"{v:.1f}", float(ax.x(v)))
          for v in np.linspace(lo, hi, 4)]
    yt = [(f"{100*v:.0f}%", float(ax.y(v))) for v in (0.0, 0.25, 0.5, 0.75, 1.0)]
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B,
               "lap time with no perturbation (s)",
               "laps that left the road, perturbed", xt, yt)
    # Corner annotations sit in the corners they name, right-aligned away from the
    # data and from each other. Placed at ax.L they collided with both the
    # "no clean lap" note and the 54%-front point label.
    s += D.text(ax.L + 8, ax.T + 18, "fast, and loses laps", V.COR, 11)
    s += D.text(ax.L + 8, ax.B - 12, "slower, and keeps them", V.TEAL, 11)

    unplaced: list[tuple[float, str, float]] = []
    for i, ff in enumerate(fracs):
        k = dkey(ff)
        # In-fit rate: the quotable one. Plotting the all-laps rate would put
        # crashes that happened at 20 deg of slip on a chart about cars.
        lap = results["speed_nominal_s"][k]
        fr = results["failure_rate_inside_fit_both"][k]
        colour = RAMP[i % len(RAMP)]
        cell = results["cells"][f"both|{k}"]
        clo, chi = cell["finish_rate_ci95"]
        if not (np.isfinite(lap) and np.isfinite(fr)):
            # No clean lap at all: it has no horizontal position, and inventing
            # one would put a fabricated number on the axis. Say so instead.
            # No unperturbed lap means no horizontal position; inventing one
            # would put a fabricated number on the axis. Noted in the side
            # column, where it cannot collide with the plotted labels.
            unplaced.append((ff, colour, fr))
            continue
        X, Y = float(ax.x(lap)), float(ax.y(fr))
        # 95% Wilson interval on the failure rate: 1 - the finish-rate interval.
        s += (f'<line x1="{X:.1f}" y1="{float(ax.y(1.0-chi)):.1f}" '
              f'x2="{X:.1f}" y2="{float(ax.y(1.0-clo)):.1f}" '
              f'stroke="{colour}" stroke-width="1.8" opacity="0.75"/>')
        s += f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="7" fill="{colour}"/>'
        s += D.text(X + 14, Y + 5, f"{100*ff:.0f}% front", colour, 12.5,
                    weight="600")

    ly = 210
    s += D.text(840, ly - 30, "what each design is betting on", V.FG, 15,
                weight="600")
    for j, (ff, colour, fr) in enumerate(unplaced):
        # In the side column, not under the axes: at y=660 this landed on top of
        # the x tick labels and the axis title.
        yy = 560 + j * 60
        s += D.text(840, yy, f"{100*ff:.0f}% front is not on this chart.",
                    colour, 12.5, weight="600")
        # `fr` is the in-fit rate and can be NaN when every lap in the cell was
        # discarded. Fall back to the reason it is off the chart, which is the
        # unperturbed failure — never to a formatted NaN.
        nom = results["cells"][f"nominal|{dkey(ff)}"]["failure_rate"]
        for li, line in enumerate(_wrap(
                f"No unperturbed lap time to plot against: it fails {nom:.0%} of "
                f"laps before any disturbance at all.", 46)):
            s += D.text(840, yy + 20 + 18 * li, line, V.MUT, 11.5)
    order = results["ranked_fastest_first"]
    for i, k in enumerate(order):
        y = ly + i * 76
        fr = results["failure_rate_inside_fit_both"][k]
        sp = results["lap_spread_perturbed_s"][k]
        if not np.isfinite(fr):
            s += D.text(840, y, f"{100*float(k):.0f}% front", V.MUT, 13.5,
                        weight="600")
            s += D.text(840, y + 20, "no in-fit laps to score", V.MUT, 12,
                        mono=True)
            continue
        s += D.text(840, y, f"{100*float(k):.0f}% front", V.FG, 13.5,
                    weight="600")
        s += D.text(840, y + 20,
                    f"{results['speed_nominal_s'][k]:5.2f} s clean, "
                    f"{fr:.0%} of dirty laps lost", V.MUT, 12, mono=True)
        s += D.text(840, y + 38,
                    f"and {sp:.2f} s of scatter on the ones it keeps"
                    if np.isfinite(sp) else "and no laps kept", V.MUT, 12,
                    mono=True)

    s += D.rule(150, 700, W - 300, V.GRID)
    for i, line in enumerate([
        "Optimal control could not have produced this chart. A minimum-time "
        "solver knows the grip and sees the whole road, so lower grip returns a new "
        "plan rather than a crash —",
        "fragility only exists for a driver that has to react to something it did "
        "not expect. Every point here is the same policy, nothing retrained, so the "
        "differences are the cars.",
        "",
        "The rates are LOWER BOUNDS wherever a discarded lap both failed and left "
        "the fitted region: those are real crashes we cannot attribute to the car "
        "rather than to our",
        "extrapolation, so they are dropped rather than counted. The ordering is "
        "robust to that; the magnitudes are floors. See FINDINGS F70.",
    ]):
        s += D.text(150, 732 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Bars are 95% Wilson intervals — the normal approximation is worst near "
        "0% and 100%, which is where this lives. Rule 4 is applied per lap: laps "
        "that exceeded 12 degrees of slip are discarded individually, not by "
        "condition. Absolute times are not comparable with Seasons 1-2 (rule 6).",
    )


def condition_card(results) -> str:
    """Which perturbation did what — so each contribution is attributable."""
    fracs = results["fractions"]
    conds = results["conditions"]
    W, H = 1480, 820
    s = V.head(
        W, H,
        "Which disturbance did the damage",
        "Steering noise and grip variation applied separately, then together. "
        "Applying only the combination would have shown fragility without saying "
        "what the car was actually sensitive to.",
    )

    x0, colw, y0, rowh = 300, 210, 210, 92
    for j, ff in enumerate(fracs):
        s += D.text(x0 + j * colw + 60, y0 - 26, f"{100*ff:.0f}%",
                    RAMP[j % len(RAMP)], 14, weight="600", anchor="middle")
    s += D.text(x0 + 2.5 * colw, y0 - 52, "front mass fraction", V.MUT, 11.5,
                anchor="middle")

    for i, c in enumerate(conds):
        y = y0 + i * rowh
        s += D.text(40, y, c["name"], V.FG, 14, weight="600")
        s += D.text(40, y + 20, c["description"], V.MUT, 11)
        for j, ff in enumerate(fracs):
            cell = results["cells"][f"{c['name']}|{dkey(ff)}"]
            fr, X = cell["finish_rate"], x0 + j * colw + 60
            # A bar, because five numbers in a row is a table and the point here
            # is the shape down each column.
            wbar = 132
            s += (f'<rect x="{X-wbar/2:.1f}" y="{y-14:.1f}" width="{wbar}" '
                  f'height="18" fill="{V.GRID}" opacity="0.5"/>')
            s += (f'<rect x="{X-wbar/2:.1f}" y="{y-14:.1f}" '
                  f'width="{wbar*fr:.1f}" height="18" '
                  f'fill="{V.TEAL if fr >= 0.999 else (V.AMB if fr >= 0.5 else V.COR)}"/>')
            s += D.text(X, y + 16, f"{fr:.0%} finished", V.MUT, 11,
                        anchor="middle", mono=True)
            lo, hi = cell["finish_rate_ci95"]
            s += D.text(X, y + 32, f"[{lo:.0%}-{hi:.0%}]", V.MUT, 9.5,
                        anchor="middle", mono=True)

    s += D.rule(40, y0 + len(conds) * rowh + 8, W - 80, V.GRID)
    yy = y0 + len(conds) * rowh + 42
    for i, line in enumerate([
        f"Ranges are 95% Wilson intervals at n = {results['n_trials']} rollouts "
        f"per cell. Where two intervals overlap, the two cells are not "
        f"distinguishable and no ranking between them is claimed.",
        "",
        "The nominal row is Episode 10's measurement, repeated here so the "
        "perturbed rows have something from the same code path to be compared "
        "against.",
    ]):
        s += D.text(40, yy + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Finish rate is the DEPLOYED policy's — mean action, no exploration "
        "noise. The steering noise here is a disturbance the deployed car "
        "actually experiences, which is a different thing entirely.",
    )


def recovery_figure(results, traces) -> str:
    """The mechanism, in two REAL laps: the same limit, two different outcomes.

    Not a schematic. The 61%-front car in the left panel reached 13.4 degrees of
    slip — further past the tire's fitted region than the 47% car in the right
    panel, which reached 12.0 — and completed the lap anyway. The fast car did not
    go further over the edge. It failed to come back from going over it.

    That is the whole episode, and it needed measured trajectories rather than
    drawings, because a drawing of this would just be an assertion.
    """
    from .line_figures import track_backdrop
    from physics.track import long_exit

    track = long_exit()
    # Track exposes heading only via centreline(); there is no heading_deg. An
    # earlier version guarded with hasattr and silently fell back to 0 degrees,
    # drawing every car pointing up the page regardless of where the road went.
    # That is exactly how F36 put a 180-degree-wrong car into a published figure.
    # Geometry never gets a silent fallback.
    _cs, _cx, _cy, _chead = track.centreline(4000)
    def heading_deg_at(s_val: float) -> float:
        return float(np.degrees(np.interp(s_val, _cs, _chead)))

    deep = results.get("deep")
    fracs = list(deep["fractions"]) if deep else list(results["fractions"])
    n_head = results.get("n_trials_headline", results["n_trials"])
    W, H = 1560, 1060
    s = V.head(
        W, H,
        "When it lets go, does it come back?",
        "Every one of these cars gets pushed past the tire's fitted limit by the "
        "disturbance, and they all get pushed past it about equally often. What "
        "separates them is what happens next — and these are two real laps.",
    )

    # --- pictorial: two measured laps, both past the limit, opposite outcomes ---
    CASES = (
        ("061", 2, 0.61, "61% front", "reached 13.4 deg of slip — and got round",
         "The nose gives up first. The car runs wide, and running wide scrubs "
         "speed, which is what saves it.", V.TEAL, True),
        ("047", 2, 0.47, "47% front", "reached 12.0 deg of slip — and did not",
         "The tail gives up first. The car rotates, and rotating points the tires "
         "further from where they need to be.", V.COR, False),
    )
    for i_c, (tag3, k, ff, title, sub, note, colour, ok) in enumerate(CASES):
        L = 50 + i_c * 500
        tag = f"both_{tag3}_{k}"
        sa, nn = traces[f"{tag}_s"], traces[f"{tag}_n"]
        sl = np.abs(traces[f"{tag}_alpha_max_deg"])
        s += D.text(L, 150, title, colour, 16, weight="600")
        s += D.text(L, 172, sub, V.FG, 12.5)
        back, to_px, _ = track_backdrop(track, S_LO, S_HI, L, L + 430, 200, 660)
        s += back
        m = (sa >= S_LO) & (sa <= S_HI)
        x, y = track.to_xy(sa[m], nn[m])
        px, py = to_px(x, y)
        slw = sl[m]
        # Segment the line by whether the tire was inside its fitted region. A
        # single-colour path cannot show that the excursion is the same on both.
        pts = list(zip(px, py))
        for a in range(len(pts) - 1):
            over = slw[a] > 12.0
            s += (f'<line x1="{pts[a][0]:.1f}" y1="{pts[a][1]:.1f}" '
                  f'x2="{pts[a+1][0]:.1f}" y2="{pts[a+1][1]:.1f}" '
                  f'stroke="{V.AMB if over else colour}" '
                  f'stroke-width="{4.2 if over else 2.6}"/>')
        # the car where slip peaked
        j = int(np.argmax(slw))
        head = heading_deg_at(float(sa[m][j]))
        s += D.car_plan(float(px[j]), float(py[j]), length=54, width=25,
                        wheel_len=13, wheel_w=6,
                        heading_deg=D.screen_heading_deg(head), body=colour)
        # Label on whichever side has room. Placed unconditionally to the right it
        # ran into the adjacent column.
        right = float(px[j]) < L + 250
        s += D.text(float(px[j]) + (22 if right else -22), float(py[j]) - 14,
                    f"{slw[j]:.1f} deg", V.AMB, 11.5,
                    "start" if right else "end", weight="600", mono=True)
        if not ok:
            ex, ey = float(px[-1]), float(py[-1])
            for dx, dy in ((-1, -1), (-1, 1)):
                s += (f'<line x1="{ex+dx*11:.1f}" y1="{ey+dy*11:.1f}" '
                      f'x2="{ex-dx*11:.1f}" y2="{ey-dy*11:.1f}" '
                      f'stroke="{V.COR}" stroke-width="3.4"/>')
            right = ex < L + 250
            s += D.text(ex + (20 if right else -20), ey + 26, "off the road",
                        V.COR, 12, "start" if right else "end", weight="600")
        s += D.text(L, 700, "COMPLETED THE LAP" if ok else "LEFT THE ROAD",
                    V.TEAL if ok else V.COR, 13, weight="600")
        for li, line in enumerate(_wrap(note, 56)):
            s += D.text(L, 726 + 19 * li, line, V.MUT, 12)
    s += (f'<line x1="50" y1="676" x2="86" y2="676" stroke="{V.AMB}" '
          f'stroke-width="4.2"/>')
    s += D.text(94, 680, "past the tire's fitted limit (>12 deg of slip)",
                V.AMB, 11)

    # --- technical: the count, per design -------------------------------------
    x0, y0, rowh = 1000, 150, 62
    s += D.panel_title(x0, y0, "Laps that left the fitted region")
    s += D.text(x0, y0 + 26, f"and how many ended off the road, of {n_head} laps",
                V.MUT, 11.5)
    wmax = max(results["cells"][f"both|{dkey(f)}"]["discarded_laps"]
               for f in fracs) or 1
    for i, ff in enumerate(fracs):
        c = results["cells"][f"both|{dkey(ff)}"]
        dl, df = c["discarded_laps"], c["discarded_failures"]
        y = y0 + 74 + i * rowh
        # Deliberately NOT the per-design ramp: 61% front is red in that ramp and
        # would read as the alarming one when it is the most robust car here.
        s += D.text(x0, y - 2, f"{100*ff:.0f}% front", V.FG, 13, weight="600")
        bw = 250.0
        s += (f'<rect x="{x0+100}" y="{y-14:.0f}" width="{bw*dl/wmax:.1f}" '
              f'height="17" fill="{V.MUT}" opacity="0.35"/>')
        s += (f'<rect x="{x0+100}" y="{y-14:.0f}" width="{bw*df/wmax:.1f}" '
              f'height="17" fill="{V.COR}"/>')
        s += D.text(x0 + 100 + bw + 12, y, f"{df:2d}/{dl:<2d}", V.FG, 12,
                    mono=True)
        s += D.text(x0 + 100 + bw + 74, y, f"{df/max(dl,1):3.0%}",
                    V.COR if df / max(dl, 1) > 0.5 else V.MUT, 12.5, mono=True,
                    weight="600")
    ly = y0 + 74 + len(fracs) * rowh + 10
    s += (f'<rect x="{x0+100}" y="{ly}" width="20" height="12" '
          f'fill="{V.MUT}" opacity="0.35"/>')
    s += D.text(x0 + 128, ly + 11, "left the fit, recovered", V.MUT, 11)
    s += (f'<rect x="{x0+100}" y="{ly+22}" width="20" height="12" '
          f'fill="{V.COR}"/>')
    s += D.text(x0 + 128, ly + 33, "left the fit, crashed", V.MUT, 11)
    s += D.text(x0, ly + 78, "Same exposure. Opposite outcome.", V.FG, 13,
                weight="600")
    for li, line in enumerate(_wrap(
            "The 61% car left the limit MORE often than the 47% car — 18 laps "
            "against 16 — and crashed once against thirteen.", 44)):
        s += D.text(x0, ly + 102 + 19 * li, line, V.MUT, 12)

    s += D.rule(50, 830, W - 100, V.GRID)
    for i, line in enumerate([
        "So the fast car is not fragile because it runs closer to the edge. Both "
        "cars go over the edge about as often. It is fragile because going over is "
        "a one-way trip.",
        "",
        "That is Season 2's understeer mechanism showing up as a robustness "
        "property rather than a lap-time one. A car that loses the front pushes "
        "wide and slows itself down; a car that loses",
        "the rear rotates, and rotating puts the tires further from where they need "
        "to be, which rotates it more. One is a negative feedback loop and the "
        "other is a positive one.",
    ]):
        s += D.text(50, 866 + 21 * i, line, V.MUT, 12.5)

    s += D.text(40, H - 40, "  -  ".join([
        f"[MEASURED] Episode 10's policy, DEPLOYED, nothing retrained",
        f"{n_head} rollouts per design, both disturbances",
        f"[ASSUMED] steering noise sigma {results['steer_noise']}, "
        f"grip +/-{results['grip_spread']:.0%} per lap",
        "left panel: two real laps, seed 2 of each",
    ]), V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "Both left-panel laps are simulation output, not drawings — same corner, "
        "same driver, same disturbance settings, different car. Amber marks the "
        "stretch where the tire was outside the region our data covers.",
    )
