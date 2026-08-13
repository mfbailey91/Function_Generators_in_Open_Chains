#!/usr/bin/env python3
"""Scaffold the Sprint V3.6C planar-2R closeout output package (V3-630).

Full report generation is deferred to V3-638/V3-639. This entrypoint only
enforces the artifact freeze guard and writes a minimal scaffold manifest.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inequality_mechanisms.audits.artifact_freeze import (  # noqa: E402
    assert_v3_6c_output_allowed,
)

DEFAULT_CONFIG = ROOT / "configs" / "v3" / "planar2r_closeout_v1.json"

FREEZE_STATEMENT = (
    "V3.6C writes only under results/v3_review/v3_6c_planar2r_closeout/. "
    "Frozen packages under results/v3_review/ matching v3_6_*, v3_6b_*, and "
    "v3_7_* (including v3_6_free_space, v3_6_free_space_v2, "
    "v3_6b_planar2r_visual_audit, and v3_7_3r_free_space) must not be "
    "overwritten. Full closeout generation is deferred to V3-638/V3-639."
)


def _load_config(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"config root must be an object: {path}")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to planar2r_closeout_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output directory (must pass freeze guard)",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config).expanduser().resolve()
    if not config_path.is_file():
        raise SystemExit(f"config not found: {config_path}")
    config = _load_config(config_path)

    if args.output is not None:
        out_root = Path(args.output)
    else:
        rel = config["artifact_contract"]["output_dir"]
        out_root = ROOT / str(rel)

    # Guard before any mkdir or write.
    out_root = assert_v3_6c_output_allowed(out_root)

    out_root.mkdir(parents=True, exist_ok=True)
    try:
        config_rel = str(config_path.relative_to(ROOT))
    except ValueError:
        config_rel = str(config_path)

    manifest = {
        "status": "scaffold",
        "audit_id": config.get("audit_id"),
        "schema_version": config.get("schema_version"),
        "architecture_version": config.get("architecture_version"),
        "config_path": config_rel,
        "output_dir": str(out_root),
        "freeze_statement": FREEZE_STATEMENT,
        "note": (
            "V3-630 scaffold only; report and evidence generation deferred "
            "to V3-638/V3-639."
        ),
    }
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote scaffold {out_root / 'manifest.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
