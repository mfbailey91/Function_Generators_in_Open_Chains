# V3.6C Gate A Corrective Review

**Disposition:** accepted (Gate A and Gate B)
**Reviewed main:** `db967ab31af8acab83d113812bab748384374234`
**Original review-candidate implementation:** `e32394978e4283015444ad8b6bcad090a6b8140f`
**Original review-candidate artifact:** `7d97666faa2245a33b39f16df6544bcef2eaaa18`
**Accepted Gate A implementation:** `ff9facdd94925916cb899700223d89dafae02918`
**Accepted V3-643 artifact:** `8f4781eca6c85c45629f0771f1fb07bd8bd3bc65`
**Corrective work packages:** V3-640–V3-644 (closed)

## Review conclusion (original Gate A request)

V3-631 through V3-639 establish the intended common planner, goal, trajectory,
trace, metric, and report architecture. The generated V3.6C package was a valid
review candidate, but Gate A remained open until the two bounded implementation
details below were corrected. Those corrections are now landed and regenerated;
see **Accepted closeout record** at the end of this note.

## Finding A — represented-goal attachment is not fail-closed

`GoalSetQueryOverlay` defaults to requiring every represented goal, but the
production `GraphSearchPlanner.solve_goal_set()` call overrides that contract
with `require_all_goals=False`. A lattice query may therefore discard one or
more unattachable candidates and solve a surviving subset.

The reviewed ten-task artifact attached the declared candidates successfully,
so this is a contract leak rather than evidence that the committed task outcomes
are numerically wrong. It must still be corrected before closeout because a
planner must not silently consume a different represented goal set.

### Required behavior

- Attempt every represented candidate in caller order.
- If any candidate cannot be attached, do not start graph search.
- Return `PlanningStatus.INVALID` with
  `query_failure=incomplete_represented_goal_set_attachment`.
- Preserve the failed candidate index and available provenance fields.
- Report requested count, attached candidate count, unique goal-node count, and
  an explicit complete/incomplete flag.
- Keep partial overlays available only as an explicit lower-level diagnostic;
  production V3.6C lattice planning must require completeness.

## Finding B — native PRM duplicates direct query edges

The native PRM query first attaches the start against samples and goals, then
attaches each goal against samples and the start. A valid direct start-goal pair
is therefore encountered in both orientations and currently inserted and traced
twice.

Equivalent duplicate edges do not change the shortest path under strict
relaxation, but they inflate motion checks and can distort query work and trace
interpretation.

### Required behavior

- Canonicalize every query edge as the undirected pair
  `(min(node_a,node_b), max(node_a,node_b))`.
- Validate each physical query pair at most once.
- Insert and trace each accepted physical pair at most once.
- Allow start-role and goal-role attachment accounting to reuse the same
  accepted physical edge without adding it again.
- Expose unique query-edge attempts, unique accepted query edges, and duplicate
  role reuses separately from roadmap-construction edges.

## Evidence and artifact rule

The current `results/v3_review/v3_6c_planar2r_closeout/` package is a Gate A
review candidate, not frozen accepted evidence. The corrective branch may
replace that canonical directory exactly once after the implementation commit is
clean. Git history preserves the previous candidate. Frozen V3.6, V3.6B, and
provisional V3.7 packages remain untouched.

## Non-goals

- No new tasks, goals, mechanisms, seeds, planner families, or tuning.
- No change to the physical Cartesian goal predicate or represented candidate
  ordering.
- No obstacle, MoveIt, 6R, population, or inference work.
- No redesign of RRTConnect, continuous trajectory evaluation, trace
  reconstruction, actuator metrics, or the shared-Q diagnostic.
- No automatic activation of V3.7.

## Gate A acceptance

Gate A may pass only when:

1. a deterministic test forces one represented lattice candidate to fail
   attachment and verifies that no search begins;
2. the failure record retains candidate identity;
3. successful lattice rows report complete attachment of the full declared set;
4. a zero-sample PRM fixture proves direct start-goal query edges are inserted
   and traced once per canonical pair;
5. PRM role attachment counts remain readable while unique physical query-edge
   work is reported separately;
6. focused V3-632, V3-633, and V3.6C report tests pass;
7. the full required regression suite passes from a clean implementation tree.

## Gate B acceptance

After Gate A passes:

1. regenerate the complete V3.6C package from the clean corrective
   implementation revision;
2. verify the manifest records that implementation SHA;
3. confirm every successful lattice run reports complete represented-goal
   attachment;
4. confirm PRM query trace pairs are unique in all ten tasks;
5. inspect `near_0`, `near_3`, and `far_2`, including required animations and
   print fallbacks;
6. record test commands and results;
7. update the V3.6B finding disposition and return `ACTIVE_SPRINT` to no
   authorization.

Residual V3.7 activation remains a separate planning change.

## Accepted closeout record

Gate A passed on the corrective branch `v3_6c-gate-a-corrective-closeout`:

1. Fail-closed incomplete lattice attachment is covered by `tests/v3/test_v3_632_multi_goal_graph_query.py`.
2. Canonical undirected PRM query edges are covered by `tests/v3/test_v3_633_roadmap_tree_goal_parity.py`.
3. Closeout HTML metric columns are covered by `tests/v3/test_v3_6c_planar2r_closeout.py`.
4. Full suite from implementation `ff9facd`: `PYTHONPATH="src:." .venv/bin/pytest` → **1528 passed, 26 skipped in 711.63s**. Repo-wide `ruff`/`mypy` remain dirty (pre-existing E501 and typing plus untracked Finder copies); Gate A tests were not waived.
5. V3-643 regenerated only `results/v3_review/v3_6c_planar2r_closeout/` from `ff9facd`; manifest `git_revision` matches; all ten successful lattice runs report complete 9/9 attachment; native PRM `attach_edge` keys are unique; required lattice and growth animations/contact sheets are present; frozen `v3_6_*` / `v3_6b_*` / `v3_7_*` checksums unchanged.

Gate B inspected `near_0`, `near_3`, and `far_2` (task identity, complete lattice attachment, unique PRM query-edge metrics, RRT `goal_root_count=9` with non-first selected roots, U/Q/X traces, `actuator_metric_on_q` panels, animations and print contact sheets). V3.6B findings are marked corrected or interpretive as recorded in [`V3_6B_GATE_B_REVIEW_FINDINGS.md`](V3_6B_GATE_B_REVIEW_FINDINGS.md). `ACTIVE_SPRINT` returns to no authorization. V3.7 is not activated.
