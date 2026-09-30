# PHASE_04A_OPERATIVE_PHENOTYPE_ASSESSABILITY_PILOT

## Purpose
This pilot tests a prerequisite for future intraoperative decision support:

Can clinically meaningful operative phenotypes be judged from isolated image appearance, or does temporal operative context materially improve their assessability?

Long-term targets:
- macroscopic inflammatory change
- fibrotic-appearing tissue
- adhesion
- difficult / unclear dissection plane
- active bleeding

This pilot does not train or validate a real-time AI model. It tests what information such a model would need.

## Sampling
40 operative moments from the 2023 RATS cohort, selected without using clinical outcomes.

Target composition:
- 5 each from anterior_hilum, posterior_hilum, superior_hilum, inferior_hilum, fissure, subcarinal
- 10 additional moments from LeakHemostasis
- maximum one sampled moment per case
- deterministic seed 20260919

## Review conditions
Each operative moment is reviewed twice:
1. still image: central frame only
2. temporal context: 11-frame sequence from t-5 to t+5 seconds using the existing 1-Hz frames

Complete all still-image reviews before starting temporal-context review. The two passes use independently randomized blinded order.

## Annotation
For each phenotype, first record assessability:
- Assessable
- Uncertain
- Not assessable

If Assessable, record:
- Present
- Absent

Phenotype definitions:
- Macroscopic inflammatory-appearing change: visible inflammatory-type reaction such as edema, erythematous/friable appearance; not histopathologic proof.
- Fibrotic-appearing tissue: dense, scar-like, whitish or rigid-appearing tissue; not histopathologic proof.
- Adhesion: apparent abnormal adherence between tissue surfaces or structures.
- Difficult / unclear dissection plane: operative plane difficult to identify or maintain.
- Active bleeding: active emergence, flow or ongoing accumulation of blood; static redness or old blood alone is not active bleeding.

## Primary endpoint
For each phenotype:
temporal assessability rate - still assessability rate.

Primary paired test:
- exact McNemar test
- Holm correction across the 5 phenotypes

Uncertain is grouped with Not assessable for the primary binary endpoint; the original three categories remain in raw data.

## Secondary descriptive outputs
- temporal rescue: still uncertain/not assessable -> temporal assessable
- lost assessability: still assessable -> temporal uncertain/not assessable
- present/absent change among moments assessable in both conditions

Temporal-context review is not treated as a gold standard.

## Interpretation
If temporal context improves assessability, that supports future temporal/context-aware operative-phenotype models. It does not establish diagnostic accuracy, histologic validity, inter-rater reliability, real-time AI performance, or clinical benefit.
