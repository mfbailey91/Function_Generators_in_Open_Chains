#!/usr/bin/env python3
"""Generate or regenerate an HTML canvas for a completed Monte Carlo run.

Example
-------
::

    PYTHONPATH=src python scripts/generate_monte_carlo_canvas.py --latest
    PYTHONPATH=src python scripts/generate_monte_carlo_canvas.py --run results/<run_id>
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import argparse  # noqa: E402

from inequality_mechanisms.experiments.canvas import (  # noqa: E402
    resolve_run_for_canvas,
    write_monte_carlo_canvas,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        type=Path,
        default=None,
        help="Completed run directory or run id under --results-root.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use the latest completed run under --results-root.",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=None,
        help="Results parent (default: repository results/).",
    )
    args = parser.parse_args()

    if args.run is not None and args.latest:
        parser.error("pass only one of --run or --latest")
    if args.run is None and not args.latest:
        # Default: latest completed run.
        args.latest = True

    target = None if args.latest else args.run
    run = resolve_run_for_canvas(target, results_root=args.results_root)
    path = write_monte_carlo_canvas(run)
    print(f"Wrote Monte Carlo canvas to {path}")
    print(f"run_id={run.run_id}")
    print(f"seed={run.seed}")


if __name__ == "__main__":
    main()
