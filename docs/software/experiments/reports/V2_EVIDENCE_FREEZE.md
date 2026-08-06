# Version 2 evidence freeze

**Status:** Frozen for Version 3 planner-agnostic rearchitecture  
**Architecture:** Version 2 (ADR-014 output-state identity on certified branches)  
**Freeze date:** 2026-08-06  
**Reference:** [Sprint V3.0](../../planning/sprints/v3/SPRINT_V3_0_ARCHITECTURE_CONTRACT.md), [V3 project plan](../../V3_PROJECT_PLAN.md), [V2→V3 pivot note](../../architecture/notes/PROJECT_NOTE_V2_TO_V3_PIVOT.md)

## Reviewed revision

| Field | Value |
| --- | --- |
| Branch | `v3_rearchitecture` |
| Commit | `a51079df0f3ae39838ed10db10aa7d5930dd3ee5` |
| Subject | Add regenerable Experiment B HTML printouts for smoke and calibration. |
| Preferred tag | `v2-evidence-freeze` (create after this freeze document lands on the trusted lineage) |

Version 3 must preserve Version 2 golden regressions and trusted experiment reports relative to this lineage. Later commits may add Version 3 contracts and adapters beside Version 2; they must not silently reinterpret frozen Version 2 estimands as general robot-planning results.

Uncommitted Version 2.12 documentation edits on the freeze branch refine protocol/sprint wording around the recorded smoke and calibration packages; they do not authorize production inference.

## Accepted ADRs (Version 2 authority)

- ADR-014 — V2 output-state on invertible branches
- ADR-015 — Topology, embedding, transition provenance
- ADR-016 — V1/V2 configuration compatibility
- ADR-017 — Shared-Q planning with normalized Q/U cost
- ADR-018 — A* heuristic for actuator-travel production campaigns
- ADR-019 — V2 external Cartesian task domain (accepted for smoke/calibration)
- ADR-020 — V2 goal-set search semantics

Version 1 ADRs (001–013) remain authoritative under `architecture_version: 1`. Version 3 ADRs (021–026) are proposed architecture contracts and do not rewrite Version 2 evidence.

## Trusted Experiment A lineage

Centered normalized \(\mathcal Q\) probes on a shared uniform-\(\mathcal Q\) graph with mechanism-dependent actuator-travel cost.

| Artifact | Path / role |
| --- | --- |
| Protocol | [`../protocols/EXPERIMENT_A_CENTERED_Q_PROBES.md`](../protocols/EXPERIMENT_A_CENTERED_Q_PROBES.md) |
| V2.10 Dijkstra report | [`V2_10_PRODUCTION_DIJKSTRA_SUMMARY.md`](V2_10_PRODUCTION_DIJKSTRA_SUMMARY.md) · [`V2_10_PRODUCTION_DIJKSTRA.html`](V2_10_PRODUCTION_DIJKSTRA.html) |
| V2.11 A* report | [`V2_11_ASTAR_PAIRED_CAMPAIGN_SUMMARY.md`](V2_11_ASTAR_PAIRED_CAMPAIGN_SUMMARY.md) · [`V2_11_ASTAR_PAIRED_CAMPAIGN.html`](V2_11_ASTAR_PAIRED_CAMPAIGN.html) |
| Supporting summaries | [`V2_8_SHARED_Q_PAIRED_STUDY_SUMMARY.md`](V2_8_SHARED_Q_PAIRED_STUDY_SUMMARY.md), [`V2_9_SHARED_Q_U_DISTANCE_SUMMARY.md`](V2_9_SHARED_Q_U_DISTANCE_SUMMARY.md) |
| Sample bank | `configs/v2/sample_banks/production_v1.json` |
| Production configs | `configs/v2/production_dijkstra.yaml`, `configs/v2/production_astar.yaml` (and smoke/pilot/calibration companions) |

Experiment A results apply to the declared centered-Q task suite, four-connected lattice topology, objective, and solver. They are not a representative Cartesian robot-task distribution.

## Bounded Experiment B lineage (non-production)

Known physical start → Cartesian position goal region (2R position-only).

