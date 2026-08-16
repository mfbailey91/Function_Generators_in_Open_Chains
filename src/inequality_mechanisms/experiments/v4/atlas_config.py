"""Strict frozen configuration for the V4.1 planar-2R geometry atlas."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inequality_mechanisms.audits.v4_artifact_guard import V4_1_ALLOWED_OUTPUT_REL

SCHEMA_VERSION = "v4.1.planar2r_geometry_atlas.v1"
NO_INFERENCE_STATEMENT = (
    "intrinsic geometry atlas; no mechanism performance inference."
)
DEFAULT_CONFIG_REL = Path("configs") / "v4" / "planar2r_geometry_atlas_v1.json"
RANK_POLICY_DEFAULT = "default_scale_aware"
MECHANISM_PAIR_ID = "planar2r_crank_rocker_span_identity_v1"


class V4AtlasConfigError(ValueError):
    """Raised when a V4.1 atlas config fails strict validation."""


class FourBarAtlasConfig(BaseModel):
    """Canonical crank-rocker lengths and assembly branch."""

    model_config = ConfigDict(extra="forbid")

    a: float = Field(gt=0.0)
    b: float = Field(gt=0.0)
    c: float = Field(gt=0.0)
    d: float = Field(gt=0.0)
    branch: int = 1


class Planar2RAtlasConfig(BaseModel):
    """Planar 2R link lengths."""

    model_config = ConfigDict(extra="forbid")

    L1: float = Field(gt=0.0)
    L2: float = Field(gt=0.0)


class GridAtlasConfig(BaseModel):
    """Deterministic shared-Q grid."""

    model_config = ConfigDict(extra="forbid")

    shape: tuple[int, int]
    inset_fraction: float = Field(gt=0.0, lt=0.5)

    @field_validator("shape")
    @classmethod
    def _odd_positive_shape(cls, value: tuple[int, int]) -> tuple[int, int]:
        if len(value) != 2:
            raise ValueError("grid.shape must have two integers")
        n0, n1 = int(value[0]), int(value[1])
        if n0 < 3 or n1 < 3 or n0 % 2 == 0 or n1 % 2 == 0:
            raise ValueError("grid.shape must be odd integers >= 3")
        return (n0, n1)


class Planar2RGeometryAtlasConfig(BaseModel):
    """Frozen V4.1 atlas experiment contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v4.1.planar2r_geometry_atlas.v1"]
    output_dir: str
    fourbar: FourBarAtlasConfig
    branch_policy: Literal["monotonic_interval"]
    matching_rule: Literal["span"]
    planar2r: Planar2RAtlasConfig
    actuator_weight: Literal["identity"]
    rank_tolerance_policy: Literal["default_scale_aware"]
    grid: GridAtlasConfig
    no_inference_statement: str
    mechanism_pair_id: str = MECHANISM_PAIR_ID

    @field_validator("output_dir")
    @classmethod
    def _output_is_v4_1_root(cls, value: str) -> str:
        rel = Path(value)
        if rel != V4_1_ALLOWED_OUTPUT_REL:
            raise ValueError(
                "output_dir must be "
                f"{V4_1_ALLOWED_OUTPUT_REL.as_posix()!r}, got {value!r}"
            )
        return rel.as_posix()

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
    def _canonical_pair(self) -> Planar2RGeometryAtlasConfig:
        fb = self.fourbar
        if (fb.a, fb.b, fb.c, fb.d, fb.branch) != (1.0, 2.5, 2.0, 2.0, 1):
            raise ValueError("fourbar must be the canonical crank-rocker (1, 2.5, 2, 2)")
        if (self.planar2r.L1, self.planar2r.L2) != (1.0, 1.0):
            raise ValueError("planar2r lengths must be (1.0, 1.0)")
        if self.grid.shape != (33, 33):
            raise ValueError("grid.shape must be [33, 33] for this frozen config")
        return self

    def canonical_json(self) -> str:
        """Return a stable JSON encoding for digests."""
        return json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        """SHA-256 of the canonical JSON encoding."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def load_atlas_config(path: Path | str) -> Planar2RGeometryAtlasConfig:
    """Load and strictly validate a V4.1 atlas config JSON file."""
    payload_path = Path(path)
    try:
        raw = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V4AtlasConfigError(f"invalid JSON in {payload_path}: {exc}") from exc
    try:
        return Planar2RGeometryAtlasConfig.model_validate(raw)
    except Exception as exc:
        raise V4AtlasConfigError(str(exc)) from exc
