"""Frozen free-space Cartesian task bank loader (Sprint V3.6 / V3-601)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
    SamplingSmokeArm,
    build_paired_arms,
)
from inequality_mechanisms.core.constraints import ConstraintSet
from inequality_mechanisms.core.goals import CartesianDiskGoal
from inequality_mechanisms.core.local_motion import InputLinearMotion
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.scene import FreeSpaceScene
from inequality_mechanisms.core.state import PhysicalState

MechanismName = Literal["fourbar", "gearbox"]

DEFAULT_BANK_PATH = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "v3"
    / "free_space_planar2r_v1.json"
)


@dataclass(frozen=True, slots=True)
class FreeSpaceBankTask:
    """One external Cartesian disk task from the frozen bank."""

    task_id: str
    start_u_frac: tuple[float, float]
    goal_center: NDArray[np.float64]
    goal_radius: float
    notes: str = ""


@dataclass(frozen=True, slots=True)
class FreeSpaceTaskBank:
    """Loaded free-space bank metadata and tasks."""

    bank_id: str
    schema_version: int
    description: str
    L1: float
    L2: float
    mechanisms: tuple[MechanismName, ...]
    size_bins: dict[str, tuple[float, float | None]]
    tasks: tuple[FreeSpaceBankTask, ...]
    source_path: Path


def default_bank_path() -> Path:
    """Return the repository path to ``free_space_planar2r_v1.json``."""
    return DEFAULT_BANK_PATH


def load_free_space_bank(path: Path | None = None) -> FreeSpaceTaskBank:
    """Load and validate the frozen free-space Cartesian bank."""
    bank_path = Path(path) if path is not None else default_bank_path()
    raw = json.loads(bank_path.read_text(encoding="utf-8"))
    if int(raw.get("schema_version", -1)) != 1:
        raise ValueError(f"unsupported bank schema_version in {bank_path}")
    bins_raw = dict(raw["size_strata_bins_tip_distance"])
    size_bins: dict[str, tuple[float, float | None]] = {}
    for name, pair in bins_raw.items():
        lo = float(pair[0])
        hi = None if pair[1] is None else float(pair[1])
        size_bins[str(name)] = (lo, hi)
    tasks: list[FreeSpaceBankTask] = []
    for item in raw["tasks"]:
        tasks.append(
            FreeSpaceBankTask(
                task_id=str(item["task_id"]),
                start_u_frac=(
                    float(item["start_u_frac"][0]),
                    float(item["start_u_frac"][1]),
                ),
                goal_center=np.asarray(item["goal_center"], dtype=np.float64),
                goal_radius=float(item["goal_radius"]),
                notes=str(item.get("notes", "")),
            )
        )
    mechanisms = tuple(str(m) for m in raw["mechanisms"])  # type: ignore[assignment]
    return FreeSpaceTaskBank(
        bank_id=str(raw["bank_id"]),
        schema_version=int(raw["schema_version"]),
        description=str(raw.get("description", "")),
        L1=float(raw["robot"]["L1"]),
        L2=float(raw["robot"]["L2"]),
        mechanisms=mechanisms,  # type: ignore[arg-type]
        size_bins=size_bins,
        tasks=tuple(tasks),
        source_path=bank_path.resolve(),
    )


def build_bank_arms(bank: FreeSpaceTaskBank) -> dict[MechanismName, SamplingSmokeArm]:
    """Build paired mechanism arms matching the bank FK lengths."""
    return build_paired_arms(L1=bank.L1, L2=bank.L2)


def state_from_u_frac(
    arm: SamplingSmokeArm, frac: tuple[float, float]
) -> PhysicalState:
    """Map a unit-box fraction to a certified actuator state."""
    cert = arm.branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    u = u_lo + np.asarray(frac, dtype=np.float64) * (u_hi - u_lo)
    return arm.robot.state_from_input(u)


def build_cartesian_problem(
    arm: SamplingSmokeArm,
    task: FreeSpaceBankTask,
    *,
    local_motion: Any | None = None,
) -> PlanningProblem:
    """Build an exact-start Cartesian disk ``PlanningProblem`` for ``task``."""
    start = state_from_u_frac(arm, task.start_u_frac)
    goal = CartesianDiskGoal(
        center=task.goal_center.copy(),
        radius=task.goal_radius,
        robot=arm.robot,
    )
    motion = local_motion
    if motion is None:
        motion = InputLinearMotion(robot=arm.robot, n_samples=12)
    return PlanningProblem(
        robot=arm.robot,
        scene=FreeSpaceScene(robot=arm.robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=motion,
        objective=ActuatorTravelObjective(),
    )


__all__ = [
    "DEFAULT_BANK_PATH",
    "FreeSpaceBankTask",
    "FreeSpaceTaskBank",
    "build_bank_arms",
    "build_cartesian_problem",
    "default_bank_path",
    "load_free_space_bank",
    "state_from_u_frac",
]
