# Documentation migration

This branch reorganizes documentation without changing Version 1 or Version 2 scientific semantics.

## Rules

1. Authoritative software documents live under `docs/software/`.
2. Paper, theory, and literature live under `docs/research/`.
3. Historical status records live under `docs/archive/`.
4. Old root-level Markdown paths are compatibility redirects only.
5. Existing paper figures remain in `docs/figures/` for old links and are copied beside the moved paper under `docs/research/paper/figures/`.
6. New documents should use the authoritative paths; compatibility redirects may be removed in a later dedicated cleanup after link checking.

## Source-of-truth map

| Question | Authoritative location |
| --- | --- |
| What differs between Version 1 and Version 2? | `software/VERSION_MATRIX.md` |
| What is the overall roadmap? | `software/PROJECT_PLAN.md` |
| What must the architecture mean? | `software/architecture/contracts/` |
| Why was a decision made? | `software/architecture/adr/` |
| What is being implemented now? | `software/planning/ACTIVE_SPRINT.md` |
| How is a claim tested? | `software/experiments/` |
| What is the research argument? | `research/` |
| What is retained only for history? | `archive/` |
