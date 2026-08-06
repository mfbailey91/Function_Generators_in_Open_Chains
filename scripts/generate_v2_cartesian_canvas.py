#!/usr/bin/env python3
"""Generate or regenerate Experiment B Cartesian HTML printouts.

Example
-------
::

    PYTHONPATH=src python scripts/generate_v2_cartesian_canvas.py --run results/v2_12_cartesian_smoke
    PYTHONPATH=src python scripts/generate_v2_cartesian_canvas.py --run v2_12_cartesian_calibration
    PYTHONPATH=src python scripts/generate_v2_cartesian_canvas.py --latest
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from inequality_mechanisms.experiments.registry import (  # noqa: E402
    default_results_root,
)
from inequality_mechanisms.experiments.v2_cartesian_canvas import (  # noqa: E402
    resolve_cartesian_run_for_canvas,
    write_cartesian_canvas,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write index.html for an Experiment B smoke or calibration package."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run", type=Path, help="Run directory or run id under results/")
    group.add_argument(
        "--latest",
        action="store_true",
        help="Use the most recent Experiment B package under results/",
    )
    parser.add_argument("--results-root", type=Path, default=None)
    args = parser.parse_args()
    if args.run is None and not args.latest:
        parser.error("pass --run or --latest")
    root = args.results_root if args.results_root is not None else default_results_root()
    target = resolve_cartesian_run_for_canvas(
        None if args.latest else args.run,
        results_root=root,
    )
    out = write_cartesian_canvas(target)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
