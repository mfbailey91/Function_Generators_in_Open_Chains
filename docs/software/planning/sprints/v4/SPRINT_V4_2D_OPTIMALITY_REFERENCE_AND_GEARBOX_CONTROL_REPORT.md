# Sprint V4.2D — Optimality-Reference and Gearbox-Control Report

**Status:** active; V4-240–V4-249 authorized  
**Purpose:** derive and expose the missing optimality controls for the frozen V4.2C OMPL planner portfolio  
**Reserved work packages:** V4-240 through V4-249  
**Input evidence:** frozen V4.2B and V4.2C packages only  
**New artifact target:** `results/v4_review/v4_2d_optimality_reference_report/`  
**No rerun rule:** no OMPL planner, stochastic campaign, calibration, task bank, mechanism certificate, or V4.2B/V4.2C row may be regenerated or changed  
**Proposed architecture decision:** `ADR-032 — Planner Optimality Must Be Measured Against the Exact Represented-Goal Reference`

---

## 1. Why this follow-up is needed

V4.2C successfully demonstrated that the corrected mechanism-aware planning problem can be consumed by RRT*, BIT*, FMT, KPIECE-U/Q/X, PRM, and RRTConnect while preserving:

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X,
\]

authoritative actuator state, exact start, input-linear local motion, and actuator-travel cost.

The retained report primarily plots absolute planner cost over time. That proves the adapters can optimize, but it does not put the two scientifically important controls in the foreground:

1. **Mechanism control**
   \[
   \Delta J^*
   =
   J^*_{\text{fourbar}}
   -
   J^*_{\text{gearbox}},
   \]
   which asks whether the mechanism changes the best achievable actuator cost.

2. **Planner optimality control**
   \[
   \epsilon_{p,m}(b)
   =
   J_{p,m}(b)-J^*_m,
   \]
   which asks how quickly planner \(p\) approaches the correct optimum for mechanism \(m\).

The central interpretive question is then:

\[
\Delta\epsilon_p(b)
=
\epsilon_{p,\text{fourbar}}(b)
-
\epsilon_{p,\text{gearbox}}(b).
\]

This distinguishes:

- a mechanism that changes the optimum;
- from a mechanism that changes how difficult that optimum is to discover.

---

## 2. Critical representation finding

The follow-up must **not** simply join the V4.2C rows to the V4.2B `input_linear` cost and call that the V4.2C optimum.

The two packages use different finite goal representations.

### V4.2B planning audit

The V4.2B task pages retain a disk representation containing the center and boundary points such as:

```text
center
boundary_0deg
boundary_45deg
...
boundary_315deg
```

Its `input_linear` row minimizes over that broader represented set.

### V4.2C OMPL worker

The V4.2C worker reconstructs a `CartesianDiskGoalGenerator`, whose implementation generates IK lifts of the **disk center only**. For a normal planar-2R center this produces two candidates:

```text
disk_center::elbow_down
disk_center::elbow_up
```

V4.2C rows correspondingly retain:

```text
goal_region = cartesian_disk_center
candidate_generator_id = cartesian_disk_center_ik
goal_sample_id = disk_center
discrete_goal_state_count = 2
```

Therefore the primary reference for V4.2C must be reconstructed over the actual V4.2C center-IK set:

\[
J^*_{C,m}
=
\min_{g\in G_{C,m}}
\|u_g-u_s\|_2.
\]

The historical V4.2B reference remains useful, but only as a **goal-representation sensitivity control**:

\[
J^*_{B,m}
=
\min_{g\in G_{B,m}}
J_U(s,g),
\]

\[
\Delta J_{\text{representation},m}
=
J^*_{C,m}-J^*_{B,m}.
\]

The report must never use \(J^*_{B,m}\) as the denominator for V4.2C convergence.

---

## 3. Sprint questions

### Q1 — Mechanism effect on the optimum

For the exact V4.2C represented goal set:

