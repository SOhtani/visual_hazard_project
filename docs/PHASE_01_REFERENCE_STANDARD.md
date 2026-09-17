# PHASE_01_REFERENCE_STANDARD.md

# Phase 01 - Surgeon reference standard for task-relevant operative-field visibility

**Status:** Draft v0.1
**Date:** 2026-09-17
**Project:** RATS / VATS operative-field visibility measurement
**Current stage:** Reference-standard design before metric validation

---

## 1. Purpose

The purpose of Phase 01 is to define an independent surgeon reference standard for **task-relevant operative-field visibility impairment** before further metric tuning, threshold selection, temporal burden construction, or clinical outcome analysis.

The primary measurement question is:

> **Do image-derived metrics correspond to thoracic surgeons' judgment of impairment of task-relevant operative-field visibility?**

The first report is therefore a **measurement-validity study**.

It is not yet intended to establish:

- patient risk;
- surgical safety;
- causal clinical effects;
- task-critical hazard burden;
- outcome prediction;
- a composite visual-hazard score.

---

## 2. Primary construct

### 2.1 Task-relevant operative-field visibility impairment

**Operational definition**

> The degree to which visual information required to identify and follow the target structure, relevant boundary, or surgical landmark for the current operative task is degraded.

The construct is not equivalent to aesthetic image cleanliness.

A field may contain blood, smoke, dark tissue, instruments, or other visually prominent features without causing meaningful visibility impairment. Conversely, visibility may be severely impaired without obvious blood contamination.

The primary human reference label must therefore measure **visibility impairment**, not the presence of a specific visual phenomenon.

---

## 3. Construct separation

Three distinct concepts must remain separate throughout annotation and downstream analysis.

### 3.1 Technical image validity

Technical image validity concerns acquisition, decoding, rendering, or data failures that make an item unsuitable for visibility assessment.

Examples include:

- all-zero image;
- corrupt or unreadable frame;
- decoder failure;
- no-signal image;
- test pattern or color bar;
- other demonstrable data-acquisition or rendering failure.

A clinically dark, bloody, blurred, occluded, or near-contact operative field is **not automatically technically invalid**.

### 3.2 Visual degradation / visibility impairment

This is the primary measurement construct.

Candidate causes include:

- blur or defocus;
- smoke, fog, or veil-like low contrast;
- blood or fluid contamination;
- glare or overexposure;
- underexposure or blackout;
- instrument or tissue obstruction;
- lens contamination;
- near-contact or red-out;
- other visual degradation.

These are real intraoperative field states and should generally remain eligible for visibility assessment.

### 3.3 Purpose-specific analyzability

Purpose-specific analyzability is a downstream analytic decision.

Examples include:

- technical analyzability;
- visibility-validation analyzability;
- color-phenotype analyzability;
- structural-phenotype analyzability;
- clean-reference eligibility.

Purpose-specific exclusions must not redefine technical validity.

---

## 4. Review decision sequence

Each review item should be evaluated in the following order.

```text
1. technical_evaluable?
        |
        +-- no --> record technical_issue
        |          visibility_impairment = NA
        |
        +-- yes
              |
              v
2. task_context_sufficient?
        |
        +-- no --> visibility_impairment = NA
        |          record comment if useful
        |
        +-- yes
              |
              v
3. visibility_impairment = 0 / 1 / 2 / 3
              |
              v
4. predominant impairment cause(s)
              |
              v
5. confidence
```

This sequence is mandatory.

A reviewer must not assign a severe visibility score simply because the task context is unclear.

---

## 5. Primary annotation fields

### 5.1 `technical_evaluable`

Binary.

| Value | Definition |
|---|---|
| 1 | The media item is technically interpretable and can be visually assessed. |
| 0 | Acquisition, decoding, rendering, or data failure prevents meaningful assessment. |

If `technical_evaluable = 0`, `visibility_impairment` must be missing.

### 5.2 `technical_issue`

Applicable when `technical_evaluable = 0`.

Recommended categories:

```text
all_zero_image
corrupt_or_unreadable
decoder_or_render_failure
no_signal
test_pattern_or_color_bar
other_technical_failure
uncertain_technical_failure
```

