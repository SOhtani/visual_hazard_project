# Phase 08 integrity follow-up

## Context

Frozen Phase 08 source commit:
640f779f27da2970832c42e0c9e538b78608884d

Provenance snapshot commit:
feff3282ec20e5dce06b9d4f9143041b45f9baba

## Smoke-test integrity findings

- CASE010 rows: 300
- CASE066 rows: 300
- color_metric_status=ok: 600/600
- workflow_level1_label nonmissing: 600/600
- workflow_level1_label: PortDockExplore in 600/600 frames
- workflow_level2_label nonmissing: 0/600
- case_phase_color_field_phenotype_summary rows: 0
- blood_like_redness_ratio_v1 nonmissing: 599/600
- fresh_red_candidate_ratio_v1 nonmissing: 599/600
- dark_red_brown_candidate_ratio_v1 nonmissing: 599/600
- blackness_candidate_ratio_v2 nonmissing: 600/600
- corrected_blackness_candidate_ratio_v2 nonmissing: 600/600
- anthracosis_like_blackness_candidate_v2 nonmissing: 600/600

## Audit interpretation

The zero-row case-phase summary is retained for later inspection.
In this smoke-test subset, workflow_level1_label is present in all 600 frames,
whereas workflow_level2_label is absent in all 600 frames.

One frame has missing redness-family metrics despite color_metric_status=ok.
The cause has not yet been established.
This is retained as an audit finding and is not corrected in the frozen Phase 08 source code.
