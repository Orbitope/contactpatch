"""A driving environment for Season 3 — a car, a road, and a stopwatch.

Everything before this episode was an *optimiser*: it saw the whole road, solved
for the best inputs, and could not be surprised. This is the other kind of driver.
It gets one instant at a time, has to choose a steering rate and a throttle from
what it can currently sense, and finds out what happens next by doing it.

Deliberate design decisions, each of which is a modelling choice and is recorded
here because the episode turns on them:

**The slip envelope is NOT enforced.** Every minimum-time solve in Seasons 1 and 2
constrains slip angle to ±12°, because a solver handed an unconstrained Magic
Formula will drive at 30° of slip where the fit is extrapolating and return a lap
time that is a statement about our curve fit. That constraint is absent here, on
purpose. The envelope is *instrumented* — every step records slip angle, slip
ratio and load, and whether they left the region the tire file supports — but
nothing stops the policy going there. Episode 9's subject is what a learner does
with a physics model that is wrong in a place nobody told it not to go. Putting
the constraint in would hide exactly the thing worth showing. See CLAUDE.md rule 4:
instrumentation is core-loop, and lap times from outside the envelope are
discarded, not celebrated.

**The reward is progress, and nothing else.** No reward for staying on the road,
no shaping toward a racing line, no penalty for slip. Distance advanced along the
track per step, minus a terminal penalty for leaving the road. "Just a stopwatch"
in the series plan is meant literally: any behaviour more sophisticated than
"go forwards" has to be discovered rather than encoded. It also means every
unintended behaviour is genuinely unintended.

**The observation is what a driver could plausibly know.** Speed, how far off the
centreline the car is, how much its heading differs from the road's, yaw rate,
sideslip, current steer angle — and a short preview of the curvature ahead,
because a driver can see. It does NOT include the whole road, the lap time so far,
or anything about the tire model. A policy that could see the full road would be a
worse-conditioned optimal-control solver, not a driver.

This module is numpy-only and has no learning code in it, so the physics can be
tested without a training framework installed.

**Episode 14 adds three action-space modes** (``EnvConfig.tv_mode``), all
routed through ``DoubleTrackBackend.attach_torque_vectoring`` — the same hook
``physics/driver.py`` uses for Episode 13's classical controller:

* ``"none"`` — every Episode 9-11 result, byte-for-bit unchanged.
* ``"hybrid"`` (variant H) — the policy adds one action, an `Mz` DEMAND, fed
  through the identical QP allocator Episode 13's classical controller uses.
  The only thing that differs from the classical variant is where the moment
  demand comes from.
* ``"end_to_end"`` (variant E) — the policy's action REPLACES the net
  drive-force channel with four raw per-wheel force fractions and there is no
  allocator at all — see ``docs/vehicle-codesign-research-plan.md`` Phase 4b
  for the variant table this reproduces exactly.

Also added: per-step lateral acceleration and per-wheel friction-ellipse
utilisation logging, absent from this file since Season 3 and flagged in
`HANDOFF.md` as the reason there was previously no way to verify a
torque-vectoring result was measuring anything a saturated tire actually did.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from physics import schema
from physics.double_track import CORNERS, DoubleTrackBackend
from physics.tire import default_tire
from physics.torque_vectoring import Allocator
from physics.track import Track, long_exit

#: Simulation step. 50 Hz — fast enough that a 200 deg/s steering rate moves the
#: wheel 4 degrees in a step, slow enough that a 400 m corner is ~650 steps.
DT = 0.02

#: Steering and drive-force authority the policy commands, matching the
#: optimal-control actuator limits so a learned driver and a solved one are given
#: the same car. [ASSUMED], as they are there.
STEER_RATE_MAX = math.radians(200.0)
STEER_MAX = math.radians(30.0)
DRIVE_MAX = 4500.0
BRAKE_MAX = 12000.0

#: The slip bound every minimum-time solve in Seasons 1-2 enforces, and the edge
#: of the region the tire file was fitted over. Ours, not the file's.
ENVELOPE_SLIP_MAX = math.radians(12.0)

#: How far ahead the policy can see, in metres. Six points spread over ~55 m at
#: 30 m/s is a bit under two seconds of road, which is roughly what a driver
#: reads. [ASSUMED] — and worth a sensitivity check before any claim rests on it.
PREVIEW_DISTANCES = (5.0, 12.0, 20.0, 30.0, 42.0, 55.0)

#: Episode 14, variant H. The bound the hybrid policy's Mz action is scaled
#: against, matching ``torque_vectoring.YawController``'s own default clip —
#: the same ceiling the classical PID is held to, so neither controller is
#: structurally freer than the other to ask for more moment than the tires
#: could plausibly deliver.
MZ_MAX = 6000.0


class _HybridTVAdapter:
    """Episode 14, variant H: the policy outputs an Mz DEMAND; the same QP
    allocator Episode 13's classical controller uses decides which wheels pay
    for it. This is deliberately the only thing that differs from variant C —
    swap this adapter's ``mz_command`` source for a PID and you have C back.

    Held for the whole control interval (RK4 substeps), same zero-order-hold
    ``physics/driver.py``'s ``TorqueVectoring`` established for Episode 13.
    """

    __slots__ = ("allocator", "mz_command")

    def __init__(self, allocator: Allocator):
        self.allocator = allocator
        self.mz_command = 0.0

    def forces(self, demand, loads, state, lateral=None):
        return self.allocator.allocate(
            demand, self.mz_command, loads, steer=state.steer,
            lateral=lateral).forces


class _EndToEndTVAdapter:
    """Episode 14, variant E: the policy outputs four raw per-wheel force
    FRACTIONS directly, in [-1, 1], each scaled by that wheel's own grip-based
    capacity. No allocator call, no shared-demand reconciliation — matching
    the research plan's "none" lower layer for this variant exactly. The
    ``Allocator`` is reused only for its ``capacities()`` method (the friction
    ellipse, not the QP), so a policy action of +1 means "everything this tire
    has left," not an arbitrary fixed force.
    """

    __slots__ = ("allocator", "fractions")

    def __init__(self, allocator: Allocator):
        self.allocator = allocator
        self.fractions = {c: 0.0 for c in CORNERS}

    def forces(self, demand, loads, state, lateral=None):
        caps = self.allocator.capacities(loads, lateral)
        return {c: self.fractions[c] * caps[c] for c in CORNERS}


@dataclass
class EnvConfig:
    """Everything about the task, separate from the car."""

    track: Track = field(default_factory=long_exit)
    params: schema.VehicleParams = field(default_factory=lambda: schema.RV_1)
    dt: float = DT
    #: Speed at the start line.
    #:
    #: **15 m/s, not the 32 m/s the optimal-control episodes use, and the
    #: difference is a task-design choice worth stating.** The corner is 40 m
    #: radius and the car makes 0.97 g, so the fastest it can physically be taken
    #: is 19.5 m/s. Starting at 32 m/s means the very first thing a driver must
    #: do is shed 12.5 m/s — about 1.3 s of hard braking — beginning two seconds
    #: before the corner arrives. A solver that sees the whole road plans that in
    #: one shot. A learner has to discover it by trial and error, and braking
    #: *reduces* the progress reward at the moment it is applied while the payoff
    #: arrives seconds later. Configured that way the policy never once completed
    #: the corner in 250k steps; it simply drove off the road at 65 m every time.
    #:
    #: Starting below the corner speed makes the task learnable without any
    #: reward shaping: the policy first learns to steer, and the progress reward
    #: then pushes it faster until braking becomes necessary on its own terms.
    #: The curriculum is in the task, not in the reward. See FINDINGS F52.
    entry_speed: float = 15.0
    #: Terminal penalty for putting a wheel off the road, in reward units. Large
    #: enough that leaving the track is never worth the progress it buys.
    off_track_penalty: float = 50.0
    #: Multiplies the progress term (``ds * dt``) only — the two penalties
    #: above stay in absolute reward units. **1.0 reproduces every existing
    #: episode exactly.**
    #:
    #: TRACKS.md staging step 5: raising ``off_track_penalty`` alone (50 ->
    #: 500, real circuit training) fixed off-track driving (rate ~1.00 ->
    #: ~0.00) by making a genuinely different failure mode strictly cheaper —
    #: decelerating to a stall carries NO penalty at all, so the policy
    #: learned to coast to a stop rather than risk the road, collapsing
    #: per-section survival distance from ~537 m to ~73 m. Raising
    #: ``progress_scale`` makes the reward for actually covering ground grow
    #: faster than the now-larger fixed penalty shrinks in relative terms,
    #: which is the OTHER lever for the same imbalance (paired with
    #: ``stall_penalty`` below, not a substitute for it — this closes the
    #: "give up slowly" loophole from the other side, by making continuing
    #: to drive worth more, not by making stopping cost something).
    progress_scale: float = 1.0
    #: Terminal penalty for coasting below ``min_speed`` — the loophole
    #: ``off_track_penalty=500`` found: stalling was free, so a policy averse
    #: to the road's risk just stopped instead of driving it. **0.0
    #: reproduces every existing episode exactly.** Kept smaller than
    #: ``off_track_penalty`` by convention (not enforced) so a crash while
    #: genuinely pushing the limit still reads as worse than giving up —
    #: matching this project's stated priority order for Season 4:
    #: on-track, then inside the slip envelope, then fast.
    stall_penalty: float = 0.0
    #: --- TRACKS.md item 19h: the field's actual structure.
    #:
    #: DENSE, speed-scaled cost for running near the track edge, charged every
    #: step rather than once at the boundary. **0.0 reproduces every existing
    #: episode exactly.**
    #:
    #: This is Fuchs et al. (RA-L 2021) `−c_w‖v‖²` and GT Sophy's
    #: `−(time off course)·speed²`, adapted: they penalise wall CONTACT / time
    #: off course and keep driving, which this project's physics cannot do
    #: (there is no off-surface friction model — the car would be on grass with
    #: tarmac grip), so the cost is charged on PROXIMITY to the edge instead,
    #: ramping in over the last ``1 - edge_threshold`` of the usable width.
    #:
    #: Fuchs is explicit that a FIXED-value penalty is the thing that cannot be
    #: fixed by tuning — "the agent either did not react to the penalty or
    #: ended up in a strategy of full braking and standing still, depending on
    #: the strength of the penalty", which is exactly this project's items 11
    #: (ignored at 50) and 12 (stalling exploit at 500). Scaling with kinetic
    #: energy is their documented cure and the reason this term exists.
    #:
    #: Calibration `[DERIVED]`: at 30 m/s hard against the edge, 0.15 · dt ·
    #: v² = 0.15 · 0.02 · 900 = 2.7/step against ~0.6/step of progress — a
    #: ~4.5:1 ratio, inside the field's measured 3-20:1 band (GT Sophy ~7:1 at
    #: Maggiore). Compare the ~500:1 this project used before.
    edge_penalty: float = 0.0
    #: Fraction of the usable half-width beyond which ``edge_penalty`` starts
    #: to ramp. High on purpose: a racing line legitimately uses the full
    #: width, so this must read as "you are about to leave", not "stay in the
    #: middle" — otherwise it fights the very behaviour the series is about.
    edge_threshold: float = 0.75
    #: Per-step cost for being off the centreline, scaled by ``|n|`` as a
    #: fraction of the usable half-width. **0.0 reproduces every existing
    #: episode.**
    #:
    #: **This was the omission that capped the Spa policy at 40% of a lap.**
    #: Measured on the best valid policy (cap 11 m/s): at the moment it left
    #: the road the corner radius was 3,934 m (i.e. straight), speed 11.5 m/s
    #: against a 199 m/s corner limit, slip 1.4 deg, and 0 of 24 exits were
    #: in a corner tighter than 40 m. It was not losing grip or arriving too
    #: fast — it simply could not hold a line, and drifted off on straights.
    #:
    #: ``edge_penalty`` only fires past ``edge_threshold`` (0.75), so below
    #: that there was no restoring force at all and lateral position was a
    #: random walk with an absorbing barrier. Every dense reward in the F105
    #: survey carries a centreline term and this one did not: Jaritz
    #: ``v(cos a − d)``; Evans CTH ``(v/v_max)cos psi − d_c``; Remonda
    #: ``V_x(cos th − sin th − |dist to axis|)``; TC-Driver ``progress − |n|``;
    #: DeepRacer's reward bands. Adding it is not a new idea, it is the
    #: single most universal term in the field.
    cross_track_penalty: float = 0.0
    #: Spawn at a speed the LOCAL corner can actually hold, rather than a flat
    #: ``entry_speed`` everywhere. **False reproduces every existing episode.**
    #:
    #: D6 (item 14) fails ``the_task_is_completable`` on all five prior runs:
    #: Spa's tightest corner caps at 10.1 m/s and every episode spawned at
    #: 15.0 m/s, so any spawn near it began already unsurvivable. Fuchs et al.
    #: spawn rolling at 100 km/h; the fix is a spawn speed the corner allows,
    #: not a fixed number inherited from a single-corner synthetic track.
    spawn_speed_from_curvature: bool = False
    #: Lateral-acceleration budget for that spawn speed, m/s². ~0.8 of the
    #: car's own ~9.5 m/s² limit, so the spawn is inside the envelope rather
    #: than exactly on it.
    spawn_lat_budget: float = 7.6
    #: Distances ahead, in metres, at which curvature is sampled into the
    #: observation. ``None`` uses the module default ``PREVIEW_DISTANCES``,
    #: reproducing every existing episode exactly.
    #:
    #: **Measured, TRACKS.md item 23**: the default reaches 55 m, but the
    #: trained policy runs at up to 42.7 m/s, where braking to a 10 m/s
    #: hairpin needs ~89 m. Above ~32 m/s the car cannot see far enough to
    #: brake for what is coming — 1.29 s of lookahead at peak speed. That is
    #: a structural blindness no reward coefficient can fix, and it is the
    #: most likely reason every configuration so far crashes at 100% of
    #: probes. Changing this changes ``obs_dim``, so a policy trained at one
    #: setting cannot be warm-started into another.
    preview_distances: tuple[float, ...] | None = None
    #: Hard ceiling on speed, m/s. ``None`` (default) reproduces every
    #: existing episode. Above the cap the policy's positive drive is clamped
    #: to zero — a speed limiter, not a penalty, so it cannot be traded away
    #: against progress the way a reward term can.
    #:
    #: **Item 25's finding is why this exists**: the classical driver laps Spa
    #: cleanly at 2.3° slip with ``v_max=12`` but spins at ``v_max=45``, and
    #: the RL policy reaches 42.7 m/s. The task is completable; the policy
    #: simply drives faster than it can control. Hildisch et al. (RLC 2025,
    #: item 19 §4b) use exactly this as a curriculum — "the action space for
    #: the speed command is [0.5; α] with α ∈ [1;7] m/s; α is increased by
    #: 0.5 m/s as soon as the agent completes three consecutive laps without
    #: track-boundary violation."
    speed_cap: float | None = None
    #: Scale penalties by speed instead of applying them at fixed magnitude.
    #: ``False`` reproduces every existing episode.
    #:
    #: **The literature is unanimous and we were the outlier** (FINDINGS
    #: F105/F112). No published limit-driving racing agent uses a dense,
    #: permanently-active, fixed-weight penalty on a continuous state
    #: variable; ours had two. GT Sophy scales off-course and wall penalties
    #: by speed SQUARED (`-(s_o' - s_o)(s_kph')^2`); Fuchs by kinetic energy
    #: (`c_w||v||^2`, c_w = 5e-4); TRI by speed (`q2 * v * alpha_excess`).
    #:
    #: The reason is mechanical: a fixed penalty can be minimised by driving
    #: slowly, so it teaches timidity. A speed-scaled one cannot. Fuchs found
    #: fixed-value penalties produced agents that "either did not react to
    #: the penalty or ended up in a strategy of full braking and standing
    #: still" -- both of which this project hit (F105).
    speed_scaled_penalties: bool = False
    #: Reference speed for the scaling, m/s. The penalty is multiplied by
    #: ``(v / v_ref)``, so at ``v_ref`` it equals its nominal weight and the
    #: existing coefficients keep their meaning.
    penalty_speed_ref: float = 25.0
    #: Cost per step for operating outside the slip envelope, scaled by how far
    #: outside. **0.0 reproduces Episode 9 exactly**, where the envelope is
    #: instrumented and deliberately unenforced.
    #:
    #: Episode 10 onward sets this, and the reason is measured rather than
    #: assumed: sliding beyond the ±12° fit covers ground at 21.0 m/s against
    #: 20.2 m/s inside it, so the unconstrained reward's optimum is genuinely to
    #: slide, and more training finds that faster (F62). A conditioned policy
    #: sliding at 121° tells you nothing about weight distribution.
    #:
    #: This is a **protocol change, recorded as one** (CLAUDE.md rule 9). It does
    #: not fix a bug — the unconstrained environment was doing exactly what it
    #: said. It changes the question from "what will a learner do with an
    #: unguarded model?" (Episode 9's subject) to "how does a car's design affect
    #: a driver who stays inside the physics we can defend?" (Episode 10's).
    #:
    #: Scaled so one degree past the bound costs about as much as a step's
    #: progress: excess/12 x this, against ~0.4 m of progress per step.
    envelope_penalty: float = 0.0
    #: Cost per step for tire workload — the mean over the four wheels of
    #: squared friction-ellipse utilisation. **0.0 reproduces every Episode
    #: 9-14 result**, which is what it must do, because this changes the
    #: question rather than fixing a bug (rule 9).
    #:
    #: Added because Episode 14 compared two variants on tire utilisation and
    #: the comparison turned out to be meaningless: on the exit straight the
    #: reward is progress alone — no off-track penalty, worst slip 0.02-1.08
    #: deg against a 12 deg bound so no envelope penalty either — and summed
    #: per-wheel LATERAL force ranged 83 N to 3,199 N across seeds at identical
    #: reward. Wheels shoving against each other was free, so "does the policy
    #: allocate efficiently" was being asked of an objective that had never
    #: mentioned efficiency. See FINDINGS F95.
    #:
    #: Squared rather than linear so that one saturated wheel costs more than
    #: four half-used ones — which is the same shape as the QP allocator's own
    #: objective (``physics/torque_vectoring.py``), deliberately: the point is
    #: to give BOTH variants the goal the allocator was built around and see
    #: which reaches it, not to hand it to the variant that already has it.
    workload_penalty: float = 0.0
    #: Give up if the car is crawling; otherwise a policy that stops still
    #: collects zero reward forever and wastes the rollout.
    min_speed: float = 3.0
    #: Hard cap on episode length, in steps. 2000 steps at 50 Hz is 40 s, and
    #: the 393 m track takes 26 s at the 15 m/s entry speed — so a slow but
    #: competent lap finishes, and only a genuinely stuck car times out.
    max_steps: int = 2000
    #: Randomise the start along the track so the policy cannot memorise one
    #: opening sequence. 0 disables it.
    start_jitter_m: float = 0.0
    #: --- Episode 12: the differential. ``"open"`` is what Episodes 9-11 drove and
    #: is the default, so every Season 3 result is reproducible unchanged.
    diff: str = "open"
    #: Override the device's torque bias ratio / locking fraction, for the
    #: sensitivity sweeps the [ASSUMED] LSD numbers require (F76).
    torque_bias_ratio: float | None = None
    locking: float | None = None

    #: --- Episode 11: perturbations. Both default to off, so every Episode 9 and
    #: 10 result is produced by exactly the environment those episodes describe.
    #:
    #: Standard deviation of zero-mean Gaussian noise added to the commanded
    #: STEERING action each step, in units of the normalised action.
    #:
    #: **Units trap, measured: this is a fraction of STEER_RATE_MAX at the ROAD
    #: WHEEL, and a driver holds the STEERING WHEEL.** Through a ~13.5:1 rack
    #: [ASSUMED], the closed-loop RMS steer deviation this produces is:
    #:
    #:   0.01 -> 1.6 deg at the steering wheel   (attentive: micro-corrections)
    #:   0.03 -> 4.7 deg                         (distracted: visual-task band)
    #:   0.15 -> 23.4 deg                        (no physical interpretation)
    #:
    #: Episodes 11 and 13 both used 0.15 and both describe it as the driver's
    #: hands. Prefer 0.01, or 0.03 for a loaded driver. See FINDINGS F96. This is the
    #: driver's hands and the steering system, not the policy's own exploration:
    #: it is applied after the policy has chosen, and it is present at deployment.
    #: [ASSUMED] — a real figure would come from steering-robot repeatability data.
    steer_noise: float = 0.0
    #: Multiplier on the tire's peak lateral friction, applied per episode through
    #: the file's ``[SCALING_COEFFICIENTS]`` (``LMUY``) and NEVER by touching a
    #: ``P*`` coefficient. 1.0 is the tire every other episode drives.
    #:
    #: Drawn uniformly from ``[1 - grip_spread, 1 + grip_spread]`` at each reset
    #: when ``grip_spread`` is non-zero: one surface per lap, not per step, which
    #: is what a damp patch or a cold track actually looks like.
    grip_spread: float = 0.0
    #: Vehicle parameters the policy is CONDITIONED ON. Naming one here does two
    #: things at once, and they belong together: the parameter is resampled from
    #: its documented design-sweep range at every reset, and its current value is
    #: appended to the observation, normalised to [-1, 1] over that range.
    #:
    #: Episode 9's policy could drive one car. Comparing designs with a driver
    #: that has to be retrained for each one measures the retraining as much as
    #: the car — every run lands somewhere different, and Season 2's comparisons
    #: were only fair because it was the same solver every time. A policy that
    #: sees the car it is driving can be trained once and asked about any of
    #: them, which is what makes an RL-versus-optimal-control cross-check
    #: possible at all. Empty tuple = Episode 9 behaviour, one fixed car.
    design_keys: tuple[str, ...] = ()
    #: Override the sampling range for a conditioned parameter. Defaults to the
    #: documented ``schema.DESIGN_SWEEP`` entry.
    #:
    #: Worth having because the design-sweep range and the range you want a
    #: policy trained over are not the same thing. ``DESIGN_SWEEP`` says
    #: 0.35-0.65 front mass, but Episode 7 only ever evaluates 0.40-0.65 — so
    #: training below 0.40 spends samples on cars nobody asks about, and those
    #: are the hardest cars in the range (K reaches -0.43 deg/g at 0.40 and gets
    #: worse). Narrowing to the evaluated range is a training decision, not a
    #: change to what the design sweep means, so it lives here rather than in
    #: the schema.
    design_ranges: dict[str, tuple[float, float]] | None = None

    #: --- Episode 14: torque vectoring. ``"none"`` is every Episode 9-11
    #: result unchanged — no allocator is constructed, no adapter is attached,
    #: and the action vector stays exactly [steer_rate, drive_force]. Pinned
    #: by a seal test, the same pattern ``diff="open"`` and ``steer_noise=0.0``
    #: already establish for every other mode this file adds.
    #:
    #: ``"hybrid"`` (variant H) — the policy's third action is an Mz DEMAND,
    #: fed through the same QP allocator variant C's classical controller
    #: uses. ``"end_to_end"`` (variant E) — the policy's action REPLACES
    #: drive_force with four raw per-wheel force fractions and there is no
    #: allocator at all. See ``docs/vehicle-codesign-research-plan.md`` Phase
    #: 4b for the variant table this reproduces.
    tv_mode: str = "none"

    #: --- TRACKS.md staging step 2: closed-loop support. Number of laps that
    #: makes an episode "finished" on a closed (looped) track. **1 reproduces
    #: every existing episode's semantics exactly** — every ``Track`` here is
    #: open, ``self.s`` never approaches ``track.length`` a second time before
    #: the episode ends some other way, and ``track.length * 1 == track.length``
    #: is the termination condition every prior episode already used. Only
    #: meaningful once ``cfg.track`` is a closed ``SampledTrack`` (TRACKS.md §4
    #: step 3 onward).
    n_laps: int = 1


class DrivingEnv:
    """One car on one road, stepped at fixed dt. Gym-like but not gym-dependent.

    Not a ``gym.Env`` subclass on purpose: the interface needed here is four
    methods, and taking the dependency would buy nothing but a version pin.
    """

    def __init__(self, config: EnvConfig | None = None, seed: int | None = None):
        self.cfg = config or EnvConfig()
        assert self.cfg.tv_mode in ("none", "hybrid", "end_to_end"), self.cfg.tv_mode
        self.backend = DoubleTrackBackend(
            self.cfg.params, diff=self.cfg.diff,
            torque_bias_ratio=self.cfg.torque_bias_ratio,
            locking=self.cfg.locking)
        self.rng = np.random.default_rng(seed)
        self._pinned: dict[str, float] | None = None
        self._ref_s = np.linspace(0.0, self.cfg.track.length, 4000)
        _, self._ref_x, self._ref_y, self._ref_head = \
            self.cfg.track.centreline(4000)
        self._tv_adapter = self._build_tv_adapter()
        self.backend.attach_torque_vectoring(self._tv_adapter)
        self.reset()

    # -- geometry ---------------------------------------------------------
    @property
    def obs_dim(self) -> int:
        return 6 + len(self._preview) + len(self.cfg.design_keys)

    def _build_tv_adapter(self):
        """The Episode 14 hook. ``None`` (mode "none") leaves the backend
        exactly as Episodes 9-11 found it — ``attach_torque_vectoring(None)``
        is a no-op, pinned by ``test_torque_vectoring.py``'s own seal test.
        Rebuilt whenever ``self.backend`` is, since the ``Allocator`` caches
        the car's params/tire at construction and a resampled design would
        make a stale one silently wrong.
        """
        if self.cfg.tv_mode == "none":
            return None
        allocator = Allocator(params=self.backend.params, tire=self.backend.tire)
        if self.cfg.tv_mode == "hybrid":
            return _HybridTVAdapter(allocator)
        return _EndToEndTVAdapter(allocator)

    def _design_vector(self) -> np.ndarray:
        """The conditioned parameters, normalised to [-1, 1] over their range."""
        out = []
        for k in self.cfg.design_keys:
            lo, hi = self._range(k)
            v = getattr(self.backend.params, k)
            out.append(2.0 * (v - lo) / (hi - lo) - 1.0)
        return np.asarray(out, dtype=float)

    def _range(self, key: str) -> tuple[float, float]:
        over = (self.cfg.design_ranges or {}).get(key)
        return tuple(over) if over else schema.DESIGN_SWEEP[key]

    def _sample_design(self) -> schema.VehicleParams:
        p = self.cfg.params
        if not self.cfg.design_keys:
            return p
        draw = {k: float(self.rng.uniform(*self._range(k)))
                for k in self.cfg.design_keys}
        draw.update(self._pinned or {})
        return replace(p, **draw)

    @property
    def act_dim(self) -> int:
        # "none": [steer_rate, drive_force]                            = 2
        # "hybrid": [steer_rate, drive_force, mz_command]               = 3
        # "end_to_end": [steer_rate, w_fl, w_fr, w_rl, w_rr]            = 5
        # drive_force does not exist in "end_to_end" — there is no shared
        # demand to reconcile against, per the "none" lower layer in
        # docs/vehicle-codesign-research-plan.md Phase 4b.
        return {"none": 2, "hybrid": 3, "end_to_end": 5}[self.cfg.tv_mode]

    def _road_heading(self, s: float) -> float:
        return float(np.interp(s % self.cfg.track.length, self._ref_s,
                               self._ref_head))

    @property
    def _preview(self) -> tuple[float, ...]:
        return self.cfg.preview_distances or PREVIEW_DISTANCES

    def _curvature_ahead(self) -> np.ndarray:
        # A closed track's curvature already wraps s % length internally
        # (SampledTrack._u_of_s) -- clamping to `length` here would flatten
        # the preview to a single repeated point right where a real circuit's
        # driver needs to see the NEXT corner coming. An open Track has no
        # wraparound and must stay clamped, or curvature(s) beyond the last
        # segment just extrapolates that segment flat, which is at least
        # bounded rather than wrong -- clamping keeps that behaviour exactly.
        if getattr(self.cfg.track, "closed", False):
            return np.array([self.cfg.track.curvature(self.s + d)
                             for d in self._preview])
        return np.array([self.cfg.track.curvature(
            min(self.s + d, self.cfg.track.length)) for d in self._preview])

    def _spawn_speed(self) -> float:
        """Entry speed for this episode's own spawn point.

        ``cfg.entry_speed`` unless ``spawn_speed_from_curvature`` is on, in
        which case it is capped at what the LOCAL corner can hold —
        ``sqrt(a_lat / |kappa|)``. See ``EnvConfig.spawn_speed_from_curvature``
        for why (D6's ``the_task_is_completable`` fails on every run so far).
        Floored just above ``min_speed`` so a spawn inside a hairpin does not
        begin already stalled, which would be a different unwinnable start
        rather than a fix for the first one.
        """
        if not self.cfg.spawn_speed_from_curvature:
            return self.cfg.entry_speed
        kappa = abs(float(self.cfg.track.curvature(self.s)))
        v_corner = math.sqrt(self.cfg.spawn_lat_budget / max(kappa, 1e-9))
        return float(min(self.cfg.entry_speed,
                        max(v_corner, self.cfg.min_speed + 1.0)))

    # -- the loop ---------------------------------------------------------
    def _tire_for(self, grip: float):
        """The tire at ``grip`` x nominal peak lateral friction.

        Retargeted through ``[SCALING_COEFFICIENTS]``, never by editing a ``P*``
        coefficient — that is a hard invariant of this project, because the ``P*``
        values are a published fit and a hand-edited one is no longer traceable to
        anything. ``LMUY`` is the sanctioned knob and it composes with whatever the
        file already carries.
        """
        base = default_tire()
        if grip == 1.0:
            return base
        return base.rescaled(lmuy=base.scaling.lmuy * grip)

    def reset(self, seed: int | None = None) -> np.ndarray:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.s = float(self.rng.uniform(0.0, self.cfg.start_jitter_m)
                       if self.cfg.start_jitter_m > 0 else 0.0)
        #: Distance covered SINCE this reset, independent of `self.s`'s
        #: absolute value. `finished` is defined against this, not against
        #: `self.s >= track.length` -- see the comment on `finished` in
        #: `step()` for why the absolute form is a real bug on a closed
        #: track with a jittered or externally-set start.
        self._dist_since_reset = 0.0
        self.n = 0.0
        self.xi = 0.0
        # One surface per lap. Drawn before the backend is built so the design
        # resample and the grip draw cannot disagree about which tire is fitted.
        self.grip = 1.0
        if self.cfg.grip_spread:
            self.grip = float(self.rng.uniform(1.0 - self.cfg.grip_spread,
                                               1.0 + self.cfg.grip_spread))
        if self.cfg.design_keys or self.cfg.grip_spread:
            base = self._sample_design() if self.cfg.design_keys else self.cfg.params
            self.backend = DoubleTrackBackend(
                base, tire=self._tire_for(self.grip), diff=self.cfg.diff,
                torque_bias_ratio=self.cfg.torque_bias_ratio,
                locking=self.cfg.locking)
            # The Allocator caches params/tire at construction, so a resampled
            # design needs a fresh one — reusing the old adapter here would be
            # silently wrong in exactly the way F72 was silently wrong.
            self._tv_adapter = self._build_tv_adapter()
        self.backend.attach_torque_vectoring(self._tv_adapter)
        self.backend.reset(self._spawn_speed())
        self.steps = 0
        self.done = False
        self.log = {k: [] for k in
                    ("s", "n", "xi", "speed", "steer", "drive", "reward",
                     "alpha_max_deg", "kappa_max", "load_min", "load_max",
                     "envelope_violation", "a_y", "utilisation_max")}
        for c in CORNERS:
            self.log[f"fx_{c}"] = []
            self.log[f"fy_{c}"] = []
            self.log[f"fz_{c}"] = []
        if self.cfg.tv_mode != "none":
            self.log["tv_extra_action"] = []
        return self.observe()

    def observe(self) -> np.ndarray:
        st = self.backend.state
        speed = math.hypot(st.v_x, st.v_y)
        beta = math.atan2(st.v_y, max(st.v_x, 1e-3))
        return np.concatenate([
            np.array([
                speed / 50.0,               # normalised, schema-style
                self.n / float(self.cfg.track.half_width_at(self.s)),
                self.xi / math.radians(60.0),
                st.yaw_rate / 2.0,
                beta / math.radians(30.0),
                st.steer / STEER_MAX,
            ], dtype=float),
            self._curvature_ahead() * 40.0,   # ~1 at the corner radius
            self._design_vector(),
        ])

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, dict]:
        """One control interval.

        ``action`` is [steer_rate, drive_force] in "none" mode (Episodes 9-11,
        unchanged); [steer_rate, drive_force, mz_command] in "hybrid" mode
        (Episode 14 variant H); [steer_rate, w_fl, w_fr, w_rl, w_rr] in
        "end_to_end" mode (variant E, no drive_force channel — see ``act_dim``).
        All components in [-1, 1].
        """
        if self.done:
            raise RuntimeError("step() after done; call reset()")
        a = np.clip(np.asarray(action, dtype=float), -1.0, 1.0)
        # Steering noise is added AFTER the policy has chosen and after the clip,
        # then re-clipped: it is the hands and the linkage, not the policy. It is
        # therefore present at deployment, which is the whole point — Episode 9's
        # exploration noise was an artefact of training and vanished on the car
        # you would ship; this does not vanish. Steering only: throttle jitter is
        # a different mechanism and mixing them would make the result
        # unattributable.
        if self.cfg.steer_noise:
            a = a.copy()
            a[0] = np.clip(a[0] + self.rng.normal(0.0, self.cfg.steer_noise),
                           -1.0, 1.0)

        # Update the Episode 14 adapter's held command BEFORE stepping the
        # backend, so it is in place for all four RK4 substeps — the same
        # zero-order hold physics/driver.py's TorqueVectoring uses. "none"
        # mode never reaches here (act_dim 2, no a[2:]).
        if self.cfg.tv_mode == "hybrid":
            self._tv_adapter.mz_command = float(a[2]) * MZ_MAX
        elif self.cfg.tv_mode == "end_to_end":
            for i, c in enumerate(CORNERS):
                self._tv_adapter.fractions[c] = float(a[1 + i])

        drive_action = 0.0 if self.cfg.tv_mode == "end_to_end" else float(a[1])
        if self.cfg.speed_cap is not None:
            # Speed limiter, applied to the ACTION before the physics: above
            # the cap the policy may coast or brake but not accelerate. A
            # limiter rather than a reward term, so it cannot be traded away
            # against progress -- see EnvConfig.speed_cap.
            v_now = math.hypot(self.backend.state.v_x, self.backend.state.v_y)
            if v_now >= self.cfg.speed_cap:
                drive_action = min(drive_action, 0.0)
        act = self.backend.act_space.pack(
            steer_rate=a[0] * STEER_RATE_MAX,
            # In "end_to_end" mode this net demand is never read — the
            # attached adapter ignores it entirely (there is no shared demand
            # to reconcile against). Passed as 0.0 rather than reusing a
            # wheel-fraction slot, so nothing here can be mistaken for meaning
            # something it does not.
            drive_force=(drive_action * DRIVE_MAX if drive_action >= 0
                        else drive_action * BRAKE_MAX),
        )
        _, info = self.backend.step(act, self.cfg.dt)
        st = self.backend.state
        speed = math.hypot(st.v_x, st.v_y)

        # Curvilinear kinematics, the same relations physics/optimal_control.py
        # integrates in the distance domain:
        #
        #     s_dot  = (v_x cos xi - v_y sin xi) / (1 - n * kappa)
        #     n_dot  =  v_x sin xi + v_y cos xi
        #     xi_dot =  r - kappa * s_dot
        #
        # All three rates come from the state BEFORE any of them is integrated.
        # An earlier version advanced xi first and then used it to compute s_dot,
        # and used kappa*speed rather than kappa*s_dot for the road's own turn
        # rate — both wrong, and both the sort of wrong that still produces a
        # plausible-looking lap.
        kappa = float(self.cfg.track.curvature(self.s))
        s_dot = ((st.v_x * math.cos(self.xi) - st.v_y * math.sin(self.xi))
                 / max(1.0 - self.n * kappa, 1e-3))
        n_dot = st.v_x * math.sin(self.xi) + st.v_y * math.cos(self.xi)
        xi_dot = st.yaw_rate - kappa * s_dot
        ds = s_dot
        self.s += s_dot * self.cfg.dt
        self._dist_since_reset += s_dot * self.cfg.dt
        self.n += n_dot * self.cfg.dt
        self.xi = self._wrap(self.xi + xi_dot * self.cfg.dt)

        self.steps += 1
        off = abs(self.n) > float(self.cfg.track.half_width_at(self.s))
        # NOT `self.s >= track.length * n_laps`. That is absolute position,
        # so on a closed track a jittered or manually-set start (every
        # per-section probe does `env.reset(); env.s = s0`, and training
        # itself uses `start_jitter_m`) needs to cover only
        # `track.length - s0` to satisfy it -- an easier bar the further
        # around the lap the episode starts, silently inflating both the
        # training-time finish signal and every per-section "finished"
        # count read from it. Found chasing an eval that reported
        # off_track=0.00, finished=1.00 for a policy that, correctly
        # scored, had never actually driven a full lap from most of its
        # 24 starts. `_dist_since_reset` is independent of where `self.s`
        # started or was set from outside.
        finished = (self._dist_since_reset
                   >= self.cfg.track.length * self.cfg.n_laps)
        stalled = speed < self.cfg.min_speed
        timeout = self.steps >= self.cfg.max_steps
        self.done = bool(off or finished or stalled or timeout)

        # reward: progress, a penalty for falling off, and — from Episode 10 on —
        # a cost for operating where the tire model has no fit.
        reward = ds * self.cfg.dt * self.cfg.progress_scale
        if off:
            reward -= self.cfg.off_track_penalty
        if stalled and self.cfg.stall_penalty > 0.0:
            reward -= self.cfg.stall_penalty
        # One factor, computed once, applied to every dense penalty below.
        pscale = 1.0
        if self.cfg.speed_scaled_penalties:
            pscale = speed / max(self.cfg.penalty_speed_ref, 1e-9)
        if self.cfg.cross_track_penalty > 0.0:
            # Gentle, everywhere -- a restoring pull toward the centreline,
            # unlike edge_penalty which only bites near the boundary.
            use_ct = abs(self.n) / max(
                float(self.cfg.track.half_width_at(self.s)), 1e-9)
            reward -= (self.cfg.cross_track_penalty * self.cfg.dt * use_ct
                      * pscale)
        if self.cfg.edge_penalty > 0.0:
            # Dense, speed-scaled, charged every step near the edge -- see
            # EnvConfig.edge_penalty. Uses |n| BEFORE the off-track test so a
            # step that leaves the road is also charged for the speed it left
            # at, rather than only the flat terminal penalty.
            thr = self.cfg.edge_threshold
            use = abs(self.n) / max(float(self.cfg.track.half_width_at(self.s)), 1e-9)
            ramp = min(max((use - thr) / max(1.0 - thr, 1e-9), 0.0), 1.0)
            if ramp > 0.0:
                reward -= (self.cfg.edge_penalty * self.cfg.dt
                           * speed * speed * ramp)
        if self.cfg.envelope_penalty > 0.0:
            sl = self.backend.slip_angles()
            worst = math.degrees(max(abs(v) for v in sl.values()))
            excess = max(0.0, worst - math.degrees(ENVELOPE_SLIP_MAX))
            if excess > 0.0:
                reward -= pscale * self.cfg.envelope_penalty * excess / math.degrees(
                    ENVELOPE_SLIP_MAX)
        if self.cfg.workload_penalty > 0.0:
            # Mean squared friction-ellipse utilisation over the four wheels.
            # Computed from the SAME per-wheel forces _record logs, so the
            # reward and the reported metric cannot describe different things.
            wheels = self.backend._last_wheels
            if wheels:
                acc = 0.0
                for c in CORNERS:
                    w = wheels[c]
                    fz = max(w.fz, 1.0)
                    u = math.hypot(w.fx / float(self.backend.tire.peak_fx(fz)),
                                   w.fy / float(self.backend.tire.peak_fy(fz)))
                    acc += u * u
                reward -= self.cfg.workload_penalty * acc / len(CORNERS)

        # Log the reward the learner actually receives, penalty included. An
        # earlier version logged only the progress term, so every training
        # summary read back a healthy positive return for episodes that had just
        # driven off the road and been penalised 50 for it.
        self._record(ds, a, speed, info, reward, drive_action)
        return self.observe(), float(reward), self.done, {
            "s": self.s, "n": self.n, "speed": speed, "off_track": off,
            "finished": finished, "stalled": stalled, "timeout": timeout,
            "envelope_violation": bool(info.envelope_violation),
        }

    @staticmethod
    def _wrap(a: float) -> float:
        return (a + math.pi) % (2.0 * math.pi) - math.pi

    def _record(self, ds, a, speed, info, reward, drive_action) -> None:
        """Everything CLAUDE.md rule 4 demands, every step, no exceptions.

        Extended for Episode 14 with lateral acceleration and per-wheel
        friction-ellipse utilisation — the fields ``HANDOFF.md`` flagged this
        environment as missing, and the only way to verify a torque-vectoring
        result is measuring anything real rather than an under-driving policy
        that never saturates a tire. Same fields ``physics/driver.py``'s
        ``drive_lap()`` already logs for Episode 13, so the two can share
        plotting code.
        """
        sl = self.backend.slip_angles()
        loads = self.backend.wheel_loads(info.a_x, info.a_y)
        wheels = self.backend._last_wheels
        self.log["s"].append(self.s)
        self.log["n"].append(self.n)
        self.log["xi"].append(self.xi)
        self.log["speed"].append(speed)
        self.log["steer"].append(self.backend.state.steer)
        self.log["drive"].append(float(drive_action))
        self.log["reward"].append(float(reward))
        self.log["alpha_max_deg"].append(
            math.degrees(max(abs(v) for v in sl.values())))
        self.log["kappa_max"].append(0.0)
        self.log["load_min"].append(min(loads.values()))
        self.log["load_max"].append(max(loads.values()))
        self.log["envelope_violation"].append(bool(info.envelope_violation))
        self.log["a_y"].append(float(info.a_y))
        util = []
        for c in CORNERS:
            w = wheels.get(c) if wheels else None
            fx, fy, fz = (w.fx, w.fy, w.fz) if w else (0.0, 0.0, loads[c])
            self.log[f"fx_{c}"].append(float(fx))
            self.log[f"fy_{c}"].append(float(fy))
            self.log[f"fz_{c}"].append(float(fz))
            fz_safe = max(fz, 1.0)
            fx_p = float(self.backend.tire.peak_fx(fz_safe))
            fy_p = float(self.backend.tire.peak_fy(fz_safe))
            util.append(math.hypot(fx / fx_p, fy / fy_p))
        self.log["utilisation_max"].append(max(util))
        if self.cfg.tv_mode != "none":
            self.log["tv_extra_action"].append(np.asarray(a[2:], dtype=float)
                                               if self.cfg.tv_mode == "hybrid"
                                               else np.asarray(a[1:], dtype=float))

    def set_design(self, **kw) -> None:
        """Pin the conditioned parameters instead of resampling them.

        Used for evaluation: train across the whole design range, then ask the
        one policy about a specific car. Takes effect at the next ``reset``.

        Pinning has to survive ``reset``, which is where the resampling happens.
        An earlier version cleared ``design_keys`` to stop the draw and then put
        it back so the observation stayed the right width — which simply re-armed
        the resampling, and every "pinned" evaluation silently ran on a random
        car. The pin is now separate state that ``reset`` checks.
        """
        unknown = set(kw) - set(self.cfg.design_keys)
        assert not unknown, f"not conditioned on {sorted(unknown)}"
        self._pinned = dict(kw)

    def history(self) -> dict[str, np.ndarray]:
        return {k: np.asarray(v) for k, v in self.log.items()}


def rollout(env: DrivingEnv, policy, seed: int | None = None) -> dict:
    """Drive one episode with ``policy(obs) -> action`` and return the history.

    Metrics are computed downstream from the logged arrays, never inside the
    loop (CLAUDE.md rule 7) — "what counts as the apex" gets redefined three
    times and re-running a training job to answer it is not acceptable.
    """
    obs = env.reset(seed)
    total = 0.0
    while not env.done:
        obs, r, done, info = env.step(policy(obs))
        total += r
    h = env.history()
    return {
        **h,
        "return": total,
        "steps": int(env.steps),
        # Relative to this episode's own start, not absolute `s` -- the
        # env tracks it; recomputing from `h["s"][-1]` is the bug this
        # module's `step()` documents at `finished`.
        "finished": bool(env._dist_since_reset
                         >= env.cfg.track.length * env.cfg.n_laps),
        "off_track": bool(abs(h["n"][-1]) >
                          float(env.cfg.track.half_width_at(h["s"][-1]))),
        "distance_m": float(env._dist_since_reset),
        "lap_time_s": float(env.steps * env.cfg.dt),
        "worst_slip_deg": float(np.max(h["alpha_max_deg"])),
        "envelope_occupancy": float(np.mean(h["envelope_violation"])),
        "slip_over_12deg_fraction": float(np.mean(h["alpha_max_deg"] > 12.0)),
        # Episode 14: is this rollout anywhere near the tire's limit at all?
        # Torque vectoring only acts where there is saturated lateral grip to
        # trade against — a policy that never approaches peak_a_y_g measures
        # nothing about torque vectoring, whatever else it measures. Same two
        # properties physics.driver.Lap exposes for Episode 13, so a TV result
        # can be checked the same way regardless of which controller made it.
        "peak_a_y_g": float(np.max(np.abs(h["a_y"])) / schema.G),
        "mean_utilisation": float(np.mean(h["utilisation_max"])),
    }


__all__ = ["DrivingEnv", "EnvConfig", "rollout", "DT", "PREVIEW_DISTANCES",
           "ENVELOPE_SLIP_MAX", "MZ_MAX",
           "STEER_RATE_MAX", "STEER_MAX", "DRIVE_MAX", "BRAKE_MAX"]
