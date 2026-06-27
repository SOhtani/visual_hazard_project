# Project Direction and Progress: Task-Critical Visual Hazard Burden in Thoracic Surgical Videos

Last updated: 2026-06-27

## 1. Core hypothesis

The starting hypothesis of this project is that **how the operative field is seen in surgical video may itself carry clinically meaningful information**.

The project should not be reduced to a simple count of camera contamination events, scope-cleaning failures, or scopist/camera-operator quality. Those factors may be relevant, especially in non-robotic surgery, but the broader research question is whether video-derived visual field states reflect or modify clinically important conditions, including:

- operative difficulty;
- bleeding tendency or active blood contamination;
- inflammatory or adhesive tissue conditions;
- smoking-related or anthracotic field phenotype;
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
Task-critical visual hazard burden in thoracic surgical videos
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

This framing separates three related but distinct constructs:

| Construct | Meaning | Current role |
|---|---|---|
| Image quality / optical fidelity | Whether the image is clear, sharp, well-exposed | component-level technical measurement |
| Visual hazard | A visual state that may interfere with safe operative recognition or manipulation | current main analytic target |
| Field phenotype | Visual appearance that may reflect patient/pathology/tissue characteristics | future module, e.g. blood-like redness, anthracosis-like blackness, inflammation-like appearance |

## 3. Relation to prior literature

The project should be positioned as a thoracic surgical video extension of several prior research streams:

### 3.1 Surgical/endoscopic artifact and image-quality literature

Prior endoscopic and laparoscopic image-quality work supports the concept that blur, smoke/fog, glare, saturation, low contrast, specularity, and other artifacts are separable video phenomena. These support the technical component vocabulary, but they do not by themselves establish clinical hazard in thoracic surgery.

Implication:

```text
Use prior image-quality literature to define measurable image properties,
but do not overclaim clinical meaning before validation.
```

### 3.2 Thoracic blood-stain quantification

Thoracic video blood-stain quantification supports the idea that video-derived field appearance can be summarized over time and linked to postoperative or intraoperative clinical variables. This is directly relevant to future blood-like redness and post-irrigation residual blood burden.

Implication:

```text
Add blood_like_redness_v1 as a material contamination candidate,
but do not call it blood until validated.
```

### 3.3 Anthracosis and thoracic field phenotype

Anthracosis-related visual blackness may reflect smoking burden, lymphatic behavior, nodal disease context, or other thoracic pathophysiology. However, blackness in video is heavily confounded by shadow, underexposure, camera border, black instruments, cautery, and true carbon deposition.

Implication:

```text
Anthracosis-like appearance should be treated as a future field-phenotype module,
not as a currently validated hazard metric.
```

### 3.4 Robotic versus non-robotic field stability

The current dataset is RATS-focused. A future extension to VATS/non-robotic surgery is important because non-robotic videos may show more variation from camera handling, scopist skill, camera contamination, unstable field centering, and more frequent lens events.

Implication:

```text
RATS can serve as a relatively stable-field baseline.
VATS/non-robotic data can later test whether visual hazard burden captures camera/team variability.
```

## 4. What has been completed

### 4.1 Pipeline and repository governance

A GitHub-based workflow was established for `visual_hazard_project`, with branch-based development and code/docs-only commits. Raw videos, extracted frames, clinical CSVs, PHI, and review sheets are not committed.

Completed branches include:

- `phase-02-component-review-set`
- `phase-02b-image-validity-gate`
- `phase-03-all-case-distribution`
- `phase-04-visual-hazard-gate`
- `phase-05-clinical-linkage`
- `phase-05b-clean-clinical-correlation`

### 4.2 Frame-level component metrics

The current frame-level script computes and/or preserves these major metrics:

| Metric | Current interpretation | Status |
|---|---|---|
| `structural_visibility_loss_v1` | structural information loss proxy | usable, but overlaps with center-low-structure |
| `center_low_structure_area_v1` | central low-information / near-uniform field proxy | strong primary candidate |
| `whiteout_ratio_v1` | whiteout / overexposure burden | strong photometric hazard |
| `low_light_or_blackout_ratio_v1` | blackout / low-light burden | strong photometric hazard |
| `reblur_response_loss_v1` | low high-frequency / reblur-response proxy | auxiliary |
| `veil_low_contrast_score_v1` | low contrast + low edge proxy | auxiliary |
| `blackness_raw_ratio_v1` | raw dark area | auxiliary / phenotype candidate support |
| `blackness_corrected_ratio_v1` | illumination-normalized dark area | auxiliary / phenotype candidate support |
| `specular_like_ratio_v1` | specular-like brightness, currently overlaps whiteout | reconsider |
| `anthracosis_like_blackness_candidate_v1` | not validated as anthracosis | deferred from default review |

Important decision:

```text
No composite score should become a primary endpoint before component validation.
```

### 4.3 Image validity gate

