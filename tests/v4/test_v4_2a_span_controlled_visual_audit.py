"""Sprint V4.2A span-controlled visual planning audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard
from inequality_mechanisms.audits.planar2r_visual import (
    assert_shared_wq_wx,
    compute_mechanism_edge_metrics,
    resolve_audit_trials,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
    V4_2_ALLOWED_PACKAGE,
    V4_2A_ALLOWED_OUTPUT_REL,
    V4_2A_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    assert_v4_2a_output_allowed,
    canonical_v4_2_retained_root,
    prepare_v4_2a_output_dir,
    v4_2_atlas_package_digest,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import (
    build_paired_lattice_arms_from_branches,
)
from inequality_mechanisms.experiments.span_cases import generate_span_cases, realize_span_case
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    FROZEN_V3_6D_DIGEST,
    SPAN_175_STATUS,
)
from inequality_mechanisms.experiments.v4.span_controlled_visual_audit import (
    _load_registry,
    _run_or_record_failure,
    _shared_weight_note,
    generate_span_controlled_visual_audit,
    sampling_arms_for_realized,
)
from inequality_mechanisms.experiments.v4.span_controlled_visual_audit_config import (
    DEFAULT_CONFIG_REL,
    NO_INFERENCE_STATEMENT,
    V4SpanVisualAuditConfigError,
    load_span_visual_audit_config,
)
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.mechanisms import span_synthesis
from inequality_mechanisms.visualization.v4.span_controlled_visual_audit import (
    write_span_visual_audit_root_html,
)


def test_v4_2a_allowed_root_and_nested_paths() -> None:
    root = (REPO_ROOT / V4_2A_ALLOWED_OUTPUT_REL).resolve()
    assert assert_v4_2a_output_allowed(root) == root
    child = root / "cases" / "span_j1_145_j2_145" / "trials" / "near_0" / "index.html"
    assert assert_v4_2a_output_allowed(child) == child.resolve()


def test_v4_2a_refuses_frozen_v4_2() -> None:
    path = canonical_v4_2_retained_root()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.2"):
        assert_v4_2a_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.2"):
        assert_v4_2a_output_allowed(path / "index.html")


@pytest.mark.parametrize(
    "package",
    [V4_0_ALLOWED_PACKAGE, V4_1_ALLOWED_PACKAGE, "v4_3_intrinsic_static_wrench"],
)
def test_v4_2a_refuses_sibling_v4_packages(package: str) -> None:
    path = (REPO_ROOT / "results" / "v4_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v4_2a_output_allowed(path)


@pytest.mark.parametrize("package", sorted(FROZEN_V3_REVIEW_PACKAGES))
def test_v4_2a_refuses_frozen_v3(package: str) -> None:
    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_2a_output_allowed(path)


def test_v4_2a_refuses_arbitrary_path(tmp_path: Path) -> None:
    with pytest.raises(ArtifactPathForbiddenError, match="not under the allowed root"):
        assert_v4_2a_output_allowed(tmp_path / "elsewhere")


def test_prepare_v4_2a_output_dir_creates_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v4_review" / V4_2A_ALLOWED_PACKAGE
    created = prepare_v4_2a_output_dir(allowed)
    assert created == allowed.resolve()
    frozen = tmp_path / "results" / "v4_review" / V4_2_ALLOWED_PACKAGE
    frozen.mkdir(parents=True)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.2"):
        prepare_v4_2a_output_dir(frozen)


def test_config_locks_digest_and_rejects_gravity(tmp_path: Path) -> None:
    cfg = load_span_visual_audit_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    assert cfg.v3_6d_digest_lock == FROZEN_V3_6D_DIGEST
    assert cfg.span_175_status == SPAN_175_STATUS
    assert cfg.seed == 7
    raw = json.loads((CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL).read_text(encoding="utf-8"))
    raw["gravity"] = 9.81
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4SpanVisualAuditConfigError, match="forbidden config key"):
        load_span_visual_audit_config(bad)


def test_registry_digest_and_no_synthesis(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = load_span_visual_audit_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    registry = _load_registry(cfg)
    assert registry.sha256 == FROZEN_V3_6D_DIGEST
    assert registry.record_for(175.0).status == SPAN_175_STATUS
    for span in (95.0, 135.0, 145.0, 150.0):
        assert registry.record_for(span).status == "certified_primary"

    def _boom(*_args, **_kwargs):
        raise AssertionError("span synthesis must not run on the V4.2A path")

    monkeypatch.setattr(span_synthesis, "synthesize_span_family", _boom)
    monkeypatch.setattr(
        "inequality_mechanisms.mechanisms.span_registry.build_span_registry",
        _boom,
    )
    again = _load_registry(cfg)
    assert again.sha256 == FROZEN_V3_6D_DIGEST
    cases = generate_span_cases()
    assert len(cases) == 17
    realized = [realize_span_case(case, registry) for case in cases]
    assert len(realized) == 17
    ids = [row.case.case_id for row in realized]
    assert len(set(ids)) == 17
    dual = next(row for row in realized if row.case.case_id == "span_j1_145_j2_145")
    assert "core_span_sweep" in dual.case.memberships
    assert "biological_refinement" in dual.case.memberships


def test_pair_invariants_and_shared_weights_one_case() -> None:
    cfg = load_span_visual_audit_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    registry = _load_registry(cfg)
    case = next(c for c in generate_span_cases() if c.case_id == "span_j1_145_j2_145")
    realized = realize_span_case(case, registry)
    arms = sampling_arms_for_realized(realized, L1=1.0, L2=1.0)
    assert set(arms) == {"fourbar", "gearbox"}
    lattice = build_paired_lattice_arms_from_branches(
        realized.fourbar,
        realized.gearbox,
        shape=(8, 8),
        connectivity=LatticeConnectivity.CHEBYSHEV_1,
    )
    audit = cfg.as_audit_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    audit.raw["task_ids"] = ["near_0", "far_0"]
    records = resolve_audit_trials(
        audit,
        sampling_arms=arms,
        lattice_shape=(8, 8),
        lattice_arms=lattice,
    )
    assert [r.task_id for r in records] == ["near_0", "far_0"]
    bundles = {
        mech: compute_mechanism_edge_metrics(lattice[mech], arms[mech], n_samples=8)
        for mech in ("fourbar", "gearbox")
    }
    assert_shared_wq_wx(bundles["fourbar"], bundles["gearbox"])
    wu_fb = {(e.a, e.b): e.w_u for e in bundles["fourbar"].edges}
    wu_gb = {(e.a, e.b): e.w_u for e in bundles["gearbox"].edges}
    assert wu_fb and wu_gb
    diffs = [abs(wu_fb[k] - wu_gb[k]) for k in wu_fb if k in wu_gb]
    assert diffs and max(diffs) > 0.0


def test_shared_weight_note_compares_intersection_when_edge_sets_disagree() -> None:
    from types import SimpleNamespace

    def _edge(a: int, b: int, w_q: float, w_x: float) -> SimpleNamespace:
        return SimpleNamespace(a=a, b=b, w_q=w_q, w_x=w_x, w_u=0.1)

    fourbar = SimpleNamespace(
        edges=[_edge(0, 1, 1.0, 2.0), _edge(1, 2, 1.5, 2.5)]
    )
    gearbox = SimpleNamespace(
        edges=[_edge(0, 1, 1.0, 2.0), _edge(2, 3, 9.0, 9.0)]
    )
    note = _shared_weight_note(fourbar, gearbox)
    assert note["edge_sets_equal"] is False
    assert note["fourbar_edges"] == 2
    assert note["gearbox_edges"] == 2
    assert note["shared_edges"] == 1
    assert note["w_q_mismatch_count"] == 0
    assert note["w_x_mismatch_count"] == 0


def test_root_html_has_seventeen_case_links(tmp_path: Path) -> None:
    cfg = load_span_visual_audit_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    registry = _load_registry(cfg)
    realized = [realize_span_case(case, registry) for case in generate_span_cases()]
    path = write_span_visual_audit_root_html(
        tmp_path,
        config=cfg,
        registry=registry,
        realized=realized,
        manifest={
            "git_revision": "test",
            "seed": 7,
            "lattice_shape": [8, 8],
            "v3_6d_digest": FROZEN_V3_6D_DIGEST,
            "no_inference_statement": NO_INFERENCE_STATEMENT,
        },
    )
    html = path.read_text(encoding="utf-8")
    assert "No-inference" in html
    assert NO_INFERENCE_STATEMENT in html
    assert SPAN_175_STATUS in html
    assert "planner arm" in html.lower()
    assert "winner" not in html.lower()
    assert "outperform" not in html.lower()
    for case in generate_span_cases():
        assert f"cases/{case.case_id}/index.html" in html
    assert html.count("span_j1_145_j2_145") >= 2


def test_tmp_export_one_case_html_and_frozen_v4_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sha_before, n_before = v4_2_atlas_package_digest()
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_2A_ALLOWED_PACKAGE
    path = generate_span_controlled_visual_audit(
        config_path=CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL,
        output=output,
        case_ids=["span_j1_145_j2_145"],
        task_ids=["near_0"],
        lattice_shape=(8, 8),
        skip_animations=True,
    )
    assert path == output.resolve()
    html = (path / "index.html").read_text(encoding="utf-8")
    assert NO_INFERENCE_STATEMENT in html
    assert SPAN_175_STATUS in html
    case_page = path / "cases" / "span_j1_145_j2_145" / "index.html"
    trial_page = path / "cases" / "span_j1_145_j2_145" / "trials" / "near_0" / "index.html"
    assert case_page.is_file()
    assert trial_page.is_file()
    trial_html = trial_page.read_text(encoding="utf-8")
    assert "Trial near_0" in trial_html
    assert "ompl" in trial_html.lower()
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    assert summary["v3_6d_digest"] == FROZEN_V3_6D_DIGEST
    assert summary["exported_case_ids"] == ["span_j1_145_j2_145"]
    assert (path / "architecture.html").is_file()
    sha_after, n_after = v4_2_atlas_package_digest()
    assert n_after == n_before
    assert sha_after == sha_before


def test_v3_6b_config_unchanged() -> None:
    path = CANONICAL_REPO_ROOT / "configs" / "v3" / "planar2r_visual_audit_v1.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["audit_id"] == "planar2r_visual_audit_v1"
    assert raw["artifact_contract"]["output_dir"] == (
        "results/v3_review/v3_6b_planar2r_visual_audit"
    )
    assert raw["mechanisms"]["fourbar"]["a"] == 1.0


def test_planner_exception_is_typed_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Arm:
        name = "fourbar"

    def _boom(**_kwargs):
        raise ValueError("edge cost from 128 to 96 produced non-finite or negative path cost inf")

    monkeypatch.setattr(
        "inequality_mechanisms.experiments.v4.span_controlled_visual_audit.run_planner_for_trial",
        _boom,
    )
    run = _run_or_record_failure(
        config=None,
        planner_name="lattice_dijkstra",
        arm=_Arm(),
        lattice_arm=None,
        task=None,
        contract=None,
        capture_trace=True,
    )
    assert run.status == "failed"
    assert run.skipped == "planner_exception"
    assert "non-finite" in str(run.planner_metrics.get("message"))
