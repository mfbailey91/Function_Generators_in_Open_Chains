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
- **Archive documents preserve history** but are not current implementation authority.

## Compatibility redirects

The former root-level Markdown paths remain as temporary redirect stubs so existing links do not break during the migration. New edits should target the authoritative paths above. See [DOCS_MIGRATION.md](DOCS_MIGRATION.md).
