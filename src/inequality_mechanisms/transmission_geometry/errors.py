"""Typed errors for kinematic transmission geometry operations."""

from __future__ import annotations


class TransmissionGeometryError(ValueError):
    """Base class for invalid differential-geometry operations."""


class DifferentialShapeError(TransmissionGeometryError):
    """Raised for incompatible vector or matrix dimensions, or nonfinite input."""

    def __init__(
        self,
        message: str,
        *,
        failure_code: str = "differential_shape_error",
    ) -> None:
        super().__init__(message)
        self.failure_code = failure_code


class DifferentialSingularityError(TransmissionGeometryError):
    """Raised when an inverse-defined operation requires unavailable rank."""

    failure_code = "transmission_rank_deficient"

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        shape: tuple[int, int],
        rank: int,
        required_rank: int,
        singular_values: tuple[float, ...],
        tolerance: float,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.shape = shape
        self.rank = rank
        self.required_rank = required_rank
        self.singular_values = singular_values
        self.tolerance = tolerance


__all__ = [
    "DifferentialShapeError",
    "DifferentialSingularityError",
    "TransmissionGeometryError",
]
