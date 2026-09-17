# PHASE_01_PILOT_SAMPLING.md

# Phase 01B - Pilot sampling specification

**Status:** Draft v0.1
**Date:** 2026-09-17
**Purpose:** Select a small, deliberately enriched set of index moments for testing the surgeon visibility-rating instrument before the main validation study.

---

## 1. Pilot objective

The pilot is an **annotation-instrument pilot**, not a final metric-validation cohort.

It should test whether:

1. the 0-3 visibility-impairment scale is usable;
2. reviewers can separate technical invalidity from real operative-field degradation;
3. still frames provide enough task context;
4. short clips reduce context-insufficient ratings;
5. the proposed cause taxonomy is understandable and sufficiently complete;
6. annotation burden is practical.

The pilot must not be used to optimize a composite score or claim final metric performance.

---

## 2. Sampling unit

The sampling unit is an **index moment**:

```text
moment_id
case_id
sample_time_sec
```

Each selected index moment should later be represented by:

```text
1 still frame
1 short clip centered on the same index time
```

The still and clip are two media representations of the same underlying moment and must retain the same `moment_id`.

---

## 3. Sampling universes

Use two explicitly separated sampling universes.

### 3.1 Visibility-pilot universe

Source:

```text
data/derived/quality_metrics/per_frame/CASE*_frame_scores.csv
```

Eligibility:

```text
metric_status is missing OR metric_status == "ok"
```

Current audited size:

```text
519,198 frames
68 cases
```

This universe is used for all real-operative-field visibility strata.

### 3.2 Confirmed technical-failure universe

Source:

```text
the same raw per-frame metric tables before metric_status filtering
```

Eligibility:

```text
metric_status is not missing
AND
metric_status != "ok"
```

Current audited finding:

```text
CASE044
sample_time_sec = 6637
metric_status = all_zero_image
```

At present, this is the only confirmed non-ok frame identified by the Phase 00 lineage audit.

Do not manufacture additional "technical failures" by applying visibility-metric percentile thresholds.

---

## 4. Pilot target size

Target:

```text
30 unique index moments
```

This is intentionally small because the purpose is to test the rating instrument.

It is not intended to estimate population prevalence or final diagnostic performance.

---

## 5. Proposed stratum allocation

Proposed v0.1 allocation:

| Stratum | Target n |
|---|---:|
| A. Clear / low-degradation candidates | 5 |
| B. Structural-visibility-loss candidates | 5 |
| C. Veil / low-contrast candidates | 4 |
| D. Low-light / blackout candidates | 4 |
| E. Whiteout / specular candidates | 3 |
| F. Obstruction / near-contact proxy candidates | 3 |
| G. Metric-discordant / hard-negative candidates | 4 |
| H. Confirmed technical failure | 1 |
| I. Ambiguous technical-validity challenge candidate | 1 |
| **Total** | **30** |

These are **sampling strata only**.

They must never be shown to reviewers and must not be treated as reference labels.

---

## 6. General selection principles

### 6.1 Enrich across a range, not only the most extreme tail

For component-specific strata, avoid selecting only the highest-scoring frames.

Where sufficient candidates exist, sample from both:

```text
upper-tail extreme candidate:
    approximately >= p99

upper-tail non-extreme candidate:
    approximately p95 to < p99
```

This provides examples more likely to span mild, moderate, and severe impairment rather than only dramatic extremes.

The percentile labels are sampling tools only and do not define clinical severity.

### 6.2 Preserve metric independence during human review

Candidate metric values may be used to construct the sampling pool.

Reviewers must not see:

```text
metric values
percentile rank
selection stratum
selection reason
hazard flags
clinical outcomes
other reviewer ratings
```

### 6.3 Use raw component metrics where possible

Sampling should use the source per-frame component tables rather than the reduced Phase 09 frame export because the raw tables retain:

