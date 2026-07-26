# Sprint 3 — Freeze Output Space, Then Trust the Experiments

## Repository

<https://github.com/mfbailey91/Function_Generators_in_Open_Chains>

## Sprint theme

> Establish one seam-safe, bounded definition of output configuration space and use it consistently throughout graph construction, search, diagnostics, and experiments.

## Baseline (post–Sprint Two P0)

Sprint 3 is **not** greenfield. Sprint Two P0 already shipped the output-space contract and core abstraction:

| Deliverable | Status | Reference |
| --- | --- | --- |
| Output-space ADR | Done | [ADR-011](ADR-011-output-space-semantics.md) (IM-032) |
| `OutputSpace` / bounded revolute | Done | `src/inequality_mechanisms/spaces/output_space.py` (IM-033) |
| Four-bar trial-consistent lift helpers | Done | IM-034 |
| Cost / heuristic compatibility | Done | ADR-005 update (IM-035) |
| Matched-task residuals | Done | IM-036 |
| Edge-validation sensitivity (basic) | Done | `scripts/edge_validation_sensitivity.py` (IM-037) |
| Seam / topology invariant suite | Done | `tests/invariants/test_sprint_two_invariants.py` (IM-038) |

**Residual risk:** consumers can still call `mechanism.input_to_output()` directly. Costs and validation often canonicalize via `OutputSpace` after a raw \(g(u)\), bypassing the graph as the authoritative boundary. Sprint 3 tightens ownership, adds diagnostics, strengthens nesting sensitivity beyond IM-037, and runs the still-open controlled ablations (IM-019–021).

## Context

The project compares how gearboxes and nonlinear four-bar transmissions reshape graph-based motion planning through

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X.
\]

Sprint Two exposed and largely repaired a representation inconsistency: periodic actuator motion in \(\mathcal U\) and four-bar follower seam correction exist, and ADR-011 defines a bounded lifted \(\mathcal Q\). Downstream graph and experiment code can still consume raw principal-angle outputs at call sites that skip the graph boundary. Large experimental conclusions should wait until every graph-facing consumer uses the same authoritative path.

## Working model

For Sprint 3, continue ADR-011 semantics:

- \(\mathcal U\) is periodic on axes whose actuator cranks physically complete a revolution.
- Raw four-bar solver output may contain a numerical \(2\pi\) representation seam.
- \(\mathcal Q\) uses bounded, lifted revolute-joint coordinates on a continuous real-valued chart.
- Lift uses the **chart-center wrap** (not a separate unique-\(k\) search API):

  \[
  q_c = \tfrac{1}{2}(q_{\min}+q_{\max}),
  \qquad
  \operatorname{lift}(\theta)
  =
  q_c +
  \operatorname{wrap}_{(-\pi,\pi]}
  (\theta-q_c).
  \]

- Out-of-bounds after lift is detected by `contains()` / validity, not by `canonicalize` raising.
- Ambiguous intervals (span \(\le 0\) or \(\ge 2\pi\)) are rejected at axis construction.
- Output displacement is ordinary Euclidean displacement between canonical lifted coordinates.
- A seam crossing is allowed only when its lifted coordinate remains inside the physical output interval.

For each output axis:

\[
\mathcal Q_i = [q_{i,\min}, q_{i,\max}] \subset \mathbb R,
\qquad
q_{i,\max}-q_{i,\min}<2\pi.
\]

The width restriction ensures that a raw principal angle has at most one admissible representative in the configured output interval. When a unique in-interval lift exists, chart-center wrap agrees with the unique integer \(k\) satisfying \(q_{\min}\le\theta+2\pi k\le q_{\max}\).

## Sprint goal

By the end of Sprint 3, every graph and experiment operation will use one authoritative, seam-safe output representation owned by the graph. Controlled experiments will then determine whether the observed four-bar expansion increase is caused by the induced output metric, graph topology, periodic boundaries, or edge validation.

## Success criteria

### Engineering gates (binary)

Sprint 3 engineering work succeeds when:

1. A physical output state has exactly one experiment coordinate under ADR-011.
2. The graph owns the conversion from raw mechanism output to canonical output coordinates.
3. Validity, costs, heuristics, task matching, residuals, plots, and saved results use canonical outputs via that boundary.
4. Periodic wrapping remains confined to physically periodic actuator axes.
5. Representation-seam tests and bounded-output tests pass (including residual ownership cases).
6. Gearbox **interior** edges (non–input-wrap lattice edges) are invariant to edge-validation sample density; wrap-crossing edges are reported separately.
7. Edge sets are nested as validation density increases.
8. Controlled tasks produce stable feasibility, path costs, and expansion counts at the selected validation density.