\[
\Delta J_C^*
=
J^*_{C,F}-J^*_{C,G}.
\]

Does the four-bar admit lower or higher minimum actuator travel than the span-matched gearbox for the same case and physical task?

### Q2 — Planner convergence relative to the correct optimum

For RRT* and BIT* checkpoints:

\[
\epsilon_{p,m}(t)
=
J_{p,m}(t)-J^*_{C,m}.
\]

How quickly does each planner approach the direct center-goal reference?

### Q3 — Mechanism effect on discoverability

\[
\Delta\epsilon_p(t)
=
\epsilon_{p,F}(t)-\epsilon_{p,G}(t).
\]

Does the nonlinear mechanism make its own optimum easier or harder to discover than the equivalent gearbox makes its optimum?

### Q4 — First feasible versus final optimized behavior

How much of the initial planner error is removed by later optimization?

### Q5 — Goal selection versus route inefficiency

At the final result, how much of the total gap comes from:

1. selecting the wrong acceptable center IK family;
2. taking an unnecessarily long path to the selected candidate?

### Q6 — Goal-representation sensitivity

How much lower was the broader V4.2B center-plus-boundary represented optimum than the V4.2C center-only optimum?

---

## 4. Source contract

The report is a deterministic derivative of two immutable packages.

### V4.2B source

```text
results/v4_review/v4_2b_span_controlled_corrective_closeout/
files_digest = ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a
```

Required inputs:

```text
cases.json
planning_audit/data/planner_rows.jsonl.gz
planning_audit/summary.json
manifest.json
```

### V4.2C source

```text
results/v4_review/v4_2c_ompl_planner_portfolio/
files_digest = 99ec523a706632391c85e16cae505e6cd11a6f14d15682eb711515aefcf76c93
source revision = 5320d6f336ef82615a51f7826d0febd39c18f9db
```

Required inputs:

```text
stage_c/resolved_config.json
stage_c/request_matrix.json
stage_c/rows/*.json
stage_c/attempts/*.json
capability_matrix.json
manifest.json
```

The generator must verify both source packages before reading comparative data. A digest mismatch fails closed.

---

## 5. Reference construction

Create a deterministic reference builder that uses the same public physical problem components as the V4.2C worker but does not import or execute OMPL.

For every:

\[
(\text{case},\text{task},\text{mechanism}),
\]

perform the following:

1. Load the frozen V3.6D span registry and mounted span case.
2. Load the frozen common-physical task.
3. Reconstruct the same V4.2C `PlanningProblem`.
4. Generate center IK candidates using `CartesianDiskGoalGenerator`.
5. Assign a stable candidate key:
   ```text
   <goal_sample_id>::<ik_family>
   ```
6. Evaluate the existing `InputLinearMotion` and `ActuatorTravelObjective` for each candidate.
7. Retain:
   - candidate validity;
   - candidate direct cost;
   - candidate U/Q/X endpoint;
   - IK family;
   - physical task residual;
   - candidate provenance.
8. Select the minimum valid direct cost as \(J^*_{C,m}\).
9. For `already satisfied` tasks, retain \(J^*_{C,m}=0\) and classify the row separately.

Expected primary reference count:

```text
5 cases × 10 tasks × 2 mechanisms = 100 reference rows
```

A separate candidate table may contain up to two center-IK candidates per nontrivial reference row.

### Reference invariants

- The reconstructed start Q and X must equal the frozen task start.
- The reconstructed start U must match the mechanism-specific V4.2C problem.
- Candidate generator ID must be `cartesian_disk_center_ik`.
- Candidate count must match the corresponding V4.2C OMPL row metadata.
- Direct motion must be valid whenever V4.2C reports `direct_connector_available=true`.
- Direct cost must agree with Euclidean U endpoint distance under the frozen input-linear contract.
- The selected reference candidate must satisfy the physical Cartesian disk.
- Every nontrivial V4.2C final or checkpoint exact cost must satisfy:
  \[
  J_{p,m}\ge J^*_{C,m}-\tau.
  \]

