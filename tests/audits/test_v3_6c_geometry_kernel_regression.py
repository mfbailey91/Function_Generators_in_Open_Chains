"""V4-005: fresh V3.6C audit path uses the shared geometry kernel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.metrics import (
    EPS,
    compute_node_fields,
    edge_bundle_to_jsonable,
    integrate_edge_weights,
)
from inequality_mechanisms.core.input_domain import InputDomain
from inequality_mechanisms.core.state import PhysicalState, Pose, StateCandidate
from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import (
    equivalent_gearbox_branch,
    fixed_ratio_gearbox_branch,
)
from inequality_mechanisms.transmission_geometry.errors import (
    DifferentialSingularityError,
)
from inequality_mechanisms.visualization.audit_actuator_metric import (
    PRIMARY_FIELD,
    field_values,
    shared_log_norm_limits,
)

_METRICS_SRC = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "inequality_mechanisms"
    / "audits"
    / "metrics.py"
)

_FIELD_ROW_KEYS = {
    "node_id",
    "q",
    "actuator_metric_on_q",
    "m_q_diag",
    "m_q_det",
    "m_q_cond",
    "j_ux_fro",
}
_NESTED_METRIC_KEYS = {
    "lambda_min",
    "lambda_max",
    "sqrt_det",
    "kappa",
    "sqrt_kappa",
    "eigenvectors",
    "j_ux_fro",
}
_V4_SCHEMA_KEYS = {
    "schema_version",
    "rank_reports",
    "metric_status",
    "provenance",
    "mobility_on_q",
    "actuator_metric_on_q_available",
}


def _equal_ratio_gearbox_robot():
    branch = fixed_ratio_gearbox_branch(
        [2.0, 2.0],
        input_lower=[-1.0, -1.0],
        input_upper=[1.0, 1.0],
        name="equal_ratio_gearbox",
    )
    return planar_2r_operating_branch_robot(branch, planar_fk=Planar2R(1.0, 1.0))


def _fourbar_robot():
    return planar_2r_operating_branch_robot(
        fourbar_2d_branch(), planar_fk=Planar2R(1.0, 1.0)
    )


def _tiny_lattice(robot, shape=(5, 5)):
    branch = robot.branch
    shared = UniformOutputLattice.from_output_space(branch.output_space, shape=shape)
    return EmbeddedPlanningGraph.from_output_lattice(shared, branch)


def _legacy_regular_metric(
    j_g: np.ndarray,
    j_f: np.ndarray,
    *,
    eps: float = EPS,
) -> tuple[float, float, tuple[float, ...], float, float]:
    """Independent regular-state formula: ``inv``, not ``pinv``."""
    j_inv = np.linalg.inv(j_g)
    m_q = j_inv.T @ j_inv
    m_q = 0.5 * (m_q + m_q.T)
    evals = np.linalg.eigvalsh(m_q)
    evals_pos = np.maximum(evals, eps)
    lambda_min = float(evals_pos[0])
    lambda_max = float(evals_pos[-1])
    kappa = float(lambda_max / max(lambda_min, eps))
    sqrt_kappa = float(np.sqrt(max(kappa, eps)))
    diag = tuple(float(m_q[i, i]) for i in range(m_q.shape[0]))
    j_ux = j_f @ j_g
    j_ux_fro = float(np.linalg.norm(j_ux, ord="fro"))
    return lambda_min, lambda_max, diag, j_ux_fro, sqrt_kappa


class _OneNodeGraph:
    node_count = 1

    def node_is_valid(self, node_id: int) -> bool:
        return int(node_id) == 0

    def q_state(self, node_id: int) -> np.ndarray:
        return np.array([0.2, -0.1], dtype=np.float64)

    def u_state(self, node_id: int) -> np.ndarray:
        return np.array([0.2, -0.1], dtype=np.float64)


class _SingularJgRobot:
    """V4-capable robot whose transmission Jacobian is rank-deficient."""

    @property
    def dof(self) -> int:
        return 2

    @property
    def input_domain(self) -> InputDomain:
        return InputDomain(
            lower=np.array([-1.0, -1.0]),
            upper=np.array([1.0, 1.0]),
            periodic=(False, False),
        )

    def state_from_input(
        self,
        u: Any,
        assembly_state: Mapping[str, Any] | None = None,
    ) -> PhysicalState:
        u_arr = np.asarray(u, dtype=np.float64)
        return PhysicalState(u=u_arr, q=u_arr)

    def states_from_output(self, q: Any) -> Sequence[StateCandidate]:
        return ()

    def validate_state(self, state: PhysicalState, tolerance: float) -> bool:
        return float(np.linalg.norm(state.q - state.u)) <= float(tolerance)

    def forward_kinematics(self, state: PhysicalState) -> Pose:
        return Pose(position=np.asarray(state.q, dtype=np.float64))

    def jacobian_q_to_x(self, state: PhysicalState) -> np.ndarray:
        return np.eye(2, dtype=np.float64)

    def jacobian_u_to_q(self, state: PhysicalState) -> np.ndarray:
        return np.asarray([[1.0, 0.0], [0.0, 0.0]], dtype=np.float64)

    def state_within_limits(self, state: PhysicalState) -> bool:
        return True


def test_audit_source_does_not_use_pinv() -> None:
    source = _METRICS_SRC.read_text(encoding="utf-8")
    assert "pinv" not in source


@pytest.mark.parametrize("robot_factory", [_equal_ratio_gearbox_robot, _fourbar_robot])
def test_regular_node_fields_match_legacy_inv_formula(robot_factory) -> None:
    robot = robot_factory()
    graph = _tiny_lattice(robot, shape=(4, 4))
    fields = compute_node_fields(graph, robot)
    assert fields
    for record in fields:
        state = PhysicalState(
            u=np.asarray(graph.u_state(record.node_id), dtype=np.float64),
            q=np.asarray(record.q, dtype=np.float64),
        )
        j_g = np.asarray(robot.jacobian_u_to_q(state), dtype=np.float64)
        j_f = np.asarray(robot.jacobian_q_to_x(state), dtype=np.float64)
        lambda_min, lambda_max, diag, j_ux_fro, _sqrt_kappa = _legacy_regular_metric(
            j_g, j_f
        )
        assert record.lambda_min == pytest.approx(lambda_min, rel=0.0, abs=1e-12)
        assert record.lambda_max == pytest.approx(lambda_max, rel=0.0, abs=1e-12)
        assert record.m_q_diag == pytest.approx(diag, rel=0.0, abs=1e-12)
        assert record.j_ux_fro == pytest.approx(j_ux_fro, rel=0.0, abs=1e-12)


def test_jsonable_keys_remain_v3_schema() -> None:
    robot = _equal_ratio_gearbox_robot()
    graph = _tiny_lattice(robot, shape=(3, 3))
    payload = edge_bundle_to_jsonable(integrate_edge_weights(graph, robot, n_samples=6))
    assert payload["fields"]
    row = payload["fields"][0]
    assert set(row) == _FIELD_ROW_KEYS
    assert set(row["actuator_metric_on_q"]) == _NESTED_METRIC_KEYS
    dumped = str(payload)
    for key in _V4_SCHEMA_KEYS:
        assert key not in payload
        assert key not in row
        assert key not in row["actuator_metric_on_q"]
        assert key not in dumped


def test_paired_log_scale_inputs_match_golden_eigenvalues() -> None:
    fourbar = fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    shared = UniformOutputLattice.from_output_space(fourbar.output_space, shape=(5, 5))
    robots = {
        "fourbar": planar_2r_operating_branch_robot(
            fourbar, planar_fk=Planar2R(1.0, 1.0)
        ),
        "gearbox": planar_2r_operating_branch_robot(
            gearbox, planar_fk=Planar2R(1.0, 1.0)
        ),
    }
    golden: dict[str, list[float]] = {"fourbar": [], "gearbox": []}
    bundles = {}
    for name, branch in (("fourbar", fourbar), ("gearbox", gearbox)):
        graph = EmbeddedPlanningGraph.from_output_lattice(shared, branch)
        robot = robots[name]
        bundles[name] = integrate_edge_weights(graph, robot, n_samples=8)
        for record in bundles[name].fields:
            state = PhysicalState(
                u=np.asarray(graph.u_state(record.node_id), dtype=np.float64),
                q=np.asarray(record.q, dtype=np.float64),
            )
            j_g = np.asarray(robot.jacobian_u_to_q(state), dtype=np.float64)
            j_f = np.asarray(robot.jacobian_q_to_x(state), dtype=np.float64)
            *_rest, sqrt_kappa = _legacy_regular_metric(j_g, j_f)
            golden[name].append(sqrt_kappa)
    fb_vals = field_values(bundles["fourbar"].fields, PRIMARY_FIELD)
    gb_vals = field_values(bundles["gearbox"].fields, PRIMARY_FIELD)
    assert fb_vals == pytest.approx(golden["fourbar"], rel=0.0, abs=1e-12)
    assert gb_vals == pytest.approx(golden["gearbox"], rel=0.0, abs=1e-12)
    vmin, vmax = shared_log_norm_limits(fb_vals, gb_vals)
    expected = shared_log_norm_limits(golden["fourbar"], golden["gearbox"])
    assert vmin == pytest.approx(expected[0], rel=0.0, abs=1e-15)
    assert vmax == pytest.approx(expected[1], rel=0.0, abs=1e-15)
    assert vmin > 0.0 and vmax >= vmin


def test_rank_deficient_transmission_raises_without_pinv() -> None:
    with pytest.raises(DifferentialSingularityError) as info:
        compute_node_fields(_OneNodeGraph(), _SingularJgRobot())  # type: ignore[arg-type]
    assert info.value.operation == "actuator_metric_on_q"
    assert info.value.rank == 1
