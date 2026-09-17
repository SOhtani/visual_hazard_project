# PHASE_01_RATING_MANUAL.md

# Phase 01 - Rating manual for task-relevant operative-field visibility

**Status:** Draft v0.1
**Date:** 2026-09-17
**Use:** Pilot annotation only
**Primary construct:** Task-relevant operative-field visibility impairment

---

## 1. What the reviewer is judging

Judge **how much the available visual information is impaired for recognizing and following the operative target, relevant boundary, or landmark needed for the current task**.

Do **not** judge:

- whether the field looks aesthetically clean;
- whether the operation is safe overall;
- whether the surgeon should stop;
- whether an adverse event will occur;
- whether the case is difficult in general.

The target of the rating is the **visibility of task-relevant information**.

---

## 2. Required decision sequence

Rate each item in this order.

```text
Step 1. Is the media technically evaluable?
        |
        +-- NO --> technical_evaluable = 0
        |          record technical_issue
        |          stop
        |
        +-- YES
              |
              v
Step 2. Is there enough task context to judge visibility?
        |
        +-- NO --> task_context_sufficient = 0
        |          stop
        |
        +-- YES
              |
              v
Step 3. Rate visibility impairment: 0 / 1 / 2 / 3
              |
              v
Step 4. Select cause(s) that contribute to the impairment
              |
              v
Step 5. Record confidence
```

Do not infer a severe score merely because the task is unclear.

---

## 3. Step 1 - Technical evaluability

### 3.1 `technical_evaluable = 1`

Use when the media is technically viewable and can be assessed.

A real operative field remains technically evaluable even if it is:

- dark;
- bloody;
- blurred;
- smoke-filled;
- partially occluded;
- very close to tissue;
- strongly overexposed;
- strongly underexposed.

These findings may represent clinically relevant visibility impairment and should not automatically be excluded.

### 3.2 `technical_evaluable = 0`

Use only for a demonstrable acquisition, decoding, rendering, or data problem.

Examples:

```text
all-zero image
corrupt or unreadable image
decoder/render failure
no-signal frame
test pattern or color bar
other technical failure
```

If `technical_evaluable = 0`:

```text
task_context_sufficient = NA
visibility_impairment = NA
cause_* = NA
```

---

## 4. Step 2 - Task-context sufficiency

### 4.1 Question

> Does this still image or clip provide enough information to understand what operative target, boundary, or local field should be judged?

### 4.2 `task_context_sufficient = 1`

Use when the relevant operative target or local field can be understood well enough to judge its visibility.

The reviewer does **not** need to know the complete formal surgical phase or exact procedural step.

### 4.3 `task_context_sufficient = 0`

Use when the media is technically viewable but the reviewer cannot determine what target, boundary, or local operative field is relevant enough to rate task-relevant visibility.

Examples may include:

- an isolated still frame where the intended target cannot be inferred;
- a transient camera movement with no interpretable target;
- an image containing several structures with no clear operative focus;
- a clip that is too short to establish the local task.

If `task_context_sufficient = 0`:

```text
visibility_impairment = NA
cause_* = NA
```

Do not convert uncertainty about the task into a visibility score.

---

## 5. Step 3 - Visibility impairment severity

### 5.1 Core principle

Rate the **functional consequence for visual recognition**, not the amount or visual prominence of an artifact.

---

### Score 0 - None

**Definition**

The task-relevant structure, boundary, or landmark can be recognized clearly enough for the current task. There is no meaningful loss of task-relevant visual information.

**Typical examples**

- clear operative field;
- mild color variation without loss of structural information;
- blood visible away from the target without obscuring it;
- dark tissue that remains well delineated;
- an instrument present but not blocking the relevant target.

**Key test**

> Is the relevant visual information essentially intact?

If yes, use 0.

---

### Score 1 - Mild

**Definition**

Visible degradation is present, but recognition of the task-relevant structure or boundary remains essentially intact.

The degradation is noticeable, but it does not materially limit interpretation of the target.

**Typical examples**

- mild blur while the relevant boundary remains clear;
- thin smoke or haze with preserved anatomy;
- a small amount of blood that does not meaningfully obscure the target;
- limited glare away from the key structure;
- partial instrument overlap without loss of the critical boundary.

**Key test**

> Is there degradation, but essentially no functional limitation of task-relevant recognition?

