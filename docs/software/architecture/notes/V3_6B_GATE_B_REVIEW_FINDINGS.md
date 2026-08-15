# V3.6B Gate B review findings

**Status:** review complete — V3.6C closeout accepted; residual V3.7 not activated
**Sprint reviewed:** V3.6B (V3-620–V3-629)
**Artifact reviewed:** `results/v3_review/v3_6b_planar2r_visual_audit/`
**Follow-up:** [Sprint V3.6C](../../planning/sprints/v3/SPRINT_V3_6C_PLANAR2R_FREE_SPACE_CLOSEOUT.md) closeout accepted. Architecture-final V3.7 remains blocked until ACTIVE_SPRINT separately authorizes residual reconciliation.

## Gate B §8 findings

### 1. Shared Q lattice and planner geometry

**Finding: pass with planner-family qualification.** The lattice pair shares
identical Q nodes and adjacency, and the exact start plus represented Cartesian
goal candidates are pair invariant. Native PRM and RRTConnect do not consume
that shared graph: they sample and connect mechanism-specific physical states in
U, as their planner-family contract requires. They therefore cannot be read as
an isolation of Dijkstra/A* over one fixed sampled graph.

**Closeout consequence:** keep native PRM as a roadmap-family architecture
control and add a separately named frozen shared-Q sampled-roadmap diagnostic
when the scientific question is the mechanism-specific graph metric alone.

### 2. U embeddings and actuator cost

**Finding: partial pass.** The shared-Q lattice U embeddings and \(w_U\) fields
make the four-bar/gearbox actuator-cost difference visible. The native roadmap
and tree report, however, shows construction and growth only in U and omits the
synchronized Q and X projections required to inspect the complete physical
chain.

**Closeout consequence:** render the same PRM/RRT states and physical edges in
U, Q, and X. U remains the authoritative state view; Q and X are projections and
must not invent connectivity at projected crossings.

### 3. \(w_U\), \(w_Q\), \(w_X\), and trajectory geometry

**Finding: partial pass.** Shared-Q lattice edge fields use the declared
output-linear connector. \(w_U\) is integrated from actuator travel, \(w_Q\) is
exact for Q-linear edges, and \(w_X\) is sampled through FK. Cross-planner path
reporting is not yet uniform: direct planners calculate connector-sampled
lengths while roadmap/tree/lattice summaries can fall back to waypoint chords.
The plotted path can therefore differ from the continuous motion used for cost.

**Closeout consequence:** reconstruct every planner trajectory as its ordered
sequence of declared local motions and use the same samples for cost diagnostics,
U/Q/X lengths, and plots.

### 4. A* and the represented goal set

**Finding: closeout blocker.** Dijkstra/A* cost parity holds for each exact
candidate query, but the audit implements a goal set by running one complete
search per candidate and retaining only the winning candidate's expansion
trace. The reported expansion count is therefore not the total work of the
implemented query and is not the expansion count of one true multi-goal search.
The per-candidate input-Euclidean heuristic is admissible for that exact goal,
but the audit does not yet demonstrate one heuristic lower-bounding the complete
represented goal set.

**Closeout consequence:** attach all represented goals to one query graph and
terminate when any goal is optimally settled. For A*, use
\(h(n)=\min_{g\in G_{\mathrm{rep}}}\|u_n-u_g\|_2\) or another documented lower
bound to the entire set. Report total query expansions and the selected goal.

### 5. Exact starts and frozen goal candidates

**Finding: closeout blocker.** Exact starts are preserved. PRM attaches all
selected goal states. RRTConnect currently chooses only the first generated goal
as its goal-tree root, so it does not solve the same represented goal-set query
as the direct, lattice, and PRM planners.

**Closeout consequence:** initialize a multi-root goal tree from every frozen
candidate, retaining candidate identity on each root and on the selected result.

### 6. Selected-goal attribution

**Finding: closeout blocker.** The finite generator creates goal-sample and IK
provenance, but common sampling helpers reduce candidates to bare
`PhysicalState` objects. Lattice rows recover a goal ID through audit-specific
logic; direct, PRM, and RRTConnect rows commonly lose it. Selected-goal changes
therefore cannot be attributed cleanly to mechanism-aware cost versus planner
suboptimality.

**Closeout consequence:** preserve `StateCandidate` provenance through planner
selection, or copy a typed goal-candidate record into result provenance. Every
successful goal-region result must expose sample ID, represented point, IK
family, and representation index when defined.

### 7. U→Q→X auditability

