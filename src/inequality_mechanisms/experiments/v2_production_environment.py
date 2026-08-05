"""Hardware and numerical-thread environment capture for production runs."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import Any

from inequality_mechanisms.experiments.registry import (
    capture_environment,
    capture_revision,
)

_THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def _run_text(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _parse_sysctl_int(name: str) -> int | None:
    text = _run_text(["sysctl", "-n", name])
    if text is None:
        return None
    try:
        return int(text.split()[0])
    except (TypeError, ValueError, IndexError):
        return None


def _parse_system_profiler() -> dict[str, Any]:
    text = _run_text(["system_profiler", "SPHardwareDataType", "-detailLevel", "mini"])
    if text is None:
        return {"available": False, "raw": None}
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return {
        "available": True,
        "chip": fields.get("Chip") or fields.get("Processor Name"),
        "model_name": fields.get("Model Name"),
        "model_identifier": fields.get("Model Identifier"),
        "total_number_of_cores": fields.get("Total Number of Cores"),
        "memory": fields.get("Memory"),
        "raw": text,
    }


def apply_numerical_thread_limits(n_threads: int = 1) -> dict[str, str]:
    """Set numerical-library thread environment variables in this process."""
    value = str(int(n_threads))
    applied: dict[str, str] = {}
    for name in _THREAD_ENV_VARS:
        os.environ[name] = value
        applied[name] = value
    return applied


def capture_thread_environment() -> dict[str, str | None]:
    """Record numerical-library thread variables, including missing ones."""
    return {name: os.environ.get(name) for name in _THREAD_ENV_VARS}


def peak_rss_bytes() -> int | None:
    """Return peak resident set size for this process when available."""
    try:
        import resource
    except ImportError:
        return None
    try:
        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except Exception:  # noqa: BLE001
        return None
    if sys.platform == "darwin":
        return rss
    return rss * 1024


def capture_production_environment(
    *,
    workers: int,
    numerical_threads_per_worker: int,
    graph_shape: list[int] | tuple[int, ...],
    process_start_method: str | None = None,
) -> dict[str, Any]:
    """Capture interpreter, package, OS, and M4-class hardware fields."""
    base = capture_environment()
    revision = capture_revision()
    hardware = _parse_system_profiler()
    physical_cpu = _parse_sysctl_int("hw.physicalcpu")
    logical_cpu = _parse_sysctl_int("hw.logicalcpu")
    memsize = _parse_sysctl_int("hw.memsize")
    payload: dict[str, Any] = {
        **base,
        "revision": revision,
        "macos_version": platform.mac_ver()[0] or None,
        "hardware": hardware,
        "physical_cpu": physical_cpu,
        "logical_cpu": logical_cpu,
        "total_memory_bytes": memsize,
        "available_memory_bytes": None,
        "process_start_method": process_start_method,
        "numerical_thread_environment": capture_thread_environment(),
        "runner_workers": int(workers),
        "numerical_threads_per_worker": int(numerical_threads_per_worker),
        "graph_shape": [int(x) for x in graph_shape],
        "expected_node_count": int(np_prod(graph_shape)),
    }
    try:
        import psutil  # type: ignore[import-untyped]
    except Exception:  # noqa: BLE001
        payload["available_memory_bytes"] = None
        payload["available_memory_source"] = "unavailable"
    else:
        payload["available_memory_bytes"] = int(psutil.virtual_memory().available)
        payload["available_memory_source"] = "psutil"
    return payload


def np_prod(values: list[int] | tuple[int, ...]) -> int:
    out = 1
    for value in values:
        out *= int(value)
    return out
