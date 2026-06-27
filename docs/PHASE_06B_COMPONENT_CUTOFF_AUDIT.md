# Phase 06B: Component cutoff audit before phenotype analysis

## Purpose

This phase audits how each frame-level component behaves when p95 and p99 are used as cutoffs.
The goal is not to make clinical claims from side, sex, or procedure differences in the current
RATS-only cohort. The goal is to decide how visual hazard scores should be used as analyzability
filters before downstream field phenotype analysis.

## Questions answered

For each score column and cutoff:

1. Total number of frames evaluated.
2. Number and fraction of frames above the p95/p99 cutoff.
3. Distribution of cutoff-positive frames across level-1 phases.
4. Frames for visual audit:
   - top 10 highest frames
   - bottom 10 lowest frames
   - 10 frames just above p95
   - 10 frames just below p95
   - 10 frames just above p99
   - 10 frames just below p99

## Primary interpretation

- p99 should be considered a severe-obstruction exclusion candidate for downstream phenotype metrics.
- p95 should be considered a conservative clean-reference filter and a sensitivity threshold.
- p95 may over-exclude frames that contain clinically meaningful field phenotypes, such as blood-like
  redness or anthracosis-like blackness.

## Recommended run

```powershell
python .\scripts\14_build_component_cutoff_audit_sets.py `
  --frame-table .\reports\visual_hazard_burden\visual_hazard_frame_flags.csv `
  --output-dir .\reports\component_cutoff_audit `
  --annotation-output-dir .\data\annotations `
  --score-col structural_visibility_loss_v1 center_low_structure_area_v1 whiteout_ratio_v1 low_light_or_blackout_ratio_v1 `
  --phase-distribution-csv .\reports\phase_component_distributions\case_phase_component_distribution_summary.csv `
  --quantile p95 p99 `
  --n-review 10 `
  --print-summary
```

## Optional all-component run

```powershell
python .\scripts\14_build_component_cutoff_audit_sets.py `
  --frame-table .\reports\visual_hazard_burden\visual_hazard_frame_flags.csv `
  --output-dir .\reports\component_cutoff_audit_all_components `
  --annotation-output-dir .\data\annotations `
  --score-col-mode common `
  --phase-distribution-csv .\reports\phase_component_distributions\case_phase_component_distribution_summary.csv `
  --quantile p95 p99 `
  --n-review 10 `
  --print-summary
```

## Notes

`visual_hazard_frame_flags.csv` may not contain frame-level phase labels. When that happens, pass `--phase-distribution-csv .\reports\phase_component_distributions\case_phase_component_distribution_summary.csv` to build the Level-1 phase summary from the existing Phase 03 distribution table.

## Outputs

```text
reports\component_cutoff_audit\component_cutoff_overall_summary.csv
reports\component_cutoff_audit\component_cutoff_level1_phase_summary.csv
reports\component_cutoff_audit\component_cutoff_case_summary.csv
reports\component_cutoff_audit\component_cutoff_review_frames.csv
reports\component_cutoff_audit\component_cutoff_audit_inventory.csv

data\annotations\component_cutoff_review_frames.csv
```

## Montage export

The review CSV includes `review_id`, so it can be passed directly to the existing review-sheet exporter:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\component_cutoff_review_frames.csv `
  --output-dir .\reports\component_cutoff_audit_sheets `
  --draw-roi

python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\component_cutoff_review_frames.csv `
  --output-dir .\reports\component_cutoff_audit_sheets_roi `
  --crop-roi
```

## Review logic

The most important frames to inspect are not only the top 10 frames. The cutoff-neighbor frames are
more important for deciding whether p95 or p99 is a reasonable exclusion threshold.

- just_above_p95 vs just_below_p95: tests whether the broad p95 cutoff is too aggressive.
- just_above_p99 vs just_below_p99: tests whether p99 captures only truly uninterpretable or severely
  obstructed images.

## Decision expected from this phase

After visual review, decide:

1. Which components are safe to use as primary analyzability filters.
2. Whether p99 should be the primary downstream exclusion rule.
3. Whether p95 should be reserved for clean-reference selection only.
4. Which components should not be used as filters because they remove meaningful field phenotype.
