"""Always-on OMPL optional-dependency gate tests (Sprint V3.5 / V3-501)."""

from __future__ import annotations

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
