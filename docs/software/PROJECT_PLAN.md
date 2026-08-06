# Inequality Mechanisms — Software Project Plan

**Repository:** <https://github.com/mfbailey91/Function_Generators_in_Open_Chains>  
**Planning status:** Version 3 planner-agnostic pivot in progress ([V3_PROJECT_PLAN.md](V3_PROJECT_PLAN.md); [Sprint V3.0](planning/sprints/v3/SPRINT_V3_0_ARCHITECTURE_CONTRACT.md)). Version 2 Experiment A (V2.10 Dijkstra + V2.11 A*) and bounded Experiment B / V2.12 smoke–calibration evidence are frozen historical lineage; V2 Cartesian production inference remains held  
**Version 1 status:** Preserved as the full-cycle, input-state research baseline  
**Version 3 status:** Architecture and migration planning only; no new planner, obstacle, OMPL, MoveIt, or Monte Carlo code until V3 contracts are accepted

## Objective

Build a trustworthy, reproducible framework for studying how transmission mechanisms reshape planning through

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X.
\]

Version 1 established the full-cycle formulation in which graph state identity lives in actuator space \(\mathcal U\), preserving duplicate output preimages and periodic mechanism state.

Version 2 studies a narrower and more biologically grounded operating regime: each mechanism is restricted to a certified, locally invertible operating branch. Under that contract, output configuration \(\mathbf q\) is a complete kinematic state and may be used as the planning state, while the corresponding actuator configuration \(\mathbf u=g_m^{-1}(\mathbf q)\) remains attached physical data.

## Version 2 research question

> When a nonlinear transmission is restricted to a one-to-one operating branch, how does uniform actuator sampling allocate resolution and capability across output configuration space, and which planning effects remain when that nonuniform sampling is normalized away by a uniform-\(\mathcal Q\) control?

The Version 2 comparison separates three effects:

1. **Sampling effect** — uniform increments in \(\mathcal U\) become nonuniform nodes and edge lengths in \(\mathcal Q\).
2. **Metric and capability effect** — actuator travel, transmission ratio, resolution, torque tendency, and later energy remain mechanism-dependent even on a common uniform-\(\mathcal Q\) graph.
3. **Task effect** — the query definition determines which portions of the induced metric are exercised. Experiment A uses centered normalized \(\mathcal Q\) probes. Experiment B begins 2R position-only goal-region planning. Later 3R and 6R tasks add independently specified orientation.

The evidence program must distinguish a controlled mechanism probe from a representative robot-planning task distribution. A result from one task definition must not be presented as a mechanism-wide effect without naming that task distribution and solver.

## Scope decision

### Version 2 includes

1. one fixed assembly mode per mechanism;
2. one continuous, strictly monotonic operating branch per axis;
3. a unique inverse \(g_m^{-1}\) over the configured output range;
4. nonperiodic branch bounds;
5. planning state identity in \(\mathcal Q\);
6. two graph-sampling modes:
   - uniform in \(\mathcal U\), mapped into a nonuniform graph in \(\mathcal Q\);
   - uniform in \(\mathcal Q\), with actuator states recovered through \(g_m^{-1}\);
7. output-, input-, and later capability-aware planning objectives;
8. deterministic 2R controls before larger Monte Carlo studies;
9. an architecture that is dimension-independent before the 3R extension.

### Version 2 excludes from its core benchmark

- full-cycle crank wrapping;
- duplicate output preimages;
- planning over folded or multi-sheet output maps;
- assembly-mode switching;
- state representations such as \((q,\sigma)\);
- dynamics, collision checking, reinforcement learning, and hardware in the initial rearchitecture;
- claims that a nonlinear transmission must improve search.

These exclusions do not invalidate Version 1. They define a different experimental regime.

## State-identity rule

The correct planning state depends on the mechanism map used by the experiment.

### Version 1: noninjective or full-cycle mechanism

If

\[
\mathbf u_a \neq \mathbf u_b,
\qquad
g_m(\mathbf u_a)=g_m(\mathbf u_b),
\]

then \(\mathbf q\) is not a complete physical state. Node identity must retain \(\mathbf u\), branch, winding, or equivalent hidden mechanism state.

