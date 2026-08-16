#!/usr/bin/env python3
"""Export the V3.6F 17-case gravity-free static wrench atlas."""

from __future__ import annotations

import argparse
from pathlib import Path

from inequality_mechanisms.audits.static_wrench_atlas import export_static_wrench_atlas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    path = export_static_wrench_atlas(output=args.output, trace=args.trace)
    print(path)


if __name__ == "__main__":
    main()
