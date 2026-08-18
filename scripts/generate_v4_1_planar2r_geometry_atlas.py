#!/usr/bin/env python3
"""Generate the V4.1 planar-2R intrinsic geometry atlas package."""

from __future__ import annotations

import argparse
from pathlib import Path

from inequality_mechanisms.experiments.v4.atlas_config import DEFAULT_CONFIG_REL
from inequality_mechanisms.experiments.v4.generate import generate_planar2r_geometry_atlas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_REL,
        help="Frozen V4.1 atlas config JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Guarded V4.1 output directory",
    )
    args = parser.parse_args()
    path = generate_planar2r_geometry_atlas(config_path=args.config, output=args.output)
    print(path)


if __name__ == "__main__":
    main()
