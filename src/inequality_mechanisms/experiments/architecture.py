"""Architecture-version classification and mixed-field rejection (ADR-016).

This module is intentionally independent of the Version 2 experiment runner so
compatibility behavior is testable from Sprint V2.0 onward.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

ArchitectureVersion = Literal[1, 2]


class ArchitectureCompatibilityError(ValueError):
    """Raised when a config mapping mixes Version 1 and Version 2 semantics."""


_V2_MARKERS = frozenset(
    {
        "planning_space",
        "branch",
        "sampling",
        "edge_validation",
        "result_schema_version",
    }
)


def classify_architecture_version(data: Mapping[str, Any]) -> ArchitectureVersion:
    """Classify a raw config mapping as Version 1 or Version 2.

    Parameters
    ----------
    data :
        Mapping loaded from YAML/JSON before typed model validation.

    Returns
    -------
    ArchitectureVersion
        ``1`` when ``architecture_version`` is absent or ``1``;
        ``2`` when ``architecture_version`` is ``2``.

    Raises
    ------
    ArchitectureCompatibilityError
        If the version field is unsupported or Version 1/2 fields are mixed.
    """
    if not isinstance(data, Mapping):
        raise ArchitectureCompatibilityError("config root must be a mapping")

    raw = data.get("architecture_version", 1)
    try:
        version = int(raw)
    except (TypeError, ValueError) as exc:
        raise ArchitectureCompatibilityError(
            f"unsupported architecture_version: {raw!r}"
        ) from exc

    if version not in (1, 2):
        raise ArchitectureCompatibilityError(
            f"unsupported architecture_version: {version}"
        )

    planning_space = data.get("planning_space")
    has_v2_markers = any(key in data for key in _V2_MARKERS) or planning_space is not None
    graph = data.get("graph")
    wrap = None
    if isinstance(graph, Mapping):
        wrap = graph.get("wrap")

    if version == 1:
        if planning_space == "output":
            raise ArchitectureCompatibilityError(
                "planning_space: output requires architecture_version: 2"
            )
        if "branch" in data:
            raise ArchitectureCompatibilityError(
                "branch fields require architecture_version: 2"
            )
        if data.get("sampling") is not None:
            sampling = data["sampling"]
            if isinstance(sampling, Mapping) and sampling.get("domain") in {
                "input",
                "output",
            }:
                # V1 configs do not use the Version 2 sampling block.
                raise ArchitectureCompatibilityError(
                    "Version 2 sampling block requires architecture_version: 2"
                )
        return 1

    # version == 2
    if planning_space is None:
        raise ArchitectureCompatibilityError(
            "architecture_version: 2 requires planning_space"
        )
    if planning_space != "output":
        raise ArchitectureCompatibilityError(
            "architecture_version: 2 requires planning_space: output"
        )
    trials = data.get("trials")
    if isinstance(trials, Mapping) and "preimage_policy" in trials:
        raise ArchitectureCompatibilityError(
            "preimage_policy is Version 1-only; omit it for architecture_version: 2"
        )
    if wrap is not None:
        wraps = list(wrap) if not isinstance(wrap, bool) else [wrap]
        if any(bool(w) for w in wraps):
            raise ArchitectureCompatibilityError(
                "Version 2 branch topology must be nonperiodic (wrap all false)"
            )
    if not has_v2_markers and planning_space != "output":
        raise ArchitectureCompatibilityError(
            "architecture_version: 2 config is missing Version 2 fields"
        )
    return 2
