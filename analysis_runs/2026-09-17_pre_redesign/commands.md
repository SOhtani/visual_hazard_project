# Analysis commands

## Phase 08 smoke test that reproduced successfully

Source commit:
640f779f27da2970832c42e0c9e538b78608884d

Input:
data/annotations/color_phenotype_analyzable_frames_v1_full_metadata.csv

Command:

python .\scripts\13_compute_color_field_phenotypes.py `
  --frame-csv .\data\annotations\color_phenotype_analyzable_frames_v1_full_metadata.csv `
  --output-csv .\data\derived\field_phenotypes\per_frame\color_field_phenotypes_smoke_CASE010_CASE066_full_metadata.csv `
  --report-dir .\reports\color_field_phenotypes_smoke_full_metadata `
  --review-csv .\data\annotations\color_field_phenotype_review_frames_smoke_full_metadata.csv `
  --case CASE010 CASE066 `
  --max-frames-per-case 300 `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --write-review-csv

Result:
PASS, exit code 0.

## Known failing historical command

Using color_phenotype_analyzable_frames_v1.csv as --frame-csv fails because that lean manifest lacks sample_time_sec and frame_index.

This is retained intentionally as a provenance finding rather than silently corrected.