- all candidate component metrics;
- image-validity candidate columns;
- `metric_status`;
- stable frame identifiers;
- image paths.

Workflow metadata may be joined separately using audited stable keys if required for sampling audit only.

---

## 7. Stratum definitions

The exact numerical thresholds should be computed from the eligible visibility universe and written to an audit table.

### A. Clear / low-degradation candidates - n=5

Purpose:

Provide low-degradation examples and prevent the pilot from being dominated by obvious failures.

Candidate rule:

Prefer frames simultaneously in low or middle-low ranges of the major component metrics, for example:

```text
structural_visibility_loss_v1 below its median
veil_smoke_mean below its median
saturation_ratio below its median
specular_ratio below its median
low_light_or_blackout_ratio_v1 below its median
```

Additional constraints:

- `metric_status == "ok"`;
- avoid confirmed technical-validity failures;
- retain case diversity.

Do not require the old `clean_reference_candidate_*` label as a ground truth.

It may be recorded for audit comparison but should not define the human reference.

### B. Structural-visibility-loss candidates - n=5

Primary sampling metric:

```text
structural_visibility_loss_v1
```

Suggested composition:

```text
2 candidates from >= p99
3 candidates from p95 to < p99
```

Prefer candidates not all simultaneously extreme on low-light or whiteout metrics.

Purpose:

Test whether the structural proxy corresponds to human-perceived task-relevant visibility loss and expose potential false positives.

### C. Veil / low-contrast candidates - n=4

Primary sampling metric:

```text
veil_smoke_mean
```

or its research-facing alias when available:

```text
veil_low_contrast_score_v1
```

Suggested composition:

```text
2 candidates from >= p99
2 candidates from p95 to < p99
```

This is a low-contrast / veil-like candidate stratum, not a confirmed smoke/fog stratum.

### D. Low-light / blackout candidates - n=4

Primary sampling metric:

```text
low_light_or_blackout_ratio_v1
```

Suggested composition:

```text
2 candidates from >= p99
2 candidates from p95 to < p99
```

Important:

These frames remain real operative-field visibility candidates.

They must not be classified as technical failures solely because they are dark.

### E. Whiteout / specular candidates - n=3

Candidate metrics:

```text
saturation_ratio / whiteout_ratio_v1
specular_ratio / specular_like_ratio_v1
```

Suggested composition:

```text
1 high whiteout candidate
1 high specular candidate
1 additional p95-p99 candidate from either metric
```

Prefer not to select three frames from the same visual mechanism.

### F. Obstruction / near-contact proxy candidates - n=3

Candidate metrics may include:

```text
local_obstruction_ratio
center_low_structure_area_v1
focus_lost_center_weighted_ratio
```

Important:

`local_obstruction_ratio` is a legacy proxy and is not validated as physical obstruction.

This stratum should therefore be interpreted as:

```text
central low-structure / possible obstruction / possible near-contact candidate
```

not as confirmed obstruction.

### G. Metric-discordant / hard-negative candidates - n=4

Purpose:

Prevent the pilot from containing only concordant, obvious examples.

Candidate patterns may include:

```text
high single-component metric
BUT
low or non-extreme structural_visibility_loss_v1

OR

high structural_visibility_loss_v1
BUT
low values on the other photometric/veil candidate metrics

OR

high legacy hazard flag
BUT
other component metrics remain low
```

These are **metric-discordant candidates**, not pre-labeled human hard negatives.

The pilot determines whether they are true false positives, clinically meaningful impairment, or a different visibility phenotype.

### H. Confirmed technical failure - n=1

Current known candidate:

```text
CASE044
sample_time_sec = 6637
metric_status = all_zero_image
```

Purpose:

Verify that reviewers and the annotation logic treat a true technical failure differently from real operative-field degradation.

This item should be included only if the media representation can be rendered in the review tool without causing the tool itself to fail.

### I. Ambiguous technical-validity challenge candidate - n=1

