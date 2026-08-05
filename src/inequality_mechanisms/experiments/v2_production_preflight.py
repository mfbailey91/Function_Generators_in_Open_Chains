"""Memory-safety preflight for production Monte Carlo launches (V2-906)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inequality_mechanisms.experiments.v2_production_config import V2ProductionConfig


class ProductionPreflightError(RuntimeError):
    """Raised when a production launch is refused for resource safety."""


@dataclass(frozen=True, slots=True)
class MemoryPreflight:
    """Estimated aggregate memory versus configured safety threshold."""

    workers: int
    parent_rss_bytes: int
    worker_peak_rss_bytes: int
    margin_bytes: int
    estimated_bytes: int
    total_memory_bytes: int | None
    max_fraction: float
    limit_bytes: int | None
    allowed: bool
    override: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "workers": self.workers,
            "parent_rss_bytes": self.parent_rss_bytes,
            "worker_peak_rss_bytes": self.worker_peak_rss_bytes,
            "margin_bytes": self.margin_bytes,
            "estimated_bytes": self.estimated_bytes,
            "total_memory_bytes": self.total_memory_bytes,
            "max_fraction": self.max_fraction,
            "limit_bytes": self.limit_bytes,
            "allowed": self.allowed,
            "override": self.override,
            "reason": self.reason,
        }


def estimate_aggregate_memory(
    *,
    parent_rss_bytes: int,
    worker_peak_rss_bytes: int,
    workers: int,
    margin_bytes: int,
) -> int:
    """Return ``R_parent + W * R_worker_peak + R_margin``."""
    return (
        int(parent_rss_bytes)
        + int(workers) * int(worker_peak_rss_bytes)
        + int(margin_bytes)
    )


def memory_preflight(
    config: V2ProductionConfig,
    *,
    total_memory_bytes: int | None,
    worker_peak_rss_bytes: int | None = None,
    parent_rss_bytes: int | None = None,
    override: bool | None = None,
) -> MemoryPreflight:
    """Estimate aggregate memory and decide whether launch is allowed."""
    workers = int(config.execution.workers)
    parent = int(
        parent_rss_bytes
        if parent_rss_bytes is not None
        else config.execution.parent_rss_bytes
    )
    worker_peak = int(
        worker_peak_rss_bytes
        if worker_peak_rss_bytes is not None
        else (
            config.execution.worker_peak_rss_bytes
            if config.execution.worker_peak_rss_bytes is not None
            else 256 * 1024 * 1024
        )
    )
    margin = int(config.execution.memory_margin_bytes)
    estimated = estimate_aggregate_memory(
        parent_rss_bytes=parent,
        worker_peak_rss_bytes=worker_peak,
        workers=workers,
        margin_bytes=margin,
    )
    use_override = bool(
        config.execution.memory_override if override is None else override
    )
    if total_memory_bytes is None:
        return MemoryPreflight(
            workers=workers,
            parent_rss_bytes=parent,
            worker_peak_rss_bytes=worker_peak,
            margin_bytes=margin,
            estimated_bytes=estimated,
            total_memory_bytes=None,
            max_fraction=float(config.execution.max_estimated_memory_fraction),
            limit_bytes=None,
            allowed=True,
            override=use_override,
            reason="total_memory_unavailable",
        )
    limit = int(
        float(total_memory_bytes)
        * float(config.execution.max_estimated_memory_fraction)
    )
    within = estimated <= limit
    if within:
        reason = "within_limit"
        allowed = True
    elif use_override:
        reason = "override_above_limit"
        allowed = True
    elif config.execution.require_override_above_limit:
        reason = "refused_above_limit"
        allowed = False
    else:
        reason = "above_limit_override_not_required"
        allowed = True
    return MemoryPreflight(
        workers=workers,
        parent_rss_bytes=parent,
        worker_peak_rss_bytes=worker_peak,
        margin_bytes=margin,
        estimated_bytes=estimated,
        total_memory_bytes=int(total_memory_bytes),
        max_fraction=float(config.execution.max_estimated_memory_fraction),
        limit_bytes=limit,
        allowed=allowed,
        override=use_override,
        reason=reason,
    )


def assert_preflight_allowed(report: MemoryPreflight) -> None:
    """Raise when a preflight report forbids launch."""
    if not report.allowed:
        raise ProductionPreflightError(
            "estimated memory "
            f"{report.estimated_bytes} exceeds "
            f"{report.max_fraction:.0%} of total "
            f"{report.total_memory_bytes}; pass execution.memory_override: true "
            "to start anyway"
        )
