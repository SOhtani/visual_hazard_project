# Phase 08: Color Field Phenotype Metrics

## Purpose

Phase 08 computes rule-based color field phenotype candidates on purpose-specific analyzable frames generated in Phase 07.

The goal is not to label blood, anthracosis, inflammation, or adhesions directly. The goal is to create reproducible, reviewable image-derived phenotype candidates:

- blood-like redness
- fresh-red candidate area
- dark-red/brown candidate area
- corrected blackness candidate area
- exploratory anthracosis-like blackness candidate area

These metrics are intended to be computed on `color_phenotype_analyzable_frames_v1.csv`, not on the overly strict `clean_reference_frame_p95_v1` set.

## Interpretation

The Phase 06B cutoff audit showed that p95 thresholds are too broad for hard exclusion before downstream field-phenotype analysis. Many p95-near frames remain clinically and phenotypically meaningful. Therefore:

- p95 visual hazard gate is used for clean reference extraction.
- p99 visual hazard gate is used as a severe obstruction flag.
- structural and center-low-structure p99 flags are retained as soft flags for color phenotype analysis.
- color phenotype metrics should be computed on the color phenotype analyzable set.

## Main script

```powershell
python .\scripts\13_compute_color_field_phenotypes.py `
  --frame-csv .\data\annotations\color_phenotype_analyzable_frames_v1.csv `
  --output-csv .\data\derived\field_phenotypes\per_frame\color_field_phenotypes_v1.csv `
  --report-dir .\reports\color_field_phenotypes `
  --review-csv .\data\annotations\color_field_phenotype_review_frames.csv `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --write-review-csv
```

## Smoke test

Run a smaller test before the full cohort:

```powershell
python .\scripts\13_compute_color_field_phenotypes.py `
  --frame-csv .\data\annotations\color_phenotype_analyzable_frames_v1.csv `
  --output-csv .\data\derived\field_phenotypes\per_frame\color_field_phenotypes_smoke_CASE010_CASE066.csv `
  --report-dir .\reports\color_field_phenotypes_smoke `
  --review-csv .\data\annotations\color_field_phenotype_review_frames_smoke.csv `
  --case CASE010 CASE066 `
  --max-frames-per-case 300 `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --write-review-csv
```

## Image path lookup

Phase 07 frame-set manifests may be intentionally lean and can lack `image_path` / `frame_path` columns. In that case, Phase 08 joins image path and ROI columns back from the original per-frame metric CSVs. Use:

```powershell
--metrics-dir .\data\derived\quality_metrics\per_frame
```

If the script reports that no image path column was found, inspect the input columns:

```powershell
python -c "import pandas as pd; p=r'.\data\annotations\color_phenotype_analyzable_frames_v1.csv'; df=pd.read_csv(p,nrows=1); print(df.columns.tolist())"
python -c "import pandas as pd, glob; p=glob.glob(r'.\data\derived\quality_metrics\per_frame\*.csv')[0]; df=pd.read_csv(p,nrows=1); print(p); print(df.columns.tolist())"
```

## Important manifest note

Running the Phase 07 optional `--color-exclude-whiteout-p99` command with the same `--annotation-output-dir .\data\annotations` overwrites `color_phenotype_analyzable_frames_v1.csv`. To restore the primary 99.0% color phenotype set, re-run Phase 07 without `--color-exclude-whiteout-p99`. For sensitivity outputs, use a separate annotation output directory or a copied manifest.

## Outputs

- `data/derived/field_phenotypes/per_frame/color_field_phenotypes_v1.csv`
- `reports/color_field_phenotypes/color_field_phenotype_global_thresholds.csv`
- `reports/color_field_phenotypes/case_color_field_phenotype_summary.csv`
- `reports/color_field_phenotypes/case_phase_color_field_phenotype_summary.csv`
- `reports/color_field_phenotypes/color_field_phenotype_status_summary.csv`
- `data/annotations/color_field_phenotype_review_frames.csv`

## Metrics

- `red_dominance_ratio_v1`
- `fresh_red_candidate_ratio_v1`
- `dark_red_brown_candidate_ratio_v1`
- `blood_like_redness_ratio_v1`
- `center_weighted_blood_like_redness_v1`
- `red_excess_mean_v1`
- `red_saturation_mean_v1`
- `blackness_candidate_ratio_v2`
- `corrected_blackness_candidate_ratio_v2`
- `anthracosis_like_blackness_candidate_v2`
- `center_weighted_blackness_candidate_v2`

## Review

The script can generate a review CSV compatible with the existing review sheet exporter:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\color_field_phenotype_review_frames.csv `
  --output-dir .\reports\color_field_phenotype_review_sheets `
  --draw-roi
```

ROI crop version:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\color_field_phenotype_review_frames.csv `
  --output-dir .\reports\color_field_phenotype_review_sheets_roi `
  --crop-roi
```

## Cautions

- These are color phenotype candidates, not histologic or clinical labels.
- `anthracosis_like_blackness_candidate_v2` remains exploratory without a pleura/lung/tissue mask.
- Blood-like redness can capture tissue, tumor, instrument reflections, cautery effects, and red-out. Visual review is required before clinical linkage.
