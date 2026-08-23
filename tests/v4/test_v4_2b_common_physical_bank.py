"""V4.2B Phase 7: common-physical task bank freeze (V4-226)."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT
from inequality_mechanisms.experiments.span_cases import generate_span_cases
from inequality_mechanisms.experiments.v4 import (
    span_controlled_corrective_audit_config as audit_cfg,
)
from inequality_mechanisms.experiments.v4.span_common_physical_bank import (
    BANK_ID,
    DEFAULT_BANK_REL,
    FK_ATOL,
    FROZEN_TASK_IDS,
    GOAL_REPRESENTATION_KIND,
    SCHEMA_VERSION,
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
_MAX_PAYLOAD_DIFFS = 20


def _loaded() -> dict:
    return load_common_physical_bank(CANONICAL_REPO_ROOT / DEFAULT_BANK_REL)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _payload_differences(
    built: Any,
    committed: Any,
    *,
    path: str = "$",
    atol: float,
) -> list[str]:
    """Return JSON-path diffs; numbers may differ by at most ``atol``."""
    differences: list[str] = []
    if isinstance(built, Mapping) and isinstance(committed, Mapping):
        built_keys = set(built)
        committed_keys = set(committed)
        for key in sorted(built_keys - committed_keys, key=str):
            differences.append(f"{path}: key only in built payload: {key!r}")
        for key in sorted(committed_keys - built_keys, key=str):
            differences.append(f"{path}: key only in committed payload: {key!r}")
        for key in sorted(built_keys & committed_keys, key=str):
            differences.extend(
                _payload_differences(
                    built[key], committed[key], path=f"{path}.{key}", atol=atol
                )
            )
            if len(differences) >= _MAX_PAYLOAD_DIFFS:
                break
        return differences

    sequence_types = (list, tuple)
    if isinstance(built, sequence_types) and isinstance(committed, sequence_types):
        if len(built) != len(committed):
            differences.append(
                f"{path}: length differs: built={len(built)}, "
                f"committed={len(committed)}"
            )
        for index, (left, right) in enumerate(zip(built, committed, strict=False)):
            differences.extend(
                _payload_differences(left, right, path=f"{path}[{index}]", atol=atol)
            )
            if len(differences) >= _MAX_PAYLOAD_DIFFS:
                break
        return differences

    if _is_number(built) and _is_number(committed):
        if not math.isclose(
            float(built), float(committed), rel_tol=0.0, abs_tol=float(atol)
        ):
            differences.append(
                f"{path}: built={built!r}, committed={committed!r}, "
                f"abs={abs(float(built) - float(committed)):.17g}"
            )
        return differences

    if built != committed:
        differences.append(
            f"{path}: built={built!r} ({type(built).__name__}), "
            f"committed={committed!r} ({type(committed).__name__})"
        )
    return differences


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
    assert committed["sha256"] == audit_cfg.FROZEN_BANK_DIGEST
    assert bank_digest(committed) == audit_cfg.FROZEN_BANK_DIGEST

    built = build_common_physical_bank()
    assert built["bank_id"] == committed["bank_id"] == BANK_ID
    assert built["schema_version"] == committed["schema_version"] == SCHEMA_VERSION
    assert built["task_ids"] == committed["task_ids"]
    assert built["preflight"] == committed["preflight"]
    for built_task, committed_task in zip(
        built["tasks"], committed["tasks"], strict=True
    ):
        assert built_task["task_id"] == committed_task["task_id"]
        assert built_task["goal_point_ids"] == committed_task["goal_point_ids"]

    # Rebuilt Cartesian FK may differ by platform libm ULPs; the committed
    # JSON remains the digest lock. Reconstruction must match within FK_ATOL.
    built_body = {key: value for key, value in built.items() if key != "sha256"}
    committed_body = {key: value for key, value in committed.items() if key != "sha256"}
    differences = _payload_differences(built_body, committed_body, atol=FK_ATOL)
    assert differences == [], "\n".join(differences)


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
