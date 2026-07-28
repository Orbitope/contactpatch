"""Every generated figure must be well-formed XML.

A bare ``<`` or ``&`` in a caption produces a file that renders as a parse error
instead of a figure, and nothing else in the pipeline notices: the SVG is
written, the diagnostic passes, and the breakage only shows when a human opens
it. Figures are deliverables (CLAUDE.md rule 1), so they get tested like one.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from viz import diagram as D

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "diagnostics" / "out"
EPISODES = ROOT / "episodes"


def _figures():
    """Every generated SVG, diagnostics AND per-episode experiment output.

    This used to glob only ``diagnostics/out``, which meant the figures that
    actually ship inside the articles were never parsed. The episode figures are
    the deliverable; the diagnostic copies are the ones that could be skipped.
    """
    return sorted(OUT.glob("*.svg")) + sorted(ROOT.glob("experiments/*/out/*.svg"))


def test_some_figures_exist():
    assert _figures(), "run the diagnostics first: python -m diagnostics.D1_tire_card"


# ---------------------------------------------------------------------------
# Article figure links
# ---------------------------------------------------------------------------

def _episode_figure_links():
    """Every ``![alt](path)`` in an episode draft, as (article, resolved path)."""
    out = []
    for md in sorted(EPISODES.glob("*.md")):
        for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", md.read_text()):
            out.append((md.name, (md.parent / m.group(1)).resolve()))
    return out


def test_episodes_reference_some_figures():
    assert _episode_figure_links(), "no figures embedded in any episode draft"


@pytest.mark.parametrize("article,path", _episode_figure_links(),
                         ids=lambda v: v if isinstance(v, str) else v.name)
def test_every_figure_an_episode_embeds_actually_exists(article, path):
    """A renumbered figure leaves a dead image in a published article.

    Renumbering Episode 5's figures from two to five broke its existing links,
    and nothing anywhere noticed: the run script succeeded, the tests passed, and
    the article rendered with a missing image. Cheap check, real defect class.
    """
    assert path.is_file(), f"{article} embeds {path.name}, which does not exist"


@pytest.mark.parametrize("path", _figures(), ids=lambda p: p.name)
def test_figure_is_wellformed_xml(path):
    ET.parse(path)


@pytest.mark.parametrize("path", _figures(), ids=lambda p: p.name)
def test_figure_carries_a_provenance_stamp(path):
    """CLAUDE.md rule 3: every number quoted anywhere carries a provenance tag."""
    body = path.read_text()
    assert any(tag in body for tag in ("[MEASURED]", "[SOURCED]", "[DERIVED]")), (
        f"{path.name} has no provenance tag"
    )


@pytest.mark.parametrize("path", _figures(), ids=lambda p: p.name)
def test_figure_has_a_title(path):
    root = ET.parse(path).getroot()
    texts = [e.text for e in root.iter() if e.tag.endswith("text") and e.text]
    assert texts and len(texts[0]) > 5


# ---------------------------------------------------------------------------
# Frame conversions
# ---------------------------------------------------------------------------
# These are the silent-failure class: a wrong sign renders a plausible picture
# of a car doing something it never did, and no test downstream notices. Every
# one of them has been wrong at least once, so each gets pinned by a check that
# works the geometry rather than restating the formula.

def _rotate(a_deg, x, y):
    """What SVG's ``rotate(a)`` does to a vector, about the origin."""
    a = math.radians(a_deg)
    return (x * math.cos(a) - y * math.sin(a),
            x * math.sin(a) + y * math.cos(a))


@pytest.mark.parametrize("theta", [0.0, 30.0, 45.0, 90.0, 135.0, 180.0, -60.0])
def test_car_heading_rotation_points_the_nose_along_travel(theta):
    """The nose must end up pointing where the car is going.

    ``car_plan`` at rotation 0 draws the nose at local ``(0, -1)``. A plan view
    maps track +x to screen right and track +y to screen UP, so a car on track
    heading ``theta`` travels screen ``(cos theta, -sin theta)``. Rotating the
    nose by the converter's answer must land on that direction.

    Worked from the geometry, not from ``90 - theta``: the previous converter
    was out by exactly 180 degrees for every heading and passed visual review,
    because a car outline is nearly symmetric.
    """
    nx, ny = _rotate(D.screen_heading_deg(theta), 0.0, -1.0)
    tx, ty = math.cos(math.radians(theta)), -math.sin(math.radians(theta))
    assert nx == pytest.approx(tx, abs=1e-9)
    assert ny == pytest.approx(ty, abs=1e-9)


def test_a_left_turn_steers_the_wheels_toward_the_inside_of_the_corner():
    """ISO positive steer is LEFT, and left is screen-left on a nose-up car."""
    # local frame, nose up: rotating the wheel by screen_deg(+delta) must move
    # its leading edge to negative x (screen-left)
    lead_x, lead_y = _rotate(D.screen_deg(10.0), 0.0, -1.0)
    assert lead_x < 0.0, "a left steer must point the wheel screen-left"
    assert lead_y < 0.0, "...while still pointing mostly forwards"
    # and the mirror case
    assert _rotate(D.screen_deg(-10.0), 0.0, -1.0)[0] > 0.0


def test_iso_lateral_maps_to_screen_left():
    assert D.screen_dx(1.0) < 0.0
    assert D.screen_deg(1.0) < 0.0


@pytest.mark.parametrize("path", _figures(), ids=lambda p: p.name)
def test_no_markdown_leaks_into_svg_text(path):
    """SVG renders no markdown, so `**bold**` appears as literal asterisks.

    Figure captions are written in the same voice as the articles, so the habit
    follows them across — and it renders as visible `**` in a published figure.
    Caught by eye in Episode 9 after every other check passed: the file is valid
    XML, carries a provenance stamp, and has a title.
    """
    root = ET.parse(path).getroot()
    bad = [e.text for e in root.iter()
           if e.tag.endswith("text") and e.text and "**" in e.text]
    assert not bad, f"{path.name} renders literal markdown: {bad[0][:70]!r}"
