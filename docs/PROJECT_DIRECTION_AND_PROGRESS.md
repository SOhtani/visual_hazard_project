# Project Direction and Progress: Visual Hazard and Field Phenotype Analysis in Thoracic Surgical Videos

Last updated: 2026-06-27

## 1. Core hypothesis

The starting hypothesis of this project is that **how the operative field is seen in surgical video may itself carry clinically meaningful information**.

The project should not be reduced to a simple count of camera contamination events, scope-cleaning failures, or scopist/camera-operator quality. Those factors may be relevant, especially in non-robotic surgery, but the broader research question is whether video-derived visual field states reflect or modify clinically important conditions, including:

- operative difficulty;
- bleeding tendency or active blood-like contamination;
- inflammatory or adhesive tissue conditions;
- smoking-related or anthracosis-like field phenotype;
- post-induction or post-preoperative-treatment tissue phenotype;
- approach-dependent differences in field stability, especially robotic versus non-robotic surgery;
- task-critical visibility during vessel dissection, bronchial dissection, fissure division, lymph node dissection, hemostasis, and final inspection.

In short:

```text
The clinical object is not only camera quality.
The clinical object is the visible surgical field as a measurable phenotype and hazard environment.
```

## 2. Revised framing

The current project framing is:

```text
Task-critical visual hazard burden and video-derived surgical field phenotype
```

Definition:

```text
Task-critical visual hazard burden
= time-integrated burden of visual field states that may interfere with safe recognition,
  judgment, dissection, division, hemostasis, or lymph node dissection during a clinically
  meaningful surgical task.
```

Practical model:

```text
visual_hazard_burden = visual_hazard_severity x duration x task_criticality
```

This framing separates three constructs:

| Construct | Meaning | Current role |
|---|---|---|
| Image quality / optical fidelity | Whether the image is clear, sharp, well-exposed | component-level technical measurement |
| Visual hazard | A visual state that may interfere with safe operative recognition or manipulation | current main analytic target |
| Field phenotype | Visual appearance that may reflect patient/pathology/tissue characteristics | next module, e.g. blood-like redness, anthracosis-like blackness, inflammation-like appearance |

## 3. Where the project currently stands

Current completed analysis:

```text
68 RATS anatomical lung resection cases
519,198 analyzed frames
```

Current Tier 1 broad visual hazard components:

```text
structural_visibility_loss_v1
center_low_structure_area_v1
whiteout_ratio_v1
low_light_or_blackout_ratio_v1
```

Current visual hazard gate:

```text
visual_hazard_any_p95 = any Tier 1 component >= global p95
visual_hazard_any_p99 = any Tier 1 component >= global p99
```

Frame-level results:

```text
all frames:      519,198
clean_p95:       449,063 frames = 86.5%
hazard_p95:       70,135 frames = 13.5%
hazard_p99:       14,825 frames =  2.9%
```

Clinical linkage:

```text
case_visual_hazard_clinical_linkage.csv: 68 rows x 120 columns
burden cases: 68
metadata cases: 73
merged cases: 68
```

## 4. What has been learned so far

### 4.1 Visual hazard gate works as a bad-image candidate gate

Visual review showed:

- `whiteout_ratio_v1` captures whiteout / overexposed frames;
- `low_light_or_blackout_ratio_v1` captures blackout / extreme low-light frames;
- `center_low_structure_area_v1` captures red-out, tissue-contact-like, near-uniform, low-information central field;
- `structural_visibility_loss_v1` captures global structural information loss but overlaps with center low-structure.

### 4.2 Some metrics are not ready for clinical interpretation

- `specular_like_ratio_v1` overlaps too much with whiteout and should be redesigned before use as a separate main metric.
- `anthracosis_like_blackness_candidate_v1` is not sufficiently specific for anthracosis and should not be used as a clinical anthracosis score.
- `composite_degradation_score` is currently a legacy alias of structural visibility loss, not an independent composite.

