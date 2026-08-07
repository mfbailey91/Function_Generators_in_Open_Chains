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

The command writes `results/v3_review/v3_5_closeout/`. Commit that generated
directory together with the V3.5 closeout changes. The exporter refuses to
produce a partial closeout snapshot when OMPL is unavailable and fails if the
native/OMPL parity invariants do not pass.
