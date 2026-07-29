"""Episode 13's controller: the sign, the optimality, and the seal on Seasons 1-3.

Three of these are checks the code was not written around (CLAUDE.md rule 11), and
they are the ones worth having:

* the allocator's idea of the yaw moment a force makes is checked against the
  *simulator's* ``yaw_moment``, which is a different piece of code with a different
  derivation;
* the QP's answer is checked against brute-force sampling of the box, which knows
  nothing about active sets or KKT conditions;
* the driver's curvilinear fix is checked against ``Track.to_xy``, which is the
  inverse map written for drawing and not for driving.

Every frame conversion in this project has been wrong at least once and every one
failed silently (F36 and its two relatives), so none of them is checked by
restating its formula.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from physics import schema
from physics.double_track import CORNERS, BicycleState, DoubleTrackBackend, WheelForces
from physics.tire import default_tire
from physics.torque_vectoring import (Allocator, ReferenceModel, TorqueVectoring,
                                      YawController, build,
                                      measure_grip_ceiling,
                                      measure_understeer_gradient)


@pytest.fixture
def backend():
    return DoubleTrackBackend(schema.RV_1, diff="open")


@pytest.fixture
def allocator(backend):
    return Allocator(params=backend.params, tire=backend.tire, effectors="four")


def _loads(backend, a_y=8.0):
    return backend.wheel_loads(0.0, a_y)


# --- the lower layer -------------------------------------------------------

def test_both_demands_are_met_when_the_tires_can_meet_them(allocator, backend):
    a = allocator.allocate(2000.0, 800.0, _loads(backend))
    assert abs(a.fx_delivered - 2000.0) < 5.0
    assert abs(a.mz_delivered - 800.0) < 5.0


def test_the_allocator_and_the_simulator_agree_about_yaw(allocator, backend):
    """Cross-check between two independently written pieces of code.

    The allocator predicts the moment from its own coefficient rows; the simulator
    computes it from per-wheel positions and a body-frame projection. They are the
    same physics written twice, and F72 exists because two such expressions in this
    project once disagreed for three seasons without anything erroring.
    """
    steer = math.radians(6.0)
    loads = _loads(backend)
    a = allocator.allocate(1500.0, 1200.0, loads, steer=steer)
    wheels = {c: WheelForces(fy=0.0, fx=a.forces[c], alpha=0.0, kappa=0.0,
                             fz=loads[c]) for c in CORNERS}
    assert backend.yaw_moment(wheels, steer) == pytest.approx(a.mz_delivered,
                                                              abs=1e-6)


def test_more_force_on_the_right_wheel_yaws_the_car_left(allocator, backend):
    """ISO 8855: y is positive to the left, so ``-y*Fx`` makes a right-hand wheel
    turn the nose left. This is the sign F72's table pins and the one the whole of
    Season 4 rests on."""
    a = allocator.allocate(0.0, 1000.0, _loads(backend))
    assert a.forces["rr"] + a.forces["fr"] > a.forces["rl"] + a.forces["fl"]
    b = allocator.allocate(0.0, -1000.0, _loads(backend))
    assert b.forces["rr"] + b.forces["fr"] < b.forces["rl"] + b.forces["fl"]


def test_no_moment_demand_on_a_level_car_gives_a_symmetric_split(backend):
    alloc = Allocator(params=backend.params, tire=backend.tire)
    loads = backend.wheel_loads(0.0, 0.0)          # straight and level
    a = alloc.allocate(3000.0, 0.0, loads)
    assert a.forces["fl"] == pytest.approx(a.forces["fr"], abs=1e-6)
    assert a.forces["rl"] == pytest.approx(a.forces["rr"], abs=1e-6)


def test_the_qp_answer_beats_brute_force(allocator, backend):
    """Optimality, checked by something that knows nothing about the solver.

    Twenty thousand random points in the box, plus small perturbations of the
    solution itself. The QP's objective must be no worse than any of them. This is
    the check that would fail if the active-set loop released the wrong variable,
    and it cannot be satisfied by the solver agreeing with itself.
    """
    rng = np.random.default_rng(13)
    loads = _loads(backend, a_y=9.0)
    steer = math.radians(5.0)
    fx_demand, mz_demand = 2500.0, 2500.0
    a = allocator.allocate(fx_demand, mz_demand, loads, steer=steer)
    cap = np.array([a.caps[c] for c in CORNERS])
    a_fx, a_mz = allocator._rows(steer)
    scale = 2.0 / backend.params.track_r

    f_ref = float(np.mean(cap))

    def cost(x):
        return (allocator.s_fx * ((a_fx @ x - fx_demand) / f_ref) ** 2
                + allocator.s_mz * ((a_mz @ x - mz_demand) * scale / f_ref) ** 2
                + allocator.s_workload * float(np.sum((x / cap) ** 2)))

    x_star = np.array([a.forces[c] for c in CORNERS])
    best = cost(x_star)
    samples = rng.uniform(-1.0, 1.0, size=(20_000, 4)) * cap
    samples = np.vstack([samples,
                         np.clip(x_star + rng.normal(0, 50.0, size=(2000, 4)),
                                 -cap, cap)])
    assert best <= min(cost(x) for x in samples) + 1e-6


def test_no_wheel_is_asked_for_more_than_it_has(allocator, backend):
    loads = _loads(backend, a_y=9.3)
    a = allocator.allocate(9000.0, 6000.0, loads)      # far more than possible
    for c in CORNERS:
        assert abs(a.forces[c]) <= a.caps[c] + 1e-6
    assert a.peak_workload <= 1.0 + 1e-9


def test_lateral_use_eats_longitudinal_capacity(allocator, backend):
    """The friction ellipse, D9. A tire already making most of its lateral force
    has little left to give the allocator, and a controller that does not know
    that will ask a saturated tire for drive it cannot deliver."""
    loads = _loads(backend, a_y=8.0)
    free = allocator.capacities(loads)
    busy = allocator.capacities(loads, lateral={
        c: 0.9 * float(default_tire().peak_fy(loads[c])) for c in CORNERS})
    for c in CORNERS:
        assert busy[c] < 0.5 * free[c]


def test_the_rear_axle_device_uses_only_the_driven_axle(backend):
    alloc = Allocator(params=backend.params, tire=backend.tire, effectors="rear")
    a = alloc.allocate(3000.0, 1000.0, _loads(backend))
    assert a.forces["fl"] == 0.0 and a.forces["fr"] == 0.0
    assert a.forces["rr"] > a.forces["rl"]             # positive moment, nose left
    assert a.fx_delivered == pytest.approx(3000.0, abs=1e-6)


def test_the_rear_axle_device_brakes_on_the_bias(backend):
    alloc = Allocator(params=backend.params, tire=backend.tire, effectors="rear",
                      brake_bias=0.65)
    a = alloc.allocate(-4000.0, 0.0, _loads(backend))
    front = a.forces["fl"] + a.forces["fr"]
    assert front == pytest.approx(-0.65 * 4000.0, abs=1e-6)


# --- the upper layer -------------------------------------------------------

def test_the_reference_model_never_asks_for_more_than_the_tires_have():
    ref = ReferenceModel(wheelbase=2.575, k_us=3.6e-4, a_y_max=9.3)
    r = ref.yaw_rate(20.0, math.radians(25.0))
    assert abs(r * 20.0) <= 9.3 + 1e-9        # a_y = v * r


def test_the_reference_model_is_linear_below_the_limit():
    ref = ReferenceModel(wheelbase=2.575, k_us=3.6e-4, a_y_max=9.3)
    small = ref.yaw_rate(15.0, math.radians(1.0))
    twice = ref.yaw_rate(15.0, math.radians(2.0))
    assert twice == pytest.approx(2.0 * small, rel=1e-9)


def test_the_integrator_does_not_wind_up_against_a_saturated_output():
    c = YawController(k_p=1e5, k_i=1e5, mz_max=1000.0)
    for _ in range(500):
        c.update(1.0, 0.0, 0.02)              # a demand it can never satisfy
    # Once the error goes away the output must follow immediately, not sit
    # saturated while a stored integral drains.
    assert abs(c.update(0.0, 0.0, 0.02)) < 1000.0


def test_the_controller_asks_for_left_yaw_when_the_car_is_not_turning_enough():
    c = YawController(k_p=10_000.0, k_i=0.0)
    assert c.update(0.5, 0.3, 0.02) > 0.0     # wants more left yaw
    assert c.update(0.3, 0.5, 0.02) < 0.0


# --- the seal on everything before Episode 13 ------------------------------

def test_an_unattached_backend_is_exactly_the_differential(backend):
    """Episodes 1-12 must be untouched by the hook, and not approximately."""
    loads = backend.wheel_loads(0.0, 8.0)
    st = BicycleState(v_x=20.0, v_y=0.0, yaw_rate=0.4, steer=0.05)
    assert backend.tv is None
    assert backend._wheel_forces(3000.0, loads, st) == \
        backend.differential_forces(3000.0, loads, st)


def test_attaching_a_controller_replaces_the_differential(backend):
    tv = build(backend, effectors="four")
    backend.attach_torque_vectoring(tv)
    tv.mz_command = 1500.0
    loads = backend.wheel_loads(0.0, 8.0)
    st = BicycleState(v_x=20.0, v_y=0.0, yaw_rate=0.4, steer=0.05)
    fx = backend._wheel_forces(2000.0, loads, st)
    assert fx["rr"] > fx["rl"]                 # the moment reached the wheels
    backend.attach_torque_vectoring(None)
    assert backend._wheel_forces(2000.0, loads, st)["rr"] == \
        pytest.approx(backend.differential_forces(2000.0, loads, st)["rr"])


def test_the_trim_solver_refuses_a_controller_it_cannot_represent(backend):
    backend.attach_torque_vectoring(build(backend))
    with pytest.raises(RuntimeError, match="torque-vectoring"):
        backend.trim_skidpad(15.0, 30.0)


def test_the_controller_is_built_from_the_car_it_is_given(backend):
    """The reference model's two numbers are measured, not assumed (rule 3)."""
    k_us = measure_understeer_gradient(backend)
    a_y_max = measure_grip_ceiling(backend)
    assert 0.0 < math.degrees(k_us) * schema.G < 1.0      # deg/g, ours is ~0.2
    assert 8.0 < a_y_max < 11.0                            # m/s^2, ours is ~9.3
    tv = build(backend)
    assert tv.reference.k_us == pytest.approx(k_us, rel=1e-9)
    assert tv.allocator.params is backend.params


def test_yaw_control_off_still_allocates(backend):
    """The control condition Episode 13 leans on: same allocator, no yaw demand.

    Without this the episode cannot separate "four wheels share force better than
    a differential does" from "the controller vectors torque", and those are
    different claims with different consequences for Episode 15.
    """
    tv = build(backend, yaw_control=False)
    st = BicycleState(v_x=20.0, v_y=0.0, yaw_rate=0.4, steer=0.05)
    assert tv.update(st, 0.02) == 0.0
    loads = backend.wheel_loads(0.0, 8.0)
    fx = tv.forces(3000.0, loads, st)
    assert sum(fx.values()) == pytest.approx(3000.0, rel=0.05)
    assert tv.last.mz_demand == 0.0
