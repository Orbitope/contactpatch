"""Episode 11's figure builders, exercised against a synthetic results dict.

These caught two real defects before the 40-minute sweep that feeds them had
finished: a NaN in-fit failure rate formatting itself onto the page as "nan%" in two
different places. The expensive experiment is not a test harness — the figures have
to be checkable without it.

The synthetic dict deliberately includes the awkward cell: a design with no
unperturbed lap time AND no laps left inside the tire fit, so every fallback path
is taken.
"""

from __future__ import annotations

import numpy as np
import pytest

from viz import fragility_figures as F


@pytest.fixture
def synthetic():
    fr = [0.40, 0.47, 0.54, 0.61, 0.65]
    conds = [("nominal",0,0),("steer",.15,0),("grip",0,.20),("both",.15,.20),("beyond",.25,.30)]
    cells = {}
    for cn, sn, gs in conds:
        for i, f in enumerate(fr):
            fail = 1.0 if f == 0.40 else max(0.0, 0.22 - 0.06*i)
            nanit = (f == 0.40)
            cells[f"{cn}|{f:.2f}"] = {
                "n":40,"n_finished":30,"finish_rate":1-fail,
                "finish_rate_ci95":[max(0,1-fail-.1),min(1,1-fail+.1)],"failure_rate":fail,
                "lap_time_mean": float("nan") if nanit else 19.1+0.3*i,"lap_time_std":0.2,
                "progress_rate_mean":18.0,"distance_mean":390.0,"worst_slip_deg":15.0,
                "median_worst_slip_deg":8.0,"envelope_exceeded_fraction":0.15,
                "n_inside_fit": 0 if nanit else 34,"inside_fit_fraction":0.0 if nanit else 0.85,
                "failures_inside_fit":3,
                "failure_rate_inside_fit": float("nan") if nanit else max(0.0,0.22-0.06*i),
                "failure_rate_inside_fit_ci95":[0.05,0.40],"discarded_laps":6,
                "discarded_failures":2,"failure_rate_is_lower_bound":True,
                "per_lap_finished":[True]*30+[False]*10,"per_lap_worst_slip_deg":[8.0]*40}
    res = {"policy":"experiments/ep10/out/policy.pt","trained_here":False,"n_trials":40,
     "jitter_m":8.0,"steer_noise":0.15,"grip_spread":0.20,"envelope_penalty":0.5,
     "fractions":fr,
     "conditions":[{"name":c,"steer_noise":s,"grip_spread":g,"description":f"{c} desc"} for c,s,g in conds],
     "cells":cells,
     "speed_nominal_s":{f"{f:.2f}":(float("nan") if f==0.40 else 19.1+0.3*i) for i,f in enumerate(fr)},
     "failure_rate_perturbed":{f"{f:.2f}":0.2-0.04*i for i,f in enumerate(fr)},
     "failure_rate_inside_fit_both":{f"{f:.2f}":(float("nan") if f==0.40 else max(0.0,0.22-0.06*i)) for i,f in enumerate(fr)},
     "failure_rate_inside_fit_steer":{f"{f:.2f}":0.05 for f in fr},
     "failure_rate_beyond_envelope":{f"{f:.2f}":0.3 for f in fr},
     "lap_spread_perturbed_s":{f"{f:.2f}":0.27 for f in fr},
     "ranked_fastest_first":[f"{f:.2f}" for f in fr[1:]],
     "quotable_conditions":["nominal","steer","grip","both"]}
    traces = {}
    for cn,_,_ in conds:
        for f in fr:
            for k in range(8):
                t=f"{cn}_{f'{f:.2f}'.replace('.','')}_{k}"
                traces[f"{t}_s"]=np.linspace(0,200,300); traces[f"{t}_n"]=np.zeros(300)
                traces[f"{t}_speed"]=np.full(300,19.0); traces[f"{t}_alpha_max_deg"]=np.full(300,7.0)
                traces[f"{t}_finished"]=np.array([1.0 if k%3 else 0.0])
    return res, traces


def _clean(svg: str, name: str) -> None:
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    # Markdown emphasis is not a thing in SVG text; it has leaked before.
    assert "**" not in svg, f"{name}: literal ** in SVG text"
    # A NaN that reaches the page renders as "nan%" and reads as a real value.
    assert "nan" not in svg.lower().replace("</svg>", ""), f"{name}: NaN on the page"


def test_fragility_paths_renders_with_an_all_discarded_design(synthetic):
    res, traces = synthetic
    _clean(F.fragility_paths(res, traces), "fragility_paths")


def test_pareto_figure_renders_with_an_unplottable_design(synthetic):
    res, _ = synthetic
    _clean(F.pareto_figure(res), "pareto_figure")


def test_condition_card_renders(synthetic):
    res, _ = synthetic
    _clean(F.condition_card(res), "condition_card")


def test_the_pareto_chart_plots_the_in_fit_rate_not_the_all_laps_rate(synthetic):
    """The two differ, and plotting the wrong one puts crashes that happened at
    20 degrees of slip onto a chart that is supposed to be about cars."""
    res, _ = synthetic
    res["failure_rate_inside_fit_both"]["0.54"] = 0.11
    res["failure_rate_perturbed"]["0.54"] = 0.99
    svg = F.pareto_figure(res)
    assert "11%" in svg and "99%" not in svg
