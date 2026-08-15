#!/usr/bin/env python3
"""Generate the Sprint V4.0 kinematic geometry-core smoke package (V4-008).

Writes only under results/v4_review/v4_0_kinematic_geometry_core/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from inequality_mechanisms.audits.v4_geometry_core_smoke import (  # noqa: E402
    default_output_path,
    generate_geometry_core_smoke,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output directory (must pass the V4.0 artifact guard). "
            "Defaults to results/v4_review/v4_0_kinematic_geometry_core."
        ),
    )
    args = parser.parse_args(argv)
    output = args.output if args.output is not None else default_output_path()
    written = generate_geometry_core_smoke(output)
    print(f"wrote V4.0 geometry-core smoke package to {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
