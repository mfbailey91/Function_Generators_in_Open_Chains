# Version 3 review results

This directory is the explicit exception to the repository-wide `results/*`
ignore rule. It contains **small, reviewable Version 3 smoke/parity snapshots**
that are intentionally committed to GitHub with the code revision that
generated them.

These snapshots are not production evidence, task-population inference, or
Monte Carlo campaigns. They exist so reviewers can inspect the behavioral
consequences of the Version 3 architecture without rerunning every local smoke
pack.

## V3.5 closeout snapshot

Generate the complete V3.2–V3.5 review package in an OMPL-enabled environment:

```bash
PYTHONPATH=src python scripts/export_v3_review_results.py
```

Output: `results/v3_review/v3_5_closeout/`.

## V3.6 free-space evidence

Bounded free-space planner evidence over the frozen Cartesian bank (not
population inference):

```bash
PYTHONPATH=src:. python scripts/run_v3_6_free_space_evidence.py
```

Prefer an OMPL-enabled interpreter (e.g. `.conda-ompl`) so `ompl_*` rows are
populated rather than skipped. Output: `results/v3_review/v3_6_free_space/`
plus `docs/software/experiments/reports/V3_6_FREE_SPACE_EVIDENCE.html`.
