# PHASE_01_LITERATURE_METHOD_AUDIT.md

**Project:** RATS operative-field phenotyping / visibility calibration  
**Date:** 2026-09-18

## Core methodological lesson

Prior work does not support a single universal "poor visibility" sampling rule. Ground truth is usually constructed at the level that matches the phenomenon:

- local artefacts -> region / bounding-box / patch annotation;
- lens contamination -> clean/dirty lens-state annotation, with uncertain frames excluded;
- smoke -> temporal video sequences in which smoke emerges, paired with a nearby smoke-free view;
- blood -> manually labelled blood/non-blood pixels, then frame- and case-level aggregation;
- tissue/inflammatory phenotype -> standardized clinically meaningful view/ROI and expert grading;
- near-contact/red-out -> local/quadrant classification and temporal aggregation.

This supports construct-specific candidate retrieval plus a common blinded surgeon reference standard.

## Blood / bleeding phenotype

### Xu et al., European Journal of Cardio-Thoracic Surgery, 2022
DOI: 10.1093/ejcts/ezac154  
PMID: 35352106

- Thoracoscopic lobectomy videos were sampled at 1 frame/second.
- Blood recognition was calibrated using 10,000 blood pixels and 10,000 non-blood pixels randomly selected from 60 frames belonging to different patients.
- Independent validation used 1,000 blood and 1,000 non-blood pixels.
- Frame-level bleeding burden was the proportion of blood pixels (PBP).
- Case-level burden was SumPBP, the sum of frame-level PBP values, thereby incorporating amount and duration.
- A context-specific burden, SumPBP-Flushing, summed PBP from flushing to the end of surgery.
- These video-derived measures were then related to intraoperative bleeding and postoperative drainage/tube duration.

### Implication

Blood should be split into:
1. blood presence/burden;
2. blood-related visibility impairment.

These are not interchangeable.

## Smoke

### Xia et al., IEEE Transactions on Medical Imaging, 2025
DOI: 10.1109/TMI.2025.3584641  
PMID: 40601460

- Real in-vivo paired de-smoking dataset.
- Relatively stationary video sequences were identified in which smoke emerges.
- Motion tracking compensated for patient/camera movement.
- Smoky images were paired with nearby smoke-free views of the same scene.
- Final dataset included 41 sequences from 132 prostatectomies and 68 sequences from 45 cholecystectomies, yielding 3,000 paired images.

### Implication

Smoke candidate retrieval should use temporal emergence/recovery in addition to a veil/low-contrast preselector. Temporal behaviour is a retrieval heuristic, not the surgeon reference label.

### LVQIS caution

Zheng et al., Int J Comput Assist Radiol Surg, 2023  
DOI: 10.1007/s11548-022-02777-y  
PMID: 36243805

LVQIS used synthetic clear, motion-blur and smoke/fog datasets. This is useful for augmentation/restoration but less suitable as a precedent for defining real clinical positive frames.

## Lens contamination / fogging

### Sayani et al., Surgical Innovation, 2026 - LUCID
DOI: 10.1177/15533506261451747  
PMID: 42175973

- 77 de-identified laparoscopic cases, about 96 h.
- Frames/clips were labelled dirty when blood, condensation, smearing or other contaminants were on the lens.
- Clean meant a clear field without physical lens obstruction.
- Unsure/noise/out-of-body frames were excluded.
- Two independent annotators reviewed frames.
- Only about 60% could be confidently labelled clean or dirty and were used.
- Train/validation/test splits were performed at the video level.

### Implication

Lens contamination can remain an independent still-image construct. Temporal persistence/cleaning transitions can enrich candidates but need not define the ground truth.

## Local artefacts: specularity, saturation, blur

### Ali et al., Scientific Reports, 2020 - EAD2019
DOI: 10.1038/s41598-020-59413-5

- EAD treated artefacts as local and potentially overlapping.
- Classes included specularity, saturation, blur, contrast, bubbles, instrument and imaging artefact; blood was added in EAD2020.
- Thousands of frames had expert bounding-box annotations; selected classes also had segmentation masks.
- Multiple artefacts could coexist in the same image.

### Implication

Glare/specularity and whiteout/saturation should retain local area, centrality and largest-component information rather than relying only on whole-frame means.

## Near-contact / wall-view phenotype

### Artificial intelligence alert system based on intraluminal view for colonoscopy intubation, Scientific Reports, 2025
DOI: 10.1038/s41598-025-99725-y

