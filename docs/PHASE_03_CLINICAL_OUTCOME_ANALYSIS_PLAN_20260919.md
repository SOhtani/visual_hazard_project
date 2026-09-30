# PHASE_03_CLINICAL_OUTCOME_ANALYSIS_PLAN_20260919.md

## Status

Measurement definitions are locked before inspecting clinical outcome associations.

## Cohort

- Video-analysis cohort: cases present in `locked_case_level_video_burden_2023.csv`
- Clinical metadata source: `master_case_inventory_2021_2025_with_metadata.csv`
- Merge key: `case_id`
- The locked video cohort defines inclusion for this analysis; the metadata file is used only to attach clinical variables.

## Locked video predictors

### Primary
- `structural_p90`

### Secondary
- `structural_fraction_ge_global_p95`
- `structural_fraction_ge_global_p99`
- `persistent_degradation_fraction`

Episode summaries are descriptive secondary variables and are not used to select or retune the measurement definition.

## Locked clinical outcomes

### Primary clinical outcomes
- `operation_time_min`
- `blood_loss_g`

## Covariates for small adjusted models

- `procedure_group`
- `side`

Each video predictor is entered in a separate adjusted model to avoid overfitting the small cohort.

## Statistical analysis

1. Cohort/merge QC.
2. Descriptive statistics of video predictors and outcomes.
3. Spearman rank correlation for each locked predictor with each outcome.
4. Adjusted models:
   - operative time: OLS with HC3 robust standard errors.
   - blood loss: OLS on `log1p(blood_loss_g)` with HC3 robust standard errors.
   - predictor standardized to 1 SD.
   - adjustment for procedure group and side.
5. Primary inference is centered on `structural_p90`.
6. Secondary predictor analyses are exploratory.
7. No threshold, phenotype definition, or predictor is modified after viewing outcome associations.

## Surgical-context analyses

Workflow and workspace results are descriptive secondary analyses.

- Phase: summarize the distribution of case-level video burden within each `workflow_level1_label`.
- Workspace: summarize the distribution within each non-null `workflow_level2_label`.
- No missing workflow/workspace labels are imputed.
- No frame-level p-values are used because frames within a patient are not independent.

## Interpretation

This is a development / feasibility / exploratory-association analysis, not independent validation or causal inference.