### 5.3 `task_context_sufficient`

Binary.

| Value | Definition |
|---|---|
| 1 | The media item provides enough operative context to judge task-relevant visibility. |
| 0 | The media item is technically viewable, but the current task or relevant target cannot be determined well enough to rate task-relevant visibility. |

If `task_context_sufficient = 0`, `visibility_impairment` must be missing.

This field is intentionally separate from technical evaluability.

### 5.4 `visibility_impairment`

Primary ordinal reference label.

| Score | Label | Operational anchor |
|---:|---|---|
| 0 | None | The target structure, relevant boundary, or surgical landmark required for the current task can be identified clearly enough for the task. No meaningful loss of task-relevant visual information is present. |
| 1 | Mild | Some degradation is visible, but recognition of the task-relevant structure or boundary remains essentially unaffected. The degradation is noticeable but does not materially limit visual interpretation. |
| 2 | Moderate | Task-relevant visual information is clearly reduced. Part of the target, boundary, continuity, or spatial relationship is obscured or degraded, but the relevant anatomy or operative field remains broadly interpretable. |
| 3 | Severe | The target structure, critical boundary, or relevant spatial relationship cannot be reliably identified or followed from the available visual information. |

### 5.5 Boundary rule: score 1 versus 2

The distinction between mild and moderate impairment is based on **functional visual consequence**, not the visual prominence of the artifact.

```text
Score 1:
artifact/degradation is present,
but task-relevant recognition remains essentially intact.

Score 2:
artifact/degradation clearly limits task-relevant recognition,
although the field remains broadly interpretable.
```

Examples:

- A large amount of blood outside the operative target may still be score 0 or 1.
- A small amount of blood directly obscuring a critical boundary may be score 2 or 3.
- A dark field may be score 0 if the target remains clearly visible.
- A near-contact image may be score 3 even without blood or smoke.

### 5.6 `confidence`

Three-level reviewer confidence.

| Value | Definition |
|---:|---|
| 1 | Low confidence |
| 2 | Moderate confidence |
| 3 | High confidence |

Confidence is not a substitute for `task_context_sufficient`.

---

## 6. Impairment-cause taxonomy

Cause labels are **secondary multi-label annotations** and must be separated from the primary severity score.

Recommended binary cause fields:

```text
cause_blur_or_defocus
cause_smoke_or_fog_or_veil
cause_blood_or_fluid_contamination
cause_glare_or_overexposure
cause_underexposure_or_blackout
cause_instrument_or_tissue_obstruction
cause_lens_contamination
cause_near_contact_or_red_out
cause_other
cause_uncertain
```

### 6.1 Cause definitions

#### Blur or defocus

Loss of local structural detail attributable to apparent focus loss, optical blur, or motion-related blur.

#### Smoke / fog / veil

Diffuse reduction of contrast or visibility consistent with smoke, fogging, vapor, or veil-like image degradation.

The reviewer does not need to determine the physical cause with certainty.

#### Blood or fluid contamination

Blood or fluid that contributes to reduced task-relevant visibility.

Blood that is visible but does not impair the task may be present in the scene without requiring a positive impairment-cause label.

#### Glare / overexposure

Bright saturation, whiteout, or intense reflection that obscures task-relevant information.

#### Underexposure / blackout

Insufficient illumination, black crush, or very dark image content that obscures task-relevant information.

#### Instrument or tissue obstruction

A physical object, including instrument or tissue, blocks or covers the task-relevant target or boundary.

#### Lens contamination

Material or optical contamination appearing to be on the imaging system rather than only in the operative field.

#### Near-contact / red-out

Extremely close camera-tissue interaction or homogeneous near-contact appearance that markedly limits interpretable field information.

#### Other

A meaningful visibility impairment not adequately represented by the predefined categories.

#### Uncertain

A visibility impairment is present but its predominant cause cannot be confidently classified.

---

## 7. Pilot review unit

### 7.1 Index moment

The fundamental pilot unit is an **index moment**, identified by:

```text
moment_id
case_id
sample_time_sec
```

Each index moment may have two media representations:

```text
still
short_clip
```

Both representations correspond to the same operative time point.

### 7.2 Still frame

The still image should be the frame corresponding to the index time.

