"""V4.2D package writer, inventory, and verifier."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.analysis.v4.optimality_metrics import (
    STAGE_C_ROW_COUNT,
    extract_stage_c_views,
    join_stage_c_to_reference,
    load_stage_c_records,
)
from inequality_mechanisms.analysis.v4.optimality_pairing import (
    PAIRING_LABEL,
    decompose_final_gaps,
    pair_mechanism_contrasts,
)
from inequality_mechanisms.analysis.v4.optimality_reference import (
    DEFAULT_CONFIG_REL,
    FROZEN_V4_2C_FILES_DIGEST,
    PRIMARY_REFERENCE_COUNT,
    build_center_ik_references,
    canonical_dumps,
    join_representation_penalty,
    load_report_config,
    load_v4_2b_historical_references,
    verify_source_package_digests,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_2D_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    DirtySourceError,
    assert_v4_2d_output_allowed,
    canonical_v4_2b_retained_root,
    canonical_v4_2c_retained_root,
    git_rev_parse_head,
    git_status_porcelain,
)
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import write_atomic_json
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    FROZEN_V4_2B_FILES_DIGEST,
)
from inequality_mechanisms.visualization.v4.ompl_planner_portfolio import href_targets
from inequality_mechanisms.visualization.v4.optimality_reference_report import (
    INTERPRETATION_BOUNDARY,
    LEDE,
    PROHIBITED_CLAIMS,
    V4_2DReportError,
    write_figures,
    write_html_report,
)

PACKAGE_SCHEMA = "v4.2d.optimality_reference_report.package.v1"
MANIFEST_NAME = "manifest.json"
MANIFEST_INVENTORY_RULE = "exclude_self"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DATA_FILES = (
    "data/v4_2c_center_reference_rows.jsonl.gz",
    "data/v4_2c_center_candidate_costs.jsonl.gz",
    "data/v4_2b_historical_reference_rows.jsonl.gz",
    "data/checkpoint_optimality_rows.jsonl.gz",
    "data/final_optimality_rows.jsonl.gz",
    "data/final_gap_decomposition.jsonl.gz",
    "data/paired_mechanism_contrasts.jsonl.gz",
    "data/task_class_rows.jsonl.gz",
)
FIGURE_RELS = (
    "figures/01_reference_cost_by_mechanism.png",
    "figures/02_mechanism_optimum_delta.png",
    "figures/03_exact_solution_rate_vs_checkpoint.png",
    "figures/04_within_5pct_vs_checkpoint.png",
    "figures/05_relative_gap_vs_checkpoint.png",
    "figures/06_first_vs_final_gap.png",
    "figures/07_final_gap_by_family.png",
    "figures/08_paired_discoverability_contrast.png",
    "figures/09_benefit_vs_discoverability.png",
    "figures/10_final_gap_decomposition.png",
    "figures/11_reference_goal_match.png",
    "figures/12_goal_representation_sensitivity.png",
)


class V4_2DArtifactError(ValueError):
    """Raised when a V4.2D retained package fails integrity or packaging."""

    failure_code = "v4_2d_artifact_integrity_failed"


def _porcelain_path(line: str) -> str:
    payload = line[3:] if len(line) >= 3 else line
    if " -> " in payload:
        payload = payload.split(" -> ", 1)[1]
    return payload.strip().strip('"')


def _is_v4_2d_package_porcelain(line: str) -> bool:
    from inequality_mechanisms.audits.v4_artifact_guard import V4_2D_ALLOWED_OUTPUT_REL

    rel = _porcelain_path(line)
    allowed = V4_2D_ALLOWED_OUTPUT_REL.as_posix()
    return rel == allowed or rel.startswith(f"{allowed}/")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _write_jsonl_gz(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    resolved = assert_v4_2d_output_allowed(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(resolved, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(canonical_dumps(row) + "\n")


def _read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _file_record(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    payload = path.read_bytes()
    compression = "gzip" if rel.endswith(".gz") else "none"
    if rel.endswith(".html"):
        media = "text/html"
    elif rel.endswith(".json"):
        media = "application/json"
    elif rel.endswith(".png"):
        media = "image/png"
    elif rel.endswith(".md"):
        media = "text/markdown"
    elif rel.endswith(".jsonl.gz"):
        media = "application/gzip"
    else:
        media = "application/octet-stream"
    return {
        "path": rel,
        "sha256": _sha256_bytes(payload),
        "byte_count": len(payload),
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
        if rel == MANIFEST_NAME:
            continue
        if "/." in f"/{rel}":
            continue
        rels.append(rel)
    return rels


def generate_optimality_reference_report(
    output_dir: Path,
    *,
    config_path: Path | None = None,
    stage_c_records: Sequence[Mapping[str, Any]] | None = None,
    verify_sources: bool = True,
) -> dict[str, Any]:
    """Reconstruct references, join Stage C, and write the V4.2D report tree."""
    resolved = assert_v4_2d_output_allowed(output_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    config = load_report_config(config_path)
    source_contract = {
        "v4_2b_files_digest": str(config["v4_2b_files_digest"]),
        "v4_2c_files_digest": str(config["v4_2c_files_digest"]),
        "v4_2c_source_revision": str(config.get("v4_2c_source_revision") or ""),
        "v4_2b_root": str(canonical_v4_2b_retained_root()),
        "v4_2c_root": str(canonical_v4_2c_retained_root()),
        "pairing_label": PAIRING_LABEL,
    }
    if verify_sources:
        live = verify_source_package_digests(config)
        source_contract.update(live)
    records = (
        list(stage_c_records) if stage_c_records is not None else load_stage_c_records()
    )
    center = build_center_ik_references(
        config=config,
        stage_c_rows=None if stage_c_records is not None else records,
    )
    historical = load_v4_2b_historical_references(config=config)
    references = join_representation_penalty(center["reference_rows"], historical)
    views = extract_stage_c_views(records)
    joined = join_stage_c_to_reference(
        views,
        references,
        tau=float(config["tau"]),
        tau_zero=float(config["tau_zero"]),
        eta=tuple(float(item) for item in config["eta"]),
        checkpoints_s=tuple(float(item) for item in config["checkpoints_s"]),
    )
    paired = pair_mechanism_contrasts(
        joined["final_rows"], references, tau=float(config["tau"])
    )
    decomp = decompose_final_gaps(
        joined["final_rows"],
        center["candidate_rows"],
        tau=float(config["tau"]),
    )
    data_dir = resolved / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl_gz(data_dir / "v4_2c_center_reference_rows.jsonl.gz", references)
    _write_jsonl_gz(
        data_dir / "v4_2c_center_candidate_costs.jsonl.gz", center["candidate_rows"]
    )
    _write_jsonl_gz(data_dir / "v4_2b_historical_reference_rows.jsonl.gz", historical)
    _write_jsonl_gz(
        data_dir / "checkpoint_optimality_rows.jsonl.gz", joined["checkpoint_rows"]
    )
    _write_jsonl_gz(data_dir / "final_optimality_rows.jsonl.gz", joined["final_rows"])
    _write_jsonl_gz(data_dir / "final_gap_decomposition.jsonl.gz", decomp)
    _write_jsonl_gz(data_dir / "paired_mechanism_contrasts.jsonl.gz", paired)
    _write_jsonl_gz(data_dir / "task_class_rows.jsonl.gz", joined["task_class_rows"])
    digest_b = str(source_contract["v4_2b_files_digest"])
    digest_c = str(source_contract["v4_2c_files_digest"])
    figures = write_figures(
        output_dir=resolved,
        reference_rows=references,
        checkpoint_rows=joined["checkpoint_rows"],
        final_rows=joined["final_rows"],
        paired_rows=paired,
        decomposition_rows=decomp,
        digest_b=digest_b,
        digest_c=digest_c,
    )
    n_already = sum(1 for row in views if row.get("already_satisfied"))
    summary = {
        "schema_version": PACKAGE_SCHEMA,
        "lede": LEDE,
        "no_inference_statement": config["no_inference_statement"],
        "interpretation_boundary": INTERPRETATION_BOUNDARY,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
        "source_contract": source_contract,
        "case_ids": list(config["case_ids"]),
        "counts": {
            "n_reference_rows": len(references),
            "n_candidate_rows": len(center["candidate_rows"]),
            "n_stage_c_rows": len(views),
            "n_orphans": joined["n_orphans"],
            "n_already_satisfied": n_already,
            "n_paired": len(paired),
            "n_decompositions": len(decomp),
        },
        "figures": figures,
        "pairing_label": PAIRING_LABEL,
    }
    prose = (
        f"{summary['lede']} {summary['no_inference_statement']} "
        f"{summary['interpretation_boundary']}"
    )
    from inequality_mechanisms.visualization.v4.ompl_planner_portfolio import (
        _forbidden_token_in,
    )

    token = _forbidden_token_in(prose)
    if token is not None:
        raise V4_2DReportError(f"summary prose contains forbidden token {token!r}")
    write_atomic_json(resolved / "resolved_config.json", config)
    write_atomic_json(resolved / "source_contract.json", source_contract)
    write_html_report(resolved, summary)
    return {
        "output_dir": str(resolved),
        "n_reference_rows": len(references),
        "n_stage_c_rows": len(views),
        "n_figures": len(figures),
        "source_contract": source_contract,
    }


def package_v4_2d_report(
    root: Path,
    *,
    source_git_revision: str | None = None,
    allow_dirty: bool = False,
) -> dict[str, Any]:
    """Write README and ``manifest.json`` for an existing V4.2D tree."""
    resolved = assert_v4_2d_output_allowed(root)
    if not resolved.is_dir():
        raise V4_2DArtifactError(f"package root does not exist: {resolved}")
    leftover: list[str] = []
    if source_git_revision is None:
        revision = git_rev_parse_head()
        leftover = [
            line
            for line in git_status_porcelain().splitlines()
            if not _is_v4_2d_package_porcelain(line)
        ]
        if leftover and not allow_dirty:
            raise DirtySourceError(
                "Refusing dirty-source V4.2D packaging; only untracked files "
                f"under {V4_2D_ALLOWED_PACKAGE} are allowed.\n" + "\n".join(leftover)
            )
    else:
        revision = source_git_revision
    readme = resolved / "README.md"
    readme.write_text(
        "# V4.2D optimality-reference report\n\n"
        "Derived from frozen V4.2B and V4.2C packages. J*_C is the exact "
        "V4.2C center-IK direct optimum. J*_B is a representation-sensitivity "
        "control only. Pairing is index-matched, not CRN. Descriptive only; "
        "not a global ranking and not a mechanism ranking.\n",
        encoding="utf-8",
    )
    rels = _inventory_rels(resolved)
    records = [_file_record(resolved, rel) for rel in rels]
    digest = files_digest(records)
    summary_path = resolved / "summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {}
    counts = summary.get("counts") or {}
    manifest = {
        "schema_version": PACKAGE_SCHEMA,
        "package": V4_2D_ALLOWED_PACKAGE,
        "manifest_inventory_rule": MANIFEST_INVENTORY_RULE,
        "source_git_revision": revision,
        "source_git_dirty": bool(leftover),
        "files_digest": digest,
        "n_files": len(records),
        "n_reference_rows": counts.get("n_reference_rows"),
        "n_stage_c_rows": counts.get("n_stage_c_rows"),
        "n_orphans": counts.get("n_orphans"),
        "v4_2b_files_digest": FROZEN_V4_2B_FILES_DIGEST,
        "v4_2c_files_digest": FROZEN_V4_2C_FILES_DIGEST,
        "pairing_label": PAIRING_LABEL,
        "no_inference_statement": summary.get("no_inference_statement"),
        "files": records,
    }
    write_atomic_json(resolved / MANIFEST_NAME, manifest)
    return {
        "package": V4_2D_ALLOWED_PACKAGE,
        "root": str(resolved),
        "files_digest": digest,
        "n_files": len(records),
        "n_reference_rows": counts.get("n_reference_rows"),
        "n_stage_c_rows": counts.get("n_stage_c_rows"),
    }


def verify_v4_2d_artifact(
    root: Path,
    *,
    require_frozen_counts: bool = True,
) -> dict[str, Any]:
    """Verify inventory, source digests, joins, figures, and decompositions."""
    resolved = Path(root).expanduser().resolve()
    try:
        assert_v4_2d_output_allowed(resolved)
    except ArtifactPathForbiddenError as exc:
        raise V4_2DArtifactError(str(exc)) from exc
    manifest_path = resolved / MANIFEST_NAME
    if not manifest_path.is_file():
        raise V4_2DArtifactError(f"missing {MANIFEST_NAME}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("package") != V4_2D_ALLOWED_PACKAGE:
        raise V4_2DArtifactError(f"manifest package must be {V4_2D_ALLOWED_PACKAGE!r}")
    listed = manifest.get("files")
    if not isinstance(listed, list) or not listed:
        raise V4_2DArtifactError("manifest files[] is missing or empty")
    recorded = []
    for item in listed:
        if not isinstance(item, Mapping):
            raise V4_2DArtifactError("manifest files[] entries must be objects")
        rel = str(item["path"])
        if rel == MANIFEST_NAME:
            raise V4_2DArtifactError("manifest.json must be excluded from files[]")
        path = resolved / rel
        if not path.is_file():
            raise V4_2DArtifactError(f"missing inventoried file {rel}")
        live = _file_record(resolved, rel)
        if live["sha256"] != item.get("sha256"):
            raise V4_2DArtifactError(f"sha256 mismatch for {rel}")
        recorded.append(live)
    live_digest = files_digest(recorded)
    if live_digest != manifest.get("files_digest"):
        raise V4_2DArtifactError("files_digest mismatch")
    for rel in DATA_FILES + FIGURE_RELS:
        if not (resolved / rel).is_file():
            raise V4_2DArtifactError(f"missing required file {rel}")
    refs = _read_jsonl_gz(resolved / "data" / "v4_2c_center_reference_rows.jsonl.gz")
    finals = _read_jsonl_gz(resolved / "data" / "final_optimality_rows.jsonl.gz")
    decomp = _read_jsonl_gz(resolved / "data" / "final_gap_decomposition.jsonl.gz")
    if require_frozen_counts:
        if len(refs) != PRIMARY_REFERENCE_COUNT:
            raise V4_2DArtifactError(
                f"expected {PRIMARY_REFERENCE_COUNT} references, got {len(refs)}"
            )
        if len(finals) != STAGE_C_ROW_COUNT:
            raise V4_2DArtifactError(
                f"expected {STAGE_C_ROW_COUNT} Stage C rows, got {len(finals)}"
            )
    if any(row.get("n_orphans") for row in [manifest]):
        if int(manifest.get("n_orphans") or 0) != 0:
            raise V4_2DArtifactError("orphan Stage C rows are present")
    tau = 1e-8
    config_path = resolved / "resolved_config.json"
    if config_path.is_file():
        tau = float(json.loads(config_path.read_text(encoding="utf-8")).get("tau", tau))
    for row in decomp:
        if row.get("decomposition_status") != "ok":
            continue
        total = float(row["total_gap"])
        parts = float(row["goal_selection_regret"]) + float(row["path_inefficiency"])
        if abs(parts - total) > tau:
            raise V4_2DArtifactError("decomposition identity failed in retained rows")
    html_pages = list(resolved.rglob("index.html"))
    if not html_pages:
        raise V4_2DArtifactError("package has no index.html")
    missing_links: list[str] = []
    for page in html_pages:
        text = page.read_text(encoding="utf-8")
        if "winner" in text.lower():
            raise V4_2DArtifactError(f"{_rel(resolved, page)} contains winner language")
        for target in href_targets(page):
            if not target.exists():
                missing_links.append(str(target))
    if missing_links:
        raise V4_2DArtifactError("broken HTML links: " + ", ".join(missing_links[:12]))
    b_digest = json.loads(
        (canonical_v4_2b_retained_root() / "manifest.json").read_text(encoding="utf-8")
    ).get("files_digest")
    c_digest = json.loads(
        (canonical_v4_2c_retained_root() / "manifest.json").read_text(encoding="utf-8")
    ).get("files_digest")
    if b_digest != FROZEN_V4_2B_FILES_DIGEST:
        raise V4_2DArtifactError("V4.2B files_digest drifted")
    if c_digest != FROZEN_V4_2C_FILES_DIGEST:
        raise V4_2DArtifactError("V4.2C files_digest drifted")
    if not SHA256_RE.fullmatch(str(manifest.get("files_digest"))):
        raise V4_2DArtifactError("files_digest is not a 64-char hex digest")
    return {
        "package": V4_2D_ALLOWED_PACKAGE,
        "root": str(resolved),
        "files_digest": live_digest,
        "n_files": len(recorded),
        "n_reference_rows": len(refs),
        "n_stage_c_rows": len(finals),
        "v4_2b_files_digest": b_digest,
        "v4_2c_files_digest": c_digest,
    }


__all__ = [
    "PACKAGE_SCHEMA",
    "V4_2DArtifactError",
    "DEFAULT_CONFIG_REL",
    "generate_optimality_reference_report",
    "package_v4_2d_report",
    "verify_v4_2d_artifact",
]
