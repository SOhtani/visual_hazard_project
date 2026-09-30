# Phase 01 Metric Alias Registry

**Status:** frozen lineage note after full-dataset audit  
**Date:** 2026-09-18

## Scope

The Phase 01 full-dataset alias audit scanned all CSV files under:

`data/derived/quality_metrics/per_frame`

For the analyzable per-frame dataset, 68 CSV files contained each audited pair, covering **519,198 nonmissing rows**.  
For every audited pair:

- NaN-pattern mismatches: 0
- exact-value mismatches: 0
- allclose mismatches: 0
- maximum absolute difference: 0.0

Therefore, within the 519,198 analyzable per-frame rows, the following columns are **exact numerical aliases**, not independent metrics.

## Frozen equivalence classes

### A. Focus / structural-loss lineage

**Canonical analysis name:** `focus_badness_v1`

Exact aliases:
- `structural_visibility_loss_v1`
- `composite_badness_v4`

Interpretation rule:
- Treat these as one feature in all future analyses.
- Do not report correlations or model contributions from these aliases as independent evidence.
- `structural_visibility_loss_v1` is a legacy semantic alias and should not be interpreted as a separately validated global visibility metric.
- `composite_badness_v4` is not an independent composite in the current exported data.

### B. Low-structure-area lineage

**Canonical analysis name:** `center_low_structure_area_v1`

Exact alias:
- `local_obstruction_ratio`

Interpretation rule:
- Treat these as one feature.
- `local_obstruction_ratio` is a legacy semantic proxy name.
- Do not describe this value as direct semantic detection of instrument/tissue/gauze obstruction.
- Human physical-obstruction correspondence remains a calibration finding, not proof that the metric identifies the obstructing object.

### C. Reblur-response lineage

**Canonical analysis name:** `reblur_response_loss_v1`

Exact alias:
- `blur_like_mean`

Interpretation rule:
- Treat these as one feature.
- This feature is distinct from `focus_badness_v1`.
- In the Phase 01 calibration pilot, its rank correspondence with human blur impairment was poor; this does not justify deleting the historical column.

### D. Saturation / whiteout lineage

**Canonical analysis name:** `saturation_ratio`

Exact alias:
- `whiteout_ratio_v1`

Interpretation rule:
- Treat these as one feature.
- The metric measures the implemented saturation/whiteout-like photometric phenotype; it is not automatically equivalent to surgeon-rated whiteout severity.

### E. Specularity lineage

**Canonical analysis name:** `specular_ratio`

Exact alias:
- `specular_like_ratio_v1`

Interpretation rule:
- Treat these as one feature.
- Surgeon-rated glare/specular impairment remains a separate human construct.

### F. Veil / low-contrast lineage

**Canonical analysis name:** `veil_low_contrast_score_v1`

Exact alias:
- `veil_smoke_mean`

Interpretation rule:
- Treat these as one feature.
- Prefer the low-contrast/veil terminology in future analyses.
- Do not label this as a validated smoke detector.
- Phase 01 calibration showed little rank correspondence with surgeon-rated smoke/fog/veil impairment.

## Analysis policy

1. Historical CSVs are immutable. Do **not** delete or overwrite legacy alias columns.
2. New analysis code should use only one canonical column from each equivalence class.
3. Legacy aliases may be retained for provenance and backwards compatibility.
4. Any table, figure, model, or statistical analysis must avoid entering exact aliases together as separate predictors.
5. Manuscripts and reports must not present exact aliases as independent metrics or independent validation results.
6. Canonicalization is an analysis-layer rule; it does not alter historical outputs.

## Phase 01 calibration implications

The following previously calculated associations share the same underlying feature and must not be interpreted as independent findings:

- `structural_visibility_loss_v1` vs Overall
- `focus_badness_v1` vs Blur
- `composite_badness_v4` vs Overall

Likewise:

- `center_low_structure_area_v1` vs Overall
- `local_obstruction_ratio` vs Physical obstruction

are analyses of the same numerical feature against different human constructs.

## Outstanding audit item

The recursive directory scan found 69 CSV files, while 68 contained each audited metric pair.  
Those 68 files contained all **519,198 analyzable nonmissing rows** used in the alias comparison.

The remaining CSV should be identified for provenance completeness, but it does not change the exact-alias conclusion for the 519,198 analyzable per-frame rows.

## Next step

Before targeted calibration sampling:

1. identify the one CSV lacking the audited pair columns;
2. update metric documentation to mark legacy aliases explicitly;
3. update future analysis scripts to reference canonical columns only;
4. then design targeted positive sampling for constructs with insufficient human severity range.
