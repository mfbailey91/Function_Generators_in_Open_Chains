# Sprint V2.3 — Output-State Graphs and Sampling Provenance

## Theme

> Build one planning space with two controlled ways of placing nodes inside it.

## Objective

Implement Version 2 graphs whose node identity and stored planning coordinate live in \(\mathcal Q\), with unique actuator realizations attached through a certified operating branch. Support uniform-input and uniform-output sampling on a shared dimension-independent topology.

## Required inputs

- generic search and topology contracts from Sprint V2.1;
- certified `OperatingBranch` from Sprint V2.2;
- `OutputSpace` from ADR-011;
- ADR-014 and ADR-015.

## Target data model

Create `src/inequality_mechanisms/graphs/embedded.py`.

```python
@dataclass(frozen=True)
class EmbeddedPlanningGraph:
    topology: TensorGridTopology
    branch: OperatingBranch
    q_nodes: NDArray[np.float64]       # shape (node_count, output_dim)
    u_nodes: NDArray[np.float64]       # shape (node_count, input_dim)
    valid_nodes: NDArray[np.bool_]
    sampling_domain: SamplingDomain
    transition_parameterization: TransitionParameterization
```

Required APIs:

```python
@property
def node_count(self) -> int: ...

def node_is_valid(self, node_id: int) -> bool: ...
def neighbors(self, node_id: int) -> tuple[int, ...]: ...
def q_state(self, node_id: int) -> NDArray[np.float64]: ...
def u_state(self, node_id: int) -> NDArray[np.float64]: ...
def edge_trace(self, a: int, b: int, n_samples: int) -> EdgeTraceV2: ...
```

The graph satisfies the generic search protocol.

## Sampling contracts

### Uniform-input sampler

Create branch-bounded axis samples:

```python
np.linspace(u_lower, u_upper, n, endpoint=True)
```

Map every node through `branch.forward`.

Store:

- `sampling_domain = input`;
- `transition_parameterization = input_linear`.

### Uniform-output sampler

Create output-space axis samples:

```python
np.linspace(q_lower, q_upper, n, endpoint=True)
```

Map every node through `branch.inverse`.

Store:

- `sampling_domain = output`;
- `transition_parameterization = output_linear`.

Both samplers use nonwrapped `TensorGridTopology`.

## Issues

### V2-301 — Add sampling enums and records

Create:

```python
class SamplingDomain(str, Enum):
    INPUT = "input"
    OUTPUT = "output"

class TransitionParameterization(str, Enum):
    INPUT_LINEAR = "input_linear"
    OUTPUT_LINEAR = "output_linear"
```

Add a serializable `SamplingSpecification` containing domain, shape, endpoint policy, and axis bounds used.

### V2-302 — Implement uniform-input sampling

Requirements:

- all sampled \(u\) lie inside the branch;
- all mapped \(q\) lie in the branch output space;
- topology is nonperiodic;
- node arrays are deterministic and contiguous;
- each node passes
  \[
  \|g(u)-q\|\le\epsilon.
  \]

Report per-axis output spacing statistics:

- minimum;
- maximum;
- mean;
- standard deviation;
- ratio of maximum to minimum positive spacing.

### V2-303 — Implement uniform-output sampling

Requirements mirror V2-302, with uniform \(q\) and recovered \(u\).

Report per-axis actuator spacing statistics.

### V2-304 — Implement Version 2 edge traces

Create a trace independent of the legacy full-cycle `build_edge_trace`.

```python
@dataclass(frozen=True)
class EdgeTraceV2:
    s: NDArray[np.float64]
    q: NDArray[np.float64]
    u: NDArray[np.float64]
    branch_valid: NDArray[np.bool_]
    forward_inverse_residual: NDArray[np.float64]
    first_invalid_index: int | None
```

For `INPUT_LINEAR`, interpolate \(u\), then compute \(q\).

For `OUTPUT_LINEAR`, interpolate \(q\), then compute \(u\).

All edge traces must remain within the same certified branch. No wrapping is permitted.

