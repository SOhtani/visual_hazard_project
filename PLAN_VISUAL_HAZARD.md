# PLAN_VISUAL_HAZARD.md

# Task-critical visual hazard burden and field phenotype analysis in thoracic surgical videos

Last updated: 2026-09-17
Project status: planning document v1.1 - measurement-validity-first redesign active
Current cohort: RATS anatomical lung resection, 68 cases; 519,199 raw metric frames, 519,198 Phase 09 metric-status-eligible frames
Current analytic stage: Phase 00 provenance audit substantially completed; Phase 01 surgeon reference-standard design next

This document is the controlling planning document for the visual hazard project. Any coding agent should read this document before modifying scripts, metric definitions, file paths, clinical-linkage logic, or downstream analysis plans.

---

## 0. Executive summary

The starting hypothesis of this project is that **how the operative field is seen in surgical video may itself carry clinical meaning**.

This project should not be reduced to a simple camera-contamination count, a scope-cleaning metric, or a scopist/scope-operator quality metric. Those are possible subdomains, particularly in non-robotic surgery, but the broader scientific target is whether **visible surgical field states** can be measured as:

1. **task-critical visual hazards** that interfere with safe recognition, judgment, dissection, division, hemostasis, lymph node dissection, or final inspection; and
2. **video-derived field phenotypes** that may reflect patient, disease, approach, or tissue characteristics such as bleeding tendency, inflammation/adhesion, smoking-related anthracosis, prior treatment effect, or approach-dependent field stability.

Current implementation has established the first reusable measurement layer:

```text
Frame-level visual hazard components
    -> visual_hazard_any_p95 / visual_hazard_any_p99 gate
    -> case-level burden
    -> phase-level burden
    -> clinical metadata linkage
```

The next step is not to build a composite score. The next step is to separate:

```text
A. generic visual hazard gate
B. phenotype-specific modules
C. task-critical weighting
D. clinical association analysis
```

---

## 0.1 Active redesign: measurement-validity-first workflow

**Effective date: 2026-09-17**

This section defines the active execution order. The later historical plan is
retained as long-term design context.

Legacy analysis code and historical outputs must not be deleted or silently
rewritten.

### Rationale for redesign

Phase 00 provenance auditing established the actual lineage of the current
2023 RATS frame dataset:

```text
Raw per-frame metric dataset
519,199 frames / 68 cases
    |
    | metric_status filtering
    | CASE044 t=6637, all_zero_image: 1 frame removed
    v
Phase 09 visual_hazard_frame_flags.csv
519,198 frames
    |
    | low_light_or_blackout p99 exclusion
    | 5,192 frames removed
    v
Legacy color_phenotype_analyzable_frames_v1
514,006 frames
```

The Phase 09 to Phase 07 reduction is exactly explained by
`hazard_ge_low_light_or_blackout_p99`, with zero membership mismatches.

The seven image-validity candidate columns are present in the raw per-frame
metric data but are not propagated into the Phase 09 frame-level export:

```text
near_uniform_frame_candidate_v1
large_whiteout_candidate_v1
large_blackout_candidate_v1
color_bar_or_test_pattern_candidate_v1
photometric_failure_candidate_v1
image_validity_problem_candidate_v1
component_review_valid_candidate_v1
```

The propagation break occurs at the Phase 09 export step, where the explicit
`keep_cols` selection does not retain these seven validity columns.

Consequently, the audited Phase 07 run had no available hard technical reason
columns and technical exclusion removed zero frames.

Therefore, the legacy 514,006-frame color phenotype dataset must not be
described as a technically quality-filtered dataset. It is a purpose-specific
subset created by excluding low-light/blackout p99 frames from the Phase 09
metric-status-eligible dataset.

### Active first-report objective

The first report is a **measurement-validity study**.

Primary question:

> Do image-derived metrics correspond to thoracic surgeons' judgment of
> impairment of task-relevant operative-field visibility?

The first report is not yet:

```text
a validated patient-risk model
a clinical outcome-prediction model
a validated task-critical hazard-burden model
a causal model
```

### Construct separation

The redesigned pipeline must explicitly separate three constructs.

#### A. Technical image validity

