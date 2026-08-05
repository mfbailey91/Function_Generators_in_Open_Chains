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
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from inequality_mechanisms.experiments.registry import (  # noqa: E402
    default_results_root,
)
from inequality_mechanisms.experiments.v2_canvas import (  # noqa: E402
    resolve_v2_run_for_canvas,
    write_v2_canvas,
)
from inequality_mechanisms.experiments.v2_production_canvas import (  # noqa: E402
    is_v2_production_run_dir,
    refresh_production_canvas,
)


def _recency(path: Path) -> tuple[str, float]:
    created = ""
    manifest_path = path / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        if isinstance(manifest, dict):
            created = str(manifest.get("created_at") or "")
    return (created, path.stat().st_mtime)


def _resolve_target(
    run: Path | None,
    *,
    latest: bool,
    results_root: Path | None,
) -> tuple[Path, str]:
    root = Path(results_root) if results_root is not None else default_results_root()
    if run is not None and not latest:
        path = Path(run)
        if not path.is_dir():
            candidate = root / str(run)
            if candidate.is_dir():
                path = candidate
            else:
                raise FileNotFoundError(f"Version 2 run not found: {run}")
        path = path.resolve()
        if is_v2_production_run_dir(path):
            return path, "production"
        return resolve_v2_run_for_canvas(path, results_root=root), "diagnostic"

    production_candidates = (
        [p for p in root.iterdir() if p.is_dir() and is_v2_production_run_dir(p)]
        if root.is_dir()
        else []
    )
    latest_production = (
        max(production_candidates, key=_recency) if production_candidates else None
    )
    latest_diagnostic = None
    try:
        latest_diagnostic = resolve_v2_run_for_canvas(None, results_root=root)
    except FileNotFoundError:
        latest_diagnostic = None
    if latest_production is None and latest_diagnostic is None:
        raise FileNotFoundError(f"no Version 2 runs under {root}")
    if latest_diagnostic is not None and (
        latest_production is None
        or _recency(latest_production) < _recency(latest_diagnostic)
    ):
        return latest_diagnostic, "diagnostic"
    assert latest_production is not None
    return latest_production.resolve(), "production"


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
    target, kind = _resolve_target(
        args.run,
        latest=bool(args.latest) or args.run is None,
        results_root=args.results_root,
    )
    if kind == "production":
        path = refresh_production_canvas(target)
        print(f"Wrote Version 2 production canvas to {path}")
        return
    path = write_v2_canvas(target)
    print(f"Wrote Version 2 canvas to {path}")


if __name__ == "__main__":
    main()
