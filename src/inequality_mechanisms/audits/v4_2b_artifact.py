"""Retained-file inventory and fail-closed verifier for V4.2B packages."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import zlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from inequality_mechanisms.experiments.span_cases import generate_span_cases
from inequality_mechanisms.experiments.v4.geometry_atlas import (
    ATLAS_ROW_SCHEMA_VERSION,
    AtlasRecordError,
    parse_retained_atlas_row,
)
from inequality_mechanisms.experiments.v4.span_common_physical_bank import (
    DEFAULT_BANK_REL,
    load_common_physical_bank,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    FROZEN_V3_6D_DIGEST,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_config import (
    SCHEMA_VERSION as PACKAGE_SCHEMA_VERSION,
    V4_2B_PACKAGE,
)

MANIFEST_INVENTORY_RULE = "exclude_self"
MANIFEST_NAME = "manifest.json"
PLANNING_AUDIT_MANIFEST_REL = "planning_audit/manifest.json"
REQUIRED_MANIFEST_KEYS = (
    "schema_version",
    "package",
    "manifest_inventory_rule",
    "source_git_revision",
    "source_git_dirty",
    "config_digest",
    "v3_6d_registry_digest",
    "common_task_bank_digest",
    "case_ids",
    "n_rows",
    "n_typed_failures",
    "n_silent_drops",
    "files",
    "files_digest",
)
REQUIRED_ROOT_FILES = (
    "cases.json",
    "resolved_config.json",
    "rank_fields.json",
    "README.md",
    "index.html",
)
FILE_RECORD_KEYS = (
    "path",
    "sha256",
    "byte_count",
    "row_count",
    "schema_version",
    "media_type",
    "compression",
)
SOURCE_GIT_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class V4_2BArtifactError(ValueError):
    """Raised when a V4.2B retained package fails integrity checks."""

    failure_code = "v4_2b_artifact_integrity_failed"


def expected_case_ids() -> tuple[str, ...]:
    """Return the frozen ordered 17 V4.2B case ids."""
    return tuple(case.case_id for case in generate_span_cases())


def frozen_common_task_bank_digest() -> str:
    """Return the committed common-physical bank digest."""
    from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT

    payload = load_common_physical_bank(CANONICAL_REPO_ROOT / DEFAULT_BANK_REL)
    return str(payload["sha256"])


def case_geometry_rel(case_id: str) -> str:
    """Return the per-case compressed geometry path."""
    return f"geometry_atlas/cases/{case_id}/geometry_samples.jsonl.gz"


def required_paths(
    case_ids: Sequence[str],
    *,
    include_planning: bool = False,
) -> tuple[str, ...]:
    """Return required retained paths excluding ``manifest.json``."""
    geometry = tuple(case_geometry_rel(str(case_id)) for case_id in case_ids)
    extra = (PLANNING_AUDIT_MANIFEST_REL,) if include_planning else ()
    return geometry + REQUIRED_ROOT_FILES + extra


def _is_geometry_rel(rel: str) -> bool:
    normalized = rel.replace("\\", "/")
    return (
        normalized.startswith("geometry_atlas/")
        or "/geometry_atlas/" in normalized
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_hex_digest(value: object, *, field: str) -> str:
    text = str(value)
    if SHA256_RE.fullmatch(text) is None:
        raise V4_2BArtifactError(f"{field} must be a 64-char hex digest")
    return text


def _iter_jsonl_objects(path: Path, *, compression: str):
    if compression == "gzip":
        opener = gzip.open
    elif compression == "none":
        opener = open
    else:
        raise V4_2BArtifactError(f"unsupported compression {compression!r} for {path}")
    try:
        with opener(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise V4_2BArtifactError(f"{path} jsonl row is not an object")
                yield payload
    except json.JSONDecodeError as exc:
        raise V4_2BArtifactError(f"schema mismatch in {path}: {exc}") from exc
    except (OSError, EOFError, gzip.BadGzipFile, zlib.error, UnicodeDecodeError) as exc:
        raise V4_2BArtifactError(f"decompression failure for {path}: {exc}") from exc


def _count_jsonl_rows(
    path: Path,
    *,
    compression: str,
    parse_geometry: bool,
) -> int:
    count = 0
    for payload in _iter_jsonl_objects(path, compression=compression):
        if parse_geometry:
            try:
                parse_retained_atlas_row(payload)
            except AtlasRecordError as exc:
                raise V4_2BArtifactError(
                    f"schema mismatch in {path}: {exc}"
                ) from exc
        count += 1
    return count


def inventory_file(
    root: Path,
    rel: str,
    *,
    schema_version: str,
    media_type: str,
    compression: str,
) -> dict[str, Any]:
    """Return one manifest ``files[]`` record for ``rel`` under ``root``."""
    path = Path(root) / rel
    if not path.is_file():
        raise V4_2BArtifactError(f"missing required file {rel}")
    payload = path.read_bytes()
    row_count: int | None
    if rel.endswith(".jsonl") or rel.endswith(".jsonl.gz"):
        parse_geometry = _is_geometry_rel(rel)
        row_count = _count_jsonl_rows(
            path, compression=compression, parse_geometry=parse_geometry
        )
    else:
        row_count = None
        if rel.endswith(".json"):
            try:
                json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise V4_2BArtifactError(f"schema mismatch in {rel}: {exc}") from exc
    return {
        "path": rel,
        "sha256": _sha256_bytes(payload),
        "byte_count": len(payload),
        "row_count": row_count,
        "schema_version": schema_version,
        "media_type": media_type,
        "compression": compression,
    }


def media_for(rel: str) -> tuple[str, str, str]:
    """Return ``(schema_version, media_type, compression)`` for a retained path."""
    if rel.endswith(".jsonl.gz"):
        schema = (
            ATLAS_ROW_SCHEMA_VERSION
            if _is_geometry_rel(rel)
            else PACKAGE_SCHEMA_VERSION
        )
        return schema, "application/gzip", "gzip"
    if rel.endswith(".json"):
        return PACKAGE_SCHEMA_VERSION, "application/json", "none"
    if rel.endswith(".md"):
        return PACKAGE_SCHEMA_VERSION, "text/markdown", "none"
    if rel.endswith(".html"):
        return PACKAGE_SCHEMA_VERSION, "text/html", "none"
    raise V4_2BArtifactError(f"unsupported retained file type for {rel}")


def inventory_required_files(root: Path, case_ids: Sequence[str]) -> list[dict[str, Any]]:
    """Build the excluded-self ``files[]`` table for a generated package."""
    planning = (Path(root) / "planning_audit").exists()
    records = []
    for rel in required_paths(case_ids, include_planning=planning):
        schema_version, media_type, compression = media_for(rel)
        records.append(
            inventory_file(
                root,
                rel,
                schema_version=schema_version,
                media_type=media_type,
                compression=compression,
            )
        )
    return records


def files_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """Stable digest of listed files, excluding the manifest."""
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda row: str(row["path"])):
        digest.update(str(record["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _require_record_keys(record: Mapping[str, Any], *, rel: str) -> None:
    missing = [key for key in FILE_RECORD_KEYS if key not in record]
    if missing:
        raise V4_2BArtifactError(f"files[] entry for {rel} missing {missing}")


def _require_manifest_keys(manifest: Mapping[str, Any]) -> None:
    missing = [key for key in REQUIRED_MANIFEST_KEYS if key not in manifest]
    if missing:
        raise V4_2BArtifactError(f"manifest missing required keys: {missing}")


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise V4_2BArtifactError(f"missing {path.name} in {path.parent}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V4_2BArtifactError(f"schema mismatch in {path.name}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise V4_2BArtifactError(f"{path.name} must be a JSON object")
    return manifest


def _verify_file_records(
    package: Path,
    listed: Sequence[Mapping[str, Any]],
    *,
    parse_geometry: bool,
) -> tuple[list[str], int]:
    listed_paths: list[str] = []
    recovered_rows = 0
    for record in listed:
        if not isinstance(record, dict):
            raise V4_2BArtifactError("files[] entries must be objects")
        rel = str(record.get("path", ""))
        _require_record_keys(record, rel=rel or "<missing>")
        if rel == MANIFEST_NAME:
            raise V4_2BArtifactError("manifest.json must be excluded from files[]")
        listed_paths.append(rel)
        path = package / rel
        if not path.is_file():
            raise V4_2BArtifactError(f"missing listed file {rel}")
        payload = path.read_bytes()
        actual_hash = _sha256_bytes(payload)
        actual_bytes = len(payload)
        if actual_hash != str(record["sha256"]):
            raise V4_2BArtifactError(f"sha256 mismatch for {rel}")
        if int(record["byte_count"]) != actual_bytes:
            raise V4_2BArtifactError(f"byte_count mismatch for {rel}")
        compression = str(record["compression"])
        schema_version, media_type, expected_compression = media_for(rel)
        if compression != expected_compression:
            raise V4_2BArtifactError(f"compression mismatch for {rel}")
        if str(record["media_type"]) != media_type:
            raise V4_2BArtifactError(f"media_type mismatch for {rel}")
        if str(record["schema_version"]) != schema_version:
            raise V4_2BArtifactError(f"schema_version mismatch for {rel}")
        if rel.endswith(".jsonl") or rel.endswith(".jsonl.gz"):
            geometry = parse_geometry and _is_geometry_rel(rel)
            actual_rows = _count_jsonl_rows(
                path, compression=compression, parse_geometry=geometry
            )
            recorded_rows = record["row_count"]
            if recorded_rows is None or int(recorded_rows) != actual_rows:
                raise V4_2BArtifactError(f"row_count mismatch for {rel}")
            recovered_rows += actual_rows
        else:
            if record["row_count"] is not None:
                raise V4_2BArtifactError(f"row_count must be null for {rel}")
            if rel.endswith(".json"):
                try:
                    json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise V4_2BArtifactError(f"schema mismatch in {rel}: {exc}") from exc
    return listed_paths, recovered_rows


def _verify_nested_planning_audit(package: Path) -> None:
    nested_root = package / "planning_audit"
    manifest = _load_manifest(nested_root / MANIFEST_NAME)
    _require_manifest_keys(manifest)
    if manifest.get("package") not in (V4_2B_PACKAGE, f"{V4_2B_PACKAGE}/planning_audit"):
        raise V4_2BArtifactError(
            "planning_audit package must be "
            f"{V4_2B_PACKAGE!r} or '{V4_2B_PACKAGE}/planning_audit'"
        )
    if str(manifest.get("schema_version")) != PACKAGE_SCHEMA_VERSION:
        raise V4_2BArtifactError(
            "planning_audit schema_version must be "
            f"{PACKAGE_SCHEMA_VERSION!r}, got {manifest.get('schema_version')!r}"
        )
    if manifest["source_git_dirty"] is not False:
        raise V4_2BArtifactError("source_git_dirty must be false")
    listed = manifest.get("files")
    if not isinstance(listed, list) or not listed:
        raise V4_2BArtifactError("planning_audit files[] is missing or empty")
    listed_paths, _recovered = _verify_file_records(
        nested_root, listed, parse_geometry=False
    )
    recorded_digest = _require_hex_digest(
        manifest.get("files_digest"), field="files_digest"
    )
    actual_digest = files_digest(listed)
    if recorded_digest != actual_digest:
        raise V4_2BArtifactError("planning_audit files_digest mismatch")
    if MANIFEST_NAME in listed_paths:
        raise V4_2BArtifactError("planning_audit manifest.json must be excluded from files[]")


def verify_v4_2b_artifact(root: Path | str) -> dict[str, Any]:
    """Verify a V4.2B retained package against its manifest inventory.

    Parameters
    ----------
    root :
        Package directory containing ``manifest.json``.

    Returns
    -------
    dict
        Summary with file count, recovered geometry row count, and digest.

    Raises
    ------
    V4_2BArtifactError
        If any required file, hash, byte count, row count, or schema fails.
    """
    package = Path(root).expanduser().resolve()
    manifest = _load_manifest(package / MANIFEST_NAME)
    _require_manifest_keys(manifest)
    if manifest.get("package") != V4_2B_PACKAGE:
        raise V4_2BArtifactError(
            f"manifest package must be {V4_2B_PACKAGE!r}, got {manifest.get('package')!r}"
        )
    if str(manifest.get("schema_version")) != PACKAGE_SCHEMA_VERSION:
        raise V4_2BArtifactError(
            "manifest schema_version must be "
            f"{PACKAGE_SCHEMA_VERSION!r}, got {manifest.get('schema_version')!r}"
        )
    rule = str(manifest.get("manifest_inventory_rule", ""))
    if rule != MANIFEST_INVENTORY_RULE:
        raise V4_2BArtifactError(
            f"manifest_inventory_rule must be {MANIFEST_INVENTORY_RULE!r}, got {rule!r}"
        )
    if manifest["source_git_dirty"] is not False:
        raise V4_2BArtifactError("source_git_dirty must be false")
    sha = str(manifest["source_git_revision"])
    if SOURCE_GIT_REVISION_RE.fullmatch(sha) is None:
        raise V4_2BArtifactError("source_git_revision must be a 40-char hex SHA")
    _require_hex_digest(manifest["config_digest"], field="config_digest")
    v3_digest = _require_hex_digest(
        manifest["v3_6d_registry_digest"], field="v3_6d_registry_digest"
    )
    if v3_digest != FROZEN_V3_6D_DIGEST:
        raise V4_2BArtifactError(
            "v3_6d_registry_digest must match the frozen V3.6D registry"
        )
    bank_digest = _require_hex_digest(
        manifest["common_task_bank_digest"], field="common_task_bank_digest"
    )
    if bank_digest != frozen_common_task_bank_digest():
        raise V4_2BArtifactError(
            "common_task_bank_digest must match the frozen common-physical bank"
        )
    if int(manifest["n_silent_drops"]) != 0:
        raise V4_2BArtifactError("n_silent_drops must be 0")
    case_ids = manifest.get("case_ids")
    if not isinstance(case_ids, list):
        raise V4_2BArtifactError("manifest case_ids must be a list")
    case_ids_t = tuple(str(item) for item in case_ids)
    expected_ids = expected_case_ids()
    if case_ids_t != expected_ids:
        raise V4_2BArtifactError(
            f"case_ids must be the exact 17 V4.2B ids, got {list(case_ids_t)}"
        )
    listed = manifest.get("files")
    if not isinstance(listed, list) or not listed:
        raise V4_2BArtifactError("manifest files[] is missing or empty")
    include_planning = (package / "planning_audit").exists()
    expected = set(required_paths(case_ids_t, include_planning=include_planning))
    listed_paths, recovered_rows = _verify_file_records(
        package, listed, parse_geometry=True
    )
    listed_set = set(listed_paths)
    missing = sorted(expected - listed_set)
    if missing:
        raise V4_2BArtifactError(f"required-file omission: {missing}")
    extra = sorted(listed_set - expected)
    if extra:
        raise V4_2BArtifactError(f"unexpected files[] paths: {extra}")
    recorded_digest = _require_hex_digest(
        manifest.get("files_digest"), field="files_digest"
    )
    actual_digest = files_digest(listed)
    if recorded_digest != actual_digest:
        raise V4_2BArtifactError("files_digest mismatch")
    recorded_rows = manifest.get("n_rows")
    recorded_typed = int(manifest.get("n_typed_failures") or 0)
    expected_total = int(recorded_rows) + recorded_typed
    if recovered_rows != expected_total:
        raise V4_2BArtifactError(
            "recovered geometry row count "
            f"{recovered_rows} disagrees with manifest "
            f"n_rows={recorded_rows} n_typed_failures={recorded_typed}"
        )
    if include_planning:
        _verify_nested_planning_audit(package)
    return {
        "package": V4_2B_PACKAGE,
        "n_files": len(listed_paths),
        "n_geometry_rows": recovered_rows,
        "files_digest": actual_digest,
        "root": str(package),
    }


__all__ = [
    "FILE_RECORD_KEYS",
    "MANIFEST_INVENTORY_RULE",
    "MANIFEST_NAME",
    "PLANNING_AUDIT_MANIFEST_REL",
    "REQUIRED_MANIFEST_KEYS",
    "REQUIRED_ROOT_FILES",
    "SHA256_RE",
    "SOURCE_GIT_REVISION_RE",
    "V4_2BArtifactError",
    "case_geometry_rel",
    "expected_case_ids",
    "files_digest",
    "frozen_common_task_bank_digest",
    "inventory_file",
    "inventory_required_files",
    "media_for",
    "required_paths",
    "verify_v4_2b_artifact",
]
