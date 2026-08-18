#!/usr/bin/env python3
"""Generate the Sprint V4.2A span-controlled visual planning audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inequality_mechanisms.experiments.v4.span_controlled_visual_audit import (
    generate_span_controlled_visual_audit,
)
from inequality_mechanisms.experiments.v4.span_controlled_visual_audit_config import (
    DEFAULT_CONFIG_REL,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / DEFAULT_CONFIG_REL,
        help="Path to planar2r_span_controlled_visual_audit_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output directory (must be the allowed V4.2A root)",
    )
    parser.add_argument(
        "--case-ids",
        nargs="*",
        default=None,
        help="Optional subset of case ids (tests only)",
    )
    parser.add_argument(
        "--task-ids",
        nargs="*",
        default=None,
        help="Optional subset of task ids (tests only)",
    )
    parser.add_argument(
        "--lattice-shape",
        type=int,
        nargs=2,
        default=None,
        metavar=("H", "W"),
        help="Override lattice shape (tests only)",
    )
    parser.add_argument(
        "--skip-animations",
        action="store_true",
        help="Skip GIF generation (static panels remain authoritative)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip case trees that already have every requested trial page",
    )
    args = parser.parse_args(argv)
    path = generate_span_controlled_visual_audit(
        config_path=args.config,
        output=args.output,
        case_ids=args.case_ids,
        task_ids=args.task_ids,
        lattice_shape=tuple(args.lattice_shape) if args.lattice_shape else None,
        skip_animations=bool(args.skip_animations),
        resume=bool(args.resume),
    )
    print(f"wrote {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
