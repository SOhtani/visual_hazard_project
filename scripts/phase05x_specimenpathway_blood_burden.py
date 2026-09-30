import importlib.util
import pandas as pd
import numpy as np
from pathlib import Path

VH = Path(r"C:\Users\SOhtani2024\visual_hazard_project")
spec = importlib.util.spec_from_file_location("bloodqc", str(VH / "scripts" / "phase05_apply_rats_blood_rule_visual_qc_gradable.py"))
bloodqc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bloodqc)

rats_rule = bloodqc.load_final_rule(VH / "reports" / "phase05_rats_blood_pixel_recalibration" / "rats_recalibrated_blood_pixel_rule.csv")
gate = bloodqc.load_gradability_gate(VH / "data" / "annotations" / "rats_blood_pixel_pilot_v2" / "rats_blood_pixel_annotation_v2_gradability_gate.csv")

flags = pd.read_csv(VH / "reports" / "visual_hazard_burden" / "visual_hazard_frame_flags.csv", usecols=["case_id", "sample_time_sec", "workflow_level1_label"])
flags = flags[flags["workflow_level1_label"] == "SpecimenPathway"].copy()
flags["sample_time_sec"] = pd.to_numeric(flags["sample_time_sec"], errors="coerce")

summaries = []
qc_rows = []
case_paths = bloodqc.case_files(VH / "data" / "derived" / "quality_metrics" / "per_frame")
n_cases = len(case_paths)
for idx, path in enumerate(case_paths, 1):
    case_id = bloodqc.case_id_from_file(path)
    print(f"[{idx}/{n_cases}] {case_id}")
    d = bloodqc.load_case(path)
    case_flags = flags[flags["case_id"] == case_id]
    if case_flags.empty:
        qc_rows.append({"case_id": case_id, "n_specimenpathway_frames": 0, "n_gradable_frames": 0})
        continue
    merged = d.merge(case_flags[["sample_time_sec"]], on="sample_time_sec", how="inner")
    n_specimenpathway = len(merged)
    gated = bloodqc.apply_gradability_gate(merged, gate)
    n_gradable = len(gated)
    qc_rows.append({"case_id": case_id, "n_specimenpathway_frames": n_specimenpathway, "n_gradable_frames": n_gradable})
    if n_gradable == 0:
        continue
    scored = bloodqc.score_case(gated, rats_rule, quiet=True)
    if len(scored) == 0:
        continue
    summary = bloodqc.case_summary(scored)
    summaries.append(summary)

out_dir = VH / "reports" / "phase05_specimenpathway_blood_burden"
out_dir.mkdir(parents=True, exist_ok=True)
summary_df = pd.DataFrame(summaries)
summary_df.to_csv(out_dir / "case_specimenpathway_blood_pbp_summary.csv", index=False)
qc_df = pd.DataFrame(qc_rows)
qc_df.to_csv(out_dir / "specimenpathway_frame_count_qc.csv", index=False)

print()
print("=== Saved ===")
print(str(out_dir / "case_specimenpathway_blood_pbp_summary.csv"))
print()
print("=== n cases with scored data ===", len(summary_df))
print()
print("=== Case-level RATS PBP distribution (median across cases) ===")
print(summary_df[["rats_mean_pbp", "rats_median_pbp", "rats_p90_pbp"]].median())
print()
print("=== Full per-case summary ===")
print(summary_df.to_string(index=False))
