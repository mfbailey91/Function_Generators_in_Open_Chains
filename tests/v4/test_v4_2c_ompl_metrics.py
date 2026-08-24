"""V4-236: namespaced checkpoint metrics and unavailable internals."""

from __future__ import annotations

import json
from types import SimpleNamespace

from inequality_mechanisms.adapters.ompl.binding import (
    checkpoint_costs_nonincreasing,
    validate_checkpoints,
)
from inequality_mechanisms.adapters.ompl.metrics import (
    FAMILY_METRIC_KEYS,
    FMT_INDEPENDENT_REASON,
    KPIECE_CELL_REASON,
    assert_common_metric_keys,
    attach_checkpoint_summaries,
    cost_improvement_sequence,
    first_exact_checkpoint,
    last_exact_checkpoint_cost,
    metric_blob_json,
    namespace_family_metrics,
    progress_properties,
    unavailable,
)


def _records() -> list[dict]:
    return [
        {
            "checkpoint_s": 0.1,
            "ompl_exact_solution": False,
            "best_cost": None,
        },
        {
            "checkpoint_s": 0.25,
            "ompl_exact_solution": True,
            "best_cost": 2.0,
        },
        {
            "checkpoint_s": 0.5,
            "ompl_exact_solution": True,
            "best_cost": 1.5,
        },
        {
            "checkpoint_s": 1.0,
            "ompl_exact_solution": True,
            "best_cost": 1.5,
        },
    ]


def test_checkpoint_times_strictly_increase() -> None:
    times = validate_checkpoints([0.1, 0.25, 0.5, 1.0])
    assert times == (0.1, 0.25, 0.5, 1.0)
    records = _records()
    checkpoints = [float(r["checkpoint_s"]) for r in records]
    assert checkpoints == sorted(checkpoints)
    assert all(checkpoints[i] < checkpoints[i + 1] for i in range(len(checkpoints) - 1))


def test_exact_best_cost_is_nonincreasing() -> None:
    records = _records()
    assert checkpoint_costs_nonincreasing(records) is True
    worse = list(records)
    worse[-1] = dict(worse[-1], best_cost=1.7)
    assert checkpoint_costs_nonincreasing(worse) is False


def test_first_exact_and_cost_sequence() -> None:
    records = _records()
    first = first_exact_checkpoint(records)
    assert first["first_exact_time_s"] == 0.25
    assert first["first_exact_cost"] == 2.0
    sequence = cost_improvement_sequence(records)
    assert [row["best_cost"] for row in sequence] == [2.0, 1.5, 1.5]
    assert last_exact_checkpoint_cost(records) == 1.5
    empty = first_exact_checkpoint([])
    assert empty["first_exact_time_s"] is None
    assert empty["unavailable_reason"] == "no_exact_checkpoint"


def test_fmt_continuation_flag_and_no_checkpoint_ladder() -> None:
    extras = namespace_family_metrics(
        {
            "ompl_planner": "FMT",
            "nn_distance": "euclidean_u",
            "continuation": "independent_sample_count",
            "checkpoints_s": None,
            "num_samples": 400,
            "family_metrics": {"unavailable_reason": FMT_INDEPENDENT_REASON},
        }
    )
    family = extras["family_metrics"]
    assert family["continuation"] == "independent_sample_count"
    assert family["checkpoints_s"] is None
    assert family["unavailable_reason"] == FMT_INDEPENDENT_REASON
    assert "num_samples" not in extras
    assert "continuation" not in extras
    assert_common_metric_keys(extras)


def test_family_keys_absent_from_common_extras() -> None:
    extras = namespace_family_metrics(
        {
            "ompl_planner": "RRTstar",
            "nn_distance": "euclidean_u",
            "planner_geometry": {"planner_role": "primary_optimizing"},
            "range_fraction": 0.2,
            "rewire_factor": 1.1,
            "checkpoints_s": [0.25, 0.5],
        }
    )
    for key in FAMILY_METRIC_KEYS:
        assert key not in extras
    assert extras["family_metrics"]["range_fraction"] == 0.2
    assert extras["ompl_planner"] == "RRTstar"
    assert extras["nn_distance"] == "euclidean_u"
    assert extras["planner_geometry"]["planner_role"] == "primary_optimizing"
    assert_common_metric_keys(extras)


def test_last_exact_checkpoint_matches_session_owned_final_exact_cost() -> None:
    records = _records()
    session = SimpleNamespace(
        checkpoint_records=records,
        ompl_metrics={"checkpoint_cost_nonincreasing": True},
        extras={"ompl_planner": "RRTstar", "family_metrics": {}},
    )

    class _Planner:
        pass

    attach_checkpoint_summaries(session, _Planner())
    last = last_exact_checkpoint_cost(records)
    assert last == 1.5
    assert session.ompl_metrics["final_exact_cost"] == last
    assert session.ompl_metrics["first_exact_cost"] == 2.0
    assert session.extras["first_exact_cost"] == 2.0
    # Session-owned comparison uses the OMPL path-length best_cost chain.
    assert (
        session.ompl_metrics["checkpoint_best_cost_units"]
        == "ompl_solution_path_length"
    )


def test_metric_json_is_deterministic() -> None:
    blob = {
        "b": 2,
        "a": {"z": 1, "y": [3, 1]},
        "progress_properties": None,
    }
    encoded = metric_blob_json(blob)
    assert encoded == json.dumps(blob, sort_keys=True, separators=(",", ":"))
    assert encoded == metric_blob_json(blob)


def test_unavailable_reason_when_progress_and_cell_getters_missing() -> None:
    class _Bare:
        pass

    progress = progress_properties(_Bare())
    assert progress["progress_properties"] is None
    assert progress["unavailable_reason"]
    occupancy = unavailable("kpiece_cell_occupancy", KPIECE_CELL_REASON)
    assert occupancy["kpiece_cell_occupancy"] is None
    assert occupancy["unavailable_reason"] == KPIECE_CELL_REASON
