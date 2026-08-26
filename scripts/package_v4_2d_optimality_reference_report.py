#!/usr/bin/env python3
"""Package a generated V4.2D optimality-reference report tree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inequality_mechanisms.audits.v4_2d_artifact import package_v4_2d_report
from inequality_mechanisms.audits.v4_artifact_guard import allowed_v4_2d_output_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--source-git-revision", default=None)
    args = parser.parse_args(argv)
    output = args.output_dir or allowed_v4_2d_output_root()
    summary = package_v4_2d_report(
        output,
        source_git_revision=args.source_git_revision,
        allow_dirty=args.allow_dirty,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
