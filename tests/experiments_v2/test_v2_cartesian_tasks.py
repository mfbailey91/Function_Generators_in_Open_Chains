from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from inequality_mechanisms.experiments.v2_cartesian_tasks import (
    CartesianAnnularSectorDomain,
    CartesianPositionTask,
    assert_paired_cartesian_query_identity,
    generate_cartesian_task_bank,
    resolve_cartesian_task,
)
from inequality_mechanisms.kinematics.planar_2r import Planar2R


class OutputSpace:
    def contains(self, _q) -> bool:
        return True

    def distance(self, a, b) -> float:
        return float(np.linalg.norm(np.asarray(b) - np.asarray(a)))


class CartesianStubGraph:
    def __init__(self) -> None:
        self._q = np.asarray(
            [
                [0.0, np.pi / 2.0],
                [np.pi / 4.0, np.pi / 2.0],
                [np.pi / 2.0, np.pi / 2.0],
            ],
            dtype=np.float64,
        )
        self.branch = SimpleNamespace(output_space=OutputSpace())

    @property
    def node_count(self) -> int:
        return len(self._q)

    def node_is_valid(self, node_id: int) -> bool:
        return 0 <= node_id < self.node_count

    def q_state(self, node_id: int):
        return self._q[node_id]

    def u_state(self, node_id: int):
        return self._q[node_id]


def domain() -> CartesianAnnularSectorDomain:
    return CartesianAnnularSectorDomain(
        domain_id="test",
        radial_min=0.5,
        radial_max=1.6,
        angle_min=0.0,
        angle_max=np.pi,
        start_tolerance=0.02,
        goal_radius=0.02,
        min_start_goal_separation=0.2,
    )


def test_sampler_is_uniform_in_radius_squared_and_respects_separation() -> None:
    d = domain()
    tasks = generate_cartesian_task_bank(d, n_tasks=4000, seed=7)
    starts = np.vstack([task.requested_start_x for task in tasks])
    r2 = np.sum(starts * starts, axis=1)
    normalized = (r2 - d.radial_min**2) / (d.radial_max**2 - d.radial_min**2)
    assert abs(float(np.mean(normalized)) - 0.5) < 0.02
    assert all(
        np.linalg.norm(task.requested_goal_x - task.requested_start_x)
        >= d.min_start_goal_separation
        for task in tasks
    )


def test_planar_2r_inverse_round_trip() -> None:
    fk = Planar2R()
    q = np.asarray([0.3, 1.2])
    x = fk.forward(q)
    solutions = fk.inverse(x)
    assert len(solutions) == 2
    assert any(np.allclose(fk.forward(candidate), x, atol=1e-10) for candidate in solutions)


def test_task_resolution_and_pair_identity() -> None:
    graph_a = CartesianStubGraph()
    graph_b = CartesianStubGraph()
    fk = Planar2R()
    task = CartesianPositionTask(
        task_id="xb00000",
        requested_start_x=fk.forward(graph_a.q_state(0)),
        requested_goal_x=fk.forward(graph_a.q_state(2)),
    )
    resolved_a = resolve_cartesian_task(graph_a, task, domain(), fk=fk)
    resolved_b = resolve_cartesian_task(graph_b, task, domain(), fk=fk)
    assert resolved_a.accepted
    assert resolved_a.start_node_id == 0
    assert resolved_a.goal_node_ids == (2,)
    assert_paired_cartesian_query_identity(
        graph_a, graph_b, resolved_a, resolved_b
    )
