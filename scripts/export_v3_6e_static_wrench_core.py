#!/usr/bin/env python3
"""Export V3.6E gravity-free static-wrench math fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

from inequality_mechanisms.audits.static_wrench_validation import export_static_wrench_core


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = export_static_wrench_core(output=args.output)
    print(path)


if __name__ == "__main__":
    main()
