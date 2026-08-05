"""Render `viz.morph_animation.frame` to a video — a test of the format.

CLAUDE.md rule 10: figures are parameterised builders so "an animation is a
loop over the same function rather than a rebuild." This is that loop:
rasterise each frame with ``cairosvg`` (the only accurate SVG->PNG path
available here — ``qlmanage`` force-fits everything into a square icon
thumbnail regardless of the source aspect ratio, which would silently
distort every frame) and encode with ``ffmpeg``.

Two cars, same policy, same seed, synchronised by SIMULATION STEP (fixed
dt=0.02, `physics.rl_env.DT`) rather than by distance travelled — so a viewer
sees one car still on the brakes while the other has already turned in,
which is the actual comparison, not a same-arc-length overlay.

    python -m experiments.ep10.render_morph_animation
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import cairosvg
import numpy as np

from physics.track import long_exit
from viz.morph_animation import frame

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "ep10" / "out"
FRAMES = OUT / "morph_frames"

#: Two designs that BOTH finish (f040 does not -- see the first render,
#: `morph_animation_crash.mp4`/`.gif`), so this comparison is about LINE
#: rather than survival: 47% front is the most rear-biased design that still
#: completes the corner, 65% front the most front-biased. Measured apex
#: depth confirms a real, monotonic difference between them, not just a
#: label -- min |n| in the corner window (4 m half-width road):
#:
#:   f047  n=-3.26 m (clips within 0.7 m of the inside edge)
#:   f054  n=-2.48 m
#:   f061  n=-1.79 m
#:   f065  n=-1.38 m (stays 2.6 m off the inside edge)
#:
#: and f047 clears the corner window in 171 steps against f065's 174 -- a
#: real but SMALL gap (3.42 s vs 3.48 s, 1.7%), stated with that caveat
#: rather than as "the rear-biased line is faster": one seed, one corner,
#: and CLAUDE.md rule 5 wants that margin checked against seed variance
#: before it is a finding, not just quoted from a video.
TAGS = ("f047", "f065")
LABELS = ("47% front (rear-biased, deepest apex)",
         "65% front (front-biased, widest line)")
COLOURS = ("#e2614a", "#4aa8a0")
DT = 0.02

#: Both cars are on-track for their full traces (955, 1,005 steps), so the
#: window is the corner itself with margin, not clipped by a crash.
START, END = 60, 460
#: Playback at half the simulation rate (25 fps against a 50 Hz trace) --
#: 2x slow motion, chosen because the interesting divergence happens over
#: ~1-2 s of sim time and real-time playback would make it hard to see on a
#: first look. `python -m ... --fps 50` for real-time.
FPS = 25


def render(start: int = START, end: int = END, fps: int = FPS, tag: str = "morph"):
    """``tag`` names the output files. Fixed filenames plus `ffmpeg -y` is how
    the FIRST render of this session (f040 vs f065, the crash comparison) got
    silently overwritten mid-session -- called once, moved to its permanent
    name only AFTER a second call had already clobbered it with `-y`. Every
    render now owns its own name from the start; nothing to remember to
    rename after the fact."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found — required to encode the video")

    traces = dict(np.load(ROOT / "experiments" / "ep10" / "out" / "traces.npz"))
    track = long_exit()

    FRAMES.mkdir(parents=True, exist_ok=True)
    for f in FRAMES.glob("*.png"):
        f.unlink()

    n = end - start
    print(f"Rendering {n} frames ({start}..{end}, {DT*n:.1f} s of simulated "
         f"time) at {fps} fps ({'%.1f' % (DT*fps)}x speed)")
    t0 = time.time()
    for k, i in enumerate(range(start, end)):
        svg = frame(track, traces, TAGS, LABELS, COLOURS, i, dt=DT)
        cairosvg.svg2png(bytestring=svg.encode(), output_width=1280,
                         output_height=760,
                         write_to=str(FRAMES / f"f{k:05d}.png"))
        if k % 100 == 0:
            print(f"  {k}/{n}", flush=True)
    wall = time.time() - t0
    print(f"  {n} frames in {wall:.1f}s ({1000*wall/n:.0f} ms/frame)")

    out_mp4 = OUT / f"{tag}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", str(FRAMES / "f%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", "scale=1280:760",
        str(out_mp4),
    ], check=True, capture_output=True)
    print(f"  wrote {out_mp4.relative_to(ROOT)}")

    # A GIF too — mp4 needs a video player, a GIF drops straight into a
    # markdown draft or a chat message with no extra step.
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
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else "morph"
    render(tag=tag)
