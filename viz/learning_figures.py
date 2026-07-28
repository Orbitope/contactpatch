"""Episode 9 figures — what a learner learned, and what it was really doing.

``learning_figure``
    The pictorial hero: the two drivers on the same road, one completing the lap
    and one in the scenery, with the training curve underneath.
``noise_figure``
    Why they differ. The action-to-force map with its kink at zero, and what a
    Gaussian policy straddling it actually delivers.
``training_card``
    The technical panels — return, distance, entropy, KL, explained variance —
    annotated with the D6 threshold each one is checked against.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V
from physics.track import CORNER_ARC as T_ARC, CORNER_RADIUS, ENTRY_STRAIGHT as T_ENTRY


def _stamp(y: float, results, extra: str = "") -> str:
    c = results["train_config"]
    bits = [
        f"[MEASURED] PPO on the double-track model, {results['total_steps']:,} steps",
        f"seed {results['seed']}",
        f"std init {c['init_log_std']}",
        "[ASSUMED] reward = progress only; slip envelope NOT enforced",
    ]
    if extra:
        bits.append(extra)
    return D.text(40, y, "  -  ".join(bits), V.MUT, 9.5)


def learning_figure(results, history, traces) -> str:
    """Two drivers, same policy, same road. One finishes."""
    from .line_figures import track_backdrop
    from physics.track import long_exit

    track = long_exit()
    ev = results["evaluation"]
    W, H = 1480, 1120
    s = V.head(
        W, H,
        "It learned to drive. Then it turned out the noise was driving.",
        "One policy, trained on nothing but distance covered. On the left it is "
        "driven the way it was trained — actions sampled from its distribution. "
        "On the right the same policy, taking its average action instead.",
    )

    panels = (("stochastic", "Sampled, as trained", V.TEAL, 70, 640),
              ("greedy", "Its own average action", V.COR, 780, 1350))
    for key, title, colour, L, R in panels:
        back, to_px, scale = track_backdrop(track, 0.0, track.length,
                                            L, R, 190, 900)
        e = ev[key]
        s += D.panel_title(L, 150, title,
                           f"{e['distance_m']:.0f} m of {track.length:.0f}  ·  "
                           f"{e['finish_rate']:.0%} of laps completed")
        s += back
        sa = traces[f"{key}_s"]
        n = traces[f"{key}_n"]
        x, y = track.to_xy(sa, n)
        px, py = to_px(x, y)
        s += (f'<path d="{V.path(list(zip(px, py)))}" fill="none" '
              f'stroke="{colour}" stroke-width="3"/>')
        # mark where it ended
        s += (f'<circle cx="{px[-1]:.1f}" cy="{py[-1]:.1f}" r="9" fill="none" '
              f'stroke="{colour}" stroke-width="2.5"/>')
        s += (f'<circle cx="{px[-1]:.1f}" cy="{py[-1]:.1f}" r="3.5" '
              f'fill="{colour}"/>')
        ended = "finished" if sa[-1] >= track.length - 1.0 else "left the road"
        s += D.text(float(px[-1]) + 16, float(py[-1]) + 4,
                    f"{ended} at {sa[-1]:.0f} m", colour, 11, weight="600")

    s += D.rule(70, 940, 1400, V.GRID)
    st, g = ev["stochastic"], ev["greedy"]
    for i, line in enumerate([
        f"Same weights. Same road. The only difference is whether the policy's "
        f"own exploration noise is switched on.",
        "",
        f"Sampled, it completes {st['finish_rate']:.0%} of laps. Taking its "
        f"average action — which is what you would ship — it reaches "
        f"{g['distance_m']:.0f} m and runs out of road on the way through the "
        f"corner.",
        "",
        "That is not a small discrepancy in a metric. It means the driver that "
        "was trained and the driver you would deploy are two different drivers, "
        "and the training",
        "curves describe only one of them.",
    ]):
        s += D.text(70, 972 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Both traces are single rollouts from the same trained policy on the "
        "same track with the same seed. Lap times are not comparable with "
        "Seasons 1-2: the slip envelope is not enforced here.",
    )


def noise_figure(results, traces) -> str:
    """The kink in the action map, and what a Gaussian policy does to it."""
    W, H = 1480, 940
    s = V.head(
        W, H,
        "Why the noise was doing the braking",
        "The car's brakes are stronger than its engine — 12 kN against 4.5 kN — "
        "so the map from the policy's throttle action to actual force has a kink "
        "at zero. That kink is real physics. What it does to a noisy policy is "
        "not.",
    )

    # left: the force map with the kink
    L, R, TT, B = 130, 640, 190, 620
    ax_x = lambda a: L + (R - L) * (a + 1.0) / 2.0
    ax_y = lambda f: B - (B - TT) * (f + 12000.0) / 16500.0
    s = V.grid(s, L, R, TT, B, 4, 4)
    xt = [(f"{v:+.1f}", ax_x(v)) for v in (-1.0, -0.5, 0.0, 0.5, 1.0)]
    yt = [(f"{v/1000:+.0f}", ax_y(v)) for v in (-12000, -8000, -4000, 0, 4000)]
    s = V.axes(s, L, R, TT, B, "throttle action", "force at the wheels (kN)",
               xt, yt)
    pts = [(ax_x(a), ax_y(a * 4500.0 if a >= 0 else a * 12000.0))
           for a in np.linspace(-1, 1, 201)]
    s += (f'<path d="{V.path(pts)}" fill="none" stroke="{V.FG}" '
          f'stroke-width="2.6"/>')
    s += (f'<circle cx="{ax_x(0.0):.1f}" cy="{ax_y(0.0):.1f}" r="7" fill="none" '
          f'stroke="{V.AMB}" stroke-width="2.4"/>')
    s += D.text(ax_x(0.0) + 14, ax_y(0.0) - 10, "the kink", V.AMB, 12,
                weight="600")
    s += D.panel_title(L, 168, "A · The action-to-force map")

    # right: what a Gaussian sees through it
    L2, R2 = 800, 1350
    rng = np.random.default_rng(0)
    mus = np.linspace(-0.4, 0.8, 25)
    std = float(np.exp(results["train_config"]["init_log_std"][1]))
    mean_force = np.array([
        (lambda a: np.where(a >= 0, a * 4500.0, a * 12000.0))(
            np.clip(rng.normal(m, std, 20000), -1, 1)).mean() for m in mus])
    direct = np.where(mus >= 0, mus * 4500.0, mus * 12000.0)
    ax2_x = lambda a: L2 + (R2 - L2) * (a - mus[0]) / (mus[-1] - mus[0])
    ax2_y = lambda f: B - (B - TT) * (f + 5000.0) / 10000.0
    s = V.grid(s, L2, R2, TT, B, 4, 4)
    xt2 = [(f"{v:+.1f}", ax2_x(v)) for v in (-0.4, 0.0, 0.4, 0.8)]
    yt2 = [(f"{v/1000:+.0f}", ax2_y(v)) for v in (-4000, -2000, 0, 2000, 4000)]
    s = V.axes(s, L2, R2, TT, B, "the policy's MEAN throttle action",
               "force actually delivered (kN)", xt2, yt2)
    s += (f'<path d="{V.path([(ax2_x(a), ax2_y(f)) for a, f in zip(mus, direct)])}" '
          f'fill="none" stroke="{V.MUT}" stroke-width="2.2" '
          f'stroke-dasharray="7 6"/>')
    s += (f'<path d="{V.path([(ax2_x(a), ax2_y(f)) for a, f in zip(mus, mean_force)])}" '
          f'fill="none" stroke="{V.COR}" stroke-width="2.8"/>')
    s += D.panel_title(L2, 168, "B · What the policy actually delivers",
                       f"sampling with standard deviation {std:.2f}")
    s += D.text(R2 - 6, ax2_y(direct[-1]) - 10, "what the mean action asks for",
                V.MUT, 11, "end")
    s += D.text(R2 - 6, ax2_y(mean_force[-1]) + 22,
                "what sampling delivers", V.COR, 11, "end", weight="600")
    i0 = int(np.argmin(np.abs(mus)))
    s += (f'<line x1="{ax2_x(mus[i0]):.1f}" y1="{ax2_y(direct[i0]):.1f}" '
          f'x2="{ax2_x(mus[i0]):.1f}" y2="{ax2_y(mean_force[i0]):.1f}" '
          f'stroke="{V.AMB}" stroke-width="2"/>')
    s += D.text(ax2_x(mus[i0]) + 10, 0.5 * (ax2_y(direct[i0]) + ax2_y(mean_force[i0])),
                f"{abs(mean_force[i0])/1000:.1f} kN of braking", V.AMB, 11,
                weight="600")
    s += D.text(ax2_x(mus[i0]) + 10,
                0.5 * (ax2_y(direct[i0]) + ax2_y(mean_force[i0])) + 15,
                "the mean action does not have", V.AMB, 10.5)

    s += D.rule(70, 670, 1400, V.GRID)
    for i, line in enumerate([
        "A straight line through a kink is not a straight line. Average a "
        "spread of throttle actions around zero and the samples that fall "
        "below zero are multiplied by 12 kN while",
        "the ones above are multiplied by 4.5 — so the average FORCE is braking "
        "even when the average ACTION is not. E[f(a)] is not f(E[a]).",
        "",
        "THE POLICY NEVER LEARNED TO BRAKE. It learned a mean throttle that "
        "produces braking once its own noise is added, and the corner is only "
        "survivable with that braking",
        "included. Switch the noise off to deploy it and the braking disappears "
        "with it.",
        "",
        "Nothing here is a bug in the physics. The brakes really are stronger "
        "than the engine. The problem is that a Gaussian policy and a kinked "
        "actuator make a driver whose",
        "behaviour lives in the noise, and no training curve shows that.",
    ]):
        s += D.text(70, 702 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Panel B is a Monte Carlo over 20,000 samples per mean action, through "
        "the same clipping and force map the environment applies.",
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


def training_card(results, history) -> str:
    steps = np.array([h["steps"] for h in history])
    W, H = 1520, 760
    s = V.head(
        W, H,
        "Episode 9 - training health",
        "The curves, each annotated with the D6 threshold it is checked against. "
        "Every one of these thresholds exists because a run failed that way "
        "while this episode was being built.",
    )

    panels = [
        ("distance_mean", "distance covered (m)", "A - Did it learn to drive?",
         100, 400, None),
        ("approx_kl", "approximate KL", "B - Did the policy update?",
         540, 840, 1e-4),
        ("explained_variance", "explained variance",
         "C - Did the critic predict?", 980, 1280, 0.3),
    ]
    for key, ylab, title, L, R, floor in panels:
        vals = np.array([h[key] for h in history])
        lo, hi = float(np.min(vals)), float(np.max(vals))
        if floor is not None:
            lo, hi = min(lo, floor * 0.5), max(hi, floor * 1.5)
        pad = 0.08 * (hi - lo or 1.0)
        ax = _Ax(L, R, 150, 440, 0, float(steps[-1]), lo - pad, hi + pad)
        s += D.panel_title(L, 132, title)
        s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 4, 4)
        xt = [(f"{v/1000:.0f}k", float(ax.x(v)))
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

    ev = results["evaluation"]
    ly = 500
    rows = [("", "distance", "laps finished", "worst slip", "beyond 12 deg")]
    for k, label in (("stochastic", "sampled, as trained"),
                     ("greedy", "mean action, as deployed")):
        e = ev[k]
        rows.append((label, f"{e['distance_m']:.0f} m",
                     f"{e['finish_rate']:.0%}",
                     f"{e['worst_slip_deg']:.1f} deg",
                     f"{100*e['slip_over_bound']:.1f}%"))
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            col = V.FG if r == 0 or c == 0 else V.MUT
            s += D.text(100 + c * 250, ly + r * 24, cell, col, 12.5,
                        weight="600" if r == 0 or c == 0 else "normal",
                        mono=(r > 0 and c > 0))
    s += D.text(100, ly + 96,
                f"D6: {'PASSED' if results['d6_passed'] else 'FAILED'}"
                + ("" if results["d6_passed"] else
                   " — " + ", ".join(results["d6_failures"])),
                V.GRN if results["d6_passed"] else V.COR, 13, weight="600")
    s += D.text(100, ly + 120,
                "A failing D6 is the point of D6. These are the checks that "
                "separate a result from a run that merely completed.", V.MUT, 11.5)
    s += _stamp(H - 40, results)
    return s + V.foot(
        W, H,
        "Distance is a trailing mean over the last 50 finished episodes. "
        "Approximate KL is Schulman's low-variance estimator, averaged over "
        "every minibatch in the update.",
    )


__all__ = ["learning_figure", "noise_figure", "training_card",
           "failure_figure"]


def failure_figure(cases, results) -> str:
    """What the failures actually look like on the road.

    Written because two episodes of "the policy does not drive" existed only as
    numbers in tables — 0% finish rate, 121 degrees of slip — and a number like
    121 degrees does not communicate that the car is travelling sideways. The
    body is drawn at the heading the car is actually pointing, and the arrow is
    the direction it is actually moving. When those disagree by more than a right
    angle, the picture says what the table cannot.

    ``cases`` is a list of dicts with keys: title, sub, trace, colour.
    """
    from .line_figures import track_backdrop, path_heading
    from physics.track import long_exit

    track = long_exit()
    W, H = 1480, 1180
    s = V.head(
        W, H,
        "What the policies are actually doing",
        "The car body points where the car is pointing; the arrow points where it "
        "is actually going. On a car that is driving, those agree. Arrow colour "
        "is slip angle — how far apart they have got.",
    )
    s += D.text(40, 92,
                "Our tire model was fitted to ±12°. Beyond that the forces it "
                "returns are arithmetic, not measurement.", V.MUT, 11.5)

    n_cases = len(cases)
    span = 1360 / n_cases
    # Crop to where anything actually happens. Both failing policies stop around
    # 130 m of a 393 m track, and drawn to the full length every car piles into
    # the first third as an unreadable caterpillar — which is what the first
    # version of this figure did.
    far = max(float(c["trace"]["s"][-1]) for c in cases)
    s_hi = min(far + 45.0, track.length)
    for ci, case in enumerate(cases):
        L = 70 + ci * span
        R = L + span - 50
        tr = case["trace"]
        back, to_px, scale = track_backdrop(track, 0.0, s_hi, L, R, 200, 860)
        s += D.panel_title(L, 152, case["title"], case["sub"])
        s += back

        sa, n, xi = tr["s"], tr["n"], tr["xi"]
        slip = tr["alpha_max_deg"]
        x, y = track.to_xy(sa, n)
        px, py = to_px(x, y)
        s += (f'<path d="{V.path(list(zip(px, py)))}" fill="none" '
              f'stroke="{V.FG}" stroke-width="1.8" opacity="0.45"/>')

        head = path_heading(track, sa, xi)
        # draw the car every ~18 m of travel, plus always the last instant
        marks = list(range(0, len(sa), max(len(sa) // 8, 1))) + [len(sa) - 1]
        for k in marks:
            hd = D.screen_heading_deg(math.degrees(float(head[k])))
            u = min(float(slip[k]) / 60.0, 1.0)
            r_, g_, b_ = V.ramp(u)
            col = f"#{r_:02x}{g_:02x}{b_:02x}"
            s += D.car_plan(float(px[k]), float(py[k]), length=46, width=22,
                            wheel_len=13, wheel_w=6.5, heading_deg=hd,
                            loads=(0.5,) * 4, body=col)
            # which way it is actually travelling: path tangent, since s and n
            # are advancing along the road
            if k + 1 < len(sa):
                vx, vy = float(px[k + 1] - px[k]), float(py[k + 1] - py[k])
                mag = math.hypot(vx, vy)
                if mag > 1e-6:
                    s += D.arrow(float(px[k]), float(py[k]),
                                 float(px[k]) + 40 * vx / mag,
                                 float(py[k]) + 40 * vy / mag, col, 2.4, 8.0)

        ended = ("finished" if sa[-1] >= track.length - 1.0
                 else f"stopped at {sa[-1]:.0f} m")
        s += D.text(L, 890, ended, case["colour"], 13, weight="600")
        s += D.text(L, 910,
                    f"worst slip {float(np.max(slip)):.0f}°   ·   "
                    f"{100*float(np.mean(slip > 12.0)):.0f}% of steps beyond 12°",
                    V.MUT, 11.5)

    ly = 948
    s += D.text(70, ly, "arrow colour — slip angle, the gap between pointing "
                "and going:", V.MUT, 11.5)
    for i, (u, lab) in enumerate(((0.0, "0°"), (0.2, "12°"), (0.5, "30°"),
                                  (0.75, "45°"), (1.0, "60°+"))):
        bx = 560 + i * 90
        r_, g_, b_ = V.ramp(u)
        s += (f'<rect x="{bx}" y="{ly-11}" width="64" height="13" rx="3" '
              f'fill="#{r_:02x}{g_:02x}{b_:02x}"/>')
        s += D.text(bx + 32, ly + 17, lab, V.MUT, 10.5, "middle")

    s += D.rule(70, 986, 1400, V.GRID)
    for i, line in enumerate([
        "A car that is driving has its body and its arrow pointing the same way. "
        "Neither of these is driving.",
        "",
        "The left-hand car is the Episode 9 policy as it would be DEPLOYED — its "
        "mean action, with the exploration noise switched off. It stays pointed "
        "roughly where it is going, and",
        "simply arrives at the corner too fast and runs out of road. That is a "
        "car being driven badly.",
        "",
        "The right-hand car is the Episode 10 policy. Body and arrow come apart "
        "completely: it is travelling sideways and backwards while the tire "
        "model, fitted to ±12°, is asked",
        "for forces at over 120°. It covers ground faster that way — 21.0 m/s "
        "against 20.2 inside the envelope — which is why it learned to. That is "
        "not a car being driven badly.",
        "That is a car exploiting a region of a curve fit where no tire was ever "
        "measured.",
    ]):
        s += D.text(70, 1018 + 21 * i, line, V.MUT, 12.5)

    s += _stamp(H - 40, results, "slip beyond ±12° is outside the tire fit")
    return s + V.foot(
        W, H,
        "Cars drawn oversized for legibility; positions and headings are to "
        "scale. The arrow is the direction of travel along the solved path.",
    )
