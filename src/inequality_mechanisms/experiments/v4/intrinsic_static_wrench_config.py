"""Strict V4.3 intrinsic static-wrench contracts (V4-300).

Schema identifiers chosen for this sprint:

* ``v4.3.intrinsic_static_wrench.config.v1``
* ``v4.3.intrinsic_static_wrench.source_lock.v1``
* ``v4.3.intrinsic_static_wrench.row.v2``
* ``v4.3.intrinsic_static_wrench.field_status.v1``
* ``v4.3.intrinsic_static_wrench.case_summary.v1``
* ``v4.3.intrinsic_static_wrench.manifest.v2``
* ``v4.3.intrinsic_static_wrench.package.v2``
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_2B_ALLOWED_PACKAGE,
    V4_3_ALLOWED_OUTPUT_REL,
    V4_3_ALLOWED_PACKAGE,
    V4_3_CORRECTIVE_OUTPUT_REL,
    V4_3_FOLLOWUP_OUTPUT_REL,
)

CONFIG_SCHEMA_VERSION: Final = "v4.3.intrinsic_static_wrench.config.v1"
SOURCE_LOCK_SCHEMA_VERSION: Final = "v4.3.intrinsic_static_wrench.source_lock.v1"
LEGACY_ROW_SCHEMA_VERSION: Final = "v4.3.intrinsic_static_wrench.row.v1"
ROW_SCHEMA_VERSION: Final = "v4.3.intrinsic_static_wrench.row.v2"
FIELD_STATUS_SCHEMA_VERSION = "v4.3.intrinsic_static_wrench.field_status.v1"
CASE_SUMMARY_SCHEMA_VERSION = "v4.3.intrinsic_static_wrench.case_summary.v1"
LEGACY_MANIFEST_SCHEMA_VERSION: Final = "v4.3.intrinsic_static_wrench.manifest.v1"
MANIFEST_SCHEMA_VERSION: Final = "v4.3.intrinsic_static_wrench.manifest.v2"
LEGACY_PACKAGE_SCHEMA_VERSION: Final = "v4.3.intrinsic_static_wrench.package.v1"
PACKAGE_SCHEMA_VERSION: Final = "v4.3.intrinsic_static_wrench.package.v2"

FROZEN_V4_2B_SOURCE_REVISION = "6680d648a0dc93d33f1cf34bb81cea69d6a44e80"
FROZEN_V4_2B_FILES_DIGEST = (
    "ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a"
)
FROZEN_V4_2B_CONFIG_DIGEST = (
    "ca632445469aa024c171fbc9d266ae58aeedf659e3ca3cbca5f16d70db1b6a9d"
)
FROZEN_V3_6D_REGISTRY_DIGEST = (
    "456efd9f9472f8cee6271347e4e13bc750473bc186f752a254c526cc853296f0"
)
FROZEN_V4_2B_N_FILES = 23
FROZEN_V4_2B_N_GEOMETRY_ROWS = 55539
FROZEN_V4_2B_N_ROWS_PER_ARM = 18513
FROZEN_V4_2B_N_CASES = 17
FROZEN_V4_2B_GRID = (33, 33)
FROZEN_MECHANISM_IDS: tuple[str, ...] = (
    "fourbar",
    "span_matched_gearbox",
    "identity_on_shared_q",
)
REQUIRED_OUTPUT_COORDINATE_KIND = "mounted_joint"
REQUIRED_MECHANISM_TYPES: dict[str, str] = {
    "fourbar": "mounted_output",
    "span_matched_gearbox": "equivalent_gearbox",
    "identity_on_shared_q": "unit_gearbox",
}

DEFAULT_TORQUE_LIMITS: tuple[float, float] = (1.0, 1.0)
TORQUE_UNITS: Final = "normalized_actuator_torque"
FORCE_UNITS: Final = "normalized_torque_per_length"

SMOKE_SPAN_PAIRS: tuple[tuple[int, int], ...] = (
    (95, 145),
    (145, 145),
    (135, 150),
    (175, 145),
)
SMOKE_GRID_INDICES: tuple[tuple[int, int], ...] = (
    (0, 0),
    (0, 16),
    (16, 16),
    (16, 32),
    (32, 32),
)
SMOKE_N_RECORDS = 60

FORBIDDEN_PHYSICS_KEYS = frozenset(
    {
        "gravity",
        "payload",
        "dynamics",
        "friction",
        "compliance",
        "contact",
        "structural_limit",
        "structural_limits",
    }
)
DEFAULT_CONFIG_REL = Path("configs") / "v4" / "intrinsic_static_wrench_v1.json"
NO_INFERENCE_STATEMENT = (
    "V4.3 intrinsic gravity-free static wrench on frozen V4.2B mounted-Q "
    "snapshots; descriptive only; not an application load rating."
)

FIELD_STATUS_VALUES = frozenset(
    {
        "finite",
        "unbounded",
        "undefined",
        "invalid",
        "masked_nonregular",
        "source_failure",
    }
)


class V4_3ConfigError(ValueError):
    """Raised when a V4.3 config or schema contract fails."""

    failure_code = "v4_3_config_invalid"


def walk_forbidden_keys(payload: Any, *, path: str = "") -> None:
    """Refuse unsupported physics keys anywhere in the raw JSON tree."""
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_s = str(key)
            here = f"{path}.{key_s}" if path else key_s
            lowered = key_s.lower()
            if key_s in FORBIDDEN_PHYSICS_KEYS or any(
                token in lowered for token in FORBIDDEN_PHYSICS_KEYS
            ):
                raise V4_3ConfigError(f"forbidden config key {key_s!r} at {here}")
            walk_forbidden_keys(value, path=here)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            walk_forbidden_keys(value, path=f"{path}[{index}]")


def walk_unknown_keys(
    payload: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    path: str = "",
) -> None:
    """Refuse unknown object keys at one nesting level."""
    for key in payload:
        key_s = str(key)
        here = f"{path}.{key_s}" if path else key_s
        if key_s not in allowed:
            raise V4_3ConfigError(f"unknown config key {key_s!r} at {here}")


class TorqueContract(BaseModel):
    """Unit actuator-effort budget for comparison, not rated motor torque."""

    model_config = ConfigDict(extra="forbid")

    limits: tuple[float, float] = DEFAULT_TORQUE_LIMITS
    units: Literal["normalized_actuator_torque"] = TORQUE_UNITS
    force_units: Literal["normalized_torque_per_length"] = FORCE_UNITS

    @field_validator("limits")
    @classmethod
    def _positive_finite(cls, value: tuple[float, float]) -> tuple[float, float]:
        if len(value) != 2:
            raise ValueError("torque limits must have length 2")
        for item in value:
            if not isinstance(item, (int, float)) or item <= 0.0:
                raise ValueError("torque limits must be positive")
            if item != item or item in (float("inf"), float("-inf")):
                raise ValueError("torque limits must be finite")
        return (float(value[0]), float(value[1]))


class SourceLock(BaseModel):
    """Pinned frozen V4.2B predecessor identities for V4.3 consumption."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v4.3.intrinsic_static_wrench.source_lock.v1"] = (
        SOURCE_LOCK_SCHEMA_VERSION
    )
    v4_2b_package: Literal["v4_2b_span_controlled_corrective_closeout"] = (
        V4_2B_ALLOWED_PACKAGE  # type: ignore[assignment]
    )
    source_revision: str = FROZEN_V4_2B_SOURCE_REVISION
    files_digest: str = FROZEN_V4_2B_FILES_DIGEST
    config_digest: str = FROZEN_V4_2B_CONFIG_DIGEST
    v3_6d_registry_digest: str = FROZEN_V3_6D_REGISTRY_DIGEST
    n_files: int = FROZEN_V4_2B_N_FILES
    n_geometry_rows: int = FROZEN_V4_2B_N_GEOMETRY_ROWS
    n_rows_per_arm: int = FROZEN_V4_2B_N_ROWS_PER_ARM
    n_cases: int = FROZEN_V4_2B_N_CASES
    grid: tuple[int, int] = FROZEN_V4_2B_GRID
    mechanisms: tuple[str, ...] = FROZEN_MECHANISM_IDS

    @field_validator(
        "source_revision",
        "files_digest",
        "config_digest",
        "v3_6d_registry_digest",
    )
    @classmethod
    def _hex_or_sha(cls, value: str) -> str:
        digest = str(value).strip().lower()
        if len(digest) not in (40, 64):
            raise ValueError("digest/revision must be 40- or 64-char hex")
        if any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("digest/revision must be lowercase hex")
        return digest

    @model_validator(mode="after")
    def _matches_freeze(self) -> SourceLock:
        if self.v4_2b_package != V4_2B_ALLOWED_PACKAGE:
            raise ValueError(f"v4_2b_package must be {V4_2B_ALLOWED_PACKAGE!r}")
        if self.source_revision != FROZEN_V4_2B_SOURCE_REVISION:
            raise ValueError("source_revision does not match the V4.3 freeze lock")
        if self.files_digest != FROZEN_V4_2B_FILES_DIGEST:
            raise ValueError("files_digest does not match the V4.3 freeze lock")
        if self.config_digest != FROZEN_V4_2B_CONFIG_DIGEST:
            raise ValueError("config_digest does not match the V4.3 freeze lock")
        if self.v3_6d_registry_digest != FROZEN_V3_6D_REGISTRY_DIGEST:
            raise ValueError(
                "v3_6d_registry_digest does not match the V4.3 freeze lock"
            )
        if self.n_files != FROZEN_V4_2B_N_FILES:
            raise ValueError("n_files does not match the V4.3 freeze lock")
        if self.n_geometry_rows != FROZEN_V4_2B_N_GEOMETRY_ROWS:
            raise ValueError("n_geometry_rows does not match the V4.3 freeze lock")
        if self.n_rows_per_arm != FROZEN_V4_2B_N_ROWS_PER_ARM:
            raise ValueError("n_rows_per_arm does not match the V4.3 freeze lock")
        if self.n_cases != FROZEN_V4_2B_N_CASES:
            raise ValueError("n_cases does not match the V4.3 freeze lock")
        if tuple(self.grid) != FROZEN_V4_2B_GRID:
            raise ValueError("grid does not match the V4.3 freeze lock")
        if tuple(self.mechanisms) != FROZEN_MECHANISM_IDS:
            raise ValueError("mechanisms do not match the V4.3 freeze lock")
        return self