| Artifact | Path / role |
| --- | --- |
| Protocol | [`../protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md`](../protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md) |
| V2.12 summary | [`V2_12_CARTESIAN_GOAL_REGION_SUMMARY.md`](V2_12_CARTESIAN_GOAL_REGION_SUMMARY.md) · [`V2_12_CARTESIAN_GOAL_REGION.html`](V2_12_CARTESIAN_GOAL_REGION.html) |
| Smoke config | `configs/v2/cartesian_goal_region_smoke.yaml` |
| Calibration config | `configs/v2/cartesian_goal_region_calibration.yaml` |
| Sprint | [`../../planning/sprints/v2/SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md`](../../planning/sprints/v2/SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md) |

**Status:** smoke and V2B-005 calibration only. Population Monte Carlo, crossed-mechanism inference, and production orchestration remain **held**. Do not promote bounded B packages into application-task estimands without Version 3 contracts.

## Configuration and schema versions

| Concern | Value |
| --- | --- |
| Architecture gate | `architecture_version: 2` (ADR-016) |
| V2 config / result modules | `experiments/v2_config.py`, `experiments/v2_results.py` |
| Graph semantics contract | `docs/software/architecture/contracts/V2_3_GRAPH_SEMANTICS.md` |
| Objective (trusted campaigns) | `actuator_travel` with ADR-018 A* heuristic where applicable |
| Cartesian domain id (B) | `planar2r_left_workcell_v1` (ADR-019) |

## Formulation limitations (must not be generalized silently)

1. **Fixed normalized Q-space task lengths (Experiment A)** — diagnostic probes, not the primary robot-task distribution.
2. **`start_tolerance` (Experiment B)** — lattice attachment approximation, not application start semantics. Version 3 uses an exact start; attachment residual is an algorithm diagnostic.
3. **Four-connected one-coordinate-at-a-time motion** — historical lattice primitive; not a general robot local-motion model.
4. **Node expansions as dominant planner metric** — meaningful for graph search; not universal across planner families.
5. **Relative log ratios alone** — obscure absolute computational importance; Version 3 requires paired absolute effects.
6. **Free-space planner necessity** — many free-space tasks may be already satisfied or directly connectable; classify before benchmarking.
7. **Q-spanner vs Cartesian estimands** — must retain separate experiment identities; do not merge.

## Files that must remain reproducible

### Configs

- `configs/v2/production_dijkstra.yaml`, `configs/v2/production_astar.yaml`
- `configs/v2/production_*_{smoke,pilot,calibration,confirmation}.yaml` companions used by trusted reports
- `configs/v2/shared_q_paired_*.yaml`
- `configs/v2/cartesian_goal_region_smoke.yaml`, `configs/v2/cartesian_goal_region_calibration.yaml`
- `configs/v2/sample_banks/production_v1.json`
- `configs/v2/smoke.yaml`

### Reports and protocols

- All Version 2 summaries linked above
- Experiment A and B protocols under `docs/software/experiments/protocols/`
- Regenerable HTML dashboards cited by those reports

### Golden / regression fixtures

- Version 1 golden fixtures under `tests/golden_v1/` (still required green under V2/V3 work)
- Version 2 unit and integration tests under `tests/` that encode shared-Q, branch, objective, and goal-set semantics

## Reproduction commands

```bash
pytest tests/golden_v1
pytest tests/search tests/graphs tests/spaces tests/mechanisms
pytest
ruff check .
ruff format --check .
mypy src
```

Trusted campaign entry points follow the Version 2 production and Cartesian runners documented in the corresponding sprint and report files. Large Monte Carlo trial packages under `results/` are **not** golden; regenerate only under the frozen configs and sample banks, and never edit generated rows to improve appearance.

## Artifacts that are not golden

- `results/**` Monte Carlo and Cartesian trial packages (except as cited run ids in trusted reports)
- Canvas HTML bundles and large diagnostic image sets regenerated for packaging
- Any run whose seed, dirty-tree flag, or dependency versions are unset
- Stochastic population draws without a fixed sample bank
- Crossed-statistics or production-inference claims for Experiment B (not authorized)

## Preservation rule

No existing Version 2 configuration may silently acquire Version 3 semantics.
Missing `architecture_version` continues to mean Version 1 (ADR-016).
`architecture_version: 2` continues to mean the frozen Version 2 contracts above.
Version 3 code and schemas must use an explicit Version 3 discriminator when introduced.
