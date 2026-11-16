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
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

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
    V4_3_ALLOWED_PACKAGE,
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
    MANIFEST_SCHEMA_VERSION,
    PACKAGE_SCHEMA_VERSION,
    ROW_SCHEMA_VERSION,
    schema_catalog,
)

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


def snapshot_predecessor_integrity() -> dict[str, Any]:
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


def _iter_jsonl_objects(path: Path, *, compression: str) -> Iterator[dict[str, Any]]:
    if compression == "gzip":
        handle_cm = gzip.open(path, "rt", encoding="utf-8")
    elif compression == "none":
        handle_cm = path.open("rt", encoding="utf-8")
    else:
        raise V4_3ArtifactError(f"unsupported compression {compression!r} for {path}")
    try:
        with handle_cm as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise V4_3ArtifactError(f"{path} jsonl row is not an object")
                yield payload
    except json.JSONDecodeError as exc:
        raise V4_3ArtifactError(f"schema mismatch in {path}: {exc}") from exc
    except (OSError, EOFError, gzip.BadGzipFile, zlib.error, UnicodeDecodeError) as exc:
        raise V4_3ArtifactError(f"decompression failure for {path}: {exc}") from exc


def _count_wrench_rows(path: Path) -> int:
    count = 0
    for payload in _iter_jsonl_objects(path, compression="gzip"):
        schema = payload.get("schema_version")
        if schema != ROW_SCHEMA_VERSION:
            raise V4_3ArtifactError(
                f"{path}: row schema_version must be {ROW_SCHEMA_VERSION!r}, "
                f"got {schema!r}"
            )
        for key in ("case_id", "q_sample_id", "mechanism_id", "grid_index"):
            if key not in payload:
                raise V4_3ArtifactError(f"{path}: wrench row missing {key!r}")
        count += 1
    return count


def inventory_file(root: Path, rel: str) -> dict[str, Any]:
    """Return one manifest ``files[]`` record for ``rel`` under ``root``."""
    path = Path(root) / rel
    if not path.is_file():
        raise V4_3ArtifactError(f"missing required file {rel}")
    payload = path.read_bytes()
    row_count: int | None = None
    if rel.endswith(".jsonl.gz"):
        row_count = _count_wrench_rows(path)
        media_type, compression = "application/gzip", "gzip"
        schema_version = ROW_SCHEMA_VERSION
    elif rel.endswith(".json"):
        try:
            json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise V4_3ArtifactError(f"schema mismatch in {rel}: {exc}") from exc
        media_type, compression = "application/json", "none"
        schema_version = PACKAGE_SCHEMA_VERSION
    elif rel.endswith(".md"):
        media_type, compression = "text/markdown", "none"
        schema_version = PACKAGE_SCHEMA_VERSION
    elif rel.endswith(".html"):
        media_type, compression = "text/html", "none"
        schema_version = PACKAGE_SCHEMA_VERSION
    elif rel.endswith(".css"):
        media_type, compression = "text/css", "none"
        schema_version = PACKAGE_SCHEMA_VERSION
    elif rel.endswith(".js"):
        media_type, compression = "text/javascript", "none"
        schema_version = PACKAGE_SCHEMA_VERSION
    elif rel.endswith(".png"):
        media_type, compression = "image/png", "none"
        schema_version = PACKAGE_SCHEMA_VERSION
    else:
        raise V4_3ArtifactError(f"unsupported retained file type for {rel}")
    return {
        "path": rel,
        "sha256": _sha256_bytes(payload),
        "byte_count": len(payload),
        "row_count": row_count,
        "schema_version": schema_version,
        "media_type": media_type,
        "compression": compression,
    }


def inventory_package_files(
    root: Path, case_ids: Sequence[str]
) -> list[dict[str, Any]]:
    """Build the exclude-self inventory for a generated V4.3 package."""
    records: list[dict[str, Any]] = []
    for rel in REQUIRED_ROOT_FILES:
        records.append(inventory_file(root, rel))
    for case_id in case_ids:
        for rel in (
            case_wrench_rel(str(case_id)),
            f"cases/{case_id}/summary.json",
            f"cases/{case_id}/index.html",
            f"cases/{case_id}/figures/scalar.png",
            f"cases/{case_id}/figures/polygons.png",
            f"cases/{case_id}/figures/identity_scalar.png",
        ):
            records.append(inventory_file(root, rel))
        # Optional true-scale / directional figures if present.
        case_fig = Path(root) / "cases" / case_id / "figures"
        for path in sorted(case_fig.glob("*.png")):
            rel = path.relative_to(root).as_posix()
            if any(item["path"] == rel for item in records):
                continue
            records.append(inventory_file(root, rel))
    # Optional copied method/trace docs.
    for optional in (
        "biological_reference_trace.md",
        "STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md",
    ):
        if (Path(root) / optional).is_file():
            records.append(inventory_file(root, optional))
    return records


