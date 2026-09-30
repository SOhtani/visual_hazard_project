import pandas as pd
from pathlib import Path

VH = Path(r"C:\Users\SOhtani2024\visual_hazard_project")
excluded_case = "20260810-115510-or03-ch1-hd"

quality = pd.read_csv(VH / "reports" / "phase05_neo_vs_reference_quality" / "neo_case_reference_percentiles_long.csv")
color = pd.read_csv(VH / "reports" / "phase05_neo_vs_reference_color" / "color_neo_case_reference_percentiles_long.csv")

print("=== structural_visibility_loss_v1 : all 5 cases, all stats ===")
q = quality[quality["metric"] == "structural_visibility_loss_v1"]
print(q[["case_id", "case_stat", "reference_case_percentile"]].to_string(index=False))
print()

q_p90 = q[q["case_stat"] == "p90"]
q_p99 = q[q["case_stat"] == "p99"]
print("structural p90: n=5 mean=%.1f median=%.1f" % (q_p90["reference_case_percentile"].mean(), q_p90["reference_case_percentile"].median()))
q_p90_n4 = q_p90[q_p90["case_id"] != excluded_case]
print("structural p90: n=4 mean=%.1f median=%.1f" % (q_p90_n4["reference_case_percentile"].mean(), q_p90_n4["reference_case_percentile"].median()))
print("structural p99: n=5 mean=%.1f median=%.1f" % (q_p99["reference_case_percentile"].mean(), q_p99["reference_case_percentile"].median()))
q_p99_n4 = q_p99[q_p99["case_id"] != excluded_case]
print("structural p99: n=4 mean=%.1f median=%.1f" % (q_p99_n4["reference_case_percentile"].mean(), q_p99_n4["reference_case_percentile"].median()))
print()

print("=== blood_like_redness_ratio_v1 : all 5 cases ===")
c1 = color[color["metric"] == "blood_like_redness_ratio_v1"]
print(c1[["case_id", "case_stat", "reference_case_percentile"]].to_string(index=False))
c1_p90 = c1[c1["case_stat"] == "p90"]
c1_p99 = c1[c1["case_stat"] == "p99"]
print("redness p90: n=5 mean=%.1f  n=4 mean=%.1f" % (c1_p90["reference_case_percentile"].mean(), c1_p90[c1_p90["case_id"] != excluded_case]["reference_case_percentile"].mean()))
print("redness p99: n=5 mean=%.1f  n=4 mean=%.1f" % (c1_p99["reference_case_percentile"].mean(), c1_p99[c1_p99["case_id"] != excluded_case]["reference_case_percentile"].mean()))
print()

print("=== red_saturation_mean_v1 : all 5 cases ===")
c2 = color[color["metric"] == "red_saturation_mean_v1"]
print(c2[["case_id", "case_stat", "reference_case_percentile"]].to_string(index=False))
c2_p90 = c2[c2["case_stat"] == "p90"]
c2_p99 = c2[c2["case_stat"] == "p99"]
print("red_saturation p90: n=5 mean=%.1f  n=4 mean=%.1f" % (c2_p90["reference_case_percentile"].mean(), c2_p90[c2_p90["case_id"] != excluded_case]["reference_case_percentile"].mean()))
print("red_saturation p99: n=5 mean=%.1f  n=4 mean=%.1f" % (c2_p99["reference_case_percentile"].mean(), c2_p99[c2_p99["case_id"] != excluded_case]["reference_case_percentile"].mean()))