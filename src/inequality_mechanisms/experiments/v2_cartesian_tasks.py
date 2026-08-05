"""Frozen Cartesian task sampling and graph attachment for Experiment B.

The sampler owns the external Cartesian exam. Mechanism-specific graph
attachment is a separate deterministic step so reachability remains an outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.kinematics.planar_2r import Planar2R


@dataclass(frozen=True, slots=True)
class CartesianAnnularSectorDomain:
    """Area-uniform annular-sector task domain in the planar base frame."""

    domain_id: str
    radial_min: float
    radial_max: float
    angle_min: float
    angle_max: float
    start_tolerance: float
    goal_radius: float
    min_start_goal_separation: float
    L1: float = 1.0
    L2: float = 1.0

    def __post_init__(self) -> None:
        values = (
            self.radial_min,
            self.radial_max,
            self.angle_min,
            self.angle_max,
            self.start_tolerance,
            self.goal_radius,
            self.min_start_goal_separation,
            self.L1,
            self.L2,
        )
        if not all(np.isfinite(v) for v in values):
            raise ValueError("Cartesian domain values must be finite")
        if not (0.0 <= self.radial_min < self.radial_max):
            raise ValueError("require 0 <= radial_min < radial_max")
        if not self.angle_min < self.angle_max:
            raise ValueError("require angle_min < angle_max")
        if self.start_tolerance <= 0.0 or self.goal_radius <= 0.0:
            raise ValueError("start_tolerance and goal_radius must be positive")
        if self.min_start_goal_separation < 2.0 * max(
            self.start_tolerance, self.goal_radius
        ):
            raise ValueError(
                "min_start_goal_separation must be at least twice the larger "
                "attachment radius"
            )
        if self.L1 <= 0.0 or self.L2 <= 0.0:
            raise ValueError("link lengths must be positive")

    def sample_point(self, rng: np.random.Generator) -> NDArray[np.float64]:
        """Draw one point uniformly with respect to Cartesian area."""
        radius_sq = rng.uniform(self.radial_min**2, self.radial_max**2)
        radius = float(np.sqrt(radius_sq))
        angle = float(rng.uniform(self.angle_min, self.angle_max))
        return np.asarray(
            [radius * np.cos(angle), radius * np.sin(angle)], dtype=np.float64
        )

    def contains(self, x: ArrayLike, *, atol: float = 1e-12) -> bool:
        point = _as_x2(x)
        radius = float(np.linalg.norm(point))
        angle = float(np.arctan2(point[1], point[0]))
        while angle < self.angle_min:
            angle += 2.0 * np.pi
        return bool(
            self.radial_min - atol <= radius <= self.radial_max + atol
            and self.angle_min - atol <= angle <= self.angle_max + atol
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "shape": "annular_sector",
            "radial_min": float(self.radial_min),
            "radial_max": float(self.radial_max),
            "angle_min": float(self.angle_min),
            "angle_max": float(self.angle_max),
            "start_tolerance": float(self.start_tolerance),
            "goal_radius": float(self.goal_radius),
            "min_start_goal_separation": float(self.min_start_goal_separation),
            "L1": float(self.L1),
            "L2": float(self.L2),
            "area_measure": "uniform_cartesian_area",
        }


@dataclass(frozen=True, slots=True)
class CartesianPositionTask:
    """One external start-position / goal-region query."""

    task_id: str
    requested_start_x: NDArray[np.float64]
    requested_goal_x: NDArray[np.float64]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "requested_start_x": self.requested_start_x.tolist(),
            "requested_goal_x": self.requested_goal_x.tolist(),
            "cartesian_separation": float(
                np.linalg.norm(self.requested_goal_x - self.requested_start_x)
            ),
        }


@dataclass(frozen=True, slots=True)
class ResolvedCartesianTask:
    """A Cartesian task attached to one shared-Q graph pair."""

    task: CartesianPositionTask
    start_node_id: int | None
    start_residual: float | None
    goal_node_ids: tuple[int, ...]
    nearest_goal_residual: float | None
    analytic_start_ik: tuple[dict[str, Any], ...]
    selected_start_ik_family: str | None
    rejection_reason: str | None

    @property
    def accepted(self) -> bool:
        return self.rejection_reason is None

    def to_dict(self) -> dict[str, Any]:
        payload = self.task.to_dict()
        payload.update(
            {
                "start_node_id": self.start_node_id,
                "start_residual": self.start_residual,
                "goal_node_ids": list(self.goal_node_ids),
                "goal_set_size": len(self.goal_node_ids),
                "nearest_goal_residual": self.nearest_goal_residual,
                "analytic_start_ik": list(self.analytic_start_ik),
                "selected_start_ik_family": self.selected_start_ik_family,
                "rejection_reason": self.rejection_reason,
            }
        )
        return payload


def default_experiment_b_domain() -> CartesianAnnularSectorDomain:
    """Return ADR-019's fixed left-facing unit-link workcell."""
    return CartesianAnnularSectorDomain(
        domain_id="planar2r_left_workcell_v1",
        radial_min=0.50,
        radial_max=1.50,
        angle_min=2.15,
        angle_max=3.55,
        start_tolerance=0.06,
        goal_radius=0.06,
        min_start_goal_separation=0.30,
        L1=1.0,
        L2=1.0,
    )


