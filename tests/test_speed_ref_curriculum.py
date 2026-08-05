"""A curriculum on the speed PLAN must actually reach the reward.

`speed_ref_penalty` charges the excess over `driver.SpeedProfile`'s target.
Both environments build that plan once and cache it -- the batched one in
`__init__`, the scalar one lazily -- so assigning `cfg.speed_ref_a_lat` on a
live env changes an attribute nobody reads again, and a curriculum built that
way silently does not happen. The run still trains, still logs a rising
`a_lat`, and still produces a plausible table.

`spa_curriculum` hit the matching version of this with the scalar cap and had
to mutate both live envs, eval env included. These tests pin the plan version
end to end: not "the attribute changed" but "the reward changed", which is the
only thing that decides whether the curriculum happened.
"""

from __future__ import annotations

import numpy as np
import pytest

from physics import schema
from physics.batched_env import BatchedDrivingEnv
from physics.rl_env import DrivingEnv, EnvConfig
from physics.tracks_data import load_real_track

LOW = 0.45 * schema.G
HIGH = 0.97 * schema.G


def _cfg(a_lat, **over):
    base = dict(track=load_real_track("Spa"), start_jitter_m=0.0,
                speed_ref_penalty=3.0, speed_ref_a_lat=a_lat, speed_cap=None)
    base.update(over)
    return EnvConfig(**base)


def _slowest_point(env):
    """Where the plan is tightest — the only place raising it can be seen."""
    prof = env._speed_reference()
    s = np.linspace(0.0, env.cfg.track.length, 2000, endpoint=False)
    t = np.array([prof.target(float(q)) for q in s])
    return float(s[int(np.argmin(t))]), float(t.min())


def test_raising_the_plan_raises_the_target_in_the_tightest_corner():
    env = DrivingEnv(_cfg(LOW))
    s_slow, t_low = _slowest_point(env)
    env.set_speed_ref_a_lat(HIGH)
    t_high = env._speed_reference().target(s_slow)
    # sqrt(a_lat / kappa): a 2.16x budget is a 1.47x target.
    assert t_high > t_low * 1.3, (
        f"plan did not move: {t_low:.2f} -> {t_high:.2f} m/s")


def test_raising_the_plan_changes_the_reward_not_just_the_attribute():
    """The end-to-end check. A speed that is punished under the low plan must
    stop being punished under the high one."""
    s_slow, t_low = _slowest_point(DrivingEnv(_cfg(LOW)))
    v = t_low + 3.0                      # over the low plan, under the high one

    def reward(a_lat, raise_to=None):
        e = DrivingEnv(_cfg(a_lat))
        if raise_to is not None:
            e.set_speed_ref_a_lat(raise_to)
        e.reset(0)
        e.s = s_slow
        e.backend.reset(v)
        return e.step(np.array([0.0, 0.0]))[1]

    r_low = reward(LOW)
    r_raised = reward(LOW, raise_to=HIGH)
    r_born_high = reward(HIGH)
    assert r_raised > r_low + 1e-9, (
        "raising the plan did not change the reward -- the curriculum is a "
        f"no-op ({r_low:.5f} vs {r_raised:.5f})")
    assert r_raised == pytest.approx(r_born_high, abs=1e-9), (
        "an env raised to a_lat differs from one built at it")


def test_assigning_the_config_alone_is_the_silent_no_op():
    """Pins the trap itself, so nobody 'simplifies' the method away.

    This is the code someone writes when they assume a dataclass field is
    live. It changes nothing, and this test says so out loud.
    """
    env = DrivingEnv(_cfg(LOW))
    s_slow, t_low = _slowest_point(env)
    env.cfg.speed_ref_a_lat = HIGH               # the tempting one-liner
    assert env._speed_reference().target(s_slow) == pytest.approx(t_low), (
        "config assignment now propagates; if that is deliberate, delete this "
        "test -- but the cache was there for a reason")
    env.set_speed_ref_a_lat(HIGH)                # the supported way
    assert env._speed_reference().target(s_slow) > t_low


def test_batched_env_plan_is_raisable_too():
    """The batched env is where training actually happens; if only the scalar
    one could be raised, every curriculum run would train at the start value."""
    b = BatchedDrivingEnv(_cfg(LOW), n=4, seed=0)
    lo = float(np.min(b._speed_ref.v))
    b.set_speed_ref_a_lat(HIGH)
    hi = float(np.min(b._speed_ref.v))
    assert hi > lo * 1.3, f"batched plan did not move: {lo:.2f} -> {hi:.2f}"
    assert b.cfg.speed_ref_a_lat == pytest.approx(HIGH)


def test_raising_a_plan_that_does_not_exist_raises():
    """`speed_ref_penalty=0` means the reward never reads a plan. Building one
    on demand would be a plan nothing consumes, which reads as working."""
    b = BatchedDrivingEnv(_cfg(LOW, speed_ref_penalty=0.0), n=2, seed=0)
    with pytest.raises(RuntimeError, match="no plan to rebuild"):
        b.set_speed_ref_a_lat(HIGH)
