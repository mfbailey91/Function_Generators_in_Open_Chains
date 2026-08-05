"""Merge immutable production shards into analysis tables (V2-912)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inequality_mechanisms.experiments.v2_production_analysis import (
    analyze_production_trials,
)
from inequality_mechanisms.experiments.v2_production_config import V2ProductionConfig


class ProductionMergeError(RuntimeError):
    """Raised when shard merge detects duplicate or missing mechanism IDs."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def iter_shard_paths(run_dir: Path) -> list[Path]:
    shard_dir = run_dir / "shards"
    if not shard_dir.is_dir():
        return []
    return sorted(
        path
        for path in shard_dir.glob("mechanism_*.jsonl")
        if not path.name.startswith(".")
    )


def load_production_shards(run_dir: Path | str) -> dict[str, list[dict[str, Any]]]:
    """Load all completed shards grouped by record type."""
    grouped: dict[str, list[dict[str, Any]]] = {
        "mechanism_summary": [],
        "trial": [],
        "pair_comparison": [],
        "failure": [],
    }
    seen: set[str] = set()
    for path in iter_shard_paths(Path(run_dir)):
        rows = _read_jsonl(path)
        mechanism_ids = {
            str(row.get("mechanism_pair_id"))
            for row in rows
            if row.get("mechanism_pair_id")
        }
        if len(mechanism_ids) != 1:
            raise ProductionMergeError(
                f"shard {path} does not contain exactly one pair"
            )
        mech_id = next(iter(mechanism_ids))
        if mech_id in seen:
            raise ProductionMergeError(f"duplicate mechanism_pair_id {mech_id}")
        seen.add(mech_id)
        for row in rows:
            rtype = str(row.get("record_type", ""))
            if rtype not in grouped:
                grouped.setdefault(rtype, []).append(row)
            else:
                grouped[rtype].append(row)
    return grouped


def merge_production_run(
    run_dir: Path | str,
    config: V2ProductionConfig,
    *,
    expected_mechanism_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Merge shards, write analysis artifacts, and return the summary payload."""
    root = Path(run_dir)
    grouped = load_production_shards(root)
    present = [
        str(row["mechanism_pair_id"])
        for row in grouped["mechanism_summary"]
        if row.get("mechanism_pair_id")
    ]
    if expected_mechanism_ids is not None:
        expected = list(expected_mechanism_ids)
        missing = [mid for mid in expected if mid not in set(present)]
        extra = [mid for mid in present if mid not in set(expected)]
        if missing or extra:
            raise ProductionMergeError(
                f"merge ID mismatch missing={missing} extra={extra}"
            )
    analysis = analyze_production_trials(
        grouped["trial"],
        mechanism_records=grouped["mechanism_summary"],
        batch_size=config.stopping.batch_size,
        target_ci_half_width=config.stopping.target_ci_half_width_log_ratio,
        n_bootstrap=config.stopping.hierarchical_bootstrap_samples,
        seed=config.stopping.hierarchical_bootstrap_seed,
        confidence=config.stopping.confidence_level,
        max_relative_estimate_change=config.stopping.max_relative_estimate_change,
        min_mechanisms=config.stopping.minimum_mechanisms,
        stable_batches_required=config.stopping.stable_batches_required,
        maximum_mechanisms=config.stopping.maximum_mechanisms,
    )
    merged_dir = root / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    _write_jsonl(merged_dir / "trials.jsonl", grouped["trial"])
    _write_jsonl(merged_dir / "mechanism_summary.jsonl", grouped["mechanism_summary"])
    _write_jsonl(merged_dir / "comparisons.jsonl", grouped["pair_comparison"])
    summary = {
        "n_mechanisms": len(present),
        "n_trials": len(grouped["trial"]),
        "n_failures": len(grouped["failure"]),
        "n_comparisons": len(grouped["pair_comparison"]),
        "mechanism_pair_ids": present,
        "analysis": analysis,
    }
    (merged_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    (reports_dir / "precision.json").write_text(
        json.dumps(analysis["precision"], indent=2, sort_keys=True) + "\n"
    )
    (reports_dir / "exclusions.json").write_text(
        json.dumps(
            {
                "analysis_exclusions": analysis["exclusions"],
                "task_failures": grouped["failure"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return summary