Technical validity concerns acquisition, decoding, or data failures that make
a frame unsuitable for image measurement.

Examples:

```text
all-zero image
corrupt or unreadable image
decoder failure
no-signal frame
test pattern / color bar
other demonstrable acquisition or data failure
```

Technical invalidity should be cause-based.

A percentile threshold on a visibility metric is not, by itself, evidence of
technical invalidity.

#### B. Visual degradation / visibility impairment

This is the primary measurement construct.

Candidate causes include:

```text
structural information loss
blur / defocus
smoke / fog / veil-like low contrast
blood or fluid contamination
whiteout / overexposure
underexposure / blackout
specular reflection
instrument or tissue obstruction
near-contact / red-out
lens contamination
```

These conditions can occur during genuine surgery and must not automatically
be discarded as technical failures.

#### C. Purpose-specific analyzability

Purpose-specific analyzability is a downstream analytic decision rather than a
universal definition of image validity.

Examples:

```text
technical_analyzable_frame
visibility_validation_analyzable_frame
color_phenotype_analyzable_frame
structural_phenotype_analyzable_frame
clean_reference_frame
```

Different analyses may legitimately use different exclusions. Every exclusion
must retain a machine-readable reason and remain traceable to the original
frame.

### Mandatory frame-level data contract

Every redesigned frame-level table must retain at least:

```text
case_id
sample_time_sec
image_path
metric_status
```

Preserve when available:

```text
frame_idx_1based
sample_ordinal
segment_id
ROI coordinates
workflow / phase labels
technical-validity candidate columns
visibility component metrics required downstream
```

For the current 2023 cohort, the audited key `case_id + sample_time_sec` is
unique and can serve as the current frame-level join key.

A downstream export must not discard the identifier required to reconstruct
image path, ROI, workflow labels, or technical-validity information.

Missing required provenance or validity columns must produce an explicit error
rather than silently defaulting to no exclusion.

### Phase 00: provenance and pipeline audit

**Goal:** establish what the historical pipeline actually did before modifying
its behavior.

**Status: substantially completed on 2026-09-17**

Confirmed findings:

1. Raw per-frame metric denominator: **519,199 frames / 68 cases**.
2. Phase 09 denominator: **519,198 frames**.
3. One CASE044 frame at `sample_time_sec=6637` is removed because
   `metric_status=all_zero_image`.
4. Legacy color phenotype manifest: **514,006 frames**.
5. The Phase 09 to Phase 07 loss of **5,192 frames** is exactly the
   `low_light_or_blackout p99` exclusion.
6. Technical exclusion contributed **0 frames** in the audited Phase 07 run.
7. Seven technical-validity candidate columns are lost at the Phase 09
   frame-level export.
8. The lean Phase 07 manifest loses the stable time/frame identifier required
   by the frozen Phase 08 metadata reattachment logic.
9. The full-metadata Phase 07 manifest represents the same 514,006-frame
   subset and successfully reproduces the frozen Phase 08 smoke test.

Phase 00 acceptance criteria:

```text
[x] pre-redesign source code frozen in Git
[x] pre-redesign tag created and pushed
[x] analysis environment recorded
[x] historical commands recorded
[x] canonical frame counts established
[x] source -> Phase 09 -> Phase 07 lineage established
[x] technical-validity propagation break localized
[ ] final Phase 00 findings committed
[ ] redesigned frame-level data contract approved before implementation
```

Historical outputs are reproducibility artifacts. Do not repair historical CSVs
in place. Corrections must generate new, versioned outputs.

### Phase 01: surgeon reference standard and measurement-validity design

**Goal:** define an independent surgeon reference standard before selecting,
tuning, or promoting image-derived visibility metrics.

Minimum review fields:

```text
technical_evaluable
visibility_impairment: 0 none / 1 mild / 2 moderate / 3 severe
predominant_impairment_causes: multi-select
confidence
needs_video_context
comment
```

Candidate causes include:

```text
blur_or_defocus
smoke_or_fog_or_veil
blood_or_fluid_contamination
glare_or_overexposure
underexposure_or_blackout
instrument_or_tissue_obstruction
lens_contamination
near_contact_or_red_out
other
uncertain
```

