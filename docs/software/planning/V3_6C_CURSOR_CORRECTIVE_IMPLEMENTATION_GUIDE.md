# Cursor Guide — V3.6C Gate A Corrective Closeout

**Repository base:** `db967ab31af8acab83d113812bab748384374234`
**Authorized implementation:** V3-640–V3-642 only
**Authorized closeout after green tests:** V3-643–V3-644
**Do not activate V3.7.**

This guide is deliberately interaction-based. Give Cursor one interaction at a
time, review the diff and test output, and commit only after the bounded change
is understood.

## Choose one execution mode

### Mode A — Cursor-led implementation

Apply only `v3_6c_gate_a_corrective_docs.patch`. Keep the code patch unapplied
as a review reference, then give Cursor Interactions 0–5 sequentially. This is
the recommended mode when the purpose is to watch and review each implementation
decision.

### Mode B — apply-ready implementation

Apply `v3_6c_gate_a_corrective_closeout.patch` (or the code and docs patches
together). In Interactions 1–3, Cursor should verify the pre-applied work package,
run the requested tests, and edit only when a concrete requirement is unmet.

Do not apply the code patch after Cursor has already implemented the same changes.
Choose one mode and keep one coherent diff.

## Interaction 0 — preflight, no edits

```text
Read these files before editing:

- .cursor/rules/project.mdc
- .cursor/rules/testing.mdc
- docs/software/VERSION_MATRIX.md
- docs/software/PROJECT_PLAN.md
- docs/software/planning/ACTIVE_SPRINT.md
- docs/software/planning/sprints/v3/SPRINT_V3_6C_PLANAR2R_FREE_SPACE_CLOSEOUT.md
- docs/software/architecture/notes/V3_6C_GATE_A_CORRECTIVE_REVIEW.md
- src/inequality_mechanisms/graphs/goal_set_query_overlay.py
- src/inequality_mechanisms/adapters/graph_search_planner.py
- src/inequality_mechanisms/planners/roadmap/prm.py
- src/inequality_mechanisms/audits/html_report.py
- tests/v3/test_v3_632_multi_goal_graph_query.py
- tests/v3/test_v3_633_roadmap_tree_goal_parity.py
- tests/v3/test_v3_6c_planar2r_closeout.py

Do not edit yet. Report:
1. current branch and HEAD;
2. whether the working tree is clean;
3. the exact two Gate A findings in your own words;
4. the minimum files you expect to touch;
5. any conflict between the patch contract and current code.

Do not propose V3.7 or adjacent cleanup.
```

Stop if HEAD is not the expected base or if unrelated work is present.

## Interaction 1 — V3-640 complete represented-goal attachment

```text
Implement or verify V3-640 only. If the implementation patch is already applied,
edit only when a requirement below is unmet.

Production GraphSearchPlanner.solve_goal_set must require every represented
candidate to attach before search starts. Preserve the lower-level overlay's
optional partial mode for explicit diagnostics, but do not use it in the V3.6C
planner path.

Requirements:
- add a structured attachment-failure record and a specific exception carrying
  requested count, attached candidate count, unique attached-goal-node count,
  failed indices, and reasons;
- collect all failed represented goals before raising, rather than stopping at
  the first failure;
- catch that specific exception in GraphSearchPlanner;
- return PlanningStatus.INVALID, search_started=false, and zero graph-work counters;
- retain goal_sample_id, goal_sample_index, goal_sample_point, ik_family, and
  candidate_generator_id when available;
- on success report requested candidate count, attached candidate count, unique
  goal-node count, and goal_set_attachment_complete=true;
- do not invoke the graph solver on an incomplete represented set.

Add or update deterministic tests in
tests/v3/test_v3_632_multi_goal_graph_query.py. Force exactly one candidate
attachment to fail and prove that candidate identity survives in the invalid
result.

Run:
pytest -q tests/v3/test_v3_632_multi_goal_graph_query.py
ruff check src/inequality_mechanisms/graphs/goal_set_query_overlay.py \
  src/inequality_mechanisms/adapters/graph_search_planner.py \
  tests/v3/test_v3_632_multi_goal_graph_query.py

Then summarize behavior, test output, and changed files. Do not start V3-641.
```

Review checkpoint:

- `require_all_goals=True` must be visible at the production call site.
- The invalid result must distinguish incomplete goal attachment from an
  unsolved complete query.
- Successful behavior, tie rules, heuristic, and selected-candidate provenance
  must remain unchanged.

## Interaction 2 — V3-641 canonical PRM query edges

```text
Implement or verify V3-641 only, starting from the reviewed V3-640 state. If the
implementation patch is already applied, edit only when a requirement is unmet.

Canonicalize native PRM query edges by undirected node pair. The start role and
goal role may refer to the same accepted direct start-goal connection, but the
physical edge must be validated, inserted, and traced once.

Requirements:
- use a per-query canonical pair cache, not a global planner cache;
- cache both accepted and rejected connector results;
- keep roadmap-construction attempted_edges/accepted_edges semantics unchanged;
- preserve role-level start and goal attachment accounting;
- add separate metrics for unique query-edge attempts, unique accepted query
  edges, and duplicate role reuses;
- emit one attach_edge event per accepted canonical physical pair;
- include the canonical edge_key in that event;
- do not disable the valid direct start-goal connector.

Add a deterministic zero-roadmap-sample fixture in
tests/v3/test_v3_633_roadmap_tree_goal_parity.py. With only the exact start and
represented goals present, prove that every direct pair is traced once, that
canonical pairs are unique, and that role attachment counts remain correct.

Run:
pytest -q tests/v3/test_v3_633_roadmap_tree_goal_parity.py
ruff check src/inequality_mechanisms/planners/roadmap/prm.py \
  tests/v3/test_v3_633_roadmap_tree_goal_parity.py

Then summarize behavior, test output, and changed files. Do not regenerate the
artifact yet.
```

