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

## Phase 2B image validity candidate flags

Phase 2B adds candidate-only image validity flags for component review. It does not use workflow phase annotations to exclude frames. See `docs/PHASE_02B_IMAGE_VALIDITY_GATE.md`.


Note: anthracosis-specific quantification is deferred until a lung or pleural-surface mask is available. The current Phase 2 review set keeps generic `raw_blackness` and `corrected_blackness` descriptors, but does not include `anthracosis_like_blackness_candidate` as a default review target.
