#!/usr/bin/env python3
"""Write the paired V2.11 Dijkstra/A* comparison JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inequality_mechanisms.experiments.v2_solver_comparison import (
    compare_exact_solver_runs,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dijkstra-run", type=Path, required=True)
    parser.add_argument("--astar-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cost-tolerance", type=float, default=1.0e-10)
    args = parser.parse_args()
    payload = compare_exact_solver_runs(
        args.dijkstra_run,
        args.astar_run,
        cost_tolerance=args.cost_tolerance,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
