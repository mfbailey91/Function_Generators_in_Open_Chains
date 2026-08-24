"""V4-239 retained-package inventory, compressed extracts, and verifier."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.audits.v4_2b_artifact import verify_v4_2b_artifact
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_2C_ALLOWED_OUTPUT_REL,
    V4_2C_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    DirtySourceError,
    assert_v4_2c_output_allowed,
    canonical_v4_2b_retained_root,
    git_rev_parse_head,
    git_status_porcelain,
)
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import (
    OPTIONAL_PLANNER_IDS,
    write_atomic_json,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    CALIBRATION_SELECTION_SCHEMA,
    CONTROL_PLANNER_IDS,
    FROZEN_V4_2B_FILES_DIGEST,
    FROZEN_V4_2B_N_FILES,
    FROZEN_V4_2B_N_GEOMETRY_ROWS,
    NO_INFERENCE_STATEMENT,
    PRIMARY_PLANNER_IDS,
    PROJECTION_PLANNER_IDS,
)
from inequality_mechanisms.visualization.v4.ompl_planner_portfolio import (
    INTERPRETATION_BOUNDARY,
    LEDE,
    PROHIBITED_CLAIMS,
    href_targets,
    write_ompl_planner_portfolio_report,
)

PACKAGE_SCHEMA = "v4.2c.ompl_planner_portfolio.package.v1"
MANIFEST_INVENTORY_RULE = "exclude_self"
MANIFEST_NAME = "manifest.json"
STAGE_A = "stage_a"
STAGE_B = "stage_b"
STAGE_C = "stage_c"
FROZEN_STAGE_ROWS = {STAGE_A: 32, STAGE_B: 768, STAGE_C: 6200}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_GIT_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class V4_2CArtifactError(ValueError):
    """Raised when a V4.2C retained package fails integrity or packaging."""

    failure_code = "v4_2c_artifact_integrity_failed"


def _porcelain_path(line: str) -> str:
    """Return the path field from one ``git status --porcelain`` line."""
    payload = line[3:] if len(line) >= 3 else line
    if " -> " in payload:
        payload = payload.split(" -> ", 1)[1]
    return payload.strip().strip('"')


def _is_v4_2c_package_porcelain(line: str) -> bool:
    """True when the porcelain path is the allowed V4.2C package or a child."""
    rel = _porcelain_path(line)
    allowed = V4_2C_ALLOWED_OUTPUT_REL.as_posix()
    return rel == allowed or rel.startswith(f"{allowed}/")


def write_calibration_selection(path: Path, *, calibration_config_digest: str) -> Path:
    """Write the digest-locked Stage B selection file under the V4.2C root."""
    resolved = assert_v4_2c_output_allowed(path)
    if not SHA256_RE.fullmatch(str(calibration_config_digest)):
        raise V4_2CArtifactError(
            "calibration_config_digest must be a 64-char hex digest"
        )
    write_atomic_json(
        resolved,
        {
            "schema_version": CALIBRATION_SELECTION_SCHEMA,
            "calibration_config_digest": str(calibration_config_digest),
        },
    )
    return resolved


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _iter_json_objects(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _write_jsonl_gz(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(dict(row), sort_keys=True, separators=(",", ":")) + "\n"
            )


def _stage_counts(stage_dir: Path) -> dict[str, Any]:
    matrix_path = stage_dir / "request_matrix.json"
    progress_path = stage_dir / "progress.json"
    if not matrix_path.is_file():
        raise V4_2CArtifactError(f"missing {matrix_path}")
    matrix = _read_json(matrix_path)
    progress = _read_json(progress_path) if progress_path.is_file() else {}
    if not isinstance(matrix, dict):
        raise V4_2CArtifactError(f"{matrix_path} must be a JSON object")
    n_rows = int(matrix.get("n_rows") or 0)
    n_completed = (
        len(list((stage_dir / "rows").glob("*.json")))
        if (stage_dir / "rows").is_dir()
        else 0
    )
    n_failed = (
        len(list((stage_dir / "attempts").glob("*.json")))
        if (stage_dir / "attempts").is_dir()
        else 0
    )
    return {
        "n_rows": n_rows,
        "n_completed_files": n_completed,
        "n_attempt_files": n_failed,
        "config_digest": matrix.get("config_digest"),
        "progress": progress if isinstance(progress, dict) else {},
    }


def _checkpoints_from_row(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    worker = row.get("worker") if isinstance(row.get("worker"), Mapping) else {}
    result = worker.get("result") if isinstance(worker.get("result"), Mapping) else {}
    records = (
        result.get("planner_metrics", {}).get("ompl", {}).get("checkpoints")
        if isinstance(result.get("planner_metrics"), Mapping)
        else None
    )
    if not isinstance(records, list):
        return []
    out = []
    for item in records:
        if isinstance(item, Mapping):
            out.append(
                {
                    "request_digest": row.get("request_digest"),
                    "planner_id": row.get("planner_id"),
                    "case_id": row.get("case_id"),
                    "task_id": row.get("task_id"),
                    "mechanism": row.get("mechanism"),
                    "repetition": row.get("repetition"),
                    **dict(item),
                }
            )
    return out


def _split_audit_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    controls: list[dict[str, Any]] = []
    stochastic: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    for row in rows:
        planner_id = str(row.get("planner_id"))
        payload = dict(row)
        if planner_id in CONTROL_PLANNER_IDS:
            controls.append(payload)
        else:
            stochastic.append(payload)
        if planner_id in PRIMARY_PLANNER_IDS or planner_id in PROJECTION_PLANNER_IDS:
            checkpoints.extend(_checkpoints_from_row(row))
    return controls, stochastic, checkpoints


def _landing_html(*, stages: Mapping[str, Mapping[str, Any]], revision: str) -> str:
    claims = "".join(f"<li>{item}</li>" for item in PROHIBITED_CLAIMS)
    stage_rows = "".join(
        (
            "<tr>"
            f"<td><code>{name}</code></td>"
            f"<td>{counts.get('n_rows')}</td>"
            f"<td>{counts.get('n_completed_files')}</td>"
            f"<td>{counts.get('n_attempt_files')}</td>"
            f"<td><a href='{name}/report/index.html'>report</a></td>"
            "</tr>"
        )
        for name, counts in stages.items()
    )
    optional = ", ".join(OPTIONAL_PLANNER_IDS)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V4.2C OMPL planner-geometry portfolio</title>
<style>
body {{ font-family: Georgia, "Times New Roman", serif; margin: 1.2rem; color: #222; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #bbb; padding: 0.35rem 0.45rem; }}
th {{ background: #f3f3f3; }}
.muted {{ color: #555; }}
@media print {{ a[href]::after {{ content: ""; }} }}
</style></head><body>
<p id="lede"><strong>{LEDE}</strong></p>
<h1>V4.2C OMPL planner-geometry portfolio</h1>
<p><strong>No-inference:</strong> {NO_INFERENCE_STATEMENT}</p>
<p class="muted">implementation <code>{revision}</code>
· package <code>{V4_2C_ALLOWED_PACKAGE}</code></p>
<p>
<a href="manifest.json">manifest.json</a> ·
<a href="capability_matrix.json">capability_matrix.json</a> ·
<a href="summary.json">summary.json</a> ·
<a href="calibration/selection.json">calibration/selection.json</a>
</p>
<p>Stage directories remain the source of truth. Compressed jsonl extracts under
<code>calibration/</code> and <code>audit/</code> are derived views.</p>
<table>
<thead><tr>
<th>stage</th><th>n_rows</th><th>completed files</th>
<th>attempt files</th><th>report</th>
</tr></thead>
<tbody>{stage_rows}</tbody>
</table>
<p>Optional planners remain visible: <code>{optional}</code>.</p>
<p id="interpretation-boundary">{INTERPRETATION_BOUNDARY}</p>
<p>Prohibited claims:</p>
<ul>{claims}</ul>
</body></html>
"""