def generate_cartesian_task_bank(
    domain: CartesianAnnularSectorDomain,
    *,
    n_tasks: int,
    seed: int,
    max_attempts_per_task: int = 10_000,
) -> tuple[CartesianPositionTask, ...]:
    """Generate a deterministic external bank without mechanism feedback."""
    if n_tasks < 1:
        raise ValueError("n_tasks must be positive")
    if max_attempts_per_task < 1:
        raise ValueError("max_attempts_per_task must be positive")
    rng = np.random.default_rng(int(seed))
    out: list[CartesianPositionTask] = []
    for task_index in range(n_tasks):
        for _attempt in range(max_attempts_per_task):
            start = domain.sample_point(rng)
            goal = domain.sample_point(rng)
            if (
                float(np.linalg.norm(goal - start))
                < domain.min_start_goal_separation
            ):
                continue
            out.append(
                CartesianPositionTask(
                    task_id=f"xb{task_index:05d}",
                    requested_start_x=start,
                    requested_goal_x=goal,
                )
            )
            break
        else:
            raise RuntimeError(
                f"failed to sample task {task_index} after "
                f"{max_attempts_per_task} attempts"
            )
    return tuple(out)


def ik_family(q: ArrayLike, *, tolerance: float = 1e-9) -> str:
    q_arr = np.asarray(q, dtype=np.float64)
    s = float(np.sin(q_arr[1]))
    if abs(s) <= tolerance:
        return "singular"
    return "elbow_up" if s > 0.0 else "elbow_down"


def graph_cartesian_positions(
    graph: Any, fk: Planar2R
) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    """Return valid node ids and their Cartesian positions in node-id order."""
    node_ids = np.asarray(
        [node_id for node_id in range(graph.node_count) if graph.node_is_valid(node_id)],
        dtype=np.int64,
    )
    if node_ids.size == 0:
        return node_ids, np.empty((0, 2), dtype=np.float64)
    x = np.vstack([fk.forward(graph.q_state(int(node_id))) for node_id in node_ids])
    return node_ids, np.asarray(x, dtype=np.float64)


