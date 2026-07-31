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
from scipy.interpolate import splev, splprep


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
        """``(s, x, y, heading)`` of the centreline, for drawing.

        Integrated by the trapezoid and midpoint rules rather than by left
        endpoints, so the geometry does not depend on ``n_points``. It used to:
        the left-endpoint sum put the 2000-point centreline **0.098 m** to one side
        of the 4000-point one by the corner exit, and kept it there for the rest of
        the track. Nothing physical reads this function — it is the drawing map and
        the driver's idea of where the road is — but two pieces of code that
        disagree about where the centreline runs by a tenth of a metre is exactly
        the silent-frame-error family this project keeps paying for (F36), and it
        showed up as a 5% error in a lateral offset the first time two of them were
        compared. See FINDINGS F81.
        """
        s = np.linspace(0.0, self.length, n_points)
        ds = np.diff(s)
        k = np.asarray(self.curvature(s), dtype=float)
        heading = np.concatenate([[0.0], np.cumsum(ds * 0.5 * (k[:-1] + k[1:]))])
        h_mid = 0.5 * (heading[:-1] + heading[1:])
        x = np.concatenate([[0.0], np.cumsum(ds * np.cos(h_mid))])
        y = np.concatenate([[0.0], np.cumsum(ds * np.sin(h_mid))])
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


# ---------------------------------------------------------------------------
# POWER-REVIEW D-D: two more radii, same 90 deg turn and same entry/exit
# straight lengths as ``long_exit``. Radius is deliberately the ONLY thing
# that changes across the three tracks below — a real hairpin usually turns
# through more than 90 deg, but holding the angle fixed isolates radius as the
# single varied quantity rather than mixing radius and angle into one
# comparison. All dimensions [ASSUMED], same as long_exit/short_exit.
# ---------------------------------------------------------------------------

HAIRPIN_RADIUS = 15.0     # second-gear, traction-dominated exit
FAST_SWEEP_RADIUS = 90.0  # lateral-dominated, high commitment


def hairpin() -> Track:
    arc = 0.5 * np.pi * HAIRPIN_RADIUS
    return Track(
        name="hairpin",
        segments=[Segment(ENTRY_STRAIGHT), Segment(arc, HAIRPIN_RADIUS),
                  Segment(260.0)],
        half_width=HALF_WIDTH,
        description="a 15 m-radius 90 deg corner, second-gear and "
                     "traction-dominated on exit",
    )


def fast_sweep() -> Track:
    arc = 0.5 * np.pi * FAST_SWEEP_RADIUS
    return Track(
        name="fast sweep",
        segments=[Segment(ENTRY_STRAIGHT), Segment(arc, FAST_SWEEP_RADIUS),
                  Segment(260.0)],
        half_width=HALF_WIDTH,
        description="a 90 m-radius 90 deg corner, lateral-dominated and "
                     "taken with far less speed lost",
    )


# ---------------------------------------------------------------------------
# TRACKS.md staging step 1: SampledTrack, validated by the round-trip test in
# tests/test_sampled_track.py before any real circuit data touches it.
# ---------------------------------------------------------------------------

