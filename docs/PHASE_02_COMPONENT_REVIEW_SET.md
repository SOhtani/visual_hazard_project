# Phase 2: Component-specific review set

## Purpose

Phase 2 creates a curated frame-level review set for validating visual hazard component metrics. This phase is not intended to create a composite score. It is intended to determine whether each component metric actually captures the visual phenomenon it is supposed to approximate.

## Principle

Do not interpret a metric using a clinical phenomenon name until component-specific validation has been completed.

Examples:

- `whiteout_ratio_v1` may be interpreted as a raw photometric saturation burden.
- `specular_like_ratio_v1` may be interpreted as a high-value / low-saturation pixel burden.
- `anthracosis_like_blackness_candidate_v1` must not be interpreted as anthracosis until manually validated.
- `center_low_structure_area_v1` must not be interpreted as physical obstruction until manually validated.

## Inputs

The expected input is the per-frame visual hazard component CSV directory:

```text
data/derived/quality_metrics/per_frame/
```

Each case-level CSV should contain at least:

```text
case_id or inferable case id from filename
image_path
sample_time_sec or frame index
roi_x0, roi_y0, roi_x1, roi_y1
component score columns
```

## Generated local outputs

The generated review CSV is written to:

```text
data/annotations/component_review_frames.csv
```

The generated montage sheets are written to:

```text
reports/component_review_sheets/
```

These outputs may contain case identifiers, local file paths, and surgical images. They should generally remain local and should not be committed to GitHub.

## Step 1: Build candidate review frames

Example:

```powershell
python .\scripts\06_build_component_review_set.py `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --output-csv .\data\annotations\component_review_frames.csv `
  --n-high 24 `
  --n-low 8 `
  --per-case-cap 3
```

For a small test run:

```powershell
python .\scripts\06_build_component_review_set.py `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --output-csv .\data\annotations\component_review_frames.csv `
  --case CASE003 CASE010 `
  --n-high 8 `
  --n-low 4 `
  --per-case-cap 2
```

Dry run:

```powershell
python .\scripts\06_build_component_review_set.py `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --dry-run
```

## Step 2: Export montage sheets

Example using full frames with ROI rectangles:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\component_review_frames.csv `
  --output-dir .\reports\component_review_sheets `
  --draw-roi
```

Example using ROI crops:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\component_review_frames.csv `
  --output-dir .\reports\component_review_sheets_roi `
  --crop-roi
```

To inspect only one component:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\component_review_frames.csv `
  --component whiteout specular_like_reflection `
  --draw-roi
```

## Step 3: Manual curation

After montage review, edit `component_review_frames.csv` locally:

```text
manual_include: 1 or 0
manual_primary_label: clear, whiteout, specular, shadow, anthracosis_like, blood_like, etc.
manual_notes: short reason for inclusion/exclusion
```

Keep intentionally ambiguous examples. They are necessary for false-positive and false-negative analysis.

## Required categories

The review set should include:

```text
clear field
defocus / lens fogging
smoke / fog / veil
whiteout / overexposure
specular reflection
low light / blackout
blood-like redness
anthracosis-like blackness
instrument / tissue / clot obstruction
low-information flat field
bloody but usable field
clean but not usable field
dark shadow without anthracosis
black instrument or camera border
```

## Acceptance criteria

Phase 2 is complete when:

1. `component_review_frames.csv` exists locally.
2. Each target component has high-score and low-score examples.
3. Montage sheets have been generated for each component.
4. Obvious false positives and false negatives are noted.
5. Generated data and image sheets are not committed to GitHub.
6. A branch PR documents which cases and score columns were used.

## What not to do in Phase 2

- Do not create a composite visual hazard score.
- Do not treat blood-like redness as validated blood.
- Do not treat blackness as validated anthracosis.
- Do not treat low-focus center area as validated obstruction.
- Do not start clinical outcome analysis before component behavior is understood.

## Phase 2B image-validity candidate columns

After initial montage review, use Phase 2B to add candidate-only image validity flags such as `large_whiteout_candidate_v1`, `large_blackout_candidate_v1`, `near_uniform_frame_candidate_v1`, and `color_bar_or_test_pattern_candidate_v1`. These flags are carried into the review CSV and displayed on montage sheets. They are not ground-truth labels and are not enabled as hard filters by default.

For the current `per_frame_manual_roi` input, SurgCap `OutsideBody` intervals had zero exact overlap with the metric CSV rows in the tested cases. Therefore, workflow-based extracorporeal exclusion is not part of this phase. See `PHASE_02B_IMAGE_VALIDITY_GATE.md`.