### Version 2: certified invertible operating branch

If

\[
g_m:\mathcal U_b\rightarrow\mathcal Q_b
\]

is one-to-one with a unique inverse over the configured branch, then

\[
\mathbf u=g_m^{-1}(\mathbf q)
\]

is uniquely determined. The planning node may therefore be identified by \(\mathbf q\), with \(\mathbf u\) stored as its physical realization.

No implementation may collapse a noninjective mechanism into a plain \(\mathcal Q\)-state graph.

## Core Version 2 model

### Output-state planning graph

A graph node has three separable meanings:

1. **topological identity** — node ID and adjacency;
2. **planning state** — output coordinate \(\mathbf q\);
3. **physical realization** — actuator coordinate \(\mathbf u\).

Conceptually:

```python
@dataclass(frozen=True)
class PlanningNode:
    node_id: int
    lattice_index: tuple[int, ...]
    q: NDArray[np.float64]
    u: NDArray[np.float64]
```

The graph must not assume that lattice coordinates, planning coordinates, and actuator coordinates are the same object.

### Sampling modes

#### Uniform actuator sampling

\[
u_{i,k}=u_{i,\min}+k\Delta u_i,
\qquad
q_{i,k}=g_i(u_{i,k}).
\]

The node lattice is regular in \(\mathcal U\) and generally nonuniform in \(\mathcal Q\). This is the primary physical-resolution case.

#### Uniform output sampling

\[
q_{i,k}=q_{i,\min}+k\Delta q_i,
\qquad
u_{i,k}=g_i^{-1}(q_{i,k}).
\]

The node lattice is regular in \(\mathcal Q\) and generally nonuniform in \(\mathcal U\). This is the representation control.

### Transition provenance

Planning state lives in \(\mathcal Q\), but each edge retains how it is continuously realized.

```python
class TransitionParameterization(str, Enum):
    INPUT_LINEAR = "input_linear"
    OUTPUT_LINEAR = "output_linear"
```

For an input-sampled edge:

\[
\mathbf u(s)=(1-s)\mathbf u_a+s\mathbf u_b,
\qquad
\mathbf q(s)=g_m(\mathbf u(s)).
\]

For an output-sampled edge:

\[
\mathbf q(s)=(1-s)\mathbf q_a+s\mathbf q_b,
\qquad
\mathbf u(s)=g_m^{-1}(\mathbf q(s)).
\]

Node identity is in \(\mathcal Q\); transition provenance remains available for validation and physical costs.

## Experimental matrix

The first controlled study must implement the following four cells.

| Sampling | Edge objective | Interpretation |
| --- | --- | --- |
| Uniform \(\mathcal U\), mapped to \(\mathcal Q\) | output distance \(c_Q\) | mechanically allocated output resolution |
| Uniform \(\mathcal Q\) | output distance \(c_Q\) | null control; mechanism identity must disappear |
| Uniform \(\mathcal Q\) | actuator distance \(c_U\) | transmission-induced actuator metric |
| Uniform \(\mathcal U\), mapped to \(\mathcal Q\) | actuator or capability cost | combined implementation effect |

where

\[
c_Q(a,b)=d_{\mathcal Q}(\mathbf q_a,\mathbf q_b)
\]

and

\[
c_U(a,b)=d_{\mathcal U}(\mathbf u_a,\mathbf u_b).
\]

## Null-control invariant

For a uniform-\(\mathcal Q\) graph with the same output bounds, topology, node count, start, goal, deterministic tie-breaking, and output-distance objective:

- a certified four-bar branch and its matched affine gearbox must expose identical \(\mathbf q\) nodes;
- adjacency must be identical;
- valid-node and valid-edge masks must be identical;
- edge weights must be identical;
- Dijkstra optimal cost and expansion order must be identical;
- A* optimal cost and expansion order must be identical when the same heuristic is used.

Any failure is an implementation defect or an undocumented experiment difference.

## Evidence ladder: from mechanism probe to robot task

Version 2 uses a staged task ladder rather than treating every start-goal definition as interchangeable.

