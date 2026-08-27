#!/usr/bin/env python3
"""Verify a retained V4.2D optimality-reference package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inequality_mechanisms.audits.v4_2d_artifact import verify_v4_2d_artifact
from inequality_mechanisms.audits.v4_artifact_guard import allowed_v4_2d_output_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--allow-partial-counts",
        action="store_true",
        help="Skip frozen 100/6200 row-count gates (synthetic tests)",
    )
    args = parser.parse_args(argv)
    output = args.output_dir or allowed_v4_2d_output_root()
    summary = verify_v4_2d_artifact(
        output,
        require_frozen_counts=not args.allow_partial_counts,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
