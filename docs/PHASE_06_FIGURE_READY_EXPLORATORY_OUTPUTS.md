# Phase 06: Figure-ready exploratory outputs

## Purpose

Phase 06 converts the case-level clinical linkage table into compact, figure-ready exploratory outputs.

This phase is intentionally descriptive. It is not a final statistical inference layer. The goal is to produce clean tables and simple plots for checking whether video-derived visual hazard burden has clinically interpretable relationships with operation time, blood loss, age, procedure, side, and target anatomy.

## Starting point

Expected input:

```text
reports/clinical_linkage_clean/case_visual_hazard_clinical_linkage.csv
```

This table should already contain:

- case-level visual hazard burden
- p95 broad hazard gate
- p99 severe hazard gate
- clinical metadata
- level-1 phase burden summaries

## Why this phase exists

Earlier correlation outputs could include metadata-derived numeric columns such as case IDs, availability flags, or audit flags. These are not clinical endpoints. Phase 06 uses an explicit clinical-variable whitelist so exploratory correlations focus on interpretable variables.

Default clinical variables:

```text
operation_time_min
blood_loss_g
age
```

Default core hazard variables:

```text
frac_visual_hazard_any_p95
frac_visual_hazard_any_p99
seconds_visual_hazard_any_p95
seconds_visual_hazard_any_p99
max_consecutive_seconds_visual_hazard_any_p95
max_consecutive_seconds_visual_hazard_any_p99
```

Default grouping variables:

```text
procedure_group
side
sex
target_lobe_or_segment
```

## Run

```powershell
python .\scripts\11_make_figure_ready_exploratory_outputs.py `
  --linkage-csv .\reports\clinical_linkage_clean\case_visual_hazard_clinical_linkage.csv `
  --output-dir .\reports\figure_ready_exploration `
  --clinical-col operation_time_min blood_loss_g age `
  --make-plots
```

## Outputs

```text
reports/figure_ready_exploration/primary_clinical_hazard_spearman.csv
reports/figure_ready_exploration/core_clinical_hazard_spearman.csv
reports/figure_ready_exploration/group_burden_summary_whitelist_long.csv
reports/figure_ready_exploration/top_cases_by_figure_metric.csv
reports/figure_ready_exploration/requested_column_inventory.csv
reports/figure_ready_exploration/figure_manifest.csv
reports/figure_ready_exploration/scatter_plots/*.png
reports/figure_ready_exploration/boxplots/*.png
```

## Interpretation rules

### Seconds vs fractions

Hazard seconds and hazard fractions answer different questions.

```text
seconds_*:
  total visual hazard burden; affected by operation/video duration

frac_*:
  normalized visual hazard burden; proportion of analyzed frames that are hazard-positive
```

In current exploratory results, operation time is expected to correlate more with hazard seconds than with hazard fractions. This is not a failure. It means total burden and normalized field quality should be analyzed separately.

### p95 vs p99

```text
p95:
  broad visual hazard burden; useful for clean/reference frame exclusion and sensitive screening

p99:
  severe visual hazard burden; useful for stricter exploratory clinical linkage
```

### Do not overinterpret group summaries

Group summaries are descriptive. Some target-anatomy groups are small. Use these outputs to decide which contrasts are worth formal testing, not to make definitive claims.

## Next step after Phase 06

Phase 07 should add a phenotype-specific module, starting with blood-like redness.

The current visual hazard gate is good at identifying poor visibility, but it does not directly measure bleeding, inflammation, adhesions, smoking-related anthracosis, or post-treatment field changes. These require additional phenotype-specific components.