Start with approximately **30-50 enriched pilot items**. The pilot determines
whether still frames are sufficient or short video clips are required.

Development and validation must be separated at the **case level**.
Neighboring frames from the same case must not be divided between development
and validation sets.

Thresholds, transformations, metric selection, and reviewer-informed tuning
must occur only in the development data. The validation set must not be used
for iterative threshold tuning.

### Initial candidate metrics

Initial candidates include:

```text
structural_visibility_loss_v1
veil_smoke_mean / veil_low_contrast_score_v1
saturation_ratio / whiteout_ratio_v1
specular_ratio / specular_like_ratio_v1
local_obstruction_ratio  # legacy proxy; not validated as true physical obstruction
low_light_or_blackout_ratio_v1
```

Blood-related color metrics may be reintroduced only as revised candidates if
they are ready for independent validation.

No metric becomes a validated visibility metric solely because its name is
clinically intuitive or because it separates extreme images.

### First-report success criteria

The first report does not require a significant association with postoperative
outcomes.

Minimum success is:

1. explicit and clinically interpretable measurement construct;
2. reproducible and auditable frame-level pipeline;
3. independent surgeon reference standard;
4. case-level development / validation separation;
5. at least one image-derived component with interpretable validation results;
6. transparent reporting of negative or failed components.

### Deferred until measurement validity is established

```text
severity * duration * task_criticality composite burden
task-criticality weighting
clinical outcome prediction as the primary objective
causal interpretation
anthracosis inference without anatomical localization
pleural invasion prediction
SAM2-based semantic segmentation
real-time intervention recommendations
```

The long-term task-critical visual hazard framework remains a future project
destination. It should be constructed only after the underlying visibility
measurements have demonstrated validity.

### Implementation gate

No redesigned production pipeline should be implemented until the Phase 00
findings and Phase 01 reference-standard schema have been reviewed.

Before each implementation session, explicitly specify:

```text
files to modify
input table
output table
stable frame key
required columns
columns that must propagate unchanged
filter / exclusion reasons
expected row-count invariants
fail-fast schema checks
tests and acceptance criteria
```

---

## 1. Clinical objective

The project aims to quantify how the operative field appears in thoracic surgical video and determine whether these video-derived field states carry clinically useful information.

The goal is not to measure whether an image is aesthetically clear. The goal is to detect, explain, and eventually use intraoperative visual field states that may be linked to:

- operative difficulty;
- bleeding or blood-like contamination;
- inflammatory or adhesive tissue conditions;
- smoking-related or anthracosis-like visual phenotype;
- tissue phenotype after induction or other preoperative treatment;
- approach-dependent differences in field stability, especially RATS versus VATS/non-robotic surgery;
- task-critical visibility during pulmonary artery dissection, bronchial dissection, fissure division, lymph node dissection, hemostasis, and final inspection;
- postoperative risk signals such as drainage burden, prolonged air leak, complications, or operative delay.

The current RATS cohort should be viewed as a stable-field baseline. Future extension to VATS or other non-robotic procedures may reveal more variation related to scope operation, camera contamination, off-centering, field instability, and scope/scopist-related factors.

---

## 2. Central construct

## 2.1 Definition

**Task-critical visual hazard burden** is the time-integrated burden of visual field states that may interfere with safe surgical recognition, decision-making, and manipulation during a clinically relevant task.

A practical formulation is:

```text
visual_hazard_burden = visual_hazard_severity * duration * task_criticality
```

The same frame-level visual state has different clinical meaning depending on phase and task. For example, transient low visibility during specimen retrieval is not equivalent to low visibility during pulmonary artery dissection or hemostasis confirmation.

## 2.2 Related but distinct constructs

| Construct | Meaning | Current role |
|---|---|---|
| Image quality / optical fidelity | Whether the image is sharp, clear, well-exposed, and free of photometric failure | technical component measurement |
| Visual hazard | A visual state that may interfere with safe operative recognition or manipulation | current main analytic target |
| Field phenotype | Visual appearance that may reflect tissue, disease, patient, approach, or treatment characteristics | next major module |
| Task-critical burden | Visual hazard weighted by surgical task risk | future analysis layer |
| Camera/scope quality | Scope contamination, cleaning, centering, stability, scope operation | future approach/scope workflow module |