### Scientific judgment (review, not CI)

9. The sprint review states whether the expansion reversal can be attributed to a tested mechanism rather than a coordinate inconsistency, and records a go/no-go on the full pilot rerun.

## Issue map

| Sprint item | Backlog | Notes |
| --- | --- | --- |
| S3-01 | IM-032 | Done; verify ADR-011 remains authoritative (no unique-\(k\) rewrite) |
| S3-02 | IM-033 | Done; residual API gaps only (`to_mechanism_native` optional) |
| S3-03 | IM-042 | Graph as canonical output boundary |
| S3-04 | IM-043 | Call-site audit of `input_to_output()` |
| S3-05 | IM-044 | Residual ownership / nesting regression tests (extends IM-038) |
| S3-06 | IM-045 | Output inspection diagnostics |
| S3-07 | IM-046 | Minimal edge microscope |
| S3-08 | IM-047 | Nested edge-sampling sensitivity (strengthens IM-037) |
| S3-09 | IM-019, IM-020, IM-021 | Controlled cost and topology ablations |

## Scope

### P0 — Ownership and residual correctness

P0 does **not** re-implement `OutputSpace`. It closes ownership gaps and residual API surface on top of ADR-011.

#### S3-01 — Confirm the output-space contract (IM-032)

Confirm [ADR-011](ADR-011-output-space-semantics.md) remains the authoritative contract:

- topology of each space;
- raw versus canonical output coordinates;
- chart-center lift selection;
- bounded displacement and distance;
- treatment of physical input wrapping;
- treatment of solver representation seams;
- out-of-bounds via `contains()` / validity after canonicalize;
- ambiguous spans rejected at construction;
- serialization conventions.

Amend ADR-011 only if Sprint 3 discovers a foundational gap (for example, documenting `to_mechanism_native` or clarifying interior vs wrap-crossing gearbox edges). Do not replace chart-center lift with a conflicting unique-\(k\) canonicalize API.

**Acceptance criteria**

- The distinction between physical wrap, representation seam, and output metric remains explicit.
- The output interval width requirement remains documented.
- Examples cover an allowed seam crossing and a seam crossing rejected by output limits.
- Sprint notes record “no ADR change” or point to a specific amendment.

#### S3-02 — Close residual output-space API gaps (IM-033)

`OutputSpace` and bounded revolute axes already exist. Extend only where the graph boundary needs it:

```python
class OutputAxis(Protocol):
    def canonicalize(self, raw: float) -> float: ...
    def to_mechanism_native(self, q: float) -> float: ...  # optional residual
    def displacement(self, q_from: float, q_to: float) -> float: ...
    def contains(self, q: float) -> bool: ...
```

**Acceptance criteria**

- Canonicalization continues to use chart-center wrap per ADR-011.
- Out-of-bounds after lift is detected by `contains()` / validity, not by silent clipping.
- Ambiguous intervals remain rejected at construction.
- Any new methods are deterministic, typed, and covered by tests.
- Do not rewrite the lift contract unless ADR-011 is amended first.

#### S3-03 — Make the graph the canonical output boundary (IM-042)

Extend the existing graph API (`ConstrainedInputGraph.output_at`) into one authoritative graph-facing output path. Prefer extending or aliasing over unnecessary rename churn:

```python
class ConstrainedInputGraph:
    def raw_output(self, u): ...           # mechanism g(u), labeled raw
    def output(self, u): ...               # may alias or replace output_at
    def output_displacement(self, u_from, u_to): ...
```

Migrate the following consumers to the graph boundary (or to `OutputSpace` only when no graph instance exists, with an explicit comment):

- node validity;
- edge-interior validity;
- edge costs;
- A* heuristics;
- task and preimage matching;
- output residuals;
- path metrics;
- plots;
- serialized results.

**Acceptance criteria**

- Downstream graph and experiment code does not use raw mechanism angles implicitly.
- Every intentional raw-output use is confined to mechanism internals or explicitly labeled diagnostics.
- Dijkstra and A* agree on optimal cost for deterministic test cases.

#### S3-04 — Audit direct mechanism-output calls (IM-043)

**Day 1:** inventory every direct call to `input_to_output()` and classify it as:

- mechanism-internal and permitted;
- graph-facing and to-be-migrated;
- diagnostic and explicitly labeled raw or canonical.

**Day 5 closeout:** re-audit after migration; no unresolved graph-facing raw-output calls remain.

**Acceptance criteria**

- The Day-1 inventory and Day-5 closeout are recorded in the pull request or sprint notes.
- No unresolved graph-facing raw-output calls remain.

#### S3-05 — Extend topology and seam regression tests (IM-044)

