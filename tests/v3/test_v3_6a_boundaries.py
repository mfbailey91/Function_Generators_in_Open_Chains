"""Sprint V3.6A source-boundary and adapter checks (V3-617)."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.adapters.operating_branch_robot import (
    OperatingBranchRobotModel,
)
from inequality_mechanisms.benchmarks.synthetic_affine_3d import (
    AffineIdentityKinematics3D,
    synthetic_affine_3d_branch,
    synthetic_affine_3d_robot,
)
from inequality_mechanisms.planners import sampling_space


_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "inequality_mechanisms"


def _module_source(rel: str) -> str:
    return (_SRC_ROOT / rel).read_text(encoding="utf-8")


def _imported_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.add(module)
            for alias in node.names:
                names.add(alias.name)
                if module:
                    names.add(f"{module}.{alias.name}")
    return names


def test_core_goals_does_not_import_planar2r() -> None:
    source = _module_source("core/goals.py")
    assert "Planar2R" not in source
    imported = _imported_names(source)
    assert "Planar2R" not in imported
    assert "inequality_mechanisms.kinematics.planar_2r" not in imported
    assert "planar_2r" not in {
        part
        for name in imported
        for part in name.split(".")
        if part == "planar_2r"
    }


def test_sampling_space_actuator_bounds_no_branch_certificate() -> None:
    source = _module_source("planners/sampling_space.py")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "actuator_bounds":
            body_src = ast.get_source_segment(source, node) or ""
            assert ".branch.certificate" not in body_src
            assert "input_domain" in body_src
            break
    else:
        pytest.fail("actuator_bounds not found in sampling_space.py")

    # Runtime: robot without input_domain must fail closed.
    class _NoDomain:
        pass

    with pytest.raises(ValueError, match="input_domain"):
        sampling_space.actuator_bounds(_NoDomain())  # type: ignore[arg-type]


def test_operating_branch_robot_accepts_3dof_kinematic_fixture() -> None:
    robot = synthetic_affine_3d_robot()
    assert isinstance(robot, OperatingBranchRobotModel)
    assert robot.dof == 3
    assert isinstance(robot.kinematic_model, AffineIdentityKinematics3D)

    state = robot.state_from_input([0.0, 0.1, -0.1])
    tip = np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)
    assert tip.shape == (3,)
    np.testing.assert_allclose(tip, state.q)

    mismatched = AffineIdentityKinematics3D()
    branch2 = synthetic_affine_3d_branch()
    # dof matches; constructing with wrong-shaped branch would fail at DOF gate.
    ok = OperatingBranchRobotModel(branch=branch2, kinematic_model=mismatched)
    assert ok.dof == 3


def test_public_core_reexports_kinematics_generators() -> None:
    import inequality_mechanisms.core as core
    import inequality_mechanisms.kinematics.planar_2r_goals as p2
    import inequality_mechanisms.kinematics.planar_3r_goals as p3

    assert core.CartesianDiskGoalGenerator is p2.CartesianDiskGoalGenerator
    assert core.planar_2r_ik_family is p2.planar_2r_ik_family
    assert core.Planar3RPoseGoalGenerator is p3.Planar3RPoseGoalGenerator
    assert (
        core.FrozenPlanar3RPositionGoalGenerator
        is p3.FrozenPlanar3RPositionGoalGenerator
    )