No metric values, selection stratum, outcome data, model predictions, or hazard flags should be shown to the reviewer.

### 7.3 Short clip

Default pilot clip:

```text
index time - 2.5 sec
through
index time + 2.5 sec

total duration: approximately 5 sec
playback: 1x
audio: off
replay: allowed
```

If the index moment is near a video boundary, the clip may be shifted while preserving approximately 5 seconds where possible.

The clip duration is a pilot parameter, not yet a validated standard.

---

## 8. Still versus clip pilot design

The pilot should determine whether static frames provide enough task context for the main validation study.

### 8.1 Default pilot design

Use approximately **30 unique index moments**.

For each moment, generate both a still and a 5-second clip.

At least two thoracic-surgeon reviewers should participate if feasible.

### 8.2 Presentation design

Do not present the still and clip from the same moment consecutively.

Preferred design:

```text
Round 1:
Reviewer A sees still for half of the moments and clip for the other half.
Reviewer B receives the complementary modality assignment.

Round 2:
After a washout interval, the modality assignment is reversed.
Item order is re-randomized.
```

A washout interval should be used to reduce direct recall. The exact interval should be recorded in the pilot protocol.

### 8.3 Purpose of the modality pilot

The still-versus-clip comparison is an **instrument-design exercise**, not a definitive scientific comparison of media modalities.

Key questions:

1. How often is `task_context_sufficient = 0` for still images?
2. Does short video context reduce context-insufficient ratings?
3. Are severity anchors interpreted more consistently with clips?
4. Does clip review create excessive annotation burden?
5. Are specific impairment causes identifiable from stills but not reliably attributable without motion context?

No final modality should be selected solely from metric performance.

---

## 9. Pilot sampling strategy

The pilot is intentionally enriched and is not intended to estimate population prevalence.

Suggested target: **approximately 30 index moments**.

Illustrative sampling strata:

| Sampling stratum | Approximate n |
|---|---:|
| Apparently clear / low candidate scores | 5 |
| High structural-visibility-loss candidates | 5 |
| Smoke / veil-like candidates | 4 |
| Low-light / blackout candidates | 4 |
| Whiteout / specular-like candidates | 3 |
| Obstruction / near-contact candidates | 4 |
| Metric-discordant hard negatives | 3 |
| Technical or highly ambiguous examples | 2 |

These strata are **sampling labels only**. They are not reference labels.

### 9.1 Case diversity

Default constraints:

- use multiple cases;
- avoid domination by a small number of cases;
- target no more than approximately two pilot moments per case where practical;
- avoid near-duplicate neighboring moments;
- when multiple moments are sampled from one case, prefer substantial temporal separation.

### 9.2 Blinding

Reviewers must not see:

- selection stratum;
- candidate metric values;
- percentile thresholds;
- model-generated hazard labels;
- clinical outcomes;
- prior reviewer labels.

Workflow or task labels should not be shown in the initial pilot unless the project explicitly decides that external task annotation is part of the reference instrument.

If task context is frequently insufficient without an external task label, this should be recorded as a pilot finding rather than silently solved during review.

---

## 10. Recommended pilot data schema

Use separate tables for review items and reviewer ratings.

### 10.1 `phase01_pilot_items.csv`

One row per media item.

Recommended columns:

```text
review_id
moment_id
case_id
sample_time_sec
media_type
image_path
clip_path
clip_start_sec
clip_end_sec
selection_stratum
selection_metric
selection_value
selection_reason
presentation_batch
```

`selection_*` fields are retained for provenance but hidden from reviewers.

### 10.2 `phase01_pilot_ratings.csv`

One row per reviewer × review item.

Recommended columns:

```text
review_id
moment_id
reviewer_id
review_round
presentation_order
technical_evaluable
technical_issue
task_context_sufficient
visibility_impairment
cause_blur_or_defocus
cause_smoke_or_fog_or_veil
cause_blood_or_fluid_contamination
cause_glare_or_overexposure
cause_underexposure_or_blackout
cause_instrument_or_tissue_obstruction
cause_lens_contamination
cause_near_contact_or_red_out
cause_other
cause_uncertain
confidence
review_time_sec
comment
```

