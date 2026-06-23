# PLAN_VISUAL_HAZARD.md

# Task-Critical Visual Hazard Burden in Thoracic Surgical Videos

## 0. Clinical purpose

This project is not intended to quantify visual quality for its own sake.

The goal is to identify and quantify intraoperative visual hazard states that may contribute to patient harm, operative difficulty, postoperative morbidity, or preventable risk.

The clinical aim is to support safer thoracic surgery by making hazardous field states measurable, explainable, and ultimately preventable.

Examples of patient-relevant hazards include:

- unsafe vessel dissection under poor visibility
- persistent blood contamination after irrigation or hemostasis
- tissue or instrument obstruction during critical maneuvers
- whiteout, glare, blackout, smoke, fog, or lens contamination during high-risk tasks
- visual conditions that may contribute to bleeding, prolonged operative time, prolonged air leak, delayed drainage recovery, or postoperative morbidity

The project must therefore remain clinically anchored. Metric construction, review sheets, validation, and aggregation must all point toward patient safety, operative difficulty, postoperative recovery, or prevention.

---

## 1. Core construct

## 1.1 Definition

**Task-critical visual hazard burden** is the time-integrated burden of visual field states that may interfere with safe recognition, judgment, dissection, division, hemostasis, or lymph node dissection during a clinically meaningful surgical task.

A simplified model is:

```text
visual hazard burden = visual hazard severity x duration x task criticality
```

This is different from generic image quality. A visually degraded frame during specimen extraction may have low clinical risk, whereas a similar frame during pulmonary artery dissection may have high clinical risk.

## 1.2 Layers

```text
Layer 1: Frame-level visual hazard components
Layer 2: Component-specific visual validation
Layer 3: Phase / field / task-critical temporal burden
Layer 4: Clinical association and prevention-oriented interpretation
```

Surgeon-rated usability is an intermediate validation target, not the final clinical endpoint.

---

## 2. Non-negotiable design principles

## 2.1 No composite before component validation

Do not construct or report a composite visual hazard score until each candidate component has passed component-specific validation.

Composite scores can hide false-positive and false-negative behavior. They must be introduced only if they improve clinical relevance, hazard detection, or outcome association compared with individual components.

## 2.2 Name metrics by image property, not hoped-for clinical cause

Each metric should be named according to the image property it actually measures.

Do not interpret a metric as blood, smoke, glare, anthracosis, or obstruction unless component-specific validation supports that interpretation.

Examples:

```text
Good: reblur_response_loss_v1
Bad: blur_score as a clinical claim

Good: anthracosis_like_blackness_candidate_v1
Bad: anthracosis_score before validation

Good: blood_like_redness_v1
Bad: blood_score before validation
```

## 2.3 Separate raw photometric hazards from corrected material phenotype candidates

Whiteout, specular reflection, and blackout are photometric hazards. They should be measured on the raw image because the illumination problem itself is the hazard.

Blood-like redness and anthracosis-like blackness are material or phenotype candidates. They require color normalization, illumination-aware interpretation, exclusion rules, and manual validation.

## 2.4 Raw and corrected blackness must both be retained

Blackness in surgical video is confounded by:

- shadow
- underexposure
- black instruments
- camera border / outside-body background
- cautery marks
- black lymph nodes
- pleural anthracosis
- true carbon deposition

Therefore, blackness should be tracked as:

```text
blackness_raw_ratio_v1
blackness_corrected_ratio_v1
anthracosis_like_blackness_candidate_v1
low_light_or_blackout_ratio_v1
```

Do not interpret blackness as anthracosis unless it remains plausible after illumination normalization and is validated against manual labels.

## 2.5 Preserve legacy outputs

Existing columns must not be removed or silently redefined:

```text
focus_badness_v1
blur_score
smoke_fog_score
exposure_score
glare_score
local_obstruction_ratio
composite_degradation_score
```

Research-facing aliases may be added, but legacy columns must remain available.

---

## 3. Current implementation status

## 3.1 Existing frame-level script

Current script:

```text
05_compute_blur_smoke_glare.py
```

This script actually computes a focus-based structural visibility metric, not just blur, smoke, or glare.

Key implemented outputs:

```text
focus_badness_v1
blur_like_mean
veil_smoke_mean
saturation_ratio
specular_ratio
focus_lost_center_weighted_ratio
composite_degradation_score
```

Current interpretation:

```text
focus_badness_v1                  -> structural visibility loss proxy
blur_like_mean                    -> reblur response loss proxy
veil_smoke_mean                   -> veil / low-contrast proxy
saturation_ratio                  -> whiteout / saturation ratio
specular_ratio                    -> specular-like ratio
focus_lost_center_weighted_ratio  -> center low-structure area proxy
```

