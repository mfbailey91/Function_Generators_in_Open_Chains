"""Sprint V3.6A synthetic 3-DOF affine architecture fixture (V3-616)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.benchmarks.synthetic_affine_3d import (
    AffineIdentityKinematics3D,
    synthetic_affine_3d_exact_problem,
    synthetic_affine_3d_robot,
)
from inequality_mechanisms.core import (
    PlanningStatus,
    physical_state_from_dict,
    physical_state_to_dict,
)
from inequality_mechanisms.graphs import LatticeConnectivity, TensorGridTopology
from inequality_mechanisms.planners import PRMPlanner, RRTConnectPlanner
from inequality_mechanisms.planners.sampling_space import (
    actuator_bounds,
    sample_state_uniform,
)
from inequality_mechanisms.planners.sampling_rng import make_generator


def test_synthetic_affine_3d_dof_and_input_domain() -> None:
    robot = synthetic_affine_3d_robot()
    assert robot.dof == 3
    assert robot.kinematic_model is not None
    assert int(robot.kinematic_model.dof) == 3
    domain = robot.input_domain
    assert domain.dim == 3
    assert domain.periodic == (False, False, False)
    lo, hi = actuator_bounds(robot)
    assert lo.shape == (3,)
    assert hi.shape == (3,)
    np.testing.assert_allclose(lo, domain.lower)
    np.testing.assert_allclose(hi, domain.upper)


def test_synthetic_affine_3d_fk_identity_and_sampling() -> None:
    robot = synthetic_affine_3d_robot()
    state = robot.state_from_input([0.1, -0.2, 0.3])
    tip = np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)
    np.testing.assert_allclose(tip, state.q)
    np.testing.assert_allclose(state.q, state.u)

    rng = make_generator(11)
    sample = sample_state_uniform(robot, rng)
    assert sample.u.shape == (3,)
    assert robot.state_within_limits(sample)
    assert robot.validate_state(sample, tolerance=1e-9)


def test_synthetic_affine_3d_tensor_topology_26_neighbors() -> None:
    topo = TensorGridTopology(
        (3, 3, 3), connectivity=LatticeConnectivity.CHEBYSHEV_1
    )
    center = topo.node_id((1, 1, 1))
    assert len(topo.neighbors(center)) == 26


def test_synthetic_affine_3d_serialization_round_trip() -> None:
    robot = synthetic_affine_3d_robot()
    state = robot.state_from_input([0.25, -0.5, 0.75])
    restored = physical_state_from_dict(physical_state_to_dict(state))
    np.testing.assert_allclose(restored.u, state.u)
    np.testing.assert_allclose(restored.q, state.q)
    assert restored.assembly_state == state.assembly_state


def test_synthetic_affine_3d_prm_and_rrt_connect() -> None:
    robot, problem = synthetic_affine_3d_exact_problem()
    assert robot.dof == 3

    prm = PRMPlanner(seed=17, n_samples=80, k_neighbors=10, max_edge_u=1.5).solve(
        problem
    )
    assert prm.status is PlanningStatus.SUCCESS
    assert prm.trajectory is not None
    assert len(prm.trajectory.states) >= 2
    assert prm.path_length_u is not None and prm.path_length_u > 0.0
    assert prm.path_length_q is not None and prm.path_length_q > 0.0
    assert prm.path_length_x is not None and prm.path_length_x > 0.0
    assert problem.goal.satisfied(prm.trajectory.states[-1])

    rrt = RRTConnectPlanner(
        seed=17, max_iterations=600, step_u=0.25, goal_bias=0.15
    ).solve(problem)
    assert rrt.status is PlanningStatus.SUCCESS
    assert rrt.trajectory is not None
    assert rrt.path_length_x is not None and rrt.path_length_x > 0.0
    assert problem.goal.satisfied(rrt.trajectory.states[-1])


@pytest.mark.ompl
def test_synthetic_affine_3d_ompl_round_trip_and_prm() -> None:
    from inequality_mechanisms.adapters.ompl import is_ompl_available
    from inequality_mechanisms.adapters.ompl.prm import OmplPRMPlanner
    from inequality_mechanisms.adapters.ompl.state_space import round_trip_residuals

    if not is_ompl_available():
        pytest.skip("OMPL Python bindings not installed")

    robot, problem = synthetic_affine_3d_exact_problem()
    du, dq = round_trip_residuals(robot, problem.start)
    assert du == pytest.approx(0.0, abs=1e-9)
    assert dq == pytest.approx(0.0, abs=1e-9)

    result = OmplPRMPlanner(
        seed=17,
        max_nearest_neighbors=10,
        solve_time_s=2.0,
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    assert result.trajectory is not None
    assert result.path_length_x is not None
    assert problem.goal.satisfied(result.trajectory.states[-1])


def test_affine_identity_kinematics_rejects_wrong_shape() -> None:
    fk = AffineIdentityKinematics3D()
    with pytest.raises(ValueError, match="shape"):
        fk.forward([0.0, 1.0])
