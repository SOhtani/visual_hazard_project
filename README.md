# Visual hazard project update: Phase 06B component cutoff audit

Adds a component-level p95/p99 cutoff audit script:

- `scripts/14_build_component_cutoff_audit_sets.py`
- `docs/PHASE_06B_COMPONENT_CUTOFF_AUDIT.md`

This phase audits how many frames each component would exclude at p95 and p99, how those frames are
distributed across level-1 phases, and which frames should be visually reviewed around the cutoffs.

The main use is to decide whether visual hazard scores should be used as analyzable-frame filters
before blood-like redness, blackness, anthracosis-like, and other field phenotype analyses.


Patch notes:

- Adds `review_id` to `component_cutoff_review_frames.csv` for compatibility with `07_export_component_review_sheets.py`.
- Adds `--phase-distribution-csv` for Level-1 phase summaries when `visual_hazard_frame_flags.csv` has no frame-level phase column.
- Writes header-only phase summary CSVs instead of empty files when no phase source is available.
