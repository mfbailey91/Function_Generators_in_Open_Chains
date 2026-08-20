#!/usr/bin/env python3
"""Generate the V4.2B mounted-Q span-controlled corrective package."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from inequality_mechanisms.experiments.v4 import (
    span_controlled_corrective_audit_config as _audit_cfg,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective import (
    generate_span_controlled_corrective_atlas,
    generate_span_controlled_corrective_package,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit import (
    generate_span_controlled_corrective_audit,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_config import (
    DEFAULT_CONFIG_REL,
)

AUDIT_CONFIG_REL = _audit_cfg.DEFAULT_CONFIG_REL


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_REL,
        help="Frozen V4.2B corrective-atlas config JSON",
    )
    parser.add_argument(
        "--audit-config",
        type=Path,
        default=AUDIT_CONFIG_REL,
        help="Frozen V4.2B planning-audit config JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="V4.2B output directory (tmp paths allowed; historical packages refused)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--geometry-only",
        action="store_true",
        help="Write the geometry atlas only",
    )
    mode.add_argument(
        "--planning-only",
        action="store_true",
        help="Write planning_audit/ only under the output root",
    )
    args = parser.parse_args()
    if args.geometry_only:
        package = generate_span_controlled_corrective_atlas(
            config_path=args.config, output=args.output
        )
        print(package["output"])
        print(
            f"n_rows={package['n_rows']} "
            f"n_typed_failures={package['n_typed_failures']} "
            f"n_silent_drops={package['n_silent_drops']}"
        )
        return
    if args.planning_only:
        target = args.output
        if target is not None:
            target = Path(target) / "planning_audit"
        package = generate_span_controlled_corrective_audit(
            config_path=args.audit_config, output=target
        )
        print(package["output"])
        print(
            f"n_rows={package['n_rows']} "
            f"n_typed_failures={package['n_typed_failures']} "
            f"n_silent_drops={package['n_silent_drops']}"
        )
        return
    package = generate_span_controlled_corrective_package(
        config_path=args.config,
        audit_config_path=args.audit_config,
        output=args.output,
    )
    print(package["output"])
    geometry = package.get("geometry") or {}
    planning = package.get("planning") or {}
    print(
        "geometry "
        f"n_rows={geometry.get('n_rows')} "
        f"n_typed_failures={geometry.get('n_typed_failures')} "
        f"n_silent_drops={geometry.get('n_silent_drops')}"
    )
    print(
        "planning "
        f"n_rows={planning.get('n_rows')} "
        f"n_typed_failures={planning.get('n_typed_failures')} "
        f"n_silent_drops={planning.get('n_silent_drops')}"
    )


if __name__ == "__main__":
    main()
