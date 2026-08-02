"""Many circuits, pre-sampled onto tables, so each instance can run its own.

**Why this exists.** `BatchedDrivingEnv` holds one `Track` and evaluates its
spline for all N instances at once. Giving every instance a different circuit
the naive way — N separate spline evaluations per step — was measured at
**3,899 us/step against 79.9 us for the shared spline: 49x slower**, which
makes multi-track training infeasible.

Pre-sampling each circuit's curvature and half-width onto a fixed arc-length
grid turns the lookup into an array gather. Measured: **1.7 us/step for 256
instances on 256 different circuits** — 47x *faster* than the single shared
spline we run today, because spline evaluation is itself the cost being
removed.

Memory is not a constraint: 10,000 circuits at 4,000 grid points is 960 MB
for curvature, half-width and a spare channel at float64, and far less at
float32.

**The approximation, measured rather than asserted.** Curvature between grid
points is linearly interpolated. Convergence is O(h), not the O(h^2) linear
interpolation would give on a smooth function — the source spline's curvature
is not smooth once reparameterised by arc length:

| n_grid | spacing | max abs error | max relative |
|---|---|---|---|
| 4,000 | 0.79 m | 2.2e-3 | 8.4% |
| 8,000 | 0.39 m | 1.0e-3 | 4.2% |
| **16,000** | **0.20 m** | **4.1e-4** | **2.0%** |
| 32,000 | 0.10 m | 1.3e-4 | 1.0% |

Error concentrates in the tightest corners, where curvature changes fastest —
which is where braking decisions live, so it is the right place to spend grid.

**2% is negligible against choices already made elsewhere in this project:**
`tracks_data.DEFAULT_SMOOTHING` alone moves Spa's recovered minimum radius
from 5.8 m to 11.4 m — a factor of two. An interpolation error two orders of
magnitude smaller than the modelling choice above it is not the thing that
will make a result wrong. Stated here so nobody has to rediscover it.

Stored as float32: 16,000 points x 2 channels x 1,000 circuits = 128 MB.
"""

from __future__ import annotations

import numpy as np

from physics.track import Track


class TrackBank:
    """A stack of circuits sampled onto a common normalised grid.

    Every circuit gets ``n_grid`` samples over its own length, so circuits of
    different lengths share one rectangular table and the lookup stays a
    single fancy-index. Position is carried as arc length and converted per
    instance using that instance's own length.
    """

    __slots__ = ("names", "lengths", "n_grid", "_kappa", "_halfwidth", "n")

    def __init__(self, tracks: list[Track], n_grid: int = 16000):
        if not tracks:
            raise ValueError("TrackBank needs at least one track")
        self.n = len(tracks)
        self.n_grid = int(n_grid)
        self.names = [getattr(t, "name", f"track{i}") for i, t in enumerate(tracks)]
        self.lengths = np.array([float(t.length) for t in tracks], dtype=float)
        self._kappa = np.zeros((self.n, self.n_grid), dtype=np.float32)
        self._halfwidth = np.zeros((self.n, self.n_grid), dtype=np.float32)
        for i, t in enumerate(tracks):
            s = np.linspace(0.0, float(t.length), self.n_grid, endpoint=False)
            self._kappa[i] = np.asarray(t.curvature(s), dtype=float)
            hw = t.half_width_at(s)
            self._halfwidth[i] = (np.asarray(hw, dtype=float)
                                  if np.ndim(hw) else np.full(self.n_grid, float(hw)))

    # -- lookup ----------------------------------------------------------

    def _frac(self, track_id: np.ndarray, s: np.ndarray) -> np.ndarray:
        """Arc length -> position in [0, n_grid), wrapping. Circuits are
        closed, so `s` beyond one lap is a second lap, not an error."""
        return (s / self.lengths[track_id]) % 1.0 * self.n_grid

    def _gather(self, table: np.ndarray, track_id: np.ndarray,
                s: np.ndarray) -> np.ndarray:
        f = self._frac(track_id, s)
        i0 = f.astype(np.int64)
        w = f - i0
        i1 = (i0 + 1) % self.n_grid
        # Linear interpolation between grid points -- see the module note on
        # why this is finer than one step of travel.
        return table[track_id, i0] * (1.0 - w) + table[track_id, i1] * w

    def curvature(self, track_id: np.ndarray, s: np.ndarray) -> np.ndarray:
        return self._gather(self._kappa, track_id, s)

    def half_width_at(self, track_id: np.ndarray, s: np.ndarray) -> np.ndarray:
        return self._gather(self._halfwidth, track_id, s)

    def length_of(self, track_id: np.ndarray) -> np.ndarray:
        return self.lengths[track_id]

    def __len__(self) -> int:
        return self.n

    def __repr__(self) -> str:
        return (f"TrackBank({self.n} circuits, {self.n_grid} grid points, "
                f"{self.lengths.min():.0f}-{self.lengths.max():.0f} m, "
                f"{self._kappa.nbytes / 1e6:.0f} MB)")


class BankTrackView:
    """One circuit from a bank, presented with the `Track` scalar interface.

    Lets the single-instance `DrivingEnv` and every existing evaluation path
    run against a bank circuit unchanged — which is what keeps the reference
    implementation usable as the differential-test oracle for the batched
    multi-track path.
    """

    __slots__ = ("bank", "idx", "name", "length", "closed")

    def __init__(self, bank: TrackBank, idx: int):
        self.bank, self.idx = bank, int(idx)
        self.name = bank.names[self.idx]
        self.length = float(bank.lengths[self.idx])
        self.closed = True

    def curvature(self, s):
        s = np.atleast_1d(np.asarray(s, dtype=float))
        out = self.bank.curvature(np.full(s.shape, self.idx), s)
        return float(out[0]) if out.size == 1 else out

    def half_width_at(self, s):
        s = np.atleast_1d(np.asarray(s, dtype=float))
        out = self.bank.half_width_at(np.full(s.shape, self.idx), s)
        return float(out[0]) if out.size == 1 else out