Image validity candidate flags were added to identify near-uniform frames, large whiteout, blackout, color-bar/test-pattern-like frames, and photometric failures. These flags are used to help build cleaner review sets and clean reference frame candidates.

### 4.4 All-case distribution analysis

All-case metric computation and distribution summaries have been completed.

Current analytic cohort:

```text
Cases: 68
Frames: 519,198
```

Global candidate cutoffs were created at p90, p95, and p99 for each component. These are candidate cutoffs, not final clinical thresholds.

### 4.5 Visual audit

Manual montage review showed:

- `whiteout_ratio_v1` high frames are visually consistent with whiteout;
- `low_light_or_blackout_ratio_v1` high frames are visually consistent with blackout/low-light states;
- `center_low_structure_area_v1` high frames capture red-out, tissue-contact-like, or near-uniform low-information fields;
- `structural_visibility_loss_v1` behaves similarly but is more general;
- `whiteout low` can include black frames, which is expected because it only means “not whiteout”; low examples are not necessarily clean examples;
- `specular_like_ratio_v1` currently overlaps substantially with whiteout and should not be a main endpoint;
- `anthracosis_like_blackness_candidate_v1` should not be interpreted as anthracosis.

### 4.6 Visual hazard gate

A Tier-1 broad visual hazard gate was created using the OR condition across:

```text
structural_visibility_loss_v1
center_low_structure_area_v1
whiteout_ratio_v1
low_light_or_blackout_ratio_v1
```

Frame-level results:

```text
All frames:      519,198
clean_p95:      449,063 frames = 86.5%
hazard_p95:      70,135 frames = 13.5%
hazard_p99:      14,825 frames =  2.9%
```

Interpretation:

```text
p95 = broad visual hazard candidate / clean-reference exclusion gate
p99 = severe visual hazard candidate
```

Generated frame manifests:

```text
clean_reference_frames_p95.csv
visual_hazard_frames_p95.csv
visual_hazard_frames_p99.csv
```

### 4.7 Clinical linkage

A case-level linkage table has been created:

```text
reports/clinical_linkage/case_visual_hazard_clinical_linkage.csv
```

Current merge:

```text
burden cases:   68
metadata cases: 73
merged cases:   68
```

The table includes case-level burden, Level-1 phase burden, operation time, blood loss, age, sex, procedure group, side, and target lobe/segment.

### 4.8 Early clinical association signals

The most important early finding is that absolute hazard seconds and hazard fraction behave differently.

Observed exploratory correlations:

```text
operation_time_min vs seconds_visual_hazard_any_p95: rho ≈ 0.40
operation_time_min vs seconds_visual_hazard_any_p99: rho ≈ 0.29
operation_time_min vs frac_visual_hazard_any_p95:    rho ≈ 0.00
operation_time_min vs frac_visual_hazard_any_p99:    rho ≈ -0.09
```

Interpretation:

```text
Longer operations tend to accumulate more visual hazard seconds,
but they do not necessarily have a higher proportion of visual hazard time.
```

Blood loss associations are weak in the current dataset:

```text
blood_loss_g vs seconds_visual_hazard_any_p95: rho ≈ 0.22
blood_loss_g vs seconds_visual_hazard_any_p99: rho ≈ 0.17
blood_loss_g vs frac_visual_hazard_any_p95:    rho ≈ -0.03
blood_loss_g vs frac_visual_hazard_any_p99:    rho ≈ -0.08
```

This suggests that blood loss is not yet a strong signal with the current broad hazard gate, but blood-like redness has not yet been implemented as a dedicated field phenotype metric.

## 5. Current interpretation

The project has moved from:

```text
Count outside-body / blur / smoke / glare and correlate with operation time or blood loss.
```

to:

```text
Quantify clinically relevant visual field states as task-critical visual hazard burden,
then test whether these states capture operative difficulty, patient/tissue phenotype,
field instability, and clinically relevant outcomes.
```

At present, the strongest implemented metrics are not “blood,” “smoke,” or “anthracosis.” They are:

```text
whiteout / overexposure
blackout / low-light
near-uniform or low-structure field
structural visibility loss
```

These are valid as visual hazard gates. They are not yet sufficient to test all intended clinical phenotype hypotheses.

## 6. Near-term priorities

### Priority 1: Fix clinical correlation variable selection

The clean correlation script improved hazard-vs-hazard contamination but still allowed non-clinical numeric metadata such as `original_case_id`, `video_exists`, and availability flags to enter the correlation table.

Next correction:

```text
Use a strict whitelist for clinical correlation variables.
```

Initial whitelist:

```text
operation_time_min
blood_loss_g
age
```

Later whitelist additions, if available:

```text
BMI
smoking_index / Brinkman index
pack-years
preoperative_treatment
adhesion grade
inflammation marker
fissure completeness
postoperative air leak
drain duration
drainage volume
complication_any
length_of_stay
surgeon_id
year
```

