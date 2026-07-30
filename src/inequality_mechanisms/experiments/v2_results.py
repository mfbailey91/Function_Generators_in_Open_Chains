"""Version 2 result schema, version 2 (Sprint V2.4, V2-405).

Records every field ``docs/software/PROJECT_PLAN.md`` requires "at minimum"
for a Version 2 trial row, plus a few explicit additions this sprint needs
to make the null-control hard gate checkable directly from stored rows
(``algorithm``, matched node ids, and the full expansion order). Small
smoke fixtures store everything inline in ``trials.jsonl``; nothing here
prevents a future sprint from moving heavy per-trial arrays to sidecar
files once run sizes grow.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any

RESULT_SCHEMA_VERSION_V2 = 2

#: Column order used for ``summary.csv``. Complex (list/dict) values are
#: JSON-encoded into the cell rather than dropped, so the CSV remains a
#: complete, if less convenient, view of every trial row.
V2_RESULT_FIELDS: tuple[str, ...] = (
    "architecture_version",
    "result_schema_version",
    "run_id",
    "trial_index",
    "mechanism_id",
    "branch_id",
    "branch_certificate",
    "sampling_domain",
    "transition_parameterization",
    "graph_shape",
    "node_count",
    "valid_node_count",
    "valid_edge_count",
    "algorithm",
    "cost_type",
    "heuristic_type",
    "alpha",
    "s_q",
    "s_u",
    "cost_d_q",
    "cost_d_u",
    "cost_norm_q",
    "cost_norm_u",
    "requested_start_q",
    "requested_goal_q",
    "realized_start_q",
    "realized_goal_q",
    "start_residual_q",
    "goal_residual_q",
    "start_residual_norm",
    "goal_residual_norm",
    "start_u",
    "goal_u",
    "start_node_id",
    "goal_node_id",
    "found",
    "optimal_cost",
    "n_expanded",
    "n_generated",
    "n_stale",
    "n_path_edges",
    "path_length_u",
    "path_length_q",
    "path_length_x",
    "expansion_fraction",
    "pair_id",
    "task_set_id",
    "q_spacing_summary",
    "u_spacing_summary",
    "seed",
    "code_revision",
    "path_node_ids",
    "expanded_node_ids",
)


@dataclass(frozen=True, slots=True)
class V2ResultRow:
    """One Version 2 trial row: one (mechanism, task, algorithm) outcome."""

    architecture_version: int
    result_schema_version: int
    run_id: str
    trial_index: int
    mechanism_id: str
    branch_id: str
    branch_certificate: dict[str, Any]
    sampling_domain: str
    transition_parameterization: str
    graph_shape: tuple[int, ...]
    node_count: int
    valid_node_count: int
    valid_edge_count: int
    algorithm: str
    cost_type: str
    heuristic_type: str
    alpha: float | None
    s_q: float | None
    s_u: float | None
    cost_d_q: float | None
    cost_d_u: float | None
    cost_norm_q: float | None
    cost_norm_u: float | None
    requested_start_q: list[float]
    requested_goal_q: list[float]
    realized_start_q: list[float] | None
    realized_goal_q: list[float] | None
    start_residual_q: list[float] | None
    goal_residual_q: list[float] | None
    start_residual_norm: float | None
    goal_residual_norm: float | None
    start_u: list[float] | None
    goal_u: list[float] | None
    start_node_id: int | None
    goal_node_id: int | None
    found: bool
    optimal_cost: float
    n_expanded: int
    n_generated: int
    n_stale: int
    n_path_edges: int
    path_length_u: float | None
    path_length_q: float | None
    path_length_x: float | None
    expansion_fraction: float | None
    pair_id: str | None
    task_set_id: str | None
    q_spacing_summary: list[dict[str, Any]]
    u_spacing_summary: list[dict[str, Any]]
    seed: int
    code_revision: str | None
    path_node_ids: tuple[int, ...] = field(default_factory=tuple)
    expanded_node_ids: tuple[int, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe plain dictionary in ``V2_RESULT_FIELDS`` order."""
        raw: dict[str, Any] = {
            "architecture_version": self.architecture_version,
            "result_schema_version": self.result_schema_version,
            "run_id": self.run_id,
            "trial_index": self.trial_index,
            "mechanism_id": self.mechanism_id,
            "branch_id": self.branch_id,
            "branch_certificate": self.branch_certificate,
            "sampling_domain": self.sampling_domain,
            "transition_parameterization": self.transition_parameterization,
            "graph_shape": list(self.graph_shape),
            "node_count": self.node_count,
            "valid_node_count": self.valid_node_count,
            "valid_edge_count": self.valid_edge_count,
            "algorithm": self.algorithm,
            "cost_type": self.cost_type,
            "heuristic_type": self.heuristic_type,
            "alpha": self.alpha,
            "s_q": self.s_q,
            "s_u": self.s_u,
            "cost_d_q": self.cost_d_q,
            "cost_d_u": self.cost_d_u,
            "cost_norm_q": self.cost_norm_q,
            "cost_norm_u": self.cost_norm_u,
            "requested_start_q": list(self.requested_start_q),
            "requested_goal_q": list(self.requested_goal_q),
            "realized_start_q": self.realized_start_q,
            "realized_goal_q": self.realized_goal_q,
            "start_residual_q": self.start_residual_q,
            "goal_residual_q": self.goal_residual_q,
            "start_residual_norm": self.start_residual_norm,
            "goal_residual_norm": self.goal_residual_norm,
            "start_u": self.start_u,
            "goal_u": self.goal_u,
            "start_node_id": self.start_node_id,
            "goal_node_id": self.goal_node_id,
            "found": self.found,
            "optimal_cost": self.optimal_cost,
            "n_expanded": self.n_expanded,
            "n_generated": self.n_generated,
            "n_stale": self.n_stale,
            "n_path_edges": self.n_path_edges,
            "path_length_u": self.path_length_u,
            "path_length_q": self.path_length_q,
            "path_length_x": self.path_length_x,
            "expansion_fraction": self.expansion_fraction,
            "pair_id": self.pair_id,
            "task_set_id": self.task_set_id,
            "q_spacing_summary": self.q_spacing_summary,
            "u_spacing_summary": self.u_spacing_summary,
            "seed": self.seed,
            "code_revision": self.code_revision,
            "path_node_ids": list(self.path_node_ids),
            "expanded_node_ids": list(self.expanded_node_ids),
        }
        return raw


