"""Hashed canonical span registry for V3.6D."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from inequality_mechanisms.mechanisms.span_synthesis import (
    PRIMARY_CERTIFICATE,
    SYNTHESIS_SEED,
    CanonicalSynthesisResult,
    reconstruct_bar,
    reconstruct_branch,
    synthesize_span_family,
)

REGISTRY_SCHEMA_VERSION = "v3.6d.span_registry.v1"
TARGET_SPANS_DEG = (95.0, 135.0, 145.0, 150.0, 175.0)


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def content_hash(payload: Mapping[str, Any]) -> str:
    """Return SHA-256 of canonical JSON."""
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SpanRegistry:
    """One typed outcome per unique target span."""

    schema_version: str
    seed: int
    certificate_profile: Mapping[str, Any]
    records: tuple[CanonicalSynthesisResult, ...]
    sha256: str

    def record_for(self, span_deg: float) -> CanonicalSynthesisResult:
        """Return the unique record for ``span_deg``."""
        matches = [
            row for row in self.records if abs(row.target_span_deg - float(span_deg)) < 1e-9
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one registry row for span {span_deg}, got {len(matches)}")
        return matches[0]

    def scientific_spans(self) -> tuple[float, ...]:
        """Return target spans that are not the legacy 78-degree fixture."""
        return tuple(row.target_span_deg for row in self.records)

    def to_dict(self) -> dict[str, Any]:
        """Serialize including the content hash."""
        body = {
            "schema_version": self.schema_version,
            "seed": int(self.seed),
            "certificate_profile": dict(self.certificate_profile),
            "records": [row.to_dict() for row in self.records],
        }
        return {**body, "sha256": content_hash(body)}

    def verify_hash(self) -> None:
        """Refuse a silently mutated registry."""
        payload = self.to_dict()
        if payload["sha256"] != self.sha256:
            raise ValueError("span registry hash mismatch")


_REGISTRY_CACHE: dict[int, SpanRegistry] = {}


def build_span_registry(*, seed: int = SYNTHESIS_SEED) -> SpanRegistry:
    """Synthesize the five-span family and attach a content hash."""
    cached = _REGISTRY_CACHE.get(int(seed))
    if cached is not None:
        return cached
    family = synthesize_span_family(TARGET_SPANS_DEG, seed=seed)
    records = tuple(family[float(span)] for span in TARGET_SPANS_DEG)
    body = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "seed": int(seed),
        "certificate_profile": PRIMARY_CERTIFICATE.to_dict(),
        "records": [row.to_dict() for row in records],
    }
    registry = SpanRegistry(
        schema_version=REGISTRY_SCHEMA_VERSION,
        seed=int(seed),
        certificate_profile=PRIMARY_CERTIFICATE.to_dict(),
        records=records,
        sha256=content_hash(body),
    )
    registry.verify_hash()
    _REGISTRY_CACHE[int(seed)] = registry
    return registry


def load_span_registry(payload: Mapping[str, Any]) -> SpanRegistry:
    """Load a registry dict and verify its hash."""
    from inequality_mechanisms.mechanisms.span_ranges import OutputRangeDefinition
    from inequality_mechanisms.mechanisms.span_synthesis import CanonicalSynthesisResult

    records: list[CanonicalSynthesisResult] = []
    for row in payload["records"]:
        ranges = row.get("range_definition")
        records.append(
            CanonicalSynthesisResult(
                target_span_deg=float(row["target_span_deg"]),
                status=row["status"],
                certificate_profile_name=str(row["certificate_profile_name"]),
                seed=int(row["seed"]),
                lengths=None if row["lengths"] is None else tuple(row["lengths"]),
                branch_sign=row["branch_sign"],
                range_definition=(
                    None if ranges is None else OutputRangeDefinition.from_dict(ranges)
                ),
                u_interval_rad=(
                    None
                    if row["u_interval_rad"] is None
                    else tuple(row["u_interval_rad"])
                ),
                q_native_interval_rad=(
                    None
                    if row["q_native_interval_rad"] is None
                    else tuple(row["q_native_interval_rad"])
                ),
                q_offset_rad=row["q_offset_rad"],
                min_abs_dq_du=row["min_abs_dq_du"],
                max_abs_dq_du=row["max_abs_dq_du"],
                mean_abs_dq_du=row["mean_abs_dq_du"],
                std_abs_dq_du=row["std_abs_dq_du"],
                endpoint_gains=(
                    None if row["endpoint_gains"] is None else tuple(row["endpoint_gains"])
                ),
                worst_certified_margin=row["worst_certified_margin"],
                span_error_deg=row["span_error_deg"],
                rejected_candidate_count=int(row["rejected_candidate_count"]),
                evaluated_candidate_count=int(row["evaluated_candidate_count"]),
                failure_reason=row.get("failure_reason"),
            )
        )
    body = {
        "schema_version": payload["schema_version"],
        "seed": int(payload["seed"]),
        "certificate_profile": dict(payload["certificate_profile"]),
        "records": [row.to_dict() for row in records],
    }
    digest = content_hash(body)
    if digest != str(payload["sha256"]):
        raise ValueError("span registry hash mismatch")
    return SpanRegistry(
        schema_version=str(payload["schema_version"]),
        seed=int(payload["seed"]),
        certificate_profile=dict(payload["certificate_profile"]),
        records=tuple(records),
        sha256=digest,
    )


__all__ = [
    "REGISTRY_SCHEMA_VERSION",
    "SpanRegistry",
    "TARGET_SPANS_DEG",
    "build_span_registry",
    "content_hash",
    "load_span_registry",
    "reconstruct_bar",
    "reconstruct_branch",
]