def resolve_cartesian_task(
    graph: Any,
    task: CartesianPositionTask,
    domain: CartesianAnnularSectorDomain,
    *,
    fk: Planar2R | None = None,
) -> ResolvedCartesianTask:
    """Attach one external task to a graph with deterministic tie-breaking."""
    model = fk if fk is not None else Planar2R(domain.L1, domain.L2)
    node_ids, positions = graph_cartesian_positions(graph, model)
    analytic: list[dict[str, Any]] = []
    for q in model.inverse(task.requested_start_x):
        in_box = bool(graph.branch.output_space.contains(q))
        analytic.append(
            {
                "family": ik_family(q),
                "q": np.asarray(q, dtype=np.float64).tolist(),
                "inside_certified_q_box": in_box,
            }
        )
    if node_ids.size == 0:
        return ResolvedCartesianTask(
            task=task,
            start_node_id=None,
            start_residual=None,
            goal_node_ids=(),
            nearest_goal_residual=None,
            analytic_start_ik=tuple(analytic),
            selected_start_ik_family=None,
            rejection_reason="no_valid_graph_nodes",
        )

    start_dist = np.linalg.norm(positions - task.requested_start_x, axis=1)
    start_candidates = np.flatnonzero(start_dist <= domain.start_tolerance)
    goal_dist = np.linalg.norm(positions - task.requested_goal_x, axis=1)
    goal_candidates = np.flatnonzero(goal_dist <= domain.goal_radius)
    nearest_goal = float(np.min(goal_dist)) if goal_dist.size else None

    if start_candidates.size == 0:
        return ResolvedCartesianTask(
            task=task,
            start_node_id=None,
            start_residual=float(np.min(start_dist)),
            goal_node_ids=tuple(int(node_ids[i]) for i in goal_candidates),
            nearest_goal_residual=nearest_goal,
            analytic_start_ik=tuple(analytic),
            selected_start_ik_family=None,
            rejection_reason="start_region_has_no_graph_node",
        )
    ranked_start = sorted(
        (float(start_dist[i]), int(node_ids[i])) for i in start_candidates
    )
    start_residual, start_node_id = ranked_start[0]
    goals = tuple(sorted(int(node_ids[i]) for i in goal_candidates))
    if not goals:
        return ResolvedCartesianTask(
            task=task,
            start_node_id=start_node_id,
            start_residual=start_residual,
            goal_node_ids=(),
            nearest_goal_residual=nearest_goal,
            analytic_start_ik=tuple(analytic),
            selected_start_ik_family=ik_family(graph.q_state(start_node_id)),
            rejection_reason="goal_region_has_no_graph_node",
        )
    if start_node_id in goals:
        return ResolvedCartesianTask(
            task=task,
            start_node_id=start_node_id,
            start_residual=start_residual,
            goal_node_ids=goals,
            nearest_goal_residual=nearest_goal,
            analytic_start_ik=tuple(analytic),
            selected_start_ik_family=ik_family(graph.q_state(start_node_id)),
            rejection_reason="start_node_inside_goal_region",
        )
    return ResolvedCartesianTask(
        task=task,
        start_node_id=start_node_id,
        start_residual=start_residual,
        goal_node_ids=goals,
        nearest_goal_residual=nearest_goal,
        analytic_start_ik=tuple(analytic),
        selected_start_ik_family=ik_family(graph.q_state(start_node_id)),
        rejection_reason=None,
    )


def assert_paired_cartesian_query_identity(
    graph_a: Any,
    graph_b: Any,
    resolved_a: ResolvedCartesianTask,
    resolved_b: ResolvedCartesianTask,
    *,
    atol: float = 1e-12,
) -> None:
    """Hard gate: shared-Q pair must resolve exactly the same Cartesian query."""
    if resolved_a.start_node_id != resolved_b.start_node_id:
        raise AssertionError("paired Cartesian start node mismatch")
    if resolved_a.goal_node_ids != resolved_b.goal_node_ids:
        raise AssertionError("paired Cartesian goal-set mismatch")
    if resolved_a.rejection_reason != resolved_b.rejection_reason:
        raise AssertionError("paired Cartesian rejection mismatch")
    for node_id in range(graph_a.node_count):
        if graph_a.node_is_valid(node_id) != graph_b.node_is_valid(node_id):
            raise AssertionError(f"paired valid-node mismatch at {node_id}")
        if graph_a.node_is_valid(node_id) and not np.allclose(
            graph_a.q_state(node_id), graph_b.q_state(node_id), atol=atol, rtol=0.0
        ):
            raise AssertionError(f"paired Q-state mismatch at {node_id}")


def _as_x2(x: ArrayLike) -> NDArray[np.float64]:
    arr = np.asarray(x, dtype=np.float64)
    if arr.shape != (2,) or not np.all(np.isfinite(arr)):
        raise ValueError("Cartesian point must be finite with shape (2,)")
    return arr