### Experiment A — centered normalized \(\mathcal Q\)-space probes

**Status:** completed for V2.10 Dijkstra and V2.11 A* on the same frozen bank.

Experiment A is a centered, normalized-\(\mathcal Q\), equal-weight canonical-query experiment designed to vary displacement scale and direction while approximately controlling query location. Its estimand is the equal-weight mean mechanism effect over the frozen probe set.

It is not a random task population, uniform \(\mathcal Q\) sampling, or Cartesian task sampling. Authoritative protocol: [`EXPERIMENT_A_CENTERED_Q_PROBES.md`](experiments/protocols/EXPERIMENT_A_CENTERED_Q_PROBES.md).

### Experiment B — 2R Cartesian position goal-region planning

**Status:** ADR-019 and ADR-020 accepted; Sprint V2.12 active for the bounded `smoke_oracle_pair_v1` correctness implementation. Population inference remains held behind Cartesian calibration decisions and a crossed statistical design.

\[
\text{known physical start state}
\longrightarrow
\text{Cartesian position goal region}.
\]

Any certified output configuration satisfying \(\lVert f(\mathbf q)-\mathbf x_g\rVert_2\le\epsilon_X\) is an accepted goal. The primary task distribution is a fixed external Cartesian domain shared across the mechanism population. Pair-local reachable-workspace sampling is a control, not the main experiment.

The smoke uses nearest-valid-node start attachment within the configured Cartesian tolerance and records analytic IK families diagnostically; it does not yet claim IK-family balancing or exact start attachment. Dijkstra and A* run together only as a bounded optimal-cost oracle pair. Any production campaign returns to one solver per immutable run.

The bounded smoke must directly record the optimally settled goal node, load one authoritative solver policy from configuration, and pass exhaustive small-graph goal-set, equal-cost tie, YAML-load, and runner-integration tests before its evidence is reviewed.

Authoritative design: [`EXPERIMENT_B_CARTESIAN_GOAL_REGION.md`](experiments/protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md).

### Higher-dimensional task roadmap

1. **2R planar:** position-only task \((x,y)\);
2. **3R planar:** full planar pose \((x,y,\theta)\in SE(2)\);
3. **6R spatial:** full spatial pose \((x,y,z,R)\in SE(3)\).

The V2.7 gate is explicitly aligned to reviewed V2.12 Cartesian goal-set Dijkstra/A* evidence: establish the 2R position-task semantics before extending the task to 3R planar pose.

## Architecture

```text
inequality-mechanisms/
├── src/inequality_mechanisms/
│   ├── mechanisms/
│   │   ├── base.py                 # Existing full mechanism contract
│   │   ├── gearbox.py
│   │   ├── fourbar.py
│   │   └── operating_branch.py     # New invertible branch wrapper/certificate
│   ├── spaces/
│   │   ├── output_space.py         # Promoted to planning-state semantics in V2
│   │   └── limits.py
│   ├── graphs/
│   │   ├── grid.py                 # Legacy PeriodicGrid2D retained for V1
│   │   ├── topology.py             # New dimension-independent topology
│   │   ├── sampling.py             # Uniform-U and uniform-Q samplers
│   │   ├── embedded.py             # Q-state graph with U realization
│   │   ├── transitions.py          # Edge parameterization and trace
│   │   └── validation.py           # Legacy V1 graph retained during migration
│   ├── search/
│   │   ├── protocol.py             # Minimal generic search-graph protocol
│   │   ├── core.py                 # Dijkstra/A* independent of grid type
│   │   ├── objectives.py
│   │   └── result.py
│   ├── experiments/
│   │   ├── v1/                     # Optional later organization; no forced move
│   │   ├── v2_config.py
│   │   ├── v2_tasks.py
│   │   ├── v2_runner.py
│   │   └── v2_results.py
│   ├── metrics/
│   └── visualization/
├── tests/
│   ├── golden_v1/
│   ├── operating_branches/
│   ├── graphs_v2/
│   ├── search/
│   └── experiments_v2/
├── configs/
│   ├── v1/
│   └── v2/
├── scripts/
├── results/
└── docs/
    ├── software/                  # Normative architecture, planning, experiments
    ├── research/                  # Paper, theory, literature
    └── archive/                   # Historical status and superseded material
```