class IntrinsicStaticWrenchConfig(BaseModel):
    """Validated V4.3 experiment configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v4.3.intrinsic_static_wrench.config.v1"] = (
        CONFIG_SCHEMA_VERSION
    )
    package: Literal["v4_3_intrinsic_static_wrench"] = V4_3_ALLOWED_PACKAGE  # type: ignore[assignment]
    output_dir: str
    source: SourceLock = Field(default_factory=SourceLock)
    torque: TorqueContract = Field(default_factory=TorqueContract)
    no_inference_statement: str = NO_INFERENCE_STATEMENT

    @field_validator("output_dir")
    @classmethod
    def _output_under_package(cls, value: str) -> str:
        rel = Path(value).as_posix().rstrip("/")
        # Historical configs remain readable; writers refuse frozen roots.
        allowed = {
            V4_3_ALLOWED_OUTPUT_REL.as_posix(),
            V4_3_CORRECTIVE_OUTPUT_REL.as_posix(),
            V4_3_FOLLOWUP_OUTPUT_REL.as_posix(),
        }
        if rel not in allowed:
            raise ValueError(
                f"output_dir must be one of {sorted(allowed)!r}, got {rel!r}"
            )
        return rel

    @model_validator(mode="after")
    def _package_name(self) -> IntrinsicStaticWrenchConfig:
        if self.package != V4_3_ALLOWED_PACKAGE:
            raise ValueError(f"package must be {V4_3_ALLOWED_PACKAGE!r}")
        return self

    def digest(self) -> str:
        """Stable SHA-256 of the canonical JSON encoding."""
        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_intrinsic_static_wrench_config(
    path: Path | str | None = None,
) -> IntrinsicStaticWrenchConfig:
    """Load and strictly validate a V4.3 config JSON file."""
    config_path = Path(path) if path is not None else Path(DEFAULT_CONFIG_REL)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V4_3ConfigError(f"failed to read config {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise V4_3ConfigError("config root must be a JSON object")
    walk_forbidden_keys(raw)
    try:
        return IntrinsicStaticWrenchConfig.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - surface as contract error
        raise V4_3ConfigError(f"invalid V4.3 config: {exc}") from exc


def schema_catalog() -> dict[str, str]:
    """Document the V4.3 schema identifiers chosen in V4-300."""
    return {
        "config": CONFIG_SCHEMA_VERSION,
        "source_lock": SOURCE_LOCK_SCHEMA_VERSION,
        "row": ROW_SCHEMA_VERSION,
        "field_status": FIELD_STATUS_SCHEMA_VERSION,
        "case_summary": CASE_SUMMARY_SCHEMA_VERSION,
        "manifest": MANIFEST_SCHEMA_VERSION,
        "package": PACKAGE_SCHEMA_VERSION,
    }


__all__ = [
    "CASE_SUMMARY_SCHEMA_VERSION",
    "CONFIG_SCHEMA_VERSION",
    "DEFAULT_CONFIG_REL",
    "DEFAULT_TORQUE_LIMITS",
    "FIELD_STATUS_SCHEMA_VERSION",
    "FIELD_STATUS_VALUES",
    "FORCE_UNITS",
    "FORBIDDEN_PHYSICS_KEYS",
    "FROZEN_MECHANISM_IDS",
    "FROZEN_V3_6D_REGISTRY_DIGEST",
    "FROZEN_V4_2B_CONFIG_DIGEST",
    "FROZEN_V4_2B_FILES_DIGEST",
    "FROZEN_V4_2B_GRID",
    "FROZEN_V4_2B_N_CASES",
    "FROZEN_V4_2B_N_FILES",
    "FROZEN_V4_2B_N_GEOMETRY_ROWS",
    "FROZEN_V4_2B_N_ROWS_PER_ARM",
    "FROZEN_V4_2B_SOURCE_REVISION",
    "IntrinsicStaticWrenchConfig",
    "LEGACY_MANIFEST_SCHEMA_VERSION",
    "LEGACY_PACKAGE_SCHEMA_VERSION",
    "LEGACY_ROW_SCHEMA_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "NO_INFERENCE_STATEMENT",
    "PACKAGE_SCHEMA_VERSION",
    "REQUIRED_MECHANISM_TYPES",
    "REQUIRED_OUTPUT_COORDINATE_KIND",
    "ROW_SCHEMA_VERSION",
    "SMOKE_GRID_INDICES",
    "SMOKE_N_RECORDS",
    "SMOKE_SPAN_PAIRS",
    "SOURCE_LOCK_SCHEMA_VERSION",
    "SourceLock",
    "TORQUE_UNITS",
    "TorqueContract",
    "V4_3ConfigError",
    "load_intrinsic_static_wrench_config",
    "schema_catalog",
    "walk_forbidden_keys",
    "walk_unknown_keys",
]