@dataclass(frozen=True, slots=True)
class V2FailureRow:
    """One rejected-task record (V2-402/403): never silently resampled."""

    run_id: str
    trial_index: int
    mechanism_id: str
    requested_start_q: list[float]
    requested_goal_q: list[float]
    output_tolerance: float
    rejection_reason: str
    start_residual_norm: float | None
    goal_residual_norm: float | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "run_id": self.run_id,
            "trial_index": self.trial_index,
            "mechanism_id": self.mechanism_id,
            "requested_start_q": list(self.requested_start_q),
            "requested_goal_q": list(self.requested_goal_q),
            "output_tolerance": self.output_tolerance,
            "rejection_reason": self.rejection_reason,
            "start_residual_norm": self.start_residual_norm,
            "goal_residual_norm": self.goal_residual_norm,
        }


def rows_to_jsonl(rows: list[dict[str, Any]]) -> str:
    """Serialize a list of row dictionaries as newline-delimited JSON."""
    lines = [json.dumps(row, sort_keys=True) for row in rows]
    return "\n".join(lines) + ("\n" if lines else "")


def rows_to_csv(
    rows: list[dict[str, Any]], *, fields: tuple[str, ...] | None = None
) -> str:
    """Serialize a list of row dictionaries as CSV text.

    List/dict cell values are JSON-encoded so the summary table stays a
    complete, machine-readable view even for structured fields such as
    ``branch_certificate`` or ``q_spacing_summary``.
    """
    if not rows:
        return ""
    fieldnames = list(fields) if fields is not None else list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        flat: dict[str, Any] = {}
        for name in fieldnames:
            value = row.get(name)
            if isinstance(value, (list, dict, tuple)):
                flat[name] = json.dumps(value, sort_keys=True)
            else:
                flat[name] = value
        writer.writerow(flat)
    return buf.getvalue()
