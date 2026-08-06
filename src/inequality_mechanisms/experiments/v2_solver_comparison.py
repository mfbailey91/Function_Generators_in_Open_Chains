"""Paired Dijkstra/A* comparison for V2.11."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def compare_exact_solver_runs(
    dijkstra_run: Path | str,
    astar_run: Path | str,
    *,
    cost_tolerance: float = 1.0e-10,
) -> dict[str, Any]:
    """Join exact-solver rows and enforce the frozen paired-campaign contract."""
    droot, aroot = Path(dijkstra_run), Path(astar_run)
    dman = json.loads((droot / "manifest.json").read_text())
    aman = json.loads((aroot / "manifest.json").read_text())
    if dman.get("solver_id") != "dijkstra" or aman.get("solver_id") != "astar":
        raise ValueError("expected Dijkstra reference and A* campaign manifests")
    if dman.get("sample_bank_digest") != aman.get("sample_bank_digest"):
        raise ValueError("solver campaigns use different sample-bank digests")
    drows = _read_jsonl(droot / "merged" / "trials.jsonl")
    arows = _read_jsonl(aroot / "merged" / "trials.jsonl")
    def key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            row.get("mechanism_pair_id"),
            row.get("mechanism_id"),
            row.get("task_id"),
            tuple(row.get("graph_shape") or ()),
            row.get("objective_id"),
        )
    dmap = {key(row): row for row in drows}
    amap = {key(row): row for row in arows}
    if dmap.keys() != amap.keys():
        raise ValueError("Dijkstra and A* trial keys are not identical")
    paired: list[dict[str, Any]] = []
    max_cost_delta = 0.0
    for trial_key in sorted(dmap, key=str):
        drow, arow = dmap[trial_key], amap[trial_key]
        if bool(drow.get("found")) != bool(arow.get("found")):
            raise ValueError(f"solver feasibility disagreement for {trial_key}")
        if not drow.get("found"):
            continue
        cost_delta = abs(float(drow["optimal_cost"]) - float(arow["optimal_cost"]))
        max_cost_delta = max(max_cost_delta, cost_delta)
        if cost_delta > cost_tolerance:
            raise ValueError(
                f"optimal-cost disagreement {cost_delta} for {trial_key}"
            )
        d_exp = int(drow["n_expanded"])
        a_exp = int(arow["n_expanded"])
        paired.append(
            {
                "mechanism_pair_id": trial_key[0],
                "mechanism_id": trial_key[1],
                "task_id": trial_key[2],
                "dijkstra_expanded": d_exp,
                "astar_expanded": a_exp,
                "heuristic_savings": 1.0 - (a_exp + 1.0) / (d_exp + 1.0),
                "log_astar_to_dijkstra": math.log((a_exp + 1.0) / (d_exp + 1.0)),
                "cost_delta": cost_delta,
            }
        )
    mean_savings = (
        sum(float(row["heuristic_savings"]) for row in paired) / len(paired)
        if paired
        else None
    )
    return {
        "sample_bank_digest": dman.get("sample_bank_digest"),
        "n_paired_trials": len(paired),
        "max_optimal_cost_delta": max_cost_delta,
        "mean_heuristic_savings": mean_savings,
        "paired_trials": paired,
    }
