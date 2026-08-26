#!/usr/bin/env python3
"""Write the V4.2C-R frozen-data clarification report from retained Stage C."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inequality_mechanisms.audits.v4_artifact_guard import (
    allowed_v4_2c_r_output_root,
    canonical_v4_2c_retained_root,
)
from inequality_mechanisms.visualization.v4 import (
    ompl_planner_portfolio_clarification as clarification,
)


def _source_files_digest(package_root: Path) -> str:
    manifest = package_root / "manifest.json"
    if not manifest.is_file():
        return clarification.FROZEN_V4_2C_FILES_DIGEST
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    digest = str(payload.get("files_digest") or "")
    return digest or clarification.FROZEN_V4_2C_FILES_DIGEST


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage-dir",
        type=Path,
        default=None,
        help="Retained V4.2C stage directory (default: canonical stage_c)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="V4.2C-R output directory (default: allowed sibling root)",
    )
    args = parser.parse_args(argv)
    package = canonical_v4_2c_retained_root()
    stage = args.stage_dir or (package / "stage_c")
    output = args.output_dir or allowed_v4_2c_r_output_root()
    digest = _source_files_digest(package)
    if digest != clarification.FROZEN_V4_2C_FILES_DIGEST:
        raise SystemExit(
            f"frozen V4.2C files_digest drifted: {digest} "
            f"!= {clarification.FROZEN_V4_2C_FILES_DIGEST}"
        )
    summary = clarification.write_ompl_planner_portfolio_clarification(
        stage,
        output_dir=output,
        source_files_digest=digest,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