A violation beyond numerical tolerance is a report-generation failure, not a clipped negative gap.

---

## 6. Metric contract

Let:

- \(J^*_{C,m}\): exact direct optimum over the actual V4.2C center-IK set;
- \(J^*_{B,m}\): historical V4.2B direct optimum over its broader represented set;
- \(J_{p,m,r}(b)\): planner cost for repetition \(r\) at budget \(b\).

### 6.1 Mechanism optimum difference

\[
\Delta J_C^*
=
J^*_{C,F}-J^*_{C,G}.
\]

Interpretation:

- negative: four-bar has the lower center-goal actuator optimum;
- positive: gearbox has the lower center-goal actuator optimum.

### 6.2 Absolute optimality gap

\[
\epsilon^{\text{abs}}_{p,m,r}(b)
=
J_{p,m,r}(b)-J^*_{C,m}.
\]

### 6.3 Relative optimality gap

For nontrivial references \(J^*_{C,m}>\tau_0\):

\[
\epsilon^{\text{rel}}_{p,m,r}(b)
=
\frac{J_{p,m,r}(b)-J^*_{C,m}}
{J^*_{C,m}}.
\]

Also retain:

\[
R_{p,m,r}(b)=\frac{J_{p,m,r}(b)}{J^*_{C,m}},
\]

\[
L_{p,m,r}(b)=\log R_{p,m,r}(b).
\]

Relative metrics are null, with reason, for zero-reference tasks.

### 6.4 Paired mechanism discoverability contrast

\[
\Delta\epsilon^{\text{rel}}_{p,r}(b)
=
\epsilon^{\text{rel}}_{p,F,r}(b)
-
\epsilon^{\text{rel}}_{p,G,r}(b).
\]

This is an index-matched descriptive contrast. It is **not** described as a common-random-number estimator because equal OMPL seeds do not prove identical sample sequences across mechanisms.

### 6.5 Time to tolerance

For RRT* and BIT*:

\[
T_{\eta}
=
\inf\left\{
t:
\epsilon^{\text{rel}}(t)\le \eta
\right\},
\]

with thresholds frozen in config, initially:

```text
1%, 5%, 10%
```

Runs that do not reach the threshold are retained as right-censored at the final checkpoint.

### 6.6 Fraction within tolerance

At checkpoint \(t\):

\[
P_{\eta}(t)
=
\frac{
\#\{\text{nontrivial runs with exact solution and }\epsilon^{rel}\le\eta\}
}{
\#\{\text{all nontrivial requested runs}\}
}.
\]

Unsolved runs count as not within tolerance. This avoids survivorship bias.

### 6.7 Final-gap decomposition

For a final selected candidate \(g_p\), reconstruct its direct cost:

\[
J^*_{C,m}(g_p).
\]

Then:

\[
\text{goal-selection regret}
=
J^*_{C,m}(g_p)-J^*_{C,m},
\]

\[
\text{path inefficiency}
=
J_{p,m}-J^*_{C,m}(g_p),
\]

\[
\text{total gap}
=
\text{goal-selection regret}
+
\text{path inefficiency}.
\]

Checkpoint-level decomposition is out of scope because V4.2C checkpoints do not retain the selected goal candidate at each checkpoint. The report must state that omission rather than infer checkpoint goal identity from the final result.

### 6.8 Goal-representation penalty

\[
\Delta J_{\text{representation},m}
=
J^*_{C,m}-J^*_{B,m}.
\]

This compares two finite representations of the same physical Cartesian disk and is not a mechanism-performance score.

---

## 7. Task-class handling

The raw V4.2C rows contain `task_class`, but the current compact report view drops it. V4.2D must preserve it.

Rows must be partitioned into at least:

```text
already_satisfied
direct_local_feasible
other_typed_status
```

Rules:

