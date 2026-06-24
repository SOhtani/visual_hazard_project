# Component Validation Protocol

## Rationale

Composite visual hazard scores are not allowed until each component metric has been validated against phenomenon-specific visual labels. Composite scores can hide false-positive and false-negative behavior and can make clinical interpretation impossible.

## Required review-set categories

The component review set should intentionally include examples of:

- clear field
- defocus / lens fogging
- smoke / fog / veil
- whiteout / overexposure
- specular reflection
- low light / blackout
- blood-like redness
- instrument / tissue / blood clot obstruction
- low-information but normal flat field
- bloody but usable field
- clean but not usable field
- dark shadow / black instrument / camera border
- black instrument or camera border

## Rating columns

Use `data/templates/component_review_rating_template.csv` as the starting schema.

Primary validation target:

- `overall_task_critical_visual_hazard_rating`

Secondary component labels:

- `structural_visibility_loss_rating`
- `blur_defocus_rating`
- `smoke_fog_veil_rating`
- `whiteout_overexposure_rating`
- `specular_reflection_rating`
- `low_light_blackout_rating`
- `blood_contamination_rating`
- `shadow_rating`
- `physical_obstruction_rating`
- `surgical_usability_rating`

## Validation analyses

For each metric:

1. High-score montage.
2. Low-score montage.
3. Spearman correlation with the target label.
4. AUC for binary positive labels when appropriate.
5. False-positive library.
6. False-negative library.
7. Inter-rater reliability.

## Illumination stress test

Apply controlled transformations to a small curated subset:

- brightness x 0.7
- brightness x 1.3
- gamma 0.8
- gamma 1.2
- synthetic vignette
- synthetic local shadow

Expected behavior:

- `whiteout_ratio_v1` may increase with brightness; that is acceptable because whiteout is a photometric hazard.
- `low_light_or_blackout_ratio_v1` may increase with darkening; that is acceptable because blackout is a photometric hazard.
- `blood_like_redness_v1` should not change greatly with brightness alone.
- Anthracosis-specific rating is deferred until anatomical masking is available; current blackness descriptors should be rated only as generic dark-area behavior.
- `structural_visibility_loss_v1` should be relatively stable under mild brightness changes.
