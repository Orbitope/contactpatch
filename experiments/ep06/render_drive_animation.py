"""Render `viz.drivetrain_animation.frame` to video — FWD vs RWD, one corner.

Standalone rather than sharing code with `experiments/ep10/render_morph_
animation.py`, per `experiments/common.py`'s stated policy: each episode's
driver script is deliberately duplicated so a later episode's changes never
silently alter an earlier one's reproduction. Only `viz/` primitives are
shared.

    python -m experiments.ep06.render_drive_animation
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import cairosvg
import numpy as np

from physics.track import long_exit, ENTRY_STRAIGHT as T_ENTRY, CORNER_ARC as T_ARC
from viz.drivetrain_animation import frame, build_time_grid

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "ep06" / "out"
FRAMES = OUT / "drive_frames"

TAGS = ("rwd", "fwd")
LABELS = ("RWD", "FWD")
COLOURS = ("#e2614a", "#4aa8a0")

#: Measured: both cars enter the corner window at t=1.12s, RWD leaves at
#: t=7.00s, FWD at t=6.97s. Margin on both ends, not the full 12.05 s solve --
#: past this window the cars are back on straight road with nothing left to
#: compare.
T0, T1 = 0.9, 7.2
N_FRAMES = 300
#: 25 fps against ~6.3 s of simulated time is already close to real time
#: (n_frames/fps = 12.0 s of video for 6.3 s of sim -- ~1.9x slow motion).
#: The headline gap here is 33 ms over a 12 s solve (0.27%), far smaller than
#: Episode 10's apex-depth comparison, so LESS slow-motion would hide it
#: entirely and MORE would misrepresent how close this actually is.
FPS = 25


def render(t0: float = T0, t1: float = T1, n_frames: int = N_FRAMES,
          fps: int = FPS, tag: str = "drive_animation"):
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found — required to encode the video")

    tr = dict(np.load(OUT / "traces.npz"))
    track = long_exit()
    s = tr["s"]
    t_nodes = {t: build_time_grid(s, tr[f"{t}_dt_ds"]) for t in TAGS}
    n = {t: tr[f"{t}_n"] for t in TAGS}
    xi = {t: tr[f"{t}_xi"] for t in TAGS}
    window = (T_ENTRY - 34.0, T_ENTRY + T_ARC + 60.0)

    FRAMES.mkdir(parents=True, exist_ok=True)
    for f in FRAMES.glob("*.png"):
        f.unlink()

    print(f"Rendering {n_frames} frames over t={t0:.2f}..{t1:.2f}s "
         f"({(t1-t0)/n_frames*fps:.2f}x speed at {fps} fps)")
    t_start = time.time()
    for k, t in enumerate(np.linspace(t0, t1, n_frames)):
        svg = frame(track, s, t_nodes, n, xi, TAGS, LABELS, COLOURS,
                   float(t), window)
        cairosvg.svg2png(bytestring=svg.encode(), output_width=1280,
                         output_height=760,
                         write_to=str(FRAMES / f"f{k:05d}.png"))
        if k % 100 == 0:
            print(f"  {k}/{n_frames}", flush=True)
    wall = time.time() - t_start
    print(f"  {n_frames} frames in {wall:.1f}s ({1000*wall/n_frames:.0f} ms/frame)")

    out_mp4 = OUT / f"{tag}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", str(FRAMES / "f%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", "scale=1280:760",
        str(out_mp4),
    ], check=True, capture_output=True)
    print(f"  wrote {out_mp4.relative_to(ROOT)}")

    out_gif = OUT / f"{tag}.gif"
    palette = OUT / "_palette.png"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(out_mp4),
        "-vf", "fps=15,scale=720:-1:flags=lanczos,palettegen",
        str(palette),
    ], check=True, capture_output=True)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(out_mp4), "-i", str(palette),
        "-lavfi", "fps=15,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse",
        str(out_gif),
    ], check=True, capture_output=True)
    palette.unlink(missing_ok=True)
    print(f"  wrote {out_gif.relative_to(ROOT)}")

    for f in FRAMES.glob("*.png"):
        f.unlink()
    FRAMES.rmdir()
    return out_mp4, out_gif


if __name__ == "__main__":
    render()