- `already_satisfied` rows remain in completeness and task-composition tables;
- they must have zero reference and zero final cost;
- they are excluded from relative-gap, cost-ratio, and time-to-tolerance plots;
- they may not silently add a large mass at zero to mechanism-difference plots;
- exact solution rate must distinguish “query already satisfied” from “planner found an exact path.”

---

## 8. Planner-family handling

### RRT* and BIT*

Use checkpoint curves:

```text
0.05, 0.10, 0.25, 0.50, 1.00 s
```

Expose:

- exact-solution rate;
- fraction within 1/5/10%;
- conditional median relative gap among exact solutions;
- first exact gap;
- final gap;
- time to tolerance;
- final gap decomposition.

### FMT

The retained audit uses a fixed sample count, not an anytime checkpoint continuation.

Expose:

- exact-solution rate at the frozen sample count;
- final absolute and relative gap;
- final goal-selection/path decomposition.

Do not place FMT sample count on the RRT*/BIT* wall-time axis.

### KPIECE-U/Q/X

KPIECE is a projection diagnostic, not an optimizing family.

Expose:

- exact-solution rate;
- final gap;
- selected reference-candidate match;
- final goal-selection/path decomposition;
- differences among U/Q/X projection arms.

Do not call a lower final cost “faster convergence.”

### PRM and RRTConnect

Retain as controls:

- final gap;
- selected goal;
- architecture/binding condition;
- PRM sequential-goal workaround status.

Do not include them on optimizer convergence curves.

---

## 9. Required figures

All figures must aggregate or facet the audit. No figure may use thousands of raw categorical bars.

### Figure 1 — Exact reference cost by mechanism

Show \(J^*_{C,F}\) and \(J^*_{C,G}\) by case and task class.

Purpose:

> Establish what “optimal” means before showing any planner.

### Figure 2 — Mechanism effect on the optimum

Plot:

\[
\Delta J_C^*=J^*_{C,F}-J^*_{C,G}.
\]

Facet by span case; distinguish near and far nontrivial tasks.

### Figure 3 — Exact-solution rate versus checkpoint

RRT* and BIT* only.

- x: checkpoint seconds;
- y: fraction with exact solution;
- mechanism as line;
- facet by planner and case or task class.

Already-satisfied rows appear in a separate task-composition annotation, not as planner successes.

### Figure 4 — Fraction within 5% of optimum versus checkpoint

Primary executive convergence plot:

\[
P_{5\%}(t).
\]

Optionally provide 1% and 10% tabs/panels.

### Figure 5 — Relative optimality gap versus checkpoint

RRT* and BIT* only.

- median relative gap among exact solutions;
- interquartile band;
- exact \(n\) printed at each checkpoint;
- horizontal zero line;
- clear note that the curve is conditional on exact solution.

### Figure 6 — First exact versus final gap

Plot first exact relative gap against final relative gap.

- diagonal means no improvement;
- points below diagonal improved;
- facet by planner and mechanism;
- no already-satisfied rows.

### Figure 7 — Final relative gap by planner family

Separate panels:

1. RRT*/BIT*/FMT;
2. KPIECE U/Q/X;
3. PRM/RRTConnect controls.

Each label must state its frozen budget semantics.

### Figure 8 — Paired mechanism discoverability contrast

Plot:

\[
\Delta\epsilon^{rel}_{p}
=
\epsilon^{rel}_{p,F}
-
\epsilon^{rel}_{p,G}.
\]

- zero line;
- planner and case grouping;
- distribution or interval summary across task/repetition;
- negative means the four-bar was closer to its own optimum.

### Figure 9 — Physical benefit versus discoverability

The central project figure:

- x:
  \[
  \Delta J_C^*
  \]
  mechanism effect on best achievable cost;
- y:
  \[
  \operatorname{median}(\Delta\epsilon^{rel}_p)
  \]
  mechanism effect on planner discoverability.

Quadrants:

