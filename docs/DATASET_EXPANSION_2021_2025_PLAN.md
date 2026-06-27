# Dataset expansion plan: 2021-2025 RATS, VATS, open surgery

## Purpose

In parallel with the RATS method-development pipeline, the project should expand toward a comprehensive surgical-video cohort from 2021-2025.

The expanded cohort should include:

```text
approaches:
  RATS
  VATS
  open thoracotomy

procedures:
  anatomical lung resection
    lobectomy
    segmentectomy
  wedge / partial resection
```

This aligns the visual-hazard project with the broader multilayer surgical phase annotation project.

## Why expansion is needed

The 2023 RATS cohort is useful as a stable-view baseline. It is not the ideal dataset for testing whether side, sex, or procedure changes visual hazard burden.

The expanded cohort allows the study to ask broader questions:

```text
1. Does visual field stability differ between RATS, VATS, and open surgery?
2. Does camera/scope contamination burden differ by approach?
3. Do blood-like redness and blackness/anthracosis-like field phenotypes vary across cases?
4. Can videos identify difficult fields related to bleeding, inflammation, adhesions, smoking burden, or preoperative treatment?
5. Can task-critical burden be modeled by combining phase annotations with visual phenotype metrics?
```

## Recommended cohort architecture

Use a common case inventory across projects.

Minimum fields:

```text
case_id
case_uid
year
surgery_date
approach_group          # RATS / VATS / open / unknown
procedure_group         # lobectomy / segmentectomy / wedge / other
anatomic_resection      # yes/no
wedge_or_partial        # yes/no
side                    # Right / Left / unknown
target_lobe_or_segment
video_exists
annotation_exists
metadata_exists
video_path
annotation_path
operation_time_min
blood_loss_g
smoking_history
pack_years
preoperative_treatment
adhesion_or_inflammation_note
```

Not all variables are expected to be immediately available. The inventory should explicitly track missingness.

## Inventory script

A preliminary scanner is provided:

```powershell
python .\scripts\13_build_expanded_dataset_inventory_template.py `
  --video-root "C:\Users\SOhtani2024\SurgCap" `
  --metadata-csv "C:\Users\SOhtani2024\SurgCap\RATS_2021_2025_data\index\master_case_inventory_2021_2025_with_metadata.csv" `
  --output-dir .\reports\dataset_expansion_2021_2025
```

If the expanded VATS/open metadata live elsewhere, run the same script with the relevant video roots and metadata CSVs.

## Outputs

```text
reports/dataset_expansion_2021_2025/expanded_video_inventory_raw.csv
reports/dataset_expansion_2021_2025/expanded_video_inventory_summary.csv
reports/dataset_expansion_2021_2025/expanded_case_candidates_for_review.csv
```

The output is a review-ready inventory, not a finalized cohort. Do not commit generated reports or raw data.

## Relationship to phenotype analysis

The expanded cohort should not start by applying clinical conclusions from the 2023 RATS cohort. Instead:

```text
Step 1:
  apply image-validity and visual-hazard filters

Step 2:
  compute phenotype metrics on analyzable frames

Step 3:
  summarize phenotype burden by case, phase, approach, and procedure

Step 4:
  compare RATS/VATS/open after checking metadata completeness and sampling bias
```

## Future endpoints

The expanded dataset can support:

```text
technical visibility endpoints:
  camera/scope contamination burden
  field stability
  severe visual obstruction frequency

field phenotype endpoints:
  blood-like redness burden
  blackness/anthracosis-like burden
  inflammation/adhesion-like appearance

clinical endpoints:
  operation time
  blood loss
  conversion or approach change
  postoperative air leak
  complication markers
  smoking burden
  preoperative treatment
```
