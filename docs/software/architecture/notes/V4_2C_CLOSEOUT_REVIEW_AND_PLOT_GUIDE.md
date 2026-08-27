# Sprint V4.2C Closeout Review and Plot Interpretation Guide

**Project:** Function Generators in Open Chains  
**Sprint:** V4.2C — OMPL Planner-Geometry Portfolio and Projection Diagnostics  
**Disposition:** **CLOSED**  
**Review conclusion:** No P0 experiment-correctness blocker was found. The remaining problems are report-design and interpretation problems, suitable for a frozen-data presentation follow-up rather than reopening the sprint or rerunning planners.

---

## 1. What this sprint was actually for

V4.2C did **not** ask whether a four-bar is universally better than a gearbox, or which OMPL planner is universally best.

It asked a narrower robustness question:

> If the physical planning problem is frozen, do the mechanism-dependent effects survive when the planner's internal search geometry changes?

The frozen physical problem was:

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X
\]

with:

- authoritative planner state in actuator coordinates \(\mathcal U\);
- the same exact physical start in mounted \(\mathcal Q\);
- mechanism-specific inverse lifting into \(\mathcal U\);
- the same finite represented Cartesian goal set;
- input-linear continuous local motion;
- Euclidean actuator travel as the optimization objective;
- no obstacles.

Only the **planner family or exploration projection** was changed.

The portfolio was chosen to exercise several different internal geometries:

| Planner family | Why it was included |
|---|---|
| RRT* | Incremental optimizing tree, nearest-neighbor selection, parent choice, and rewiring |
| BIT* | Informed batch search over an implicit sampled graph |
| FMT | Fixed-sample cost wavefront, analogous to a sampled graph search |
| KPIECE-U | Projection-guided exploration viewed in normalized actuator space |
| KPIECE-Q | Same physical U-state, but exploration cells formed in mounted joint space |
| KPIECE-X | Same physical U-state, but exploration cells formed in Cartesian space |
| PRM | Roadmap adapter and goal-attachment architecture control |
| RRTConnect | First-feasible tree/control |
| Direct/Dijkstra/A* references | Mathematical and deterministic references inherited from the corrected planning contract |

This is therefore a **planner-semantics and robustness sprint**, not a final performance campaign.

---

## 2. What happened

### 2.1 The implementation and retained campaign completed cleanly

The retained package contains:

- Stage A smoke: 32 rows;
- Stage B calibration: 768 rows;
- Stage C audit: 6,200 worker rows;
- all Stage C rows completed without retained failure rows;
- guarded, digest-verified artifacts;
- an unchanged V4.2B predecessor package;
- explicit capability records for missing or unsupported OMPL binding features.

This is the primary closeout result:

> The same mechanism-aware planning problem was successfully consumed by a substantially broader OMPL planner portfolio without surrendering authoritative U-state, exact-start, finite-goal, local-motion, or actuator-cost semantics.

### 2.2 Free space was intentionally a weak routing problem

The certified actuator domain is a bounded box. There are no obstacles. When a straight input-linear connection to a represented goal is valid, that connection is already the Euclidean actuator-travel reference.

Consequently:

- optimizing planners mostly have to recover or approach a known direct reference;
- feasibility planners may return longer finite-time paths without violating their contract;
- PRM may connect directly and reveal little independent structure;
- planner differences are principally transient convergence, exploration, or terminal-goal-selection effects;
- this sprint cannot demonstrate obstacle-routing superiority.

### 2.3 Some near tasks require no planning at all

The retained rows include tasks where the exact start already lies inside the Cartesian goal disk. These rows correctly report:

- `task_class = already satisfied`;
- objective cost \(0\);
- zero U/Q path length;
- no OMPL solution trajectory.

These are valid task-bank controls, but they are not planner-search evidence. They should be separated from nontrivial planning rows in figures. Pooling them into paired-cost graphics introduces many zero differences and makes the figures look flatter or more mysterious than the meaningful search cases.

### 2.4 The sprint deliberately stopped before inference

The retained package is descriptive. It does not compute a universal mechanism effect or planner ranking. It supplies the common-condition records needed for a later, properly specified statistical analysis.

The defensible scientific statement is:

> Planner-internal geometry can now be varied while the physical mechanism-aware planning contract remains fixed and auditable.

The sprint does **not** yet support:

> The four-bar universally improves planning across OMPL.

---

## 3. Implementation review

## 3.1 Passed boundaries

### Authoritative state and objective

OMPL states remain bounded actuator coordinates \(u\). The objective remains Euclidean actuator travel. The mechanism is not silently converted back to ordinary Q-space planning.

### Exact start and finite goal set

The exact start and represented goal candidates are constructed from the shared physical task. Approximate paths are not promoted to exact success.

### Continuous motion validation

Candidate OMPL motions are interpreted through the project-owned input-linear local-motion contract rather than endpoint-only validity.

### Planner-geometry provenance

Each result records the planner role, state coordinates, sampling measure, nearest-neighbor metric, optimization objective, projection, normalization, goal representation, and local-motion model.

### KPIECE projection isolation

KPIECE-U/Q/X preserve U as physical state and alter only the exploration projection. The Q projection uses mounted output coordinates. The X normalization is built deterministically from a shared mounted-Q domain.

### Process isolation and failure typing

Stochastic rows execute in isolated processes. Worker completion, planner solution, already-satisfied tasks, crashes, timeouts, unsupported optional features, and unavailable binding metrics remain distinct states.

### Artifact lineage

The V4.2C writer is guarded to the new package root. V4.2B is rechecked by digest. Stage matrices, row files, reports, manifests, and checksums are retained.

---

## 3.2 Known limitations that are correctly recorded

### Seeds are not common random samples

Using the same OMPL seed across a mechanism pair does not prove that both planners consumed the identical sample sequence. The binding did not expose a safe frozen sampler allocator.

### PRM is not a true multi-goal query in this binding

The installed nanobind PRM hangs with multiple `GoalStates`, so the adapter retains a labeled sequential single-goal envelope. This remains an architecture control, not primary multi-goal evidence.

### KPIECE cell occupancy is unavailable

The OMPL 2.0.1 binding does not expose the desired occupancy counters. The data are retained as typed nulls with `kpiece_cell_stats_not_exposed_by_binding`, not fabricated zeros.

### Family work units are not interchangeable

Tree vertices, roadmap edges, FMT samples, projection cells, validity checks, and seconds cannot be pooled into one generic “effort” score.

### Environment split is provenance, not a planner result

Evidence generation used CPython 3.13 with the available OMPL wheel; the main project environment is CPython 3.14. This is recorded and does not support a performance conclusion.

---

## 4. What each plot is trying to show

| Plot | Intended question | How to read it | Current limitation |
|---|---|---|---|
| `optimizer_cost_vs_checkpoint.png` | Does additional planning time lower the best actuator-travel cost for RRT*/BIT*? | Downward movement means later solutions improve; a flat line means no later improvement. Compare only within the same case/task/mechanism. | It overlays too many case-task-mechanism curves. The legend omits the case ID even though the data are grouped by case, producing duplicate-looking labels. |
| `first_vs_final_cost.png` | How much did an optimizer improve after its first exact solution? | Points on \(y=x\) did not improve. Points below the diagonal improved. | All planners, cases, tasks, and mechanisms are pooled without faceting, so it hides where improvement occurred. |
| `planner_data_growth.png` | How large was the retained planner search structure? | Larger vertex counts mean a larger final recorded tree/graph. | The current x-axis mixes first-solution time, final checkpoint, and repetition index, then connects unrelated runs. This is **not actual within-run growth** and should be renamed. |
| `selected_goal_ids.png` | Which candidate in the frozen finite Cartesian goal representation was selected? | Different IDs mean planners/mechanisms settled on different acceptable terminal states. | Counts are pooled across case, task, planner, mechanism, and repetition. It is a provenance diagnostic, not a quality score. |
| `kpiece_projection_occupancy.png` | Did U/Q/X projections partition KPIECE exploration differently? | A real occupancy heatmap would show which projection cells were visited. | The binding does not expose occupancy; the panels are effectively capability-gap placeholders. KPIECE should instead be summarized with available metrics. |
| `paired_mechanism_delta.png` | For the same planner condition, was final U-cost lower for the four-bar or gearbox? | \(\Delta J=J_\text{four-bar}-J_\text{gearbox}\). Negative favors the four-bar for that run; positive favors the gearbox; zero is equal. | It renders one bar per raw pair, yielding thousands of bars with labels that omit case and repetition. The plot is not interpretable at production scale. |
| `synchronized_uqx_path.png` | Is one returned trajectory represented consistently in U, Q, and X? | The three panels are projections of one physical plan. | It selects only the first available trajectory. It is a coordinate-consistency example, not a paired mechanism comparison. |