IM-038 already covers core seam and Dijkstra/A* invariants. Add residual cases that lock ownership and nesting behavior:

1. An actuator transition from \(2\pi-\epsilon\) to \(0\) follows the short periodic input path.
2. Raw follower samples \(179^\circ,-178^\circ\) canonicalize continuously to \(179^\circ,182^\circ\) when the interval permits it.
3. The same raw seam crossing is rejected when \(182^\circ\) exceeds the output limit (`contains` / validity).
4. Bounded output displacement does not take a shortest-angle shortcut through a forbidden region.
5. Canonicalization is consistent at nodes and edge-interior samples.
6. Cost and heuristic calculations use identical output semantics via the graph boundary.
7. Serialization round-trips without changing the output-space contract.
8. Graph-facing modules do not call `mechanism.input_to_output()` except through `raw_output` / labeled diagnostics.

**Acceptance criteria**

- New tests fail against remaining raw call-site / ownership gaps where appropriate.
- All new regression and invariant tests pass after integration.
- Do not require failure against pre–Sprint Two behavior already removed from main.

### P1 — Instrumentation and controlled science

S3-08 and S3-09 are the primary science work after P0 ownership repair.

#### S3-06 — Add output inspection diagnostics (IM-045)

Provide a diagnostic API without burdening the normal search path:

```python
graph.output(u)          # Fast path
graph.inspect_output(u)  # Diagnostic path
```

Suggested diagnostic record:

```python
@dataclass(frozen=True)
class AxisMappingDiagnostic:
    raw: float
    canonical: float | None
    winding: int | None
    within_bounds: bool
    crossed_native_seam: bool
```

**Acceptance criteria**

- Diagnostics expose raw and canonical values without changing search results.
- Records can be serialized into an experiment bundle.

#### S3-07 — Build a minimal edge microscope (IM-046)

For a selected graph edge, record and visualize:

- interpolation parameter;
- input samples;
- raw output samples;
- canonical output samples;
- winding numbers;
- assembly validity;
- output-limit validity;
- segment costs;
- first invalid sample.

The validator and visualizer must share the same trace-building logic.

**Acceptance criteria**

- A seam edge and an ordinary interior edge can be inspected.
- The reported edge decision matches graph construction exactly.
- The output identifies the first reason an edge is rejected.

#### S3-08 — Strengthen edge-sampling sensitivity (IM-047)

Builds on completed IM-037. Evaluate edge-validation densities:

\[
5,\ 9,\ 17,\ 33,\ 65.
\]

Verify:

\[
E_{65}\subseteq E_{33}\subseteq E_{17}\subseteq E_9\subseteq E_5.
\]

Track at every level:

- valid nodes;
- valid edges;
- connected components;
- reachable nodes;
- task feasibility;
- optimal path cost;
- gearbox expansions;
- four-bar expansions;
- removed **seam** edges versus removed **interior** edges;
- whether a removed edge belonged to the previous optimal path.

**Definitions**

- **Interior edge (gearbox):** a lattice edge that does not cross a periodic input wrap.
- **Wrap-crossing edge:** a lattice edge that uses input-axis periodicity.
- If unit-gearbox interior edges change with sample density, investigate before accepting a default density (do not silently absorb the change).

**Acceptance criteria**

- Valid-node count remains constant for a fixed sampled graph.
- Valid-edge count is nonincreasing.
- Optimal cost is nondecreasing for a fixed task that remains feasible.
- Unit-gearbox interior edges do not change with sample density; wrap-crossing edges are reported separately.
- The selected default density has stable deterministic search outcomes.
- Nesting \(E_{65}\subseteq\cdots\subseteq E_5\) is checked explicitly (stronger than IM-037 reporting alone).

#### S3-09 — Run controlled cost and topology ablations (IM-019, IM-020, IM-021)

Use a small fixed set of mechanisms and tasks **after** the graph boundary repair. Evaluate the same graph using:

1. uniform edge cost;
2. Euclidean input displacement;
3. canonical output-space displacement.

Also compare:

- periodic versus nonperiodic input boundaries (IM-020);
- monotonic follower branch versus full cycle, where applicable (IM-019);
- one source/goal pair versus all matched preimage sets.

**Acceptance criteria**

- Tasks are selected once and reused across conditions.
- Results distinguish metric effects from topology and connectivity effects.
- Expansion counts are reported both raw and normalized by reachable nodes.
- The sprint review states whether the observed reversal persists after the representation repair.

### P2 — Stretch work

Pull these items only after all P0 work is accepted:

- Dijkstra distance-field plots in \(\mathcal U\);
- expanded-node masks and goal-cost contours;
- reachable expansion fraction;
- goal-cost-ball fraction;
- low-transmission-ratio fraction;
- pullback-metric variation descriptors;
- full Monte Carlo pilot rerun.

