"""ADR-017 / Sprint V2.8 objective and study regression tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.experiments.v2_shared_q_fixtures import (
    FROZEN_MECHANISM_PAIRS,
    TASK_TEMPLATES,
    fractions_to_q,
)
from inequality_mechanisms.experiments.v2_runner import (
    UNIT_GEARBOX_MECHANISM_ID,
    unit_gearbox_branch,
)
from inequality_mechanisms.experiments.v2_shared_q_paired_study import (
    load_shared_q_paired_study_config,
    run_shared_q_paired_study,
)
from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.mechanisms import equivalent_gearbox_branch
from inequality_mechanisms.search.v2_objectives import (
    pair_box_scales,
    path_q_u_blend_components,
    q_u_blend_components,
    q_u_blend_edge_components,
    resolve_v2_objective,
)


REPO = Path(__file__).resolve().parents[2]


def _paired_graphs(shape: tuple[int, int] = (6, 6)):
    fourbar = fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    shared = UniformOutputLattice.from_output_space(fourbar.output_space, shape=shape)
    return (
        fourbar,
        gearbox,
        EmbeddedPlanningGraph.from_output_lattice(shared, fourbar),
        EmbeddedPlanningGraph.from_output_lattice(shared, gearbox),
    )


class TestQUBlendObjective:
    def test_affine_inverse_recovers_u(self) -> None:
        fourbar, gearbox, _, g_gb = _paired_graphs()
        cert = fourbar.certificate
        for node_id in range(g_gb.node_count):
            if not g_gb.valid_nodes[node_id]:
                continue
            q = g_gb.q_state(node_id)
            u = g_gb.u_state(node_id)
            # Span-matched affine inverse: u = u_min + (q - q_min) / r_eq
            u_lo = np.asarray(cert.input_lower)
            q_lo = np.asarray(cert.output_lower)
            q_hi = np.asarray(cert.output_upper)
            u_hi = np.asarray(cert.input_upper)
            r = (q_hi - q_lo) / (u_hi - u_lo)
            u_expected = u_lo + (q - q_lo) / r
            assert u == pytest.approx(u_expected, abs=1e-8)

    def test_span_matched_shares_branch_spans(self) -> None:
        fourbar, gearbox, _, _ = _paired_graphs()
        assert np.allclose(
            fourbar.certificate.input_lower, gearbox.certificate.input_lower
        )
        assert np.allclose(
            fourbar.certificate.input_upper, gearbox.certificate.input_upper
        )
        assert np.allclose(
            fourbar.certificate.output_lower, gearbox.certificate.output_lower
        )
        assert np.allclose(
            fourbar.certificate.output_upper, gearbox.certificate.output_upper
        )
        prov = gearbox.mechanism.provenance
        assert prov.get("label") == "span_matched_gearbox"
        assert "r_eq" in prov

    def test_fourbar_round_trip(self) -> None:
        fourbar, _, g_fb, _ = _paired_graphs()
        for node_id in range(g_fb.node_count):
            if not g_fb.valid_nodes[node_id]:
                continue
            q = g_fb.q_state(node_id)
            u = g_fb.u_state(node_id)
            assert fourbar.forward(u) == pytest.approx(q, abs=1e-6)

    def test_pure_q_edge_costs_identical(self) -> None:
        fourbar, _, g_fb, g_gb = _paired_graphs()
        cert = fourbar.certificate
        s_q, s_u = pair_box_scales(
            cert.output_lower, cert.output_upper, cert.input_lower, cert.input_upper
        )
        for a, b in list(g_fb.topology.iter_edges())[:20]:
            if not (
                g_fb.valid_nodes[a]
                and g_fb.valid_nodes[b]
                and g_gb.valid_nodes[a]
                and g_gb.valid_nodes[b]
            ):
                continue
            ca = q_u_blend_edge_components(
                g_fb, a, b, alpha=1.0, s_q=s_q, s_u=s_u
            )
            cb = q_u_blend_edge_components(
                g_gb, a, b, alpha=1.0, s_q=s_q, s_u=s_u
            )
            assert ca.combined == pytest.approx(cb.combined, abs=1e-12)
            assert ca.d_q == pytest.approx(cb.d_q, abs=1e-12)

    def test_blended_equals_normalized_sum(self) -> None:
        comps = q_u_blend_components(0.4, 0.6, alpha=0.25, s_q=2.0, s_u=3.0)
        assert comps.norm_q == pytest.approx(0.2)
        assert comps.norm_u == pytest.approx(0.2)
        assert comps.combined == pytest.approx(
            0.25 * comps.norm_q + 0.75 * comps.norm_u
        )

    def test_alpha_zero_matches_normalized_actuator(self) -> None:
        fourbar, _, g_fb, _ = _paired_graphs()
        cert = fourbar.certificate
        s_q, s_u = pair_box_scales(
            cert.output_lower, cert.output_upper, cert.input_lower, cert.input_upper
        )
        edges = [
            (a, b)
            for a, b in g_fb.topology.iter_edges()
            if g_fb.valid_nodes[a] and g_fb.valid_nodes[b]
        ][:10]
        for a, b in edges:
            comps = q_u_blend_edge_components(
                g_fb, a, b, alpha=0.0, s_q=s_q, s_u=s_u
            )
            assert comps.combined == pytest.approx(comps.norm_u, abs=1e-12)
            assert comps.combined == pytest.approx(comps.d_u / s_u, abs=1e-12)

    def test_components_nonnegative_finite(self) -> None:
        comps = q_u_blend_components(1.0, 2.0, alpha=0.5, s_q=4.0, s_u=5.0)
        assert comps.d_q >= 0 and comps.d_u >= 0
        assert np.isfinite(comps.combined)

    def test_path_components_match_edge_sum(self) -> None:
        fourbar, _, g_fb, _ = _paired_graphs()
        cert = fourbar.certificate
        s_q, s_u = pair_box_scales(
            cert.output_lower, cert.output_upper, cert.input_lower, cert.input_upper
        )
        # Short lattice path along first row.
        path = (0, 1, 2)
        if not all(g_fb.valid_nodes[n] for n in path):
            pytest.skip("fixture path invalid")
        path_comps = path_q_u_blend_components(
            g_fb, path, alpha=0.5, s_q=s_q, s_u=s_u
        )
        d_q = d_u = 0.0
        for a, b in zip(path[:-1], path[1:]):
            c = q_u_blend_edge_components(g_fb, a, b, alpha=0.5, s_q=s_q, s_u=s_u)
            d_q += c.d_q
            d_u += c.d_u
        assert path_comps.d_q == pytest.approx(d_q)
        assert path_comps.d_u == pytest.approx(d_u)

    def test_resolve_requires_scales(self) -> None:
        _, _, g_fb, _ = _paired_graphs()
        with pytest.raises(ValueError, match="q_u_blend"):
            resolve_v2_objective(g_fb, goal=0, cost_name="q_u_blend", alpha=0.5)


class TestFrozenFixtures:
    def test_five_pairs_and_task_templates(self) -> None:
        assert len(FROZEN_MECHANISM_PAIRS) == 5
        assert len(TASK_TEMPLATES) == 3
        assert {t.task_set_id for t in TASK_TEMPLATES} == {
            "cross_range",
            "joint1_dominant",
            "joint2_dominant",
        }

    def test_fractions_to_q(self) -> None:
        q = fractions_to_q([0.0, 10.0], [10.0, 20.0], (0.15, 0.20))
        assert q == pytest.approx([1.5, 12.0])


class TestSharedQPairedStudySmoke:
    def test_smoke_config_loads(self) -> None:
        cfg = load_shared_q_paired_study_config(
            REPO / "configs" / "v2" / "shared_q_paired_smoke.yaml"
        )
        assert cfg.study.name == "shared_q_paired_smoke"
        assert cfg.study.alphas == [1.0, 0.5]
        assert cfg.study.task_template_ids == ["cross_range"]

    def test_smoke_study_end_to_end(self, tmp_path: Path) -> None:
        cfg = load_shared_q_paired_study_config(
            REPO / "configs" / "v2" / "shared_q_paired_smoke.yaml"
        )
        # Shrink further for unit-test speed.
        cfg = cfg.model_copy(
            update={
                "sampling": cfg.sampling.model_copy(update={"shape": [5, 5]}),
                "branch": cfg.branch.model_copy(
                    update={
                        "n_samples": 48,
                        "table_samples_per_axis": 9,
                        "certification_samples_per_axis": 5,
                    }
                ),
            }
        )
        result = run_shared_q_paired_study(
            cfg, results_root=tmp_path, run_id="v28_smoke", write_figures=True
        )
        assert result.n_trial_rows == 6  # 1 pair × 1 task × 2 alpha × 3 mechs
        assert result.n_pair_comparisons == 4  # 2 alphas × 2 partners
        assert (result.path / "index.html").is_file()
        assert (result.path / "pair_comparisons.jsonl").is_file()
        assert (result.path / "pair_invariants.json").is_file()
        assert (result.path / "figures" / "expansions_raw.png").is_file()
        assert list((result.path / "figures" / "paths").glob("*_q.png"))
        assert list((result.path / "figures" / "paths").glob("*_x.png"))
        assert list((result.path / "figures").glob("*/u_unit_gearbox.png"))
        assert list((result.path / "figures").glob("*/qu_axis_maps.png"))
        html = (result.path / "index.html").read_text(encoding="utf-8")
        assert "Expansions" in html
        assert "Cartesian paths" in html
        assert "Identity control" in html
        assert "Transmission maps" in html
        study_block = html.split("Shared-Q paired study", 1)[1].split("Expansions", 1)[0]
        assert "Cross-range" in study_block
        assert "Joint-1" not in study_block
        assert "Joint-2" not in study_block
        trials = (result.path / "trials.jsonl").read_text(encoding="utf-8")
        assert "span_matched_gearbox" in trials
        assert "unit_gearbox" in trials
        assert "q_u_blend" in trials

        # Unit arm path/expansions are invariant across alphas.
        import json

        trial_rows = [
            json.loads(line)
            for line in (result.path / "trials.jsonl").read_text().splitlines()
            if line.strip()
        ]
        unit_rows = [
            r for r in trial_rows if r.get("mechanism_id") == UNIT_GEARBOX_MECHANISM_ID
        ]
        assert len(unit_rows) == 2
        assert unit_rows[0]["path_node_ids"] == unit_rows[1]["path_node_ids"]
        assert unit_rows[0]["n_expanded"] == unit_rows[1]["n_expanded"]
        fb_a1 = next(
            r
            for r in trial_rows
            if r.get("mechanism_id") == "fourbar" and float(r.get("alpha")) == 1.0
        )
        unit_a1 = next(r for r in unit_rows if float(r.get("alpha")) == 1.0)
        assert fb_a1["path_node_ids"] == unit_a1["path_node_ids"]
        assert fb_a1["n_expanded"] == unit_a1["n_expanded"]


class TestSharedQUDistanceStudySmoke:
    def test_u_smoke_config_loads(self) -> None:
        cfg = load_shared_q_paired_study_config(
            REPO / "configs" / "v2" / "shared_q_paired_u_smoke.yaml"
        )
        assert cfg.study.name == "shared_q_paired_u_smoke"
        assert cfg.u_distance_only
        assert cfg.study.alphas == []
        assert cfg.study.include_unit_gearbox is False
        assert cfg.study.task_template_ids == [
            "cross_range",
            "joint1_dominant",
            "joint2_dominant",
        ]

    def test_u_smoke_study_end_to_end(self, tmp_path: Path) -> None:
        cfg = load_shared_q_paired_study_config(
            REPO / "configs" / "v2" / "shared_q_paired_u_smoke.yaml"
        )
        cfg = cfg.model_copy(
            update={
                "sampling": cfg.sampling.model_copy(update={"shape": [5, 5]}),
                "branch": cfg.branch.model_copy(
                    update={
                        "n_samples": 48,
                        "table_samples_per_axis": 9,
                        "certification_samples_per_axis": 5,
                    }
                ),
            }
        )
        result = run_shared_q_paired_study(
            cfg, results_root=tmp_path, run_id="v29_u_smoke", write_figures=True
        )
        # 1 pair × 3 tasks × 1 cost × 2 mechs
        assert result.n_trial_rows == 6
        assert result.n_pair_comparisons == 3
        assert (result.path / "index.html").is_file()
        html = (result.path / "index.html").read_text(encoding="utf-8")
        assert "actuator travel only" in html
        assert "joint1_dominant" in html or "Joint-1" in html
        assert "Alphas" not in html or "α" not in html.split("Shared-Q paired study")[1][
            :800
        ]
        trials = [
            __import__("json").loads(line)
            for line in (result.path / "trials.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert all(r["cost_type"] == "actuator_travel" for r in trials)
        assert all(r.get("alpha") is None for r in trials)
        assert "unit_gearbox" not in {
            r["mechanism_id"] for r in trials
        }
        assert all(
            r.get("cost_norm_u") is not None and r["cost_norm_u"] >= 0.0 for r in trials
        )
        manifest = __import__("json").loads(
            (result.path / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["objective"]["cost"] == "actuator_travel"
        assert manifest["divergence_onset_by_alpha"] is None


class TestUnitGearboxBranch:
    def test_unit_branch_identity_round_trip(self) -> None:
        fourbar = fourbar_2d_branch()
        unit = unit_gearbox_branch(fourbar, name=UNIT_GEARBOX_MECHANISM_ID)
        cert = unit.certificate
        assert np.allclose(cert.input_lower, fourbar.certificate.output_lower)
        assert np.allclose(cert.input_upper, fourbar.certificate.output_upper)
        mid = 0.5 * (
            np.asarray(cert.input_lower) + np.asarray(cert.input_upper)
        )
        assert unit.forward(mid) == pytest.approx(mid, abs=1e-9)
        assert unit.inverse(mid) == pytest.approx(mid, abs=1e-9)
        jac = unit.mechanism.output_jacobian(mid)
        assert jac == pytest.approx(np.eye(len(mid)), abs=1e-12)
