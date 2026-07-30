# V2.3 Graph Semantics Contract

**Status:** Accepted
**Scope:** Version 2 embedded planning graphs only. Does not change Version 1
(`ConstrainedInputGraph`, `PeriodicGrid2D`, `MonotonicOutputGraph`) semantics.
**Related:** ADR-001, ADR-011, ADR-014, ADR-015, ADR-016

## Purpose

Describes the current, expected behavior of `EmbeddedPlanningGraph`,
`UniformOutputLattice`, `SamplingSpecification`, and `EdgeTraceV2`
(`src/inequality_mechanisms/graphs/embedded.py`,
`graphs/sampling.py`, `graphs/transitions.py`) built in Sprint V2.3. This is a
behavior contract, not a decision record; see the referenced ADRs for *why*.

## Node identity

Every `EmbeddedPlanningGraph` node has a flat integer ID in
`[0, node_count)`, owned by a `TensorGridTopology`. For that node:

- `q_nodes[node_id]` is the planning-state identity (ADR-014), always in the
  branch's certified output chart;
- `u_nodes[node_id]` is the unique attached actuator realization
  (`branch.inverse(q)` or the sampled `u` that produced `q` via
  `branch.forward`), always in the branch's certified input box;
- `valid_nodes[node_id]` records whether that pair is certified-branch valid.

A plain `Q` node is never built for a noninjective or uncertified map
(ADR-014's prohibition). Every `EmbeddedPlanningGraph` is constructed from a
certified `OperatingBranch`; there is no code path that builds one from a
bare `Mechanism`.

## Topology

`EmbeddedPlanningGraph.topology` is always a `TensorGridTopology` with
`wrap=(False, ...)` on every axis (nonperiodic, ADR-014/ADR-015). No Version 2
factory in this module ever wraps an axis or constructs a `PeriodicGrid2D`.
Node adjacency depends only on topology; `neighbors(node_id)` filters
topology-order neighbors by `valid_nodes` and returns node IDs only (no
coordinates), satisfying
`inequality_mechanisms.search.protocol.SearchGraph`.

## Sampling domains and provenance

`SamplingDomain.INPUT` and `SamplingDomain.OUTPUT` record *how* lattice nodes
were placed; both modes still use `Q` as planning identity once the branch is
certified (ADR-015). `SamplingSpecification` records the concrete axis
bounds, shape, and endpoint policy (`np.linspace(..., endpoint=True)` in both
samplers) used to build a lattice.

### Uniform-input sampling (`from_uniform_input`)

1. `u` axis samples: `np.linspace(u_lower, u_upper, n, endpoint=True)` from
   `branch.certificate.input_lower` / `input_upper`.
2. Every node's `q = branch.forward(u)`.
3. `sampling_domain = INPUT`, `transition_parameterization = INPUT_LINEAR`.
4. Every sampled node is valid: the certified box assembles and forward-maps
   everywhere on it by construction.
5. `output_axis_spacing(axis)` reports per-axis statistics (min, max, mean,
   std, max/min ratio) of the mapped `q` spacing along that lattice axis.

### Uniform-output sampling (`from_uniform_output`)

1. `q` axis samples: `np.linspace(q_lower, q_upper, n, endpoint=True)` from
   `branch.certificate.output_lower` / `output_upper`.
2. Every node's `u = branch.inverse(q)`.
3. `sampling_domain = OUTPUT`, `transition_parameterization = OUTPUT_LINEAR`.
4. A node is marked invalid only if `branch.inverse` raises
   `BranchInverseError` at that sample; this should not happen inside the
   certified output box, but the mask stays explicit rather than assumed.
5. `actuator_axis_spacing(axis)` reports the mirrored per-axis statistics for
   mapped `u` spacing.

### Shared uniform-`Q` null control (`UniformOutputLattice` / `from_output_lattice`)

`UniformOutputLattice.from_output_space(output_space, shape)` builds the `q`
sample array and topology **once**. `EmbeddedPlanningGraph.from_output_lattice(shared,
branch)` reuses `shared.topology` and `shared.q_nodes` verbatim for every
attached mechanism and only computes a mechanism-specific `u_nodes` /
`valid_nodes` pair. No factory in this module calls `np.linspace` a second
time to reproduce a "same" `q` array; graphs sharing one `UniformOutputLattice`
are therefore guaranteed identical topology and bitwise-identical `q_nodes`,
not merely tolerance-equal ones.

## Edge parameterization and traces

`transition_parameterization` decides how `edge_trace(a, b, n_samples)`
interpolates between two node endpoints (ADR-015):

| Parameterization | Interpolates | Recovers | Round-trip residual reported |
| --- | --- | --- | --- |
| `INPUT_LINEAR` | `u(s) = u_a + s (u_b - u_a)` | `q(s) = branch.forward(u(s))` | `\|\|branch.inverse(q(s)) - u(s)\|\|_inf` |
| `OUTPUT_LINEAR` | `q(s) = q_a + s (q_b - q_a)` | `u(s) = branch.inverse(q(s))` | `\|\|branch.forward(u(s)) - q(s)\|\|_inf` |

`EdgeTraceV2` never wraps: both endpoints are themselves points in the
certified branch's axis-aligned box, so linear interpolation stays inside the
box for every interior sample. `branch_valid[k]` reflects only the primary
mapping (interpolated coordinate to its paired coordinate); the round-trip
residual is a secondary, best-effort self-consistency check that may itself
report `nan` (without invalidating the sample) if a confirmatory solve hits
a rare numerical near-miss, e.g. a monotone-table bracket right at a table
breakpoint. A sample is marked invalid (`branch_valid[k] = False`, `q[k]` /
`u[k]` = `nan`) only if the branch raises on the primary mapping itself;
`first_invalid_index` records the first such sample. `EdgeTraceV2` is
independent of the Version 1
`graphs.edge_trace.build_edge_trace` (which remains periodic-aware and
`U`-identity based) and is not used by any Version 1 code path.

## What this contract does not cover

- Experiment configuration, the Version 2 runner, and query overlays are out
  of scope for Sprint V2.3 (see the sprint's non-goals) and are not built by
  this module.
- Search cost functions and heuristics over `EmbeddedPlanningGraph` are not
  defined here; only the `SearchGraph`-shaped structural contract
  (`node_count`, `node_is_valid`, `neighbors`) plus the coordinate/trace
  accessors excluded from that protocol (`q_state`, `u_state`, `edge_trace`).
- `ConstrainedInputGraph`, `PeriodicGrid2D`, and `MonotonicOutputGraph` are
  unchanged Version 1 objects; this contract does not alter or supersede
  their behavior.
