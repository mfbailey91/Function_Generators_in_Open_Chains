"""V4.3 strict-JSON transport and retained-package verifier (V4-300/308).

Finite numbers are retained. Unavailable or nonfinite values become
``null`` with an explicit field-status label. This module does not rewrite
the V3.6E ``static_wrench`` schema.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import zlib
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.audits.v4_2b_artifact import expected_case_ids
from inequality_mechanisms.audits.v4_artifact_guard import (
    FROZEN_V3_REVIEW_PACKAGES,
    V4_0_ALLOWED_OUTPUT_REL,
    V4_1_ALLOWED_OUTPUT_REL,
    V4_2_ALLOWED_OUTPUT_REL,
    V4_2A_ALLOWED_OUTPUT_REL,
    V4_2B_ALLOWED_OUTPUT_REL,
    V4_2C_ALLOWED_OUTPUT_REL,
    V4_2C_R_ALLOWED_OUTPUT_REL,
    V4_2D_ALLOWED_OUTPUT_REL,
    V4_3_ALLOWED_OUTPUT_REL,
    V4_3_ALLOWED_PACKAGE,
    V4_3_CORRECTIVE_OUTPUT_REL,
    V4_3_FOLLOWUP_OUTPUT_REL,
    canonical_v4_2b_retained_root,
    git_tracked_rel_digest,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FIELD_STATUS_SCHEMA_VERSION,
    FIELD_STATUS_VALUES,
    FROZEN_MECHANISM_IDS,
    FROZEN_V4_2B_FILES_DIGEST,
    FROZEN_V4_2B_N_CASES,
    FROZEN_V4_2B_N_GEOMETRY_ROWS,
    FROZEN_V4_2B_N_ROWS_PER_ARM,
    LEGACY_MANIFEST_SCHEMA_VERSION,
    LEGACY_PACKAGE_SCHEMA_VERSION,
    LEGACY_ROW_SCHEMA_VERSION,
    MANIFEST_SCHEMA_VERSION,
    PACKAGE_SCHEMA_VERSION,
    ROW_SCHEMA_VERSION,
    schema_catalog,
)
from inequality_mechanisms.metrics.wrench_directions import DIRECTION_EPS

LEGACY_MANIFEST_SHA256 = (
    "703263e1851ff12a1637474f7bcb0032feccf894515552670feb26d243c04ce7"
)
LEGACY_FILES_DIGEST = "a7abec714721afa2e4f6551990e3532e5ad9a6234f72f93b2480344fcc5d4218"
DIRECTIONS = ("positive_x", "positive_y", "radial", "tangential")
RANK_MAPS = ("u_to_q", "q_to_x", "u_to_x")
LEGACY_REQUIRED_FIGURES = ("scalar", "polygons", "identity_scalar")
CORRECTIVE_REQUIRED_FIGURES = (
    *LEGACY_REQUIRED_FIGURES,
    *DIRECTIONS,
    "true_scale_detail",
    "delta",
    "ratio",
    "status",
)
DIAGNOSTIC_DIRECTION_FIGURES = tuple(f"{name}_diagnostic" for name in DIRECTIONS)
FOLLOWUP_REQUIRED_FIGURES = (
    *CORRECTIVE_REQUIRED_FIGURES,
    *DIAGNOSTIC_DIRECTION_FIGURES,
)
# Absolute |A d| floor below which a near-singular ray may keep numerical
# accommodation. Directions with larger projections are verified like regular.
RAY_CAPACITY_SENSITIVITY_ABS = 1e-8
MANIFEST_INVENTORY_RULE = "exclude_self"
MANIFEST_NAME = "manifest.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_ROOT_FILES = (
    "README.md",
    "config_resolved.json",
    "environment.json",
    "source_lock.json",
    "schema.json",
    "cases.json",
    "smoke_selection.json",
    "validation.json",
    "coverage.json",
    "predecessor_integrity.json",
    "methods.md",
    "biological_reference_pointer.md",
    "index.html",
    "assets/atlas.css",
    "assets/atlas.js",
    "fixtures/analytic_expectations.json",
    "fixtures/analytic_results.json",
)
REQUIRED_MANIFEST_KEYS = (
    "schema_version",
    "package",
    "manifest_inventory_rule",
    "source_git_revision",
    "source_git_dirty",
    "config_digest",
    "case_ids",
    "n_rows",
    "n_typed_failures",
    "n_silent_drops",
    "files",
    "files_digest",
)

__all__ = [
    "MANIFEST_INVENTORY_RULE",
    "MANIFEST_NAME",
    "V4_3ArtifactError",
    "aggregate_vertex_diagnostics",
    "case_wrench_rel",
    "encode_numeric_field",
    "files_digest",
    "inventory_package_files",
    "schema_documentation",
    "snapshot_predecessor_integrity",
    "strict_json_dumps",
    "to_strict_jsonable",
    "verify_v4_3_artifact",
]


def snapshot_predecessor_integrity(
    *,
    include_original_v4_3: bool = True,
) -> dict[str, Any]:
    """Record git-tracked digests for frozen V3/V4 packages through V4.2D."""
    packages: dict[str, dict[str, Any]] = {}
    for name in sorted(FROZEN_V3_REVIEW_PACKAGES):
        rel = Path("results") / "v3_review" / name
        digest, n_files = git_tracked_rel_digest(rel)
        packages[name] = {
            "rel": rel.as_posix(),
            "git_tracked_digest": digest,
            "n_git_tracked_files": n_files,
        }
    for label, rel in (
        ("v4_0", V4_0_ALLOWED_OUTPUT_REL),
        ("v4_1", V4_1_ALLOWED_OUTPUT_REL),
        ("v4_2", V4_2_ALLOWED_OUTPUT_REL),
        ("v4_2a", V4_2A_ALLOWED_OUTPUT_REL),
        ("v4_2b", V4_2B_ALLOWED_OUTPUT_REL),
        ("v4_2c", V4_2C_ALLOWED_OUTPUT_REL),
        ("v4_2c_r", V4_2C_R_ALLOWED_OUTPUT_REL),
        ("v4_2d", V4_2D_ALLOWED_OUTPUT_REL),
    ):
        digest, n_files = git_tracked_rel_digest(rel)
        packages[label] = {
            "rel": rel.as_posix(),
            "git_tracked_digest": digest,
            "n_git_tracked_files": n_files,
        }
    if include_original_v4_3:
        digest, n_files = git_tracked_rel_digest(V4_3_ALLOWED_OUTPUT_REL)
        packages["v4_3_original"] = {
            "rel": V4_3_ALLOWED_OUTPUT_REL.as_posix(),
            "git_tracked_digest": digest,
            "n_git_tracked_files": n_files,
        }
    return {
        "schema_version": "v4.3.intrinsic_static_wrench.predecessor_integrity.v1",
        "v4_2b_files_digest": FROZEN_V4_2B_FILES_DIGEST,
        "packages": packages,
    }


class V4_3ArtifactError(ValueError):
    """Raised when a V4.3 retained package fails integrity checks."""

    failure_code = "v4_3_artifact_integrity_failed"


def encode_numeric_field(
    value: float | None,
    *,
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Encode one numeric field for strict JSON transport."""
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
        payload["value"] = number
        return payload
    payload["value"] = number
    return payload


