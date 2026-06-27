# Phase 07: Purpose-specific analyzable frame sets

## Rationale

The component cutoff audit showed that p95 thresholds are too broad for hard exclusion before downstream field-phenotype analysis. In particular, p95-adjacent frames for `structural_visibility_loss_v1` and `center_low_structure_area_v1` often contain blood-like redness, blackness, tissue contact, instruments, smoke/fog, or field information that may be biologically or surgically meaningful.

Therefore, the visual-hazard gate should not be treated as a clinical endpoint in the current stable RATS cohort. It should be used to define image analyzability strata.

## Revised principle

Do not use a single universal exclusion rule.

Separate the frame sets by analytic purpose:

1. `technical_analyzable_frame_v1`
   - used as the broad base set for downstream phenotype analysis.
   - excludes technical failures, gross photometric failures, color bar/test pattern, large whiteout, and large blackout when those flags are available.

2. `color_phenotype_analyzable_frame_v1`
   - primary set for blood-like redness, blackness, and anthracosis-like color phenotype metrics.
   - excludes technical failures and severe low-light/blackout.
   - keeps structural/center-low-structure p99 frames as soft flags, because these may contain the phenotype of interest.

3. `structural_phenotype_analyzable_frame_v1`
   - stricter set for morphology/structure-oriented analysis.
   - excludes technical failures and p99 visual hazard.

4. `clean_reference_frame_p95_v1`
   - conservative clean reference / negative control set.
   - not the default phenotype-analysis set.

## Key interpretation from cutoff audit

- `low_light_or_blackout_ratio_v1` top frames are true blackout and should be excluded.
- `whiteout_ratio_v1` top frames are true whiteout and should be excluded; p95/p99 boundary frames are often still interpretable.
- `structural_visibility_loss_v1` and `center_low_structure_area_v1` p95 are too broad for exclusion.
- `structural_visibility_loss_v1` and `center_low_structure_area_v1` p99 should be soft flags for color phenotype work, not hard exclusions.

## Run command

```powershell
python .\scripts\12_build_purpose_specific_analyzable_frame_sets.py `
  --frame-flags .\reports\visual_hazard_burden\visual_hazard_frame_flags.csv `
  --output-dir .\reports\purpose_specific_analyzable_frame_sets `
  --annotation-output-dir .\data\annotations `
  --write-frame-manifests
```

Optional stricter color analysis sensitivity:

```powershell
python .\scripts\12_build_purpose_specific_analyzable_frame_sets.py `
  --frame-flags .\reports\visual_hazard_burden\visual_hazard_frame_flags.csv `
  --output-dir .\reports\purpose_specific_analyzable_frame_sets_color_no_whiteout_p99 `
  --annotation-output-dir .\data\annotations `
  --color-exclude-whiteout-p99 `
  --write-frame-manifests
```

## Outputs

Summary outputs:

- `reports/purpose_specific_analyzable_frame_sets/frame_set_overall_summary.csv`
- `reports/purpose_specific_analyzable_frame_sets/case_frame_set_summary.csv`
- `reports/purpose_specific_analyzable_frame_sets/case_phase_frame_set_summary.csv`
- `reports/purpose_specific_analyzable_frame_sets/technical_exclusion_reason_summary.csv`
- `reports/purpose_specific_analyzable_frame_sets/soft_visual_hazard_flag_summary.csv`
- `reports/purpose_specific_analyzable_frame_sets/frame_set_flag_inventory.csv`
- `reports/purpose_specific_analyzable_frame_sets/frame_set_parameters.csv`

Frame manifests:

- `data/annotations/technical_analyzable_frames_v1.csv`
- `data/annotations/technical_excluded_frames_v1.csv`
- `data/annotations/color_phenotype_analyzable_frames_v1.csv`
- `data/annotations/structural_phenotype_analyzable_frames_v1.csv`
- `data/annotations/clean_reference_frames_p95_v1.csv`
- `data/annotations/severe_visual_obstruction_softflag_p99_v1.csv`

## Use in downstream phases

### Blood-like redness

Use `color_phenotype_analyzable_frames_v1.csv` as the primary denominator.

Keep the following as covariates/sensitivity flags:

- `softflag_structural_visibility_loss_ge_p99_v1`
- `softflag_center_low_structure_area_ge_p99_v1`
- `softflag_whiteout_ge_p99_v1`
- `softflag_low_light_or_blackout_ge_p99_v1`

### Blackness / anthracosis-like phenotype

Use `color_phenotype_analyzable_frames_v1.csv`, but treat severe low-light exclusion carefully. If the target is illumination-independent blackness, compare against the technical-only frame set.

### Clean reference

Use `clean_reference_frames_p95_v1.csv` for baseline/negative-control examples. Do not use it as the primary denominator for blood-like or anthracosis-like phenotype burden.

## Positioning

This phase changes the interpretation of the visual-hazard gate:

> The visual-hazard gate is not the primary clinical endpoint in the stable RATS cohort. It is used to stratify image analyzability for downstream video-derived field-phenotype analysis.
