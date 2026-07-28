#!/usr/bin/env python3
"""Generate or regenerate the Sprint Six HTML canvas.

Example
-------
::

    PYTHONPATH=src python scripts/generate_sprint6_canvas.py --latest
    PYTHONPATH=src python scripts/generate_sprint6_canvas.py --run results/<run_id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from inequality_mechanisms.experiments.canvas import (  # noqa: E402
    resolve_run_for_canvas,
)
from inequality_mechanisms.experiments.sprint6_canvas import (  # noqa: E402
    write_sprint6_canvas,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write Sprint Six index.html for a completed run."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--run",
        type=Path,
        help="Run directory or run id under results/.",
    )
    group.add_argument(
        "--latest",
        action="store_true",
        help="Use the latest completed run under results/.",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=None,
        help="Results parent directory (default: repository results/).",
    )
    args = parser.parse_args()
    target = None if args.latest or args.run is None else args.run
    if args.latest:
        target = None
    run = resolve_run_for_canvas(target, results_root=args.results_root)
    path = write_sprint6_canvas(run)
    print(f"Wrote Sprint Six canvas to {path}")


if __name__ == "__main__":
    main()
