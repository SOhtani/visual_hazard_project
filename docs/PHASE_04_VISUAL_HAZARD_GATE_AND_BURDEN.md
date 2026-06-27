# Phase 04: Visual-hazard flags and burden summaries

## Purpose

Phase 04 converts component scores into exploratory visual-hazard flags and burden summaries.

The key distinction is:

- For hazard-burden analyses, bad frames are **counted**, not discarded.
- For clean-reference or downstream model-training analyses, bad frames may be **excluded** as non-clean candidates.

This phase therefore creates both:

1. visual-hazard-positive flags, and
2. clean-reference candidate flags.

## Default component profile

The default profile is `tier1_broad`:

- `structural_visibility_loss_v1`
- `center_low_structure_area_v1`
- `whiteout_ratio_v1`
- `low_light_or_blackout_ratio_v1`

A compact profile is also available:

- `center_low_structure_area_v1`
- `whiteout_ratio_v1`
- `low_light_or_blackout_ratio_v1`

The compact profile avoids double counting between whole-ROI structural loss and center-weighted structural loss.

## Thresholds

The default thresholds are `p95` and `p99`, taken from:

```text
reports/phase_component_distributions/global_component_candidate_cutoffs.csv
```

These remain candidate thresholds. They are distribution-based and require visual, surgeon-rating, and clinical-outcome validation.

## Outputs

The script writes:

```text
reports/visual_hazard_burden/visual_hazard_thresholds_used.csv
reports/visual_hazard_burden/case_visual_hazard_burden_summary.csv
reports/visual_hazard_burden/case_phase_visual_hazard_burden_summary.csv
reports/visual_hazard_burden/component_hazard_overlap_summary.csv
reports/visual_hazard_burden/top_visual_hazard_cases.csv
```

Optional full frame-level flags can be written with `--write-frame-flags`:

```text
reports/visual_hazard_burden/visual_hazard_frame_flags.csv
```

The script also writes a review CSV compatible with `07_export_component_review_sheets.py`:

```text
data/annotations/visual_hazard_gate_audit_frames.csv
```

## Interpretation

`visual_hazard_any_p95` means that at least one selected component score is greater than or equal to its global p95 candidate threshold.

`clean_reference_candidate_p95` means that the frame is not visual-hazard-positive at p95 and is not marked as an image-validity problem candidate.

Do not use `visual_hazard_any` as a final clinical endpoint yet. It is a screening and burden summarization flag.

## Legacy badness

The previous badness-like value, `composite_degradation_score`, is currently an alias of structural visibility loss in the scaffold. It should be retained only as a legacy screening alias, not as an independent composite score.

A future composite score should be defined explicitly after component-level validation and clinical linkage analyses.