- Red-out was linked to colonoscope-tip contact with mucosa.
- Each image was divided into four quadrants.
- Quadrants were labelled red-out, informative or non-informative.
- Expert colonoscopists performed classification; disagreement was resolved by voting, with consensus from at least 3 experts.
- For real-time analysis, 1 frame in every 10 was sampled.
- Video burden was quantified as the percentage of quadrants classified as red-out.

### Implication

For thoracic surgery, the useful precedent is local spatial assessment, not redness itself. Prefer the construct name `near-contact / wall-view impairment`.

Candidate retrieval should emphasize local low structure/edge/entropy and abrupt onset/recovery; redness should be only a secondary cue.

## Inflammation / adhesion and long-term phenotype layer

### Ward et al., Surgical Endoscopy, 2022
DOI: 10.1007/s00464-021-08929-8  
PMID: 35031869

- 200 laparoscopic cholecystectomy videos.
- Surgical phases, Parkland grade, CVS attainment and gallbladder injury were labelled.
- Parkland grade was assessed from the initial gallbladder view.
- The visual inflammation grade was linked to operative course.

**Lesson:** inflammatory phenotype should be anchored to a standardized clinically meaningful view, not arbitrary redness.

### Loukas et al., Int J Comput Assist Radiol Surg, 2021
DOI: 10.1007/s11548-020-02285-x  
PMID: 33146850

- 53 operations.
- 800 patches and 181 outlined gallbladder-wall regions.
- Two expert surgeons labelled vascularity with 2- and 3-class schemes.

### Loukas et al., Int J Med Robot, 2022
DOI: 10.1002/rcs.2445  
PMID: 35942601

- 234 gallbladder images from 68 videos.
- Multiple patches were sampled within a gallbladder ROI and aggregated using multiple-instance learning.

**Lesson:** tissue phenotypes should eventually be measured in the relevant anatomical tissue/ROI, not across the full frame.

### Abbing et al., Int J Med Robot, 2023
DOI: 10.1080/21681163.2022.2163296

- 93 laparoscopic cholecystectomy videos.
- Modified Nassar difficulty grade and adhesion grade were used as explicit labels.
- Early operative video appearance was used to predict difficulty.

**Lesson:** adhesion/difficulty should eventually be treated as explicit clinical constructs rather than inferred from generic image-quality scores.

## Recommended annotation architecture

For selected constructs, record both:

### Phenomenon presence / burden
Examples: blood amount, smoke amount, lens contamination state, physical obstruction extent.

### Task-relevant visibility impairment
Keep the current 0-3 component impairment score.

Example:

`blood burden = 3` and `blood-related visibility impairment = 0`

is valid if substantial blood is visible away from the operative target.

## Recommended candidate retrieval

- Blur: `focus_badness_v1` extremes + low-texture hard negatives.
- Smoke: `veil_low_contrast_score_v1` + temporal rise/recovery; include persistent low-contrast and lens-contamination hard negatives.
- Lens contamination: visually dirty frames + optional persistence/cleaning-transition enrichment.
- Glare: `specular_ratio` + local/center-weighted and connected-component features.
- Whiteout: `saturation_ratio` + local/center-weighted saturation; include white gauze as hard negative.
- Underexposure: low-light metric extremes, retaining human-negative dark frames.
- Physical obstruction: `center_low_structure_area_v1` and local maximum-component proxy.
- Near-contact/wall-view: local low structure + low edge/entropy + abrupt onset/recovery; redness secondary only.
- Blood/fluid: future blood-likelihood preselector inspired by Xu et al.; thoracic redness alone must not define ground truth.

## Sampling principles

- Exclude all existing 30 Phase-01 pilot moments.
- Blind reviewer to case, time, candidate method and metric values.
- Limit repeated samples from the same case.
- Include hard negatives deliberately.
- Preserve uncertain labels instead of forcing mechanism classification.
- Use case-level separation for later independent validation.
- Use temporal information for candidate retrieval while keeping the initial still-image rating blinded.

## Next implementation step

Before generating a 60-frame targeted manifest:

1. audit candidate-pool counts for each construct;
2. compute temporal deltas for smoke and near-contact retrieval;
3. add phenomenon-presence labels to the annotation specification;
4. review candidate diversity internally;
5. freeze the targeted sampling plan;
6. then generate the blinded manifest.
