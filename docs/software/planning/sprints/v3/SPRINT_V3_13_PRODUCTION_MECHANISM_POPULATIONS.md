# Sprint V3.13 — Production Mechanism Populations

**Status:** drafted / not activated  
**Reserved work packages:** V3-1300–V3-1307  
**Code authorization:** none until application/benchmark gates explicitly authorize production inference

## Sprint intent

Return to scaled mechanism/task populations only after Version 3 has separated mechanism geometry, dimensional/task family, planner representation, local motion, goal representation, collision scene, and stochastic repetition policy.

This is the first sprint in the revised roadmap permitted to make population-level statistical claims.

## Work packages

### V3-1300 — Estimand freeze

Define exactly which mechanism, task, scene, and planner populations each reported effect represents.

### V3-1301 — Frozen mechanism banks

Version mechanism populations and matching rules, including gearbox and identity/null controls where relevant.

### V3-1302 — Frozen task/scene banks

Freeze application-task distributions separately by DOF/task family and scene class.

### V3-1303 — Planner statistical designs

Use deterministic paired designs where appropriate and repeated stochastic designs with declared seed/process protocols.

### V3-1304 — Resolution/resource calibration

Calibrate numerical resolution, memory, wall-time budgets, and failure/retry policies without tuning on production outcomes.

### V3-1305 — Production runner

Immutable configs, sharding, restart/failure accounting, provenance, and review artifacts.

### V3-1306 — Statistical analysis

Paired absolute/relative effects, uncertainty intervals, mechanism-descriptor correlations, task/scene strata, and multiple-comparison discipline where required.

### V3-1307 — Evidence freeze

Publish immutable data, configs, code revision, environment, report, and reproduction commands.

## Exit criteria

1. Every effect has an explicit estimand and frozen sampling population.
2. Planner-specific events are never pooled as one universal effort metric.
3. Invalid/unreachable/direct/global strata are not silently mixed.
4. Stochastic repetitions are statistically and operationally reproducible.
5. Production evidence is immutable and independently reviewable.
