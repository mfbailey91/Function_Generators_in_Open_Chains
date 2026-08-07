"""Always-on OMPL optional-dependency gate tests (Sprint V3.5 / V3-501)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.adapters.ompl import (
    is_ompl_available,
    ompl_version_string,
    require_ompl,
)


def test_is_ompl_available_returns_bool() -> None:
    assert isinstance(is_ompl_available(), bool)


def test_ompl_version_string_consistent_with_availability() -> None:
    available = is_ompl_available()
    version = ompl_version_string()
    if available:
        assert version is not None
        assert len(version) > 0
    else:
        assert version is None


def test_require_ompl_raises_clearly_when_missing() -> None:
    """Document the skip/fail path for environments without OMPL bindings."""
    if is_ompl_available():
        ob, og = require_ompl()
        assert ob is not None
        assert og is not None
    else:
        with pytest.raises(ImportError, match="OMPL Python bindings"):
            require_ompl()


def test_adapters_package_import_does_not_require_ompl() -> None:
    """Core adapters exports must remain importable without OMPL."""
    from inequality_mechanisms import adapters

    assert hasattr(adapters, "OperatingBranchRobotModel")
    assert hasattr(adapters, "GraphSearchPlanner")


def test_ompl_marked_tests_are_skippable_without_backend() -> None:
    """``pytest -m ompl`` collects adapter tests that skip when OMPL is absent."""
    # Smoke module must import without bindings so collection stays green.
    import inequality_mechanisms.benchmarks.smoke_ompl_2r as smoke

    assert hasattr(smoke, "run_ompl_parity_smoke_pack")


def test_solution_flags_do_not_promote_approximate_paths() -> None:
    from inequality_mechanisms.adapters.ompl.planner_base import _solution_flags

    class ApproximateProblemDefinition:
        def hasSolution(self) -> bool:  # noqa: N802
            return True

        def hasExactSolution(self) -> bool:  # noqa: N802
            return False

        def getSolutionDifference(self) -> float:  # noqa: N802
            return 0.25

    any_solution, exact_solution, difference = _solution_flags(
        ApproximateProblemDefinition()
    )
    assert any_solution
    assert not exact_solution
    assert difference == pytest.approx(0.25)


def test_solution_flags_fail_closed_without_exact_api() -> None:
    from inequality_mechanisms.adapters.ompl.planner_base import _solution_flags

    class ProblemDefinitionWithoutExactAPI:
        def hasSolution(self) -> bool:  # noqa: N802
            return True

        def getSolutionDifference(self) -> float:  # noqa: N802
            return 0.1

    any_solution, exact_solution, difference = _solution_flags(
        ProblemDefinitionWithoutExactAPI()
    )
    assert any_solution
    assert not exact_solution
    assert difference == pytest.approx(0.1)


def test_exact_start_mismatch_fails_instead_of_repairing() -> None:
    from inequality_mechanisms.adapters.ompl.planner_base import (
        _canonicalize_exact_start,
    )
    from inequality_mechanisms.core.state import PhysicalState

    exact = PhysicalState(u=np.array([0.0, 0.0]), q=np.array([0.0, 0.0]))
    wrong = PhysicalState(u=np.array([0.1, 0.0]), q=np.array([0.1, 0.0]))
    with pytest.raises(RuntimeError, match="exact-start round trip"):
        _canonicalize_exact_start((wrong,), exact, planner_id="test_ompl")


def test_exact_start_numerical_equivalent_is_canonicalized() -> None:
    from inequality_mechanisms.adapters.ompl.planner_base import (
        _canonicalize_exact_start,
    )
    from inequality_mechanisms.core.state import PhysicalState

    exact = PhysicalState(u=np.array([0.0, 0.0]), q=np.array([0.0, 0.0]))
    near = PhysicalState(u=np.array([1e-12, 0.0]), q=np.array([0.0, 0.0]))
    states, residual = _canonicalize_exact_start(
        (near,), exact, planner_id="test_ompl"
    )
    assert states[0] is exact
    assert residual == pytest.approx(1e-12)


def test_last_valid_failure_marks_exact_start_and_zero_fraction() -> None:
    from inequality_mechanisms.adapters.ompl.validity import (
        _set_last_valid_at_start,
    )

    class FakeSpace:
        def copyState(self, destination, source) -> None:  # noqa: N802
            destination[:] = source

    start = [1.0, 2.0]
    destination = [0.0, 0.0]
    last_valid = [destination, 1.0]
    assert _set_last_valid_at_start(FakeSpace(), last_valid, start)
    assert destination == start
    assert last_valid[1] == pytest.approx(0.0)
