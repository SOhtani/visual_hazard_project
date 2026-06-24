# Metric Calculation Reference

This document records how each visual hazard component relates to prior reports and how it is implemented or planned in this project.

## Core rule

Name each metric according to the image property it actually measures, not according to the clinical phenomenon it is hoped to represent.

Clinical interpretations such as blood, smoke, glare, anthracosis, or obstruction should be assigned only after component-specific validation.

## Current and planned metrics

| Research-facing metric | Legacy/current source | Status | Meaning |
|---|---|---|---|
| `structural_visibility_loss_v1` | `focus_badness_v1` | implemented | Patch-level structural information loss |
| `reblur_response_loss_v1` | `blur_like_mean` / `blur_score` | implemented | Low response to additional Gaussian blur; high-frequency loss proxy |
| `veil_low_contrast_score_v1` | `veil_smoke_mean` / `smoke_fog_score` | implemented | Low local contrast + low edge energy proxy |
| `whiteout_ratio_v1` | `saturation_ratio` / `exposure_score` | implemented | Raw saturation / near-white pixel ratio |
| `specular_like_ratio_v1` | `specular_ratio` / `glare_score` | implemented | Raw high-value low-saturation pixel ratio |
| `center_low_structure_area_v1` | `focus_lost_center_weighted_ratio` / `local_obstruction_ratio` | implemented | Center-weighted low-structure patch ratio |
| `low_light_or_blackout_ratio_v1` | new | implemented in bootstrap v2 | Raw very-low-value pixel ratio |
| `blackness_raw_ratio_v1` | new | implemented in bootstrap v2 | Raw dark-pixel candidate ratio |
| `blackness_corrected_ratio_v1` | new | implemented in bootstrap v2 | Dark-pixel candidate after illumination normalization |
| `anthracosis_like_blackness_candidate_v1` | deferred | retained as output only | Generic persistent dark-area candidate; anthracosis quantification deferred until lung/pleural-surface mask is available |
| `blood_like_redness_v1` | planned | not implemented | Red-dominant pixel candidate, inspired by PBP-like burden |
| `visual_hazard_burden` | planned extension of current aggregation | not implemented | Severity x duration x task criticality |

## 1. Structural visibility loss

### Prior method basis

Classical focus-measure literature uses focus operators such as Tenengrad, Laplacian variance, and entropy to quantify sharpness and structural information. Tenengrad is based on Sobel gradient energy, Laplacian variance measures second-derivative variation, and entropy measures gray-level information content.

### Project method

Patch-level focus is computed as:

```text
patch_focus = 0.45 * tenengrad_score + 0.30 * lapvar_score + 0.25 * entropy_score
```

Then:

```text
focus_badness_v1 = 1 - clip(0.45 * patch_focus_q90 + 0.55 * focus_coverage, 0, 1)
```

Research-facing alias:

```text
structural_visibility_loss_v1 = focus_badness_v1
```

This is not a pure blur detector. It is a structural visibility loss proxy.

## 2. Reblur response loss

### Prior method basis

Blur/focus literature often uses high-frequency, gradient, or Laplacian response. Capsule endoscopy image-quality studies have also used Gaussian blur to simulate poor focus or motion-related degradation.

### Project method

Use illumination-corrected grayscale image:

```text
reblur = GaussianBlur(illum_corr, sigma=1.2)
reblur_absdiff = abs(illum_corr - reblur)
reblur_response_local = local mean(reblur_absdiff)
reblur_response_loss_v1 = 1 - mean(robust_minmax(reblur_response_local))
```

This is a high-frequency loss proxy, not a validated blur detector.

## 3. Veil / low-contrast score

### Prior method basis

Endoscopic artifact taxonomies distinguish contrast loss, blur, smoke, fogging, and saturation as image-degrading factors. Laparoscopic video enhancement studies treat smoke, blur, and lens fogging as major causes of poor clarity.

### Project method

```text
veil_local = 0.60 * (1 - contrast_norm) + 0.40 * (1 - tenengrad_norm)
veil_low_contrast_score_v1 = mean(veil_local)
```

This is not a smoke detector. It is a low-contrast / low-edge veil proxy.

## 4. Whiteout ratio

### Prior method basis

