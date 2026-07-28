"""MF 2002 (MF-Tyre 5.2) pure-slip tire model, reading an ADAMS ``.tir`` file.

Scope: **pure slip only** — lateral ``Fy0(alpha, Fz, gamma)`` and longitudinal
``Fx0(kappa, Fz)``. Combined slip and aligning moment are deliberately absent;
combined slip is open item #1 in ``docs/vehicle-reference-parameters.md`` §6
and arrives with the double-track model, and ``Mz`` is not used by any Season 1
episode. The ``[ALIGNING_COEFFICIENTS]`` block is parsed and carried so that
adding it later does not touch the parser.

Why full MF 2002 rather than a four-parameter fit: Chrono consumes this same
file with the same equations, so Ep 16's cross-check compares two *vehicle
models* rather than two tire models plus two vehicle models
(``vehicle-reference-parameters.md`` §6 item 7).

Sign conventions come from :mod:`physics.schema` and are asserted on every tire
that is constructed — see :func:`schema.assert_lateral_sign_convention`.

**The project drives an offset-free tire.** :func:`default_tire` removes the
file's conicity and ply-steer shifts; :func:`as_shipped_tire` does not. See
:meth:`MF02Tire.without_offsets` for why, and D1 for the evidence.

Reference: Pacejka, *Tyre and Vehicle Dynamics*, 2nd ed., §4.3.2 (eqs 4.E1–E31),
MF 5.2 / "MF 2002" variant.
"""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from . import schema
from .mathkit import NUMPY, MathKit

_ASSIGN = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^$!]*?)\s*(?:[$!].*)?$"
)
_SECTION = re.compile(r"^\s*\[([A-Za-z_0-9]+)\]")


# ---------------------------------------------------------------------------
# .tir parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TirFile:
    """Flat, case-normalised view of an ADAMS ``.tir`` property file.

    Sections are kept for provenance but lookup is flat: MF parameter names are
    globally unique within a ``.tir``, and the equations do not care which block
    a coefficient came from.
    """

    path: Path
    numbers: dict[str, float]
    strings: dict[str, str]
    sections: dict[str, tuple[str, ...]]

    def get(self, key: str, default: float | None = None) -> float:
        """Fetch a coefficient. Missing keys are an error unless a default is given.

        A missing coefficient with a *documented* default (``PDX3``, ``PEY5``,
        ``PKY4`` — terms that later MF revisions added) is the only legitimate
        use of ``default``. Anything else should raise.
        """
        key = key.upper()
        if key in self.numbers:
            return self.numbers[key]
        if default is not None:
            return default
        raise KeyError(f"{self.path.name}: missing coefficient {key!r}")

    def text(self, key: str) -> str:
        return self.strings[key.upper()]