---

## 5. Why the plots feel disconnected

The report is trying to satisfy several different audiences at once:

1. artifact provenance;
2. adapter correctness;
3. planner-family diagnostics;
4. convergence behavior;
5. mechanism-paired comparison;
6. binding capability gaps.

Those questions should not be combined into a single visual hierarchy.

The current plots also retain raw audit granularity. That is good for traceability but poor for reading. The most serious presentation problems are:

- too many optimizer curves;
- paired differences rendered as thousands of individual bars;
- no separation of `already satisfied` tasks;
- a “growth” plot that is not a time history;
- pooled selected-goal counts;
- an occupancy figure with unavailable occupancy data;
- only one arbitrary U/Q/X trajectory example;
- plot labels that omit important grouping fields.

These are report defects, not evidence that the experiment failed.

---

## 6. Recommended report-only follow-up

Create a bounded **V4.2C-R Frozen-Data Report Clarification** task. It should not rerun OMPL, modify frozen rows, change the estimand, or introduce inference.

### Replacement executive figures

1. **Optimizer convergence**
   - one panel per planner;
   - facet by span case;
   - mechanism as line grouping;
   - aggregate repetitions within each task class;
   - separate nontrivial near and far tasks;
   - include direct-reference gap.

2. **First-to-final improvement**
   - plot \((J_\text{first}-J_\text{final})/J_\text{first}\);
   - facet by planner and mechanism;
   - exclude or separately display already-satisfied rows.

3. **Paired mechanism difference**
   - show descriptive distributions of
     \[
     \Delta J=J_\text{four-bar}-J_\text{gearbox}
     \]
     by planner and case;
   - include a zero reference line;
   - keep individual rows available through drill-down, not as thousands of x-axis bars.

4. **Goal-selection behavior**
   - report paired goal-ID agreement/switch rate by planner, case, and task;
   - distinguish mechanism-induced terminal selection from stochastic planner variation.

5. **KPIECE projection diagnostic**
   - replace unavailable occupancy heatmaps with available success, first-solution time, final U-cost, final PlannerData size, and selected-goal summaries;
   - retain the explicit note that cell occupancy is unavailable from the binding.

6. **Paired U/Q/X example**
   - deliberately choose one nontrivial case/task;
   - show gearbox and four-bar side by side;
   - annotate start, selected goal, direct reference, and U/Q/X path lengths.

### Naming correction

Rename:

```text
planner_data_growth.png
```

to something like:

```text
final_planner_data_size_vs_solution_time.png
```

unless checkpoint-resolved vertex histories are actually retained.

### Acceptance criteria

- no executive figure has thousands of categorical x-axis labels;
- every curve label identifies planner, case, task class, and mechanism or is clearly faceted;
- already-satisfied rows are separated;
- unavailable KPIECE statistics are not shown as empty scientific evidence;
- paired deltas are summarized at an interpretable grouping level;
- one page explains the result before the raw audit tables;
- all figures remain regenerable exclusively from the frozen V4.2C package.

---

## 7. Final closeout decision

\[
\boxed{\text{Sprint V4.2C is closed.}}
\]

The sprint successfully established the cross-planner mechanism-aware OMPL contract and retained a complete descriptive audit. No implementation defect found in this review requires reopening the experiment.

The remaining work is presentation debt:

\[
\boxed{
\text{freeze data}
\;\rightarrow\;
\text{clarify report}
\;\rightarrow\;
\text{do not rerun or reinterpret the sprint}
}
\]

A future inferential sprint may use this package to ask whether paired mechanism effects persist across planner families, but it must define the estimand, treatment of already-satisfied tasks, stochastic pairing assumptions, and planner-family-specific uncertainty before making comparative claims.