---

## 3. Relationship to prior literature and research directions

The calculation strategy should use prior literature where possible, while avoiding over-interpretation of unvalidated image features.

## 3.1 Endoscopic and laparoscopic image-quality literature

Prior endoscopic and laparoscopic image-quality work supports that blur, smoke/fog, glare, saturation, low contrast, specularity, and other artifacts are separable video phenomena.

Project implication:

- use artifact literature to define measurable image properties;
- do not assume that a technical image-quality metric is automatically a clinical hazard;
- validate component behavior visually and, where feasible, by surgeon review.

## 3.2 Thoracic blood-stain quantification

Thoracic video blood-stain quantification supports the idea that video-derived field appearance can be summarized over time and linked to postoperative or intraoperative variables.

Project implication:

- implement `blood_like_redness_v1` as a material-contamination candidate;
- distinguish active blood-like field, residual post-irrigation blood-like burden, and red tissue false positives;
- do not call red pixels blood until validated.

Preferred initial names:

```text
blood_like_redness_v1
blood_like_area_ratio_v1
blood_like_center_weighted_ratio_v1
post_irrigation_blood_like_burden_v1
```

## 3.3 Anthracosis, smoking, and carbonaceous field phenotype

Thoracic fields can contain black or carbonaceous visual patterns related to anthracosis, smoking exposure, lymphatic phenotype, or regional tissue appearance. However, blackness is heavily confounded by underexposure, shadow, black instruments, cautery, clots, camera border, and background.

Current decision:

- existing `anthracosis_like_blackness_candidate_v1` is not sufficiently specific;
- it should remain output-only or exploratory;
- it must not be used as a clinical anthracosis score until lung/pleural-surface masks or manual validation are available.

Potential future direction:

```text
blackness / anthracosis-like phenotype module
    -> lung/pleural surface mask if available
    -> exclusion of instruments/background/underexposure
    -> validation against smoking index, pathology, surgeon labels, or visual rating
```

## 3.4 RATS versus VATS/non-robotic surgery

RATS offers a relatively stable operative field. This makes the current RATS cohort useful for building baseline visual hazard and field phenotype metrics. In VATS/non-robotic surgery, field appearance may vary more due to camera operator behavior, lens contamination, off-centering, motion, and scope cleaning.

Project implication:

- current RATS analysis establishes measurement feasibility under relatively stable view conditions;
- future VATS/non-robotic expansion can test field-stability and scope-workflow hypotheses;
- approach comparison should not be attempted until RATS metrics are stable and validated.

## 3.5 Pathology-relevant field phenotype

Surgical video may contain disease- or tissue-relevant information beyond generic visibility, such as pleural invasion appearance, adhesions, treatment-related fibrosis, or inflammation-like tissue phenotype.

Project implication:

- field phenotype modules should be developed after the visual hazard gate is stable;
- phenotype-specific modules should be named cautiously, e.g. `blood_like`, `anthracosis_like`, `adhesion_like`, not definitive clinical labels;
- clinical linkage should be exploratory until validated labels or external endpoints are available.

---

## 4. Data and current status

## 4.1 Current analyzed cohort

Current frame-level processing and clinical linkage have been completed for:

```text
68 analyzed cases
519,198 analyzed frames
```

The case-level clinical linkage table currently contains:

```text
68 rows
120 columns
```

The clinical metadata merge audit showed:

```text
burden cases:   68
metadata cases: 73
merged cases:   68
```

## 4.2 Current visual hazard components

Tier 1 broad visual hazard profile currently uses four components:

```text
structural_visibility_loss_v1
center_low_structure_area_v1
whiteout_ratio_v1
low_light_or_blackout_ratio_v1
```

`visual_hazard_any_p95` is true if any Tier 1 component is at or above its global p95 threshold.  
`visual_hazard_any_p99` is true if any Tier 1 component is at or above its global p99 threshold.

## 4.3 Frame-level gate result

Current frame-level manifest counts:

