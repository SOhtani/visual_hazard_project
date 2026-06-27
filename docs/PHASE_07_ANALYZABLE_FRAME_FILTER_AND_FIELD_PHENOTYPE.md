# Phase 07: Analyzable-frame filter and field-phenotype direction

## Purpose

Phase 07 repositions the current visual-hazard gate as a preprocessing filter for downstream field-phenotype analyses.

The current 2023 RATS cohort is a stable-view method-development cohort. It should not be used to overinterpret sex, side, or procedure differences in visual-hazard burden. The more useful role of the current Tier-1 visual-hazard gate is to identify frames that are unsuitable for downstream visual phenotype quantification.

## Conceptual shift

Earlier exploratory outputs summarized visual-hazard burden against operation time, blood loss, age, procedure, side, and target anatomy. Those outputs are useful for sanity checking, but they are not the main endpoint.

The next analysis should use a two-stage design:

```text
Stage 1: analyzable-frame gate
  Separate frames that are technically and visually interpretable enough for phenotype analysis.

Stage 2: field-phenotype metrics
  Within analyzable frames, quantify blood-like redness, blackness/anthracosis-like features, inflammation/adhesion-like visual features, and approach-related field stability.
```

## Recommended frame sets

### Primary analyzable set

```text
analyzable_frame_primary_p99
```

Default definition:

```text
not visual_hazard_any_p99
and not image-validity failure if available
```

In practice, the Phase 04 `clean_reference_candidate_p99` column is used when available because it already excludes severe visual hazard and image-validity problems.

This is the preferred frame set for phenotype analysis because it excludes severe whiteout, blackout, and near-uninterpretable red-out while avoiding excessive exclusion of frames that may contain clinically meaningful blood-like or anthracosis-like features.

### Conservative clean reference set

```text
clean_reference_frame_p95
```

Default definition:

```text
not visual_hazard_any_p95
and not image-validity failure if available
```

This is useful for negative controls, clean reference images, and baseline field appearance. It may be too restrictive for phenotype analysis because p95 exclusion can remove the very red/black field appearances that later modules aim to quantify.

## Run

```powershell
python .\scripts\12_build_analyzable_frame_sets.py `
  --frame-flags .\reports\visual_hazard_burden\visual_hazard_frame_flags.csv `
  --output-dir .\reports\analyzable_frame_sets `
  --annotation-output-dir .\data\annotations `
  --primary-threshold p99 `
  --clean-threshold p95 `
  --write-frame-manifests
```

## Outputs

```text
reports/analyzable_frame_sets/analyzable_frame_overall_summary.csv
reports/analyzable_frame_sets/case_analyzable_frame_summary.csv
reports/analyzable_frame_sets/case_phase_analyzable_frame_summary.csv

data/annotations/analyzable_frames_primary_p99.csv
data/annotations/clean_reference_frames_p95.csv
data/annotations/excluded_from_primary_analyzable_p99.csv
```

## Interpretation

The primary analyzable set should be used for blood-like redness and blackness/anthracosis-like metrics.

The conservative clean set should be used for clean reference sampling and negative controls.

Do not use the current RATS cohort to make strong claims that visual hazard burden differs by sex, side, or procedure. The current cohort is mainly a method-development and stable-view baseline dataset.

## Next phenotype modules

The next modules should be computed within `analyzable_frame_primary_p99`:

```text
blood_like_redness_v1
fresh_red_candidate_ratio_v1
dark_red_brown_candidate_ratio_v1
blackness_raw_ratio_v1
blackness_corrected_ratio_v1
anthracosis_like_candidate_v2
```

These should be named according to what they measure visually. Avoid calling a pixel-level metric “blood” or “anthracosis” without segmentation, anatomical context, or review-based validation.
