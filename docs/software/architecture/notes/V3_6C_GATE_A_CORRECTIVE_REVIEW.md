# V3.6C Gate A Corrective Review

**Disposition:** changes requested
**Reviewed main:** `db967ab31af8acab83d113812bab748384374234`
**Reviewed implementation source:** `e32394978e4283015444ad8b6bcad090a6b8140f`
**Reviewed generated-artifact commit:** `7d97666faa2245a33b39f16df6544bcef2eaaa18`
**Corrective work packages:** V3-640–V3-644

## Review conclusion

V3-631 through V3-639 establish the intended common planner, goal, trajectory,
trace, metric, and report architecture. The generated V3.6C package is a valid
review candidate, but Gate A remains open because two bounded implementation
details weaken the declared comparison contract.

This review does not reopen the V3.6C scientific formulation and does not
authorize V3.7. It authorizes only the two corrections below, their report and
regression coverage, clean regeneration, and final disposition.

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
