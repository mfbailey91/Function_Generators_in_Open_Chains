"""Namespaced OMPL PlannerData and checkpoint summaries (V3-504 / V4-236)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

FAMILY_METRIC_KEYS: Final[frozenset[str]] = frozenset(
    {
        "range_fraction",
        "range_u",
        "goal_bias",
        "rewire_factor",
        "k_nearest",
        "delay_cc",
        "tree_pruning",
        "informed_sampling",
        "num_samples",
        "effective_sample_count",
        "nearest_k",
        "radius_multiplier",
        "heuristics",
        "extended_fmt",
        "cache_cc",
        "continuation",
        "samples_per_batch",
        "use_k_nearest",
        "pruning",
        "strict_queue_ordering",
        "checkpoints_s",
        "cells_per_axis",
        "projection",
        "border_fraction",
        "min_valid_path_fraction",
        "kpiece_cell_occupancy",
        "max_nearest_neighbors",
        "binding_methods",
    }
)
COMMON_EXTRAS_KEYS: Final[frozenset[str]] = frozenset(
    {
        "nn_distance",
        "planner_geometry",
        "ompl_planner",
        "family_metrics",
        "seed_protocol",
        "ompl_version",
        "ompl_seed_requested",
        "ompl_seed_scope",
        "reproducibility_contract",
        "ompl_seed_applied",
        "first_exact_time_s",
        "first_exact_cost",
        "cost_improvements",
        "progress_properties",
        "checkpoint_cost_nonincreasing",
    }
)
CHECKPOINT_RECORD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "checkpoint_s",
        "remaining_s",
        "ompl_status",
        "ompl_solved",
        "ompl_exact_solution",
        "ompl_solution_difference",
        "best_cost",
        "planner_data",
    }
)
FMT_INDEPENDENT_REASON: Final = "fmt_is_independent_sample_count_run"
KPIECE_CELL_REASON: Final = "kpiece_cell_stats_not_exposed_by_binding"
PROGRESS_UNAVAILABLE_REASON: Final = (
    "planner_progress_properties_not_exposed_by_binding"
)


def planner_data_metrics(si: Any, planner: Any) -> dict[str, Any]:
    """Return a compact ``planner_metrics['ompl']``-ready PlannerData summary."""
    try:
        from inequality_mechanisms.adapters.ompl._availability import require_ompl

        ob, _og = require_ompl()
        data = ob.PlannerData(si)
        planner.getPlannerData(data)
        return {
            "num_vertices": int(data.numVertices()),
            "num_edges": int(data.numEdges()),
            "num_start_vertices": int(data.numStartVertices()),
            "num_goal_vertices": int(data.numGoalVertices()),
        }
    except Exception as exc:  # pragma: no cover - binding differences
        return {
            "planner_data_error": str(exc),
            "num_vertices": None,
            "num_edges": None,
        }


def unavailable(field: str, reason: str) -> dict[str, Any]:
    """Return a null field plus the reason it cannot be populated."""
    return {field: None, "unavailable_reason": str(reason)}


def first_exact_checkpoint(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return time and cost of the first exact checkpoint, or unavailable."""
    for record in records:
        if not record.get("ompl_exact_solution"):
            continue
        cost = record.get("best_cost")
        if cost is None:
            continue
        return {
            "first_exact_time_s": float(record["checkpoint_s"]),
            "first_exact_cost": float(cost),
        }
    payload = unavailable("first_exact_time_s", "no_exact_checkpoint")
    payload["first_exact_cost"] = None
    return payload


def cost_improvement_sequence(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, float]]:
    """Return the exact-solution best-cost sequence in checkpoint order."""
    sequence: list[dict[str, float]] = []
    for record in records:
        if not record.get("ompl_exact_solution"):
            continue
        cost = record.get("best_cost")
        if cost is None:
            continue
        sequence.append(
            {
                "checkpoint_s": float(record["checkpoint_s"]),
                "best_cost": float(cost),
            }
        )
    return sequence


