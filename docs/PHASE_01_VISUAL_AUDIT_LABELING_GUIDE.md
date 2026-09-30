# Phase 01 Targeted Visual-Audit Labeling Guide

**Status:** internal development / calibration only  
**Dataset:** 136 frames selected from construct-specific retrieval strata  
**Purpose:** determine what visual phenomena are actually present in retrieved frames and how much each phenomenon impairs task-relevant operative-field visibility.

## 1. Core principle

The retrieval stratum is **not** the ground-truth label. A frame selected by a blur, smoke, lens, near-contact, glare, whiteout, low-light, or obstruction heuristic may ultimately receive any phenomenon label.

The reviewer must judge the image itself, blinded to:

- candidate stratum;
- metric values;
- percentile thresholds;
- case and time when feasible.

This 136-frame set is **not** an independent validation set and should not be used to estimate prevalence or final diagnostic performance.

## 2. What is being separated

For each visual phenomenon, record two distinct quantities:

1. **Phenomenon presence / visual burden** — how clearly and extensively the phenomenon is present in the frame.
2. **Visibility impairment** — how much that phenomenon reduces recognition of task-relevant structures, boundaries, or spatial relationships.

A phenomenon can be visually prominent but have little or no effect on the relevant operative field.

Example:

- blood/fluid presence = 3
- blood/fluid-related visibility impairment = 0

is valid if substantial blood is visible but does not obscure the task-relevant field.

## 3. Overall visibility impairment

Independent global surgeon judgment. Do **not** calculate this from component scores.

- **0**: task-relevant visual information is essentially intact.
- **1**: mildly degraded; recognition is essentially intact.
- **2**: clearly limits recognition, but the operative field remains interpretable.
- **3**: task-relevant structures, boundaries, or spatial relationships cannot be recognized reliably.
- **NA**: cannot be judged from the still image.

There is no required mathematical relation between Overall and component scores. Apparent inconsistencies should be reviewed, not automatically corrected.

## 4. Phenomenon presence / burden score

Use the same generic scale for all nine phenomena.

- **0**: absent.
- **1**: definitely present but focal/mild.
- **2**: clearly present and moderate in extent or intensity.
- **3**: extensive, dominant, or severe in the image.
- **U**: uncertain whether the phenomenon is truly present.

This score is about the phenomenon itself, not its clinical consequence.

## 5. Phenomenon-related visibility impairment score

Score only the visibility consequence attributable to that phenomenon.

- **0**: no meaningful effect on task-relevant visibility.
- **1**: mild contribution; recognition remains essentially intact.
- **2**: clearly limits recognition, but the field remains interpretable.
- **3**: severely limits or prevents reliable recognition.
- **NA**: attribution cannot be judged.

If presence = 0, impairment should normally be 0. If presence = U, impairment may be NA.

## 6. Phenomena

### A. Technical / visual-condition phenotypes

#### Blur / defocus / motion blur
Loss of spatial detail attributable to optical defocus or motion blur. Do not label a naturally smooth or low-texture tissue surface as blur solely because few edges are present.

#### Smoke / airborne veil
Airborne smoke, mist, or veil within the operative field. Judge visible smoke directly when identifiable. Do not equate generic low contrast with smoke.

#### Lens contamination / lens fogging
Blood, condensation, smear, droplets, fogging, or other contamination located on the imaging surface/lens. If the image does not permit confident distinction from field smoke/fluid, use presence = U and mechanism uncertain = Yes.

#### Glare / specular reflection
Bright reflection from tissue, fluid, instruments, or other surfaces. A white object is not automatically glare.

#### Whiteout / overexposure
Loss of visual information because a region is saturated/overexposed. A clearly textured white gauze or instrument is not whiteout simply because it is white.

#### Underexposure / blackout
Loss of visual information because the relevant field is too dark. A dark background is not impairment if the task-relevant region is adequately visible.

### B. Operative-field / camera-interaction phenotypes

#### Blood / fluid
Visible blood or fluid within the operative field. Score presence/burden independently from whether it obscures the relevant target. Do not infer inflammation from redness alone.

#### Physical obstruction
A physical object such as an instrument, gauze, specimen, tissue, or debris blocks the task-relevant view. The obstructing object may itself be sharply visible.

#### Near-contact / wall view
The camera is excessively close to or contacting tissue so that spatial context, boundaries, or orientation are lost. Redness is not required. Do not use the term red-out as the defining criterion.

## 7. Imaging-mode context

Record one of:

- Standard visible light
- Firefly / ICG
- Other
- Uncertain

Imaging mode is context, not visibility impairment.

## 8. Technical evaluability

**No** only for true technical invalidity such as unreadable/corrupt/no-signal/test-pattern/all-zero data.

Darkness, blood, smoke, whiteout, gauze obstruction, lens contamination, or near-contact are not technical invalidity when they represent a valid surgical image.

## 9. Mechanism uncertainty

Set **Yes** when the visual degradation is real but its cause cannot be confidently distinguished, for example:

- smoke vs lens fogging;
- blood in the field vs blood on the lens;
- near-contact vs a homogeneous tissue close-up.

Do not force a mechanism label merely because the frame was retrieved by a particular heuristic.

## 10. Confidence

How confident are you that you would give essentially the same rating under the same rules if you reviewed the frame again?

- **1**: low
- **2**: moderate
- **3**: high

## 11. What is not being labelled in this round

Do not label inflammation, adhesion, surgical difficulty, anthracosis, or outcome relevance in this 136-frame audit. These require separate clinically anchored definitions, anatomical context, and in some cases temporal information.

## 12. After this audit

The labels will be merged back to the hidden retrieval strata to determine:

- which retrieval routes actually enrich each phenomenon;
- which false-positive mechanisms dominate each route;
- whether additional examples are needed for specific constructs;
- which frames should enter the subsequent targeted calibration set;
- which retrieval heuristics require revision before independent validation.
