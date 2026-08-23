"""V4.2B lint gate: scoped files clean; full-tree counts cannot grow."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT

PATH_LIST = CANONICAL_REPO_ROOT / "tests" / "v4" / "data" / "v4_2b_lint_paths.txt"
BASELINE_PATH = (
    CANONICAL_REPO_ROOT
    / "tests"
    / "v4"
    / "data"
    / "frozen_full_tree_lint_baseline.json"
)
_MYPY_FOUND = re.compile(r"Found (\d+) errors? in (\d+) files?")
_REFORMAT = re.compile(r"(\d+) files? would be reformatted")


def _load_v4_2b_paths() -> list[Path]:
    lines = [
        line.strip()
        for line in PATH_LIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    paths = [CANONICAL_REPO_ROOT / rel for rel in lines]
    missing = [
        str(path.relative_to(CANONICAL_REPO_ROOT))
        for path in paths
        if not path.is_file()
    ]
    assert not missing, f"V4.2B lint paths missing: {missing}"
    return paths


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=CANONICAL_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def ruff_error_count(paths: list[Path] | None) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json"]
    if paths is None:
        cmd.append(".")
    else:
        cmd.extend(str(path) for path in paths)
    proc = _run(cmd)
    if proc.returncode not in (0, 1):
        return sys.maxsize, proc.stderr or proc.stdout
    payload = proc.stdout.strip() or "[]"
    findings = json.loads(payload)
    return len(findings), proc.stdout


def ruff_format_would_reformat(paths: list[Path] | None) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "ruff", "format", "--check"]
    if paths is None:
        cmd.append(".")
    else:
        cmd.extend(str(path) for path in paths)
    proc = _run(cmd)
    text = proc.stdout + proc.stderr
    if proc.returncode not in (0, 1):
        return sys.maxsize, text
    match = _REFORMAT.search(text)
    if match is not None:
        return int(match.group(1)), text
    if proc.returncode == 0:
        return 0, text
    return sys.maxsize, text


def mypy_counts(
    paths: list[Path] | None, *, follow_imports: str
) -> tuple[int, int, str]:
    cmd = [sys.executable, "-m", "mypy", f"--follow-imports={follow_imports}"]
    if paths is None:
        cmd.append("src")
    else:
        cmd.extend(str(path) for path in paths)
    proc = _run(cmd)
    text = proc.stdout + proc.stderr
    if "Success: no issues found" in text:
        return 0, 0, text
    match = _MYPY_FOUND.search(text)
    if match is None:
        return sys.maxsize, sys.maxsize, text
    return int(match.group(1)), int(match.group(2)), text


def collect_full_tree_lint_counts() -> dict[str, int]:
    ruff_n, _ = ruff_error_count(None)
    format_n, _ = ruff_format_would_reformat(None)
    mypy_n, mypy_files, _ = mypy_counts(None, follow_imports="normal")
    return {
        "ruff_error_count": ruff_n,
        "ruff_format_would_reformat_count": format_n,
        "mypy_error_count": mypy_n,
        "mypy_file_count": mypy_files,
    }


def test_v4_2b_python_files_are_ruff_and_format_clean() -> None:
    paths = _load_v4_2b_paths()
    n_ruff, ruff_out = ruff_error_count(paths)
    assert n_ruff == 0, ruff_out
    n_fmt, fmt_out = ruff_format_would_reformat(paths)
    assert n_fmt == 0, fmt_out


def test_v4_2b_src_modules_are_mypy_clean() -> None:
    src_root = (CANONICAL_REPO_ROOT / "src").resolve()
    src_paths = [
        path for path in _load_v4_2b_paths() if path.resolve().is_relative_to(src_root)
    ]
    n_err, n_files, text = mypy_counts(src_paths, follow_imports="silent")
    assert n_err == 0, text
    assert n_files == 0, text


def test_full_tree_lint_does_not_exceed_frozen_baseline() -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    current = collect_full_tree_lint_counts()
    regressions = {
        key: {"baseline": baseline[key], "current": current[key]}
        for key in (
            "ruff_error_count",
            "ruff_format_would_reformat_count",
            "mypy_error_count",
            "mypy_file_count",
        )
        if int(current[key]) > int(baseline[key])
    }
    assert not regressions, regressions
