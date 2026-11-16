#!/usr/bin/env python3
"""Verify a V4.3 retained package against its manifest inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from inequality_mechanisms.audits.v4_3_artifact import (
    V4_3ArtifactError,
    verify_v4_3_artifact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        type=Path,
        help="V4.3 package directory containing manifest.json",
    )
    args = parser.parse_args(argv)
    try:
        summary = verify_v4_3_artifact(args.root)
    except V4_3ArtifactError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