```text
all frames:      519,198
clean_p95:       449,063 frames = 86.5%
hazard_p95:       70,135 frames = 13.5%
hazard_p99:       14,825 frames =  2.9%
```

Interpretation:

- p95 is a broad bad-image / visual hazard candidate gate;
- p99 is a severe visual hazard candidate gate;
- p95 clean reference frames can be used for clean/reference image sampling;
- hazard frames must not be removed from burden analyses; they are the phenomenon being measured.

## 4.4 Current case-level clinical signals

Preliminary clinical linkage suggests:

```text
operation_time_min vs seconds_visual_hazard_any_p95: rho approximately 0.40
operation_time_min vs seconds_visual_hazard_any_p99: rho approximately 0.29
operation_time_min vs frac_visual_hazard_any_p95:    near 0
operation_time_min vs frac_visual_hazard_any_p99:    near 0 or weak negative
```

Interpretation:

```text
Longer operations accumulate more visual hazard seconds,
but they do not necessarily have a larger fraction of visual hazard time.
```

Therefore:

- `seconds_*` is a total burden metric and is expected to be duration-sensitive;
- `frac_*` is the duration-normalized burden metric;
- both should be reported, but they answer different questions.

Preliminary blood-loss association is weak with the current Tier 1 visual hazard gate. This does not rule out a blood-related video signal because the current gate does not yet directly measure blood-like redness or post-hemostasis residual blood.

---

## 5. Current metric interpretation and decisions

## 5.1 Adopted / retained Tier 1 metrics

| Metric | Current interpretation | Status |
|---|---|---|
| `center_low_structure_area_v1` | center-weighted low-information / red-out / tissue-contact-like field | main candidate |
| `whiteout_ratio_v1` | saturated / whiteout photometric hazard | main candidate |
| `low_light_or_blackout_ratio_v1` | blackout or low-light hazard | main candidate |
| `structural_visibility_loss_v1` | global ROI structural information loss proxy | retained; overlaps with center low-structure |

## 5.2 Auxiliary metrics

| Metric | Current interpretation | Status |
|---|---|---|
| `reblur_response_loss_v1` | low high-frequency / reblur-response proxy | auxiliary |
| `veil_low_contrast_score_v1` | low contrast + low edge-energy proxy | auxiliary |
| `blackness_raw_ratio_v1` | generic dark area | auxiliary / phenotype candidate |
| `blackness_corrected_ratio_v1` | illumination-normalized dark area | auxiliary / phenotype candidate |

## 5.3 Reconsider / deferred metrics

| Metric | Reason |
|---|---|
| `specular_like_ratio_v1` | overlaps substantially with whiteout; requires redesign for small/local reflection |
| `anthracosis_like_blackness_candidate_v1` | currently generic blackness; not specific for anthracosis |
| `composite_degradation_score` | legacy alias of structural visibility loss; not an independent composite |

## 5.4 Composite score policy

A composite score is not the primary next step.

Composite scoring may be introduced only if:

1. component metrics have visual and/or surgeon validation;
2. components are complementary rather than redundant;
3. the composite improves clinically meaningful discrimination;
4. the composite remains interpretable;
5. overfitting risk is controlled.

Until then, report component-specific burden and visual-hazard OR gates.

---

## 6. Current implemented phases

## Phase 01: Repository and planning scaffold

Status: completed.

Key branch / commit history includes:

```text
main
phase-02-component-review-set
phase-02b-image-validity-gate
phase-03-all-case-distribution
phase-04-visual-hazard-gate
phase-05-clinical-linkage
phase-05b-clean-clinical-correlation
```

## Phase 02: Component review set

Status: completed.

Implemented:

- component-specific review frame selection;
- high/low review montage generation;
- ROI draw and ROI crop outputs;
- review of Tier 1 and auxiliary components.

Major decision:

```text
anthracosis-like candidate is excluded from default review targets and clinical interpretation.
```

## Phase 02B: Image validity candidate gate

Status: completed.

Implemented image validity columns including:

```text
near_uniform_frame_candidate_v1
large_whiteout_candidate_v1
large_blackout_candidate_v1
color_bar_or_test_pattern_candidate_v1
photometric_failure_candidate_v1
image_validity_problem_candidate_v1
component_review_valid_candidate_v1
```

