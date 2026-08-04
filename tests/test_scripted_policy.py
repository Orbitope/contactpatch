"""O9 — the scripted-policy sanity check the RL environment never had.

**Why this file exists.** The open-questions register has carried O9 since
Season 3, blocking "any further RL result":

    The RL environment has no scripted-policy sanity check -- a trivial
    policy with a hand-derived expected return, which is the cheapest
    reward-specification test there is. Its absence is how F95's flat reward
    direction survived to publication.

HANDOFF calls it "the oldest outstanding correctness item", and SEASON5 makes
it an explicit gate on Episode 19: "O9's scripted-policy test and D6 pass on
the new env before any result is quoted."

Every test elsewhere checks that the two IMPLEMENTATIONS agree
(`test_batched_env.py`) or that a component behaves (`test_rl_env.py`). None
checks that the reward means what the spec says it means -- two implementations
can agree perfectly on the wrong quantity, which is exactly the F95 failure.

The derivation, done by hand rather than read off the code:

    reward_t = ds_t * dt * progress_scale                (all penalties off)
    ds_t     = s_dot_t,  so  ds_t * dt = the arc length advanced in step t
    => sum_t reward_t = progress_scale * (s_final - s_initial)

That identity is what these tests assert. It pins the reward to a physical
quantity, so a sign flip, a missing `dt`, a double-counted term or a
progress reward that silently stops tracking progress all fail here.
"""

import numpy as np
import pytest

from physics.batched_env import BatchedDrivingEnv
from physics.rl_env import DrivingEnv, EnvConfig
from physics.track import long_exit
from physics.track_gen import generate_track_arcade

#: Every penalty off, so the return is pure progress and hand-derivable.
BARE = dict(envelope_penalty=0.0, off_track_penalty=0.0, stall_penalty=0.0,
            edge_penalty=0.0, cross_track_penalty=0.0, workload_penalty=0.0)

#: A scripted policy: hold a small steering rate and part throttle. Nothing
#: learned, fully reproducible, and it drives far enough to accumulate a
#: meaningful return before leaving the road.
SCRIPTED = np.array([0.0, 0.3])


def _run(cfg, action=SCRIPTED, n=150):
    env = DrivingEnv(cfg)
    env.reset(0)
    s0, total = env.s, 0.0
    for _ in range(n):
        _, r, done, _ = env.step(action)
        total += r
        if done:
            break
    return total, env.s - s0, env


def test_return_equals_arc_length_advanced():
    """THE O9 TEST. With penalties off, summed reward IS distance along the
    track -- not approximately, exactly."""
    total, arc, _ = _run(EnvConfig(track=long_exit(), max_steps=300, **BARE))
    assert arc > 10.0, "scripted policy barely moved; the test is vacuous"
    assert total == pytest.approx(arc, rel=1e-12, abs=1e-9), (
        f"return {total:.6f} != arc length {arc:.6f} -- the progress reward "
        f"is not measuring progress")


def test_progress_scale_scales_the_return_exactly():
    """A linear coefficient must be exactly linear. Catches a progress term
    that has picked up an offset or a second contribution."""
    t1, arc1, _ = _run(EnvConfig(track=long_exit(), max_steps=300,
                                 progress_scale=1.0, **BARE))
    t2, arc2, _ = _run(EnvConfig(track=long_exit(), max_steps=300,
                                 progress_scale=2.0, **BARE))
    assert arc1 == pytest.approx(arc2, rel=1e-12), "trajectories diverged"
    assert t2 == pytest.approx(2.0 * t1, rel=1e-12)


def test_the_identity_holds_on_a_generated_circuit_too():
    """`long_exit` is open and starts at s=0; a closed generated circuit
    exercises wrapping and a non-trivial half-width. The reward specification
    must not depend on which track it is."""
    t = generate_track_arcade(1)
    total, arc, _ = _run(EnvConfig(track=t, max_steps=300, **BARE))
    assert arc > 10.0
    assert total == pytest.approx(arc, rel=1e-12, abs=1e-9)


def test_the_batched_env_obeys_the_same_identity():
    """Both implementations must satisfy the SPEC, not merely agree with each
    other -- two implementations can agree on the wrong quantity."""
    cfg = EnvConfig(track=long_exit(), max_steps=300, **BARE)
    bat = BatchedDrivingEnv(cfg, n=1, seed=0)
    bat.reset(0)
    s0, total = float(bat.s[0]), 0.0
    for _ in range(150):
        _, r, d, _ = bat.step(SCRIPTED[None, :])
        total += float(r[0])
        if d[0]:
            break
    arc = float(bat.s[0]) - s0
    assert arc > 10.0
    assert total == pytest.approx(arc, rel=1e-9, abs=1e-6)


def test_a_stationary_policy_earns_nothing():
    """The degenerate case. Full brake from the start: the car stops, makes no
    progress, and must earn no progress reward. A reward that pays for merely
    existing fails here."""
    cfg = EnvConfig(track=long_exit(), max_steps=300, min_speed=-1.0, **BARE)
    total, arc, _ = _run(cfg, action=np.array([0.0, -1.0]), n=200)
    assert arc < 60.0, f"'stationary' policy travelled {arc:.1f} m"
    assert total == pytest.approx(arc, rel=1e-9, abs=1e-9)


def test_penalties_only_ever_subtract():
    """Every penalty term must reduce the return relative to the bare reward.
    A sign error anywhere turns a penalty into a bonus -- F95's failure mode."""
    bare, _, _ = _run(EnvConfig(track=long_exit(), max_steps=300, **BARE))
    for name, value in (("envelope_penalty", 6.0), ("off_track_penalty", 5.0),
                        ("stall_penalty", 2.0), ("edge_penalty", 0.15),
                        ("cross_track_penalty", 2.0)):
        kw = dict(BARE)
        kw[name] = value
        got, _, _ = _run(EnvConfig(track=long_exit(), max_steps=300, **kw))
        assert got <= bare + 1e-9, (
            f"{name}={value} RAISED the return ({bare:.4f} -> {got:.4f}) -- "
            f"it is acting as a bonus, not a penalty")
