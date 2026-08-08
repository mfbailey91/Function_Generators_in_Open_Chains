"""U/Q/X edge and field metrics for the planar-2R visual audit (V3-623)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.adapters.lattice_edge_cost import connector_for_graph
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.core.trajectory_metrics import (
    TrajectoryPathMetrics,
    path_metrics_from_motion_samples,
    path_metrics_from_states,
)
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph

EPS = 1e-12


@dataclass(frozen=True, slots=True)
class EdgeWeightRecord:
    """Integrated weights for one undirected shared-Q lattice edge."""

    a: int
    b: int
    w_u: float
    w_q: float
    w_x: float
    stretch_q_over_u: float
    stretch_u_over_q: float


@dataclass(frozen=True, slots=True)
class FieldScalarRecord:
    """Scalar differential diagnostics at one lattice node."""

    node_id: int
    q: tuple[float, ...]
    m_q_diag: tuple[float, ...]
    m_q_det: float
    m_q_cond: float
    j_ux_fro: float


@dataclass(frozen=True, slots=True)
class LatticeMetricBundle:
    """Edge weights and node fields for one mechanism lattice."""

    edges: tuple[EdgeWeightRecord, ...]
    fields: tuple[FieldScalarRecord, ...]
    connector_id: str


def _polyline_length(samples: NDArray[np.float64]) -> float:
    if samples.shape[0] < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(samples, axis=0), axis=1)))


def _state_from_node(
    graph: EmbeddedPlanningGraph,
    node_id: int,
    *,
    assembly_state: Mapping[str, Any] | None,
) -> PhysicalState:
    return PhysicalState(
        u=np.asarray(graph.u_state(node_id), dtype=np.float64),
        q=np.asarray(graph.q_state(node_id), dtype=np.float64),
        assembly_state=dict(assembly_state or {}),
        auxiliary_state={"lattice_node_id": int(node_id)},
    )


def integrate_edge_weights(
    graph: EmbeddedPlanningGraph,
    robot: RobotModel,
    *,
    n_samples: int = 32,
    assembly_state: Mapping[str, Any] | None = None,
) -> LatticeMetricBundle:
    """Integrate declared local-motion arc lengths on every undirected edge.

    Uses the graph's transition parameterization connector (output-linear for
    uniform-Q lattices). Failed connections store ``inf`` weights.
    """
    connector = connector_for_graph(graph, robot, n_samples=n_samples)
    objective = ActuatorTravelObjective()
    assembly = dict(assembly_state or {})
    edges: list[EdgeWeightRecord] = []

    for a, b in graph.topology.iter_edges():
        if not (graph.node_is_valid(a) and graph.node_is_valid(b)):
            continue
        sa = _state_from_node(graph, a, assembly_state=assembly)
        sb = _state_from_node(graph, b, assembly_state=assembly)
        motion = connector.connect(sa, sb)
        if motion is None:
            w_u = w_q = w_x = float("inf")
        else:
            w_u = float(objective.motion_cost(motion))
            sample_u = np.asarray(motion.parameters["sample_u"], dtype=np.float64)
            sample_q = np.asarray(motion.parameters["sample_q"], dtype=np.float64)
            # Output-linear sample_q is collinear; endpoint length is exact.
            w_q = float(np.linalg.norm(sb.q - sa.q))
            tips = []
            for u_row, q_row in zip(sample_u, sample_q):
                st = PhysicalState(u=u_row, q=q_row, assembly_state=assembly)
                tips.append(
                    np.asarray(robot.forward_kinematics(st).position, dtype=np.float64)
                )
            w_x = _polyline_length(np.asarray(tips, dtype=np.float64))
        edges.append(
            EdgeWeightRecord(
                a=int(a),
                b=int(b),
                w_u=w_u,
                w_q=w_q,
                w_x=w_x,
                stretch_q_over_u=float(w_q / max(w_u, EPS)),
                stretch_u_over_q=float(w_u / max(w_q, EPS)),
            )
        )

    fields = compute_node_fields(graph, robot, assembly_state=assembly)
    connector_id = str(getattr(connector, "model_id", type(connector).__name__))
    return LatticeMetricBundle(
        edges=tuple(edges),
        fields=tuple(fields),
        connector_id=connector_id,
    )


def compute_node_fields(
    graph: EmbeddedPlanningGraph,
    robot: RobotModel,
    *,
    assembly_state: Mapping[str, Any] | None = None,
) -> list[FieldScalarRecord]:
    """Compute independent-axis scalar fields from ``M_Q`` and ``J_u→x``."""
    branch = getattr(robot, "branch", None)
    if branch is None:
        raise TypeError("robot must expose an operating branch for field metrics")
    assembly = dict(assembly_state or {})
    out: list[FieldScalarRecord] = []
    for node_id in range(graph.node_count):
        if not graph.node_is_valid(node_id):
            continue
        q = np.asarray(graph.q_state(node_id), dtype=np.float64)
        u = np.asarray(graph.u_state(node_id), dtype=np.float64)
        state = PhysicalState(u=u, q=q, assembly_state=assembly)
        j_g = np.asarray(branch.jacobian(u), dtype=np.float64)
        j_g_inv = np.linalg.inv(j_g)
        m_q = j_g_inv.T @ j_g_inv
        j_f = np.asarray(robot.jacobian_q_to_x(state), dtype=np.float64)
        j_ux = j_f @ j_g
        diag = tuple(float(m_q[i, i]) for i in range(m_q.shape[0]))
        det = float(np.linalg.det(m_q))
        try:
            cond = float(np.linalg.cond(m_q))
        except np.linalg.LinAlgError:
            cond = float("inf")
        out.append(
            FieldScalarRecord(
                node_id=int(node_id),
                q=tuple(float(v) for v in q),
                m_q_diag=diag,
                m_q_det=det,
                m_q_cond=cond,
                j_ux_fro=float(np.linalg.norm(j_ux, ord="fro")),
            )
        )
    return out


def path_lengths(
    states: Sequence[PhysicalState],
    *,
    robot: RobotModel | None = None,
) -> TrajectoryPathMetrics:
    """Polyline path lengths via shared trajectory metrics."""
    return path_metrics_from_states(states, robot=robot)


def composite_j_alpha(
    *,
    length_u: float | None,
    length_q: float | None,
    length_x: float | None,
    weights: Mapping[str, float],
    norm_refs: Mapping[str, float],
    epsilon: float = EPS,
) -> dict[str, Any]:
    """Return exposed composite diagnostic components (not a ranking score)."""

    def _hat(value: float | None, key: str) -> float | None:
        if value is None:
            return None
        ref = float(norm_refs.get(key, 0.0))
        return float(abs(value) / max(abs(ref), epsilon))

    hats = {
        "L_U_hat": _hat(length_u, "L_U"),
        "L_Q_hat": _hat(length_q, "L_Q"),
        "L_X_hat": _hat(length_x, "L_X"),
    }
    alpha_u = float(weights.get("alpha_U", 0.0))
    alpha_q = float(weights.get("alpha_Q", 0.0))
    alpha_x = float(weights.get("alpha_X", 0.0))
    parts = []
    if hats["L_U_hat"] is not None:
        parts.append(alpha_u * hats["L_U_hat"])
    if hats["L_Q_hat"] is not None:
        parts.append(alpha_q * hats["L_Q_hat"])
    if hats["L_X_hat"] is not None:
        parts.append(alpha_x * hats["L_X_hat"])
    j_val = float(sum(parts)) if parts else None
    return {
        "J_alpha": j_val,
        "components_unnormalized": {
            "L_U": length_u,
            "L_Q": length_q,
            "L_X": length_x,
        },
        "components_normalized": hats,
        "weights": {
            "alpha_U": alpha_u,
            "alpha_Q": alpha_q,
            "alpha_X": alpha_x,
        },
        "normalization_refs": dict(norm_refs),
    }


def edge_bundle_to_jsonable(bundle: LatticeMetricBundle) -> dict[str, Any]:
    """Serialize a lattice metric bundle."""
    return {
        "connector_id": bundle.connector_id,
        "edges": [
            {
                "a": e.a,
                "b": e.b,
                "w_u": e.w_u,
                "w_q": e.w_q,
                "w_x": e.w_x,
                "stretch_q_over_u": e.stretch_q_over_u,
                "stretch_u_over_q": e.stretch_u_over_q,
            }
            for e in bundle.edges
        ],
        "fields": [
            {
                "node_id": f.node_id,
                "q": list(f.q),
                "m_q_diag": list(f.m_q_diag),
                "m_q_det": f.m_q_det,
                "m_q_cond": f.m_q_cond,
                "j_ux_fro": f.j_ux_fro,
            }
            for f in bundle.fields
        ],
    }


__all__ = [
    "EPS",
    "EdgeWeightRecord",
    "FieldScalarRecord",
    "LatticeMetricBundle",
    "composite_j_alpha",
    "compute_node_fields",
    "edge_bundle_to_jsonable",
    "integrate_edge_weights",
    "path_lengths",
    "path_metrics_from_motion_samples",
]