def load_tir(path: str | Path) -> TirFile:
    """Parse an ADAMS ``.tir`` property file.

    Handles the three comment forms that appear in Chrono's files (``$`` full
    line, ``!`` full line, and trailing ``$comment`` after a value), quoted
    string values, and free-format tabular blocks such as ``[SHAPE]`` (skipped —
    nothing here uses the carcass shape).
    """
    path = Path(path)
    numbers: dict[str, float] = {}
    strings: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current = "_PREAMBLE"

    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith(("$", "!")):
            continue
        m_section = _SECTION.match(line)
        if m_section:
            current = m_section.group(1).upper()
            sections.setdefault(current, [])
            continue
        m = _ASSIGN.match(line)
        if not m:
            continue  # tabular row (e.g. [SHAPE]) or free text
        key, value = m.group(1).upper(), m.group(2).strip()
        sections.setdefault(current, []).append(key)
        if value.startswith(("'", '"')):
            strings[key] = value.strip("'\"")
            continue
        try:
            numbers[key] = float(value)
        except ValueError:
            strings[key] = value

    if not numbers:
        raise ValueError(f"{path}: parsed no coefficients — is this a .tir file?")
    fmt = strings.get("PROPERTY_FILE_FORMAT", "")
    if fmt and "PAC2002" not in fmt.upper():
        raise ValueError(
            f"{path}: PROPERTY_FILE_FORMAT is {fmt!r}; this module implements "
            "MF 2002 (PAC2002) only."
        )
    return TirFile(
        path=path,
        numbers=numbers,
        strings=strings,
        sections={k: tuple(v) for k, v in sections.items()},
    )


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scaling:
    """The MF ``[SCALING_COEFFICIENTS]`` we actually use.

    This is the sanctioned way to retarget a fitted tire to a different vehicle:
    ``LFZO`` rescales nominal load, ``LMUY``/``LMUX`` peak friction, and
    ``LKY``/``LKX`` slip stiffness. Hand-editing the ``P*`` coefficients instead
    would discard the fit's internal consistency
    (``docs/vehicle-reference-parameters.md`` §3.3).

    Defaults are read from the file. ``Sedan_Pac02Tire.tir`` ships ``LFZO=0.81``
    and everything else at 1.0.
    """

    lfzo: float = 1.0
    lcx: float = 1.0
    lmux: float = 1.0
    lex: float = 1.0
    lkx: float = 1.0
    lhx: float = 1.0
    lvx: float = 1.0
    lcy: float = 1.0
    lmuy: float = 1.0
    ley: float = 1.0
    lky: float = 1.0
    lhy: float = 1.0
    lvy: float = 1.0
    lgay: float = 1.0

    @classmethod
    def from_tir(cls, tir: TirFile) -> "Scaling":
        g = lambda k: tir.get(k, 1.0)  # noqa: E731
        return cls(
            lfzo=g("LFZO"), lcx=g("LCX"), lmux=g("LMUX"), lex=g("LEX"), lkx=g("LKX"),
            lhx=g("LHX"), lvx=g("LVX"), lcy=g("LCY"), lmuy=g("LMUY"), ley=g("LEY"),
            lky=g("LKY"), lhy=g("LHY"), lvy=g("LVY"), lgay=g("LGAY"),
        )


# ---------------------------------------------------------------------------
# The tire
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PeakLateral:
    """Everything the D1 tire card reports for one vertical load."""

    fz: float
    mu_peak: float
    fy_peak: float
    alpha_peak: float  # rad
    cornering_stiffness: float  # N/rad, signed (negative under our convention)

    @property
    def alpha_peak_deg(self) -> float:
        return math.degrees(self.alpha_peak)

    @property
    def cornering_stiffness_per_deg(self) -> float:
        """Magnitude in N/deg — the form the reference tables are quoted in."""
        return abs(self.cornering_stiffness) * math.pi / 180.0


