import pandas as pd
import importlib.util
from pathlib import Path

VH = Path(r"C:\Users\SOhtani2024\visual_hazard_project")
spec = importlib.util.spec_from_file_location("bloodqc", str(VH / "scripts" / "phase05_apply_rats_blood_rule_visual_qc_gradable.py"))
bloodqc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bloodqc)

rats_rule = bloodqc.load_final_rule(VH / "reports" / "phase05_rats_blood_pixel_recalibration" / "rats_recalibrated_blood_pixel_rule.csv")
gate = bloodqc.load_gradability_gate(VH / "data" / "annotations" / "rats_blood_pixel_pilot_v2" / "rats_blood_pixel_annotation_v2_gradability_gate.csv")

flags = pd.read_csv(VH / "reports" / "visual_hazard_burden" / "visual_hazard_frame_flags.csv", usecols=["case_id", "sample_time_sec", "workflow_level1_label"])
flags["sample_time_sec"] = pd.to_numeric(flags["sample_time_sec"], errors="coerce")

case_paths = bloodqc.case_files(VH / "data" / "derived" / "quality_metrics" / "per_frame")
n_cases = len(case_paths)

all_scored = []
for idx, path in enumerate(case_paths, 1):
    case_id = bloodqc.case_id_from_file(path)
    print(idx, "/", n_cases, case_id)
    d = bloodqc.load_case(path)
    case_flags = flags[flags["case_id"] == case_id]
    merged = d.merge(case_flags[["sample_time_sec", "workflow_level1_label"]], on="sample_time_sec", how="left")
    gated = bloodqc.apply_gradability_gate(merged, gate)
    if len(gated) == 0:
        continue
    scored = bloodqc.score_case(gated, rats_rule, quiet=True)
    if len(scored) == 0:
        continue
    scored = scored.merge(gated[["sample_time_sec", "workflow_level1_label"]], on="sample_time_sec", how="left")
    all_scored.append(scored)

full_df = pd.concat(all_scored, ignore_index=True)
out_dir = VH / "data" / "analysis"
out_dir.mkdir(parents=True, exist_ok=True)
full_df.to_csv(out_dir / "all_frames_blood_pbp_scores.csv", index=False)

print()
print("Saved:", out_dir / "all_frames_blood_pbp_scores.csv")
print("total rows:", len(full_df))
print("n cases:", full_df["case_id"].nunique())
