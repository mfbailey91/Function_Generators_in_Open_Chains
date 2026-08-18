#!/usr/bin/env python3
"""Generate the V4.2B mounted-Q span-controlled corrective geometry atlas."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from inequality_mechanisms.experiments.v4.span_controlled_corrective import (
    generate_span_controlled_corrective_atlas,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_config import (
    DEFAULT_CONFIG_REL,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_REL,
        help="Frozen V4.2B corrective-atlas config JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="V4.2B output directory (tmp paths allowed; historical packages refused)",
    )
    args = parser.parse_args()
    package = generate_span_controlled_corrective_atlas(
        config_path=args.config, output=args.output
    )
    print(package["output"])
    print(
        f"n_rows={package['n_rows']} "
        f"n_typed_failures={package['n_typed_failures']} "
        f"n_silent_drops={package['n_silent_drops']}"
    )


if __name__ == "__main__":
    main()