class SampledTrack:
    """A centreline given as ``(x, y)`` points, not analytic segments.

    Where ``Track`` composes curvature from named ``Segment``s (exact by
    construction), this recovers curvature from raw coordinates — what a real
    circuit's centreline actually is. **The recovery method is the whole
    subject of TRACKS.md's curvature trap**: naive finite-differencing of even
    clean, evenly-sampled points amplifies noise catastrophically (390x the
    signal, measured, TRACKS.md §2). This class does the thing TRACKS.md
    prescribes instead — periodic cubic-spline fit, arclength
    reparameterisation, analytic curvature from the spline's own derivatives
    — and does not implement the naive version at all, so there is no
    tempting shortcut sitting next to the right answer.

    ``half_width`` is a single scalar here, matching ``Track``'s current
    interface exactly so this is a drop-in wherever a ``Track`` is used.
    Variable width along ``s`` is TRACKS.md staging step 2, deliberately not
    this one.

    ``closed`` defaults to ``True`` because a real circuit is a loop and
    that is the actual target of this class — but the round-trip test
    (``tests/test_sampled_track.py``) validates against ``long_exit``, which
    is deliberately NOT a loop (an open corner: straight, corner, straight,
    start far from the end). Fitting a periodic spline through an open curve
    forces it closed anyway, which does not error — it just fits a curve
    roughly twice the intended length, silently. Caught by the round-trip
    test itself (``length`` came out at ~785 m against a known 393 m, almost
    exactly double) rather than assumed away, which is the entire reason a
    round-trip test against a KNOWN answer is step 1 and not skipped.

    ``smoothing`` (scipy's ``splprep`` ``s``) does not have a good universal
    default and must scale with point count, not be a fixed constant — an
    arbitrary small value (tested: 0.05) recovered curvature *worse* than the
    naive finite-difference trap it exists to beat (err 42 vs. 8.7), while
    scipy's own unweighted-data convention, ``s ~= m`` (the point count),
    matched TRACKS.md's measured "tuned smoothing spline" row almost exactly
    (err 0.015 vs. 0.013). Start from ``s = len(x)`` for noisy real data and
    verify against an independent curvature check (rule 2), same as every
    other number in this project.

    Not CasADi-safe (built on scipy, which has no symbolic/autodiff path) —
    by design, not by oversight. RL training (``physics/rl_env.py``,
    ``physics/batched_env.py``) is pure NumPy and is what this project is
    prioritising (D13); the optimal-control solver needs an analytic
    ``Track`` and was never going to get real-circuit geometry through this
    class regardless.
    """

    def __init__(self, name: str, x, y, half_width: float,
                 blend: float = 4.0, description: str = "",
                 n_resample: int = 4000, smoothing: float = 0.0,
                 closed: bool = True):
        assert half_width > 0
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        assert len(x) == len(y) and len(x) >= 4, \
            "need at least 4 points for a cubic spline"
        self.name = name
        self.half_width = half_width
        self.blend = blend
        self.description = description
        self.closed = closed

        # Parametric cubic spline through the raw points, u in [0, 1].
        # `per=closed`: a real circuit is a loop (the actual target of this
        # class) and must be fit periodically or the join is a kink, not a
        # corner; an open reference track like long_exit must NOT be, or the
        # fit closes a gap that was never there (see the class docstring).
        # `smoothing=0` interpolates exactly (clean synthetic data, e.g. the
        # round-trip test); `smoothing>0` fits through noisy data rather than
        # chasing every sample (TRACKS.md's own measurement: this is what
        # keeps recovered curvature usable against real, noisy survey data).
        self._tck, _ = splprep([x, y], s=smoothing, per=closed, k=3)

        # Arclength reparameterisation: densely resample the fitted spline
        # in u, integrate the chord lengths to get s(u), then invert for
        # u(s). This is the step a naive np.gradient(x, y) skips entirely,
        # and skipping it is the 390x-the-signal trap (TRACKS.md §2).
        u_dense = np.linspace(0.0, 1.0, n_resample, endpoint=not closed)
        xd, yd = splev(u_dense, self._tck)
        if closed:
            # close the loop for the chord-length sum
            xd_c = np.concatenate([xd, xd[:1]])
            yd_c = np.concatenate([yd, yd[:1]])
            chord = np.hypot(np.diff(xd_c), np.diff(yd_c))
            self._u_dense = np.concatenate([u_dense, [1.0]])
        else:
            chord = np.hypot(np.diff(xd), np.diff(yd))
            self._u_dense = u_dense
        s_dense = np.concatenate([[0.0], np.cumsum(chord)])
        self._s_dense = s_dense
        self.length = float(s_dense[-1])

    def _u_of_s(self, s):
        s = np.asarray(s, dtype=float)
        if self.closed:
            s = s % self.length
        else:
            s = np.clip(s, 0.0, self.length)
        return np.interp(s, self._s_dense, self._u_dense)

    def curvature(self, s):
        """Analytic curvature from the spline's own derivatives, not from
        differencing the recovered coordinates a second time."""
        u = self._u_of_s(s)
        dx, dy = splev(u, self._tck, der=1)
        ddx, ddy = splev(u, self._tck, der=2)
        denom = np.power(dx * dx + dy * dy, 1.5)
        return (dx * ddy - dy * ddx) / denom

    def centreline(self, n_points: int = 600):
        """``(s, x, y, heading)`` of the centreline, matching ``Track``'s
        interface. Read directly from the fitted spline (exact), not
        re-integrated from curvature the way ``Track.centreline`` has to —
        ``Track`` has no other source of ``(x, y)``; this class does."""
        s = np.linspace(0.0, self.length, n_points)
        u = self._u_of_s(s)
        x, y = splev(u, self._tck)
        dx, dy = splev(u, self._tck, der=1)
        heading = np.arctan2(dy, dx)
        return s, np.asarray(x), np.asarray(y), heading

    def to_xy(self, s, n):
        """Curvilinear ``(s, n)`` -> Cartesian ``(x, y)``, matching
        ``Track.to_xy``'s convention (+n left of the direction of travel)."""
        s_ref, x_ref, y_ref, h_ref = self.centreline(2000)
        x0 = np.interp(s, s_ref, x_ref)
        y0 = np.interp(s, s_ref, y_ref)
        h = np.interp(s, s_ref, h_ref)
        return x0 - n * np.sin(h), y0 + n * np.cos(h)


__all__ = ["Segment", "Track", "short_exit", "long_exit", "hairpin",
           "fast_sweep", "SampledTrack",
           "CORNER_RADIUS", "ENTRY_STRAIGHT", "CORNER_ARC", "HALF_WIDTH",
           "HAIRPIN_RADIUS", "FAST_SWEEP_RADIUS"]