The source-code split is a target, not a requirement to move stable Version 1 modules immediately. Documentation is organized now by authority: software contracts and ADRs are normative, sprint files execute those decisions, experiment documents define evidence, and research documents motivate without silently expanding implementation scope.

## Core interfaces

### Generic search graph

Search must depend on node IDs and adjacency, not on `PeriodicGrid2D` or actuator coordinates.

```python
class SearchGraph(Protocol):
    @property
    def node_count(self) -> int: ...

    def node_is_valid(self, node_id: int) -> bool: ...

    def neighbors(self, node_id: int) -> Iterable[int]: ...
```

Coordinates remain graph-specific APIs used by objectives, heuristics, metrics, and visualization:

```python
class EmbeddedStateGraph(SearchGraph, Protocol):
    def q_state(self, node_id: int) -> NDArray[np.float64]: ...
    def u_state(self, node_id: int) -> NDArray[np.float64]: ...
```

### Certified operating branch

```python
class OperatingBranch(Protocol):
    @property
    def input_dim(self) -> int: ...

    @property
    def output_dim(self) -> int: ...

    def forward(self, u: ArrayLike) -> NDArray[np.float64]: ...
    def inverse(self, q: ArrayLike) -> NDArray[np.float64]: ...
    def jacobian(self, u: ArrayLike) -> NDArray[np.float64]: ...
    def contains_input(self, u: ArrayLike) -> bool: ...
    def contains_output(self, q: ArrayLike) -> bool: ...
    def to_dict(self) -> dict[str, Any]: ...
```

```python
@dataclass(frozen=True)
class BranchCertificate:
    input_lower: tuple[float, ...]
    input_upper: tuple[float, ...]
    output_lower: tuple[float, ...]
    output_upper: tuple[float, ...]
    monotonic_sign: tuple[int, ...]
    min_abs_gain: tuple[float, ...]
    max_abs_gain: tuple[float, ...]
    max_forward_inverse_residual: float
    max_inverse_forward_residual: float
    certification_samples_per_axis: int
```

Version 2 initially requires square, axis-separable maps with a unique inverse. General coupled maps are future work.

## Configuration versioning

Version 1 configurations and result schemas must remain reproducible.

Version 2 configurations require an explicit architecture discriminator:

```yaml
architecture_version: 2
planning_space: output

sampling:
  domain: input          # input | output
  shape: [64, 64]
  include_endpoints: true

branch:
  certification_samples_per_axis: 1025
  minimum_abs_gain: 0.05
  inverse_tolerance: 1.0e-9

objective:
  cost: output_euclidean
  heuristic: output_euclidean
```

The loader must reject ambiguous configurations. It must never infer Version 2 semantics from a Version 1 file.

## Result schema

Every Version 2 trial must record at minimum:

```text
architecture_version
result_schema_version
mechanism_id
branch_id
branch_certificate
sampling_domain
transition_parameterization
graph_shape
node_count
valid_node_count
valid_edge_count
requested_start_q
requested_goal_q
realized_start_q
realized_goal_q
start_residual_q
goal_residual_q
start_u
goal_u
cost_type
heuristic_type
found
optimal_cost
n_expanded
n_generated
n_stale
n_path_edges
path_length_u
path_length_q
path_length_x
q_spacing_summary
u_spacing_summary
seed
code_revision
```

## Primary engineering invariants

1. Existing Version 1 golden fixtures remain unchanged after generic-search refactoring.
2. A branch is rejected unless its inverse and gain margins satisfy the configured certificate.
3. Every Version 2 graph node stores finite \(\mathbf q\) and \(\mathbf u\) vectors of the expected dimension.
4. For every node:
   \[
   g_m(\mathbf u)\approx\mathbf q,
   \qquad
   g_m^{-1}(\mathbf q)\approx\mathbf u.
   \]
