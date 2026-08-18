#!/usr/bin/env python3
"""Verify a V4.2B retained package against its manifest inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from inequality_mechanisms.audits.v4_2b_artifact import (
    V4_2BArtifactError,
    verify_v4_2b_artifact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        type=Path,
        help="V4.2B package directory containing manifest.json",
    )
    args = parser.parse_args(argv)
    try:
        summary = verify_v4_2b_artifact(args.root)
    except V4_2BArtifactError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
