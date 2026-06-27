# Phase 05B: Clean Clinical Correlation

## Purpose

Phase 05B corrects the clinical correlation workflow so that visual-hazard-derived columns are not treated as clinical numeric variables. The Phase 05 linkage table is valid, but the initial `numeric_spearman_correlations.csv` included hazard-vs-hazard self-correlations because the merged table contains both clinical metadata and visual hazard burden columns.

## Change

`10_build_clinical_linkage_table.py` now restricts clinical numeric variable detection to metadata-derived columns and excludes visual-hazard-derived names such as:

- `visual_hazard`
- `clean_reference`
- `structural_visibility_loss`
- `center_low_structure_area`
- `whiteout`
- `low_light`
- `blackout`
- `composite_degradation`

The correlation table should now represent:

```text
clinical variable x visual hazard burden variable
```

not:

```text
visual hazard burden variable x visual hazard burden variable
```

## Recommended interpretation

For clinical linkage, duration-based burden and fraction-based burden answer different questions.

- `seconds_visual_hazard_any_p95`: total burden duration; expected to correlate partly with operation time.
- `frac_visual_hazard_any_p95`: proportion of analyzed operative frames with visual hazard; less directly confounded by case duration.
- `seconds_visual_hazard_any_p99`: severe visual hazard duration.
- `frac_visual_hazard_any_p99`: severe visual hazard proportion.
- `max_consecutive_seconds_visual_hazard_any_p95/p99`: longest continuous hazard segment.

Initial one-off checking suggested that operation time correlated more with hazard seconds than with hazard fraction, which is consistent with duration confounding. Therefore, seconds and fractions should both be reported.

## Example command

```powershell
python .\scripts\10_build_clinical_linkage_table.py `
  --burden-summary .\reports\visual_hazard_burden\case_visual_hazard_burden_summary.csv `
  --phase-burden-summary .\reports\visual_hazard_burden\case_phase_visual_hazard_burden_summary.csv `
  --metadata "C:\Users\SOhtani2024\SurgCap\RATS_2021_2025_data\index\master_case_inventory_2021_2025_with_metadata.csv" `
  --output-dir .\reports\clinical_linkage_clean `
  --clinical-col operation_time_min blood_loss_g age
```

## Main output

```text
reports\clinical_linkage_clean\numeric_spearman_correlations.csv
```

This file should now start with clinical columns such as `operation_time_min`, `blood_loss_g`, and `age`, not visual-hazard columns.
