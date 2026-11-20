#!/usr/bin/env python3
"""Generate or independently verify the bounded V4.4 velocity/IK smoke package."""

from __future__ import annotations

import argparse
from pathlib import Path

from inequality_mechanisms.audits.v4_4_artifact import (
    CANONICAL_REPO_ROOT,
    OUTPUT_REL,
    strict_json,
    verify_v4_4_artifact,
)
from inequality_mechanisms.experiments.v4.intrinsic_velocity import (
    generate_velocity_smoke,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, help="Validated frozen smoke config JSON"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Read-only independent verification of the retained smoke",
    )
    args = parser.parse_args()
    result = (
        verify_v4_4_artifact(CANONICAL_REPO_ROOT / OUTPUT_REL)
        if args.verify
        else generate_velocity_smoke(config_path=args.config)
    )
    print(strict_json(result))


if __name__ == "__main__":
    main()