5. Uniform-input samples are uniform in \(\mathcal U\) and generally nonuniform in \(\mathcal Q\).
6. Uniform-output samples are uniform in \(\mathcal Q\) and generally nonuniform in \(\mathcal U\).
7. Version 2 branch graphs have no periodic topology.
8. Dijkstra and A* agree on optimal cost for every supported objective/heuristic pair.
9. The uniform-\(\mathcal Q\), output-distance null control is exact within deterministic numerical tolerances.
10. No graph or experiment silently calls an all-preimages API where a unique branch inverse is required.

## Milestones and sprint sequence

### V2-M0 — Contract and baseline preservation

Freeze the Version 2 scientific contract, preserve Version 1, write ADRs, and establish golden regression fixtures.

**Sprint:** [`SPRINT_V2_0_CONTRACT_AND_BASELINE.md`](planning/sprints/v2/SPRINT_V2_0_CONTRACT_AND_BASELINE.md)

### V2-M1 — Generic search and topology boundary

Decouple Dijkstra/A* from `ConstrainedInputGraph` and `PeriodicGrid2D`. Add a dimension-independent topology contract while retaining Version 1 behavior through adapters.

**Sprint:** [`SPRINT_V2_1_GENERIC_SEARCH_GRAPH.md`](planning/sprints/v2/SPRINT_V2_1_GENERIC_SEARCH_GRAPH.md)

### V2-M2 — Certified operating branches

Add explicit branch objects, unique inverses, certification, gain margins, and matched affine gearboxes.

**Sprint:** [`SPRINT_V2_2_OPERATING_BRANCHES.md`](planning/sprints/v2/SPRINT_V2_2_OPERATING_BRANCHES.md)

### V2-M3 — Output-state graph construction

Implement uniform-input and uniform-output samplers, embedded \(\mathcal Q\)-state graphs, transition provenance, and null-control graph invariants.

**Sprint:** [`SPRINT_V2_3_OUTPUT_STATE_GRAPHS.md`](planning/sprints/v2/SPRINT_V2_3_OUTPUT_STATE_GRAPHS.md)

### V2-M4 — Versioned experiment pipeline

Add Version 2 tasks, configs, result schema, runner, CLI, provenance, and compatibility gates.

**Sprint:** [`SPRINT_V2_4_EXPERIMENT_PIPELINE.md`](planning/sprints/v2/SPRINT_V2_4_EXPERIMENT_PIPELINE.md)

### V2-M5 — Controlled 2R study

Run deterministic controls, resolution sweeps, matched mechanism comparisons, and only then a modest mechanism population.

**Sprint:** [`SPRINT_V2_5_CONTROLLED_2R_STUDY.md`](planning/sprints/v2/SPRINT_V2_5_CONTROLLED_2R_STUDY.md)

### V2-M6 — Exact tasks and capability objectives

Remove endpoint-snapping confounds with query overlays; add actuator and initial capability-aware objectives.

**Sprint:** [`SPRINT_V2_6_QUERY_OVERLAYS_AND_CAPABILITIES.md`](planning/sprints/v2/SPRINT_V2_6_QUERY_OVERLAYS_AND_CAPABILITIES.md)

### V2 evaluation deliverable — HTML run printout

After V2.6, each Version 2 run package must support a Sprint-6-style HTML printout (`results/<run_id>/index.html`) summarizing manifest metadata, null-control status, trials, failures, branch certificates, diagnostics, and figures. Regenerate with `scripts/generate_v2_canvas.py`. Use this printout (and the controlled 2R study artifacts) to evaluate 2R evidence before any higher-dimension work.

### V2-M7 — 3R extension (deferred)

**Status: deferred / held.** Extend the proven abstractions to 3R planar planning only after trusted 2R Cartesian goal-set evaluation. First with full pose \((x,y,\phi)\), then with position-only redundant goals.

**Sprint:** [`SPRINT_V2_7_3R_EXTENSION.md`](planning/sprints/v2/SPRINT_V2_7_3R_EXTENSION.md) (not in the active execution sequence)

The V2.7 entry gate is review of trusted V2.12 2R Cartesian goal-set Dijkstra and A* evidence. This is an explicit roadmap decision: 2R position tasks precede 3R planar-pose tasks.