## 3.2 Existing burden script

Current script:

```text
13_compute_rule_based_badness.py
```

This computes case-level statistics using global percentile thresholds and event-like summaries.

Current implemented summary types:

- mean / median / p90 / p95 / p99 / max
- p95 / p99 / p99.5 exceedance ratios
- top 1% mean
- top 0.5% mean
- bad-segment count
- maximum continuous bad duration

This is the basis for future task-critical visual hazard burden.

## 3.3 Existing review script

Current script:

```text
25_evaluate_focus_goodness_v1.py
```

This creates review sheets sorted by `focus_badness_v1`. It should be generalized to arbitrary component metrics.

---

## 4. Metric definitions and references

Detailed metric definitions are maintained in:

```text
docs/METRIC_CALCULATION_REFERENCE.md
```

That document must be updated whenever a metric definition changes.

Current status:

| Metric | Status | Source |
|---|---|---|
| `structural_visibility_loss_v1` | implemented | alias of `focus_badness_v1` |
| `reblur_response_loss_v1` | implemented | alias of `blur_like_mean` |
| `veil_low_contrast_score_v1` | implemented | alias of `veil_smoke_mean` |
| `whiteout_ratio_v1` | implemented | alias of `saturation_ratio` |
| `specular_like_ratio_v1` | implemented | alias of `specular_ratio` |
| `center_low_structure_area_v1` | implemented | alias of `focus_lost_center_weighted_ratio` |
| `low_light_or_blackout_ratio_v1` | implemented in bootstrap v2 | raw low-V ratio |
| `blackness_raw_ratio_v1` | implemented in bootstrap v2 | raw dark-pixel candidate |
| `blackness_corrected_ratio_v1` | implemented in bootstrap v2 | illumination-normalized dark candidate |
| `anthracosis_like_blackness_candidate_v1` | implemented in bootstrap v2 | raw-and-corrected blackness candidate |
| `blood_like_redness_v1` | planned | red-dominance candidate, PBP-inspired |
| `visual_hazard_burden` | planned | severity x duration x task criticality |

---

## 5. GitHub governance

## 5.1 Repository strategy

This project should be maintained in GitHub.

The planning document should be committed and updated along with code. This allows AI-assisted implementation to restart from the plan, reduces drift, and provides reviewable history of decisions.

Recommended repository files:

```text
plans/PLAN_VISUAL_HAZARD.md
docs/METRIC_CALCULATION_REFERENCE.md
docs/COMPONENT_VALIDATION_PROTOCOL.md
docs/GITHUB_WORKFLOW.md
scripts/legacy/
scripts/05_compute_frame_visual_hazard_components.py
data/templates/component_review_rating_template.csv
README.md
.gitignore
.github/PULL_REQUEST_TEMPLATE.md
.github/ISSUE_TEMPLATE/component-validation.md
```

## 5.2 Pull request rule

Every PR must state:

1. Which PLAN phase it implements.
2. Which files it touches.
3. Which legacy columns it preserves.
4. Whether any metric definition changed.
5. What smoke checks or tests were run.
6. Whether the progress log was updated.

## 5.3 PHI rule

Do not commit raw videos, extracted frames, patient identifiers, clinical CSVs, or generated review sheets containing patient information.

Only code, plans, templates, and fully de-identified example fixtures may be committed.

---

## 6. Implementation phases

## Phase 0: Freeze legacy scripts

Goal:

Preserve current working behavior.

Actions:

- Copy current scripts into `scripts/legacy/`.
- Do not modify legacy copies.
- Use legacy scripts as reproducibility references.

Files:

```text
scripts/legacy/05_compute_blur_smoke_glare.py
scripts/legacy/13_compute_rule_based_badness.py
scripts/legacy/25_evaluate_focus_goodness_v1.py
```

Acceptance criteria:

- Legacy files exist.
- New code does not require modifying legacy files.
- Existing columns remain reproducible.

Status:

```text
Done in bootstrap package.
```

---

## Phase 1: Add research-facing aliases and raw/corrected photometric safeguards

Goal:

Keep legacy output but add safer research-facing metric names and raw/corrected photometric variables.

Implemented / intended aliases:

```text
structural_visibility_loss_v1 = focus_badness_v1
reblur_response_loss_v1 = blur_like_mean
veil_low_contrast_score_v1 = veil_smoke_mean
whiteout_ratio_v1 = saturation_ratio
specular_like_ratio_v1 = specular_ratio
center_low_structure_area_v1 = focus_lost_center_weighted_ratio
```