| Quadrant | Meaning |
| --- | --- |
| x < 0, y < 0 | four-bar lower optimum and easier to discover |
| x < 0, y > 0 | four-bar lower optimum but harder to discover |
| x > 0, y < 0 | four-bar higher optimum but easier to discover |
| x > 0, y > 0 | four-bar higher optimum and harder to discover |

### Figure 10 — Final gap decomposition

Stack or facet:

```text
goal-selection regret
path inefficiency
```

by planner and mechanism.

This answers whether the planner chose the wrong acceptable center IK family or simply took a long route to the candidate it chose.

### Figure 11 — Reference-goal match rate

Compare final planner-selected candidate key with the direct reference candidate key.

Use:

```text
disk_center::elbow_up
disk_center::elbow_down
```

### Figure 12 — Goal-representation sensitivity

Compare:

\[
J^*_{C,m}
\quad\text{against}\quad
J^*_{B,m}.
\]

This plot must be explicitly labeled:

> center-only V4.2C representation versus broader historical V4.2B representation.

---

## 10. Report structure

The landing page should lead with four questions rather than planner names.

### Section 1 — What is the exact reference?

- actual V4.2C goal representation;
- candidate table;
- task-class counts;
- reference-cost figure.

### Section 2 — What did the mechanism change?

- \(J^*_{C,F}\) versus \(J^*_{C,G}\);
- \(\Delta J_C^*\);
- representation sensitivity.

### Section 3 — How quickly did optimizers approach it?

- exact solution rate;
- within-5% rate;
- relative gap curves;
- first-to-final improvement.

### Section 4 — Did the mechanism change discoverability?

- paired gap contrast;
- benefit-versus-discoverability quadrant plot.

### Section 5 — Why was the final solution suboptimal?

- goal-family match;
- goal-selection regret;
- path inefficiency.

### Section 6 — Fixed-budget and projection controls

- FMT;
- KPIECE-U/Q/X;
- PRM/RRTConnect;
- binding caveats.

### Section 7 — Methods, provenance, and nonclaims

- source package digests;
- grouping and censoring rules;
- candidate key semantics;
- same-seed limitation;
- no obstacle inference;
- no universal planner or mechanism ranking.

---

## 11. Target software architecture

```text
src/inequality_mechanisms/
├── analysis/
│   └── v4/
│       ├── __init__.py
│       ├── optimality_reference.py
│       ├── optimality_metrics.py
│       └── optimality_pairing.py
├── visualization/
│   └── v4/
│       └── optimality_reference_report.py
└── audits/
    ├── v4_artifact_guard.py
    └── v4_2d_artifact.py

configs/v4/
└── optimality_reference_report_v1.json

scripts/
├── generate_v4_2d_optimality_reference_report.py
├── package_v4_2d_optimality_reference_report.py
└── verify_v4_2d_artifact.py

tests/v4/
├── test_v4_2d_artifact_guard.py
├── test_v4_2d_reference_builder.py
├── test_v4_2d_optimality_metrics.py
├── test_v4_2d_pairing.py
├── test_v4_2d_report.py
└── test_v4_2d_closeout.py
```

No file under the OMPL adapters or stochastic experiment runner requires modification.

---

## 12. Proposed output package

```text
results/v4_review/v4_2d_optimality_reference_report/
├── README.md
├── index.html
├── manifest.json
├── resolved_config.json
├── source_contract.json
├── summary.json
├── data/
│   ├── v4_2c_center_reference_rows.jsonl.gz
│   ├── v4_2c_center_candidate_costs.jsonl.gz
│   ├── v4_2b_historical_reference_rows.jsonl.gz
│   ├── checkpoint_optimality_rows.jsonl.gz
│   ├── final_optimality_rows.jsonl.gz
│   ├── final_gap_decomposition.jsonl.gz
│   ├── paired_mechanism_contrasts.jsonl.gz
│   └── task_class_rows.jsonl.gz
├── figures/
│   ├── 01_reference_cost_by_mechanism.png
│   ├── 02_mechanism_optimum_delta.png
│   ├── 03_exact_solution_rate_vs_checkpoint.png
│   ├── 04_within_5pct_vs_checkpoint.png
│   ├── 05_relative_gap_vs_checkpoint.png
│   ├── 06_first_vs_final_gap.png
│   ├── 07_final_gap_by_family.png
│   ├── 08_paired_discoverability_contrast.png
│   ├── 09_benefit_vs_discoverability.png
│   ├── 10_final_gap_decomposition.png
│   ├── 11_reference_goal_match.png
│   └── 12_goal_representation_sensitivity.png
└── cases/
    └── <case_id>/
        └── index.html
```

