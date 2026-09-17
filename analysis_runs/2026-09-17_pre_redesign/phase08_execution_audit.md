# Phase 08 execution audit

## Frozen source commit

640f779f27da2970832c42e0c9e538b78608884d

## Syntax check

PASS: python -m py_compile scripts/13_compute_color_field_phenotypes.py

## CLI check

PASS: --help completed successfully.

## Lean vs full-metadata manifest audit

- Lean rows: 514006
- Full-metadata rows: 514006
- Lean cases: 68
- Full-metadata cases: 68
- Case-level row-count mismatches: 0
- Full-metadata duplicate case_id/sample_time_sec keys: 0
- Shared-column row-wise mismatches: 0 for all tested shared columns

Interpretation:
Within the tested shared columns, the full-metadata manifest represents the same ordered frame set as the lean manifest, with additional sample_time_sec, image_path, workflow, and hazard metadata.

## Lean-manifest Phase 08 smoke test

FAIL.

Error:
ValueError: Could not construct merge key: need a time or frame-index column.

Interpretation:
The lean Phase 07 manifest does not retain sample_time_sec or frame_index, so the Phase 08 metadata attachment logic cannot reconstruct a stable join key.
The frozen source commit is retained unchanged.

## Full-metadata Phase 08 smoke test

PASS.

- Exit code: 0
- Input manifest rows: 514006
- Filtered smoke-test rows: 600
- Cases: CASE010 and CASE066
- Maximum frames per case: 300
- Per-frame output rows: 600
- Global threshold rows: 35
- Case summary rows: 2
- Review CSV rows: 330
- Script completed with: [OK] color field phenotype metrics complete

Interpretation:
The frozen Phase 08 source code is executable when the full-metadata Phase 07 manifest is used.
The lean manifest failure is attributable to the absence of a stable frame-level time or frame-index join key.
This finding is retained as a pipeline design issue for the Phase 00 provenance audit.
