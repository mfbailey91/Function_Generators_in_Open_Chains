"""V4.2D Stage C extraction, join, and optimality-gap metrics (ADR-032)."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.analysis.v4.optimality_reference import (
    FROZEN_STAGE_C_ROWS,
    OptimalityReferenceError,
    candidate_key,
)
from inequality_mechanisms.audits.v4_artifact_guard import canonical_v4_2c_retained_root
from inequality_mechanisms.benchmarks.classification import TASK_ALREADY_SATISFIED
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import (
    STATUS_COMPLETED,
    STATUS_UNSUPPORTED_OPTIONAL,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    CONTROL_PLANNER_IDS,
    PRIMARY_PLANNER_IDS,
    PROJECTION_PLANNER_IDS,
)

STAGE_C_ROW_COUNT = FROZEN_STAGE_C_ROWS
OPTIMIZER_IDS = frozenset({"ompl_rrt_star", "ompl_bit_star"})
FMT_ID = "ompl_fmt"
CHECKPOINT_SECONDS = (0.05, 0.10, 0.25, 0.50, 1.00)
RELATIVE_NULL_ZERO_REFERENCE = "zero_reference"
RELATIVE_NULL_NO_EXACT = "no_exact_solution"
PARTITION_ALREADY = "already_satisfied"
PARTITION_DIRECT = "direct_local_feasible"
PARTITION_OTHER = "other_typed_status"


def load_stage_c_records(stage_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load retained Stage C row JSON objects without mutating V4-238 views."""
    root = (
        Path(stage_dir)
        if stage_dir is not None
        else canonical_v4_2c_retained_root() / "stage_c"
    )
    rows_dir = root / "rows"
    if not rows_dir.is_dir():
        raise OptimalityReferenceError(f"missing Stage C rows directory {rows_dir}")
    rows: list[dict[str, Any]] = []
    for path in sorted(rows_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["_source_rel"] = f"rows/{path.name}"
            rows.append(payload)
    return rows


def _nested(mapping: Mapping[str, Any] | None, *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _ompl(result: Mapping[str, Any] | None) -> Mapping[str, Any]:
    metrics = result.get("planner_metrics") if isinstance(result, Mapping) else None
    if not isinstance(metrics, Mapping):
        return {}
    ompl = metrics.get("ompl")
    return ompl if isinstance(ompl, Mapping) else {}


def _selected_candidate_key(result: Mapping[str, Any] | None) -> str | None:
    if not isinstance(result, Mapping):
        return None
    selected = result.get("selected_goal_candidate")
    if not isinstance(selected, Mapping):
        return None
    provenance = selected.get("provenance")
    if not isinstance(provenance, Mapping):
        return None
    sample = provenance.get("goal_sample_id")
    family = provenance.get("ik_family")
    if sample is None or family is None:
        return None
    return candidate_key(str(sample), str(family))


def _checkpoints(ompl: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = ompl.get("checkpoints")
    if not isinstance(records, list):
        return []
    out: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, Mapping):
            continue
        out.append(
            {
                "checkpoint_s": item.get("checkpoint_s"),
                "best_cost": item.get("best_cost"),
                "ompl_exact_solution": bool(item.get("ompl_exact_solution")),
                "ompl_solved": item.get("ompl_solved"),
            }
        )
    return out


def extract_stage_c_view(record: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve task class, goal identity, exact flags, and checkpoints."""
    worker = record.get("worker")
    worker_map: Mapping[str, Any] = worker if isinstance(worker, Mapping) else {}
    result_raw = worker_map.get("result")
    result: Mapping[str, Any] | None = (
        result_raw if isinstance(result_raw, Mapping) else None
    )
    ompl = _ompl(result)
    status = str(worker_map.get("status") or record.get("status") or "unknown")
    task_class = None if result is None else result.get("task_class")
    if task_class == TASK_ALREADY_SATISFIED:
        partition = PARTITION_ALREADY
    elif task_class == "direct/local feasible":
        partition = PARTITION_DIRECT
    else:
        partition = PARTITION_OTHER
    exact = bool(ompl.get("ompl_exact_solution"))
    approximate = bool(ompl.get("ompl_approximate_solution"))
    first_time = ompl.get("first_exact_time_s")
    first_cost = ompl.get("first_exact_cost")
    checkpoints = _checkpoints(ompl)
    if first_time is None:
        for item in checkpoints:
            if item.get("ompl_exact_solution") and item.get("best_cost") is not None:
                first_time = item.get("checkpoint_s")
                first_cost = item.get("best_cost")
                break
    planner_id = str(record.get("planner_id") or "")
    if planner_id in PRIMARY_PLANNER_IDS:
        family_role = "primary"
    elif planner_id in PROJECTION_PLANNER_IDS:
        family_role = "projection_diagnostic"
    elif planner_id in CONTROL_PLANNER_IDS:
        family_role = "control"
    else:
        family_role = "other"
    return {
        "request_digest": record.get("request_digest"),
        "source_rel": record.get("_source_rel"),
        "case_id": record.get("case_id"),
        "task_id": record.get("task_id"),
        "mechanism": record.get("mechanism"),
        "planner_id": record.get("planner_id"),
        "repetition": record.get("repetition"),
        "seed": record.get("seed"),
        "status": status,
        "unavailable_reason": worker_map.get("unavailable_reason"),
        "task_class": task_class,
        "task_partition": partition,
        "already_satisfied": task_class == TASK_ALREADY_SATISFIED,
        "candidate_generator_id": _nested(
            result, "selected_goal_candidate", "provenance", "candidate_generator_id"
        )
        or ompl.get("goal_representation"),
        "goal_sample_id": _nested(
            result, "selected_goal_candidate", "provenance", "goal_sample_id"
        ),
        "ik_family": _nested(
            result, "selected_goal_candidate", "provenance", "ik_family"
        ),
        "selected_candidate_key": _selected_candidate_key(result),
        "direct_connector_available": ompl.get("direct_connector_available"),
        "discrete_goal_state_count": ompl.get("discrete_goal_state_count"),
        "ompl_exact_solution": exact,
        "ompl_approximate_solution": approximate,
        "objective_cost": None if result is None else result.get("objective_cost"),
        "first_exact_time_s": first_time,
        "first_exact_cost": first_cost,
        "checkpoints": checkpoints,
        "checkpoint_cost_units": ompl.get("checkpoint_best_cost_units")
        or ompl.get("objective_cost_units"),
        "family_role": family_role,
        "prm_sequential_goal_workaround": planner_id == "ompl_prm",
        "completed": status == STATUS_COMPLETED and result is not None,
        "unsupported_optional": status == STATUS_UNSUPPORTED_OPTIONAL,
    }


def extract_stage_c_views(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Extract the V4.2D compact view for every Stage C record."""
    return [extract_stage_c_view(record) for record in records]


def _relative_metrics(
    cost: float | None,
    j_star: float,
    *,
    exact: bool,
    tau_zero: float,
) -> dict[str, Any]:
    if j_star <= tau_zero:
        return {
            "epsilon_abs": None if cost is None else float(cost) - j_star,
            "epsilon_rel": None,
            "cost_ratio": None,
            "log_cost_ratio": None,
            "relative_null_reason": RELATIVE_NULL_ZERO_REFERENCE,
        }
    if cost is None or not exact:
        return {
            "epsilon_abs": None,
            "epsilon_rel": None,
            "cost_ratio": None,
            "log_cost_ratio": None,
            "relative_null_reason": RELATIVE_NULL_NO_EXACT,
        }
    epsilon_abs = float(cost) - j_star
    ratio = float(cost) / j_star
    return {
        "epsilon_abs": epsilon_abs,
        "epsilon_rel": epsilon_abs / j_star,
        "cost_ratio": ratio,
        "log_cost_ratio": math.log(ratio) if ratio > 0.0 else None,
        "relative_null_reason": None,
    }


def join_stage_c_to_reference(
    views: Sequence[Mapping[str, Any]],
    reference_rows: Sequence[Mapping[str, Any]],
    *,
    tau: float,
    tau_zero: float,
    eta: Sequence[float],
    checkpoints_s: Sequence[float] = CHECKPOINT_SECONDS,
) -> dict[str, Any]:
    """Join every Stage C view to J*_C,m and compute gap metrics."""
    refs = {
        (row["case_id"], row["task_id"], row["mechanism"]): row
        for row in reference_rows
    }
    final_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    task_class_rows: list[dict[str, Any]] = []
    n_orphans = 0
    for view in views:
        key = (view.get("case_id"), view.get("task_id"), view.get("mechanism"))
        ref = refs.get(key)
        if ref is None:
            n_orphans += 1
            continue
        j_star = float(ref["j_star_c"])
        exact = (
            bool(view.get("ompl_exact_solution"))
            and view.get("objective_cost") is not None
        )
        cost = view.get("objective_cost")
        metrics = _relative_metrics(
            None if cost is None else float(cost),
            j_star,
            exact=exact,
            tau_zero=tau_zero,
        )
        if metrics["epsilon_abs"] is not None and float(metrics["epsilon_abs"]) < -tau:
            raise OptimalityReferenceError(
                f"negative optimality gap beyond tau for {key}/{view.get('planner_id')}"
            )
        first_metrics = _relative_metrics(
            None
            if view.get("first_exact_cost") is None
            else float(view["first_exact_cost"]),
            j_star,
            exact=view.get("first_exact_cost") is not None,
            tau_zero=tau_zero,
        )
        time_to: dict[str, Any] = {}
        for threshold in eta:
            time_to[str(threshold)] = {
                "eta": float(threshold),
                "time_s": None,
                "right_censored": True,
            }
        planner_id = str(view.get("planner_id") or "")
        if planner_id in OPTIMIZER_IDS:
            for item in view.get("checkpoints") or []:
                if not item.get("ompl_exact_solution") or item.get("best_cost") is None:
                    continue
                rel = _relative_metrics(
                    float(item["best_cost"]),
                    j_star,
                    exact=True,
                    tau_zero=tau_zero,
                )
                eps = rel["epsilon_rel"]
                t_s = item.get("checkpoint_s")
                if eps is None or t_s is None:
                    continue
                for threshold in eta:
                    bucket = time_to[str(threshold)]
                    if float(eps) <= float(threshold) and bucket["time_s"] is None:
                        bucket["time_s"] = float(t_s)
                        bucket["right_censored"] = False
        joined = {
            **dict(view),
            "j_star_c": j_star,
            "j_star_b": ref.get("j_star_b"),
            "reference_candidate_key": ref.get("reference_candidate_key"),
            "already_satisfied_reference": bool(ref.get("already_satisfied")),
            "zero_reference": bool(ref.get("zero_reference")),
            "n_reference_candidates": ref.get("n_candidates"),
            "final_epsilon_abs": metrics["epsilon_abs"],
            "final_epsilon_rel": metrics["epsilon_rel"],
            "final_cost_ratio": metrics["cost_ratio"],
            "final_log_cost_ratio": metrics["log_cost_ratio"],
            "relative_null_reason": metrics["relative_null_reason"],
            "first_epsilon_abs": first_metrics["epsilon_abs"],
            "first_epsilon_rel": first_metrics["epsilon_rel"],
            "time_to_tolerance": time_to,
            "reference_goal_match": (
                view.get("selected_candidate_key") == ref.get("reference_candidate_key")
                if view.get("selected_candidate_key") is not None
                and ref.get("reference_candidate_key") is not None
                else None
            ),
        }
        final_rows.append(joined)
        task_class_rows.append(
            {
                "request_digest": view.get("request_digest"),
                "case_id": view.get("case_id"),
                "task_id": view.get("task_id"),
                "mechanism": view.get("mechanism"),
                "planner_id": view.get("planner_id"),
                "task_class": view.get("task_class"),
                "task_partition": view.get("task_partition"),
                "already_satisfied": view.get("already_satisfied"),
                "completed": view.get("completed"),
                "ompl_exact_solution": view.get("ompl_exact_solution"),
            }
        )
        if planner_id in OPTIMIZER_IDS:
            seen: dict[float, dict[str, Any]] = {}
            for item in view.get("checkpoints") or []:
                t_s = item.get("checkpoint_s")
                if t_s is None:
                    continue
                seen[float(t_s)] = dict(item)
            last_cost: float | None = None
            for t_s in checkpoints_s:
                item = seen.get(float(t_s), {})
                exact_cp = bool(item.get("ompl_exact_solution"))
                cost = item.get("best_cost")
                if (
                    last_cost is not None
                    and cost is not None
                    and float(cost) > last_cost + tau
                    and exact_cp
                ):
                    raise OptimalityReferenceError(
                        f"checkpoint costs increased at t={t_s} for {key}"
                    )
                if cost is not None:
                    last_cost = float(cost)
                rel = _relative_metrics(
                    None if cost is None else float(cost),
                    j_star,
                    exact=exact_cp,
                    tau_zero=tau_zero,
                )
                if rel["epsilon_abs"] is not None and float(rel["epsilon_abs"]) < -tau:
                    raise OptimalityReferenceError(
                        f"negative checkpoint gap beyond tau at t={t_s} for {key}"
                    )
                checkpoint_rows.append(
                    {
                        "request_digest": view.get("request_digest"),
                        "case_id": view.get("case_id"),
                        "task_id": view.get("task_id"),
                        "mechanism": view.get("mechanism"),
                        "planner_id": planner_id,
                        "repetition": view.get("repetition"),
                        "checkpoint_s": float(t_s),
                        "best_cost": None if cost is None else float(cost),
                        "ompl_exact_solution": exact_cp,
                        "j_star_c": j_star,
                        "already_satisfied": view.get("already_satisfied"),
                        "zero_reference": bool(ref.get("zero_reference")),
                        "epsilon_abs": rel["epsilon_abs"],
                        "epsilon_rel": rel["epsilon_rel"],
                        "cost_ratio": rel["cost_ratio"],
                        "log_cost_ratio": rel["log_cost_ratio"],
                        "relative_null_reason": rel["relative_null_reason"],
                    }
                )
    if n_orphans:
        raise OptimalityReferenceError(f"{n_orphans} Stage C rows have no J*_C join")
    if len(final_rows) != len(views):
        raise OptimalityReferenceError("Stage C join dropped rows")
    return {
        "final_rows": final_rows,
        "checkpoint_rows": checkpoint_rows,
        "task_class_rows": task_class_rows,
        "n_stage_c_rows": len(views),
        "n_orphans": 0,
    }


def within_tolerance_fraction(
    checkpoint_rows: Sequence[Mapping[str, Any]],
    *,
    planner_id: str,
    checkpoint_s: float,
    eta: float,
    mechanism: str | None = None,
) -> dict[str, Any]:
    """Compute P_eta(t) with unsolved nontrivial runs in the denominator."""
    eligible = [
        row
        for row in checkpoint_rows
        if row.get("planner_id") == planner_id
        and abs(float(row["checkpoint_s"]) - float(checkpoint_s)) < 1e-12
        and not row.get("already_satisfied")
        and not row.get("zero_reference")
        and (mechanism is None or row.get("mechanism") == mechanism)
    ]
    n = len(eligible)
    n_hit = sum(
        1
        for row in eligible
        if row.get("ompl_exact_solution")
        and row.get("epsilon_rel") is not None
        and float(row["epsilon_rel"]) <= float(eta)
    )
    return {
        "planner_id": planner_id,
        "checkpoint_s": float(checkpoint_s),
        "eta": float(eta),
        "mechanism": mechanism,
        "n_requested_nontrivial": n,
        "n_within_tolerance": n_hit,
        "p_eta": None if n == 0 else n_hit / n,
        "denominator": "all_nontrivial_requested_runs",
    }
