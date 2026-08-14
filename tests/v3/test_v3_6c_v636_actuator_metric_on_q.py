"""V3-636: actuator metric on Q (eigenvalues, shared log scales, ellipses)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.metrics import (
    ActuatorMetricOnQRecord,
    compute_node_fields,
    edge_bundle_to_jsonable,
    ellipse_semi_axes_from_eigenvalues,
    integrate_edge_weights,
)
from inequality_mechanisms.audits.planar2r_visual import pack_actuator_metric_on_q_panels
from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import (
    equivalent_gearbox_branch,
    fixed_ratio_gearbox_branch,
)
from inequality_mechanisms.visualization.audit_actuator_metric import (
    PRIMARY_FIELD,
    field_values,
    shared_log_norm_limits,
    write_actuator_metric_on_q_panels,
)


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
    graph = EmbeddedPlanningGraph.from_output_lattice(shared, branch)
    return graph


def test_equal_ratio_gearbox_kappa_near_one() -> None:
    robot = _equal_ratio_gearbox_robot()
    graph = _tiny_lattice(robot, shape=(4, 4))
    fields = compute_node_fields(graph, robot)
    assert fields
    for f in fields:
        assert isinstance(f, ActuatorMetricOnQRecord)
        assert f.kappa == pytest.approx(1.0, abs=1e-9, rel=0.0)
        assert f.sqrt_kappa == pytest.approx(1.0, abs=1e-9, rel=0.0)
        # Equal ratios ⇒ M = (1/r^2) I; eigenvalues equal.
        assert f.lambda_min == pytest.approx(f.lambda_max, abs=1e-9, rel=0.0)


def test_fourbar_finite_on_certified_branch() -> None:
    robot = _fourbar_robot()
    graph = _tiny_lattice(robot, shape=(6, 6))
    fields = compute_node_fields(graph, robot)
    assert fields
    for f in fields:
        assert np.isfinite(f.lambda_min) and f.lambda_min > 0.0
        assert np.isfinite(f.lambda_max) and f.lambda_max >= f.lambda_min
        assert np.isfinite(f.kappa) and f.kappa >= 1.0
        assert np.isfinite(f.sqrt_kappa) and f.sqrt_kappa >= 1.0
        assert np.isfinite(f.sqrt_det) and f.sqrt_det > 0.0
        assert np.isfinite(f.j_ux_fro)
        assert f.m_q_cond == pytest.approx(f.kappa, abs=0.0, rel=0.0)


def test_shared_paired_color_limits(tmp_path: Path) -> None:
    fourbar = fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    shared = UniformOutputLattice.from_output_space(fourbar.output_space, shape=(5, 5))
    robots = {
        "fourbar": planar_2r_operating_branch_robot(fourbar, planar_fk=Planar2R(1.0, 1.0)),
        "gearbox": planar_2r_operating_branch_robot(gearbox, planar_fk=Planar2R(1.0, 1.0)),
    }
    bundles = {}
    for mech, branch in (("fourbar", fourbar), ("gearbox", gearbox)):
        graph = EmbeddedPlanningGraph.from_output_lattice(shared, branch)
        bundles[mech] = integrate_edge_weights(graph, robots[mech], n_samples=8)

    fb_vals = field_values(bundles["fourbar"].fields, PRIMARY_FIELD)
    gb_vals = field_values(bundles["gearbox"].fields, PRIMARY_FIELD)
    vmin, vmax = shared_log_norm_limits(fb_vals, gb_vals)
    assert vmin > 0.0 and vmax >= vmin
    assert vmin <= min(min(fb_vals), min(gb_vals)) + 1e-15
    assert vmax >= max(max(fb_vals), max(gb_vals)) - 1e-15

    assets = write_actuator_metric_on_q_panels(
        bundles=bundles,
        out_dir=tmp_path,
        task_id="t0",
        ellipse_stride=4,
    )
    assert "fourbar_actuator_metric_sqrt_kappa" in assets
    assert "gearbox_actuator_metric_sqrt_kappa" in assets
    assert assets["fourbar_actuator_metric_sqrt_kappa"].is_file()
    assert assets["gearbox_actuator_metric_sqrt_kappa"].is_file()
    limits = assets["actuator_metric_shared_log_limits"]
    assert limits.is_file()
    import json

    payload = json.loads(limits.read_text(encoding="utf-8"))
    assert payload["field"] == PRIMARY_FIELD
    assert payload["vmin"] == pytest.approx(vmin)
    assert payload["vmax"] == pytest.approx(vmax)

    packed = pack_actuator_metric_on_q_panels(
        bundles=bundles,
        out_dir=tmp_path / "packed",
        task_id="t0",
    )
    assert "fourbar_actuator_metric_sqrt_kappa" in packed


def test_serialization_naming() -> None:
    robot = _equal_ratio_gearbox_robot()
    graph = _tiny_lattice(robot, shape=(3, 3))
    bundle = integrate_edge_weights(graph, robot, n_samples=6)
    payload = edge_bundle_to_jsonable(bundle)
    assert payload["fields"]
    row = payload["fields"][0]
    assert "actuator_metric_on_q" in row
    am = row["actuator_metric_on_q"]
    for key in (
        "lambda_min",
        "lambda_max",
        "sqrt_det",
        "kappa",
        "sqrt_kappa",
        "eigenvectors",
        "j_ux_fro",
    ):
        assert key in am
    # Legacy aliases retained for callers still reading m_q_*.
    assert "m_q_cond" in row
    assert row["m_q_cond"] == pytest.approx(am["kappa"])
    assert "m_q_diag" in row
    assert "m_q_det" in row


def test_diagonal_ellipse_axis_length_smoke() -> None:
    # M = diag(4, 1) ⇒ lambdas (1, 4); semi-axes 1/sqrt(lambda).
    axes = ellipse_semi_axes_from_eigenvalues((1.0, 4.0))
    assert axes.shape == (2,)
    assert float(axes[0]) == pytest.approx(1.0, abs=1e-12)
    assert float(axes[1]) == pytest.approx(0.5, abs=1e-12)

    robot = _equal_ratio_gearbox_robot()
    graph = _tiny_lattice(robot, shape=(3, 3))
    fields = compute_node_fields(graph, robot)
    f = fields[0]
    axes_f = ellipse_semi_axes_from_eigenvalues((f.lambda_min, f.lambda_max))
    expected = 1.0 / np.sqrt(np.array([f.lambda_min, f.lambda_max]))
    assert axes_f == pytest.approx(expected, abs=1e-12)
