# Visual Hazard Project

## Phase 07 update: purpose-specific analyzable frame sets

The component cutoff audit showed that p95 component thresholds are too broad for hard exclusion before field-phenotype analysis. The project therefore separates technical image exclusion, color-phenotype analyzability, structural analyzability, and clean-reference extraction.

Run:

```powershell
python .\scripts\12_build_purpose_specific_analyzable_frame_sets.py `
  --frame-flags .\reports\visual_hazard_burden\visual_hazard_frame_flags.csv `
  --output-dir .\reports\purpose_specific_analyzable_frame_sets `
  --annotation-output-dir .\data\annotations `
  --write-frame-manifests
```

Primary downstream phenotype metrics such as blood-like redness and blackness/anthracosis-like burden should use `color_phenotype_analyzable_frames_v1.csv` as the main denominator, with severe visual-hazard component flags retained as soft flags rather than universal exclusions.

See `docs/PHASE_07_PURPOSE_SPECIFIC_ANALYZABLE_FRAME_SETS.md`.
