"""V3.6E gravity-free static wrench core tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits import v3_span_wrench_guard
from inequality_mechanisms.audits.v3_span_wrench_guard import (
    REPO_ROOT,
    V3_6E_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    assert_v3_6e_output_allowed,
    prepare_v3_6e_output_dir,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
)
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    fixed_ratio_gearbox_branch,
    select_fourbar_monotonic_branch,
    unit_gearbox_branch,
)
from inequality_mechanisms.mechanisms.span_registry import load_span_registry
from inequality_mechanisms.mechanisms.span_synthesis import reconstruct_bar
from inequality_mechanisms.metrics.static_wrench import (
    DEFAULT_TORQUE_LIMITS,
    WrenchStateStatus,
    directional_capacity,
    evaluate_static_wrench_grid,
    grid_cache_key,
    isotropic_radius,
    jacobians_from_snapshot,
    reject_unsupported_physics,
    static_wrench_at_q,
    static_wrench_at_state,
    static_wrench_from_maps,
    static_wrench_from_snapshot,
)
from inequality_mechanisms.metrics.wrench_directions import named_task_directions
from inequality_mechanisms.transmission_geometry import (
    composite_jacobian,
    geometry_snapshot,
    pullback_covector,
    pushforward_vector,
)
from tests.graphs_v2._fixtures import fourbar_2d_branch
from tests.v4.jacobian_finite_difference import central_difference_jacobian

PLANAR = Planar2R(L1=1.0, L2=1.0)
D_REGISTRY = REPO_ROOT / "results" / "v3_review" / "v3_6d_span_corpus" / "registry.json"


def _identity_robot():
    branch = unit_gearbox_branch(2, input_lower=[-2.0, -2.0], input_upper=[2.0, 2.0])
    return planar_2r_operating_branch_robot(branch, planar_fk=PLANAR)


def _ratio_robot():
    branch = fixed_ratio_gearbox_branch(
        [2.0, 0.5],
        input_lower=[-2.0, -2.0],
        input_upper=[2.0, 2.0],
    )
    return planar_2r_operating_branch_robot(branch, planar_fk=PLANAR)


def _fourbar_robot():
    return planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=PLANAR)


def _interior_u(robot) -> np.ndarray:
    cert = robot.branch.certificate
    lo = np.asarray(cert.input_lower, dtype=np.float64)
    hi = np.asarray(cert.input_upper, dtype=np.float64)
    return 0.5 * (lo + hi)


def _polygon_ray_alpha(vertices: np.ndarray, direction: np.ndarray) -> float:
    d = np.asarray(direction, dtype=np.float64)
    d = d / np.linalg.norm(d)
    best = np.inf
    n = len(vertices)
    for i in range(n):
        start = vertices[i]
        edge = vertices[(i + 1) % n] - start
        mat = np.column_stack([edge, -d])
        if abs(float(np.linalg.det(mat))) <= 1e-14:
            continue
        s, t = np.linalg.solve(mat, -start)
        if -1e-9 <= s <= 1.0 + 1e-9 and t >= -1e-9:
            best = min(best, float(t))
    return float(best)


def test_v3_6e_allowed_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v3_span_wrench_guard, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v3_review" / V3_6E_ALLOWED_PACKAGE
    created = prepare_v3_6e_output_dir(allowed)
    assert created.is_dir()
    assert assert_v3_6e_output_allowed(created / "manifest.json") == (
        created / "manifest.json"
    ).resolve()


@pytest.mark.parametrize("package", [V4_0_ALLOWED_PACKAGE, V4_1_ALLOWED_PACKAGE])
def test_v3_6e_refuses_retained_v4(package: str) -> None:
    path = REPO_ROOT / "results" / "v4_review" / package
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6e_output_allowed(path)


def test_v3_6e_refuses_d_and_f_and_arbitrary(tmp_path: Path) -> None:
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6e_output_allowed(
            REPO_ROOT / "results" / "v3_review" / "v3_6d_span_corpus"
        )
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6e_output_allowed(
            REPO_ROOT / "results" / "v3_review" / "v3_6f_static_wrench_atlas"
        )
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6e_output_allowed(tmp_path / "elsewhere")


def test_reject_gravity_fields() -> None:
    with pytest.raises(Exception, match="gravity"):
        reject_unsupported_physics({"gravity_vector": [0.0, -9.81]})
    with pytest.raises(Exception, match="payload"):
        reject_unsupported_physics({"payload_mass": 2.0})
    robot = _identity_robot()
    state = robot.state_from_input([0.2, 0.7])
    snap = geometry_snapshot(robot, state)
    with pytest.raises(Exception, match="gravity"):
        static_wrench_from_snapshot(snap, extra_physics={"gravity_compensation": True})


def test_virtual_work_identity_random() -> None:
    rng = np.random.default_rng(660)
    robot = _identity_robot()
    for _ in range(8):
        u = np.array([rng.uniform(-0.6, 0.6), rng.uniform(0.3, 1.0)])
        state = robot.state_from_input(u)
        snap = geometry_snapshot(robot, state)
        j_g, j_f, j_xu = jacobians_from_snapshot(snap)
        np.testing.assert_allclose(j_xu, composite_jacobian(j_f, j_g), atol=1e-12)
        w = rng.normal(size=2)
        du = rng.normal(size=2)
        tau_u = pullback_covector(j_xu, w)
        dx = pushforward_vector(j_xu, du)
        np.testing.assert_allclose(tau_u @ du, w @ dx, atol=1e-12)


def test_identity_and_constant_gear_analytic() -> None:
    identity = _identity_robot()
    ratio = _ratio_robot()
    u = np.array([0.0, np.pi / 2])
    cap_i = static_wrench_at_state(identity, identity.state_from_input(u))
    cap_r = static_wrench_at_state(ratio, ratio.state_from_input(u))
    assert cap_i.status is WrenchStateStatus.REGULAR
    assert cap_r.status is WrenchStateStatus.REGULAR
    np.testing.assert_allclose(cap_i.j_g, np.eye(2), atol=1e-12)
    np.testing.assert_allclose(np.diag(cap_r.j_g), [2.0, 0.5], atol=1e-12)
    np.testing.assert_allclose(cap_i.joint_torque_amplification, [1.0, 1.0], atol=1e-12)
    np.testing.assert_allclose(cap_r.joint_torque_amplification, [0.5, 2.0], atol=1e-12)
    assert cap_i.vertices is not None and cap_r.vertices is not None
    expected_jf = np.array([[-1.0, -1.0], [1.0, 0.0]], dtype=np.float64)
    np.testing.assert_allclose(cap_i.j_f, expected_jf, atol=1e-12)
    assert cap_i.isotropic_radius == pytest.approx(1.0 / np.sqrt(2.0), rel=1e-9)


def test_fourbar_jg_finite_difference() -> None:
    robot = _fourbar_robot()
    u = _interior_u(robot)
    state = robot.state_from_input(u)
    analytic = np.asarray(robot.jacobian_u_to_q(state), dtype=np.float64)
    fd = central_difference_jacobian(lambda uu: robot.branch.forward(uu), u, h=1e-6)
    np.testing.assert_allclose(analytic, fd, atol=5e-8, rtol=5e-8)


def test_regular_vertices_saturate_torque_box_and_hrep() -> None:
    robot = _identity_robot()
    cap = static_wrench_at_state(robot, robot.state_from_input([0.1, 0.8]))
    assert cap.vertices is not None
    a_map = cap.j_xu.T
    sat = a_map @ cap.vertices.T
    np.testing.assert_allclose(
        np.abs(sat),
        np.broadcast_to(cap.torque_limits[:, None], sat.shape),
        atol=1e-9,
    )
    hrep = cap.hrep_a @ cap.vertices.T
    assert np.all(hrep <= cap.hrep_b[:, None] + 1e-9)
    mid = 0.25 * cap.vertices.sum(axis=0)
    assert np.all(cap.hrep_a @ mid <= cap.hrep_b + 1e-9)


def test_directional_capacity_matches_polygon_ray() -> None:
    robot = _identity_robot()
    cap = static_wrench_at_state(robot, robot.state_from_input([0.2, 0.7]))
    assert cap.vertices is not None
    a_map = cap.j_xu.T
    for d in ([1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [-0.3, 0.8]):
        alpha = directional_capacity(a_map, cap.torque_limits, d)
        ray = _polygon_ray_alpha(cap.vertices, np.asarray(d, dtype=np.float64))
        assert alpha == pytest.approx(ray, rel=1e-7, abs=1e-7)


def test_isotropic_radius_matches_angular_sample() -> None:
    robot = _identity_robot()
    cap = static_wrench_at_state(robot, robot.state_from_input([0.15, 0.9]))
    a_map = cap.j_xu.T
    thetas = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
    sampled = [
        directional_capacity(a_map, cap.torque_limits, [np.cos(t), np.sin(t)])
        for t in thetas
    ]
    assert min(sampled) == pytest.approx(cap.isotropic_radius, rel=2e-3, abs=2e-3)
    assert isotropic_radius(a_map, cap.torque_limits) == pytest.approx(
        cap.isotropic_radius, abs=1e-12
    )


def test_linear_torque_scaling() -> None:
    robot = _identity_robot()
    state = robot.state_from_input([0.2, 0.6])
    snap = geometry_snapshot(robot, state)
    cap1 = static_wrench_from_snapshot(snap, torque_limits=(1.0, 1.0))
    cap2 = static_wrench_from_snapshot(snap, torque_limits=(2.0, 2.0))
    assert cap1.vertices is not None and cap2.vertices is not None
    np.testing.assert_allclose(cap2.vertices, 2.0 * cap1.vertices, atol=1e-9)
    assert cap2.isotropic_radius == pytest.approx(2.0 * cap1.isotropic_radius, rel=1e-9)


def test_rotational_equivariance_of_cartesian_force() -> None:
    robot = _identity_robot()
    cap = static_wrench_at_state(robot, robot.state_from_input([0.25, 0.65]))
    theta = np.pi / 5
    rot = np.array(
        [[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]],
        dtype=np.float64,
    )
    j_f = rot @ cap.j_f
    j_xu = composite_jacobian(j_f, cap.j_g)
    rotated = static_wrench_from_maps(
        q=cap.q,
        u=cap.u,
        x=rot @ cap.x,
        j_g=cap.j_g,
        j_f=j_f,
        j_xu=j_xu,
        named_directions={"positive_x": np.array([1.0, 0.0])},
    )
    assert cap.vertices is not None and rotated.vertices is not None
    expected = cap.vertices @ rot.T
    # Sort both by angle about origin.
    def _order(verts: np.ndarray) -> np.ndarray:
        ang = np.arctan2(verts[:, 1], verts[:, 0])
        return verts[np.argsort(ang)]

    np.testing.assert_allclose(_order(rotated.vertices), _order(expected), atol=1e-9)


def test_rank_deficient_and_unbounded_are_typed() -> None:
    robot = _identity_robot()
    stretched = static_wrench_at_state(robot, robot.state_from_input([0.35, 0.0]))
    assert stretched.vertices is None
    assert stretched.status in {
        WrenchStateStatus.RANK_DEFICIENT,
        WrenchStateStatus.UNBOUNDED_IDEAL_DIRECTION,
    }
    assert stretched.rank_attribution["j_f"] == "rank_deficient"
    assert stretched.rank_attribution["primary_cause"] == "arm_jacobian_rank_loss"
    zero = static_wrench_from_maps(
        q=[0.0, 0.0],
        u=[0.0, 0.0],
        x=[2.0, 0.0],
        j_g=np.eye(2),
        j_f=np.zeros((2, 2)),
        j_xu=np.zeros((2, 2)),
        named_directions={"positive_x": np.array([1.0, 0.0])},
    )
    assert zero.status is WrenchStateStatus.UNBOUNDED_IDEAL_DIRECTION
    assert zero.vertices is None
    assert np.isinf(zero.directional_capacity["positive_x"])
    invalid = static_wrench_at_q(robot, [10.0, 10.0])
    assert invalid.status is WrenchStateStatus.INVALID_MECHANISM_STATE
    origin_dirs = named_task_directions([0.0, 0.0])
    assert origin_dirs["radial"] is None
    assert origin_dirs["tangential"] is None


def test_scalar_and_batched_outputs_agree() -> None:
    robot = _identity_robot()
    qs = np.array([[0.1, 0.6], [0.2, 0.7], [0.0, 0.5]], dtype=np.float64)
    key = grid_cache_key(
        registry_hash="test",
        case_id="identity",
        mechanism_id="identity",
        q_samples=qs,
        torque_limits=DEFAULT_TORQUE_LIMITS,
    )
    batched = evaluate_static_wrench_grid(robot, qs, cache_key=key)
    cached = evaluate_static_wrench_grid(robot, qs, cache_key=key)
    assert batched is cached
    for q, row in zip(qs, batched):
        scalar = static_wrench_at_q(robot, q)
        np.testing.assert_allclose(row.isotropic_radius, scalar.isotropic_radius)
        assert row.status is scalar.status
        if row.vertices is not None:
            np.testing.assert_allclose(row.vertices, scalar.vertices)


def test_five_span_outcomes_evaluate_from_d_artifact() -> None:
    payload = json.loads(D_REGISTRY.read_text(encoding="utf-8"))
    registry = load_span_registry(payload)
    statuses = []
    for record in registry.records:
        bar = reconstruct_bar(record)
        pair = IndependentFourBars([bar, bar], name=f"span_{record.target_span_deg:.0f}")
        min_gain = 0.005 if record.status == "boundary_stress_only" else 0.05
        branch = select_fourbar_monotonic_branch(
            pair,
            u_intervals=[record.u_interval_rad, record.u_interval_rad],
            min_abs_gain=min_gain,
            endpoint_margin_fraction=0.0,
            name=pair.name,
        )
        robot = planar_2r_operating_branch_robot(branch, planar_fk=PLANAR)
        cap = static_wrench_at_state(robot, robot.state_from_input(_interior_u(robot)))
        assert cap.status is WrenchStateStatus.REGULAR
        assert cap.vertices is not None
        assert np.isfinite(cap.isotropic_radius)
        statuses.append(record.status)
    assert statuses == [
        "certified_primary",
        "certified_primary",
        "certified_primary",
        "certified_primary",
        "boundary_stress_only",
    ]


def test_no_second_jacobian_module() -> None:
    path = (
        REPO_ROOT
        / "src"
        / "inequality_mechanisms"
        / "kinematics"
        / "composite_jacobian.py"
    )
    assert not path.exists()
