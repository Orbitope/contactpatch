"""Replay tests for the speed-cap curriculum gate.

**Why this file exists.** Four separate bugs in this project's curriculum
logic reached a 75-minute training run before being noticed:

  1. the selected checkpoint scored at the curriculum's FINAL cap (F109)
  2. the cap raised past the policy's competence and destroyed it
  3. the release latch fired at update 49, mid-adaptation, and froze the cap
     for the remaining 195 updates
  4. the gate read `speed_mean`, which PPO did not record, so it would have
     read NaN forever

Every one was "smoke tested" first. That is the point: a smoke test runs the
code for 3-14 updates and proves it does not crash. **It cannot exercise a
feedback loop whose failure mode appears at update 49.**

These tests drive the gate with SYNTHETIC update records describing policy
behaviours we know we care about -- a policy slowly learning to use new
headroom, one genuinely at the grip limit, one sliding outside the tyre fit
-- and assert what the cap does. Milliseconds, not 75 minutes.
"""

import numpy as np
import pytest

from experiments.tracks_pilot import spa_pushlimit as PL


class GateHarness:
    """Runs `spa_pushlimit`'s gate over a scripted speed trace.

    Mirrors the real `on_update` decision structure. Kept deliberately small
    and explicit rather than importing the closure, so the ASSERTIONS are
    about intended behaviour rather than a restatement of the implementation
    (CLAUDE.md rule 11).
    """

    def __init__(self, cap0=13.0, step=1.5, cap_max=60.0):
        self.cap, self.step, self.cap_max = cap0, step, cap_max
        self.hot = self.cold = 0
        self.last = -99
        self.raises = []
        self.caps = []

    def feed(self, update, speed, slip=5.0):
        ratio = speed / self.cap
        binding = ratio >= PL.CAP_BINDING_RATIO
        over = slip > PL.SLIP_BOUND_DEG
        if binding:
            self.hot += 1
            self.cold = 0
        elif update - self.last >= PL.CAP_ADAPT_UPDATES:
            self.cold += 1
            self.hot = 0
        if (binding and not over and self.cap < self.cap_max
                and update - self.last >= PL.CAP_MIN_UPDATES_BETWEEN):
            self.cap = min(self.cap + self.step, self.cap_max)
            self.last = update
            self.raises.append(update)
        self.caps.append(self.cap)
        return self.cap


def test_a_policy_slowly_learning_the_new_headroom_is_not_mistaken_for_grip():
    """THE BUG THAT COST A RUN. After a raise the policy's mean speed dips and
    then climbs back over tens of updates. That climb must not be read as
    'the tyres will not allow more' and must not stop the curriculum."""
    g = GateHarness()
    # Measured shape from the real run: 85% -> 97% of the cap over ~60 updates.
    for u in range(200):
        ratio = 0.85 + 0.12 * min(u / 60.0, 1.0)
        g.feed(u, speed=ratio * g.cap, slip=6.0)
    assert g.cap > 13.0 + 3 * 1.5, (
        f"cap stalled at {g.cap} -- a policy that reaches 97% of its cap is "
        f"limited by the CAP, and the curriculum must keep raising it")


def test_the_gate_does_not_latch_after_a_quiet_stretch():
    """A stretch below the threshold must not permanently end the curriculum.
    The first version set `released=True` and never raised again."""
    g = GateHarness()
    for u in range(40):                       # genuinely slow: grip-limited
        g.feed(u, speed=0.70 * g.cap, slip=6.0)
    frozen_at = g.cap
    for u in range(40, 160):                  # then it learns, and pushes again
        g.feed(u, speed=0.98 * g.cap, slip=6.0)
    assert g.cap > frozen_at, (
        "gate latched: it stopped raising permanently after a quiet stretch, "
        "so any premature dip ends the curriculum for good")


def test_a_genuinely_grip_limited_policy_stops_the_cap():
    """The curriculum's terminating condition. A policy that will not go
    faster than 70% of its cap, however long you wait, must not have the cap
    raised out from under it forever."""
    g = GateHarness()
    for u in range(300):
        g.feed(u, speed=0.70 * g.cap, slip=9.0)
    assert g.cap == 13.0, f"cap rose to {g.cap} on a policy never near it"


def test_the_cap_never_rises_while_outside_the_tyre_fit():
    """Rule 4. Even pinned against the cap, a policy already sliding past the
    12 degree bound must not be given more speed."""
    g = GateHarness()
    for u in range(200):
        g.feed(u, speed=0.99 * g.cap, slip=PL.SLIP_BOUND_DEG + 3.0)
    assert g.cap == 13.0, (
        f"cap rose to {g.cap} while slip exceeded the tyre-model bound")


def test_raises_respect_the_cooldown():
    g = GateHarness()
    for u in range(120):
        g.feed(u, speed=0.99 * g.cap, slip=5.0)
    gaps = np.diff(g.raises)
    assert (gaps >= PL.CAP_MIN_UPDATES_BETWEEN).all(), (
        f"raises {g.raises} violate the {PL.CAP_MIN_UPDATES_BETWEEN}-update "
        f"cooldown; the policy gets no time to adapt")


def test_the_cap_is_bounded():
    g = GateHarness(cap_max=20.0)
    for u in range(400):
        g.feed(u, speed=0.99 * g.cap, slip=5.0)
    assert g.cap == 20.0
