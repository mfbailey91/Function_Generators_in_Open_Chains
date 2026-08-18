"""Strict V3.6D–F program config. Gravity keys are rejected, not defaulted."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inequality_mechanisms.audits.v3_span_wrench_guard import (
    V3_6D_ALLOWED_OUTPUT_REL,
    V3_6E_ALLOWED_PACKAGE,
    V3_6F_ALLOWED_PACKAGE,
)

SCHEMA_VERSION = "v3.planar2r.span_wrench_program.v1"
DEFAULT_CONFIG_REL = Path("configs") / "v3" / "planar2r_span_wrench_program_v1.json"
FORBIDDEN_GRAVITY_KEYS = (
    "gravity",
    "gravity_vector",
    "payload_mass",
    "gravity_compensation",
    "payload",
)
UNIQUE_TARGET_SPANS_DEG = (95.0, 135.0, 145.0, 150.0, 175.0)


class SpanWrenchConfigError(ValueError):
    """Raised when the span/wrench program config fails closed."""


def _reject_forbidden_keys(payload: Any, *, path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            joined = f"{path}.{key}" if path else str(key)
            if str(key) in FORBIDDEN_GRAVITY_KEYS:
                raise SpanWrenchConfigError(
                    f"gravity/payload field {joined!r} is outside the "
                    "gravity-free V3.6D–F model"
                )
            _reject_forbidden_keys(value, path=joined)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _reject_forbidden_keys(value, path=f"{path}[{index}]")


class ScopeConfig(BaseModel):
    """Declared included/excluded physics."""

    model_config = ConfigDict(extra="forbid")

    model: Literal["intrinsic_kinematic_geometry_static_virtual_work"]
    included: tuple[str, ...]
    excluded: tuple[str, ...]

    @field_validator("excluded")
    @classmethod
    def _gravity_excluded(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if "gravity" not in value or "payload" not in value:
            raise ValueError("scope.excluded must include gravity and payload")
        return value


class RobotConfig(BaseModel):
    """Planar 2R robot used by every span case."""

    model_config = ConfigDict(extra="forbid")

    kinematic_model: Literal["planar2r"]
    link_lengths: tuple[float, float]
    joint_centers_deg: tuple[float, float]

    @field_validator("link_lengths")
    @classmethod
    def _positive_links(cls, value: tuple[float, float]) -> tuple[float, float]:
        if len(value) != 2 or any(float(x) <= 0.0 for x in value):
            raise ValueError("robot.link_lengths must be two positive lengths")
        return (float(value[0]), float(value[1]))

    @field_validator("joint_centers_deg")
    @classmethod
    def _zero_centers(cls, value: tuple[float, float]) -> tuple[float, float]:
        if any(abs(float(x)) > 1e-12 for x in value):
            raise ValueError("V3.6D joint centers must be 0 deg")
        return (0.0, 0.0)


class SpanDefinitionsConfig(BaseModel):
    """Core and biological span sets."""

    model_config = ConfigDict(extra="forbid")

    core_span_sweep_deg: tuple[float, ...]
    biological_refinement_deg: tuple[float, ...]
    legacy_regression_span_approx_deg: float
    legacy_in_scientific_case_registry: bool

    @field_validator("legacy_in_scientific_case_registry")
    @classmethod
    def _legacy_excluded(cls, value: bool) -> bool:
        if value:
            raise ValueError("legacy 78-degree fixture must not enter the registry")
        return value


class SynthesisConfig(BaseModel):
    """Frozen synthesis contract."""

    model_config = ConfigDict(extra="forbid")

    unique_target_spans_deg: tuple[float, ...]
    target_is_usable_q_span: bool
    target_span_tolerance_deg: float = Field(gt=0.0)
    center_deg: float
    certificate_profile: str
    near_limit_policy: tuple[str, ...]
    deterministic_seed: int

    @field_validator("unique_target_spans_deg")
    @classmethod
    def _expected_targets(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        got = tuple(float(x) for x in value)
        if got != UNIQUE_TARGET_SPANS_DEG:
            raise ValueError(f"unique_target_spans_deg must be {UNIQUE_TARGET_SPANS_DEG}")
        return got

    @field_validator("center_deg")
    @classmethod
    def _zero_center(cls, value: float) -> float:
        if abs(float(value)) > 1e-12:
            raise ValueError("synthesis.center_deg must be 0")
        return 0.0

    @field_validator("target_is_usable_q_span")
    @classmethod
    def _usable_target(cls, value: bool) -> bool:
        if not value:
            raise ValueError("target must be usable Q span")
        return value


class CaseGroupConfig(BaseModel):
    """One ordered 3x3 span factorial."""

    model_config = ConfigDict(extra="forbid")

    j1_spans_deg: tuple[float, ...]
    j2_spans_deg: tuple[float, ...]


class CaseGroupsConfig(BaseModel):
    """Core and biological factorials."""

    model_config = ConfigDict(extra="forbid")

    core_span_sweep: CaseGroupConfig
    biological_refinement: CaseGroupConfig


class UniqueCaseConfig(BaseModel):
    """Planning-seed case identity. Implementation regenerates and checks these."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    span_j1_deg: float
    span_j2_deg: float
    memberships: tuple[str, ...]


