#!/usr/bin/env python3
"""Print the V4-231 OMPL Python-binding capability matrix as JSON.

Default output is stdout only. ``--output`` may write a file only under
``results/v4_review/v4_2c_ompl_planner_portfolio/``. This script does not
create that package directory unless an allowed output path is requested.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from inequality_mechanisms.adapters.ompl.capabilities import probe_ompl_capabilities
from inequality_mechanisms.audits.v4_artifact_guard import (
    ArtifactPathForbiddenError,
    assert_v4_2c_output_allowed,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional JSON path under the V4.2C artifact root. "
            "Refused for any other location."
        ),
    )
    args = parser.parse_args(argv)
    # OMPL C++ warnings write to stdout; keep the JSON payload on stdout.
    saved_stdout = os.dup(1)
    os.dup2(sys.stderr.fileno(), 1)
    try:
        matrix = probe_ompl_capabilities()
    finally:
        sys.stdout.flush()
        os.dup2(saved_stdout, 1)
        os.close(saved_stdout)
    text = json.dumps(matrix, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output is not None:
        try:
            destination = assert_v4_2c_output_allowed(args.output)
        except ArtifactPathForbiddenError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
