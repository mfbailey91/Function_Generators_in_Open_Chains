"""Frozen-seed RNG helpers for Version 3 sampling planners (Sprint V3.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.random import Generator


@dataclass(frozen=True, slots=True)
class SeededRun:
    """One declared sampling repetition under a frozen seed contract.

    Version 3.4 smoke packs use ``repetition_index=0`` and a single
    repetition per task. Multi-repetition protocols land in V3.6.
    """

    seed: int
    repetition_index: int = 0

    def __post_init__(self) -> None:
        if self.repetition_index < 0:
            raise ValueError("repetition_index must be nonnegative")


def make_generator(seed: int, *, repetition_index: int = 0) -> Generator:
    """Return a NumPy Generator derived from ``seed`` and repetition index."""
    # Mix repetition into the seed stream without mutating caller state.
    mixed = int(seed) + 1_000_003 * int(repetition_index)
    return np.random.default_rng(mixed)


def seed_provenance_extras(
    run: SeededRun,
    *,
    planner_id: str,
) -> dict[str, Any]:
    """Return provenance extras for a seeded sampling solve."""
    return {
        "seed": int(run.seed),
        "repetition_index": int(run.repetition_index),
        "seed_protocol": "v3_4_single_repetition",
        "planner_id": planner_id,
    }
