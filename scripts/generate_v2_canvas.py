#!/usr/bin/env python3
"""Generate or regenerate the Version 2 HTML printout.

Example
-------
::

    PYTHONPATH=src python scripts/generate_v2_canvas.py --latest
    PYTHONPATH=src python scripts/generate_v2_canvas.py --run results/<run_id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from inequality_mechanisms.experiments.v2_canvas import (  # noqa: E402
    resolve_v2_run_for_canvas,
    write_v2_canvas,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write Version 2 index.html for a completed V2 run package."
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
        help="Use the latest Version 2 run under results/.",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=None,
        help="Results parent directory (default: repository results/).",
    )
    args = parser.parse_args()
    if args.latest or args.run is None:
        target = resolve_v2_run_for_canvas(None, results_root=args.results_root)
    else:
        target = resolve_v2_run_for_canvas(args.run, results_root=args.results_root)
    path = write_v2_canvas(target)
    print(f"Wrote Version 2 canvas to {path}")


if __name__ == "__main__":
    main()
