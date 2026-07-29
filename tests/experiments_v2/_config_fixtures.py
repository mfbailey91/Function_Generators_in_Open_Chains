"""Shared raw-mapping fixture for Version 2 config tests."""

from __future__ import annotations

import copy
from typing import Any


def base_v2_config_mapping() -> dict[str, Any]:
    """Return a fresh, valid Version 2 config mapping (deep-copy per call)."""
    return copy.deepcopy(
        {
            "architecture_version": 2,
            "result_schema_version": 2,
            "planning_space": "output",
            "mechanisms": {
                "comparison": "fourbar_vs_equivalent_affine_gearbox",
                "dim": 2,
                "fourbar": {"a": 1.0, "b": 2.5, "c": 2.0, "d": 2.0, "branch": 1},
                "matching_rule": "span",
            },
            "branch": {
                "selection": "monotonic_interval",
                "certification_samples_per_axis": 17,
                "minimum_abs_gain": 0.05,
                "inverse_tolerance": 1.0e-6,
                "endpoint_margin_fraction": 0.05,
            },
            "sampling": {
                "domain": "output",
                "shape": [8, 8],
                "include_endpoints": True,
            },
            "objective": {
                "cost": "output_euclidean",
                "heuristic": "output_euclidean",
            },
            "edge_validation": {"samples": 17},
            "tasks": {
                "source": "fixed_output_pairs",
                "output_tolerance": 0.3,
            },
            "algorithms": ["dijkstra", "astar"],
            "seed": 12345,
            "trials": 5,
        }
    )