def verify_v4_3_artifact(root: Path | str) -> dict[str, Any]:
    """Fail-closed verification of a retained V4.3 package."""
    package_root = Path(root).expanduser().resolve()
    manifest_path = package_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise V4_3ArtifactError(f"missing {MANIFEST_NAME}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V4_3ArtifactError(f"invalid manifest JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise V4_3ArtifactError("manifest must be a JSON object")
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            raise V4_3ArtifactError(f"manifest missing {key!r}")
    if manifest.get("package") != V4_3_ALLOWED_PACKAGE:
        raise V4_3ArtifactError(
            f"manifest package must be {V4_3_ALLOWED_PACKAGE!r}"
        )
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise V4_3ArtifactError(
            f"manifest schema_version must be {MANIFEST_SCHEMA_VERSION!r}"
        )
    if manifest.get("manifest_inventory_rule") != MANIFEST_INVENTORY_RULE:
        raise V4_3ArtifactError("manifest_inventory_rule must be exclude_self")
    if int(manifest["n_silent_drops"]) != 0:
        raise V4_3ArtifactError("n_silent_drops must be 0")
    if int(manifest["n_typed_failures"]) != 0:
        raise V4_3ArtifactError("n_typed_failures must be 0 for the canonical corpus")
    if int(manifest["n_rows"]) != FROZEN_V4_2B_N_GEOMETRY_ROWS:
        raise V4_3ArtifactError(
            f"n_rows must be {FROZEN_V4_2B_N_GEOMETRY_ROWS}, "
            f"got {manifest['n_rows']}"
        )

    case_ids = tuple(str(v) for v in manifest["case_ids"])
    if case_ids != expected_case_ids():
        raise V4_3ArtifactError("manifest case_ids do not match expected_case_ids()")
    if len(case_ids) != FROZEN_V4_2B_N_CASES:
        raise V4_3ArtifactError(f"expected {FROZEN_V4_2B_N_CASES} cases")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise V4_3ArtifactError("manifest files[] must be a non-empty array")
    for record in files:
        if str(record.get("path")) == MANIFEST_NAME:
            raise V4_3ArtifactError("manifest must exclude itself from files[]")

    live = inventory_package_files(package_root, case_ids)
    live_by_path = {str(item["path"]): item for item in live}
    declared_by_path = {str(item["path"]): item for item in files}
    if set(live_by_path) != set(declared_by_path):
        missing = sorted(set(live_by_path) - set(declared_by_path))
        extra = sorted(set(declared_by_path) - set(live_by_path))
        raise V4_3ArtifactError(
            f"files[] path set mismatch; missing={missing} extra={extra}"
        )
    for rel, live_rec in live_by_path.items():
        declared = declared_by_path[rel]
        if live_rec["sha256"] != declared["sha256"]:
            raise V4_3ArtifactError(f"sha256 mismatch for {rel}")
        if live_rec["byte_count"] != declared["byte_count"]:
            raise V4_3ArtifactError(f"byte_count mismatch for {rel}")
        if live_rec["row_count"] != declared.get("row_count"):
            raise V4_3ArtifactError(f"row_count mismatch for {rel}")

    digest = files_digest(live)
    declared_digest = str(manifest["files_digest"])
    if SHA256_RE.fullmatch(declared_digest) is None:
        raise V4_3ArtifactError("files_digest must be a 64-char hex digest")
    if digest != declared_digest:
        raise V4_3ArtifactError(
            f"files_digest mismatch: live={digest} manifest={declared_digest}"
        )

    n_rows = 0
    per_arm = {mech: 0 for mech in FROZEN_MECHANISM_IDS}
    for case_id in case_ids:
        rel = case_wrench_rel(case_id)
        path = package_root / rel
        for payload in _iter_jsonl_objects(path, compression="gzip"):
            n_rows += 1
            mech = str(payload["mechanism_id"])
            if mech not in per_arm:
                raise V4_3ArtifactError(f"unknown mechanism_id {mech!r} in {rel}")
            per_arm[mech] += 1
            if str(payload["case_id"]) != case_id:
                raise V4_3ArtifactError(f"{rel}: case_id mismatch inside rows")
    if n_rows != FROZEN_V4_2B_N_GEOMETRY_ROWS:
        raise V4_3ArtifactError(
            f"decompressed row count {n_rows} != {FROZEN_V4_2B_N_GEOMETRY_ROWS}"
        )
    for mech in FROZEN_MECHANISM_IDS:
        if per_arm[mech] != FROZEN_V4_2B_N_ROWS_PER_ARM:
            raise V4_3ArtifactError(
                f"arm {mech} rows {per_arm[mech]} != {FROZEN_V4_2B_N_ROWS_PER_ARM}"
            )

    predecessor = json.loads(
        (package_root / "predecessor_integrity.json").read_text(encoding="utf-8")
    )
    if predecessor.get("v4_2b_files_digest") != FROZEN_V4_2B_FILES_DIGEST:
        raise V4_3ArtifactError("predecessor_integrity V4.2B digest mismatch")
    live_pred = snapshot_predecessor_integrity()
    recorded_packages = predecessor.get("packages")
    if not isinstance(recorded_packages, dict):
        raise V4_3ArtifactError("predecessor_integrity packages must be an object")
    for label, live_rec in live_pred["packages"].items():
        recorded = recorded_packages.get(label)
        if not isinstance(recorded, dict):
            raise V4_3ArtifactError(
                f"predecessor_integrity missing package record {label!r}"
            )
        if recorded.get("git_tracked_digest") != live_rec["git_tracked_digest"]:
            raise V4_3ArtifactError(
                f"predecessor {label} git-tracked digest changed after packaging"
            )
        if int(recorded.get("n_git_tracked_files", -1)) != int(
            live_rec["n_git_tracked_files"]
        ):
            raise V4_3ArtifactError(
                f"predecessor {label} git-tracked file count changed after packaging"
            )

    return {
        "package": V4_3_ALLOWED_PACKAGE,
        "root": str(package_root),
        "n_files": len(live),
        "n_rows": n_rows,
        "n_cases": len(case_ids),
        "files_digest": digest,
        "n_rows_per_arm": per_arm,
        "source_git_revision": manifest.get("source_git_revision"),
    }