Additional photometric / blackness outputs:

```text
whiteout_center_weighted_ratio_v1
specular_center_weighted_ratio_v1
low_light_or_blackout_ratio_v1
low_light_center_weighted_ratio_v1
blackness_raw_ratio_v1
blackness_corrected_ratio_v1
blackness_raw_center_weighted_ratio_v1
anthracosis_like_blackness_candidate_v1
anthracosis_like_blackness_center_weighted_candidate_v1
```

Important:

- `anthracosis_like_blackness_candidate_v1` is not an anthracosis diagnosis.
- `low_light_or_blackout_ratio_v1` is a photometric hazard, not material blackness.
- `whiteout_ratio_v1` and `specular_like_ratio_v1` should be raw-image metrics.

Acceptance criteria:

- Script compiles.
- Legacy columns remain.
- New columns are added.
- No composite score is created.

Status:

```text
Implemented in bootstrap v2 script.
```

---

## Phase 2: Build component-specific review set

Goal:

Create a curated review set that tests each visual hazard component rather than only overall visual quality.

Required categories:

```text
clear field
defocus / lens fogging
smoke / fog / veil
whiteout / overexposure
specular reflection
low light / blackout
blood-like redness
anthracosis-like blackness
instrument / tissue / clot obstruction
low-information flat field
bloody but usable field
clean but not usable field
dark shadow without anthracosis
black instrument or camera border
```

Outputs:

```text
data/annotations/component_review_frames.csv
data/annotations/component_review_clips.csv
```

Acceptance criteria:

- Each category has positive and negative examples.
- Ambiguous examples are intentionally included.
- Image/clip identifiers are de-identified.
- No patient-identifying data is committed.

Status:

```text
In progress in phase-02-component-review-set branch.
Initial scripts added:
- scripts/06_build_component_review_set.py
- scripts/07_export_component_review_sheets.py
- docs/PHASE_02_COMPONENT_REVIEW_SET.md
```

---

## Phase 3: Export arbitrary-metric review sheets

Goal:

Generalize focus-only review sheets to any component metric.

New script:

```text
scripts/07_export_component_review_sheets.py
```

Inputs:

```text
component_review_frames.csv
per-frame metric CSVs
```

Required sorting metrics:

```text
structural_visibility_loss_v1
reblur_response_loss_v1
veil_low_contrast_score_v1
whiteout_ratio_v1
specular_like_ratio_v1
low_light_or_blackout_ratio_v1
blackness_raw_ratio_v1
blackness_corrected_ratio_v1
anthracosis_like_blackness_candidate_v1
center_low_structure_area_v1
```

Acceptance criteria:

- Each metric can generate high-to-low and low-to-high sheets.
- Missing optional metrics do not crash the script.
- Review sheets include case/time/metric labels.
- Review sheets are not committed if they contain PHI.

---

## Phase 4: Component-specific surgeon rating

Goal:

Validate whether each metric measures its intended visual phenomenon.

Template:

```text
data/templates/component_review_rating_template.csv
```

Primary validation label:

```text
overall_task_critical_visual_hazard_rating
```

Secondary labels:

```text
structural_visibility_loss_rating
blur_defocus_rating
smoke_fog_veil_rating
whiteout_overexposure_rating
specular_reflection_rating
low_light_blackout_rating
blood_contamination_rating
black_anthracosis_like_rating
shadow_rating
physical_obstruction_rating
surgical_usability_rating
```

Acceptance criteria:

- At least two reviewers, preferably three.
- Component labels separated from overall hazard.
- Shadow and blackness labels are separated.
- Usability is recorded but treated as an intermediate validation target.

---

## Phase 5: Component validity analysis

Goal:

Decide which components are usable, need revision, or should be dropped.

New script:

```text
scripts/15_validate_visual_hazard_components.py
```

Required outputs:

```text
reports/validation/component_spearman.csv
reports/validation/component_auc.csv
reports/validation/inter_rater_reliability.csv
reports/validation/false_positive_examples/
reports/validation/false_negative_examples/
```

Analysis:

- Spearman correlation between metric and matching rating.
- AUC for positive/negative component label where appropriate.
- False-positive review.
- False-negative review.
- Reviewer agreement.
- Illumination stress test for white/black/red metrics.

Acceptance criteria:

- No composite score until this phase is reviewed.
- Any metric with major failure modes must be renamed, modified, or dropped.

---

## Phase 6: Add blood-like redness metric

