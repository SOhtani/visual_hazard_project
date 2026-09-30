# PHASE_01_STILL_REVIEW_APP_SPEC.md

# Phase 01C - Blinded still-image review app specification

**Status:** Draft v0.1
**Date:** 2026-09-17
**Scope:** Self-review pilot of 30 selected still images
**Purpose:** Test the surgeon rating instrument before clip review and before independent validation

---

## 1. Role of this pilot

The first 30-image review is an **instrument-development / calibration pilot**.

It is intended to determine whether one surgeon can apply the proposed rating scheme consistently and whether still images provide sufficient task context.

These self-ratings are not, by themselves, the final independent reference standard.

For the final measurement-validity study, the validation set should be rated by one or more thoracic surgeons who are blinded to candidate metric values, sampling strata, and clinical outcomes.

---

## 2. Blinding

The review app must NOT display:

```text
case_id
sample_time_sec
moment_id
selection_stratum
selection_slot
selection_metric
selection_value
selection_percentile_band
eligible_strata
discordance_reason
p95 / p99 thresholds
legacy hazard flags
clinical outcomes
```

The app displays only:

```text
blinded review_item_id
current item number / total
still image
rating controls
comment field
```

The mapping between `review_item_id` and the internal `moment_id` is stored in a separate internal mapping file.

---

## 3. Review medium

Phase 01C begins with **still images only**.

Use the full surgical frame as the primary review image.

Do not display the metric ROI, ROI rectangle, metric heatmap, or derived image transformation during blinded rating.

Optional user controls:

```text
fit to window
100% zoom
zoom in / out
reset zoom
```

The image itself must not be altered beyond display scaling.

---

## 4. Required decision sequence

Every item follows the same sequence.

```text
1. Technical evaluable?
        |
        +-- No
        |     -> technical issue
        |     -> overall/component scores = NA
        |
        +-- Yes
              |
              v
2. Task context sufficient?
        |
        +-- No
        |     -> overall/component scores = NA
        |
        +-- Yes
              |
              v
3. Overall visibility impairment: 0 / 1 / 2 / 3
              |
              v
4. Nine component ratings: each 0 / 1 / 2 / 3
              |
              v
5. Confidence: 1 / 2 / 3
              |
              v
6. Optional comment
```

---

## 5. Gate 1 - Technical evaluability

### Question

> Is this image technically interpretable as an image?

### Values

```text
1 = Yes
0 = No
```

### `technical_evaluable = 0`

Use only for a true acquisition, decoding, rendering, or image-data failure.

Examples:

```text
all-zero image
corrupt/unreadable image
decoder/render failure
no-signal frame
test pattern/color bar
other demonstrable technical image failure
```

Do not use `technical_evaluable = 0` merely because the operative field is dark, bloody, blurred, overexposed, obstructed, or near-contact.

### Technical issue field

If `technical_evaluable = 0`, require one:

```text
all_zero_image
corrupt_or_unreadable
decoder_or_render_failure
no_signal
test_pattern_or_color_bar
other_technical_failure
uncertain_technical_failure
```

---

## 6. Gate 2 - Task-context sufficiency

### Question

> From this still image alone, is there enough information to identify the local operative target, relevant boundary, or field well enough to judge task-relevant visibility?

### Values

```text
1 = Yes
0 = No
```

If `task_context_sufficient = 0`:

```text
overall_visibility_impairment = NA
all nine component scores = NA
```

This is not a score of 0 and not a score of 3.

It means that the still image is insufficient for the intended task-relevant judgment.

---

## 7. Overall visibility impairment

This is the primary human rating.

### Score 0 - None

The task-relevant visual information is essentially intact.

The target, relevant boundary, or local field can be recognized without meaningful visibility limitation.

### Score 1 - Mild

Visible degradation is present, but task-relevant recognition remains essentially intact.

The degradation is noticeable but does not materially limit interpretation.

### Score 2 - Moderate

Task-relevant recognition is clearly limited.

Part of the target, boundary, continuity, or spatial relationship is obscured or degraded, but the relevant field remains broadly interpretable.

### Score 3 - Severe

Available visual information is insufficient to reliably identify or follow the task-relevant structure, boundary, or spatial relationship.

The rating concerns visibility, not overall surgical safety.

---

## 8. Nine component ratings

All nine component ratings use the same 0-3 framework:

```text
0 = absent or no relevant degradation
1 = present, but no material limitation of task-relevant recognition
2 = clearly limits task-relevant recognition
3 = severely limits or prevents reliable task-relevant recognition
```

The component score measures the **visibility consequence attributable to that component**, not merely whether the visual feature is present.

### 8.1 Blur / defocus / motion blur

Variable:

```text
component_blur_defocus
```

Judge loss of structural detail caused by apparent defocus, optical blur, or motion-related blur.

### 8.2 Smoke / fog / veil

Variable:

```text
component_smoke_fog_veil
```

Judge diffuse contrast loss consistent with smoke, fogging, vapor, or veil-like degradation.

### 8.3 Blood / fluid

Variable:

```text
component_blood_fluid
```

Judge the effect of blood or fluid on task-relevant visibility.

Important:

```text
blood present != blood-related visibility impairment
```

### 8.4 Glare / specular reflection

Variable:

```text
component_glare_specular
```

Judge localized intense reflections or highlights that reduce visibility.

### 8.5 Whiteout / overexposure

Variable:

```text
component_whiteout_overexposure
```

Judge broader high-intensity saturation or overexposure that removes visual information.

### 8.6 Underexposure / blackout

Variable:

```text
component_underexposure_blackout
```

Judge visibility loss due to insufficient illumination, dark image regions, or black crush.

Important:

```text
dark appearance != impaired visibility
```

