"""V4-245 index-matched pairing and final-gap decomposition."""

from __future__ import annotations

import pytest

from inequality_mechanisms.analysis.v4.optimality_pairing import (
    PAIRING_LABEL,
    decompose_final_gaps,
    pair_mechanism_contrasts,
)
from inequality_mechanisms.analysis.v4.optimality_reference import (
    OptimalityReferenceError,
)


def test_pairing_is_labeled_index_matched_not_crn() -> None:
    refs = [
        {
            "case_id": "c",
            "task_id": "far_0",
            "mechanism": "fourbar",
            "j_star_c": 1.0,
        },
        {
            "case_id": "c",
            "task_id": "far_0",
            "mechanism": "gearbox",
            "j_star_c": 1.5,
        },
    ]
    finals = [
        {
            "case_id": "c",
            "task_id": "far_0",
            "mechanism": "fourbar",
            "planner_id": "ompl_bit_star",
            "repetition": 0,
            "final_epsilon_rel": 0.1,
            "already_satisfied": False,
            "request_digest": "a" * 64,
        },
        {
            "case_id": "c",
            "task_id": "far_0",
            "mechanism": "gearbox",
            "planner_id": "ompl_bit_star",
            "repetition": 0,
            "final_epsilon_rel": 0.4,
            "already_satisfied": False,
            "request_digest": "b" * 64,
        },
    ]
    paired = pair_mechanism_contrasts(finals, refs, tau=1e-8)
    assert len(paired) == 1
    row = paired[0]
    assert row["pairing_label"] == PAIRING_LABEL
    assert row["delta_j_star_c_fourbar_minus_gearbox"] == pytest.approx(-0.5)
    assert row["delta_epsilon_rel_fourbar_minus_gearbox"] == pytest.approx(-0.3)


def test_unpaired_mechanism_fails_closed() -> None:
    refs = [
        {"case_id": "c", "task_id": "t", "mechanism": "fourbar", "j_star_c": 1.0},
        {"case_id": "c", "task_id": "t", "mechanism": "gearbox", "j_star_c": 1.0},
    ]
    finals = [
        {
            "case_id": "c",
            "task_id": "t",
            "mechanism": "fourbar",
            "planner_id": "ompl_fmt",
            "repetition": 0,
            "final_epsilon_rel": 0.1,
            "already_satisfied": False,
        }
    ]
    with pytest.raises(OptimalityReferenceError, match="unpaired"):
        pair_mechanism_contrasts(finals, refs, tau=1e-8)


def test_decomposition_identity_and_selected_candidate_map() -> None:
    finals = [
        {
            "request_digest": "a" * 64,
            "case_id": "c",
            "task_id": "far_0",
            "mechanism": "fourbar",
            "planner_id": "ompl_rrt_star",
            "repetition": 0,
            "selected_candidate_key": "disk_center::elbow_down",
            "reference_candidate_key": "disk_center::elbow_up",
            "reference_goal_match": False,
            "j_star_c": 1.0,
            "objective_cost": 1.4,
            "ompl_exact_solution": True,
            "already_satisfied": False,
        }
    ]
    candidates = [
        {
            "case_id": "c",
            "task_id": "far_0",
            "mechanism": "fourbar",
            "candidate_key": "disk_center::elbow_up",
            "direct_cost": 1.0,
        },
        {
            "case_id": "c",
            "task_id": "far_0",
            "mechanism": "fourbar",
            "candidate_key": "disk_center::elbow_down",
            "direct_cost": 1.1,
        },
    ]
    rows = decompose_final_gaps(finals, candidates, tau=1e-8)
    assert len(rows) == 1
    row = rows[0]
    assert row["goal_selection_regret"] == pytest.approx(0.1)
    assert row["path_inefficiency"] == pytest.approx(0.3)
    assert row["total_gap"] == pytest.approx(0.4)
    assert row["decomposition_status"] == "ok"
    assert "not retain the selected goal" in row["checkpoint_goal_identity"]


def test_unknown_selected_candidate_fails_closed() -> None:
    finals = [
        {
            "case_id": "c",
            "task_id": "t",
            "mechanism": "fourbar",
            "planner_id": "ompl_fmt",
            "repetition": 0,
            "selected_candidate_key": "disk_center::missing",
            "reference_candidate_key": "disk_center::elbow_up",
            "j_star_c": 1.0,
            "objective_cost": 1.2,
            "ompl_exact_solution": True,
            "already_satisfied": False,
        }
    ]
    with pytest.raises(OptimalityReferenceError, match="not a reconstructed"):
        decompose_final_gaps(finals, [], tau=1e-8)
