# V3.6A dimensional-generalization migration note

**Sprint:** V3.6A (V3-610–V3-617)  
**Status:** post-refactor ownership note (not an ADR)

## Purpose

Record public-import compatibility and module ownership after the
dimensional-generalization refactor. This note does not authorize new planner
work or reinterpret frozen evidence.

## Public imports to preserve

Package-level re-exports from `inequality_mechanisms.core` remain supported:

- goal predicates: `ExactOutputGoal`, `CartesianDiskGoal`, `PlanarPoseRegionGoal`,
  `GoalConstraint`, `GoalResidual`, `GoalSamplingRequest`, `GoalStateGenerator`
- kinematics generators (shimmed): `CartesianDiskGoalGenerator`,
  `planar_2r_ik_family`, `Planar3RPoseGoalGenerator`,
  `FrozenPlanar3RPositionGoalGenerator`

Preferred direct imports for generators:

- `inequality_mechanisms.kinematics.planar_2r_goals`
- `inequality_mechanisms.kinematics.planar_3r_goals`

`inequality_mechanisms.core.goals` retains predicates and generator *protocols*
only. It must not import `Planar2R`.

## Ownership model

| Concern | Owner |
| --- | --- |
| DOF / tip FK / Jacobian protocol | `core.kinematic_model.KinematicModel` |
| Actuator sampling box | `core.input_domain.InputDomain` on `RobotModel` |
| Operating-branch adapter | `adapters.operating_branch_robot` (generic `kinematic_model`) |
| Sampling bounds for PRM/RRT/OMPL | `planners.sampling_space.actuator_bounds` via `input_domain` |
| Planar 2R / 3R IK goal generators | `kinematics.*_goals` |
| Endpoint U/Q/X path metrics | `core.trajectory_metrics` |

## Provisional V3.7 path

Provisional planar-3R free-space code and evidence under
`results/v3_review/v3_7_3r_free_space/` remain compatibility baselines. Do not
regenerate or rewrite that package while executing or closing V3.6A. Residual
V3.7 reconciliation (architecture-final 3R) waits for V3.6B and explicit
re-authorization.

## Frozen evidence

Do not regenerate, overwrite, or reinterpret frozen artifacts under:

- `results/v3_review/v3_6_*`
- `results/v3_review/v3_7_*`
- Version 1 / Version 2 golden fixtures

New metrics such as `path_length_x` are opt-in on fresh planner runs only.

## Follow-on

Sprint V3.6B (planar 2R visual audit) remains drafted and blocked until ACTIVE_SPRINT
explicitly activates it. No V3.6B HTML/traces are authorized by this note.
