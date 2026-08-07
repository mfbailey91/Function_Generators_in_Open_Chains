#!/usr/bin/env python3
"""Export bounded Version 3 smoke/parity results for GitHub review.

This is a review snapshot, not a production evidence campaign. It intentionally
collects the bounded smoke packs from V3.2 through V3.5 into one tracked
directory so implementation behavior is inspectable without re-running locally.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.adapters.ompl import (
    is_ompl_available,
    ompl_version_string,
)
from inequality_mechanisms.benchmarks.smoke_direct_2r import run_smoke_pack
from inequality_mechanisms.benchmarks.smoke_lattice_2r import run_lattice_smoke_pack
from inequality_mechanisms.benchmarks.smoke_ompl_2r import (
    run_ompl_parity_smoke_pack,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
    SMOKE_SEED,
    run_sampling_smoke_pack,
)

DEFAULT_OUTPUT = Path("results/v3_review/v3_5_closeout")


def _git_revision() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = proc.stdout.strip()
    return value or None


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


def _status_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get(key))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _validate_snapshot(
    direct_rows: list[dict[str, Any]],
    lattice_rows: list[dict[str, Any]],
    sampling_rows: list[dict[str, Any]],
    ompl_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    failures: list[str] = []
    if any(row.get("architecture_version") != 3 for row in direct_rows):
        failures.append("direct smoke contains non-V3 result")
    if any(row.get("architecture_version") != 3 for row in lattice_rows):
        failures.append("lattice smoke contains non-V3 result")
    if any(row.get("architecture_version") != 3 for row in sampling_rows):
        failures.append("sampling smoke contains non-V3 result")
    if any(not row.get("same_task_class", False) for row in ompl_rows):
        failures.append("OMPL/native parity contains task-class mismatch")
    if any(
        not row.get("both_success_when_native_success", False)
        for row in ompl_rows
    ):
        failures.append("OMPL failed a smoke task solved by its native counterpart")
    return {
        "passed": not failures,
        "failures": failures,
    }


def _markdown_table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]
    head = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    rule = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = [
        "| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |"
        for row in rows
    ]
    return "\n".join([head, rule, *body])


def _build_readme(
    *,
    manifest: dict[str, Any],
    ompl_rows: list[dict[str, Any]],
) -> str:
    suites = manifest["suites"]
    suite_rows = [
        [
            name,
            str(info["rows"]),
            json.dumps(info["status_counts"], sort_keys=True),
        ]
        for name, info in suites.items()
    ]
    parity_rows = [
        [
            str(row["task_id"]),
            str(row["mechanism"]),
            str(row["ompl_planner"]),
            str(row["native_planner"]),
            str(row["ompl_status"]),
            str(row["native_status"]),
            "yes" if row["same_task_class"] else "NO",
        ]
        for row in ompl_rows
    ]
    return "\n".join(
        [
            "# Version 3 review snapshot — V3.5 closeout",
            "",
            "This directory is a **bounded smoke/parity review artifact**, not a "
            "production population study or Monte Carlo result.",
            "",
            f"- Code revision: `{manifest['code_revision']}`",
            f"- Generated UTC: `{manifest['generated_at_utc']}`",
            f"- OMPL version: `{manifest['ompl_version']}`",
            f"- Frozen smoke seed: `{manifest['seed']}`",
            f"- OMPL solve budget per query: `{manifest['solve_time_s']}` s",
            f"- Snapshot validation: `{'PASS' if manifest['validation']['passed'] else 'FAIL'}`",
            "",
            "## Included suites",
            "",
            _markdown_table(suite_rows, ["suite", "rows", "status counts"]),
            "",
            "## OMPL/native parity",
            "",
            _markdown_table(
                parity_rows,
                [
                    "task",
                    "mechanism",
                    "OMPL",
                    "native",
                    "OMPL status",
                    "native status",
                    "same class",
                ],
            ),
            "",
            "Full row-level data are stored beside this README:",
            "",
            "- `v3_2_direct_smoke.json`",
            "- `v3_3_lattice_smoke.json`",
            "- `v3_4_sampling_smoke.json`",
            "- `v3_5_ompl_native_parity.json`",
            "- `manifest.json`",
            "",
            "Regenerate with:",
            "",
            "```bash",
            "PYTHONPATH=src python scripts/export_v3_review_results.py",
            "```",
            "",
        ]
    )


def export_snapshot(
    output: Path,
    *,
    seed: int,
    solve_time_s: float,
) -> dict[str, Any]:
    if not is_ompl_available():
        raise RuntimeError(
            "V3.5 review export requires OMPL bindings; refusing to publish a "
            "partial closeout snapshot"
        )
    output.mkdir(parents=True, exist_ok=True)

    direct_rows = run_smoke_pack()
    lattice_rows = run_lattice_smoke_pack()
    sampling_rows = run_sampling_smoke_pack(seed=seed)
    ompl_rows = run_ompl_parity_smoke_pack(
        seed=seed,
        solve_time_s=solve_time_s,
    )
    validation = _validate_snapshot(
        direct_rows,
        lattice_rows,
        sampling_rows,
        ompl_rows,
    )

    _write_json(output / "v3_2_direct_smoke.json", direct_rows)
    _write_json(output / "v3_3_lattice_smoke.json", lattice_rows)
    _write_json(output / "v3_4_sampling_smoke.json", sampling_rows)
    _write_json(output / "v3_5_ompl_native_parity.json", ompl_rows)

    manifest = {
        "snapshot_schema_version": 1,
        "snapshot_id": "v3_5_closeout",
        "architecture_version": 3,
        "code_revision": _git_revision(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "ompl_version": ompl_version_string(),
        "seed": int(seed),
        "solve_time_s": float(solve_time_s),
        "suites": {
            "v3_2_direct_smoke": {
                "rows": len(direct_rows),
                "status_counts": _status_counts(direct_rows, "status"),
            },
            "v3_3_lattice_smoke": {
                "rows": len(lattice_rows),
                "status_counts": _status_counts(lattice_rows, "status"),
            },
            "v3_4_sampling_smoke": {
                "rows": len(sampling_rows),
                "status_counts": _status_counts(sampling_rows, "status"),
            },
            "v3_5_ompl_native_parity": {
                "rows": len(ompl_rows),
                "status_counts": _status_counts(ompl_rows, "ompl_status"),
            },
        },
        "validation": validation,
        "scope_note": (
            "Bounded deterministic/stochastic smoke and parity evidence only; "
            "not population inference."
        ),
    }
    _write_json(output / "manifest.json", manifest)
    (output / "README.md").write_text(
        _build_readme(manifest=manifest, ompl_rows=ompl_rows),
        encoding="utf-8",
    )
    if not validation["passed"]:
        raise RuntimeError(
            "V3 review snapshot failed closeout validation: "
            + "; ".join(validation["failures"])
        )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=SMOKE_SEED)
    parser.add_argument("--solve-time-s", type=float, default=5.0)
    args = parser.parse_args()
    manifest = export_snapshot(
        args.out,
        seed=args.seed,
        solve_time_s=args.solve_time_s,
    )
    print(
        f"wrote {args.out} at revision {manifest['code_revision']} "
        f"(OMPL {manifest['ompl_version']})"
    )


if __name__ == "__main__":
    main()
