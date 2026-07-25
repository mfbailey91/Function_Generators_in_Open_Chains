#!/usr/bin/env python3
"""CLI for IM-037 edge-validation sensitivity study."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from inequality_mechanisms.experiments.edge_sensitivity import (
    DEFAULT_EDGE_SAMPLE_GRID,
    edge_sensitivity_stable,
    rows_to_csv,
    run_edge_sensitivity,
)


def main(argv: list[str] | None = None) -> int:
    """Run the sensitivity sweep and write CSV / JSON under ``--out``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("results/edge_sensitivity"),
        help="Output directory for CSV and JSON reports",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--shape", type=int, nargs=2, default=[16, 16])
    args = parser.parse_args(argv)

    rows = run_edge_sensitivity(
        shape=(int(args.shape[0]), int(args.shape[1])),
        seed=int(args.seed),
        edge_samples_grid=DEFAULT_EDGE_SAMPLE_GRID,
    )
    stable = edge_sensitivity_stable(rows, from_samples=17)
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "edge_sensitivity.csv").write_text(rows_to_csv(rows), encoding="utf-8")
    payload = {
        "seed": int(args.seed),
        "shape": list(args.shape),
        "edge_samples_grid": list(DEFAULT_EDGE_SAMPLE_GRID),
        "stable_from_17": stable,
        "rows": [r.to_dict() for r in rows],
        "recommendation": (
            "default edge_samples=17 is stable under denser sampling"
            if stable
            else "results did not stabilize; consider adaptive subdivision"
        ),
    }
    (out_dir / "edge_sensitivity.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"stable_from_17": stable, "out": str(out_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
