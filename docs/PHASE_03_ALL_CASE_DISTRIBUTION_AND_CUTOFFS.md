# Phase 3: All-case component distributions and candidate cutoffs

## Purpose

Phase 3 applies the current component metric set to all available cases and summarizes score distributions by case and SurgCap workflow phase.

This phase is exploratory. It should not define final clinical cutoffs. The immediate goal is to understand:

1. which metrics have usable dynamic range,
2. how metrics differ by case and workflow phase,
3. whether candidate cutoffs such as global p95/p99 behave sensibly,
4. how legacy badness-like values relate to component-specific metrics.

## Metric policy

The Phase 3 default component set excludes `anthracosis_like_blackness_candidate` from the default review/analysis target list. Anthracosis-specific quantification is deferred until a lung or pleural-surface mask is available.

The current default analysis set is:

```text
Tier 1 main candidates:
  structural_visibility_loss_v1
  center_low_structure_area_v1
  whiteout_ratio_v1
  low_light_or_blackout_ratio_v1

Tier 2 auxiliary descriptors:
  reblur_response_loss_v1
  veil_low_contrast_score_v1
  blackness_raw_ratio_v1
  blackness_corrected_ratio_v1

Tier 3 reconsider / redesign:
  specular_like_ratio_v1
```

`blackness_raw_ratio_v1` and `blackness_corrected_ratio_v1` remain generic blackness descriptors only. They should not be interpreted as pleural anthracosis.

## Legacy badness position

Legacy badness-like values should be retained only as screening and continuity variables.

In the current scaffold, `composite_degradation_score`, `composite_badness_v3`, and `composite_badness_v4` are aliases of `focus_badness_v1` / `structural_visibility_loss_v1`. They are not independent composite scores.

Recommended interpretation:

```text
component metrics:
  explain what type of visual hazard is present

legacy badness-like score:
  ranks visually poor frames or segments for screening
  should not be treated as final clinical endpoint
```

If summarized, use `--include-legacy-badness` and interpret it as `legacy_badness_alias`.

## Generated outputs

`scripts/08_summarize_phase_component_distributions.py` writes:

```text
reports/phase_component_distributions/component_metric_metadata.csv
reports/phase_component_distributions/global_component_candidate_cutoffs.csv
reports/phase_component_distributions/phase_component_candidate_cutoffs.csv
reports/phase_component_distributions/case_component_distribution_summary.csv
reports/phase_component_distributions/case_phase_component_distribution_summary.csv
reports/phase_component_distributions/image_validity_flag_summary.csv
reports/phase_component_distributions/component_spearman_correlation.csv
```

These outputs are local analysis files and should not be committed to GitHub.

## Recommended workflow

### 1. Recompute all-case metrics

Omit `--case` to process all case CSVs present in `per_frame_manual_roi`.

```powershell
python .\scripts\05_compute_frame_visual_hazard_components.py `
  --per-frame-input-dir "C:\Users\SOhtani2024\rats_visibility_study\data\derived\quality_metrics\per_frame_manual_roi" `
  --per-frame-output-dir .\data\derived\quality_metrics\per_frame `
  --overwrite
```

If runtime is a concern, first run a small case subset.

```powershell
python .\scripts\05_compute_frame_visual_hazard_components.py `
  --per-frame-input-dir "C:\Users\SOhtani2024\rats_visibility_study\data\derived\quality_metrics\per_frame_manual_roi" `
  --per-frame-output-dir .\data\derived\quality_metrics\per_frame `
  --case CASE003 CASE010 `
  --overwrite
```

### 2. Summarize distributions with workflow phases

```powershell
python .\scripts\08_summarize_phase_component_distributions.py `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --annotation-root "C:\Users\SOhtani2024\SurgCap\surgcap-project\data\raw\videos" `
  --output-dir .\reports\phase_component_distributions `
  --include-legacy-badness
```

This assigns SurgCap `Level-1` and `Level-2` labels when matching annotation JSONs are available.

### 3. Inspect candidate cutoffs

```powershell
python -c "import pandas as pd; p=r'.\reports\phase_component_distributions\global_component_candidate_cutoffs.csv'; df=pd.read_csv(p); print(df[['component','score_col','tier','quantile_name','threshold_value','n_frames']].to_string(index=False))"
```

### 4. Inspect phase-level distributions

```powershell
python -c "import pandas as pd; p=r'.\reports\phase_component_distributions\case_phase_component_distribution_summary.csv'; df=pd.read_csv(p); keep=df[(df['phase_level']=='Level-1') & (df['component'].isin(['structural_visibility_loss','whiteout','low_light_or_blackout']))]; print(keep[['case_id','phase_label','component','n_frames','mean','p95','p99','frac_ge_global_p95','seconds_ge_global_p95']].head(80).to_string(index=False))"
```

### 5. Inspect metric redundancy

```powershell
python -c "import pandas as pd; p=r'.\reports\phase_component_distributions\component_spearman_correlation.csv'; df=pd.read_csv(p); print(df.to_string(index=False))"
```

## Cutoff interpretation

Candidate cutoffs should be described as distribution-based candidates, not optimal cutoffs.

Recommended candidate families:

```text
global p95 / p99:
  good for cross-case rare-event burden

phase-specific p95 / p99:
  useful when phases have different baseline visual properties

visual-review threshold:
  candidate threshold refined by montage review

clinical-linked threshold:
  future threshold selected against surgeon ratings or clinical events
```

Do not select a final cutoff from distribution alone.

## Next decision point

After Phase 3 summaries are generated, decide whether the first clinical/expert review should use:

1. Tier 1 metrics only,
2. Tier 1 plus selected Tier 2 metrics,
3. a legacy badness-like screening index to find candidate segments, followed by component-specific explanation.

The default recommendation is option 3 for triage and option 1/2 for interpretation.