Purpose:

Test whether the technical-validity definition is operationally clear.

Candidate pool:

frames with `metric_status == "ok"` but one or more image-validity candidate flags, such as:

```text
near_uniform_frame_candidate_v1
large_whiteout_candidate_v1
large_blackout_candidate_v1
color_bar_or_test_pattern_candidate_v1
photometric_failure_candidate_v1
image_validity_problem_candidate_v1
```

This item must **not** be presented as a technical failure.

It is deliberately sampled because the legacy rule-based validity flags may conflict with the new cause-based technical-validity construct.

Prefer a candidate with:

```text
metric_status == "ok"
AND
image_validity_problem_candidate_v1 == 1
```

while avoiding the confirmed all-zero frame.

---

## 8. Overlap handling

A frame may qualify for multiple strata.

The pilot must assign each selected moment exactly one `selection_stratum`.

Recommended priority for candidate assignment:

```text
H confirmed_technical_failure
I ambiguous_technical_validity
G metric_discordant
F obstruction_or_near_contact_proxy
E whiteout_or_specular
D low_light_or_blackout
C veil_or_low_contrast
B structural_visibility_loss
A clear
```

However, do not simply take the first eligible frame.

The selector should construct candidate pools first, then perform constrained sampling with case and temporal-diversity rules.

Store all qualifying strata in an audit field if useful:

```text
eligible_strata
```

while retaining one primary:

```text
selection_stratum
```

---

## 9. Case-diversity constraints

Default constraints:

```text
target maximum = 2 selected moments per case
```

Prefer one moment per case when possible.

Allow a second moment from the same case only when required to fill an otherwise underrepresented stratum.

No single case should dominate the pilot.

---

## 10. Temporal-separation constraint

For two selected moments from the same case:

```text
minimum preferred separation = 60 seconds
```

This is an operational anti-duplication rule, not a biologically validated threshold.

If a stratum cannot be filled under the 60-second rule:

1. first search additional cases;
2. then allow a shorter separation only with an explicit audit reason;
3. never allow near-identical adjacent sampled frames solely to meet the target count.

Store:

```text
temporal_separation_override
temporal_separation_override_reason
```

if an override is required.

---

## 11. Deterministic randomization

Use a fixed random seed:

```text
20260917
```

Within each eligible stratum after deterministic eligibility filtering:

1. randomize candidate order using the fixed seed;
2. apply case-cap constraints;
3. apply temporal-separation constraints;
4. fill the stratum target;
5. log rejected candidates and rejection reasons when practical.

The purpose is reproducibility, not statistical representativeness.

---

## 12. Candidate percentile calculation

Compute percentiles from the **visibility-pilot universe** only:

```text
metric_status missing or "ok"
```

Do not include confirmed non-ok technical-failure rows in the component percentile distribution.

For each sampling metric, record at minimum:

```text
n_nonmissing
p50
p95
p99
```

Optionally also record:

```text
p90
p97_5
p99_5
min
max
```

Thresholds used for sampling must be written to a versioned audit CSV.

---

## 13. Required sampling audit outputs

The future pilot-selection script should write:

### 13.1 `phase01_pilot_sampling_thresholds.csv`

Suggested columns:

```text
metric
n_nonmissing
p50
p95
p99
```

### 13.2 `phase01_pilot_candidate_pool.csv`

One row per eligible candidate before final constrained selection.

Suggested columns:

```text
case_id
sample_time_sec
image_path
metric_status
eligible_strata
candidate_metric
candidate_value
candidate_percentile_band
validity flags
```

This file is an internal audit artifact and is not shown to reviewers.

### 13.3 `phase01_pilot_items.csv`

One row per selected media item after still/clip generation.

Before media generation, a moment-level selection table may be written as:

```text
phase01_pilot_moments.csv
```

Suggested moment-level columns:

