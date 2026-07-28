"""Contact Patch — versioned obs/action/logging schema.

SINGLE SOURCE OF TRUTH for units, sign conventions, and normalisation constants.
Both backends and all analysis import from here. Nothing else in the project
interprets raw simulator output.

The point of this module is that a sign error becomes an ``AssertionError`` at
load time rather than a plausible-looking plot three episodes later.

Frame — ISO 8855 vehicle axis system, right-handed
--------------------------------------------------
==================  ========================================================
``x``               forward, along the vehicle centreline
``y``               **left**
``z``               up
yaw rate ``r``      positive = nose rotating left (a left turn is ``r > 0``)
steer ``delta``     positive = road wheels turned left
lateral accel       ``a_y > 0`` in a left turn
==================  ========================================================

Tire — TYDEX/ISO-W wheel axis system
------------------------------------
Slip angle is defined from the contact-point velocity ``v`` expressed in the
wheel-carrier frame::

    alpha = arctan(v_y / v_x)

so a wheel whose contact point is sliding *left* has ``alpha > 0``, and the
tire pushes back to the *right*:

    **Fy has the opposite sign to alpha.**

That is the convention baked into ``tires/Sedan_Pac02Tire.tir`` — its ``PKY1``
is **negative**, which makes the cornering stiffness ``K_y_alpha`` negative and
the lateral force restoring. Evaluate that file assuming the more common
positive-``PKY1`` convention and you get zero peak force and a negative
cornering stiffness, silently and with no error. Hence
:func:`assert_lateral_sign_convention`, which is called by ``physics.tire`` on
every tire it builds.

Slip ratio uses the same restoring logic in reverse — it is *not* a restoring
quantity, it is a commanded one::

    kappa = (Omega * R_e - v_x) / |v_x|

positive under drive torque, and ``Fx`` has the **same** sign as ``kappa``
(``PKX1 > 0``). :func:`assert_longitudinal_sign_convention` checks it.

Units
-----
SI throughout, everywhere, with no exceptions inside the simulation: metres,
newtons, kilograms, seconds, **radians**. Degrees appear only in
human-facing output (tire cards, plots, understeer gradient in deg/g) and are
converted at the boundary. Any variable holding degrees is suffixed ``_deg``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

import numpy as np

SCHEMA_VERSION = "0.1.0"

#: Machine-readable restatement of the docstring above, so that a run log can
#: record which conventions produced it.
CONVENTIONS = {
    "schema_version": SCHEMA_VERSION,
    "frame": "ISO 8855 (x forward, y left, z up)",
    "angles": "radians internally; *_deg suffix at output boundaries only",
    "slip_angle": "alpha = arctan(v_y / v_x); Fy opposes alpha (K_y_alpha < 0)",
    "slip_ratio": "kappa = (Omega*R_e - v_x)/|v_x|; Fx follows kappa (K_x_kappa > 0)",
    "yaw_rate": "positive = left turn",
    "steer": "positive = road wheels turned left",
    "vertical_load": "Fz > 0 in compression (a loaded tire has positive Fz)",
}

G = 9.80665  # m/s^2, standard gravity


# ---------------------------------------------------------------------------
# Sign-convention asserts
# ---------------------------------------------------------------------------


def assert_lateral_sign_convention(k_y_alpha: float, source: str = "tire") -> None:
    """Assert lateral force is *restoring* under this module's slip-angle sign.

    ``k_y_alpha`` is ``dFy/dalpha`` at ``alpha = 0`` in N/rad. Under the
    convention in the module docstring it must be **negative**.

    This is the check that would have caught the ``PKY1`` bug described in
    ``docs/vehicle-reference-parameters.md`` §3.2 at the cost of one line.
    """
    if not math.isfinite(k_y_alpha):
        raise AssertionError(f"{source}: K_y_alpha is not finite ({k_y_alpha!r})")
    if k_y_alpha >= 0.0:
        raise AssertionError(
            f"{source}: K_y_alpha = {k_y_alpha:+.1f} N/rad is non-negative, so Fy "
            "would grow *with* slip angle rather than oppose it. Either the tire "
            "file uses the positive-PKY1 convention (negate alpha at the "
            "boundary) or a sign has been dropped. See physics/schema.py."
        )


def assert_longitudinal_sign_convention(k_x_kappa: float, source: str = "tire") -> None:
    """Assert longitudinal force follows slip ratio. ``dFx/dkappa`` > 0, N/unit."""
    if not math.isfinite(k_x_kappa):
        raise AssertionError(f"{source}: K_x_kappa is not finite ({k_x_kappa!r})")
    if k_x_kappa <= 0.0:
        raise AssertionError(
            f"{source}: K_x_kappa = {k_x_kappa:+.1f} N is non-positive; drive slip "
            "would produce braking force. See physics/schema.py."
        )


# ---------------------------------------------------------------------------
# Operating envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TireEnvelope:
    """Where the tire model may be believed.

    Two tiers, kept deliberately separate because they have different standing:

    ``declared_*``
        Read from the ``.tir`` file's own range blocks. ``FZMIN``/``FZMAX`` are
        a real, meaningful statement about the fit and are enforced directly.

    ``imposed_*``
        **Ours.** The file declares slip angle valid to ±90° and slip ratio to
        ±1.5; those are statements about where the *formula is defined*, not
        where it was *fitted*, and are useless as validity checks. We impose
        ±12° and ±0.20 on the reasoning that tire rigs sweep roughly that width.
        Documented as an assumption in ``docs/vehicle-reference-parameters.md``
        §3.4 — not as a property of the file.

    Non-negotiable #1 of ``HANDOFF.md``: every rollout logs per-wheel slip
    angle, slip ratio and vertical load, and lap times from outside this
    envelope are discarded rather than celebrated.
    """

    declared_fz_min: float
    declared_fz_max: float
    declared_alpha_max: float
    declared_kappa_max: float
    imposed_alpha_max: float = math.radians(12.0)
    imposed_kappa_max: float = 0.20

    def violation_mask(
        self,
        alpha: np.ndarray | float,
        kappa: np.ndarray | float,
        fz: np.ndarray | float,
    ) -> np.ndarray:
        """Boolean mask of samples outside the *imposed* operating envelope.

        ``Fz`` is checked against the file's declared range (that bound is
        real); slip angle and slip ratio against ours (the file's are not).
        """
        alpha = np.asarray(alpha, dtype=float)
        kappa = np.asarray(kappa, dtype=float)
        fz = np.asarray(fz, dtype=float)
        return (
            (np.abs(alpha) > self.imposed_alpha_max)
            | (np.abs(kappa) > self.imposed_kappa_max)
            | (fz < self.declared_fz_min)
            | (fz > self.declared_fz_max)
        )

    def occupancy(self, alpha, kappa, fz) -> float:
        """Fraction of samples outside the envelope. Gate 4 wants < 0.02."""
        mask = self.violation_mask(alpha, kappa, fz)
        return float(mask.mean()) if mask.size else 0.0


# ---------------------------------------------------------------------------
# Reference vehicle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VehicleParams:
    """RV-1 and its design-sweep variants.

    Every value here is sourced in ``docs/vehicle-reference-parameters.md`` §1
    with a confidence tier. The tiers are not decoration: ``track_f``/``track_r``
    are [LIKELY] and are the moment arm for torque vectoring, so every Season 4
    magnitude claim gets re-run at ±3% track width before it is published.
    """

    mass: float = 1360.0  # kg, curb 1280 + 80 kg driver           [SOURCED]
    wheelbase: float = 2.575  # m                                   [SOURCED]
    track_f: float = 1.505  # m                                     [LIKELY]
    track_r: float = 1.495  # m                                     [LIKELY]
    front_mass_fraction: float = 0.54  # driver-inclusive, 0.53-0.56 [SOURCED]
    com_height: float = 0.460  # m                                  [SOURCED]
    i_zz: float = 1950.0  # kg.m^2, geometry-aware estimate         [DERIVED]
    #: Fraction of the car's total roll stiffness at the front axle. This is the
    #: anti-roll bar knob: raise it and more of the lateral load transfer happens
    #: across the front axle, which costs the front axle grip and adds understeer.
    #: A bicycle model cannot represent it at all — it has no left and right —
    #: which is the whole subject of Episode 5.
    roll_stiffness_front_share: float = 0.55  #                       [ASSUMED]
    #: Spring rate per corner, N/m. The front figure is a published CarSim
    #: B-class anchor [SOURCED, order-of-magnitude]; the rear is [ASSUMED]. These
    #: do not enter the load-transfer calculation — that uses the share above —
    #: but they set the roll ANGLE, which is what a body-roll figure needs to draw
    #: something honest rather than decorative.
    spring_rate_front: float = 28_000.0
    spring_rate_rear: float = 26_000.0
    frontal_area: float = 1.99  # m^2                               [ASSUMED]
    c_d: float = 0.29  #                                            [ASSUMED]
    peak_engine_torque: float = 250.0  # N.m @ 3700 rpm             [SOURCED]
    drive: str = "rwd"  #                                           [SOURCED]

    # --- derived geometry ------------------------------------------------
    @property
    def a(self) -> float:
        """Distance CoM -> front axle, m."""
        return self.wheelbase * (1.0 - self.front_mass_fraction)

    @property
    def b(self) -> float:
        """Distance CoM -> rear axle, m."""
        return self.wheelbase * self.front_mass_fraction

    @property
    def weight(self) -> float:
        """Total static vertical load, N."""
        return self.mass * G

    @property
    def static_fz_front(self) -> float:
        """Static load on *one* front tire, N."""
        return 0.5 * self.weight * self.front_mass_fraction

    @property
    def static_fz_rear(self) -> float:
        """Static load on *one* rear tire, N."""
        return 0.5 * self.weight * (1.0 - self.front_mass_fraction)

    @property
    def track_mean(self) -> float:
        return 0.5 * (self.track_f + self.track_r)

    @property
    def static_stability_factor(self) -> float:
        """``(t/2)/h``. NHTSA range runs ~0.95 (SUV) to ~1.8 (Corvette)."""
        return 0.5 * self.track_mean / self.com_height

    @property
    def roll_stiffness_front(self) -> float:
        """Front axle roll stiffness from its springs, N.m/rad.

        ``0.5 * k * t^2`` for a pair of springs at the track width. Anti-roll bars
        add to this; we do not model their absolute rate, only the resulting
        front/rear share.
        """
        return 0.5 * self.spring_rate_front * self.track_f ** 2

    @property
    def roll_stiffness_rear(self) -> float:
        return 0.5 * self.spring_rate_rear * self.track_r ** 2

    @property
    def roll_stiffness_total(self) -> float:
        return self.roll_stiffness_front + self.roll_stiffness_rear

    @property
    def spring_only_roll_share(self) -> float:
        """Front share of roll stiffness from the springs alone.

        Worth comparing against ``roll_stiffness_front_share``: the springs give
        0.522 and we assume 0.55, a difference consistent with a modest front
        anti-roll bar. Two numbers from different places agreeing is cheap
        reassurance that the assumed share is not arbitrary.
        """
        return self.roll_stiffness_front / self.roll_stiffness_total

    @property
    def roll_gradient_rad_per_g(self) -> float:
        """Body roll angle per g of lateral acceleration, radians.

        ``m*g*h / K_phi``. Rigid-axle approximation: no roll-centre geometry, no
        jacking, no compliance. Real road cars run roughly 3-7 deg/g, and this
        lands at 5.8, so it is the right size — but it is a **visualisation
        quantity**, not a state. The load-transfer model computes transfer from
        moment balance directly and never uses this angle.
        """
        return self.mass * G * self.com_height / self.roll_stiffness_total

    @property
    def roll_gradient_deg_per_g(self) -> float:
        return math.degrees(self.roll_gradient_rad_per_g)

    # --- what a bar does to the roll ANGLE, not just the load split ---------
    #
    # ``roll_stiffness_front_share`` is the load-split knob and Episode 5 sweeps
    # it directly. That sweep silently assumes a **trade** protocol: total roll
    # stiffness is held fixed and only its distribution moves, which is what you
    # get by stiffening one bar and softening the other. Under that protocol the
    # roll angle genuinely does not change.
    #
    # Bolting a bar on is the other protocol, and it is the more common one. A
    # bar is a spring: adding it raises the TOTAL, so the car leans less as well
    # as redistributing. Episode 5's figure claimed "a bar cannot change how much
    # a car leans", which is true of our parameterisation and false of cars.
    # These two methods make the second protocol computable so the claim can be
    # stated correctly and its size quoted. See FINDINGS F35.

    def bar_rate_for_share(self, share: float) -> tuple[float, str]:
        """Bar stiffness needed to reach ``share`` by ADDING a bar, N.m/rad.

        Returns ``(rate, end)`` where ``end`` is the axle it goes on. Reaching a
        front share above the spring-only value takes a front bar; below it takes
        a rear bar. Either way the total rises, so either way the car leans less
        — the roll angle is *non-monotonic* in front share, which is not what
        anyone expects from a knob labelled "front stiffness".
        """
        assert 0.0 < share < 1.0, "front roll-stiffness share is a fraction"
        k_f, k_r, k_t = (self.roll_stiffness_front, self.roll_stiffness_rear,
                         self.roll_stiffness_total)
        if share >= self.spring_only_roll_share:
            if share >= 1.0 - 1e-9:
                return math.inf, "front"
            return (share * k_t - k_f) / (1.0 - share), "front"
        return ((1.0 - share) * k_t - k_r) / share, "rear"

    def roll_gradient_deg_per_g_with_bar(self, share: float) -> float:
        """Roll gradient once a bar has been added to reach ``share``, deg/g."""
        rate, _ = self.bar_rate_for_share(share)
        total = self.roll_stiffness_total + rate
        return math.degrees(self.mass * G * self.com_height / total)

    def scaled_track(self, factor: float) -> "VehicleParams":
        """The ±3% sensitivity variant demanded by ``result-evaluation-guide`` §A3."""
        return replace(self, track_f=self.track_f * factor, track_r=self.track_r * factor)

    def check(self) -> None:
        """Cheap structural asserts. Run at construction sites, not in hot loops."""
        assert self.mass > 0.0, "mass must be positive"
        assert self.wheelbase > 0.0, "wheelbase must be positive"
        assert 0.0 < self.front_mass_fraction < 1.0, "front mass fraction is a fraction"
        assert self.com_height > 0.0, "CoM height must be positive"
        assert self.i_zz > 0.0, "I_zz must be positive"
        assert min(self.track_f, self.track_r) > 0.0, "track widths must be positive"
        assert 0.0 < self.roll_stiffness_front_share < 1.0, (
            "roll stiffness front share is a fraction")
        assert min(self.spring_rate_front, self.spring_rate_rear) > 0.0, (
            "spring rates must be positive")
        assert abs(self.a + self.b - self.wheelbase) < 1e-12, "a + b must equal L"


RV_1 = VehicleParams()

#: Engine-layout archetypes (``docs/vehicle-reference-parameters.md`` §1).
#: Yaw inertia is what separates layouts once weight distribution is controlled
#: for; the multipliers are [ASSUMED], ordered by physical reasoning. Note that
#: rear-engine is *high* inertia despite being rearward-biased — these are two
#: independent axes, which is the whole point of Ep 8.
LAYOUT_ARCHETYPES: dict[str, VehicleParams] = {
    "front_fwd": replace(RV_1, front_mass_fraction=0.62, i_zz=RV_1.i_zz * 1.25, drive="fwd"),
    "front_rwd": replace(RV_1, front_mass_fraction=0.55, i_zz=RV_1.i_zz * 1.20, drive="rwd"),
    "front_mid_rwd": replace(RV_1, front_mass_fraction=0.53, i_zz=RV_1.i_zz * 1.00, drive="rwd"),
    "mid_rwd": replace(RV_1, front_mass_fraction=0.43, i_zz=RV_1.i_zz * 0.80, drive="rwd"),
    "rear_rwd": replace(RV_1, front_mass_fraction=0.38, i_zz=RV_1.i_zz * 1.22, drive="rwd"),
}

#: Design-sweep ranges (``docs/vehicle-reference-parameters.md`` §2).
DESIGN_SWEEP: dict[str, tuple[float, float]] = {
    "front_mass_fraction": (0.35, 0.65),
    "i_zz_multiplier": (0.75, 1.40),
    "com_height": (0.42, 0.60),
    "spring_rate_front": (18e3, 45e3),  # N/m per corner
    "spring_rate_rear": (18e3, 45e3),
    "roll_stiffness_front_share": (0.40, 0.70),
    "diff_preload": (0.0, 400.0),  # N.m
}

#: Validation bands (``docs/result-evaluation-guide.md`` Part B Gate 2). Kept
#: here so that D3 and any episode analysis assert against the *same* numbers.
VALIDATION_BANDS = {
    "understeer_gradient_deg_per_g": (1.5, 3.0),  # expected for RV-1
    "understeer_gradient_test_band_deg_per_g": (1.8, 5.5),  # D3 hard band
    "understeer_gradient_noise_floor_deg_per_g": 0.2,
    "max_lateral_g": (0.95, 1.10),
    "step_steer_rise_time_s": (0.08, 0.30),
    "step_steer_overshoot_frac": (0.05, 0.40),
    "envelope_occupancy_max": 0.02,
    "oc_gap_max_frac": 0.01,
}


# ---------------------------------------------------------------------------
# Channel specs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Channel:
    """One named scalar in an observation, action, or log array.

    ``scale`` is the divisor that maps the physical quantity into roughly
    ``[-1, 1]`` for a policy network. It is a *normalisation constant*, not a
    clip: values outside the range are legal and meaningful (that is how
    envelope violations stay visible).
    """

    name: str
    unit: str
    scale: float
    description: str = ""

    def __post_init__(self) -> None:
        assert self.scale > 0.0, f"channel {self.name}: scale must be positive"


class Space:
    """An ordered, named set of :class:`Channel`\\ s with a stable layout.

    Order is part of the schema. Appending a channel is a minor version bump;
    reordering or reinterpreting one is a major bump, because trained policies
    and logged arrays both depend on the index -> meaning mapping.
    """

    def __init__(self, name: str, channels: Sequence[Channel]) -> None:
        names = [c.name for c in channels]
        assert len(names) == len(set(names)), f"{name}: duplicate channel names"
        self.name = name
        self.channels = tuple(channels)
        self._index = {c.name: i for i, c in enumerate(self.channels)}
        self.scales = np.array([c.scale for c in self.channels], dtype=float)

    def __len__(self) -> int:
        return len(self.channels)

    def __repr__(self) -> str:
        return f"Space({self.name!r}, {len(self)} channels)"

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.channels)

    def index(self, name: str) -> int:
        try:
            return self._index[name]
        except KeyError:
            raise KeyError(
                f"{self.name} has no channel {name!r}; available: {list(self._index)}"
            ) from None

    def select(self, array: np.ndarray, name: str) -> np.ndarray:
        """Pull one channel out of a ``(..., n_channels)`` array by name."""
        return np.asarray(array)[..., self.index(name)]

    def normalise(self, array: np.ndarray) -> np.ndarray:
        """Physical units -> network units."""
        return np.asarray(array, dtype=float) / self.scales

    def denormalise(self, array: np.ndarray) -> np.ndarray:
        """Network units -> physical units."""
        return np.asarray(array, dtype=float) * self.scales

    def pack(self, **values: float) -> np.ndarray:
        """Build one physical-units vector from keyword channel values."""
        missing = set(self.names) - set(values)
        extra = set(values) - set(self.names)
        assert not missing, f"{self.name}: missing channels {sorted(missing)}"
        assert not extra, f"{self.name}: unknown channels {sorted(extra)}"
        return np.array([values[n] for n in self.names], dtype=float)

    def unpack(self, array: np.ndarray) -> dict[str, np.ndarray]:
        """Physical-units vector -> ``{channel_name: value}``."""
        array = np.asarray(array)
        assert array.shape[-1] == len(self), (
            f"{self.name}: expected trailing dim {len(self)}, got {array.shape[-1]}"
        )
        return {n: array[..., i] for i, n in enumerate(self.names)}


#: Axle labels for the two-axle (bicycle) backend.
AXLES: tuple[str, ...] = ("f", "r")

#: Corner labels for the four-wheel (double-track) backend. Order is
#: front-left, front-right, rear-left, rear-right and is load-bearing: D5's
#: "sum of loads equals mg" and the lateral-transfer sign check both index it.
CORNERS: tuple[str, ...] = ("fl", "fr", "rl", "rr")


OBS_BICYCLE = Space(
    "obs_bicycle",
    [
        Channel("v_x", "m/s", 40.0, "longitudinal speed, body frame"),
        Channel("v_y", "m/s", 5.0, "lateral speed, body frame (positive = left)"),
        Channel("yaw_rate", "rad/s", 1.5, "positive = left turn"),
        Channel("beta", "rad", math.radians(15.0), "body sideslip, atan2(v_y, v_x)"),
        Channel("a_y", "m/s^2", G, "lateral acceleration, positive left"),
        Channel("alpha_f", "rad", math.radians(12.0), "front axle slip angle"),
        Channel("alpha_r", "rad", math.radians(12.0), "rear axle slip angle"),
        Channel("fz_f", "N", 4000.0, "front axle vertical load (both tires)"),
        Channel("fz_r", "N", 4000.0, "rear axle vertical load (both tires)"),
        Channel("steer", "rad", math.radians(30.0), "current road-wheel angle"),
    ],
)

ACT_BICYCLE = Space(
    "act_bicycle",
    [
        Channel("steer_rate", "rad/s", math.radians(120.0), "road-wheel angle rate"),
        Channel("drive_force", "N", 6000.0, "net longitudinal demand at the driven axle"),
    ],
)


def wheel_log_space(labels: Iterable[str] = CORNERS) -> Space:
    """The envelope-instrumentation log, per wheel.

    Non-negotiable #1: this is core-loop, not polish. Every rollout logs these
    three quantities for every wheel, and :class:`TireEnvelope` reads them back
    to decide whether the rollout is admissible evidence.
    """
    channels: list[Channel] = []
    for w in labels:
        channels += [
            Channel(f"alpha_{w}", "rad", math.radians(12.0), f"{w} slip angle"),
            Channel(f"kappa_{w}", "-", 0.20, f"{w} slip ratio"),
            Channel(f"fz_{w}", "N", 4000.0, f"{w} vertical load"),
        ]
    return Space(f"wheel_log[{','.join(labels)}]", channels)


WHEEL_LOG_BICYCLE = wheel_log_space(AXLES)
WHEEL_LOG_DOUBLE_TRACK = wheel_log_space(CORNERS)


__all__ = [
    "SCHEMA_VERSION",
    "CONVENTIONS",
    "G",
    "assert_lateral_sign_convention",
    "assert_longitudinal_sign_convention",
    "TireEnvelope",
    "VehicleParams",
    "RV_1",
    "LAYOUT_ARCHETYPES",
    "DESIGN_SWEEP",
    "VALIDATION_BANDS",
    "Channel",
    "Space",
    "AXLES",
    "CORNERS",
    "OBS_BICYCLE",
    "ACT_BICYCLE",
    "wheel_log_space",
    "WHEEL_LOG_BICYCLE",
    "WHEEL_LOG_DOUBLE_TRACK",
]
