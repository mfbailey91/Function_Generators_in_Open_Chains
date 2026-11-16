"""V4.3 strict-JSON transport and schema helpers (V4-300).

Finite numbers are retained. Unavailable or nonfinite values become
``null`` with an explicit field-status label. This module does not rewrite
the V3.6E ``static_wrench`` schema.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FIELD_STATUS_SCHEMA_VERSION,
    FIELD_STATUS_VALUES,
    schema_catalog,
)

__all__ = [
    "encode_numeric_field",
    "schema_documentation",
    "strict_json_dumps",
    "to_strict_jsonable",
]


def encode_numeric_field(
    value: float | None,
    *,
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Encode one numeric field for strict JSON transport.

    Parameters
    ----------
    value :
        Finite number, or ``None`` when unavailable.
    status :
        One of the V4.3 field-status labels.
    reason :
        Optional explicit reason string.

    Returns
    -------
    dict
        Strict field-status object.
    """
    if status not in FIELD_STATUS_VALUES:
        raise ValueError(f"unknown field status {status!r}")
    payload: dict[str, Any] = {
        "schema_version": FIELD_STATUS_SCHEMA_VERSION,
        "status": status,
        "value": None,
    }
    if reason is not None:
        payload["reason"] = reason
    if value is None:
        return payload
    number = float(value)
    if not math.isfinite(number):
        if status == "finite":
            raise ValueError("nonfinite value cannot use status 'finite'")
        payload["value"] = None
        if "reason" not in payload:
            if math.isinf(number):
                payload["reason"] = "nonfinite_infinity"
            else:
                payload["reason"] = "nonfinite_nan"
        return payload
    if status != "finite":
        # Retain the finite diagnostic while keeping the declared status.
        payload["value"] = number
        return payload
    payload["value"] = number
    return payload


def to_strict_jsonable(obj: Any) -> Any:
    """Convert nested structures into JSON with ``allow_nan=False`` safety.

    Nonfinite floats become ``null``. Mappings and sequences are walked
    recursively. Callers that need an explicit status label should use
    :func:`encode_numeric_field` instead of bare floats.
    """
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return None
        return float(obj)
    if isinstance(obj, Mapping):
        return {str(key): to_strict_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_strict_jsonable(item) for item in obj]
    if hasattr(obj, "item"):
        try:
            return to_strict_jsonable(obj.item())
        except Exception:  # noqa: BLE001
            pass
    raise TypeError(f"object of type {type(obj)!r} is not strict-JSON serializable")


def strict_json_dumps(obj: Any, *, indent: int | None = 2) -> str:
    """Serialize ``obj`` with ``allow_nan=False`` after strict conversion."""
    return json.dumps(
        to_strict_jsonable(obj),
        indent=indent,
        sort_keys=True,
        allow_nan=False,
    )


def schema_documentation() -> dict[str, Any]:
    """Return the documented V4.3 schema catalog for package ``schema.json``."""
    return {
        "package": "v4_3_intrinsic_static_wrench",
        "schemas": schema_catalog(),
        "field_status_values": sorted(FIELD_STATUS_VALUES),
        "numeric_transport": (
            "Finite values retained; nonfinite/unavailable values are null "
            "with an explicit field-status label."
        ),
    }
