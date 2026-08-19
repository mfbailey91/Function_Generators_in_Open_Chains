"""V4.2B mounted-Q span-controlled geometry atlas driver.

Consumes the frozen V3.6D registry through ``realize_mounted_span_case``.
Does not call span synthesis and does not overwrite V4.2 packages.
"""

from __future__ import annotations

import gzip
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from inequality_mechanisms.audits.v4_2b_artifact import (
    MANIFEST_INVENTORY_RULE,
    files_digest,
    inventory_required_files,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    REPO_ROOT,
    ArtifactPathForbiddenError,
    allowed_v4_2b_output_root,
    assert_v4_2b_output_allowed,
    assert_v4_2b_output_root_empty,
    assert_v4_2b_source_clean,
    canonical_v4_0_retained_root,
    canonical_v4_1_retained_root,
    canonical_v4_2_retained_root,
    canonical_v4_2a_retained_root,
    canonical_v4_2b_retained_root,
    git_rev_parse_head,
    git_status_porcelain,
)
from inequality_mechanisms.experiments.span_cases import (
    generate_span_cases,
    realize_mounted_span_case,
)
from inequality_mechanisms.experiments.v4.geometry_atlas import (
    AtlasRow,
    assert_shared_pose,
    evaluate_atlas_sample,
    git_revision,
)
from inequality_mechanisms.experiments.v4.shared_q_atlas import SharedQSample
from inequality_mechanisms.experiments.v4.rank_fields import attribution_from_row
from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
    SpanCaseAtlas,
    arms_for_realized,
    bank_from_fourbar,
    load_locked_v3_6d_registry,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    DEFAULT_CONFIG_REL as V4_2_DEFAULT_CONFIG_REL,
    FROZEN_V3_6D_DIGEST,
    SPAN_175_STATUS,
    load_span_atlas_config,
)
from inequality_mechanisms.experiments.v4.span_common_physical_bank import (
    DEFAULT_BANK_REL,
    load_common_physical_bank,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_config import (
    DEFAULT_CONFIG_REL,
    V4_2B_PACKAGE,
    SpanControlledCorrectiveConfig,
    load_span_corrective_config,
)
from inequality_mechanisms.visualization.v4.span_controlled_corrective import (
    write_span_controlled_corrective_html,
)

N_SPAN_CASES = 17
GRID_SHAPE = (33, 33)
GEOMETRY_ARMS = 3
EXPECTED_GEOMETRY_ROWS = (
    N_SPAN_CASES * GRID_SHAPE[0] * GRID_SHAPE[1] * GEOMETRY_ARMS
)
_POSE_ATOL = 1e-12


class SpanCorrectiveError(ValueError):
    """Typed V4.2B corrective-atlas construction failure."""

    failure_code = "span_corrective_atlas_failed"


def _is_under(path: Path, parent: Path) -> bool:
    path_r = path.resolve()
    parent_r = parent.resolve()
    return path_r == parent_r or parent_r in path_r.parents


def _is_canonical_v4_2b_write(resolved: Path) -> bool:
    """Return True when ``resolved`` is the retained V4.2B package root."""
    return _is_under(resolved, canonical_v4_2b_retained_root())


def _begin_v4_2b_write(resolved: Path) -> tuple[str, bool]:
    """Create the output tree and return ``(source_sha, source_git_dirty)``.

    Canonical writes refuse a dirty source tree and a nonempty output
    root before any mkdir. Pytest ``tmp_path`` destinations keep the
    existing rmtree policy so a dirty developer tree still works.
    """
    if _is_canonical_v4_2b_write(resolved):
        sha = assert_v4_2b_source_clean()
        assert_v4_2b_output_root_empty(resolved)
        resolved.mkdir(parents=True, exist_ok=True)
        return sha, False
    porcelain = git_status_porcelain()
    sha = git_revision() or git_rev_parse_head()
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    return sha, bool(porcelain.strip())


def _resolve_output(output: Path) -> Path:
    """Allow the V4.2B root or tmp; refuse frozen historical packages."""
    resolved = Path(output).expanduser().resolve()
    allowed = allowed_v4_2b_output_root()
    if _is_under(resolved, allowed):
        return assert_v4_2b_output_allowed(resolved)
    return _refuse_historical_output(resolved)


def _refuse_historical_output(output: Path) -> Path:
    """Allow tmp or the V4.2B root; refuse frozen historical packages."""
    resolved = Path(output).expanduser().resolve()
    historical = (
        (canonical_v4_0_retained_root(), "frozen V4.0"),
        (canonical_v4_1_retained_root(), "frozen V4.1"),
        (canonical_v4_2_retained_root(), "frozen V4.2"),
        (canonical_v4_2a_retained_root(), "frozen V4.2A"),
    )
    for root, label in historical:
        if _is_under(resolved, root):
            raise ArtifactPathForbiddenError(
                f"Refusing to write into {label} retained evidence at {resolved}."
            )
    v3_root = (CANONICAL_REPO_ROOT / "results" / "v3_review").resolve()
    if _is_under(resolved, v3_root):
        raise ArtifactPathForbiddenError(
            f"Refusing to write into frozen V3 retained evidence at {resolved}."
        )
    return resolved


def _assert_identity_jg(row: AtlasRow) -> None:
    if row.snapshot is None:
        return
    jg = np.asarray(row.snapshot.j_u_to_q, dtype=np.float64)
    if not np.allclose(jg, np.eye(jg.shape[0]), atol=_POSE_ATOL):
        raise SpanCorrectiveError(
            f"identity J_g is not I at {row.q_sample_id}"
        )


def _comparative_sample(
    sample: SharedQSample,
    by_mech: Mapping[str, AtlasRow],
) -> dict[str, Any] | None:
    """Shared mounted Q/X identity for within-case export checks.

    Inverse round-trip on the four-bar can move snapshot ``q`` by ~1e-10.
    The declared shared pose is the bank sample and the identity-arm FK.
    Per-arm snapshots remain in the gzipped JSONL.
    """
    fourbar = by_mech["fourbar"]
    gearbox = by_mech["span_matched_gearbox"]
    identity = by_mech["identity_on_shared_q"]
    if (
        fourbar.snapshot is None
        or gearbox.snapshot is None
        or identity.snapshot is None
    ):
        return None
    q_shared = [float(value) for value in sample.q]
    x_shared = [float(value) for value in identity.snapshot.x]
    return {
        "case_id": fourbar.mechanism_pair_id,
        "q_sample_id": fourbar.q_sample_id,
        "grid_index": [int(fourbar.grid_index[0]), int(fourbar.grid_index[1])],
        "q_fourbar": list(q_shared),
        "q_gearbox": list(q_shared),
        "q_identity": list(q_shared),
        "x_fourbar": list(x_shared),
        "x_gearbox": list(x_shared),
        "x_identity": list(x_shared),
        "identity_j_g": [list(row) for row in identity.snapshot.j_u_to_q],
    }


def _evaluate_mounted_case(
    realized,
    config: SpanControlledCorrectiveConfig,
    *,
    revision: str | None,
) -> tuple[SpanCaseAtlas, list[dict[str, Any]]]:
    """Evaluate one mounted case on the shared-Q bank."""
    arms = arms_for_realized(
        realized, L1=config.planar2r.L1, L2=config.planar2r.L2
    )
    bank = bank_from_fourbar(
        realized.fourbar,
        shape=config.grid.shape,
        inset_fraction=config.grid.inset_fraction,
        case_id=realized.case.case_id,
    )
    digest = config.digest()
    rows: list[AtlasRow] = []
    comparative: list[dict[str, Any]] = []
    for sample in bank.samples:
        by_mech: dict[str, AtlasRow] = {}
        for mechanism_id, arm in arms.items():
            row = evaluate_atlas_sample(
                arm,
                sample,
                revision=revision,
                mechanism_pair_id=realized.case.case_id,
                config_digest=digest,
            )
            by_mech[mechanism_id] = row
            rows.append(row)
        assert_shared_pose(by_mech)
        _assert_identity_jg(by_mech["identity_on_shared_q"])
        sample_payload = _comparative_sample(sample, by_mech)
        if sample_payload is not None:
            comparative.append(sample_payload)
    return (
        SpanCaseAtlas(realized=realized, arms=arms, bank=bank, rows=rows),
        comparative,
    )


def _write_case_jsonl(output: Path, atlas: SpanCaseAtlas) -> Path:
    case_id = atlas.realized.case.case_id
    case_dir = output / "geometry_atlas" / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    path = case_dir / "geometry_samples.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in atlas.rows:
            handle.write(json.dumps(row.to_dict()) + "\n")
    return path


def _readme_text(manifest: Mapping[str, object]) -> str:
    return (
        "# V4.2B span-controlled corrective geometry atlas\n\n"
        "Mounted robot joint coordinates over the frozen V3.6D span family. "
        "Identity-on-shared-Q is a null control, not a ranked competitor. "
        f"{manifest['no_inference_statement']}\n\n"
        f"- cases: {manifest['n_cases']}\n"
        f"- grid: {manifest['grid']}\n"
        f"- rows: {manifest['n_rows']}\n"
        f"- typed failures: {manifest['n_typed_failures']}\n"
        f"- silent drops: {manifest['n_silent_drops']}\n"
        f"- V3.6D digest: `{manifest['v3_6d_digest']}`\n"
        f"- 175° status: `{manifest['span_175_status']}`\n"
        "- samples: `geometry_atlas/cases/<case_id>/geometry_samples.jsonl.gz`\n"
    )


def generate_span_controlled_corrective_atlas(
    *,
    config_path: Path | str | None = None,
    output: Path | str | None = None,
    prepare: bool = True,
    source_git_revision: str | None = None,
    source_git_dirty: bool | None = None,
) -> dict[str, Any]:
    """Evaluate mounted span cases and write the V4.2B geometry package.

    Parameters
    ----------
    config_path :
        Frozen V4.2B config JSON. Defaults to the committed corrective config.
    output :
        Destination directory. May be a pytest ``tmp_path``. Canonical
        V4.0/V4.1/V4.2/V4.2A and ``results/v3_review/`` paths are refused.
    prepare :
        When True, empty the destination before writing. Orchestrators that
        already prepared the package root pass False.
    source_git_revision, source_git_dirty :
        Optional provenance from a package orchestrator.

    Returns
    -------
    dict
        Package summary with comparative sample rows for within-case checks.
    """
    cfg_path = (
        Path(config_path)
        if config_path is not None
        else (CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    )
    config = load_span_corrective_config(cfg_path)
    target = Path(output) if output is not None else (REPO_ROOT / config.output_dir)
    resolved = _resolve_output(target)
    if prepare:
        source_git_revision, source_git_dirty = _begin_v4_2b_write(resolved)
    else:
        resolved.mkdir(parents=True, exist_ok=True)
        if source_git_revision is None:
            source_git_revision = git_revision() or git_rev_parse_head()
        if source_git_dirty is None:
            source_git_dirty = bool(git_status_porcelain().strip())
    revision = source_git_revision

    v42_config = load_span_atlas_config(CANONICAL_REPO_ROOT / V4_2_DEFAULT_CONFIG_REL)
    registry = load_locked_v3_6d_registry(v42_config)
    if registry.sha256 != config.v3_6d_digest_lock:
        raise SpanCorrectiveError(
            "V3.6D registry digest mismatch: "
            f"file={registry.sha256} lock={config.v3_6d_digest_lock}"
        )
    if registry.sha256 != FROZEN_V3_6D_DIGEST:
        raise SpanCorrectiveError(
            "V3.6D registry digest is not the frozen lock "
            f"{FROZEN_V3_6D_DIGEST}, got {registry.sha256}"
        )

    cases = generate_span_cases()
    if len(cases) != N_SPAN_CASES:
        raise SpanCorrectiveError(f"expected {N_SPAN_CASES} cases, got {len(cases)}")
    atlases: list[SpanCaseAtlas] = []
    comparative_rows: list[dict[str, Any]] = []
    n_arm_rows = 0
    n_typed = 0
    for case in cases:
        realized = realize_mounted_span_case(case, registry)
        atlas, sample_rows = _evaluate_mounted_case(
            realized, config, revision=revision
        )
        expected_case_rows = len(atlas.bank.samples) * GEOMETRY_ARMS
        if len(atlas.rows) != expected_case_rows:
            raise SpanCorrectiveError(
                f"{case.case_id} silent drop: "
                f"got {len(atlas.rows)} rows, expected {expected_case_rows}"
            )
        n_arm_rows += sum(1 for row in atlas.rows if row.failure_code is None)
        n_typed += sum(1 for row in atlas.rows if row.failure_code is not None)
        comparative_rows.extend(sample_rows)
        _write_case_jsonl(resolved, atlas)
        atlases.append(atlas)

    n_silent_drops = EXPECTED_GEOMETRY_ROWS - n_arm_rows - n_typed
    if n_silent_drops != 0:
        raise SpanCorrectiveError(
            f"silent drops must be 0, got {n_silent_drops} "
            f"(n_rows={n_arm_rows}, n_typed_failures={n_typed})"
        )

    rank_records = []
    case_payloads = []
    for atlas in atlases:
        for row in atlas.rows:
            record = attribution_from_row(row).to_dict()
            record["case_id"] = atlas.realized.case.case_id
            rank_records.append(record)
        case_payloads.append(
            {
                **atlas.realized.case.to_dict(),
                "j1_status": atlas.realized.j1.status,
                "j2_status": atlas.realized.j2.status,
                "n_samples": len(atlas.bank.samples),
                "n_rows": len(atlas.rows),
                "n_failed": sum(
                    1 for row in atlas.rows if row.failure_code is not None
                ),
                "q_box": {
                    "lower": list(atlas.bank.q_lower),
                    "upper": list(atlas.bank.q_upper),
                    "inset": list(atlas.bank.inset),
                    "inner_lower": list(atlas.bank.inner_lower),
                    "inner_upper": list(atlas.bank.inner_upper),
                },
                "span_matched_ratios": list(
                    atlas.arms["span_matched_gearbox"].provenance.get("ratios", [])
                ),
                "output_coordinate_kind": atlas.realized.fourbar.selector.get(
                    "output_coordinate_kind"
                ),
                "native_output_offset_rad": atlas.realized.fourbar.selector.get(
                    "native_output_offset_rad"
                ),
            }
        )
    (resolved / "rank_fields.json").write_text(
        json.dumps(rank_records, indent=2), encoding="utf-8"
    )
    (resolved / "cases.json").write_text(
        json.dumps(case_payloads, indent=2), encoding="utf-8"
    )
    resolved_config = {
        "config": config.model_dump(),
        "config_digest": config.digest(),
        "v3_6d_digest": registry.sha256,
        "v3_6d_registry_digest": registry.sha256,
        "evaluated_grid": list(GRID_SHAPE),
        "n_cases": len(atlases),
        "n_samples": sum(len(atlas.bank.samples) for atlas in atlases),
        "n_rows": n_arm_rows,
        "n_typed_failures": n_typed,
        "n_silent_drops": n_silent_drops,
        "case_ids": [atlas.realized.case.case_id for atlas in atlases],
        "source_git_revision": source_git_revision,
        "source_git_dirty": source_git_dirty,
        "common_task_bank_digest": load_common_physical_bank(
            CANONICAL_REPO_ROOT / DEFAULT_BANK_REL
        )["sha256"],
    }
    (resolved / "resolved_config.json").write_text(
        json.dumps(resolved_config, indent=2), encoding="utf-8"
    )
    manifest = {
        "schema_version": config.schema_version,
        "package": V4_2B_PACKAGE,
        "git_revision": revision,
        "source_git_revision": source_git_revision,
        "source_git_dirty": source_git_dirty,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "no_inference_statement": config.no_inference_statement,
        "config_digest": config.digest(),
        "v3_6d_digest": registry.sha256,
        "v3_6d_registry_digest": registry.sha256,
        "span_175_status": SPAN_175_STATUS,
        "n_cases": len(atlases),
        "n_samples": resolved_config["n_samples"],
        "n_rows": n_arm_rows,
        "n_typed_failures": n_typed,
        "n_silent_drops": n_silent_drops,
        "grid": list(GRID_SHAPE),
        "mechanisms": [
            "fourbar",
            "span_matched_gearbox",
            "identity_on_shared_q",
        ],
        "case_ids": [case.case_id for case in cases],
        "manifest_inventory_rule": MANIFEST_INVENTORY_RULE,
        "common_task_bank_digest": resolved_config["common_task_bank_digest"],
    }
    (resolved / "README.md").write_text(_readme_text(manifest), encoding="utf-8")
    write_span_controlled_corrective_html(
        resolved,
        config=config,
        registry=registry,
        atlases=atlases,
        manifest=manifest,
    )
    files = inventory_required_files(
        resolved, [atlas.realized.case.case_id for atlas in atlases]
    )
    manifest["files"] = files
    manifest["files_digest"] = files_digest(files)
    (resolved / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return {
        "output": str(resolved),
        "n_rows": n_arm_rows,
        "n_typed_failures": n_typed,
        "n_silent_drops": n_silent_drops,
        "rows": comparative_rows,
        "n_cases": len(atlases),
        "grid": list(GRID_SHAPE),
    }


def _patch_root_manifest_for_planning(package: Path) -> None:
    """Re-inventory the root package after ``planning_audit/`` is written."""
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    case_ids = [str(item) for item in manifest["case_ids"]]
    files = inventory_required_files(package, case_ids)
    manifest["files"] = files
    manifest["files_digest"] = files_digest(files)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def generate_span_controlled_corrective_package(
    *,
    config_path: Path | str | None = None,
    audit_config_path: Path | str | None = None,
    output: Path | str | None = None,
    include_geometry: bool = True,
    include_planning: bool = True,
    case_ids: Sequence[str] | None = None,
    task_ids: Sequence[str] | None = None,
    lattice_shape: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Write geometry and/or planning audit under one V4.2B package root."""
    from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit import (
        generate_span_controlled_corrective_audit,
    )
    from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit_config import (
        DEFAULT_CONFIG_REL as AUDIT_CONFIG_REL,
    )

    if not include_geometry and not include_planning:
        raise SpanCorrectiveError("package generator requires geometry or planning")
    cfg_path = (
        Path(config_path)
        if config_path is not None
        else (CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    )
    config = load_span_corrective_config(cfg_path)
    target = Path(output) if output is not None else (REPO_ROOT / config.output_dir)
    resolved = _resolve_output(target)
    source_git_revision, source_git_dirty = _begin_v4_2b_write(resolved)
    atlas: dict[str, Any] | None = None
    if include_geometry:
        atlas = generate_span_controlled_corrective_atlas(
            config_path=cfg_path,
            output=resolved,
            prepare=False,
            source_git_revision=source_git_revision,
            source_git_dirty=source_git_dirty,
        )
    audit: dict[str, Any] | None = None
    if include_planning:
        audit_cfg = (
            Path(audit_config_path)
            if audit_config_path is not None
            else (CANONICAL_REPO_ROOT / AUDIT_CONFIG_REL)
        )
        audit = generate_span_controlled_corrective_audit(
            config_path=audit_cfg,
            output=resolved / "planning_audit",
            case_ids=case_ids,
            task_ids=task_ids,
            lattice_shape=lattice_shape,
            prepare_subdir=True,
            source_git_revision=source_git_revision,
            source_git_dirty=source_git_dirty,
        )
        if include_geometry:
            _patch_root_manifest_for_planning(resolved)
    return {
        "output": str(resolved),
        "geometry": atlas,
        "planning": audit,
    }