Goal:

Add a PBP-inspired redness component without overclaiming blood detection.

Planned metrics:

```text
blood_like_redness_v1
blood_like_center_weighted_ratio_v1
```

Principles:

- Use conservative color-normalized red-dominance masks.
- Do not call it `blood_score` before validation.
- Validate against `blood_contamination_rating`.
- Analyze residual post-irrigation redness separately when phase labels allow.

Acceptance criteria:

- Component review shows obvious blood examples ranked high.
- Red tissue and vessels are documented false positives or reduced by rules.
- No clinical interpretation until validation.

---

## Phase 7: Generalize burden aggregation

Goal:

Extend case-level burden into phase / field / task-critical burden.

New script:

```text
scripts/13_compute_visual_hazard_burden.py
```

Groupings:

```text
case_id
case_id + phase_label
case_id + field_label
case_id + phase_label + field_label
case_id + task_criticality_group
```

Burden metrics:

```text
mean
median
p90 / p95 / p99
max
bad_frame_ratio
severe_bad_frame_ratio
top1pct_mean
event_count
max_continuous_hazard_sec
hazard_auc
threshold_exceedance_auc
```

Acceptance criteria:

- Reproduces legacy case-level output when using `composite_degradation_score` and `case_id` only.
- Supports multiple component scores.
- Does not require composite score.

---

## Phase 8: Add task-criticality

Goal:

Weight visual hazards by clinical task importance.

Initial categories:

```text
high-risk task
intermediate-risk task
low-risk task
```

Initial high-risk candidates:

- pulmonary artery dissection
- vessel division
- bronchial dissection
- fissure division near vessels
- mediastinal lymph node dissection
- hemostasis confirmation

Initial low-risk candidates:

- extracorporeal handling
- specimen retrieval
- non-critical camera repositioning

Output:

```text
task_critical_visual_hazard_burden
```

Acceptance criteria:

- Weights are documented.
- Sensitivity analyses use alternative weights.
- No claim of causality from weights alone.

---

## Phase 9: Clinical association

Goal:

Test whether visual hazard burden is clinically meaningful.

Candidate outcomes:

```text
operative_time
console_time
blood_loss
drain_duration
drainage_volume
prolonged_air_leak
postoperative_complication
conversion
length_of_stay
```

Initial analysis:

- exploratory univariable associations
- missingness report
- prespecified primary endpoint before confirmatory analysis
- covariate-adjusted models only when sample size supports them

Acceptance criteria:

- Analysis clearly states exploratory vs confirmatory.
- Patient benefit pathway is explicit.
- No causal overclaim.

---

## Phase 10: Decide whether to construct a composite score

Composite score is optional.

Create a composite only if:

1. component metrics have passed validation;
2. components provide complementary information;
3. composite improves surgeon-rating agreement or clinical outcome association;
4. composite remains interpretable;
5. component metrics remain reported separately.

If these conditions are not met, do not create a composite. Use component-specific burden instead.

---

## 7. Immediate next actions

1. Commit updated planning docs and bootstrap code to GitHub.
2. Run `py_compile` on the bootstrap script.
3. Run the script on one de-identified case or a small local fixture.
4. Inspect the added raw/corrected photometric columns.
5. Build the component-specific review set.
6. Generate high-to-low review sheets by component.
7. Start surgeon rating only after the review set is stable.

---

## 8. Progress log

### 2026-06-24

Updated project direction:

- Reframed the project around patient-relevant task-critical visual hazard burden.
- Explicitly blocked composite score construction before component validation.
- Added raw photometric vs corrected material phenotype distinction.
- Added raw/corrected blackness handling.
- Added GitHub governance plan.
- Added metric calculation reference and component validation protocol.
- Added review rating template and PR/issue templates.
- Updated bootstrap script to add raw/corrected photometric and blackness candidate outputs while preserving legacy columns.

Current status:

```text
Phase 0: done
Phase 1: done in bootstrap v2
Phase 2: in progress
```

### 2026-06-24 Phase 2 update

Added component-specific review set scaffolding:

- `scripts/06_build_component_review_set.py` selects high-score and low-score candidate frames per component metric.
- `scripts/07_export_component_review_sheets.py` exports montage sheets grouped by target component and selection direction.
- `docs/PHASE_02_COMPONENT_REVIEW_SET.md` defines commands, acceptance criteria, and manual curation rules.
- `data/templates/component_review_seed_template.csv` allows manually seeded examples to be appended.
- Generated `data/annotations/` and `reports/` outputs remain ignored by Git to avoid committing surgical images or local paths.

