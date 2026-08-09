"""Robot-owned actuator input domain (Sprint V3.6A / V3-613)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class InputDomain:
    """Bounded actuator sampling domain owned by a ``RobotModel``.

    Parameters
    ----------
    lower, upper :
        Actuator box bounds, shape ``(n,)``.
    periodic :
        Per-axis periodicity flags. The initial certified monotonic branch
        uses all ``False``; later noninjective work may enable axes.
    """

    lower: NDArray[np.float64]
    upper: NDArray[np.float64]
    periodic: tuple[bool, ...]

    def __post_init__(self) -> None:
        lower = np.asarray(self.lower, dtype=np.float64).copy()
        upper = np.asarray(self.upper, dtype=np.float64).copy()
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)
        if lower.ndim != 1 or upper.ndim != 1:
            raise ValueError("lower and upper must be 1-D")
        if lower.shape != upper.shape:
            raise ValueError("lower and upper must share shape")
        if len(self.periodic) != lower.shape[0]:
            raise ValueError("periodic length must match domain dimension")
        if not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper)):
            raise ValueError("bounds must be finite")
        if np.any(upper < lower):
            raise ValueError("upper must be componentwise >= lower")

    @property
    def dim(self) -> int:
        """Actuator dimension."""
        return int(self.lower.shape[0])