def _file_record(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    payload = path.read_bytes()
    compression = "gzip" if rel.endswith(".gz") else "none"
    if rel.endswith(".html"):
        media = "text/html"
    elif rel.endswith(".json"):
        media = "application/json"
    elif rel.endswith(".jsonl.gz"):
        media = "application/gzip"
    else:
        media = "application/octet-stream"
    return {
        "path": rel,
        "sha256": _sha256_bytes(payload),
        "byte_count": len(payload),
        "row_count": None,
        "schema_version": None,
        "media_type": media,
        "compression": compression,
    }


def files_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """Stable digest of listed files, excluding the manifest."""
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda row: str(row["path"])):
        digest.update(str(record["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _inventory_rels(root: Path) -> list[str]:
    rels: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = _rel(root, path)
        if rel == MANIFEST_NAME or "/work/" in f"/{rel}/" or rel.startswith("work/"):
            continue
        if "/." in f"/{rel}":
            continue
        rels.append(rel)
    return rels


def package_ompl_planner_portfolio(
    root: Path,
    *,
    source_git_revision: str | None = None,
    allow_dirty: bool = False,
) -> dict[str, Any]:
    """Write compressed extracts, landing pages, and ``manifest.json``."""
    resolved = assert_v4_2c_output_allowed(root)
    if not resolved.is_dir():
        raise V4_2CArtifactError(f"package root does not exist: {resolved}")
    leftover: list[str] = []
    if source_git_revision is None:
        revision = git_rev_parse_head()
        leftover = [
            line
            for line in git_status_porcelain().splitlines()
            if not _is_v4_2c_package_porcelain(line)
        ]
        if leftover and not allow_dirty:
            raise DirtySourceError(
                "Refusing dirty-source V4.2C packaging; only untracked files "
                f"under {V4_2C_ALLOWED_PACKAGE} are allowed.\n"
                + "\n".join(leftover)
            )
    else:
        revision = str(source_git_revision)
    if SOURCE_GIT_REVISION_RE.fullmatch(revision) is None:
        raise V4_2CArtifactError("source_git_revision must be a 40-char hex SHA")

    stages: dict[str, dict[str, Any]] = {}
    for name in (STAGE_A, STAGE_B, STAGE_C):
        stage_dir = resolved / name
        if not stage_dir.is_dir():
            raise V4_2CArtifactError(f"missing {name} under {resolved}")
        write_ompl_planner_portfolio_report(stage_dir)
        stages[name] = _stage_counts(stage_dir)

    calibration_rows = _iter_json_objects(resolved / STAGE_B / "rows")
    _write_jsonl_gz(resolved / "calibration" / "rows.jsonl.gz", calibration_rows)
    selection_src = resolved / STAGE_B / "calibration_selection.json"
    if not selection_src.is_file():
        raise V4_2CArtifactError("missing stage_b/calibration_selection.json")
    selection = _read_json(selection_src)
    write_atomic_json(resolved / "calibration" / "selection.json", selection)

    audit_rows = _iter_json_objects(resolved / STAGE_C / "rows")
    audit_attempts = _iter_json_objects(resolved / STAGE_C / "attempts")
    controls, stochastic, checkpoints = _split_audit_rows(audit_rows)
    _write_jsonl_gz(resolved / "audit" / "deterministic_controls.jsonl.gz", controls)
    _write_jsonl_gz(resolved / "audit" / "stochastic_rows.jsonl.gz", stochastic)
    _write_jsonl_gz(
        resolved / "audit" / "convergence_checkpoints.jsonl.gz", checkpoints
    )
    _write_jsonl_gz(resolved / "audit" / "failures.jsonl.gz", audit_attempts)

    capability_src = resolved / "capability_matrix.json"
    if not capability_src.is_file():
        stage_cap = resolved / STAGE_C / "capability_matrix.json"
        if stage_cap.is_file():
            write_atomic_json(capability_src, _read_json(stage_cap))
        else:
            write_atomic_json(
                capability_src,
                {
                    "schema_version": "v4.2c.ompl_capability_matrix.v1",
                    "rows": [
                        {
                            "feature_id": planner_id,
                            "status": "optional_not_run",
                            "required": False,
                            "detail": "optional planner remains visible at closeout",
                        }
                        for planner_id in OPTIONAL_PLANNER_IDS
                    ],
                },
            )

    stage_c_summary = resolved / STAGE_C / "report" / "summary.json"
    if stage_c_summary.is_file():
        write_atomic_json(resolved / "summary.json", _read_json(stage_c_summary))
    else:
        raise V4_2CArtifactError("stage_c report summary.json was not written")

    (resolved / "index.html").write_text(
        _landing_html(stages=stages, revision=revision),
        encoding="utf-8",
    )
    (resolved / "README.md").write_text(
        "# V4.2C OMPL planner-geometry portfolio\n\n"
        f"{NO_INFERENCE_STATEMENT}\n\n"
        f"{LEDE}\n\n"
        "Stage directories are the source of truth. "
        "Compressed jsonl files are derived.\n",
        encoding="utf-8",
    )

    records = [_file_record(resolved, rel) for rel in _inventory_rels(resolved)]
    manifest = {
        "schema_version": PACKAGE_SCHEMA,
        "package": V4_2C_ALLOWED_PACKAGE,
        "manifest_inventory_rule": MANIFEST_INVENTORY_RULE,
        "source_git_revision": revision,
        "source_git_dirty": bool(leftover) if not allow_dirty else True,
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "lede": LEDE,
        "interpretation_boundary": INTERPRETATION_BOUNDARY,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
        "v4_2b_files_digest": FROZEN_V4_2B_FILES_DIGEST,
        "v4_2b_n_files": FROZEN_V4_2B_N_FILES,
        "v4_2b_n_geometry_rows": FROZEN_V4_2B_N_GEOMETRY_ROWS,
        "n_rows_stage_a": stages[STAGE_A]["n_rows"],
        "n_rows_stage_b": stages[STAGE_B]["n_rows"],
        "n_rows_stage_c": stages[STAGE_C]["n_rows"],
        "stages": stages,
        "files": records,
        "files_digest": files_digest(records),
    }
    (resolved / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "root": str(resolved),
        "source_git_revision": revision,
        "files_digest": manifest["files_digest"],
        "n_files": len(records),
        "n_rows_stage_a": manifest["n_rows_stage_a"],
        "n_rows_stage_b": manifest["n_rows_stage_b"],
        "n_rows_stage_c": manifest["n_rows_stage_c"],
    }


def _require_hex(value: object, *, field: str) -> str:
    text = str(value)
    if SHA256_RE.fullmatch(text) is None:
        raise V4_2CArtifactError(f"{field} must be a 64-char hex digest")
    return text


def verify_v4_2c_artifact(
    root: Path,
    *,
    require_frozen_matrix: bool = True,
    require_predecessor: bool = True,
) -> dict[str, Any]:
    """Verify manifest inventory, HTML links, and optional frozen counts."""
    resolved = Path(root).expanduser().resolve()
    try:
        assert_v4_2c_output_allowed(resolved)
    except ArtifactPathForbiddenError as exc:
        raise V4_2CArtifactError(str(exc)) from exc
    manifest_path = resolved / MANIFEST_NAME
    if not manifest_path.is_file():
        raise V4_2CArtifactError(f"missing {MANIFEST_NAME}")
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise V4_2CArtifactError("manifest.json must be a JSON object")
    if manifest.get("package") != V4_2C_ALLOWED_PACKAGE:
        raise V4_2CArtifactError(f"manifest package must be {V4_2C_ALLOWED_PACKAGE!r}")
    if manifest.get("schema_version") != PACKAGE_SCHEMA:
        raise V4_2CArtifactError(f"manifest schema_version must be {PACKAGE_SCHEMA!r}")
    if manifest.get("manifest_inventory_rule") != MANIFEST_INVENTORY_RULE:
        raise V4_2CArtifactError("manifest_inventory_rule must exclude the manifest")
    listed = manifest.get("files")
    if not isinstance(listed, list) or not listed:
        raise V4_2CArtifactError("manifest files[] is missing or empty")
    recorded = []
    for item in listed:
        if not isinstance(item, Mapping):
            raise V4_2CArtifactError("manifest files[] entries must be objects")
        rel = str(item["path"])
        if rel == MANIFEST_NAME:
            raise V4_2CArtifactError("manifest.json must be excluded from files[]")
        path = resolved / rel
        if not path.is_file():
            raise V4_2CArtifactError(f"missing inventoried file {rel}")
        live = _file_record(resolved, rel)
        if live["sha256"] != item.get("sha256"):
            raise V4_2CArtifactError(f"sha256 mismatch for {rel}")
        recorded.append(live)
    live_digest = files_digest(recorded)
    if live_digest != _require_hex(manifest.get("files_digest"), field="files_digest"):
        raise V4_2CArtifactError("files_digest mismatch")
    if require_frozen_matrix:
        for name, expected in FROZEN_STAGE_ROWS.items():
            key = f"n_rows_{name}"
            if int(manifest.get(key) or -1) != expected:
                raise V4_2CArtifactError(
                    f"{key} must be {expected}, got {manifest.get(key)!r}"
                )
    html_pages = list(resolved.rglob("index.html"))
    if not html_pages:
        raise V4_2CArtifactError("package has no index.html")
    missing_links: list[str] = []
    pdst_visible = False
    for page in html_pages:
        text = page.read_text(encoding="utf-8")
        if any(planner_id in text for planner_id in OPTIONAL_PLANNER_IDS):
            pdst_visible = True
        if "winner" in text.lower():
            raise V4_2CArtifactError(f"{_rel(resolved, page)} contains winner language")
        for target in href_targets(page):
            if not target.exists():
                missing_links.append(str(target))
    if missing_links:
        raise V4_2CArtifactError("broken HTML links: " + ", ".join(missing_links[:12]))
    if not pdst_visible:
        raise V4_2CArtifactError("optional PDST is not visible in retained HTML")
    predecessor = None
    if require_predecessor:
        predecessor = verify_v4_2b_artifact(canonical_v4_2b_retained_root())
        if predecessor["files_digest"] != FROZEN_V4_2B_FILES_DIGEST:
            raise V4_2CArtifactError("V4.2B files_digest drifted")
        if int(predecessor["n_files"]) != FROZEN_V4_2B_N_FILES:
            raise V4_2CArtifactError("V4.2B n_files drifted")
        if int(predecessor["n_geometry_rows"]) != FROZEN_V4_2B_N_GEOMETRY_ROWS:
            raise V4_2CArtifactError("V4.2B n_geometry_rows drifted")
    return {
        "package": V4_2C_ALLOWED_PACKAGE,
        "root": str(resolved),
        "files_digest": live_digest,
        "n_files": len(recorded),
        "n_rows_stage_a": manifest.get("n_rows_stage_a"),
        "n_rows_stage_b": manifest.get("n_rows_stage_b"),
        "n_rows_stage_c": manifest.get("n_rows_stage_c"),
        "source_git_revision": manifest.get("source_git_revision"),
        "v4_2b_files_digest": predecessor["files_digest"] if predecessor else None,
    }
