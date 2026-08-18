"""Multi-case V4.2 span-controlled geometry atlas driver.

Consumes the frozen V3.6D registry. Does not call span synthesis.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import numpy as np

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    REPO_ROOT,
    assert_v4_2_output_allowed,
    prepare_v4_2_output_dir,
)
from inequality_mechanisms.experiments.span_cases import (
    RealizedSpanCase,
    SpanCase,
    generate_span_cases,
    realize_span_case,
)
from inequality_mechanisms.experiments.v4.controls import (
    AtlasArm,
    AtlasControlError,
    identity_on_shared_q,
    span_matched_ratios,
)
from inequality_mechanisms.experiments.v4.geometry_atlas import (
    AtlasRow,
    assert_shared_pose,
    evaluate_atlas_sample,
    git_revision,
)
from inequality_mechanisms.experiments.v4.rank_fields import attribution_from_row
from inequality_mechanisms.experiments.v4.shared_q_atlas import (
    SharedQSample,
    SharedQSampleBank,
    build_shared_q_bank,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    DEFAULT_CONFIG_REL,
    FROZEN_V3_6D_DIGEST,
    SPAN_175_STATUS,
    SpanControlledAtlasConfig,
    load_span_atlas_config,
)
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms.span_registry import SpanRegistry, load_span_registry
from inequality_mechanisms.visualization.v4.span_controlled_atlas import (
    write_span_controlled_atlas_html,
)

REQUIRED_FILES = (
    "manifest.json",
    "resolved_config.json",
    "cases.json",
    "geometry_samples.jsonl",
    "rank_fields.json",
    "index.html",
    "README.md",
)


class SpanAtlasError(ValueError):
    """Typed V4.2 atlas construction failure."""

    failure_code = "span_atlas_failed"


@dataclass(frozen=True, slots=True)
class SpanCaseAtlas:
    """One generated span case evaluated on the three atlas arms."""

    realized: RealizedSpanCase
    arms: dict[str, AtlasArm]
    bank: SharedQSampleBank
    rows: list[AtlasRow]


def load_locked_v3_6d_registry(
    config: SpanControlledAtlasConfig,
    *,
    repo_root: Path | None = None,
) -> SpanRegistry:
    """Load the committed V3.6D registry and verify the frozen digest.

    Does not call ``build_span_registry`` or span synthesis.
    """
    root = CANONICAL_REPO_ROOT if repo_root is None else Path(repo_root)
    path = root / config.v3_6d_registry
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SpanAtlasError(f"missing frozen V3.6D registry at {path}") from exc
    except json.JSONDecodeError as exc:
        raise SpanAtlasError(f"invalid V3.6D registry JSON at {path}: {exc}") from exc
    registry = load_span_registry(payload)
    if registry.sha256 != config.v3_6d_digest_lock:
        raise SpanAtlasError(
            "V3.6D registry digest mismatch: "
            f"file={registry.sha256} lock={config.v3_6d_digest_lock}"
        )
    if registry.sha256 != FROZEN_V3_6D_DIGEST:
        raise SpanAtlasError(
            "V3.6D registry digest is not the frozen V4.2 lock "
            f"{FROZEN_V3_6D_DIGEST}, got {registry.sha256}"
        )
    status_175 = registry.record_for(175.0).status
    if status_175 != SPAN_175_STATUS or status_175 != config.span_175_status:
        raise SpanAtlasError(
            "175° status must remain "
            f"{SPAN_175_STATUS!r}, got registry={status_175!r} "
            f"config={config.span_175_status!r}"
        )
    return registry


def prefix_bank(bank: SharedQSampleBank, case_id: str) -> SharedQSampleBank:
    """Attach a stable per-case sample id while preserving grid coordinates."""
    samples = tuple(
        SharedQSample(
            q_sample_id=f"{case_id}__{sample.q_sample_id}",
            grid_index=sample.grid_index,
            q=sample.q,
        )
        for sample in bank.samples
    )
    return SharedQSampleBank(
        samples=samples,
        shape=bank.shape,
        q_lower=bank.q_lower,
        q_upper=bank.q_upper,
        inset=bank.inset,
        inner_lower=bank.inner_lower,
        inner_upper=bank.inner_upper,
    )


def bank_from_fourbar(
    fourbar_branch,
    *,
    shape: tuple[int, int],
    inset_fraction: float,
    case_id: str,
) -> SharedQSampleBank:
    """Build the per-case shared-Q bank from the four-bar certificate box."""
    cert = fourbar_branch.certificate
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=shape,
        inset_fraction=inset_fraction,
    )
    return prefix_bank(bank, case_id)


def arms_for_realized(
    realized: RealizedSpanCase,
    *,
    L1: float,
    L2: float,
) -> dict[str, AtlasArm]:
    """Attach four-bar, span-matched gearbox, and identity-on-shared-Q arms."""
    fk = Planar2R(L1=L1, L2=L2)
    fourbar = realized.fourbar
    gearbox = realized.gearbox
    identity = identity_on_shared_q(fourbar)
    q_lo = np.asarray(fourbar.certificate.output_lower, dtype=np.float64)
    q_hi = np.asarray(fourbar.certificate.output_upper, dtype=np.float64)
    u_lo = np.asarray(fourbar.certificate.input_lower, dtype=np.float64)
    u_hi = np.asarray(fourbar.certificate.input_upper, dtype=np.float64)
    gb_q_lo = np.asarray(gearbox.certificate.output_lower, dtype=np.float64)
    gb_q_hi = np.asarray(gearbox.certificate.output_upper, dtype=np.float64)
    gb_u_lo = np.asarray(gearbox.certificate.input_lower, dtype=np.float64)
    gb_u_hi = np.asarray(gearbox.certificate.input_upper, dtype=np.float64)
    if not (
        np.allclose(gb_q_lo, q_lo, atol=1e-12, rtol=0.0)
        and np.allclose(gb_q_hi, q_hi, atol=1e-12, rtol=0.0)
        and np.allclose(gb_u_lo, u_lo, atol=1e-12, rtol=0.0)
        and np.allclose(gb_u_hi, u_hi, atol=1e-12, rtol=0.0)
    ):
        raise AtlasControlError(
            "span_matched_gearbox U/Q endpoints do not match the four-bar: "
            f"fourbar_u=[{u_lo.tolist()}, {u_hi.tolist()}], "
            f"gearbox_u=[{gb_u_lo.tolist()}, {gb_u_hi.tolist()}], "
            f"fourbar_q=[{q_lo.tolist()}, {q_hi.tolist()}], "
            f"gearbox_q=[{gb_q_lo.tolist()}, {gb_q_hi.tolist()}]"
        )
    ident_lo = np.asarray(identity.certificate.output_lower, dtype=np.float64)
    ident_hi = np.asarray(identity.certificate.output_upper, dtype=np.float64)
    if not (
        np.allclose(ident_lo, q_lo, atol=1e-12, rtol=0.0)
        and np.allclose(ident_hi, q_hi, atol=1e-12, rtol=0.0)
    ):
        raise AtlasControlError(
            "identity_on_shared_q output box does not cover the four-bar Q box"
        )
    ratios = span_matched_ratios(fourbar)
    return {
        "fourbar": AtlasArm(
            mechanism_id="fourbar",
            branch=fourbar,
            robot=planar_2r_operating_branch_robot(fourbar, planar_fk=fk),
            provenance={
                "role": "v3_6d_fourbar",
                "case_id": realized.case.case_id,
                "j1_status": realized.j1.status,
                "j2_status": realized.j2.status,
            },
        ),
        "span_matched_gearbox": AtlasArm(
            mechanism_id="span_matched_gearbox",
            branch=gearbox,
            robot=planar_2r_operating_branch_robot(gearbox, planar_fk=fk),
            provenance={
                "role": "span_matched_affine_gearbox",
                "matching_rule": "span",
                "ratios": list(ratios),
                "case_id": realized.case.case_id,
            },
        ),
        "identity_on_shared_q": AtlasArm(
            mechanism_id="identity_on_shared_q",
            branch=identity,
            robot=planar_2r_operating_branch_robot(identity, planar_fk=fk),
            provenance={
                "role": "identity_null_control",
                "note": "J_g = I on the four-bar Q box; not a ranked competitor",
                "case_id": realized.case.case_id,
            },
        ),
    }


def evaluate_span_case(
    realized: RealizedSpanCase,
    config: SpanControlledAtlasConfig,
    *,
    shape: tuple[int, int],
    revision: str | None,
) -> SpanCaseAtlas:
    """Evaluate one generated case on the shared-Q bank."""
    arms = arms_for_realized(
        realized, L1=config.planar2r.L1, L2=config.planar2r.L2
    )
    bank = bank_from_fourbar(
        realized.fourbar,
        shape=shape,
        inset_fraction=config.grid.inset_fraction,
        case_id=realized.case.case_id,
    )
    digest = config.digest()
    rows: list[AtlasRow] = []
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
    return SpanCaseAtlas(realized=realized, arms=arms, bank=bank, rows=rows)


def collect_span_atlas(
    config: SpanControlledAtlasConfig,
    *,
    registry: SpanRegistry | None = None,
    grid_shape: tuple[int, int] | None = None,
    revision: str | None = None,
) -> tuple[SpanRegistry, tuple[SpanCase, ...], list[SpanCaseAtlas]]:
    """Realize the generated 17-case union and evaluate each shared-Q bank."""
    used_registry = (
        load_locked_v3_6d_registry(config) if registry is None else registry
    )
    cases = generate_span_cases()
    if len(cases) != 17:
        raise SpanAtlasError(f"expected 17 unique cases, got {len(cases)}")
    used_revision = git_revision() if revision is None else revision
    shape = config.grid.shape if grid_shape is None else grid_shape
    atlases: list[SpanCaseAtlas] = []
    for case in cases:
        realized = realize_span_case(case, used_registry)
        atlases.append(
            evaluate_span_case(
                realized, config, shape=shape, revision=used_revision
            )
        )
    return used_registry, cases, atlases


def _readme_text(manifest: Mapping[str, object]) -> str:
    return (
        "# V4.2 span-controlled geometry atlas\n\n"
        "Intrinsic geometry atlas over the frozen V3.6D span family. "
        "Identity-on-shared-Q is a null control, not a ranked competitor. "
        f"{manifest['no_inference_statement']}\n\n"
        f"- cases: {manifest['n_cases']}\n"
        f"- grid: {manifest['grid']}\n"
        f"- rows: {manifest['n_rows']}\n"
        f"- failed rows: {manifest['n_failed']}\n"
        f"- V3.6D digest: `{manifest['v3_6d_digest']}`\n"
        f"- 175° status: `{manifest['span_175_status']}`\n"
    )


def write_span_atlas_package(
    config: SpanControlledAtlasConfig,
    output: Path,
    *,
    registry: SpanRegistry | None = None,
    atlases: list[SpanCaseAtlas] | None = None,
    grid_shape: tuple[int, int] | None = None,
) -> Path:
    """Write the V4.2 package under the guarded span-atlas root."""
    resolved = assert_v4_2_output_allowed(output)
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved = prepare_v4_2_output_dir(resolved)
    if atlases is None:
        used_registry, cases, atlases = collect_span_atlas(
            config, registry=registry, grid_shape=grid_shape
        )
    else:
        used_registry = (
            load_locked_v3_6d_registry(config) if registry is None else registry
        )
        cases = generate_span_cases()
    all_rows = [row for atlas in atlases for row in atlas.rows]
    jsonl_path = resolved / "geometry_samples.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in all_rows:
            handle.write(json.dumps(row.to_dict()) + "\n")
    rank_records = []
    for atlas in atlases:
        for row in atlas.rows:
            record = attribution_from_row(row).to_dict()
            record["case_id"] = atlas.realized.case.case_id
            rank_records.append(record)
    (resolved / "rank_fields.json").write_text(
        json.dumps(rank_records, indent=2), encoding="utf-8"
    )
    used_shape = atlases[0].bank.shape if atlases else config.grid.shape
    case_payloads = []
    for atlas in atlases:
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
            }
        )
    (resolved / "cases.json").write_text(
        json.dumps(case_payloads, indent=2), encoding="utf-8"
    )
    n_failed = sum(1 for row in all_rows if row.failure_code is not None)
    n_samples = sum(len(atlas.bank.samples) for atlas in atlases)
    resolved_config = {
        "config": config.model_dump(),
        "config_digest": config.digest(),
        "v3_6d_digest": used_registry.sha256,
        "evaluated_grid": list(used_shape),
        "n_cases": len(atlases),
        "n_samples": n_samples,
        "n_rows": len(all_rows),
        "n_failed": n_failed,
        "case_ids": [atlas.realized.case.case_id for atlas in atlases],
    }
    (resolved / "resolved_config.json").write_text(
        json.dumps(resolved_config, indent=2), encoding="utf-8"
    )
    manifest = {
        "schema_version": config.schema_version,
        "package": "v4_2_span_controlled_geometry_atlas",
        "git_revision": git_revision(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "no_inference_statement": config.no_inference_statement,
        "config_digest": config.digest(),
        "v3_6d_digest": used_registry.sha256,
        "span_175_status": SPAN_175_STATUS,
        "n_cases": len(atlases),
        "n_samples": n_samples,
        "n_rows": len(all_rows),
        "n_failed": n_failed,
        "grid": list(used_shape),
        "mechanisms": ["fourbar", "span_matched_gearbox", "identity_on_shared_q"],
        "case_ids": [case.case_id for case in cases],
    }
    (resolved / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (resolved / "README.md").write_text(_readme_text(manifest), encoding="utf-8")
    write_span_controlled_atlas_html(
        resolved,
        config=config,
        registry=used_registry,
        atlases=atlases,
        manifest=manifest,
    )
    return resolved


def generate_span_controlled_geometry_atlas(
    *,
    config_path: Path | str | None = None,
    output: Path | str | None = None,
    grid_shape: tuple[int, int] | None = None,
) -> Path:
    """Load frozen config and write the V4.2 span-atlas package."""
    path = (
        Path(config_path)
        if config_path is not None
        else (REPO_ROOT / DEFAULT_CONFIG_REL)
    )
    config = load_span_atlas_config(path)
    target = Path(output) if output is not None else (REPO_ROOT / config.output_dir)
    assert_v4_2_output_allowed(target)
    return write_span_atlas_package(config, target, grid_shape=grid_shape)
