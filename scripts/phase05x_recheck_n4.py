import pandas as pd
from pathlib import Path

VH = Path(r"C:\Users\SOhtani2024\visual_hazard_project")
excluded_case = "20260810-115510-or03-ch1-hd"

quality = pd.read_csv(VH / "reports" / "phase05_neo_vs_reference_quality" / "neo_case_reference_percentiles_long.csv")
color = pd.read_csv(VH / "reports" / "phase05_neo_vs_reference_color" / "color_neo_case_reference_percentiles_long.csv")

print("=== quality columns ===")
print(list(quality.columns))
print()
print("=== color columns ===")
print(list(color.columns))
print()

print("=== quality: structural_visibility_loss_v1 percentile rank, n=5 vs n=4 (excluded case dropped) ===")
q_sub = quality[quality["metric"] == "structural_visibility_loss_v1"]
q5 = q_sub.groupby("case_stat")["reference_case_percentile"].agg(["mean", "median", "count"])
q4 = q_sub[q_sub["case_id"] != excluded_case].groupby("case_stat")["reference_case_percentile"].agg(["mean", "median", "count"])
print("--- n=5 (all) ---")
print(q5)
print("--- n=4 (excluded case dropped) ---")
print(q4)
print()

print("=== color: key redness metrics percentile rank, n=5 vs n=4 ===")
key_metrics = ["blood_like_redness_ratio_v1", "red_saturation_mean_v1", "red_dominance_ratio_v1", "dark_red_brown_candidate_ratio_v1"]
for m in key_metrics:
    c_sub = color[color["metric"] == m]
    c5 = c_sub.groupby("case_stat")["reference_case_percentile"].agg(["mean", "median", "count"])
    c4 = c_sub[c_sub["case_id"] != excluded_case].groupby("case_stat")["reference_case_percentile"].agg(["mean", "median", "count"])
    print("---", m, "n=5 ---")
    print(c5)
    print("---", m, "n=4 ---")
    print(c4)
    print()

print("=== raw per-case values for structural_visibility_loss_v1 (to see individual cases) ===")
print(q_sub[["case_id", "case_stat", "reference_case_percentile"]].to_string(index=False))