The V4.2B and V4.2C packages remain byte-identical.

---

## 13. Work packages

## V4-240 — Sprint contract, ADR-032, and artifact guard

### Deliver

- Sprint document.
- ADR-032.
- `V4_2D_ALLOWED_PACKAGE`.
- Guard that permits writes only under the new V4.2D root.
- Source package digest locks.

### Tests

- V4.2D output succeeds.
- V4.2B and V4.2C writes fail.
- every V3 and sibling V4 package fails.
- arbitrary external paths fail.

---

## V4-241 — V4.2C center-goal reference builder

### Deliver

- Reconstruct the actual V4.2C center-IK candidate set.
- Compute candidate direct costs and selected reference.
- Serialize candidate and reference tables.
- No OMPL import or solve.

### Tests

- 100 primary reference rows.
- candidate counts agree with retained V4.2C metadata.
- direct cost equals input-linear actuator objective.
- already-satisfied rows equal zero.
- deterministic repeated generation is byte-identical.

---

## V4-242 — Historical V4.2B reference loader and representation audit

### Deliver

- Read V4.2B `planner_rows.jsonl.gz`.
- Filter authoritative `input_linear` rows.
- Build \(J^*_{B,m}\) lookup.
- Compute representation penalty against \(J^*_{C,m}\).

### Tests

- one unique row per case/task/mechanism.
- selected goal and cost match retained V4.2B task pages.
- expected source digest is enforced.
- no V4.2B file is written.

---

## V4-243 — V4.2C row extraction and task-class preservation

### Deliver

Extend the compact view to retain:

```text
task_class
goal generator ID
goal sample ID
IK family
direct_connector_available
exact/approximate status
checkpoint cost units
```

Do this in the new analysis layer rather than mutating the frozen V4.2C report.

### Tests

- all 6,200 Stage C rows are represented.
- every row joins to one primary reference.
- already-satisfied rows remain identifiable.
- failed/unsupported rows remain typed.

---

## V4-244 — Optimality metric engine

### Deliver

Compute:

```text
absolute gap
relative gap
cost ratio
log cost ratio
first exact gap
final gap
time to 1/5/10%
right-censor status
```

### Tests

- gaps cannot be negative beyond tolerance.
- relative metrics are null for zero references.
- checkpoint costs remain nonincreasing where claimed.
- final checkpoint and final result agree within tolerance.
- unsolved rows count correctly in within-tolerance fractions.

---

## V4-245 — Mechanism pairing and final-gap decomposition

### Deliver

Compute:

```text
delta_J_star_fourbar_minus_gearbox
delta_relative_gap_fourbar_minus_gearbox
reference-goal match
goal-selection regret
path inefficiency
representation penalty
```

### Tests

- both mechanisms exist for every paired condition.
- decomposition sums to total final gap.
- selected final candidate maps to one reconstructed center candidate.
- pairing is labeled index-matched, not identical-sample paired.

---

## V4-246 — Executive figures

### Deliver

All twelve figures listed in Section 9.

### Plot acceptance rules

- no raw thousands-of-bars chart;
- no line joins unrelated repetitions;
- no mixed time/sample-count x-axis;
- no already-satisfied rows in normalized-gap plots;
- every figure states grouping, denominator, and sample count;
- every figure records source row digests;
- zero/reference lines are explicit;
- cross-family effort units remain separate.

---

