"""V4-105 rank attribution from snapshot reports."""

from __future__ import annotations

import numpy as np

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.v4_artifact_guard import REPO_ROOT
from inequality_mechanisms.experiments.v4.atlas_config import (
    DEFAULT_CONFIG_REL,
    load_atlas_config,
)
from inequality_mechanisms.experiments.v4.controls import build_atlas_arms
from inequality_mechanisms.experiments.v4.geometry_atlas import evaluate_atlas_sample
from inequality_mechanisms.experiments.v4.rank_fields import (
    attribution_from_row,
    attribution_from_snapshot,
)
from inequality_mechanisms.experiments.v4.shared_q_atlas import build_shared_q_bank
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms.operating_branch import unit_gearbox_branch
from inequality_mechanisms.transmission_geometry import geometry_snapshot
from inequality_mechanisms.transmission_geometry.differential import RankReport
from inequality_mechanisms.transmission_geometry.snapshot import (
    METRIC_STATUS_AVAILABLE,
    METRIC_STATUS_RANK_DEFICIENT,
    KinematicGeometrySnapshot,
)


def _report(*, rank: int, full: bool, cond: float | None) -> RankReport:
    return RankReport(
        shape=(2, 2),
        rank=rank,
        required_full_rank=2,
        singular_values=(1.0, 0.0 if rank < 2 else 0.5),
        tolerance=1e-12,
        full_rank=full,
        condition_number=cond,
    )


def test_regular_interior_is_transmission_full_rank() -> None:
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    arms = build_atlas_arms(config)
    cert = arms["fourbar"].branch.certificate
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=(3, 3),
        inset_fraction=0.01,
    )
    row = evaluate_atlas_sample(
        arms["fourbar"], bank.samples[4], config=config, revision="test"
    )
    attr = attribution_from_row(row)
    assert attr.failure_code is None
    assert attr.transmission_full_rank
    assert attr.manipulator_full_rank
    assert attr.composite_full_rank
    assert attr.metric_status == METRIC_STATUS_AVAILABLE


def test_manipulator_singularity_is_not_blamed_on_transmission() -> None:
    branch = unit_gearbox_branch(
        2,
        input_lower=[-0.2, -0.2],
        input_upper=[0.2, 0.2],
        name="identity_near_stretch",
    )
    robot = planar_2r_operating_branch_robot(branch, planar_fk=Planar2R(L1=1.0, L2=1.0))
    state = robot.state_from_input(np.zeros(2))
    snapshot = geometry_snapshot(robot, state)
    attr = attribution_from_snapshot(
        snapshot, q_sample_id="crafted", mechanism_id="identity"
    )
    assert attr.transmission_full_rank
    assert not attr.manipulator_full_rank
    assert not attr.composite_full_rank
    assert attr.metric_status == METRIC_STATUS_AVAILABLE


def test_transmission_singularity_test_double() -> None:
    snapshot = KinematicGeometrySnapshot(
        u=(0.0, 0.0),
        q=(0.0, 0.0),
        x=(1.0, 0.0),
        j_u_to_q=((1.0, 0.0), (0.0, 0.0)),
        j_q_to_x=((1.0, 0.0), (0.0, 1.0)),
        j_u_to_x=((1.0, 0.0), (0.0, 0.0)),
        rank_u_to_q=_report(rank=1, full=False, cond=None),
        rank_q_to_x=_report(rank=2, full=True, cond=1.0),
        rank_u_to_x=_report(rank=1, full=False, cond=None),
        actuator_weight=((1.0, 0.0), (0.0, 1.0)),
        actuator_metric_on_q=None,
        mobility_on_q=((1.0, 0.0), (0.0, 0.0)),
        mobility_on_x=((1.0, 0.0), (0.0, 0.0)),
        metric_status=METRIC_STATUS_RANK_DEFICIENT,
        provenance={"kernel": "v4.0"},
    )
    attr = attribution_from_snapshot(
        snapshot, q_sample_id="double", mechanism_id="test"
    )
    assert not attr.transmission_full_rank
    assert attr.manipulator_full_rank
    assert attr.metric_status == METRIC_STATUS_RANK_DEFICIENT
    assert attr.transmission_rank == 1