def to_strict_jsonable(obj: Any) -> Any:
    """Convert nested structures into JSON with ``allow_nan=False`` safety."""
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
        "package": V4_3_ALLOWED_PACKAGE,
        "schemas": schema_catalog(),
        "field_status_values": sorted(FIELD_STATUS_VALUES),
        "numeric_transport": (
            "Finite values retained; nonfinite/unavailable values are null "
            "with an explicit field-status label."
        ),
    }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def files_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """SHA-256 over sorted ``path\\0sha256\\n`` inventory lines."""
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: str(item["path"])):
        digest.update(str(record["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def case_wrench_rel(case_id: str) -> str:
    """Return the per-case compressed wrench-sample path."""
    return f"cases/{case_id}/wrench_samples.jsonl.gz"


def _reject_constant(value: str) -> None:
    raise V4_3ArtifactError(f"nonfinite JSON constant {value!r}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise V4_3ArtifactError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _strict_loads(text: str) -> Any:
    result = json.loads(
        text, parse_constant=_reject_constant, object_pairs_hook=_unique_object
    )

    def finite(value: Any) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise V4_3ArtifactError("nonfinite JSON number (including overflow)")
        if isinstance(value, dict):
            for child in value.values():
                finite(child)
        elif isinstance(value, list):
            for child in value:
                finite(child)

    finite(result)
    return result


def _read_json(path: Path) -> Any:
    try:
        return _strict_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V4_3ArtifactError(f"invalid JSON in {path}: {exc}") from exc


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise V4_3ArtifactError(f"{label} must be an object")
    return value


def _iter_jsonl_objects(path: Path, *, compression: str) -> Iterator[dict[str, Any]]:
    if compression == "gzip":
        handle_cm = gzip.open(path, "rt", encoding="utf-8")
    elif compression == "none":
        handle_cm = path.open("rt", encoding="utf-8")
    else:
        raise V4_3ArtifactError(f"unsupported compression {compression!r} for {path}")
    try:
        with handle_cm as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    raise V4_3ArtifactError(f"{path}:{line_no}: empty record")
                yield _object(_strict_loads(line), f"{path}:{line_no}")
    except json.JSONDecodeError as exc:
        raise V4_3ArtifactError(f"schema mismatch in {path}: {exc}") from exc
    except (OSError, EOFError, zlib.error, UnicodeError) as exc:
        raise V4_3ArtifactError(f"decompression failure for {path}: {exc}") from exc


def _row_inventory(path: Path) -> tuple[int, str]:
    count = 0
    schema: str | None = None
    for payload in _iter_jsonl_objects(path, compression="gzip"):
        version = payload.get("schema_version")
        if version not in (ROW_SCHEMA_VERSION, LEGACY_ROW_SCHEMA_VERSION):
            raise V4_3ArtifactError(f"{path}: unknown row schema_version {version!r}")
        if schema is not None and version != schema:
            raise V4_3ArtifactError(f"{path}: mixed row schemas")
        schema = str(version)
        for key in ("case_id", "q_sample_id", "mechanism_id", "grid_index"):
            if key not in payload:
                raise V4_3ArtifactError(f"{path}: wrench row missing {key!r}")
        count += 1
    return count, schema or ROW_SCHEMA_VERSION


def _safe_relative(rel: Any) -> str:
    if not isinstance(rel, str) or not rel or "\\" in rel:
        raise V4_3ArtifactError("inventory path must be a canonical relative path")
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != rel:
        raise V4_3ArtifactError(f"unsafe inventory path {rel!r}")
    return rel


def inventory_file(
    root: Path, rel: str, *, package_schema: str = PACKAGE_SCHEMA_VERSION
) -> dict[str, Any]:
    """Inventory actual bytes, rejecting escaping links and nonstandard JSON."""
    rel = _safe_relative(rel)
    path = Path(root) / rel
    if path.is_symlink() or not path.is_file():
        raise V4_3ArtifactError(f"missing required file or forbidden symlink {rel}")
    payload = path.read_bytes()
    row_count: int | None = None
    schema_version = package_schema
    if rel.endswith(".jsonl.gz"):
        row_count, schema_version = _row_inventory(path)
        media_type, compression = "application/gzip", "gzip"
    elif rel.endswith(".json"):
        _read_json(path)
        media_type, compression = "application/json", "none"
    else:
        types = {
            ".md": "text/markdown",
            ".html": "text/html",
            ".css": "text/css",
            ".js": "text/javascript",
            ".png": "image/png",
        }
        if path.suffix not in types:
            raise V4_3ArtifactError(f"unsupported retained file type for {rel}")
        media_type, compression = types[path.suffix], "none"
    return {
        "path": rel,
        "sha256": _sha256_bytes(payload),
        "byte_count": len(payload),
        "row_count": row_count,
        "schema_version": schema_version,
        "media_type": media_type,
        "compression": compression,
    }


def _required_figures(
    *, legacy: bool = False, followup: bool = False
) -> tuple[str, ...]:
    if legacy:
        return LEGACY_REQUIRED_FIGURES
    if followup:
        return FOLLOWUP_REQUIRED_FIGURES
    return CORRECTIVE_REQUIRED_FIGURES


def _is_followup_root(root: Path) -> bool:
    return root.resolve().name == V4_3_FOLLOWUP_OUTPUT_REL.name


def inventory_package_files(
    root: Path,
    case_ids: Sequence[str],
    *,
    legacy: bool = False,
    followup: bool | None = None,
) -> list[dict[str, Any]]:
    """Inventory every actual file, excluding only the root manifest."""
    root = Path(root)
    if followup is None:
        followup = (not legacy) and _is_followup_root(root)
    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise V4_3ArtifactError(f"symlink in package: {path.relative_to(root)}")
        if path.is_file() and path != root / MANIFEST_NAME:
            actual.add(path.relative_to(root).as_posix())
    required = set(REQUIRED_ROOT_FILES)
    required_figures = _required_figures(legacy=legacy, followup=followup)
    for cid in case_ids:
        required.update(
            {
                case_wrench_rel(cid),
                f"cases/{cid}/summary.json",
                f"cases/{cid}/index.html",
                *(f"cases/{cid}/figures/{name}.png" for name in required_figures),
            }
        )
    if missing := required - actual:
        raise V4_3ArtifactError(f"missing required files: {sorted(missing)}")
    cases_dir = root / "cases"
    actual_cases = {p.name for p in cases_dir.iterdir() if p.is_dir()}
    if actual_cases != set(case_ids):
        raise V4_3ArtifactError("actual case-directory set differs from case_ids")
    package_schema = LEGACY_PACKAGE_SCHEMA_VERSION if legacy else PACKAGE_SCHEMA_VERSION
    return [
        inventory_file(root, rel, package_schema=package_schema)
        for rel in sorted(actual)
    ]


def _number(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise V4_3ArtifactError(f"{label} must be a finite number")
    if nonnegative and value < 0:
        raise V4_3ArtifactError(f"{label} must be nonnegative")
    return float(value)


def _integer(value: Any, expected: int, label: str) -> None:
    if type(value) is not int or value != expected:
        raise V4_3ArtifactError(f"{label} must be integer {expected}")


def _array(value: Any, shape: tuple[int, ...], label: str) -> np.ndarray[Any, Any]:
    if not isinstance(value, list):
        raise V4_3ArtifactError(f"{label} must be an array of shape {shape}")
    try:
        array = np.asarray(value)
    except (ValueError, TypeError) as exc:
        raise V4_3ArtifactError(f"invalid {label} array") from exc
    if (
        array.shape != shape
        or array.dtype.kind not in "ifu"
        or not np.isfinite(array).all()
    ):
        raise V4_3ArtifactError(f"{label} must have finite numeric shape {shape}")
    return np.asarray(array, dtype=float)


def _field(value: Any, label: str) -> dict[str, Any]:
    field = _object(value, label)
    if field.get("schema_version") != FIELD_STATUS_SCHEMA_VERSION:
        raise V4_3ArtifactError(f"{label}: invalid field-status schema")
    status = field.get("status")
    if (
        not isinstance(status, str)
        or status not in FIELD_STATUS_VALUES
        or "value" not in field
    ):
        raise V4_3ArtifactError(f"{label}: invalid field status/value")
    number = field["value"]
    if status in {"finite", "masked_nonregular"}:
        _number(number, label)
    elif number is not None:
        raise V4_3ArtifactError(f"{label}: {status} value must be null")
    if status != "finite" and not isinstance(field.get("reason"), str):
        raise V4_3ArtifactError(f"{label}: unavailable field needs a reason")
    return field


def _assert_distinct_polygon_vertices(verts: np.ndarray[Any, Any]) -> None:
    exact = {tuple(map(float, vertex)) for vertex in verts}
    if len(exact) != 4:
        raise V4_3ArtifactError("polygon vertices must be four distinct points")


def _assert_consistent_polygon_cycle(verts: np.ndarray[Any, Any]) -> None:
    """Reject collapsed edges and inconsistent/self-intersecting vertex order."""
    crosses: list[float] = []
    for index in range(4):
        a = verts[index]
        b = verts[(index + 1) % 4]
        c = verts[(index + 2) % 4]
        edge1 = b - a
        edge2 = c - b
        scale = float(np.linalg.norm(edge1) * np.linalg.norm(edge2))
        if scale <= DIRECTION_EPS:
            raise V4_3ArtifactError("polygon edges must be non-degenerate")
        crosses.append(float(edge1[0] * edge2[1] - edge1[1] * edge2[0]))
    max_abs = max(abs(value) for value in crosses)
    if max_abs <= DIRECTION_EPS:
        raise V4_3ArtifactError("polygon vertex order is degenerate")
    # Compare turns relative to the largest retained cross-product so skinny
    # near-singular parallelograms keep a consistent orientation while bow-ties
    # (sign-changing turns) still fail closed.
    signs = [float(np.sign(value)) for value in crosses if abs(value) > 1e-9 * max_abs]
    if len(signs) < 3:
        raise V4_3ArtifactError("polygon vertex order is degenerate")
    if any(sign != signs[0] for sign in signs):
        raise V4_3ArtifactError(
            "polygon vertex order is inconsistent or self-intersecting"
        )


def _ray_is_ill_conditioned(
    a_map: np.ndarray[Any, Any], direction: np.ndarray[Any, Any]
) -> bool:
    """True when every active |row·d| is below the sensitivity floor."""
    unit = np.asarray(direction, dtype=float).reshape(-1)
    norm = float(np.linalg.norm(unit))
    if norm <= DIRECTION_EPS or not np.all(np.isfinite(unit)):
        return True
    unit = unit / norm
    dens = [
        abs(float(np.dot(row, unit)))
        for row in a_map
        if float(np.linalg.norm(row)) > DIRECTION_EPS
    ]
    if not dens:
        return True
    return min(dens) <= RAY_CAPACITY_SENSITIVITY_ABS


def _validate_row(row: Mapping[str, Any], *, legacy: bool = False) -> None:
    """Validate retained science and transport independently of the writer."""
    common = {
        "schema_version",
        "case_id",
        "q_sample_id",
        "mechanism_id",
        "mechanism_pair_id",
        "grid_index",
        "config_digest",
        "source_revision",
        "source_relpath",
        "status",
        "primary_eligible",
        "q",
        "u",
        "x",
        "isotropic_radius",
        "isotropic_radius_field",
        "directional_fields",
        "directional_capacity",
        "undefined_directions",
        "vertices",
        "rank_attribution",
        "singular_values",
        "low_gain_warning",
        "j_g",
        "j_f",
        "j_xu",
        "torque_limits",
        "vertex_feasibility",
        "source_failure_code",
        "source_failure_message",
    }
    if not legacy:
        common.update(
            {
                "hrep_a",
                "hrep_b",
                "direction_vectors",
                "rank",
                "rank_reports",
                "rank_tolerance_policy",
                "rank_tolerances",
                "inherited_tolerances",
                "joint_torque_amplification",
                "wrench_schema_version",
            }
        )
    if missing := common - row.keys():
        raise V4_3ArtifactError(
            f"wrench row missing scientific fields {sorted(missing)}"
        )
    expected_schema = LEGACY_ROW_SCHEMA_VERSION if legacy else ROW_SCHEMA_VERSION
    if row["schema_version"] != expected_schema:
        raise V4_3ArtifactError("row schema disagrees with manifest profile")
    if (
        row["source_failure_code"] is not None
        or row["source_failure_message"] is not None
    ):
        raise V4_3ArtifactError("canonical corpus contains typed source failure")
    for key in (
        "case_id",
        "q_sample_id",
        "mechanism_id",
        "mechanism_pair_id",
        "config_digest",
        "source_revision",
        "source_relpath",
    ):
        if not isinstance(row[key], str) or not row[key]:
            raise V4_3ArtifactError(f"{key} must be a nonempty string")
    status = row["status"]
    if not isinstance(status, str) or status not in {
        "regular",
        "near_singular",
        "rank_deficient",
        "unbounded_ideal_direction",
    }:
        raise V4_3ArtifactError(f"invalid canonical wrench status {status!r}")
    grid = row["grid_index"]
    if (
        not isinstance(grid, list)
        or len(grid) != 2
        or any(type(i) is not int or not 0 <= i < 33 for i in grid)
    ):
        raise V4_3ArtifactError("invalid 33x33 grid_index")
    expected_id = f"{row['case_id']}__q_{grid[0]:04d}_{grid[1]:04d}"
    if row["q_sample_id"] != expected_id or row["mechanism_pair_id"] != row["case_id"]:
        raise V4_3ArtifactError("source/grid identity mismatch")
    for key in ("q", "u", "x", "torque_limits", "singular_values"):
        _array(row[key], (2,), key)
    for key in ("j_g", "j_f", "j_xu"):
        _array(row[key], (2, 2), key)
    tau = _array(row["torque_limits"], (2,), "torque_limits")
    if not np.array_equal(tau, [1.0, 1.0]):
        raise V4_3ArtifactError("canonical normalization must use the unit effort box")
    iso = _field(row["isotropic_radius_field"], "isotropic_radius_field")
    if iso["value"] != row["isotropic_radius"]:
        raise V4_3ArtifactError("raw isotropic radius disagrees with field transport")
    if row["isotropic_radius"] is not None:
        _number(row["isotropic_radius"], "isotropic_radius", nonnegative=True)
    regular = status == "regular"
    if type(row["primary_eligible"]) is not bool or row["primary_eligible"] != regular:
        raise V4_3ArtifactError(
            "primary eligibility disagrees with regular finite status"
        )
    if (
        iso["status"] != ("finite" if regular else "masked_nonregular")
        and iso["value"] is not None
    ):
        raise V4_3ArtifactError("isotropic field mask disagrees with whole-set status")
    directions = _object(row["directional_fields"], "directional_fields")
    capacities = _object(row["directional_capacity"], "directional_capacity")
    if set(directions) != set(DIRECTIONS) or set(capacities) != set(DIRECTIONS):
        raise V4_3ArtifactError(
            "directional records must contain four named directions"
        )
    undefined: set[str] = set()
    for name in DIRECTIONS:
        field = _field(directions[name], name)
        if field["value"] != capacities[name]:
            raise V4_3ArtifactError(
                f"{name}: raw capacity disagrees with field transport"
            )
        if field["value"] is not None:
            _number(field["value"], name, nonnegative=True)
        if field["status"] == "undefined":
            undefined.add(name)
        if field["status"] not in {"finite", "undefined", "unbounded"}:
            raise V4_3ArtifactError(f"{name}: invalid canonical directional status")
    if (
        not isinstance(row["undefined_directions"], list)
        or any(not isinstance(item, str) for item in row["undefined_directions"])
        or set(row["undefined_directions"]) != undefined
    ):
        raise V4_3ArtifactError(
            "undefined_directions disagrees with transport statuses"
        )
    attribution = _object(row["rank_attribution"], "rank_attribution")
    if set(attribution) != {"j_g", "j_f", "j_xu", "primary_cause"}:
        raise V4_3ArtifactError("incomplete rank attribution")
    if type(row["low_gain_warning"]) is not bool or row["low_gain_warning"] != (
        attribution["primary_cause"] == "four_bar_low_gain"
    ):
        raise V4_3ArtifactError("low-gain warning disagrees with attribution")
    feasibility = _object(row["vertex_feasibility"], "vertex_feasibility")
    if {
        "ok",
        "max_hrep_residual",
        "max_corner_saturation_residual",
        "n_vertices",
        "failure_code",
        "details",
    } - feasibility.keys():
        raise V4_3ArtifactError("incomplete vertex feasibility diagnostics")
    if type(feasibility.get("ok")) is not bool:
        raise V4_3ArtifactError("vertex feasibility must have Boolean ok")
    vertices = row["vertices"]
    verts: np.ndarray[Any, Any] | None = None
    if vertices is not None:
        verts = _array(vertices, (4, 2), "vertices")
        _integer(feasibility.get("n_vertices"), 4, "n_vertices")
        if not legacy and (regular or status == "near_singular"):
            _assert_distinct_polygon_vertices(verts)
            _assert_consistent_polygon_cycle(verts)
        if regular:
            mapped = _array(row["j_xu"], (2, 2), "j_xu").T @ verts.T
            if not feasibility["ok"] or np.max(np.abs(mapped) - tau[:, None]) > 1e-9:
                raise V4_3ArtifactError(
                    "regular vertices violate their effort-box constraints"
                )
            if not legacy and np.max(np.abs(np.abs(mapped) - tau[:, None])) > 1e-9:
                raise V4_3ArtifactError(
                    "regular vertices fail effort-box corner equality"
                )
    elif regular or status == "near_singular":
        raise V4_3ArtifactError("full-rank state requires four closed-polygon vertices")
    else:
        _integer(feasibility.get("n_vertices"), 0, "n_vertices")
    if legacy:
        return
    from inequality_mechanisms.metrics.static_wrench import (
        NEAR_SINGULAR_CONDITION,
        directional_capacity,
        isotropic_radius,
        joint_torque_amplification,
    )
    from inequality_mechanisms.metrics.static_wrench import (
        SCHEMA_VERSION as WRENCH_SCHEMA_VERSION,
    )
    from inequality_mechanisms.metrics.wrench_directions import named_task_directions

    if row["wrench_schema_version"] != WRENCH_SCHEMA_VERSION:
        raise V4_3ArtifactError("accepted wrench API schema mismatch")
    a_map = _array(row["j_xu"], (2, 2), "j_xu").T
    expected_iso = isotropic_radius(a_map, tau)
    if math.isfinite(expected_iso):
        if row["isotropic_radius"] is None or not math.isclose(
            row["isotropic_radius"], expected_iso, rel_tol=1e-12, abs_tol=1e-12
        ):
            raise V4_3ArtifactError("isotropic radius disagrees with the retained map")
    elif row["isotropic_radius"] is not None or iso["status"] != "unbounded":
        raise V4_3ArtifactError("unbounded isotropic radius transport mismatch")
    if (
        regular
        and verts is not None
        and len({tuple(v) for v in np.sign(a_map @ verts.T).T}) != 4
    ):
        raise V4_3ArtifactError(
            "regular polygon must contain four distinct effort corners"
        )
    expected_directions = named_task_directions(row["x"])
    vectors = _object(row["direction_vectors"], "direction_vectors")
    for name, expected_direction in expected_directions.items():
        stored_direction = vectors.get(name)
        if expected_direction is None:
            if stored_direction is not None or name not in undefined:
                raise V4_3ArtifactError("undefined named direction transport mismatch")
            continue
        if stored_direction is None or not np.allclose(
            stored_direction, expected_direction, rtol=1e-12, atol=1e-12
        ):
            raise V4_3ArtifactError("named direction vector disagrees with retained X")
        # Near-singular accommodation is per-direction: only rays whose |A d|
        # projections fall below RAY_CAPACITY_SENSITIVITY_ABS may skip equality.
        accommodate = status == "near_singular" and _ray_is_ill_conditioned(
            a_map, np.asarray(expected_direction, dtype=float)
        )
        if not accommodate:
            expected_capacity = directional_capacity(a_map, tau, expected_direction)
            if math.isfinite(expected_capacity):
                if capacities[name] is None or not math.isclose(
                    capacities[name], expected_capacity, rel_tol=1e-12, abs_tol=1e-12
                ):
                    raise V4_3ArtifactError("ray capacity disagrees with retained map")
                if directions[name]["status"] != "finite":
                    raise V4_3ArtifactError(
                        "finite ray capacity must keep finite field status"
                    )
            elif (
                capacities[name] is not None
                or directions[name]["status"] != "unbounded"
            ):
                raise V4_3ArtifactError("unbounded ray transport mismatch")
    expected_amp = to_strict_jsonable(
        joint_torque_amplification(_array(row["j_g"], (2, 2), "j_g"))
    )
    if row["joint_torque_amplification"] != expected_amp:
        raise V4_3ArtifactError(
            "joint effort amplification disagrees with retained map"
        )
    if not np.array_equal(
        _array(row["hrep_a"], (4, 2), "hrep_a"), np.vstack([a_map, -a_map])
    ):
        raise V4_3ArtifactError(
            "H-representation matrix disagrees with retained Jacobian"
        )
    if not np.array_equal(
        _array(row["hrep_b"], (4,), "hrep_b"), np.concatenate([tau, tau])
    ):
        raise V4_3ArtifactError(
            "H-representation bounds disagree with effort normalization"
        )
    vectors = _object(row["direction_vectors"], "direction_vectors")
    if set(vectors) != set(DIRECTIONS):
        raise V4_3ArtifactError("missing named direction vectors")
    for name, vector in vectors.items():
        if name in undefined:
            if vector is not None:
                raise V4_3ArtifactError("undefined direction vector must be null")
        else:
            unit = _array(vector, (2,), name)
            if not math.isclose(float(np.linalg.norm(unit)), 1.0, abs_tol=1e-12):
                raise V4_3ArtifactError("direction vectors must be normalized")
    reports = _object(row["rank_reports"], "rank_reports")
    if set(reports) != set(RANK_MAPS):
        raise V4_3ArtifactError("missing component rank reports")
    for key in RANK_MAPS:
        report = _object(reports[key], key)
        required = {
            "shape",
            "rank",
            "required_full_rank",
            "singular_values",
            "tolerance",
            "full_rank",
            "condition_number",
        }
        if required - report.keys():
            raise V4_3ArtifactError(f"{key}: incomplete inherited rank report")
        if (
            report["shape"] != [2, 2]
            or type(report["rank"]) is not int
            or not 0 <= report["rank"] <= 2
        ):
            raise V4_3ArtifactError(f"{key}: invalid rank report")
        _integer(report["required_full_rank"], 2, "required_full_rank")
        if type(report["full_rank"]) is not bool or report["full_rank"] != (
            report["rank"] == 2
        ):
            raise V4_3ArtifactError(f"{key}: full-rank flag mismatch")
        _array(report["singular_values"], (2,), f"{key} singular_values")
        _number(report["tolerance"], "rank tolerance", nonnegative=True)
        if report["condition_number"] is not None:
            _number(report["condition_number"], "condition number", nonnegative=True)
    if (
        row["rank"] != reports["u_to_x"]["rank"]
        or row["singular_values"] != reports["u_to_x"]["singular_values"]
    ):
        raise V4_3ArtifactError(
            "composite rank information disagrees with inherited report"
        )
    if not isinstance(row["rank_tolerance_policy"], dict) or not isinstance(
        row["rank_tolerances"], dict
    ):
        raise V4_3ArtifactError("missing inherited rank tolerance policy")
    for key in RANK_MAPS:
        if row["rank_tolerances"].get(key) != reports[key]["tolerance"]:
            raise V4_3ArtifactError("rank tolerance metadata disagrees with report")
    if type(row["rank"]) is not int:
        raise V4_3ArtifactError("rank must be an integer")
    details = _object(feasibility["details"], "vertex feasibility details")
    if vertices is not None:
        # max_hrep_residual is the largest signed halfspace violation. Small
        # negatives are interior slack; absurd negatives (e.g. -100) cannot
        # arise from retained vertices and must fail closed.
        hrep_residual = _number(feasibility["max_hrep_residual"], "H-rep residual")
        if hrep_residual < -1.0:
            raise V4_3ArtifactError("H-rep residual is impossibly negative")
        corner_residual = _number(
            feasibility["max_corner_saturation_residual"],
            "corner residual",
            nonnegative=True,
        )
        if details.get("atol") != 1e-9:
            raise V4_3ArtifactError("vertex diagnostic tolerance mismatch")
        expected_ok = (
            hrep_residual <= 1e-9
            and corner_residual <= 1e-9
            and details.get("n_distinct_actuator_corners") == 4
        )
        if feasibility["ok"] is not expected_ok:
            raise V4_3ArtifactError(
                "vertex diagnostic outcome disagrees with residuals"
            )
    if feasibility["ok"] and feasibility["failure_code"] is not None:
        raise V4_3ArtifactError("passing vertex diagnostic has a failure code")
    if not feasibility["ok"] and not isinstance(feasibility["failure_code"], str):
        raise V4_3ArtifactError("failed vertex diagnostic lacks a failure code")
    composite = reports["u_to_x"]
    condition = composite["condition_number"]
    expected_status = (
        "unbounded_ideal_direction"
        if composite["rank"] < 2
        else "near_singular"
        if condition is not None and condition >= NEAR_SINGULAR_CONDITION
        else "regular"
    )
    if status != expected_status:
        raise V4_3ArtifactError("whole-set status disagrees with inherited rank report")
    expected_attribution = {
        label: "full_rank" if reports[key]["full_rank"] else "rank_deficient"
        for label, key in zip(("j_g", "j_f", "j_xu"), RANK_MAPS, strict=True)
    }
    if not reports["q_to_x"]["full_rank"]:
        cause = "arm_jacobian_rank_loss"
    elif not reports["u_to_q"]["full_rank"]:
        cause = "mechanism_rank_loss"
    elif not reports["u_to_x"]["full_rank"]:
        cause = "composite_rank_loss"
    elif np.min(np.abs(np.diag(row["j_g"]))) < 0.05:
        cause = "four_bar_low_gain"
    else:
        cause = "none"
    expected_attribution["primary_cause"] = cause
    if attribution != expected_attribution:
        raise V4_3ArtifactError("rank attribution disagrees with inherited reports")
    inherited = _object(row["inherited_tolerances"], "inherited_tolerances")
    if (
        inherited.get("vertex_feasibility_atol") != 1e-9
        or inherited.get("direction_eps") != 1e-12
        or inherited.get("near_singular_condition") != NEAR_SINGULAR_CONDITION
        or inherited.get("primary_display_statuses") != ["regular"]
    ):
        raise V4_3ArtifactError("inherited tolerance metadata changed")
    amplification = row["joint_torque_amplification"]
    if not isinstance(amplification, list) or len(amplification) != 2:
        raise V4_3ArtifactError("missing joint torque amplification")
    for value in amplification:
        if value is not None:
            _number(value, "joint torque amplification", nonnegative=True)


def _verify_provenance(root: Path, manifest: dict[str, Any], *, legacy: bool) -> Any:
    from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
        assert_v4_2b_source_lock,
    )
    from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
        IntrinsicStaticWrenchConfig,
    )

    revision = manifest["source_git_revision"]
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise V4_3ArtifactError(
            "source_git_revision must be a full hexadecimal revision"
        )
    if manifest["source_git_dirty"] is not False:
        raise V4_3ArtifactError("source_git_dirty must be Boolean false")
    resolved = _object(_read_json(root / "config_resolved.json"), "resolved config")
    try:
        config = IntrinsicStaticWrenchConfig.model_validate(resolved.get("config"))
    except ValueError as exc:
        raise V4_3ArtifactError(f"invalid resolved config: {exc}") from exc
    if legacy:
        expected_outputs = {V4_3_ALLOWED_OUTPUT_REL.as_posix()}
    else:
        expected_outputs = {
            V4_3_CORRECTIVE_OUTPUT_REL.as_posix(),
            V4_3_FOLLOWUP_OUTPUT_REL.as_posix(),
        }
    if config.output_dir not in expected_outputs:
        raise V4_3ArtifactError(
            "resolved config output_dir disagrees with package profile"
        )
    if tuple(config.torque.limits) != (1.0, 1.0):
        raise V4_3ArtifactError(
            "canonical torque limits must be the normalized unit box"
        )
    if (
        resolved.get("config_digest") != config.digest()
        or manifest["config_digest"] != config.digest()
    ):
        raise V4_3ArtifactError("resolved config digest mismatch")
    try:
        verified_source = assert_v4_2b_source_lock(config.source)
    except ValueError as exc:
        raise V4_3ArtifactError(f"frozen source lock failed: {exc}") from exc
    source = _object(_read_json(root / "source_lock.json"), "source_lock")
    environment = _object(_read_json(root / "environment.json"), "environment")
    for document in (source, environment):
        if (
            document.get("generation_git_revision") != revision
            or document.get("generation_git_dirty") is not False
        ):
            raise V4_3ArtifactError(
                "generation provenance disagrees across package metadata"
            )
    for key in (
        "source_revision",
        "files_digest",
        "config_digest",
        "v3_6d_registry_digest",
        "n_files",
        "n_geometry_rows",
        "case_ids",
        "grid",
        "mechanisms",
        "package",
    ):
        if source.get(key) != to_strict_jsonable(verified_source.get(key)):
            raise V4_3ArtifactError(f"source_lock {key} disagrees with frozen source")
    schemas = _object(_read_json(root / "schema.json"), "schema catalog")
    expected_schemas = schema_catalog()
    if legacy:
        expected_schemas.update(
            row=LEGACY_ROW_SCHEMA_VERSION,
            manifest=LEGACY_MANIFEST_SCHEMA_VERSION,
            package=LEGACY_PACKAGE_SCHEMA_VERSION,
        )
    if schemas.get("schemas") != expected_schemas:
        raise V4_3ArtifactError("schema catalog disagrees with package profile")
    return config


def _verify_source_record(
    row: dict[str, Any], source: dict[str, Any], *, legacy: bool
) -> None:
    snapshot = _object(source.get("snapshot"), "frozen source snapshot")
    for key in (
        "config_digest",
        "mechanism_pair_id",
        "grid_index",
        "q_sample_id",
        "mechanism_id",
    ):
        if row[key] != source.get(key):
            raise V4_3ArtifactError(f"retained {key} disagrees with frozen source")
    if row["source_revision"] != source.get("git_revision"):
        raise V4_3ArtifactError("retained source revision disagrees with frozen source")
    for key in ("q", "u", "x"):
        if row[key] != snapshot[key]:
            raise V4_3ArtifactError(f"retained {key} disagrees with frozen source")
    for output_key, source_key in (
        ("j_g", "j_u_to_q"),
        ("j_f", "j_q_to_x"),
        ("j_xu", "j_u_to_x"),
    ):
        if row[output_key] != snapshot["jacobians"][source_key]:
            raise V4_3ArtifactError(
                f"retained {output_key} disagrees with frozen source"
            )
    if not legacy:
        if row["rank_reports"] != snapshot["rank_reports"]:
            raise V4_3ArtifactError("inherited rank reports differ from frozen source")
        for key in ("rank_tolerance_policy", "rank_tolerances"):
            if row[key] != snapshot["provenance"].get(key):
                raise V4_3ArtifactError(f"inherited {key} differs from frozen source")


def _verify_case_summary(
    root: Path,
    case_id: str,
    rows: list[dict[str, Any]],
    *,
    legacy: bool,
    followup: bool = False,
) -> None:
    summary = _object(
        _read_json(root / f"cases/{case_id}/summary.json"), "case summary"
    )
    if summary.get("case_id") != case_id or summary.get("n_records") != len(rows):
        raise V4_3ArtifactError("case summary identity/count mismatch")
    stress = "175" in case_id.split("_")
    if summary.get("stress_only") is not stress:
        raise V4_3ArtifactError("case stress-only classification mismatch")
    if legacy:
        return
    required_figures = _required_figures(followup=followup)
    assets = _object(summary.get("assets"), "case assets")
    if set(assets) != set(required_figures):
        raise V4_3ArtifactError(
            "case assets must expose every required retained figure view"
        )
    for name in required_figures:
        asset = _object(assets[name], f"{name} asset")
        rel = _safe_relative(asset.get("src"))
        if rel != f"figures/{name}.png":
            raise V4_3ArtifactError(
                "case asset link must name its local retained figure"
            )
        if not (root / "cases" / case_id / rel).is_file():
            raise V4_3ArtifactError("case asset link targets a missing figure")
        for text_key in ("alt", "caption"):
            if not isinstance(asset.get(text_key), str) or not asset[text_key]:
                raise V4_3ArtifactError("case figure needs alt text and a caption")
    if summary.get("samples_href") != "wrench_samples.jsonl.gz":
        raise V4_3ArtifactError("case samples link must name the retained row bank")
    by_sample: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_sample.setdefault(row["q_sample_id"], {})[row["mechanism_id"]] = row
    mask = _object(summary.get("status_mask"), "status mask")
    cells = mask.get("cells")
    if not isinstance(cells, list) or len(cells) != len(by_sample):
        raise V4_3ArtifactError("status mask coverage mismatch")
    seen: set[str] = set()
    for cell in cells:
        cell = _object(cell, "status mask cell")
        sample = cell.get("q_sample_id")
        if not isinstance(sample, str) or sample not in by_sample or sample in seen:
            raise V4_3ArtifactError("duplicate or unknown status-mask sample")
        seen.add(sample)
        expected = {
            mech: record["status"] for mech, record in by_sample[sample].items()
        }
        if cell.get("status_by_mechanism") != expected:
            raise V4_3ArtifactError("status mask disagrees with retained rows")
    comparisons = _object(summary.get("comparisons"), "paired comparisons")
    for key in ("isotropic_radius", *DIRECTIONS):
        group = _object(comparisons.get(key), f"{key} comparisons")
        entries = group.get("comparisons")
        if not isinstance(entries, list) or len(entries) != len(by_sample):
            raise V4_3ArtifactError("paired comparison coverage mismatch")
        seen = set()
        eligible_count = 0
        for entry in entries:
            entry = _object(entry, "paired comparison")
            sample = entry.get("q_sample_id")
            if not isinstance(sample, str) or sample not in by_sample or sample in seen:
                raise V4_3ArtifactError("duplicate or unknown comparison sample")
            seen.add(sample)
            arms = by_sample[sample]
            left, right = arms["fourbar"], arms["span_matched_gearbox"]
            lv = (
                left["isotropic_radius"]
                if key == "isotropic_radius"
                else left["directional_capacity"][key]
            )
            rv = (
                right["isotropic_radius"]
                if key == "isotropic_radius"
                else right["directional_capacity"][key]
            )
            eligible = (
                left["status"] == right["status"] == "regular"
                and lv is not None
                and rv is not None
                and rv > 0
            )
            if entry.get("eligible") is not eligible:
                raise V4_3ArtifactError("paired comparison eligibility mismatch")
            for name, expected_value in (
                ("delta", lv - rv if eligible else None),
                ("ratio", lv / rv if eligible else None),
            ):
                field = _field(entry.get(name), name)
                if eligible:
                    if field["status"] != "finite" or not math.isclose(
                        field["value"],
                        _number(expected_value, name),
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    ):
                        raise V4_3ArtifactError(
                            "paired delta/ratio disagrees with retained rows"
                        )
                elif field["value"] is not None or not entry.get("exclusion_reason"):
                    raise V4_3ArtifactError(
                        "ineligible comparison must retain an exclusion reason"
                    )
            eligible_count += int(bool(eligible))
        if (
            group.get("n_pairs") != len(by_sample)
            or group.get("n_eligible") != eligible_count
        ):
            raise V4_3ArtifactError("paired comparison counts mismatch")


def verify_v4_3_artifact(root: Path | str) -> dict[str, Any]:
    """Verify scientific records, complete inventory, and frozen-source joins.

    Legacy v1 is accepted only as the exact immutable historical packet. It
    never qualifies a newly generated or downgraded corrective package.
    """
    package_root = Path(root).expanduser().resolve()
    manifest_path = package_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise V4_3ArtifactError(f"missing {MANIFEST_NAME}")
    manifest = _object(_read_json(manifest_path), "manifest")
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            raise V4_3ArtifactError(f"manifest missing {key!r}")
    if manifest["source_git_dirty"] is not False:
        raise V4_3ArtifactError("source_git_dirty must be Boolean false")
    revision = manifest["source_git_revision"]
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise V4_3ArtifactError(
            "source_git_revision must be a full hexadecimal revision"
        )
    if manifest["package"] != V4_3_ALLOWED_PACKAGE:
        raise V4_3ArtifactError("manifest package mismatch")
    legacy = manifest["schema_version"] == LEGACY_MANIFEST_SCHEMA_VERSION
    if not legacy and manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise V4_3ArtifactError("unsupported manifest schema_version")
    if manifest["manifest_inventory_rule"] != MANIFEST_INVENTORY_RULE:
        raise V4_3ArtifactError("manifest_inventory_rule must be exclude_self")
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise V4_3ArtifactError("manifest files[] must be a non-empty array")
    declared: dict[str, dict[str, Any]] = {}
    for item in files:
        item = _object(item, "inventory record")
        rel = _safe_relative(item.get("path"))
        if rel == MANIFEST_NAME:
            raise V4_3ArtifactError("manifest must exclude itself from files[]")
        if rel in declared:
            raise V4_3ArtifactError(f"duplicate inventory path {rel}")
        declared[rel] = item
    if legacy and _sha256_bytes(manifest_path.read_bytes()) != LEGACY_MANIFEST_SHA256:
        raise V4_3ArtifactError(
            "legacy profile is restricted to the pinned historical manifest"
        )
    case_ids = (
        tuple(manifest["case_ids"]) if isinstance(manifest["case_ids"], list) else ()
    )
    if case_ids != expected_case_ids():
        raise V4_3ArtifactError("manifest case_ids do not match frozen case set")
    for key, count in (
        ("n_rows", FROZEN_V4_2B_N_GEOMETRY_ROWS),
        ("n_cases", FROZEN_V4_2B_N_CASES),
        ("n_pairs", FROZEN_V4_2B_N_ROWS_PER_ARM),
        ("n_typed_failures", 0),
        ("n_silent_drops", 0),
    ):
        _integer(manifest.get(key), count, key)
    followup = (not legacy) and _is_followup_root(package_root)
    live = inventory_package_files(
        package_root, case_ids, legacy=legacy, followup=followup
    )
    live_by_path = {item["path"]: item for item in live}
    if set(live_by_path) != set(declared):
        raise V4_3ArtifactError(
            "files[] path set mismatch with complete filesystem inventory"
        )
    for rel, record in live_by_path.items():
        for key, value in record.items():
            if declared[rel].get(key) != value:
                raise V4_3ArtifactError(f"{key} mismatch for {rel}")
    digest = files_digest(live)
    if manifest["files_digest"] != digest:
        raise V4_3ArtifactError("files_digest mismatch")
    if legacy and digest != LEGACY_FILES_DIGEST:
        raise V4_3ArtifactError("historical packet digest differs from immutable pin")
    per_arm: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    retained_rows: list[dict[str, Any]] = []
    n_pairs = 0
    for case_id in case_ids:
        source_rel = f"geometry_atlas/cases/{case_id}/geometry_samples.jsonl.gz"
        source_rows = list(
            _iter_jsonl_objects(
                canonical_v4_2b_retained_root() / source_rel, compression="gzip"
            )
        )
        sources = {
            (row["q_sample_id"], row["mechanism_id"]): row for row in source_rows
        }
        if len(sources) != 33 * 33 * 3 or len(source_rows) != len(sources):
            raise V4_3ArtifactError("frozen source identity coverage mismatch")
        output_rows = list(
            _iter_jsonl_objects(
                package_root / case_wrench_rel(case_id), compression="gzip"
            )
        )
        grid_arms: dict[tuple[int, int], dict[str, dict[str, Any]]] = {}
        for row in output_rows:
            _validate_row(row, legacy=legacy)
            if row["case_id"] != case_id or row["source_relpath"] != source_rel:
                raise V4_3ArtifactError("case/source path mismatch inside rows")
            identity = (row["q_sample_id"], row["mechanism_id"])
            source = sources.pop(identity, None)
            if source is None:
                raise V4_3ArtifactError("duplicate or unknown retained source identity")
            _verify_source_record(row, source, legacy=legacy)
            grid = tuple(row["grid_index"])
            grid_arms.setdefault(grid, {})[row["mechanism_id"]] = row
            per_arm[row["mechanism_id"]] += 1
            statuses[row["status"]] += 1
            retained_rows.append(row)
        if sources:
            raise V4_3ArtifactError(
                "silent drop: frozen source identities missing from output"
            )
        if set(grid_arms) != {(i, j) for i in range(33) for j in range(33)}:
            raise V4_3ArtifactError("per-case grid coverage mismatch")
        for arms in grid_arms.values():
            if set(arms) != set(FROZEN_MECHANISM_IDS):
                raise V4_3ArtifactError("incomplete three-arm pair")
            reference = arms["fourbar"]
            for row in arms.values():
                for key in ("q", "x"):
                    if not np.allclose(row[key], reference[key], rtol=0, atol=1e-9):
                        raise V4_3ArtifactError("paired arms do not share physical Q/X")
        n_pairs += len(grid_arms)
        _verify_case_summary(
            package_root,
            case_id,
            output_rows,
            legacy=legacy,
            followup=followup,
        )
    n_rows = sum(per_arm.values())
    expected_per_arm = {
        mech: FROZEN_V4_2B_N_ROWS_PER_ARM for mech in FROZEN_MECHANISM_IDS
    }
    if dict(per_arm) != expected_per_arm or n_rows != FROZEN_V4_2B_N_GEOMETRY_ROWS:
        raise V4_3ArtifactError("actual row/arm counts disagree with frozen corpus")
    coverage = _object(_read_json(package_root / "coverage.json"), "coverage")
    validation = _object(_read_json(package_root / "validation.json"), "validation")
    for document in (manifest, coverage):
        if document.get("n_rows_per_arm") != dict(per_arm) or document.get(
            "status_counts"
        ) != dict(statuses):
            raise V4_3ArtifactError(
                "declared arm/status counts disagree with actual rows"
            )
        for key, count in (
            ("n_rows", n_rows),
            ("n_cases", len(case_ids)),
            ("n_pairs", n_pairs),
            ("n_typed_failures", 0),
            ("n_silent_drops", 0),
        ):
            _integer(document.get(key), count, key)
    if coverage.get("mode") != "canonical" or coverage.get("mechanisms") != list(
        FROZEN_MECHANISM_IDS
    ):
        raise V4_3ArtifactError("coverage mode/mechanisms mismatch")
    if (
        validation.get("status_counts") != dict(statuses)
        or validation.get("require_full_corpus") is not True
    ):
        raise V4_3ArtifactError("validation counts/full-corpus flag mismatch")
    for key in ("n_typed_failures", "n_silent_drops"):
        _integer(validation.get(key), 0, key)
    if followup:
        expected_diagnostics = aggregate_vertex_diagnostics(retained_rows)
        for key, expected in expected_diagnostics.items():
            if key == "status_counts":
                continue
            if validation.get(key) != expected:
                raise V4_3ArtifactError(
                    f"validation {key} disagrees with retained vertex diagnostics"
                )
    cases = _read_json(package_root / "cases.json")
    if not isinstance(cases, list) or [case.get("case_id") for case in cases] != list(
        case_ids
    ):
        raise V4_3ArtifactError("case metadata inventory mismatch")
    _verify_provenance(package_root, manifest, legacy=legacy)
    predecessor = _object(
        _read_json(package_root / "predecessor_integrity.json"), "predecessor_integrity"
    )
    if predecessor.get("v4_2b_files_digest") != FROZEN_V4_2B_FILES_DIGEST:
        raise V4_3ArtifactError("predecessor_integrity V4.2B digest mismatch")
    live_pred = snapshot_predecessor_integrity(include_original_v4_3=not legacy)
    recorded = _object(predecessor.get("packages"), "predecessor packages")
    if recorded != live_pred["packages"]:
        raise V4_3ArtifactError(
            "frozen predecessor inventories changed after packaging"
        )
    return {
        "package": V4_3_ALLOWED_PACKAGE,
        "root": str(package_root),
        "n_files": len(live),
        "n_rows": n_rows,
        "n_cases": len(case_ids),
        "files_digest": digest,
        "n_rows_per_arm": dict(per_arm),
        "status_counts": dict(statuses),
        "n_typed_failures": 0,
        "n_silent_drops": 0,
        "source_git_revision": manifest["source_git_revision"],
        "verification_profile": (
            "frozen_historical_v1"
            if legacy
            else "followup_v3"
            if followup
            else "corrective_v2"
        ),
    }


def aggregate_vertex_diagnostics(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize vertex-feasibility diagnostics separately from typed failures."""
    status_counts: Counter[str] = Counter()
    failures_by_status: Counter[str] = Counter()
    failures_by_case: Counter[str] = Counter()
    max_corner: dict[str, float] = {}
    max_hrep: dict[str, float] = {}
    for row in rows:
        status = row.get("status")
        if not isinstance(status, str):
            continue
        status_counts[status] += 1
        feasibility = row.get("vertex_feasibility")
        if not isinstance(feasibility, Mapping):
            continue
        corner = feasibility.get("max_corner_saturation_residual")
        hrep = feasibility.get("max_hrep_residual")
        if isinstance(corner, (int, float)) and math.isfinite(corner):
            prior = max_corner.get(status)
            if prior is None or float(corner) > prior:
                max_corner[status] = float(corner)
        if isinstance(hrep, (int, float)) and math.isfinite(hrep):
            prior = max_hrep.get(status)
            if prior is None or float(hrep) > prior:
                max_hrep[status] = float(hrep)
        if feasibility.get("ok") is False:
            failures_by_status[status] += 1
            case_id = row.get("case_id")
            if isinstance(case_id, str):
                failures_by_case[case_id] += 1
    return {
        "status_counts": dict(sorted(status_counts.items())),
        "vertex_diagnostic_failures_by_status": dict(
            sorted(failures_by_status.items())
        ),
        "vertex_diagnostic_failures_by_case": dict(sorted(failures_by_case.items())),
        "max_corner_residual": dict(sorted(max_corner.items())),
        "max_hrep_residual": dict(sorted(max_hrep.items())),
    }
