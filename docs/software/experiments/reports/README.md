# Experiment reports

Reports record code revision, configuration, result location, exclusions, plots, statistical interpretation, and limitations for an accepted study. A report does not replace its protocol.

- [V2.8 Shared-Q paired study summary](V2_8_SHARED_Q_PAIRED_STUDY_SUMMARY.md)
- [V2.9 U-distance-only shared-Q paired study summary](V2_9_SHARED_Q_U_DISTANCE_SUMMARY.md)
- [V2.10 Dijkstra production Monte Carlo summary](V2_10_PRODUCTION_DIJKSTRA_SUMMARY.md) · [HTML dashboard](V2_10_PRODUCTION_DIJKSTRA.html) (Experiment A, Dijkstra cell)
- [V2.11 A* paired campaign summary](V2_11_ASTAR_PAIRED_CAMPAIGN_SUMMARY.md) · [HTML dashboard](V2_11_ASTAR_PAIRED_CAMPAIGN.html) (Experiment A, A* cell)

Experiment A protocol: [`../protocols/EXPERIMENT_A_CENTERED_Q_PROBES.md`](../protocols/EXPERIMENT_A_CENTERED_Q_PROBES.md).

Per-run production canvases also live under `results/<run_id>/reports/` after `scripts/merge_v2_production.py` or a completed `scripts/run_v2_production.py` stage. The frozen production sample bank is `configs/v2/sample_banks/production_v1.json`.
