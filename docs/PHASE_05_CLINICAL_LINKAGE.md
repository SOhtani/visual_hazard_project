# Phase 05: Clinical Linkage Table

## Purpose

Phase 05 converts the Phase 04 visual-hazard burden outputs into a case-level analysis table that can be linked to clinical and procedural variables.

The goal is not to claim causality or define a final clinical cutoff. The immediate goal is to prepare an exploratory, auditable table for:

- operation time versus visual hazard burden
- blood loss versus visual hazard burden
- procedure group differences
- side / target differences
- phase-specific burden summaries
- sensitivity comparison of p95 and p99 hazard thresholds

## Inputs

Default burden inputs:

```text
reports/visual_hazard_burden/case_visual_hazard_burden_summary.csv
reports/visual_hazard_burden/case_phase_visual_hazard_burden_summary.csv
```

Expected optional clinical metadata input:

```text
C:\Users\SOhtani2024\SurgCap\RATS_2021_2025_data\index\master_case_inventory_2021_2025_with_metadata.csv
```

If the metadata path changes, pass the correct path using `--metadata`.

## Core command

```powershell
python .\scripts\10_build_clinical_linkage_table.py `
  --burden-summary .\reports\visual_hazard_burden\case_visual_hazard_burden_summary.csv `
  --phase-burden-summary .\reports\visual_hazard_burden\case_phase_visual_hazard_burden_summary.csv `
  --metadata "C:\Users\SOhtani2024\SurgCap\RATS_2021_2025_data\index\master_case_inventory_2021_2025_with_metadata.csv" `
  --output-dir .\reports\clinical_linkage
```

If case-column detection fails, add:

```powershell
  --metadata-case-col case_id
```

or replace `case_id` with the actual case identifier column.

## Outputs

```text
reports/clinical_linkage/case_visual_hazard_clinical_linkage.csv
reports/clinical_linkage/case_id_merge_audit.csv
reports/clinical_linkage/hazard_column_inventory.csv
reports/clinical_linkage/clinical_numeric_column_inventory.csv
reports/clinical_linkage/numeric_spearman_correlations.csv
reports/clinical_linkage/group_burden_summary.csv
reports/clinical_linkage/top_cases_by_primary_burden_metrics.csv
reports/clinical_linkage/level1_phase_burden_wide.csv
```

## Interpretation

`visual_hazard_any_p95` is a broad bad-image candidate gate. It is appropriate for excluding non-clean frames when building a clean/reference frame set.

`visual_hazard_any_p99` is a stricter severe visual hazard candidate. It is more appropriate for sensitivity analysis against clinical outcomes.

For clinical linkage, do not discard visual hazard frames. Count them as burden:

- seconds above threshold
- fraction above threshold
- maximum consecutive seconds above threshold
- phase-specific burden

## Current status of legacy badness

The previous `composite_degradation_score` / badness-like value is currently treated as a legacy alias of `structural_visibility_loss_v1`, not as an independent composite score. A new composite should only be built after component-level validation and clinical linkage checks.