class MF02Tire:
    """MF 2002 pure-slip evaluation of one tire.

    All methods broadcast: ``alpha``, ``kappa``, ``fz`` and ``gamma`` may be
    scalars or numpy arrays of compatible shape.

    Parameters
    ----------
    tir:
        Parsed property file.
    scaling:
        Override for the file's ``[SCALING_COEFFICIENTS]``. Pass a modified
        :class:`Scaling` to retarget the tire; record what you passed.
    ey_camber_asymmetry:
        Whether the lateral curvature factor includes MF 2002's
        ``(1 - (PEY3 + PEY4*gamma_y)*sgn(alpha_y))`` term. ``True`` is the
        standard formulation and the default. See :ref:`the note below
        <ey-note>`.

    .. _ey-note:

    **On** ``ey_camber_asymmetry``. This file's ``PEY3 = -9.9935`` and
    ``PEY4 = -760.14`` are degenerate: the standard term evaluates to a factor
    of ~11 at zero camber, and ``PEY4`` in particular implies an absurd camber
    sensitivity. They are almost certainly artefacts of an unconstrained fit to
    data that contained no camber sweep. The term affects *only* where the
    lateral peak sits — peak force, peak mu and cornering stiffness are
    untouched by ``Ey``, because the Magic Formula's maximum is ``Dy``
    regardless. Setting this flag ``False`` drops the term and reproduces the
    reference table in ``HANDOFF.md`` exactly, which is how ``D1`` establishes
    that the 0.2-1.0 deg disagreement in that table's slip-at-peak column is
    this term and nothing else. Keep it ``True`` for physics; the flag exists to
    make one specific discrepancy a test rather than a shrug.
    """

    def __init__(
        self,
        tir: TirFile,
        scaling: Scaling | None = None,
        ey_camber_asymmetry: bool = True,
    ) -> None:
        self.tir = tir
        self.scaling = scaling if scaling is not None else Scaling.from_tir(tir)
        self.ey_camber_asymmetry = ey_camber_asymmetry
        #: Provenance flag. ``True`` once :meth:`without_offsets` has been
        #: applied. Logged with every run so a figure can always be traced back
        #: to which tire produced it.
        self.offsets_removed = False

        g = tir.get
        self.fz0 = g("FNOMIN")
        self.r0 = g("UNLOADED_RADIUS")
        self.vertical_stiffness = g("VERTICAL_STIFFNESS")

        #: Nominal load after ``LFZO`` scaling — ``Fz0'`` in Pacejka's notation.
        #: Every ``dfz`` in the model is measured against this, not ``FNOMIN``.
        self.fz0_prime = self.fz0 * self.scaling.lfzo

        self.envelope = schema.TireEnvelope(
            declared_fz_min=g("FZMIN"),
            declared_fz_max=g("FZMAX"),
            declared_alpha_max=abs(g("ALPMAX")),
            declared_kappa_max=abs(g("KPUMAX")),
        )

        # Lateral
        self.PCY1 = g("PCY1")
        self.PDY1, self.PDY2, self.PDY3 = g("PDY1"), g("PDY2"), g("PDY3")
        self.PEY1, self.PEY2 = g("PEY1"), g("PEY2")
        self.PEY3, self.PEY4 = g("PEY3"), g("PEY4")
        self.PKY1, self.PKY2, self.PKY3 = g("PKY1"), g("PKY2"), g("PKY3")
        self.PHY1, self.PHY2, self.PHY3 = g("PHY1"), g("PHY2"), g("PHY3")
        self.PVY1, self.PVY2 = g("PVY1"), g("PVY2")
        self.PVY3, self.PVY4 = g("PVY3"), g("PVY4")

        # Longitudinal
        self.PCX1 = g("PCX1")
        self.PDX1, self.PDX2 = g("PDX1"), g("PDX2")
        self.PDX3 = g("PDX3", 0.0)  # camber term, absent in MF 5.2 files
        self.PEX1, self.PEX2 = g("PEX1"), g("PEX2")
        self.PEX3, self.PEX4 = g("PEX3"), g("PEX4")
        self.PKX1, self.PKX2, self.PKX3 = g("PKX1"), g("PKX2"), g("PKX3")
        self.PHX1, self.PHX2 = g("PHX1"), g("PHX2")
        self.PVX1, self.PVX2 = g("PVX1"), g("PVX2")

        # The check that pays for this whole module.
        schema.assert_lateral_sign_convention(
            self.cornering_stiffness(self.fz0_prime), source=tir.path.name
        )
        schema.assert_longitudinal_sign_convention(
            self.longitudinal_slip_stiffness(self.fz0_prime), source=tir.path.name
        )

    # -- helpers ----------------------------------------------------------

    def __repr__(self) -> str:
        bits = [
            self.tir.path.name,
            f"Fz0'={self.fz0_prime:.0f} N",
            f"LMUY={self.scaling.lmuy:g}",
            f"LKY={self.scaling.lky:g}",
        ]
        if self.offsets_removed:
            bits.append("offset-free")
        if not self.ey_camber_asymmetry:
            bits.append("simplified Ey")
        return f"MF02Tire({', '.join(bits)})"

    @property
    def provenance(self) -> dict:
        """What produced this tire — record it alongside any result it generates."""
        return {
            "file": self.tir.path.name,
            "fz0_prime": self.fz0_prime,
            "scaling": vars(self.scaling),
            "offsets_removed": self.offsets_removed,
            "ey_camber_asymmetry": self.ey_camber_asymmetry,
        }

    def dfz(self, fz, xp: MathKit = NUMPY):
        """Normalised load increment ``(Fz - Fz0')/Fz0'``."""
        if xp is NUMPY:
            fz = np.asarray(fz, dtype=float)
        return (fz - self.fz0_prime) / self.fz0_prime

    def rescaled(self, **overrides: float) -> "MF02Tire":
        """A copy with modified scaling coefficients, e.g. ``rescaled(lmuy=0.95)``."""
        clone = MF02Tire(
            self.tir,
            replace(self.scaling, **overrides),
            ey_camber_asymmetry=self.ey_camber_asymmetry,
        )
        return clone.without_offsets() if self.offsets_removed else clone

    #: The Magic Formula's horizontal and vertical shift coefficients — the
    #: ones :meth:`without_offsets` zeroes.
    OFFSET_COEFFICIENTS = (
        "PHY1", "PHY2", "PHY3", "PVY1", "PVY2", "PVY3", "PVY4",
        "PHX1", "PHX2", "PVX1", "PVX2",
    )

    def without_offsets(self) -> "MF02Tire":
        """A copy with the horizontal and vertical shifts zeroed.

        ``PHY*``/``PVY*`` and ``PHX*``/``PVX*`` encode **conicity** (the tire is
        very slightly conical, so it rolls toward the apex — the force survives
        a reversal of rolling direction and flips if the tire is flipped on the
        rim) and **ply steer** (the belt plies are laid at a bias angle, so the
        tread band shears sideways through the contact patch — this one flips
        with rolling direction and is identical for every tire of the
        construction). Both are per-sample manufacturing artefacts, and both are
        what real cars align out.

        Zeroing them is *not* an idealisation of the tire's physics. Every
        fitted shape coefficient survives: B, C, D and E as functions of load
        are untouched, so peak mu, load sensitivity, cornering stiffness and
        slip at peak are exactly as fitted. What goes away is a 7.4% difference
        in peak mu between cornering one way and the other — bigger than the
        entire plausibility band for max lateral g, and enough to corrupt any
        left/right comparison in the double-track model.

        This is why :func:`default_tire` returns an offset-free tire. Use
        :func:`as_shipped_tire` when the file's exact behaviour is the subject,
        which is essentially only D1's reference-table check.
        """
        clone = copy.copy(self)
        for name in self.OFFSET_COEFFICIENTS:
            setattr(clone, name, 0.0)
        clone.offsets_removed = True
        # The clone bypasses __init__, so re-run the checks that pay for it.
        schema.assert_lateral_sign_convention(
            clone.cornering_stiffness(clone.fz0_prime),
            source=f"{self.tir.path.name} (offset-free)",
        )
        schema.assert_longitudinal_sign_convention(
            clone.longitudinal_slip_stiffness(clone.fz0_prime),
            source=f"{self.tir.path.name} (offset-free)",
        )
        return clone

    # -- pure lateral -----------------------------------------------------

    def fy0(self, alpha, fz, gamma=0.0, xp: MathKit = NUMPY):
        """Pure-slip lateral force, N. ``alpha`` in rad, ``fz`` in N.

        Negative for positive ``alpha`` under this project's convention.

        ``xp`` selects the evaluation backend — numpy by default, CasADi when
        this is being built into an optimisation. Same formulas either way; see
        :mod:`physics.mathkit`.
        """
        if xp is NUMPY:
            alpha = np.asarray(alpha, dtype=float)
            fz = np.asarray(fz, dtype=float)
        s = self.scaling
        dfz = self.dfz(fz, xp)
        gy = gamma * s.lgay

        Shy = (self.PHY1 + self.PHY2 * dfz) * s.lhy + self.PHY3 * gy
        alpha_y = alpha + Shy

        Cy = self.PCY1 * s.lcy
        muy = (self.PDY1 + self.PDY2 * dfz) * (1.0 - self.PDY3 * gy**2) * s.lmuy
        Dy = muy * fz
        Ey = self._ey(dfz, gy, alpha_y, xp)
        Ky = self._ky_alpha(fz, gy, xp)
        Svy = fz * (
            (self.PVY1 + self.PVY2 * dfz) * s.lvy
            + (self.PVY3 + self.PVY4 * dfz) * gy
        ) * s.lmuy

        By = Ky / (Cy * Dy)
        x = By * alpha_y
        return Dy * xp.sin(Cy * xp.arctan(x - Ey * (x - xp.arctan(x)))) + Svy

    def _ey(self, dfz, gy, alpha_y, xp: MathKit = NUMPY):
        """Lateral curvature factor, Pacejka eq 4.E21. Capped at 1 as required."""
        base = (self.PEY1 + self.PEY2 * dfz) * self.scaling.ley
        if self.ey_camber_asymmetry:
            base = base * (1.0 - (self.PEY3 + self.PEY4 * gy) * xp.sign(alpha_y))
        return xp.minimum(base, 1.0)

    def _ky_alpha(self, fz, gy=0.0, xp: MathKit = NUMPY):
        """``BCD`` for lateral: the slope of the Magic Formula at ``alpha_y = 0``."""
        if xp is NUMPY:
            fz = np.asarray(fz, dtype=float)
        return (
            self.PKY1
            * self.fz0_prime
            * xp.sin(2.0 * xp.arctan(fz / (self.PKY2 * self.fz0_prime)))
            * (1.0 - self.PKY3 * xp.abs(gy))
            * self.scaling.lky
        )

    def cornering_stiffness(self, fz, gamma=0.0):
        """``dFy/dalpha`` at ``alpha = 0``, N/rad. Negative by convention.

        This is *not* ``BCD``. It is the slope of the real curve at zero slip
        angle, which the horizontal shift ``Shy`` displaces slightly off the
        Magic Formula's own origin. The difference is ~0.4% for this tire — small,
        but it is the difference between reproducing a reference table and
        nearly reproducing it.
        """
        fz = np.asarray(fz, dtype=float)
        s = self.scaling
        dfz = self.dfz(fz)
        gy = np.asarray(gamma, dtype=float) * s.lgay

        Shy = (self.PHY1 + self.PHY2 * dfz) * s.lhy + self.PHY3 * gy
        Cy = self.PCY1 * s.lcy
        Dy = (self.PDY1 + self.PDY2 * dfz) * (1.0 - self.PDY3 * gy**2) * s.lmuy * fz
        Ey = self._ey(dfz, gy, Shy)
        Ky = self._ky_alpha(fz, gy)
        By = Ky / (Cy * Dy)

        x = By * Shy
        g = x - Ey * (x - np.arctan(x))
        dg = 1.0 - Ey * (1.0 - 1.0 / (1.0 + x**2))
        return Dy * np.cos(Cy * np.arctan(g)) * Cy / (1.0 + g**2) * dg * By

    def peak_lateral(self, fz, gamma=0.0, branch: str = "positive") -> PeakLateral:
        """Peak lateral force and where it occurs, for one scalar load.

        ``branch`` selects which side of the curve is measured. The two differ
        because of ply steer and conicity: at 1000 N this tire peaks at 1139 N
        on the positive-``alpha`` side and 1228 N on the negative side. The
        reference table in ``HANDOFF.md`` quotes the positive branch, so that is
        the default; ``"mean"`` averages the magnitudes and is the more honest
        single number for an axle that corners both ways.
        """
        fz = float(fz)
        Cy = self.PCY1 * self.scaling.lcy
        assert Cy > 1.0, "peak search assumes Cy > 1 (the Magic Formula has a maximum)"

        def _peak(sign: float) -> tuple[float, float]:
            # Parameterise as alpha = sign*t, t >= 0, and maximise
            # q(t) = -sign*Fy. Then dq/dt = -dFy/dalpha regardless of branch, so
            # one bisection handles both sides.
            #
            # Bracket: the peak sits at a few times the linear-range slip
            # Dy/|Ky|. Ten times is comfortably beyond it for any load here.
            dy = abs((self.PDY1 + self.PDY2 * self.dfz(fz)) * self.scaling.lmuy * fz)
            ky = abs(self._ky_alpha(fz, gamma * self.scaling.lgay))
            t_hi = min(10.0 * dy / ky, math.radians(75.0))
            grid = np.linspace(1e-6, t_hi, 4001)
            q = -sign * self.fy0(sign * grid, fz, gamma)
            i = int(np.argmax(q))
            lo = float(grid[max(i - 1, 0)])
            hi = float(grid[min(i + 1, grid.size - 1)])
            h = 1e-7
            for _ in range(50):
                mid = 0.5 * (lo + hi)
                dq = -float(
                    self.fy0(sign * (mid + h), fz, gamma)
                    - self.fy0(sign * (mid - h), fz, gamma)
                ) / (2.0 * h) * sign
                if dq > 0.0:
                    lo = mid
                else:
                    hi = mid
            t = 0.5 * (lo + hi)
            return abs(float(self.fy0(sign * t, fz, gamma))), t

        if branch == "positive":
            fy_peak, alpha_peak = _peak(+1.0)
        elif branch == "negative":
            fy_peak, alpha_peak = _peak(-1.0)
        elif branch == "mean":
            p, ap = _peak(+1.0)
            n, an = _peak(-1.0)
            fy_peak, alpha_peak = 0.5 * (p + n), 0.5 * (ap + an)
        else:
            raise ValueError(f"branch must be positive/negative/mean, got {branch!r}")

        return PeakLateral(
            fz=fz,
            mu_peak=fy_peak / fz,
            fy_peak=fy_peak,
            alpha_peak=alpha_peak,
            cornering_stiffness=float(self.cornering_stiffness(fz, gamma)),
        )

    # -- pure longitudinal ------------------------------------------------

    def fx0(self, kappa, fz, gamma=0.0, xp: MathKit = NUMPY):
        """Pure-slip longitudinal force, N. ``kappa`` dimensionless.

        Same sign as ``kappa``: drive slip drives, brake slip brakes.
        """
        if xp is NUMPY:
            kappa = np.asarray(kappa, dtype=float)
            fz = np.asarray(fz, dtype=float)
        s = self.scaling
        dfz = self.dfz(fz, xp)
        gx = gamma * s.lgay

        Shx = (self.PHX1 + self.PHX2 * dfz) * s.lhx
        kappa_x = kappa + Shx

        Cx = self.PCX1 * s.lcx
        mux = (self.PDX1 + self.PDX2 * dfz) * (1.0 - self.PDX3 * gx**2) * s.lmux
        Dx = mux * fz
        Ex = xp.minimum(
            (self.PEX1 + self.PEX2 * dfz + self.PEX3 * dfz**2)
            * (1.0 - self.PEX4 * xp.sign(kappa_x))
            * s.lex,
            1.0,
        )
        Kx = self._kx_kappa(fz, xp)
        Svx = fz * (self.PVX1 + self.PVX2 * dfz) * s.lvx * s.lmux

        Bx = Kx / (Cx * Dx)
        x = Bx * kappa_x
        return Dx * xp.sin(Cx * xp.arctan(x - Ex * (x - xp.arctan(x)))) + Svx

    def _kx_kappa(self, fz, xp: MathKit = NUMPY):
        dfz = self.dfz(fz, xp)
        if xp is NUMPY:
            fz = np.asarray(fz, dtype=float)
        return (
            fz
            * (self.PKX1 + self.PKX2 * dfz)
            * xp.exp(self.PKX3 * dfz)
            * self.scaling.lkx
        )

    def longitudinal_slip_stiffness(self, fz):
        """``dFx/dkappa`` at ``kappa = 0``, N. Positive by convention."""
        fz = np.asarray(fz, dtype=float)
        s = self.scaling
        dfz = self.dfz(fz)
        Shx = (self.PHX1 + self.PHX2 * dfz) * s.lhx
        Cx = self.PCX1 * s.lcx
        Dx = (self.PDX1 + self.PDX2 * dfz) * s.lmux * fz
        Ex = np.minimum(
            (self.PEX1 + self.PEX2 * dfz + self.PEX3 * dfz**2)
            * (1.0 - self.PEX4 * np.sign(Shx))
            * s.lex,
            1.0,
        )
        Kx = self._kx_kappa(fz)
        Bx = Kx / (Cx * Dx)
        x = Bx * Shx
        g = x - Ex * (x - np.arctan(x))
        dg = 1.0 - Ex * (1.0 - 1.0 / (1.0 + x**2))
        return Dx * np.cos(Cx * np.arctan(g)) * Cx / (1.0 + g**2) * dg * Bx

    # -- combined slip ----------------------------------------------------

    def peak_fx(self, fz, xp: MathKit = NUMPY):
        """Peak longitudinal force, N. Analytic, so it is cheap in a loop.

        The Magic Formula's maximum is ``Dx`` whenever ``Cx > 1``, exactly as for
        the lateral curve, so this needs no search.
        """
        if xp is NUMPY:
            fz = np.asarray(fz, dtype=float)
        s = self.scaling
        mux = (self.PDX1 + self.PDX2 * self.dfz(fz, xp)) * s.lmux
        return mux * fz

    def peak_fy(self, fz, xp: MathKit = NUMPY):
        """Peak lateral force, N. Analytic — see :meth:`peak_fx`."""
        if xp is NUMPY:
            fz = np.asarray(fz, dtype=float)
        s = self.scaling
        muy = (self.PDY1 + self.PDY2 * self.dfz(fz, xp)) * s.lmuy
        return muy * fz

    def fy_combined(self, alpha, fz, fx=0.0, gamma=0.0,
                    xp: MathKit = NUMPY):
        """Lateral force when the tire is also being asked for ``fx``.

        **Friction ellipse — this is the placeholder, not a fitted model.** Open
        item O2 in ``FINDINGS.md``. It scales the pure-slip lateral force by

            ``sqrt(1 - (Fx / Fx_peak)^2)``

        which encodes the one thing that is certainly true: a tire has a finite
        total force budget, and longitudinal force spends part of it. Braking at
        70% of what the tire can do longitudinally leaves it about 71% of its
        cornering force, not 100%.

        What it is not: MF 2002 ships its own fitted combined-slip weighting
        functions (``RBX*``, ``RBY*`` and friends), and this file does not contain
        those coefficients. The ellipse is the standard stand-in and is used by a
        lot of vehicle-dynamics work, but it is an assumption about the *shape* of
        the interaction rather than a measurement of it. Any result that depends
        on the shape — as opposed to merely on there being a trade-off — needs
        that caveat attached.

        A tire asked for more longitudinal force than it has is clamped to zero
        lateral force rather than returning a NaN.
        """
        fy0 = self.fy0(alpha, fz, gamma, xp)
        budget = xp.maximum(self.peak_fx(fz, xp), 1e-9)
        used = xp.abs(fx) / budget
        # Floor the radicand instead of clipping `used` at exactly 1. At the
        # saturation point sqrt(0) has an infinite derivative, which is a NaN in
        # the Jacobian the moment an optimiser asks a fully-braked tire for
        # cornering force. 1e-6 caps the lateral force at 0.1% of pure slip
        # there -- physically the same answer, numerically differentiable.
        return fy0 * xp.sqrt(xp.maximum(1.0 - used**2, 1e-6))

    def peak_longitudinal(self, fz) -> tuple[float, float]:
        """``(mu_x_peak, kappa_at_peak)`` on the drive side, for one scalar load."""
        fz = float(fz)
        grid = np.linspace(1e-6, 0.6, 60001)
        f = self.fx0(grid, fz)
        i = int(np.argmax(f))
        return float(f[i] / fz), float(grid[i])


