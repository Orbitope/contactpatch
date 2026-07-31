"""Real circuits, fetched rather than vendored (TRACKS.md staging step 3).

TUM's ``racetrack-database`` (LGPL-3.0) publishes centreline coordinates for
25 real circuits, derived from OpenStreetMap (ODbL, share-alike). Vendoring
the CSVs would mean carrying a share-alike-encumbered file inside this
repository's own licence; TRACKS.md's own licensing survey (§3) recommends
against that. Instead: this module downloads the CSV on first use, caches it
locally (``physics/tracks_cache/``, git-ignored — see ``.gitignore`` for why),
and only our own converter code is ever committed.

Data source: <https://github.com/TUMFTM/racetrack-database>, LGPL-3.0,
derived from OpenStreetMap (© OpenStreetMap contributors, ODbL). Circuit
silhouettes are separately trademarked by their operators (TRACKS.md §3) —
this project uses the geometry for physics, not to reproduce or sell a
depiction of the circuit.
"""

from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path

import numpy as np

from physics.track import SampledTrack

_BASE_URL = "https://raw.githubusercontent.com/TUMFTM/racetrack-database/master/tracks"
_CACHE_DIR = Path(__file__).parent / "tracks_cache"


def download_track_csv(name: str, cache_dir: Path | None = None,
                       timeout: float = 15.0) -> Path:
    """Fetch ``{name}.csv`` from TUM's racetrack-database, caching locally.

    Returns the cached path without re-fetching if it already exists — this
    module is meant to be called from tests and experiments repeatedly, not
    just once, and TUM's data does not change under us.
    """
    cache_dir = cache_dir or _CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{name}.csv"
    if path.exists():
        return path
    url = f"{_BASE_URL}/{name}.csv"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read()
    path.write_bytes(data)
    return path


#: Default `smoothing` for `load_real_track`. **Measured on Spa, not assumed
#: from TUM's own description.** Exact interpolation (`smoothing=0.0`) looked
#: like the right call going in -- TUM's centreline is a processed racing
#: surface, not raw noisy GPS -- but it produced a minimum radius of 5.8 m,
#: tighter than any real corner on the circuit, because 5 m point spacing
#: still carries enough residual irregularity for an exact-interpolating
#: spline to fit as a spurious sharp wiggle rather than smooth it away. A
#: sweep from 0 to 1401 (TRACKS.md's own step-1 `s ~= m` convention) found
#: `length` within 0.05-0.25% of the published 7.004 km throughout, and
#: recovered minimum radius stabilises to a physically plausible 9-11.5 m
#: for `10 <= smoothing <= 300` -- this value sits inside that plateau.
#: `s ~= m` (1401) is too much here: it washes the corner down to 9.9 m at a
#: DIFFERENT location than the lighter values agree on, and pulls `length`
#: to the sweep's worst match (-0.24%). Step 1's synthetic test had ~0.1 m
#: point spacing and i.i.d. noise; Spa's real data has ~5 m spacing and
#: already-processed centreline, so the same formula does not transfer, and
#: this project's own rule 9 is the reason to measure rather than reuse it.
DEFAULT_SMOOTHING = 20.0


def load_real_track(name: str, cache_dir: Path | None = None,
                    smoothing: float | None = None,
                    n_resample: int = 4000) -> SampledTrack:
    """Real circuit -> ``SampledTrack``, downloading via ``download_track_csv``.

    ``smoothing``: see ``DEFAULT_SMOOTHING``'s comment for the measurement
    behind the default. Pass a specific value to override it; there is no
    single number this project can defend as universally correct across
    circuits, only one measured against Spa and left as the starting point.

    **Width collapse is a modelling choice, recorded here rather than
    hidden**: TUM's ``w_tr_right_m``/``w_tr_left_m`` are asymmetric about the
    centreline (their own README: the smoothed centreline "does not lie
    perfectly in the middle of the track anymore"); this collapses them to
    one symmetric ``half_width(s) = (right + left) / 2``, per TRACKS.md §3's
    "two things to record when adopted."
    """
    path = download_track_csv(name, cache_dir=cache_dir)
    x, y, w_right, w_left = [], [], [], []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if not row or row[0].startswith("#"):
                continue
            xi, yi, wr, wl = (float(v) for v in row)
            x.append(xi)
            y.append(yi)
            w_right.append(wr)
            w_left.append(wl)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    half_width = (np.asarray(w_right, dtype=float)
                 + np.asarray(w_left, dtype=float)) / 2.0

    return SampledTrack(
        name, x, y, half_width=float(np.mean(half_width)),
        closed=True,
        smoothing=(DEFAULT_SMOOTHING if smoothing is None else smoothing),
        n_resample=n_resample, width=half_width,
        description=f"Imported from TUMFTM/racetrack-database ({name}.csv), "
                    f"LGPL-3.0, derived from OpenStreetMap (ODbL).")


__all__ = ["download_track_csv", "load_real_track"]
