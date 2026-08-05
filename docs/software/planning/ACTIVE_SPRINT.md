# Active sprint

**Current focus:** [Sprint V2.10 — Production Monte Carlo Orchestration: Dijkstra Campaign](sprints/v2/SPRINT_V2_10_PRODUCTION_MONTE_CARLO_ORCHESTRATION.md)

**Completed:** V2.0, V2.1, V2.2, V2.3, V2.4, V2.5, V2.6, V2.8, V2.9

**Held:** [Sprint V2.7 — 3R Planar Extension](sprints/v2/SPRINT_V2_7_3R_EXTENSION.md) (deferred until trusted 2R production evidence is reviewed)

V2.10 scales the reviewed shared-Q paired study into a restartable, memory-bounded Dijkstra Monte Carlo. It freezes `actuator_travel` as the only production objective, uses one solver per campaign, and keeps A*, bidirectional search, and sampling-based planners for later campaigns on the same sample bank.
