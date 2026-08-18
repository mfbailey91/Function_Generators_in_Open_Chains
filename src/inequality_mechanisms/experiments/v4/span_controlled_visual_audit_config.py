"""Strict frozen configuration for the V4.2A span-controlled visual audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from inequality_mechanisms.audits.planar2r_visual import AuditConfig
from inequality_mechanisms.audits.v4_artifact_guard import V4_2A_ALLOWED_OUTPUT_REL
from inequality_mechanisms.experiments.v4.atlas_config import Planar2RAtlasConfig
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    FROZEN_V3_6D_DIGEST,
    FROZEN_V3_6D_REGISTRY_REL,
    SPAN_175_STATUS,
)

SCHEMA_VERSION = "v4.2a.planar2r.span_controlled_visual_audit.v1"
DEFAULT_CONFIG_REL = Path("configs") / "v4" / "planar2r_span_controlled_visual_audit_v1.json"
NO_INFERENCE_STATEMENT = (
    "This audit does not support inferential statistics, stochastic repetition "
    "estimates, or ranking mechanisms by a hidden composite. Static print panels "
    "are authoritative; animations are supplementary. Failures remain in the "
    "report; tasks are not replaced after seeing outcomes."
)
FROZEN_TASK_IDS = (
    "near_0",
    "near_1",
    "near_2",
    "near_3",
    "near_4",
    "far_0",
    "far_1",
    "far_2",
    "far_3",
    "far_4",
)
FROZEN_PLANNERS = (
    "input_linear",
    "output_linear",
    "lattice_dijkstra",
    "lattice_astar",
    "prm",
    "rrt_connect",
    "ompl_prm",
    "ompl_rrt_connect",
)
FORBIDDEN_CONFIG_KEYS = frozenset({"gravity", "payload"})


class V4SpanVisualAuditConfigError(ValueError):
    """Raised when a V4.2A visual-audit config fails strict validation."""


def _walk_forbidden_keys(payload: Any, *, path: str = "") -> None:
    """Refuse gravity/payload keys anywhere in the raw JSON."""
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_s = str(key)
            here = f"{path}.{key_s}" if path else key_s
            lowered = key_s.lower()
            if key_s in FORBIDDEN_CONFIG_KEYS or any(
                token in lowered for token in FORBIDDEN_CONFIG_KEYS
            ):
                raise V4SpanVisualAuditConfigError(
                    f"forbidden config key {key_s!r} at {here}"
                )
            _walk_forbidden_keys(value, path=here)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _walk_forbidden_keys(value, path=f"{path}[{index}]")


class SourceBankAuditConfig(BaseModel):
    """Frozen V3.6 v2 bank pointer."""

    model_config = ConfigDict(extra="forbid")

    contract_path: str
    bank_id: Literal["free_space_planar2r_v2"]
    reuse_only: Literal[True]
    do_not_edit: Literal[True]


class LatticeVisualAuditConfig(BaseModel):
    """Audit lattice; not a scientific convergence grid."""

    model_config = ConfigDict(extra="forbid")

    shape: tuple[int, int]
    connectivity: Literal["chebyshev_1"]
    edge_cost_mode: Literal["integrated"]
    edge_n_samples: int
    note: str


class SpanControlledVisualAuditConfig(BaseModel):
    """Frozen V4.2A span-controlled visual-audit contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v4.2a.planar2r.span_controlled_visual_audit.v1"]
    output_dir: str
    v3_6d_registry: str
    v3_6d_digest_lock: str
    matching_rule: Literal["span"]
    span_175_status: Literal["boundary_stress_only"]
    planar2r: Planar2RAtlasConfig
    audit_id: str
    description: str
    no_inference_statement: str
    source_bank: SourceBankAuditConfig
    task_ids: tuple[str, ...]
    seed: int
    lattice: LatticeVisualAuditConfig
    planners: tuple[str, ...]
    planner_settings: dict[str, Any]
    animation_policy: dict[str, Any]
    delta_convention: dict[str, Any]
    composite_diagnostic: dict[str, Any]

    @field_validator("output_dir")
    @classmethod
    def _output_is_v4_2a_root(cls, value: str) -> str:
        rel = Path(value)
        if rel != V4_2A_ALLOWED_OUTPUT_REL:
            raise ValueError(
                "output_dir must be "
                f"{V4_2A_ALLOWED_OUTPUT_REL.as_posix()!r}, got {value!r}"
            )
        return rel.as_posix()

    @field_validator("v3_6d_registry")
    @classmethod
    def _registry_is_frozen_d(cls, value: str) -> str:
        rel = Path(value)
        if rel != FROZEN_V3_6D_REGISTRY_REL:
            raise ValueError(
                "v3_6d_registry must be "
                f"{FROZEN_V3_6D_REGISTRY_REL.as_posix()!r}, got {value!r}"
            )
        return rel.as_posix()

    @field_validator("v3_6d_digest_lock")
    @classmethod
    def _digest_is_frozen(cls, value: str) -> str:
        digest = str(value).strip().lower()
        if digest != FROZEN_V3_6D_DIGEST:
            raise ValueError(
                "v3_6d_digest_lock must equal the committed V3.6D registry "
                f"sha256 {FROZEN_V3_6D_DIGEST}, got {value!r}"
            )
        return digest

    @field_validator("no_inference_statement")
    @classmethod
    def _statement_forbids_ranking(cls, value: str) -> str:
        text = str(value).strip()
        if text != NO_INFERENCE_STATEMENT:
            raise ValueError(
                "no_inference_statement must be "
                f"{NO_INFERENCE_STATEMENT!r}, got {value!r}"
            )
        lowered = text.lower()
        for token in ("winner", "outperform", "estimand"):
            if token in lowered:
                raise ValueError("no_inference_statement contains ranking language")
        return text

    @model_validator(mode="after")
    def _frozen_audit_contract(self) -> SpanControlledVisualAuditConfig:
        if (self.planar2r.L1, self.planar2r.L2) != (1.0, 1.0):
            raise ValueError("planar2r lengths must be (1.0, 1.0)")
        if self.seed != 7:
            raise ValueError("audit seed must be frozen at 7")
        if tuple(self.task_ids) != FROZEN_TASK_IDS:
            raise ValueError("audit task_ids must be exactly the ten frozen V3.6B tasks")
        if tuple(self.planners) != FROZEN_PLANNERS:
            raise ValueError("audit planners must match the frozen V3.6B planner set")
        if self.lattice.shape != (32, 32):
            raise ValueError("lattice.shape must be [32, 32] for this frozen config")
        if self.span_175_status != SPAN_175_STATUS:
            raise ValueError(f"span_175_status must be {SPAN_175_STATUS!r}")
        return self

    def canonical_json(self) -> str:
        """Return a stable JSON encoding for digests."""
        return json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        """SHA-256 of the canonical JSON encoding."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def as_audit_config(self, path: Path) -> AuditConfig:
        """Return a V3.6B-compatible ``AuditConfig`` for the existing exporter."""
        raw = {
            "audit_id": self.audit_id,
            "schema_version": 1,
            "architecture_version": 4,
            "description": self.description,
            "no_inference_statement": self.no_inference_statement,
            "source_bank": self.source_bank.model_dump(),
            "task_ids": list(self.task_ids),
            "seed": self.seed,
            "lattice": self.lattice.model_dump(),
            "planners": list(self.planners),
            "planner_settings": dict(self.planner_settings),
            "animation_policy": dict(self.animation_policy),
            "delta_convention": dict(self.delta_convention),
            "composite_diagnostic": dict(self.composite_diagnostic),
            "artifact_contract": {
                "output_dir": self.output_dir,
            },
        }
        return AuditConfig(raw=raw, path=Path(path).resolve())


def load_span_visual_audit_config(path: Path | str) -> SpanControlledVisualAuditConfig:
    """Load and strictly validate a V4.2A visual-audit config JSON file."""
    payload_path = Path(path)
    try:
        raw = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V4SpanVisualAuditConfigError(
            f"invalid JSON in {payload_path}: {exc}"
        ) from exc
    try:
        _walk_forbidden_keys(raw)
        return SpanControlledVisualAuditConfig.model_validate(raw)
    except V4SpanVisualAuditConfigError:
        raise
    except Exception as exc:
        raise V4SpanVisualAuditConfigError(str(exc)) from exc
