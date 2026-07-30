# Documentation

The documentation is organized by authority so Version 1 and Version 2 can coexist without blending their assumptions.

## Start here

### Implementing software

1. [Version matrix](software/VERSION_MATRIX.md)
2. [Software project plan](software/PROJECT_PLAN.md)
3. [Architecture guide](software/architecture/README.md)
4. [Active sprint](software/planning/ACTIVE_SPRINT.md)

### Running or interpreting experiments

1. [Experiment documentation](software/experiments/README.md)
2. The relevant protocol and schema
3. The relevant runbook

### Working on the research narrative

1. [Research documentation](research/README.md)
2. [Paper draft](research/paper/inequality_mechanisms_paper_draft.md)
3. [Literature map](research/literature/literature_map.md)

## Authority model

- **Contracts specify** what the current software must mean.
- **ADRs decide** why foundational choices were made and which version they apply to.
- **Sprints execute** accepted contracts and ADRs.
- **Experiment protocols define evidence** and reports interpret completed runs.
- **Research documents motivate** the program without silently creating software requirements.
- **Archive documents preserve unique history** but are not current implementation authority.

## Document lifecycle

- Keep one canonical file for each live document.
- Update links when a document moves; do not add new redirect files.
- Preserve completed Version 1 sprint records under `software/planning/sprints/v1/`.
- Use Git history for superseded plans and deleted migration scaffolding.
- Archive a document only when it contains unique context not preserved elsewhere.

The root ADR redirect files remain temporarily because existing Version 1 records still reference them. They are compatibility paths, not authority, and should be removed after the Version 2 contract sprint completes a repository-wide link audit.
