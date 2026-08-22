"""V4.2B Phase 7: common-physical task bank freeze (V4-226)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT
from inequality_mechanisms.experiments.span_cases import generate_span_cases
from inequality_mechanisms.experiments.v4.span_common_physical_bank import (
    BANK_ID,
    DEFAULT_BANK_REL,
    FROZEN_TASK_IDS,
    GOAL_REPRESENTATION_KIND,
    bank_digest,
    build_common_physical_bank,
    common_mounted_q_box,
    load_common_physical_bank,
    strictly_inside,
)

V3_BANK_V2_REL = CANONICAL_REPO_ROOT / "configs" / "v3" / "free_space_planar2r_v2.json"
V3_BANK_V1_REL = CANONICAL_REPO_ROOT / "configs" / "v3" / "free_space_planar2r_v1.json"
V4_2A_AUDIT_REL = (
    CANONICAL_REPO_ROOT
    / "configs"
    / "v4"
    / "planar2r_span_controlled_visual_audit_v1.json"
)
CANDIDATE_IDS = (
    "center",
    "boundary_0deg",
    "boundary_45deg",
    "boundary_90deg",
    "boundary_135deg",
    "boundary_180deg",
    "boundary_225deg",
    "boundary_270deg",
    "boundary_315deg",
)


def _loaded() -> dict:
    return load_common_physical_bank(CANONICAL_REPO_ROOT / DEFAULT_BANK_REL)


def test_common_box_uses_frozen_registry_intervals_as_owner() -> None:
    usable = (-1.0, 1.0)
    drift = 5.0e-10  # Accepted reconstruction noise under FK_ATOL=1e-9.
    row = SimpleNamespace(
        target_span_deg=95.0,
        range_definition=SimpleNamespace(usable_interval_rad=usable),
    )
    certificate = SimpleNamespace(
        output_lower=(-1.0 + drift, -1.0 + drift),
        output_upper=(1.0 - drift, 1.0 - drift),
    )
    realized = SimpleNamespace(
        case=SimpleNamespace(case_id="synthetic_roundoff"),
        fourbar=SimpleNamespace(certificate=certificate),
        gearbox=SimpleNamespace(certificate=certificate),
        j1=row,
        j2=row,
    )

    lower, upper = common_mounted_q_box((realized,))

    np.testing.assert_array_equal(lower, np.asarray([-1.0, -1.0]))
    np.testing.assert_array_equal(upper, np.asarray([1.0, 1.0]))


def test_frozen_bank_ids_and_source_contract() -> None:
    bank = _loaded()
    assert bank["bank_id"] == BANK_ID
    assert tuple(bank["task_ids"]) == FROZEN_TASK_IDS
    assert len(bank["tasks"]) == 10
    assert [row["task_id"] for row in bank["tasks"]] == list(FROZEN_TASK_IDS)
    assert bank["goal_representation"]["kind"] == GOAL_REPRESENTATION_KIND
    assert bank["residual_policy"] == "cartesian_disk"
    assert bank["seed"] == 7
    for task in bank["tasks"]:
        assert "start_u_frac" not in task
        assert tuple(task["goal_point_ids"]) == CANDIDATE_IDS
        assert task["goal_radius"] == pytest.approx(bank["goal_radius"])
        assert len(task["goal_points"]) == len(CANDIDATE_IDS)


def test_start_goal_and_candidates_are_case_invariant() -> None:
    bank = _loaded()
    by_id = {row["task_id"]: row for row in bank["tasks"]}
    matrix = bank["preflight"]["matrix"]
    case_ids = [case.case_id for case in generate_span_cases()]
    assert list(matrix) == case_ids or set(matrix) == set(case_ids)
    assert len(matrix) == 17
    first_case = case_ids[0]
    for case_id in case_ids:
        assert tuple(matrix[case_id]) == FROZEN_TASK_IDS or set(matrix[case_id]) == set(
            FROZEN_TASK_IDS
        )
        for task_id in FROZEN_TASK_IDS:
            assert matrix[case_id][task_id] == matrix[first_case][task_id]
            task = by_id[task_id]
            assert task["start_q"] == by_id[task_id]["start_q"]
            assert task["start_x"] == by_id[task_id]["start_x"]
            assert task["goal_center"] == by_id[task_id]["goal_center"]
            assert task["goal_radius"] == by_id[task_id]["goal_radius"]
            assert task["goal_point_ids"] == by_id[task_id]["goal_point_ids"]


def test_starts_and_witnesses_are_strictly_inside_common_box() -> None:
    bank = _loaded()
    lower = np.asarray(bank["common_q_box"]["lower"], dtype=np.float64)
    upper = np.asarray(bank["common_q_box"]["upper"], dtype=np.float64)
    for task in bank["tasks"]:
        assert strictly_inside(
            np.asarray(task["start_q"], dtype=np.float64), lower, upper
        )
        assert strictly_inside(
            np.asarray(task["witness_q"], dtype=np.float64), lower, upper
        )


def test_preflight_passed_for_all_mounted_cases() -> None:
    bank = _loaded()
    preflight = bank["preflight"]
    assert preflight["all_passed"] is True
    assert preflight["n_cases"] == 17
    assert preflight["n_tasks"] == 10
    assert preflight["n_arms"] == 2
    case_ids = {case.case_id for case in generate_span_cases()}
    assert set(preflight["matrix"]) == case_ids
    for case_id, tasks in preflight["matrix"].items():
        assert set(tasks) == set(FROZEN_TASK_IDS)
        for task_id in FROZEN_TASK_IDS:
            assert tasks[task_id]["fourbar"] == "ok"
            assert tasks[task_id]["gearbox"] == "ok"


def test_builder_digest_matches_committed_json() -> None:
    committed = _loaded()
    built = build_common_physical_bank()
    assert built["sha256"] == committed["sha256"]
    assert bank_digest(built) == committed["sha256"]
    assert built["task_ids"] == committed["task_ids"]
    assert built["tasks"] == committed["tasks"]


def test_v3_6b_and_v4_2a_banks_are_not_the_primary_source() -> None:
    bank = _loaded()
    v3 = json.loads(V3_BANK_V2_REL.read_text(encoding="utf-8"))
    v3_tasks = json.loads(V3_BANK_V1_REL.read_text(encoding="utf-8"))
    v4_2a = json.loads(V4_2A_AUDIT_REL.read_text(encoding="utf-8"))
    assert v3["bank_id"] == "free_space_planar2r_v2"
    assert v3["bank_id"] != bank["bank_id"]
    assert v4_2a["source_bank"]["bank_id"] == "free_space_planar2r_v2"
    assert v4_2a["source_bank"]["bank_id"] != bank["bank_id"]
    assert v4_2a["source_bank"]["do_not_edit"] is True
    v3_near = next(row for row in v3_tasks["tasks"] if row["task_id"] == "near_0")
    ours = next(row for row in bank["tasks"] if row["task_id"] == "near_0")
    assert "start_u_frac" in v3_near
    assert "start_q" in ours
    assert list(v3_near["goal_center"]) != list(ours["goal_center"])
