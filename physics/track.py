"""Track geometry as curvature against distance.

A track is a centreline plus a width. The centreline is described by its
**curvature** ``kappa(s)`` as a function of distance along it, which is all the
distance-domain optimal control needs: integrate curvature to get heading,
integrate heading to get position, and the optimiser never has to reason about
Cartesian coordinates at all.

Episode 4 needs exactly one corner, twice: once followed by a short straight and
once by a long one. Nothing here is a real circuit — that arrives with the
lap-time work in Season 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Segment:
    """One piece of centreline. ``radius=None`` means straight."""

    length: float
    radius: float | None = None

    @property
    def curvature(self) -> float:
        return 0.0 if self.radius is None else 1.0 / self.radius


@dataclass
class Track:
    """A centreline built from segments, plus a usable width.

    ``half_width`` is how far the car's centre of mass may sit from the
    centreline. It is the track half-width minus half the car's width, so the
    car stays on the road rather than its centreline doing so — a distinction
    worth 0.9 m on a 3.5 m lane and therefore worth being explicit about.
    """

    name: str
    segments: list[Segment]
    half_width: float
    #: Curvature is blended over this distance at each segment join. A real
    #: corner has a transition; a step change in curvature would ask the car for
    #: an infinite steering rate and the solver would smear it out anyway, but
    #: less predictably.
    blend: float = 4.0
    description: str = ""
    _edges: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        assert self.segments, "a track needs at least one segment"
        assert self.half_width > 0
        self._edges = np.concatenate(
            [[0.0], np.cumsum([s.length for s in self.segments])])

    @property
    def length(self) -> float:
        return float(self._edges[-1])

    def curvature(self, s):
        """Centreline curvature at distance ``s``, blended across joins.

        Uses ``tanh`` ramps so the result is smooth and differentiable — the
        solver needs a gradient here, and a piecewise-constant curvature has
        none at the joins.
        """
        s = np.asarray(s, dtype=float)
        k = np.full(s.shape, self.segments[0].curvature)
        for i, seg in enumerate(self.segments[1:], start=1):
            edge = self._edges[i]
            prev = self.segments[i - 1].curvature
            ramp = 0.5 * (1.0 + np.tanh((s - edge) / (self.blend / 2.0)))
            k = k + (seg.curvature - prev) * ramp
        return k

    def centreline(self, n_points: int = 600):
        """``(s, x, y, heading)`` of the centreline, for drawing."""
        s = np.linspace(0.0, self.length, n_points)
        k = self.curvature(s)
        heading = np.concatenate([[0.0], np.cumsum(np.diff(s) * k[:-1])])
        x = np.concatenate([[0.0], np.cumsum(np.diff(s) * np.cos(heading[:-1]))])
        y = np.concatenate([[0.0], np.cumsum(np.diff(s) * np.sin(heading[:-1]))])
        return s, x, y, heading

    def to_xy(self, s, n):
        """Curvilinear ``(s, n)`` -> Cartesian ``(x, y)``, for drawing a line."""
        s_ref, x_ref, y_ref, h_ref = self.centreline(2000)
        x0 = np.interp(s, s_ref, x_ref)
        y0 = np.interp(s, s_ref, y_ref)
        h = np.interp(s, s_ref, h_ref)
        # +n is to the left of the direction of travel, matching schema's frame
        return x0 - n * np.sin(h), y0 + n * np.cos(h)


# ---------------------------------------------------------------------------
# Episode 4's two corners
# ---------------------------------------------------------------------------

#: Approach, one 40 m-radius left-hander of 90 degrees, exit. Two versions,
#: differing only in how much straight follows. All dimensions [ASSUMED] — this
#: is a made-up corner chosen to be readable, not a real one.
CORNER_RADIUS = 40.0
ENTRY_STRAIGHT = 70.0
CORNER_ARC = 0.5 * np.pi * CORNER_RADIUS      # 90 degrees
HALF_WIDTH = 4.0                              # m from the centreline [ASSUMED]


def short_exit() -> Track:
    return Track(
        name="short exit",
        segments=[Segment(ENTRY_STRAIGHT), Segment(CORNER_ARC, CORNER_RADIUS),
                  Segment(30.0)],
        half_width=HALF_WIDTH,
        description="90 deg corner with 30 m of straight after it",
    )


def long_exit() -> Track:
    return Track(
        name="long exit",
        segments=[Segment(ENTRY_STRAIGHT), Segment(CORNER_ARC, CORNER_RADIUS),
                  Segment(260.0)],
        half_width=HALF_WIDTH,
        description="the same corner with 260 m of straight after it",
    )


__all__ = ["Segment", "Track", "short_exit", "long_exit",
           "CORNER_RADIUS", "ENTRY_STRAIGHT", "CORNER_ARC", "HALF_WIDTH"]