Review checkpoint:

- Do not count a cached role reuse as a second motion-validity check.
- Do not insert a second adjacency entry for a reversed pair.
- Do not collapse different represented goal vertices merely because they share
  similar coordinates; deduplication is by query node ID pair.

## Interaction 3 — V3-642 report contract and focused regression

```text
Implement or verify V3-642 only. If the implementation patch is already applied,
edit only when a requirement below is unmet.

Update the compact PRM family table to display role attachment counts separately
from unique physical query-edge work. Keep native PRM clearly separated from the
shared-Q sampled-roadmap diagnostic.

Update tests so the HTML exposes lattice requested/attached/unique goal counts
and attachment completeness, plus native-PRM query metrics:
- query unique attempted;
- query unique accepted;
- duplicate pair reuses.

Run the focused closeout set:
pytest -q \
  tests/v3/test_v3_632_multi_goal_graph_query.py \
  tests/v3/test_v3_633_roadmap_tree_goal_parity.py \
  tests/v3/test_v3_6c_planar2r_closeout.py

Then run formatting and static checks on all changed Python files:
ruff check <changed python files>
ruff format --check <changed python files>
mypy src

Report every command exactly, including skips or environment limitations. Do not
claim Gate A passed unless all required commands pass or the limitation is
explicitly recorded for review.
```

## Interaction 4 — diff audit before commit

```text
Perform a no-edit audit of the complete V3-640–V3-642 diff.

Check and report:
1. no source outside the authorized files changed;
2. no task bank, mechanism geometry, seed, goal ordering, or planner tuning
   changed;
3. incomplete lattice attachment cannot reach backend.solve;
4. successful lattice metrics prove full represented-set attachment;
5. every PRM query attach_edge event has a unique canonical edge_key;
6. roadmap construction metrics retain their old meaning;
7. trace mode remains noninterfering;
8. frozen result packages are unchanged.

Show git diff --stat and a concise semantic diff by work package. Do not edit
unless a concrete violation is found; if one is found, stop and explain it.
```

## Interaction 5 — full regression and implementation commit

```text
Run the repository-required regression suite from the cleanly reviewed source
tree:

pytest
ruff check .
ruff format --check .
mypy src

Record pass/fail/skip counts and runtime. If any failure is unrelated, provide
the exact failing test and why it is unrelated; do not silently waive it.

If and only if the required suite is accepted, commit source and tests without
generated results. Suggested commit message:

Close V3.6C Gate A attachment and PRM query-edge gaps

Do not generate or commit results in this interaction. Report the clean
implementation commit SHA and verify git status is clean.
```

## Interaction 6 — V3-643 clean artifact regeneration

```text
Verify the working tree is clean and HEAD is the accepted V3-640–V3-642
implementation commit. Then regenerate only the canonical V3.6C package using
the existing versioned config and exporter.

Do not touch:
- results/v3_review/v3_6_free_space/
- results/v3_review/v3_6_free_space_v2/
- results/v3_review/v3_6b_planar2r_visual_audit/
- results/v3_review/v3_7_3r_free_space/

Generate:
MPLBACKEND=Agg PYTHONPATH=src python \
  scripts/export_v3_6c_planar2r_closeout.py \
  --config configs/v3/planar2r_closeout_v1.json

After generation, verify:
1. manifest git_revision equals the implementation HEAD;
2. all ten task pages and raw records exist;
3. every successful lattice run has goal_set_attachment_complete=true and
   attached_goal_candidate_count=requested_goal_count;
4. all PRM attach_edge canonical pairs are unique per run;
5. all local HTML links and manifest assets resolve;
6. required animations and contact sheets remain present;
7. no frozen package changed.

Show a result-directory diff summary. Do not update ACTIVE_SPRINT yet.
```

Commit the regenerated artifact separately only after the checks pass.

## Interaction 7 — V3-644 manual review and disposition

```text
Do not edit source. Prepare the final V3.6C review disposition.

Inspect near_0, near_3, and far_2 in the generated HTML, including:
- task/candidate identity;
- lattice complete-goal metrics;
- PRM unique query-edge metrics;
- RRT multi-root identity;
- continuous U/Q/X paths;
- actuator_metric_on_q scales and interpretation;
- required animations and print contact sheets.

Update the Gate B finding disposition and ACTIVE_SPRINT only after the human
review is accepted. The final ACTIVE_SPRINT state must authorize no code.
Do not activate V3.7 in the same commit.

Suggested final documentation commit message:
Close V3.6C Gate B and return to no authorization
```

## Stop conditions

Stop and ask for review if:

- current HEAD differs from the declared base before implementation;
- the incomplete-goal fixture reaches graph search;
- PRM deduplication changes the selected goal or objective cost;
- any physical task or planner setting changes;
- frozen evidence changes;
- the regenerated package records a dirty or wrong implementation revision;
- OMPL availability differs and would make the artifact incomparable without an
  explicit disposition;
- any step requires activating V3.7.