class StaticWrenchConfig(BaseModel):
    """Planning-seed wrench contract retained for later sprints."""

    model_config = ConfigDict(extra="forbid")

    task_dimension: Literal[2]
    task_vector: tuple[str, str]
    normalized_actuator_torque_limits: tuple[float, float]
    primary_scalar: str
    directions: tuple[str, ...]
    exact_regular_representation: str
    rank_deficient_policy: str


class VisualizationConfig(BaseModel):
    """Planning-seed atlas views retained for later sprints."""

    model_config = ConfigDict(extra="forbid")

    default_view: str
    polygon_overlay: str
    paired_mechanism_shared_color_scale: bool
    source_values_clipped: bool
    show_physical_and_normalized_q_axes: bool


class ArtifactTargetsConfig(BaseModel):
    """Declared result lineages."""

    model_config = ConfigDict(extra="forbid")

    v3_6d: str
    v3_6e: str
    v3_6f: str

    @field_validator("v3_6d")
    @classmethod
    def _d_path(cls, value: str) -> str:
        expected = V3_6D_ALLOWED_OUTPUT_REL.as_posix() + "/"
        if value not in {expected, V3_6D_ALLOWED_OUTPUT_REL.as_posix()}:
            raise ValueError(f"artifact_targets.v3_6d must be {expected}")
        return expected

    @field_validator("v3_6e")
    @classmethod
    def _e_path(cls, value: str) -> str:
        if V3_6E_ALLOWED_PACKAGE not in value:
            raise ValueError("artifact_targets.v3_6e must name the E package")
        return value

    @field_validator("v3_6f")
    @classmethod
    def _f_path(cls, value: str) -> str:
        if V3_6F_ALLOWED_PACKAGE not in value:
            raise ValueError("artifact_targets.v3_6f must name the F package")
        return value


class Planar2RSpanWrenchProgramConfig(BaseModel):
    """Frozen V3.6D–F program configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v3.planar2r.span_wrench_program.v1"]
    program_id: Literal["v3_6d_to_v3_6f_span_wrench"]
    scope: ScopeConfig
    robot: RobotConfig
    span_definitions: SpanDefinitionsConfig
    synthesis: SynthesisConfig
    case_groups: CaseGroupsConfig
    unique_cases: tuple[UniqueCaseConfig, ...]
    static_wrench: StaticWrenchConfig
    visualization: VisualizationConfig
    artifact_targets: ArtifactTargetsConfig

    @model_validator(mode="after")
    def _seventeen_cases(self) -> Planar2RSpanWrenchProgramConfig:
        if len(self.unique_cases) != 17:
            raise ValueError("unique_cases must contain 17 planning-seed rows")
        return self


def load_span_wrench_program_config(path: Path) -> Planar2RSpanWrenchProgramConfig:
    """Parse JSON, reject gravity keys, and return the strict config."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    _reject_forbidden_keys(raw)
    try:
        return Planar2RSpanWrenchProgramConfig.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        raise SpanWrenchConfigError(str(exc)) from exc