### 8.7 Instrument / tissue obstruction

Variable:

```text
component_instrument_tissue_obstruction
```

Judge physical blocking of the task-relevant target or boundary by an instrument or tissue.

Important:

```text
instrument present != obstruction
```

### 8.8 Lens contamination

Variable:

```text
component_lens_contamination
```

Judge degradation that appears to arise from material or optical contamination on the imaging system/lens.

### 8.9 Near-contact / red-out

Variable:

```text
component_near_contact_redout
```

Judge loss of interpretable field information caused by extreme camera-tissue proximity or homogeneous near-contact/red-out appearance.

---

## 9. Relationship between overall and component scores

The overall score is an independent integrated surgeon judgment.

It must NOT be calculated mechanically from the nine component scores.

However, the app should warn about obvious logical inconsistencies:

```text
overall = 0 AND any component >= 2

overall = 1 AND any component >= 2

overall in {2,3} AND all components = 0
```

Warnings should not silently alter ratings.

---

## 10. Confidence

Variable:

```text
confidence
```

Values:

```text
1 = low
2 = moderate
3 = high
```

Confidence refers to confidence in the submitted decision path for that item.

It may be recorded even when a gate is negative.

---

## 11. Optional comment

Variable:

```text
comment
```

Free text.

Use when a rating is difficult, the task context is insufficient, the mechanism is uncertain, or the overall impairment is not explained by the nine predefined components.

---

## 12. Reviewer-facing screen

Suggested layout:

```text
+-----------------------------------------------------------+
| Review item V017                         Item 8 / 30      |
+-----------------------------------------------------------+
|                                                           |
|                     FULL STILL IMAGE                      |
|                                                           |
+-----------------------------------------------------------+

Technical evaluable?
[ Yes ] [ No ]

Task context sufficient?
[ Yes ] [ No ]

Overall visibility impairment
[ 0 ] [ 1 ] [ 2 ] [ 3 ]

Component impairment
Blur / defocus / motion blur       [0] [1] [2] [3]
Smoke / fog / veil                 [0] [1] [2] [3]
Blood / fluid                      [0] [1] [2] [3]
Glare / specular reflection        [0] [1] [2] [3]
Whiteout / overexposure            [0] [1] [2] [3]
Underexposure / blackout           [0] [1] [2] [3]
Instrument / tissue obstruction    [0] [1] [2] [3]
Lens contamination                 [0] [1] [2] [3]
Near-contact / red-out             [0] [1] [2] [3]

Confidence
[1] [2] [3]

Comment
[                                                     ]

[ Previous ]        [ Save ]        [ Save & Next ]
```

---

## 13. Save and resume behavior

The app must:

- save after every explicit `Save` or `Save & Next`;
- load prior ratings on restart;
- indicate completed versus incomplete items;
- permit backward navigation and correction;
- preserve a modification timestamp;
- avoid duplicate rows for the same reviewer x review item.

The canonical row key is:

```text
reviewer_id + review_item_id
```

---

## 14. Blinded review manifest

Create:

```text
data/annotations/phase01_pilot_review_manifest.csv
```

Suggested columns:

```text
review_item_id
review_order
image_path
```

Do not include metric or stratum information.

---

## 15. Internal mapping file

Create separately:

```text
reports/phase01_pilot_sampling/phase01_pilot_review_mapping.csv
```

Suggested columns:

```text
review_item_id
review_order
moment_id
case_id
sample_time_sec
selection_stratum
selection_slot
selection_metric
selection_value
selection_percentile_band
image_path
```

This file must not be displayed by the review app.

---

## 16. Rating output schema

Suggested output:

```text
data/annotations/phase01_pilot_still_ratings.csv
```

One row per reviewer x review item.

Columns:

```text
reviewer_id
review_item_id
review_order

technical_evaluable
technical_issue
task_context_sufficient

overall_visibility_impairment

component_blur_defocus
component_smoke_fog_veil
component_blood_fluid
component_glare_specular
component_whiteout_overexposure
component_underexposure_blackout
component_instrument_tissue_obstruction
component_lens_contamination
component_near_contact_redout

confidence
comment

review_started_at
review_saved_at
review_time_sec
completed
```

No candidate metric values are written into the rating table.

---

## 17. Logical validation

If `technical_evaluable = 0`:

```text
technical_issue required
task_context_sufficient = NA
overall_visibility_impairment = NA
all component scores = NA
```

If `technical_evaluable = 1` and `task_context_sufficient = 0`:

```text
technical_issue = NA
overall_visibility_impairment = NA
all component scores = NA
```

If both gates are positive, require:

```text
overall_visibility_impairment
all nine component scores
confidence
```

---

## 18. Review order

The 30 still images should be shown in a deterministic randomized order.

Reviewer-facing IDs:

```text
V001
V002
...
V030
```

These IDs must not reveal the original `P01M###` order.

The randomization seed must be stored in the internal mapping/audit documentation.

---

## 19. Phase 01C output interpretation

After the 30-image self-review, summarize:

```text
technical_evaluable distribution
task_context_sufficient distribution
overall score distribution
component score distributions
confidence distribution
review time
missingness
logical-QC warnings
```

Then inspect the still images with:

```text
task_context_sufficient = 0
low confidence
overall/component logical discordance
```

These findings determine whether still images are adequate, short clips are required, rating definitions need revision, or the main independent review protocol is ready.

---

## 20. Methodological boundary

The project developer's self-ratings are appropriate for:

```text
pilot instrument refinement
testing UI usability
identifying ambiguous anchors
testing still-image sufficiency
checking annotation burden
```

They should not be treated as the sole independent criterion reference for final metric validation.

The final validation design should preserve independent blinded surgeon review at the case-separated validation stage.
