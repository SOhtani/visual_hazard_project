# PHASE_01C_TARGETED_RETRIEVAL_V2_PLAN.md

## Purpose

Phase 01C is the final **measurement-development** step before the phenotype definitions are locked and applied to the full 2023 cohort.

The goal is not to optimize every possible visual-quality construct. The goal is to obtain enough human-confirmed examples to lock a defensible measurement workflow for the phenotypes that are sufficiently supported by the current data and then move to full-video temporal/phase aggregation and exploratory clinical-outcome analysis.

## Scope freeze for the 2-week analysis

### Advance now
1. **Lens contamination / lens fogging**
   - Existing persistent-degradation retrieval retained.
   - No new candidate search required unless later calibration reveals a clear gap.

2. **Near-contact / wall view**
   - Human-confirmed positives: 19 frames / 17 cases in the 136-frame development audit.
   - Existing near-contact retrieval was weak, but reverse audit showed a consistent static signal:
     - low `roi_edge_density_v1`
     - high `focus_badness_v1`
     - high `local_obstruction_max_component_ratio`
     - high `center_low_structure_area_v1`
   - Build v2 candidate routes from these signals.

3. **Smoke / airborne veil**
   - Human-confirmed positives: 10 frames / 8 cases.
   - Existing temporal retrieval was weak.
   - Reverse audit supported:
     - high `veil_low_contrast_score_v1`
     - positive frame-to-frame veil increase
   - Build simpler v2 routes instead of stacking many conditions.

4. **Blood / fluid**
   - Human-confirmed positives: 16 frames / 15 cases.
   - Full 2023 color metrics already computed for 514,006 frames.
   - Reverse audit showed strongest descriptive separation for `red_saturation_mean_v1`, with supporting information from red-excess, fresh-red, dark-red/brown and broad-redness metrics.
   - Build multiple blood-candidate routes plus a redness-only challenge route.
   - In the next review, split **blood** from **non-blood fluid** prospectively.

### Do not optimize now
- Glare/specular reflection as a standalone clinical phenotype
- Whiteout/overexposure as a standalone clinical phenotype
- Underexposure/blackout as a standalone clinical phenotype
- Physical obstruction as a standalone static-frame phenotype
- Inflammation, adhesion, anthracosis and difficult-dissection phenotypes

These remain future or context-dependent constructs. Their existing numeric descriptors may still be retained as photometric/technical variables.

## Previously reviewed frames

New v2 sampling must exclude:
- the original 30-frame pilot moments, if supplied;
- all 136 frames from the completed quick-presence audit.

No previously reviewed frame may be presented as a new v2 candidate.

## Retrieval v2

### Near-contact routes

**NC-A — very low edge density**
- `roi_edge_density_v1 <= cohort q01`

**NC-B — low edge + high focus-badness**
- `roi_edge_density_v1 <= q05`
- `focus_badness_v1 >= q95`

**NC-C — low edge + large low-structure component**
- `roi_edge_density_v1 <= q05`
- `local_obstruction_max_component_ratio >= q95`

`center_low_structure_area_v1` is retained in the audit table but is not required in every route. Temporal abruptness is not a mandatory criterion in v2.

### Smoke routes

A transparent frame-to-frame quantity is computed within each case:

`veil_delta_prev = veil_low_contrast_score_v1(t) - veil_low_contrast_score_v1(t-1)`

**SM-A — very high veil**
- `veil_low_contrast_score_v1 >= q99`

**SM-B — high veil + positive temporal rise**
- `veil_low_contrast_score_v1 >= q95`
- `veil_delta_prev >= q95`

**SM-C — extreme positive temporal rise**
- `veil_delta_prev >= q99`

These are candidate-retrieval routes, not a smoke detector.

### Blood/fluid routes

Thresholds are calculated in the 514,006-frame color-analyzable cohort.

**BL-A — red saturation extreme**
- `red_saturation_mean_v1 >= q99`

**BL-B — red excess extreme**
- `red_excess_mean_v1 >= q99`

**BL-C — fresh-red extreme**
- `fresh_red_candidate_ratio_v1 >= q99`

**BL-D — dark-red/brown extreme**
- `dark_red_brown_candidate_ratio_v1 >= q99`

**BL-E — multi-feature high**
- at least 3 of the four metrics above are `>= q95`

**BL-HN — redness-only challenge**
- `blood_like_redness_ratio_v1 >= q99`
- and not positive for BL-A through BL-E

BL-HN is **not presumed to be a true negative**. It is a deliberately difficult redness-only candidate route intended to expose normal red tissue or other non-blood causes of broad redness.

## Sampling design

Default internal audit sample:
- 6 candidates per retrieval route
- global maximum 2 selected moments per case
- minimum 60 s between selected moments from the same case
- deterministic random seed
- duplicate frame removal across routes

With 12 retrieval routes, this yields at most 72 newly reviewed frames before route overlap and case/time restrictions. The final count is allowed to be smaller.

This is a retrieval-development sample, not an unbiased prevalence or accuracy sample.

## V2 review labels

The next quick review remains presence-based and blinded to retrieval route.

Minimum prospective labels:
- Near-contact / wall view: present / absent / uncertain
- Smoke / airborne veil: present / absent / uncertain
- Blood: present / absent / uncertain
- Non-blood fluid: present / absent / uncertain
- Lens contamination/fogging: present / absent / uncertain
- Non-standard imaging mode: yes / no
- Optional comment

No 0-3 visibility severity scoring is added during this retrieval audit.

## Decision / stop rules

After the v2 quick audit:

1. Do not continue threshold hunting if the new routes provide enough additional human-confirmed examples for calibration.
2. Retain the best-performing **retrieval routes**, but do not call their descriptive fractions validation precision.
3. Build one targeted calibration set from:
   - existing human-confirmed examples from the 136-frame audit;
   - new v2 human-confirmed examples;
   - deliberate hard/challenge negatives.
4. Perform detailed 0-3 annotation only on that frozen calibration set.
5. Lock the measurement definition by Day 4 of the 2-week schedule.
6. After lock, do not alter thresholds/rules in response to full-cohort outcome associations.

## Two-week milestone

- Days 1-3: finish v2 retrieval audit + targeted calibration
- Day 4: measurement lock
- Days 5-8: full-video application, temporal episodes, phase/workspace and case-level aggregation
- Days 9-12: clinical metadata merge and exploratory outcome analyses
- Days 13-14: sensitivity analyses, figures, tables and interpretation

The 2023 cohort is treated as the measurement-development/calibration cohort. A genuinely independent patient-level validation cohort is reserved for later work and must not be represented as already completed.
