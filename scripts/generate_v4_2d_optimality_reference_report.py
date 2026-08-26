#!/usr/bin/env python3
"""Generate the V4.2D optimality-reference report from frozen V4.2B/V4.2C."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inequality_mechanisms.audits.v4_2d_artifact import (
    generate_optimality_reference_report,
)
from inequality_mechanisms.audits.v4_artifact_guard import allowed_v4_2d_output_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="V4.2D output directory (default: allowed sibling root)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Frozen V4.2D config JSON",
    )
    args = parser.parse_args(argv)
    output = args.output_dir or allowed_v4_2d_output_root()
    summary = generate_optimality_reference_report(
        output,
        config_path=args.config,
        verify_sources=True,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
