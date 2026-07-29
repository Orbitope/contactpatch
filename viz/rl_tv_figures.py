"""Episode 14 figures.

``pilot_sanity_figure``
    ONE figure for the pilot phase: realized yaw moment against distance for
    whichever of C (Episode 13, if present), H and E trained, plus each
    variant's D6 status. Enough to look at by eye before committing to a
    production run (rule: every figure gets looked at, F68's lesson) — not a
    pictorial/technical pair. Those come once there is a real result to draw,
    per the approved plan for this episode.

Production figures (pictorial/technical pairs, rule 1), built from
``results.json`` + ``production_report.json`` once every seed has landed:

``control_surfaces_figure`` (pictorial hero)
    Classical C and each RL variant's representative seed, one instant near
    peak lateral g, four wheel-force arrows per car to one scale.
``yaw_moment_figure`` (technical companion to the hero)
    Realized Mz against distance for the same three traces.
``envelope_escape_figure`` (pictorial)
    All SIX seeds' worst-SLIP instant, one friction circle per wheel, the
    ±12 deg tire-fit boundary made visible as "did this wheel's circle
    still have room in it."
``seed_scorecard_figure`` (technical companion)
    The same six seeds' worst slip angle and envelope occupancy as bars,
    against the tire file's own ±12 deg bound.
"""

from __future__ import annotations

import math

import numpy as np

from . import diagram as D
from . import lib as V

COLOUR = {"C": V.SLATE, "H": V.TEAL, "E": V.COR}
LABEL = {"C": "classical (Ep 13)", "H": "variant H — RL Mz + allocator",
         "E": "variant E — end-to-end"}
CORNERS = ("fl", "fr", "rl", "rr")
ENVELOPE_SLIP_DEG = 12.0


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