### 4.3 Hazard seconds and hazard fraction have different meanings

Preliminary clinical linkage suggests:

```text
operation_time_min vs seconds_visual_hazard_any_p95: rho about 0.40
operation_time_min vs seconds_visual_hazard_any_p99: rho about 0.29
operation_time_min vs frac_visual_hazard_any_p95: near 0
operation_time_min vs frac_visual_hazard_any_p99: near 0 or weak negative
```

Interpretation:

```text
Longer operations accumulate more visual hazard seconds,
but they do not necessarily have a higher fraction of visual hazard time.
```

Therefore, seconds and fraction metrics must both be reported and interpreted separately.

### 4.4 Blood loss signal is not well captured by the current gate

The current Tier 1 gate measures visibility loss, whiteout, blackout, and low-structure frames. It does not directly measure blood-like field appearance. Therefore, weak blood-loss association at this stage should not be interpreted as absence of a blood-related video signal.

## 5. Scientific direction from here

The next scientific goal is to move from:

```text
generic bad-image / visual hazard gate
```

toward:

```text
video-derived surgical field phenotype
```

Priority phenotype modules:

1. `blood_like_redness_v1`
   - active blood-like contamination;
   - residual blood-like field after hemostasis or irrigation;
   - possible relation to bleeding, inflammation, adhesion, post-treatment tissue.

2. blackness / anthracosis-like phenotype
   - smoking burden or anthracotic visual field candidate;
   - requires better exclusion of underexposure, shadows, instruments, background, and cautery.

3. field instability / approach-dependent field behavior
   - important for future RATS versus VATS/non-robotic comparison;
   - may capture scope/scopist/camera-operation effects.

4. task-critical burden
   - visual hazard weighted by surgical phase/task;
   - poor view during pulmonary artery dissection should not be treated the same as poor view during specimen retrieval.

## 6. Near-term implementation sequence

### Phase 05C: strict clinical correlation whitelist

Purpose:

- remove technical metadata columns from formal clinical correlation output;
- keep only interpretable clinical variables such as operation time, blood loss, age, procedure group, side, target lobe/segment, and sex.

### Phase 06: figure-ready exploratory outputs

Purpose:

- create plot-ready tables for operation time, blood loss, procedure group, side, target lobe/segment, and phase-specific burden;
- display seconds and fraction metrics separately.

### Phase 07: blood-like redness module

Purpose:

- implement the first phenotype-specific video metric;
- build visual review sheets and validate false positives;
- examine whether blood-like burden relates better to blood loss, hemostasis, inflammation, or postoperative drainage than generic hazard burden.

### Phase 08: field phenotype expansion

Purpose:

- revisit blackness/anthracosis-like phenotype;
- consider inflammation/adhesion-like field features if appropriate;
- avoid definitive naming before validation.

### Phase 09: surgeon validation

Purpose:

- validate whether component metrics and phenotype candidates match surgeon-perceived visual states;
- use ratings as intermediate validation, not final clinical endpoints.

### Phase 10: task-critical burden

Purpose:

- weight visual hazard by phase/task risk;
- distinguish low-risk poor views from high-risk poor views.

### Phase 11: clinical phenotype analysis

Purpose:

- connect validated visual hazard and phenotype metrics to clinical outcomes and patient/surgery characteristics;
- avoid causal claims.

### Phase 12: approach comparison

Purpose:

- extend from RATS baseline to VATS/non-robotic surgery;
- evaluate field stability, scope contamination, camera operation, and approach-dependent visual hazard differences.

## 7. Working interpretation

At this stage, the project can claim feasibility of frame-level visual hazard measurement and case/phase burden aggregation in RATS lung resection videos. It cannot yet claim validated blood, anthracosis, inflammation, or tissue phenotype detection.

Current position:

```text
The measurement infrastructure for visual hazard is now in place.
The next research step is to build and validate phenotype-specific modules.
```