**Finding: partial pass / closeout blocker.** The architecture page and shared-Q
lattice sections expose source ownership and the main transformations. Native
PRM/RRT final traces and animations omit physical edges in Q and X, and PRM
accepted-edge endpoint coordinates are not currently retained in the trace.
Family-specific planner metrics exist in raw JSON but are not readable in the
trial HTML.

**Closeout consequence:** retain enough trace data to reconstruct each accepted
physical edge, render it in all three spaces, and add compact graph/roadmap/tree
metric tables to each trial page.

### 8. Dimensional seams after V3.6A

**Finding: pass with an intentional audit-only exception.** Shared kinematics,
input-domain, sampling, and trajectory-metric ownership is dimension-generalized.
The V3.6B resolver and visualization helpers remain explicitly planar-2R audit
code, which is appropriate so long as they do not become shared planner
dependencies.

## Additional cross-cutting findings

1. **Physical goal residuals are inconsistent.** Structured goal residuals can
   become `None`, while the lattice audit reports exact-Q attachment residual.
   The closeout report must distinguish physical task residual from
   representation/attachment residual.
2. **`cond(M_Q)` is underspecified.** The implemented field is the
   actuator-travel metric expressed on Q,
   \(M_Q^{(U)}=J_{g^{-1}}^T J_{g^{-1}}\). Its condition number measures squared
   directional actuator-cost anisotropy, not Cartesian dexterity or total cost.
   Paired plots need one shared logarithmic scale plus \(\sqrt{\kappa}\),
   eigenvalue/scale statistics, and sparse metric ellipses.
3. **PRM's free-space role is secondary.** In the present convex, obstacle-free
   domain, native PRM commonly attaches a direct start-goal edge and reproduces
   the input-linear result. It remains useful as an adapter/roadmap control but
   is not primary evidence of mechanism-shaped graph search.
4. **Frozen artifacts remain provenance.** Corrections must write a new V3.6C
   package rather than overwrite V3.6 or V3.6B outputs.

## V3.6C closeout disposition

Inspected accepted package [`results/v3_review/v3_6c_planar2r_closeout/`](../../../../results/v3_review/v3_6c_planar2r_closeout/) (implementation `ff9facd`, artifact `8f4781e`). Focused HTML/raw-record review: `near_0`, `near_3`, `far_2`.

| Finding | Closeout | Notes |
| --- | --- | --- |
| 1 Shared-Q vs native roadmap | corrected as designed | Native PRM remains a roadmap-family control; shared-Q sampled roadmap is a separately labeled diagnostic. |
| 2 Native U-only traces | corrected | PRM/RRT final traces and required growth contact sheets exist in U, Q, and X. |
| 3 Continuous trajectory vs chords | corrected | Path lengths match rebuilt local-motion evaluation in raw records. |
| 4 Multi-goal lattice / A* | corrected | One query attaches all nine represented candidates (`goal_set_attachment_complete=true`); Dijkstra/A* costs agree; A* expansions are total query work and smaller than Dijkstra. |
| 5 RRT first-goal-only | corrected | `goal_root_count=9` on both mechanisms; selected roots are not the first candidate (`near_0`/`near_3`: `boundary_135deg` index 4; `far_2`: `boundary_0deg` index 1). |
| 6 Lost selected-goal provenance | corrected | Direct, lattice, PRM, and RRT rows expose `selected_goal_sample_id`. |
| 7 Unreadable family metrics / missing Q/X edges | corrected | Trial HTML includes lattice attachment completeness and unique PRM query-edge metrics; traces retain canonical `edge_key`. |
| 8 Dimensional seams | unchanged pass | Planar-2R audit helpers remain audit-owned. |
| Cross-cut residuals | corrected | Physical vs attachment residuals remain separately named. |
| Cross-cut `actuator_metric_on_q` | corrected | Named metric and shared-scale panels present on trial pages. |
| Cross-cut PRM free-space role | interpretive, not a blocker | Native PRM costs match input-linear on the three inspected tasks (direct query edge valid). Unique query edges plus role reuses are reported. |
| Cross-cut freeze | corrected | Frozen V3.6 / V3.6B / provisional V3.7 packages were not rewritten. |

OMPL bindings were unavailable (`ompl_available=false`), matching the prior V3-639 candidate. Skipped OMPL rows are an explicit adapter-control gap, not a change of task or planner settings.

## Disposition

- [x] Gate B review complete
- [x] Discrepancies entered as explicit V3.6C blockers
- [x] V3.6C corrections and tests complete
- [x] V3.6C report reviewed and accepted
- [ ] ACTIVE_SPRINT may separately activate residual V3.7