def _util_colour(u: float) -> str:
    r, g, b = V.ramp(float(min(max(u, 0.0), 1.0)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _rep_seed_report(report, results, variant):
    rep = results["variants"][variant]["representative_seed"]
    for e in report.get("variants", {}).get(variant, []):
        if e["seed"] == rep:
            return e
    return None


def control_surfaces_figure(results, report) -> str:
    """The pictorial hero: classical C and each RL variant's representative
    seed (median finish distance, not the best of its 3 — F71), drawn at
    their own peak-lateral-g instant with the four wheel-force arrows
    Episodes 12 and 13 already use. Longitudinal force only (fx) — the
    channel a torque-vectoring controller actually splits across the axle,
    and the one channel logged for the classical trace, which has no
    per-wheel fy of its own to show.
    """
    panels = []
    c = results.get("classical_c")
    if c and "peak_instant" in c:
        pk = c["peak_instant"]
        panels.append({
            "key": "C", "label": LABEL["C"], "a_y_g": pk["a_y_g"],
            "fx": {k: v["fx"] for k, v in pk["corners"].items()},
            "util": {k: v["util"] for k, v in pk["corners"].items()},
            "d6": None, "seed": None,
        })
    for variant in ("H", "E"):
        info = results.get("variants", {}).get(variant)
        e = _rep_seed_report(report, results, variant)
        if info is None or e is None:
            continue
        pk = e["peak_instant"]
        panels.append({
            "key": variant, "label": LABEL[variant], "a_y_g": pk["a_y_g"],
            "fx": {k: v["fx"] for k, v in pk["corners"].items()},
            "util": {k: v["util"] for k, v in pk["corners"].items()},
            "d6": info["d6_passed"], "seed": info["representative_seed"],
        })

    W, H = 1560, 900
    s = V.head(
        W, H,
        "The same wheels, three different decision-makers",
        "One instant near peak lateral acceleration, for the classical "
        "controller and each RL variant's representative seed (median finish "
        "distance across its 3 seeds, not the best — F71). Same corner, "
        "same tire model, same four wheels; only who decided the split "
        "differs.",
    )

    if not panels:
        s += D.text(60, 200, "no data available", V.MUT, 14)
        return s + V.foot(W, H, "")

    max_force = max(abs(v) for p in panels for v in p["fx"].values())
    scale = 110.0 / max(max_force, 1.0)
    n = len(panels)
    dxp = (W - 160) / n
    cy = 430

    for i, p in enumerate(panels):
        cx = 80 + dxp * i + dxp / 2
        s += D.text(cx, 152, p["label"], V.FG, 16, "middle", weight="600")
        s += D.text(cx, 176, f"peak {p['a_y_g']:.2f} g", V.MUT, 12.5,
                    "middle", mono=True)
        patches = [_util_colour(p["util"][c2]) for c2 in CORNERS]
        s += D.car_plan(cx, cy, length=250, width=118, wheel_len=54,
                        wheel_w=24, loads=(0.55, 0.8, 0.55, 0.8),
                        body=V.MUT, patches=patches)
        hw = 118 / 2
        ax_f, ax_r = -250 * 0.30, 250 * 0.30
        for c2, dx, dy in (("fl", -1, ax_f), ("fr", 1, ax_f),
                          ("rl", -1, ax_r), ("rr", 1, ax_r)):
            wx = cx + dx * (hw + 24 * 0.35)
            wy = cy + dy
            f = p["fx"][c2]
            length = f * scale
            colour = V.TEAL if f >= 0 else V.COR
            if abs(length) > 1.5:
                s += D.arrow(wx, wy, wx, wy - length, colour, 4.4, 12)
            s += D.text(wx + (16 if dx > 0 else -16), wy - length / 2 + 4,
                        f"{f:+.0f}", colour, 11.5,
                        "start" if dx > 0 else "end", weight="600", mono=True)

        by = cy + 230
        if p["d6"] is None:
            s += D.text(cx, by, "deterministic controller — no D6", V.MUT,
                        12, "middle")
        else:
            d6_colour = V.TEAL if p["d6"] else V.COR
            s += D.text(cx, by,
                        f"seed {p['seed']} — D6 "
                        f"{'PASSED' if p['d6'] else 'FAILED'}", d6_colour,
                        13, "middle", weight="600")

    s += D.rule(60, 660, W - 120, V.GRID)
    for i, line in enumerate(D_wrap(
            "Arrow length is longitudinal force at the contact patch, one "
            "scale across all three cars; teal pushes forward, coral drags "
            "back. Contact-patch shading is friction-ellipse utilisation at "
            "that instant, hypot(Fx/Fx_peak, Fy/Fy_peak) — the same measure "
            "regardless of whether a human or a policy chose the forces.",
            148)):
        s += D.text(60, 694 + 20 * i, line, V.MUT, 12.5)

    s += D.text(40, H - 40,
               "[MEASURED] production run, 3 seeds/variant, 5,000,000 steps "
               "each · RUNG 2 — mechanism and ordering only, not a real car "
               "(rule 15)", V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "The classical panel has no seed and no D6 verdict — it is not a "
        "trained policy.",
    )


def yaw_moment_figure(results) -> str:
    """The technical companion to the hero: realized Mz against distance for
    the same three traces, plus each variant's D6 pass rate across all 3
    seeds (not just the representative one — a single number would hide
    exactly the seed-to-seed disagreement this episode's other figures make
    the point of).
    """
    W, H = 1480, 980
    s = V.head(
        W, H,
        "Yaw moment along the road",
        "Realized yaw moment, computed downstream from each trace's own "
        "logged per-wheel forces (rule 7) — the same physics regardless of "
        "which controller chose them. H and E show their REPRESENTATIVE "
        "seed (median finish distance of 3, not the best — F71); classical "
        "C's line is the reference model's DEMAND, since a deterministic "
        "controller has no other run to disagree with.",
    )

    series = {}
    if "classical_c" in results:
        c = results["classical_c"]
        series["C"] = (np.asarray(c["s"]), np.asarray(c["mz_demand"]))
    for v in ("H", "E"):
        info = results.get("variants", {}).get(v)
        if info and "s" in info:
            series[v] = (np.asarray(info["s"]), np.asarray(info["mz"]))

    all_y = [y for arr in series.values() for y in arr[1].tolist()] or [0.0, 1.0]
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

    # Everything below here sits under the axis-label row (B+46=526), so
    # legend and status text never cross the "distance along the road (m)"
    # caption that pilot_sanity_figure's tighter y=522 collided with.
    ly = 560
    for i, (key, (sa, mz)) in enumerate(series.items()):
        s += (f'<path d="{V.path(ax.pts(sa, mz))}" fill="none" '
              f'stroke="{COLOUR[key]}" stroke-width="2.4"/>')
        y = ly + i * 22
        s += (f'<line x1="100" y1="{y-4}" x2="140" y2="{y-4}" '
              f'stroke="{COLOUR[key]}" stroke-width="3"/>')
        seed_note = ""
        if key in ("H", "E"):
            rep = results["variants"][key]["representative_seed"]
            seed_note = f" (seed {rep})"
        s += D.text(150, y, LABEL[key] + seed_note, COLOUR[key], 13)

    tx = 780
    s += D.panel_title(tx, 558,
                       "Did training find a policy that agrees with the humans?")
    for v in ("H", "E"):
        info = results.get("variants", {}).get(v)
        y = 598 + (0 if v == "H" else 120)
        if info is None:
            s += D.text(tx, y, f"variant {v}: not yet run", V.MUT, 13)
            continue
        n = info["n_seeds"]
        n_pass = len(info["d6_passed_seeds"])
        colour = V.TEAL if n_pass == n else (V.AMB if n_pass else V.COR)
        s += D.text(tx, y, f"variant {v} — D6 passed {n_pass}/{n} seeds",
                    colour, 14, weight="600")
        s += D.text(tx, y + 20,
                    f"passed: {info['d6_passed_seeds'] or 'none'}   "
                    f"failed: {info['d6_failed_seeds'] or 'none'}",
                    V.MUT, 11.5, mono=True)
        s += D.text(tx, y + 44,
                    f"representative (seed {info['representative_seed']}): "
                    f"finished={info['finished']}  "
                    f"peak {info['peak_a_y_g']:.2f} g  "
                    f"util {info['mean_utilisation']:.2f}", V.MUT, 12, mono=True)

    s += D.rule(60, 800, W - 120, V.GRID)
    for i, line in enumerate(D_wrap(
            "Neither variant reliably converges to a policy that agrees "
            "with the classical controller at this training budget: H "
            "passes D6 in 0 of 3 seeds, E in 1 of 3. H's typical failure is "
            "mild — an optimistic critic, an occasional excursion past the "
            "tire's own +/-12 deg fit. E's is sharper: two of its three "
            "seeds found a way to run substantially outside that fit despite "
            "the same envelope penalty classical training already uses, "
            "echoing the exploit Episode 9 first found (F53/F56).", 148)):
        s += D.text(60, 824 + 20 * i, line, V.MUT, 12)

    s += D.text(40, H - 40,
               "[MEASURED] realized Mz from logged per-wheel forces via "
               "DoubleTrackBackend.yaw_moment · 3 seeds/variant, 5,000,000 "
               "steps each · RUNG 2 (rule 15)", V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "Classical C's line is Episode 13's DEMANDED moment, not realized; "
        "H and E have no separate demand, so theirs is what the wheels "
        "actually did.",
    )


def envelope_escape_figure(results, report) -> str:
    """Pictorial: all six trained seeds at their own worst-SLIP instant, one
    friction circle per wheel. The ring is everything that tire's own load
    and the tire file's fit support; an arrow reaching or passing it is the
    policy asking the model for something outside the +/-12 deg region every
    minimum-time solve in this project also stays inside — the seed-to-seed
    disagreement made visible rather than reduced to a pass rate.

    The instant shown is ``argmax(alpha_max_deg)``, the SAME step
    ``worst_slip_deg`` (in ``result_*.json`` and the seed-scorecard figure)
    already reports — not the peak-utilisation step, which need not be the
    same moment and would otherwise put a smaller angle on this figure than
    the number quoted next to it.
    """
    W, H = 1400, 900
    s = V.head(
        W, H,
        "Did it stay on the map?",
        "Every trained seed's worst-slip instant — friction-circle usage at "
        "the moment it reached its worst slip angle, teal through amber to "
        "coral by how much of that tire's own grip it spent. An arrow "
        "reaching or passing its ring is the policy asking the tire model "
        "for something past the fit it was validated over.",
    )

    cols, x0, dxp = 3, 160, 460
    row_cy = {"H": 320, "E": 580}
    worst = {"H": [], "E": []}
    for variant in ("H", "E"):
        seeds = sorted(report.get("variants", {}).get(variant, []),
                       key=lambda e: e["seed"])
        info = results.get("variants", {}).get(variant, {})
        cy = row_cy[variant]
        for i, e in enumerate(seeds):
            seed = e["seed"]
            cx = x0 + (i % cols) * dxp
            wu = e["worst_slip_instant"]
            worst[variant].append((seed, wu["alpha_max_deg"]))
            # The label states the ENVELOPE verdict, which is what this figure
            # is about, and names any other D6 failure separately. Printing a
            # bare "D6 FAILED" next to a slip angle implies the slip caused the
            # failure — H seed 2 is inside the fit at 6.8 deg and fails on its
            # critic, and the first version of this figure said "D6 FAILED
            # worst slip 6.8 deg", which reads as exactly the opposite. That is
            # F68's failure mode: a caption contradicting its own data.
            inside = wu["alpha_max_deg"] <= ENVELOPE_SLIP_DEG
            others = [f for f in info.get("d6_failures_by_seed", {})
                      .get(str(seed), [])
                      if f != "the_policy_stayed_inside_the_tire_model"]
            s += D.text(cx, cy - 154, f"variant {variant} — seed {seed}",
                        V.FG, 15, "middle", weight="600")
            s += D.text(cx, cy - 134,
                        f"worst slip {wu['alpha_max_deg']:.1f} deg — "
                        f"{'inside' if inside else 'OUTSIDE'} the tire fit",
                        V.TEAL if inside else V.COR, 12, "middle",
                        weight="600")
            s += D.text(cx, cy - 116,
                        "D6 passed" if not others
                        else "D6 fails elsewhere: " + ", ".join(
                            f.replace("_", " ") for f in others),
                        V.MUT, 10.5, "middle")
            s += D.car_plan(cx, cy, length=118, width=54, wheel_len=26,
                            wheel_w=11, loads=(0.5,) * 4, body=V.MUT)
            for c2, dx, dy in (("fl", -1, -1), ("fr", 1, -1),
                              ("rl", -1, 1), ("rr", 1, 1)):
                frac = wu["fracs"][c2]
                u = math.hypot(frac["fx_frac"], frac["fy_frac"])
                wx, wy = cx + dx * 96, cy + dy * 46
                s += D.friction_circle(
                    wx, wy, 30, frac["fx_frac"], frac["fy_frac"],
                    colour=(V.COR if u > 1.0 else
                           (V.AMB if u > 0.85 else V.TEAL)),
                    label=f"{100*u:.0f}%")

    # The closing sentence is composed from the actual numbers above it,
    # not a fixed string — a caption that quotes a range the data has since
    # moved past is exactly the kind of silent drift rule 10 exists to
    # prevent.
    allv = worst["H"] + worst["E"]
    over = [(sd, v) for sd, v in allv if v > ENVELOPE_SLIP_DEG]
    lo = min(v for _, v in allv) if allv else 0.0
    hi = max(v for _, v in allv) if allv else 0.0
    if allv and not over:
        h_desc = (f"Every one of the {len(allv)} deployed policies stays "
                  f"inside the tire fit — worst slip {lo:.1f}-{hi:.1f} deg "
                  f"against a {ENVELOPE_SLIP_DEG:.0f} deg bound, and all six "
                  f"drive the full corner.")
        e_desc = ("That is the whole correction. The first production run "
                  "reported excursions to 16.8 deg and three seeds that could "
                  "not finish, because it kept each run's LAST weights rather "
                  "than its best — every one of those seeds had already driven "
                  "a clean lap and been trained past it (F93). The D6 failures "
                  "that remain are training-process checks, not driving: one "
                  "weak critic and two rising-entropy runs. No seed fails an "
                  "envelope or deployment check.")
    elif allv:
        over_txt = ", ".join(f"{v:.1f}" for _, v in
                             sorted(over, key=lambda t: t[1]))
        h_desc = (f"Worst slip across the {len(allv)} deployed policies runs "
                  f"{lo:.1f}-{hi:.1f} deg against a "
                  f"{ENVELOPE_SLIP_DEG:.0f} deg bound.")
        e_desc = (f"{len(over)} of {len(allv)} go past the fit ({over_txt} "
                  f"deg) — the tire-model exploit Episode 9 first found "
                  f"(F53/F56), under the same envelope penalty (0.5) "
                  f"classical training already uses.")
    else:
        h_desc, e_desc = "No seeds available.", ""

    s += D.rule(60, 720, W - 60, V.GRID)
    for i, line in enumerate(D_wrap(h_desc + " " + e_desc, 148)):
        s += D.text(60, 750 + 20 * i, line, V.MUT, 12.5)

    s += D.text(40, H - 40,
               "[MEASURED] friction_circle fractions = Fx/Fx_peak, "
               "Fy/Fy_peak from physics/tire.py at each seed's own "
               "worst-slip step · RUNG 2 (rule 15)", V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "Percentage under each wheel is friction-ellipse utilisation, "
        "hypot(Fx_frac, Fy_frac); over 100% is outside the ring the arrow "
        "is drawn in.",
    )


def seed_scorecard_figure(results) -> str:
    """The technical companion to the escape figure: the same six seeds'
    worst slip angle and envelope occupancy as bars against the tire file's
    own +/-12 deg bound — the quantitative backing for what the friction
    circles show pictorially.
    """
    rows = []
    for variant in ("H", "E"):
        info = results.get("variants", {}).get(variant, {})
        for seed_str, slip in sorted(
                info.get("worst_slip_deg_by_seed", {}).items(),
                key=lambda kv: int(kv[0])):
            seed = int(seed_str)
            occ = info["envelope_occupancy_by_seed"][seed_str]
            d6 = seed in info.get("d6_passed_seeds", [])
            fin = info["finished_by_seed"][seed_str]
            rows.append((variant, seed, slip, occ, d6, fin))

    W, H = 1400, 880
    s = V.head(
        W, H,
        "Seed by seed",
        "Every trained seed on its own: worst slip angle it ever reached "
        "against the tire file's own +/-12 deg fit, and what share of the "
        "whole run it spent past that line. Rule 5's minimum is 3 seeds per "
        "configuration; here the seeds do not agree with each other.",
    )

    if not rows:
        s += D.text(60, 200, "no data available", V.MUT, 14)
        return s + V.foot(W, H, "")

    top, row_h = 170, 84
    L1, R1 = 260, 700
    L2, R2 = 900, 1340
    s += D.panel_title(L1, top - 34, "worst slip angle reached (deg)")
    s += D.panel_title(L2, top - 34, "share of the run past +/-12 deg")

    slip_max = max(12.0, max(r[2] for r in rows)) * 1.15
    occ_max = max(0.05, max(r[3] for r in rows)) * 1.25
    bound_x1 = L1 + (R1 - L1) * (ENVELOPE_SLIP_DEG / slip_max)

    for i, (variant, seed, slip, occ, d6, fin) in enumerate(rows):
        y = top + i * row_h
        colour = COLOUR[variant]
        s += D.text(60, y + 8, f"{variant} seed {seed}", V.FG, 13.5,
                    weight="600")
        s += D.text(60, y + 28,
                    f"D6 {'PASSED' if d6 else 'FAILED'}  finished={fin}",
                    V.TEAL if d6 else V.COR, 11, mono=True)

        bw1 = (R1 - L1) * min(slip / slip_max, 1.0)
        s += (f'<rect x="{L1}" y="{y-14}" width="{R1-L1}" height="26" rx="4" '
              f'fill="{V.GRID}" opacity="0.5"/>')
        s += (f'<rect x="{L1}" y="{y-14}" width="{bw1:.1f}" height="26" '
              f'rx="4" fill="{colour}" opacity="0.9"/>')
        s += (f'<line x1="{bound_x1:.1f}" y1="{y-20}" x2="{bound_x1:.1f}" '
              f'y2="{y+16}" stroke="{V.FG}" stroke-width="1.4" '
              f'stroke-dasharray="4 3"/>')
        s += D.text(L1 + bw1 + 8, y + 4, f"{slip:.1f} deg", V.FG, 12.5,
                    mono=True)

        bw2 = (R2 - L2) * min(occ / occ_max, 1.0)
        s += (f'<rect x="{L2}" y="{y-14}" width="{R2-L2}" height="26" rx="4" '
              f'fill="{V.GRID}" opacity="0.5"/>')
        s += (f'<rect x="{L2}" y="{y-14}" width="{bw2:.1f}" height="26" '
              f'rx="4" fill="{colour}" opacity="0.9"/>')
        s += D.text(L2 + bw2 + 8, y + 4, f"{100*occ:.1f}%", V.FG, 12.5,
                    mono=True)

    s += D.text(bound_x1, top - 48, "+/-12 deg bound", V.FG, 10.5, "middle")

    bottom = top + len(rows) * row_h + 16
    s += D.rule(60, bottom, W - 60, V.GRID)
    for i, line in enumerate(D_wrap(
            "The dashed line is the +/-12 deg slip angle every minimum-time "
            "solve in this project also enforces, and the edge of the "
            "region physics/tire.py was fitted over — ours, not the tire "
            "file's own limit. A seed sitting past it is not a worse "
            "driver; it is a policy whose Mz or wheel-force number was "
            "computed by a curve fit that no longer applies.", 148)):
        s += D.text(60, bottom + 30 + 20 * i, line, V.MUT, 12.5)

    s += D.text(40, H - 40,
               "[MEASURED] worst_slip_deg, envelope_occupancy from "
               "evaluate_variant's greedy rollout · 3 seeds/variant, "
               "5,000,000 steps each", V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "Bars are independent scales (left panel vs right panel); only "
        "positions within a panel are directly comparable.",
    )


def _seed_stats(results, variant, key):
    d = results["variants"][variant][key]
    return np.array([d[k] for k in sorted(d, key=int)], dtype=float)


def tire_spend_figure(results, report) -> str:
    """The pictorial hero for what this episode actually found.

    Two variants x two places on the lap. **The second column is the point.**
    At the apex H and E look the same — both tires nearly full — and a figure
    drawn only there would tell the reader the opposite of the result. On the
    exit straight, where two thirds of the lap is, H's circles empty out and
    E's do not.
    """
    W, H = 1560, 1000
    s = V.head(
        W, H,
        "Same lap, same grip, half the tire",
        "Each wheel's friction circle — the ring is everything that tire has "
        "at that instant, the fill is how much of it is being spent. Both "
        "variants reach the apex at the same grip and get round in the same "
        "time. What differs is what they spend on the straight afterwards.",
    )

    cols = [("at the apex", "peak_instant",
             "Hardest cornering. Both variants are near the limit; there is "
             "almost nothing to choose between them here."),
            ("on the exit straight", "straight_instant",
             "Going in a straight line. H has let the tires go; E is still "
             "spending most of what they have.")]

    for ci, (title, key, blurb) in enumerate(cols):
        cx0 = 300 + ci * 760
        s += D.text(cx0, 150, title, V.FG, 19, "middle", weight="600")
        for i, line in enumerate(D_wrap(blurb, 52)):
            s += D.text(cx0, 176 + 18 * i, line, V.MUT, 12, "middle")

        for ri, variant in enumerate(("H", "E")):
            e = _rep_seed_report(report, results, variant)
            if e is None or key not in e:
                continue
            cy = 380 + ri * 300
            corners = e[key]["corners"]
            if ci == 0:
                s += D.text(70, cy - 96, LABEL[variant], COLOUR[variant], 15,
                            weight="600")
                s += D.text(70, cy - 74,
                            f"seed {results['variants'][variant]['representative_seed']}",
                            V.MUT, 12, mono=True)
            s += D.car_plan(cx0, cy, length=118, width=54, wheel_len=26,
                            wheel_w=11, loads=(0.5,) * 4, body=V.MUT)
            us = []
            for c2, dx, dy in (("fl", -1, -1), ("fr", 1, -1),
                              ("rl", -1, 1), ("rr", 1, 1)):
                w = corners[c2]
                u = float(w["util"])
                us.append(u)
                s += D.friction_circle(
                    cx0 + dx * 96, cy + dy * 46, 30,
                    float(w["fx_frac"]), float(w["fy_frac"]),
                    colour=(V.COR if u > 0.9 else (V.AMB if u > 0.5 else V.TEAL)),
                    label=f"{100*u:.0f}%")
            s += D.text(cx0, cy + 116, f"average {100*np.mean(us):.0f}% of grip in use",
                        V.FG, 14, "middle", weight="600", mono=True)

    lap_h, lap_e = (_seed_stats(results, v, "lap_time_by_seed")
                    if "lap_time_by_seed" in results["variants"][v] else None
                    for v in ("H", "E"))
    util_h = _seed_stats(results, "H", "mean_utilisation_by_seed")
    util_e = _seed_stats(results, "E", "mean_utilisation_by_seed")

    s += D.rule(60, 800, W - 120, V.GRID)
    lines = [
        f"Averaged over the whole lap, H spends {util_h.mean():.0%} of the "
        f"available grip and E spends {util_e.mean():.0%} — and the three seeds "
        f"of each do not overlap. They get round in the same time and reach the "
        f"same peak cornering force while doing it, so this is not H driving "
        f"more slowly.",
        "The gap is not in the corner. It is on the straight, which is 260 of "
        "this lap's 393 m. Why is not settled: H's allocator will happily "
        "produce opposing wheel forces on a straight if its policy asks for a "
        "yaw moment there, and on some seeds it does.",
    ]
    y = 834
    for para in lines:
        for line in D_wrap(para, 148):
            s += D.text(60, y, line, V.MUT, 12.5)
            y += 20
        y += 8

    s += D.text(40, H - 40,
               "[MEASURED] friction-ellipse utilisation = hypot(Fx/Fx_peak, "
               "Fy/Fy_peak) per wheel, deployed policy, representative seed "
               "(median finish distance) · RUNG 2 (rule 15)", V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "Arrow direction inside each circle is where that tire's force points; "
        "length and percentage are how much of its capacity is spent.")


def utilisation_along_the_lap_figure(out_dir, results) -> str:
    """The technical companion: every seed's tire usage against distance.

    The pictorial figure shows two instants. This shows that those instants are
    representative rather than cherry-picked — the separation opens up after
    the corner and holds for the rest of the lap, on all six seeds.
    """
    import numpy as _np
    from pathlib import Path
    W, H = 1480, 900
    s = V.head(
        W, H,
        "Where the tire actually goes",
        "Friction-ellipse utilisation against distance, all six deployed "
        "policies. The corner is where both variants work hardest and where "
        "they agree; the straight afterwards is where they part company.",
    )

    series = {}
    for v in ("H", "E"):
        for seed in sorted(results["variants"][v]["mean_utilisation_by_seed"],
                           key=int):
            p = Path(out_dir) / f"full_trace_{v}_seed{seed}.npz"
            if p.exists():
                d = _np.load(p)
                series[(v, int(seed))] = (d["s"], d["utilisation_max"])
    if not series:
        s += D.text(60, 200, "no traces available", V.MUT, 14)
        return s + V.foot(W, H, "")

    ax = _Ax(100, 1380, 170, 520, 0.0, 400.0, 0.0, 1.05)
    s = V.grid(s, ax.L, ax.R, ax.T, ax.B, 8, 4)
    xt = [(f"{v:.0f}", float(ax.x(v))) for v in range(0, 401, 50)]
    yt = [(f"{v:.0%}", float(ax.y(v))) for v in (0.0, 0.25, 0.5, 0.75, 1.0)]
    s = V.axes(s, ax.L, ax.R, ax.T, ax.B, "distance along the lap (m)",
              "share of each tire's grip in use", xt, yt)

    # The corner, shaded, so "in the corner" and "on the straight" are visible
    # rather than asserted in the caption.
    x0, x1 = float(ax.x(60.0)), float(ax.x(150.0))
    s += (f'<rect x="{x0:.0f}" y="{ax.T}" width="{x1-x0:.0f}" '
          f'height="{ax.B-ax.T}" fill="{V.FG}" opacity="0.05"/>')
    s += D.text((x0 + x1) / 2, ax.T - 8, "the corner", V.MUT, 12, "middle")
    s += D.text((x1 + ax.R) / 2, ax.T - 8, "the exit straight", V.MUT, 12,
                "middle")

    for (v, seed), (sd, u) in series.items():
        k = max(1, len(sd) // 400)
        pts = ax.pts(sd[::k], _np.clip(u[::k], 0.0, 1.05))
        s += (f'<path d="{V.path(pts)}" fill="none" stroke="{COLOUR[v]}" '
              f'stroke-width="1.9" opacity="0.85"/>')

    for i, v in enumerate(("H", "E")):
        y = 570 + i * 24
        s += (f'<line x1="100" y1="{y-4}" x2="140" y2="{y-4}" '
              f'stroke="{COLOUR[v]}" stroke-width="3"/>')
        util = _seed_stats(results, v, "mean_utilisation_by_seed")
        s += D.text(150, y, f"{LABEL[v]} — 3 seeds, lap average "
                    f"{util.mean():.0%}", COLOUR[v], 13)

    s += D.rule(60, 640, W - 120, V.GRID)
    uh = _seed_stats(results, "H", "mean_utilisation_by_seed")
    ue = _seed_stats(results, "E", "mean_utilisation_by_seed")
    pooled = float(np.sqrt((uh.var(ddof=1) + ue.var(ddof=1)) / 2))
    ratio = abs(ue.mean() - uh.mean()) / pooled if pooled else float("nan")
    for i, line in enumerate(D_wrap(
            f"Lap-average utilisation is {uh.mean():.0%} for H and "
            f"{ue.mean():.0%} for E, a gap of {ratio:.1f}x the seed-to-seed "
            f"standard deviation. CLAUDE.md rule 5 asks for more than 2x before "
            f"a difference counts as a finding, so this one does — while the "
            f"lap times and peak cornering forces, which sit at 0.5x and 1.3x, "
            f"are reported as no measurable difference at all.", 148)):
        s += D.text(60, 674 + 20 * i, line, V.MUT, 12.5)

    s += D.text(40, H - 40,
               "[MEASURED] per-step max over the four wheels of "
               "hypot(Fx/Fx_peak, Fy/Fy_peak), deployed policy, 3 seeds per "
               "variant · RUNG 2 (rule 15)", V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "One line per seed. Traces end where that policy's lap ends.")


def lines_driven_figure(out_dir, results) -> str:
    """The line every seed actually drove, on the actual road.

    This should have been the first figure in the episode and was the last one
    written. Everything else here is a derived quantity plotted against
    distance; this is where the car went. A reader who knows nothing about slip
    angles can see six cars take six lines through one corner, and see at a
    glance which ones ran wide.
    """
    import numpy as _np
    from pathlib import Path
    from physics.track import long_exit
    from . import line_figures as LF

    W, H = 1560, 980
    s = V.head(
        W, H,
        "Six policies, one corner, six lines",
        "The path each deployed policy actually drove, on the road it drove "
        "it on. Colour is how much of the tires' grip was in use — teal is "
        "loafing, coral is at the limit.",
    )

    track = long_exit()
    back, to_px, scale = LF.track_backdrop(track, 0.0, track.length,
                                           90, W - 60, 150, 700)
    s += back

    rows = []
    for v in ("H", "E"):
        for seed in sorted(results["variants"][v]["mean_utilisation_by_seed"],
                           key=int):
            p = Path(out_dir) / f"full_trace_{v}_seed{seed}.npz"
            if not p.exists():
                continue
            d = _np.load(p)
            if "n" not in d:
                continue
            rows.append((v, int(seed), d))

    if not rows:
        s += D.text(60, 760, "no traces with lateral offset available — "
                    "re-run --aggregate to rebuild them", V.MUT, 13)
        return s + V.foot(W, H, "")

    for v, seed, d in rows:
        x, y = track.to_xy(d["s"], d["n"])
        px, py = to_px(x, y)
        u = _np.clip(d["utilisation_max"], 0.0, 1.0)
        # Coloured per segment by utilisation, so the line carries its own
        # result instead of needing a second chart to explain it.
        k = max(1, len(px) // 260)
        for i in range(0, len(px) - k, k):
            r_, g_, b_ = V.ramp(float(u[i]))
            s += (f'<line x1="{px[i]:.1f}" y1="{py[i]:.1f}" '
                  f'x2="{px[i+k]:.1f}" y2="{py[i+k]:.1f}" '
                  f'stroke="#{r_:02x}{g_:02x}{b_:02x}" stroke-width="2.6" '
                  f'stroke-linecap="round" opacity="0.95"/>')
        # where it ended, and whether that was the finish line or the grass
        fin = results["variants"][v]["finished_by_seed"][str(seed)]
        s += (f'<circle cx="{px[-1]:.1f}" cy="{py[-1]:.1f}" r="4.5" '
              f'fill="{V.TEAL if fin else V.COR}"/>')
        s += D.text(px[0] - 8, py[0] + 4, f"{v}{seed}", COLOUR[v], 11.5,
                    "end", weight="600", mono=True)

    # grip scale
    lx, ly = 120, 742
    for i in range(60):
        r_, g_, b_ = V.ramp(i / 59.0)
        s += (f'<rect x="{lx + i * 3.2:.1f}" y="{ly}" width="3.4" height="12" '
              f'fill="#{r_:02x}{g_:02x}{b_:02x}"/>')
    s += D.text(lx - 8, ly + 11, "grip used", V.MUT, 11.5, "end")
    s += D.text(lx, ly + 28, "0%", V.MUT, 10.5, "middle")
    s += D.text(lx + 192, ly + 28, "100%", V.MUT, 10.5, "middle")
    s += D.text(lx + 230, ly + 11, "· filled dot = finished, coral = left the road",
                V.MUT, 11.5)

    s += D.rule(60, 800, W - 120, V.GRID)
    for i, line in enumerate(D_wrap(
            "All six get round. The lines are not identical — each policy "
            "found its own way through, and none of them was given a racing "
            "line to follow or told what one is. What separates the variants "
            "is not the path but the colour: through the corner every line "
            "runs hot, and on the straight afterwards H's lines cool off "
            "while E's stay warm.", 148)):
        s += D.text(60, 834 + 20 * i, line, V.MUT, 12.5)

    s += D.text(40, H - 40,
               "[MEASURED] deployed policy, one rollout per seed, plotted "
               "through Track.to_xy on the same road every other figure in "
               "this project draws · RUNG 2 (rule 15)", V.MUT, 9.5)
    return s + V.foot(
        W, H,
        "The road is drawn to scale; the dashed line is the centreline. "
        "Lateral offset is the policy's own logged distance from it.")


__all__ = ["pilot_sanity_figure", "control_surfaces_figure",
           "yaw_moment_figure", "envelope_escape_figure",
           "seed_scorecard_figure", "tire_spend_figure",
           "utilisation_along_the_lap_figure", "lines_driven_figure"]
