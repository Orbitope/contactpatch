"""The abstract simulator interface.

Analysis code, diagnostics, optimal control and (eventually) RL all talk to a
:class:`Backend`. None of them touches a simulator directly. That is what makes
Episode 5 (bicycle vs double-track, identical inputs) and Episode 16 (our model
vs Project Chrono) a matter of swapping one object rather than rewriting the
experiment.

Three backends are planned:

======================  =========================================
``BicycleBackend``      two axles, longitudinal load transfer only. Ep 1-4.
``DoubleTrackBackend``  four wheels, lateral load transfer, roll. Ep 5+.
``ChronoBackend``       Project Chrono, for the Ep 16 cross-check.
======================  =========================================

Everything a backend exposes is described by :mod:`physics.schema`, including
units and sign conventions, so a caller never has to ask what a number means.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from . import schema


@dataclass
class StepInfo:
    """Everything a step produced that is not part of the observation.

    Metrics are computed downstream from these arrays, never inside the sim loop
    (CLAUDE.md rule 7) — you will redefine "apex" three times and must not have
    to re-run anything to do it.
    """

    t: float
    a_x: float  # m/s^2, body frame, positive forward
    a_y: float  # m/s^2, body frame, positive left
    wheel_log: np.ndarray  # per the backend's wheel_log_space
    position: np.ndarray  # (X, Y) in the ground frame, m
    heading: float  # rad, ground frame, positive counter-clockwise
    envelope_violation: bool


class Backend(ABC):
    """A vehicle simulator with a fixed, schema-described interface."""

    #: The observation layout this backend produces.
    obs_space: schema.Space
    #: The action layout it consumes.
    act_space: schema.Space
    #: The per-wheel envelope log it produces every step (non-negotiable #3).
    wheel_log_space: schema.Space

    schema_version: str = schema.SCHEMA_VERSION

    # -- design ------------------------------------------------------------

    @abstractmethod
    def set_design(self, params: schema.VehicleParams) -> None:
        """Change the vehicle. Must be cheap: design sweeps call it thousands of times.

        Implementations validate with ``params.check()`` and must not leave the
        backend in a half-updated state if it raises.
        """

    @property
    @abstractmethod
    def params(self) -> schema.VehicleParams:
        """The design currently loaded."""

    # -- simulation --------------------------------------------------------

    @abstractmethod
    def reset(self, speed: float, seed: int | None = None) -> np.ndarray:
        """Put the car in a straight line at ``speed`` m/s. Returns the observation."""

    @abstractmethod
    def step(self, action: np.ndarray, dt: float) -> tuple[np.ndarray, StepInfo]:
        """Advance by ``dt`` seconds. ``action`` is in **physical units**.

        Normalisation is the policy's business, not the simulator's — see
        :meth:`schema.Space.normalise`. Keeping the backend in physical units is
        what lets a diagnostic drive it with a steering angle in radians and get
        an answer it can check against a textbook.
        """

    @abstractmethod
    def get_obs(self) -> np.ndarray:
        """The current observation, in physical units, laid out per ``obs_space``."""

    @abstractmethod
    def wheel_log(self) -> np.ndarray:
        """Current per-wheel slip angle, slip ratio and vertical load."""

    # -- shared helpers ----------------------------------------------------

    @property
    def envelope(self) -> schema.TireEnvelope:
        """The operating envelope of the backend's tire."""
        raise NotImplementedError

    def envelope_violated(self, log: np.ndarray | None = None) -> bool:
        """Whether the current (or given) wheel log sits outside the envelope."""
        log = self.wheel_log() if log is None else log
        sp = self.wheel_log_space
        names = sp.names
        alpha = np.array([log[sp.index(n)] for n in names if n.startswith("alpha_")])
        kappa = np.array([log[sp.index(n)] for n in names if n.startswith("kappa_")])
        fz = np.array([log[sp.index(n)] for n in names if n.startswith("fz_")])
        return bool(self.envelope.violation_mask(alpha, kappa, fz).any())

    def rollout(self, actions, dt: float, speed: float, seed: int | None = None):
        """Convenience: run a sequence of actions and return stacked logs.

        Returns ``(obs, infos)`` where ``obs`` is ``(n+1, n_obs)`` including the
        reset observation. Nothing is reduced here — reduction happens downstream.
        """
        obs = [self.reset(speed, seed)]
        infos: list[StepInfo] = []
        for a in actions:
            o, info = self.step(np.asarray(a, dtype=float), dt)
            obs.append(o)
            infos.append(info)
        return np.array(obs), infos


__all__ = ["Backend", "StepInfo"]
