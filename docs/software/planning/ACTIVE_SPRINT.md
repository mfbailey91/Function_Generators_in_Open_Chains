# Active sprint

**Current focus:** Sprint V4.2B — Final Canonical Evidence and Closeout Gate.

**Code authorization:** **V4-220–V4-229 only.** Implement only [SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md](sprints/v4/SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md) under [ADR-029](../architecture/adr/ADR-029-mounted-output-coordinate.md). Write fresh evidence only under `results/v4_review/v4_2b_span_controlled_corrective_closeout/`. Do not implement V4.3, V4.4+, residual V3.7, obstacles, MoveIt, 6R, gravity-aware wrench, or force-aware planning. Do not overwrite V4.0, V4.1, V4.2, V4.2A, or any `results/v3_review/` package. Do not resynthesize the V3.6D registry or retune `PRIMARY_CERTIFICATE`.

**Corrective purpose:** apply the frozen V3.6D output mounting offsets exactly once; make mounted robot joint coordinates authoritative for FK, `J_f`, shared-Q samples, and goals; restore one common paired graph topology; filter invalid local motions before search; retain complete compressed primary data with hashes; and regenerate from a clean implementation revision. V4.2/V4.2A remain immutable historical evidence.

**Implementation checkpoint:** PR #27 merged the mounted-Q realization, common candidate graph, finite-edge adapter, common-physical task bank, compressed row inventory, and clean-source guard. Final paired-edge admission, nonfinite semantics, manifest hardening, common-physical audit, closeout tests, CI, and documentation are in tree. Canonical V4.2B generation, independent review, and V4-229 authorization reset remain open. Follow [V4_2B_FINAL_CLOSEOUT_GATE.md](sprints/v4/V4_2B_FINAL_CLOSEOUT_GATE.md) and [ADR-030](../architecture/adr/ADR-030-paired-final-topology-and-nonfinite-edge-semantics.md). Do not create V4.2C.

**Completed:** V2.0–V2.12 smoke/calibration (production held); V3.0–V3.5; V3.6 corrective 2R free-space evidence; **Sprint V3.6A**; **Sprint V3.6B**; **Sprint V3.6C**; **Sprint V4.0** kinematic geometry core; **Sprint V4.1** planar-2R intrinsic geometry atlas; **Sprint V3.6D** canonical span corpus; **Sprint V3.6E** gravity-free static wrench core; **Sprint V3.6F** static wrench atlas; **Sprint V4.2** span-controlled geometry atlas; **Sprint V4.2A** span-controlled visual planning audit. **Provisional** Sprint V3.7 remains non-final.

**Frozen evidence:** all committed packages under `results/v3_review/`; V4.0 `v4_0_kinematic_geometry_core`; V4.1 `v4_1_planar2r_geometry_atlas`; V4.2 `v4_2_span_controlled_geometry_atlas`; and V4.2A `v4_2a_span_controlled_visual_audit`. V4.2B may read and digest these packages but may not mutate or regenerate them.

**Roadmap:** V4.2B final closeout gate → no authorization → separately reviewed V4.3 intrinsic-wrench activation → V4.4 velocity/IK. Residual V3.7 remains separately drafted / blocked. See the [final closeout gate](sprints/v4/V4_2B_FINAL_CLOSEOUT_GATE.md), [V4.2B amendment](V4_2B_CORRECTIVE_PROGRAM_AMENDMENT.md), [V4 sprint index](sprints/v4/README.md), [ADR-027](../architecture/adr/ADR-027-v4-kinematic-transmission-geometry.md), [ADR-028](../architecture/adr/ADR-028-gravity-free-static-wrench.md), [ADR-029](../architecture/adr/ADR-029-mounted-output-coordinate.md), and [ADR-030](../architecture/adr/ADR-030-paired-final-topology-and-nonfinite-edge-semantics.md).

**Closeout rule:** V4-229 must return this file to no authorization. Do not activate V4.3 in the V4.2B closeout change.

**Held:** Version 2 Cartesian production inference, obstacles, MoveIt, 6R, Sprint V3.7 residual, Sprint V3.8+, Sprint V4.3+, V4.0A kernel rewrites, production V4-006, gravity-aware wrench, force-aware planning, mechanism resynthesis, certificate retuning, and deferred items (`V3-DEFER-001`, `V3-DEFER-002`).
