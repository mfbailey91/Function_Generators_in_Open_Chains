"""V4-107 analytic controls, V4.0 overlap, and test-only finite differences."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from inequality_mechanisms.audits.v4_artifact_guard import (
    REPO_ROOT,
    V4_0_ALLOWED_OUTPUT_REL,
    v4_0_smoke_package_digest,
)
from inequality_mechanisms.experiments.v4.atlas_config import (
    DEFAULT_CONFIG_REL,
    load_atlas_config,
)
from inequality_mechanisms.experiments.v4.controls import build_atlas_arms, span_matched_ratios
from inequality_mechanisms.experiments.v4.geometry_atlas import evaluate_atlas_sample
from inequality_mechanisms.experiments.v4.shared_q_atlas import SharedQSample, build_shared_q_bank
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.transmission_geometry import geometry_snapshot
from tests.v4.jacobian_finite_difference import (
    central_difference_jacobian,
    step_size_sensitivity,
)
from tests.v4.test_v4_009_closeout import DIGEST_LOCK as V3_DIGEST_LOCK
from tests.v4.test_v4_009_closeout import test_frozen_v3_review_digests_are_unchanged

DIGEST_V4_0 = Path(__file__).resolve().parent / "data" / "frozen_v4_0_smoke_digests.json"


def test_v3_and_v4_0_digests_unchanged() -> None:
    test_frozen_v3_review_digests_are_unchanged()
    lock = json.loads(DIGEST_V4_0.read_text(encoding="utf-8"))
    sha, n_files = v4_0_smoke_package_digest()
    assert n_files == lock["n_files"]
    assert sha == lock["sha256"]
    assert V3_DIGEST_LOCK.is_file()


def test_analytic_identity_and_span_metric() -> None:
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    arms = build_atlas_arms(config)
    ratios = np.asarray(span_matched_ratios(arms["fourbar"].branch), dtype=np.float64)
    cert = arms["fourbar"].branch.certificate
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=(3, 3),
        inset_fraction=0.01,
    )
    sample = bank.samples[4]
    ident = evaluate_atlas_sample(
        arms["identity_on_shared_q"], sample, config=config, revision="test"
    )
    gb = evaluate_atlas_sample(
        arms["span_matched_gearbox"], sample, config=config, revision="test"
    )
    assert ident.snapshot is not None and gb.snapshot is not None
    np.testing.assert_allclose(ident.snapshot.actuator_metric_on_q, np.eye(2), atol=1e-12)
    np.testing.assert_allclose(ident.snapshot.mobility_on_q, np.eye(2), atol=1e-12)
    expected_m = np.diag(1.0 / (ratios ** 2))
    expected_b = np.diag(ratios ** 2)
    np.testing.assert_allclose(gb.snapshot.actuator_metric_on_q, expected_m, atol=1e-12)
    np.testing.assert_allclose(gb.snapshot.mobility_on_q, expected_b, atol=1e-12)


def test_direct_snapshot_and_v4_0_overlap() -> None:
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    arms = build_atlas_arms(config)
    smoke_root = REPO_ROOT / V4_0_ALLOWED_OUTPUT_REL
    lines = (smoke_root / "geometry_samples.jsonl").read_text(encoding="utf-8").splitlines()
    smoke_rows = [json.loads(line) for line in lines if line.strip()]
    compared = 0
    for smoke in smoke_rows[:12]:
        mech = smoke["mechanism_id"]
        if mech not in arms:
            continue
        snap = smoke["snapshot"]
        q = tuple(float(v) for v in snap["q"])
        sample = SharedQSample(
            q_sample_id=str(smoke["q_sample_id"]),
            grid_index=(int(smoke["grid_i"]), int(smoke["grid_j"])),
            q=(q[0], q[1]),
        )
        row = evaluate_atlas_sample(arms[mech], sample, config=config, revision="test")
        assert row.snapshot is not None
        state = arms[mech].robot.states_from_output(np.asarray(q))[0].state
        fresh = geometry_snapshot(arms[mech].robot, state)
        np.testing.assert_allclose(row.snapshot.j_u_to_q, fresh.j_u_to_q, atol=1e-12)
        np.testing.assert_allclose(row.snapshot.q, snap["q"], atol=1e-10)
        np.testing.assert_allclose(row.snapshot.x, snap["x"], atol=1e-10)
        np.testing.assert_allclose(
            row.snapshot.j_u_to_q, snap["jacobians"]["j_u_to_q"], atol=1e-10
        )
        compared += 1
    assert compared >= 8


def test_independent_finite_differences_and_near_singular() -> None:
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    arms = build_atlas_arms(config)
    robot = arms["fourbar"].robot
    cert = arms["fourbar"].branch.certificate
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=(3, 3),
        inset_fraction=0.01,
    )
    state = robot.states_from_output(np.asarray(bank.samples[4].q))[0].state
    snapshot = geometry_snapshot(robot, state)
    u = np.asarray(state.u, dtype=np.float64)

    def g(uu: np.ndarray) -> np.ndarray:
        return np.asarray(robot.branch.forward(uu), dtype=np.float64)

    def f_of_q(qq: np.ndarray) -> np.ndarray:
        st = PhysicalState(u=state.u, q=qq, assembly_state=state.assembly_state)
        return np.asarray(robot.forward_kinematics(st).position, dtype=np.float64)

    def f_of_u(uu: np.ndarray) -> np.ndarray:
        st = robot.state_from_input(uu)
        return np.asarray(robot.forward_kinematics(st).position, dtype=np.float64)

    j_g = np.asarray(snapshot.j_u_to_q)
    j_f = np.asarray(snapshot.j_q_to_x)
    j_xu = np.asarray(snapshot.j_u_to_x)
    fd_g = central_difference_jacobian(g, u, h=1e-6)
    fd_xu = central_difference_jacobian(f_of_u, u, h=1e-6)
    q = np.asarray(state.q)
    fd_f = central_difference_jacobian(f_of_q, q, h=1e-6)
    assert float(np.max(np.abs(fd_g - j_g))) < 1e-5
    assert float(np.max(np.abs(fd_f - j_f))) < 1e-5
    assert float(np.max(np.abs(fd_xu - j_xu))) < 1e-5
    residuals = step_size_sensitivity(g, j_g, u)
    assert min(residuals.values()) < 1e-5

    from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
    from inequality_mechanisms.kinematics.planar_2r import Planar2R
    from inequality_mechanisms.mechanisms.operating_branch import unit_gearbox_branch

    near = unit_gearbox_branch(
        2, input_lower=[-0.2, -0.2], input_upper=[0.2, 0.2], name="near_stretch"
    )
    near_robot = planar_2r_operating_branch_robot(
        near, planar_fk=Planar2R(L1=1.0, L2=1.0)
    )
    near_state = near_robot.state_from_input(np.zeros(2))
    near_snap = geometry_snapshot(near_robot, near_state)
    assert near_snap.rank_u_to_q.full_rank
    assert not near_snap.rank_q_to_x.full_rank
