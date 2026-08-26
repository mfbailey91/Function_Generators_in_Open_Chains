"""V4-243 / V4-244 Stage C join and optimality metrics."""

from __future__ import annotations

import pytest

from inequality_mechanisms.analysis.v4.optimality_metrics import (
    extract_stage_c_view,
    join_stage_c_to_reference,
    within_tolerance_fraction,
)
from inequality_mechanisms.analysis.v4.optimality_reference import (
    OptimalityReferenceError,
)
from inequality_mechanisms.benchmarks.classification import TASK_ALREADY_SATISFIED
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import STATUS_COMPLETED


def _record(
    *,
    digest: str,
    case_id: str = "span_j1_145_j2_145",
    task_id: str = "far_0",
    mechanism: str = "fourbar",
    planner_id: str = "ompl_rrt_star",
    repetition: int = 0,
    task_class: str = "direct/local feasible",
    cost: float | None = 1.2,
    exact: bool = True,
    first_cost: float | None = 1.5,
    checkpoints: list[dict] | None = None,
    selected: dict | None = None,
) -> dict:
    cps = checkpoints or [
        {
            "checkpoint_s": t,
            "best_cost": cost,
            "ompl_exact_solution": exact,
        }
        for t in (0.05, 0.10, 0.25, 0.50, 1.00)
    ]
    return {
        "request_digest": digest,
        "case_id": case_id,
        "task_id": task_id,
        "mechanism": mechanism,
        "planner_id": planner_id,
        "repetition": repetition,
        "seed": 7,
        "worker": {
            "status": STATUS_COMPLETED,
            "result": {
                "task_class": task_class,
                "objective_cost": cost,
                "selected_goal_candidate": selected
                or {
                    "provenance": {
                        "candidate_generator_id": "cartesian_disk_center_ik",
                        "goal_sample_id": "disk_center",
                        "ik_family": "elbow_up",
                    }
                },
                "planner_metrics": {
                    "ompl": {
                        "ompl_exact_solution": exact,
                        "direct_connector_available": True,
                        "discrete_goal_state_count": 2,
                        "first_exact_time_s": None if first_cost is None else 0.05,
                        "first_exact_cost": first_cost,
                        "checkpoints": cps,
                    }
                },
            },
        },
    }


def test_extract_preserves_task_class_and_goal_identity() -> None:
    view = extract_stage_c_view(_record(digest="a" * 64))
    assert view["task_class"] == "direct/local feasible"
    assert view["task_partition"] == "direct_local_feasible"
    assert view["selected_candidate_key"] == "disk_center::elbow_up"
    assert view["direct_connector_available"] is True
    assert view["ompl_exact_solution"] is True
    assert len(view["checkpoints"]) == 5


def test_already_satisfied_rows_remain_identifiable() -> None:
    view = extract_stage_c_view(
        _record(
            digest="b" * 64,
            task_class=TASK_ALREADY_SATISFIED,
            cost=0.0,
            first_cost=0.0,
        )
    )
    assert view["already_satisfied"] is True
    assert view["task_partition"] == "already_satisfied"


def test_join_computes_nonnegative_gaps_and_null_relative_for_zero() -> None:
    refs = [
        {
            "case_id": "span_j1_145_j2_145",
            "task_id": "far_0",
            "mechanism": "fourbar",
            "j_star_c": 1.0,
            "already_satisfied": False,
            "zero_reference": False,
            "n_candidates": 2,
            "reference_candidate_key": "disk_center::elbow_up",
        },
        {
            "case_id": "span_j1_145_j2_145",
            "task_id": "near_0",
            "mechanism": "fourbar",
            "j_star_c": 0.0,
            "already_satisfied": True,
            "zero_reference": True,
            "n_candidates": 2,
            "reference_candidate_key": None,
        },
    ]
    views = [
        extract_stage_c_view(_record(digest="a" * 64, cost=1.2)),
        extract_stage_c_view(
            _record(
                digest="b" * 64,
                task_id="near_0",
                task_class=TASK_ALREADY_SATISFIED,
                cost=0.0,
                first_cost=0.0,
            )
        ),
    ]
    joined = join_stage_c_to_reference(
        views,
        refs,
        tau=1e-8,
        tau_zero=1e-9,
        eta=(0.01, 0.05, 0.10),
    )
    assert joined["n_orphans"] == 0
    far = joined["final_rows"][0]
    assert far["final_epsilon_abs"] == pytest.approx(0.2)
    assert far["final_epsilon_rel"] == pytest.approx(0.2)
    near = joined["final_rows"][1]
    assert near["final_epsilon_rel"] is None
    assert near["relative_null_reason"] == "zero_reference"
    assert near["already_satisfied"] is True


def test_negative_gap_beyond_tau_fails_closed() -> None:
    refs = [
        {
            "case_id": "span_j1_145_j2_145",
            "task_id": "far_0",
            "mechanism": "fourbar",
            "j_star_c": 2.0,
            "already_satisfied": False,
            "zero_reference": False,
            "n_candidates": 2,
            "reference_candidate_key": "disk_center::elbow_up",
        }
    ]
    views = [extract_stage_c_view(_record(digest="a" * 64, cost=1.0))]
    with pytest.raises(OptimalityReferenceError, match="negative optimality gap"):
        join_stage_c_to_reference(views, refs, tau=1e-8, tau_zero=1e-9, eta=(0.05,))


def test_unsolved_rows_count_in_within_tolerance_denominator() -> None:
    refs = [
        {
            "case_id": "span_j1_145_j2_145",
            "task_id": "far_0",
            "mechanism": "fourbar",
            "j_star_c": 1.0,
            "already_satisfied": False,
            "zero_reference": False,
            "n_candidates": 2,
            "reference_candidate_key": "disk_center::elbow_up",
        }
    ]
    exact = extract_stage_c_view(_record(digest="a" * 64, cost=1.02, repetition=0))
    unsolved = extract_stage_c_view(
        _record(
            digest="c" * 64,
            cost=None,
            exact=False,
            first_cost=None,
            checkpoints=[
                {
                    "checkpoint_s": t,
                    "best_cost": None,
                    "ompl_exact_solution": False,
                }
                for t in (0.05, 0.10, 0.25, 0.50, 1.00)
            ],
            repetition=1,
        )
    )
    joined = join_stage_c_to_reference(
        [exact, unsolved],
        refs,
        tau=1e-8,
        tau_zero=1e-9,
        eta=(0.05,),
    )
    payload = within_tolerance_fraction(
        joined["checkpoint_rows"],
        planner_id="ompl_rrt_star",
        checkpoint_s=1.0,
        eta=0.05,
        mechanism="fourbar",
    )
    assert payload["n_requested_nontrivial"] == 2
    assert payload["n_within_tolerance"] == 1
    assert payload["p_eta"] == pytest.approx(0.5)
