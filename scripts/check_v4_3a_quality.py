#!/usr/bin/env python3
"""Run the V4.3A source/test lint, formatting, and type gates."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "src/inequality_mechanisms/audits/v4_artifact_guard.py",
    "src/inequality_mechanisms/audits/v4_3_artifact.py",
    "src/inequality_mechanisms/experiments/v4/intrinsic_static_wrench.py",
    "src/inequality_mechanisms/experiments/v4/intrinsic_static_wrench_config.py",
    "src/inequality_mechanisms/experiments/v4/intrinsic_static_wrench_fields.py",
    "src/inequality_mechanisms/visualization/v4/intrinsic_static_wrench.py",
)


def main() -> int:
    tests = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests" / "v4").glob("test_v4_3*.py")
    )
    paths = [
        *SOURCES,
        *tests,
        "scripts/check_v4_3a_quality.py",
        "scripts/generate_v4_3_intrinsic_static_wrench.py",
        "scripts/verify_v4_3_artifact.py",
    ]
    for args in (
        ["ruff", "check", *paths],
        ["ruff", "format", "--check", *paths],
        ["mypy", "--follow-imports=silent", *SOURCES],
    ):
        result = subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
