"""The racing line in real geometry, plus tire forces as world-frame vectors.

The article could describe the line the solver finds but never drew it: the
existing corner widget shows four tires in a fixed box, which is right for
reading percentages and useless for seeing that the car runs to the outside
edge before it turns.

**All frame arithmetic happens here, in Python, through `Track.to_xy` — the
conversion the test suite already pins.** The widget receives world (x, y) and
draws them. This is deliberate: CLAUDE.md's rule about named frame conversions
exists because all three of them have been wrong at least once and every one
failed silently (F36 put a 180 deg-wrong car into a published figure). A second
implementation of the same conversion, in a second language, with no test, is
exactly how that happens again.

    python -m tools.export_racing_line
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from physics import track as T
from physics.schema import VehicleParams

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "linegeom.js"
#: Frames the scrubber steps through. Dense through the corner, sparse down the
#: straight, same reasoning as the wheel widget's focus sampling.
FOCUS_M = 200.0
TAIL_STEP = 3


def _r(a, nd):
    return [round(float(v), nd) for v in np.asarray(a).ravel()]


def main() -> int:
    trk = T.long_exit()
    v = VehicleParams()
    z = np.load(ROOT / "experiments/ep06/out/traces.npz")

    # body-frame wheel offsets: x forward, y left (ISO)
    a = v.wheelbase * (1.0 - v.front_mass_fraction)   # CG to front axle
    b = v.wheelbase * v.front_mass_fraction           # CG to rear axle
    OFF = {"fl": (a, v.track_f / 2), "fr": (a, -v.track_f / 2),
           "rl": (-b, v.track_r / 2), "rr": (-b, -v.track_r / 2)}

    s_ref, x_ref, y_ref, h_ref = trk.centreline(2000)
    hw = float(trk.half_width)
    lx, ly = trk.to_xy(s_ref, np.full_like(s_ref, hw))
    rx, ry = trk.to_xy(s_ref, np.full_like(s_ref, -hw))

    out = {
        "road": {"cx": _r(x_ref[::6], 2), "cy": _r(y_ref[::6], 2),
                 "lx": _r(lx[::6], 2), "ly": _r(ly[::6], 2),
                 "rx": _r(rx[::6], 2), "ry": _r(ry[::6], 2)},
        "car": {"wheelbase": v.wheelbase, "trackF": v.track_f, "trackR": v.track_r,
                "a": round(a, 3), "b": round(b, 3)},
        "geo": {"entry": float(T.ENTRY_STRAIGHT), "arc": float(T.CORNER_ARC),
                "radius": float(T.CORNER_RADIUS), "halfWidth": hw,
                "length": round(float(trk.length), 1)},
        "drives": {},
    }

    for drv in ("rwd", "fwd"):
        # one shared s grid for both drivetrains, not a per-drive key
        s, n, xi = z["s"], z[f"{drv}_n"], z[f"{drv}_xi"]
        px, py = trk.to_xy(s, n)
        head = np.interp(s, s_ref, h_ref)      # track tangent at each station
        psi = head + xi                        # the car's own heading, world

        keep = [i for i in range(len(s))
                if s[i] <= FOCUS_M or i % TAIL_STEP == 0]
        cpsi, spsi = np.cos(psi), np.sin(psi)

        frames = []
        for i in keep:
            wh = {}
            for c, (ox, oy) in OFF.items():
                # offset and force both rotate by the same psi: forward is
                # (cos, sin), the car's left is (-sin, cos)
                wx = px[i] + ox * cpsi[i] - oy * spsi[i]
                wy = py[i] + ox * spsi[i] + oy * cpsi[i]
                fx, fy = z[f"{drv}_fx_{c}"][i], z[f"{drv}_fy_{c}"][i]
                wh[c] = {
                    "x": round(float(wx), 2), "y": round(float(wy), 2),
                    "fx": round(float(fx * cpsi[i] - fy * spsi[i]), 0),
                    "fy": round(float(fx * spsi[i] + fy * cpsi[i]), 0),
                    "load": round(float(z[f"{drv}_load_{c}"][i]), 0),
                    "u": round(float(z[f"{drv}_utilisation_{c}"][i]), 3),
                }
            # Body-frame totals, so the caption can state what the car is
            # doing without the widget re-deriving a frame. A hand-written
            # caption claimed "braking" at 20 m where the car is still on
            # power -- exactly the drift this project keeps finding.
            fl_ = sum(float(z[f"{drv}_fx_{c}"][i]) for c in OFF)
            ft_ = sum(float(z[f"{drv}_fy_{c}"][i]) for c in OFF)
            fzf = sum(float(z[f"{drv}_load_{c}"][i]) for c in ("fl", "fr"))
            fzr = sum(float(z[f"{drv}_load_{c}"][i]) for c in ("rl", "rr"))
            frames.append({
                "long": round(fl_, 0),          # + drive, - brake (body frame)
                "lat": round(ft_, 0),           # + left
                "frontShare": round(100 * fzf / (fzf + fzr), 1),
                "s": round(float(s[i]), 1),
                "x": round(float(px[i]), 2), "y": round(float(py[i]), 2),
                "psi": round(float(psi[i]), 4),
                "v": round(float(z[f"{drv}_speed"][i]), 2),
                "w": wh,
            })
        out["drives"][drv] = {
            "line": {"x": _r(px, 2), "y": _r(py, 2)},
            "frames": frames,
        }

    OUT.write_text(
        "/* The racing line in world coordinates, with tire forces as world\n"
        "   vectors. Every frame conversion done in Python via Track.to_xy.\n"
        "   Generated by tools/export_racing_line.py. */\n"
        "window.CPGeom = " + json.dumps(out, separators=(",", ":")) + ";\n")
    nf = len(out["drives"]["rwd"]["frames"])
    print(f"wrote {OUT.relative_to(ROOT)}  {OUT.stat().st_size/1024:.0f} KB "
          f"({nf} frames/drivetrain)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
