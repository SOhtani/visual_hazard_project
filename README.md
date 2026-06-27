# Visual hazard project update: Phase 04

This update adds visual-hazard flags and burden summaries.

New file:

```text
scripts/09_build_visual_hazard_flags_and_burden.py
```

Documentation:

```text
docs/PHASE_04_VISUAL_HAZARD_GATE_AND_BURDEN.md
```

Typical command:

```powershell
python .\scripts\09_build_visual_hazard_flags_and_burden.py `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --cutoff-csv .\reports\phase_component_distributions\global_component_candidate_cutoffs.csv `
  --annotation-root "C:\Users\SOhtani2024\SurgCap\surgcap-project\data\raw\videos" `
  --output-dir .\reports\visual_hazard_burden `
  --component-profile tier1_broad `
  --threshold p95 p99 `
  --audit-threshold p95
```

Then export the audit montage:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\visual_hazard_gate_audit_frames.csv `
  --output-dir .\reports\visual_hazard_gate_audit_sheets `
  --draw-roi
```

ROI crop:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\visual_hazard_gate_audit_frames.csv `
  --output-dir .\reports\visual_hazard_gate_audit_sheets_roi `
  --crop-roi
```