Current role:

- exclude non-informative photometric failures when building clean reference sets;
- flag validity problems during visual audit;
- do not confuse image validity with clinical hazard burden.

## Phase 03: All-case component distributions and candidate cutoffs

Status: completed.

Implemented:

- all-case per-frame component scoring;
- global p90/p95/p99 candidate cutoffs;
- phase-specific p90/p95/p99 candidate cutoffs;
- case-level component distribution summaries;
- case-phase component distribution summaries;
- component correlation matrix.

Important findings:

- `composite_degradation_score` equals `structural_visibility_loss_v1` and is legacy alias only;
- `whiteout_ratio_v1` and `specular_like_ratio_v1` overlap substantially;
- `structural_visibility_loss_v1` and `center_low_structure_area_v1` are strongly related but not identical.

## Phase 04: Visual hazard gate and burden summary

Status: completed.

Implemented:

- `visual_hazard_any_p95` and `visual_hazard_any_p99` OR gates;
- case-level visual hazard burden;
- phase-level visual hazard burden;
- component overlap summary;
- top visual hazard cases;
- frame-level visual hazard flags;
- clean/hazard frame manifests.

Output manifests:

```text
data/annotations/clean_reference_frames_p95.csv
data/annotations/visual_hazard_frames_p95.csv
data/annotations/visual_hazard_frames_p99.csv
reports/visual_hazard_burden/visual_hazard_frame_flags.csv
```

## Phase 05: Clinical linkage

Status: completed.

Implemented:

- merge of case-level visual hazard burden with RATS metadata;
- case-level linkage table;
- phase burden wide table;
- group summaries by procedure, side, sex, target, and other metadata fields;
- preliminary numeric correlation table.

Key output:

```text
reports/clinical_linkage/case_visual_hazard_clinical_linkage.csv
```

## Phase 05B: Clean clinical correlation variable selection

Status: partially completed.

Improved:

- reduced hazard-vs-hazard self-correlation issue;
- allowed explicit `--clinical-col operation_time_min blood_loss_g age`.

Remaining issue:

- some metadata-derived numeric columns such as `original_case_id`, `video_exists`, availability flags, and inclusion flags can still appear in numeric correlation output.

Next fix:

```text
strict whitelist clinical correlation mode
```

Only clinically interpretable variables should be included in formal exploratory summaries.

---

## 7. Updated target pipeline

```text
Raw / extracted surgical frames
    ↓
ROI validation and image validity gate
    ↓
Frame-level visual hazard components
    ↓
Component-specific visual audit
    ↓
All-case component distributions and candidate cutoffs
    ↓
Visual hazard OR gate: p95 broad, p99 severe
    ↓
Case / phase burden summaries
    ↓
Clinical metadata linkage
    ↓
Strict clinical correlation and figure-ready summaries
    ↓
Phenotype-specific modules
      - blood-like redness
      - residual blood-like burden after hemostasis/irrigation
      - blackness / anthracosis-like field phenotype
      - adhesion/inflammation-like appearance if feasible
    ↓
Surgeon validation and task-critical weighting
    ↓
Clinical phenotype analysis and, later, approach comparison
```

---

## 8. Near-term implementation plan

## Phase 05C: Strict clinical correlation whitelist

Goal:

Make clinical correlation outputs interpretable and publication-ready at the exploratory level.

Actions:

1. Modify `10_build_clinical_linkage_table.py` or add a new script so that clinical variables are selected by strict whitelist.
2. Exclude technical metadata columns from clinical correlation output:

```text
original_case_id
video_exists
frames_exists
annotation_v2_exists
metadata_exists
include_candidate
include_level0
include_level1
include_level2
operation_time_available
blood_loss_available
```

3. Preferred initial clinical variables:

```text
operation_time_min
blood_loss_g
age
procedure_group
side
target_lobe_or_segment
sex
```

4. Keep Japanese duplicate columns as metadata but avoid duplicate correlations unless explicitly requested.

Acceptance criteria:

