#!/usr/bin/env python3
"""Generate the corrected Sprint V3.6 review artifact.

Publication is intentionally two-stage.  Commit this implementation first, then
run this script from a clean worktree.  The manifest records that clean HEAD;
the generated result files are committed in a second commit.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.adapters.ompl import ompl_version_string
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    load_free_space_bank_v2,
)
from inequality_mechanisms.benchmarks.free_space_report_v2 import (
    build_html_v2,
    build_readme_v2,
    summarize_v3_6_v2,
)
from inequality_mechanisms.benchmarks.run_free_space_evidence_v2 import (
    evidence_manifest_v2,
    run_free_space_evidence_v2,
)

DEFAULT_OUTPUT = Path("results/v3_review/v3_6_free_space_v2")
DEFAULT_HTML_COPY = Path(
    "docs/software/experiments/reports/V3_6_FREE_SPACE_EVIDENCE_V2.html"
)


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
    return proc.stdout.strip() or None


def _git_dirty() -> bool:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return True
    return bool(proc.stdout.strip())


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ompl-solve-time-s", type=float, default=1.0)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--no-html-copy", action="store_true")
    args = parser.parse_args()

    if _git_dirty() and not args.allow_dirty:
        raise SystemExit(
            "Refusing V3.6 evidence generation from a dirty worktree. "
            "Commit the corrected implementation first, then rerun. "
            "Use --allow-dirty only for diagnostics, not published evidence."
        )

    implementation_revision = _git_revision()
    contract = load_free_space_bank_v2()
    rows, resolved_bank = run_free_space_evidence_v2(
        contract=contract,
        ompl_solve_time_s=args.ompl_solve_time_s,
    )
    manifest = evidence_manifest_v2(
        rows,
        contract=contract,
        implementation_revision=implementation_revision,
        ompl_solve_time_s=args.ompl_solve_time_s,
    )
    manifest["ompl_version"] = ompl_version_string()
    summary = summarize_v3_6_v2(rows)

    args.out.mkdir(parents=True, exist_ok=True)
    _write_json(args.out / "resolved_bank.json", resolved_bank)
    _write_json(args.out / "rows.json", rows)
    _write_json(args.out / "manifest.json", manifest)
    _write_json(args.out / "summary.json", summary)
    (args.out / "README.md").write_text(
        build_readme_v2(manifest=manifest, summary=summary),
        encoding="utf-8",
    )
    html = build_html_v2(manifest=manifest, summary=summary)
    html_path = args.out / "V3_6_FREE_SPACE_EVIDENCE_V2.html"
    html_path.write_text(html, encoding="utf-8")

    if not args.no_html_copy:
        DEFAULT_HTML_COPY.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(html_path, DEFAULT_HTML_COPY)

    print(
        f"wrote corrected V3.6 evidence rows={len(rows)} "
        f"implementation_revision={implementation_revision}"
    )
    print(
        "Review the artifact, then commit the generated result directory "
        "as a separate evidence commit."
    )


if __name__ == "__main__":
    main()
