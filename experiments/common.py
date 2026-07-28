"""Shared plumbing for per-episode experiments.

Each episode owns a directory under ``experiments/epNN/`` holding the code that
produced its figures and the figures themselves. That is deliberate duplication:
the diagnostics regenerate their own copies whenever the physics changes, but a
published episode must stay reproducible exactly as published. Episode 15
re-runs Episode 6's and 7's sweeps with torque vectoring on, and the difference
between that being an afternoon and a rebuild is whether the original run script
still exists and still runs.

Usage::

    from experiments.common import episode_dir, write

    out = episode_dir(1)
    write(out / "01-slip-angle.svg", svg)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def episode_dir(n: int) -> Path:
    """``experiments/epNN/out/``, created if needed."""
    d = ROOT / "experiments" / f"ep{n:02d}" / "out"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write(path: Path, svg: str) -> Path:
    path.write_text(svg)
    print(f"  {path.relative_to(ROOT)}")
    return path


__all__ = ["ROOT", "episode_dir", "write"]
