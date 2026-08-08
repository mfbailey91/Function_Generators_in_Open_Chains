#!/usr/bin/env python3
"""Run and export Sprint V3.6 free-space planner evidence.

Writes a tracked review package under ``results/v3_review/v3_6_free_space/`` and a
print-ready HTML copy under ``docs/software/experiments/reports/``.

This is bounded free-space evidence only — not population inference.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.adapters.ompl import is_ompl_available, ompl_version_string
from inequality_mechanisms.benchmarks.free_space_bank import load_free_space_bank
from inequality_mechanisms.benchmarks.free_space_report import (
    build_html,
    build_readme,
    summarize_strata,
)
from inequality_mechanisms.benchmarks.run_free_space_evidence import (
    DEFAULT_PLANNERS,
    PlannerName,
    evidence_manifest,
    run_free_space_evidence,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import SMOKE_SEED

DEFAULT_OUTPUT = Path("results/v3_review/v3_6_free_space")
DEFAULT_HTML_COPY = Path(
    "docs/software/experiments/reports/V3_6_FREE_SPACE_EVIDENCE.html"
)


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            default=_json_default,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def export_free_space_evidence(
    output: Path,
    *,
    seed: int,
    ompl_solve_time_s: float,
    planners: tuple[PlannerName, ...] = DEFAULT_PLANNERS,
    html_copy: Path | None = DEFAULT_HTML_COPY,
) -> dict[str, Any]:
    """Run the evidence pack and write the review artifact."""
    bank = load_free_space_bank()
    rows = run_free_space_evidence(
        bank=bank,
        planners=planners,
        seed=seed,
        ompl_solve_time_s=ompl_solve_time_s,
    )
    manifest = evidence_manifest(
        rows,
        bank=bank,
        seed=seed,
        ompl_solve_time_s=ompl_solve_time_s,
        planners=planners,
    )
    manifest["ompl_version"] = ompl_version_string()
    summary = summarize_strata(rows)

    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "rows.json", rows)
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "summary.json", summary)
    (output / "README.md").write_text(
        build_readme(manifest=manifest, summary=summary),
        encoding="utf-8",
    )
    html = build_html(manifest=manifest, rows=rows, summary=summary)
    html_path = output / "V3_6_FREE_SPACE_EVIDENCE.html"
    html_path.write_text(html, encoding="utf-8")
    if html_copy is not None:
        html_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(html_path, html_copy)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Sprint V3.6 free-space evidence review package"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=SMOKE_SEED)
    parser.add_argument("--ompl-solve-time-s", type=float, default=2.0)
    parser.add_argument(
        "--no-html-copy",
        action="store_true",
        help="Do not copy HTML into docs/software/experiments/reports/",
    )
    args = parser.parse_args()
    manifest = export_free_space_evidence(
        args.out,
        seed=args.seed,
        ompl_solve_time_s=args.ompl_solve_time_s,
        html_copy=None if args.no_html_copy else DEFAULT_HTML_COPY,
    )
    print(
        f"wrote {args.out} rows={manifest['n_rows']} "
        f"ompl_available={manifest['ompl_available']} "
        f"revision={manifest['code_revision']}"
    )
    if not is_ompl_available():
        print(
            "note: OMPL bindings unavailable; ompl_* rows were skipped "
            "(re-run with .conda-ompl to publish OMPL evidence)"
        )


if __name__ == "__main__":
    main()