```text
moment_id
case_id
sample_time_sec
image_path
frame_idx_1based
selection_stratum
selection_metric
selection_value
selection_percentile_band
selection_reason
metric_status
eligible_strata
```

### 13.4 `phase01_pilot_sampling_summary.csv`

Suggested fields:

```text
selection_stratum
target_n
selected_n
n_unique_cases
n_with_temporal_override
```

---

## 14. Stable identifiers

At minimum retain:

```text
moment_id
case_id
sample_time_sec
image_path
metric_status
```

Also retain when available:

```text
frame_idx_1based
sample_ordinal
segment_id
ROI coordinates
```

The selector must fail explicitly if required keys are missing.

Do not create a "lean" pilot manifest that drops the stable time/frame identifier.

---

## 15. Reviewer blinding table

The full internal sampling table and reviewer-facing table must be separate.

### Internal table may contain

```text
selection_stratum
selection_metric
selection_value
percentile band
validity flags
workflow metadata
```

### Reviewer-facing table must not contain

```text
selection_stratum
selection_metric
selection_value
percentile band
hazard flags
validity-rule flags
clinical outcomes
prior reviewer labels
```

The reviewer-facing item should contain only what is needed to locate/display the media and record the rating.

---

## 16. Still / clip generation rules

For each selected moment:

### Still

Use the source frame corresponding to the index moment.

### Clip

Default pilot clip:

```text
start = sample_time_sec - 2.5 sec
end   = sample_time_sec + 2.5 sec
target duration = approximately 5 sec
```

If the index moment is near the video boundary:

- shift the window where possible;
- preserve the index moment;
- record the actual start/end times.

Do not silently replace the index moment with a different event.

---

## 17. Reviewer modality assignment

For two reviewers and 30 moments, proposed Round 1 assignment:

```text
Reviewer A:
15 still
15 clip

Reviewer B:
complementary modality for the same 30 moments
```

Thus, for each moment in Round 1:

```text
one reviewer sees still
the other reviewer sees clip
```

If a Round 2 crossover is performed after a washout interval:

```text
Reviewer A and B switch modality for every moment
item order is independently re-randomized
```

The exact washout interval should be decided and documented before Round 2.

Round 2 is useful if reviewer burden is acceptable, but the pilot may first run Round 1 to evaluate feasibility.

---

## 18. What must not be inferred from the pilot sample

Because the sample is deliberately enriched:

Do not estimate:

- prevalence of poor visibility in the cohort;
- prevalence of blood, smoke, blackout, or obstruction;
- patient-level exposure burden;
- clinical outcome association;
- final metric sensitivity/specificity from the pilot alone.

The pilot sample is designed to stress-test the annotation instrument.

---

## 19. Pre-implementation decisions

Before writing the pilot-selection script, approve or revise the following:

```text
[ ] target n = 30 moments
[ ] stratum allocation
[ ] p95-p99 and >=p99 enrichment strategy
[ ] maximum 2 moments per case
[ ] preferred 60-second within-case separation
[ ] random seed = 20260917
[ ] one confirmed technical-failure item
[ ] one ambiguous validity-challenge item
[ ] still = index frame
[ ] clip = approximately 5 seconds centered on index time
[ ] reviewer blinding rules
[ ] Round 1 complementary still/clip assignment
[ ] whether Round 2 crossover will be used
```

No pilot-selection code should be implemented until these design choices are reviewed.

---

## 20. Current recommendation

The default v0.1 recommendation is:

```text
30 unique moments
visibility candidates drawn from 519,198 metric-status-eligible frames
1 confirmed all-zero technical failure drawn separately
component enrichment using p95-p99 and >=p99 bands
max 2 moments per case
prefer >=60 sec separation within a case
fixed seed 20260917
still + 5-sec clip generated for every moment
reviewers blinded to metric-driven selection
Round 1 uses complementary still/clip assignments
```

This design deliberately separates **sampling enrichment** from **human reference labels**.
