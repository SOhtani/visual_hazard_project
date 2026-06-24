# Phase 2B: Image validity candidate flags

## Purpose

Phase 2B adds candidate-only image validity flags to support component review. The purpose is not to exclude surgical phases. The purpose is to label frames whose visual state may distort component-level validation.

This phase was introduced after reviewing component montage sheets and observing that several high-score examples were dominated by photometric or near-uniform image states rather than the intended component phenomenon.

## Key decision

For the current input data, `per_frame_manual_roi` already contains frames with manually available ROI coordinates. In the tested cases, `OutsideBody` intervals from SurgCap workflow annotation had zero exact overlap with the metric CSV rows. Therefore, workflow-based `OutsideBody` exclusion is not required for the current component review set.

Workflow annotations may still be useful later for phase-specific burden analysis. They should not be used here to remove `PortDockExplore`, `DrainClosure`, `FireFly`, or other phases unless a separate analysis question explicitly requires phase restriction.

## Added candidate columns

`05_compute_frame_visual_hazard_components.py` adds the following columns to per-frame metric CSVs:

```text
roi_gray_std_v1
roi_edge_density_v1
roi_gray_entropy_bits_v1
near_uniform_frame_candidate_v1
large_whiteout_candidate_v1
large_blackout_candidate_v1
color_bar_or_test_pattern_candidate_v1
photometric_failure_candidate_v1
image_validity_problem_candidate_v1
component_review_valid_candidate_v1
```

These are candidates, not labels. They should be interpreted as triage markers for montage review.

## Intended use

Default behavior is annotation only:

```text
1. Recompute per-frame metrics with image validity candidate columns.
2. Build the same component review set.
3. Carry the candidate validity columns into component_review_frames.csv.
4. Display compact validity flags on montage sheets.
5. Decide manually whether the flags are useful.
```

The review-set builder includes an optional `--use-image-validity-filter` flag, but it is off by default. Do not enable it until the candidate flags have been inspected visually.

## Flag abbreviations on montage sheets

```text
WU     large whiteout candidate
BO     large blackout candidate
UNI    near-uniform frame candidate
CB/TP  color bar or test-pattern candidate
VALID?N image-validity problem candidate
```

Absence of a flag does not prove that a frame is valid. Presence of a flag does not prove that a frame should be excluded.

## Example commands

Recompute metrics for the current two-case test set:

```powershell
python .\scripts\05_compute_frame_visual_hazard_components.py `
  --per-frame-input-dir "C:\Users\SOhtani2024\rats_visibility_study\data\derived\quality_metrics\per_frame_manual_roi" `
  --per-frame-output-dir .\data\derived\quality_metrics\per_frame `
  --case CASE003 CASE010 `
  --overwrite
```

Build review set with validity columns carried through, but without filtering:

```powershell
python .\scripts\06_build_component_review_set.py `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --output-csv .\data\annotations\component_review_frames_image_validity.csv `
  --case CASE003 CASE010 `
  --n-high 8 `
  --n-low 4 `
  --per-case-cap 2 `
  --print-validity-summary
```

Export montage sheets:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\component_review_frames_image_validity.csv `
  --output-dir .\reports\component_review_sheets_image_validity `
  --draw-roi
```

Export ROI-crop montage sheets:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\component_review_frames_image_validity.csv `
  --output-dir .\reports\component_review_sheets_image_validity_roi `
  --crop-roi
```

Optional filtering mode, only after visual review:

```powershell
python .\scripts\06_build_component_review_set.py `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --output-csv .\data\annotations\component_review_frames_image_validity_filtered.csv `
  --case CASE003 CASE010 `
  --n-high 8 `
  --n-low 4 `
  --per-case-cap 2 `
  --use-image-validity-filter `
  --print-validity-summary
```


## Anthracosis candidate deferred

The initial image-validity review showed that `anthracosis_like_blackness_candidate_v1` behaves as a generic persistent dark-area descriptor. Without a lung mask or pleural-surface mask, it cannot distinguish pleural anthracosis from blood, clot, instruments, shadows, FireFly/monochrome frames, or camera-border darkness. Therefore, `anthracosis_like_blackness_candidate` is removed from the default Phase 2 review targets.

The underlying blackness columns may remain in metric CSVs for exploratory quality control, but anthracosis-specific quantification should be redesigned after anatomical masking is available.

## Interpretation rule

Do not rename `near_uniform_frame_candidate_v1` as obstruction, smoke, fog, or poor field. It only means low variation / low edge / low entropy by image statistics.

Do not rename `large_blackout_candidate_v1` as extracorporeal. In the current dataset, true extracorporeal frames have already been largely removed upstream by the manual ROI dataset.