### V2-305 — Implement graph validity and adjacency

The initial Version 2 branch box should make every sampled node and axis-aligned edge valid. Keep masks explicit because later constraints may remove nodes or edges.

Requirements:

- node validity is cached;
- edge validity may be cached or compiled;
- deterministic neighbor order comes from topology;
- graph exposes node-ID neighbors only;
- no direct use of `PeriodicGrid2D`.

### V2-306 — Build shared uniform-\(\mathcal Q\) topology control

For the null control, construct the \(q\) sample array and topology once, then attach mechanism-specific actuator arrays.

Preferred API:

```python
shared = UniformOutputLattice.from_output_space(output_space, shape)
gearbox_graph = EmbeddedPlanningGraph.from_output_lattice(shared, gearbox_branch)
fourbar_graph = EmbeddedPlanningGraph.from_output_lattice(shared, fourbar_branch)
```

Do not independently regenerate supposedly identical floating-point \(q\) arrays for each mechanism.

### V2-307 — Add graph diagnostics

Produce static 2R diagnostics:

- input samples in \(\mathcal U\);
- corresponding graph in \(\mathcal Q\);
- cell spacing or node-density view;
- per-axis \(q(u)\) mapping;
- side-by-side input-sampled and output-sampled graphs;
- edge trace for each parameterization.

Visualization must consume graph-owned arrays.

### V2-308 — Null-control graph invariants

Before search is involved, assert that matched mechanisms on the shared uniform-\(\mathcal Q\) lattice have:

- identical topology;
- bitwise-identical or explicitly tolerance-equal `q_nodes`;
- identical validity masks;
- identical neighbor lists;
- identical output edge distances.

## Tests

- 1D affine branch sampling;
- 2D gearbox sampling;
- 2D four-bar branch sampling;
- uniformity checks in selected domain;
- nonuniformity evidence in mapped domain for a nonlinear fixture;
- round-trip node invariants;
- edge-trace endpoint and interior consistency;
- no periodic neighbors;
- shared-\(q\) null-control graph equality;
- Version 1 golden tests.

## Expected file changes

```text
src/inequality_mechanisms/graphs/sampling.py
src/inequality_mechanisms/graphs/embedded.py
src/inequality_mechanisms/graphs/transitions.py
src/inequality_mechanisms/visualization/embedded_graphs.py
tests/graphs_v2/...
docs/notes/V2_3_GRAPH_SEMANTICS.md
```

## Non-goals

- no experiment YAML or runner;
- no query-overlay nodes;
- no collision constraints;
- no 3R experiment;
- no large graph optimization;
- no deletion of `ConstrainedInputGraph`.

## Recommended pull requests

1. **PR V2.3-A:** sampling records and uniform-input graph construction.
2. **PR V2.3-B:** uniform-output graph construction and shared lattice.
3. **PR V2.3-C:** transition traces and validity.
4. **PR V2.3-D:** diagnostics and null-control graph tests.

## Verification

```bash
pytest tests/graphs_v2
pytest tests/operating_branches tests/search tests/golden_v1
pytest
ruff check .
ruff format --check .
mypy src
```

## Sprint exit criteria

1. Both sampling modes construct reproducible \(\mathcal Q\)-state graphs.
2. Every node stores a consistent unique actuator realization.
3. All Version 2 graphs are nonperiodic.
4. Edge traces respect sampling provenance.
5. Shared uniform-\(\mathcal Q\) graph invariants pass before search.
6. Version 1 remains unchanged.

## Cursor starter prompt

```text
Implement Sprint V2.3 only. Use the generic topology/search contracts and the
certified OperatingBranch; do not reuse PeriodicGrid2D as the Version 2 graph.
Implement uniform-input and uniform-output samplers, EmbeddedPlanningGraph,
transition provenance, edge traces, and shared-Q null-control graph invariants.
Construct the shared uniform-Q lattice once and attach mechanism-specific U
realizations. Keep node and edge masks explicit but simple. Add static 2R
diagnostics and comprehensive tests. Do not build the Version 2 runner yet.
```
