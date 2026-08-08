# V3.6B Gate B review findings stub

**Status:** drafted stub — fill after reviewing
`results/v3_review/v3_6b_planar2r_visual_audit/`
**Sprint:** V3.6B (V3-620–V3-629)
**Does not activate V3.7.** Residual V3.7 remains drafted/blocked until this
review is completed and ACTIVE_SPRINT separately authorizes residual work.

## Gate B §8 questions

Record findings against each question before residual V3.7 activation.

1. **Is the current Q lattice truly shared, or do any planners regenerate task
   geometry per mechanism?**
   - _Finding:_ _(pending review)_
   - _Evidence:_ trial pages §4 embeddings; `assert_pair_invariants` / shared
     `q_nodes` checks.

2. **Do the U embeddings visibly explain the mechanism-specific actuator cost?**
   - _Finding:_ _(pending review)_
   - _Evidence:_ U embeddings and \(w_U\) panels; \(\Delta L_U\) tables.

3. **Are \(w_Q\), \(w_U\), and \(w_X\) calculated from the intended local motion
   rather than endpoint shortcuts?**
   - _Finding:_ _(pending review)_
   - _Evidence:_ `audits/metrics.integrate_edge_weights` uses declared
     output-linear connector; \(w_U\) from `ActuatorTravelObjective.motion_cost`;
     \(w_Q\) endpoint length is exact for output-linear Q; \(w_X\) from tip
     polyline on connector samples.

4. **Does A\* reduce exploration for the right reason, and does its heuristic
   remain a lower bound to the represented goal set?**
   - _Finding:_ _(pending review)_
   - _Evidence:_ lattice expansion animations / masks; Dijkstra–A\* cost parity
     tests.

5. **Do PRM and RRTConnect preserve exact starts and the same frozen goal
   candidates?**
   - _Finding:_ _(pending review)_
   - _Evidence:_ runs JSON `selected_goal_sample_id`; trajectory first waypoint;
     frozen generator provenance.

6. **Are differences in selected goal states visible and correctly attributed to
   mechanism-aware cost or planner suboptimality?**
   - _Finding:_ _(pending review)_
   - _Evidence:_ paired metrics tables; \(\Delta z = z_F - z_G\).

7. **Do the report and code architecture make every U→Q→X transition auditable?**
   - _Finding:_ _(pending review)_
   - _Evidence:_ `architecture.html` ownership table; trial section order.

8. **Are any shared modules still 2R-specific after V3.6A?**
   - _Finding:_ _(pending review)_
   - _Evidence:_ V3.6A migration note; audit-only planar helpers under
     `audits/` and `visualization/audit_*`.

## Disposition

- [ ] Review complete
- [ ] Discrepancies corrected **or** entered as explicit V3.7 residual blockers
- [ ] ACTIVE_SPRINT may separately activate residual V3.7 (not done here)