### Priority 2: Separate “hazard burden” from “field phenotype”

Current Tier-1 hazard gate is suitable for identifying bad or low-quality visual states. The next clinical hypothesis requires phenotype-specific modules:

```text
blood_like_redness_v1
post_irrigation_blood_like_burden_v1
anthracosis_like_blackness_revised_v1
smoke_or_veil_event_burden_v1
lens_contamination_event_v1
field_instability_or_off-center_target_v1
```

### Priority 3: Build blood-like redness module

This is the most direct bridge to bleeding, hemostasis, inflammation, and surgical difficulty.

Requirements:

- use conservative red-dominance / hue / saturation criteria;
- exclude whiteout and very dark pixels;
- separate red tissue/vessel false positives from blood contamination;
- manually validate high examples;
- analyze post-irrigation or post-hemostasis residual redness separately when phase labels allow.

### Priority 4: Revisit blackness/anthracosis as field phenotype, not hazard

The previous anthracosis-like metric did not specifically detect anthracosis. It should be redesigned only after better masking and validation.

Possible future approach:

- use pleural/lung-surface ROI or segmentation;
- exclude instruments, camera border, blackout, and shadow;
- separate raw blackness, corrected blackness, and anthracosis-like phenotype;
- validate against surgeon labels or smoking/anthracosis-related clinical variables.

### Priority 5: Add task-critical weighting

The same bad image has different meaning depending on the surgical task.

Next step:

```text
Map Level-1 / Level-2 / later Layer-3 surgical phases to task-criticality classes.
```

Initial high-risk task candidates:

- pulmonary artery dissection;
- vessel division;
- bronchial dissection;
- fissure division near vessels;
- mediastinal lymph node dissection;
- hemostasis confirmation;
- post-irrigation inspection.

### Priority 6: Extend to non-robotic surgery later

The current RATS cohort can be treated as a stable-field baseline. VATS/non-robotic data should be used later to test:

- camera instability;
- scope/scopist quality dependence;
- lens contamination frequency;
- field-centering variability;
- whether visual hazard burden differs by approach independent of patient/tissue factors.

## 7. Recommended next implementation sequence

### Phase 05c: Strict clinical correlation whitelist

Goal:

```text
Remove non-clinical numeric metadata from correlation output.
```

Output:

```text
reports/clinical_linkage_clean_strict/numeric_spearman_correlations.csv
```

### Phase 06: Figure-ready exploratory outputs

Goal:

Create CSVs and plots for:

- operation time vs hazard seconds;
- operation time vs hazard fraction;
- blood loss vs hazard burden;
- procedure group boxplots;
- side/lobe/segment summaries;
- top visual hazard cases with clinical metadata.

### Phase 07: Blood-like redness module

Goal:

Implement and validate `blood_like_redness_v1` as a material contamination candidate.

### Phase 08: Surgeon visual validation set

Goal:

Create a compact review set for surgeon rating of:

- whiteout;
- blackout;
- structural visibility loss;
- center low-structure field;
- blood-like redness;
- black/anthracosis-like appearance;
- overall task-critical visual hazard;
- surgical usability.

### Phase 09: Task-critical burden

Goal:

Integrate phase/task labels and compute task-weighted burden.

### Phase 10: Clinical phenotype analysis

Goal:

Test hypotheses such as:

- high blood-like redness burden correlates with blood loss, drain duration, or prolonged air leak;
- anthracosis-like phenotype correlates with smoking burden or nodal/field characteristics;
- post-induction cases show distinct field phenotype or increased structural/low-contrast burden;
- non-robotic surgery shows higher camera-related hazard burden than RATS;
- severe task-critical burden, rather than generic hazard fraction, better predicts clinical difficulty.

## 8. Working manuscript direction

A plausible manuscript structure is:

```text
Title concept:
Task-Critical Visual Hazard Burden in Robot-Assisted Thoracic Surgery Videos:
A Frame-Level Quantification and Clinical Linkage Study
```

Core message:

```text
Surgical video contains quantifiable information about intraoperative visual conditions.
In RATS lung resection videos, whiteout, blackout, structural visibility loss,
and central low-structure field states can be measured at frame level and aggregated into
case- and phase-level burden. Early clinical linkage suggests that absolute visual hazard
seconds track operation duration, whereas normalized hazard fraction captures a different
construct. Further phenotype-specific metrics, especially blood-like redness and
anthracosis-like field appearance, are needed to test patient- and tissue-related hypotheses.
```

## 9. Non-goals and caution

Do not claim yet:

- that current metrics detect blood;
- that current metrics detect anthracosis;
- that current metrics detect smoke or inflammation as clinical entities;
- that visual hazard causes longer operation time;
- that p95/p99 thresholds are externally validated;
- that a composite score is validated.

Do claim cautiously:

```text
The current pipeline can quantify several visually interpretable hazard states at frame level
and summarize them as case- and phase-level burden for exploratory clinical linkage.
```
