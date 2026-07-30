"""Version 2 output-task matching tests (Sprint V2.4, V2-402/V2-403)."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch, gearbox_2d_branch

from inequality_mechanisms.experiments.v2_tasks import (
    OutputTask,
    TaskRejectionReason,
    generate_random_output_tasks,
    match_nearest_valid_q_node,
    resolve_output_task,
)
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph


def _uniform_output_graph() -> EmbeddedPlanningGraph:
    return EmbeddedPlanningGraph.from_uniform_output(gearbox_2d_branch(), shape=(5, 5))


class TestOutputTask:
    def test_requires_matching_dims(self) -> None:
        with pytest.raises(ValueError, match="same shape"):
            OutputTask(np.array([1.0, 2.0]), np.array([1.0, 2.0, 3.0]))

    def test_rejects_nonfinite(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            OutputTask(np.array([np.nan, 0.0]), np.array([0.0, 0.0]))

    def test_stores_vectors(self) -> None:
        task = OutputTask(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
        assert np.array_equal(task.requested_start_q, [1.0, 2.0])
        assert np.array_equal(task.requested_goal_q, [3.0, 4.0])


class TestNearestNodeMatching:
    def test_matches_exact_node_with_zero_residual(self) -> None:
        graph = _uniform_output_graph()
        q_exact = graph.q_state(12)
        node_id, resid_vec, resid_norm = match_nearest_valid_q_node(graph, q_exact)
        assert node_id == 12
        assert resid_norm == pytest.approx(0.0, abs=1e-12)
        assert np.allclose(resid_vec, 0.0, atol=1e-12)

    def test_ties_break_to_lowest_node_id(self) -> None:
        # Force an exact distance tie between two distinct nodes by
        # overwriting q_nodes directly, then confirm the lower node id wins.
        graph = _uniform_output_graph()
        forced = np.array(graph.q_nodes, copy=True)
        forced.flags.writeable = True
        query = forced[3].copy()
        forced[7] = query  # nodes 3 and 7 now sit exactly on the query point
        forced.flags.writeable = False
        object.__setattr__(graph, "q_nodes", forced)
        node_id, resid_vec, resid_norm = match_nearest_valid_q_node(graph, query)
        assert node_id == 3
        assert resid_norm == pytest.approx(0.0, abs=1e-12)

    def test_no_valid_nodes_raises(self) -> None:
        graph = _uniform_output_graph()
        object.__setattr__(graph, "valid_nodes", np.zeros_like(graph.valid_nodes))
        with pytest.raises(ValueError, match=TaskRejectionReason.NO_VALID_NODES.value):
            match_nearest_valid_q_node(graph, graph.q_state(0))


class TestResolveOutputTask:
    def test_accepts_within_tolerance(self) -> None:
        graph = _uniform_output_graph()
        q_start = graph.q_state(0)
        q_goal = graph.q_state(24)
        task = OutputTask(q_start, q_goal)
        resolved = resolve_output_task(graph, task, output_tolerance=1e-6)
        assert not resolved.rejected
        assert resolved.rejection_reason is None
        assert resolved.start_node_id == 0
        assert resolved.goal_node_id == 24
        assert resolved.start is not None
        assert resolved.start.residual_norm == pytest.approx(0.0, abs=1e-9)

    def test_rejects_when_start_residual_exceeds_tolerance(self) -> None:
        graph = _uniform_output_graph()
        q_start = graph.q_state(0) + np.array([0.5, 0.5])
        q_goal = graph.q_state(24)
        task = OutputTask(q_start, q_goal)
        resolved = resolve_output_task(graph, task, output_tolerance=1e-9)
        assert resolved.rejected
        assert (
            resolved.rejection_reason
            == TaskRejectionReason.START_RESIDUAL_EXCEEDS_TOLERANCE.value
        )
        # Endpoints are still recorded even when rejected (no silent drop).
        assert resolved.start is not None
        assert resolved.goal is not None

    def test_rejects_when_goal_residual_exceeds_tolerance(self) -> None:
        graph = _uniform_output_graph()
        q_start = graph.q_state(0)
        q_goal = graph.q_state(24) + np.array([0.5, 0.5])
        task = OutputTask(q_start, q_goal)
        resolved = resolve_output_task(graph, task, output_tolerance=1e-9)
        assert resolved.rejected
        assert (
            resolved.rejection_reason
            == TaskRejectionReason.GOAL_RESIDUAL_EXCEEDS_TOLERANCE.value
        )

    def test_rejected_task_has_no_node_id_accessors(self) -> None:
        graph = _uniform_output_graph()
        q_start = graph.q_state(0) + np.array([0.5, 0.5])
        task = OutputTask(q_start, graph.q_state(24))
        resolved = resolve_output_task(graph, task, output_tolerance=1e-9)
        assert resolved.rejected
        with pytest.raises(ValueError):
            _ = resolved.start_node_id
        with pytest.raises(ValueError):
            _ = resolved.goal_node_id

    def test_same_task_reused_across_mechanisms_records_separate_residuals(
        self,
    ) -> None:
        """V2-403: one requested task, resolved independently per graph."""
        fourbar_graph = EmbeddedPlanningGraph.from_uniform_output(
            fourbar_2d_branch(), shape=(6, 6)
        )
        gearbox_graph = EmbeddedPlanningGraph.from_uniform_output(
            gearbox_2d_branch(), shape=(6, 6)
        )
        task = OutputTask(np.array([1.4, 1.4]), np.array([1.9, 1.9]))
        resolved_fourbar = resolve_output_task(
            fourbar_graph, task, output_tolerance=1.0
        )
        resolved_gearbox = resolve_output_task(
            gearbox_graph, task, output_tolerance=1.0
        )
        assert resolved_fourbar.task is task
        assert resolved_gearbox.task is task
        # Independently resolved per graph: each endpoint's realized state
        # comes from its own graph, not copied from the other mechanism.
        assert resolved_fourbar.start is not None and resolved_gearbox.start is not None
        assert np.array_equal(
            resolved_fourbar.start.realized_q,
            fourbar_graph.q_state(resolved_fourbar.start.selected_node_id),
        )
        assert np.array_equal(
            resolved_gearbox.start.realized_q,
            gearbox_graph.q_state(resolved_gearbox.start.selected_node_id),
        )

    def test_negative_tolerance_rejected(self) -> None:
        graph = _uniform_output_graph()
        task = OutputTask(graph.q_state(0), graph.q_state(1))
        with pytest.raises(ValueError, match="output_tolerance"):
            resolve_output_task(graph, task, output_tolerance=-1.0)


class TestGenerateRandomOutputTasks:
    def test_deterministic_given_seed(self) -> None:
        rng1 = np.random.default_rng(7)
        rng2 = np.random.default_rng(7)
        tasks1 = generate_random_output_tasks(
            lower=[0.0, 0.0], upper=[1.0, 1.0], n_tasks=4, rng=rng1
        )
        tasks2 = generate_random_output_tasks(
            lower=[0.0, 0.0], upper=[1.0, 1.0], n_tasks=4, rng=rng2
        )
        for t1, t2 in zip(tasks1, tasks2):
            assert np.array_equal(t1.requested_start_q, t2.requested_start_q)
            assert np.array_equal(t1.requested_goal_q, t2.requested_goal_q)

    def test_within_bounds(self) -> None:
        rng = np.random.default_rng(3)
        tasks = generate_random_output_tasks(
            lower=[0.0, -1.0], upper=[2.0, 1.0], n_tasks=10, rng=rng
        )
        for task in tasks:
            assert np.all(task.requested_start_q >= [0.0, -1.0])
            assert np.all(task.requested_start_q <= [2.0, 1.0])
            assert np.all(task.requested_goal_q >= [0.0, -1.0])
            assert np.all(task.requested_goal_q <= [2.0, 1.0])

    def test_rejects_degenerate_box(self) -> None:
        rng = np.random.default_rng(1)
        with pytest.raises(ValueError, match="exceed"):
            generate_random_output_tasks(lower=[0.0], upper=[0.0], n_tasks=1, rng=rng)
