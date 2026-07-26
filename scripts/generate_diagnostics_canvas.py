#!/usr/bin/env python3
"""Generate Sprint 3 diagnostic PNG bundle and HTML canvas."""

from __future__ import annotations

import argparse
from pathlib import Path

from inequality_mechanisms.diagnostics.bundle import generate_diagnostics_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("diagnostics"),
        help="Output directory for PNGs, traces.json, and index.html",
    )
    parser.add_argument(
        "--shape",
        type=int,
        nargs=2,
        default=(24, 24),
        metavar=("N0", "N1"),
        help="Lattice shape (default: 24 24)",
    )
    args = parser.parse_args()
    traces = generate_diagnostics_bundle(args.out, shape=tuple(args.shape))
    print(f"Wrote diagnostic canvas to {args.out.resolve() / 'index.html'}")
    print(f"Nested edge sets: {traces['edge_density']['nested']}")
    print(
        "Gearbox interior invariant: "
        f"{traces['edge_density']['gearbox_interior_invariant']}"
    )


if __name__ == "__main__":
    main()
