# PHASE_01_MEASUREMENT_LOCK_20260919.md

## Status

**Measurement development is closed for the current 2023 RATS exploratory analysis.**

No further threshold hunting, candidate-route tuning, or outcome-informed rule changes are permitted before the planned full-cohort burden and clinical-outcome analyses.

## Development evidence used for the lock

### Frozen surgeon-review datasets

1. 136-frame quick presence audit  
   SHA256: `879FA2C563092E63C05AE7207D8FC1A0CF7CFE2089D1F1A1BC49947C5C212C91`

2. Phase 01C v2 blinded review manifest, 72 frames  
   SHA256: `3F53812BD5FC3811AD35C01E3FD37143646597FDA410A78E3D1A79A280F562DA`

3. Phase 01C v2 selected full metadata, 72 frames  
   SHA256: `C804B8A22E4E0F4997C543156027DA904BCAF5796725B95548D4920DAEF3D14D`

4. Phase 01C v2 surgeon presence labels, 72 frames  
   SHA256: `6772083450B04847DB153A8D08F34139F1495183B6BBE422E583FB9BACCC0A12`

The 2023 cohort is therefore treated as a **measurement-development / calibration cohort**, not an independent validation cohort.

## Locked measurements for the current analysis

### 1. Structural visibility impairment — PRIMARY video measurement

Per-frame variable:

`structural_visibility_loss_v1`

This is numerically identical to historical aliases including `focus_badness_v1` / `composite_badness_v4`; aliases must not be treated as independent measurements.

Use all technically valid frames.

#### Locked case-level summaries

Primary:
- `structural_p90`

Secondary:
- `structural_median`
- `structural_fraction_ge_global_p95`
- `structural_fraction_ge_global_p99`

The global p95 and p99 thresholds are calculated once from all technically valid 2023 frames, without using clinical outcomes.

### 2. Persistent visual degradation proxy — SECONDARY technical measurement

Historical retrieval variable:

`cand_lens_persistent_degradation_proxy`

The historical candidate rule is retained exactly as previously generated. For full-cohort analysis, positive frame identity is taken from the existing v1.1 candidate-pool output; the rule is not retuned.

#### Human-audit interpretation

Across the combined 208 manually reviewed development frames:

- proxy negative: 25/120 (20.8%) had surgeon-identified lens contamination/fogging
- proxy positive: 39/88 (44.3%) had surgeon-identified lens contamination/fogging

Thus the proxy enriched surgeon-identified lens contamination by approximately 2.13-fold in the selected development sample.

**This is not an unbiased estimate of sensitivity, specificity, PPV, NPV, or diagnostic accuracy**, because the 208 frames were deliberately metric-enriched development samples.

Therefore the full-cohort variable must be named and interpreted as:

`persistent_degradation_proxy_v1`

Acceptable description:
> a persistent visual-degradation proxy enriched for surgeon-identified lens contamination/fogging in development review.

Do **not** call every proxy-positive frame "lens contamination."

#### Locked case-level summaries

Primary:
- `persistent_degradation_fraction`

Secondary:
- `persistent_degradation_total_seconds`
- `persistent_degradation_episode_count`
- `persistent_degradation_max_episode_seconds`

Episodes are defined by consecutive positive 1-second samples, with an observed inter-frame time gap <= 1.5 s.

## Constructs NOT locked for full-cohort semantic phenotype analysis

The following are not used as semantic frame-level phenotypes in the current outcome analysis:

- Blood
- Smoke / airborne veil
- Near-contact / wall view
- Glare
- Whiteout / overexposure
- Underexposure / blackout
- Physical obstruction

Reason: prospective targeted retrieval did not provide sufficient specificity to justify labeling full-cohort frames with these semantic constructs.

Existing color, brightness, veil, low-structure, and specular metrics may remain available as technical descriptors, but they are not renamed as validated clinical phenotypes.

### Blood-specific negative finding

Color-only redness metrics were insufficiently specific for blood in thoracic surgical video. In the Phase 01C v2 review, the union of BL-A through BL-E routes contained:

- blood: 3/36
- non-blood fluid: 11/36
- lens contamination/fogging: 14/36

Therefore color-only blood labeling is not propagated to the full cohort.

### Smoke-specific negative finding

The union of SM-A through SM-C routes contained only 2 surgeon-confirmed smoke frames among 26 selected route-positive frames. Smoke is therefore not propagated as a semantic full-cohort phenotype.

### Near-contact-specific negative finding

The union of NC-A through NC-C routes contained 11 surgeon-confirmed near-contact frames among 40 selected route-positive frames. This showed enrichment but insufficient specificity for a locked binary semantic detector in the current analysis.

## Surgical-context integration

### Workflow level 0

Not used for phase analysis.

Observed coverage in the 514,006-frame metadata table:
- non-null: 2 frames
- only observed label: `OutsideBody`

### Workflow level 1 — PHASE

Use `workflow_level1_label`.

Coverage:
- 494,653 / 514,006 frames (96.2%) non-null
- 6 observed labels

Use the labels exactly as stored. Do not rename or reinterpret them during the current analysis.

### Workflow level 2 — WORKSPACE / FIELD

Use `workflow_level2_label`.

Coverage:
- 320,873 / 514,006 frames (62.4%) non-null
- 9 observed labels

Use only frames with non-null workspace labels for workspace-specific analyses.

The missing workspace labels are not imputed.

### Context-table limitation

Workflow context is currently available through the 514,006-frame purpose-specific metadata table. Full-cohort case-level structural burden uses all technically valid frames; phase/workspace analyses use the subset with available workflow labels.

## Clinical-outcome analysis lock

Primary clinical outcomes:
1. operative time
2. blood loss

Primary video predictor:
- `structural_p90`

Secondary video predictors:
- `structural_fraction_ge_global_p95`
- `structural_fraction_ge_global_p99`
- `persistent_degradation_fraction`

Additional episode summaries are descriptive / secondary.

No video threshold or phenotype definition may be changed after inspecting its association with operative time or blood loss.

## Interpretation boundary

The current analysis is:
- measurement-development
- feasibility
- exploratory clinical association

It is not:
- independent validation
- causal inference
- a validated diagnostic detector for lens contamination, blood, smoke, or near-contact
- a clinical prediction model

A separate patient-level cohort not used in this development process is required for independent validation.