If yes, use 1.

---

### Score 2 - Moderate

**Definition**

Task-relevant visual information is clearly reduced.

Part of the target, boundary, continuity, or spatial relationship is obscured or degraded, but the relevant anatomy or local operative field remains broadly interpretable.

**Typical examples**

- blood obscures part of the relevant dissection plane;
- smoke or fog reduces contrast enough that boundaries require effort to follow;
- underexposure obscures part of the target while other landmarks remain visible;
- an instrument or tissue flap blocks part of the target;
- blur removes some fine structural detail but the operative target remains identifiable.

**Key test**

> Does the degradation clearly limit recognition, while enough information remains to understand the relevant field?

If yes, use 2.

---

### Score 3 - Severe

**Definition**

The available visual information is insufficient to reliably identify or follow the task-relevant structure, critical boundary, or relevant spatial relationship.

**Typical examples**

- the operative target is substantially hidden by blood or tissue;
- severe red-out or near-contact appearance prevents interpretation of the field;
- blackout/underexposure removes the relevant structural information;
- severe glare or whiteout obscures the target;
- dense smoke/fog eliminates useful local contrast;
- severe blur prevents reliable identification of the relevant boundary.

**Key test**

> Is the task-relevant visual information no longer reliable enough to identify or follow the relevant structure or boundary?

If yes, use 3.

---

## 6. The most important boundary: score 1 versus score 2

This distinction must be made according to **functional visual limitation**.

```text
Score 1:
degradation is present,
but task-relevant recognition is essentially preserved.

Score 2:
degradation clearly limits task-relevant recognition,
although the relevant field remains broadly interpretable.
```

Do not assign score 2 solely because an artifact looks dramatic.

Examples:

```text
Large blood stain outside the target:
    may be 0 or 1

Small blood layer directly covering a critical boundary:
    may be 2 or 3

Dark operative field with clear boundaries:
    may be 0 or 1

Less dramatic darkening that hides the relevant plane:
    may be 2

Instrument occupying a large image area but not the target:
    may be 0 or 1

Small instrument tip directly blocking the critical point:
    may be 2
```

---

## 7. Step 4 - Impairment causes

Select cause labels only when they **contribute to the visibility impairment being rated**.

The cause labels are not simple scene-presence labels.

For example:

```text
Blood is visible but does not reduce task-relevant visibility:
    cause_blood_or_fluid_contamination = 0

Blood directly obscures the relevant boundary:
    cause_blood_or_fluid_contamination = 1
```

Multiple causes may be selected.

### 7.1 `cause_blur_or_defocus`

Use when apparent blur, defocus, or motion-related image blur contributes to impaired recognition of relevant structure.

### 7.2 `cause_smoke_or_fog_or_veil`

Use when diffuse smoke, fog, vapor, or veil-like contrast reduction contributes to impaired visibility.

The reviewer does not need to establish the exact physical origin.

### 7.3 `cause_blood_or_fluid_contamination`

Use when blood or fluid contributes to loss of task-relevant visibility.

Do not mark simply because blood is present.

### 7.4 `cause_glare_or_overexposure`

Use when bright saturation, whiteout, or intense reflection obscures task-relevant information.

### 7.5 `cause_underexposure_or_blackout`

Use when insufficient illumination, black crush, or very dark image content obscures task-relevant information.

### 7.6 `cause_instrument_or_tissue_obstruction`

Use when an instrument or tissue physically blocks the relevant target or boundary.

### 7.7 `cause_lens_contamination`

Use when degradation appears to arise from contamination on the imaging system or lens rather than only from material within the operative field.

### 7.8 `cause_near_contact_or_red_out`

Use when extreme camera-tissue proximity or homogeneous near-contact appearance prevents adequate interpretation of the field.

### 7.9 `cause_other`

Use when a meaningful impairment cause is present but not represented by the predefined categories.

Describe the cause in `comment`.

### 7.10 `cause_uncertain`

Use when impairment is present but the reviewer cannot confidently determine its cause.

Do not use `cause_uncertain` merely because severity is difficult to grade.

---

## 8. Step 5 - Confidence

Use:

```text
1 = low confidence
2 = moderate confidence
3 = high confidence
```

Confidence describes certainty in the submitted judgment.

It does not replace `task_context_sufficient`.

If the task cannot be judged from the media, use:

