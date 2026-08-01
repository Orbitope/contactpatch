"""Audit of the canonical policy evaluator and the start-relative `finished`.

These exist because a bug in `finished` survived ~20 training runs and put a
wrong claim into FINDINGS.md. Each test below is written to FAIL against the
old absolute-`s` definition, so the suite would have caught it.
"""

import numpy as np
import pytest

from physics.rl_env import DrivingEnv, EnvConfig
from physics.batched_env import BatchedDrivingEnv
from physics.track import Track, long_exit
from physics.tracks_data import load_real_track
from experiments.tracks_pilot import policy_eval as PE


def _closed_spa():
    return load_real_track("Spa")


# --- PASS 1: the bug itself -------------------------------------------------

def test_finished_is_relative_to_the_episode_start_not_absolute_s():
    """A probe started 90% round the lap must NOT be 'finished' after
    covering only the remaining 10%. This is the F109 bug exactly."""
    spa = _closed_spa()
    env = DrivingEnv(EnvConfig(track=spa, max_steps=10, start_jitter_m=0.0))
    env.reset(0)
    env.s = 0.99 * spa.length
    assert env._dist_since_reset == 0.0
    # Force s past the line without covering the distance.
    env.s = spa.length + 5.0
    # The old condition (s >= length) is now true; the correct one is not.
    assert env.s >= spa.length, "precondition: old rule would fire here"
    assert env._dist_since_reset < spa.length
    _, _, _, info = env.step(np.array([0.0, 0.0]))
    assert not info["finished"], (
        "finished fired on absolute s -- the F109 bug is back")


def test_finished_still_fires_when_the_distance_is_genuinely_covered():
    """Guard against 'fixing' it by making finished unreachable."""
    spa = _closed_spa()
    env = DrivingEnv(EnvConfig(track=spa, max_steps=10, start_jitter_m=0.0))
    env.reset(0)
    env._dist_since_reset = spa.length + 1.0
    _, _, _, info = env.step(np.array([0.0, 0.0]))
    assert info["finished"]


def test_batched_finished_is_also_start_relative():
    spa = _closed_spa()
    b = BatchedDrivingEnv(EnvConfig(track=spa, max_steps=10,
                                    start_jitter_m=spa.length), n=4, seed=0)
    b.reset(0)
    b.s = np.full(4, spa.length + 5.0)          # past the absolute line...
    b._start_s = np.full(4, 0.9 * spa.length)   # ...but barely moved
    _, _, _, info = b.step(np.zeros((4, b.act_dim)))
    assert not info["finished"].any(), "batched finished fired on absolute s"


def test_episode_distance_is_start_relative():
    """PPO's training-time distance metric reads this; if it stays absolute
    the training curve is measuring start position, not driving.

    Forces a termination rather than hoping for one -- the first version of
    this test guarded the assertion with `if len(...)` and passed vacuously
    against the buggy code, which is the same class of mistake as the bug.
    """
    spa = _closed_spa()
    b = BatchedDrivingEnv(EnvConfig(track=spa, max_steps=1,
                                    start_jitter_m=spa.length), n=8, seed=0)
    b.reset(0)
    b._start_s = np.full(8, 0.95 * spa.length)
    b.s = np.full(8, 0.99 * spa.length)
    _, _, dones, info = b.step(np.zeros((8, b.act_dim)))
    assert dones.all(), "max_steps=1 must terminate every instance"
    got = info["episode_distance"]
    assert len(got) == 8, f"expected 8 terminated instances, got {len(got)}"
    # ~0.04 of a lap actually covered; the absolute form would report ~0.99.
    assert (got < 0.5 * spa.length).all(), (
        f"episode_distance looks absolute: {got[:3]} vs lap {spa.length:.0f}")


# --- PASS 2: the evaluator's own contract -----------------------------------

def test_termination_reasons_account_for_every_probe():
    """Every probe ends for exactly one logged reason. If these do not sum
    to ~1 the report is hiding a case."""
    res = PE.evaluate(_stub_model(), long_exit(), n_sections=4, max_steps=300)
    total = (res.finish_rate + res.off_track_rate
             + res.stall_rate + res.timeout_rate)
    assert total == pytest.approx(1.0, abs=1e-9), (
        f"termination reasons sum to {total}, not 1 -- a probe ended for a "
        f"reason the report does not name")


def test_validity_verdict_follows_rule_4_and_gates_the_headline():
    res = PE.evaluate(_stub_model(), long_exit(), n_sections=4, max_steps=300)
    res.sections_over_bound = 3
    res.envelope_occupancy = 0.02
    assert not res.valid
    assert "NOT QUOTABLE" in res.headline()
    res.sections_over_bound = 0
    res.envelope_occupancy = 0.0
    assert res.valid
    assert "NOT QUOTABLE" not in res.headline()


def test_distance_never_exceeds_one_lap_per_probe():
    """n_laps=1: no probe can report more than a lap of travel."""
    spa = _closed_spa()
    res = PE.evaluate(_stub_model(), spa, speed_cap=11.0, n_sections=3,
                      max_steps=400)
    for r in res.sections:
        assert r["distance_travelled"] <= spa.length + 1.0


def _stub_model():
    """An untrained net. The evaluator's CONTRACT is what is under test here,
    not any policy's competence."""
    from physics.ppo import ActorCritic
    probe = DrivingEnv(EnvConfig(track=long_exit()))
    return ActorCritic(probe.obs_dim, probe.act_dim, 64, (-2.5, -1.0))
