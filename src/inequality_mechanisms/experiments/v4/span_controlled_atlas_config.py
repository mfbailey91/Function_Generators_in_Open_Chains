"""Strict frozen configuration for the V4.2 span-controlled geometry atlas."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from inequality_mechanisms.audits.v4_artifact_guard import V4_2_ALLOWED_OUTPUT_REL
from inequality_mechanisms.experiments.v4.atlas_config import (
    GridAtlasConfig,
    NO_INFERENCE_STATEMENT,
    Planar2RAtlasConfig,
)

SCHEMA_VERSION = "v4.2.planar2r.span_controlled_atlas.v1"
DEFAULT_CONFIG_REL = Path("configs") / "v4" / "planar2r_span_controlled_atlas_v1.json"
FROZEN_V3_6D_REGISTRY_REL = Path("results") / "v3_review" / "v3_6d_span_corpus" / "registry.json"
FROZEN_V3_6D_DIGEST = "456efd9f9472f8cee6271347e4e13bc750473bc186f752a254c526cc853296f0"
SPAN_175_STATUS = "boundary_stress_only"
FORBIDDEN_CONFIG_KEYS = frozenset({"gravity", "payload"})


class V4SpanAtlasConfigError(ValueError):
    """Raised when a V4.2 span-atlas config fails strict validation."""


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
                raise V4SpanAtlasConfigError(
                    f"forbidden config key {key_s!r} at {here}"
                )
            _walk_forbidden_keys(value, path=here)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _walk_forbidden_keys(value, path=f"{path}[{index}]")


class SpanControlledAtlasConfig(BaseModel):
    """Frozen V4.2 span-controlled atlas experiment contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v4.2.planar2r.span_controlled_atlas.v1"]
    output_dir: str
    v3_6d_registry: str
    v3_6d_digest_lock: str
    matching_rule: Literal["span"]
    planar2r: Planar2RAtlasConfig
    grid: GridAtlasConfig
    span_175_status: Literal["boundary_stress_only"]
    no_inference_statement: str
    rank_tolerance_policy: Literal["default_scale_aware"] = "default_scale_aware"

    @field_validator("output_dir")
    @classmethod
    def _output_is_v4_2_root(cls, value: str) -> str:
        rel = Path(value)
        if rel != V4_2_ALLOWED_OUTPUT_REL:
            raise ValueError(
                "output_dir must be "
                f"{V4_2_ALLOWED_OUTPUT_REL.as_posix()!r}, got {value!r}"
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
        for token in ("winner", "outperform", "ranking", "estimand"):
            if token in lowered:
                raise ValueError("no_inference_statement contains ranking language")
        return text

    @model_validator(mode="after")
    def _canonical_robot_grid(self) -> SpanControlledAtlasConfig:
        if (self.planar2r.L1, self.planar2r.L2) != (1.0, 1.0):
            raise ValueError("planar2r lengths must be (1.0, 1.0)")
        if self.grid.shape != (33, 33):
            raise ValueError("grid.shape must be [33, 33] for this frozen config")
        if self.grid.inset_fraction != 0.01:
            raise ValueError("grid.inset_fraction must be 0.01")
        return self

    def canonical_json(self) -> str:
        """Return a stable JSON encoding for digests."""
        return json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        """SHA-256 of the canonical JSON encoding."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def load_span_atlas_config(path: Path | str) -> SpanControlledAtlasConfig:
    """Load and strictly validate a V4.2 span-atlas config JSON file."""
    payload_path = Path(path)
    try:
        raw = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V4SpanAtlasConfigError(f"invalid JSON in {payload_path}: {exc}") from exc
    try:
        _walk_forbidden_keys(raw)
        return SpanControlledAtlasConfig.model_validate(raw)
    except V4SpanAtlasConfigError:
        raise
    except Exception as exc:
        raise V4SpanAtlasConfigError(str(exc)) from exc