## V4-247 — Question-grouped HTML and case pages

### Deliver

- landing page organized by scientific question;
- per-case drill-down;
- machine-readable summary;
- provenance links back to frozen rows;
- explicit representation caveat.

### Tests

- HTML introduces no calculation absent from `summary.json`;
- all local links resolve;
- source row digests are visible;
- no prohibited universal-ranking language;
- same-seed limitation is visible.

---

## V4-248 — Package, manifest, and verifier

### Deliver

- package script;
- file inventory;
- SHA-256 digest;
- source package verification;
- figure inventory;
- row-count and join-coverage checks.

### Verifier gates

```text
V4.2B digest matches
V4.2C digest matches
100 primary reference rows
6,200 Stage C rows consumed
zero orphan Stage C rows
zero unauthorized writes
all figure links exist
all decomposition identities pass
all source packages remain unchanged
```

---

## V4-249 — Closeout and authorization reset

### Deliver

- implementation review;
- closeout note;
- V4 project plan update;
- V4 sprint index update;
- version matrix update;
- `ACTIVE_SPRINT.md` reset to no authorization.

V4.3 is not activated automatically.

---

## 14. Suggested implementation sequence

1. Land sprint/ADR/authorization only.
2. Implement artifact guard.
3. Build V4.2C center-goal reference table.
4. Verify it against retained row goal metadata.
5. Load V4.2B historical reference and expose representation shift.
6. Extract Stage C task class, final results, and checkpoints.
7. Implement optimality and censoring metrics.
8. Implement paired mechanism contrasts.
9. Implement final goal/path decomposition.
10. Generate executive figures.
11. Generate HTML and case pages.
12. Package and verify from a clean implementation revision.
13. Review interpretation.
14. Freeze package and reset authorization.

---

## 15. Exit criteria

Sprint V4.2D is complete when:

1. the exact V4.2C center-goal reference is reconstructed and digest-locked;
2. every Stage C row joins to the correct mechanism-specific reference;
3. already-satisfied tasks are separated from planner-search evidence;
4. RRT*/BIT* exact-solution and optimality-gap curves are visible;
5. time/fraction to within 1/5/10% is reported with censoring;
6. the gearbox/four-bar optimum difference is separated from planner error;
7. paired discoverability contrast is reported;
8. final gap is decomposed into goal-selection regret and path inefficiency;
9. V4.2B/V4.2C goal-representation sensitivity is visible;
10. all source packages remain byte-identical;
11. the new artifact verifies from a clean revision;
12. no planner or mechanism superiority claim is made.

---

## 16. Allowed conclusion

V4.2D may support a statement of the form:

> Under the frozen V4.2C center-goal representation, the span-matched gearbox and four-bar possess different exact actuator-travel references, and planner families approach those mechanism-specific references at different finite-budget rates.

It may further distinguish cases where the four-bar:

- has a lower optimum and is easier to optimize;
- has a lower optimum but is harder to optimize;
- has a higher optimum but is easier to optimize;
- has a higher optimum and is harder to optimize.

It may not claim universal mechanism or planner superiority, obstacle-routing performance, common-random-number inference, or continuous Cartesian-goal-region optimality.

---

## 17. Cursor-oriented first implementation prompt

> Implement only Sprint V4.2D work packages V4-240 through V4-243. Do not run OMPL and do not modify any frozen V4.2B or V4.2C artifact. Add ADR-032 and the V4.2D artifact guard, then build a deterministic reference table for the exact V4.2C goal representation by reconstructing each frozen case/task/mechanism, generating the disk-center planar-2R IK candidates with `CartesianDiskGoalGenerator`, and evaluating the existing input-linear actuator-travel objective. Preserve `task_class`, candidate generator ID, goal sample ID, and IK family. Verify source package digests, expect 100 primary reference rows, and fail closed if a retained V4.2C row’s goal metadata does not match the reconstructed reference contract. Write only synthetic test artifacts until the report implementation is reviewed.