```text
task_context_sufficient = 0
visibility_impairment = NA
```

rather than forcing a low-confidence visibility score.

---

## 9. Important examples and edge cases

### 9.1 Blood without impairment

```text
technical_evaluable = 1
task_context_sufficient = 1
visibility_impairment = 0 or 1
cause_blood_or_fluid_contamination = 0
```

Blood presence alone is not the primary construct.

### 9.2 Blood directly obscuring the target

```text
technical_evaluable = 1
task_context_sufficient = 1
visibility_impairment = 2 or 3
cause_blood_or_fluid_contamination = 1
```

### 9.3 Dark but usable field

```text
technical_evaluable = 1
task_context_sufficient = 1
visibility_impairment = 0 or 1
cause_underexposure_or_blackout = 0
```

Dark appearance alone is insufficient for an impairment label.

### 9.4 Clinically dark field that prevents recognition

```text
technical_evaluable = 1
task_context_sufficient = 1
visibility_impairment = 2 or 3
cause_underexposure_or_blackout = 1
```

Do not classify this as technical invalidity merely because a low-light metric is extreme.

### 9.5 All-zero image

```text
technical_evaluable = 0
technical_issue = all_zero_image
task_context_sufficient = NA
visibility_impairment = NA
cause_* = NA
```

### 9.6 Large instrument in the image but target remains visible

```text
visibility_impairment = 0 or 1
cause_instrument_or_tissue_obstruction = 0
```

### 9.7 Small obstruction at the critical boundary

```text
visibility_impairment = 2 or 3
cause_instrument_or_tissue_obstruction = 1
```

### 9.8 Static frame is clear but task cannot be inferred

```text
technical_evaluable = 1
task_context_sufficient = 0
visibility_impairment = NA
cause_* = NA
```

This is not score 0.

### 9.9 Severe near-contact / red-out

If the frame is a genuine surgical image rather than a technical failure:

```text
technical_evaluable = 1
task_context_sufficient = 1
visibility_impairment = 3
cause_near_contact_or_red_out = 1
```

---

## 10. Still-image and clip review

For the pilot, still frames and short clips may both be used.

The reviewer should apply the same construct and severity anchors to both media types.

For clips:

- judge the index moment and its immediate operative context;
- use motion/context to understand the target;
- do not average the entire clip into a generic quality score;
- if visibility changes rapidly, judge the visibility relevant to the index moment;
- use the surrounding seconds primarily to establish task context and interpret the visual state.

For still images:

- do not infer unseen temporal information;
- if the task cannot be determined, use `task_context_sufficient = 0`.

---

## 11. Reviewer blinding

The reviewer must not be shown:

```text
candidate metric values
selection metric
selection stratum
p95 / p99 thresholds
model-generated hazard flags
clinical outcomes
other reviewers' ratings
```

The purpose of the human rating is to provide a reference independent of the candidate metrics.

---

## 12. Pilot annotation logic

Recommended logical rules:

```text
if technical_evaluable == 0:
    technical_issue must be recorded
    task_context_sufficient = NA
    visibility_impairment = NA
    all cause fields = NA

if technical_evaluable == 1:
    technical_issue = NA

if task_context_sufficient == 0:
    visibility_impairment = NA
    all cause fields = NA

if visibility_impairment == 0:
    cause fields should normally all be 0

if visibility_impairment in {1, 2, 3}:
    at least one cause should normally be selected,
    or cause_other / cause_uncertain should be used
```

A data-entry tool should enforce these constraints where practical.

---

## 13. What the pilot is trying to learn

The pilot is not intended to validate the final image metric.

It should answer:

1. Can thoracic surgeons apply the 0-3 visibility scale consistently?
2. Is the distinction between score 1 and score 2 operationally usable?
3. How often are still frames insufficient for task context?
4. Does a short clip substantially reduce context-insufficient ratings?
5. Are the proposed cause categories understandable and sufficient?
6. Which examples produce disagreement and why?
7. How much time does each review item require?
8. Is the annotation burden practical for the main validation study?

---

## 14. Issues to revisit after the pilot

Do not finalize the main validation protocol until the pilot has addressed:

```text
still versus clip
clip duration
need for external phase/task labels
severity wording
cause taxonomy
reviewer burden
confidence scale
discordant / ambiguous examples
```

Any revision after the pilot should be versioned before the main annotation begins.
