#!/usr/bin/env python3
"""Generate the V4.3 intrinsic static-wrench retained package."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    DEFAULT_CONFIG_REL,
)
from inequality_mechanisms.visualization.v4.intrinsic_static_wrench import (
    generate_intrinsic_static_wrench_package,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_REL,
        help="Frozen V4.3 intrinsic-wrench config JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="V4.3 output directory (tmp paths allowed; historical packages refused)",
    )
    args = parser.parse_args()
    package = generate_intrinsic_static_wrench_package(
        config_path=args.config,
        output=args.output,
        require_full_corpus=True,
    )
    print(package["output"])
    print(
        f"n_rows={package['n_rows']} n_cases={package['n_cases']} "
        f"n_typed_failures={package['n_typed_failures']} "
        f"n_silent_drops={package['n_silent_drops']} "
        f"files_digest={package['files_digest']}"
    )


if __name__ == "__main__":
    main()