def progress_properties(planner: Any) -> dict[str, Any]:
    """Return ``getPlannerProgressProperties()`` when the binding exposes it."""
    getter = getattr(planner, "getPlannerProgressProperties", None)
    if getter is None:
        return unavailable("progress_properties", PROGRESS_UNAVAILABLE_REASON)
    try:
        raw = getter()
    except Exception as exc:  # pragma: no cover - binding differences
        return unavailable(
            "progress_properties",
            f"planner_progress_properties_error:{exc}",
        )
    if raw is None:
        return unavailable("progress_properties", PROGRESS_UNAVAILABLE_REASON)
    try:
        return {"progress_properties": dict(raw)}
    except Exception:
        return {"progress_properties": raw}


def resolved_getter_values(
    binding_methods: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Collect already-recorded setter/getter values from a binding log."""
    resolved: dict[str, Any] = {}
    if not binding_methods:
        return resolved
    for entry in binding_methods:
        if not entry.get("applied"):
            continue
        method = entry.get("method")
        if not method:
            continue
        resolved[str(method)] = entry.get("recorded", entry.get("requested"))
    return resolved


def namespace_family_metrics(extras: dict[str, Any]) -> dict[str, Any]:
    """Move family knobs under ``extras['family_metrics']`` in place."""
    family = dict(extras.get("family_metrics") or {})
    for key in list(extras):
        if key in FAMILY_METRIC_KEYS:
            family[key] = extras.pop(key)
    extras["family_metrics"] = family
    return extras


def family_metric_leaks(extras: Mapping[str, Any]) -> tuple[str, ...]:
    """Return family keys that leaked into the common extras namespace."""
    return tuple(sorted(key for key in extras if key in FAMILY_METRIC_KEYS))


def assert_common_metric_keys(extras: Mapping[str, Any]) -> None:
    """Fail if family-specific knobs sit on the common extras dict."""
    leaks = family_metric_leaks(extras)
    if leaks:
        raise AssertionError(
            "family metrics leaked into the common extras namespace: "
            + ", ".join(leaks)
        )


def last_exact_checkpoint_cost(records: Sequence[Mapping[str, Any]]) -> float | None:
    """Return the last exact checkpoint ``best_cost``, if any."""
    last: float | None = None
    for record in records:
        if record.get("ompl_exact_solution") and record.get("best_cost") is not None:
            last = float(record["best_cost"])
    return last


def metric_blob_json(payload: Mapping[str, Any]) -> str:
    """Serialize a metric mapping with sorted keys for digest stability."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def attach_checkpoint_summaries(session: Any, planner: Any) -> None:
    """Write first-exact, cost sequence, and progress getters onto the session."""
    records = list(getattr(session, "checkpoint_records", []) or [])
    first = first_exact_checkpoint(records)
    session.ompl_metrics["first_exact_time_s"] = first.get("first_exact_time_s")
    session.ompl_metrics["first_exact_cost"] = first.get("first_exact_cost")
    if first.get("unavailable_reason") and first.get("first_exact_time_s") is None:
        session.ompl_metrics["first_exact_unavailable_reason"] = first[
            "unavailable_reason"
        ]
    session.ompl_metrics["cost_improvements"] = cost_improvement_sequence(records)
    session.ompl_metrics["final_exact_cost"] = last_exact_checkpoint_cost(records)
    session.ompl_metrics["checkpoint_best_cost_units"] = "ompl_solution_path_length"
    progress = progress_properties(planner)
    session.ompl_metrics["progress_properties"] = progress.get("progress_properties")
    if progress.get("unavailable_reason"):
        session.ompl_metrics["progress_properties_unavailable_reason"] = progress[
            "unavailable_reason"
        ]
    extras = session.extras
    extras["first_exact_time_s"] = session.ompl_metrics["first_exact_time_s"]
    extras["first_exact_cost"] = session.ompl_metrics["first_exact_cost"]
    extras["cost_improvements"] = session.ompl_metrics["cost_improvements"]
    extras["progress_properties"] = session.ompl_metrics["progress_properties"]
    family = extras.get("family_metrics")
    methods = None
    if isinstance(family, dict):
        methods = family.get("binding_methods")
        if methods:
            family["resolved_getters"] = resolved_getter_values(methods)
    elif extras.get("binding_methods"):
        methods = extras.pop("binding_methods")
        extras["family_metrics"] = {
            "binding_methods": methods,
            "resolved_getters": resolved_getter_values(methods),
        }