# ---------------------------------------------------------------------------


DEFAULT_TIR = Path(__file__).resolve().parent.parent / "tires" / "Sedan_Pac02Tire.tir"


def as_shipped_tire(**kwargs) -> MF02Tire:
    """Chrono's ``Sedan_Pac02Tire.tir`` exactly as the file defines it.

    Includes the conicity and ply-steer offsets, so it is left/right asymmetric
    by 7.4% in peak mu. Use it only where the file's own behaviour is the
    subject — which in practice means D1's reference-table check. For anything
    that drives a car, use :func:`default_tire`.
    """
    return MF02Tire(load_tir(DEFAULT_TIR), **kwargs)


def default_tire(**kwargs) -> MF02Tire:
    """The project's simulation tire. **Offset-free** — see below.

    Chrono's BSD-3 ``Sedan_Pac02Tire.tir``, unscaled, with the conicity and
    ply-steer shifts removed via :meth:`MF02Tire.without_offsets`. Every fitted
    shape coefficient is intact; what is removed is a manufacturing artefact
    that made the tire generate 7.4% more peak grip turning one way than the
    other (1.012 vs 1.086 at Fz0'), which would have contaminated Ep 3's max
    lateral g and every left/right comparison from Ep 5 onward.

    The Ey curvature asymmetry is deliberately **kept**: removing it would mean
    editing the ``P*`` coefficients, which discards the fit's internal
    consistency, and it costs only 1.1% of peak near the peak itself and nothing
    at all in peak magnitude. So the two branches share a peak force exactly and
    differ by 0.8 deg in where it occurs.

    Sizing caveat unchanged: this is a 245/40 R18 fitted for roughly a 1980 kg
    car, so it is mildly optimistic on RV-1 — see
    ``docs/vehicle-reference-parameters.md`` §3.3. Any episode that rescales
    must say so and record the ``L*`` factors it used.
    """
    return as_shipped_tire(**kwargs).without_offsets()


__all__ = [
    "TirFile",
    "load_tir",
    "Scaling",
    "PeakLateral",
    "MF02Tire",
    "DEFAULT_TIR",
    "as_shipped_tire",
    "default_tire",
]