## Out of scope

The following work is intentionally excluded from Sprint 3:

- interactive visualization applications;
- reinforcement learning;
- mechanism optimization;
- collision checking or dynamics;
- Cartesian path-complexity metrics;
- broad scientific claims based on the existing pilot;
- large new mechanism populations before P0 acceptance;
- rewriting `OutputSpace` lift semantics unless ADR-011 is amended.

## Delivery sequence

### Days 1–2 — Audit and confirm contract

- Confirm S3-01 against ADR-011 (amend only if needed).
- Complete the S3-04 Day-1 call-site inventory.
- Note residual S3-02 API gaps; write acceptance tests for ownership migration.

### Days 3–5 — Integrate ownership boundary

- Complete S3-03 graph boundary migration.
- Close residual S3-02 API gaps only as required by migration.
- Complete the S3-04 Day-5 closeout audit.
- Migrate costs, heuristics, validation, and task matching through the graph path.

### Days 6–7 — Verify and instrument

- Complete S3-05 residual regression tests.
- Add S3-06 diagnostics.
- Complete the minimal S3-07 edge microscope.

### Days 8–9 — Run controlled studies (primary science)

- Complete S3-08 nested edge-sampling sensitivity.
- Complete S3-09 cost and topology ablations (IM-019–021).
- Investigate any remaining gearbox interior-edge changes first.

### Day 10 — Sprint review

- Review engineering acceptance evidence.
- Document the ownership repair and experimental consequences.
- Record scientific judgment on criterion 9 and go/no-go for the large pilot rerun.
- Move incomplete stretch work back to the backlog.

## Dependencies

```text
S3-01 Confirm ADR-011 (done unless amended)
  └── S3-02 Residual OutputSpace API gaps
        ├── S3-04 Day-1 audit ──► S3-03 Graph boundary ──► S3-04 Day-5 closeout
        │                              └── S3-05 Residual regression tests
        └── S3-06 Diagnostics
              └── S3-07 Edge microscope

S3-03 + S3-05
  └── S3-08 Nested edge sensitivity (primary science)
        └── S3-09 Controlled ablations IM-019–021 (primary science)
```

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Lift selection depends on an implicit branch or reference | Results remain history-dependent or ambiguous | Keep chart-center lift and interval frozen in ADR-011; serialize the chart |
| Sprint rewrites OutputSpace against ADR-011 | Two lift contracts in force | Treat ADR-011 as authoritative; amend before changing code |
| Gearbox and four-bar use different coordinate charts | The comparison is not controlled | Use the same `OutputSpace` object and joint-limit interval for both mechanisms in each trial |
| A* heuristic uses different displacement semantics from edge costs | A* can lose admissibility or disagree with Dijkstra | Route both through the same graph / output-space distance operation and add agreement tests |
| Denser edge validation changes tasks or endpoints | Sensitivity results become confounded | Select fixed tasks at the densest setting and reuse them across levels |
| Gearbox wrap-crossing edges vary with sample density | Interior-invariance claim is misread | Separate interior vs wrap-crossing edges; investigate interior changes before accepting a default |
| Sprint expands into visualization platform work | Correctness work slips | Limit diagnostics to serializable traces and static plots |
| Existing experimental results are treated as final | Incorrect conclusions propagate | Mark current pilot results provisional until Sprint 3 exit criteria pass |

## Sprint artifacts

Expected deliverables:

- confirmation or amendment note for ADR-011 (not a duplicate ADR);
- residual `OutputSpace` API updates only as needed;
- graph integration and call-site audit (Day-1 inventory + Day-5 closeout);
- residual ownership / nesting regression tests;
- edge diagnostic trace and static edge microscope;
- nested edge-sampling sensitivity report (IM-047);
- controlled ablation summary (IM-019–021);
- go/no-go decision for the large pilot rerun.

## Definition of done

Sprint 3 is complete when:

- all P0 items meet their acceptance criteria;
- CI checks pass;
- no unresolved downstream raw-output usage remains;
- seam crossings behave according to physical output limits;
- gearbox interior edges are validation-density invariant (wrap-crossing reported separately);
- the chosen edge-validation density produces stable deterministic costs and expansions;
- Dijkstra and A* agree under the shared output semantics;
- the controlled ablation results have a documented interpretation;
- the team has recorded scientific judgment on criterion 9 and an explicit go/no-go on the full pilot rerun.

## Product decision

Large Monte Carlo claims are blocked by P0 ownership correctness. Small diagnostic runs and controlled ablations may proceed during the sprint because they directly validate the repair. S3-08 and S3-09 are the primary science deliverables after that repair.