Endoscopic artifact datasets include saturation / overexposure as an artifact class. Saturation is often operationalized as near-white or high-intensity pixels.

### Project method

Compute on raw image because whiteout is itself a hazard:

```text
whiteout_mask = (HSV V >= 0.98) or any RGB channel >= 0.98
whiteout_ratio_v1 = mean(whiteout_mask)
whiteout_center_weighted_ratio_v1 = center-weighted mean(whiteout_mask)
```

This should not be illumination-corrected away.

## 5. Specular-like ratio

### Prior method basis

Specular reflection detection in endoscopy often uses intensity, saturation, HSV features, RGB relationships, and spatial pattern. EAD-like artifact taxonomies treat specularity as a distinct artifact.

### Project method

Compute on raw image:

```text
specular_mask = (HSV V >= 0.90) and (HSV S <= 0.30)
specular_like_ratio_v1 = mean(specular_mask)
specular_center_weighted_ratio_v1 = center-weighted mean(specular_mask)
```

This is a specular-like proxy. It may pick up white tissue, fat, or metal reflection.

## 6. Center low-structure area

### Prior method basis

Endoscopic artifact taxonomies include instruments and occluding artifacts. However, true obstruction requires object or target segmentation, which is not yet available here.

### Project method

```text
low_focus_patch = patch_focus < focus_coverage_thr
center_low_structure_area_v1 = center-weighted mean(low_focus_patch)
```

This is not a true obstruction detector. It is a center-weighted low-structure proxy.

## 7. Low light / blackout

### Prior method basis

Underexposure and contrast failure are recognized photometric problems in endoscopic video quality literature.

### Project method

Compute on raw image because darkness itself can be a hazard:

```text
low_light_mask = HSV V <= 0.08
low_light_or_blackout_ratio_v1 = mean(low_light_mask)
low_light_center_weighted_ratio_v1 = center-weighted mean(low_light_mask)
```

This is a photometric hazard metric, not anthracosis.

## 8. Blackness descriptors; anthracosis deferred

### Project method

Raw and corrected representations are kept separately:

```text
blackness_raw_mask = raw V <= 0.25, excluding all-zero-like pixels
blackness_corrected_mask = illum_corr <= 0.25 and raw V <= 0.35
persistent_dark_area_candidate = blackness_raw_mask AND blackness_corrected_mask
```

Outputs:

```text
blackness_raw_ratio_v1
blackness_corrected_ratio_v1
blackness_raw_center_weighted_ratio_v1
anthracosis_like_blackness_candidate_v1  # retained output; not a Phase 2 review target
anthracosis_like_blackness_center_weighted_candidate_v1  # retained output; not a Phase 2 review target
```

Do not interpret any of these columns as anthracosis. Anthracosis quantification is deferred until lung or pleural-surface masking is available. In the current phase, use `raw_blackness` and `corrected_blackness` only as generic blackness descriptors.

## 9. Blood-like redness

### Prior method basis

Thoracoscopic blood-stain quantification has used blood pixel proportion and time-integrated burden such as SumPBP and post-flushing SumPBP.

### Planned project method

Initial implementation should use conservative color-normalized red-dominance masks and retain the term `blood_like_redness_v1` until validation:

```text
blood_like_mask = red-dominant HSV/RGB candidate mask
blood_like_redness_v1 = mean(blood_like_mask)
blood_like_center_weighted_ratio_v1 = center-weighted mean(blood_like_mask)
```

Longitudinal burden:

```text
redness_burden = sum(blood_like_redness_v1 * frame_duration)
post_irrigation_residual_redness_burden = same calculation after irrigation/hemostasis checkpoint
```

## 10. Visual hazard burden

### Prior method basis

Frame-level visual quantities become clinically meaningful when integrated over time and linked to outcomes. Blood-stain studies use time-integrated blood burden rather than a single frame.

### Planned project method

```text
visual_hazard_burden = sum(component_score(t) * duration(t) * task_criticality_weight(t))
```

Initial burden summaries should include:

- mean
- p90 / p95 / p99
- bad-frame ratio
- top 1% mean
- event count
- max continuous duration
- AUC

Composite hazard scores are blocked until component-specific validation is completed.
