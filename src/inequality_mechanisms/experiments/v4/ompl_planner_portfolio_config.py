"""Strict Pydantic configuration for the V4.2C OMPL planner portfolio (V4-237)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inequality_mechanisms.audits.v4_2b_artifact import expected_case_ids
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_2B_ALLOWED_PACKAGE,
    V4_2C_ALLOWED_OUTPUT_REL,
)
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import (
    OPTIONAL_PLANNER_IDS,
    REQUIRED_PLANNER_IDS,
)
from inequality_mechanisms.experiments.v4.span_common_physical_bank import (
    FROZEN_TASK_IDS,
)

SCHEMA_VERSION = "v4.2c.ompl_planner_portfolio.v1"
CALIBRATION_SELECTION_SCHEMA = "v4.2c.ompl_planner_portfolio.calibration_selection.v1"
NO_INFERENCE_STATEMENT = (
    "OMPL planner-geometry portfolio; descriptive only; no mechanism "
    "performance inference."
)
FROZEN_V4_2B_GIT_TRACKED_SHA256 = (
    "31f2a141e42297223b21f647b5ad670d104382fc53b7abae4eface11e3977a8e"
)
FROZEN_V4_2B_GIT_TRACKED_N_FILES = 14098
FROZEN_V4_2B_FILES_DIGEST = (
    "ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a"
)
FROZEN_V4_2B_N_FILES = 23
FROZEN_V4_2B_N_GEOMETRY_ROWS = 55539
CONTROL_PLANNER_IDS = frozenset({"ompl_prm", "ompl_rrt_connect"})
PROJECTION_PLANNER_IDS = frozenset({"ompl_kpiece_u", "ompl_kpiece_q", "ompl_kpiece_x"})
PRIMARY_PLANNER_IDS = frozenset({"ompl_rrt_star", "ompl_bit_star", "ompl_fmt"})
MECHANISM_IDS: tuple[Literal["fourbar", "gearbox"], ...] = ("fourbar", "gearbox")
ModeName = Literal["smoke", "calibration", "audit", "all_cases_optional"]
StageName = Literal["stage_a", "stage_b", "stage_c", "all_cases_optional"]
MODE_STAGE: dict[str, StageName] = {
    "smoke": "stage_a",
    "calibration": "stage_b",
    "audit": "stage_c",
    "all_cases_optional": "all_cases_optional",
}
FORBIDDEN_CONFIG_KEYS = frozenset({"gravity", "payload"})
DEFAULT_SMOKE_CONFIG_REL = (
    Path("configs") / "v4" / "ompl_planner_portfolio_smoke_v1.json"
)
DEFAULT_CALIBRATION_CONFIG_REL = (
    Path("configs") / "v4" / "ompl_planner_portfolio_calibration_v1.json"
)
DEFAULT_AUDIT_CONFIG_REL = (
    Path("configs") / "v4" / "ompl_planner_portfolio_audit_v1.json"
)
SMOKE_CASE_IDS = ("span_j1_145_j2_145",)
SMOKE_TASK_IDS = ("near_0", "far_0")
CALIBRATION_CASE_IDS = (
    "span_j1_095_j2_095",
    "span_j1_145_j2_145",
    "span_j1_095_j2_145",
)
CALIBRATION_TASK_IDS = ("near_0", "near_1", "far_0", "far_1")
AUDIT_CASE_IDS = (
    "span_j1_095_j2_095",
    "span_j1_145_j2_145",
    "span_j1_175_j2_175",
    "span_j1_095_j2_175",
    "span_j1_145_j2_095",
)


class V4OmplPortfolioConfigError(ValueError):
    """Raised when a V4.2C planner-portfolio config fails strict validation."""

    failure_code = "v4_2c_portfolio_config_invalid"


def walk_forbidden_keys(payload: Any, *, path: str = "") -> None:
    """Refuse gravity/payload keys anywhere in the raw JSON."""
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_s = str(key)
            here = f"{path}.{key_s}" if path else key_s
            lowered = key_s.lower()
            if key_s in FORBIDDEN_CONFIG_KEYS or any(
                token in lowered for token in FORBIDDEN_CONFIG_KEYS
            ):
                raise V4OmplPortfolioConfigError(
                    f"forbidden config key {key_s!r} at {here}"
                )
            walk_forbidden_keys(value, path=here)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            walk_forbidden_keys(value, path=f"{path}[{index}]")


class PhysicalContract(BaseModel):
    """Frozen physical planning contract shared by every portfolio row."""

    model_config = ConfigDict(extra="forbid")

    state_coordinates: Literal["authoritative_u"]
    local_motion: Literal["input_linear"]
    objective: Literal["actuator_travel_euclidean_u"]
    goal_representation: Literal["frozen_finite_physical_goal_set"]


class SourceLock(BaseModel):
    """V4.2B predecessor lock. Writers must not mutate the frozen package."""

    model_config = ConfigDict(extra="forbid")

    v4_2b_package: Literal["v4_2b_span_controlled_corrective_closeout"]
    v4_2b_git_tracked_sha256: str
    v4_2b_git_tracked_n_files: int = Field(gt=0)
    v4_2b_files_digest: str
    v4_2b_n_files: int = Field(gt=0)
    v4_2b_n_geometry_rows: int = Field(gt=0)

    @field_validator("v4_2b_git_tracked_sha256", "v4_2b_files_digest")
    @classmethod
    def _hex_digest(cls, value: str) -> str:
        digest = str(value).strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("digest must be a 64-char lowercase hex sha256")
        return digest

    @model_validator(mode="after")
    def _matches_frozen_closeout(self) -> SourceLock:
        if self.v4_2b_package != V4_2B_ALLOWED_PACKAGE:
            raise ValueError(f"v4_2b_package must be {V4_2B_ALLOWED_PACKAGE!r}")
        if self.v4_2b_git_tracked_sha256 != FROZEN_V4_2B_GIT_TRACKED_SHA256:
            raise ValueError("v4_2b_git_tracked_sha256 does not match the freeze lock")
        if self.v4_2b_git_tracked_n_files != FROZEN_V4_2B_GIT_TRACKED_N_FILES:
            raise ValueError("v4_2b_git_tracked_n_files does not match the freeze lock")
        if self.v4_2b_files_digest != FROZEN_V4_2B_FILES_DIGEST:
            raise ValueError("v4_2b_files_digest does not match verify_v4_2b_artifact")
        if self.v4_2b_n_files != FROZEN_V4_2B_N_FILES:
            raise ValueError("v4_2b_n_files does not match verify_v4_2b_artifact")
        if self.v4_2b_n_geometry_rows != FROZEN_V4_2B_N_GEOMETRY_ROWS:
            raise ValueError(
                "v4_2b_n_geometry_rows does not match verify_v4_2b_artifact"
            )
        return self


class PlannerSpec(BaseModel):
    """Typed nested settings for one portfolio planner ID."""

    model_config = ConfigDict(extra="forbid")

    planner_id: str
    role: Literal["primary", "control", "projection", "optional"]
    enabled: bool = True
    required: bool = True
    solve_time_s: float = Field(gt=0.0)
    range_fraction: float | None = Field(default=None, gt=0.0)
    range_u: float | None = Field(default=None, gt=0.0)
    goal_bias: float | None = Field(default=None, ge=0.0, le=1.0)
    rewire_factor: float | None = Field(default=None, gt=0.0)
    num_samples: int | None = Field(default=None, ge=1)
    samples_per_batch: int | None = Field(default=None, ge=1)
    cells_per_axis: int | None = Field(default=None, ge=1)
    checkpoints_s: tuple[float, ...] | None = None
    max_nearest_neighbors: int | None = Field(default=None, ge=1)
    k_nearest: bool | None = None
    delay_cc: bool | None = None
    border_fraction: float | None = Field(default=None, gt=0.0, le=1.0)
    min_valid_path_fraction: float | None = Field(default=None, gt=0.0, le=1.0)

    @field_validator("planner_id")
    @classmethod
    def _known_planner(cls, value: str) -> str:
        allowed = set(REQUIRED_PLANNER_IDS) | set(OPTIONAL_PLANNER_IDS)
        if value not in allowed:
            raise ValueError(f"unknown planner_id {value!r}")
        return value

    @field_validator("checkpoints_s")
    @classmethod
    def _increasing_checkpoints(
        cls, value: tuple[float, ...] | None
    ) -> tuple[float, ...] | None:
        if value is None:
            return None
        times = tuple(float(t) for t in value)
        if not times or any(t < 0.0 for t in times):
            raise ValueError("checkpoints_s must be nonnegative and nonempty")
        if any(times[i] <= times[i - 1] for i in range(1, len(times))):
            raise ValueError("checkpoints_s must be strictly increasing")
        return times

    @model_validator(mode="after")
    def _role_matches_family(self) -> PlannerSpec:
        planner_id = self.planner_id
        if planner_id in CONTROL_PLANNER_IDS and self.role != "control":
            raise ValueError(f"{planner_id} role must be 'control'")
        if planner_id in PRIMARY_PLANNER_IDS and self.role != "primary":
            raise ValueError(f"{planner_id} role must be 'primary'")
        if planner_id in PROJECTION_PLANNER_IDS and self.role != "projection":
            raise ValueError(f"{planner_id} role must be 'projection'")
        if planner_id in OPTIONAL_PLANNER_IDS:
            if self.role != "optional":
                raise ValueError(f"{planner_id} role must be 'optional'")
            if self.required:
                raise ValueError(f"{planner_id} cannot be required")
        if planner_id == "ompl_fmt" and self.checkpoints_s is not None:
            raise ValueError("ompl_fmt cannot declare optimizer checkpoints_s")
        if planner_id in CONTROL_PLANNER_IDS | PROJECTION_PLANNER_IDS:
            if self.checkpoints_s is not None:
                raise ValueError(f"{planner_id} cannot declare optimizer checkpoints_s")
        if self.required and not self.enabled:
            raise ValueError(f"{planner_id} is required but disabled")
        return self

    def worker_params(self) -> dict[str, Any]:
        """Return JSON planner_params for the process worker."""
        payload: dict[str, Any] = {"solve_time_s": float(self.solve_time_s)}
        optional = {
            "range_fraction": self.range_fraction,
            "range_u": self.range_u,
            "goal_bias": self.goal_bias,
            "rewire_factor": self.rewire_factor,
            "num_samples": self.num_samples,
            "samples_per_batch": self.samples_per_batch,
            "cells_per_axis": self.cells_per_axis,
            "checkpoints_s": (
                list(self.checkpoints_s) if self.checkpoints_s is not None else None
            ),
            "max_nearest_neighbors": self.max_nearest_neighbors,
            "delay_cc": self.delay_cc,
            "border_fraction": self.border_fraction,
            "min_valid_path_fraction": self.min_valid_path_fraction,
        }
        for key, value in optional.items():
            if value is not None:
                payload[key] = value
        if self.k_nearest is not None:
            if self.planner_id == "ompl_bit_star":
                payload["use_k_nearest"] = self.k_nearest
            elif self.planner_id == "ompl_fmt":
                payload["nearest_k"] = self.k_nearest
            else:
                payload["k_nearest"] = self.k_nearest
        return payload


class PlannersConfig(BaseModel):
    """Explicit per-ID planner block. Unknown IDs are forbidden."""

    model_config = ConfigDict(extra="forbid")

    ompl_prm: PlannerSpec
    ompl_rrt_connect: PlannerSpec
    ompl_rrt_star: PlannerSpec
    ompl_bit_star: PlannerSpec
    ompl_fmt: PlannerSpec
    ompl_kpiece_u: PlannerSpec
    ompl_kpiece_q: PlannerSpec
    ompl_kpiece_x: PlannerSpec
    ompl_pdst_u: PlannerSpec

    def by_id(self) -> dict[str, PlannerSpec]:
        """Return planner specs keyed by planner_id."""
        return {
            spec.planner_id: spec
            for spec in (
                self.ompl_prm,
                self.ompl_rrt_connect,
                self.ompl_rrt_star,
                self.ompl_bit_star,
                self.ompl_fmt,
                self.ompl_kpiece_u,
                self.ompl_kpiece_q,
                self.ompl_kpiece_x,
                self.ompl_pdst_u,
            )
        }

    @model_validator(mode="after")
    def _ids_match_fields(self) -> PlannersConfig:
        mapping = {
            "ompl_prm": self.ompl_prm,
            "ompl_rrt_connect": self.ompl_rrt_connect,
            "ompl_rrt_star": self.ompl_rrt_star,
            "ompl_bit_star": self.ompl_bit_star,
            "ompl_fmt": self.ompl_fmt,
            "ompl_kpiece_u": self.ompl_kpiece_u,
            "ompl_kpiece_q": self.ompl_kpiece_q,
            "ompl_kpiece_x": self.ompl_kpiece_x,
            "ompl_pdst_u": self.ompl_pdst_u,
        }
        for expected_id, spec in mapping.items():
            if spec.planner_id != expected_id:
                raise ValueError(
                    f"planners.{expected_id}.planner_id must be {expected_id!r}"
                )
        return self


class OmplPlannerPortfolioConfig(BaseModel):
    """Frozen V4.2C staged-runner experiment contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v4.2c.ompl_planner_portfolio.v1"]
    mode: ModeName
    output_dir: str
    source: SourceLock
    case_ids: tuple[str, ...]
    task_ids: tuple[str, ...]
    mechanisms: tuple[Literal["fourbar", "gearbox"], ...]
    repetitions: int = Field(ge=1)
    seed_base: int
    physical_contract: PhysicalContract
    planners: PlannersConfig
    no_inference_statement: str
    calibration_selection_rel: str | None = None
    calibration_config_digest: str | None = None
    child_timeout_s: float = Field(gt=0.0)

    @field_validator("output_dir")
    @classmethod
    def _output_is_v4_2c_root(cls, value: str) -> str:
        rel = Path(value)
        if rel != V4_2C_ALLOWED_OUTPUT_REL:
            raise ValueError(
                "output_dir must be "
                f"{V4_2C_ALLOWED_OUTPUT_REL.as_posix()!r}, got {value!r}"
            )
        return rel.as_posix()

    @field_validator("case_ids")
    @classmethod
    def _known_cases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        ids = tuple(str(item) for item in value)
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("case_ids must be a nonempty unique tuple")
        allowed = set(expected_case_ids())
        unknown = [item for item in ids if item not in allowed]
        if unknown:
            raise ValueError(f"unknown V4.2B case_ids: {unknown}")
        return ids

    @field_validator("task_ids")
    @classmethod
    def _known_tasks(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        ids = tuple(str(item) for item in value)
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("task_ids must be a nonempty unique tuple")
        allowed = set(FROZEN_TASK_IDS)
        unknown = [item for item in ids if item not in allowed]
        if unknown:
            raise ValueError(f"unknown frozen task_ids: {unknown}")
        return ids

    @field_validator("mechanisms")
    @classmethod
    def _paired_mechanisms(
        cls, value: tuple[str, ...]
    ) -> tuple[Literal["fourbar", "gearbox"], ...]:
        ids = tuple(str(item) for item in value)
        if ids != MECHANISM_IDS:
            raise ValueError(f"mechanisms must be {MECHANISM_IDS!r}, got {ids!r}")
        return MECHANISM_IDS

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
    def _mode_corpus_and_audit_gate(self) -> OmplPlannerPortfolioConfig:
        if self.mode == "smoke":
            if tuple(self.case_ids) != SMOKE_CASE_IDS:
                raise ValueError(f"smoke case_ids must be {SMOKE_CASE_IDS!r}")
            if tuple(self.task_ids) != SMOKE_TASK_IDS:
                raise ValueError(f"smoke task_ids must be {SMOKE_TASK_IDS!r}")
            if self.repetitions != 1:
                raise ValueError("smoke repetitions must be 1")
        elif self.mode == "calibration":
            if tuple(self.case_ids) != CALIBRATION_CASE_IDS:
                raise ValueError(
                    f"calibration case_ids must be {CALIBRATION_CASE_IDS!r}"
                )
            if tuple(self.task_ids) != CALIBRATION_TASK_IDS:
                raise ValueError(
                    f"calibration task_ids must be {CALIBRATION_TASK_IDS!r}"
                )
            if self.repetitions < 5:
                raise ValueError("calibration repetitions must be >= 5")
        elif self.mode == "audit":
            if tuple(self.case_ids) != AUDIT_CASE_IDS:
                raise ValueError(f"audit case_ids must be {AUDIT_CASE_IDS!r}")
            if tuple(self.task_ids) != FROZEN_TASK_IDS:
                raise ValueError("audit task_ids must be the ten frozen bank tasks")
            if self.repetitions != 10:
                raise ValueError("audit repetitions must be 10")
            if not self.calibration_selection_rel:
                raise ValueError("audit mode requires calibration_selection_rel")
            if not self.calibration_config_digest:
                raise ValueError("audit mode requires calibration_config_digest")
        elif self.mode == "all_cases_optional":
            if tuple(self.case_ids) != expected_case_ids():
                raise ValueError(
                    "all_cases_optional case_ids must be the full V4.2B case list"
                )
        required_ids = [spec.planner_id for spec in self.enabled_required_planners()]
        if set(required_ids) != set(REQUIRED_PLANNER_IDS):
            raise ValueError("every required planner ID must be enabled")
        pdst = self.planners.ompl_pdst_u
        if pdst.enabled or pdst.required:
            raise ValueError("ompl_pdst_u stays disabled until optional PDST lands")
        return self

    def enabled_required_planners(self) -> tuple[PlannerSpec, ...]:
        """Return enabled required planner specs in stable ID order."""
        specs = []
        for planner_id in REQUIRED_PLANNER_IDS:
            spec = self.planners.by_id()[planner_id]
            if spec.enabled and spec.required:
                specs.append(spec)
        return tuple(specs)

    def stage_name(self) -> StageName:
        """Return the evidence-stage directory name for this mode."""
        return MODE_STAGE[self.mode]

    def canonical_json(self) -> str:
        """Return a stable JSON encoding for digests."""
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )

    def digest(self) -> str:
        """SHA-256 of the canonical JSON encoding."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def frozen_source_lock() -> SourceLock:
    """Return the committed V4.2B closeout lock used by every portfolio config."""
    return SourceLock(
        v4_2b_package="v4_2b_span_controlled_corrective_closeout",
        v4_2b_git_tracked_sha256=FROZEN_V4_2B_GIT_TRACKED_SHA256,
        v4_2b_git_tracked_n_files=FROZEN_V4_2B_GIT_TRACKED_N_FILES,
        v4_2b_files_digest=FROZEN_V4_2B_FILES_DIGEST,
        v4_2b_n_files=FROZEN_V4_2B_N_FILES,
        v4_2b_n_geometry_rows=FROZEN_V4_2B_N_GEOMETRY_ROWS,
    )


def load_ompl_portfolio_config(path: Path | str) -> OmplPlannerPortfolioConfig:
    """Load and strictly validate a V4.2C planner-portfolio config JSON file."""
    payload_path = Path(path)
    try:
        raw = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V4OmplPortfolioConfigError(
            f"invalid JSON in {payload_path}: {exc}"
        ) from exc
    try:
        walk_forbidden_keys(raw)
        return OmplPlannerPortfolioConfig.model_validate(raw)
    except V4OmplPortfolioConfigError:
        raise
    except Exception as exc:
        raise V4OmplPortfolioConfigError(str(exc)) from exc
