#!/usr/bin/env python3
"""Generate or independently verify the V4.4 intrinsic velocity atlas package."""

from __future__ import annotations

import argparse
from pathlib import Path

from inequality_mechanisms.audits.v4_4_artifact import strict_json
from inequality_mechanisms.audits.v4_4_atlas_artifact import (
    ATLAS_OUTPUT_REL,
    CANONICAL_REPO_ROOT,
    DEFAULT_ATLAS_CONFIG_REL,
    verify_v4_4_atlas_artifact,
)
from inequality_mechanisms.experiments.v4.intrinsic_velocity_atlas import (
    generate_velocity_atlas,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_ATLAS_CONFIG_REL,
        help="Validated frozen atlas config JSON",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Read-only independent verification of the retained atlas",
    )
    args = parser.parse_args()
    result = (
        verify_v4_4_atlas_artifact(CANONICAL_REPO_ROOT / ATLAS_OUTPUT_REL)
        if args.verify
        else generate_velocity_atlas(config_path=args.config)
    )
    print(strict_json(result))


if __name__ == "__main__":
    main()