- no hazard-vs-hazard correlations in `numeric_spearman_correlations.csv`;
- no technical metadata columns in formal correlation output;
- `operation_time_min`, `blood_loss_g`, and `age` are present when available;
- output includes n and missingness per variable.

## Phase 06: Figure-ready exploratory outputs

Goal:

Create readable outputs for internal review and abstract/manuscript planning.

Actions:

1. Generate figure-ready CSVs for:

```text
operation_time_min vs seconds_visual_hazard_any_p95/p99
operation_time_min vs frac_visual_hazard_any_p95/p99
blood_loss_g vs visual hazard burden
procedure_group vs visual hazard burden
side vs visual hazard burden
phase-specific visual hazard burden
```

2. Generate simple plots or plot-ready tables:

```text
scatter_operation_time_vs_hazard_seconds
scatter_operation_time_vs_hazard_fraction
boxplot_procedure_group_hazard_fraction
boxplot_side_hazard_fraction
phase_burden_heatmap_table
```

3. Avoid overinterpretation.

Acceptance criteria:

- table/figure outputs are generated without committing PHI or raw images;
- plots are exploratory and labeled as such;
- seconds and fraction metrics are shown separately.

## Phase 07: Blood-like redness module

Goal:

Build the first field phenotype module that may connect more directly with bleeding, inflammation, adhesion, and post-treatment tissue state.

Initial columns:

```text
blood_like_redness_v1
blood_like_area_ratio_v1
blood_like_center_weighted_ratio_v1
blood_like_component_count_v1
blood_like_largest_component_ratio_v1
```

Design constraints:

- use cautious `blood_like` naming;
- exclude near-white saturated pixels and very dark pixels;
- document false positives from normal red tissue, vessels, warm lighting, and cautery;
- validate with visual review before clinical interpretation.

Potential downstream summaries:

```text
case_blood_like_burden
phase_blood_like_burden
post_hemostasis_blood_like_burden
post_irrigation_residual_blood_like_burden
```

## Phase 08: Field phenotype modules

Candidate modules:

```text
blackness / anthracosis-like phenotype
adhesion/inflammation-like phenotype
smoke/thermal haze phenotype
field instability / off-center field phenotype
instrument/tissue obstruction phenotype
```

Each module needs its own validation plan and cautious naming.

## Phase 09: Surgeon validation

Goal:

Validate whether metric-derived visual hazards and phenotype candidates match surgeon-perceived field states.

Design:

- sample clean, p95 hazard, p99 hazard, blood-like high, blackness high, and ambiguous frames;
- obtain ratings from at least two thoracic surgeons;
- rate overall task-critical visual hazard, surgical usability, blood-like contamination, blackness/anthracosis-like appearance, whiteout, blackout, and structural visibility.

Important:

Surgeon ratings are intermediate validation, not the final clinical endpoint.

## Phase 10: Task-critical burden

Goal:

Weight visual hazard by phase/task criticality.

Initial strategy:

- map Level-1 and later Level-2/Level-3 surgical phases to risk tiers;
- keep unweighted burden available;
- implement sensitivity analysis for task weights.

Initial high-risk tasks:

```text
pulmonary_artery_dissection
vessel_division
bronchial_dissection
fissure_division
mediastinal_node_dissection
hemostasis_confirmation
post_irrigation_inspection
```

## Phase 11: Clinical phenotype analysis

Goal:

Evaluate whether visual hazard or field phenotype measures are associated with clinically meaningful variables.

Candidate explanatory variables:

```text
procedure_group
side
target_lobe_or_segment
smoking_history
preoperative_treatment
adhesion
inflammation
surgeon_id
year
approach
```

Candidate outcomes:

```text
operation_time_min
blood_loss_g
drain_duration
drainage_volume
prolonged_air_leak
postoperative_complication
length_of_stay
conversion
```

Principles:

- first pass is exploratory;
- report sample size and missingness;
- avoid causality claims;
- use seconds and fractions separately;
- account for operation time when interpreting total seconds burden;
- defer multivariable models until sample size and event count justify them.

## Phase 12: Approach comparison

Goal:

Extend from RATS baseline to VATS/non-robotic procedures.

Hypotheses:

- non-robotic videos may have higher field instability, camera contamination, off-centering, and scope-operation variation;
- RATS may have more stable field but still meaningful field phenotype and task-critical hazards;
- approach differences should be analyzed only after RATS metrics are stable and validated.

---

## 9. Analysis principles and guardrails

## 9.1 Do not overname unvalidated metrics

Use cautious names:

```text
whiteout_ratio_v1
low_light_or_blackout_ratio_v1
center_low_structure_area_v1
blood_like_redness_v1
anthracosis_like_blackness_candidate_v1
```

Avoid unvalidated names:

```text
blood_score
anthracosis_score
inflammation_score
difficult_case_score
surgical_risk_score
```

## 9.2 Do not discard hazard frames from burden analysis

Hazard frames can be excluded from clean/reference frame extraction. They must not be excluded from hazard burden analysis.

Correct use:

```text
clean_reference_candidate_p95 -> clean image sampling
visual_hazard_any_p95/p99 -> burden outcome / exposure variable
```

Incorrect use:

```text
remove visual_hazard_any frames before calculating visual hazard burden
```

## 9.3 Seconds and fractions answer different questions

`seconds_*` is total accumulated burden and is expected to correlate with operation/video duration.  
`frac_*` is duration-normalized burden and answers whether a larger proportion of the operation had a visual hazard.

Report both.

## 9.4 Current RATS cohort is not sufficient for all intended claims

Current RATS analysis can support:

- feasibility of frame-level and case-level visual hazard quantification;
- initial clinical linkage;
- phenotype-module development;
- phase-level burden exploration.

It does not yet support:

- validated blood/anthracosis/inflammation phenotype claims;
- causal association with clinical outcomes;
- generalization to VATS/non-robotic surgery;
- real-time feedback claims.

---

## 10. Non-goals for the next implementation cycle

Do not implement yet:

- deep learning model training;
- real-time feedback;
- pleural invasion prediction;
- automatic anatomy segmentation;
- instrument segmentation;
- multivariable clinical modeling as primary evidence;
- external validation;
- formal approach comparison.

These require separate planning once the measurement layer is stable.

---

## 11. AI coding instructions

At the start of each coding session, the AI must summarize:

1. current phase;
2. files to modify;
3. columns to preserve;
4. metric definitions to preserve;
5. output files that should not be committed;
6. tests or commands to run;
7. assumptions and unresolved decisions.

The AI must not:

- silently rename existing columns;
- change the meaning of existing score columns;
- interpret red pixels as blood without validation;
- interpret black pixels as anthracosis without validation;
- create a primary composite score before component validation;
- remove hazard frames from burden analysis;
- include technical metadata columns as clinical variables in formal correlation outputs;
- commit raw video, frames, patient identifiers, PHI-bearing tables, or review images.

After each completed phase, update the Progress Log below.

---

## 12. Progress log

### 2026-06-23

Planning document v0.1 created.

Initial goal:

```text
Reframe image-quality measurement as task-critical visual hazard burden.
```

### 2026-06-24 to 2026-06-26

Implemented component review workflow and image validity candidate flags.

Major decisions:

- keep component metrics separate;
- do not use composite as primary;
- defer anthracosis-like candidate from default review.

### 2026-06-27

Completed all-case distributions, visual hazard gate, frame-level flags, case/phase burden summaries, and clinical linkage.

Current numeric status:

```text
68 analyzed cases
519,198 analyzed frames
clean_p95: 449,063 frames, 86.5%
hazard_p95: 70,135 frames, 13.5%
hazard_p99: 14,825 frames, 2.9%
```

Clinical linkage status:

```text
case_visual_hazard_clinical_linkage.csv: 68 rows x 120 columns
burden cases: 68
metadata cases: 73
merged cases: 68
```

Preliminary interpretation:

- visual hazard seconds correlate with operation time moderately;
- visual hazard fraction does not show the same operation-time relationship;
- blood loss association is weak with current Tier 1 gate;
- blood-like redness and field phenotype modules are needed for the next scientific question.

Next planned phase:

```text
Phase 05C: strict clinical correlation whitelist
Phase 06: figure-ready exploratory outputs
Phase 07: blood-like redness module
```

