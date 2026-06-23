# Visual Hazard Project Bootstrap

This repository scaffold is for a thoracic surgical video project that quantifies task-critical visual hazard burden.

The goal is not to quantify visual quality for its own sake. The goal is to identify and quantify intraoperative visual hazard states that may contribute to patient harm, operative difficulty, postoperative morbidity, or preventable risk.

Start every coding session by reading:

- `plans/PLAN_VISUAL_HAZARD.md`
- `docs/METRIC_CALCULATION_REFERENCE.md`
- `docs/COMPONENT_VALIDATION_PROTOCOL.md`
- `docs/PHASE_02_COMPONENT_REVIEW_SET.md`
- `docs/GITHUB_WORKFLOW.md`

Do not construct a composite score until component-specific validation is completed.

## Current phase

```text
Phase 0: legacy preservation - done
Phase 1: component metric scaffold - done
Phase 2: component-specific review set - in progress
```

## Phase 2 quick start

Build candidate review frames from per-frame metric CSVs:

```powershell
python .\scripts\06_build_component_review_set.py `
  --metrics-dir .\data\derived\quality_metrics\per_frame `
  --output-csv .\data\annotations\component_review_frames.csv `
  --n-high 24 `
  --n-low 8 `
  --per-case-cap 3
```

Export montage sheets:

```powershell
python .\scripts\07_export_component_review_sheets.py `
  --review-csv .\data\annotations\component_review_frames.csv `
  --output-dir .\reports\component_review_sheets `
  --draw-roi
```

Generated annotations and review images may contain local paths, case identifiers, and surgical images. They are intentionally ignored by Git.
