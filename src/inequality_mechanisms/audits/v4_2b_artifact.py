"""Retained-file inventory and fail-closed verifier for V4.2B packages."""

from __future__ import annotations

import gzip
import hashlib
import json
import zlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from inequality_mechanisms.experiments.v4.geometry_atlas import ATLAS_ROW_SCHEMA_VERSION
from inequality_mechanisms.experiments.v4.span_controlled_corrective_config import (
    SCHEMA_VERSION as PACKAGE_SCHEMA_VERSION,
    V4_2B_PACKAGE,
)

MANIFEST_INVENTORY_RULE = "exclude_self"
MANIFEST_NAME = "manifest.json"
JSONL_ROW_KEYS = ("schema_version", "q_sample_id", "mechanism_id")
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


class V4_2BArtifactError(ValueError):
    """Raised when a V4.2B retained package fails integrity checks."""

    failure_code = "v4_2b_artifact_integrity_failed"


def case_geometry_rel(case_id: str) -> str:
    """Return the per-case compressed geometry path."""
    return f"geometry_atlas/cases/{case_id}/geometry_samples.jsonl.gz"


def required_paths(case_ids: Sequence[str]) -> tuple[str, ...]:
    """Return required retained paths excluding ``manifest.json``."""
    geometry = tuple(case_geometry_rel(str(case_id)) for case_id in case_ids)
    return geometry + REQUIRED_ROOT_FILES


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _count_jsonl_rows(path: Path, *, compression: str) -> int:
    if compression == "gzip":
        opener = gzip.open
    elif compression == "none":
        opener = open
    else:
        raise V4_2BArtifactError(f"unsupported compression {compression!r} for {path}")
    count = 0
    try:
        with opener(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise V4_2BArtifactError(f"{path} jsonl row is not an object")
                missing = [key for key in JSONL_ROW_KEYS if key not in payload]
                if missing:
                    raise V4_2BArtifactError(
                        f"{path} jsonl schema mismatch, missing {missing}"
                    )
                count += 1
    except json.JSONDecodeError as exc:
        raise V4_2BArtifactError(f"schema mismatch in {path}: {exc}") from exc
    except (OSError, EOFError, gzip.BadGzipFile, zlib.error, UnicodeDecodeError) as exc:
        raise V4_2BArtifactError(f"decompression failure for {path}: {exc}") from exc
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
        row_count = _count_jsonl_rows(path, compression=compression)
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
        return ATLAS_ROW_SCHEMA_VERSION, "application/gzip", "gzip"
    if rel.endswith(".json"):
        return PACKAGE_SCHEMA_VERSION, "application/json", "none"
    if rel.endswith(".md"):
        return PACKAGE_SCHEMA_VERSION, "text/markdown", "none"
    if rel.endswith(".html"):
        return PACKAGE_SCHEMA_VERSION, "text/html", "none"
    raise V4_2BArtifactError(f"unsupported retained file type for {rel}")


def inventory_required_files(root: Path, case_ids: Sequence[str]) -> list[dict[str, Any]]:
    """Build the excluded-self ``files[]`` table for a generated package."""
    records = []
    for rel in required_paths(case_ids):
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
    manifest_path = package / MANIFEST_NAME
    if not manifest_path.is_file():
        raise V4_2BArtifactError(f"missing {MANIFEST_NAME} in {package}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V4_2BArtifactError(f"schema mismatch in {MANIFEST_NAME}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise V4_2BArtifactError("manifest.json must be a JSON object")
    if manifest.get("package") not in (None, V4_2B_PACKAGE):
        raise V4_2BArtifactError(
            f"manifest package must be {V4_2B_PACKAGE!r}, got {manifest.get('package')!r}"
        )
    rule = str(manifest.get("manifest_inventory_rule", ""))
    if rule != MANIFEST_INVENTORY_RULE:
        raise V4_2BArtifactError(
            f"manifest_inventory_rule must be {MANIFEST_INVENTORY_RULE!r}, got {rule!r}"
        )
    listed = manifest.get("files")
    if not isinstance(listed, list) or not listed:
        raise V4_2BArtifactError("manifest files[] is missing or empty")
    case_ids = [str(item) for item in manifest.get("case_ids", [])]
    if not case_ids:
        raise V4_2BArtifactError("manifest case_ids is missing or empty")
    expected = set(required_paths(case_ids))
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
            actual_rows = _count_jsonl_rows(path, compression=compression)
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
    listed_set = set(listed_paths)
    missing = sorted(expected - listed_set)
    if missing:
        raise V4_2BArtifactError(f"required-file omission: {missing}")
    extra = sorted(listed_set - expected)
    if extra:
        raise V4_2BArtifactError(f"unexpected files[] paths: {extra}")
    recorded_digest = str(manifest.get("files_digest", ""))
    actual_digest = files_digest(listed)
    if recorded_digest and recorded_digest != actual_digest:
        raise V4_2BArtifactError("files_digest mismatch")
    recorded_rows = manifest.get("n_rows")
    recorded_typed = int(manifest.get("n_typed_failures") or 0)
    if recorded_rows is not None:
        expected_total = int(recorded_rows) + recorded_typed
        if recovered_rows != expected_total:
            raise V4_2BArtifactError(
                "recovered geometry row count "
                f"{recovered_rows} disagrees with manifest "
                f"n_rows={recorded_rows} n_typed_failures={recorded_typed}"
            )
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
    "REQUIRED_ROOT_FILES",
    "V4_2BArtifactError",
    "case_geometry_rel",
    "files_digest",
    "inventory_file",
    "inventory_required_files",
    "media_for",
    "required_paths",
    "verify_v4_2b_artifact",
]
