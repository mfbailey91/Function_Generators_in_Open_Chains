"""U/Q/X edge and field metrics for the planar-2R visual audit (V3-623 / V3-636)."""

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
from inequality_mechanisms.transmission_geometry.differential import (
    composite_jacobian,
)
from inequality_mechanisms.transmission_geometry.metrics import actuator_metric_on_q
from inequality_mechanisms.transmission_geometry.protocols import (
    KinematicTransmissionRobotModel,
)

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
class ActuatorMetricOnQRecord:
    """Actuator-travel metric expressed in Q at one lattice node (V3-636).

    For the operating-branch map ``q = g(u)``,

    .. math::

        M_Q^{(U)}(q) = J_{g^{-1}}(q)^\\mathsf T J_{g^{-1}}(q),
        \\qquad
        ds_U^2 = dq^\\mathsf T M_Q^{(U)} dq.

    ``kappa`` is ``lambda_max / lambda_min``; ``sqrt_kappa`` is the directional
    actuator-cost ratio. Legacy ``m_q_*`` properties remain for V3.6B callers.
    """

    node_id: int
    q: tuple[float, ...]
    lambda_min: float
    lambda_max: float
    sqrt_det: float
    kappa: float
    sqrt_kappa: float
    eigenvectors: tuple[tuple[float, ...], ...]
    j_ux_fro: float
    m_q_diag: tuple[float, ...]

    @property
    def m_q_det(self) -> float:
        """Determinant of ``M_Q^{(U)}`` (product of eigenvalues)."""
        return float(self.sqrt_det * self.sqrt_det)

    @property
    def m_q_cond(self) -> float:
        """Legacy alias for ``kappa`` (condition number of ``M_Q^{(U)}``)."""
        return float(self.kappa)

    def actuator_metric_on_q_dict(self) -> dict[str, Any]:
        """Serialize the fresh ``actuator_metric_on_q`` payload."""
        return {
            "lambda_min": self.lambda_min,
            "lambda_max": self.lambda_max,
            "sqrt_det": self.sqrt_det,
            "kappa": self.kappa,
            "sqrt_kappa": self.sqrt_kappa,
            "eigenvectors": [list(v) for v in self.eigenvectors],
            "j_ux_fro": self.j_ux_fro,
        }


# Backward-compatible name used by V3.6B call sites.
FieldScalarRecord = ActuatorMetricOnQRecord


@dataclass(frozen=True, slots=True)
class LatticeMetricBundle:
    """Edge weights and node fields for one mechanism lattice."""

    edges: tuple[EdgeWeightRecord, ...]
    fields: tuple[ActuatorMetricOnQRecord, ...]
    connector_id: str


def ellipse_semi_axes_from_eigenvalues(
    eigenvalues: Sequence[float],
    *,
    eps: float = EPS,
) -> NDArray[np.float64]:
    """Return metric-ellipse semi-axis lengths ``1 / sqrt(lambda_i)``.

    The unit-cost ellipse ``{dq : dq^T M dq = 1}`` has semi-axes
    ``1/sqrt(lambda_i)`` along the eigenvectors of ``M``.
    """
    lam = np.asarray(eigenvalues, dtype=np.float64).reshape(-1)
    return 1.0 / np.sqrt(np.maximum(lam, eps))


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
    eps: float = EPS,
) -> list[ActuatorMetricOnQRecord]:
    """Compute ``actuator_metric_on_q`` fields via the V4 geometry kernel.

    ``M_Q`` comes from :func:`actuator_metric_on_q` and ``J_{xu}`` from
    :func:`composite_jacobian`. Rank-deficient transmissions raise
    ``DifferentialSingularityError`` rather than using a pseudoinverse.
    Eigenvalue and ellipse diagnostics remain V3 visualization fields.
    """
    branch = getattr(robot, "branch", None)
    v4_robot = isinstance(robot, KinematicTransmissionRobotModel)
    if branch is None and not v4_robot:
        raise TypeError("robot must expose an operating branch for field metrics")
    assembly = dict(assembly_state or {})
    out: list[ActuatorMetricOnQRecord] = []
    for node_id in range(graph.node_count):
        if not graph.node_is_valid(node_id):
            continue
        q = np.asarray(graph.q_state(node_id), dtype=np.float64)
        u = np.asarray(graph.u_state(node_id), dtype=np.float64)
        state = PhysicalState(u=u, q=q, assembly_state=assembly)
        if v4_robot:
            j_g = np.asarray(robot.jacobian_u_to_q(state), dtype=np.float64)
        else:
            assert branch is not None
            j_g = np.asarray(branch.jacobian(u), dtype=np.float64)
        m_q = actuator_metric_on_q(j_g)
        evals, evecs = np.linalg.eigh(m_q)
        evals = np.asarray(evals, dtype=np.float64)
        # Guard tiny / non-positive eigenvalues from roundoff.
        evals_pos = np.maximum(evals, eps)
        lambda_min = float(evals_pos[0])
        lambda_max = float(evals_pos[-1])
        kappa = float(lambda_max / max(lambda_min, eps))
        sqrt_kappa = float(np.sqrt(max(kappa, eps)))
        det_guarded = float(np.prod(evals_pos))
        sqrt_det = float(np.sqrt(max(det_guarded, eps)))
        j_f = np.asarray(robot.jacobian_q_to_x(state), dtype=np.float64)
        j_ux = composite_jacobian(j_f, j_g)
        diag = tuple(float(m_q[i, i]) for i in range(m_q.shape[0]))
        evec_cols = tuple(
            tuple(float(x) for x in evecs[:, i]) for i in range(evecs.shape[1])
        )
        out.append(
            ActuatorMetricOnQRecord(
                node_id=int(node_id),
                q=tuple(float(v) for v in q),
                lambda_min=lambda_min,
                lambda_max=lambda_max,
                sqrt_det=sqrt_det,
                kappa=kappa,
                sqrt_kappa=sqrt_kappa,
                eigenvectors=evec_cols,
                j_ux_fro=float(np.linalg.norm(j_ux, ord="fro")),
                m_q_diag=diag,
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
    """Serialize a lattice metric bundle.

    Fresh node fields expose ``actuator_metric_on_q`` (V3-636). Legacy
    ``m_q_*`` keys remain as aliases for callers that still read them. This
    writer must not be used to overwrite frozen V3.6B metric JSON.
    """
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
                "actuator_metric_on_q": f.actuator_metric_on_q_dict(),
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
    "ActuatorMetricOnQRecord",
    "EdgeWeightRecord",
    "FieldScalarRecord",
    "LatticeMetricBundle",
    "composite_j_alpha",
    "compute_node_fields",
    "edge_bundle_to_jsonable",
    "ellipse_semi_axes_from_eigenvalues",
    "integrate_edge_weights",
    "path_lengths",
    "path_metrics_from_motion_samples",
]
