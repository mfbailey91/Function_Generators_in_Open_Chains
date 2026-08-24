#!/usr/bin/env python3
"""Write compressed extracts, landing HTML, and manifest for a V4.2C package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from inequality_mechanisms.audits.v4_2c_artifact import (
    V4_2CArtifactError,
    package_ompl_planner_portfolio,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_2C_ALLOWED_OUTPUT_REL,
    DirtySourceError,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        type=Path,
        nargs="?",
        default=V4_2C_ALLOWED_OUTPUT_REL,
        help="V4.2C package directory",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Record a dirty tree instead of refusing (tests only)",
    )
    args = parser.parse_args(argv)
    try:
        summary = package_ompl_planner_portfolio(
            args.root, allow_dirty=bool(args.allow_dirty)
        )
    except (V4_2CArtifactError, DirtySourceError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
