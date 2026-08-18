"""Named planar force directions for the gravity-free wrench atlas."""

from __future__ import annotations

from typing import Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

DIRECTION_EPS = 1e-12


def unit(vector: ArrayLike) -> NDArray[np.float64] | None:
    """Return a unit vector, or None if the input is too small."""
    arr = np.asarray(vector, dtype=np.float64).reshape(-1)
    nrm = float(np.linalg.norm(arr))
    if nrm <= DIRECTION_EPS or not np.all(np.isfinite(arr)):
        return None
    return arr / nrm


def named_task_directions(x: ArrayLike) -> Mapping[str, NDArray[np.float64] | None]:
    """Cartesian, radial, and tangential unit directions at endpoint ``x``."""
    pos = np.asarray(x, dtype=np.float64).reshape(-1)[:2]
    radial = unit(pos)
    tangential = None if radial is None else np.array([-radial[1], radial[0]], dtype=np.float64)
    return {
        "positive_x": np.array([1.0, 0.0], dtype=np.float64),
        "positive_y": np.array([0.0, 1.0], dtype=np.float64),
        "radial": radial,
        "tangential": tangential,
    }