Binary cause columns are preferred over a delimited multi-select string because they are easier to validate and analyze reproducibly.

---

## 11. Pilot quality-control rules

The rating workflow should enforce the following logical constraints.

```text
if technical_evaluable == 0:
    visibility_impairment = NA
    task_context_sufficient = NA
    cause_* = NA

if technical_evaluable == 1 and task_context_sufficient == 0:
    visibility_impairment = NA
    cause_* = NA

if visibility_impairment == 0:
    impairment cause labels should generally be 0
    unless a specific protocol exception is documented

if visibility_impairment in {1, 2, 3}:
    at least one cause label should usually be selected,
    or cause_uncertain / cause_other should be used
```

These rules are intended to prevent logically inconsistent annotations.

---

## 12. Pilot review outcomes

The pilot is used to refine the annotation instrument.

Primary outputs are descriptive:

- proportion technically evaluable;
- proportion with sufficient task context;
- distribution of severity scores;
- distribution of cause labels;
- reviewer confidence;
- review time;
- discordant examples;
- still-versus-clip context sufficiency;
- examples where severity anchors are interpreted differently;
- taxonomy gaps identified in free text.

Inter-rater agreement may be calculated descriptively, but the pilot is not the definitive validation cohort.

Potential measures include:

- weighted Cohen's kappa for ordinal severity between two reviewers;
- Fleiss' kappa or alternative multi-rater measures if more reviewers participate;
- agreement for binary cause labels;
- modality-specific missingness due to insufficient context.

Because the pilot is small and enriched, these estimates should not be treated as precise population parameters.

---

## 13. Decision after pilot

Before building the main reference-standard set, explicitly decide:

1. still frame versus short clip as the primary review medium;
2. whether task labels must be supplied externally;
3. final severity wording;
4. final cause taxonomy;
5. whether any causes require merging or splitting;
6. clip duration if clips are used;
7. reviewer instructions and examples;
8. development/validation case split strategy;
9. primary validation metrics and statistical analysis plan.

The decision and rationale must be documented before the main annotation begins.

---

## 14. Development and validation separation

After the pilot instrument is finalized:

- split at the **case level**;
- do not place neighboring frames from the same case in different partitions;
- perform threshold tuning and metric redesign only in development data;
- preserve the validation set for final evaluation;
- do not use clinical outcomes to select or tune visibility metrics for the first measurement-validity analysis.

The frame count is not the independent clinical sample size. Case-level clustering and repeated frames must be respected in downstream statistical analysis.

---

## 15. Initial candidate metrics for validation

The first validation round may include:

```text
structural_visibility_loss_v1
veil_smoke_mean / veil_low_contrast_score_v1
saturation_ratio / whiteout_ratio_v1
specular_ratio / specular_like_ratio_v1
low_light_or_blackout_ratio_v1
local_obstruction_ratio
```

`local_obstruction_ratio` is a legacy proxy and is **not validated as a true physical-obstruction detector**.

Blood-related color metrics should be treated as candidate metrics only if a revised formulation is ready. The failed legacy color-only blood and anthracosis approaches must not be promoted solely because they already exist.

---

## 16. Phase 01 acceptance criteria

Phase 01 design is complete when:

```text
[ ] primary visibility construct approved
[ ] technical_evaluable definition approved
[ ] task_context_sufficient definition approved
[ ] 0-3 severity anchors approved
[ ] cause taxonomy approved
[ ] still-versus-clip pilot design approved
[ ] pilot item schema approved
[ ] pilot rating schema approved
[ ] reviewer blinding rules approved
[ ] pilot sampling strategy approved
[ ] pilot decision rules documented
```

Only after these items are approved should code be written to construct the pilot review set or review interface.

---

## 17. Non-goals for Phase 01

Do not use Phase 01 to:

- optimize a composite score;
- maximize correlation with clinical outcomes;
- select thresholds using the validation set;
- define technical failure from p95/p99 image metrics;
- infer blood, anthracosis, or tissue pathology from unvalidated color rules;
- introduce task-criticality weights;
- claim that visibility impairment is equivalent to surgical danger.

Phase 01 establishes the **human measurement reference** against which candidate image-derived metrics will later be evaluated.