### V2-M8 — Experiment B / V2.12 Cartesian goal regions

**Status: active bounded smoke; production held.** ADR-019 and ADR-020 authorize the goal-set search primitive, fixed smoke domain, nearest-node start attachment, and paired Dijkstra/A* correctness run. Production calibration, crossed uncertainty, sequential stopping, and evidence reporting remain incomplete.

**Sprint:** [`SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md`](planning/sprints/v2/SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md) (active bounded smoke)

## Migration strategy

1. **Do not delete or reinterpret Version 1.** Tag or record its last trusted revision.
2. **Refactor search before changing science.** The first code sprint must reproduce existing results.
3. **Add new branch and graph types beside legacy types.** Avoid changing `Mechanism.inverse_output()` into a unique-inverse API.
4. **Use explicit adapters.** Legacy `ConstrainedInputGraph` should satisfy the generic search protocol without becoming a Version 2 graph.
5. **Add Version 2 configs and runners beside Version 1.** Do not silently migrate old YAML.
6. **Promote only after the null control passes.** Large Version 2 Monte Carlo runs are blocked until the exact uniform-\(\mathcal Q\) control is green.
7. **Move files only when movement provides architectural value.** Rename-only churn should be deferred.

## Testing strategy

Each sprint must add tests at four levels where applicable:

1. **unit tests** for pure interfaces and numerical functions;
2. **property/invariant tests** for maps, graphs, and objectives;
3. **golden regression tests** protecting Version 1 behavior;
4. **small end-to-end fixtures** with deterministic paths, costs, and expansions.

Required CI commands remain:

```bash
pytest
ruff check .
ruff format --check .
mypy src
```

Sprints may add targeted commands, but no acceptance criterion may depend only on manual notebook inspection.

## Cursor and coding-agent rules

- Work one numbered issue at a time.
- Read this plan, the active sprint file, and referenced ADRs before editing code.
- Begin architectural issues with a call-site and dependency inventory.
- Preserve existing APIs through adapters unless the sprint explicitly authorizes a break.
- Do not change experiment semantics to make tests pass.
- Add tests before or with the implementation.
- After each issue, run targeted tests and then the full CI suite.
- Update issue status and record any deviation from the specified interface.
- Stop and write an ADR amendment when a foundational assumption changes.
- Do not implement future-sprint work opportunistically.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Version 1 and Version 2 state rules become conflated | False connectivity or misleading comparisons | Explicit architecture version, separate ADRs, compatibility tests |
| Generic graph abstraction becomes overly clever | Harder scientific auditing | Keep search protocol minimal; coordinates stay explicit on concrete graphs |
| Branch certification samples miss a reversal | Invalid unique-inverse assumption | Dense deterministic certification, derivative margin, inverse residual tests, rejection near extrema |
| Uniform-\(\mathcal Q\) control differs by mechanism | Null control is contaminated | Construct shared topology and shared \(q\) array once; attach mechanism-specific \(u\) arrays afterward |
| Endpoint snapping dominates results | Apparent mechanism effect is discretization error | Record residuals first; add exact query overlays before capability claims |
| 3R begins before 2R semantics are trusted | Higher dimension hides defects | Block 3R on null-control, grid-convergence, and explicit 2R evaluation review (V2-M7 deferred) |
| Cursor follows the old always-apply rule literally | Agent rejects Version 2 architecture | Update `.cursor/rules/project.mdc` during V2-M0 with conditional V1/V2 state rules |

## Version 2 release gate

Version 2 is ready for a paper-facing controlled study when:

1. Version 1 golden regressions pass;
2. generic search is independent of graph implementation and dimension;
3. branch certificates reject noninjective or near-singular operating ranges;
4. both sampling modes produce valid, reproducible output-state graphs;
5. the uniform-\(\mathcal Q\), output-distance null control passes exactly;
6. endpoint residuals are bounded and reported, or exact overlays are used;
7. Dijkstra and A* agree for all supported objectives;
8. grid-resolution trends are understood;
9. one versioned command reproduces the controlled 2R result package;
10. the report distinguishes sampling, metric, heuristic, and task effects without presuming their sign.
