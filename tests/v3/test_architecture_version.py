"""Architecture version 3 discriminator tests (Sprint V3.1 / V3-101)."""

from __future__ import annotations

import pytest

from inequality_mechanisms.experiments.architecture import (
    ArchitectureCompatibilityError,
    classify_architecture_version,
)


def test_architecture_version_3_classifies() -> None:
    assert classify_architecture_version({"architecture_version": 3}) == 3


def test_architecture_version_3_does_not_require_v2_blocks() -> None:
    data = {"architecture_version": 3, "run_id": "v3_smoke"}
    assert classify_architecture_version(data) == 3


def test_architecture_version_3_rejects_preimage_policy() -> None:
    data = {
        "architecture_version": 3,
        "trials": {"preimage_policy": "lex_min_node_id"},
    }
    with pytest.raises(ArchitectureCompatibilityError, match="preimage_policy"):
        classify_architecture_version(data)


def test_architecture_version_3_rejects_periodic_wrap() -> None:
    data = {
        "architecture_version": 3,
        "graph": {"shape": [8, 8], "wrap": [True, False]},
    }
    with pytest.raises(ArchitectureCompatibilityError, match="wrap"):
        classify_architecture_version(data)


def test_v1_and_v2_behavior_unchanged() -> None:
    assert classify_architecture_version({}) == 1
    assert (
        classify_architecture_version(
            {
                "architecture_version": 2,
                "planning_space": "output",
                "branch": {},
                "sampling": {"domain": "output", "shape": [4, 4]},
            }
        )
        == 2
    )
