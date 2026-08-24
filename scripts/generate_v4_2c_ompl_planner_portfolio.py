#!/usr/bin/env python3
"""Run one V4.2C OMPL planner-portfolio stage from a frozen config."""

from __future__ import annotations

import argparse
from pathlib import Path

from inequality_mechanisms.experiments.v4.ompl_planner_portfolio import (
    run_ompl_planner_portfolio_from_path,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    DEFAULT_SMOKE_CONFIG_REL,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_SMOKE_CONFIG_REL,
        help="Frozen V4.2C planner-portfolio config JSON",
    )
    args = parser.parse_args()
    summary = run_ompl_planner_portfolio_from_path(args.config)
    print(summary["stage_dir"])
    print(
        f"n_rows={summary['n_rows']} "
        f"n_completed={summary['n_completed']} "
        f"n_failed={summary['n_failed']} "
        f"n_skipped={summary['n_skipped']}"
    )


if __name__ == "__main__":
    main()
