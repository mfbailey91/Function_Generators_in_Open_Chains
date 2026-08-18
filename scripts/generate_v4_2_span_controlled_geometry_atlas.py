#!/usr/bin/env python3
"""Generate the V4.2 span-controlled geometry atlas package."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
    generate_span_controlled_geometry_atlas,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    DEFAULT_CONFIG_REL,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_REL,
        help="Frozen V4.2 span-atlas config JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Guarded V4.2 output directory",
    )
    args = parser.parse_args()
    path = generate_span_controlled_geometry_atlas(
        config_path=args.config, output=args.output
    )
    print(path)


if __name__ == "__main__":
    main()
